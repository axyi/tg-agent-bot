"""spec-v1.9.0 T5 (docs/spec/spec-v1.9.0.md Sec.5, REQ-V190-RET-03..07;
Sec.9, REQ-V190-SEC-01): `rag.py` -- vector search, BM25 rebuilt per query,
RRF fusion, the LLM listwise rerank (never fatal) and the `Searcher`
pipeline with its hydrate-before-rerank ordering guarantee.

Offline and deterministic throughout: `FakeEmbedder`/`FakeLLM` only, no
socket, `tmp_path` databases only.

**Erratum (disclosed, see `docs/prompts/150-v190-t5-retrieval.md`):** the
brief's RET-06 call is `resolve_reasoning("off", frozenset(), "final")`
(`llm/base.py:126`). Traced empirically: `policy="off"` -> `value="off"`,
then `REASONING_MECHANISMS["final"]` (`llm/base.py:117`) is `None`, so the
call degrades to `ReasoningRequest("default", None, "final")` --
`.value == "default"`, not `"off"` as spec-v1.9.0-delta-1's test table row
for `T-V190-RET-06` states. The brief's call is implemented verbatim (it is
explicit and the degradation is POL-03's documented, deliberate behaviour);
the assertions below check the value the code actually produces.
"""

from __future__ import annotations

import logging
import re
import types

import sqlite_vec

import rag
import storage
from llm.base import LLMError, LLMResponse
from tests.fakes import FakeEmbedder, FakeLLM

NOW = "2026-09-11T00:00:00Z"


def _conn(tmp_path, dim=16, name="a.db"):
    conn = storage.connect(tmp_path / name)
    storage.init_schema(conn, embedding_dim=dim, embedding_model="m")
    return conn


def _document(conn, user_id, filename, **overrides):
    fields = {
        "user_id": user_id, "filename": filename, "file_type": "txt",
        "created_at": NOW, "size_bytes": 5, "text_chars": 5,
        "page_count": None, "chunk_count": 1, "sha256": "x" * 8,
    }
    fields.update(overrides)
    return storage.add_document(conn, **fields)


def _index(conn, embedder, user_id, filename, texts):
    """Indexes `texts` as one chunk each, embedded through `embedder` --
    the store phase of `documents.index_document`, done by hand so tests can
    pick exact chunk text without going through parsing/chunking."""
    doc_id = _document(conn, user_id, filename, chunk_count=len(texts))
    chunk_ids = storage.add_chunks(
        conn, user_id=user_id, document_id=doc_id,
        chunks=[(i, text, None, 0, len(text)) for i, text in enumerate(texts)],
    )
    vectors = embedder.embed(texts)
    storage.add_vectors(
        conn, user_id=user_id,
        rows=[
            (cid, sqlite_vec.serialize_float32(v))
            for cid, v in zip(chunk_ids, vectors, strict=True)
        ],
    )
    return doc_id, chunk_ids


def _cfg(**overrides):
    fields = {"rag_rerank": "on", "rag_top_k": 5}
    fields.update(overrides)
    return types.SimpleNamespace(**fields)


def _passages(n):
    return [
        rag.Passage(
            chunk_id=i, filename="a.txt", page=None, chunk_index=i - 1, text=f"passage {i} text"
        )
        for i in range(1, n + 1)
    ]


def _expected_hybrid_order(conn, embedder, user_id, query):
    """The RRF order `Searcher.search` must hydrate and (absent a
    successful rerank) return -- computed independently of `Searcher`."""
    vector_ids = rag.vector_search(conn, user_id=user_id, embedder=embedder, query=query)
    rows = storage.user_chunks(conn, user_id=user_id)
    bm25_ids = rag.bm25_search(rows, query)
    return rag.rrf([vector_ids, bm25_ids])[:10]


# ----------------------------------------------------------------------------
# T-V190-RET-03 -- vector search
# ----------------------------------------------------------------------------


