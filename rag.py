"""spec-v1.9.0 T5 (docs/spec/spec-v1.9.0.md Sec.5, REQ-V190-RET-03..07;
Sec.9, REQ-V190-SEC-01): retrieval -- vector search, BM25 rebuilt per query
(NG-07: no persistent index, no caching across queries), Reciprocal Rank
Fusion, an LLM listwise rerank that is never fatal, and the `Searcher` that
sequences all four behind one five-field `SearchResult`.

This module issues no raw SQL of its own -- every runtime statement goes
through `storage.*` (SEC-01: zero direct connection-level execute calls
here). It imports `agent` for `agent._record_llm_call` (the rerank
bookkeeping helper, the same one the summary path uses); `agent.py` never
imports this module, so there is no cycle. It does not import `bot`.
"""

import contextlib
import itertools
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import rank_bm25
import snowballstemmer
import sqlite_vec

import agent
import config
import storage
import tracing
from llm.base import LLMClient, LLMError, resolve_reasoning

log = logging.getLogger("rag")

_STEMMER = snowballstemmer.stemmer("russian")

_RERANK_SYSTEM = (
    "Rank passages by relevance to the question. Reply with a JSON array "
    "of passage numbers, most relevant first, nothing else."
)
_RERANK_CANDIDATE_CHARS = 600
# v1.9.1 T1 (docs/reports/report-v1.9.1.md): v1.9.0's 2048 assumed another
# model's chain-of-thought had to be absorbed inside this budget. Measured
# instead, across every routed model and a JSON-schema request (below), the
# passing completion length tops out at 53 tokens; 128 keeps over 2x
# headroom on that measurement. A thinking model pointed at rerank will now
# truncate before ever emitting `{"order": [...]}` and `_parse_rerank_reply`
# returns `None` -- Searcher.search's existing fallback to the plain RRF
# order still applies, so this is a safe, gate-visible degradation (gate 7
# fails loudly), never a silent one.
_RERANK_MAX_TOKENS = 128
# v1.9.1 T3 (docs/spec/task-briefs/v191-T3.md, amended): 10.0 (this
# constant's first T3 value) was measured against a contaminated gate 7 run
# (concurrent with gate 6's mutation of this file) and turned out too tight
# for the real tail: three clean, sha-verified sequential gate 7 runs all
# showed the same shape -- one item's rerank call times out on attempt 1
# and attempt 2 at 10.0s each, succeeding only on attempt 3, i.e. every one
# of those passes had zero retry budget left. 15.0 restores real headroom
# on that measured tail while a 429 still returns fast enough not to matter
# -- worst case per item is now 3 * 15.0 + (0.5 + 1.5) = 47.0s.
_RERANK_TIMEOUT_S = 15.0
# v1.9.1 T3: one initial try plus two retries -- a transient, explicitly
# `retryable` upstream error (a 429 from a single-upstream model, the exact
# failure that took gate 7 down under T1) must not degrade straight to RRF
# fallback on its first occurrence.
_RERANK_MAX_ATTEMPTS = 3
# v1.9.1 T3: backoff before each retry, in seconds, indexed by
# `attempt - 1` (attempt 1 failing waits index 0 before attempt 2, and so
# on) -- a module constant, never a literal buried in the retry loop.
_RERANK_RETRY_BACKOFF_S = (0.5, 1.5)

_HYBRID_CANDIDATES = 10  # RRF is cut to this many candidates for the reranker


def tokenize(text: str) -> list[str]:
    """REQ-V190-RET-04's tokenizer rule, exactly: `\\w+` over the lowercased
    text, then the Russian Snowball stemmer over the resulting token list.
    The stemmer passes English tokens through unchanged."""
    return _STEMMER.stemWords(re.findall(r"\w+", text.lower()))


def vector_search(
    conn, *, user_id: int, embedder, query: str, k: int = 20, conv_id: int | None = None
) -> list[int]:
    """REQ-V190-RET-03: embed `query` (one text), then the partition-keyed
    KNN (T1's `storage.knn_chunk_ids`). Returns chunk ids ordered by
    ascending cosine distance; `[]` when the user has no `vec_chunks` rows.

    `conv_id` is not part of the brief's abbreviated signature but is
    `llm/embeddings.py:48-56`'s own contract: the caller passes the turn's
    `conv_id` through so the one CLIENT span per embeddings request is
    attributable to the query that triggered it (RET-01), distinct from an
    indexing call's `conv_id=None`. `Searcher.search` supplies its own."""
    [vector] = embedder.embed([query], conv_id=conv_id)
    serialized = sqlite_vec.serialize_float32(vector)
    rows = storage.knn_chunk_ids(conn, user_id=user_id, vector=serialized, k=k)
    return [chunk_id for chunk_id, _distance in rows]


