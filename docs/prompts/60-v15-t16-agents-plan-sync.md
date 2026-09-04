# Prompt 60 — spec-v1.5 T16: `AGENTS.md` / `docs/plan.md` sync

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** REQ-V15-RPT-05 names the exact sections and files;
  the judgment calls were identifying every real staleness (an
  under-documented commit-type/branch-prefix set, a missing new-gates
  subsection, a genuine version-number naming collision in
  `docs/plan.md`) and taking a delegated review seriously enough to
  fix what it found, including waiting past the first time budget
  rather than skip it
- **Harness:** Claude Code
- **Stage:** T16
- **Owner of:** `AGENTS.md` (Stack, Commit format, Branch strategy,
  Gates, new "Local quality gates" subsection, Reporting),
  `docs/plan.md` (v1.5 Status-table row and narrative section, the
  renamed token-economy-candidates section, the Acceptance-gates
  mutation count), `docs/reports/report-v1.5.md` (T16 section, RLM
  row), `docs/prompts/60-v15-t16-agents-plan-sync.md` (new)
- **REQ ids:** REQ-V15-RPT-05

## Goal

Bring `AGENTS.md`'s Stack, Commit format, Branch strategy, Gates and
Reporting sections, and `docs/plan.md`, true to the repository's
current state after T0–T15.

## Constraints

- The six verbatim gate commands in `AGENTS.md` (REQ-V15-GATE-09) do
  not change one character — only the surrounding prose.
- `docs/plan.md`'s v1.5 entry must not claim completion it hasn't
  reached — mark it in progress, with the task count landed so far.
- The diff is delegated for review even though both files are under
  the RLM size threshold, per this task's own explicit instruction.

## Acceptance

- Stack, gate list, Commit format, Branch strategy and Reporting all
  match reality — verified against the live repository, not merely
  asserted (`ALLOWED_TYPES`, the `branch-name` pattern, `.githooks/`
  contents, the mutation count, `checks.py`'s subcommands, the test
  count).
- `docs/plan.md` records the v1.5 milestone and the current test count.
- A delegated review of the diff either confirms it or the findings
  are fixed and re-verified.
- `uv run --locked ruff check .` and the full `uv run --locked pytest`
  suite both exit 0.

## Stop

If the delegated review cannot be trusted to return in a reasonable
time, do not skip verification — fall back to checking the same
concrete claims directly rather than committing unverified prose. If
the review does return afterward with real findings, fix them even if
that means revising an already-drafted report section.
