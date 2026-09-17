# Prompt 205 — v1.10.1 T2: gate `env:` key, matrix and `lint-docs` repoint

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (§16.1: `delegate? yes`);
  general-purpose subagent, briefed by `docs/spec/task-briefs/v1101-T2.md`.
- **Harness:** Claude Code (background session, subagent)
- **Stage:** T2
- **Owner of:** `devtools/checks.py`, `config/quality_gates.yaml`,
  `tests/test_v15_standards.py:1772-1834`, `tests/test_v170_bench.py:316-331`,
  `tests/test_v1101_gates.py`
- **REQ ids:** REQ-V1101-GC-01, REQ-V1101-GATE-03, REQ-V1101-RPT-01
  (first sentence)

## Goal

An optional, validated `env:` map on command gates, passed through to the
gate's subprocess; pinned on `skylos` (`SKYLOS_GREP_BUDGET=180`). Repoint
the gate-matrix test at `spec-v1.10.1.md` and `lint-docs`'s `report_path`
at `report-v1.10.1.md`.

## Constraints

Touch only the files listed in the task brief. No new dependency, no
`v1101-*` mutation entry (T6's job). Gates 1–4 plus `doctor` and
`lint-docs` only — no gate 5/6/7/8. `--no-verify` never used.

## Acceptance

Gates 1–4 exit 0. `doctor` and `lint-docs` exit 0.
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` green against
`spec-v1.10.1.md`. New `tests/test_v1101_gates.py` covers every rejected
`env:` shape with its exact error message.

## Stop

Any contradiction between the brief and the actual current source (line
numbers may have shifted from T1's edits) — report back rather than
guessing.
