"""spec-v1.11.0 T1: the outbound table path.

`tables.py` (`render_table`, `fit_lines`, `utf16_length`) and `bot.py`'s
`_pre_text`/`send_pre`/`edit_pre` plumbing, the two new `TelegramClient`
methods and `tests/fakes.py`'s `FakeTelegram` growth. See
`docs/spec/spec-v1.11.0.md` sec.3 (REQ-V1110-OUT-01..05).
"""

import html
import inspect
import json
import random

import httpx
import pytest

import bot
import config
import tables
from tests.fakes import FakeLLM, FakeTelegram, RecordingRunner, mock_llm_transport
from tests.test_v1100_sanitization import (
    test_t_v1100_out_04_send_message_source_has_no_parse_mode_or_entities,
    test_t_v1100_out_04_send_payload_is_exactly_chat_id_and_text,
    test_t_v1100_out_05_markdownv2_specials_delivered_verbatim,
)

TOKEN = "123456789:sentinel-telegram-token-for-v1110-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"
ASTRAL = "\U0001f600"


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


def tg_client(handler, token=TOKEN):
    return bot.TelegramClient(token, client=httpx.Client(transport=mock_llm_transport(handler)))


# --------------------------------------------------------------------------
# T-V1110-OUT-01: render_table -- properties over 200 generated row sets,
# plus the explicit truncation / ValueError / raw-text edge cases.
# --------------------------------------------------------------------------


def _ref_truncate(text, width):
    if width is None or tables.utf16_length(text) <= width:
        return text
    budget = width - 1
    kept: list[str] = []
    used = 0
    for char in text:
        w = 2 if ord(char) > 0xFFFF else 1
        if used + w > budget:
            break
        kept.append(char)
        used += w
    return "".join(kept) + "…"


def _ref_render_table(headers, rows, *, align=None, max_width=None):
    """An independent reference implementation of REQ-V1110-OUT-03, written
    straight from the spec text -- not copied from `tables.render_table`."""
    n = len(headers)
    str_rows = [["n/a" if v is None else str(v) for v in row] for row in rows]
    if max_width is not None:
        for row in str_rows:
            for c in range(n):
                w = max_width[c] if c < len(max_width) else None
                row[c] = _ref_truncate(row[c], w)

    aligns = []
    for c in range(n):
        forced = align[c] if align is not None and c < len(align) else None
        if forced:
            aligns.append(forced)
            continue
        vals = [row[c] for row in rows if row[c] is not None]
        numeric = bool(vals) and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals
        )
        aligns.append("r" if numeric else "l")

    widths = [
        max([tables.utf16_length(headers[c])] + [tables.utf16_length(r[c]) for r in str_rows])
        for c in range(n)
    ]

    def pad(text, width, alignment):
        gap = width - tables.utf16_length(text)
        if gap <= 0:
            return text
        return (" " * gap + text) if alignment == "r" else (text + " " * gap)

    lines = ["  ".join(pad(headers[c], widths[c], aligns[c]) for c in range(n))]
    lines.append("  ".join("-" * widths[c] for c in range(n)))
    lines.extend("  ".join(pad(row[c], widths[c], aligns[c]) for c in range(n)) for row in str_rows)
    return "\n".join(lines)


def _random_row_set(rng):
    n_cols = rng.randint(2, 4)
    n_rows = rng.randint(1, 6)
    kinds = [rng.choice(["num", "text"]) for _ in range(n_cols)]
    headers = [f"H{i}" for i in range(n_cols)]
    rows = []
    for _ in range(n_rows):
        row = []
        for kind in kinds:
            if rng.random() < 0.15:
                row.append(None)
            elif kind == "num":
                row.append(
                    rng.randint(-1000, 100000)
                    if rng.random() < 0.5
                    else round(rng.uniform(-1000, 1000), 3)
                )
            else:
                pick = rng.random()
                if pick < 0.2:
                    row.append(ASTRAL * rng.randint(1, 4))
                elif pick < 0.4:
                    row.append("w" * rng.randint(20, 60))
                else:
                    row.append("".join(rng.choice("abcXYZ_ ") for _ in range(rng.randint(0, 30))))
        rows.append(row)
    for c in range(n_cols):
        if all(row[c] is None for row in rows):
            rows[0][c] = 0 if kinds[c] == "num" else "x"
    max_width = [rng.randint(4, 12) for _ in range(n_cols)]
    return headers, rows, max_width


