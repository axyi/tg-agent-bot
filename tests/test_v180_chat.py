"""spec-v1.8.0 T2 (docs/spec/spec-v1.8.0.md §4, REQ-V180-CHAT-01..-04, -08
items 1/3/4/5; -07's outcome contract is proved here too): `delete_message`
on the Telegram client, delete-on-success / edit-to-`STATUS_FAILED`-on-failure
for `_StatusMessage.finish`, the `AgentOutcome` / `run_agent_outcome` split,
and the reordered `process_update` call site.

T3 (REQ-V180-CHAT-05, -08 step 2) adds `_TypingIndicator` below and wires it
into the same call site; `T-V180-CHAT-09`/`-10` above are re-run against that
change, unmodified, as part of this file's suite.
"""

import inspect
import json
import logging
import threading

import httpx
import pytest

import agent
import bot
import storage
from llm.base import LLMError, LLMResponse, ToolCall
from tests.fakes import FakeLLM, RecordingRunner, mock_llm_transport
from tests.test_v1_guardrails import USER_ID, make_cfg, process, update

NOW = "2026-09-09T00:00:00Z"
EXEC_ARGS = '{"argv": ["true"]}'


def _tool_response(content=""):
    return LLMResponse(content, [ToolCall("call_0", "exec", EXEC_ARGS)], "tool_calls")


def _answer(content="done"):
    return LLMResponse(content, [], "stop")


def _tg_client(handler, token="123456789:sentinel-chat-test-token"):
    return bot.TelegramClient(token, client=httpx.Client(transport=mock_llm_transport(handler)))


# ---------------------------------------------------------------------------
# T-V180-CHAT-01 -- TelegramClient.delete_message
# ---------------------------------------------------------------------------


def test_t_v180_chat_01_delete_message_posts_delete_message_via_retry():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": True})

    result = _tg_client(handler).delete_message(424242, 1)
    assert result is True
    request = seen[0]
    assert request.url.path.endswith("/deleteMessage")
    assert json.loads(request.read()) == {"chat_id": 424242, "message_id": 1}


def test_t_v180_chat_01_delete_message_raises_telegram_error_on_fatal_result():
    def handler(request):
        return httpx.Response(401, text="Unauthorized")

    with pytest.raises(bot.TelegramError) as raised:
        _tg_client(handler).delete_message(424242, 1)
    assert raised.value.fatal is True


# ---------------------------------------------------------------------------
# T-V180-CHAT-02 / -03 -- `_StatusMessage.finish(*, ok: bool)`
# ---------------------------------------------------------------------------


class _StatusTg:
    """Records sends/edits/deletes; `delete_message` can be scripted to
    return a non-`True` result or raise, for the failed-delete cases."""

    def __init__(self, *, delete_result=True, delete_error=None, edit_error=None):
        self.sent = []
        self.edits = []
        self.deleted = []
        self._delete_result = delete_result
        self._delete_error = delete_error
        self._edit_error = edit_error

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))
        return {"message_id": 1}

    def edit_message_text(self, chat_id, message_id, text):
        if self._edit_error is not None:
            raise self._edit_error
        self.edits.append((chat_id, message_id, text))
        return {"message_id": message_id}

    def delete_message(self, chat_id, message_id):
        if self._delete_error is not None:
            raise self._delete_error
        self.deleted.append((chat_id, message_id))
        return self._delete_result


def _started_status(tg):
    """A `_StatusMessage` with a message already in flight, and no edit
    recorded yet -- `on_tool` with a name outside `("exec", "fetch")` starts
    the message without emitting the exec-line edit."""
    status = bot._StatusMessage(tg, 424242)
    status.on_tool("other", "x")
    assert status._message_id == 1
    return status


def test_t_v180_chat_02_finish_ok_true_deletes_and_clears_message_id():
    tg = _StatusTg(delete_result=True)
    status = _started_status(tg)
    status.finish(ok=True)
    assert tg.deleted == [(424242, 1)]
    assert tg.edits == []
    assert status._message_id is None


@pytest.mark.parametrize("bad_result", [False, {"ok": True}, None])
def test_t_v180_chat_02_finish_ok_true_failed_delete_leaves_message_and_id(bad_result, caplog):
    tg = _StatusTg(delete_result=bad_result)
    status = _started_status(tg)
    with caplog.at_level(logging.WARNING):
        status.finish(ok=True)
    assert tg.deleted == [(424242, 1)]
    assert tg.edits == []
    assert status._message_id == 1
    # A failed delete is not an exception: the whole status message is not
    # disabled over it (only this one delete attempt is given up on).
    assert status._disabled is False
    assert any("status message delete failed" in r.getMessage() for r in caplog.records)


