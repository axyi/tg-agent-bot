# Prompt 55 — spec-v1.5 T11: prompt format, `checks.py lint-docs`

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** REQ-V15-PRM-01..04 and REQ-V15-RPT-01/03 fully
  specify the lint's three prompt-file checks and the report's
  ledger-row check; the judgment calls were empirical (verifying the
  header check's exact-vs-subsequence semantics against a real file
  before trusting either design) and delegation (a 29-file historical
  backfill, briefed and then independently re-verified rather than
  trusted)
- **Harness:** Claude Code
- **Stage:** T11
- **Owner of:** `docs/prompts/TEMPLATE.md` (new), `devtools/checks.py`
  (`lint_docs` builtin handler, two prompt-file checkers, the
  report-ledger checker, `cmd_lint_docs` wired for real),
  `tests/test_v15_standards.py` (`T-V15-PRM-01..04`, `T-V15-RPT-01`),
  `docs/prompts/01-*.md` through `29-*.md` (header block backfilled,
  body content untouched — via a delegated subagent),
  `docs/reports/report-v1.5.md` (T11 section, RLM row, Deviations item
  4), `docs/prompts/55-v15-t11-lint-docs.md` (new)
- **REQ ids:** REQ-V15-PRM-01..04, REQ-V15-RPT-01, REQ-V15-RPT-03

## Goal

Implement `checks.py lint-docs`: the four-block/seven-bullet prompt
format lint plus the report's ledger-row structural check, add
`docs/prompts/TEMPLATE.md` as valid lint input, and bring every
existing prompt file's header into compliance with REQ-V15-PRM-04's
"applies to all prompt files, historical ones included" — since T18's
own acceptance bullet requires `checks.py lint-docs` green.

## Constraints

- No policy value (the glob, the exemption list, the report path, the
  ledger header) is a Python literal — read from
  `config["gates"]["lint-docs"]` (REQ-V15-GATE-02, carried over).
- The `exempt_files` check is a literal filename comparison, never a
  numeric one, so it cannot silently grow.
- Historical prompt files' body content is never edited — only the
  header block, and only to add the seven required bullets, sourced
  from the file's own text or `git log`, never fabricated.
- The 46+-file sweep is delegated, summary only, per this task's own
  reading-map instruction.

## Acceptance

- `T-V15-PRM-01` through `-04` and `T-V15-RPT-01` green.
- `docs/prompts/TEMPLATE.md` passes the lint directly.
- Every prompt file numbered ≥ 43 passes the lint (T11's own scope).
- `checks.py lint-docs` reports zero header-check failures across all
  54 prompt files after the backfill — verified independently, not
  merely trusted from the delegated agent's own report.
- `uv run --locked ruff check .` and the full `uv run --locked pytest`
  suite both exit 0.

## Stop

If a historical file's required field value cannot be sourced from
its own text or from git history, write `not recorded` rather than
guess — and if the header check's exact-vs-subsequence semantics
can't be settled against a real example (a file with a legitimate
extra bullet), stop and record which reading was chosen and why
rather than picking silently.
