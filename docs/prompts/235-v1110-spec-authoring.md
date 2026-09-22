# Prompt 235 — authoring spec-v1.11.0

- **Date:** 2026-09-22
- **Executor model:** claude-fable-5-1 (lab session: three read-only reconnaissance subagents, one drafting subagent, one citation-audit subagent, one applying subagent per cross-review round)
- **Model reason:** spec authoring is the stage where an error multiplies
  downstream, so `standards/workflow.md` §3 sends it to the strongest model;
  the executor that later runs this spec is named in the spec's Execution
  contract (`claude-sonnet-5`)
- **Harness:** Claude Code (lab session), `spec-authoring` skill
- **Stage:** authoring — no task in this spec; the run it describes starts at
  prompt 236
- **Owner of:** `docs/spec/spec-v1.11.0.md`,
  `docs/prompts/235-v1110-spec-authoring.md`
- **REQ ids:** none implemented; this prompt produces the file that defines
  REQ-V1110-* and T-V1110-*

## Goal

Write the feature specification for v1.11.0 — the Telegram interface
release — so an autonomous executor can run it end-to-end via `go` in a
session with no access to this conversation. The operator asked for six
things: a command that lists the caller's sessions, a command that switches
to a session by id, a `/model` reworked as a menu (provider first, then a
model from a list), `/stats` and `/documents` rendered as real tables
instead of pipe-separated prose, and support for larger documents. The lab
added, as a small separately strikable group, `setMyCommands`, `/help` and
`/start`.

The decisions frozen into the spec: version **1.11.0**, MINOR, tag local,
no push; rich formatting is HTML `parse_mode` with a single `<pre>` block
on a dedicated table path only — the agent-reply path stays plain
`{chat_id, text}` and the v1.10.0 pin is retired by id and narrowed, not
contradicted; inline keyboards and `callback_query` enter for `/model` and
`/sessions` only, with the same guards as messages; the model catalogue is
two env allowlists, never a live enumeration; provider and model overrides
stay global `bot_state` keys; sessions are the existing `conversations`
rows, titles derived at list time, no schema migration; the document cap
rises to the Bot API `getFile` ceiling (20,000,000 bytes), ingest moves to
one daemon worker thread with its own SQLite connection, a bounded queue,
one in-flight job per user, an 1800 s budget and a cooperative `/cancel`;
no new third-party dependencies; exactly eight `v1110-*` mutation entries;
gate 8 exactly once on the shipping tree, reused by the version-only
identity check; the benchmark rule is not triggered; T0 is a structural
frozen-pin inventory and a pin found later is a disclosed amendment.

There is no unmerged `/stats` spec: the two requirements that ever shaped
`/stats` (v1.3, v1.6.0) are both implemented; what the operator remembered
is the README sample, two lines out of date — the spec fixes it in passing.

## Constraints

- Authoring only: no code changes, no live model calls beyond the Codex
  cross-review; `.env`, `data/`, `bot.db`, `sandbox/` never opened; the
  Telegram Bot API limits were fetched once from the public documentation
  and recorded verbatim in the brief's facts file.
- Drafted from a frozen brief (decisions D1–D22 plus four facts files the
  lab session established by read-only reconnaissance), then audited
  citation by citation, then cross-reviewed against OpenAI Codex
  `gpt-5.6-sol` for up to three rounds; every finding is ruled on by the
  lab before a clean-context subagent applies it; Appendix C records every
  verdict.
- Spec size is a lab decision (`standards/workflow.md` §12); the file
  references the mechanisms of v1.9.0 through v1.10.4 by id instead of
  restating them.

## Acceptance

- `docs/spec/spec-v1.11.0.md` exists; Appendix A is a bijection between MUST
  ids and traceability rows, every test id and every Gherkin id is cited by
  a row; every task has a reading-map row with a `delegate` cell; no
  `[[VERIFY: …]]` marker is left without a decision rule.
- Every `file:line` citation was opened and confirmed by the audit pass.
- Appendix C names the challenger, the rounds, the termination reason and
  the accept/reject tally.
- `uv run --locked python devtools/checks.py lint-docs` accepts this prompt
  file (header bullets and the four blocks in order).

## Stop

The lab session stops and reports when the Codex seam cannot be reached
after a real attempt (recorded in Appendix C with what stood in for it), or
when the citation audit surfaces a contradiction between the frozen
decisions and the repository that the operator has to resolve.
