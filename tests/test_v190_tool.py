"""spec-v1.9.0 T6 (docs/spec/spec-v1.9.0.md Sec.6, REQ-V190-TOOL-01..06;
Sec.9, REQ-V190-SEC-02 and SEC-04's currently-checkable half): the fourth
tool (`search_documents`), its dispatch/envelope, the agent-loop plumbing
(the history stub, the status line, `run_agent`'s frozen signature), the one
system-prompt rule line, and the `Searcher` Protocol boundary `tools.py`
declares without importing `rag.py`.

Offline throughout: `FakeLLM`/`FakeSearcher`/`RecordingRunner` only, no
socket. This file imports `rag` for its two real dataclasses
(`Passage`/`SearchResult`) to build fixtures; `tools.py` and `agent.py`
themselves never import `rag.py` (REQ-V190-TOOL-02).
"""

import ast
import inspect
import json
from pathlib import Path

import agent
import bot
import documents
import rag
import storage
import tools
from llm.base import LLMResponse, ToolCall
from tests.fakes import FakeLLM, FakeSearcher, RecordingRunner

NOW = "2026-09-11T00:00:00Z"
USER_ID = 424242
REPO_ROOT = Path(__file__).resolve().parents[1]


def passage(**overrides):
    fields = {
        "chunk_id": 1,
        "filename": "policy.pdf",
        "page": 3,
        "chunk_index": 0,
        "text": "passage text",
    }
    fields.update(overrides)
    return rag.Passage(**fields)


def result(
    passages=(),
    *,
    documents_present=True,
    rerank_attempted=False,
    rerank_succeeded=False,
    rerank_failure=None,
):
    return rag.SearchResult(
        passages=list(passages),
        documents_present=documents_present,
        rerank_attempted=rerank_attempted,
        rerank_succeeded=rerank_succeeded,
        rerank_failure=rerank_failure,
    )


def search_call(index=0, query="vacation days"):
    return ToolCall(f"call_{index}", "search_documents", json.dumps({"query": query}))


# --------------------------------------------------------------------------
# T-V190-TOOL-01 -- the fourth tool: shape and the char budgets
# --------------------------------------------------------------------------

SEARCH_SPEC = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Search the users uploaded documents; returns the best passages with "
            "filename and page. Use it before answering about their files."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


def test_t_v190_tool_01_the_fourth_entry_is_appended_last_and_exact():
    specs = tools.tool_specs()
    assert [s["function"]["name"] for s in specs] == [
        "exec",
        "load_skill",
        "fetch",
        "search_documents",
    ]
    assert specs[3] == SEARCH_SPEC


def test_t_v190_tool_01_the_entry_fits_350_chars():
    entry_chars = len(json.dumps(SEARCH_SPEC))
    assert entry_chars <= 350, entry_chars


def test_t_v190_tool_01_the_whole_catalog_fits_1800_chars():
    catalog_chars = len(json.dumps(tools.tool_specs()))
    assert catalog_chars <= 1800, catalog_chars


def test_t_v190_tool_01_description_is_ascii_and_quote_free():
    description = SEARCH_SPEC["function"]["description"]
    assert description.isascii()
    assert '"' not in description


def test_t_v190_tool_01_known_tool_names_picks_it_up_by_construction():
    assert "search_documents" in agent._known_tool_names()


# --------------------------------------------------------------------------
# T-V190-TOOL-02 -- dispatch, the result envelope, exact truncation
# --------------------------------------------------------------------------


def execute(query="find it", *, searcher=None):
    return json.loads(
        tools.execute_tool(
            "search_documents",
            json.dumps({"query": query}),
            skills={},
            runner=RecordingRunner(),
            searcher=searcher,
        )
    )


def test_t_v190_tool_02_no_searcher_is_not_available():
    searcher_missing = execute(searcher=None)
    assert searcher_missing == {"error": "search_documents is not available"}


def test_t_v190_tool_02_whitespace_only_query_refused():
    searcher = FakeSearcher(result=result([passage()]))
    payload = execute(query="   ", searcher=searcher)
    assert payload == {"error": "query must be a non-empty string of at most 1000 characters"}
    assert searcher.queries == []


def test_t_v190_tool_02_non_string_query_refused():
    payload = json.loads(
        tools.execute_tool(
            "search_documents",
            json.dumps({"query": 7}),
            skills={},
            runner=RecordingRunner(),
            searcher=FakeSearcher(),
        )
    )
    assert payload == {"error": "query must be a non-empty string of at most 1000 characters"}


def test_t_v190_tool_02_query_over_1000_chars_refused():
    searcher = FakeSearcher(result=result([passage()]))
    payload = execute(query="x" * 1001, searcher=searcher)
    assert payload == {"error": "query must be a non-empty string of at most 1000 characters"}
    assert searcher.queries == []


