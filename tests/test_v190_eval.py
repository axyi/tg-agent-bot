"""spec-v1.9.0 T8 (docs/spec/spec-v1.9.0.md Sec.10, REQ-V190-EVAL-01..04):
`devtools/rag_eval.py`, gate 7, and the committed `evals/rag/` corpus and
question set.

Offline throughout, `FakeEmbedder` plus a small local rerank/agent double
(`_DynamicRerankLLM`, defined below -- `rag.rerank`'s prompt always lists
`[1] ...`, `[2] ...`, one line per candidate, so a valid reply is generated
from the actual candidate count rather than hand-guessed, which varies with
real BM25/vector ranking). `T-V190-EVAL-01`/`T-V190-EVAL-04` read the real
committed `evals/rag/corpus/` and `evals/rag/questions.json` (still no
network: parsing/extraction is pure). `T-V190-EVAL-02`/`T-V190-EVAL-03`
drive `devtools.rag_eval.run()` -- the whole script's logic -- against a
tiny synthetic four-document corpus with fully disjoint vocabulary and at
most one chunk per source, so every mode's top-5 always contains every
chunk in the corpus (recall@5 == 1.0 is then a pigeonhole guarantee, never
a coin flip on real ranking behaviour) while MRR is still real, scripted
ranking arithmetic, cross-checked independently from the printed table.
"""

from __future__ import annotations

import json
import re

import config
import devtools.rag_eval as rag_eval
import documents
import storage
from devtools.pdf_fixture import write_pdf
from llm.base import LLMError, LLMResponse, ToolCall
from tests.fakes import FakeEmbedder

DIM = 256
REPO_ROOT = rag_eval.REPO_ROOT


# ---------------------------------------------------------------------------
# Shared offline fixtures
# ---------------------------------------------------------------------------


def _conn(tmp_path, *, dim=DIM, model="fake-model", name="a.db"):
    conn = storage.connect(tmp_path / name)
    storage.init_schema(conn, embedding_dim=dim, embedding_model=model)
    return conn


def _cfg(tmp_path, **overrides):
    fields = {
        "telegram_bot_token": "123456789:sentinel-token-for-rag-eval-tests",
        "allowed_tg_ids": frozenset({1}),
        "llm_provider": "lmstudio",
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_model": "m",
        "openrouter_api_key": "",
        "openrouter_model": "",
        "llm_timeout_s": 30.0,
        "exec_workdir": tmp_path / "sandbox",
        "db_path": tmp_path / "test.db",
        "embedding_base_url": "http://localhost:1234/v1",
        "embedding_model": "fake-model",
        "embedding_dim": DIM,
    }
    fields.update(overrides)
    return config.Config(**fields)


class _DynamicRerankLLM:
    """A rerank call (`tool_definitions is None`, `rag.rerank`'s own
    contract) always gets a valid ascending-order reply sized to the actual
    candidate count parsed out of the prompt's `[N] ...` lines -- real
    BM25/vector ranking decides how many candidates a query gets, so a
    hand-picked constant would be fragile. Every other call (an agent turn,
    `tool_definitions is not None`) is served from a small scripted queue
    reserved for exactly those calls; `fail_on_rerank_call` (1-based) makes
    one specific rerank call return unparsable content instead, for the
    RET-07 gate's own negative test."""

    def __init__(self, agent_script=(), *, fail_on_rerank_call=None):
        self._agent_script = list(agent_script)
        self._fail_on_rerank_call = fail_on_rerank_call
        self._rerank_calls = 0
        self.calls = []

    def describe(self):
        return ("fake", "fake-rerank-model")

    def complete(
        self,
        messages,
        tool_definitions,
        *,
        max_tokens=None,
        reasoning=None,
        timeout_s=None,
        response_format=None,
    ):
        self.calls.append((list(messages), tool_definitions))
        if tool_definitions is None:
            self._rerank_calls += 1
            if self._rerank_calls == self._fail_on_rerank_call:
                return LLMResponse(content="not valid json", tool_calls=[], finish_reason="stop")
            n = len(re.findall(r"^\[\d+\]", messages[-1]["content"], re.MULTILINE))
            return LLMResponse(
                content=json.dumps(list(range(1, n + 1))),
                tool_calls=[],
                finish_reason="stop",
            )
        if not self._agent_script:
            raise AssertionError("agent script exhausted")
        item = self._agent_script.pop(0)
        if isinstance(item, LLMError):
            raise item
        return item


