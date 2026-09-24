"""spec-v1.11.1 T1: the plain fallback narrowed to HTTP 400 only.

`TelegramError.status`, `TelegramClient.call`'s status-tagging on every
response-driven raise, and `send_pre`/`edit_pre`'s 400-only fallback
predicate. See `docs/spec/spec-v1.11.1.md` sec.3.1 (REQ-V1111-OUT-01,
REQ-V1111-OUT-02).
"""

import json
import logging

import httpx
import pytest

import bot
import tables
from tests.fakes import mock_llm_transport

TOKEN = "123456789:sentinel-telegram-token-for-v1111-tests"
USER_ID = 424242
MESSAGE_ID = 99


@pytest.fixture(autouse=True)
def reset_shutdown(monkeypatch):
    monkeypatch.setattr(bot, "_shutdown", False)


def tg_client(handler, sleeps=None):
    return bot.TelegramClient(
        TOKEN,
        client=httpx.Client(transport=mock_llm_transport(handler)),
        sleep=(sleeps.append if sleeps is not None else (lambda s: None)),
    )


def _error_lines(caplog, fragment):
    return [r for r in caplog.records if r.levelno == logging.ERROR and fragment in r.getMessage()]


# --------------------------------------------------------------------------
# T-V1111-OUT-01: TelegramClient.call sets TelegramError.status from the
# response on every response-driven raise, leaves it None on transport.
# --------------------------------------------------------------------------


def test_t_v1111_out_01_status_set_from_response():
    # 400 -> status set, not fatal.
    tg = tg_client(lambda request: httpx.Response(400, json={"ok": False}))
    with pytest.raises(bot.TelegramError) as excinfo:
        tg.call("sendMessage", {}, read_timeout=5.0)
    assert excinfo.value.status == 400
    assert excinfo.value.fatal is False

    # 401 -> fatal, status set.
    tg = tg_client(lambda request: httpx.Response(401, json={"ok": False}))
    with pytest.raises(bot.TelegramError) as excinfo:
        tg.call("sendMessage", {}, read_timeout=5.0)
    assert excinfo.value.status == 401
    assert excinfo.value.fatal is True

    # 429 with retry_after 0 -> status and retry_after both set.
    def handler_429(request):
        return httpx.Response(
            429,
            json={
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 0},
            },
        )

    tg = tg_client(handler_429)
    with pytest.raises(bot.TelegramError) as excinfo:
        tg.call("sendMessage", {}, read_timeout=5.0)
    assert excinfo.value.status == 429
    assert excinfo.value.retry_after == 0.0

    # 500 -> status set.
    tg = tg_client(lambda request: httpx.Response(500, json={"ok": False}))
    with pytest.raises(bot.TelegramError) as excinfo:
        tg.call("sendMessage", {}, read_timeout=5.0)
    assert excinfo.value.status == 500

    # A transport error -> status stays None, transport True.
    def handler_transport(request):
        raise httpx.ConnectError("down")

    tg = tg_client(handler_transport)
    with pytest.raises(bot.TelegramError) as excinfo:
        tg.call("sendMessage", {}, read_timeout=5.0)
    assert excinfo.value.status is None
    assert excinfo.value.transport is True

    # 200 with {"ok": false} -> status is the HTTP status, 200.
    tg = tg_client(lambda request: httpx.Response(200, json={"ok": False}))
    with pytest.raises(bot.TelegramError) as excinfo:
        tg.call("sendMessage", {}, read_timeout=5.0)
    assert excinfo.value.status == 200


# --------------------------------------------------------------------------
# T-V1111-OUT-02: the plain fallback fires only on status == 400, for both
# send_pre and edit_pre; a failure of the fallback itself never chains into
# a second fallback.
# --------------------------------------------------------------------------


