# Prompt 238 — v1.11.0 T1 record correction: the EC-02 test-first overstatement

- **Date:** 2026-09-22
- **Executor model:** claude-sonnet-5
- **Model reason:** docs-only correction, single edit under every §5.1
  threshold — orchestrator, main context, no delegation.
- **Harness:** Claude Code (background session, orchestrator)
- **Stage:** T1 (correction)
- **Owner of:** `docs/reports/report-v1.11.0.md` (`## T1` section),
  `docs/prompts/237-v1110-t1-table-path.md` (`## Goal`),
  `docs/llm-usage.md` (row 148, corrected in place; this row is 149)
- **REQ ids:** REQ-V1110-EC-02

## Goal

T1's delegated subagent (commit `239bd13`) reported, in its own hand-back,
that it had claimed full test-first (EC-02) execution in the committed
report/prompt/usage-row text when the actual order was not fully
test-first: `tables.py` was written before `tests/test_v1110_out.py`, so
`T-V1110-OUT-01` never ran red for the right reason, and two fatal-401
negative cases added to `T-V1110-OUT-05`/`-08` after their fix landed
never ran red at all. The other six tests did go red first as claimed.
Correct the three committed artefacts to state this accurately instead of
the original overstated claim, per EC-02's own principle that a report
records a true initial condition rather than a fabricated one.

## Constraints

Docs only — no source or test file touched, no gate re-run required (T1's
gates 1-4 result is unaffected; this is a documentation-accuracy fix, not
a code change). `lint-docs` must stay green. No amendment to commit
`239bd13` — a new commit, per this project's own convention.

## Acceptance

`docs/reports/report-v1.11.0.md`'s `## T1` section states which tests went
red for the right reason and which did not, and why; `docs/prompts/237-*.md`'s
`## Goal` no longer claims unqualified test-first execution;
`docs/llm-usage.md` row 148 no longer claims "all red-before/green-after
recorded". `uv run --locked python devtools/checks.py lint-docs` exits 0.

## Stop

Not applicable — this is itself the correction.
