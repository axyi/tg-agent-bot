"""Tracing layer -- spec-v1.6.0 section 5 (REQ-V160-TRC-*).

T1's own tests, plus T2's (schema 3 -> 4, the `spans` table, `storage.py`'s
three new helpers and the sink seam exercised against a real connection).

Offline, deterministic, no Docker, no network. Only synthetic canaries are
used as secrets, registered through `config.register_secret`.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sqlite3

import pytest

import agent
import config
import storage
import tracing
from llm.base import LLMError, LLMResponse
from tests.fakes import FakeLLM, RecordingRunner
from tests.test_observability import NOW, USER_ID, llm_rows, make_cfg, run, tool_call, tool_rows

CANARY = "SYNTHETIC-CANARY-TRC-NEVER-A-LIVE-VALUE"

# A version-3 database on disk, written literally (mirrors `V2_SCHEMA` in
# `tests/test_observability.py`): `storage.init_schema` now emits v4, so it
# cannot be used to build the fixture the 3 -> 4 migration is fed.
V3_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 3);

CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER NOT NULL,
    created_at TEXT    NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_one_active
    ON conversations (tg_user_id) WHERE active = 1;

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id         INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn_id         INTEGER NOT NULL,
    role            TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content         TEXT    NOT NULL DEFAULT '',
    tool_calls_json TEXT,
    tool_call_id    TEXT,
    created_at      TEXT    NOT NULL,
    CHECK (
        (role = 'user'      AND tool_calls_json IS NULL AND tool_call_id IS NULL)
     OR (role = 'assistant' AND tool_call_id IS NULL)
     OR (role = 'tool'      AND tool_calls_json IS NULL AND tool_call_id IS NOT NULL)
    ),
    CHECK (tool_calls_json IS NULL OR json_valid(tool_calls_json))
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages (conv_id, id);

CREATE TABLE IF NOT EXISTS bot_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id      INTEGER NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
    tg_user_id   INTEGER NOT NULL,
    created_at   TEXT    NOT NULL,
    summary_json TEXT    NOT NULL CHECK (json_valid(summary_json))
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id                   INTEGER PRIMARY KEY,
    conv_id              INTEGER NOT NULL REFERENCES conversations(id),
    turn_id              INTEGER,
    purpose              TEXT    NOT NULL CHECK (purpose IN ('agent', 'summary')),
    round                INTEGER NOT NULL,
    attempt              INTEGER NOT NULL,
    ts                   TEXT    NOT NULL,
    provider             TEXT    NOT NULL,
    model                TEXT    NOT NULL,
    prompt_tokens        INTEGER,
    completion_tokens    INTEGER,
    total_tokens         INTEGER,
    cached_tokens        INTEGER,
    reasoning_tokens     INTEGER,
    reasoning_chars      INTEGER NOT NULL DEFAULT 0,
    prompt_chars         INTEGER NOT NULL,
    prompt_chars_by_role TEXT    NOT NULL,
    messages_n           INTEGER NOT NULL,
    tools_exposed        INTEGER NOT NULL,
    latency_ms           INTEGER NOT NULL,
    finish_reason        TEXT,
    tool_calls_n         INTEGER NOT NULL DEFAULT 0,
    error_kind           TEXT,
    cost_usd             REAL,
    cost_basis           TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_conv ON llm_calls (conv_id, id);

CREATE TABLE IF NOT EXISTS tool_calls (
    id                INTEGER PRIMARY KEY,
    conv_id           INTEGER NOT NULL REFERENCES conversations(id),
    turn_id           INTEGER NOT NULL,
    tool_call_id      TEXT    NOT NULL,
    tool              TEXT    NOT NULL,
    ts                TEXT    NOT NULL,
    input_chars       INTEGER NOT NULL,
    raw_output_chars  INTEGER NOT NULL,
    output_chars      INTEGER NOT NULL,
    output_tokens_est INTEGER NOT NULL,
    duration_ms       INTEGER NOT NULL,
    outcome           TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_conv ON tool_calls (conv_id, id);
"""

# A version-1 database, minimal (mirrors `V0_SCHEMA` in `tests/test_summary.py`).
V1_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 1);

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
"""

# A version-2 database (mirrors `V2_SCHEMA` in `tests/test_observability.py`,
# minus the CHECK constraints that don't matter to a chain-migration smoke test).
V2_SCHEMA = (
    V1_SCHEMA.replace(
        "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 1);",
        "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 2);",
    )
    + """