def bm25_search(rows, query: str, k: int = 20) -> list[int]:
    """REQ-V190-RET-04: `rank_bm25.BM25Okapi` built fresh over `rows` (T1's
    `storage.user_chunks`) for this query only -- no persistent index, no
    caching across queries (NG-07). Only `score > 0` rows are returned, by
    descending score then ascending id, at most `k`; a zero-score row is
    dropped, never ranked last. `[]` for an empty corpus or an all-zero
    score vector."""
    if not rows:
        return []
    corpus = [tokenize(row["text"]) for row in rows]
    bm25 = rank_bm25.BM25Okapi(corpus)
    scores = bm25.get_scores(tokenize(query))
    scored = [(row["id"], score) for row, score in zip(rows, scores, strict=True) if score > 0]
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    return [chunk_id for chunk_id, _score in scored[:k]]


def rrf(rankings: list[list[int]], k: int = 60) -> list[int]:
    """REQ-V190-RET-05: for every ranking, for every chunk id at its 0-based
    position `rank` within that ranking, `score[d] += 1 / (k + rank)`.
    Result: ids sorted by descending score, ties broken by ascending id."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    return [chunk_id for chunk_id, _score in ordered]


@dataclass(frozen=True)
class Passage:
    chunk_id: int
    filename: str
    page: int | None
    chunk_index: int
    text: str


def _rerank_messages(question: str, candidates: list[Passage]) -> list[dict]:
    lines = [f"Question: {question}", "", "Passages:"]
    for i, passage in enumerate(candidates, start=1):
        lines.append(f"[{i}] {passage.text[:_RERANK_CANDIDATE_CHARS]}")
    return [
        {"role": "system", "content": _RERANK_SYSTEM},
        {"role": "user", "content": "\n".join(lines)},
    ]


def _rerank_response_format(n: int) -> dict:
    """The JSON-schema `response_format` for the rerank call (v1.9.1 T1):
    `n` is the candidate count actually sent to this call, never
    `_HYBRID_CANDIDATES` -- a smaller final batch must produce a tighter
    `maximum`/`maxItems`, not the constant's ceiling. `_parse_rerank_reply`
    needs no change to read `{"order": [...]}`: its `re.search(r"\\[.*?\\]",
    ...)` already lifts the array out of the wrapping object."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "rerank",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "order": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 1, "maximum": n},
                        "minItems": 1,
                        "maxItems": n,
                    }
                },
                "required": ["order"],
                "additionalProperties": False,
            },
        },
    }


def _parse_rerank_reply(content: str, n: int) -> list[int] | None:
    """The reply as a JSON array of integers, tolerating a fenced code block
    or surrounding prose by extracting the first `[`...`]` substring.
    Returns 0-based indices, or `None` on any failure: unparsable JSON, not
    a list, an index outside `1..n`, or a duplicate index."""
    match = re.search(r"\[.*?\]", content, re.DOTALL)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, list) or not parsed:
        return None
    seen: set[int] = set()
    indices: list[int] = []
    for item in parsed:
        if not isinstance(item, int) or isinstance(item, bool):
            return None
        if item < 1 or item > n or item in seen:
            return None
        seen.add(item)
        indices.append(item - 1)
    return indices


def _reorder(candidates: list[Passage], order: list[int]) -> list[Passage]:
    reordered = [candidates[i] for i in order]
    omitted = [c for i, c in enumerate(candidates) if i not in order]
    return reordered + omitted