def test_t_v190_tool_02_query_exactly_1000_chars_is_accepted():
    searcher = FakeSearcher(result=result([]))
    payload = execute(query="x" * 1000, searcher=searcher)
    assert "error" not in payload
    assert searcher.queries == ["x" * 1000]


def test_t_v190_tool_02_no_documents_present():
    searcher = FakeSearcher(result=result([], documents_present=False))
    payload = execute(searcher=searcher)
    assert payload == {
        "text": "No documents uploaded for this user. Supported: .txt .md .docx .pdf",
        "passages": 0,
    }


def test_t_v190_tool_02_documents_present_but_no_passages():
    searcher = FakeSearcher(result=result([], documents_present=True))
    payload = execute(searcher=searcher)
    assert payload == {"text": "No passages matched.", "passages": 0}


def test_t_v190_tool_02_one_passage_with_a_page():
    p = passage(filename="a.pdf", page=3, chunk_index=1, text="hello world")
    searcher = FakeSearcher(result=result([p]))
    payload = execute(searcher=searcher)
    assert payload["passages"] == 1
    assert payload["text"] == "Found 1 passages:\n\n[1] a.pdf — page 3 | chunk 1: hello world"


def test_t_v190_tool_02_a_null_page_omits_the_page_segment():
    p = passage(filename="a.txt", page=None, chunk_index=0, text="hello")
    searcher = FakeSearcher(result=result([p]))
    payload = execute(searcher=searcher)
    assert payload["text"] == "Found 1 passages:\n\n[1] a.txt — chunk 0: hello"


def test_t_v190_tool_02_two_passages_are_blank_line_separated():
    p1 = passage(filename="a.txt", page=None, chunk_index=0, text="one")
    p2 = passage(filename="b.txt", page=2, chunk_index=1, text="two")
    searcher = FakeSearcher(result=result([p1, p2]))
    payload = execute(searcher=searcher)
    assert payload["text"] == (
        "Found 2 passages:\n\n[1] a.txt — chunk 0: one\n\n[2] b.txt — page 2 | chunk 1: two"
    )


def test_t_v190_tool_02_a_passage_body_over_1000_chars_is_cut_to_exactly_1000():
    p = passage(filename="policy.pdf", page=3, chunk_index=0, text="y" * 1500)
    searcher = FakeSearcher(result=result([p]))
    payload = execute(searcher=searcher)
    header = "Found 1 passages:\n\n[1] policy.pdf — page 3 | chunk 0: "
    assert payload["text"].startswith(header)  # the header is never truncated
    body = payload["text"][len(header) :]
    assert len(body) == 1000
    assert body == ("y" * 999) + "…"


def test_t_v190_tool_02_a_passage_body_of_exactly_1000_is_unchanged():
    text = "z" * 1000
    p = passage(text=text)
    searcher = FakeSearcher(result=result([p]))
    payload = execute(searcher=searcher)
    assert payload["text"].endswith(text)
    assert "…" not in payload["text"]


def test_t_v190_tool_02_ten_max_length_passages_all_survive_uncut():
    passages = [
        passage(filename="document-name.pdf", page=99, chunk_index=i, text="w" * 1200)
        for i in range(10)
    ]
    searcher = FakeSearcher(result=result(passages))
    payload = execute(searcher=searcher)
    assert payload["passages"] == 10
    for i in range(1, 11):
        assert f"[{i}] document-name.pdf — page 99 | chunk {i - 1}: " in payload["text"]
    assert len(payload["text"]) <= 12000


def test_t_v190_tool_02_worst_case_envelope_never_bisects_a_passage():
    """The tools.py:112-131 comment's worst-case proof, checked empirically:
    a maximum-length filename (`documents.CLEAN_FILENAME_MAX_CHARS`), a
    3-digit page and chunk_index (the worst-case header, 150 chars), and a
    body of exactly `RAG_PASSAGE_CHARS`, repeated for the max `rag_top_k`
    (10, RET-02). The envelope stays under `compact_output`'s 12,000-char
    cap, so it is returned unmodified -- every passage block survives whole,
    none truncated or bisected."""
    filename = "a" * documents.CLEAN_FILENAME_MAX_CHARS
    body = "b" * tools.RAG_PASSAGE_CHARS
    passages = [passage(filename=filename, page=500, chunk_index=999, text=body) for _ in range(10)]
    searcher = FakeSearcher(result=result(passages))
    payload = execute(searcher=searcher)
    text = payload["text"]
    assert payload["passages"] == 10
    assert len(text) < tools.RAG_SEARCH_ENVELOPE_MAX_CHARS
    assert "…" not in text
    blocks = [tools._render_passage_block(i, p) for i, p in enumerate(passages, start=1)]
    assert max(len(b) - len(body) for b in blocks) == 150  # worst-case header
    for block in blocks:
        assert block in text  # full header + full 1,000-char body, intact


