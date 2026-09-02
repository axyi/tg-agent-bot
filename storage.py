"""SQLite persistence: conversations, messages and the polling cursor.

All SQL lives here. Transactions are explicit because the connection is opened
in autocommit mode.
"""

import json
import logging
import os
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import config

WINDOW_TURNS = 40
SCHEMA_VERSION = 3
RECENT_GOAL_CHARS = 200

log = logging.getLogger("storage")

# The column order of the two observability tables, written once: the INSERT,
# the structured log line and the tests all read it, so a row and its log line
# can never drift apart (REQ-V13-OBS-06).
LLM_CALL_COLUMNS = (
    "id", "conv_id", "turn_id", "purpose", "round", "attempt", "ts", "provider", "model",
    "prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens", "reasoning_tokens",
    "reasoning_chars", "prompt_chars", "prompt_chars_by_role", "messages_n", "tools_exposed",
    "latency_ms", "finish_reason", "tool_calls_n", "error_kind", "cost_usd", "cost_basis",
)
TOOL_CALL_COLUMNS = (
    "id", "conv_id", "turn_id", "tool_call_id", "tool", "ts", "input_chars",
    "raw_output_chars", "output_chars", "output_tokens_est", "duration_ms", "outcome",
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

_SCHEMA = """
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

""" + _SUMMARIES_DDL + _OBSERVABILITY_DDL

# Both migrations are additive: a database keeps every row it had (REQ-V1-MEM-01,
# REQ-V13-OBS-03). They chain, so a version-1 database reaches 3 in one call.
_MIGRATION_1_TO_2 = """
BEGIN IMMEDIATE;
""" + _SUMMARIES_DDL + """
UPDATE schema_version SET version = 2 WHERE id = 1;
COMMIT;
"""

_MIGRATION_2_TO_3 = """
BEGIN IMMEDIATE;
""" + _OBSERVABILITY_DDL + """
UPDATE schema_version SET version = 3 WHERE id = 1;
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
    if existing is not None and existing not in (1, 2, SCHEMA_VERSION):
        raise RuntimeError(f"unsupported database schema version: {existing}")
    if existing == 1:
        conn.executescript(_MIGRATION_1_TO_2)
        existing = 2
    if existing == 2:
        conn.executescript(_MIGRATION_2_TO_3)
    conn.executescript(_SCHEMA)
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


def add_tool_turn(
    conn: sqlite3.Connection,
    conv_id: int,
    content: str,
    tool_calls: list[dict],
    results: list[tuple[str, str]],
) -> int:
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
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            _INSERT_MESSAGE,
            (conv_id, turn_id, "assistant", redacted_content, payload, None, utc_now_iso()),
        )
        for tool_call_id, result in redacted_results:
            conn.execute(
                _INSERT_MESSAGE,
                (conv_id, turn_id, "tool", result, None, tool_call_id, utc_now_iso()),
            )
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
) -> int:
    """One row per `llm.complete` invocation (REQ-V13-OBS-04). Sizes, counts and
    timings only — never a fragment of the prompt itself."""
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
) -> int:
    """One row per tool call the agent decided on — executed, rejected or
    refused for budget (REQ-V13-OBS-05)."""
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
    }
    row_id = _insert_row(conn, "tool_calls", row)
    _log_row("tool_call", TOOL_CALL_COLUMNS, row_id, row, {})
    return row_id


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
