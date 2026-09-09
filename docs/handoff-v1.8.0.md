# Handoff — v1.8.0, ready for `go`

What the `go` session reads first. Authored 2026-09-09 in the lab session;
the run happens in a different session (`standards/workflow.md` §14).

## The `go` line

```text
go docs/spec/spec-v1.8.0.md
```

No operator input is needed in the request text. The release makes no live
model call: every acceptance scenario runs offline against fakes, a fake
clock and a temporary database. LM Studio does not have to be reachable, and
the GPU box's floating IP — which cost four re-pins across v1.6.0 and
v1.7.0 — is irrelevant to this release.

## What it is

Four areas, in the operator's words:

1. **`AGENTS.md` and the project prompts** — the repository has no Context
   discipline section at all. That is why the v1.7.0 run delegated one task
   of thirteen: the spec's reading map was the only mechanism and it lost
   four of four. The section is added, and this release binds its own run to
   it.
2. **Telegram chat UX** — the in-chat status message is deleted when the run
   succeeds and kept when it fails; a typing indicator runs while the request
   is processed.
3. **Dashboard visual rework** — the operator's verdict was that it "looks
   like a piece of something unclear, the numbers slide, nothing is
   understandable".
4. **Conversations and transcripts** — a conversation list and a transcript
   view, both new concepts in this codebase.

## Frozen decisions the run must not reopen

- **Version is 1.8.0**, not the 1.7.1 first requested: the release adds
  user-facing functionality, so SemVer makes it a minor. The bump lands in
  T9, after the gates pass, so any earlier stop needs no revert.
- **Transcripts come from the conversation store** (`messages.content`),
  always available. This does not touch REQ-V160-TRC-09, which governs
  *trace* content attributes — those stay opt-in and off, and
  `served_span()` keeps dropping them.
- **The entity is a conversation, not a "session".** "Session" is the
  operator's word for the same thing; the codebase already has
  `conversations`, and no parallel concept is introduced.
- **No new runtime dependency, no schema change, no JavaScript, no external
  font, stylesheet, image or CDN.** System font stack only — a webfont is
  unreachable under the dashboard's own constraints. Loopback-only,
  read-only, CSP `default-src 'none'` all stay.
- **Pagination is cursor-based with no previous link.** The browser's
  history is the back button; a wrong "prev" is worse than none.
- **The failure signal is structural.** `AgentOutcome` +
  `run_agent_outcome()`, with `run_agent()` kept as a `-> str` wrapper so the
  ~25 existing test call sites are untouched.

## State

- Spec: `docs/spec/spec-v1.8.0.md`, 103,612 bytes.
- Delta: `docs/spec/spec-v1.8.0-delta-1.md`, 20,149 bytes — §5.1's frozen
  design plan, the gate matrix the standards test parses, and Appendix C's
  round tables. The spec points at it; the matrix test reads it there.
- 51 MUST · 24 tests · 11 tasks (T0–T10) · 14 Gherkin scenarios · 6 mutation
  entries. Appendix A is a verified bijection in both directions.
- Nine of eleven tasks are delegated in §12.1's reading map. Each delegated
  task is briefed by a **task-brief file** the orchestrator writes before
  spawning the subagent: `docs/spec/task-briefs/v180-T<N>.md`. That directory
  does not exist yet; T0 creates it.
- Commits: `58d4553` (draft), `e537335` (round 1), `a8a3db9` (round 2),
  `ece29cc` (round 3). Authoring prompt: `docs/prompts/126-v180-spec-authoring.md`.
  The run's own prompts start at **127**.
- `[[VERIFY: …]]` markers: **none**.

## Cross-review

Three rounds against OpenAI Codex `gpt-5.6-sol`. **50 findings, 50 accepted
(14 adapted), 0 rejected.** Termination is `round_limit`, not a clean round:
round 3 still returned one Critical and six High findings, all accepted.
**Residual findings may exist.** Appendix C carries the full log.

Two of the lab session's own pre-round rulings were overturned by the review
and are recorded as such: the text-matching failure predicate (round 1, F1)
and the task-number-based stop route (rounds 1 and 2).

## Repository facts folded in during authoring

- `_STATIC_ROUTES` (`dashboard_server.py:53-55`) is referenced nowhere.
  Pre-existing dead code — surfaced, deliberately not deleted.
- `delete_message` already exists as dead stubs in two test doubles
  (`tests/test_pricing.py`, `tests/test_observability.py`); `TelegramClient`
  itself lacks the method.
- `messages` has no `trace_id`; the transcript's trace link is a
  `(conv_id, turn_id)` join against `llm_calls`/`tool_calls`.
- `font-variant-numeric: tabular-nums` already exists, paired with
  `ui-monospace` — so the "numbers slide" requirement is specified as column
  coverage, and the monospace face for data is dropped.
- `_call_with_retry`'s `-> dict` annotation is already inaccurate for any
  boolean-result method; `_send` swallows `TelegramError` with no success
  signal. Both are specified as edits for the run.
- The v1.7.0 report's "19 skylos shadow findings" is a stale module-scoped
  figure; the in-scope count is 8.

## Open, not blocking

`docs/llm-usage.md` row 62 was added retroactively this session: prompt 125
shipped without a usage row, which `/verify-run` item 3 would have raised.
