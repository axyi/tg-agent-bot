# Prompt 163 — v1.9.1 T3: a transient 429 must not fail the gate

- **Date:** 2026-09-12
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded, fully specified patch against an existing
  contract (`docs/spec/task-briefs/v191-T3.md`) — a retry loop mirroring a
  pattern already in `agent.py`, its tests, one mutation entry and one
  `.env.example` line; no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.1 T3 (patch, no new spec file — precedent v1.5.1)
- **Owner of:** `rag.py`, `tests/test_v190_retrieval.py`,
  `tests/test_v191_rerank_contract.py`, `devtools/mutation_check.py`,
  `.env.example`, `docs/spec/task-briefs/v191-T3.md` (amendment block only —
  extended past this prompt's original assignment because the pinned test
  literal must match its own cited contract, not contradict it; see that
  file's "Amendment" section)
- **REQ ids:** none new — a patch to REQ-V190-RET-06/-07's existing contract

## Goal

T1 fixed the rerank contract, but gate 7 stayed red across three consecutive
runs, each failing a different subset of the ten answerable items. The
diagnosis in `docs/spec/task-briefs/v191-T3.md` is twofold. T1's recommended
route, `google/gemma-3-12b-it`, is served by a single OpenRouter upstream
that rate-limits a burst (measured 1/10 ok, 9x HTTP 429), while
`mistralai/mistral-small-24b-instruct-2501` survived the same burst 10/10 at
the best measured recall (9/10). The deeper defect is ours: `llm/base.py:401`
already classifies a 429 as `retryable=True`, and `rag.rerank()` caught
`LLMError` and returned `None` without ever reading that flag, so an
explicitly transient upstream error degraded silently to RRF order and took
the gate down with it. Implement exactly what the brief specifies: honour
`retryable` with a bounded retry (`_RERANK_MAX_ATTEMPTS = 3`, backoff 0.5s
then 1.5s as a module constant, `_RERANK_TIMEOUT_S` 30.0 → 10.0 so the worst
case per item stays near 32s), a warning per retry naming the attempt and the
error, no retry for a non-retryable error or an unparsable reply, the
`.env.example` route change, tests at both layers, and one new `v191-`
mutation entry that must be killed.

## Constraints

- Everything the brief states verbatim — it is the contract, not a starting
  point for re-derivation. The retry literals (3; 0.5, 1.5; 10.0) are pinned
  in tests as literals from the brief, never re-derived from the module.
- Commit only this task's files; every other modified path in `git status`
  belongs to T2 and is left exactly as found. No version bump, no tag, no
  push, never `--no-verify`.
- `.env` is never read, printed or committed — only `.env.example` changes.
- Do not write `docs/reports/report-v1.9.1.md`, `docs/llm-usage.md`,
  `README.md`, `AGENTS.md` or any version file; T2 documents this task.

## Acceptance

All seven gates from `AGENTS.md` — `uv sync --locked`,
`uv run --locked ruff check .`, `uv run --locked pytest`,
`uv run --locked python bot.py --selftest`,
`uv run --locked python bot.py --selftest-live`,
`uv run --locked python devtools/mutation_check.py`, and
`uv run --locked python devtools/rag_eval.py` — run verbatim, each exit 0;
gate 7 no longer flaking on a transient 429 is the point of this patch. The
new mutation entry `v191-rerank-retry-dropped` must be killed by the
retryable-then-success test.

## Stop

If gate 7 is still red after the fix, stop and report with the failure text
rather than adjusting the recall floor, the retry budget or the eval.

## Amendment — 2026-09-12

Two void gate 7 runs (concurrent with gate 6, which mutates `rag.py` on
disk) produced a false 429/quota signal against both the timeout value and
the recommended model. Three clean, sha-verified sequential re-runs showed
the model recommendation was correct all along, but `_RERANK_TIMEOUT_S`
itself was too tight (one item timing out on attempts 1 and 2, succeeding
only on attempt 3, on every passing run). Changed 10.0 -> 15.0 and added
success-path retry logging (attempt number, elapsed seconds); see
`docs/spec/task-briefs/v191-T3.md`'s own amendment section for the full
evidence. Gate 6 not required to rerun: neither changed line intersects any
existing mutation `find` string (checked by exact-string grep against the
diff before re-running gates).