def test_t_v190_ret_03_vector_search_ranks_shared_tokens_first(tmp_path):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _, chunk_ids = _index(
        conn, embedder, 1, "a.txt",
        ["python programming language", "cooking recipes for dinner"],
    )

    result = rag.vector_search(conn, user_id=1, embedder=embedder, query="python programming")

    assert result[0] == chunk_ids[0]
    conn.close()


def test_t_v190_ret_03_vector_search_empty_with_no_rows(tmp_path):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)

    assert rag.vector_search(conn, user_id=1, embedder=embedder, query="anything") == []
    conn.close()


def test_t_v190_ret_03_vector_search_threads_conv_id_into_the_embeddings_call(tmp_path):
    # llm/embeddings.py:48-56's contract: the caller passes conv_id through
    # so the embeddings span is attributable to the querying turn.
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)

    rag.vector_search(conn, user_id=1, embedder=embedder, query="anything", conv_id=42)

    assert embedder.calls[-1] == (["anything"], 42)
    conn.close()


def test_t_v190_ret_03_searcher_threads_its_own_conv_id_into_vector_search(tmp_path):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", ["alpha token"])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([])

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="off"),
        conv_id=conv_id, resolve_cost=None,
    )
    searcher.search("alpha token")

    # the first embed call after _index's own indexing call is the query.
    assert embedder.calls[-1] == (["alpha token"], conv_id)
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-RET-04 -- tokenize / bm25_search
# ----------------------------------------------------------------------------


def test_t_v190_ret_04_tokenize_stems_russian_and_passes_english_through():
    tokens = rag.tokenize("Кошки бегают быстро. Running cats are fast.")

    assert tokens == ["кошк", "бега", "быстр", "running", "cats", "are", "fast"]


def test_t_v190_ret_04_bm25_search_drops_zero_score_rows_and_orders_by_score(tmp_path):
    conn = _conn(tmp_path)
    doc_id = _document(conn, 1, "a.txt", chunk_count=3)
    chunk_ids = storage.add_chunks(
        conn, user_id=1, document_id=doc_id,
        chunks=[
            (0, "кошки любят рыбу", None, 0, 10),
            (1, "собаки любят кости", None, 10, 20),
            (2, "случайный текст без отношения", None, 20, 30),
        ],
    )
    rows = storage.user_chunks(conn, user_id=1)

    result = rag.bm25_search(rows, "кошка рыба", k=20)

    # only the matching chunk survives -- the zero-score rows are dropped,
    # never appended at the tail.
    assert result == [chunk_ids[0]]
    conn.close()


def test_t_v190_ret_04_bm25_search_respects_k_and_breaks_ties_by_ascending_id(tmp_path):
    conn = _conn(tmp_path)
    doc_id = _document(conn, 1, "a.txt", chunk_count=4)
    chunk_ids = storage.add_chunks(
        conn, user_id=1, document_id=doc_id,
        chunks=(
            [(i, "яблоко груша слива", None, 0, 10) for i in range(3)]
            # a distractor sharing no query token -- without it "яблоко" is
            # in every row and BM25's idf (and so every score) is <= 0.
            + [(3, "совершенно другой текст без совпадений", None, 0, 10)]
        ),
    )
    rows = storage.user_chunks(conn, user_id=1)

    result = rag.bm25_search(rows, "яблоко", k=2)

    assert result == sorted(chunk_ids[:3])[:2]
    conn.close()


def test_t_v190_ret_04_bm25_search_empty_corpus_returns_empty_list():
    assert rag.bm25_search([], "query", k=20) == []


# ----------------------------------------------------------------------------
# T-V190-RET-05 -- RRF fusion
# ----------------------------------------------------------------------------


def test_t_v190_ret_05_rrf_fuses_two_rankings_by_the_1_over_k_plus_rank_formula():
    # id 1: rank0 in [0] (1/60) + rank1 in [1] (1/61) = 0.033060...
    # id 3: rank2 in [0] (1/62) + rank0 in [1] (1/60) = 0.032796...
    # id 2: rank1 in [0] only = 1/61 = 0.016393...
    # id 4: rank2 in [1] only = 1/62 = 0.016129...
    result = rag.rrf([[1, 2, 3], [3, 1, 4]])

    assert result == [1, 3, 2, 4]


