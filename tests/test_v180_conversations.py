"""spec-v1.8.0 T5 (docs/spec/spec-v1.8.0.md §6, REQ-V180-CONV-02): the four
`storage.py` read functions behind the conversations/transcript dashboard
pages -- `conversation_row`, `recent_conversations`, `conversation_messages`
(the by-turn cursor-paging algorithm) and `conversation_turn_traces`.

Test scope note (task-brief v180-T5): `T-V180-CONV-01`/`-02`/`-03` below are
this task's own required tests, storage-layer only. `conversation_list_section`
and `conversation_transcript_section` in `dashboard_render.py` are also built
here but get their authoritative coverage later, at T6 (`T-V180-CONV-04`/
`-05`, exercised over HTTP once that task wires the routes) -- the two smoke
test classes near the bottom of this file are this task's own basic check
that the builders do not crash and produce the documented shape, nothing
more.

Offline, deterministic, no Docker, no network.
"""

from __future__ import annotations

import pytest

import dashboard_render
import storage

NOW = "2026-09-09T00:00:00Z"


def _insert_message(conn, conv_id, turn_id, *, role="user", content="", tool_call_id=None):
    """A raw `messages` insert with an explicit `turn_id`, bypassing
    `add_user_message`/`add_tool_turn`'s own turn-id allocation so tests can
    lay out arbitrary turn shapes (message counts per turn) directly."""
    cur = conn.execute(
        "INSERT INTO messages (conv_id, turn_id, role, content, tool_calls_json, "
        "tool_call_id, created_at) VALUES (?, ?, ?, ?, NULL, ?, ?)",
        (conv_id, turn_id, role, content, tool_call_id, NOW),
    )
    return cur.lastrowid


def _seed_llm_call(conn, conv_id, turn_id, *, trace_id):
    return storage.add_llm_call(
        conn,
        conv_id=conv_id,
        turn_id=turn_id,
        purpose="agent",
        round_no=1,
        attempt=1,
        ts=NOW,
        provider="lmstudio",
        model="m",
        prompt_chars=10,
        prompt_chars_by_role={"system": 10, "tools": 0, "user": 0, "assistant": 0, "tool": 0},
        messages_n=2,
        tools_exposed=0,
        latency_ms=100,
        trace_id=trace_id,
    )


def _seed_tool_call(conn, conv_id, turn_id, *, trace_id):
    return storage.add_tool_call(
        conn,
        conv_id=conv_id,
        turn_id=turn_id,
        tool_call_id="call_0",
        tool="exec",
        ts=NOW,
        input_chars=1,
        raw_output_chars=1,
        output_chars=1,
        output_tokens_est=1,
        duration_ms=1,
        outcome="ok",
        trace_id=trace_id,
    )


# ============================================================================
# T-V180-CONV-01 -- recent_conversations
# ============================================================================


def test_t_v180_conv_01_six_fields_newest_first_bounded(conn):
    empty_conv = storage.get_or_create_active_conversation(conn, 101)
    busy_conv = storage.get_or_create_active_conversation(conn, 102)
    _insert_message(conn, busy_conv, 1, role="user", content="hi")
    _insert_message(conn, busy_conv, 1, role="assistant", content="hello")
    third_conv = storage.get_or_create_active_conversation(conn, 103)
    _insert_message(conn, third_conv, 1, role="user", content="one")

    rows = storage.recent_conversations(conn, limit=50)
    assert len(rows) == 3
    for row in rows:
        assert set(row.keys()) == {
            "id", "tg_user_id", "created_at", "active", "message_count", "last_activity",
        }

    # newest first -- created_at ties broken by id, so ids must be strictly
    # descending given these were inserted in ascending id order.
    ids = [row["id"] for row in rows]
    assert ids == sorted(ids, reverse=True)
    assert ids[0] == third_conv

    by_id = {row["id"]: row for row in rows}
    assert by_id[empty_conv]["message_count"] == 0
    assert by_id[empty_conv]["last_activity"] is None
    assert by_id[busy_conv]["message_count"] == 2
    assert by_id[busy_conv]["last_activity"] == NOW
    assert by_id[busy_conv]["active"] == 1


