# Prompt 151 — v1.9.0 T6: the fourth tool, dispatch, prompt, attribution

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for spec-driven implementation tasks in this run (T1-T5 used the same model).
- **Harness:** Claude Code
- **Stage:** T6
- **Owner of:** `tools.py`; `agent.py`; `bot.py`; `rag.py` (attribution tail only); `tests/fakes.py` (`FakeSearcher`); `tests/test_prefix.py`; `tests/test_skills.py`; `tests/test_observability.py` (one-line EC-03 extension); `tests/test_v190_tool.py` (new); `tests/test_v190_attribution.py` (new)
- **REQ ids:** REQ-V190-TOOL-01, REQ-V190-TOOL-02, REQ-V190-TOOL-03, REQ-V190-TOOL-04, REQ-V190-TOOL-05, REQ-V190-TOOL-06, REQ-V190-SEC-02 (checkable half), REQ-V190-SEC-04 (documents.py half)

## Goal

Implement TOOL-01..06 end to end: the fourth tool `search_documents`
appended to `tool_specs()` (TOOL-01); `execute_tool`'s dispatch, the
`Searcher` Protocol boundary (`tools.py` never imports `rag.py`), the
result envelope with exact per-passage truncation arithmetic
(`RAG_PASSAGE_CHARS = 1000`) and a 12,000-char cap proven never to bisect
a represented passage (TOOL-02); `searcher` threaded from
`run_agent_outcome` through `_run_agent_turn`/`_execute_tool_calls` into
`execute_tool`, `run_agent` itself left byte-unchanged (EC-05), the
history stub and the status line (TOOL-03); one new system-prompt rule
line, ≤140 chars, whole prompt ≤700 (TOOL-04); `rag.attach_sources`/
`rag._render_sources` -- the structural `Sources:` guarantee validated
only by generating the closed set of canonical renderings the returned
passages license and checking whole-line equality, never by parsing a
filename (TOOL-05); and conversation-aware RAG pinned offline as a
plumbing/history guarantee, no query-rewriting layer (TOOL-06).

## Constraints

Test-first. `tools.py` gains a `Searcher` Protocol (`search(query: str) ->
SearchResult`) with `SearchResult` imported only under `TYPE_CHECKING`
(quoted forward reference) -- a real import would cycle through
`agent.py`, which `rag.py` itself imports. `RAG_PASSAGE_CHARS` is a fixed
module constant in `tools.py`, deliberately not configuration.
`run_agent`'s signature must stay byte-identical (EC-05); grepped and
pinned by a dedicated test. Attribution never parses a filename out of a
reply line; validation is exact string equality against a generated set
of canonical renderings (at most 31 subsets of at most 5 collected
pairs). One `log.warning("stripped an invented source line")` per
`attach_sources` call regardless of how many invented lines were
stripped. `bot.py`'s `Searcher` wiring is scaffolding only in this
release -- `process_update` passes `searcher=None`; the CMD task
constructs and binds the real instance -- so the `rag.attach_sources`
call site is reachable in shape but inert in production until then. Do
not run `devtools/mutation_check.py` or any live gate.

**Operator-ratified EC-03 extension** (same class as T1's `SCHEMA_VERSION`
erratum and T2's live-embeddings erratum): `tests/test_observability.py:530`
(`test_obs04_a_successful_tool_round_is_recorded`, a pre-v1.9.0 REQ-V13-OBS-04
test, structurally outside REQ-V190-EC-03's original amendment list) hardcoded
`first["tools_exposed"] == 3`; `tools_exposed` is `len(tool_specs())` over the
live catalog, which TOOL-01 unconditionally raises to 4. Found mid-task,
reported to the orchestrator with the file:line and the exact mechanical fix
before touching it (per this run's standing "discovered pre-existing test
break -> stop and wait" instruction), then applied on explicit operator
approval: `3` -> `4`, with an inline comment recording the ratification. No
other hardcoded `tools_exposed` literal in the suite needed touching -- every
other occurrence (`tests/test_observability.py:238`,
`tests/test_v190_storage.py:41`, `tests/test_bench.py`,
`tests/test_v14_patch.py`, `tests/test_pricing.py`,
`tests/test_v160_observability.py`, `tests/fixtures/bench/*.json`) is a
synthetic fixture value fed as input, never compared against a live
`tool_specs()` call.

## Acceptance

`uv run --locked ruff check .`, `uv run --locked pytest` (1463 collected,
up from 1410 before this task's two new files -- 32 in
`tests/test_v190_tool.py`, 21 in `tests/test_v190_attribution.py`),
`uv run --locked python bot.py --selftest` all exit 0. `run_agent`'s
signature has no diff on its `def` line and
`test_t_v180_chat_04_run_agent_signature_and_return_type_unchanged`
(`tests/test_v180_chat.py`) still passes. The fourth tool spec entry is
343 chars (<=350); the whole catalog is 1733 chars (<=1800); the new
prompt line is 137 chars (<=140); the whole prompt is 670 chars (<=700).
`T-V190-TOOL-08` (`tests/test_v190_attribution.py`) proves the
delimiter-hostile filename case (`"a, b (page 9).pdf"`) survives only by
exact canonical-rendering equality, never by parsing.

## Stop

Stopped once, mid-task, per this run's standing instruction: discovered
`tests/test_observability.py:530` broken by TOOL-01's MUST-mandated
catalog change (see Constraints above), reported the file:line and the
exact fix, and waited rather than self-authorizing the amendment-list
extension. Resumed on explicit operator approval; see Constraints for the
ratified fix and its scope.

Also disclosed, not stopped on (deviations from the brief's literal file/line
list, each with its one-line reason):

- `agent._first_argument` (`agent.py:1055-1069`) gained a `search_documents
  -> query` branch. Outside the brief's listed ranges, but MUST-mandated by
  TOOL-03's own text: without it the status line renders
  `search_documents: ` with an empty argument.
- `T-V190-SEC-04` implemented for its two currently-checkable halves only
  (the `documents.py` AST-walked grep -- not a literal substring search,
  since that module's own docstring documents the invariant in prose and
  would false-positive one -- and SEC-02's "an extra `user_id` key changes
  nothing" dispatcher check). The spec's `inspect.getsource(bot._handle_document)`
  half cannot be implemented yet: that handler lands in the CMD task.
- `tests/fakes.py` gained `FakeSearcher`, mirroring the existing
  `FakeFetcher`/`FakeEmbedder` pattern; not in the brief's file list but
  needed by both new test files and available for the CMD task to reuse.