def rerank(
    llm: LLMClient,
    *,
    question: str,
    candidates: list[Passage],
    conn,
    conv_id: int,
    resolve_cost,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Passage] | None:
    """REQ-V190-RET-06/-07 (v1.9.1 T3, docs/spec/task-briefs/v191-T3.md): an
    LLM listwise rerank call, retried up to `_RERANK_MAX_ATTEMPTS` times
    when -- and only when -- the raised `LLMError` is `retryable`. Every
    attempt is recorded in `llm_calls` with `purpose="rerank"`, `round=0`,
    `attempt=<n>`, `turn_id=None`, inside its own `chat` CLIENT span (one
    span per attempt -- REQ-V160-TRC-04's rule, mirrored from `agent.py`'s
    per-attempt loop), through `agent._record_llm_call` -- the same
    function the summary path uses (`agent.py:1238-1257`'s pattern).

    Reasoning is forced off regardless of the operator's policy
    (`resolve_reasoning("off", frozenset(), "final")`, RET-06), not left to
    `cfg.llm_reasoning_policy`.

    A retry that succeeds is logged too (attempt number, elapsed seconds of
    the successful call) at the same level as a retry that fails -- a
    silent recovery hides a degraded route as much as a silent retry does.

    Returns the candidates reordered per the parsed reply, followed by any
    candidate the reply omitted (in their original order). Returns `None`
    when every attempt is exhausted or the failure is not retryable: a
    non-retryable `LLMError`, a retryable `LLMError` still failing after
    `_RERANK_MAX_ATTEMPTS` attempts (including a timeout, which surfaces as
    an `LLMError` with `kind="timeout"`), an unparsable reply, an index
    outside `1..len(candidates)`, or a duplicate index. An unparsable reply
    or an out-of-range/duplicate index is never retried -- it is not
    transient, and a retry would only burn the attempt budget. Never raises
    for any of those classes; an unexpected failure in the bookkeeping
    below (`_record_llm_call`, span finalisation, `resolve_cost`) is
    deliberately left to propagate -- the caller (`Searcher.search`) is the
    one that wraps this whole call in `try/except Exception`.
    """
    messages = _rerank_messages(question, candidates)
    reasoning = resolve_reasoning("off", frozenset(), "final")
    sink = tracing.SqliteSpanSink(conn)
    response = None
    failure: LLMError | None = None
    for attempt in range(1, _RERANK_MAX_ATTEMPTS + 1):
        ts = storage.utc_now_iso()
        started = time.monotonic()
        response = None
        failure = None
        with tracing.start_span("chat", tracing.KIND_CLIENT, sink=sink, conv_id=conv_id) as span:
            try:
                response = llm.complete(
                    messages,
                    None,
                    max_tokens=_RERANK_MAX_TOKENS,
                    reasoning=reasoning,
                    timeout_s=_RERANK_TIMEOUT_S,
                    response_format=_rerank_response_format(len(candidates)),
                )
            except LLMError as exc:
                span.set_error(exc)
                failure = exc
            elapsed_s = time.monotonic() - started
            agent._record_llm_call(
                conn,
                conv_id,
                llm,
                resolve_cost,
                span=span,
                purpose="rerank",
                round_no=0,
                attempt=attempt,
                ts=ts,
                latency_ms=max(0, int(elapsed_s * 1000)),
                turn_id=None,
                messages=messages,
                tools=None,
                response=response,
                error_kind=None if failure is None else failure.kind,
                reasoning=reasoning,
            )
        if failure is None:
            # v1.9.1 T3 (amended): a silent retry is how a degraded route
            # hides, and so is a silent recovery -- log the attempt it took
            # and the successful call's own elapsed time, so a future gate 7
            # run can show how close to _RERANK_TIMEOUT_S the real call gets.
            if attempt > 1:
                log.warning(
                    "rerank succeeded on attempt %d after %.2fs",
                    attempt,
                    elapsed_s,
                )
            break
        if failure.retryable and attempt < _RERANK_MAX_ATTEMPTS:
            log.warning(
                "rerank attempt %d failed, retrying: %s",
                attempt,
                failure,
            )
            sleep(_RERANK_RETRY_BACKOFF_S[attempt - 1])
            continue
        return None
    order = _parse_rerank_reply(response.content, len(candidates))
    if order is None:
        return None
    return _reorder(candidates, order)


@dataclass(frozen=True)
class SearchResult:
    passages: list[Passage]
    documents_present: bool
    rerank_attempted: bool
    rerank_succeeded: bool
    rerank_failure: str | None


_FAILURE_REASON_MAX_CHARS = 200


def _failure_reason(exc: BaseException) -> str:
    """A short, redacted reason string -- the same text the fallback
    warning carries. Redacted first (never truncate a secret's fragment
    into something that still leaks it), then capped."""
    reason = config.redact(f"{exc.__class__.__name__}: {exc}")
    return reason[:_FAILURE_REASON_MAX_CHARS]


