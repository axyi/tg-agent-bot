"""SQLite persistence: conversations, messages and the polling cursor.

All SQL lives here. Transactions are explicit because the connection is opened
in autocommit mode.
"""

import json
import logging
import os
import sqlite3
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

import config

WINDOW_TURNS = 40
SCHEMA_VERSION = 5
RECENT_GOAL_CHARS = 200
# REQ-V180-CONV-02: the SQL bound on `conversation_messages`'s message fetch --
# four times the maximum page `limit` of 500, so no lawful page ever reaches
# it. Hitting it is not an error; the extra row is dropped and its turn
# becomes the render-time split case (CONV-04, not this module's concern).
TRANSCRIPT_FETCH_ROWS_MAX = 2000

log = logging.getLogger("storage")

# The column order of the two observability tables, written once: the INSERT,
# the structured log line and the tests all read it, so a row and its log line
# can never drift apart (REQ-V13-OBS-06).
LLM_CALL_COLUMNS = (
    "id", "conv_id", "turn_id", "purpose", "round", "attempt", "ts", "provider", "model",
    "prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens", "reasoning_tokens",
    "reasoning_chars", "prompt_chars", "prompt_chars_by_role", "messages_n", "tools_exposed",
    "latency_ms", "finish_reason", "tool_calls_n", "error_kind", "cost_usd", "cost_basis",
    "trace_id", "span_id",
    # v1.7.0 additions (REQ-V170-OBS-01), appended after span_id.
    "reasoning_requested", "reasoning_honored",
)
TOOL_CALL_COLUMNS = (
    "id", "conv_id", "turn_id", "tool_call_id", "tool", "ts", "input_chars",
    "raw_output_chars", "output_chars", "output_tokens_est", "duration_ms", "outcome",
    "trace_id", "span_id",
)
# REQ-V160-TRC-05: mirrors the `spans` table's own column list exactly, in the
# same order as the DDL, so `T-V160-TRC-06` can assert it against
# `PRAGMA table_info(spans)` directly.
SPAN_COLUMNS = (
    "id", "trace_id", "span_id", "parent_span_id", "conv_id", "turn_id", "name", "kind",
    "ts", "start_ns", "duration_ms", "status", "status_message", "attributes_json",
)

_SUMMARIES_DDL = """
CREATE TABLE IF NOT EXISTS summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id      INTEGER NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
    tg_user_id   INTEGER NOT NULL,
    created_at   TEXT    NOT NULL,
    summary_json TEXT    NOT NULL CHECK (json_valid(summary_json))
);
"""

# REQ-V13-OBS-03: the observability tables. They hold sizes, timings and token
# counts only — never message content, arguments, output or Telegram ids.
_OBSERVABILITY_DDL = """
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
    cost_basis           TEXT,
    trace_id             TEXT,
    span_id              TEXT
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
    outcome           TEXT    NOT NULL,
    trace_id          TEXT,
    span_id           TEXT
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_conv ON tool_calls (conv_id, id);
"""

# REQ-V160-TRC-05: the span table. Appended to `_SCHEMA` so a fresh database is
# born at schema 4, and reused verbatim by `_MIGRATION_3_TO_4`.
_SPANS_DDL = """
CREATE TABLE IF NOT EXISTS spans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id        TEXT NOT NULL,
    span_id         TEXT NOT NULL UNIQUE,
    parent_span_id  TEXT,
    conv_id         INTEGER REFERENCES conversations(id),
    turn_id         INTEGER,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('INTERNAL', 'CLIENT')),
    ts              TEXT NOT NULL,
    start_ns        INTEGER NOT NULL,
    duration_ms     INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    status_message  TEXT,
    attributes_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans (trace_id, id);
CREATE INDEX IF NOT EXISTS idx_spans_conv  ON spans (conv_id, id);
"""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 4);

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

