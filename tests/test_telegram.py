import json
import logging

import httpx
import pytest

import bot
import config
import storage
from llm.base import LLMResponse
from tests.fakes import FakeLLM, FakeTelegram, RecordingRunner, mock_llm_transport

TOKEN = "123456789:sentinel-telegram-token-for-log-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"


@pytest.fixture(autouse=True)
def reset_shutdown(monkeypatch):
    monkeypatch.setattr(bot, "_shutdown", False)


def make_cfg(tmp_path, token=TOKEN):
    return config.Config(
        telegram_bot_token=token,
        allowed_tg_ids=frozenset({USER_ID}),
        llm_provider="lmstudio",
        lmstudio_base_url="http://localhost:1234/v1",
        lmstudio_model="m",
        openrouter_api_key="",
        openrouter_model="",
        llm_timeout_s=120.0,
        exec_workdir=tmp_path / "sandbox",
        db_path=tmp_path / "bot.db",
    )


def update(text="hello", update_id=1, user_id=USER_ID, chat_type="private", **message):
    payload = {
        "message_id": 1,
        "date": 0,
        "chat": {"id": user_id, "type": chat_type},
        "from": {"id": user_id, "is_bot": False},
        "text": text,
    }
    payload.update(message)
    return {"update_id": update_id, "message": payload}


def process(conn, cfg, upd, *, tg=None, llm=None, skills=None, runner=None):
    tg = tg if tg is not None else FakeTelegram()
    llm = llm if llm is not None else FakeLLM([])
    runner = runner if runner is not None else RecordingRunner()
    bot.process_update(
        upd,
        conn=conn,
        tg=tg,
        cfg=cfg,
        llm=llm,
        skills=skills or {},
        runner=runner,
        bot_username=BOT_USERNAME,
    )
    return tg, llm, runner


def counts(conn):
    return (
        conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
    )


def tg_client(handler, token=TOKEN):
    return bot.TelegramClient(token, client=httpx.Client(transport=mock_llm_transport(handler)))


def test_t_tg_01_unauthorized_sender(conn, tmp_path, caplog):
    cfg = make_cfg(tmp_path)
    with caplog.at_level(logging.WARNING):
        tg, llm, runner = process(conn, cfg, update(user_id=999, update_id=5))
    assert counts(conn) == (0, 0)
    assert llm.calls == []
    assert runner.argv_calls == []
    assert tg.sent == []
    assert storage.get_state(conn, "last_update_id") == "5"
    assert any("unauthorized update from tg_id=999" in r.getMessage() for r in caplog.records)


def test_t_tg_02_poison_updates(conn, tmp_path, caplog):
    cfg = make_cfg(tmp_path)
    no_message = {"update_id": 1}
    no_from = {"update_id": 2, "message": {"chat": {"id": 1, "type": "private"}, "text": "x"}}
    from_bot = update(update_id=3)
    from_bot["message"]["from"]["is_bot"] = True
    group_chat = update(update_id=4, chat_type="group")
    missing_id = {"message": {"text": "x"}}
    not_a_dict = ["nope"]

    for upd, expected_cursor in (
        (no_message, "1"),
        (no_from, "2"),
        (from_bot, "3"),
        (group_chat, "4"),
    ):
        tg, llm, runner = process(conn, cfg, upd)
        assert tg.sent == []
        assert llm.calls == []
        assert storage.get_state(conn, "last_update_id") == expected_cursor

    for upd in (missing_id, not_a_dict):
        tg, llm, runner = process(conn, cfg, upd)
        assert tg.sent == []
        assert storage.get_state(conn, "last_update_id") == "4"

    assert counts(conn) == (0, 0)

    # The chat-type rule runs before the allowlist rule, so a group message from
    # an unlisted sender is dropped as a group message, not as an intruder.
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        tg, llm, runner = process(conn, cfg, update(update_id=5, user_id=999, chat_type="group"))
    assert not any("unauthorized" in r.getMessage() for r in caplog.records)
    assert tg.sent == []


