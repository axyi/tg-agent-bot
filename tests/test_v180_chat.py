"""spec-v1.8.0 T2 (docs/spec/spec-v1.8.0.md §4, REQ-V180-CHAT-01..-04, -08
items 1/3/4/5; -07's outcome contract is proved here too): `delete_message`
on the Telegram client, delete-on-success / edit-to-`STATUS_FAILED`-on-failure
for `_StatusMessage.finish`, the `AgentOutcome` / `run_agent_outcome` split,
and the reordered `process_update` call site.

No typing indicator here: `_TypingIndicator` and step 2 of REQ-V180-CHAT-08's
ordering are T3's (REQ-V180-CHAT-05), not this task's.
"""

import inspect
import json
import logging

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
        "conn", "conv_id", "llm", "skills", "runner", "now", "sleep", "cfg",
        "fetcher", "audit", "recent_goals", "should_stop", "on_tool", "resolve_cost",
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
        conn=conn, conv_id=conv, llm=FakeLLM([_answer("hello there")]),
        skills={}, runner=RecordingRunner(), now=NOW, sleep=lambda s: None,
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
        conn=conn, conv_id=conv, llm=FakeLLM(script), skills={},
        runner=RecordingRunner(), now=NOW, sleep=lambda s: None, **kwargs,
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
        failed=True, kind="llm_error",
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
        conn, cfg, update(text="hi", update_id=1), tg=tg,
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

    def complete(self, messages, tool_definitions, *, max_tokens=None, reasoning=None,
                 timeout_s=None):
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
        process(conn, cfg, update(text="hi", update_id=2), tg=tg, llm=llm,
                runner=RecordingRunner())
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
        conn, cfg, update(text="hi", update_id=1), tg=tg,
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
        conn, cfg, update(text="hi", update_id=2), tg=tg,
        llm=FakeLLM([_tool_response(), LLMError("llm http 500", retryable=False)]),
        runner=RecordingRunner(),
    )
    assert tg.deleted == []
    assert tg.edits[-1] == (USER_ID, 1, bot.STATUS_FAILED)
    assert tg.sent == [(USER_ID, agent.FALLBACK_LLM_ERROR.format(reason="llm http 500"))]