""" + _SUMMARIES_DDL + _OBSERVABILITY_DDL + _SPANS_DDL

# All three migrations are additive: a database keeps every row it had
# (REQ-V1-MEM-01, REQ-V13-OBS-03). They chain, so a version-1 database reaches
# 4 in one `init_schema` call.
_MIGRATION_1_TO_2 = """
BEGIN IMMEDIATE;
""" + _SUMMARIES_DDL + """
UPDATE schema_version SET version = 2 WHERE id = 1;
COMMIT;
"""

# Retained but no longer reached by `init_schema`'s chain: `_OBSERVABILITY_DDL`
# is now the v4 shape (it already carries `trace_id`/`span_id`), so a database
# chaining through version 2 must not stop and commit `version = 3` over
# already-v4-shaped tables -- that would be a version row lying about the
# table shape it just wrote. `_MIGRATION_2_TO_4` below is the real chain step;
# this constant stays only because deleting it is an unlisted edit the
# amendment table doesn't call for.
_MIGRATION_2_TO_3 = """
BEGIN IMMEDIATE;
""" + _OBSERVABILITY_DDL + """
UPDATE schema_version SET version = 3 WHERE id = 1;
COMMIT;
"""

# The real 2 -> 4 chain step: builds the (already v4-shaped) observability
# tables and the spans table in one transaction, straight to version 4, with
# no intermediate version = 3 commit.
_MIGRATION_2_TO_4 = """
BEGIN IMMEDIATE;
""" + _OBSERVABILITY_DDL + _SPANS_DDL + """
UPDATE schema_version SET version = 4 WHERE id = 1;
COMMIT;
"""

# REQ-V160-TRC-05: the `ALTER TABLE ... ADD COLUMN` statements exist only
# here, never in `_OBSERVABILITY_DDL`'s fresh-database path, which already has
# the columns from the start. This runs only against a genuine on-disk
# version-3 database (built by pre-v1.6.0 code), which is exactly the shape
# these ALTERs were written for.
_MIGRATION_3_TO_4 = """
BEGIN IMMEDIATE;
""" + _SPANS_DDL + """
ALTER TABLE llm_calls ADD COLUMN trace_id TEXT;
ALTER TABLE llm_calls ADD COLUMN span_id TEXT;
ALTER TABLE tool_calls ADD COLUMN trace_id TEXT;
ALTER TABLE tool_calls ADD COLUMN span_id TEXT;
UPDATE schema_version SET version = 4 WHERE id = 1;
COMMIT;
"""

# REQ-V170-OBS-01: added and chained after `_MIGRATION_2_TO_4` /
# `_MIGRATION_3_TO_4`, not folded into them or into `_OBSERVABILITY_DDL`.
# `_OBSERVABILITY_DDL` deliberately stays v4-shaped (unlike the v3->v4 step,
# which could embed the new columns straight into the fresh-table DDL because
# a v2 database never had `llm_calls` at all): `_MIGRATION_2_TO_4` still
# builds `llm_calls` via `CREATE TABLE IF NOT EXISTS` from that same DDL, so
# embedding the two new columns there would make this migration's own
# `ALTER TABLE ADD COLUMN` fail with "duplicate column name" on that path.
# `init_schema` instead runs this step, unconditionally, whenever the tree has
# just reached (or already sits at) version 4 -- covering the fresh-database
# path too, which is why `_SCHEMA` below still inserts version 4, not 5.
_MIGRATION_4_TO_5 = """
BEGIN IMMEDIATE;
ALTER TABLE llm_calls ADD COLUMN reasoning_requested TEXT;
ALTER TABLE llm_calls ADD COLUMN reasoning_honored INTEGER;
UPDATE schema_version SET version = 5 WHERE id = 1;
COMMIT;
"""

_INSERT_MESSAGE = (
    "INSERT INTO messages "
    "(conv_id, turn_id, role, content, tool_calls_json, tool_call_id, created_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
)

# The bound is on turn_id, never on a row count, so a turn group can never be
# cut in half and a window can never start with a 'tool' row.
_FETCH_TURNS = (
    "SELECT id, turn_id, role, content, tool_calls_json, tool_call_id "
    "FROM messages "
    "WHERE conv_id = :conv "
    "  AND turn_id > (SELECT COALESCE(MAX(turn_id), 0) - :turns "
    "                 FROM messages WHERE conv_id = :conv) "
    "ORDER BY id ASC"
)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), isolation_level=None, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _restrict_permissions(db_path)
    return conn


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    """REQ-V160-TRC-12 / -SRV-06: the dashboard's read-only handle. It changes
    no file, so it skips `_restrict_permissions`; a read-only connection also
    cannot set `journal_mode`. A missing database file raises
    `sqlite3.OperationalError` from the `mode=ro` URI itself rather than being
    silently created."""
    conn = sqlite3.connect(
        f"file:{db_path}?mode=ro", uri=True, isolation_level=None, timeout=5.0
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _restrict_permissions(db_path: Path) -> None:
    """REQ-V1-SEC-04: the conversation store is readable by its owner only."""
    os.chmod(db_path, 0o600)
    for suffix in ("-wal", "-shm"):
        try:
            os.chmod(str(db_path) + suffix, 0o600)
        except FileNotFoundError:
            pass
    # `config.PROJECT_ROOT` is read at call time so that a monkeypatched root is
    # honoured; the project root itself is never chmod-ed.
    parent = Path(os.path.normpath(db_path.parent))
    if parent != Path(os.path.normpath(config.PROJECT_ROOT)):
        os.chmod(parent, 0o700)


def init_schema(conn: sqlite3.Connection) -> None:
    # The version is read before any DDL runs, so a database from a future version
    # is refused untouched and the 1 -> 2 migration is the transaction the spec
    # describes rather than a no-op after the fact.
    existing = _existing_version(conn)
    if existing is not None and existing not in (1, 2, 3, 4, SCHEMA_VERSION):
        raise RuntimeError(f"unsupported database schema version: {existing}")
    if existing == 1:
        conn.executescript(_MIGRATION_1_TO_2)
        existing = 2
    if existing == 2:
        conn.executescript(_MIGRATION_2_TO_4)
    elif existing == 3:
        conn.executescript(_MIGRATION_3_TO_4)
    conn.executescript(_SCHEMA)
    # REQ-V170-OBS-01: the fresh-database path above still lands at version 4
    # (`_SCHEMA`'s own INSERT), exactly like every migrated path that just
    # reached 4 -- so this one further step, applied whenever the tree sits at
    # 4, covers all of them uniformly and never double-adds a column.
    if schema_version(conn) == 4:
        conn.executescript(_MIGRATION_4_TO_5)
    version = schema_version(conn)
    if version != SCHEMA_VERSION:
        raise RuntimeError(f"unsupported database schema version: {version}")


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]


def _existing_version(conn: sqlite3.Connection) -> int | None:
    present = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_version'"
    ).fetchone()
    return None if present is None else schema_version(conn)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_or_create_active_conversation(conn: sqlite3.Connection, tg_user_id: int) -> int:
    row = conn.execute(
        "SELECT id FROM conversations WHERE tg_user_id = ? AND active = 1",
        (tg_user_id,),
    ).fetchone()
    if row is not None:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO conversations (tg_user_id, created_at, active) VALUES (?, ?, 1)",
        (tg_user_id, utc_now_iso()),
    )
    return cursor.lastrowid


def start_new_conversation(conn: sqlite3.Connection, tg_user_id: int) -> int:
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE conversations SET active = 0 WHERE tg_user_id = ? AND active = 1",
            (tg_user_id,),
        )
        cursor = conn.execute(
            "INSERT INTO conversations (tg_user_id, created_at, active) VALUES (?, ?, 1)",
            (tg_user_id, utc_now_iso()),
        )
        conv_id = cursor.lastrowid
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return conv_id


def add_user_message(conn: sqlite3.Connection, conv_id: int, content: str) -> int:
    return _add_single_row(conn, conv_id, "user", config.redact(content))


def add_assistant_message(conn: sqlite3.Connection, conv_id: int, content: str) -> int:
    return _add_single_row(conn, conv_id, "assistant", config.redact(content))


def _add_tool_turn_body(
    conn: sqlite3.Connection,
    conv_id: int,
    content: str,
    tool_calls: list[dict],
    results: list[tuple[str, str]],
) -> int:
    """The transaction **body** of `add_tool_turn`, without the
    `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` triple (REQ-V160-TRC-07): a future
    root-span sequence reuses this inside its own transaction, so no
    `BEGIN IMMEDIATE` is ever nested inside another."""
    # REQ-V11-RED-01: a last-line guard so no write path can bypass redaction,
    # even one that reaches this function directly. `config.redact` is
    # idempotent, so double redaction (agent.py already redacts once) is
    # harmless and expected.
    turn_id = _next_turn_id(conn, conv_id)
    redacted_content = config.redact(content)
    payload = config.redact(json.dumps(tool_calls, ensure_ascii=False))
    redacted_results = [
        (tool_call_id, config.redact(result)) for tool_call_id, result in results
    ]
    conn.execute(
        _INSERT_MESSAGE,
        (conv_id, turn_id, "assistant", redacted_content, payload, None, utc_now_iso()),
    )
    for tool_call_id, result in redacted_results:
        conn.execute(
            _INSERT_MESSAGE,
            (conv_id, turn_id, "tool", result, None, tool_call_id, utc_now_iso()),
        )
    return turn_id


def add_tool_turn(
    conn: sqlite3.Connection,
    conv_id: int,
    content: str,
    tool_calls: list[dict],
    results: list[tuple[str, str]],
) -> int:
    conn.execute("BEGIN IMMEDIATE")
    try:
        turn_id = _add_tool_turn_body(conn, conv_id, content, tool_calls, results)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return turn_id


def load_context_messages(
    conn: sqlite3.Connection,
    conv_id: int,
    limit: int = 30,
    *,
    token_budget: int | None = None,
    estimator: Callable[[dict], int] | None = None,
    transform: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    """`transform` rewrites the whole fetched window *before* the budget walk
    (REQ-V13-HST-04: the budget is computed on the stubbed messages). It must
    return a list of the same length in the same order — message `i` still
    describes row `i` — so that turn grouping and eviction are unaffected by
    what it did to the contents."""
    rows = _fetch_turn_rows(conn, conv_id)
    messages = [_to_message(row) for row in rows]
    if transform is not None:
        messages = transform(messages)
        if len(messages) != len(rows):
            raise ValueError("a context transform must preserve the message count")

    groups: list[list[int]] = []
    for index, row in enumerate(rows):
        if groups and rows[groups[-1][0]]["turn_id"] == row["turn_id"]:
            groups[-1].append(index)
        else:
            groups.append([index])

    # With no budget the walk is byte-for-byte the v0 one (REQ-DB-09).
    budgeting = token_budget is not None and estimator is not None
    selected: list[int] = []
    total = 0
    tokens = 0
    for index, group in enumerate(reversed(groups)):
        if total >= limit:
            break
        if budgeting:
            cost = sum(estimator(messages[position]) for position in group)
            # The newest group is always taken whole; the budget may exclude older
            # groups but never splits one.
            if index > 0 and tokens + cost > token_budget:
                break
            tokens += cost
        selected[0:0] = group
        total += len(group)
    return [messages[position] for position in selected]


def add_summary(
    conn: sqlite3.Connection, conv_id: int, tg_user_id: int, summary_json: str
) -> None:
    conn.execute(
        "INSERT INTO summaries (conv_id, tg_user_id, created_at, summary_json) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(conv_id) DO UPDATE SET "
        "  tg_user_id = excluded.tg_user_id, "
        "  created_at = excluded.created_at, "
        "  summary_json = excluded.summary_json",
        (conv_id, tg_user_id, utc_now_iso(), config.redact(summary_json)),
    )


def get_summary(conn: sqlite3.Connection, conv_id: int) -> str | None:
    row = conn.execute(
        "SELECT summary_json FROM summaries WHERE conv_id = ?", (conv_id,)
    ).fetchone()
    return None if row is None else row["summary_json"]


def recent_goals(conn: sqlite3.Connection, tg_user_id: int, limit: int = 3) -> list[str]:
    """The `goal` of the newest `limit` summaries, newest first. Rows whose JSON
    carries no string goal are skipped rather than rendered."""
    rows = conn.execute(
        "SELECT summary_json FROM summaries WHERE tg_user_id = ? ORDER BY id DESC LIMIT ?",
        (tg_user_id, limit),
    ).fetchall()
    goals: list[str] = []
    for row in rows:
        try:
            parsed = json.loads(row["summary_json"])
        except ValueError:
            continue
        goal = parsed.get("goal") if isinstance(parsed, dict) else None
        if isinstance(goal, str) and goal.strip():
            goals.append(goal[:RECENT_GOAL_CHARS])
    return goals


def active_conversation_id(conn: sqlite3.Connection, tg_user_id: int) -> int | None:
    """The active conversation, or `None`. A read-only counterpart of
    `get_or_create_active_conversation`: `/status` and `/stats` must not open a
    conversation just by being asked for numbers."""
    row = conn.execute(
        "SELECT id FROM conversations WHERE tg_user_id = ? AND active = 1",
        (tg_user_id,),
    ).fetchone()
    return None if row is None else row["id"]


def add_llm_call(
    conn: sqlite3.Connection,
    *,
    conv_id: int,
    turn_id: int | None,
    purpose: str,
    round_no: int,
    attempt: int,
    ts: str,
    provider: str,
    model: str,
    prompt_chars: int,
    prompt_chars_by_role: dict[str, int],
    messages_n: int,
    tools_exposed: int,
    latency_ms: int,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    cached_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    reasoning_chars: int = 0,
    finish_reason: str | None = None,
    tool_calls_n: int = 0,
    error_kind: str | None = None,
    cost_usd: float | None = None,
    cost_basis: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    reasoning_requested: str | None = None,
    reasoning_honored: int | None = None,
) -> int:
    """One row per `llm.complete` invocation (REQ-V13-OBS-04). Sizes, counts and
    timings only — never a fragment of the prompt itself. `trace_id`/`span_id`
    default to `None` (REQ-V160-EC-05): the agent.py wiring that always
    supplies them is T3's, not this function's, concern. `reasoning_requested`/
    `reasoning_honored` default to `None` the same way (REQ-V170-EC-05): the
    `agent.py` wiring that computes and supplies them is T5's concern, not
    this function's."""
    row = {
        "conv_id": conv_id,
        "turn_id": turn_id,
        "purpose": purpose,
        "round": round_no,
        "attempt": attempt,
        "ts": ts,
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
        "reasoning_chars": reasoning_chars,
        "prompt_chars": prompt_chars,
        "prompt_chars_by_role": json.dumps(prompt_chars_by_role, sort_keys=True),
        "messages_n": messages_n,
        "tools_exposed": tools_exposed,
        "latency_ms": latency_ms,
        "finish_reason": finish_reason,
        "tool_calls_n": tool_calls_n,
        "error_kind": error_kind,
        "cost_usd": cost_usd,
        "cost_basis": cost_basis,
        "trace_id": trace_id,
        "span_id": span_id,
        "reasoning_requested": reasoning_requested,
        "reasoning_honored": reasoning_honored,
    }
    row_id = _insert_row(conn, "llm_calls", row)
    _log_row("llm_call", LLM_CALL_COLUMNS, row_id, row,
             {"prompt_chars_by_role": prompt_chars_by_role})
    return row_id