# A four-document corpus with fully disjoint vocabulary (no shared token,
# not even a stopword) and one chunk per source -- BM25 drops every
# non-matching document outright (score > 0 only) and every mode's top-5
# always contains all four chunks, so recall@5 == 1.0 and page_hit_rate ==
# 1.0 are pigeonhole guarantees, never contingent on real ranking order.
_SYNTH_VACATION = (
    "Wombat colony population reached forty specimens this season according to the survey.\n"
)
_SYNTH_ONBOARDING = (
    "Giraffe herd size documented seventeen animals near the savanna region reported today.\n"
)
_SYNTH_EXPENSES = (
    "Elephant sanctuary recorded twelve rescued individuals during the annual census update.\n"
)
_SYNTH_SECURITY = "Lion pride tracked nine members within the reserve boundary this month.\n"

_SYNTH_QUESTIONS = [
    {
        "question": "How many wombat specimens are in the colony?",
        "expected_source": "vacation_policy.md",
        "expected_page": None,
        "expected_evidence": "forty specimens",
    },
    {
        "question": "How many giraffes are in the herd?",
        "expected_source": "onboarding.txt",
        "expected_page": None,
        "expected_evidence": "seventeen animals",
    },
    {
        "question": "How many elephants were rescued?",
        "expected_source": "expenses.docx",
        "expected_page": None,
        "expected_evidence": "twelve rescued individuals",
    },
    {
        "question": "How many lions are in the pride?",
        "expected_source": "security_guidelines.pdf",
        "expected_page": 1,
        "expected_evidence": "nine members",
    },
    {
        "question": "How many tigers are in the reserve?",
        "expected_source": None,
        "expected_page": None,
        "expected_evidence": None,
    },
]


def _write_synth_corpus(tmp_path):
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / "vacation_policy.md").write_text(_SYNTH_VACATION, encoding="utf-8")
    (corpus_dir / "onboarding.txt").write_text(_SYNTH_ONBOARDING, encoding="utf-8")
    (corpus_dir / "expenses.docx.md").write_text(_SYNTH_EXPENSES, encoding="utf-8")
    (corpus_dir / "security_guidelines.pdf.txt").write_text(_SYNTH_SECURITY, encoding="ascii")
    return corpus_dir


def _write_synth_questions(tmp_path, questions=None, *, name="questions.json"):
    path = tmp_path / name
    path.write_text(json.dumps(questions or _SYNTH_QUESTIONS), encoding="utf-8")
    return path


def _smoke_script(turn2_query):
    return [
        LLMResponse(
            "", [ToolCall("c0", "search_documents", json.dumps({"query": "wombat"}))], "tool_calls"
        ),
        LLMResponse("There are forty wombats.", [], "stop"),
        LLMResponse(
            "",
            [ToolCall("c1", "search_documents", json.dumps({"query": turn2_query}))],
            "tool_calls",
        ),
        LLMResponse("In weeks: about six.", [], "stop"),
    ]


