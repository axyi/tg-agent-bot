"""spec-v1.11.0 T3: sessions -- list and switch, no schema change
(REQ-V1110-SES-01..-03).

Builds on T1's outbound table path (`tables.py`, `bot.send_pre`) and T2's
`/documents`/`/stats` table conventions. Reuses `tests/test_observability.py`'s
`make_cfg`/`update`/`process`/`USER_ID` -- the same pattern
`tests/test_v1110_sta.py` already uses for T2, and the `conn` fixture from
`tests/conftest.py`.
"""

from __future__ import annotations

import html

import agent
import storage
from llm.base import LLMResponse
from tests.fakes import FakeLLM, FakeTelegram
from tests.test_observability import USER_ID, make_cfg, process, update

# --------------------------------------------------------------------------
# T-V1110-SES-01 -- list_conversations / count_conversations, schema 6
# --------------------------------------------------------------------------


def test_t_v1110_ses_01_list_conversations_and_schema_6(conn):
    assert storage.SCHEMA_VERSION == 6
    assert len(conn.execute("PRAGMA table_info(conversations)").fetchall()) == 4

    other_user = USER_ID + 1

    conv1 = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv1, "  first   conversation ever  ")
    conv2 = storage.start_new_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv2, "x" * 50)
    conv3 = storage.start_new_conversation(conn, USER_ID)  # no user message

    foreign = storage.get_or_create_active_conversation(conn, other_user)
    storage.add_user_message(conn, foreign, "not yours")

    rows = storage.list_conversations(conn, USER_ID, limit=10)

    # last_activity DESC NULLS LAST, id DESC -- conv3 has no message (NULL
    # last_activity) so it sorts last even though it is the newest row.
    assert [row["id"] for row in rows] == [conv2, conv1, conv3]
    assert set(rows[0].keys()) == {
        "id",
        "created_at",
        "active",
        "message_count",
        "last_activity",
        "title",
    }

    by_id = {row["id"]: row for row in rows}
    assert by_id[conv1]["title"] == "first conversation ever"
    assert by_id[conv2]["title"] == "x" * 40 + "…"
    assert by_id[conv3]["title"] == "(empty)"
    assert by_id[conv1]["message_count"] == 1
    assert by_id[conv3]["message_count"] == 0
    assert by_id[conv3]["last_activity"] is None
    assert by_id[conv3]["active"] == 1  # the most recently started conversation
    assert by_id[conv1]["active"] == 0
    assert by_id[conv2]["active"] == 0

    # another user's rows are absent
    assert foreign not in {row["id"] for row in rows}

    # limit is honoured
    limited = storage.list_conversations(conn, USER_ID, limit=2)
    assert [row["id"] for row in limited] == [conv2, conv1]

    assert storage.count_conversations(conn, USER_ID) == 3
    assert storage.count_conversations(conn, other_user) == 1


# --------------------------------------------------------------------------
# T-V1110-SES-02 -- activate_conversation ownership (negative)
# --------------------------------------------------------------------------


def _active_id(conn, tg_user_id):
    return storage.active_conversation_id(conn, tg_user_id)


def _active_count(conn, tg_user_id):
    return conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE tg_user_id = ? AND active = 1",
        (tg_user_id,),
    ).fetchone()[0]


def test_t_v1110_ses_02_activate_conversation_ownership(conn):
    caller = 4242  # never 0, 1 or None -- v1110-activate-ownership-dropped bait
    other = 4243

    conv1 = storage.get_or_create_active_conversation(conn, caller)
    conv2 = storage.start_new_conversation(conn, caller)  # now the active one
    foreign = storage.get_or_create_active_conversation(conn, other)

    # own id -> True, exactly one active=1 row for the caller, the target
    assert storage.activate_conversation(conn, caller, conv1) is True
    assert _active_id(conn, caller) == conv1
    assert _active_count(conn, caller) == 1

    # foreign id -> False, caller's active row unchanged, owner's unchanged
    assert storage.activate_conversation(conn, caller, foreign) is False
    assert _active_id(conn, caller) == conv1
    assert _active_id(conn, other) == foreign
    assert _active_count(conn, caller) == 1
    assert _active_count(conn, other) == 1

    # missing id -> False, caller's active row unchanged
    assert storage.activate_conversation(conn, caller, 999999) is False
    assert _active_id(conn, caller) == conv1

    # the partial unique index still holds after 50 alternating switches
    for i in range(50):
        target = conv1 if i % 2 == 0 else conv2
        assert storage.activate_conversation(conn, caller, target) is True
        assert _active_id(conn, caller) == target
        assert _active_count(conn, caller) == 1


# --------------------------------------------------------------------------
# T-V1110-SES-03 -- /sessions table
# --------------------------------------------------------------------------


def _sessions_body(conn, cfg, update_id=1) -> str:
    tg = process(conn, cfg, update(text="/sessions", update_id=update_id), tg=FakeTelegram())
    assert len(tg.sent) == 1
    assert tg.sent_payloads[-1].get("parse_mode") == "HTML"
    raw = tg.sent[0][1]
    assert raw.startswith("<pre>") and raw.endswith("</pre>")
    return html.unescape(raw[len("<pre>") : -len("</pre>")])


