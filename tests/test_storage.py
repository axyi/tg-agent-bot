import json
import sqlite3

import pytest

import storage


def tool_group(conn, conv_id, n, prefix="c"):
    """Write one tool turn carrying `n` tool calls, i.e. `1 + n` rows."""
    calls = [
        {
            "id": f"{prefix}{i}",
            "type": "function",
            "function": {"name": "exec", "arguments": '{"argv": ["true"]}'},
        }
        for i in range(n)
    ]
    results = [(f"{prefix}{i}", '{"exit_code": 0}') for i in range(n)]
    return storage.add_tool_turn(conn, conv_id, "", calls, results)


def assert_groups_intact(window):
    """Every assistant-with-tools row is followed by all of its tool siblings."""
    i = 0
    while i < len(window):
        message = window[i]
        if message["role"] == "assistant" and "tool_calls" in message:
            declared = [c["id"] for c in message["tool_calls"]]
            siblings = window[i + 1 : i + 1 + len(declared)]
            assert [s["role"] for s in siblings] == ["tool"] * len(declared)
            assert [s["tool_call_id"] for s in siblings] == declared
            i += len(declared) + 1
        else:
            i += 1


def test_t_db_01_init_schema_idempotent(tmp_path):
    path = tmp_path / "a.db"
    c1 = storage.connect(path)
    storage.init_schema(c1)
    storage.init_schema(c1)
    version = c1.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    assert version == storage.SCHEMA_VERSION
    c1.close()
    c2 = storage.connect(path)
    storage.init_schema(c2)
    assert c2.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 1
    c2.close()


def test_t_db_02_one_active_conversation_per_user(conn):
    storage.get_or_create_active_conversation(conn, 7)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO conversations (tg_user_id, created_at, active) VALUES (?, ?, 1)",
            (7, storage.utc_now_iso()),
        )


def test_t_db_03_start_new_conversation(conn):
    old = storage.get_or_create_active_conversation(conn, 7)
    storage.add_user_message(conn, old, "kept")
    new = storage.start_new_conversation(conn, 7)
    assert new != old
    rows = conn.execute(
        "SELECT id, active FROM conversations WHERE tg_user_id = 7 ORDER BY id"
    ).fetchall()
    assert [(r["id"], r["active"]) for r in rows] == [(old, 0), (new, 1)]
    assert storage.get_or_create_active_conversation(conn, 7) == new
    kept = conn.execute("SELECT content FROM messages WHERE conv_id = ?", (old,)).fetchall()
    assert [r["content"] for r in kept] == ["kept"]