def test_t_v1111_out_02_fallback_on_400_send_and_edit(caplog):
    _, fitted = bot._pre_text("hello")

    # send_pre: 400 then 200 -> exactly two requests, the second plain.
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(400, json={"ok": False})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 2}})

    result = bot.send_pre(tg_client(handler), USER_ID, "hello")
    assert len(calls) == 2
    second = json.loads(calls[1].content)
    assert set(second) == {"chat_id", "text"}
    assert second["text"] == fitted
    assert result == {"message_id": 2}

    # edit_pre: same shape.
    calls2 = []

    def handler2(request):
        calls2.append(request)
        if len(calls2) == 1:
            return httpx.Response(400, json={"ok": False})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 3}})

    result2 = bot.edit_pre(tg_client(handler2), USER_ID, MESSAGE_ID, "hello")
    assert len(calls2) == 2
    second2 = json.loads(calls2[1].content)
    assert set(second2) == {"chat_id", "message_id", "text"}
    assert second2["text"] == fitted
    assert result2 == {"message_id": 3}

    # send_pre: second failure is a 5xx -- exactly two requests total, the
    # second without parse_mode, no sleep, one ERROR line, None returned.
    calls3 = []
    sleeps3 = []

    def handler3(request):
        calls3.append(request)
        if len(calls3) == 1:
            return httpx.Response(400, json={"ok": False})
        return httpx.Response(500, json={"ok": False})

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        result3 = bot.send_pre(tg_client(handler3, sleeps3), USER_ID, "hello")
    assert len(calls3) == 2
    assert "parse_mode" not in json.loads(calls3[1].content)
    assert sleeps3 == []
    assert result3 is None
    assert len(_error_lines(caplog, "sending the reply failed")) == 1

    # edit_pre: the same 400-then-5xx shape.
    calls4 = []
    sleeps4 = []

    def handler4(request):
        calls4.append(request)
        if len(calls4) == 1:
            return httpx.Response(400, json={"ok": False})
        return httpx.Response(500, json={"ok": False})

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        result4 = bot.edit_pre(tg_client(handler4, sleeps4), USER_ID, MESSAGE_ID, "hello")
    assert len(calls4) == 2
    assert "parse_mode" not in json.loads(calls4[1].content)
    assert sleeps4 == []
    assert result4 is None
    assert len(_error_lines(caplog, "editing the reply failed")) == 1

    # send_pre: second failure is persistent transport -- exactly
    # 1 + SEND_ATTEMPT_LIMIT requests: one HTML, SEND_ATTEMPT_LIMIT plain,
    # every plain one without parse_mode and the same fitted text,
    # SEND_ATTEMPT_LIMIT - 1 sleeps, one ERROR line, None returned.
    calls5 = []
    sleeps5 = []

    def handler5(request):
        calls5.append(request)
        if len(calls5) == 1:
            return httpx.Response(400, json={"ok": False})
        raise httpx.ConnectError("down")

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        result5 = bot.send_pre(tg_client(handler5, sleeps5), USER_ID, "hello")
    assert len(calls5) == 1 + bot.SEND_ATTEMPT_LIMIT
    first_payload = json.loads(calls5[0].content)
    assert first_payload.get("parse_mode") == "HTML"
    for req in calls5[1:]:
        payload = json.loads(req.content)
        assert "parse_mode" not in payload
        assert payload["text"] == fitted
    assert sleeps5 == [bot.SEND_TRANSPORT_SLEEP_S] * (bot.SEND_ATTEMPT_LIMIT - 1)
    assert result5 is None
    assert len(_error_lines(caplog, "sending the reply failed")) == 1

    # edit_pre: the same 400-then-persistent-transport shape.
    calls6 = []
    sleeps6 = []

    def handler6(request):
        calls6.append(request)
        if len(calls6) == 1:
            return httpx.Response(400, json={"ok": False})
        raise httpx.ConnectError("down")

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        result6 = bot.edit_pre(tg_client(handler6, sleeps6), USER_ID, MESSAGE_ID, "hello")
    assert len(calls6) == 1 + bot.SEND_ATTEMPT_LIMIT
    first_payload6 = json.loads(calls6[0].content)
    assert first_payload6.get("parse_mode") == "HTML"
    for req in calls6[1:]:
        payload = json.loads(req.content)
        assert "parse_mode" not in payload
        assert payload["text"] == fitted
    assert sleeps6 == [bot.SEND_TRANSPORT_SLEEP_S] * (bot.SEND_ATTEMPT_LIMIT - 1)
    assert result6 is None
    assert len(_error_lines(caplog, "editing the reply failed")) == 1