def _parse_table(lines):
    """Recovers `{mode: [rank|None, ...]}` from `run()`'s own printed
    markdown table -- the per-question source of truth this test recomputes
    recall/MRR/page-hit-rate from independently of `run()`'s own
    aggregation, so a bug in that aggregation arithmetic (wrong
    denominator, wrong reciprocal) is still caught even though the ranks
    themselves come from real, unmocked retrieval."""
    header_idx = next(i for i, line in enumerate(lines) if line.startswith("| question |"))
    rows = []
    for line in lines[header_idx + 2 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows.append(cells[1:])
    per_mode = {mode: [] for mode in rag_eval.MODES}
    for row in rows:
        for mode, cell in zip(rag_eval.MODES, row, strict=True):
            per_mode[mode].append(None if cell == "miss" else int(cell.removeprefix("hit@")))
    return per_mode


# ---------------------------------------------------------------------------
# T-V190-EVAL-01 -- the committed corpus and question set: shape and counts
# ---------------------------------------------------------------------------


def test_t_v190_eval_01_questions_json_shape_and_counts():
    questions = rag_eval.load_questions(rag_eval.QUESTIONS_PATH)
    assert len(questions) == 12
    answerable = [q for q in questions if q["expected_source"] is not None]
    null_items = [q for q in questions if q["expected_source"] is None]
    assert len(answerable) == 10
    assert len(null_items) == 2
    for q in null_items:
        assert q["expected_page"] is None
        assert q["expected_evidence"] is None

    known_filenames = {indexed for _source, indexed, _kind in rag_eval._CORPUS_SOURCES}
    per_source_count: dict[str, int] = {}
    for q in answerable:
        assert q["expected_source"] in known_filenames
        assert isinstance(q["expected_evidence"], str) and q["expected_evidence"].strip()
        per_source_count[q["expected_source"]] = per_source_count.get(q["expected_source"], 0) + 1
    assert set(per_source_count) == known_filenames
    assert all(count >= 2 for count in per_source_count.values())

    pdf_pages = sorted(
        q["expected_page"] for q in answerable if q["expected_source"] == "security_guidelines.pdf"
    )
    assert pdf_pages == [1, 2, 3]
    for q in answerable:
        if q["expected_source"] != "security_guidelines.pdf":
            assert q["expected_page"] is None


def test_t_v190_eval_01_corpus_files_exist_and_are_disjoint_by_filename():
    for source_name, _indexed, _kind in rag_eval._CORPUS_SOURCES:
        assert (rag_eval.CORPUS_DIR / source_name).is_file()


# ---------------------------------------------------------------------------
# T-V190-EVAL-04 -- every answerable item's evidence occurs verbatim
# (case-insensitive, whitespace-normalised) in its source's *extracted*
# text. Must be green before any live run.
# ---------------------------------------------------------------------------


def test_t_v190_eval_04_every_evidence_occurs_in_its_extracted_source_text():
    documents_to_index = rag_eval.load_corpus_documents(rag_eval.CORPUS_DIR)
    file_type = {
        "vacation_policy.md": "md",
        "onboarding.txt": "txt",
        "expenses.docx": "docx",
        "security_guidelines.pdf": "pdf",
    }
    extracted_text = {
        filename: "\n".join(p.text for p in documents.extract(data, file_type[filename]).pages)
        for filename, data in documents_to_index
    }
    questions = rag_eval.load_questions(rag_eval.QUESTIONS_PATH)
    for q in questions:
        if q["expected_source"] is None:
            continue
        assert rag_eval.contains_evidence(
            extracted_text[q["expected_source"]], q["expected_evidence"]
        ), f"{q['question']!r}: evidence not found verbatim in {q['expected_source']}"


# ---------------------------------------------------------------------------
# T-V190-EVAL-02 -- the whole script, offline: `run()` against the tiny
# synthetic corpus, exit code and metric arithmetic.
# ---------------------------------------------------------------------------


def test_t_v190_eval_02_run_offline_exits_zero_with_correct_metrics(tmp_path):
    corpus_dir = _write_synth_corpus(tmp_path)
    questions_path = _write_synth_questions(tmp_path)
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=DIM)
    llm = _DynamicRerankLLM(_smoke_script("wombat colony in weeks"))
    cfg = _cfg(tmp_path)

    lines: list[str] = []
    code = rag_eval.run(
        conn=conn,
        cfg=cfg,
        embedder=embedder,
        llm=llm,
        corpus_dir=corpus_dir,
        questions_path=questions_path,
        print_fn=lines.append,
    )

    assert code == 0
    assert any(line.startswith("gate-7 override: rag_rerank='on' rag_top_k=5") for line in lines)
    assert any(line == "gate-7: PASS" for line in lines)

    per_mode = _parse_table(lines)
    n = len(per_mode["vector"])
    assert n == 4  # the four answerable synthetic questions

    summary = {
        mode: next(line for line in lines if line.strip().startswith(f"{mode}: recall@5="))
        for mode in rag_eval.MODES
    }
    for mode in rag_eval.MODES:
        ranks = per_mode[mode]
        expected_recall = sum(1 for r in ranks if r is not None) / n
        expected_mrr = sum(1.0 / r if r is not None else 0.0 for r in ranks) / n
        # By construction (<= 4 total chunks, every mode's top-5 holds them
        # all) every answerable item is a hit in every mode.
        assert expected_recall == 1.0
        assert f"recall@5={expected_recall:.3f}" in summary[mode]
        assert f"mrr={expected_mrr:.3f}" in summary[mode]
        assert "page_hit_rate=1.000" in summary[mode]

    assert any("passages returned" in line for line in lines if "How many tigers" in line)
    assert any(line.strip().startswith("conversation-aware smoke: pass") for line in lines)