def test_t_v1110_ses_03_sessions_table(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    conv_ids = []
    for i in range(12):
        conv_id = storage.start_new_conversation(conn, USER_ID)
        storage.add_user_message(conn, conv_id, f"conversation number {i}")
        conv_ids.append(conv_id)
    active_id = conv_ids[-1]

    body = _sessions_body(conn, cfg, update_id=1)
    lines = body.splitlines()
    header = lines[0]
    for col in ["●", "#", "title", "msgs", "last"]:
        assert col in header
    data_lines = lines[2:12]
    assert len(data_lines) == 10
    assert lines[12] == ""
    assert lines[13] == "2 older sessions not shown"
    assert data_lines[0].lstrip().startswith("●")
    assert all(not line.lstrip().startswith("●") for line in data_lines[1:])
    assert str(active_id) in data_lines[0]

    conn2 = storage.connect(tmp_path / "sessions-b.db")
    storage.init_schema(conn2)
    for i in range(3):
        conv_id = storage.start_new_conversation(conn2, USER_ID)
        storage.add_user_message(conn2, conv_id, f"c{i}")
    body2 = _sessions_body(conn2, cfg, update_id=2)
    lines2 = body2.splitlines()
    assert len(lines2) == 5  # header + rule + 3 rows, no trailing note
    assert "older sessions not shown" not in body2
    conn2.close()


# --------------------------------------------------------------------------
# T-V1110-SES-04 -- /session switch + context adoption (negative)
# --------------------------------------------------------------------------


def _messages_mention(messages, needle: str) -> bool:
    return any(needle in str(message.get("content", "")) for message in messages)


def test_t_v1110_ses_04_session_switch_and_context(conn, tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    other_user = USER_ID + 1

    conv1 = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv1, "MARKER_ONE distinctive content")
    conv2 = storage.start_new_conversation(conn, USER_ID)  # active now
    storage.add_user_message(conn, conv2, "MARKER_TWO distinctive content")

    foreign_conv = storage.get_or_create_active_conversation(conn, other_user)

    def _never_summarize(*_a, **_k):
        raise AssertionError("agent.summarize_conversation must not be called by /session")

    monkeypatch.setattr(agent, "summarize_conversation", _never_summarize)

    tg = process(conn, cfg, update(text=f"/session {conv1}", update_id=1))
    assert tg.sent == [(USER_ID, f"Switched to session #{conv1}: MARKER_ONE distinctive content")]
    assert storage.get_summary(conn, conv2) is None
    assert conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0] == 0
    assert storage.active_conversation_id(conn, USER_ID) == conv1

    # the next text turn's FakeLLM request carries conv1's messages, not conv2's
    llm = FakeLLM([LLMResponse("ok", [], "stop")])
    tg2 = process(conn, cfg, update(text="hello again", update_id=2), llm=llm)
    assert tg2.sent
    request_messages = llm.calls[-1][0]
    assert _messages_mention(request_messages, "MARKER_ONE")
    assert not _messages_mention(request_messages, "MARKER_TWO")

    # foreign id and a missing id -> identical wording, no ownership leak
    tg3 = process(conn, cfg, update(text=f"/session {foreign_conv}", update_id=3))
    assert tg3.sent == [(USER_ID, f"No session #{foreign_conv}.")]
    tg4 = process(conn, cfg, update(text="/session 999999", update_id=4))
    assert tg4.sent == [(USER_ID, "No session #999999.")]

    # usage errors: bare, non-integer, more than one argument
    for i, text in enumerate(("/session", "/session x", "/session 1 2"), start=5):
        result = process(conn, cfg, update(text=text, update_id=i))
        assert result.sent == [(USER_ID, "Usage: /session <id> (see /sessions)")]

    # an id past sqlite3's INTEGER ceiling -> no OverflowError, not found;
    # the same regression guard `_handle_delete` uses (`_DELETE_MAX_ID`),
    # reused here for the same reason -- not itself in the brief's test
    # table, added and verified as a mutation-kill-style proof (see prompt).
    huge_id = "9" * 25
    tg5 = process(conn, cfg, update(text=f"/session {huge_id}", update_id=8))
    assert tg5.sent == [(USER_ID, f"No session #{huge_id}.")]


# --------------------------------------------------------------------------
# T-V1110-SES-05 -- /new names its id
# --------------------------------------------------------------------------


def test_t_v1110_ses_05_new_reply_names_id(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    tg = process(conn, cfg, update(text="/new", update_id=1))
    first_id = storage.active_conversation_id(conn, USER_ID)
    assert tg.sent == [(USER_ID, f"New conversation started (#{first_id}).")]

    tg2 = process(conn, cfg, update(text="/new", update_id=2))
    second_id = storage.active_conversation_id(conn, USER_ID)
    assert second_id != first_id
    assert tg2.sent == [(USER_ID, f"New conversation started (#{second_id}).")]
