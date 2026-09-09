# Prompt 134 — v1.8.0 T6 conversations server + security + mutations

- **Date:** 2026-09-09
- **Executor model:** claude-sonnet-5
- **Model reason:** a large, two-halved task with a verified-against-tree
  brief (four HTTP routes plus a byte-budget algorithm reimplemented
  independently for JSON, then six mutation entries with real, measured
  timing runs) — careful mechanical translation of a fully-specified design
  against an existing architecture, not open design search.
- **Harness:** Claude Code
- **Stage:** T6
- **Owner of:** `dashboard_server.py`, `dashboard_render.py` (one small,
  flagged addition — see Stop), `tests/test_v180_conversations.py`,
  `devtools/mutation_check.py`, `config/quality_gates.yaml`,
  `tests/test_v15_standards.py`
- **REQ ids:** REQ-V180-CONV-03/-04/-05/-06/-07 (the four routes, pagination,
  trace links, JSON mirrors, routing/404/400), REQ-V180-SEC-01..-05
  (redaction, the three-fold byte bound, the TRC-09 separation, server
  invariants, parameterized SQL), REQ-V180-EC-10/-12 (the six mutation
  entries and the gate matrix)

## Goal

Implement `docs/spec/task-briefs/v180-T6.md` end to end, in one commit: (1)
four new dashboard routes (`/conversations`, `/conversations/<id>`,
`/api/conversations`, `/api/conversations/<id>`) with shared redaction and
truncation, byte-budget-bounded pagination independently correct on both the
HTML and JSON sinks, and security tests; (2) six new `v180-*` mutation
entries plus two really-measured mutation-gate timeout values, wiring
`mutation-v180` into `config/quality_gates.yaml` and repointing the
gate-matrix standards test at `docs/spec/spec-v1.8.0-delta-1.md`.

## Constraints

- File map as listed above. `storage.py` untouched (T5's, already landed) —
  every new route calls T5's four parameterized readers, no new raw SQL.
- No DDL, no schema change (`SCHEMA_VERSION` stays 5, NG-07).
- Redaction happens in exactly one place (`dashboard_server._redact_message`)
  and covers `content`, `role` and `tool_call_id` alike; `dashboard_render.py`
  only escapes (HTML sink) or is untouched (JSON sink).
- The JSON route's byte budget (`/api/conversations/<id>`) is its own,
  independent reimplementation of CONV-04's atomic turn admission against
  `_dumps`-shaped bytes — it must not go through
  `conversation_transcript_section`.
- No file outside this repository read or written (EC-01).
- Only `ruff check .`, the whole `pytest` suite, and the two timed mutation
  runs this task specifically requires — no other gate commands run.
- A pre-existing test file breaking unexpectedly is stopped on and reported,
  never silently fixed.

## Acceptance

`T-V180-CONV-04`/`-05`, `T-V180-SEC-01`..`-04` (14 new tests in
`tests/test_v180_conversations.py`, 37 total in that file) proven red before
their code existed (each assertion depends on code this task adds — the
route handlers, `_redact_message`, `_admit_json_transcript`,
`transcript_page_footer`) and green after. `uv run --locked ruff check .`
exits 0. `uv run --locked pytest` exits 0: 1216 passed, 1 skipped (1202
passed, 1 skipped baseline at T5's close, plus this task's 14 new tests) — no
pre-existing test regressed. `uv run --locked python devtools/mutation_check.py
--select v180-` exits 0, 6/6 killed, real wall-clock 402s (6m42s) — timeout
set to 810s (2×, rounded up). `uv run --locked python devtools/mutation_check.py`
(no `--select`) exits 0, 98/98 killed, real wall-clock 2809s (46m49s) —
`mutation-all`'s timeout set to 5620s (2×, rounded up). All six mutate → run
killing test → revert → confirm green cycles were run individually via
`--only <id>` before the batch `--select v180-` run, per REV-01 item 8.
`tests/test_v15_standards.py::test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
green after repointing at `docs/spec/spec-v1.8.0-delta-1.md` (not
hand-edited — it already carries the matrix table verbatim, including the
`mutation_check.py --select v180-` row).

## Stop

Any pre-existing test file going red from this change: stop, report the
exact failing assertion, leave it unmodified for the orchestrator to decide.
In this run, `tests/test_v160_dashboard.py::test_t_v160_dsh_01_dashboard_server_holds_no_html_literal`
went red once after the first draft of the transcript page's next-link/
first-page-link/range-note markup was written directly in
`dashboard_server.py` — REQ-V160-DSH-01 forbids any HTML literal outside
`dashboard_render.py`. This is the one place this task's own file map is
crossed, as the brief's own constraints anticipated: the smallest possible
fix was made — one new pure function, `dashboard_render.transcript_page_footer`
(range note + next link + first-page link, reusing `_row_field`, `meta_line`
and `esc`, no other change to that module) — and `dashboard_server.py`'s own
three ad-hoc HTML-literal helpers were removed in favour of calling it. No
other pre-existing test went red.

`_STATIC_ROUTES` (`dashboard_server.py`) remains pre-existing dead code,
referenced nowhere in the repository (REQ-V180-RPT-02 item 8) — this task
added `"/conversations"` and `"/api/conversations"` to it per the spec's own
instruction so it does not grow *more* stale, and otherwise left it alone.