CREATE TABLE IF NOT EXISTS summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id      INTEGER NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
    tg_user_id   INTEGER NOT NULL,
    created_at   TEXT    NOT NULL,
    summary_json TEXT    NOT NULL
);
"""
)


@pytest.fixture(autouse=True)
def _reset_tracing_state():
    tracing._dropped_spans = 0
    tracing.set_run_context(None, None)
    yield
    tracing.set_run_context(None, None)


# --- T-V160-TRC-01 -----------------------------------------------------


def test_t_v160_trc_01_module_resolves_to_a_py_file_not_a_package():
    # dashboard_render and dashboard_server are added at T5/T6; this check
    # widens to cover them once those modules exist (REQ-V160-TREE-03).
    for name in ("tracing", "dashboard_render"):
        spec = importlib.util.find_spec(name)
        assert spec is not None, name
        assert spec.origin is not None and spec.origin.endswith(".py"), name
        assert spec.submodule_search_locations is None, f"{name} is a package, not a module"


# --- T-V160-TRC-02 -------------------------------------------------------


def test_t_v160_trc_02_ids_are_fixed_width_hex_and_unique():
    trace_id = tracing.new_trace_id()
    span_id = tracing.new_span_id()
    assert len(trace_id) == 32
    assert all(c in "0123456789abcdef" for c in trace_id)
    assert len(span_id) == 16
    assert all(c in "0123456789abcdef" for c in span_id)
    assert tracing.new_span_id() != tracing.new_span_id()


def test_t_v160_trc_02_nested_span_inherits_trace_and_records_parent():
    with tracing.start_span("outer", tracing.KIND_INTERNAL) as outer:
        with tracing.start_span("inner", tracing.KIND_CLIENT) as inner:
            assert inner.trace_id == outer.trace_id
            assert inner.parent_span_id == outer.span_id
            assert inner.span_id != outer.span_id


# --- T-V160-TRC-09 ---------------------------------------------------------


def test_t_v160_trc_09_set_attribute_rejects_unlisted_key():
    with tracing.start_span("s", tracing.KIND_INTERNAL) as span:
        with pytest.raises(ValueError, match="bogus.key"):
            span.set_attribute("bogus.key", "x")


def test_t_v160_trc_09_content_attributes_absent_when_capture_is_false():
    with tracing.start_span("s", tracing.KIND_CLIENT) as span:
        for key in tracing.CONTENT_ATTRIBUTE_KEYS:
            tracing.set_content_attribute(span, key, "some content", capture=False)
        assert not (tracing.CONTENT_ATTRIBUTE_KEYS & span.attributes.keys())


def test_t_v160_trc_09_content_attributes_present_when_capture_is_true():
    with tracing.start_span("s", tracing.KIND_CLIENT) as span:
        for key in tracing.CONTENT_ATTRIBUTE_KEYS:
            tracing.set_content_attribute(span, key, "some content", capture=True)
        assert tracing.CONTENT_ATTRIBUTE_KEYS <= span.attributes.keys()


# --- T-V160-TRC-11 -----------------------------------------------------


def test_t_v160_trc_11_status_message_is_redacted_then_truncated(monkeypatch):
    config.register_secret(CANARY)
    captured = {}
    monkeypatch.setattr(
        tracing.NullSink, "write", lambda self, span: captured.__setitem__("span", span)
    )
    with pytest.raises(RuntimeError):
        with tracing.start_span("s", tracing.KIND_INTERNAL):
            raise RuntimeError("boom: " + CANARY)
    message = captured["span"].status_message
    assert CANARY not in message
    assert config.REDACTION in message


def test_t_v160_trc_11_secret_straddling_the_boundary_does_not_survive(monkeypatch):
    # redact-then-truncate order matters exactly here: "RuntimeError: " (14
    # chars) + 180 filler puts the secret's 32 characters spanning position
    # 200 in the *unredacted* text. A truncate-first bug would leave a
    # fragment of the raw secret sitting in the 200-character result,
    # unmatched by redact()'s whole-string replacement.
    config.register_secret(CANARY)
    captured = {}
    monkeypatch.setattr(
        tracing.NullSink, "write", lambda self, span: captured.__setitem__("span", span)
    )
    padding = "x" * 180
    with pytest.raises(RuntimeError):
        with tracing.start_span("s", tracing.KIND_INTERNAL):
            raise RuntimeError(padding + CANARY)
    message = captured["span"].status_message
    assert CANARY not in message
    assert CANARY[:16] not in message
    assert CANARY[-16:] not in message


# --- T-V160-TRC-12 -----------------------------------------------------


def test_t_v160_trc_12_exception_sets_error_and_reraises():
    with pytest.raises(ValueError):
        with tracing.start_span("s", tracing.KIND_INTERNAL) as span:
            raise ValueError("boom")
    assert span.status == tracing.STATUS_ERROR
    assert span.status_message is not None


def test_t_v160_trc_12_no_sink_uses_null_sink(monkeypatch):
    calls = []
    monkeypatch.setattr(tracing.NullSink, "write", lambda self, span: calls.append(span))
    with tracing.start_span("s", tracing.KIND_INTERNAL):
        pass
    assert len(calls) == 1


def test_t_v160_trc_12_non_sqlite_sink_failure_is_swallowed_and_counted(caplog):
    class FlakySink:
        def write(self, span):
            raise RuntimeError("sink is down")

    before = tracing.dropped_spans()
    with caplog.at_level(logging.WARNING, logger="tracing"):
        with tracing.start_span("s", tracing.KIND_INTERNAL, sink=FlakySink()):
            pass
    assert tracing.dropped_spans() == before + 1
    assert any("sink is down" in r.message or "RuntimeError" in r.message for r in caplog.records)


def test_t_v160_trc_12_non_sqlite_sink_failure_does_not_mask_body_exception():
    class FlakySink:
        def write(self, span):
            raise RuntimeError("sink is down")

    with pytest.raises(ValueError, match="body raised this"):
        with tracing.start_span("s", tracing.KIND_INTERNAL, sink=FlakySink()):
            raise ValueError("body raised this")


def test_t_v160_trc_12_sqlite_sink_failure_propagates(monkeypatch):
    def failing_add_span(conn, **kwargs):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(tracing.storage, "add_span", failing_add_span, raising=False)
    sink = tracing.SqliteSpanSink(conn=object())
    with pytest.raises(RuntimeError, match="insert failed"):
        with tracing.start_span("s", tracing.KIND_CLIENT, sink=sink):
            pass


def test_t_v160_trc_12_second_finish_raises():
    with tracing.start_span("s", tracing.KIND_INTERNAL) as span:
        pass
    with pytest.raises(RuntimeError):
        span.finish()


# --- T-V160-TRC-06 -- SPAN_COLUMNS and the derived "span" log payload -------


def _add_span_row(conn, **overrides):
    fields = {
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "parent_span_id": None,
        "conv_id": None,
        "turn_id": None,
        "name": "invoke_agent tg-agent-bot",
        "kind": "INTERNAL",
        "ts": "2026-09-04T00:00:00Z",
        "start_ns": 1_000,
        "duration_ms": 5,
        "status": "ok",
        "status_message": None,
        "attributes_json": "{}",
    }
    fields.update(overrides)
    return storage.add_span(conn, **fields)


def test_t_v160_trc_06_span_columns_matches_pragma_table_info(conn):
    pragma_columns = [row["name"] for row in conn.execute("PRAGMA table_info(spans)")]
    assert list(storage.SPAN_COLUMNS) == pragma_columns


def test_t_v160_trc_06_span_log_payload_keys_equal_span_columns(conn, caplog):
    caplog.set_level(logging.INFO, logger="storage")
    _add_span_row(conn)
    payloads = [
        json.loads(record.getMessage()[len("span ") :])
        for record in caplog.records
        if record.getMessage().startswith("span ")
    ]
    assert len(payloads) == 1
    assert set(payloads[0]) == set(storage.SPAN_COLUMNS)


# --- T-V160-TRC-07 -- migration 3 -> 4 --------------------------------------


def _seed_v3_database(path):
    legacy = sqlite3.connect(str(path), isolation_level=None)
    legacy.executescript(V3_SCHEMA)
    legacy.execute("INSERT INTO conversations (tg_user_id, created_at, active) VALUES (7, 'x', 1)")
    legacy.execute(
        "INSERT INTO llm_calls (conv_id, turn_id, purpose, round, attempt, ts, provider, "
        "model, prompt_chars, prompt_chars_by_role, messages_n, tools_exposed, latency_ms) "
        "VALUES (1, 1, 'agent', 1, 1, 'x', 'lmstudio', 'small', 10, '{}', 2, 3, 5)"
    )
    legacy.execute(
        "INSERT INTO tool_calls (conv_id, turn_id, tool_call_id, tool, ts, input_chars, "
        "raw_output_chars, output_chars, output_tokens_est, duration_ms, outcome) "
        "VALUES (1, 1, 'call_1', 'exec', 'x', 10, 10, 10, 3, 5, 'ok')"
    )
    legacy.close()


def test_t_v160_trc_07_migration_3_to_4_adds_spans_and_nullable_columns(tmp_path):
    path = tmp_path / "v3.db"
    _seed_v3_database(path)

    conn = storage.connect(path)
    storage.init_schema(conn)
    assert storage.schema_version(conn) == 5
    assert (
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'spans'"
        ).fetchone()
        is not None
    )

    llm_row = conn.execute("SELECT * FROM llm_calls").fetchone()
    assert llm_row["trace_id"] is None
    assert llm_row["span_id"] is None
    tool_row = conn.execute("SELECT * FROM tool_calls").fetchone()
    assert tool_row["trace_id"] is None
    assert tool_row["span_id"] is None
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 1

    # Idempotence: a second init_schema changes nothing further.
    storage.init_schema(conn)
    assert storage.schema_version(conn) == 5
    assert conn.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0] == 1
    conn.close()


def test_t_v160_trc_07_migration_1_to_4_chains(tmp_path):
    path = tmp_path / "v1.db"
    legacy = sqlite3.connect(str(path), isolation_level=None)
    legacy.executescript(V1_SCHEMA)
    legacy.execute("INSERT INTO conversations (tg_user_id, created_at, active) VALUES (7, 'x', 1)")
    legacy.close()

    conn = storage.connect(path)
    storage.init_schema(conn)
    assert storage.schema_version(conn) == 5
    for table in ("summaries", "llm_calls", "tool_calls", "spans"):
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
            ).fetchone()
            is not None
        ), table
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 1
    conn.close()


def test_t_v160_trc_07_migration_2_to_4_chains(tmp_path):
    path = tmp_path / "v2.db"
    legacy = sqlite3.connect(str(path), isolation_level=None)
    legacy.executescript(V2_SCHEMA)
    legacy.execute("INSERT INTO conversations (tg_user_id, created_at, active) VALUES (7, 'x', 1)")
    legacy.close()

    conn = storage.connect(path)
    storage.init_schema(conn)
    assert storage.schema_version(conn) == 5
    for table in ("llm_calls", "tool_calls", "spans"):
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
            ).fetchone()
            is not None
        ), table
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 1
    conn.close()


# --- T-V160-TRC-08 -- unsupported versions ----------------------------------


@pytest.mark.parametrize("bad_version", [0, 6, "x"])
def test_t_v160_trc_08_unsupported_version_raises(conn, bad_version):
    conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (bad_version,))
    with pytest.raises(RuntimeError) as raised:
        storage.init_schema(conn)
    assert str(bad_version) in str(raised.value)


# --- T-V160-TRC-13 -- the sink seam against a real connection ---------------


def test_t_v160_trc_13_sqlite_span_sink_writes_one_row_on_the_real_connection(conn):
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    sink = tracing.SqliteSpanSink(conn)
    with tracing.start_span("chat model", tracing.KIND_CLIENT, sink=sink, conv_id=conv_id) as span:
        pass
    rows = conn.execute("SELECT * FROM spans").fetchall()
    assert len(rows) == 1
    assert rows[0]["span_id"] == span.span_id
    assert rows[0]["trace_id"] == span.trace_id
    assert rows[0]["conv_id"] == conv_id
    assert rows[0]["status"] == "ok"


def test_t_v160_trc_13_second_finish_raises_on_the_real_sink(conn):
    sink = tracing.SqliteSpanSink(conn)
    with tracing.start_span("chat model", tracing.KIND_CLIENT, sink=sink) as span:
        pass
    with pytest.raises(RuntimeError):
        span.finish()
    # The exit path never re-finishes: still exactly one row.
    assert conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0] == 1


def test_t_v160_trc_13_add_span_opens_no_transaction_of_its_own(conn):
    """`add_span` must be a plain INSERT relying on the caller's transaction,
    exactly like `add_llm_call`/`add_tool_call` -- so the REQ-V160-TRC-07
    sequence can wrap it and a call-row insert in one `BEGIN IMMEDIATE`
    without ever nesting one. If `add_span` opened its own transaction, this
    `BEGIN IMMEDIATE` would raise `sqlite3.OperationalError` here."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        _add_span_row(conn)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    assert conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0] == 1