def test_t_v180_conv_01_bounded_by_limit(conn):
    for uid in range(200, 210):
        storage.get_or_create_active_conversation(conn, uid)
    rows = storage.recent_conversations(conn, limit=3)
    assert len(rows) == 3
    # the three newest (highest ids) of the ten created.
    all_ids = sorted(r["id"] for r in conn.execute("SELECT id FROM conversations").fetchall())
    assert [r["id"] for r in rows] == sorted(all_ids[-3:], reverse=True)


# ============================================================================
# T-V180-CONV-02 -- conversation_messages
# ============================================================================


def _seed_turns(conn, conv_id, counts):
    """Writes `len(counts)` turns, turn i holding `counts[i]` messages,
    turn ids 1..len(counts), message ids increasing with insertion order.
    Returns the flat list of inserted message ids, grouped by turn."""
    turns = []
    for turn_id, n in enumerate(counts, start=1):
        ids = [_insert_message(conn, conv_id, turn_id, content=f"t{turn_id}m{i}") for i in range(n)]
        turns.append(ids)
    return turns


def test_t_v180_conv_02_missing_conversation_yields_empty_none(conn):
    rows, next_cursor = storage.conversation_messages(conn, 9999, limit=10, cursor=None)
    assert rows == []
    assert next_cursor is None


def test_t_v180_conv_02_bad_cursor_raises_value_error(conn):
    conv = storage.get_or_create_active_conversation(conn, 1)
    _seed_turns(conn, conv, [1])
    with pytest.raises(ValueError):
        storage.conversation_messages(conn, conv, limit=10, cursor=(999, 999))


def test_t_v180_conv_02_ordering_pagination_no_split_no_repeat_no_skip(conn):
    conv = storage.get_or_create_active_conversation(conn, 2)
    # turn 1: 1 msg, turn 2: 2 msgs, turn 3: 1 msg, turn 4: 3 msgs, turn 5: 1 msg
    turns = _seed_turns(conn, conv, [1, 2, 1, 3, 1])
    all_ids = [i for group in turns for i in group]
    assert len(all_ids) == 8

    collected: list[int] = []
    cursor = None
    pages = 0
    while True:
        rows, next_cursor = storage.conversation_messages(conn, conv, limit=2, cursor=cursor)
        pages += 1
        assert pages <= 10, "pagination did not terminate"
        # ordering: turn_id, id ascending within the page.
        keys = [(r["turn_id"], r["id"]) for r in rows]
        assert keys == sorted(keys)
        collected.extend(r["id"] for r in rows)
        if next_cursor is None:
            break
        cursor = next_cursor

    # no repeat, no skip: every message exactly once, across the whole walk.
    assert collected == all_ids

    # first page (limit=2) must cross into turn 2 (1 + 2 = 3 > 2) and take it
    # whole -- turn 2 is never split.
    first_rows, first_next = storage.conversation_messages(conn, conv, limit=2, cursor=None)
    assert [r["id"] for r in first_rows] == turns[0] + turns[1]
    assert first_next == (3, turns[2][0])  # the probe: turn 3's first message


def test_t_v180_conv_02_probe_turn_never_in_rows(conn):
    conv = storage.get_or_create_active_conversation(conn, 3)
    turns = _seed_turns(conn, conv, [1, 2, 1])
    rows, next_cursor = storage.conversation_messages(conn, conv, limit=2, cursor=None)
    returned_ids = {r["id"] for r in rows}
    assert returned_ids == set(turns[0] + turns[1])
    assert not returned_ids & set(turns[2])
    assert next_cursor == (3, turns[2][0])


def test_t_v180_conv_02_cursor_inside_a_turn_resumes_at_its_message(conn):
    conv = storage.get_or_create_active_conversation(conn, 4)
    turns = _seed_turns(conn, conv, [1, 2, 1, 3, 1])
    turn4 = turns[3]  # 3 messages
    mid_cursor = (4, turn4[1])  # the second message of turn 4

    rows, next_cursor = storage.conversation_messages(conn, conv, limit=10, cursor=mid_cursor)
    returned_ids = [r["id"] for r in rows]
    # resumes at turn4's second message, never repeats its first.
    assert turn4[0] not in returned_ids
    assert returned_ids == [turn4[1], turn4[2]] + turns[4]
    assert next_cursor is None  # end of conversation


