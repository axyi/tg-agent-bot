# Prompt 102 — spec-v1.7.0 authoring

- **Date:** 2026-09-06
- **Executor model:** claude-fable-5-1 (lab session) with claude-opus-5 subagents for the draft, the verification pass and the application of cross-review findings
- **Model reason:** specification authoring is design work with open judgement calls (a spike protocol that must separate an honored reasoning switch from a lucky sample, per-purpose shippability against a frozen baseline, a wall-clock budget for the summary path); the lab writes specs with its strongest model and runs `go` with a cheaper executor
- **Harness:** Claude Code (lab session) with OpenAI Codex `gpt-5.6-sol` as the cross-review challenger
- **Stage:** spec authoring, before `go`
- **Owner of:** `docs/spec/spec-v1.7.0.md`, `docs/prompts/102-v170-spec-authoring.md`
- **REQ ids:** none implemented; this prompt defines REQ-V170-* (67 MUST, 14 NON-GOAL)

## Goal

Write `docs/spec/spec-v1.7.0.md`, the complete contract for the 1.7.0 minor
release: a reasoning-mechanism spike on LM Studio Bionic 1.1.x, a reasoning
policy resolved per call purpose, one wall-clock budget for the summary path,
candidate benchmark runs against the frozen `baseline-v1.6.0` with the cost
gate (−30 %) and the quality gate (S13–S18 back at 3/3, S15 and S18 blocking
again), and the three items carried from v1.6.0. The spec is handed to a
claude-sonnet-5 executor in another session via `go docs/spec/spec-v1.7.0.md`.

## Constraints

No production code, tests or configuration change in this prompt — only the
spec and this prompt file. Zero new runtime dependencies may be introduced by
the spec. Secret values, `.env`, `data/` and sandbox contents are never read
or quoted. Decisions taken by the user before authoring (same instrument and
frozen baseline, per-purpose policy with the summary as the first target,
cost gate −30 %, at most three candidate runs, executor model) are encoded,
not reopened.

## Acceptance

`docs/spec/spec-v1.7.0.md` exists with every REQ-V170-* id mapped in its
Appendix A, `uv run --locked python devtools/checks.py lint-docs` exits 0,
and Appendix C records every cross-review round with each finding's verdict.

## Stop

A cross-review finding that contradicts a user decision is reported to the
user instead of being applied; a finding that cannot be applied without
reading protected material stops the round.