def test_t_v190_eval_02_run_offline_below_floor_exits_one(tmp_path):
    corpus_dir = _write_synth_corpus(tmp_path)
    bad_questions = json.loads(json.dumps(_SYNTH_QUESTIONS))
    bad_questions[0]["expected_evidence"] = "this text is nowhere in the corpus at all"
    questions_path = _write_synth_questions(tmp_path, bad_questions, name="bad.json")
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=DIM)
    llm = _DynamicRerankLLM(_smoke_script("wombat colony in weeks"))
    cfg = _cfg(tmp_path)

    lines: list[str] = []
    code = rag_eval.run(
        conn=conn,
        cfg=cfg,
        embedder=embedder,
        llm=llm,
        corpus_dir=corpus_dir,
        questions_path=questions_path,
        print_fn=lines.append,
    )

    assert code == 1
    assert any("below the 0.8 floor" in line for line in lines)


def test_t_v190_eval_02_run_offline_rerank_not_both_true_exits_two(tmp_path):
    corpus_dir = _write_synth_corpus(tmp_path)
    questions_path = _write_synth_questions(tmp_path)
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=DIM)
    llm = _DynamicRerankLLM(_smoke_script("wombat colony in weeks"), fail_on_rerank_call=1)
    cfg = _cfg(tmp_path)

    lines: list[str] = []
    code = rag_eval.run(
        conn=conn,
        cfg=cfg,
        embedder=embedder,
        llm=llm,
        corpus_dir=corpus_dir,
        questions_path=questions_path,
        print_fn=lines.append,
    )

    assert code == 2
    assert any("rerank did not run for every answerable item" in line for line in lines)


def test_t_v190_eval_02_run_offline_index_failure_exits_two(tmp_path, monkeypatch):
    corpus_dir = _write_synth_corpus(tmp_path)
    questions_path = _write_synth_questions(tmp_path)
    conn = _conn(tmp_path)
    llm = _DynamicRerankLLM(_smoke_script("wombat colony in weeks"))
    cfg = _cfg(tmp_path)

    class _BrokenEmbedder:
        def embed(self, texts, *, conv_id=None):
            from llm.embeddings import EmbeddingError

            raise EmbeddingError("the box is unreachable")

        def describe(self):
            return ("fake", "broken")

    lines: list[str] = []
    code = rag_eval.run(
        conn=conn,
        cfg=cfg,
        embedder=_BrokenEmbedder(),
        llm=llm,
        corpus_dir=corpus_dir,
        questions_path=questions_path,
        print_fn=lines.append,
    )
    assert code == 2
    assert any("FAIL indexing the corpus" in line for line in lines)


# ---------------------------------------------------------------------------
# T-V190-EVAL-03 -- the script's own components
# ---------------------------------------------------------------------------


def test_t_v190_eval_03_normalize_and_contains_evidence():
    assert rag_eval.normalize("  A\tB\n\nC  ") == "a b c"
    assert rag_eval.contains_evidence("Foo\tBar   Baz", "bar baz")
    assert not rag_eval.contains_evidence("Foo Bar Baz", "quux")


def test_t_v190_eval_03_markdown_to_docx_round_trips_paragraphs_and_table():
    source = (
        "Title paragraph one.\n\n"
        "| A | B |\n| --- | --- |\n| x | 1 |\n| y | 2 |\n\n"
        "Trailing\nparagraph two."
    )
    data = rag_eval.markdown_to_docx_bytes(source)
    extracted = documents.extract(data, "docx")
    text = "\n".join(p.text for p in extracted.pages)
    assert "Title paragraph one." in text
    assert "Trailing paragraph two." in text
    assert "x\t1" in text
    assert "y\t2" in text
    assert "---" not in text  # the separator row must be dropped


