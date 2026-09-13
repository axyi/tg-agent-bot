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
            "id",
            "tg_user_id",
            "created_at",
            "active",
            "message_count",
            "last_activity",
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


# ============================================================================
# T6 (task-brief v180-T6): the four HTTP routes -- /conversations,
# /conversations/<id>, /api/conversations, /api/conversations/<id>
# (REQ-V180-CONV-03/-04/-05/-06/-07), redaction/truncation (REQ-V180-SEC-01,
# -02 item 1), the byte budget on both sinks (REQ-V180-SEC-02 item 3), and
# security (REQ-V180-SEC-03/-04/-05). This section owns its own `live_server`
# fixture rather than importing test_v160_dashboard.py's: same pattern
# (REQ-V160-TST-01), a fresh empty schema per test.
# ============================================================================

import http.client  # noqa: E402
import json  # noqa: E402
import socket  # noqa: E402
import threading  # noqa: E402
import urllib.parse  # noqa: E402

import config  # noqa: E402
import dashboard_server  # noqa: E402

CANARY = "SYNTHETIC-CANARY-CONV-NEVER-A-LIVE-VALUE"


@pytest.fixture(autouse=True)
def isolated_secret_registry():
    """`config._secrets` is process-global (see tests/test_v11_patch.py) --
    this section registers a canary secret in several tests."""
    before = set(config._secrets)
    config._secrets.clear()
    yield
    config._secrets.clear()
    config._secrets.update(before)


def _loopback_getaddrinfo(host, port, *args, **kwargs):
    if host != "127.0.0.1":
        raise AssertionError(f"unexpected DNS lookup: {host}")
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", int(port)))]


