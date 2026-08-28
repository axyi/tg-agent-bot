"""SQLite persistence: conversations, messages and the polling cursor.

All SQL lives here. Transactions are explicit because the connection is opened
in autocommit mode.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

WINDOW_TURNS = 40

_SCHEMA = """
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
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    version = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    if version != 1:
        raise RuntimeError(f"unsupported database schema version: {version}")


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
    return _add_single_row(conn, conv_id, "user", content)


def add_assistant_message(conn: sqlite3.Connection, conv_id: int, content: str) -> int:
    return _add_single_row(conn, conv_id, "assistant", content)


def add_tool_turn(
    conn: sqlite3.Connection,
    conv_id: int,
    content: str,
    tool_calls: list[dict],
    results: list[tuple[str, str]],
) -> int:
    turn_id = _next_turn_id(conn, conv_id)
    payload = json.dumps(tool_calls, ensure_ascii=False)
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            _INSERT_MESSAGE,
            (conv_id, turn_id, "assistant", content, payload, None, utc_now_iso()),
        )
        for tool_call_id, result in results:
            conn.execute(
                _INSERT_MESSAGE,
                (conv_id, turn_id, "tool", result, None, tool_call_id, utc_now_iso()),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return turn_id


def load_context_messages(conn: sqlite3.Connection, conv_id: int, limit: int = 30) -> list[dict]:
    groups: list[list[sqlite3.Row]] = []
    for row in _fetch_turn_rows(conn, conv_id):
        if groups and groups[-1][0]["turn_id"] == row["turn_id"]:
            groups[-1].append(row)
        else:
            groups.append([row])

    selected: list[sqlite3.Row] = []
    total = 0
    for group in reversed(groups):
        if total >= limit:
            break
        selected[0:0] = group
        total += len(group)
    return [_to_message(row) for row in selected]


def get_state(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM bot_state WHERE key = ?", (key,)).fetchone()
    return None if row is None else row["value"]


def set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO bot_state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


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
