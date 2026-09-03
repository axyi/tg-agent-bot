# Prompt 54 — spec-v1.5 T10: RTK project-local hook

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** REQ-V15-RTK-01/02 give the exact JSON shape and the
  exact required sentence verbatim; the only judgment call is verifying
  current Claude Code hook syntax against documentation before writing
  `.claude/settings.json`, per this project's own global config-change
  rule, and being honest about what this run cannot verify (hook
  activation needs a fresh session)
- **Harness:** Claude Code
- **Stage:** T10
- **Owner of:** `.claude/settings.json` (new), `CLAUDE.md` (RTK block
  appended), `docs/reports/report-v1.5.md` (T10 section, RLM row),
  `docs/prompts/54-v15-t10-rtk-hook.md` (new)
- **REQ ids:** REQ-V15-RTK-01, REQ-V15-RTK-02

## Goal

Add this repository's own `.claude/settings.json` carrying the
`PreToolUse`/`Bash`/`rtk hook claude` shape REQ-V15-RTK-01 specifies,
and append the RTK instruction block to `CLAUDE.md` (keeping the
existing `@AGENTS.md` import), containing the required telemetry
sentence verbatim.

## Constraints

- Verify current Claude Code hooks syntax via context7 before writing
  `.claude/settings.json` — config schema evolves, and acting from
  memory silently no-ops or breaks the setup.
- The telemetry sentence must match the spec's quoted text
  character-for-character.
- `.claude/settings.json` must be committed, not git-ignored (only
  `.claude/agent-memory/` is).
- No file outside this repository is read to source the copied block —
  it was already present in this session's own inherited config
  context.

## Acceptance

- `.claude/settings.json` and the `CLAUDE.md` block both present and
  committed.
- The telemetry sentence verbatim.
- `rtk --version` matches the 0.47.0 pin; `rtk telemetry status` stays
  `consent: never asked`; `rtk hook check` confirms the rewrite engine
  itself works against the installed version.
- The task table's third item — "a Bash call in a fresh session shows
  the filter active" — is explicitly recorded as unverifiable within
  this run (hooks load at session start) rather than asserted.

## Stop

If the telemetry sentence cannot be reproduced character-for-character,
or if `.claude/settings.json`'s shape cannot be confirmed against
current documentation, stop rather than guess from memory.