def test_t_tg_03_non_text_message(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    upd = update(update_id=9)
    del upd["message"]["text"]
    upd["message"]["photo"] = [{"file_id": "x"}]
    tg, llm, runner = process(conn, cfg, upd)
    assert tg.sent == [(USER_ID, "I can only process plain text messages.")]
    assert counts(conn) == (0, 0)
    assert llm.calls == []


def test_t_tg_04_api_error_is_distinct_from_status_error():
    def handler(request):
        return httpx.Response(200, json={"ok": False, "error_code": 400, "description": "x"})

    with pytest.raises(bot.TelegramError) as raised:
        tg_client(handler).get_me()
    assert str(raised.value) == "telegram getMe api error 400: x"
    assert raised.value.retry_after is None
    assert raised.value.fatal is False

    def status_handler(request):
        return httpx.Response(400, text="nope")

    with pytest.raises(bot.TelegramError) as other:
        tg_client(status_handler).get_me()
    assert str(other.value) == "telegram getMe http 400"


def test_t_tg_05_retry_after_beats_backoff(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    seen = []

    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(
                429,
                json={
                    "ok": False,
                    "error_code": 429,
                    "description": "Too Many Requests",
                    "parameters": {"retry_after": 7},
                },
            )
        return httpx.Response(401, text="Unauthorized")

    # The value comes out of the response body, not out of the caller.
    with pytest.raises(bot.TelegramError) as raised:
        tg_client(handler).get_updates(None)
    assert raised.value.retry_after == 7.0
    assert raised.value.fatal is False
    assert str(raised.value) == "telegram getUpdates rate limited"

    seen.clear()
    sleeps = []
    code = bot.poll_loop(
        conn=conn, tg=tg_client(handler), cfg=cfg, llm=FakeLLM([]), skills={},
        runner=RecordingRunner(), bot_username=BOT_USERNAME, sleep=sleeps.append,
    )
    assert code == 2
    assert sleeps == [8.0]      # retry_after + 1.0, never the generic backoff


def test_t_tg_06_token_never_reaches_logs_or_exceptions(conn, tmp_path, caplog):
    config.register_secret(TOKEN)

    def transport_error(request):
        raise httpx.ConnectError(f"cannot reach https://api.telegram.org/bot{TOKEN}/getMe")

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(bot.TelegramError) as raised:
            tg_client(transport_error).get_me()
        assert TOKEN not in str(raised.value)

        def api_error(request):
            return httpx.Response(
                200, json={"ok": False, "error_code": 401, "description": f"token {TOKEN} bad"}
            )

        with pytest.raises(bot.TelegramError) as other:
            tg_client(api_error).get_me()
        assert TOKEN not in str(other.value)
        assert "***REDACTED***" in str(other.value)

    for record in caplog.records:
        assert TOKEN not in record.getMessage()
        assert "api.telegram.org" not in record.getMessage()


def test_t_tg_07_split_message():
    assert bot.split_message("") == []
    assert bot.split_message("a" * 4096) == ["a" * 4096]
    parts = bot.split_message("a" * 10000)
    assert len(parts) == 3
    assert "".join(parts) == "a" * 10000
    assert all(len(p) <= 4096 for p in parts)
    astral = "\U0001f600" * 3000
    astral_parts = bot.split_message(astral)
    assert len(astral_parts) == 2
    assert len(astral_parts[0]) == 2048
    assert "".join(astral_parts) == astral


def test_t_tg_08_new_command(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    first = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, first, "earlier")

    for i, text in enumerate(("/new", "/new@ThisBot", "/new keep this", " /NEW "), start=10):
        tg, llm, runner = process(conn, cfg, update(text=text, update_id=i))
        assert tg.sent == [(USER_ID, "New conversation started.")]
        assert llm.calls == []
    active = conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE tg_user_id = ? AND active = 1", (USER_ID,)
    ).fetchone()[0]
    assert active == 1
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 5

    tg, llm, runner = process(conn, cfg, update(text="/new@OtherBot", update_id=20))
    assert tg.sent == []
    assert llm.calls == []
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 5

    stored = conn.execute("SELECT content FROM messages").fetchall()
    assert [r["content"] for r in stored] == ["earlier"]


def test_t_tg_09_get_updates_request_shape():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": []})

    tg_client(handler).get_updates(41)
    request = seen[0]
    assert request.url.path.endswith("/getUpdates")
    body = json.loads(request.read())
    assert body == {"timeout": 50, "allowed_updates": ["message"], "offset": 41}
    timeout = request.extensions["timeout"]
    assert timeout["read"] == 60.0
    assert timeout["read"] > body["timeout"]
    assert timeout["connect"] == 10.0

    seen.clear()
    tg_client(handler).get_updates(None)
    assert "offset" not in json.loads(seen[0].read())


def test_t_tg_10_partial_delivery(conn, tmp_path, caplog):
    cfg = make_cfg(tmp_path)
    long_answer = "x" * 9000
    tg = FakeTelegram(fail_on=2, error=bot.TelegramError("telegram sendMessage http 500"))
    with caplog.at_level(logging.ERROR):
        tg, llm, runner = process(
            conn, cfg, update(update_id=3), tg=tg,
            llm=FakeLLM([LLMResponse(long_answer, [], "stop")]),
        )
    assert len(tg.sent) == 1
    assert tg.send_calls == 2
    assert any("telegram sendMessage http 500" in r.getMessage() for r in caplog.records)
    assert storage.get_state(conn, "last_update_id") == "3"


def test_t_tg_11_at_most_once(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram(fail_on=1, error=bot.TelegramError("telegram sendMessage http 500"))
    process(conn, cfg, update(update_id=77), tg=tg,
            llm=FakeLLM([LLMResponse("lost reply", [], "stop")]))
    assert tg.sent == []
    assert storage.get_state(conn, "last_update_id") == "77"

    offsets = []

    class Restarted:
        def get_updates(self, offset):
            offsets.append(offset)
            raise bot.TelegramError("telegram getUpdates rejected the bot token", fatal=True)

    second_llm = FakeLLM([])
    code = bot.poll_loop(
        conn=conn, tg=Restarted(), cfg=cfg, llm=second_llm, skills={},
        runner=RecordingRunner(), bot_username=BOT_USERNAME, sleep=lambda s: None,
    )
    assert code == 2
    assert offsets == [78]
    assert second_llm.calls == []
    stored = conn.execute("SELECT content FROM messages ORDER BY id").fetchall()
    assert [r["content"] for r in stored] == ["hello", "lost reply"]


def test_t_tg_12_fatal_token_error(conn, tmp_path):
    cfg = make_cfg(tmp_path)

    def handler(request):
        return httpx.Response(401, text="Unauthorized")

    code = bot.poll_loop(
        conn=conn, tg=tg_client(handler), cfg=cfg, llm=FakeLLM([]), skills={},
        runner=RecordingRunner(), bot_username=BOT_USERNAME, sleep=lambda s: None,
    )
    assert code == 2
