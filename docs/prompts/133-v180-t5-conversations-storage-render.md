# Prompt 133 — v1.8.0 T5 conversations storage + render

- **Date:** 2026-09-09
- **Executor model:** claude-sonnet-5
- **Model reason:** a fully-specified, intricate algorithm (the by-turn
  cursor-paging window/probe/cap logic and the byte-budget atomic turn
  admission) with a verified-against-tree task brief and the spec's own
  exact SQL shapes given — careful, correct mechanical translation, no open
  design search.
- **Harness:** Claude Code
- **Stage:** T5
- **Owner of:** `storage.py`, `dashboard_render.py`, `tests/test_v180_conversations.py`
- **REQ ids:** REQ-V180-CONV-02 (all four readers), REQ-V180-CONV-03 (list
  builder), REQ-V180-CONV-04 (transcript builder, atomic admission),
  REQ-V180-CONV-05 (trace map, consumed by the transcript builder),
  REQ-V180-SEC-02 items 1 and 3 (the two structural pieces this task owns:
  the 2000-char input assumption and the whole-response byte-budget seed —
  not item 2, the `limit` bound itself, which is CONV-04/T6's)

## Goal

Implement `docs/spec/task-briefs/v180-T5.md` end to end: four new
`storage.py` read functions behind the `/conversations` and
`/conversations/<id>` dashboard pages (`conversation_row`,
`recent_conversations`, `conversation_messages` — the exact by-turn
cursor-paging algorithm of REQ-V180-CONV-02 item 3 — and
`conversation_turn_traces`), plus two new pure `dashboard_render.py`
builders (`conversation_list_section`, `conversation_transcript_section`
with byte-budget-bounded atomic turn admission). `dashboard_server.py`
route wiring, JSON mirrors and the authoritative render-builder test
coverage are T6's, out of this task's scope.

## Constraints

- File map: `storage.py`, `dashboard_render.py`,
  `tests/test_v180_conversations.py`, this prompt file. Never
  `dashboard_server.py`, never any other pre-existing test file.
- No DDL, no migration, `SCHEMA_VERSION` stays 5 (NG-07).
- Every SQL statement binds `conv_id`, `limit`, cursor values and turn ids
  as parameters — no f-string/`%`/`.format`/concatenation of request-shaped
  values into SQL text.
- `dashboard_render.py` additions stay pure: no `import config`, no
  `import storage`, no `import sqlite3`, no I/O, no `Path`. Reuse T4's
  column-spec helpers (`ColumnSpec`, `_th_cell`, `_td_cell`, `_row_th_cell`,
  `_head_row`, `_num_class`) and `_row_field` — do not duplicate them.
- My own required tests are storage-layer only (`T-V180-CONV-01/-02/-03`);
  the two render builders get basic smoke coverage here, their
  authoritative test coverage is T6's (`T-V180-CONV-04/-05`).
- No file outside this repository read or written (EC-01).
- Do not run the full six-gate sequence; only `ruff check .` and the whole
  `pytest` suite.
- A pre-existing test file breaking unexpectedly is stopped on and reported,
  never silently fixed.

## Acceptance

`T-V180-CONV-01`/`-02`/`-03` (23 tests total in
`tests/test_v180_conversations.py`, including the two builders' smoke
tests) proven red on the unmodified tree (`git stash` of `storage.py` +
`dashboard_render.py`, restored before committing) and green on the
modified tree. `uv run --locked ruff check .` exits 0. `uv run --locked
pytest` exits 0: 1202 passed, 1 skipped (1179 passed, 1 skipped baseline
plus this task's 23 new tests) — no pre-existing test regressed.
`git diff` shows no DDL/schema change; `SCHEMA_VERSION` unchanged at 5.

## Stop

Any pre-existing test file going red from this change: stop, report the
exact failing assertion, leave it unmodified for the orchestrator to
decide. In this run no pre-existing test went red.