def test_t_v190_ret_05_rrf_ties_break_by_ascending_id():
    # both rank 0 in their own (single-element) ranking -> equal scores.
    assert rag.rrf([[5], [3]]) == [3, 5]


def test_t_v190_ret_05_rrf_an_empty_ranking_yields_the_other_orders_order():
    assert rag.rrf([[10, 20, 30], []]) == [10, 20, 30]


# ----------------------------------------------------------------------------
# T-V190-RET-06 -- rerank, success path
# ----------------------------------------------------------------------------


def test_t_v190_ret_06_rerank_reorders_truncates_candidates_and_records_the_call(tmp_path):
    conn = _conn(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    candidates = [
        rag.Passage(chunk_id=1, filename="a.txt", page=None, chunk_index=0, text="x" * 700),
        rag.Passage(chunk_id=2, filename="a.txt", page=None, chunk_index=1, text="y" * 700),
        rag.Passage(chunk_id=3, filename="a.txt", page=None, chunk_index=2, text="z" * 700),
    ]
    llm = FakeLLM([LLMResponse(content="[3, 1, 2]", tool_calls=[], finish_reason="stop")])

    result = rag.rerank(
        llm, question="what is x?", candidates=candidates,
        conn=conn, conv_id=conv_id, resolve_cost=None,
    )

    assert [p.chunk_id for p in result] == [3, 1, 2]
    # v1.9.1 T1 (docs/reports/report-v1.9.1.md): 128, not v1.9.0's 2048 --
    # measured across every routed model with the JSON schema below, the
    # passing completion length never exceeds 53 tokens.
    assert llm.max_tokens_calls == [128]
    # v1.9.1 T3, amended: 15.0 -- three clean sequential gate 7 runs showed
    # the real tail needs more room than the first T3 value (10.0) gave it
    # (see tests/test_v191_rerank_contract.py for the pinned attempt/backoff
    # constants).
    assert llm.timeout_s_calls == [15.0]
    # See module docstring: resolve_reasoning("off", frozenset(), "final")
    # degrades to "default", not "off" -- disclosed erratum.
    assert llm.reasoning_calls[0].value == "default"
    # v1.9.1 T1: the rerank call carries a JSON schema whose maximum/maxItems
    # equal the candidate count actually sent (3), not _HYBRID_CANDIDATES.
    # Asserted against literals, never against _rerank_response_format's own
    # output: a comparison to the function under test would survive any bug
    # inside it (clean-context review, v1.9.1 T1 finding 1). The schema's full
    # shape is pinned independently in tests/test_v191_rerank_contract.py; what
    # this call site owes is that a schema is sent at all and that it is sized
    # to the candidates, so that is what is checked here.
    assert len(llm.response_format_calls) == 1
    sent = llm.response_format_calls[0]
    assert sent["type"] == "json_schema"
    order = sent["json_schema"]["schema"]["properties"]["order"]
    assert order["items"]["maximum"] == 3
    assert order["maxItems"] == 3

    messages, tools = llm.calls[0]
    assert tools is None
    assert messages[0] == {"role": "system", "content": rag._RERANK_SYSTEM}
    user_content = messages[1]["content"]
    assert "x" * 600 in user_content
    assert "x" * 601 not in user_content

    rows = conn.execute("SELECT purpose, round, attempt, turn_id FROM llm_calls").fetchall()
    assert len(rows) == 1
    assert rows[0]["purpose"] == "rerank"
    assert rows[0]["round"] == 0
    assert rows[0]["attempt"] == 1
    assert rows[0]["turn_id"] is None
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-RET-07 -- rerank, every named failure class returns None;
# Searcher falls back and the bookkeeping guard holds.
# ----------------------------------------------------------------------------


def test_t_v190_ret_07_rerank_returns_none_on_llm_error(tmp_path):
    conn = _conn(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([LLMError("boom", retryable=False, kind="http")])

    result = rag.rerank(
        llm, question="q", candidates=_passages(2),
        conn=conn, conv_id=conv_id, resolve_cost=None,
    )

    assert result is None
    # v1.9.1 T3: a non-retryable failure is never retried.
    assert len(llm.calls) == 1
    conn.close()


def test_t_v190_ret_07_rerank_retries_a_retryable_failure_and_succeeds(tmp_path):
    """v1.9.1 T3 (docs/spec/task-briefs/v191-T3.md): a retryable LLMError
    on attempt 1, success on attempt 2 -- rerank() retries and returns the
    reordered passages, having called the client exactly twice and slept
    once for the first backoff step."""
    conn = _conn(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([
        LLMError("boom", retryable=True, kind="http"),
        LLMResponse(content="[2, 1]", tool_calls=[], finish_reason="stop"),
    ])
    sleeps = []

    result = rag.rerank(
        llm, question="q", candidates=_passages(2),
        conn=conn, conv_id=conv_id, resolve_cost=None,
        sleep=lambda s: sleeps.append(s),
    )

    assert [p.chunk_id for p in result] == [2, 1]
    assert len(llm.calls) == 2
    assert sleeps == [0.5]
    rows = conn.execute("SELECT attempt FROM llm_calls ORDER BY id").fetchall()
    assert [r["attempt"] for r in rows] == [1, 2]
    conn.close()


def test_t_v190_ret_07_rerank_logs_a_successful_retry(tmp_path, caplog):
    """v1.9.1 T3, amended: a retry that succeeds is logged too (not just a
    retry that fails or gives up) -- attempt number and the successful
    call's own elapsed seconds, at the same level as the retry-failure
    warning, so a live gate 7 run can show how close to _RERANK_TIMEOUT_S
    the real call gets."""
    conn = _conn(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([
        LLMError("boom", retryable=True, kind="http"),
        LLMResponse(content="[2, 1]", tool_calls=[], finish_reason="stop"),
    ])

    with caplog.at_level(logging.WARNING, logger="rag"):
        result = rag.rerank(
            llm, question="q", candidates=_passages(2),
            conn=conn, conv_id=conv_id, resolve_cost=None,
            sleep=lambda s: None,
        )

    assert [p.chunk_id for p in result] == [2, 1]
    success_records = [r for r in caplog.records if "succeeded on attempt" in r.getMessage()]
    assert len(success_records) == 1
    message = success_records[0].getMessage()
    assert "2" in message  # the attempt number the success landed on
    assert re.search(r"\d+\.\d+s", message)  # the elapsed-seconds value
    conn.close()


def test_t_v190_ret_07_rerank_does_not_log_success_on_the_first_attempt(tmp_path, caplog):
    """A first-attempt success is the ordinary path, not a recovery -- it
    must not be logged (the brief's own concern is a silent retry or a
    silent recovery, not routine success noise)."""
    conn = _conn(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([LLMResponse(content="[2, 1]", tool_calls=[], finish_reason="stop")])

    with caplog.at_level(logging.WARNING, logger="rag"):
        result = rag.rerank(
            llm, question="q", candidates=_passages(2),
            conn=conn, conv_id=conv_id, resolve_cost=None,
        )

    assert [p.chunk_id for p in result] == [2, 1]
    success_records = [r for r in caplog.records if "succeeded on attempt" in r.getMessage()]
    assert len(success_records) == 0
    conn.close()


def test_t_v190_ret_07_rerank_returns_none_on_timeout(tmp_path):
    """v1.9.1 T3: a `kind="timeout"` LLMError is retryable, so three
    consecutive timeouts exhaust the attempt budget (_RERANK_MAX_ATTEMPTS)
    rather than failing on the first one -- exactly three calls, both
    backoff steps slept, and still None once the budget is spent."""
    conn = _conn(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([
        LLMError("timed out", retryable=True, kind="timeout"),
        LLMError("timed out", retryable=True, kind="timeout"),
        LLMError("timed out", retryable=True, kind="timeout"),
    ])
    sleeps = []

    result = rag.rerank(
        llm, question="q", candidates=_passages(2),
        conn=conn, conv_id=conv_id, resolve_cost=None,
        sleep=lambda s: sleeps.append(s),
    )

    assert result is None
    assert len(llm.calls) == 3
    assert sleeps == [0.5, 1.5]
    conn.close()


def test_t_v190_ret_07_rerank_returns_none_on_unparsable_reply(tmp_path):
    conn = _conn(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([LLMResponse(content="not json", tool_calls=[], finish_reason="stop")])

    result = rag.rerank(
        llm, question="q", candidates=_passages(2),
        conn=conn, conv_id=conv_id, resolve_cost=None,
    )

    assert result is None
    # v1.9.1 T3: an unparsable reply is not a transient failure; never retried.
    assert len(llm.calls) == 1
    conn.close()


def test_t_v190_ret_07_rerank_returns_none_on_out_of_range_index(tmp_path):
    conn = _conn(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([LLMResponse(content="[9]", tool_calls=[], finish_reason="stop")])

    result = rag.rerank(
        llm, question="q", candidates=_passages(2),
        conn=conn, conv_id=conv_id, resolve_cost=None,
    )

    assert result is None
    assert len(llm.calls) == 1
    conn.close()


def test_t_v190_ret_07_rerank_returns_none_on_duplicate_index(tmp_path):
    conn = _conn(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([LLMResponse(content="[1, 1]", tool_calls=[], finish_reason="stop")])

    result = rag.rerank(
        llm, question="q", candidates=_passages(2),
        conn=conn, conv_id=conv_id, resolve_cost=None,
    )

    assert result is None
    assert len(llm.calls) == 1
    conn.close()


def test_t_v190_ret_07_searcher_falls_back_and_logs_exactly_one_warning(tmp_path, caplog):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", ["alpha beta gamma", "alpha beta delta"])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    expected_order = _expected_hybrid_order(conn, embedder, 1, "alpha beta")
    llm = FakeLLM([LLMError("boom", retryable=False, kind="http")])

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="on"),
        conv_id=conv_id, resolve_cost=None,
    )
    with caplog.at_level(logging.WARNING, logger="rag"):
        result = searcher.search("alpha beta")

    assert result.rerank_attempted is True
    assert result.rerank_succeeded is False
    assert result.rerank_failure
    assert [p.chunk_id for p in result.passages] == expected_order
    warnings = [r for r in caplog.records if "rerank fell back to rrf order" in r.getMessage()]
    assert len(warnings) == 1
    conn.close()


def test_t_v190_ret_07_searcher_rerank_retries_then_succeeds(tmp_path, monkeypatch):
    """v1.9.1 T3: a retryable failure on attempt 1, success on attempt 2,
    through the full Searcher.search path (rerank()'s default `sleep`
    parameter, unchanged at this call site per the brief) -- the backoff
    constant is patched to zero so the suite does not really sleep."""
    monkeypatch.setattr(rag, "_RERANK_RETRY_BACKOFF_S", (0.0, 0.0))
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", ["alpha beta gamma", "alpha beta delta"])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    expected_order = _expected_hybrid_order(conn, embedder, 1, "alpha beta")
    llm = FakeLLM([
        LLMError("boom", retryable=True, kind="http"),
        LLMResponse(content="[2, 1]", tool_calls=[], finish_reason="stop"),
    ])

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="on"),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("alpha beta")

    assert result.rerank_attempted is True
    assert result.rerank_succeeded is True
    assert result.rerank_failure is None
    assert [p.chunk_id for p in result.passages] == list(reversed(expected_order))
    assert len(llm.calls) == 2
    conn.close()


def test_t_v190_ret_07_searcher_rerank_exhausts_retries_and_falls_back(
    tmp_path, monkeypatch, caplog,
):
    """v1.9.1 T3: three retryable failures exhaust _RERANK_MAX_ATTEMPTS --
    rerank_succeeded False, rerank_failure non-empty, passages fall back to
    RRF order, and at least one per-retry warning fires in addition to the
    existing single fallback warning. Backoff patched to zero, same reason
    as the test above."""
    monkeypatch.setattr(rag, "_RERANK_RETRY_BACKOFF_S", (0.0, 0.0))
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", ["alpha beta gamma", "alpha beta delta"])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    expected_order = _expected_hybrid_order(conn, embedder, 1, "alpha beta")
    llm = FakeLLM([
        LLMError("boom", retryable=True, kind="http"),
        LLMError("boom", retryable=True, kind="http"),
        LLMError("boom", retryable=True, kind="http"),
    ])

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="on"),
        conv_id=conv_id, resolve_cost=None,
    )
    with caplog.at_level(logging.WARNING, logger="rag"):
        result = searcher.search("alpha beta")

    assert result.rerank_attempted is True
    assert result.rerank_succeeded is False
    assert result.rerank_failure
    assert [p.chunk_id for p in result.passages] == expected_order
    assert len(llm.calls) == 3
    retry_warnings = [r for r in caplog.records if "retrying" in r.getMessage()]
    assert len(retry_warnings) >= 1
    fallback_warnings = [
        r for r in caplog.records if "rerank fell back to rrf order" in r.getMessage()
    ]
    assert len(fallback_warnings) == 1
    conn.close()


def test_t_v190_ret_07_searcher_falls_back_when_record_llm_call_raises(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", ["alpha beta gamma", "alpha beta delta"])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    expected_order = _expected_hybrid_order(conn, embedder, 1, "alpha beta")
    llm = FakeLLM([LLMResponse(content="[1, 2]", tool_calls=[], finish_reason="stop")])

    def _boom(*args, **kwargs):
        raise RuntimeError("record boom")

    monkeypatch.setattr(rag.agent, "_record_llm_call", _boom)

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="on"),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("alpha beta")  # must not raise

    assert result.rerank_attempted is True
    assert result.rerank_succeeded is False
    assert result.rerank_failure
    assert [p.chunk_id for p in result.passages] == expected_order
    conn.close()


def test_t_v190_ret_07_searcher_falls_back_when_the_logger_raises(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", ["alpha beta gamma", "alpha beta delta"])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    expected_order = _expected_hybrid_order(conn, embedder, 1, "alpha beta")
    llm = FakeLLM([LLMError("boom", retryable=False, kind="http")])

    def _boom(*args, **kwargs):
        raise RuntimeError("log boom")

    monkeypatch.setattr(rag.log, "warning", _boom)

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="on"),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("alpha beta")  # must not raise

    assert result.rerank_attempted is True
    assert result.rerank_succeeded is False
    assert result.rerank_failure
    assert [p.chunk_id for p in result.passages] == expected_order
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-RET-08 -- the Searcher pipeline
# ----------------------------------------------------------------------------


def test_t_v190_ret_08_searcher_slices_to_top_k_with_rerank_off(tmp_path):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", [f"shared token number {i}" for i in range(8)])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([])  # must never be called

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="off", rag_top_k=3),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("shared token")

    assert len(result.passages) == 3
    assert result.rerank_attempted is False
    assert result.rerank_succeeded is False
    assert result.rerank_failure is None
    assert llm.calls == []
    assert searcher.calls == [result]
    conn.close()


def test_t_v190_ret_08_documents_present_is_false_with_no_rows(tmp_path):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([])

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("anything")

    assert result.documents_present is False
    assert result.passages == []
    assert result.rerank_attempted is False
    conn.close()


def test_t_v190_ret_08_single_candidate_with_rerank_on_is_not_attempted(tmp_path):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", ["only one chunk here"])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([])

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="on"),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("only one chunk")

    assert result.rerank_attempted is False
    assert result.rerank_succeeded is False
    assert result.rerank_failure is None
    assert llm.calls == []
    conn.close()


def test_t_v190_ret_08_clean_rerank_succeeds_and_reranker_sees_hydrated_passages(
    tmp_path, monkeypatch
):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", ["alpha token one", "alpha token two", "alpha token three"])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    llm = FakeLLM([LLMResponse(content="[2, 1, 3]", tool_calls=[], finish_reason="stop")])

    original = storage.chunks_by_ids
    calls = []

    def _counting(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(storage, "chunks_by_ids", _counting)

    original_rerank = rag.rerank
    seen_candidates = []

    def _recording_rerank(*args, **kwargs):
        seen_candidates.append(kwargs["candidates"])
        return original_rerank(*args, **kwargs)

    monkeypatch.setattr(rag, "rerank", _recording_rerank)

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="on"),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("alpha token")

    assert result.rerank_attempted is True
    assert result.rerank_succeeded is True
    assert result.rerank_failure is None
    assert len(calls) == 1  # chunks_by_ids called exactly once per search

    # the reranker itself received hydrated `Passage` objects -- filename
    # and text both already populated, never bare chunk ids.
    assert len(seen_candidates) == 1
    for passage in seen_candidates[0]:
        assert isinstance(passage, rag.Passage)
        assert passage.filename == "a.txt"
        assert passage.text  # non-empty

    seen_user_message = llm.calls[0][0][1]["content"]
    assert "alpha token" in seen_user_message
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-RET-10 -- hydration cannot reorder RRF
# ----------------------------------------------------------------------------


def test_t_v190_ret_10_hydration_does_not_reorder_rrf_when_rerank_is_off(tmp_path, monkeypatch):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", [f"token{i} shared" for i in range(5)])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    expected_order = _expected_hybrid_order(conn, embedder, 1, "shared")

    original = storage.chunks_by_ids
    calls = []

    def _reversed_rows(conn_, *, user_id, ids):
        calls.append(ids)
        rows = original(conn_, user_id=user_id, ids=ids)
        return list(reversed(rows))

    monkeypatch.setattr(storage, "chunks_by_ids", _reversed_rows)

    llm = FakeLLM([])
    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="off", rag_top_k=10),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("shared")

    assert [p.chunk_id for p in result.passages] == expected_order
    assert len(calls) == 1
    conn.close()


def test_t_v190_ret_10_reranker_receives_rrf_order_despite_reversed_hydration(
    tmp_path, monkeypatch
):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", [f"token{i} shared" for i in range(5)])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    expected_order = _expected_hybrid_order(conn, embedder, 1, "shared")

    original = storage.chunks_by_ids

    def _reversed_rows(conn_, *, user_id, ids):
        rows = original(conn_, user_id=user_id, ids=ids)
        return list(reversed(rows))

    monkeypatch.setattr(storage, "chunks_by_ids", _reversed_rows)

    # rerank fails, so the observable result is the fallback (step-3) order --
    # still proves the RRF order survived hydration, whatever the DB gave back.
    llm = FakeLLM([LLMError("boom", retryable=False, kind="http")])
    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="on", rag_top_k=10),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("shared")

    assert result.rerank_attempted is True
    assert result.rerank_succeeded is False
    assert [p.chunk_id for p in result.passages] == expected_order
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-RET-11 -- the rerank flags cannot claim a rerank that did not apply
# ----------------------------------------------------------------------------