class Searcher:
    """REQ-V190-RET-07: vector + BM25 retrieval, RRF fusion to at most ten
    candidates, hydration through `storage.chunks_by_ids` (restoring RRF
    order -- the DB's row order never reorders the candidates), an optional
    listwise rerank, and a slice to `cfg.rag_top_k`.

    `user_id` is bound at construction (by `bot.py`, T7's job) and is not a
    parameter of `search`. `self.calls` collects every `SearchResult` of the
    turn, in order (T6's attribution logic reads this).
    """

    def __init__(self, conn, *, user_id: int, embedder, llm, cfg, conv_id, resolve_cost):
        self.conn = conn
        self.user_id = user_id
        self.embedder = embedder
        self.llm = llm
        self.cfg = cfg
        self.conv_id = conv_id
        self.resolve_cost = resolve_cost
        self.calls: list[SearchResult] = []

    def search(self, query: str) -> SearchResult:
        documents_present = storage.document_count(self.conn, user_id=self.user_id) > 0

        # Step 1: vector retrieval (RET-03) and BM25 retrieval (RET-04),
        # each at most 20 ids.
        vector_ids = vector_search(
            self.conn,
            user_id=self.user_id,
            embedder=self.embedder,
            query=query,
            conv_id=self.conv_id,
        )
        rows = storage.user_chunks(self.conn, user_id=self.user_id)
        bm25_ids = bm25_search(rows, query)

        # Step 2: RRF fusion (RET-05), cut to at most ten candidates.
        hybrid = rrf([vector_ids, bm25_ids])[:_HYBRID_CANDIDATES]

        # Step 3: hydrate through storage.chunks_by_ids -- exactly once per
        # search -- and restore the RRF order over the returned rows.
        hydrated_rows = storage.chunks_by_ids(self.conn, user_id=self.user_id, ids=hybrid)
        by_id = {row["id"]: row for row in hydrated_rows}
        passages = [
            Passage(
                chunk_id=chunk_id,
                filename=by_id[chunk_id]["filename"],
                page=by_id[chunk_id]["page"],
                chunk_index=by_id[chunk_id]["chunk_index"],
                text=by_id[chunk_id]["text"],
            )
            for chunk_id in hybrid
            if chunk_id in by_id
        ]

        # Step 4: rerank when on and there are >= 2 candidates. Any failure
        # -- expected (rerank() itself returned None) or not (an exception
        # from the rerank call or any of its bookkeeping) -- falls back to
        # the hydrated RRF order from step 3.
        rerank_attempted = self.cfg.rag_rerank == "on" and len(passages) >= 2
        rerank_succeeded = False
        rerank_failure: str | None = None
        final_passages = passages

        if rerank_attempted:
            reason: str | None = None
            try:
                reordered = rerank(
                    self.llm,
                    question=query,
                    candidates=passages,
                    conn=self.conn,
                    conv_id=self.conv_id,
                    resolve_cost=self.resolve_cost,
                )
                if reordered is not None:
                    final_passages = reordered
                    rerank_succeeded = True
                else:
                    reason = "rerank returned no usable order"
            except Exception as exc:  # the fallback boundary
                reason = _failure_reason(exc)
            if not rerank_succeeded:
                rerank_failure = reason
                with contextlib.suppress(Exception):  # a failing logger must not escape
                    log.warning("rerank fell back to rrf order: %s", rerank_failure)

        # Step 5: slice to the first cfg.rag_top_k.
        result = SearchResult(
            passages=final_passages[: self.cfg.rag_top_k],
            documents_present=documents_present,
            rerank_attempted=rerank_attempted,
            rerank_succeeded=rerank_succeeded,
            rerank_failure=rerank_failure,
        )
        self.calls.append(result)
        return result


# --------------------------------------------------------------------------
# Attribution (REQ-V190-TOOL-05, T6): a structural `Sources:` guarantee --
# never by parsing a filename out of the reply, always by generating the
# closed set of canonical renderings the returned passages license and
# checking a candidate line for whole-string equality against it.
# --------------------------------------------------------------------------

_MAX_SOURCE_PAIRS = 5
_STRIPPED_SOURCE_WARNING = "stripped an invented source line"


