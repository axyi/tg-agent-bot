# Prompt 119 — spec-v1.7.0: sync uv.lock to T12's version bump

- **Date:** 2026-09-08
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T12 (mechanical follow-up)
- **Owner of:** `uv.lock`
- **REQ ids:** none directly; keeps gate 1 (`uv sync --locked`) green after
  REQ-V170-VER-01's version bump

## Goal

Regenerate `uv.lock` so its recorded project version matches
`pyproject.toml`'s `1.7.0` (T12, commit `17578b1`). `uv sync --locked`
refuses to proceed with a stale lockfile, and `uv.lock` is not in
REQ-V170-REV-01 item 8's five-file selection-commit allowlist, so this is
a separate, immediately-following commit rather than part of T12 itself
(documented in `docs/prompts/117-v170-t12-selection-commit.md`'s own Stop
section).

## Constraints

- `uv lock` only — no dependency added, removed or upgraded; the resolution
  is otherwise byte-identical (`git diff uv.lock` touches only the version
  field).
- Does not cite a `docs/prompts/\d+-v170-t12-[\w.-]*\.md` path in this
  commit's body, for the same ambiguity reason as prompt 118.

## Acceptance

- `git diff --stat uv.lock` shows exactly one changed line.
- `uv sync --locked` exits 0.

## Stop

None.
