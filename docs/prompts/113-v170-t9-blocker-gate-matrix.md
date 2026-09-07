# Prompt 113 — spec-v1.7.0 T9: blocker, gate-matrix test vs. missing table

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T9 — blocked partway through, before commit
- **Owner of:** `docs/reports/report-v1.7.0.md` (Blocker section),
  `docs/prompts/113-v170-t9-blocker-gate-matrix.md` (new)
- **REQ ids:** REQ-V170-GATE-02, REQ-V170-GATE-03, REQ-V170-RPT-03 item 4
  (conflict identified, not resolved)

## Goal

Record a discovered conflict between REQ-V170-GATE-02 (the `mutation-v170`
gate MUST join the `pre-push` profile) / §14.1's literal instruction
(`tests/test_v15_standards.py:1726`'s matrix test MUST read
`docs/spec/spec-v1.7.0.md` instead of `spec-v1.6.0.md`) on one hand, and the
fact that `docs/spec/spec-v1.7.0.md` — as actually committed — contains no
`| gate | pre-commit | pre-push | full |` table for that test to parse, on
the other. Fixing it the only way that keeps the test's own logic within
§14.1's exhaustive amendment list (authoring the amended table into
`spec-v1.7.0.md`) collides with REQ-V170-RPT-03 item 4's separate MUST that
the spec's T0-recorded `sha256` stay unchanged through T14.

## Constraints

- No source, test, config or spec file is committed by this task — the
  blocker is reported, not resolved. `docs/reports/report-v1.7.0.md`'s new
  "Blocker at T9" section and this prompt are the only committed changes.
- The in-progress T9 work (the nine `v170-*` mutation entries, the
  corrected `T-V170-SUM-05` test input, `mutation-v170`'s and
  `mutation-all`'s re-measured timeouts, `AGENTS.md`'s mutation-count
  correction) is complete, verified and left **uncommitted** in the
  working tree — not reverted, not discarded, ready to resume the moment
  this is resolved.
- Per `AGENTS.md`'s go-protocol clause ("Where the spec and this file
  disagree, stop and ask"), the fix is not applied without the operator's
  explicit authorisation.

## Acceptance

- The report's Blocker section states the conflicting requirements, the
  exact failing test and its traceback, the two greps proving
  `spec-v1.7.0.md` carries no gate-matrix table, confirmation that the T0
  `sha256` still matches the file on disk today, and three costed
  resolution options with a recommendation.
- T0–T8's already-committed state is explicitly reconfirmed as unaffected.

## Stop

This whole task IS the stop: work halts here until the operator authorises
one of the three proposed resolutions or directs something else.
