"""Observability layer — spec-v1.3 sections 6.1-6.2 (REQ-V13-OBS-01…09).

Everything here is offline: no Docker, no network, no real provider. The only
secrets used are synthetic canaries registered through `config.register_secret`.
"""

import json
import logging
import sqlite3

import httpx
import pytest

import agent
import bot
import config
import metrics
import storage
from llm.base import (
    REQUEST_DEFAULTS,
    LLMError,
    LLMResponse,
    ToolCall,
    Usage,
    build_payload,
    parse_response,
    parse_usage,
)
from llm.failover import FAILOVER_THRESHOLD, FailoverLLMClient
from llm.lmstudio import LMStudioClient
from llm.openrouter import OpenRouterClient
from tests.fakes import FakeLLM, RecordingRunner

NOW = "2026-09-02T10:00:00Z"
USER_ID = 424242
TOKEN = "123456789:sentinel-telegram-token-for-observability-tests"
BOT_USERNAME = "ThisBot"
EXEC_ARGS = '{"argv": ["uname", "-a"]}'

# A version-2 database on disk, written literally: `storage.init_schema` now
# emits v3, so it cannot be used to build the fixture the migration is fed.
V2_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 2);

CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER NOT NULL,
    created_at TEXT    NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id         INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn_id         INTEGER NOT NULL,
    role            TEXT    NOT NULL,
    content         TEXT    NOT NULL DEFAULT '',
    tool_calls_json TEXT,
    tool_call_id    TEXT,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id      INTEGER NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
    tg_user_id   INTEGER NOT NULL,
    created_at   TEXT    NOT NULL,
    summary_json TEXT    NOT NULL
);
"""


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def body(message, usage=None, finish_reason="stop"):
    payload = {"choices": [{"message": message, "finish_reason": finish_reason}]}
    if usage is not None:
        payload["usage"] = usage
    return payload


def capture_payloads():
    """An httpx transport that records every request body and answers minimally."""
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=body({"content": "ok"}))

    return seen, httpx.MockTransport(handler)


class NamedLLM:
    """A client with `describe()`; replays a scripted list like `FakeLLM`."""

    def __init__(self, provider, model, script=()):
        self.provider = provider
        self.model = model
        self.script = list(script)
        self.calls = []

    def complete(self, messages, tools, *, max_tokens=None):
        self.calls.append((list(messages), tools))
        item = self.script.pop(0) if self.script else LLMResponse("ok", [], "stop")
        if isinstance(item, LLMError):
            raise item
        return item

    def describe(self):
        return (self.provider, self.model)


def tool_call(index=1, name="exec", arguments=EXEC_ARGS):
    return ToolCall(f"call_{index}", name, arguments)


def run(conn, script, *, skills=None, runner=None, user="hello", resolve_cost=None, llm=None):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, user)
    llm = llm if llm is not None else FakeLLM(script)
    runner = runner if runner is not None else RecordingRunner()
    reply = agent.run_agent(
        conn=conn,
        conv_id=conv,
        llm=llm,
        skills=skills or {},
        runner=runner,
        now=NOW,
        sleep=lambda _seconds: None,
        resolve_cost=resolve_cost,
    )
    return reply, llm, conv


def llm_rows(conn):
    return conn.execute("SELECT * FROM llm_calls ORDER BY id").fetchall()


def tool_rows(conn):
    return conn.execute("SELECT * FROM tool_calls ORDER BY id").fetchall()


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
        "db_path": tmp_path / "test.db",
        "audit_log_path": tmp_path / "exec_audit.jsonl",
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


class RecordingTelegram:
    def __init__(self):
        self.sent = []

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))

    def edit_message_text(self, chat_id, message_id, text):
        return None

    def delete_message(self, chat_id, message_id):
        return None


def process(conn, cfg, upd, **kwargs):
    tg = kwargs.pop("tg", None) or RecordingTelegram()
    llm = kwargs.pop("llm", None) or FakeLLM([])
    bot.process_update(
        upd, conn=conn, tg=tg, cfg=cfg, llm=llm, skills=kwargs.pop("skills", {}),
        runner=kwargs.pop("runner", None) or RecordingRunner(),
        bot_username=BOT_USERNAME, **kwargs,
    )
    return tg


CALL_DEFAULTS = {
    "turn_id": 1,
    "purpose": "agent",
    "round_no": 1,
    "attempt": 1,
    "ts": NOW,
    "provider": "lmstudio",
    "model": "small",
    "prompt_tokens": 100,
    "completion_tokens": 10,
    "total_tokens": 110,
    "cached_tokens": None,
    "reasoning_tokens": None,
    "reasoning_chars": 0,
    "prompt_chars": 300,
    "prompt_chars_by_role": {"system": 100, "tools": 50, "user": 150,
                             "assistant": 0, "tool": 0},
    "messages_n": 2,
    "tools_exposed": 3,
    "latency_ms": 5,
    "finish_reason": "stop",
    "tool_calls_n": 0,
    "error_kind": None,
    "cost_usd": None,
    "cost_basis": None,
}


def add_call(conn, conv_id, **overrides):
    fields = dict(CALL_DEFAULTS, conv_id=conv_id)
    fields.update(overrides)
    return storage.add_llm_call(conn, **fields)


@pytest.fixture
def registered_secrets():
    """Secrets are process-global; a test that registers one restores the set."""
    before = set(config._secrets)
    yield
    config._secrets.clear()
    config._secrets.update(before)


def add_tool(conn, conv_id, **overrides):
    fields = {
        "conv_id": conv_id, "turn_id": 1, "tool_call_id": "call_1_0", "tool": "exec",
        "ts": NOW, "input_chars": 20, "raw_output_chars": 100, "output_chars": 100,
        "output_tokens_est": 33, "duration_ms": 7, "outcome": "ok",
    }
    fields.update(overrides)
    return storage.add_tool_call(conn, **fields)


# --------------------------------------------------------------------------
# 6.1 REQ-V13-OBS-01 — usage on the response
# --------------------------------------------------------------------------

def test_obs01_usage_full():
    response = parse_response(body(
        {"content": "hi"},
        {
            "prompt_tokens": 900,
            "completion_tokens": 40,
            "total_tokens": 940,
            "prompt_tokens_details": {"cached_tokens": 128},
            "completion_tokens_details": {"reasoning_tokens": 12},
            "cost": 0.00042,
        },
    ))
    assert response.usage == Usage(900, 40, 940, 128, 12, 0.00042)


def test_obs01_usage_partial_leaves_the_rest_none():
    response = parse_response(body({"content": "hi"}, {"prompt_tokens": 5}))
    assert response.usage == Usage(5, None, None, None, None, None)


def test_obs01_usage_absent_is_none():
    assert parse_response(body({"content": "hi"})).usage is None
    assert parse_response(body({"content": "hi"}, "not-an-object")).usage is None


@pytest.mark.parametrize("value", ["900", 12.5, True, None, {"n": 1}, [1]])
def test_obs01_non_integer_usage_reads_as_none(value):
    usage = parse_usage({"prompt_tokens": value, "completion_tokens": 7})
    assert usage.prompt_tokens is None
    assert usage.completion_tokens == 7


def test_obs01_missing_fields_are_none_never_zero():
    assert parse_usage({}) == Usage(None, None, None, None, None, None)


def test_obs01_nested_detail_objects_may_be_missing_or_wrong():
    assert parse_usage({"prompt_tokens_details": 7}).cached_tokens is None
    assert parse_usage({"completion_tokens_details": {}}).reasoning_tokens is None
    assert parse_usage({"prompt_tokens_details": {"cached_tokens": 0}}).cached_tokens == 0


def test_obs01_provider_cost_accepts_numbers_only():
    assert parse_usage({"cost": 1}).provider_cost_usd == 1.0
    assert parse_usage({"cost": 0.5}).provider_cost_usd == 0.5
    assert parse_usage({"cost": "0.5"}).provider_cost_usd is None
    assert parse_usage({"cost": True}).provider_cost_usd is None


def test_obs01_openrouter_asks_for_usage_accounting():
    seen, transport = capture_payloads()
    with httpx.Client(transport=transport) as client:
        OpenRouterClient("k", "m", 5.0, client).complete([{"role": "user", "content": "x"}], None)
    assert seen[0]["usage"] == {"include": True}


def test_obs01_lmstudio_request_is_unchanged():
    seen, transport = capture_payloads()
    with httpx.Client(transport=transport) as client:
        LMStudioClient("http://local/v1", "m", 5.0, client).complete(
            [{"role": "user", "content": "x"}], None
        )
    assert "usage" not in seen[0]


def test_request_defaults_are_the_single_source_of_the_control_values():
    assert REQUEST_DEFAULTS == {"temperature": 0, "stream": False, "tool_choice": "auto"}
    payload = build_payload("m", [{"role": "user", "content": "x"}], [{"type": "function"}])
    assert payload["temperature"] == REQUEST_DEFAULTS["temperature"]
    assert payload["stream"] == REQUEST_DEFAULTS["stream"]
    assert payload["tool_choice"] == REQUEST_DEFAULTS["tool_choice"]


def test_tool_choice_appears_only_with_tools():
    payload = build_payload("m", [{"role": "user", "content": "x"}], None)
    assert "tool_choice" not in payload
    assert "tools" not in payload


# --------------------------------------------------------------------------
# 6.1 REQ-V13-OBS-02 — reasoning never reaches the user
# --------------------------------------------------------------------------

def test_obs02_think_block_is_stripped_from_content():
    response = parse_response(body({"content": "<think>plan</think>Answer"}))
    assert response.content == "Answer"
    assert response.reasoning_chars == 4


def test_obs02_several_blocks_are_removed_and_counted():
    response = parse_response(body({"content": "a<think>12</think>b<think>345</think>c"}))
    assert response.content == "abc"
    assert response.reasoning_chars == 5


def test_obs02_reasoning_content_field_is_counted():
    response = parse_response(body({"content": "A", "reasoning_content": "12345"}))
    assert response.content == "A"
    assert response.reasoning_chars == 5


def test_obs02_reasoning_is_the_fallback_field_and_the_two_are_not_summed():
    both = parse_response(body({"content": "A", "reasoning_content": "123", "reasoning": "45678"}))
    assert both.reasoning_chars == 3
    only = parse_response(body({"content": "A", "reasoning": "45678"}))
    assert only.reasoning_chars == 5


def test_obs02_a_field_and_a_block_add_up():
    response = parse_response(body({"content": "x<think>12</think>", "reasoning": "abc"}))
    assert response.content == "x"
    assert response.reasoning_chars == 5


def test_obs02_no_reasoning_at_all_is_zero():
    response = parse_response(body({"content": "plain answer"}))
    assert response.content == "plain answer"
    assert response.reasoning_chars == 0
    assert "<think>" not in response.content


def test_obs02_unclosed_think_block_never_reaches_the_user():
    # A response cut off by the output cap can open a block and never close it;
    # leaving it in `content` would deliver the whole chain of thought.
    response = parse_response(body({"content": "<think>half a plan"}, finish_reason="length"))
    assert response.content == ""
    assert response.reasoning_chars == len("half a plan")


def test_obs02_non_string_reasoning_field_is_ignored():
    assert parse_response(body({"content": "A", "reasoning": 12345})).reasoning_chars == 0


# --------------------------------------------------------------------------
# 6.1 REQ-V13-OBS-04 — describe() on all three clients
# --------------------------------------------------------------------------

def test_describe_on_the_two_adapters():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    with httpx.Client(transport=transport) as client:
        assert LMStudioClient("http://local/v1", "small", 1.0, client).describe() == (
            "lmstudio", "small")
        assert OpenRouterClient("key", "big", 1.0, client).describe() == ("openrouter", "big")


def test_describe_on_failover_reports_the_client_that_served_the_call():
    primary = NamedLLM("lmstudio", "small", [LLMError("boom", retryable=True)])
    secondary = NamedLLM("openrouter", "big", [LLMResponse("from the fallback", [], "stop")])
    failover = FailoverLLMClient(
        primary, secondary, primary_name="lmstudio", secondary_name="openrouter"
    )
    assert failover.describe() == ("lmstudio", "small")
    failover.failure_counts["lmstudio"] = FAILOVER_THRESHOLD - 1
    assert failover.complete([{"role": "user", "content": "x"}], None).content == (
        "from the fallback")
    assert failover.describe() == ("openrouter", "big")


# --------------------------------------------------------------------------
# 6.1 REQ-V13-OBS-03 — schema v3
# --------------------------------------------------------------------------

def test_obs03_fresh_database_is_v3(conn):
    assert storage.SCHEMA_VERSION == 3
    assert storage.schema_version(conn) == 3
    for table in ("llm_calls", "tool_calls"):
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone() is not None


def test_obs03_migration_from_v2_is_additive_and_idempotent(tmp_path):
    path = tmp_path / "v2.db"
    legacy = sqlite3.connect(str(path), isolation_level=None)
    legacy.executescript(V2_SCHEMA)
    legacy.execute(
        "INSERT INTO conversations (tg_user_id, created_at, active) VALUES (7, 'x', 1)")
    legacy.execute(
        "INSERT INTO messages (conv_id, turn_id, role, content, created_at) "
        "VALUES (1, 1, 'user', 'hi', 'x')")
    legacy.close()

    conn = storage.connect(path)
    storage.init_schema(conn)
    assert storage.schema_version(conn) == 3
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 1
    assert conn.execute("SELECT content FROM messages").fetchone()[0] == "hi"
    add_call(conn, 1)
    storage.init_schema(conn)
    assert storage.schema_version(conn) == 3
    assert len(llm_rows(conn)) == 1
    conn.close()


def test_obs03_a_future_version_is_still_refused(tmp_path):
    path = tmp_path / "future.db"
    conn = storage.connect(path)
    storage.init_schema(conn)
    conn.execute("UPDATE schema_version SET version = 4 WHERE id = 1")
    with pytest.raises(RuntimeError) as raised:
        storage.init_schema(conn)
    assert "4" in str(raised.value)
    conn.close()


def test_obs03_llm_calls_purpose_is_constrained(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    with pytest.raises(sqlite3.IntegrityError):
        add_call(conn, conv, purpose="benchmark")


def test_obs03_writers_round_trip(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    row_id = add_call(conn, conv, cached_tokens=7, cost_usd=0.25, cost_basis="manual")
    row = llm_rows(conn)[0]
    assert row["id"] == row_id
    assert row["purpose"] == "agent" and row["round"] == 1 and row["attempt"] == 1
    assert row["cached_tokens"] == 7 and row["cost_usd"] == 0.25
    assert row["cost_basis"] == "manual"
    assert json.loads(row["prompt_chars_by_role"])["system"] == 100

    tool_id = add_tool(conn, conv, outcome="rejected")
    tool = tool_rows(conn)[0]
    assert tool["id"] == tool_id and tool["outcome"] == "rejected"
    assert tool["raw_output_chars"] == tool["output_chars"] == 100


# --------------------------------------------------------------------------
# 6.1 REQ-V13-OBS-04 — one row per llm.complete invocation
# --------------------------------------------------------------------------

def test_obs04_a_successful_tool_round_is_recorded(conn):
    script = [
        LLMResponse("", [tool_call()], "tool_calls",
                    Usage(900, 40, 940, None, None, None)),
        LLMResponse("done", [], "stop"),
    ]
    _, _, conv = run(conn, script)
    rows = llm_rows(conn)
    assert len(rows) == 2
    first = rows[0]
    assert first["conv_id"] == conv
    assert first["purpose"] == "agent" and first["round"] == 1 and first["attempt"] == 1
    assert first["prompt_tokens"] == 900 and first["completion_tokens"] == 40
    assert first["total_tokens"] == 940
    assert first["finish_reason"] == "tool_calls" and first["tool_calls_n"] == 1
    assert first["error_kind"] is None
    assert set(json.loads(first["prompt_chars_by_role"])) == {
        "system", "tools", "user", "assistant", "tool"}
    assert first["prompt_chars"] == sum(json.loads(first["prompt_chars_by_role"]).values())
    assert first["tools_exposed"] == 3 and first["messages_n"] >= 2
    assert first["latency_ms"] >= 0
    assert rows[1]["round"] == 2 and rows[1]["prompt_tokens"] is None


def test_obs04_the_row_points_at_the_turn_it_produced(conn):
    script = [
        LLMResponse("", [tool_call()], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ]
    _, _, conv = run(conn, script)
    rows = llm_rows(conn)
    turns = [r["turn_id"] for r in rows]
    stored = [r["turn_id"] for r in conn.execute(
        "SELECT DISTINCT turn_id FROM messages WHERE conv_id = ? AND role != 'user' "
        "ORDER BY turn_id", (conv,))]
    assert turns == stored


def test_obs04_a_failed_invocation_is_recorded_and_retried(conn):
    script = [LLMError("llm http 500", retryable=True), LLMResponse("done", [], "stop")]
    reply, _, _ = run(conn, script)
    assert reply == "done"
    rows = llm_rows(conn)
    assert [r["attempt"] for r in rows] == [1, 2]
    assert rows[0]["error_kind"] == "http"
    assert rows[0]["turn_id"] is None
    assert rows[0]["prompt_tokens"] is None
    assert rows[0]["completion_tokens"] is None
    assert rows[0]["total_tokens"] is None
    assert rows[0]["finish_reason"] is None
    assert rows[0]["provider"] and rows[0]["model"]
    assert rows[1]["error_kind"] is None


def test_obs04_every_failed_invocation_is_recorded_even_when_none_succeeds(conn):
    script = [LLMError("llm http 500", retryable=True)] * agent.HTTP_ATTEMPT_LIMIT
    run(conn, script)
    rows = llm_rows(conn)
    assert len(rows) == agent.HTTP_ATTEMPT_LIMIT
    assert all(r["error_kind"] == "http" for r in rows)


def test_obs04_a_failover_inside_one_invocation_is_one_row(conn):
    primary = NamedLLM("lmstudio", "small", [LLMError("boom", retryable=True)])
    secondary = NamedLLM("openrouter", "big", [LLMResponse("served", [], "stop")])
    failover = FailoverLLMClient(
        primary, secondary, primary_name="lmstudio", secondary_name="openrouter"
    )
    failover.failure_counts["lmstudio"] = FAILOVER_THRESHOLD - 1
    reply, _, _ = run(conn, [], llm=failover)
    assert reply == "served"
    rows = llm_rows(conn)
    assert len(rows) == 1
    assert rows[0]["attempt"] == 1
    assert (rows[0]["provider"], rows[0]["model"]) == ("openrouter", "big")


def test_obs04_summary_calls_are_recorded_with_round_zero(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    storage.add_assistant_message(conn, conv, "hi")
    llm = FakeLLM([
        LLMResponse("not json", [], "stop"),
        LLMResponse('{"goal": "g", "files": [], "decisions": [], '
                    '"errors": [], "next_action": ""}', [], "stop"),
    ])
    assert agent.summarize_conversation(conn, conv, llm, None) is not None
    rows = llm_rows(conn)
    assert len(rows) == 2
    # OBS-04 pins `attempt 1` for the summary purpose, repair round included.
    assert all(r["purpose"] == "summary" for r in rows)
    assert all(r["round"] == 0 for r in rows)
    assert all(r["attempt"] == 1 for r in rows)
    assert all(r["turn_id"] is None for r in rows)


def test_obs04_a_stub_resolver_lands_in_the_row(conn):
    seen = []

    def resolver(provider, model, usage):
        seen.append((provider, model, usage))
        return (0.125, "reference:anthropic/claude")

    run(conn, [LLMResponse("done", [], "stop", Usage(10, 2, 12, None, None, None))],
        resolve_cost=resolver)
    row = llm_rows(conn)[0]
    assert row["cost_usd"] == 0.125
    assert row["cost_basis"] == "reference:anthropic/claude"
    assert seen[0][2] == Usage(10, 2, 12, None, None, None)


def test_obs04_no_resolver_stores_null(conn):
    run(conn, [LLMResponse("done", [], "stop", Usage(10, 2, 12, None, None, None))])
    row = llm_rows(conn)[0]
    assert row["cost_usd"] is None and row["cost_basis"] is None


def test_obs04_the_resolver_sees_the_post_invocation_describe_values(conn):
    seen = []
    primary = NamedLLM("lmstudio", "small", [LLMError("boom", retryable=True)])
    secondary = NamedLLM("openrouter", "big", [LLMResponse("served", [], "stop")])
    failover = FailoverLLMClient(
        primary, secondary, primary_name="lmstudio", secondary_name="openrouter"
    )
    failover.failure_counts["lmstudio"] = FAILOVER_THRESHOLD - 1
    run(conn, [], llm=failover,
        resolve_cost=lambda p, m, u: (seen.append((p, m)), (None, None))[1])
    assert seen == [("openrouter", "big")]


def test_obs04_the_resolver_runs_for_a_failed_invocation_too(conn):
    seen = []
    run(conn, [LLMError("llm http 500", retryable=False)],
        resolve_cost=lambda p, m, u: (seen.append(u), (None, None))[1])
    assert seen == [None]


def test_obs04_a_client_without_describe_still_records_provider_and_model(conn):
    class Bare:
        def complete(self, messages, tools, *, max_tokens=None):
            return LLMResponse("done", [], "stop")

    run(conn, [], llm=Bare())
    row = llm_rows(conn)[0]
    assert row["provider"] and row["model"]


# --------------------------------------------------------------------------
# 6.1 REQ-V13-OBS-05 — one row per tool call, whatever its outcome
# --------------------------------------------------------------------------

def test_obs05_an_executed_tool_call_is_recorded(conn):
    script = [LLMResponse("", [tool_call()], "tool_calls"), LLMResponse("done", [], "stop")]
    _, _, conv = run(conn, script)
    rows = tool_rows(conn)
    assert len(rows) == 1
    row = rows[0]
    assert row["conv_id"] == conv and row["tool"] == "exec"
    assert row["outcome"] == "ok"
    assert row["tool_call_id"] == "call_2_0"
    assert row["input_chars"] == len(EXEC_ARGS)
    # REQ-V13-TOO-03: the two chars columns measure the stream text (here an
    # uncompacted `recorded\n`), while `output_tokens_est` stays on the
    # envelope the model is actually sent — the basis the O1 metric
    # `tool_output_tokens_est` was benchmarked on.
    envelope = conn.execute(
        "SELECT content FROM messages WHERE role = 'tool'").fetchone()[0]
    assert row["output_chars"] == row["raw_output_chars"] == len("recorded\n")
    assert row["output_tokens_est"] == agent.estimate_tokens(envelope)
    assert row["duration_ms"] >= 0
    assert row["turn_id"] == conn.execute(
        "SELECT turn_id FROM messages WHERE role = 'tool'").fetchone()[0]


def test_obs05_excess_calls_are_recorded_as_rejected(conn):
    calls = [tool_call(i) for i in range(agent.MAX_TOOL_CALLS_PER_RESPONSE + 2)]
    script = [LLMResponse("", calls, "tool_calls"), LLMResponse("done", [], "stop")]
    run(conn, script)
    outcomes = [row["outcome"] for row in tool_rows(conn)]
    assert outcomes == ["ok"] * agent.MAX_TOOL_CALLS_PER_RESPONSE + ["rejected"] * 2


def test_obs05_a_budget_refusal_is_recorded(conn):
    # One call in the first round puts the execution budget off the round
    # boundary, so the last round runs out of budget half-way through.
    def full_round():
        return LLMResponse(
            "", [tool_call(i) for i in range(agent.MAX_TOOL_CALLS_PER_RESPONSE)], "tool_calls")

    script = [LLMResponse("", [tool_call()], "tool_calls")]
    script += [full_round() for _ in range(4)]
    script.append(LLMResponse("done", [], "stop"))
    run(conn, script)
    outcomes = [row["outcome"] for row in tool_rows(conn)]
    assert outcomes.count("ok") == agent.TOOL_EXECUTION_LIMIT
    assert outcomes[-1] == "budget"


def test_obs05_an_error_envelope_is_recorded_as_error(conn):
    script = [
        LLMResponse("", [ToolCall("call_1", "nosuchtool", "{}")], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ]
    run(conn, script)
    row = tool_rows(conn)[0]
    assert row["outcome"] == "error"
    # REQ-V12-ID-01: a name outside the advertised set is stored as "unknown".
    assert row["tool"] == "unknown"


# --------------------------------------------------------------------------
# 6.1 REQ-V13-OBS-06 / 6.2 REQ-V13-OBS-09 — structured log lines, no content
# --------------------------------------------------------------------------

def parse_log(caplog, prefix):
    payloads = []
    for record in caplog.records:
        message = record.getMessage()
        if message.startswith(prefix + " "):
            payloads.append(json.loads(message[len(prefix) + 1:]))
    return payloads


def columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_obs06_log_lines_mirror_the_stored_rows(conn, caplog):
    caplog.set_level(logging.INFO, logger="storage")
    script = [
        LLMResponse("", [tool_call()], "tool_calls", Usage(900, 40, 940, None, None, None)),
        LLMResponse("the answer", [], "stop"),
    ]
    run(conn, script, user="what is the kernel version")

    calls = parse_log(caplog, "llm_call")
    tools_logged = parse_log(caplog, "tool_call")
    assert len(calls) == len(llm_rows(conn)) == 2
    assert len(tools_logged) == len(tool_rows(conn)) == 1
    assert set(calls[0]) == columns(conn, "llm_calls")
    assert set(tools_logged[0]) == columns(conn, "tool_calls")
    assert isinstance(calls[0]["prompt_chars_by_role"], dict)
    assert calls[0]["id"] == llm_rows(conn)[0]["id"]
    for payload in calls + tools_logged:
        assert "content" not in payload
        assert "arguments" not in payload
        assert "url" not in payload


def test_obs06_log_lines_carry_no_message_text(conn, caplog):
    caplog.set_level(logging.INFO, logger="storage")
    run(conn, [LLMResponse("the secret answer", [], "stop")], user="a memorable question")
    dumped = json.dumps(parse_log(caplog, "llm_call"))
    assert "memorable" not in dumped
    assert "secret answer" not in dumped


def test_obs09_the_tables_store_no_message_content(conn, registered_secrets):
    config.register_secret("SYNTHETIC-CANARY-OBS")
    script = [
        LLMResponse("", [ToolCall("c1", "exec", json.dumps(
            {"argv": ["echo", "SYNTHETIC-CANARY-OBS"]}))], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ]
    run(conn, script, user="please echo SYNTHETIC-CANARY-OBS")
    dumped = json.dumps([dict(row) for row in llm_rows(conn) + tool_rows(conn)])
    assert "SYNTHETIC-CANARY-OBS" not in dumped
    assert "echo" not in dumped
    assert "please" not in dumped


# --------------------------------------------------------------------------
# 6.1 REQ-V13-OBS-07 — /stats and the /status token line
# --------------------------------------------------------------------------

def seed_conversation(conn, *, basis=(None, None), user_id=USER_ID):
    conv = storage.get_or_create_active_conversation(conn, user_id)
    add_call(conn, conv, turn_id=2, round_no=1, prompt_tokens=2980, completion_tokens=88,
             total_tokens=3068, tool_calls_n=1, finish_reason="tool_calls",
             cost_usd=None if basis[0] is None else 0.01, cost_basis=basis[0])
    add_call(conn, conv, turn_id=3, round_no=2, prompt_tokens=3512, completion_tokens=210,
             total_tokens=3722, cost_usd=None if basis[1] is None else 0.0123,
             cost_basis=basis[1])
    add_tool(conn, conv, turn_id=2, tool="exec", duration_ms=412, output_tokens_est=1812)
    return conv


def stats_text(conn, cfg, update_id=1):
    tg = process(conn, cfg, update(text="/stats", update_id=update_id))
    return "".join(text for _chat, text in tg.sent)


def test_obs07_stats_layout(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    seed_conversation(conn, basis=("reference:big", "reference:big"))
    text = stats_text(conn, cfg)
    lines = text.splitlines()
    assert lines[0] == "Stats (this conversation | all time)"
    assert lines[1] == "LLM calls: 2 | 2 (errors 0 | 0)"
    assert lines[2] == "Tokens in: 6492 | 6492 (cached: n/a | n/a, reasoning: 0 | 0)"
    assert lines[3] == "Tokens out: 298 | 298"
    assert lines[4] == "Est. cost: $0.0223 | $0.0223 (basis: reference:big | reference:big)"
    assert lines[5].startswith("Avg prompt/call: 3246 | 3246; re-sent share: ")
    assert lines[6].startswith("Top tools by output tokens (all time): exec 1812 (100%)")
    assert lines[7] == "Last turn: r1 in 2980 out 88 → exec 412 ms; r2 in 3512 out 210 (final)"
    assert len(text) <= 3500


def test_obs07_stats_reports_no_pricing(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    seed_conversation(conn)
    text = stats_text(conn, cfg)
    assert "Est. cost: n/a (no pricing)" in text
    assert "LLM calls: 2 |" in text


def test_obs07_stats_basis_is_mixed_when_the_rows_disagree(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    seed_conversation(conn, basis=("provider", "openrouter-list-stale"))
    assert "(basis: mixed | mixed)" in stats_text(conn, cfg)


def test_obs07_stats_on_an_empty_database(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    text = stats_text(conn, cfg)
    assert "LLM calls: 0 | 0 (errors 0 | 0)" in text
    assert "Tokens in: n/a | n/a" in text
    assert "Est. cost: n/a (no pricing)" in text
    assert "Top tools by output tokens (all time): none" in text
    assert "Last turn: none" in text
    # A read-only command never opens a conversation.
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0


def test_obs07_stats_separates_this_conversation_from_all_time(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    other = storage.get_or_create_active_conversation(conn, 999)
    add_call(conn, other, prompt_tokens=1000, completion_tokens=100, total_tokens=1100,
             error_kind="http")
    seed_conversation(conn)
    text = stats_text(conn, cfg)
    assert "LLM calls: 2 | 3 (errors 0 | 1)" in text
    assert "Tokens in: 6492 | 7492" in text


def test_obs07_stats_reports_cached_and_reasoning_when_present(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    add_call(conn, conv, cached_tokens=128, reasoning_tokens=12)
    assert "(cached: 128 | 128, reasoning: 12 | 12)" in stats_text(conn, cfg)


def test_obs07_status_carries_the_token_line(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    seed_conversation(conn)
    tg = process(conn, cfg, update(text="/status"))
    assert "Tokens this conversation: in 6492 / out 298" in tg.sent[0][1]


def test_obs07_status_token_line_without_a_conversation(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    tg = process(conn, cfg, update(text="/status"))
    assert "Tokens this conversation: in 0 / out 0" in tg.sent[0][1]


def test_obs07_stats_stays_under_the_cap(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    for index in range(60):
        add_call(conn, conv, turn_id=index + 2, round_no=(index % 8) + 1)
        add_tool(conn, conv, turn_id=index + 2, tool="exec" if index % 2 else "fetch")
    text = stats_text(conn, cfg)
    assert len(text) <= 3500


# --------------------------------------------------------------------------
# 6.1 REQ-V13-OBS-08 — metrics.py
# --------------------------------------------------------------------------

def test_obs08_resent_tokens_on_a_hand_computed_sequence():
    calls = [{"prompt_tokens": 100}, {"prompt_tokens": 250}, {"prompt_tokens": 200}]
    resent, new = metrics.resent_tokens(calls)
    assert (resent, new) == (300, 250)
    assert resent + new == sum(call["prompt_tokens"] for call in calls)


def test_obs08_resent_tokens_clamps_a_window_drop_at_zero():
    calls = [{"prompt_tokens": 900}, {"prompt_tokens": 100}]
    resent, new = metrics.resent_tokens(calls)
    assert (resent, new) == (100, 900)


def test_obs08_resent_tokens_skips_rows_without_usage():
    calls = [{"prompt_tokens": 100}, {"prompt_tokens": None}, {"prompt_tokens": 250}]
    assert metrics.resent_tokens(calls) == (100, 250)
    assert metrics.resent_tokens([]) == (0, 0)


def test_obs08_context_growth_is_the_per_role_char_delta():
    calls = [
        {"purpose": "agent", "prompt_chars_by_role":
            {"system": 100, "tools": 2000, "user": 40, "assistant": 0, "tool": 0}},
        {"purpose": "summary", "prompt_chars_by_role":
            {"system": 9999, "tools": 0, "user": 0, "assistant": 0, "tool": 0}},
        {"purpose": "agent", "prompt_chars_by_role":
            {"system": 100, "tools": 2000, "user": 40, "assistant": 250, "tool": 900}},
    ]
    assert metrics.context_growth(calls) == {
        "system": 0, "tools": 0, "user": 0, "assistant": 250, "tool": 900}


def test_obs08_context_growth_needs_two_agent_calls():
    zeros = dict.fromkeys(metrics.PROMPT_ROLE_KEYS, 0)
    single = [{"purpose": "agent", "prompt_chars_by_role": {"system": 100}}]
    assert metrics.context_growth(single) == zeros
    assert metrics.context_growth([]) == zeros
    assert metrics.context_growth(
        [{"purpose": "summary", "prompt_chars_by_role": {}}] * 3) == zeros


def test_obs08_context_growth_reads_the_stored_json_column(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    add_call(conn, conv, prompt_chars_by_role={
        "system": 100, "tools": 50, "user": 150, "assistant": 0, "tool": 0})
    add_call(conn, conv, purpose="summary", round_no=0, turn_id=None,
             prompt_chars_by_role={"system": 5000, "tools": 0, "user": 0,
                                   "assistant": 0, "tool": 0})
    add_call(conn, conv, prompt_chars_by_role={
        "system": 100, "tools": 50, "user": 150, "assistant": 300, "tool": 700})
    growth = metrics.context_growth(storage.fetch_llm_calls(conn, conv))
    assert growth == {"system": 0, "tools": 0, "user": 0, "assistant": 300, "tool": 700}


def test_obs08_top_tools_ranks_by_output_tokens(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    add_tool(conn, conv, tool="exec", output_tokens_est=1812)
    add_tool(conn, conv, tool="fetch", output_tokens_est=401)
    add_tool(conn, conv, tool="load_skill", output_tokens_est=110)
    ranked = metrics.top_tools(conn, 2)
    assert [(tool, tokens) for tool, tokens, _share in ranked] == [("exec", 1812), ("fetch", 401)]
    assert round(ranked[0][2] * 100) == 78
    assert metrics.top_tools(conn, 10)[2][0] == "load_skill"


def test_obs08_stats_aggregate_rows(conn):
    conv = seed_conversation(conn)
    here = metrics.conversation_stats(conn, conv)
    assert here.calls == 2 and here.errors == 0
    assert here.tokens_in == 6492 and here.tokens_out == 298
    assert here.cached_tokens is None and here.reasoning_tokens == 0
    assert here.cost_usd is None and here.cost_basis is None
    assert here.avg_prompt == 3246
    assert metrics.global_stats(conn) == here
    assert metrics.conversation_stats(conn, None) == metrics.Stats()


def test_obs08_global_resent_share_is_per_conversation(conn):
    first = storage.get_or_create_active_conversation(conn, USER_ID)
    add_call(conn, first, prompt_tokens=100)
    add_call(conn, first, prompt_tokens=250)
    second = storage.get_or_create_active_conversation(conn, 999)
    add_call(conn, second, prompt_tokens=100)
    add_call(conn, second, prompt_tokens=250)
    # Each conversation contributes 100 re-sent tokens; a naive global walk would
    # also count the jump between the two conversations.
    assert metrics.global_stats(conn).resent_share == pytest.approx(200 / 700)


def test_obs08_turn_timeline_defaults_to_the_last_exchange(conn):
    conv = seed_conversation(conn)
    timeline = metrics.turn_timeline(conn, conv, 2)
    assert [entry["round"] for entry in timeline] == [1, 2]
    assert timeline[0]["tools"] == [("exec", 412)]
    assert timeline[1]["final"] is True
    assert metrics.turn_timeline(conn, conv) == timeline
    assert metrics.turn_timeline(conn, conv, 99) == []


def test_obs07_stats_drops_whole_lines_before_it_cuts_one(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    add_call(conn, conv, cost_usd=0.5, cost_basis="reference:" + "m" * 4000)
    text = stats_text(conn, cfg)
    lines = text.splitlines()
    assert len(text) <= 3500
    assert lines[0] == "Stats (this conversation | all time)"
    assert lines[1].startswith("LLM calls: 1 | 1")
