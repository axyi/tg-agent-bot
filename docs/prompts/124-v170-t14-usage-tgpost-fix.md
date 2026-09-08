# Prompt 124 — spec-v1.7.0: post-T14 documentation-only correction

- **Date:** 2026-09-08
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** post-T14 (REQ-V170-ACC-03 exception 1)
- **Owner of:** `docs/llm-usage.md`, `docs/reports/tg-post-v1.7.0.md`,
  `docs/reports/report-v1.7.0.md`,
  `docs/prompts/124-v170-t14-usage-tgpost-fix.md` (new)
- **REQ ids:** REQ-V170-ACC-03 (exception 1), REQ-V170-RPT-04

## Goal

Close two gaps an advisor review surfaced right after T14's evidence-only
commit landed: `docs/llm-usage.md` had no row for prompt 123/T14's own
work, and `docs/reports/tg-post-v1.7.0.md` still quoted T13's stale commit
count (20) and prompt range (103–122) instead of T14's (23, 103–123).
Also tightens the Appendix B E10 row's evidence from "checked by
inspection" to the actual mechanical check that backs it
(`gitleaks-tree`, tree-wide, 0 findings every gate run this release).

## Constraints

- This is REQ-V170-ACC-03's exception 1: "a documentation-only correction
  of the evidence the run produced." No source, test or config file
  touched.
- Does not reopen or re-litigate T14's verdict, gate results or the
  no-tag decision — those stand as recorded.
- Re-verifies only what exception 1 requires: `commit-msg` checks, the
  `pre-commit` profile, `lint-docs` and `gitleaks-tree` — not the six
  verbatim gates or `full --since <base>` again, since nothing
  source-relevant changed.

## Acceptance

- `uv run --locked python devtools/checks.py lint-docs` exits 0.
- `uv run --locked python devtools/checks.py run --profile pre-commit`
  exits 0.
- `docs/reports/tg-post-v1.7.0.md` reads 23 commits / prompts 103–123,
  still under 1500 characters by `wc -m`.
- `docs/llm-usage.md` carries a row for prompt 123.

## Stop

None.