def test_t_v160_trc_13_add_tool_turn_body_reusable_without_nesting(conn):
    """REQ-V160-TRC-07: `add_tool_turn`'s transaction body, exposed as
    `_add_tool_turn_body`, must be callable inside a transaction the caller
    already opened -- the shape the future root-span sequence (T3) needs. If
    it issued its own `BEGIN IMMEDIATE`, this would raise
    `sqlite3.OperationalError` instead of returning a turn id."""
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    conn.execute("BEGIN IMMEDIATE")
    try:
        turn_id = storage._add_tool_turn_body(conn, conv_id, "assistant text", [], [])
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    assert turn_id == 1
    row = conn.execute(
        "SELECT role, content FROM messages WHERE conv_id = ? AND turn_id = ?",
        (conv_id, turn_id),
    ).fetchone()
    assert row["role"] == "assistant" and row["content"] == "assistant text"


def test_t_v160_trc_13_add_tool_turn_still_works_and_redacts(conn):
    """`add_tool_turn`'s own signature and behaviour stay byte-identical for
    today's callers (REQ-V160-TRC-07): it still redacts and still wraps its
    own transaction."""
    config.register_secret(CANARY)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    turn_id = storage.add_tool_turn(
        conn, conv_id, f"leaked: {CANARY}", [{"id": "call_1"}], [("call_1", "ok")]
    )
    row = conn.execute(
        "SELECT content FROM messages WHERE conv_id = ? AND turn_id = ? AND role = 'assistant'",
        (conv_id, turn_id),
    ).fetchone()
    assert CANARY not in row["content"]
    assert config.REDACTION in row["content"]


# --- T-V160-SRV-06 (storage half) -- the read-only connection --------------


def test_t_v160_srv_06_readonly_connection_rejects_insert(tmp_path):
    path = tmp_path / "ro.db"
    conn = storage.connect(path)
    storage.init_schema(conn)
    conn.close()

    ro = storage.connect_readonly(path)
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("INSERT INTO conversations (tg_user_id, created_at, active) VALUES (99, 'x', 1)")
    ro.close()


def test_t_v160_srv_06_readonly_connect_missing_database_raises(tmp_path):
    missing = tmp_path / "does-not-exist.db"
    with pytest.raises(sqlite3.OperationalError):
        storage.connect_readonly(missing)
    assert not missing.exists()


# --- storage.spans_for_trace / storage.recent_traces (REQ-V160-TRC-12) -----


def test_spans_for_trace_orders_by_id(conn):
    trace_id = "c" * 32
    first = _add_span_row(conn, trace_id=trace_id, span_id="1" * 16, name="root")
    second = _add_span_row(
        conn, trace_id=trace_id, span_id="2" * 16, parent_span_id="1" * 16, name="child"
    )
    other_trace = _add_span_row(conn, trace_id="d" * 32, span_id="3" * 16, name="other")
    rows = storage.spans_for_trace(conn, trace_id)
    assert [row["id"] for row in rows] == [first, second]
    assert other_trace not in [row["id"] for row in rows]


