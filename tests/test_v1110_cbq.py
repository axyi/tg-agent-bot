"""spec-v1.11.0 T4: callback queries and inline keyboards
(REQ-V1110-CBQ-01..-03).

Builds on T1's outbound table path (`tables.py`, `bot.send_pre`/`edit_pre`)
and the `FakeTelegram` growth T1 already landed (`answer_callback_query`,
`callback_answers`, `edited_payloads`). See `docs/spec/spec-v1.11.0.md`
sec.7 and `docs/spec/task-briefs/v1110-T4.md`.
"""

from __future__ import annotations

import inspect
import json
import logging
import re

import httpx
import pytest

import bot
import config
import storage
import tables
from tests.fakes import FakeLLM, FakeTelegram, RecordingRunner, mock_llm_transport

TOKEN = "123456789:sentinel-telegram-token-for-v1110-cbq-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"


@pytest.fixture(autouse=True)
def reset_shutdown(monkeypatch):
    monkeypatch.setattr(bot, "_shutdown", False)


@pytest.fixture(autouse=True)
def isolated_secret_registry():
    """`config._secrets` is process-global (see `tests/test_v1_guardrails.py`)."""
    before = set(config._secrets)
    yield
    config._secrets.clear()
    config._secrets.update(before)


def make_cfg(tmp_path, **overrides):
    fields = {
        "telegram_bot_token": TOKEN,
        "allowed_tg_ids": frozenset({USER_ID}),
        "llm_provider": "lmstudio",
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_model": "m-default",
        "lmstudio_models": ("m-default",),
        "openrouter_api_key": "sk-or-sentinel-key-value",
        "openrouter_model": "o-default",
        "openrouter_models": ("o-default", "o-alt"),
        "llm_timeout_s": 120.0,
        "exec_workdir": tmp_path / "sandbox",
        "db_path": tmp_path / "bot.db",
        "audit_log_path": tmp_path / "audit.jsonl",
    }
    fields.update(overrides)
    return config.Config(**fields)


def update(text="hello", update_id=1, user_id=USER_ID):
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False},
            "text": text,
        },
    }


def callback(
    data,
    *,
    update_id=1,
    user_id=USER_ID,
    chat_id=None,
    message_id=50,
    text="",
    callback_id="cbq1",
):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": callback_id,
            "from": {"id": user_id, "is_bot": False},
            "message": {
                "message_id": message_id,
                "date": 0,
                "chat": {"id": chat_id if chat_id is not None else user_id, "type": "private"},
                "text": text,
            },
            "chat_instance": "ci1",
            "data": data,
        },
    }


def process(
    conn, cfg, upd, *, tg=None, llm=None, skills=None, runner=None, limiter=None, set_provider=None
):
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
        limiter=limiter,
        set_provider=set_provider,
    )
    return tg, llm, runner


def tg_client(handler, token=TOKEN):
    return bot.TelegramClient(token, client=httpx.Client(transport=mock_llm_transport(handler)))


