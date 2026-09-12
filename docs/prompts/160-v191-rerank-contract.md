# Prompt 160 — v1.9.1 T1: make the rerank contract enforceable and fast

- **Date:** 2026-09-12
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded, well-specified patch task against an existing
  contract (`docs/spec/task-briefs/v191-T1.md`) — implementation, tests and
  gate execution, no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.1 T1 (patch, no new spec file — precedent v1.5.1)
- **Owner of:** `llm/base.py`, `llm/lmstudio.py`, `llm/openrouter.py`,
  `llm/failover.py`, `llm/__init__.py`, `rag.py`, `config.py`, `bot.py`,
  `devtools/rag_eval.py`, `devtools/mutation_check.py`,
  `config/quality_gates.yaml`, `.env.example`, `README.md`, `AGENTS.md`,
  `tests/fakes.py`, `tests/test_llm.py`, `tests/test_failover.py`,
  `tests/test_routing.py`, `tests/test_v190_retrieval.py`,
  `tests/test_v191_rerank_contract.py`,
  `docs/reports/report-v1.9.1.md`
- **REQ ids:** none new — a patch to REQ-V190-RET-06/-07's existing contract

## Goal

Gate 7 has been red since v1.9.0 T8, shipped under an operator waiver: the
production rerank model's measured median latency (196.9s) is past
`_RERANK_TIMEOUT_S` (120.0), and ten answerable items times that median
blows through `rag-eval`'s own 600s gate timeout. The brief's own measurement
table shows a JSON-schema `response_format` plus a small, non-thinking
routed model (`google/gemma-3-12b-it` via OpenRouter) passes 10/10 at a
0.83s median. Implement exactly what `docs/spec/task-briefs/v191-T1.md`
specifies: `response_format` passthrough in the LLM client layer, the
rerank call requesting the schema, `_RERANK_MAX_TOKENS`/`_RERANK_TIMEOUT_S`
brought down to measured reality, `LLM_RERANK_MODEL` routing (mirroring
`LLM_SUMMARY_MODEL`'s existing shape), gate 7's own timeout re-measured at
2x the real wall clock, docs, and two new mutation entries.

## Constraints

- Everything the brief states verbatim — it is the contract, not a
  starting point for re-derivation.
- No version bump (T2's job). No touching `evals/rag/questions.json` or the
  corpus. No softening `docs/reports/report-v1.9.0.md`'s record of gate 7
  as shipped red. `.env` is never read, printed or committed.
- Never `--no-verify`.

## Acceptance

All seven gates from `AGENTS.md` — `uv sync --locked`,
`uv run --locked ruff check .`, `uv run --locked pytest`,
`uv run --locked python bot.py --selftest`,
`uv run --locked python bot.py --selftest-live`,
`uv run --locked python devtools/mutation_check.py`, and
`uv run --locked python devtools/rag_eval.py` — run verbatim, each exit 0;
gate 7 green is the point of this patch. Evidence recorded in
`docs/reports/report-v1.9.1.md`.

## Stop

If gate 7 is still red after the fix, stop and report with the failure
text rather than adjusting the recall floor or the eval.
