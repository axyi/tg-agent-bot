# Prompt 230 — v1.10.4 T2: land the five `v1103-*` mutation entries

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (test-first landing of
  a byte-exact stash/Appendix-D patch plus per-entry isolation proofs);
  general-purpose subagent, briefed by file per §10.1/EC-03.
- **Harness:** Claude Code (background session, delegated subagent)
- **Stage:** T2
- **Owner of:** `devtools/mutation_check.py` (the five `v1103-*`
  entries), `config/quality_gates.yaml` (`mutation-v1103` gate,
  `mutation-subsets`, the `mutation-all` comment), `tests/test_v1104_gates.py`
  (extended), `tests/test_v1100_gates.py` (row 2b's appended group
  assertion), `docs/reports/report-v1.10.4.md` (`## T2` section)
- **REQ ids:** REQ-V1104-MUT-01, REQ-V1104-MUT-02

## Goal

Land the five `v1103-*` mutation entries the v1.10.3 run authored and
verified but never committed (preserved in `stash@{0}`), test-first:
prove the pre-apply tree fails/passes as expected, apply the stash (or
Appendix D's byte-exact fallback), verify the post-image, re-verify each
entry's isolation proof under exact pytest node ids. Full detail in
`docs/spec/task-briefs/v1104-T2.md`.

## Constraints

Strict order: tests and their pre-apply record **before** the apply,
never after. Stash is read-only (`show -p`, `rev-parse`) — never `pop`,
`apply` (bare), or `drop`. Isolation proofs use exact node ids, never
`-k`. No new mutation id (NG-02). Gates 1-4 only this task — gate 6
(the mutation CLI itself) is T4's, never run here. `--no-verify` never
used.

## Acceptance

Six T2 tests green after apply (three were red pre-apply, three
structurally green, recorded as such); five per-entry isolation proofs
recorded with exact node ids and selected counts; post-image hash
`d09909d…` confirmed; `len(mc.MUTATIONS) == 144`; full pytest green;
gates 1-4 green; `doctor` green.

## Stop

A `git apply --check` failure on the post-T1 tree despite the stash id
matching (ERR-01 row 1b) is a construction defect — never retry the same
patch blindly; repair only by byte-exact reconstruction of Appendix D's
post-image hunks, spending one repair cycle, and report back if that
also fails. A post-image mismatch after applying (ERR-01 row 2) or a
collection miss/extra selected node in an isolation proof (ERR-01 row 3)
is likewise a stop-and-disclose, not something to paper over.