def test_t_db_04_add_tool_turn_atomic(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    turn = tool_group(conn, conv, 3)
    rows = conn.execute(
        "SELECT role, turn_id FROM messages WHERE conv_id = ? ORDER BY id", (conv,)
    ).fetchall()
    assert [r["role"] for r in rows] == ["assistant", "tool", "tool", "tool"]
    assert {r["turn_id"] for r in rows} == {turn}

    before = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    calls = [
        {"id": "x0", "type": "function", "function": {"name": "exec", "arguments": "{}"}},
        {"id": "x1", "type": "function", "function": {"name": "exec", "arguments": "{}"}},
    ]
    with pytest.raises(sqlite3.IntegrityError):
        storage.add_tool_turn(conn, conv, "", calls, [("x0", "ok"), (None, "boom")])
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == before


def test_t_db_05_window_returns_newest_thirty(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    for i in range(40):
        storage.add_user_message(conn, conv, f"m{i}")
    window = storage.load_context_messages(conn, conv, 30)
    assert len(window) == 30
    assert window[0]["content"] == "m10"
    assert window[-1]["content"] == "m39"


def test_t_db_06_oldest_group_is_complete_and_may_overshoot(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    for i in range(5):
        storage.add_user_message(conn, conv, f"old{i}")
    tool_group(conn, conv, 3)  # a 4-row group
    for i in range(28):
        storage.add_user_message(conn, conv, f"new{i}")
    window = storage.load_context_messages(conn, conv, 30)
    assert len(window) == 32
    assert window[0]["role"] == "assistant"
    assert len(window[0]["tool_calls"]) == 3
    assert_groups_intact(window)


def test_t_db_07_newest_group_larger_than_limit(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    storage.add_user_message(conn, conv, "hi")
    tool_group(conn, conv, 4)  # a 5-row group
    window = storage.load_context_messages(conn, conv, 3)
    assert len(window) == 5
    assert window[0]["role"] == "assistant"


def test_t_db_08_window_never_starts_with_tool(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    for size in (1, 8, 2, 5, 1, 8, 3):
        storage.add_user_message(conn, conv, "u")
        tool_group(conn, conv, size)
        storage.add_assistant_message(conn, conv, "a")
        for limit in (1, 3, 10, 30):
            assert storage.load_context_messages(conn, conv, limit)[0]["role"] != "tool"


def test_t_db_09_bot_state_round_trip(tmp_path):
    path = tmp_path / "s.db"
    c1 = storage.connect(path)
    storage.init_schema(c1)
    assert storage.get_state(c1, "last_update_id") is None
    storage.set_state(c1, "last_update_id", "42")
    storage.set_state(c1, "last_update_id", "43")
    c1.close()
    c2 = storage.connect(path)
    assert storage.get_state(c2, "last_update_id") == "43"
    c2.close()


def test_t_db_10_check_constraints(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    now = storage.utc_now_iso()
    bad_rows = [
        ("tool", "x", None, None),          # tool without tool_call_id
        ("user", "x", "[]", None),          # user carrying tool_calls_json
        ("x", "x", None, None),             # unknown role
        ("assistant", "x", "not json", None),  # tool_calls_json is not JSON
    ]
    for role, content, tool_calls_json, tool_call_id in bad_rows:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO messages "
                "(conv_id, turn_id, role, content, tool_calls_json, tool_call_id, created_at) "
                "VALUES (?, 1, ?, ?, ?, ?, ?)",
                (conv, role, content, tool_calls_json, tool_call_id, now),
            )


def test_t_db_11_tool_calls_wire_shape_round_trip(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "exec", "arguments": '{"argv": ["uname", "-a"]}'},
        }
    ]
    storage.add_tool_turn(conn, conv, "", calls, [("call_1", '{"exit_code": 0}')])
    stored = conn.execute(
        "SELECT tool_calls_json FROM messages WHERE role = 'assistant'"
    ).fetchone()[0]
    assert json.loads(stored) == calls
    window = storage.load_context_messages(conn, conv, 30)
    assert window[0] == {"role": "assistant", "content": "", "tool_calls": calls}
    assert window[1] == {"role": "tool", "tool_call_id": "call_1", "content": '{"exit_code": 0}'}


def test_t_db_12a_no_mid_group_cut(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    for turn in range(1, 301):
        if turn % 3 == 0:
            tool_group(conn, conv, 8)
        else:
            storage.add_user_message(conn, conv, f"m{turn}")
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1100
    fetched = storage._fetch_turn_rows(conn, conv)
    assert len(fetched) <= storage.WINDOW_TURNS * 9
    window = storage.load_context_messages(conn, conv, 30)
    assert window[0]["role"] != "tool"
    assert_groups_intact(window)


def test_t_db_12b_oversized_group_is_never_cut(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    for i in range(10):
        storage.add_user_message(conn, conv, f"u{i}")
    now = storage.utc_now_iso()
    calls = [
        {"id": f"big{i}", "type": "function",
         "function": {"name": "exec", "arguments": "{}"}}
        for i in range(200)
    ]
    conn.execute(
        "INSERT INTO messages "
        "(conv_id, turn_id, role, content, tool_calls_json, tool_call_id, created_at) "
        "VALUES (?, 11, 'assistant', '', ?, NULL, ?)",
        (conv, json.dumps(calls), now),
    )
    for i in range(200):
        conn.execute(
            "INSERT INTO messages "
            "(conv_id, turn_id, role, content, tool_calls_json, tool_call_id, created_at) "
            "VALUES (?, 11, 'tool', '{}', NULL, ?, ?)",
            (conv, f"big{i}", now),
        )
    window = storage.load_context_messages(conn, conv, 30)
    assert window[0]["role"] == "assistant"
    assert len(window) == 201


def test_t_db_13a_bounds_singleton_turns(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    for i in range(1, 101):
        storage.add_user_message(conn, conv, f"m{i}")
    fetched = storage._fetch_turn_rows(conn, conv)
    assert len(fetched) == 40
    assert {r["turn_id"] for r in fetched} == set(range(61, 101))
    window = storage.load_context_messages(conn, conv, 30)
    assert len(window) == 30
    assert window[0]["role"] == "user"


def test_t_db_13b_bounds_maximum_groups(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    for _ in range(200):
        tool_group(conn, conv, 8)
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1800
    fetched = storage._fetch_turn_rows(conn, conv)
    assert len(fetched) == 40 * 9
    window = storage.load_context_messages(conn, conv, 30)
    assert len(window) == 36
    assert window[0]["role"] == "assistant"