# --------------------------------------------------------------------------
# T-V1111-OUT-03: a 429 that outlives _call_with_retry's own budget never
# triggers the plain fallback.
# --------------------------------------------------------------------------


def test_t_v1111_out_03_no_fallback_on_429_after_budget(caplog):
    attempts = []
    sleeps = []

    def handler(request):
        attempts.append(request)
        return httpx.Response(
            429,
            json={
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 0},
            },
        )

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        result = bot.send_pre(tg_client(handler, sleeps), USER_ID, "hello")

    assert result is None
    assert len(attempts) == bot.SEND_ATTEMPT_LIMIT
    for req in attempts:
        assert json.loads(req.content).get("parse_mode") == "HTML"
    assert sleeps == [1.0] * (bot.SEND_ATTEMPT_LIMIT - 1)
    assert len(_error_lines(caplog, "sending the reply failed")) == 1


# --------------------------------------------------------------------------
# T-V1111-OUT-04: a 5xx or a persistent transport failure never triggers the
# plain fallback, for both send_pre and edit_pre.
# --------------------------------------------------------------------------


def test_t_v1111_out_04_no_fallback_on_5xx_or_transport(caplog):
    # send_pre, a 500 -> one request, None.
    calls = []

    def handler500(request):
        calls.append(request)
        return httpx.Response(500, json={"ok": False})

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        result = bot.send_pre(tg_client(handler500), USER_ID, "hello")
    assert len(calls) == 1
    assert result is None
    assert len(_error_lines(caplog, "sending the reply failed")) == 1

    # send_pre, a persistent transport failure -> SEND_ATTEMPT_LIMIT HTML
    # requests, no plain resend, None.
    calls2 = []
    sleeps2 = []

    def handler_transport(request):
        calls2.append(request)
        raise httpx.ConnectError("down")

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        result2 = bot.send_pre(tg_client(handler_transport, sleeps2), USER_ID, "hello")
    assert len(calls2) == bot.SEND_ATTEMPT_LIMIT
    for req in calls2:
        assert json.loads(req.content).get("parse_mode") == "HTML"
    assert result2 is None
    assert len(_error_lines(caplog, "sending the reply failed")) == 1

    # edit_pre, a 500 -> one request, None.
    calls3 = []

    def handler500b(request):
        calls3.append(request)
        return httpx.Response(500, json={"ok": False})

    caplog.clear()
    with caplog.at_level(logging.ERROR):
        result3 = bot.edit_pre(tg_client(handler500b), USER_ID, MESSAGE_ID, "hello")
    assert len(calls3) == 1
    assert result3 is None
    assert len(_error_lines(caplog, "editing the reply failed")) == 1


# --------------------------------------------------------------------------
# T-V1111-OUT-05: the three docstrings say what the code does.
# --------------------------------------------------------------------------


def test_t_v1111_out_05_docstrings_current():
    assert "status" in bot.send_pre.__doc__
    assert "400" in bot.send_pre.__doc__
    assert "bot.py:154-198" not in bot.send_pre.__doc__

    assert "400-only" in bot.edit_pre.__doc__

    assert "bot.py:1190" not in tables.fit_lines.__doc__
    assert "_fit" not in tables.fit_lines.__doc__

    assert "cancel.is_set()" in bot.IngestJob.__doc__
    assert "read and written only" not in bot.IngestJob.__doc__
