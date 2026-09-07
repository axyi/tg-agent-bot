# Prompt 114 — spec-v1.7.0 T9: mutation entries and gate config

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T9
- **Owner of:** `devtools/mutation_check.py` (nine new entries),
  `config/quality_gates.yaml` (`mutation-v170` gate, `pre-push` profile,
  `mutation-all` timeout), `AGENTS.md` (mutation-entry count),
  `tests/test_v170_reasoning.py` (one test-input fix),
  `tests/test_v15_standards.py` (`_GATE_MATRIX_LABEL_TO_NAME`, the matrix
  test's spec-file pointer), `docs/spec/spec-v1.7.0.md` (the amended
  gate-matrix table, per the blocker's authorized resolution),
  `docs/reports/report-v1.7.0.md` (T9 section, both spec `sha256`
  values), `docs/prompts/114-v170-t9-mutation-entries.md` (new)
- **REQ ids:** REQ-V170-TST-03, REQ-V170-TST-04, REQ-V170-GATE-02,
  REQ-V170-GATE-03, REQ-V170-RPT-03 item 4 (disclosed deviation), REQ-V170-RPT-04

## Goal

Land the nine `v170-*` mutation entries section 14.4 specifies, wire the
new `mutation-v170` gate into the `pre-push` profile with a freshly
measured timeout, re-measure `mutation-all`'s timeout at 92 entries, and
resolve the T9 blocker (`docs/prompts/113-v170-t9-blocker-gate-matrix.md`)
per the operator's authorization: author the amended gate-matrix table
into `spec-v1.7.0.md` itself, disclosing the resulting spec `sha256`
change against REQ-V170-RPT-03 item 4.

## Constraints

- Every mutation entry's `find` string is verified byte-exact against its
  real target line before being added (`sed -n ... | cat -A`), and
  `mutation_check.py --list` is run and recorded before the gate is
  trusted (REQ-V170-TST-04).
- Both timeouts are **measured**, not guessed: `mutation-v170` from a real
  `time`-wrapped `--select v170-` run, `mutation-all` from a real
  `time`-wrapped full run at the new 92-entry count.
- The spec-file edit is scoped to exactly what the operator authorized:
  the restated gate-matrix table is byte-identical to
  `spec-v1.6.0.md:2146-2167` except the one new `mutation-v170` row.
  Nothing else in `spec-v1.7.0.md` changes.
- One prompt -> one commit, referencing this file.

## Acceptance

- `uv run --locked python devtools/mutation_check.py --select v170-` exits
  0 (9/9 killed).
- `uv run --locked python devtools/mutation_check.py` exits 0 (92/92
  killed, 0 survived/errored/drifted).
- `tests/test_v15_standards.py -k gate_04` passes against the amended
  `spec-v1.7.0.md`.
- Full suite green: `uv run --locked pytest` (1133 collected, 2 skipped).
- `uv run --locked ruff check .` exits 0.
- `uv run --locked python bot.py --selftest` and `--selftest-live` both
  exit 0.
- `uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json`
  exits 0.
- `uv run --locked python devtools/checks.py lint-docs` exits 0.

## Stop

Two things happened mid-task, both resolved before this commit:

1. **Blocker** (`docs/prompts/113-v170-t9-blocker-gate-matrix.md`,
   committed separately): wiring `mutation-v170` into `pre-push` broke
   `tests/test_v15_standards.py::test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`,
   and section 14.1's one authorized repair (point the test's spec-file
   read at `spec-v1.7.0.md`) could not succeed because that file carried
   no gate-matrix table at all. The operator authorized resolution option
   1: author the amended table into `spec-v1.7.0.md`, accepting a changed
   spec `sha256` disclosed against REQ-V170-RPT-03 item 4 (T0:
   `d6ad4a4a05859883f6f6cde4466512b2fa980767df6b9ab82d778a0ae32c263a` ->
   post-T9: `16fa1361122c11e14ab37bbb45abfb855efef7c8fc715247a4d741fc3952f7c8`).
2. **Self-caught survivor** (fixed, not stopped on): `v170-summary-floor-check-removed`
   survived its first `--select v170-` run because the killer test's
   original input was already caught by the pre-existing
   `_check_timeout_budget` check for an unrelated reason. Fixed by
   choosing an input that discriminates the two checks — see the report's
   T9 section for the arithmetic.