def test_t_v1110_out_01_render_table_properties_and_width_ceiling():
    rng = random.Random(111001)
    for _ in range(200):
        headers, rows, max_width = _random_row_set(rng)
        expected = _ref_render_table(headers, rows, max_width=max_width)
        actual = tables.render_table(headers, rows, max_width=max_width)
        assert actual == expected

        lines = actual.split("\n")
        assert not actual.endswith("\n")
        line_lengths = {tables.utf16_length(line) for line in lines}
        assert len(line_lengths) == 1
        assert line_lengths.pop() <= 72
        # the rule line is ASCII '-' per column, joined by the same two-space
        # separator as every other row -- never U+2500, never anything else.
        assert all(set(segment) == {"-"} for segment in lines[1].split("  "))

    # None -> "n/a"
    out = tables.render_table(["a", "b"], [[None, 1], [2, None]])
    body_lines = out.split("\n")[2:]
    assert "n/a" in body_lines[0]
    assert "n/a" in body_lines[1]

    # truncation: astral-safe, exact, guarantees the max_width contract
    wide = ASTRAL * 5 + "tail"
    out = tables.render_table(["h"], [[wide]], max_width=[5])
    cell = out.split("\n")[2]
    assert cell == ASTRAL * 2 + "…"
    assert tables.utf16_length(cell) <= 5

    # width > 72 raises ValueError
    with pytest.raises(ValueError):
        tables.render_table(["h"], [["x" * 100]])

    # raw, unescaped text -- _pre_text/send_pre do the escaping, not this
    out = tables.render_table(["h"], [["<b>&here</b>"]], max_width=[40])
    assert "<b>&here</b>" in out


# --------------------------------------------------------------------------
# T-V1110-OUT-02: send_pre's payload shape and the escape-then-wrap contract.
# --------------------------------------------------------------------------


def test_t_v1110_out_02_send_pre_payload_and_escape():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    tg = tg_client(handler)
    result = bot.send_pre(tg, USER_ID, "before <script>&\nafter")

    assert len(requests) == 1
    request = requests[0]
    assert request.url.path.endswith("/sendMessage")
    body = json.loads(request.content)
    assert set(body) == {"chat_id", "text", "parse_mode"}
    assert body["chat_id"] == USER_ID
    assert body["parse_mode"] == "HTML"
    text = body["text"]
    assert text.startswith("<pre>")
    assert text.endswith("</pre>")
    assert "&lt;script&gt;&amp;" in text
    assert result == {"message_id": 7}

    # payload invariant (OUT-03): no body-supplied literal <, >, & inside
    # <pre>...</pre>, only the trusted tags and generated entities.
    inner = text[len("<pre>") : -len("</pre>")]
    assert "<" not in inner
    assert ">" not in inner
    for fragment in inner.split("&")[1:]:
        assert fragment.startswith(("amp;", "lt;", "gt;"))

    markup = {"inline_keyboard": [[{"text": "x", "callback_data": "y"}]]}
    bot.send_pre(tg, USER_ID, "hi", reply_markup=markup)
    assert len(requests) == 2
    body2 = json.loads(requests[1].content)
    assert set(body2) == {"chat_id", "text", "parse_mode", "reply_markup"}
    assert body2["reply_markup"] == markup


# --------------------------------------------------------------------------
# T-V1110-OUT-03: redact before fit, fit before escape (negative).
# --------------------------------------------------------------------------


