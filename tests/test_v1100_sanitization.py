"""spec-v1.10.0 T1/T2: inbound sanitisation and outbound text.

REQ-V1100-SAN-01 (pin only), REQ-V1100-SAN-02 (the UTF-16 inbound cap),
REQ-V1100-OUT-01 (`reply_parts`: redact before split, at all five call
sites) and REQ-V1100-OUT-02 (no `parse_mode`/`entities`, ever -- "satisfied
by design", pinned rather than implemented). See `docs/spec/spec-v1.10.0.md`
sec.3 and sec.12.
"""

import inspect
import itertools
import json

import httpx
import pytest

import bot
import config
from llm.base import LLMResponse
from tests.fakes import FakeLLM, FakeTelegram, RecordingRunner, mock_llm_transport

TOKEN = "123456789:sentinel-telegram-token-for-v1100-tests"
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
        "lmstudio_model": "m",
        "openrouter_api_key": "",
        "openrouter_model": "",
        "llm_timeout_s": 120.0,
        "exec_workdir": tmp_path / "sandbox",
        "db_path": tmp_path / "bot.db",
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


def process(conn, cfg, upd, *, tg=None, llm=None, skills=None, runner=None, **kwargs):
    tg = tg if tg is not None else FakeTelegram()
    llm = llm if llm is not None else FakeLLM([])
    runner = runner if runner is not None else RecordingRunner()
    bot.process_update(
        upd,
        conn=conn,
        tg=tg,
        cfg=cfg,
        llm=llm,
        skills={} if skills is None else skills,
        runner=runner,
        bot_username=BOT_USERNAME,
        **kwargs,
    )
    return tg, llm, runner


def counts(conn):
    return (
        conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
    )


# --------------------------------------------------------------------------
# T-V1100-SAN-01: whitespace-only text is a non-text message (pin only).
# --------------------------------------------------------------------------


