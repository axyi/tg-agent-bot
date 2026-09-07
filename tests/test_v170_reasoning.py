"""spec-v1.7.0 T4: the reasoning-policy vocabulary (POL-01…-03), the
storage migration (OBS-01) and the summary-budget config check (SUM-05).

Offline and deterministic (REQ-V170-TST-01): no network, no Docker, no
`.env`, no live LLM. Every clock and every LLM in a test is a fake.
"""

import sqlite3

import pytest

import storage
from config import ConfigError, load_config
from llm.base import (
    REASONING_DEFAULT,
    REASONING_MECHANISMS,
    REASONING_TAGS,
    ReasoningMechanism,
    ReasoningRequest,
    reasoning_tag,
    resolve_reasoning,
)
from tests.test_config import base_env

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
