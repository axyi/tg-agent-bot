# Prompt 56 — spec-v1.5 T12: profile matrix, wall-clock, mutations

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** §15.4's four mutation targets and REQ-V15-GATE-04's
  `--select` semantics are fully specified; the judgment calls were
  empirical (locating the exact `find` strings, verifying each mutation
  is actually killed) and two live bugs found only by running
  `checks.py run --profile pre-push` against the real repository for
  the wall-clock measurement — no design decision, a live debugging
  session
- **Harness:** Claude Code
- **Stage:** T12
- **Owner of:** `devtools/mutation_check.py` (`--select`, four `v15-*`
  entries), `devtools/checks.py` (`scan_root` fix for
  `execute_command_gate`'s path normalisation), `.gitleaks.toml`
  (unanchored allowlist `paths` patterns), `tests/test_v15_standards.py`
  (`T-V15-GATE-04`, `T-V15-GATE-05`, the tracked-tree normalisation
  regression), `docs/reports/report-v1.5.md` (T12 section, RLM row),
  `docs/prompts/56-v15-t12-profiles-mutations.md` (new)
- **REQ ids:** REQ-V15-TST-01, REQ-V15-TST-02, REQ-V15-GATE-04,
  REQ-V15-GATE-11, REQ-V15-HOOK-04

## Goal

Add the four `v15-*` mutation entries and `--select <prefix>` to
`devtools/mutation_check.py`, prove `T-V15-GATE-04`'s profile-matrix
agreement between the spec's §14 table and `quality_gates.yaml`, and
measure `pre-push`'s wall-clock three times against the real
repository, recording the median.

## Constraints

- The byte-exact anchor line in `main()` (the pre-existing `args.only`
  guard) must survive unchanged; `--select`'s check is a separate,
  adjacent branch.
- Every mutation's `find` string must match its target file exactly
  once (REQ-V15-TST-02).
- The wall-clock measurement is observational only — no gate is moved,
  demoted or removed to hit the 180 s budget, regardless of what the
  three runs show.
- A real, live run against the actual repository is required for the
  measurement — not a synthetic estimate.

## Acceptance

- `--select v15-` runs exactly the four new mutations, all `killed`;
  `mutation_check.py`'s own bytes verified unchanged afterward.
- `--select nope-` exits non-zero naming the prefix; `--only` and
  `--select` together are refused.
- `T-V15-GATE-04` and `T-V15-GATE-05` green.
- Three real `checks.py run --profile pre-push` runs against this
  repository, all twelve gates green on every run, median wall-clock
  recorded as a number.
- `uv run --locked ruff check .` and the full `uv run --locked pytest`
  suite both exit 0.

## Stop

If a wall-clock run surfaces a gate that cannot pass against the real
repository, stop and fix the actual defect before re-measuring — a
median computed from runs that silently worked around a real bug is
not evidence of anything.