def test_t_v1100_san_01_whitespace_only_is_non_text(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    tg, llm, _runner = process(conn, cfg, update(text="   \n\t "))
    assert tg.sent == [(USER_ID, bot.NON_TEXT_REPLY)]
    assert llm.calls == []
    assert counts(conn) == (0, 0)


# --------------------------------------------------------------------------
# T-V1100-SAN-02: the inbound cap counts UTF-16 code units, not code points.
# --------------------------------------------------------------------------


def test_t_v1100_san_02_astral_boundary_rejected(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    text = "\U0001f600" * 2001  # 4,002 UTF-16 units
    tg, llm, _runner = process(conn, cfg, update(text=text))
    assert tg.sent == [(USER_ID, bot.TOO_LONG_REPLY)]
    assert llm.calls == []
    assert counts(conn) == (0, 0)


def test_t_v1100_san_02_astral_boundary_passes(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    text = "\U0001f600" * 2000  # 4,000 UTF-16 units, exactly at the cap
    llm = FakeLLM([LLMResponse("ok", [], "stop")])
    tg, llm, _runner = process(conn, cfg, update(text=text), llm=llm)
    assert tg.sent == [(USER_ID, "ok")]
    assert len(llm.calls) == 1


def test_t_v1100_san_02_utf16_length_agrees_with_split_message(conn, tmp_path):
    # A `len`-based width rule would pack all 4093 characters of the first
    # part (they fit under 4096 *characters*), missing that each emoji costs
    # two UTF-16 units. `utf16_length` must agree with `split_message`'s own
    # rule: the first part is tight at exactly 4,096 *units*, not characters.
    mixed = ("a" * 4090) + ("\U0001f600" * 10) + ("b" * 4000)
    parts = bot.split_message(mixed)
    assert "".join(parts) == mixed
    assert len(parts[0]) == 4093
    assert bot.utf16_length(parts[0]) == bot.MESSAGE_LIMIT
    assert all(bot.utf16_length(part) <= bot.MESSAGE_LIMIT for part in parts)
    assert sum(bot.utf16_length(part) for part in parts) == bot.utf16_length(mixed)


# --------------------------------------------------------------------------
# T-V1100-SAN-03: the BMP boundary, and the over-length message consumes no
# rate-limit token.
# --------------------------------------------------------------------------


def test_t_v1100_san_03_bmp_boundary_passes(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    llm = FakeLLM([LLMResponse("ok", [], "stop")])
    tg, llm, _runner = process(conn, cfg, update(text="z" * 4000), llm=llm)
    assert tg.sent == [(USER_ID, "ok")]
    assert len(llm.calls) == 1


def test_t_v1100_san_03_bmp_boundary_rejected(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    tg, llm, _runner = process(conn, cfg, update(text="z" * 4001))
    assert tg.sent == [(USER_ID, bot.TOO_LONG_REPLY)]
    assert llm.calls == []
    assert counts(conn) == (0, 0)


def test_t_v1100_san_03_over_length_message_consumes_no_rate_limit_token(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    limiter = bot.RateLimiter(1, 6.0, clock=lambda: 1000.0)
    tg, _llm, _runner = process(conn, cfg, update(text="z" * 4001), limiter=limiter)
    assert tg.sent == [(USER_ID, bot.TOO_LONG_REPLY)]

    llm = FakeLLM([LLMResponse("ok", [], "stop")])
    tg, llm, _runner = process(
        conn, cfg, update(text="short", update_id=2), llm=llm, limiter=limiter
    )
    assert tg.sent == [(USER_ID, "ok")]


# --------------------------------------------------------------------------
# T-V1100-OUT-01: `reply_parts` redacts before it splits.
# --------------------------------------------------------------------------


def test_t_v1100_out_01_empty_text_is_no_parts():
    assert bot.reply_parts("") == []


def test_t_v1100_out_01_rejoins_exactly_with_no_secrets():
    text = "c" * 10000
    parts = bot.reply_parts(text)
    assert "".join(parts) == text


def test_t_v1100_out_01_redacts_a_registered_secret_before_splitting():
    canary = "CANARY-" + "Q" * 17  # 24 chars, well above MIN_SECRET_LENGTH
    config.register_secret(canary)
    text = ("f" * 5000) + canary + ("g" * 5000)
    parts = bot.reply_parts(text)
    assert all(canary not in part for part in parts)
    assert sum(part.count(config.REDACTION) for part in parts) == 1


def test_t_v1100_out_01_secret_straddling_the_boundary_is_gone_before_split():
    # The geometry `reply_parts` exists for: the canary sits exactly where a
    # split-then-redact bug (`split_message(text)` instead of
    # `split_message(redact(text))`) would cut it in half, leaking its first
    # six characters into part 0 unredacted. Redact-before-split means the
    # canary is gone entirely before any boundary is drawn, so no fragment of
    # it -- not even a prefix -- reaches either part.
    canary = "CANARY-" + "Z" * 17  # 24 chars
    config.register_secret(canary)
    text = ("f" * 4090) + canary + ("g" * 5000)
    parts = bot.reply_parts(text)
    assert all(canary not in part for part in parts)
    assert canary[:6] not in parts[0]  # the leak signature under split-then-redact
    assert "".join(parts).count(config.REDACTION) == 1


def test_t_v1100_out_01_send_still_redacts_a_part_reply_parts_never_saw():
    """`_send`'s own per-part `redact` call (defence in depth, `bot.py:1500-1511`)
    stays load-bearing on its own, independent of `reply_parts` -- v11's
    `v11-send-redacts` mutation entry defends exactly this line. Before
    REQ-V1100-OUT-01, every text reaching `_send` was hand-split and
    already unredacted, so that mutation's kill came from a caller reaching
    `_send` directly; since every production call site now routes through
    `reply_parts` first (which already redacts), a part built by hand and
    passed straight to `_send` -- bypassing `reply_parts` entirely, the
    way `_send`'s own signature (`parts: list[str]`) allows any caller to
    -- is this codebase's only remaining path that exercises `_send`'s
    redaction independently of `reply_parts`'s. Removing `_send`'s own
    `redact(part)` call must still leak this canary."""
    canary = "CANARY-" + "S" * 17  # 24 chars
    config.register_secret(canary)
    tg = FakeTelegram()
    ok = bot._send(tg, 1, [f"before {canary} after"])
    assert ok is True
    assert canary not in tg.sent[0][1]
    assert config.REDACTION in tg.sent[0][1]


# --------------------------------------------------------------------------
# T-V1100-OUT-02: negative, end to end -- a secret straddling the 4,096-unit
# boundary never survives intact in the sent parts.
# --------------------------------------------------------------------------


def test_t_v1100_out_02_secret_straddling_the_split_boundary_never_leaks(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    sentinel = "CANARY-" + "R" * 17  # 24 chars
    config.register_secret(sentinel)
    reply_text = ("x" * 4090) + sentinel + ("y" * 4000)
    llm = FakeLLM([LLMResponse(reply_text, [], "stop")])
    tg, _llm, _runner = process(conn, cfg, update(), llm=llm)

    assert len(tg.sent) == 2
    parts = [text for _chat_id, text in tg.sent]
    assert all(sentinel not in part for part in parts)
    for first, second in itertools.pairwise(parts):
        assert sentinel not in (first + second)
    joined = "".join(parts)
    assert joined.count(config.REDACTION) == 1


# --------------------------------------------------------------------------
# T-V1100-OUT-03: source-level -- `split_message(` occurs exactly twice.
# --------------------------------------------------------------------------


def test_t_v1100_out_03_split_message_used_only_inside_reply_parts():
    import pathlib

    bot_source = pathlib.Path(bot.__file__).read_text(encoding="utf-8")
    assert bot_source.count("split_message(") == 2
    def_index = bot_source.index("def split_message(")
    reply_parts_index = bot_source.index("def reply_parts(")
    # The two occurrences are the `def` line itself and the call inside
    # `reply_parts`'s body.
    first = bot_source.index("split_message(")
    second = bot_source.index("split_message(", first + 1)
    assert first == def_index + len("def ")
    assert reply_parts_index < second
    outside_reply_parts_def = bot_source.count("reply_parts(") - bot_source.count(
        "def reply_parts("
    )
    assert outside_reply_parts_def >= 5


# --------------------------------------------------------------------------
# T-V1100-OUT-04: the sendMessage payload is exactly {chat_id, text} through
# the real `TelegramClient`, and the send-payload builder's own source
# carries neither `parse_mode` nor `entities` (REQ-V1100-OUT-02).
# --------------------------------------------------------------------------


def tg_client(handler, token=TOKEN):
    return bot.TelegramClient(token, client=httpx.Client(transport=mock_llm_transport(handler)))


def test_t_v1100_out_04_send_payload_is_exactly_chat_id_and_text():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    tg_client(handler).send_message(USER_ID, "hello *_[world]_*")

    assert len(requests) == 1
    request = requests[0]
    assert request.url.path.endswith("/sendMessage")
    body = json.loads(request.content)
    assert set(body) == {"chat_id", "text"}
    assert "parse_mode" not in body
    assert "entities" not in body


def test_t_v1100_out_04_send_message_source_has_no_parse_mode_or_entities():
    # Sliced to just this one method's source (never the whole repository --
    # OUT-02's pin is on the send-payload builder, not on `bot.py` at large).
    source = inspect.getsource(bot.TelegramClient.send_message)
    assert "parse_mode" not in source
    assert "entities" not in source


# --------------------------------------------------------------------------
# T-V1100-OUT-05: MarkdownV2 specials and unbalanced markup are delivered
# verbatim, byte-equal -- no `parse_mode`, so nothing is ever escaped,
# rejected, or otherwise reinterpreted (OUT-02, assignment row 3 by design).
# --------------------------------------------------------------------------


def test_t_v1100_out_05_markdownv2_specials_delivered_verbatim(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    reply_text = "_*[](){}~`>#+-=|.! *bold [link](x ```unterminated fence\nstill open"
    llm = FakeLLM([LLMResponse(reply_text, [], "stop")])
    tg, _llm, _runner = process(conn, cfg, update(), llm=llm)
    assert tg.sent == [(USER_ID, reply_text)]
