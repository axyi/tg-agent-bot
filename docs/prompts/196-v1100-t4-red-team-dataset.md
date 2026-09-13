# Prompt 196 — v1.10.0 T4: the red-team dataset and the checkers

- **Date:** 2026-09-14
- **Executor model:** claude-sonnet-5 (delegated subagent, general-purpose)
- **Model reason:** precision-critical dataset authoring plus pure-function
  checker logic; default model is sufficient, no reasoning-tier need since
  every rule is deterministic and spelled out.
- **Harness:** Claude Code (background session, delegated via Agent tool)
- **Stage:** T4
- **Owner of:** `devtools/agent_eval.py` (new, checkers/validation only),
  `evals/agent/red_team.json`, `evals/agent/judge_questions.json`,
  `tests/test_v1100_red_team.py`
- **REQ ids:** REQ-V1100-RT-01, -02, -03, -04, -06, REQ-V1100-RUN-03,
  REQ-V1100-JDG-01

## Goal

Build the frozen red-team dataset (12 cases), the judge-questions dataset
(5 questions), the three pure checkers (`check_injection`,
`check_hallucination`, `check_memory_recall`/`check_memory_reset`), and
`validate_datasets()`, exactly as `docs/spec/task-briefs/v1100-T4.md`
specifies — read the brief and the cited spec sections in full.

## Constraints

New files only (see brief). Gates 1-4 only. No live calls anywhere in this
task — `devtools/agent_eval.py` must import cleanly with no runner yet.
`--no-verify` never used.

## Acceptance

`validate_datasets()` passes on the real committed files with zero
exceptions; ≥ 30 parametrised test items in `tests/test_v1100_red_team.py`;
every one of RT-03's worked examples in the brief verifies to the stated
verdict; gates 1-4 exit 0; both dataset `sha256`s recorded in the report
back.

## Stop

If a canonical text or id-mapping constraint in the brief seems impossible
to satisfy simultaneously with the checker rules, stop and report the
contradiction rather than silently relaxing either side.