def test_t_v190_ret_11_malformed_json_reply_yields_correct_flags_and_rrf_order(tmp_path):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", ["alpha shared", "beta shared"])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    expected_order = _expected_hybrid_order(conn, embedder, 1, "shared")
    llm = FakeLLM([LLMResponse(content="not json at all", tool_calls=[], finish_reason="stop")])

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="on"),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("shared")

    assert result.rerank_attempted is True
    assert result.rerank_succeeded is False
    assert result.rerank_failure  # non-empty
    assert [p.chunk_id for p in result.passages] == expected_order

    # an llm_calls row exists even though the rerank did not succeed -- proof
    # that an llm_calls row is not evidence of a successful rerank.
    rows = conn.execute("SELECT purpose FROM llm_calls WHERE purpose = 'rerank'").fetchall()
    assert len(rows) == 1
    conn.close()


def test_t_v190_ret_11_record_llm_call_raising_after_a_well_formed_reply_still_falls_back(
    tmp_path, monkeypatch
):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _index(conn, embedder, 1, "a.txt", ["alpha shared", "beta shared"])
    conv_id = storage.get_or_create_active_conversation(conn, 1)
    expected_order = _expected_hybrid_order(conn, embedder, 1, "shared")
    llm = FakeLLM([LLMResponse(content="[1, 2]", tool_calls=[], finish_reason="stop")])

    def _boom(*args, **kwargs):
        raise RuntimeError("record boom")

    monkeypatch.setattr(rag.agent, "_record_llm_call", _boom)

    searcher = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="on"),
        conv_id=conv_id, resolve_cost=None,
    )
    result = searcher.search("shared")  # must not raise

    assert result.rerank_attempted is True
    assert result.rerank_succeeded is False
    assert result.rerank_failure
    assert [p.chunk_id for p in result.passages] == expected_order
    # no llm_calls row: the injected failure pre-empts storage.add_llm_call.
    rows = conn.execute("SELECT purpose FROM llm_calls WHERE purpose = 'rerank'").fetchall()
    assert rows == []
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-SEC-01 -- the owner predicate, exercised through Searcher.search
# ----------------------------------------------------------------------------