def test_t_v180_chat_03_finish_ok_false_edits_status_failed_and_keeps_message():
    tg = _StatusTg()
    status = _started_status(tg)
    status.finish(ok=False)
    assert tg.edits == [(424242, 1, bot.STATUS_FAILED)]
    assert tg.deleted == []
    assert status._message_id == 1


def test_t_v180_chat_03_status_done_removed_from_bot_namespace():
    assert not hasattr(bot, "STATUS_DONE")


def test_t_v180_chat_03_status_failed_under_max_chars():
    assert bot.STATUS_FAILED == "⚠️ failed"
    assert len(bot.STATUS_FAILED) <= bot.STATUS_MAX_CHARS


# ---------------------------------------------------------------------------
# T-V180-CHAT-04 -- `run_agent` is a one-line wrapper over `run_agent_outcome`
# ---------------------------------------------------------------------------


def test_t_v180_chat_04_run_agent_signature_and_return_type_unchanged():
    sig = inspect.signature(agent.run_agent)
    assert list(sig.parameters) == [
        "conn",
        "conv_id",
        "llm",
        "skills",
        "runner",
        "now",
        "sleep",
        "cfg",
        "fetcher",
        "audit",
        "recent_goals",
        "should_stop",
        "on_tool",
        "resolve_cost",
    ]
    assert sig.return_annotation is str


def test_t_v180_chat_04_run_agent_returns_exactly_the_outcomes_reply(conn, monkeypatch):
    captured = []
    real_run_agent_outcome = agent.run_agent_outcome

    def spy(**kwargs):
        outcome = real_run_agent_outcome(**kwargs)
        captured.append(outcome)
        return outcome

    monkeypatch.setattr(agent, "run_agent_outcome", spy)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hi")
    reply = agent.run_agent(
        conn=conn,
        conv_id=conv,
        llm=FakeLLM([_answer("hello there")]),
        skills={},
        runner=RecordingRunner(),
        now=NOW,
        sleep=lambda s: None,
    )
    assert len(captured) == 1
    assert isinstance(captured[0], agent.AgentOutcome)
    assert reply == captured[0].reply == "hello there"


# ---------------------------------------------------------------------------
# T-V180-CHAT-08 -- the outcome contract, per fallback return path
# ---------------------------------------------------------------------------


def _outcome(conn, script, *, should_stop=None):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    kwargs = {} if should_stop is None else {"should_stop": should_stop}
    return agent.run_agent_outcome(
        conn=conn,
        conv_id=conv,
        llm=FakeLLM(script),
        skills={},
        runner=RecordingRunner(),
        now=NOW,
        sleep=lambda s: None,
        **kwargs,
    )


def test_t_v180_chat_08_answer_path_is_not_failed(conn):
    outcome = _outcome(conn, [_answer("the answer")])
    assert outcome == agent.AgentOutcome(reply="the answer", failed=False, kind=None)


def test_t_v180_chat_08_interrupted(conn):
    outcome = _outcome(conn, [], should_stop=lambda: True)
    assert outcome == agent.AgentOutcome(
        reply=agent.FALLBACK_INTERRUPTED, failed=True, kind="interrupted"
    )


def test_t_v180_chat_08_llm_error(conn):
    outcome = _outcome(conn, [LLMError("llm http 400: bad", retryable=False)])
    assert outcome == agent.AgentOutcome(
        reply=agent.FALLBACK_LLM_ERROR.format(reason="llm http 400: bad"),
        failed=True,
        kind="llm_error",
    )


def test_t_v180_chat_08_empty(conn):
    outcome = _outcome(conn, [_answer(""), _answer("")])
    assert outcome == agent.AgentOutcome(reply=agent.FALLBACK_EMPTY, failed=True, kind="empty")


def test_t_v180_chat_08_no_answer(conn):
    script = [_tool_response() for _ in range(agent.ROUND_LIMIT)]
    outcome = _outcome(conn, script)
    assert outcome == agent.AgentOutcome(
        reply=agent.FALLBACK_NO_ANSWER, failed=True, kind="no_answer"
    )


# ---------------------------------------------------------------------------
# T-V180-CHAT-09 -- negative: the reply send raises
# ---------------------------------------------------------------------------


class _ReplyFailsTg:
    """`STATUS_WORKING` sends succeed; every other send (the reply) raises."""

    def __init__(self):
        self.edits = []
        self.deleted = []

    def send_message(self, chat_id, text):
        if text == bot.STATUS_WORKING:
            return {"message_id": 1}
        raise bot.TelegramError("telegram sendMessage http 500")

    def edit_message_text(self, chat_id, message_id, text):
        self.edits.append((chat_id, message_id, text))
        return {"message_id": message_id}

    def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))
        return True