# --------------------------------------------------------------------------
# T-V190-TOOL-03 -- plumbing: run_agent_outcome -> execute_tool, the history
# stub, `_first_argument`, `run_agent`'s frozen signature (EC-05)
# --------------------------------------------------------------------------


def test_t_v190_tool_03_run_agent_outcome_threads_searcher_to_execute_tool(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "how many vacation days do I have?")
    p = passage(filename="hr.pdf", page=4, text="30 days per year")
    searcher = FakeSearcher(result=result([p]))
    llm = FakeLLM(
        [
            LLMResponse("", [search_call()], "tool_calls"),
            LLMResponse("You have 30 days.", [], "stop"),
        ]
    )
    outcome = agent.run_agent_outcome(
        conn=conn,
        conv_id=conv,
        llm=llm,
        skills={},
        runner=RecordingRunner(),
        now=NOW,
        sleep=lambda _s: None,
        searcher=searcher,
    )
    assert outcome.reply == "You have 30 days."
    assert searcher.queries == ["vacation days"]
    tool_message = llm.calls[1][0][-1]
    assert tool_message["role"] == "tool"
    payload = json.loads(tool_message["content"])
    assert payload["passages"] == 1
    assert "hr.pdf" in payload["text"]


def test_t_v190_tool_03_run_agent_gained_no_searcher_parameter():
    """EC-05/NG: `run_agent` (agent.py:234-256) is unchanged, byte-identical,
    so its ~25 existing test call sites stay valid. Its full parameter list
    is separately pinned by `test_t_v180_chat_04_run_agent_signature_and_return_type_unchanged`
    (tests/test_v180_chat.py) -- this only guards the fact T6 could break."""
    assert "searcher" not in inspect.signature(agent.run_agent).parameters


def test_t_v190_tool_03_the_history_stub_shape():
    message = {"content": json.dumps({"text": "Found 1 passages: ...", "passages": 1})}
    arguments = {"query": "x" * 200}
    stub = json.loads(agent._tool_stub(message, ("search_documents", arguments)))
    assert stub == {
        "stub": True,
        "tool": "search_documents",
        "query": ("x" * 200)[:120],
        "passages": 1,
    }


def test_t_v190_tool_03_the_history_stub_defaults_passages_to_zero_on_error():
    message = {"content": json.dumps({"error": "search_documents is not available"})}
    stub = json.loads(agent._tool_stub(message, ("search_documents", {"query": "q"})))
    assert stub["passages"] == 0


def test_t_v190_tool_03_first_argument_reads_the_query():
    assert agent._first_argument(search_call(query="how many days?")) == "how many days?"


# --------------------------------------------------------------------------
# T-V190-TOOL-04 -- the status line
# --------------------------------------------------------------------------


class _StatusTg:
    def __init__(self):
        self.sent = []
        self.edits = []

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))
        return {"message_id": 1}

    def edit_message_text(self, chat_id, message_id, text):
        self.edits.append((chat_id, message_id, text))
        return {"message_id": message_id}


def test_t_v190_tool_04_on_tool_edits_the_status_for_search_documents():
    tg = _StatusTg()
    status = bot._StatusMessage(tg, 424242)
    status.on_tool("search_documents", "vacation days")
    assert tg.edits == [(424242, 1, "⚙️ search_documents: vacation days…")]


def test_t_v190_tool_04_status_line_stays_under_the_char_cap():
    line = bot._status_line("search_documents", "x" * 500)
    assert len(line) <= bot.STATUS_MAX_CHARS


# --------------------------------------------------------------------------
# T-V190-TOOL-05 -- the one system-prompt rule line
# --------------------------------------------------------------------------

PROMPT_LINE = (
    "Docs: search_documents finds user files; answer from returned passages only, "
    "cite Source: <filename> (page N); else say the docs lack it."
)


def test_t_v190_tool_05_the_prompt_gains_exactly_this_line():
    assert PROMPT_LINE in agent.SYSTEM_PROMPT


def test_t_v190_tool_05_the_line_is_140_chars_or_fewer_and_ascii():
    assert len(PROMPT_LINE) <= 140, len(PROMPT_LINE)
    assert PROMPT_LINE.isascii()


def test_t_v190_tool_05_the_whole_prompt_stays_at_or_under_700_chars():
    measured = len(agent.SYSTEM_PROMPT.replace("{skill_lines}", ""))
    assert measured <= 700, measured