def test_t_v180_conv_02_fetch_rows_cap_yields_cursor_not_error(conn, monkeypatch):
    monkeypatch.setattr(storage, "TRANSCRIPT_FETCH_ROWS_MAX", 3)
    conv = storage.get_or_create_active_conversation(conn, 5)
    turns = _seed_turns(conn, conv, [5])  # one oversized turn
    rows, next_cursor = storage.conversation_messages(conn, conv, limit=500, cursor=None)
    assert [r["id"] for r in rows] == turns[0][:3]
    assert next_cursor == (1, turns[0][3])


def test_t_v180_conv_02_fetch_rows_max_constant_is_2000():
    assert storage.TRANSCRIPT_FETCH_ROWS_MAX == 2000


# ============================================================================
# T-V180-CONV-03 -- conversation_turn_traces
# ============================================================================


def test_t_v180_conv_03_prefers_llm_calls_lowest_id(conn):
    conv = storage.get_or_create_active_conversation(conn, 6)
    _seed_llm_call(conn, conv, 1, trace_id="T1-FIRST")
    _seed_llm_call(conn, conv, 1, trace_id="T1-SECOND")
    mapping = storage.conversation_turn_traces(conn, conv, [1])
    assert mapping == {1: "T1-FIRST"}


def test_t_v180_conv_03_falls_back_to_tool_calls(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    _seed_llm_call(conn, conv, 2, trace_id=None)  # null trace_id -- ignored
    _seed_tool_call(conn, conv, 2, trace_id="T2-TOOL")
    mapping = storage.conversation_turn_traces(conn, conv, [2])
    assert mapping == {2: "T2-TOOL"}


def test_t_v180_conv_03_llm_calls_preferred_over_tool_calls_regardless_of_id(conn):
    conv = storage.get_or_create_active_conversation(conn, 8)
    # tool_calls row inserted first (lower global id) but llm_calls still wins.
    _seed_tool_call(conn, conv, 4, trace_id="T4-TOOL")
    _seed_llm_call(conn, conv, 4, trace_id="T4-LLM")
    mapping = storage.conversation_turn_traces(conn, conv, [4])
    assert mapping == {4: "T4-LLM"}


def test_t_v180_conv_03_omits_turn_with_neither(conn):
    conv = storage.get_or_create_active_conversation(conn, 9)
    mapping = storage.conversation_turn_traces(conn, conv, [3])
    assert mapping == {}
    assert 3 not in mapping


def test_t_v180_conv_03_bounded_to_given_turn_ids(conn):
    conv = storage.get_or_create_active_conversation(conn, 10)
    _seed_llm_call(conn, conv, 1, trace_id="T1")
    _seed_llm_call(conn, conv, 5, trace_id="T5")  # not requested
    mapping = storage.conversation_turn_traces(conn, conv, [1])
    assert mapping == {1: "T1"}
    assert 5 not in mapping


def test_t_v180_conv_03_empty_turn_ids_returns_empty(conn):
    conv = storage.get_or_create_active_conversation(conn, 11)
    assert storage.conversation_turn_traces(conn, conv, []) == {}


# ============================================================================
# conversation_row -- the existence reader (used by CONV-01/-02/-03's setup,
# also exercised on its own here since T6 depends on its None/row contract)
# ============================================================================


def test_conversation_row_none_vs_existing(conn):
    assert storage.conversation_row(conn, 9999) is None
    conv = storage.get_or_create_active_conversation(conn, 12)
    row = storage.conversation_row(conn, conv)
    assert row is not None
    assert row["id"] == conv
    assert row["tg_user_id"] == 12
    assert row["active"] == 1


# ============================================================================
# dashboard_render.py smoke tests -- basic shape only; T-V180-CONV-04/-05
# (T6) own the authoritative coverage of these two builders.
# ============================================================================


class TestConversationListSectionSmoke:
    def test_empty_state(self):
        html = dashboard_render.conversation_list_section([])
        assert "No conversation recorded." in html
        assert '<td colspan="6">' in html

    def test_row_shape_and_num_classes(self):
        rows = [
            {
                "id": 7,
                "tg_user_id": 42,
                "created_at": "2026-01-01T00:00:00Z",
                "active": 1,
                "message_count": 3,
                "last_activity": "2026-01-01T00:01:00Z",
            },
            {
                "id": 8,
                "tg_user_id": 43,
                "created_at": "2026-01-02T00:00:00Z",
                "active": 0,
                "message_count": 0,
                "last_activity": None,
            },
        ]
        html = dashboard_render.conversation_list_section(rows)
        assert html.count("<th") >= 6
        assert '<a href="/conversations/7">7</a>' in html
        assert '<span class="ok">yes</span>' in html
        assert ">no<" in html
        assert "—" in html  # NULL last_activity placeholder
        # five num columns (id, user, started, messages, last activity) --
        # count class="num" occurrences in the header row alone.
        head = html.split("<tbody>")[0]
        assert head.count('class="num"') == 5


class TestConversationTranscriptSectionSmoke:
    def _messages(self, spec):
        """`spec` is a list of (turn_id, id, role, content, tool_call_id)."""
        return [
            {
                "turn_id": t,
                "id": i,
                "role": role,
                "content": content,
                "tool_call_id": tool_call_id,
                "created_at": NOW,
            }
            for t, i, role, content, tool_call_id in spec
        ]

    def test_empty_messages(self):
        html, next_cursor, split = dashboard_render.conversation_transcript_section(
            [], chrome_bytes=0
        )
        assert "No messages in this conversation." in html
        assert next_cursor is None
        assert split is False

    def test_everything_fits_passes_through_reader_cursor(self):
        messages = self._messages(
            [
                (1, 1, "user", "hi", None),
                (2, 2, "assistant", "hello", None),
                (2, 3, "tool", "ok", "call_0"),
            ]
        )
        html, next_cursor, split = dashboard_render.conversation_transcript_section(
            messages, chrome_bytes=0, reader_next_cursor=(9, 99)
        )
        assert "hi" in html and "hello" in html and "ok" in html
        assert "call_0" in html
        assert "user" in html and "assistant" in html and "tool" in html
        assert next_cursor == (9, 99)
        assert split is False

    def test_trace_link_present_and_absent(self):
        messages = self._messages(
            [
                (1, 1, "assistant", "with trace", None),
                (2, 2, "assistant", "without trace", None),
            ]
        )
        html, _, _ = dashboard_render.conversation_transcript_section(
            messages, chrome_bytes=0, trace_map={1: "abcdef0123456789"}
        )
        assert '<a href="/traces/abcdef0123456789"' in html
        assert "abcdef0123" in html  # abbreviated

    def test_budget_stops_page_between_turns_case_3(self):
        messages = self._messages(
            [(1, 1, "user", "first turn", None), (2, 2, "user", "second turn", None)]
        )
        # An exact budget: wrapper + the first turn's own rendered bytes,
        # with nothing left over for the second turn.
        turn1_html = dashboard_render._message_html(messages[0], trace_link_html="")
        wrapper_bytes = len(
            (
                dashboard_render._TRANSCRIPT_SECTION_OPEN
                + dashboard_render._TRANSCRIPT_SECTION_CLOSE
            ).encode("utf-8")
        )
        exact_budget = wrapper_bytes + len(turn1_html.encode("utf-8"))
        html, next_cursor, split = dashboard_render.conversation_transcript_section(
            messages, chrome_bytes=0, budget_bytes=exact_budget, suffix_bytes=0
        )
        assert "first turn" in html
        assert "second turn" not in html
        assert split is False
        assert next_cursor == (2, 2)

    def test_oversized_single_turn_splits_case_4(self):
        messages = self._messages(
            [
                (1, 1, "user", "x" * 500, None),
                (1, 2, "user", "y" * 500, None),
            ]
        )
        html, next_cursor, split = dashboard_render.conversation_transcript_section(
            messages, chrome_bytes=0, budget_bytes=400, suffix_bytes=0
        )
        assert split is True
        assert "x" * 500 in html  # at least the first message admitted
        assert next_cursor == (1, 2)