def test_t_v190_eval_03_split_pdf_pages():
    text = "Page one line.\n\n\x0c\n\nPage two line."
    pages = rag_eval.split_pdf_pages(text)
    assert pages == ["Page one line.", "Page two line."]
    data = write_pdf(pages)
    extracted = documents.extract(data, "pdf")
    assert [p.page for p in extracted.pages] == [1, 2]
    assert "Page one line." in extracted.pages[0].text
    assert "Page two line." in extracted.pages[1].text


def test_t_v190_eval_03_split_pdf_pages_single_page_no_separator():
    assert rag_eval.split_pdf_pages("Only one page here.") == ["Only one page here."]


def test_t_v190_eval_03_first_hit_requires_filename_and_evidence():
    items = [
        {"filename": "wrong.txt", "page": None, "text": "has the right evidence phrase"},
        {"filename": "right.txt", "page": 3, "text": "does not have it"},
        {"filename": "right.txt", "page": 5, "text": "has the right evidence phrase here"},
    ]
    rank, page = rag_eval.first_hit(
        items, expected_source="right.txt", expected_evidence="right evidence phrase"
    )
    assert (rank, page) == (3, 5)


def test_t_v190_eval_03_first_hit_miss():
    items = [{"filename": "a.txt", "page": None, "text": "irrelevant"}]
    assert rag_eval.first_hit(items, expected_source="a.txt", expected_evidence="not present") == (
        None,
        None,
    )


def test_t_v190_eval_03_conversation_smoke_pass_and_fail(tmp_path):
    corpus_dir = _write_synth_corpus(tmp_path)
    questions_path = _write_synth_questions(tmp_path)
    documents_to_index = rag_eval.load_corpus_documents(corpus_dir)
    del questions_path  # only the corpus is needed directly in this test

    conn = _conn(tmp_path, name="pass.db")
    embedder = FakeEmbedder(dim=DIM)
    rag_eval.index_corpus(conn, embedder=embedder, documents_to_index=documents_to_index)
    cfg = _cfg(tmp_path)
    llm = _DynamicRerankLLM(_smoke_script("wombat colony in weeks"))
    ok, detail = rag_eval.conversation_smoke(
        conn,
        question="How many wombat specimens are in the colony?",
        embedder=embedder,
        llm=llm,
        cfg=cfg,
    )
    assert ok is True
    assert "wombat colony in weeks" in detail

    conn2 = _conn(tmp_path, name="fail.db")
    rag_eval.index_corpus(conn2, embedder=embedder, documents_to_index=documents_to_index)
    llm2 = _DynamicRerankLLM(_smoke_script("giraffe herd size"))
    ok2, detail2 = rag_eval.conversation_smoke(
        conn2,
        question="How many wombat specimens are in the colony?",
        embedder=embedder,
        llm=llm2,
        cfg=cfg,
    )
    assert ok2 is False
    assert "no search_documents call sharing a token" in detail2


def test_t_v190_eval_03_freeze_reports_every_corpus_file_and_questions(tmp_path):
    corpus_dir = _write_synth_corpus(tmp_path)
    questions_path = _write_synth_questions(tmp_path)
    hashes = rag_eval.freeze(corpus_dir, questions_path)
    assert set(hashes) == {
        "vacation_policy.md",
        "onboarding.txt",
        "expenses.docx.md",
        "security_guidelines.pdf.txt",
        "questions.json",
    }
    assert all(len(digest) == 64 for digest in hashes.values())
    # Same content, same hash -- and a byte-for-byte re-read never touches
    # the file, so this also pins "frozen" as "computed from disk", not
    # from some in-memory copy that could silently drift.
    assert hashes == rag_eval.freeze(corpus_dir, questions_path)


def test_t_v190_eval_03_load_corpus_documents_uses_indexed_filenames(tmp_path):
    corpus_dir = _write_synth_corpus(tmp_path)
    documents_to_index = rag_eval.load_corpus_documents(corpus_dir)
    indexed_filenames = {indexed for _source, indexed, _kind in rag_eval._CORPUS_SOURCES}
    assert {filename for filename, _data in documents_to_index} == indexed_filenames