def _render_sources(pairs: list[tuple[str, int | None]]) -> str:
    """Group `pairs` by filename, in first-seen filename order. Each
    filename is followed by `(page N)` for a single distinct page or
    `(pages N, M, ...)` for several, in first-seen page order, and by
    nothing when every occurrence of that filename carries a `NULL` page.
    Filenames are joined with `, `."""
    order: list[str] = []
    pages_by_filename: dict[str, list[int]] = {}
    for filename, page in pairs:
        if filename not in pages_by_filename:
            pages_by_filename[filename] = []
            order.append(filename)
        if page is not None and page not in pages_by_filename[filename]:
            pages_by_filename[filename].append(page)

    parts = []
    for filename in order:
        pages = pages_by_filename[filename]
        if not pages:
            parts.append(filename)
        elif len(pages) == 1:
            parts.append(f"{filename} (page {pages[0]})")
        else:
            parts.append(f"{filename} (pages {', '.join(str(p) for p in pages)})")
    return ", ".join(parts)


def _collect_source_pairs(calls: list[SearchResult]) -> list[tuple[str, int | None]]:
    """Distinct `(filename, page)` pairs across every call of the turn, in
    first-seen order, capped at `_MAX_SOURCE_PAIRS`."""
    pairs: list[tuple[str, int | None]] = []
    seen: set[tuple[str, int | None]] = set()
    for call in calls:
        for passage in call.passages:
            pair = (passage.filename, passage.page)
            if pair not in seen:
                seen.add(pair)
                pairs.append(pair)
    return pairs[:_MAX_SOURCE_PAIRS]


def _valid_source_lines(pairs: list[tuple[str, int | None]]) -> set[str]:
    """Every non-empty subset of `pairs`, in first-seen order, rendered
    behind either accepted prefix -- the canonical-rendering set a reply's
    `Source:`/`Sources:` line is checked against by whole-string equality.
    At most `_MAX_SOURCE_PAIRS` pairs means at most 31 subsets, computed
    once per turn; nothing here ever parses a filename back out of a line."""
    lines: set[str] = set()
    for size in range(1, len(pairs) + 1):
        for combo in itertools.combinations(range(len(pairs)), size):
            rendered = _render_sources([pairs[i] for i in combo])
            lines.add(f"Source: {rendered}")
            lines.add(f"Sources: {rendered}")
    return lines


def _is_source_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("Source:", "Sources:"))


def _strip_source_lines(reply: str, *, keep: set[str]) -> tuple[str, bool]:
    """Removes every `Source:`/`Sources:` line whose stripped text is not in
    `keep` (an empty set strips all of them). Returns the rebuilt reply and
    whether a valid line survived. One `log.warning` total for the whole
    call, regardless of how many lines were removed."""
    kept_lines = []
    removed_any = False
    kept_valid = False
    for line in reply.split("\n"):
        if _is_source_line(line):
            if line.strip() in keep:
                kept_lines.append(line)
                kept_valid = True
            else:
                removed_any = True
        else:
            kept_lines.append(line)
    if removed_any:
        with contextlib.suppress(Exception):  # a failing logger must not escape
            log.warning(_STRIPPED_SOURCE_WARNING)
    return "\n".join(kept_lines), kept_valid


def attach_sources(reply: str, calls: list[SearchResult]) -> tuple[str, bool]:
    """REQ-V190-TOOL-05: only ever called from `bot.py` when `outcome.failed`
    is false and this turn's `Searcher` recorded >= 1 call.

    - Any call returned >= 1 passage: every `Source:`/`Sources:` line of
      `reply` survives only when it exactly equals one of the canonical
      renderings `_valid_source_lines` generates over the collected pairs;
      every other such line is stripped. If no valid line remains, the
      canonical block (`\\n\\nSources: ` + the rendering over every
      collected pair) is appended.
    - No call returned any passage: every `Source:`/`Sources:` line is
      stripped (the model's answer is "the documents do not cover it").
    - No calls at all: `reply` is returned untouched (`bot.py` does not call
      this function in that case; the check is defensive).

    Returns `(reply, True)` whenever the reply changed.
    """
    if not calls:
        return reply, False
    if not any(call.passages for call in calls):
        new_reply, _ = _strip_source_lines(reply, keep=set())
        return new_reply, new_reply != reply
    pairs = _collect_source_pairs(calls)
    new_reply, kept_valid = _strip_source_lines(reply, keep=_valid_source_lines(pairs))
    if not kept_valid:
        new_reply = new_reply + "\n\nSources: " + _render_sources(pairs)
    return new_reply, new_reply != reply