def test_t_v180_chat_09_reply_send_failure_keeps_status_failed_no_delete(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    tg = _ReplyFailsTg()
    process(
        conn,
        cfg,
        update(text="hi", update_id=1),
        tg=tg,
        llm=FakeLLM([_tool_response(), _answer("final answer")]),
        runner=RecordingRunner(),
    )
    assert tg.deleted == []
    assert tg.edits[-1] == (USER_ID, 1, bot.STATUS_FAILED)


class _RaisingLLM:
    """One scripted response, then a bare (non-`LLMError`) exception -- the
    kind that escapes `run_agent_outcome` entirely, per the spec's "the
    paths that really do raise" (`finish`'s transactional write is one;
    a raw provider-library exception is another). `FakeLLM` cannot express
    this: it only raises what its script hands it, and a scripted `LLMError`
    is caught and turned into a fallback, never left to propagate."""

    def __init__(self, first_response):
        self._first = first_response
        self.calls = 0

    def describe(self):
        return ("fake", "fake-model")

    def complete(
        self, messages, tool_definitions, *, max_tokens=None, reasoning=None, timeout_s=None
    ):
        self.calls += 1
        if self.calls == 1:
            return self._first
        raise RuntimeError("boom")


def test_t_v180_chat_09_exception_escaping_run_agent_outcome_marks_failed_and_reraises(
    conn, tmp_path
):
    cfg = make_cfg(tmp_path)
    tg = _ReplyFailsTg()
    llm = _RaisingLLM(_tool_response())
    with pytest.raises(RuntimeError, match="boom"):
        process(conn, cfg, update(text="hi", update_id=2), tg=tg, llm=llm, runner=RecordingRunner())
    assert tg.deleted == []
    assert tg.edits[-1] == (USER_ID, 1, bot.STATUS_FAILED)


# ---------------------------------------------------------------------------
# T-V180-CHAT-10 -- the production path, both directions
# ---------------------------------------------------------------------------


class _ProductionTg:
    def __init__(self, *, delete_result=True):
        self.sent = []
        self.edits = []
        self.deleted = []
        self._delete_result = delete_result

    def send_message(self, chat_id, text):
        if text == bot.STATUS_WORKING:
            return {"message_id": 1}
        self.sent.append((chat_id, text))
        return {"message_id": 100 + len(self.sent)}

    def edit_message_text(self, chat_id, message_id, text):
        self.edits.append((chat_id, message_id, text))
        return {"message_id": message_id}

    def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))
        return self._delete_result


