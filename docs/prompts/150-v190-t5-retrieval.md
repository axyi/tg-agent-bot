# Prompt 150 — v1.9.0 T5: retrieval (vector, BM25, RRF, rerank, Searcher)

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for spec-driven implementation tasks in this run (T1-T4 used the same model).
- **Harness:** Claude Code
- **Stage:** T5
- **Owner of:** `rag.py` (new); `tests/test_v190_retrieval.py` (new)
- **REQ ids:** REQ-V190-RET-03, REQ-V190-RET-04, REQ-V190-RET-05, REQ-V190-RET-06, REQ-V190-RET-07, REQ-V190-SEC-01

## Goal

Implement `rag.py` end to end: `vector_search` (RET-03, T1's
`storage.knn_chunk_ids`), `tokenize`/`bm25_search` (RET-04, `rank_bm25`
rebuilt fresh per query over T1's `storage.user_chunks`), `rrf` (RET-05,
the `1/(k+rank)` fusion with `k=60`), `rerank` (RET-06, one never-fatal LLM
listwise rerank recorded through `agent._record_llm_call` with reasoning
forced off), and the `Searcher` (RET-07): vector + BM25 -> RRF to ≤10 ->
hydrate through `storage.chunks_by_ids` restoring RRF order -> optional
rerank with fallback -> slice to `cfg.rag_top_k`, exposed as a five-field
`SearchResult` whose three rerank flags are the only sound proof a rerank
ran.

## Constraints

Test-first. `rag.py` issues no raw SQL of its own -- every runtime
statement goes through `storage.*` (SEC-01); verified by a dedicated test
(`test_t_v190_sec_01_rag_module_issues_no_raw_sql`) as well as by
inspection. `rag.py` imports `agent` for `agent._record_llm_call`;
`agent.py` never imports `rag.py`. The rerank invocation **and all of its
bookkeeping** (`_record_llm_call`, span finalisation, `resolve_cost`,
warning formatting) sit inside one `try/except Exception` at the
`Searcher` level; the warning itself is inside its own guarded block so a
failing logger cannot escape either. `rerank_succeeded` is set only as the
last statement on the success path. Exactly one `storage.chunks_by_ids`
call per `search`. Do not run `devtools/mutation_check.py` or any live
gate; every test uses `FakeEmbedder`/`FakeLLM`, no socket.

## Acceptance

`uv run --locked ruff check .`, `uv run --locked pytest` (1409 collected,
up from 1379 before this task -- 30 new in `tests/test_v190_retrieval.py`),
`uv run --locked python bot.py --selftest` all exit 0. The fallback is
proved for every RET-06 failure class named in the brief (`LLMError`, a
`timeout`-kind `LLMError`, an unparsable reply, an out-of-range index, a
duplicate index) -- one test each. Hydration cannot reorder the RRF
candidates (`chunks_by_ids` monkeypatched to return reversed rows; the
final order still matches the independently-computed RRF order, both with
rerank off and with rerank on-but-failing). `llm_calls` carries a `rerank`
row (`purpose='rerank'`, `round=0`, `attempt=1`, `turn_id=NULL`) after a
successful rerank call. The three `SearchResult` rerank flags are checked
on the success path and on every failure path, including two bookkeeping
injections (`agent._record_llm_call` raising, `rag.log.warning` raising)
that must not escape `Searcher.search`.

## Stop

Not stopped on; disclosed here per the orchestrator's standing instruction
to disclose rather than silently choose:

**Reasoning-value erratum (RET-06 vs. spec-v1.9.0-delta-1's test table).**
The brief's exact call, `resolve_reasoning("off", frozenset(), "final")`
(`llm/base.py:126`), was traced empirically before writing any assertion:
`policy="off"` sets `value="off"`, then `REASONING_MECHANISMS["final"]`
(`llm/base.py:117`) is `None` (only `"summary"` carries a mechanism), so
`resolve_reasoning` degrades the result to
`ReasoningRequest("default", None, "final")` -- `.value == "default"`, not
`"off"` as the delta-1 test table's `T-V190-RET-06` row states. This is
POL-03's documented, deliberate degradation rule
(`llm/base.py:132-142`'s docstring: `"off"` reads
`mechanisms.get(tag)`, and when that entry is `None` the request degrades
to `("default", None, tag)` rather than sending a mechanism that does not
exist), not a bug in this task's code. The brief's call is implemented
verbatim, since it is explicit and the degradation is intentional upstream
behaviour; `tests/test_v190_retrieval.py`'s
`test_t_v190_ret_06_rerank_reorders_truncates_candidates_and_records_the_call`
asserts `reasoning.value == "default"` (the value the code actually
produces) with an inline comment pointing back to this erratum, rather than
asserting the delta-1 table's `"off"`. Downstream effect: the `llm_calls`
row for a rerank call stores `reasoning_requested='default'`, not `'off'`;
`reasoning_honored` is computed the same three-valued way every other
purpose's is (`agent.py`'s `_reasoning_honored`, unmodified by this task).

**`T-V190-SEC-05` (the AST walk in `tests/test_v190_isolation.py:178`) was
deliberately left unwidened.** That test's own comment says it "MUST be
widened once `rag.py` lands," and spec line 1393 names `rag.py` as part of
its intended scope. This task's brief downgraded that obligation
explicitly to "confirm with a quick self-review... `rag.py` should contain
zero `conn.execute(` calls of its own" and does not list
`tests/test_v190_isolation.py` under "Files." Per this run's standing
instruction ("do NOT resolve it yourself... wait"), the self-review was
done (and made durable as
`test_t_v190_sec_01_rag_module_issues_no_raw_sql` in the new test file,
which asserts `rag.py`'s source contains no `conn.execute(`/
`conn.executemany(`), but the AST walk itself was not widened to also
cover `rag.py`. The exact mechanical fix, if the orchestrator wants it
applied: in `tests/test_v190_isolation.py`'s
`test_t_v190_sec_05_every_runtime_statement_is_user_scoped` (line 178),
change `source = inspect.getsource(storage)` / `tree = ast.parse(source)`
to also walk a second module object, `rag` (imported at the top of that
file), unioning both modules' offender lists before the final
`assert offenders == []` -- a no-op change given `rag.py` has zero
qualifying `execute`/`executemany` calls, but it closes the file's own
documented gap.
