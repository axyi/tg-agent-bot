# Prompt 126 — authoring spec-v1.8.0

- **Date:** 2026-09-09
- **Executor model:** claude-opus-5 (lab session, drafting and applying subagents)
- **Model reason:** spec authoring is the stage where an error multiplies
  downstream, so `standards/workflow.md` §3 sends it to the strongest model;
  the executor that later runs this spec is chosen separately in §1
- **Harness:** Claude Code (lab session), `spec-authoring` skill
- **Stage:** authoring — no task in this spec; the run it describes starts at
  prompt 127
- **Owner of:** `docs/spec/spec-v1.8.0.md`,
  `docs/prompts/126-v180-spec-authoring.md`
- **REQ ids:** none implemented; this prompt produces the file that defines
  REQ-V180-* and T-V180-*

## Goal

Write the release specification for v1.8.0 so an autonomous executor can run
it end-to-end via `go` in a session with no access to this conversation. The
release covers four areas the operator named: the missing Context discipline
section in `AGENTS.md` and the project's other prompts; the Telegram chat UX
(the in-chat status message is deleted on success and kept on failure, and a
typing indicator runs while the request is processed); a visual rework of the
dashboard; and a conversations list with a transcript view.

Two operator decisions are frozen into the spec. The version is **1.8.0**,
not the 1.7.1 first requested: the release adds user-facing functionality, so
SemVer makes it a minor. Transcripts are read from the conversation store
(`messages.content`), always available — not from span content attributes,
which stay opt-in and off under REQ-V160-TRC-09.

The release also fixes the process defect the v1.7.0 run exposed. That run
delegated one task of thirteen because this repository's `AGENTS.md` carries
no Context discipline section at all, leaving the spec's reading map as the
only mechanism; the map lost four of four. This spec adds the section and
binds its own run to a per-task reading map, a closed list of delegation
exemptions and a named task-brief file.

## Constraints

No code, tests or configuration are changed by this prompt — it produces the
spec and this prompt file only. The spec itself forbids, for the run it
describes: any new runtime dependency, any database schema change, any
JavaScript, and any external font, stylesheet, image or CDN on the dashboard,
which stays bound to `127.0.0.1` and read-only. `.env`, `data/`, `bot.db` and
`exec_audit.jsonl` are never opened at any point.

The spec sits at 80,746 bytes against the ~80 KB ceiling in
`standards/workflow.md` §12 — an overshoot of 746 bytes, accepted with the
per-task reading map in place, which is what the ceiling exists to force.
Cross-review rounds must be size-neutral or net-negative; overflow goes to
`docs/spec/spec-v1.8.0-delta-1.md`.

## Acceptance

`docs/spec/spec-v1.8.0.md` exists and carries 50 MUST requirements, 23 test
ids, 11 tasks (T0–T10), 14 Gherkin scenarios and 6 mutation entries, with
Appendix A a verified bijection over the 50 ids in both directions.
`python3 devtools/checks.py lint-docs` exits 0. Every `file:line` citation in
the spec was opened and confirmed by a citation-audit pass in a clean
context, and every class, function and constant name the spec asserts exists
was checked against source.

## Stop

Stop and report rather than continue if: the spec cannot be made
self-consistent within the size ceiling without dropping a requirement; a
cross-review round raises a Critical finding that contradicts one of the
operator's frozen decisions; or the citation audit finds a cited artefact
that no longer exists and no correct replacement is derivable.