def test_t_v1110_out_03_redact_before_escape():
    # (a) a registered sentinel secret containing '<' on a retained line.
    sentinel = "CANARY-" + "L" * 10 + "<" + "M" * 10
    config.register_secret(sentinel)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    tg = tg_client(handler)
    bot.send_pre(tg, USER_ID, f"line one\n{sentinel}\nline three")
    body = json.loads(requests[0].content)
    assert sentinel not in body["text"]
    assert config.REDACTION in body["text"]

    # (b) the sentinel's redacted length shifts the retained-line boundary:
    # `_pre_text` called directly on the sentinel line vs. a neutral line of
    # the same raw length -- the retained lines differ exactly as
    # redact-before-fit predicts (redact shrinks 27 raw chars to REDACTION's
    # 14, pulling the joined body back under the 4096-unit limit).
    filler = "F" * 4069
    sentinel2 = "CANARY-" + "S" * 20  # 27 raw chars
    neutral = "N" * len(sentinel2)  # same raw length, not a registered secret
    config.register_secret(sentinel2)

    _text_s, fitted_s = bot._pre_text(filler + "\n" + sentinel2)
    _text_n, fitted_n = bot._pre_text(filler + "\n" + neutral)

    assert fitted_n == filler + "\n… 1 more"
    assert fitted_s == filler + "\n" + config.REDACTION
    assert sentinel2 not in fitted_s


# --------------------------------------------------------------------------
# T-V1110-OUT-04: fit_lines over send_pre at the 4096-unit boundary.
# --------------------------------------------------------------------------


def test_t_v1110_out_04_fit_lines_at_4096_units():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    tg = tg_client(handler)

    # a 4097-unit body, built with '&' so the raw (entity-parsed) length,
    # never the escaped-HTML-string length, governs the fit.
    line_a = "&" * 800
    body = "\n".join([line_a] * 5 + ["&" * 92])
    assert bot.utf16_length(body) == 4097

    bot.send_pre(tg, USER_ID, body)
    assert len(requests) == 1
    sent_text = json.loads(requests[0].content)["text"]
    expected_fitted = "\n".join([line_a] * 5) + "\n… 1 more"
    assert sent_text == "<pre>" + html.escape(expected_fitted, quote=False) + "</pre>"

    # a 4096-unit body is sent unfitted
    requests.clear()
    body_4096 = "&" * 4096
    bot.send_pre(tg, USER_ID, body_4096)
    sent_text = json.loads(requests[0].content)["text"]
    assert sent_text == "<pre>" + html.escape(body_4096, quote=False) + "</pre>"

    # a trailing newline is dropped
    requests.clear()
    bot.send_pre(tg, USER_ID, "line1\nline2\n")
    sent_text = json.loads(requests[0].content)["text"]
    assert sent_text == "<pre>line1\nline2</pre>"


# --------------------------------------------------------------------------
# T-V1110-OUT-05: the one-time plain fallback on a table-path 400 (negative).
# --------------------------------------------------------------------------