def add_tool_call(
    conn: sqlite3.Connection,
    *,
    conv_id: int,
    turn_id: int,
    tool_call_id: str,
    tool: str,
    ts: str,
    input_chars: int,
    raw_output_chars: int,
    output_chars: int,
    output_tokens_est: int,
    duration_ms: int,
    outcome: str,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> int:
    """One row per tool call the agent decided on — executed, rejected or
    refused for budget (REQ-V13-OBS-05). `trace_id`/`span_id` default to
    `None` (REQ-V160-EC-05): the agent.py wiring that always supplies them is
    T3's, not this function's, concern."""
    row = {
        "conv_id": conv_id,
        "turn_id": turn_id,
        "tool_call_id": tool_call_id,
        "tool": tool,
        "ts": ts,
        "input_chars": input_chars,
        "raw_output_chars": raw_output_chars,
        "output_chars": output_chars,
        "output_tokens_est": output_tokens_est,
        "duration_ms": duration_ms,
        "outcome": outcome,
        "trace_id": trace_id,
        "span_id": span_id,
    }
    row_id = _insert_row(conn, "tool_calls", row)
    _log_row("tool_call", TOOL_CALL_COLUMNS, row_id, row, {})
    return row_id


def add_span(
    conn: sqlite3.Connection,
    *,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    conv_id: int | None,
    turn_id: int | None,
    name: str,
    kind: str,
    ts: str,
    start_ns: int,
    duration_ms: int,
    status: str,
    status_message: str | None,
    attributes_json: str,
) -> int:
    """One row per finished span (REQ-V160-TRC-05, -07). A plain, parameterised
    INSERT with no transaction of its own — the caller (`SqliteSpanSink`, via
    the sequence of REQ-V160-TRC-07) wraps this and the call-row insert it
    belongs to in one `BEGIN IMMEDIATE` … `COMMIT`."""
    row = {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "conv_id": conv_id,
        "turn_id": turn_id,
        "name": name,
        "kind": kind,
        "ts": ts,
        "start_ns": start_ns,
        "duration_ms": duration_ms,
        "status": status,
        "status_message": status_message,
        "attributes_json": attributes_json,
    }
    row_id = _insert_row(conn, "spans", row)
    _log_row("span", SPAN_COLUMNS, row_id, row, {})
    return row_id


def spans_for_trace(conn: sqlite3.Connection, trace_id: str) -> list[sqlite3.Row]:
    """Every span of one trace, ordered by insertion (`id`)."""
    return conn.execute(
        "SELECT * FROM spans WHERE trace_id = ? ORDER BY id", (trace_id,)
    ).fetchall()


def recent_traces(
    conn: sqlite3.Connection, *, limit: int, conv_id: int | None = None
) -> list[sqlite3.Row]:
    """One row per `trace_id` — the root span's `ts`, `name` and `status`, the
    trace's `conv_id`, its span count and total duration — newest first,
    bounded by `limit`. "Root span" is the span of that trace whose
    `parent_span_id IS NULL`."""
    query = (
        "SELECT root.trace_id AS trace_id, root.ts AS ts, root.name AS name, "
        "       root.status AS status, root.conv_id AS conv_id, "
        "       COUNT(all_spans.id) AS span_count, "
        "       SUM(all_spans.duration_ms) AS total_duration_ms "
        "FROM spans AS root "
        "JOIN spans AS all_spans ON all_spans.trace_id = root.trace_id "
        "WHERE root.parent_span_id IS NULL "
    )
    params: list[object] = []
    if conv_id is not None:
        query += "  AND root.conv_id = ? "
        params.append(conv_id)
    query += (
        "GROUP BY root.id, root.trace_id, root.ts, root.name, root.status, root.conv_id "
        "ORDER BY root.ts DESC, root.id DESC "
        "LIMIT ?"
    )
    params.append(limit)
    return conn.execute(query, params).fetchall()


# ----------------------------------------------------------------------------
# REQ-V180-CONV-02: four read functions for the conversations/transcript
# dashboard pages. All mirror `recent_traces` above: parameterized SQL,
# bounds as parameters, `sqlite3.Row` results, no string formatting of
# request-shaped values into SQL text.
# ----------------------------------------------------------------------------


def conversation_row(conn: sqlite3.Connection, conv_id: int) -> sqlite3.Row | None:
    """The `conversations` row for `conv_id`, or `None`. The existence
    reader: it is what tells an empty conversation (row exists, zero
    messages) from an absent one, which `conversation_messages` cannot --
    that function returns an empty list either way (CONV-04, CONV-07)."""
    return conn.execute(
        "SELECT id, tg_user_id, created_at, active FROM conversations WHERE id = ?",
        (conv_id,),
    ).fetchone()


def recent_conversations(conn: sqlite3.Connection, *, limit: int) -> list[sqlite3.Row]:
    """`id`, `tg_user_id`, `created_at`, `active`, `message_count` (`COUNT`
    over `messages`) and `last_activity` (`MAX(messages.created_at)`, `NULL`
    for an empty conversation) -- newest first (`created_at DESC, id DESC`),
    bounded by `limit`. A `LEFT JOIN` so a conversation with zero messages
    still appears, with `message_count = 0` and `last_activity = NULL`."""
    query = (
        "SELECT c.id AS id, c.tg_user_id AS tg_user_id, c.created_at AS created_at, "
        "       c.active AS active, COUNT(m.id) AS message_count, "
        "       MAX(m.created_at) AS last_activity "
        "FROM conversations AS c "
        "LEFT JOIN messages AS m ON m.conv_id = c.id "
        "GROUP BY c.id, c.tg_user_id, c.created_at, c.active "
        "ORDER BY c.created_at DESC, c.id DESC "
        "LIMIT ?"
    )
    return conn.execute(query, (limit,)).fetchall()


def conversation_messages(
    conn: sqlite3.Connection,
    conv_id: int,
    *,
    limit: int,
    cursor: tuple[int, int] | None,
) -> tuple[list[sqlite3.Row], tuple[int, int] | None]:
    """Pages `messages` by turn, never by row (REQ-V180-CONV-02). `cursor` is
    the `(turn_id, id)` pair of the page's first message, or `None` for the
    first page.

    Steps, in order (spec-v1.8.0 §6, REQ-V180-CONV-02 item 3):

    0. cursor check -- an exact `(conv_id, turn_id, id)` match, never a range
       probe; no match raises `ValueError` (the caller, T6, turns this into a
       400);
    1. the turn window -- turns from `turn_id` (or the cursor's position)
       onward, `limit + 1` of them, each carrying its message count and its
       lowest `id`;
    2. the page -- turns taken in order while the running message count
       stays below `limit`; the turn that crosses `limit` is taken whole;
    3. the probe -- the first turn from the window not taken, never fetched
       or rendered, only its `(turn_id, first_id)` kept;
    4. the messages -- fetched for the taken turns only, bounded in SQL by
       `LIMIT TRANSCRIPT_FETCH_ROWS_MAX + 1`; a cap hit drops the extra row;
    5. `next_cursor` -- the `(turn_id, id)` of the first message this reader
       did not return: the dropped row from step 4 if the cap was hit, else
       the probe's pair from step 3, else `None`.

    A missing conversation (no rows for `conv_id` at all) yields an empty
    `rows` list and `next_cursor = None` -- the caller decides the 404 via
    `conversation_row`, not this function's empty result."""
    cursor_turn_id: int | None = None
    cursor_id: int | None = None
    if cursor is not None:
        cursor_turn_id, cursor_id = cursor
        match = conn.execute(
            "SELECT 1 FROM messages WHERE conv_id = ? AND turn_id = ? AND id = ? LIMIT 1",
            (conv_id, cursor_turn_id, cursor_id),
        ).fetchone()
        if match is None:
            raise ValueError(
                f"cursor (turn_id={cursor_turn_id}, id={cursor_id}) names no message "
                f"of conversation {conv_id}"
            )

    if cursor is None:
        window = conn.execute(
            "SELECT turn_id, COUNT(*) AS n, MIN(id) AS first_id FROM messages "
            "WHERE conv_id = ? "
            "GROUP BY turn_id ORDER BY turn_id ASC LIMIT ?",
            (conv_id, limit + 1),
        ).fetchall()
    else:
        window = conn.execute(
            "SELECT turn_id, COUNT(*) AS n, MIN(id) AS first_id FROM messages "
            "WHERE conv_id = ? AND (turn_id > ? OR (turn_id = ? AND id >= ?)) "
            "GROUP BY turn_id ORDER BY turn_id ASC LIMIT ?",
            (conv_id, cursor_turn_id, cursor_turn_id, cursor_id, limit + 1),
        ).fetchall()

    taken: list[sqlite3.Row] = []
    probe: sqlite3.Row | None = None
    running = 0
    for row in window:
        if running < limit:
            taken.append(row)
            running += row["n"]
        else:
            probe = row
            break

    if not taken:
        return [], None

    turn_ids = [row["turn_id"] for row in taken]
    placeholders = ", ".join("?" for _ in turn_ids)
    query = (
        "SELECT turn_id, role, content, tool_call_id, created_at, id FROM messages "
        f"WHERE conv_id = ? AND turn_id IN ({placeholders})"
    )
    params: list[object] = [conv_id, *turn_ids]
    if cursor is not None:
        query += " AND (turn_id > ? OR (turn_id = ? AND id >= ?))"
        params.extend([cursor_turn_id, cursor_turn_id, cursor_id])
    query += " ORDER BY turn_id ASC, id ASC LIMIT ?"
    params.append(TRANSCRIPT_FETCH_ROWS_MAX + 1)

    rows = conn.execute(query, params).fetchall()

    if len(rows) > TRANSCRIPT_FETCH_ROWS_MAX:
        dropped = rows[TRANSCRIPT_FETCH_ROWS_MAX]
        next_cursor: tuple[int, int] | None = (dropped["turn_id"], dropped["id"])
        rows = rows[:TRANSCRIPT_FETCH_ROWS_MAX]
    elif probe is not None:
        next_cursor = (probe["turn_id"], probe["first_id"])
    else:
        next_cursor = None

    return rows, next_cursor


def conversation_turn_traces(
    conn: sqlite3.Connection, conv_id: int, turn_ids: Sequence[int]
) -> dict[int, str]:
    """`turn_id -> trace_id` for exactly the given `turn_ids` (REQ-V180-CONV-05),
    bounded to the page's own turns, nothing wider. Per turn: the `trace_id`
    of the lowest `id` in `llm_calls` for that `(conv_id, turn_id)` whose
    `trace_id` is non-null; failing that, the lowest `id` in `tool_calls`
    under the same condition; failing that, the turn is absent from the
    mapping -- no key, not a `None` value."""
    turn_id_list = list(dict.fromkeys(turn_ids))
    if not turn_id_list:
        return {}
    placeholders = ", ".join("?" for _ in turn_id_list)

    def _lowest_trace_per_turn(table: str) -> dict[int, str]:
        # `table` is one of the two literal, hard-coded names below -- never
        # request-shaped -- so this f-string carries no untrusted value.
        query = (
            f"SELECT turn_id, trace_id FROM {table} "
            f"WHERE id IN ("
            f"    SELECT MIN(id) FROM {table} "
            f"    WHERE conv_id = ? AND trace_id IS NOT NULL AND turn_id IN ({placeholders}) "
            f"    GROUP BY turn_id"
            f")"
        )
        params: list[object] = [conv_id, *turn_id_list]
        return {row["turn_id"]: row["trace_id"] for row in conn.execute(query, params)}

    llm_map = _lowest_trace_per_turn("llm_calls")
    tool_map = _lowest_trace_per_turn("tool_calls")
    return {
        turn_id: llm_map[turn_id] if turn_id in llm_map else tool_map[turn_id]
        for turn_id in turn_id_list
        if turn_id in llm_map or turn_id in tool_map
    }


def fetch_llm_calls(
    conn: sqlite3.Connection, conv_id: int | None = None
) -> list[sqlite3.Row]:
    """Every recorded call, oldest first; one conversation when `conv_id` is given."""
    if conv_id is None:
        return conn.execute("SELECT * FROM llm_calls ORDER BY id").fetchall()
    return conn.execute(
        "SELECT * FROM llm_calls WHERE conv_id = ? ORDER BY id", (conv_id,)
    ).fetchall()


def fetch_tool_calls(
    conn: sqlite3.Connection, conv_id: int | None = None
) -> list[sqlite3.Row]:
    if conv_id is None:
        return conn.execute("SELECT * FROM tool_calls ORDER BY id").fetchall()
    return conn.execute(
        "SELECT * FROM tool_calls WHERE conv_id = ? ORDER BY id", (conv_id,)
    ).fetchall()


def _insert_row(conn: sqlite3.Connection, table: str, row: dict) -> int:
    columns = ", ".join(f'"{name}"' for name in row)
    placeholders = ", ".join("?" for _ in row)
    cursor = conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(row.values())
    )
    return cursor.lastrowid


