# Prompt 247 — v1.11.0 T7 Phase B: isolation verification of the 8 entries

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only orchestration (T7's own §14.1
  exemption: *commands only* for the gate/verification run) — no
  delegation.
- **Harness:** Claude Code (background session, orchestrator)
- **Stage:** T7 (Phase B)
- **Owner of:** `devtools/mutation_check.py` (`why` fields only)
- **REQ ids:** REQ-V1110-MUT-01

## Goal

Run each of the eight `v1110-*` mutation entries in isolation
(`--only <id>`) against the clean tree committed at `33729eb`, confirm
each is killed by its expected test(s) (entry 7 confirmed by both named
killers — `T-V1110-CBQ-05` via `--only`, `T-V1110-MOD-08` via a manual
hand-applied mutate/run/revert since the tool's `--only` stops at the
first failure across the whole run), then run `--select v1110-` once for
all eight together. Replace each entry's placeholder `why` text ("NOT YET
empirically verified...") with the actual observed failure.

## Constraints

`bot.py`/`storage.py`/`documents.py` must be byte-identical to `HEAD`
after every run (the tool's own revert, verified via `git status
--porcelain` after each). Entry 7's manual MOD-08 check used the same
mutate → run one test → restore-from-backup → `git diff --stat` empty
discipline established at the T5 lock-assertion bite-check (prompt 243).
Only the `why` string values changed — no `find`/`replace` pair was
altered, re-confirmed by re-running the uniqueness check after editing.

## Acceptance

All 8 entries: `--only <id>` reports 1/1 killed, tree clean after. Entry
7 additionally confirmed by `T-V1110-MOD-08` via the manual check.
`--select v1110-` reports 8/8 killed, 0 survived/errored/drifted (real
26.4s). `T-V1110-MUT-01` still green after the `why`-field edits. `ruff
check .` clean, `ruff format --check` clean (one line-length fix applied
by hand). Gates 1-4 unaffected (no source file touched).

## Stop

Not applicable — every entry killed as expected; no survivor, no error,
no drift to report.