def bot_state_rows(conn):
    return {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM bot_state")}


# --------------------------------------------------------------------------
# T-V1110-CBQ-01 -- allowed_updates gains callback_query; the branch is hit
# before the message-only guard.
# --------------------------------------------------------------------------


def test_t_v1110_cbq_01_allowed_updates_and_callback_branch(conn, tmp_path, monkeypatch, caplog):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": []})

    tg_client(handler).get_updates(41)
    body = json.loads(seen[0].read())
    assert body == {"timeout": 50, "allowed_updates": ["message", "callback_query"], "offset": 41}

    cfg = make_cfg(tmp_path)
    calls = []

    def spy(callback_query, **kwargs):
        calls.append(callback_query)

    monkeypatch.setattr(bot, "_handle_callback", spy)
    upd = callback("mod:prov:lmstudio")
    with caplog.at_level(logging.INFO):
        bot.process_update(
            upd,
            conn=conn,
            tg=FakeTelegram(),
            cfg=cfg,
            llm=FakeLLM([]),
            skills={},
            runner=RecordingRunner(),
            bot_username=BOT_USERNAME,
        )
    assert len(calls) == 1
    assert calls[0]["data"] == "mod:prov:lmstudio"
    assert "carries no message" not in caplog.text


# --------------------------------------------------------------------------
# T-V1110-CBQ-02 -- an intruder's callback: one bare ack, nothing else
# (negative).
# --------------------------------------------------------------------------


def test_t_v1110_cbq_02_intruder_callback_one_ack(conn, tmp_path, caplog):
    cfg = make_cfg(tmp_path)
    intruder_id = USER_ID + 999
    upd = callback("mod:prov:lmstudio", user_id=intruder_id, chat_id=intruder_id, update_id=7)
    before = bot_state_rows(conn)
    tg = FakeTelegram()
    llm = FakeLLM([])
    with caplog.at_level(logging.WARNING):
        bot.process_update(
            upd,
            conn=conn,
            tg=tg,
            cfg=cfg,
            llm=llm,
            skills={},
            runner=RecordingRunner(),
            bot_username=BOT_USERNAME,
        )
    assert tg.callback_answers == [{"callback_query_id": "cbq1"}]
    assert tg.sent_payloads == []
    assert tg.edited_payloads == []
    after = bot_state_rows(conn)
    after.pop("last_update_id", None)
    before.pop("last_update_id", None)
    assert after == before
    assert storage.get_state(conn, "last_update_id") == "7"
    assert llm.calls == []
    assert caplog.text.count("unauthorized update") == 1


# --------------------------------------------------------------------------
# T-V1110-CBQ-03 -- the other guards: group chat / bot sender / chat-from
# mismatch (no answer at all); rate limiter (acked with RATE_LIMIT_REPLY);
# cursor written first, nothing else touched (negative).
# --------------------------------------------------------------------------


def test_t_v1110_cbq_03_callback_guards_and_cursor(conn, tmp_path):
    cfg = make_cfg(tmp_path)

    upd = callback("mod:prov:lmstudio", update_id=1)
    upd["callback_query"]["message"]["chat"]["type"] = "group"
    tg = FakeTelegram()
    process(conn, cfg, upd, tg=tg)
    assert tg.callback_answers == []
    assert storage.get_state(conn, "last_update_id") == "1"

    upd2 = callback("mod:prov:lmstudio", update_id=2)
    upd2["callback_query"]["from"]["is_bot"] = True
    tg2 = FakeTelegram()
    process(conn, cfg, upd2, tg=tg2)
    assert tg2.callback_answers == []
    assert storage.get_state(conn, "last_update_id") == "2"

    upd3 = callback("mod:prov:lmstudio", update_id=3, chat_id=USER_ID + 1)
    tg3 = FakeTelegram()
    process(conn, cfg, upd3, tg=tg3)
    assert tg3.callback_answers == []
    assert storage.get_state(conn, "last_update_id") == "3"

    upd4 = callback("mod:prov:lmstudio", update_id=4)
    tg4 = FakeTelegram()
    limiter = bot.RateLimiter(0, 60.0)
    process(conn, cfg, upd4, tg=tg4, limiter=limiter)
    assert tg4.callback_answers == [{"callback_query_id": "cbq1", "text": bot.RATE_LIMIT_REPLY}]
    assert tg4.sent_payloads == []
    assert tg4.edited_payloads == []
    assert storage.get_state(conn, "last_update_id") == "4"

    assert set(bot_state_rows(conn)) == {"last_update_id"}


# --------------------------------------------------------------------------
# T-V1110-CBQ-04 -- ack once, first, before any other Telegram call.
# --------------------------------------------------------------------------


def test_t_v1110_cbq_04_ack_once_first(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    order = []
    orig_ack = tg.answer_callback_query
    orig_edit = tg.edit_message_html

    def tracked_ack(*a, **k):
        order.append("ack")
        return orig_ack(*a, **k)

    def tracked_edit(*a, **k):
        order.append("edit")
        return orig_edit(*a, **k)

    tg.answer_callback_query = tracked_ack
    tg.edit_message_html = tracked_edit

    process(conn, cfg, callback("mod:prov:lmstudio"), tg=tg)
    assert order == ["ack", "edit"]
    assert tg.callback_answers == [{"callback_query_id": "cbq1"}]
    assert len(tg.edited_payloads) == 1


# --------------------------------------------------------------------------
# T-V1110-CBQ-05 -- stale/malformed callback_data: Expired, zero state
# change (negative).
# --------------------------------------------------------------------------


def test_t_v1110_cbq_05_stale_and_malformed_data(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    catalogue = cfg.lmstudio_models
    digest = bot._catalogue_hash(catalogue)
    header = f"Models for lmstudio:\n0. {catalogue[0]}"

    cases = [
        "zzz:prov:x",
        "mod:zzz:1",
        f"mod:model:x:{digest}",
        f"mod:model:99:{digest}",
        f"mod:model:-1:{digest}",
        "mod:model:1",
        "mod:model:1:zzzzzzzz",
        "ses:switch:1",
        "A" * 65,
        f"mod:model:１:{digest}",
        "mod:model:1 OR 1=1",
        "ses:switch:../x",
    ]
    for i, data in enumerate(cases):
        before = bot_state_rows(conn)
        tg = FakeTelegram()
        installed = []
        process(
            conn,
            cfg,
            callback(data, text=header, update_id=100 + i),
            tg=tg,
            set_provider=installed.append,
        )
        assert tg.callback_answers[-1] == {
            "callback_query_id": "cbq1",
            "text": bot.CALLBACK_EXPIRED_REPLY,
        }, data
        assert tg.edited_payloads == [], data
        assert installed == [], data
        after = bot_state_rows(conn)
        after.pop("last_update_id", None)
        before.pop("last_update_id", None)
        assert after == before, data

    # a provider that is not configured
    bare_cfg = make_cfg(tmp_path, openrouter_api_key="", openrouter_model="", openrouter_models=())
    tg2 = FakeTelegram()
    process(conn, bare_cfg, callback("mod:prov:openrouter", update_id=200), tg=tg2)
    assert tg2.callback_answers[-1] == {
        "callback_query_id": "cbq1",
        "text": bot.CALLBACK_EXPIRED_REPLY,
    }
    assert tg2.edited_payloads == []


# --------------------------------------------------------------------------
# T-V1110-CBQ-06 -- the client methods' payload shapes; a selection edits
# the original message_id; `sent` never grows.
# --------------------------------------------------------------------------


def test_t_v1110_cbq_06_client_methods_and_same_message_edit(conn, tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": True})

    tg = tg_client(handler)
    result = tg.answer_callback_query("cbq-a")
    assert requests[-1].url.path.endswith("/answerCallbackQuery")
    assert json.loads(requests[-1].content) == {"callback_query_id": "cbq-a"}
    assert result is True

    tg.answer_callback_query("cbq-b", text="hi")
    assert json.loads(requests[-1].content) == {"callback_query_id": "cbq-b", "text": "hi"}

    cfg = make_cfg(tmp_path)
    fake = FakeTelegram()
    process(conn, cfg, update("/model"), tg=fake)
    assert len(fake.sent) == 1
    message_id = 100 + len(fake.sent)

    process(conn, cfg, callback("mod:prov:openrouter", message_id=message_id, update_id=2), tg=fake)
    assert fake.edited_payloads[-1]["message_id"] == message_id
    assert len(fake.sent) == 1

    step2_text = bot._model_step2_body(cfg, "openrouter")
    digest = bot._catalogue_hash(cfg.openrouter_models)
    process(
        conn,
        cfg,
        callback(f"mod:model:0:{digest}", text=step2_text, message_id=message_id, update_id=3),
        tg=fake,
    )
    assert fake.edited_payloads[-1]["message_id"] == message_id
    assert len(fake.sent) == 1
    assert "reply_markup" not in fake.edited_payloads[-1]


# --------------------------------------------------------------------------
# T-V1110-CBQ-07 -- the callback_data grammar and the 64-byte ceiling, even
# with a 200-char model id.
# --------------------------------------------------------------------------


_CBQ_GRAMMAR_RE = re.compile(r"^(mod|ses):[a-z]+:[A-Za-z0-9_-]+(:[0-9a-f]{8})?$")


def test_t_v1110_cbq_07_callback_data_grammar_and_64_bytes(tmp_path):
    long_id = "vendor/" + "y" * 193  # 200 chars
    cfg = make_cfg(tmp_path, openrouter_model="o-default", openrouter_models=("o-default", long_id))

    for keyboard in (bot._model_step1_keyboard(cfg), bot._model_step2_keyboard(cfg, "openrouter")):
        for row in keyboard["inline_keyboard"]:
            for button in row:
                data = button["callback_data"]
                assert data.isascii(), data
                assert len(data.encode("utf-8")) <= 64, data
                assert _CBQ_GRAMMAR_RE.match(data), data
                assert tables.utf16_length(button["text"]) <= 32, button["text"]


# --------------------------------------------------------------------------
# T-V1110-CBQ-08 -- every callback edit rides edit_pre: hostile and
# 4097-unit bodies arrive escaped/fitted; no handler names
# edit_message_html directly (negative).
# --------------------------------------------------------------------------


def test_t_v1110_cbq_08_callback_edits_ride_edit_pre(conn, tmp_path, monkeypatch):
    hostile = "<script>&"
    cfg = make_cfg(tmp_path, openrouter_model="o-default", openrouter_models=("o-default", hostile))
    fake = FakeTelegram()
    process(conn, cfg, callback("mod:prov:openrouter", update_id=1), tg=fake)
    body_text = fake.edited_payloads[-1]["text"]
    inner = body_text[len("<pre>") : -len("</pre>")]
    assert "&lt;script&gt;&amp;" in inner
    assert "<" not in inner
    assert ">" not in inner

    huge_body = "\n".join(f"line{i}" for i in range(1000))
    monkeypatch.setattr(bot, "_model_step2_body", lambda cfg, name: huge_body)
    fake2 = FakeTelegram()
    process(conn, cfg, callback("mod:prov:lmstudio", update_id=2), tg=fake2)
    edited_text = fake2.edited_payloads[-1]["text"]
    assert "more" in edited_text
    assert bot.utf16_length(edited_text) <= bot.MESSAGE_LIMIT + len("<pre></pre>")

    for name, func in inspect.getmembers(bot, inspect.isfunction):
        if func.__module__ != "bot" or name == "edit_pre":
            continue
        assert "edit_message_html" not in inspect.getsource(func), name