def test_t_v1110_out_05_plain_fallback_once_on_400():
    # (a) the first sendMessage 400s, the plain fallback succeeds.
    calls = []

    def handler_400_then_ok(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(400, json={"ok": False})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 2}})

    tg = tg_client(handler_400_then_ok)
    result = bot.send_pre(tg, USER_ID, "hello")
    assert len(calls) == 2
    second_body = json.loads(calls[1].content)
    assert set(second_body) == {"chat_id", "text"}
    assert second_body["text"] == "hello"
    assert result == {"message_id": 2}

    # (b) a 4097-unit body's HTML request forced to 400 -> the fallback
    # carries the same fitted body, never the original.
    calls2 = []

    def handler_400_then_ok2(request):
        calls2.append(request)
        if len(calls2) == 1:
            return httpx.Response(400, json={"ok": False})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 3}})

    tg2 = tg_client(handler_400_then_ok2)
    line_a = "&" * 800
    body = "\n".join([line_a] * 5 + ["&" * 92])
    bot.send_pre(tg2, USER_ID, body)
    assert len(calls2) == 2
    fallback_body = json.loads(calls2[1].content)
    expected_fitted = "\n".join([line_a] * 5) + "\n… 1 more"
    assert fallback_body["text"] == expected_fitted
    assert fallback_body["text"] != body
    assert "parse_mode" not in fallback_body

    # (c) two 400s -> exactly two requests, send_pre returns None.
    calls3 = []

    def handler_always_400(request):
        calls3.append(request)
        return httpx.Response(400, json={"ok": False})

    tg3 = tg_client(handler_always_400)
    result3 = bot.send_pre(tg3, USER_ID, "hello")
    assert len(calls3) == 2
    assert result3 is None

    # (d) a fatal 401 skips the fallback entirely -- a bad token is not a
    # payload problem a plain resend could fix (bot.py:154-198's
    # classification stands unchanged, REQ-V1110-OUT-04).
    calls4 = []

    def handler_401(request):
        calls4.append(request)
        return httpx.Response(401, json={"ok": False})

    tg4 = tg_client(handler_401)
    result4 = bot.send_pre(tg4, USER_ID, "hello")
    assert len(calls4) == 1
    assert result4 is None


# --------------------------------------------------------------------------
# T-V1110-OUT-06: the agent-reply path is unchanged (negative).
# --------------------------------------------------------------------------


def test_t_v1110_out_06_agent_reply_path_unchanged(conn, tmp_path):
    sig = inspect.signature(bot.TelegramClient.send_message)
    assert list(sig.parameters) == ["self", "chat_id", "text"]

    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    tg_client(handler).send_message(USER_ID, "hello")
    assert len(requests) == 1
    posted = json.loads(requests[0].content)
    assert set(posted) == {"chat_id", "text"}

    cfg = make_cfg(tmp_path)
    tg, _llm, _runner = process(conn, cfg, update(text="/status", update_id=101))
    assert tg.sent
    assert all("parse_mode" not in payload for payload in tg.sent_payloads)

    tg2, _llm2, _runner2 = process(conn, cfg, update(text="/summary", update_id=102))
    assert tg2.sent
    assert all("parse_mode" not in payload for payload in tg2.sent_payloads)

    # T-V1100-OUT-04/-05 stay green, unamended (imported, called directly --
    # tests/test_v1103_gates.py's own precedent for this pattern).
    test_t_v1100_out_04_send_payload_is_exactly_chat_id_and_text()
    test_t_v1100_out_04_send_message_source_has_no_parse_mode_or_entities()
    test_t_v1100_out_05_markdownv2_specials_delivered_verbatim(conn, tmp_path)


# --------------------------------------------------------------------------
# T-V1110-OUT-07: FakeTelegram grows compatibly.
# --------------------------------------------------------------------------


def test_t_v1110_out_07_fake_telegram_grows_compatibly():
    tg = FakeTelegram()

    tg.send_message(USER_ID, "plain")
    tg.send_message_html(USER_ID, "<pre>html</pre>", reply_markup={"inline_keyboard": []})
    assert tg.sent == [(USER_ID, "plain"), (USER_ID, "<pre>html</pre>")]
    assert tg.sent_payloads[0] == {"chat_id": USER_ID, "text": "plain"}
    assert tg.sent_payloads[1] == {
        "chat_id": USER_ID,
        "text": "<pre>html</pre>",
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": []},
    }

    tg.edit_message_text(USER_ID, 5, "plain edit")
    tg.edit_message_html(USER_ID, 6, "<pre>edit</pre>")
    assert tg.edited_payloads[0] == {"chat_id": USER_ID, "message_id": 5, "text": "plain edit"}
    assert tg.edited_payloads[1] == {
        "chat_id": USER_ID,
        "message_id": 6,
        "text": "<pre>edit</pre>",
        "parse_mode": "HTML",
    }

    tg.answer_callback_query("cbq1", text="ok")
    assert tg.callback_answers == [{"callback_query_id": "cbq1", "text": "ok"}]

    tg.set_my_commands([{"command": "help", "description": "help text"}])
    assert tg.commands_set == [[{"command": "help", "description": "help text"}]]

    tg.fail_html_with = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        tg.send_message_html(USER_ID, "<pre>x</pre>")
    assert tg.fail_html_with is None
    tg.send_message_html(USER_ID, "<pre>y</pre>")  # succeeds now, not scripted any more
    assert tg.sent[-1] == (USER_ID, "<pre>y</pre>")


