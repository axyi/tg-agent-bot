# Prompt 121 — spec-v1.7.0: correct T12's report section

- **Date:** 2026-09-08
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T12 (report correction)
- **Owner of:** `docs/reports/report-v1.7.0.md`,
  `docs/prompts/121-v170-report-correction.md` (new)
- **REQ ids:** REQ-V170-RPT-03

## Goal

Fix two errors in T12's just-written report section: the wrong prompt
number attributed to `de0586f` (116, should be 118), and disclose that
prompt 120's own filename accidentally matches
`docs/prompts/\d+-v170-t12-[\w.-]*\.md` despite its Constraints section
saying it should not — `62cc364` citing it makes
`_acc03_find_selection_commit()` see two matches and return `None`
(ambiguous) from here on, permanently, since commit messages are never
amended.

## Constraints

- This filename does not match `docs/prompts/\d+-v170-t12-[\w.-]*\.md`
  either (checked before writing it).
- Documentation-only; no source, test or config file touched.
- Does not attempt to "fix" the ambiguity itself — that would require
  rewriting git history, forbidden by this project's own rules. Disclosure
  only.

## Acceptance

- `uv run --locked python devtools/checks.py lint-docs` exits 0.
- `docs/reports/report-v1.7.0.md` accurately names which prompt each T12
  commit cites.

## Stop

None.
