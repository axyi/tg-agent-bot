# Prompt 128 — v1.8.0 T1: AGENTS.md context discipline

- **Date:** 2026-09-09
- **Executor model:** claude-sonnet-5
- **Model reason:** `docs/handoff-v1.8.0.md` §Models: sonnet-5 executed
  v1.5, v1.6.0 and v1.7.0 end to end in this repository; T1 is prose-only
  and makes no live model call.
- **Harness:** Claude Code
- **Stage:** T1
- **Owner of:** `AGENTS.md`, `tests/test_v180_agents.py`,
  `docs/prompts/128-v180-t1-context-discipline.md`
- **REQ ids:** REQ-V180-AGT-01, REQ-V180-AGT-02, REQ-V180-AGT-03 (T1's
  non-count half), REQ-V180-AGT-04

## Goal

Execute `docs/spec/task-briefs/v180-T1.md` (spec-v1.8.0 §3): give
`AGENTS.md` the `## Context discipline` section it has lacked since v1.7.0
exposed the gap, append the ownership-zone rule to `## Branch strategy`,
correct the `dashboard_server.py` project-layout line for the conversations
routes it will gain, and review (without rewriting) the project's three
other prompt files — `skills/host-info.md`, `skills/weather.md`, `CLAUDE.md`.

## Constraints

Test-first: `tests/test_v180_agents.py` was written and confirmed red
before `AGENTS.md` changed. No count-bearing `AGENTS.md` line (pytest count,
mutation-entry count, the `--select` example) is touched — that is T7's,
after T6 lands the real numbers. No existing `## Branch strategy` bullet is
deleted or reworded; the ownership-zone rule is appended only. The four
exemptions in `## Context discipline` are verbatim in the words
REQ-V180-AGT-01 item 3 gives. No file outside this repository is read or
written (EC-01); `templates/project/AGENTS.md`, cited by the spec as the
adaptation source, sits above the repository root and was not searched for.
Only `ruff check .` and `pytest tests/test_v180_agents.py` (plus the full
suite, time-budget permitting) run here — not the six-gate sequence, which
is T8/T10's job.

## Acceptance

`uv run --locked pytest tests/test_v180_agents.py` exits 0 (11 tests,
red before the `AGENTS.md` edit, green after). `uv run --locked ruff check
.` exits 0. `git diff -U0 -- AGENTS.md` shows exactly three hunks: the
`dashboard_server.py` line, the new `## Context discipline` section, and
the appended ownership-zone bullet — nothing else moved.

## Stop

Stop and report instead of continuing if the four exemptions cannot be
stated verbatim without contradicting the existing `AGENTS.md` voice, if a
count-bearing line turns out to need touching to make the section
consistent, or if either `skills/host-info.md` or `skills/weather.md` turns
out to need a substantive change this task's scope does not cover.