def test_recent_traces_reports_the_root_span_and_aggregates(conn):
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    trace_a = "a" * 32
    _add_span_row(
        conn,
        trace_id=trace_a,
        span_id="1" * 16,
        conv_id=conv_id,
        name="invoke_agent tg-agent-bot",
        ts="2026-09-04T00:00:00Z",
        duration_ms=10,
    )
    _add_span_row(
        conn,
        trace_id=trace_a,
        span_id="2" * 16,
        parent_span_id="1" * 16,
        conv_id=conv_id,
        name="chat model",
        ts="2026-09-04T00:00:01Z",
        duration_ms=20,
    )
    trace_b = "b" * 32
    _add_span_row(
        conn,
        trace_id=trace_b,
        span_id="3" * 16,
        conv_id=conv_id,
        name="invoke_agent tg-agent-bot",
        ts="2026-09-04T00:01:00Z",
        duration_ms=5,
    )

    rows = storage.recent_traces(conn, limit=10)
    assert [row["trace_id"] for row in rows] == [trace_b, trace_a]
    newest, oldest = rows
    assert newest["name"] == "invoke_agent tg-agent-bot"
    assert newest["span_count"] == 1
    assert oldest["span_count"] == 2
    assert oldest["total_duration_ms"] == 30


def test_recent_traces_respects_limit_and_conv_id(conn):
    conv_1 = storage.get_or_create_active_conversation(conn, 1)
    conv_2 = storage.get_or_create_active_conversation(conn, 2)
    _add_span_row(conn, trace_id="a" * 32, span_id="1" * 16, conv_id=conv_1)
    _add_span_row(conn, trace_id="b" * 32, span_id="2" * 16, conv_id=conv_2)

    only_conv_1 = storage.recent_traces(conn, limit=10, conv_id=conv_1)
    assert [row["trace_id"] for row in only_conv_1] == ["a" * 32]

    capped = storage.recent_traces(conn, limit=1)
    assert len(capped) == 1


# ============================================================================
# T3 -- agent.py span wiring (REQ-V160-TRC-04, -07, -08, -09, -10, -14)
# ============================================================================


def _trace_id_of(conn) -> str:
    traces = storage.recent_traces(conn, limit=10)
    assert len(traces) == 1, "expected exactly one trace"
    return traces[0]["trace_id"]


# --- T-V160-TRC-03: the span tree ------------------------------------------


def test_t_v160_trc_03_span_tree_for_a_two_round_tool_turn(conn):
    script = [
        LLMResponse("", [tool_call()], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ]
    reply, _, _ = run(conn, script)
    assert reply == "done"

    trace_id = _trace_id_of(conn)
    spans = storage.spans_for_trace(conn, trace_id)
    roots = [s for s in spans if s["parent_span_id"] is None]
    assert len(roots) == 1
    root = roots[0]
    assert root["name"] == "invoke_agent tg-agent-bot"
    assert root["kind"] == "INTERNAL"

    children = [s for s in spans if s["parent_span_id"] == root["span_id"]]
    chat_children = [s for s in children if s["name"].startswith("chat ")]
    tool_children = [s for s in children if s["name"].startswith("execute_tool ")]
    assert len(chat_children) == 2
    assert len(tool_children) == 1
    assert all(s["kind"] == "CLIENT" for s in chat_children)
    assert all(s["kind"] == "INTERNAL" for s in tool_children)
    assert len(spans) == 1 + len(chat_children) + len(tool_children)


# --- T-V160-TRC-04: chat span / llm_calls bijection, rollback --------------


def test_t_v160_trc_04_a_non_retried_failure_gets_one_error_chat_span(conn):
    script = [LLMError("boom", retryable=False)]
    run(conn, script)
    rows = llm_rows(conn)
    assert len(rows) == 1

    trace_id = _trace_id_of(conn)
    spans = storage.spans_for_trace(conn, trace_id)
    chat_spans = [s for s in spans if s["name"].startswith("chat")]
    assert len(chat_spans) == 1
    assert chat_spans[0]["status"] == "error"
    assert chat_spans[0]["span_id"] == rows[0]["span_id"]
    assert chat_spans[0]["trace_id"] == rows[0]["trace_id"]
    assert rows[0]["turn_id"] is not None


def test_t_v160_trc_04_bijection_holds_across_a_retried_failure(conn):
    script = [LLMError("boom", retryable=True), LLMResponse("done", [], "stop")]
    run(conn, script)
    rows = llm_rows(conn)
    assert len(rows) == 2

    trace_id = _trace_id_of(conn)
    spans = storage.spans_for_trace(conn, trace_id)
    chat_span_ids = {s["span_id"] for s in spans if s["name"].startswith("chat")}
    row_span_ids = {r["span_id"] for r in rows}
    assert chat_span_ids == row_span_ids
    assert len(chat_span_ids) == 2
    # every row's own trace_id/span_id resolves to a distinct spans row
    for row in rows:
        matching = [s for s in spans if s["span_id"] == row["span_id"]]
        assert len(matching) == 1


def test_t_v160_trc_04_add_span_failure_rolls_back_the_llm_call_row(conn, monkeypatch):
    def failing_add_span(c, **kwargs):
        raise sqlite3.OperationalError("boom")

    monkeypatch.setattr(storage, "add_span", failing_add_span)
    script = [LLMError("http fail", retryable=False)]
    with pytest.raises(sqlite3.OperationalError):
        run(conn, script)
    assert llm_rows(conn) == []
    assert conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0] == 0


# --- T-V160-TRC-05: execute_tool span / tool_calls bijection, rollback -----