def test_t_v190_sec_01_search_is_isolated_per_user_with_the_same_filename(tmp_path):
    conn = _conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    _, a_ids = _index(conn, embedder, 1, "a.txt", ["shared secret alpha content"])
    _, b_ids = _index(conn, embedder, 2, "a.txt", ["shared secret alpha content"])
    conv_id_a = storage.get_or_create_active_conversation(conn, 1)
    conv_id_b = storage.get_or_create_active_conversation(conn, 2)
    llm = FakeLLM([])

    searcher_a = rag.Searcher(
        conn, user_id=1, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="off"),
        conv_id=conv_id_a, resolve_cost=None,
    )
    searcher_b = rag.Searcher(
        conn, user_id=2, embedder=embedder, llm=llm, cfg=_cfg(rag_rerank="off"),
        conv_id=conv_id_b, resolve_cost=None,
    )

    result_a = searcher_a.search("shared secret alpha")
    result_b = searcher_b.search("shared secret alpha")

    assert {p.chunk_id for p in result_a.passages} == set(a_ids)
    assert {p.chunk_id for p in result_b.passages} == set(b_ids)
    assert set(a_ids).isdisjoint(b_ids)

    # both retrieval halves are isolated on their own, not just the hydrated
    # result -- KNN and BM25 each never cross the owner boundary.
    vector_a = rag.vector_search(conn, user_id=1, embedder=embedder, query="shared secret alpha")
    vector_b = rag.vector_search(conn, user_id=2, embedder=embedder, query="shared secret alpha")
    assert set(vector_a) == set(a_ids)
    assert set(vector_b) == set(b_ids)

    # BM25 needs some rows that do NOT contain the query terms for a
    # non-degenerate (positive) idf -- add one distractor chunk per user,
    # each still scoped to its own owner.
    distractor_a = _document(conn, 1, "distractor-a.txt")
    storage.add_chunks(
        conn, user_id=1, document_id=distractor_a,
        chunks=[(0, "unrelated filler text zzz one", None, 0, 10),
                (1, "unrelated filler text zzz two", None, 0, 10)],
    )
    distractor_b = _document(conn, 2, "distractor-b.txt")
    storage.add_chunks(
        conn, user_id=2, document_id=distractor_b,
        chunks=[(0, "unrelated filler text zzz one", None, 0, 10),
                (1, "unrelated filler text zzz two", None, 0, 10)],
    )

    bm25_a = rag.bm25_search(storage.user_chunks(conn, user_id=1), "shared secret alpha")
    bm25_b = rag.bm25_search(storage.user_chunks(conn, user_id=2), "shared secret alpha")
    assert set(bm25_a) == set(a_ids)
    assert set(bm25_b) == set(b_ids)
    conn.close()


def test_t_v190_sec_01_rag_module_issues_no_raw_sql():
    """The self-review the brief asks for, made durable: `rag.py` calls only
    `storage.*` -- no `conn.execute(`/`conn.executemany(` of its own."""
    import inspect

    source = inspect.getsource(rag)

    assert "conn.execute(" not in source
    assert "conn.executemany(" not in source
