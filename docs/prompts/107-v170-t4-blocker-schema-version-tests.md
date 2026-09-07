# Prompt 107 — spec-v1.7.0 T4: blocker, SCHEMA_VERSION bump vs. unlisted tests

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T4 — blocked before any implementation
- **Owner of:** `docs/reports/report-v1.7.0.md` (Blocker section),
  `docs/prompts/107-v170-t4-blocker-schema-version-tests.md` (new)
- **REQ ids:** REQ-V170-OBS-01, REQ-V170-EC-03 (conflict identified, not
  resolved)

## Goal

Record a discovered conflict between REQ-V170-OBS-01 (bump
`storage.SCHEMA_VERSION` to 5) and REQ-V170-EC-03 (forbids editing any test
not named in §14.1's exhaustive amendment list), found while planning T4's
storage.py migration and before any source file was touched. Two
pre-existing, unlisted tests (`tests/test_observability.py:462-471`,
`tests/test_summary.py:150-161`) hardcode `5` as an always-refused future
schema version; that premise becomes structurally false the moment
`SCHEMA_VERSION` becomes 5, for any correct implementation — a
`schema_version` row is a bare integer, so `init_schema` cannot distinguish
a value written by the real migration from one forced by a test.

## Constraints

- No source, test or config file is edited by this task — the blocker is
  reported, not resolved. `docs/reports/report-v1.7.0.md`'s new "Blocker at
  T4" section and this prompt are the only changes.
- Per REQ-V170-EC-03's own text ("stop and reconsider, do not edit the
  test") and `AGENTS.md`'s go-protocol clause ("Where the spec and this
  file disagree, stop and ask"), the fix is not applied without the
  operator's explicit authorisation.

## Acceptance

- The report's Blocker section states both requirement ids, the exact
  affected test locations, the trace proving no implementation avoids the
  conflict, the evidence the spec's own N8 anticipated the new boundary
  (`6`, not `5`), and a precisely scoped proposed erratum.
- T0-T3's already-committed state is explicitly reconfirmed as unaffected
  and not reverted.

## Stop

This whole task IS the stop: work halts here until the operator authorises
the proposed erratum, a different resolution, or declines and directs
something else.
