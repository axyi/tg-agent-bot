# Prompt 71 — spec-v1.6.0 authoring

- **Date:** 2026-09-04
- **Executor model:** claude-fable-5-1 (lab session) with claude-opus-5 subagents for the draft, the compression pass and the application of cross-review findings
- **Model reason:** specification authoring is design work with open judgement calls (scope alignment, the OTel GenAI naming contract, the security envelope of a dashboard served from the bot process); the lab writes specs with its strongest model and runs `go` with a cheaper executor
- **Harness:** Claude Code (lab session) with OpenAI Codex `gpt-5.6-sol` as the cross-review challenger
- **Stage:** spec authoring, before `go`
- **Owner of:** `docs/spec/spec-v1.6.0.md`, `docs/prompts/71-v160-spec-authoring.md`
- **REQ ids:** none implemented; this prompt defines REQ-V160-* (100 MUST, 16 NON-GOAL)

## Goal

Write `docs/spec/spec-v1.6.0.md`, the complete contract for the 1.6.0 minor
release: own tracing with OpenTelemetry GenAI semantic-convention names,
metrics over the recorded rows, a read-only dashboard served by default from
the bot process, scenarios S13–S18 with the starved-summary and repeated
tool-error fixes, a fresh benchmark baseline, and three-number SemVer. The
spec is handed to a claude-sonnet-5 executor in another session via
`go docs/spec/spec-v1.6.0.md`.

## Constraints

No production code, tests or configuration change in this prompt — only the
spec and this prompt file. Zero new runtime dependencies may be introduced by
the spec. Secret values, `.env`, `data/` and sandbox contents are never read
or quoted. Decisions taken by the user before authoring (self-built stack,
dashboard on by default, 1.6.0 / 1.7.0 split, SemVer, executor model) are
encoded, not reopened.

## Acceptance

`docs/spec/spec-v1.6.0.md` exists with every REQ-V160-* id mapped in its
Appendix A, `uv run --locked python devtools/checks.py lint-docs` exits 0,
and Appendix C records every cross-review round with each finding's verdict.

## Stop

A cross-review finding that contradicts a user decision is reported to the
user instead of being applied; a finding that cannot be applied without
reading protected material stops the round.