def _log_row(
    prefix: str, columns: tuple[str, ...], row_id: int, row: dict, expanded: dict
) -> None:
    """REQ-V13-OBS-06: one INFO line per row, JSON, keyed by the table's own
    columns and nothing else — no content, no arguments, no URL. Building the
    line from the declared column tuple is what keeps the two in step: a column
    added to the row but not to the tuple (or the reverse) raises here."""
    values = {"id": row_id, **row, **expanded}
    payload = {name: values[name] for name in columns}
    if len(values) != len(payload):
        raise KeyError(f"{prefix}: the row carries columns {set(values) - set(payload)}")
    log.info("%s %s", prefix, config.redact(json.dumps(payload, ensure_ascii=False)))


def get_state(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM bot_state WHERE key = ?", (key,)).fetchone()
    return None if row is None else row["value"]


def set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO bot_state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def delete_state(conn: sqlite3.Connection, key: str) -> None:
    conn.execute("DELETE FROM bot_state WHERE key = ?", (key,))


def _fetch_turn_rows(
    conn: sqlite3.Connection, conv_id: int, turns: int = WINDOW_TURNS
) -> list[sqlite3.Row]:
    """Step 1 of REQ-DB-09: the most recent whole turns, oldest row first."""
    return conn.execute(_FETCH_TURNS, {"conv": conv_id, "turns": turns}).fetchall()


def _next_turn_id(conn: sqlite3.Connection, conv_id: int) -> int:
    return conn.execute(
        "SELECT COALESCE(MAX(turn_id), 0) + 1 FROM messages WHERE conv_id = ?",
        (conv_id,),
    ).fetchone()[0]


def next_turn_id(conn: sqlite3.Connection, conv_id: int) -> int:
    """Public alias of `_next_turn_id` (REQ-V12-ID-01): a pure read, safe to call
    before `add_tool_turn` allocates the same value, since no row is inserted
    between the two calls in a round."""
    return _next_turn_id(conn, conv_id)


def _add_single_row(conn: sqlite3.Connection, conv_id: int, role: str, content: str) -> int:
    turn_id = _next_turn_id(conn, conv_id)
    conn.execute(
        _INSERT_MESSAGE, (conv_id, turn_id, role, content, None, None, utc_now_iso())
    )
    return turn_id


def _to_message(row: sqlite3.Row) -> dict:
    if row["role"] == "tool":
        return {"role": "tool", "tool_call_id": row["tool_call_id"], "content": row["content"]}
    message = {"role": row["role"], "content": row["content"]}
    if row["role"] == "assistant" and row["tool_calls_json"] is not None:
        message["tool_calls"] = json.loads(row["tool_calls_json"])
    return message
