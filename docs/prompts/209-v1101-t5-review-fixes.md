# Prompt 209 — v1.10.1 T5: closing the clean-context review's findings

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated fix task (§16.1: `delegate? yes` — T5 "puts
  the review in the `code-reviewer` subagent's own context, and any fix
  it returns writes source"); general-purpose subagent, briefed by
  `docs/spec/task-briefs/v1101-T5.md`.
- **Harness:** Claude Code (background session, subagent)
- **Stage:** T5
- **Owner of:** `devtools/agent_eval.py` (line 133), `evals/agent/red_team.json`
  (INJ-02's `any_of`), `tests/test_v1100_red_team.py`, `tests/
  test_v1101_red_team.py`, `tests/test_v190_tool.py`, `tests/
  test_v1101_prompt.py` (new), `tests/test_v1101_runner.py`, `tests/
  test_v1101_gates.py`
- **REQ ids:** REQ-V1101-RT-02, REQ-V1101-PRM-01, REQ-V1101-PRM-02,
  REQ-V1101-GC-01, REQ-V1101-REV-01

## Goal

Close REV-01's review findings from `docs/prompts/208-v1101-t5-review.md`'s
review: the 🔴 `INJ02_ANY_OF` miss (a real gate-8 false-miss risk) and four
🟡 should-fix items (a misplaced/mislabeled test module, two mislabeled
ERR-01 row tests, one untested GC-06 case).

## Constraints

Touch only the files listed in the task brief, only at the named sites.
Gates 1-4 only, offline. `--no-verify` never used. Re-freeze
`evals/agent/red_team.json`'s `sha256` after the one authorized edit
(INJ-02's `any_of`) and report the new hash.

## Acceptance

Gates 1-4 exit 0. A new test directly pins `ae.INJ02_ANY_OF` against the
spec's seven-alternative literal. `tests/test_v1101_prompt.py` exists and
covers PRM-01's exact-once/old-line-absent assertions plus PRM-03's
exact-736-char assertion. The two `test_v1101_runner.py` tests no longer
claim to be `ERR-01` rows 7/8. `T-V1101-GC-06`'s NUL-in-key case is
tested.

## Stop

Any of the four fix groups revealing a deeper contradiction than the
review described — report back rather than improvising beyond this
brief's scope.