# tests/test_prefix.py::test_pfx_01_every_mandatory_statement_survives is the
# guard for the v1.3 prompt compression's mandatory statements; it is not
# re-imported here (that would double-collect it) -- it is run explicitly as
# part of this task's gate and quoted in the report instead.


# --------------------------------------------------------------------------
# REQ-V190-TOOL-06 -- conversation-aware RAG, pinned offline (T-V190-TOOL-07)
# --------------------------------------------------------------------------


def test_t_v190_tool_07_the_second_turns_query_and_history_carry_the_subject(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "Сколько дней отпуска?")
    p = passage(filename="hr.pdf", page=1, text="28 дней в год")
    searcher = FakeSearcher(script=[result([p]), result([p])])
    llm1 = FakeLLM(
        [
            LLMResponse("", [search_call(query="дни отпуска")], "tool_calls"),
            LLMResponse("28 дней.", [], "stop"),
        ]
    )
    agent.run_agent_outcome(
        conn=conn,
        conv_id=conv,
        llm=llm1,
        skills={},
        runner=RecordingRunner(),
        now=NOW,
        sleep=lambda _s: None,
        searcher=searcher,
    )
    storage.add_user_message(conn, conv, "а в неделях?")
    llm2 = FakeLLM(
        [
            LLMResponse("", [search_call(index=1, query="отпуск в неделях")], "tool_calls"),
            LLMResponse("4 недели.", [], "stop"),
        ]
    )
    outcome2 = agent.run_agent_outcome(
        conn=conn,
        conv_id=conv,
        llm=llm2,
        skills={},
        runner=RecordingRunner(),
        now=NOW,
        sleep=lambda _s: None,
        searcher=searcher,
    )
    assert outcome2.reply == "4 недели."
    # No query-rewriting layer exists (NG-07's spirit): the harness passes
    # the model's own scripted query to the Searcher unmodified.
    assert searcher.queries == ["дни отпуска", "отпуск в неделях"]
    # The mechanism REQ-V190-TOOL-06 actually relies on -- the existing
    # history window -- really did carry the first turn's subject into the
    # second turn's request.
    first_round_messages = llm2.calls[0][0]
    contents = [
        message.get("content", "")
        for message in first_round_messages
        if isinstance(message.get("content"), str)
    ]
    assert any("Сколько дней отпуска" in c for c in contents)
    # And the tool result reached the model.
    tool_message = llm2.calls[1][0][-1]
    assert json.loads(tool_message["content"])["passages"] == 1


# --------------------------------------------------------------------------
# T-V190-SEC-04 -- the model cannot choose the user (SEC-02); no file on
# disk in documents.py (SEC-04's currently-checkable half). The spec also
# greps `inspect.getsource` of the new bot.py upload handler
# (spec-v1.9.0.md:1416-1421); that handler does not exist yet -- it lands in
# the CMD task -- so only the two halves below are implementable now.
# --------------------------------------------------------------------------


def _forbidden_file_io(source: str) -> set[str]:
    """AST-walked, not text-grepped: `documents.py`'s own module docstring
    documents this exact invariant in prose (`no open()`, `no Path`), so a
    literal substring search would trip on its own documentation."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        is_open_call = (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        )
        if is_open_call:
            found.add("open(")
        if isinstance(node, ast.Name) and node.id == "Path":
            found.add("Path")
        if isinstance(node, ast.Attribute) and node.attr == "write_bytes":
            found.add("write_bytes")
        if isinstance(node, ast.Import) and any(
            alias.name.split(".")[0] == "tempfile" for alias in node.names
        ):
            found.add("tempfile")
        if isinstance(node, ast.ImportFrom) and node.module == "tempfile":
            found.add("tempfile")
    return found


def test_t_v190_sec_04_documents_module_has_no_file_io():
    source = (REPO_ROOT / "documents.py").read_text(encoding="utf-8")
    assert _forbidden_file_io(source) == set()


def test_t_v190_sec_04_the_schema_has_no_user_id_property():
    parameters = SEARCH_SPEC["function"]["parameters"]
    assert "user_id" not in parameters["properties"]
    assert parameters["additionalProperties"] is False


def test_t_v190_sec_04_the_extra_key_changes_nothing():
    searcher = FakeSearcher(result=result([]), user_id=USER_ID)
    payload = json.loads(
        tools.execute_tool(
            "search_documents",
            json.dumps({"query": "x", "user_id": 7}),
            skills={},
            runner=RecordingRunner(),
            searcher=searcher,
        )
    )
    assert "error" not in payload
    assert searcher.queries == ["x"]
    assert searcher.user_id == USER_ID  # unaffected by the arguments' user_id
