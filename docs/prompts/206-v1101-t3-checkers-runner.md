# Prompt 206 — v1.10.1 T3: the checkers (RT-01…05) and the gate-8 runner

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (§16.1: `delegate? yes`);
  general-purpose subagent, briefed by `docs/spec/task-briefs/v1101-T3.md`
  (the densest brief of this release — exact regexes and exact current
  source pre-extracted by the orchestrator).
- **Harness:** Claude Code (background session, subagent)
- **Stage:** T3
- **Owner of:** `devtools/agent_eval.py`, `evals/agent/red_team.json`,
  `tests/test_v1100_red_team.py` (four named sites only),
  `tests/test_v1101_red_team.py`, `tests/test_v1101_runner.py`,
  `tests/test_v1101_embeddings.py` (EMB-05B extension only)
- **REQ ids:** REQ-V1101-RT-01, REQ-V1101-RT-02, REQ-V1101-RT-03,
  REQ-V1101-RT-04, REQ-V1101-RT-05, REQ-V1101-RUN-01, REQ-V1101-SEC-01

## Goal

Clause (c) becomes echo/negation-aware and clause-bounded (leak-shape
regex for env-key names, adversative/coordination clause splitting, a
shared negation guard); `INJ_MARKERS` and `HAL_MARKERS` both grow from
eight to fifteen; a new clause (e) fails an injection case that called
`exec`/`fetch` under attack; `check_hallucination` drops its entity
conjunction. The gate-8 runner gets a real `Searcher` over an empty temp
index (RAG's tool surface now matches production's) and records tool
calls per case. Entirely offline.

## Constraints

Touch only the files listed in the task brief. Entirely offline — gates
1–4 only, never 5/6/7/8. No new `v1101-*` mutation entry (T6's job). Both
dataset files frozen by `sha256`, recorded in the commit body.
`--no-verify` never used.

## Acceptance

Gates 1–4 exit 0. `tests/test_v1100_runner.py` and every
`tests/test_v1100_red_team.py` test outside the four named amendment
sites stay green unamended. The five v1.10.0-recorded checker misses
(INJ-02, INJ-03, INJ-04's two failure modes, HAL-01, HAL-02) each resolve
exactly as the brief's §11 and "Tests to write" sections describe.

## Stop

Any real contradiction between the brief and the actual current source
(not just a line-number drift — those are expected and noted in the
brief) — report back rather than guessing. Judgment calls the brief left
open (an invented `any_of` regex per INJ case, the per-turn-vs-per-case
`Searcher` construction) are fine to make, but must be flagged in the
final report for orchestrator review.
