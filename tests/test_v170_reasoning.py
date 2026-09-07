"""spec-v1.7.0 T4/T5: the reasoning-policy vocabulary (POL-01…-06), the
storage migration (OBS-01…-04) and the summary-budget config check (SUM-05).

Offline and deterministic (REQ-V170-TST-01): no network, no Docker, no
`.env`, no live LLM. Every clock and every LLM in a test is a fake.
"""

import json
import sqlite3

import httpx
import pytest

import storage
import tracing
from agent import _reasoning_honored, run_agent, summarize_conversation
from config import ConfigError, load_config
from llm.base import (
    REASONING_DEFAULT,
    REASONING_MECHANISMS,
    REASONING_TAGS,
    LLMError,
    LLMResponse,
    ReasoningMechanism,
    ReasoningRequest,
    ToolCall,
    build_payload,
    json_fields,
    reasoning_tag,
    resolve_reasoning,
)
from llm.failover import FailoverLLMClient
from llm.lmstudio import LMStudioClient
from llm.openrouter import OpenRouterClient
from tests.fakes import FakeLLM, RecordingRunner
from tests.test_config import base_env
from tests.test_summary import VALID_SUMMARY

# --------------------------------------------------------------------------
# T-V170-POL-01 -- the two environment variables
# --------------------------------------------------------------------------


def test_t_v170_pol_01_policy_accepts_exactly_the_three_values():
    for value in ("model-default", "off", "by-purpose"):
        cfg = load_config(env=base_env(LLM_REASONING_POLICY=value), load_env_file=False)
        assert cfg.llm_reasoning_policy == value


def test_t_v170_pol_01_policy_rejects_an_unknown_value_naming_it():
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_REASONING_POLICY="aggressive"), load_env_file=False)
    message = str(exc.value)
    assert "LLM_REASONING_POLICY" in message and "aggressive" in message


def test_t_v170_pol_01_policy_defaults_to_model_default_when_absent():
    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.llm_reasoning_policy == "model-default"


def test_t_v170_pol_01_purposes_parses_order_insensitively_and_trims():
    cfg = load_config(
        env=base_env(LLM_REASONING_ON_PURPOSES=" final , tool-round ,final"),
        load_env_file=False,
    )
    assert cfg.llm_reasoning_on_purposes == frozenset({"final", "tool-round"})


def test_t_v170_pol_01_purposes_empty_string_is_the_empty_set():
    cfg = load_config(env=base_env(LLM_REASONING_ON_PURPOSES=""), load_env_file=False)
    assert cfg.llm_reasoning_on_purposes == frozenset()


def test_t_v170_pol_01_purposes_absent_defaults_to_tool_round():
    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.llm_reasoning_on_purposes == frozenset({"tool-round"})


def test_t_v170_pol_01_purposes_rejects_an_unknown_tag_naming_it():
    with pytest.raises(ConfigError) as exc:
        load_config(
            env=base_env(LLM_REASONING_ON_PURPOSES="tool-round,bogus"),
            load_env_file=False,
        )
    message = str(exc.value)
    assert "LLM_REASONING_ON_PURPOSES" in message and "bogus" in message


def test_t_v170_pol_01_both_absent_safe():
    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.llm_reasoning_policy == "model-default"
    assert cfg.llm_reasoning_on_purposes == frozenset({"tool-round"})


# N1, N2, N3 --------------------------------------------------------------


def test_n1_reasoning_policy_wrong_case_is_rejected():
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_REASONING_POLICY="OFF"), load_env_file=False)
    assert "LLM_REASONING_POLICY" in str(exc.value)


def test_n2_reasoning_on_purposes_unknown_tag_rejected():
    with pytest.raises(ConfigError) as exc:
        load_config(
            env=base_env(LLM_REASONING_ON_PURPOSES="tool-round,summry"),
            load_env_file=False,
        )
    message = str(exc.value)
    assert "LLM_REASONING_ON_PURPOSES" in message and "summry" in message


def test_n3_purposes_summary_alone_is_a_legal_by_purpose_configuration():
    cfg = load_config(
        env=base_env(LLM_REASONING_POLICY="by-purpose", LLM_REASONING_ON_PURPOSES="summary"),
        load_env_file=False,
    )
    assert cfg.llm_reasoning_policy == "by-purpose"
    assert cfg.llm_reasoning_on_purposes == frozenset({"summary"})


# --------------------------------------------------------------------------
# T-V170-POL-02 -- reasoning_tag, pure
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "purpose,tools,expected",
    [
        ("agent", None, "final"),
        ("agent", [], "final"),
        ("agent", [{"type": "function"}], "tool-round"),
        ("summary", None, "summary"),
        ("summary", [], "summary"),
        ("summary", [{"type": "function"}], "summary"),
    ],
)
def test_t_v170_pol_02_reasoning_tag_cross_product(purpose, tools, expected):
    assert reasoning_tag(purpose, tools) == expected


def test_t_v170_pol_02_reads_no_config_no_global():
    # Purely a signature/behaviour check: calling it twice with the same
    # arguments from a fresh, otherwise-untouched process state returns the
    # same answer -- there is no Config parameter to pass in the first place.
    import inspect

    params = inspect.signature(reasoning_tag).parameters
    assert list(params) == ["purpose", "request_tools"]


# --------------------------------------------------------------------------
# T-V170-POL-03 -- resolve_reasoning
# --------------------------------------------------------------------------


def test_t_v170_pol_03_model_default_sends_nothing_for_every_tag():
    for tag in REASONING_TAGS:
        req = resolve_reasoning("model-default", frozenset(), tag)
        assert req == ReasoningRequest("default", None, tag)


def test_t_v170_pol_03_on_looks_nothing_up_even_with_a_raising_table():
    class _RaisingMapping(dict):
        def get(self, *_a, **_kw):
            raise AssertionError("on/default must never look the table up")

    table = _RaisingMapping()
    for tag in REASONING_TAGS:
        req = resolve_reasoning("by-purpose", frozenset(REASONING_TAGS), tag, mechanisms=table)
        assert req == ReasoningRequest("on", None, tag)
        req = resolve_reasoning("model-default", frozenset(), tag, mechanisms=table)
        assert req == ReasoningRequest("default", None, tag)