def test_t_v160_trc_05_execute_tool_spans_bijection_with_tool_calls(conn):
    script = [
        LLMResponse("", [tool_call()], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ]
    run(conn, script)
    rows = tool_rows(conn)
    assert len(rows) == 1

    trace_id = _trace_id_of(conn)
    spans = storage.spans_for_trace(conn, trace_id)
    tool_spans = [s for s in spans if s["name"].startswith("execute_tool")]
    assert len(tool_spans) == 1
    assert tool_spans[0]["span_id"] == rows[0]["span_id"]
    assert tool_spans[0]["kind"] == "INTERNAL"


def test_t_v160_trc_05_budget_and_rejected_outcomes_get_their_own_spans(conn):
    # MAX_TOOL_CALLS_PER_RESPONSE is 3: five offered calls means two land in
    # `excess`, executed=0, outcome="rejected" for each.
    calls = [tool_call(index=i) for i in range(1, 6)]
    script = [LLMResponse("", calls, "tool_calls"), LLMResponse("done", [], "stop")]
    run(conn, script)
    rows = tool_rows(conn)
    assert len(rows) == 5
    assert sum(1 for r in rows if r["outcome"] == "rejected") == 2

    trace_id = _trace_id_of(conn)
    spans = storage.spans_for_trace(conn, trace_id)
    tool_spans = [s for s in spans if s["name"].startswith("execute_tool")]
    assert len(tool_spans) == len(rows)
    assert {s["span_id"] for s in tool_spans} == {r["span_id"] for r in rows}


def test_t_v160_trc_05_add_span_failure_rolls_back_only_the_tool_call_row(conn, monkeypatch):
    real_add_span = storage.add_span

    def selective_failing_add_span(c, **kwargs):
        if kwargs.get("name", "").startswith("execute_tool"):
            raise sqlite3.OperationalError("boom")
        return real_add_span(c, **kwargs)

    monkeypatch.setattr(storage, "add_span", selective_failing_add_span)
    script = [LLMResponse("", [tool_call()], "tool_calls"), LLMResponse("done", [], "stop")]
    with pytest.raises(sqlite3.OperationalError):
        run(conn, script)
    assert tool_rows(conn) == []
    # round 1's chat span/row landed fine -- only the execute_tool insert failed
    assert len(llm_rows(conn)) == 1
    assert (
        conn.execute("SELECT COUNT(*) FROM spans WHERE name LIKE 'execute_tool%'").fetchone()[0]
        == 0
    )


# --- T-V160-TRC-09/-10: content capture, real secret, redacted and bounded -


def test_t_v160_trc_10_content_capture_off_by_default(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    assert cfg.obs_capture_content is False
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    agent.run_agent(
        conn=conn,
        conv_id=conv,
        llm=FakeLLM([LLMResponse("done", [], "stop")]),
        skills={},
        runner=RecordingRunner(),
        now=NOW,
        sleep=lambda _s: None,
        cfg=cfg,
    )
    trace_id = _trace_id_of(conn)
    spans = storage.spans_for_trace(conn, trace_id)
    chat_spans = [s for s in spans if s["name"].startswith("chat")]
    attrs = json.loads(chat_spans[0]["attributes_json"])
    assert not (tracing.CONTENT_ATTRIBUTE_KEYS & attrs.keys())


def test_t_v160_trc_10_content_capture_on_redacts_and_bounds(conn, tmp_path):
    config.register_secret(CANARY)
    cfg = make_cfg(tmp_path, obs_capture_content=True)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, f"please remember {CANARY}")
    agent.run_agent(
        conn=conn,
        conv_id=conv,
        llm=FakeLLM([LLMResponse("done", [], "stop")]),
        skills={},
        runner=RecordingRunner(),
        now=NOW,
        sleep=lambda _s: None,
        cfg=cfg,
    )
    trace_id = _trace_id_of(conn)
    spans = storage.spans_for_trace(conn, trace_id)
    chat_spans = [s for s in spans if s["name"].startswith("chat")]
    attrs = json.loads(chat_spans[0]["attributes_json"])
    assert "gen_ai.input.messages" in attrs
    captured = attrs["gen_ai.input.messages"]
    assert CANARY not in captured
    assert config.REDACTION in captured
    assert len(captured) <= tracing.CONTENT_ATTRIBUTE_MAX_CHARS + 1  # + the "…" mark
    # status_message never carries content -- it isn't a content attribute at all
    assert "status_message" not in attrs


def test_t_v160_trc_10_content_capture_on_redacts_a_fresh_never_stored_secret(
    conn, tmp_path
):
    """The gap the T13 report flagged: unlike the test above, this canary is
    never written through `storage.add_user_message`/`add_assistant_message`
    (both of which redact on the way in) before `set_content_attribute` sees
    it. It arrives fresh inside the FakeLLM response's own `.content`, read
    straight off `response` by `_record_llm_call` -- which runs and captures
    `gen_ai.output.messages` *before* `finish()` ever persists the reply
    (agent.py: `_record_llm_call` at the top of the round loop vs. `finish()`
    only once the round ends). So `tracing.set_content_attribute`'s own
    `config.redact(value)` call is the *only* thing standing between this
    secret and the stored span -- exactly the line the round-3 orchestrator
    hand-mutated (`text = config.redact(value)` -> `text = value`) and found
    zero test failures against, before this test existed.
    """
    fresh_secret = "SYNTHETIC-CANARY-TRC-FRESH-NEVER-STORED-FIRST"
    config.register_secret(fresh_secret)
    cfg = make_cfg(tmp_path, obs_capture_content=True)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    agent.run_agent(
        conn=conn,
        conv_id=conv,
        llm=FakeLLM([LLMResponse(f"the secret is {fresh_secret}", [], "stop")]),
        skills={},
        runner=RecordingRunner(),
        now=NOW,
        sleep=lambda _s: None,
        cfg=cfg,
    )
    trace_id = _trace_id_of(conn)
    spans = storage.spans_for_trace(conn, trace_id)
    chat_spans = [s for s in spans if s["name"].startswith("chat")]
    assert len(chat_spans) == 1
    attrs = json.loads(chat_spans[0]["attributes_json"])
    assert "gen_ai.output.messages" in attrs
    captured = attrs["gen_ai.output.messages"]
    # This is the discriminating assertion: `response.content` has not
    # touched `config.redact()` anywhere else by this point -- the reply is
    # only persisted (redacted, independently) afterward, inside `finish()`.
    assert fresh_secret not in captured
    assert config.REDACTION in captured


# --- T-V160-TRC-14: persistence failure over operation failure, no bare ROLLBACK


def test_t_v160_trc_14_persistence_failure_escapes_over_operation_failure(conn, monkeypatch):
    def failing_add_span(c, **kwargs):
        raise sqlite3.OperationalError("persistence boom")

    monkeypatch.setattr(storage, "add_span", failing_add_span)
    script = [LLMError("operation boom", retryable=True)]
    with pytest.raises(sqlite3.OperationalError, match="persistence boom"):
        run(conn, script)


def test_t_v160_trc_14_a_failed_begin_immediate_is_never_followed_by_a_bare_rollback(tmp_path):
    # A genuine lock, not a mock: `sqlite3.Connection` is a builtin type and
    # cannot have `execute` monkeypatched on it. A second connection holding
    # an EXCLUSIVE lock makes `BEGIN IMMEDIATE` fail for real. If the guarded
    # `if conn.in_transaction: ROLLBACK` were missing or wrong, sqlite3 would
    # raise its own "cannot rollback - no transaction is active" instead,
    # *replacing* this message -- so matching on the original message is
    # itself proof no bare ROLLBACK ran.
    db_path = tmp_path / "locked.db"
    blocker = storage.connect(db_path)
    storage.init_schema(blocker)
    blocker.execute("BEGIN EXCLUSIVE")
    # A short timeout so the test fails fast rather than waiting out
    # `storage.connect`'s 5s retry budget.
    working_conn = sqlite3.connect(str(db_path), isolation_level=None, timeout=0.1)
    working_conn.row_factory = sqlite3.Row
    try:
        script = [LLMResponse("done", [], "stop")]
        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
            run(working_conn, script)
        assert working_conn.in_transaction is False
    finally:
        working_conn.close()
        blocker.execute("ROLLBACK")
        blocker.close()


# --- root-span limit_hit mechanism (feeds T-V160-MET-09, full aggregate at T4)


def test_root_span_records_tool_round_limit_hit(conn):
    # TOOL_ROUND_LIMIT (7) < ROUND_LIMIT (8): a round that keeps offering
    # tool calls always exits through the "tools discarded, not exposed"
    # path at round 8, before the while loop can ever exhaust ROUND_LIMIT
    # naturally -- matching the pre-existing "normally unreachable" comment
    # on the loop's final `return`. This exercises the constant that
    # genuinely fires in that situation.
    script = [LLMResponse("", [tool_call(index=i)], "tool_calls") for i in range(1, 9)]
    run(conn, script)
    trace_id = _trace_id_of(conn)
    spans = storage.spans_for_trace(conn, trace_id)
    root = next(s for s in spans if s["parent_span_id"] is None)
    attrs = json.loads(root["attributes_json"])
    hits = set(attrs.get("tg_agent.limit_hit", "").split(","))
    assert "TOOL_ROUND_LIMIT" in hits
    # only real budget-constant names ever appear
    assert hits <= {
        "ROUND_LIMIT",
        "TOOL_ROUND_LIMIT",
        "HTTP_ATTEMPT_LIMIT",
        "TOOL_EXECUTION_LIMIT",
        "MAX_TOOL_CALLS_PER_RESPONSE",
        "MALFORMED_RETRY_LIMIT",
        "EMPTY_REPAIR_LIMIT",
    }
    assert "MAX_TOOL_CALLS_ACCEPTED" not in hits


def test_root_span_records_max_tool_calls_per_response_hit(conn):
    calls = [tool_call(index=i) for i in range(1, 6)]  # > MAX_TOOL_CALLS_PER_RESPONSE
    script = [LLMResponse("", calls, "tool_calls"), LLMResponse("done", [], "stop")]
    run(conn, script)
    trace_id = _trace_id_of(conn)
    spans = storage.spans_for_trace(conn, trace_id)
    root = next(s for s in spans if s["parent_span_id"] is None)
    attrs = json.loads(root["attributes_json"])
    hits = set(attrs.get("tg_agent.limit_hit", "").split(","))
    assert "MAX_TOOL_CALLS_PER_RESPONSE" in hits


# ============================================================================
# T4 -- metrics.py aggregates (REQ-V160-MET-01..07)
# ============================================================================

import metrics  # noqa: E402 -- appended block, module-level import style matches T1-T3


def _seed_llm_call(conn, conv_id, **overrides):
    fields = {
        "conv_id": conv_id,
        "turn_id": 1,
        "purpose": "agent",
        "round_no": 1,
        "attempt": 1,
        "ts": NOW,
        "provider": "lmstudio",
        "model": "m",
        "prompt_chars": 10,
        "prompt_chars_by_role": {"system": 10, "tools": 0, "user": 0, "assistant": 0, "tool": 0},
        "messages_n": 2,
        "tools_exposed": 0,
        "latency_ms": 100,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "cached_tokens": None,
        "reasoning_tokens": None,
        "finish_reason": "stop",
        "error_kind": None,
        "cost_usd": None,
        "cost_basis": None,
    }
    fields.update(overrides)
    return storage.add_llm_call(conn, **fields)


def test_t_v160_met_02_usage_by_model_groups_the_provider_model_pair(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    _seed_llm_call(conn, conv, provider="lmstudio", model="same-name", prompt_tokens=10)
    _seed_llm_call(conn, conv, provider="openrouter", model="same-name", prompt_tokens=20)
    rows = metrics.usage_by(conn, group="model")
    assert len(rows) == 2
    keys = {r.key for r in rows}
    assert keys == {"lmstudio/same-name", "openrouter/same-name"}
    for row in rows:
        assert row.purpose is None and row.day is None and row.scenario is None


def test_t_v160_met_02_usage_by_rejects_unknown_group(conn):
    with pytest.raises(ValueError, match="nope"):
        metrics.usage_by(conn, group="nope")


def test_t_v160_met_02_usage_by_since_excludes_older_rows_includes_boundary(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    _seed_llm_call(conn, conv, ts="2026-09-01T00:00:00Z")
    _seed_llm_call(conn, conv, ts="2026-09-04T00:00:00Z")
    from datetime import date

    rows = metrics.usage_by(conn, group="purpose", since=date(2026, 9, 4))
    assert sum(r.calls for r in rows) == 1


def test_t_v160_met_03_cache_hit_share_is_none_without_qualifying_rows(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    _seed_llm_call(conn, conv, cached_tokens=None, prompt_tokens=100)
    rows = metrics.usage_by(conn, group="purpose")
    assert rows[0].cache_hit_share is None


def test_t_v160_met_03_cache_hit_share_computed_over_qualifying_rows(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    _seed_llm_call(conn, conv, cached_tokens=50, prompt_tokens=100)
    _seed_llm_call(conn, conv, cached_tokens=10, prompt_tokens=100)
    rows = metrics.usage_by(conn, group="purpose")
    assert rows[0].cache_hit_share == pytest.approx(60 / 200)


def test_t_v160_met_03_mixed_cost_basis_joins_rather_than_picks_one(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    _seed_llm_call(conn, conv, cost_usd=0.01, cost_basis="live")
    _seed_llm_call(conn, conv, cost_usd=0.02, cost_basis="reference")
    rows = metrics.usage_by(conn, group="purpose")
    assert rows[0].cost_basis == "live, reference"


def test_t_v160_met_04_error_breakdown_buckets_nulls(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    _seed_llm_call(conn, conv, finish_reason=None, error_kind=None)
    _seed_llm_call(conn, conv, finish_reason="stop", error_kind="timeout")
    breakdown = metrics.error_breakdown(conn)
    assert breakdown.by_finish_reason["(none)"] == 1
    assert breakdown.by_error_kind["ok"] == 1
    assert breakdown.by_error_kind["timeout"] == 1
    assert breakdown.total == 2
    assert breakdown.error_rate == pytest.approx(0.5)


def test_t_v160_met_11_error_breakdown_caps_at_100_plus_other(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    for i in range(250):
        _seed_llm_call(conn, conv, finish_reason=f"fr{i:04d}", error_kind=f"ek{i:04d}")
    breakdown = metrics.error_breakdown(conn)
    assert len(breakdown.by_finish_reason) == 101
    assert len(breakdown.by_error_kind) == 101
    assert sum(breakdown.by_finish_reason.values()) == breakdown.total == 250
    assert sum(breakdown.by_error_kind.values()) == breakdown.total == 250
    assert breakdown.error_rate == pytest.approx(1.0)


def test_t_v160_met_05_latency_histogram_boundary_and_overflow(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    _seed_llm_call(conn, conv, latency_ms=1280)  # exactly the 1.28s boundary
    _seed_llm_call(conn, conv, latency_ms=999999)  # overflow bucket
    histograms = metrics.latency_histogram(conn)
    assert len(histograms) == 1
    hist = histograms[0]
    assert len(hist.counts) == len(hist.boundaries) + 1
    boundary_index = hist.boundaries.index(1.28)
    assert hist.counts[boundary_index] == 1  # lands in the lower bucket, not the next
    assert hist.counts[-1] == 1  # the overflow bucket
    assert [k for k, _ in hist.attributes] == sorted(k for k, _ in hist.attributes)


def test_t_v160_met_06_token_histogram_per_type_and_dimension(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    _seed_llm_call(conn, conv, provider="a", model="m1", prompt_tokens=10, completion_tokens=5)
    _seed_llm_call(conn, conv, provider="b", model="m2", prompt_tokens=20, completion_tokens=15)
    histograms = metrics.token_histogram(conn, token_type="input")
    assert len(histograms) == 2
    for hist in histograms:
        keys = [k for k, _ in hist.attributes]
        assert "gen_ai.token.type" in keys
        assert keys == sorted(keys)
    with pytest.raises(ValueError, match="bogus"):
        metrics.token_histogram(conn, token_type="bogus")


def test_t_v160_met_07_tool_health_max_consecutive_repeats_within_one_turn(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)

    def add_tool(turn_id, tool, tool_call_id):
        storage.add_tool_call(
            conn,
            conv_id=conv,
            turn_id=turn_id,
            tool_call_id=tool_call_id,
            tool=tool,
            ts=NOW,
            input_chars=1,
            raw_output_chars=1,
            output_chars=1,
            output_tokens_est=1,
            duration_ms=1,
            outcome="ok",
        )

    # turn 1: exec, exec, fetch -- longest run for exec is 2
    add_tool(1, "exec", "c1")
    add_tool(1, "exec", "c2")
    add_tool(1, "fetch", "c3")
    # turn 2 (a different turn): exec alone -- must not extend turn 1's run
    add_tool(2, "exec", "c4")

    rows = {row.tool: row for row in metrics.tool_health(conn)}
    assert rows["exec"].max_consecutive_repeats == 2
    assert rows["fetch"].max_consecutive_repeats == 1


def test_t_v160_met_09_limit_hits_only_reports_the_seven_real_names(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_span(
        conn,
        trace_id="a" * 32,
        span_id="1" * 16,
        parent_span_id=None,
        conv_id=conv,
        turn_id=None,
        name="invoke_agent tg-agent-bot",
        kind="INTERNAL",
        ts=NOW,
        start_ns=0,
        duration_ms=1,
        status="ok",
        status_message=None,
        attributes_json=json.dumps(
            {"tg_agent.limit_hit": "ROUND_LIMIT,TOOL_ROUND_LIMIT,ROUND_LIMIT"}
        ),
    )
    hits = metrics.limit_hits(conn)
    assert hits == {"ROUND_LIMIT": 1, "TOOL_ROUND_LIMIT": 1}
    assert "MAX_TOOL_CALLS_ACCEPTED" not in hits


def test_t_v160_met_10_usage_by_caps_at_500_with_other_remainder(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    for i in range(520):
        _seed_llm_call(conn, conv, provider="p", model=f"m{i:04d}", prompt_tokens=1)
    rows = metrics.usage_by(conn, group="model")
    assert len(rows) == 501
    other = next(r for r in rows if r.key == "(other)")
    assert other.calls == 20
    assert sum(r.calls for r in rows) == 520


def test_t_v160_met_08_stats_and_metrics_report_the_same_totals(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    _seed_llm_call(conn, conv, prompt_tokens=100, completion_tokens=50)
    everywhere = metrics.global_stats(conn)
    usage_total = sum(r.calls for r in metrics.usage_by(conn, group="purpose"))
    assert everywhere.calls == usage_total == 1


def test_summary_health_row_based_formulas(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    _seed_llm_call(conn, conv, purpose="summary", round_no=0, attempt=1, error_kind=None)
    _seed_llm_call(conn, conv, purpose="summary", round_no=0, attempt=1, error_kind="truncated")
    _seed_llm_call(conn, conv, purpose="summary", round_no=0, attempt=2, error_kind="truncated")
    _seed_llm_call(conn, conv, purpose="summary", round_no=0, attempt=1, error_kind="timeout")
    health = metrics.summary_health(conn)
    assert health.attempts == 4
    assert health.ok == 1
    assert health.truncated == 2
    assert health.retried == 1
    # failed: the attempt=2 truncated row, plus the timeout row -- not the
    # lone attempt=1 truncation, which TQ-01 still gets to retry
    assert health.failed == 2


def test_stats_gains_two_lines_appended(conn):
    import bot

    storage.get_or_create_active_conversation(conn, USER_ID)
    lines = bot._render_stats(conn, USER_ID).splitlines()
    assert lines[0] == "Stats (this conversation | all time)"
    assert any(line.startswith("Errors: ") for line in lines)
    assert any(line.startswith("Summaries: ") for line in lines)
    assert lines[-2].startswith("Errors: ")
    assert lines[-1].startswith("Summaries: ")


# ============================================================================
# T8 -- truncated-summary retry, LLM_SUMMARY_MAX_TOKENS, closed outcome
# vocabulary (REQ-V160-TQ-01, -02, -03)
# ============================================================================

from tests.test_config import base_env  # noqa: E402 -- appended block

SUMMARY_PAYLOAD = json.dumps(
    {"goal": "ship it", "files": [], "decisions": [], "errors": [], "next_action": ""}
)


def _seed_summary_history(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hi")
    storage.add_assistant_message(conn, conv, "hello")
    return conv


def test_t_v160_tq_01_double_truncation_proceeds_without_a_summary(conn):
    conv = _seed_summary_history(conn)
    llm = FakeLLM(
        [LLMResponse("cut off", [], "length"), LLMResponse("cut off again", [], "length")]
    )
    result = agent.summarize_conversation(conn, conv, llm, None, retry_max_tokens=1536)
    assert result is None
    rows = llm_rows(conn)
    assert [r["attempt"] for r in rows] == [1, 2]
    assert [r["error_kind"] for r in rows] == ["truncated", "truncated"]
    assert llm.max_tokens_calls == [agent.SUMMARY_MAX_TOKENS, 1536]
    for row in conn.execute("SELECT attributes_json FROM spans WHERE name LIKE 'chat%'"):
        assert json.loads(row["attributes_json"])["tg_agent.summary.truncated"] is True
    health = metrics.summary_health(conn)
    assert health.truncated == 2
    # N8: a summary truncated twice is one terminal failure -- the attempt=2
    # row, not the lone attempt=1 truncation TQ-01 still gets to retry.
    assert health.failed == 1


def test_t_v160_tq_01_single_truncation_retries_and_then_succeeds(conn):
    conv = _seed_summary_history(conn)
    llm = FakeLLM([LLMResponse("cut off", [], "length"), LLMResponse(SUMMARY_PAYLOAD, [], "stop")])
    result = agent.summarize_conversation(conn, conv, llm, None, retry_max_tokens=1536)
    assert result is not None
    assert json.loads(result)["goal"] == "ship it"
    rows = llm_rows(conn)
    assert [r["attempt"] for r in rows] == [1, 2]
    assert [r["error_kind"] for r in rows] == ["truncated", None]
    assert llm.max_tokens_calls == [agent.SUMMARY_MAX_TOKENS, 1536]
    health = metrics.summary_health(conn)
    assert health.truncated == 1
    assert health.failed == 0  # a lone attempt=1 truncation is not a terminal failure


def test_t_v160_tq_01_malformed_reply_still_repairs_once_at_attempt_1(conn):
    """A non-truncated malformed reply keeps REQ-V13-OBS-04's existing
    behaviour -- both rows at attempt=1 -- untouched by REQ-V160-TQ-01."""
    conv = _seed_summary_history(conn)
    llm = FakeLLM([LLMResponse("not json", [], "stop"), LLMResponse(SUMMARY_PAYLOAD, [], "stop")])
    result = agent.summarize_conversation(conn, conv, llm, None)
    assert result is not None
    rows = llm_rows(conn)
    assert [r["attempt"] for r in rows] == [1, 1]
    assert [r["error_kind"] for r in rows] == [None, None]


def test_t_v160_tq_01_n8_non_truncation_failure_also_counts(conn):
    """N8's second half: a row whose only failure is a non-truncation
    error_kind is a terminal failure too, exactly like MET-06's formula."""
    conv = _seed_summary_history(conn)
    llm = FakeLLM([LLMError("boom", retryable=False, kind="timeout")])
    result = agent.summarize_conversation(conn, conv, llm, None, retry_max_tokens=1536)
    assert result is None
    rows = llm_rows(conn)
    assert len(rows) == 1
    assert rows[0]["error_kind"] == "timeout"
    health = metrics.summary_health(conn)
    assert health.failed == 1


def test_t_v160_tq_02_retry_budget_never_requested_without_truncation(conn, tmp_path):
    conv = _seed_summary_history(conn)
    cfg = make_cfg(tmp_path, llm_summary_max_tokens=1536)
    llm = FakeLLM([LLMResponse(SUMMARY_PAYLOAD, [], "stop")])
    result = agent.summarize_conversation(
        conn, conv, llm, cfg, retry_max_tokens=cfg.llm_summary_max_tokens
    )
    assert result is not None
    assert llm.max_tokens_calls == [agent.SUMMARY_MAX_TOKENS]


def test_t_v160_tq_02_llm_summary_max_tokens_parsed_and_defaulted():
    cfg = config.load_config(env=base_env(), load_env_file=False)
    assert cfg.llm_summary_max_tokens == 1536
    cfg = config.load_config(env=base_env(LLM_SUMMARY_MAX_TOKENS="900"), load_env_file=False)
    assert cfg.llm_summary_max_tokens == 900
    # Unchanged at default configuration: max(2048, 1536) == 2048, same floor as before T8.
    assert cfg.llm_timeout_s == 240.0


def test_t_v160_tq_02_config_error_names_both_variables():
    with pytest.raises(config.ConfigError) as exc:
        config.load_config(
            env=base_env(LLM_TIMEOUT_S="240", LLM_MAX_TOKENS="2048", LLM_SUMMARY_MAX_TOKENS="8192"),
            load_env_file=False,
        )
    message = str(exc.value)
    assert "LLM_TIMEOUT_S" in message
    assert "LLM_MAX_TOKENS" in message
    assert "LLM_SUMMARY_MAX_TOKENS" in message


def test_t_v160_tq_03_closed_outcome_vocabulary(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    call = tool_call()
    for outcome in agent.TOOL_OUTCOMES:
        with tracing.start_span(
            "execute_tool", tracing.KIND_INTERNAL, sink=tracing.SqliteSpanSink(conn)
        ) as span:
            agent._record_tool_call(conn, conv, 1, call, "{}", outcome, 5, None, span=span)
    rows = tool_rows(conn)
    assert [r["outcome"] for r in rows] == list(agent.TOOL_OUTCOMES)
    health = metrics.tool_health(conn)
    assert len(health) == 1
    row = health[0]
    assert (row.ok, row.error, row.budget, row.rejected, row.refused_repeat) == (1, 1, 1, 1, 1)

    with tracing.start_span(
        "execute_tool", tracing.KIND_INTERNAL, sink=tracing.NullSink()
    ) as span:
        with pytest.raises(ValueError):
            agent._record_tool_call(conn, conv, 1, call, "{}", "bogus", 0, None, span=span)
    assert len(tool_rows(conn)) == len(agent.TOOL_OUTCOMES)  # the bogus row never landed


# ============================================================================
# T9 -- repeat-call refusal (REQ-V160-TQ-04)
# ============================================================================


def test_t_v160_tq_04_call_key_ignores_argument_key_order(conn):
    a = tool_call(arguments='{"argv": ["true"], "timeout_s": null}')
    b = tool_call(index=2, arguments='{"timeout_s": null, "argv": ["true"]}')
    assert agent._call_key(a) == agent._call_key(b)
    # A different tool, or different arguments, is a different key.
    different_tool = tool_call(index=3, name="fetch", arguments=a.arguments)
    different_args = tool_call(index=4, arguments='{"argv": ["false"]}')
    assert agent._call_key(different_tool) != agent._call_key(a)
    assert agent._call_key(different_args) != agent._call_key(a)


def test_t_v160_tq_04_third_identical_failure_is_refused_not_executed(conn, monkeypatch):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    call = tool_call(arguments='{"argv": ["true"]}')
    responses = iter([
        json.dumps({"error": "docker: no such host"}),
        json.dumps({"error": "docker: TIMEOUT exceeded!!"}),
        json.dumps({"exit_code": 0, "stdout": "ok"}),
    ])
    calls_made = []

    def fake_execute_tool(name, arguments, **kwargs):
        calls_made.append((name, arguments))
        return next(responses)

    monkeypatch.setattr(agent, "execute_tool", fake_execute_tool)
    repeat_failures: dict[tuple[str, str], int] = {}
    for _ in range(2):
        agent._execute_tool_calls(
            [call], skills={}, runner=RecordingRunner(), tools_used=0,
            conn=conn, conv_id=conv, turn_id=1, repeat_failures=repeat_failures,
        )
    assert len(calls_made) == 2
    # Two distinct error classes, same call_key -- summed, not the max of either.
    assert len(repeat_failures) == 2
    assert sum(repeat_failures.values()) == 2

    results, tools_used = agent._execute_tool_calls(
        [call], skills={}, runner=RecordingRunner(), tools_used=0,
        conn=conn, conv_id=conv, turn_id=1, repeat_failures=repeat_failures,
    )
    assert len(calls_made) == 2                      # the third call is never dispatched
    assert results == [(call.id, agent.REFUSED_REPEAT_RESULT)]
    assert tools_used == 1                            # counts toward TOOL_EXECUTION_LIMIT

    row = tool_rows(conn)[-1]
    assert row["outcome"] == "refused_repeat"
    assert row["duration_ms"] == 0

    span_row = conn.execute(
        "SELECT attributes_json FROM spans "
        "WHERE name = 'execute_tool exec' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    attrs = json.loads(span_row["attributes_json"])
    assert attrs["tg_agent.tool.fingerprint"] == agent._call_key(call)[:16]

    # A fresh user message (a fresh dict) starts the count again.
    agent._execute_tool_calls(
        [call], skills={}, runner=RecordingRunner(), tools_used=0,
        conn=conn, conv_id=conv, turn_id=1, repeat_failures={},
    )
    assert len(calls_made) == 3


def test_t_v160_tq_04_end_to_end_through_run_agent(conn):
    malformed = tool_call(arguments="not valid json")
    script = [
        LLMResponse("", [malformed], "tool_calls"),
        LLMResponse("", [malformed], "tool_calls"),
        LLMResponse("", [malformed], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ]
    reply, llm, conv = run(conn, script)
    assert reply == "done"
    rows = tool_rows(conn)
    assert [r["outcome"] for r in rows] == ["error", "error", "refused_repeat"]
    assert rows[-1]["duration_ms"] == 0
