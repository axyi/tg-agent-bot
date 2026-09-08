# Prompt 120 — spec-v1.7.0: T12 report write-up and full gate re-verification

- **Date:** 2026-09-08
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T12 (report write-up, after the selection commit landed)
- **Owner of:** `docs/reports/report-v1.7.0.md` (T12 section, Status line),
  `docs/prompts/120-v170-t12-report-writeup.md` (new)
- **REQ ids:** REQ-V170-RPT-03, REQ-V170-BEN-07

## Goal

Run the full gate sequence after T12's three commits land, verify
`checks.py replay` across the whole `<base>..HEAD` range, and write T12's
report section covering the two discovered-and-resolved blockers, the
transient 1Password/git-signing outage, and the gate results.

## Constraints

- This file is deliberately **not** named to match
  `docs/prompts/\d+-v170-t12-[\w.-]*\.md`, for the same reason as prompts
  118 and 119: citing it in this commit's body must not create a second
  match for `_acc03_find_selection_commit` alongside the real selection
  commit (`17578b1`, citing prompt 117).
- Documentation-only commit: no source, test or config file touched.

## Acceptance

- `checks.py run --profile full --since <base>` exits 0, 15/15 gates PASS.
- `checks.py replay --range <base>..<tip>` exits 0, every commit PASS.
- `lint-docs` passes against the updated report.

## Stop

None. One external interruption handled without a full stop: the first
full-profile attempt failed its `pytest` gate because 1Password's
SSH-agent-based git-commit signing was temporarily down (confirmed
reproducible with a plain `git init && git commit` outside the repo,
unrelated to any T12 change) — no workaround applied, the operator
restarted the agent, and the run was re-executed clean.