def test_t_v170_pol_03_off_looks_up_and_degrades_when_absent():
    mech = ReasoningMechanism("x:test", fields=(("a", 1),))
    table = {"summary": mech}
    assert resolve_reasoning("off", frozenset(), "summary", mechanisms=table) == (
        ReasoningRequest("off", mech, "summary")
    )
    # tool-round has no entry -> degrades to default, not off-with-nothing.
    assert resolve_reasoning("off", frozenset(), "tool-round", mechanisms=table) == (
        ReasoningRequest("default", None, "tool-round")
    )


def test_t_v170_pol_03_by_purpose_mixed_table():
    mech = ReasoningMechanism("c:assistant-prefill", message_patch=("append_assistant", "x"))
    table = {"summary": mech}
    on_purposes = frozenset({"tool-round"})
    assert resolve_reasoning("by-purpose", on_purposes, "tool-round", mechanisms=table) == (
        ReasoningRequest("on", None, "tool-round")
    )
    assert resolve_reasoning("by-purpose", on_purposes, "summary", mechanisms=table) == (
        ReasoningRequest("off", mech, "summary")
    )


def test_t_v170_pol_03_returned_request_is_frozen():
    req = resolve_reasoning("model-default", frozenset(), "final")
    with pytest.raises(AttributeError):
        req.value = "off"  # type: ignore[misc]


def test_t_v170_pol_03_tag_always_equals_the_argument():
    for policy in ("model-default", "off", "by-purpose"):
        for tag in REASONING_TAGS:
            assert resolve_reasoning(policy, frozenset(REASONING_TAGS), tag).tag == tag


def test_t_v170_pol_03_the_shipped_table_matches_stage_a():
    """Sanity check against the real, shipped REASONING_MECHANISMS -- the
    T3 finding: summary-only, candidate c."""
    assert REASONING_MECHANISMS["tool-round"] is None
    assert REASONING_MECHANISMS["final"] is None
    summary_mech = REASONING_MECHANISMS["summary"]
    assert summary_mech is not None
    assert summary_mech.message_patch == ("append_assistant", "<think>\n\n</think>\n\n")
    assert resolve_reasoning("off", frozenset(), "tool-round") == (
        ReasoningRequest("default", None, "tool-round")
    )
    assert resolve_reasoning("off", frozenset(), "summary") == (
        ReasoningRequest("off", summary_mech, "summary")
    )


def test_t_v170_pol_03_reasoning_default_constant():
    assert REASONING_DEFAULT == ReasoningRequest("default", None, "final")


# --------------------------------------------------------------------------
# T-V170-OBS-01 -- schema 4 -> 5
# --------------------------------------------------------------------------

_V1_SCHEMA = """
CREATE TABLE schema_version (id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL);
INSERT INTO schema_version (id, version) VALUES (1, 1);
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tg_user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);
CREATE UNIQUE INDEX idx_conversations_one_active ON conversations (tg_user_id) WHERE active = 1;
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, conv_id INTEGER NOT NULL, turn_id INTEGER NOT NULL,
    role TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', tool_calls_json TEXT,
    tool_call_id TEXT, created_at TEXT NOT NULL
);
CREATE TABLE bot_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _seed(path, schema: str):
    legacy = sqlite3.connect(str(path), isolation_level=None)
    legacy.executescript(schema)
    legacy.close()


def _v3_schema() -> str:
    # v3: llm_calls/tool_calls exist, without trace_id/span_id.
    return _V1_SCHEMA.replace(
        "INSERT INTO schema_version (id, version) VALUES (1, 1);",
        "INSERT INTO schema_version (id, version) VALUES (1, 3);",
    ) + """
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT, conv_id INTEGER NOT NULL UNIQUE,
    tg_user_id INTEGER NOT NULL, goal TEXT NOT NULL DEFAULT '',
    facts_json TEXT NOT NULL DEFAULT '[]', recent_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);
CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY, conv_id INTEGER NOT NULL, turn_id INTEGER,
    purpose TEXT NOT NULL, round INTEGER NOT NULL, attempt INTEGER NOT NULL,
    ts TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
    prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
    cached_tokens INTEGER, reasoning_tokens INTEGER, reasoning_chars INTEGER NOT NULL DEFAULT 0,
    prompt_chars INTEGER NOT NULL, prompt_chars_by_role TEXT NOT NULL,
    messages_n INTEGER NOT NULL, tools_exposed INTEGER NOT NULL, latency_ms INTEGER NOT NULL,
    finish_reason TEXT, tool_calls_n INTEGER NOT NULL DEFAULT 0, error_kind TEXT,
    cost_usd REAL, cost_basis TEXT
);
CREATE TABLE tool_calls (
    id INTEGER PRIMARY KEY, conv_id INTEGER NOT NULL, turn_id INTEGER NOT NULL,
    tool_call_id TEXT NOT NULL, tool TEXT NOT NULL, ts TEXT NOT NULL,
    input_chars INTEGER NOT NULL, raw_output_chars INTEGER NOT NULL,
    output_chars INTEGER NOT NULL, output_tokens_est INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL, outcome TEXT NOT NULL
);
"""


def _v2_schema() -> str:
    return _V1_SCHEMA.replace(
        "INSERT INTO schema_version (id, version) VALUES (1, 1);",
        "INSERT INTO schema_version (id, version) VALUES (1, 2);",
    ) + """
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT, conv_id INTEGER NOT NULL UNIQUE,
    tg_user_id INTEGER NOT NULL, goal TEXT NOT NULL DEFAULT '',
    facts_json TEXT NOT NULL DEFAULT '[]', recent_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);