# --------------------------------------------------------------------------
# T-V1110-OUT-08: edit_pre -- hostile and 4097-unit bodies (negative).
# --------------------------------------------------------------------------


def test_t_v1110_out_08_edit_pre_hostile_and_4097_unit_bodies():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    tg = tg_client(handler)
    result = bot.edit_pre(tg, USER_ID, 42, "before <script>&\nafter")
    assert len(requests) == 1
    request = requests[0]
    assert request.url.path.endswith("/editMessageText")
    body = json.loads(request.content)
    assert set(body) == {"chat_id", "message_id", "text", "parse_mode"}
    assert body["message_id"] == 42
    text = body["text"]
    assert text.startswith("<pre>")
    assert text.endswith("</pre>")
    assert "&lt;script&gt;&amp;" in text
    assert result == {"message_id": 42}

    markup = {"inline_keyboard": [[{"text": "x", "callback_data": "y"}]]}
    bot.edit_pre(tg, USER_ID, 42, "hi", reply_markup=markup)
    body2 = json.loads(requests[1].content)
    assert set(body2) == {"chat_id", "message_id", "text", "parse_mode", "reply_markup"}
    assert body2["reply_markup"] == markup

    # 4097-unit fitted / 4096-unit unfitted
    requests.clear()
    line_a = "&" * 800
    body_4097 = "\n".join([line_a] * 5 + ["&" * 92])
    bot.edit_pre(tg, USER_ID, 42, body_4097)
    sent_text = json.loads(requests[0].content)["text"]
    expected_fitted = "\n".join([line_a] * 5) + "\n… 1 more"
    assert sent_text == "<pre>" + html.escape(expected_fitted, quote=False) + "</pre>"

    requests.clear()
    body_4096 = "&" * 4096
    bot.edit_pre(tg, USER_ID, 42, body_4096)
    sent_text = json.loads(requests[0].content)["text"]
    assert sent_text == "<pre>" + html.escape(body_4096, quote=False) + "</pre>"

    # 400 -> two requests, the second a plain editMessageText w/o parse_mode
    calls = []

    def handler_400_then_ok(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(400, json={"ok": False})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    tg2 = tg_client(handler_400_then_ok)
    result2 = bot.edit_pre(tg2, USER_ID, 42, "hello")
    assert len(calls) == 2
    second = json.loads(calls[1].content)
    assert set(second) == {"chat_id", "message_id", "text"}
    assert second["text"] == "hello"
    assert result2 == {"message_id": 42}

    # two 400s -> no third request, None
    calls2 = []

    def handler_always_400(request):
        calls2.append(request)
        return httpx.Response(400, json={"ok": False})

    tg3 = tg_client(handler_always_400)
    result3 = bot.edit_pre(tg3, USER_ID, 42, "hello")
    assert len(calls2) == 2
    assert result3 is None

    # a fatal 401 skips the fallback entirely, same rule as send_pre
    calls3 = []

    def handler_401(request):
        calls3.append(request)
        return httpx.Response(401, json={"ok": False})

    tg4 = tg_client(handler_401)
    result4 = bot.edit_pre(tg4, USER_ID, 42, "hello")
    assert len(calls3) == 1
    assert result4 is None

    # send_pre/edit_pre share _pre_text
    assert "_pre_text" in inspect.getsource(bot.send_pre)
    assert "_pre_text" in inspect.getsource(bot.edit_pre)
