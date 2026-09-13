# Prompt 198 — v1.10.0 T6: gate 8 registration and documentation

- **Date:** 2026-09-14
- **Executor model:** claude-sonnet-5 (delegated subagent, general-purpose)
- **Model reason:** config/doc registration task with an exact worked
  target (the spec's own gate matrix table); no reasoning-tier need.
- **Harness:** Claude Code (background session, delegated via Agent tool)
- **Stage:** T6
- **Owner of:** `config/quality_gates.yaml`, `tests/test_v15_standards.py`,
  `tests/test_v170_bench.py`, `AGENTS.md`, `README.md`,
  `tests/test_v1100_gates.py`
- **REQ ids:** REQ-V1100-GATE-03, REQ-V1100-EVAL-01, REQ-V1100-RPT-01

## Goal

Register `agent-eval` (gate 8) in `config/quality_gates.yaml` with T0's
measured 8200s timeout, repoint the gate-matrix test and `lint-docs` at
this release, and land the eight-gate blocks in `AGENTS.md`/`README.md`
plus a placeholder numbers section, exactly as
`docs/spec/task-briefs/v1100-T6.md` specifies.

## Constraints

Touch only the files the brief names. Gates 1-4 plus `doctor` and
`lint-docs`. Never 5, 6, 7, 8, never `--profile full`.

## Acceptance

Gates 1-4 exit 0; `doctor` and `lint-docs` exit 0; the gate-matrix test
passes against the repointed spec file; `T-V1100-EVAL-01…03` pass.

## Stop

If adding `mutation-v1100` to `mutation-subsets` before T7 defines the
actual gate entry breaks `_validate_profiles` or `doctor`, stop and report
rather than defining the gate entry yourself (that's T7's job, with its
own re-measured timeout).