def _write_pyproject_stub(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.8.0"\n', encoding="utf-8")


@pytest.fixture
def live_server(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _loopback_getaddrinfo)
    _write_pyproject_stub(tmp_path)
    db_path = tmp_path / "srv.db"
    conn = storage.connect(db_path)
    storage.init_schema(conn)
    conn.close()

    server = dashboard_server.build_server(db_path=db_path, port=0)
    port = server.server_address[1]
    # v1.9.2 T2 section 3.1: serve_forever's default poll_interval (0.5s)
    # makes every shutdown() wait up to half a second -- fixture-only, no
    # property under test changes.
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield port, db_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request(port, method, path, *, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        headers = {"Host": host if host is not None else f"127.0.0.1:{port}"}
        conn.request(method, path, headers=headers)
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, dict(resp.getheaders()), body
    finally:
        conn.close()


# ----------------------------------------------------------------------------
# T-V180-CONV-04 (per task-brief v180-T6's own id assignment): the LIST
# page/API -- row shape over HTTP, `limit` validation.
# ----------------------------------------------------------------------------


def test_t_v180_conv_04_list_page_and_api_render(live_server):
    port, db_path = live_server
    conn = storage.connect(db_path)
    conv = storage.get_or_create_active_conversation(conn, 555)
    _insert_message(conn, conv, 1, role="user", content="hi")
    conn.close()

    status, _, body = _request(port, "GET", "/conversations")
    assert status == 200
    text = body.decode("utf-8")
    assert f"/conversations/{conv}" in text
    assert "A conversation is one `/new`-to-`/new` stretch of chat" in text

    status, _, body = _request(port, "GET", "/api/conversations")
    assert status == 200
    payload = json.loads(body)
    assert payload["limit"] == 50
    assert payload["conversations"][0]["id"] == conv
    assert set(payload["conversations"][0].keys()) == {
        "id",
        "tg_user_id",
        "created_at",
        "active",
        "message_count",
        "last_activity",
    }


def test_t_v180_conv_04_bad_limit_400_both_routes(live_server):
    port, _ = live_server
    for bad in ("0", "501", "x"):
        status, _, _ = _request(port, "GET", f"/conversations?limit={bad}")
        assert status == 400, bad
        status, _, _ = _request(port, "GET", f"/api/conversations?limit={bad}")
        assert status == 400, bad


# ----------------------------------------------------------------------------
# T-V180-CONV-05: the transcript page/API -- order, trace links, pagination,
# cursor validation, 404s, empty-but-existing 200, the byte-budget split.
# ----------------------------------------------------------------------------


def test_t_v180_conv_05_order_and_only_traced_turns_linked(live_server):
    port, db_path = live_server
    conn = storage.connect(db_path)
    conv = storage.get_or_create_active_conversation(conn, 777)
    _seed_turns(conn, conv, [1, 2, 1])  # turn1: 1 msg, turn2: 2 msgs, turn3: 1 msg
    trace_id = "a" * 32
    _seed_llm_call(conn, conv, 1, trace_id=trace_id)
    conn.close()

    status, _, body = _request(port, "GET", f"/conversations/{conv}")
    assert status == 200
    text = body.decode("utf-8")
    assert text.index("t1m0") < text.index("t2m0") < text.index("t3m0")
    assert f"/traces/{trace_id}" in text
    assert text.count("/traces/") == 1  # only turn 1 is traced


def test_t_v180_conv_05_pagination_next_link_first_page_no_prev(live_server):
    port, db_path = live_server
    conn = storage.connect(db_path)
    conv = storage.get_or_create_active_conversation(conn, 778)
    _seed_turns(conn, conv, [1, 2, 1])
    conn.close()

    status, _, body = _request(port, "GET", f"/conversations/{conv}?limit=1")
    assert status == 200
    text = body.decode("utf-8")
    assert "t1m0" in text
    assert "t2m0" not in text  # limit=1 never splits turn 1 into turn 2
    assert "cursor=2-" in text  # next link carries the first unrendered message
    assert "first page" in text
    assert "prev" not in text.lower()

    status, _, body = _request(port, "GET", f"/api/conversations/{conv}?limit=1")
    assert status == 200
    payload = json.loads(body)
    assert payload["next_cursor"] is not None
    assert payload["next_cursor"].startswith("2-")
    assert "has_more" not in payload


def test_t_v180_conv_05_cursor_400_and_404_cases(live_server):
    port, db_path = live_server
    conn = storage.connect(db_path)
    conv = storage.get_or_create_active_conversation(conn, 779)
    _seed_turns(conn, conv, [1])
    conn.close()

    for path in (
        f"/conversations/{conv}?cursor=nope",
        f"/api/conversations/{conv}?cursor=nope",
        f"/conversations/{conv}?cursor=1-999999",
        f"/api/conversations/{conv}?cursor=1-999999",
    ):
        status, _, _ = _request(port, "GET", path)
        assert status == 400, path

    for path in ("/conversations/999999", "/api/conversations/999999"):
        status, _, _ = _request(port, "GET", path)
        assert status == 404, path

    # the regex only bounds digit *count* (1-10 digits) -- `0` and a
    # 10-digit value above 2**31 - 1 both need the route's own numeric
    # range check to answer 404 too.
    for bad_id in ("0", "9999999999"):
        status, _, _ = _request(port, "GET", f"/conversations/{bad_id}")
        assert status == 404, bad_id
        status, _, _ = _request(port, "GET", f"/api/conversations/{bad_id}")
        assert status == 404, bad_id


def test_t_v180_conv_05_existing_empty_conversation_is_200(live_server):
    port, db_path = live_server
    conn = storage.connect(db_path)
    empty_conv = storage.get_or_create_active_conversation(conn, 780)
    conn.close()

    status, _, body = _request(port, "GET", f"/conversations/{empty_conv}")
    assert status == 200
    assert b"No messages in this conversation." in body

    status, _, body = _request(port, "GET", f"/api/conversations/{empty_conv}")
    assert status == 200
    payload = json.loads(body)
    assert payload["messages"] == []
    assert payload["next_cursor"] is None


def test_t_v180_conv_05_byte_budget_splits_only_when_page_empty(live_server):
    port, db_path = live_server
    conn = storage.connect(db_path)
    conv = storage.get_or_create_active_conversation(conn, 781)
    # one oversized turn -- the only case CONV-04 ever splits.
    for _ in range(800):
        _insert_message(conn, conv, 1, role="user", content="x" * 2000)
    conn.close()

    status, _, body = _request(port, "GET", f"/conversations/{conv}?limit=500")
    assert status == 200
    assert len(body) < dashboard_render.TRANSCRIPT_PAGE_BUDGET_BYTES
    text = body.decode("utf-8")
    assert "continued" in text  # the split marker
    assert "cursor=1-" in text  # still inside turn 1

    status, _, body = _request(port, "GET", f"/api/conversations/{conv}?limit=500")
    assert status == 200
    assert len(body) < dashboard_render.TRANSCRIPT_PAGE_BUDGET_BYTES
    payload = json.loads(body)
    assert payload["next_cursor"] is not None
    assert payload["messages"][-1].get("continued") is True
    # no message before the last one is ever marked continued.
    assert all("continued" not in m for m in payload["messages"][:-1])


# ----------------------------------------------------------------------------
# T-V180-SEC-01: redact() on content, role and tool_call_id alike, on both
# sinks; HTML escapes, JSON carries the literal redacted text.
# ----------------------------------------------------------------------------


def test_t_v180_sec_01_redact_message_covers_content_role_and_tool_call_id():
    config.register_secret(CANARY)
    row = {
        "turn_id": 1,
        "id": 1,
        # `role` can never actually hold a secret through the real schema's
        # CHECK constraint (storage.py:163) -- SEC-01 still names it as one
        # of the three fields `_redact_message` must never skip, so this
        # exercises the helper directly rather than only through a route.
        "role": CANARY,
        "content": f"hello {CANARY} world",
        "tool_call_id": CANARY,
        "created_at": NOW,
    }
    redacted = dashboard_server._redact_message(row)
    assert CANARY not in redacted["role"]
    assert CANARY not in redacted["content"]
    assert CANARY not in redacted["tool_call_id"]
    assert config.REDACTION in redacted["role"]
    assert config.REDACTION in redacted["content"]
    assert config.REDACTION in redacted["tool_call_id"]


def test_t_v180_sec_01_redact_message_keeps_absent_tool_call_id_none():
    row = {
        "turn_id": 1,
        "id": 1,
        "role": "user",
        "content": "hi",
        "tool_call_id": None,
        "created_at": NOW,
    }
    assert dashboard_server._redact_message(row)["tool_call_id"] is None


def test_t_v180_sec_01_secret_redacted_over_http_both_sinks(live_server):
    port, db_path = live_server
    config.register_secret(CANARY)
    conn = storage.connect(db_path)
    conv = storage.get_or_create_active_conversation(conn, 902)
    # a raw insert (not `storage.add_tool_turn`, which already redacts at
    # write time -- REQ-V11-RED-01): this must be *dashboard_server.py's*
    # own redaction, exercised at serve time, that strips the canary.
    _insert_message(
        conn,
        conv,
        1,
        role="tool",
        content=f"<script>steal({CANARY})</script> secret={CANARY}",
        tool_call_id=f"call-{CANARY}",
    )
    conn.close()

    status, _, body = _request(port, "GET", f"/conversations/{conv}")
    assert status == 200
    html_text = body.decode("utf-8")
    assert CANARY not in html_text
    assert "<script>steal" not in html_text  # redact() before esc()

    status, _, body = _request(port, "GET", f"/api/conversations/{conv}")
    assert status == 200
    payload = json.loads(body)
    msg = payload["messages"][0]
    assert msg["role"] == "tool"
    assert CANARY not in msg["content"]
    assert CANARY not in msg["tool_call_id"]
    assert config.REDACTION in msg["content"]
    assert "<script>" in msg["content"]  # JSON sink: redact() only, no esc()


# ----------------------------------------------------------------------------
# T-V180-SEC-02: the per-message 2000-character cap, and the worst-case
# fixture (4-byte + escape-expanding chars) staying under the byte budget on
# both sinks, on the normal 200 path.
# ----------------------------------------------------------------------------


def test_t_v180_sec_02_redact_message_caps_content_at_2000_chars():
    long_content = "y" * 5000
    row = {
        "turn_id": 1,
        "id": 1,
        "role": "user",
        "content": long_content,
        "tool_call_id": None,
        "created_at": NOW,
    }
    redacted = dashboard_server._redact_message(row)
    # 2000 characters of the (here: unredacted) content, plus a truncation
    # note that is additional to the 2000-char cap, not inside it.
    assert redacted["content"][:2000] == "y" * 2000
    assert len(redacted["content"]) > 2000
    assert "5000" in redacted["content"]  # original length is noted


def test_t_v180_sec_02_worst_case_fixture_stays_under_budget_both_routes(live_server):
    port, db_path = live_server
    conn = storage.connect(db_path)
    conv = storage.get_or_create_active_conversation(conn, 903)
    unit = '𝕏"&<>'  # one astral (4-byte UTF-8) char + four escape-expanding
    content = (unit * 1600)[:8000]  # truncated to 2000 chars at serve time
    for turn_id in range(1, 501):
        _insert_message(conn, conv, turn_id, role="user", content=content)
    conn.close()

    status, _, body = _request(port, "GET", f"/conversations/{conv}?limit=500")
    assert status == 200
    assert len(body) < dashboard_render.TRANSCRIPT_PAGE_BUDGET_BYTES

    status, _, body = _request(port, "GET", f"/api/conversations/{conv}?limit=500")
    assert status == 200
    assert len(body) < dashboard_render.TRANSCRIPT_PAGE_BUDGET_BYTES
    payload = json.loads(body)
    assert payload["messages"]  # not the "response too large" empty path


# ----------------------------------------------------------------------------
# T-V180-SEC-03: the transcript is a wholly separate source from trace
# content capture -- both halves in one test.
# ----------------------------------------------------------------------------


def test_t_v180_sec_03_transcript_path_is_separate_from_trace_content_capture(live_server):
    port, db_path = live_server
    # half 1 (REQ-V160-TRC-09, NG-10): the four trace-content attribute keys
    # stay outside what `served_span()` ever serves, untouched by this task.
    assert dashboard_render.SERVED_SPAN_ATTRIBUTE_KEYS.isdisjoint(
        {
            "gen_ai.system_instructions",
            "gen_ai.input.messages",
            "gen_ai.output.messages",
            "gen_ai.tool.definitions",
        }
    )

    conn = storage.connect(db_path)
    conv = storage.get_or_create_active_conversation(conn, 904)
    _insert_message(conn, conv, 1, role="user", content="plain transcript content")
    conn.close()

    # half 2: the transcript route serves `messages.content` -- a different
    # source, unaffected by OBS_CAPTURE_CONTENT (never read by this module).
    status, _, body = _request(port, "GET", f"/conversations/{conv}")
    assert status == 200
    assert b"plain transcript content" in body


# ----------------------------------------------------------------------------
# T-V180-SEC-04: an injection-shaped id/cursor is rejected, never executed.
# ----------------------------------------------------------------------------


def test_t_v180_sec_04_injection_shaped_ids_are_rejected_not_executed(live_server):
    port, db_path = live_server
    conn = storage.connect(db_path)
    conv = storage.get_or_create_active_conversation(conn, 905)
    _insert_message(conn, conv, 1, role="user", content="hi")
    conn.close()

    payload = "1' OR '1'='1"
    encoded = urllib.parse.quote(payload, safe="")
    cases = [
        f"/conversations/{encoded}",
        f"/api/conversations/{encoded}",
        f"/conversations/{conv}?cursor={encoded}",
        f"/api/conversations/{conv}?cursor={encoded}",
    ]
    for path in cases:
        status, _, body = _request(port, "GET", path)
        assert status in (400, 404), path
        assert payload not in body.decode("utf-8", "replace")

    conn = storage.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    finally:
        conn.close()
