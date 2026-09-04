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

import config
import storage
import tracing

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
    for name in ("tracing",):
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
    assert storage.schema_version(conn) == 4
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
    assert storage.schema_version(conn) == 4
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
    assert storage.schema_version(conn) == 4
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
    assert storage.schema_version(conn) == 4
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


@pytest.mark.parametrize("bad_version", [0, 5, "x"])
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