"""


@pytest.mark.parametrize("schema_fn,start_version", [
    (lambda: _V1_SCHEMA, 1),
    (_v2_schema, 2),
    (_v3_schema, 3),
])
def test_t_v170_obs_01_chains_to_5(tmp_path, schema_fn, start_version):
    path = tmp_path / f"v{start_version}.db"
    _seed(path, schema_fn())
    conn = storage.connect(path)
    storage.init_schema(conn)
    assert storage.schema_version(conn) == 5
    row = conn.execute("PRAGMA table_info(llm_calls)").fetchall()
    names = {r[1] for r in row}
    assert {"reasoning_requested", "reasoning_honored"} <= names
    conn.close()


def test_t_v170_obs_01_migration_4_to_5_on_populated_db(tmp_path):
    """A genuine on-disk v4 database (pre-v1.7.0 shape): both new columns
    appear nullable, a pre-existing row reads NULL in both, version reads 5."""
    path = tmp_path / "v4.db"
    conn = storage.connect(path)
    storage.init_schema(conn)  # today's code -> lands at 5 directly; force back to 4 to simulate
    conn.execute("ALTER TABLE llm_calls RENAME TO llm_calls_v5")
    conn.execute("UPDATE schema_version SET version = 4 WHERE id = 1")
    conn.execute("""
        CREATE TABLE llm_calls (
            id INTEGER PRIMARY KEY, conv_id INTEGER NOT NULL, turn_id INTEGER,
            purpose TEXT NOT NULL, round INTEGER NOT NULL, attempt INTEGER NOT NULL,
            ts TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
            prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
            cached_tokens INTEGER, reasoning_tokens INTEGER,
            reasoning_chars INTEGER NOT NULL DEFAULT 0, prompt_chars INTEGER NOT NULL,
            prompt_chars_by_role TEXT NOT NULL, messages_n INTEGER NOT NULL,
            tools_exposed INTEGER NOT NULL, latency_ms INTEGER NOT NULL,
            finish_reason TEXT, tool_calls_n INTEGER NOT NULL DEFAULT 0, error_kind TEXT,
            cost_usd REAL, cost_basis TEXT, trace_id TEXT, span_id TEXT
        )
    """)
    conn.execute("DROP TABLE llm_calls_v5")
    conn.execute(
        "INSERT INTO conversations (tg_user_id, created_at, active) VALUES (7, 'x', 1)"
    )
    conn.execute(
        "INSERT INTO llm_calls (conv_id, turn_id, purpose, round, attempt, ts, provider, "
        "model, prompt_chars, prompt_chars_by_role, messages_n, tools_exposed, latency_ms) "
        "VALUES (1, 1, 'agent', 1, 1, 'x', 'lmstudio', 'small', 10, '{}', 2, 3, 5)"
    )

    storage.init_schema(conn)
    assert storage.schema_version(conn) == 5
    row = conn.execute("SELECT reasoning_requested, reasoning_honored FROM llm_calls").fetchone()
    assert row[0] is None and row[1] is None

    # idempotent
    storage.init_schema(conn)
    assert storage.schema_version(conn) == 5
    assert conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0] == 1
    conn.close()


@pytest.mark.parametrize("bad", [0, "x"])
def test_t_v170_obs_01_unsupported_version_still_raises(conn, bad):
    conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (bad,))
    with pytest.raises(RuntimeError) as raised:
        storage.init_schema(conn)
    assert str(bad) in str(raised.value)


def test_n8_schema_version_6_raises(conn):
    conn.execute("UPDATE schema_version SET version = 6 WHERE id = 1")
    with pytest.raises(RuntimeError) as raised:
        storage.init_schema(conn)
    assert "6" in str(raised.value)


# --------------------------------------------------------------------------
# T-V170-SUM-05
# --------------------------------------------------------------------------


def test_t_v170_sum_05_raises_below_the_summary_floor():
    with pytest.raises(ConfigError) as exc:
        load_config(
            env=base_env(LLM_TIMEOUT_S="240", LLM_SUMMARY_MAX_TOKENS="8000"),
            load_env_file=False,
        )
    message = str(exc.value)
    assert "LLM_TIMEOUT_S" in message and "LLM_SUMMARY_MAX_TOKENS" in message


def test_t_v170_sum_05_does_not_raise_at_shipped_defaults():
    cfg = load_config(env=base_env(LLM_TIMEOUT_S="240"), load_env_file=False)
    assert cfg.llm_timeout_s == 240.0 and cfg.llm_summary_max_tokens == 1536


def test_t_v170_sum_05_does_not_raise_at_the_1_7_0_instrument():
    cfg = load_config(
        env=base_env(LLM_TIMEOUT_S="600", LLM_MAX_TOKENS="4096"), load_env_file=False
    )
    assert cfg.llm_timeout_s == 600.0


def test_t_v170_sum_05_preexisting_check_message_unchanged():
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_TIMEOUT_S="120"), load_env_file=False)
    message = str(exc.value)
    assert "LLM_TIMEOUT_S" in message and "LLM_MAX_TOKENS" in message


# --------------------------------------------------------------------------
# T-V170-POL-04 -- one ReasoningRequest parameter, five sites
# --------------------------------------------------------------------------


class _RecordingClient:
    """A minimal LLMClient double that records every complete() call."""

    def __init__(self, name, script):
        self.name = name
        self.script = list(script)
        self.calls = []

    def describe(self):
        return (self.name, self.name)

    def complete(self, messages, tools, *, max_tokens=None, reasoning=REASONING_DEFAULT,
                 timeout_s=None):
        self.calls.append((messages, tools, max_tokens, reasoning, timeout_s))
        item = self.script.pop(0)
        if isinstance(item, LLMError):
            raise item
        return item


def test_t_v170_pol_04_failover_forwards_the_same_reasoning_request_unchanged():
    primary = _RecordingClient("lmstudio", [LLMError("boom", retryable=True)] * 5)
    secondary = _RecordingClient("openrouter", [LLMResponse("from secondary", [], "stop")])
    failover = FailoverLLMClient(
        primary, secondary, primary_name="lmstudio", secondary_name="openrouter"
    )
    failover.failure_counts["lmstudio"] = 2  # one more failure trips FAILOVER_THRESHOLD (3)

    mech = ReasoningMechanism("c:assistant-prefill", message_patch=("append_assistant", "x"))
    sent = ReasoningRequest("off", mech, "summary")
    response = failover.complete([{"role": "user", "content": "hi"}], None, reasoning=sent)

    assert response.content == "from secondary"
    assert len(secondary.calls) == 1
    _, _, _, received, _ = secondary.calls[0]
    assert received is sent
    assert received.value == "off" and received.mechanism is mech and received.tag == "summary"


def test_t_v170_pol_04_bench_warmup_probe_passes_defaults_explicitly():
    from devtools import bench

    stub = _RecordingClient("lmstudio", [LLMResponse("ok", [], "stop", usage=None)])
    bench._prefix_tokens(stub, {})
    assert len(stub.calls) == 1
    _, _, _, reasoning, timeout_s = stub.calls[0]
    assert reasoning is REASONING_DEFAULT
    assert timeout_s is None


# --------------------------------------------------------------------------
# T-V170-POL-05 -- the provider forms
# --------------------------------------------------------------------------


def _capture_payload():
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        })

    return captured, httpx.MockTransport(handler)


def test_t_v170_pol_05_lmstudio_applies_mechanism_fields_alone():
    captured, transport = _capture_payload()
    client = LMStudioClient("http://x/v1", "m", 5.0, httpx.Client(transport=transport))
    mech = ReasoningMechanism(
        "a:chat_template_kwargs.enable_thinking=false",
        fields=(("chat_template_kwargs", (("enable_thinking", False),)),),
    )
    req = ReasoningRequest("off", mech, "OUTSIDE_REASONING_TAGS")
    client.complete([{"role": "user", "content": "hi"}], None, reasoning=req)
    assert captured["payload"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_t_v170_pol_05_lmstudio_append_assistant_is_the_last_message():
    captured, transport = _capture_payload()
    client = LMStudioClient("http://x/v1", "m", 5.0, httpx.Client(transport=transport))
    mech = ReasoningMechanism("c:assistant-prefill", message_patch=("append_assistant", "X"))
    req = ReasoningRequest("off", mech, "summary")
    client.complete([{"role": "user", "content": "hi"}], None, reasoning=req)
    assert captured["payload"]["messages"][-1] == {"role": "assistant", "content": "X"}


def test_t_v170_pol_05_lmstudio_suffix_last_user_extends_the_last_user_message():
    captured, transport = _capture_payload()
    client = LMStudioClient("http://x/v1", "m", 5.0, httpx.Client(transport=transport))
    mech = ReasoningMechanism("d:no_think", message_patch=("suffix_last_user", " /no_think"))
    req = ReasoningRequest("off", mech, "tool-round")
    client.complete([{"role": "user", "content": "hi"}], None, reasoning=req)
    assert captured["payload"]["messages"][-1]["content"] == "hi /no_think"


def test_t_v170_pol_05_lmstudio_mechanism_none_adds_nothing():
    captured, transport = _capture_payload()
    client = LMStudioClient("http://x/v1", "m", 5.0, httpx.Client(transport=transport))
    client.complete([{"role": "user", "content": "hi"}], None, reasoning=REASONING_DEFAULT)
    assert "chat_template_kwargs" not in captured["payload"]
    assert captured["payload"]["messages"] == [{"role": "user", "content": "hi"}]


def test_t_v170_pol_05_lmstudio_never_reads_request_tag():
    """A tag outside REASONING_TAGS must not change the outcome in any way --
    the client never looks at `.tag`, only `.mechanism`."""
    captured, transport = _capture_payload()
    client = LMStudioClient("http://x/v1", "m", 5.0, httpx.Client(transport=transport))
    req = ReasoningRequest("off", None, "this-tag-does-not-exist")
    client.complete([{"role": "user", "content": "hi"}], None, reasoning=req)
    assert "chat_template_kwargs" not in captured["payload"]


def test_t_v170_pol_05_openrouter_off_form_is_exact():
    captured, transport = _capture_payload()
    client = OpenRouterClient("key", "m", 5.0, httpx.Client(transport=transport))
    client.complete(
        [{"role": "user", "content": "hi"}], None,
        reasoning=ReasoningRequest("off", None, "summary"),
    )
    assert captured["payload"]["reasoning"] == {"enabled": False}


@pytest.mark.parametrize("value", ["on", "default"])
def test_t_v170_pol_05_openrouter_on_and_default_add_nothing(value):
    captured, transport = _capture_payload()
    client = OpenRouterClient("key", "m", 5.0, httpx.Client(transport=transport))
    client.complete(
        [{"role": "user", "content": "hi"}], None,
        reasoning=ReasoningRequest(value, None, "summary"),
    )
    assert "reasoning" not in captured["payload"]


def test_t_v170_pol_05_no_mechanism_string_reaches_system_prompt_or_tools():
    from agent import build_system_prompt
    from tools import tool_specs

    prompt = build_system_prompt({}, "2026-01-01T00:00:00Z")
    tools_json = json.dumps(tool_specs())
    for mech in REASONING_MECHANISMS.values():
        if mech is None:
            continue
        assert mech.label not in prompt and mech.label not in tools_json
        if mech.message_patch is not None:
            text = mech.message_patch[1]
            assert text not in prompt and text not in tools_json


def test_t_v170_pol_05_prompt_tools_sha256_unchanged_by_any_policy():
    """A treated tree computes the same prompt_tools_sha256 as the untreated
    one: the mechanism table never touches the system prompt or the tool
    schema, so the hash the baseline locks stays byte-identical. Resolving
    every policy/tag combination (as a running bot would, per request) in
    between the two hash computations is the "treatment" -- resolve_reasoning
    touches no shared state, so this is the whole test."""
    from devtools import bench

    baseline_hash = bench._prompt_tools_sha256({})
    for policy in ("model-default", "off", "by-purpose"):
        for tag in REASONING_TAGS:
            resolve_reasoning(policy, frozenset(REASONING_TAGS), tag)
    treated_hash = bench._prompt_tools_sha256({})
    assert treated_hash == baseline_hash


def test_t_v170_pol_05_deep_immutability_no_dict_list_set_anywhere():
    def walk(value):
        assert not isinstance(value, (dict, list, set))
        if isinstance(value, tuple):
            for item in value:
                walk(item)

    for mech in REASONING_MECHANISMS.values():
        if mech is not None:
            walk(mech.fields)


def test_t_v170_pol_05_json_fields_builds_fresh_dicts_every_call():
    fields = (("chat_template_kwargs", (("enable_thinking", False),)),)
    # REASONING_MECHANISMS holds only frozen dataclasses over tuples (no
    # dict/list/set anywhere -- proved separately below), so a shallow
    # snapshot of its items is already a value snapshot; deepcopy chokes on
    # the outer MappingProxyType itself and is not needed here.
    before = dict(REASONING_MECHANISMS)

    first = json_fields(fields)
    first["chat_template_kwargs"]["enable_thinking"] = True  # mutate the produced payload
    first["new_key"] = "mutated"

    second = json_fields(fields)
    assert second == {"chat_template_kwargs": {"enable_thinking": False}}
    assert first is not second
    assert first["chat_template_kwargs"] is not second["chat_template_kwargs"]

    after = dict(REASONING_MECHANISMS)
    assert before == after


# --------------------------------------------------------------------------
# T-V170-POL-06 -- build_payload's reasoning_fields
# --------------------------------------------------------------------------


def test_t_v170_pol_06_none_is_byte_identical_to_today():
    for tools in (None, [{"type": "function"}]):
        assert build_payload("m", [{"role": "user", "content": "x"}], tools) == build_payload(
            "m", [{"role": "user", "content": "x"}], tools, reasoning_fields=None
        )


def test_t_v170_pol_06_merged_after_existing_keys():
    payload = build_payload(
        "m", [{"role": "user", "content": "x"}], None,
        reasoning_fields={"chat_template_kwargs": {"enable_thinking": False}},
    )
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert list(payload)[:5] == ["model", "messages", "temperature", "max_tokens", "stream"]


@pytest.mark.parametrize("key", [
    "model", "messages", "temperature", "max_tokens", "stream", "tools", "tool_choice",
])
def test_t_v170_pol_06_collision_raises_naming_the_key(key):
    with pytest.raises(ValueError) as exc:
        build_payload(
            "m", [{"role": "user", "content": "x"}], [{"type": "function"}],
            reasoning_fields={key: "poison"},
        )
    assert key in str(exc.value)


def test_n4_reasoning_fields_containing_messages_raises():
    with pytest.raises(ValueError) as exc:
        build_payload(
            "m", [{"role": "user", "content": "x"}], None,
            reasoning_fields={"messages": "poison"},
        )
    assert "messages" in str(exc.value)


def test_t_v170_pol_06_message_patch_never_mutates_the_callers_list():
    captured, transport = _capture_payload()
    client = LMStudioClient("http://x/v1", "m", 5.0, httpx.Client(transport=transport))
    original = [{"role": "user", "content": "hi"}]
    mech = ReasoningMechanism("c:assistant-prefill", message_patch=("append_assistant", "X"))
    client.complete(original, None, reasoning=ReasoningRequest("off", mech, "summary"))
    assert original == [{"role": "user", "content": "hi"}]


# --------------------------------------------------------------------------
# T-V170-OBS-02 -- storage/tracing shape
# --------------------------------------------------------------------------


def test_t_v170_obs_02_llm_call_columns_equals_pragma_table_info(conn):
    names = [row[1] for row in conn.execute("PRAGMA table_info(llm_calls)").fetchall()]
    assert list(storage.LLM_CALL_COLUMNS) == names


def test_t_v170_obs_02_tracing_attribute_keys_has_the_new_key_and_still_rejects_unlisted():
    assert "tg_agent.reasoning.requested" in tracing.ATTRIBUTE_KEYS
    span = tracing.MutableSpan(
        trace_id="t", span_id="s", parent_span_id=None, conv_id=None, turn_id=None,
        name="x", kind=tracing.KIND_CLIENT, ts="2026-01-01T00:00:00Z", start_ns=0,
        sink=tracing.NullSink(),
    )
    span.set_attribute("tg_agent.reasoning.requested", "off")  # does not raise
    with pytest.raises(ValueError):
        span.set_attribute("not.a.real.key", "x")


# --------------------------------------------------------------------------
# T-V170-OBS-03 -- the three-valued honored table, in full
# --------------------------------------------------------------------------


@pytest.mark.parametrize("value,reasoning_tokens,reasoning_chars,expected", [
    ("default", 7, 5, None),
    ("default", None, 0, None),
    ("off", None, 0, None),
    ("on", None, 0, None),
    ("off", 0, 0, 1),
    ("off", None, 5, 0),
    ("off", 1, 0, 0),
    ("off", 0, 5, 0),
    ("on", 0, 0, 0),
    ("on", 7, 0, 1),
    ("on", None, 5, 1),
])
def test_t_v170_obs_03_honored_truth_table(value, reasoning_tokens, reasoning_chars, expected):
    result = _reasoning_honored(value, reasoning_tokens, reasoning_chars)
    assert result is expected  # `is`, not `==`: a None regression must not read as falsy-0
    if expected is not None:
        assert result == expected


def test_t_v170_obs_03_a_call_that_raises_before_a_response_is_null():
    assert _reasoning_honored("off", None, 0) is None
    assert _reasoning_honored("on", None, 0) is None


# --------------------------------------------------------------------------
# T-V170-OBS-04 -- exactly six rows, through _record_llm_call only
# --------------------------------------------------------------------------


def _llm_rows(conn):
    return conn.execute("SELECT * FROM llm_calls ORDER BY id").fetchall()


def _tool_call(index=1):
    return ToolCall(f"call_{index}", "exec", '{"argv": ["true"]}')


def test_t_v170_obs_04_exactly_six_rows_all_requested_non_null(conn, tmp_path, monkeypatch):
    conv = storage.get_or_create_active_conversation(conn, 7)
    storage.add_user_message(conn, conv, "hello")

    agent_script = [
        LLMResponse("", [_tool_call()], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ]
    llm = FakeLLM(agent_script)
    run_agent(
        conn=conn, conv_id=conv, llm=llm, skills={}, runner=RecordingRunner(),
        now="2026-01-01T00:00:00Z", sleep=lambda _s: None,
    )
    assert len(_llm_rows(conn)) == 2

    truncating_llm = FakeLLM([
        LLMResponse("cut off", [], "length"),
        LLMResponse(json.dumps(VALID_SUMMARY), [], "stop"),
    ])
    result = summarize_conversation(conn, conv, truncating_llm, None)
    assert result is not None
    assert len(_llm_rows(conn)) == 4

    repairing_llm = FakeLLM([
        LLMResponse("not json at all", [], "stop"),
        LLMResponse(json.dumps(VALID_SUMMARY), [], "stop"),
    ])
    result = summarize_conversation(conn, conv, repairing_llm, None)
    assert result is not None
    rows = _llm_rows(conn)
    assert len(rows) == 6
    columns = storage.LLM_CALL_COLUMNS
    for row in rows:
        assert row[columns.index("reasoning_requested")] is not None


def test_t_v170_obs_04_a_failover_inside_one_call_adds_no_extra_row(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    storage.add_user_message(conn, conv, "hello")

    primary = _RecordingClient("lmstudio", [LLMError("down", retryable=True)] * 5)
    secondary = _RecordingClient("openrouter", [
        LLMResponse("", [_tool_call()], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ])
    failover = FailoverLLMClient(
        primary, secondary, primary_name="lmstudio", secondary_name="openrouter"
    )
    failover.failure_counts["lmstudio"] = 2  # one more trips FAILOVER_THRESHOLD

    run_agent(
        conn=conn, conv_id=conv, llm=failover, skills={}, runner=RecordingRunner(),
        now="2026-01-01T00:00:00Z", sleep=lambda _s: None,
    )
    rows = _llm_rows(conn)
    assert len(rows) == 2
    columns = storage.LLM_CALL_COLUMNS
    for row in rows:
        assert row[columns.index("provider")] == "openrouter"


# --------------------------------------------------------------------------
# T-V170-SUM-01…-04, N5 -- the summary wall-clock budget
# --------------------------------------------------------------------------


class _FakeClock:
    """A stateful, injectable clock. `t` is advanced by the fake LLM below,
    simulating the wall-clock time one `complete()` call actually consumed --
    the only realistic place to inject that, since `summarize_conversation`
    itself calls the clock only around request decisions, never mid-request.
    """

    def __init__(self, start: float = 0.0):
        self.t = start

    def __call__(self) -> float:
        return self.t


class _ClockAdvancingLLM:
    """Each scripted item is `(advance_seconds, response_or_error)`. Records
    every `(reasoning, timeout_s)` pair it actually receives."""

    def __init__(self, clock: _FakeClock, script):
        self.clock = clock
        self.script = list(script)
        self.calls: list[tuple[ReasoningRequest, float | None]] = []

    def describe(self):
        return ("fake", "fake-model")

    def complete(self, messages, tools, *, max_tokens=None, reasoning=REASONING_DEFAULT,
                 timeout_s=None):
        self.calls.append((reasoning, timeout_s))
        advance, item = self.script.pop(0)
        self.clock.t += advance
        if isinstance(item, LLMError):
            raise item
        return item


def _summary_conn_with_content(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    storage.add_user_message(conn, conv, "hello")
    storage.add_assistant_message(conn, conv, "hi")
    return conv


def test_t_v170_sum_01_deadline_taken_once_both_requests_issued(conn):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(clock, [
        (40.0, LLMResponse("cut off", [], "length")),
        (50.0, LLMResponse(json.dumps(VALID_SUMMARY), [], "stop")),
    ])
    result = summarize_conversation(
        conn, conv, llm, None, budget_s=100.0, clock=clock,
    )
    assert result is not None
    assert len(llm.calls) == 2  # both issued: 100 - 40 = 60 >= 30 floor


def test_t_v170_sum_01_budget_s_none_is_byte_identical_to_todays_behaviour(conn):
    conv = _summary_conn_with_content(conn)
    llm = FakeLLM([LLMResponse(json.dumps(VALID_SUMMARY), [], "stop")])
    result = summarize_conversation(conn, conv, llm, None)
    assert result is not None
    assert llm.timeout_s_calls == [None]


def test_t_v170_sum_02_retry_skipped_below_floor_returns_none_one_row(conn, caplog):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(clock, [
        (80.0, LLMResponse("cut off", [], "length")),
    ])
    with caplog.at_level("WARNING"):
        result = summarize_conversation(conn, conv, llm, None, budget_s=100.0, clock=clock)
    assert result is None
    assert len(llm.calls) == 1  # the retry was never issued
    assert len(_llm_rows(conn)) == 1
    assert any("budget exhausted" in r.message for r in caplog.records)


def test_t_v170_sum_02_repair_skipped_below_floor_returns_none_one_row(conn, caplog):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(clock, [
        (80.0, LLMResponse("not json at all", [], "stop")),
    ])
    with caplog.at_level("WARNING"):
        result = summarize_conversation(conn, conv, llm, None, budget_s=100.0, clock=clock)
    assert result is None
    assert len(llm.calls) == 1
    assert len(_llm_rows(conn)) == 1
    assert any("budget exhausted" in r.message for r in caplog.records)


def test_t_v170_sum_03_attempt_1_timeout_is_the_remaining_budget_not_none_not_client_own(conn):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(clock, [
        (0.0, LLMResponse(json.dumps(VALID_SUMMARY), [], "stop")),
    ])
    summarize_conversation(conn, conv, llm, None, budget_s=10.0, clock=clock)
    assert len(llm.calls) == 1
    _, timeout_s = llm.calls[0]
    assert timeout_s == 10.0  # not None, and not the client's own (irrelevant) 600


def test_t_v170_sum_03_retrys_timeout_equals_the_budget_remaining_then(conn):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(clock, [
        (40.0, LLMResponse("cut off", [], "length")),
        (0.0, LLMResponse(json.dumps(VALID_SUMMARY), [], "stop")),
    ])
    summarize_conversation(conn, conv, llm, None, budget_s=100.0, clock=clock)
    assert len(llm.calls) == 2
    _, second_timeout = llm.calls[1]
    assert second_timeout == 60.0  # 100 - 40


def test_n5_attempt_1_issued_at_10s_no_retry_below_floor(conn, caplog):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(clock, [
        (0.0, LLMResponse("cut off", [], "length")),
    ])
    with caplog.at_level("WARNING"):
        result = summarize_conversation(conn, conv, llm, None, budget_s=10.0, clock=clock)
    assert len(llm.calls) == 1  # attempt 1 WAS issued -- 10s remain, positive
    _, timeout_s = llm.calls[0]
    assert timeout_s == 10.0
    assert result is None  # no retry: remaining is still 10s < 30s floor


def test_t_v170_sum_04_retry_and_repair_forced_off_under_every_policy(conn):
    for policy, on_purposes in [
        ("model-default", frozenset()),
        ("off", frozenset()),
        ("by-purpose", frozenset({"summary"})),
    ]:
        conv = storage.get_or_create_active_conversation(conn, 42)
        storage.add_user_message(conn, conv, "hello")
        clock = _FakeClock(0.0)
        llm = _ClockAdvancingLLM(clock, [
            (0.0, LLMResponse("cut off", [], "length")),
            (0.0, LLMResponse(json.dumps(VALID_SUMMARY), [], "stop")),
        ])
        cfg_stub = type("Cfg", (), {
            "obs_capture_content": False,
            "llm_reasoning_policy": policy,
            "llm_reasoning_on_purposes": on_purposes,
        })()
        summarize_conversation(conn, conv, llm, cfg_stub, budget_s=1000.0, clock=clock)
        assert len(llm.calls) == 2
        attempt1_reasoning, _ = llm.calls[0]
        retry_reasoning, _ = llm.calls[1]
        assert retry_reasoning.value == "off" and retry_reasoning.tag == "summary"
        if policy == "by-purpose":
            assert attempt1_reasoning.value == "on"  # summary is in on_purposes here


def test_t_v170_sum_05_module_constant_matches_config_local_copy():
    from agent import SUMMARY_BUDGET_FLOOR_S
    from config import _SUMMARY_BUDGET_FLOOR_S
    assert SUMMARY_BUDGET_FLOOR_S == _SUMMARY_BUDGET_FLOOR_S == 30.0


# --------------------------------------------------------------------------
# T-V170-BEN-01…-05, CAR-01, N6, N7 -- devtools/bench.py
# --------------------------------------------------------------------------

import dataclasses  # noqa: E402
import shutil  # noqa: E402
from pathlib import Path  # noqa: E402

from devtools import bench  # noqa: E402

_REAL_BASELINE_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "assets" / "bench" / "baseline-v1.6.0.json"
)


def _load_real_baseline() -> dict:
    with open(_REAL_BASELINE_PATH) as f:
        return json.load(f)


def _candidate_from_real_baseline(baseline: dict, *, scale: float = 1.0,
                                   fix_failures: bool = True, tag: str = "cand-test") -> dict:
    """A copy of the real, committed baseline: `meta.reasoning` and the two
    new `llm_calls` fields added (T-V170-BEN-01's "candidate-shaped
    document"); costs/tokens optionally scaled and failing repeats optionally
    fixed, entirely through the real `totals_from_rows`/`summarize` so the
    result stays internally consistent for `check_document`."""
    candidate = json.loads(json.dumps(baseline))  # a plain, dict-only deep copy
    candidate["meta"]["tag"] = tag
    candidate["meta"]["git_commit"] = "b" * 40
    candidate["meta"]["reasoning"] = {
        "policy": "by-purpose", "on_purposes": ["tool-round"],
        "mechanism": {"tool-round": None, "final": None, "summary": "c:assistant-prefill"},
        "provider_form": "lmstudio",
    }
    for run in candidate["runs"]:
        if fix_failures:
            run["success"] = True
            run["failure"] = None
            for check in run.get("checks", []):
                check["ok"] = True
                check["detail"] = "ok"
        for call in run["llm_calls"]:
            call["reasoning_requested"] = "default"
            call["reasoning_honored"] = None
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                if call.get(key) is not None:
                    call[key] = int(call[key] * scale)
            if call.get("cost_usd") is not None:
                call["cost_usd"] = call["cost_usd"] * scale
        run["totals"] = bench.totals_from_rows(
            run["llm_calls"], run["tool_calls"], run["totals"]["wall_ms"]
        )
    candidate["summary"] = bench.summarize(
        candidate["runs"], candidate["meta"]["skipped_scenarios"], candidate["meta"]["repeats"]
    )
    return candidate


def test_t_v170_ben_01_meta_reasoning_shape_and_additive_optionality():
    real_baseline = _load_real_baseline()
    # The real, committed baseline carries neither field -- frozen, never
    # back-filled (REQ-V170-NG-03).
    assert "reasoning" not in real_baseline["meta"]
    for run in real_baseline["runs"]:
        for call in run["llm_calls"]:
            assert "reasoning_requested" not in call
            assert "reasoning_honored" not in call
    # bench.py check still exits 0 on it after LLM_CALL_COLUMNS widened.
    code, reason = bench.check_document(real_baseline, mode="strict")
    assert (code, reason) == (0, "valid")
    assert "reasoning" not in bench.LOCKED_META_FIELDS

    # A candidate-shaped document carrying both also passes check.
    candidate = _candidate_from_real_baseline(real_baseline)
    code, reason = bench.check_document(candidate, mode="strict")
    assert (code, reason) == (0, "valid")

    for policy in ("model-default", "off", "by-purpose"):
        cfg_stub = type("Cfg", (), {
            "llm_reasoning_policy": policy,
            "llm_reasoning_on_purposes": frozenset({"final", "tool-round"}),
        })()
        meta = bench.reasoning_meta(cfg_stub, "lmstudio")
        assert meta["policy"] == policy  # present on every run, model-default included
        assert meta["on_purposes"] == ["final", "tool-round"]  # sorted
        assert meta["mechanism"]["tool-round"] is None  # no off-mechanism -> null
        assert meta["mechanism"]["summary"] is not None


def test_t_v170_ben_02_comparability_against_the_real_baseline():
    real_baseline = _load_real_baseline()
    # The baseline compares clean with itself -- previously impossible
    # (measured refusal: "env_flags.HISTORY_TOOL_STUB must be null on the
    # baseline side"), which is why REQ-V170-BEN-02 exists at all.
    assert bench.comparability(real_baseline, real_baseline) is None

    # A treatment-only pair (only env_flags.LLM_REASONING_POLICY/_ON_PURPOSES
    # and git_commit differ) compares clean too.
    treated = _candidate_from_real_baseline(real_baseline)
    treated["meta"]["env_flags"]["LLM_REASONING_POLICY"] = "off"
    treated["meta"]["env_flags"]["LLM_REASONING_ON_PURPOSES"] = ""
    assert bench.comparability(real_baseline, treated) is None

    generation_changed = _candidate_from_real_baseline(real_baseline)
    generation_changed["meta"]["generation_settings"] = dict(
        generation_changed["meta"]["generation_settings"], agent={"temperature": 1}
    )
    reason = bench.comparability(real_baseline, generation_changed)
    assert reason is not None and "locked meta field differs" in reason

    stub_changed = _candidate_from_real_baseline(real_baseline)
    stub_changed["meta"]["env_flags"]["HISTORY_TOOL_STUB"] = "off"
    assert bench.comparability(real_baseline, stub_changed) == (
        "env_flags.HISTORY_TOOL_STUB differs"
    )

    failover_changed = _candidate_from_real_baseline(real_baseline)
    failover_changed["meta"]["env_flags"]["LLM_FAILOVER"] = "auto"
    reason = bench.comparability(real_baseline, failover_changed)
    assert reason is not None and "LLM_FAILOVER" in reason

    routed = _candidate_from_real_baseline(real_baseline)
    routed["meta"]["env_flags"]["LLM_SUMMARY_MODEL"] = "openrouter:cheap/model"
    reason = bench.comparability(real_baseline, routed)
    assert reason is not None and "LLM_SUMMARY_MODEL" in reason


def test_t_v170_ben_03_config_sha256_excludes_only_the_treatment():
    base = load_config(env=base_env(), load_env_file=False)
    treated = dataclasses.replace(
        base, llm_reasoning_policy="off", llm_reasoning_on_purposes=frozenset()
    )
    assert bench.config_sha256(base) == bench.config_sha256(treated)

    non_excluded_changed = dataclasses.replace(base, llm_max_tokens=base.llm_max_tokens + 1)
    assert bench.config_sha256(base) != bench.config_sha256(non_excluded_changed)


def test_t_v170_ben_04_and_ben_06_gate_verdicts_against_the_real_baseline(tmp_path):
    real_baseline = _load_real_baseline()
    base_path = tmp_path / "baseline.json"
    base_path.write_text(json.dumps(real_baseline), encoding="utf-8")

    def _report(candidate: dict) -> int:
        cand_path = tmp_path / "candidate.json"
        cand_path.write_text(json.dumps(candidate), encoding="utf-8")
        return bench.main([
            "report", "--baseline", str(base_path), "--candidate", str(cand_path),
            "--gate", "--out", str(tmp_path / "report.md"),
        ])

    both_pass = _candidate_from_real_baseline(real_baseline, scale=0.5, fix_failures=True)
    assert _report(both_pass) == 0

    cost_fails = _candidate_from_real_baseline(real_baseline, scale=1.0, fix_failures=True)
    assert _report(cost_fails) == 1

    s18_stays_2_of_3 = _candidate_from_real_baseline(real_baseline, scale=0.5, fix_failures=False)
    assert s18_stays_2_of_3["summary"]["per_scenario"]["S18"] == {
        **s18_stays_2_of_3["summary"]["per_scenario"]["S18"], "success": 2, "of": 3,
    }
    v = bench.verdict(real_baseline, s18_stays_2_of_3)
    assert v.passed is False
    assert any("S18 2/3" in line for line in v.lines)
    # item 2 (two-repeat-loss) does NOT catch a 2-of-3 alone -- prove the new
    # rule is the one doing the work, not the old one.
    assert not any("regressed scenarios" in line and "S18" in line for line in v.lines)
    assert _report(s18_stays_2_of_3) == 1

    two_repeat_loss = _candidate_from_real_baseline(real_baseline, scale=0.5, fix_failures=True)
    s01_runs = [r for r in two_repeat_loss["runs"] if r["scenario"] == "S01"]
    for run in s01_runs[:2]:
        run["success"] = False
        run["failure"] = "checks"
    two_repeat_loss["summary"] = bench.summarize(
        two_repeat_loss["runs"], two_repeat_loss["meta"]["skipped_scenarios"],
        two_repeat_loss["meta"]["repeats"],
    )
    assert _report(two_repeat_loss) == 1

    timeout_trap = _candidate_from_real_baseline(real_baseline, scale=0.5, fix_failures=True)
    timeout_trap["meta"]["timeout_s"] = 600.0
    assert _report(timeout_trap) == 2


def test_n6_aborted_candidate_refused_before_per_scenario():
    real_baseline = _load_real_baseline()
    candidate = _candidate_from_real_baseline(real_baseline, scale=0.5, fix_failures=True)
    candidate["meta"]["aborted"] = "timeout:S05-2"
    code, reason = bench.check_document(candidate, mode="strict")
    assert code == bench.EXIT_NOT_COMPARABLE
    assert "aborted" in reason
    v = bench.verdict(real_baseline, candidate)
    assert v.passed is False


def test_t_v170_ben_05_gate_required_full_scenarios_shape():
    assert bench.GATE_REQUIRED_FULL_SCENARIOS == ("S13", "S14", "S15", "S16", "S17", "S18")
    from llm.base import REQUEST_DEFAULTS
    assert "GATE_REQUIRED_FULL_SCENARIOS" not in bench.constants()
    assert "GATE_REQUIRED_FULL_SCENARIOS" not in REQUEST_DEFAULTS
    real_baseline = _load_real_baseline()
    assert bench.scenarios_sha256() == real_baseline["meta"]["scenarios_sha256"]


# --------------------------------------------------------------------------
# T-V170-CAR-01, N7 -- the --tag sanitiser
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tag", [
    "baseline-v1.6.0", "cand-v170-off", "a", "a" * 64,
])
def test_t_v170_car_01_tag_accepts(tag):
    assert bench._TAG_RE.match(tag) is not None
    assert tag not in (".", "..")


@pytest.mark.parametrize("tag", [
    "..", ".", "a/b", "../x", "a\\b", "", "a" * 65, "a b",
])
def test_t_v170_car_01_tag_rejects(tag):
    assert tag in (".", "..") or bench._TAG_RE.match(tag) is None


def test_n7_tag_escape_refused_before_any_filesystem_write(monkeypatch, capsys):
    def _forbidden(*args, **kwargs):
        raise AssertionError("shutil.rmtree must not be called")

    monkeypatch.setattr(shutil, "rmtree", _forbidden)
    code = bench.main(["run", "--tag", "../escape"])
    assert code == bench.EXIT_ERROR
    err = capsys.readouterr().err
    assert "--tag" in err and "[A-Za-z0-9._-]" in err