def test_t_v180_chat_10_successful_outcome_deletes_status_no_failed_edit(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    tg = _ProductionTg()
    tg, llm, runner = process(
        conn,
        cfg,
        update(text="hi", update_id=1),
        tg=tg,
        llm=FakeLLM([_tool_response(), _answer("final answer")]),
        runner=RecordingRunner(),
    )
    assert tg.deleted == [(USER_ID, 1)]
    assert all(text != bot.STATUS_FAILED for _chat, _mid, text in tg.edits)
    assert tg.sent == [(USER_ID, "final answer")]


def test_t_v180_chat_10_structurally_failed_outcome_marks_status_failed_no_delete(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    tg = _ProductionTg()
    tg, llm, runner = process(
        conn,
        cfg,
        update(text="hi", update_id=2),
        tg=tg,
        llm=FakeLLM([_tool_response(), LLMError("llm http 500", retryable=False)]),
        runner=RecordingRunner(),
    )
    assert tg.deleted == []
    assert tg.edits[-1] == (USER_ID, 1, bot.STATUS_FAILED)
    assert tg.sent == [(USER_ID, agent.FALLBACK_LLM_ERROR.format(reason="llm http 500"))]


# ---------------------------------------------------------------------------
# T-V180-CHAT-06 / -07 -- `_TypingIndicator` (REQ-V180-CHAT-05)
# ---------------------------------------------------------------------------


class _CallRecordingTg:
    """A `tg` stub exposing only `call`, matching what `_TypingIndicator`
    itself uses (never `_call_with_retry`, never `send_message`/`edit_...`)."""

    def __init__(self, handler=None):
        self.calls = []
        self._handler = handler

    def call(self, method, payload, **kwargs):
        self.calls.append((method, payload, kwargs))
        if self._handler is not None:
            return self._handler(method, payload, kwargs)
        return {}


class _RaisingTg:
    def __init__(self, exc):
        self.calls = []
        self._exc = exc

    def call(self, method, payload, **kwargs):
        self.calls.append((method, payload, kwargs))
        raise self._exc


class _FakeClock:
    """A scripted `monotonic()` -- returns each value in turn, then repeats
    the last one forever (so a runaway loop terminates on the ceiling
    instead of raising `StopIteration`)."""

    def __init__(self, values):
        self._values = list(values)
        self.calls = 0

    def __call__(self):
        index = min(self.calls, len(self._values) - 1)
        self.calls += 1
        return self._values[index]


_EXPECTED_TICK_KWARGS = {
    "read_timeout": bot.TYPING_REQUEST_TIMEOUT_S,
    "connect_timeout": bot.TYPING_REQUEST_TIMEOUT_S,
    "write_timeout": bot.TYPING_REQUEST_TIMEOUT_S,
    "pool_timeout": bot.TYPING_REQUEST_TIMEOUT_S,
}


def test_t_v180_chat_06_sends_immediately_then_one_per_tick_until_ceiling():
    tg = _CallRecordingTg()
    clock = _FakeClock([0.0, 1.0, 2.0, 20.0])  # deadline = 0.0 + ceiling_s(10.0)
    indicator = bot._TypingIndicator(
        tg,
        424242,
        ceiling_s=10.0,
        interval_s=0.0,
        monotonic=clock,
    )
    indicator.start()
    indicator._thread.join(1.0)
    assert not indicator._thread.is_alive()
    # Two ticks land (elapsed 1.0 and 2.0, both under the 10.0 ceiling); the
    # third check sees elapsed 20.0 >= ceiling and sends nothing more.
    assert len(tg.calls) == 2
    for method, payload, kwargs in tg.calls:
        assert method == "sendChatAction"
        assert payload == {"chat_id": 424242, "action": "typing"}
        assert kwargs == _EXPECTED_TICK_KWARGS
    indicator.stop()  # idempotent after a natural exit; returns promptly


def test_t_v180_chat_06_stop_event_rechecked_after_the_request_returns():
    stop_event = threading.Event()
    calls = []

    def handler(method, payload, kwargs):
        calls.append((method, payload, kwargs))
        stop_event.set()  # as if stop() fired while this request was in flight
        return {}

    tg = _CallRecordingTg(handler)
    clock = _FakeClock([0.0])  # ceiling far away: only the event should end the loop
    indicator = bot._TypingIndicator(
        tg,
        424242,
        ceiling_s=1000.0,
        interval_s=0.0,
        monotonic=clock,
        stop_event=stop_event,
    )
    indicator.start()
    indicator._thread.join(1.0)
    assert not indicator._thread.is_alive()
    assert len(tg.calls) == 1  # the in-flight request landed, nothing scheduled after it
    indicator.stop()  # idempotent, joins an already-finished thread promptly


def test_t_v180_chat_06_stop_wakes_a_worker_parked_in_the_interval_wait():
    sent = threading.Event()
    tg = _CallRecordingTg(lambda method, payload, kwargs: sent.set() or {})
    clock = _FakeClock([0.0])  # ceiling far away: only stop() should end the loop
    indicator = bot._TypingIndicator(
        tg,
        424242,
        ceiling_s=1000.0,
        interval_s=1000.0,
        monotonic=clock,
    )
    indicator.start()
    assert sent.wait(1.0)  # bounded wait for the first (immediate) send
    thread = indicator._thread
    indicator.stop()  # must wake the worker out of `wait(1000.0)` and join well inside
    assert not thread.is_alive()  # TYPING_JOIN_TIMEOUT_S (3.0)
    assert len(tg.calls) == 1  # stop() pre-empted the would-be second tick


def test_t_v180_chat_07_raising_send_chat_action_disables_indicator_only(caplog):
    tg = _RaisingTg(RuntimeError("boom"))
    clock = _FakeClock([0.0])
    indicator = bot._TypingIndicator(
        tg,
        424242,
        ceiling_s=1000.0,
        interval_s=0.0,
        monotonic=clock,
    )
    with caplog.at_level(logging.WARNING):
        indicator.start()
        indicator._thread.join(1.0)
    assert not indicator._thread.is_alive()
    assert len(tg.calls) == 1  # no retry, no second attempt after the error
    assert any("typing indicator disabled" in r.getMessage() for r in caplog.records)
    indicator.stop()  # idempotent even though the worker already disabled itself


def test_t_v180_chat_07_ceiling_s_has_no_default():
    with pytest.raises(TypeError):
        bot._TypingIndicator(_CallRecordingTg(), 424242)


def test_t_v180_chat_08_thread_start_raising_disables_indicator_without_raising(
    monkeypatch, caplog
):
    class _RaisingThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")

    monkeypatch.setattr(bot.threading, "Thread", _RaisingThread)
    tg = _CallRecordingTg()
    clock = _FakeClock([0.0])
    indicator = bot._TypingIndicator(
        tg,
        424242,
        ceiling_s=1000.0,
        interval_s=0.0,
        monotonic=clock,
    )
    with caplog.at_level(logging.WARNING):
        indicator.start()  # Thread.start() raises RuntimeError; must not propagate
    assert indicator._thread is None
    assert len(tg.calls) == 0  # the worker never ran
    assert any("typing indicator disabled" in r.getMessage() for r in caplog.records)
    indicator.stop()  # idempotent no-op: nothing was ever started
