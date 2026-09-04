# Prompt 74 — spec-v1.6.0 T2: storage schema 4, the `spans` table

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §"Executor: claude-sonnet-5"; every table
  shape, migration formula and helper signature is already written out in §5.
  This task was delegated to a general-purpose subagent per REQ-V160-EC-07's
  RLM rule (T2's own reading map, §14.1, spans five file:line ranges across
  `storage.py` alone, beyond the auto-delegate threshold) — this file is that
  delegate's own prompt record.
- **Harness:** Claude Code
- **Stage:** T2
- **Owner of:** `storage.py`, `tests/test_v160_observability.py` (extended)
- **REQ ids:** REQ-V160-TRC-05, -06, -07, -12; REQ-V160-EC-05

## Goal

Take `storage.SCHEMA_VERSION` from 3 to 4: add the `spans` table (`_SPANS_DDL`,
copied verbatim from §5), give `llm_calls`/`tool_calls` nullable
`trace_id`/`span_id` columns in both the fresh-database DDL and a new
`_MIGRATION_3_TO_4`, and chain `init_schema` through `1 → 2 → 3 → 4`. Add the
three storage helpers `tracing.SqliteSpanSink` already calls or that the
dashboard will need: `add_span`, `spans_for_trace`, `recent_traces`, plus
`connect_readonly` for the read-only dashboard connection. Split
`add_tool_turn` into a transaction-body helper (`_add_tool_turn_body`) and its
existing wrapper, unchanged in signature and behaviour, so a future root-span
sequence (T3) can reuse the body without nesting a `BEGIN IMMEDIATE`.

## Constraints

- `storage.add_span`'s keyword arguments must match exactly what
  `tracing.SqliteSpanSink.write` (already committed in T1) passes:
  `trace_id, span_id, parent_span_id, conv_id, turn_id, name, kind, ts,
  start_ns, duration_ms, status, status_message, attributes_json`.
- `SPAN_COLUMNS`, `LLM_CALL_COLUMNS`, `TOOL_CALL_COLUMNS` are the sole
  authority for both the INSERT and the structured log line
  (`_log_row` was already deriving the payload from the column tuple before
  this task — no refactor needed there); `add_llm_call`/`add_tool_call` gain
  `trace_id`/`span_id` keyword parameters defaulting to `None`
  (REQ-V160-EC-05) so today's callers and fakes are untouched.
- No nested `BEGIN IMMEDIATE`: `add_span` is a plain parameterised `INSERT`
  with no transaction of its own, exactly like `add_llm_call`/`add_tool_call`.
- `connect_readonly` uses the `mode=ro` URI form and `PRAGMA query_only = ON`,
  skips `_restrict_permissions` (it changes no file) and skips
  `journal_mode` (a read-only connection cannot set it); a missing database
  file raises `sqlite3.OperationalError` for free from the URI form.
- Whole-tree `ruff format` stays a NON-GOAL (REQ-V15-NG-04): only this task's
  own new/changed lines were kept format-clean, not pre-existing code the
  formatter would otherwise rewrite wholesale — one pre-existing line in
  `_add_single_row` still fails `ruff format --check storage.py` and was left
  alone rather than reformatted, to avoid inflating the diff and risking
  collisions with unrelated `mutation_check.py` `find` strings.
- One prompt → one commit, referencing this file.

## Acceptance

- `T-V160-TRC-06`, `-07`, `-08`, `-13` and the storage half of `T-V160-SRV-06`
  all green in `tests/test_v160_observability.py`; `tests/test_observability.py:431`
  amended exactly as spec'd (version `3 → 4`, `"spans"` added to the checked
  table list) and no other spec-listed test touched.
- Two deviations, both mechanical and unavoidable consequences of the
  `SCHEMA_VERSION` bump `§15.1` did not enumerate: `tests/test_observability.py`'s
  `test_obs03_a_future_version_is_still_refused` and
  `tests/test_summary.py`'s `test_t_v1_sum_01_migration_from_version_one` each
  hardcoded `4` as "one past current" when `SCHEMA_VERSION` was 3; both are
  bumped to `5`, the boundary `T-V160-TRC-08` itself tests. Recorded here and
  in the commit message, not silently edited.
- A second, purely internal defect found and fixed during implementation:
  `_OBSERVABILITY_DDL` is now the v4 shape (`trace_id`/`span_id` baked in from
  the start), so a database chaining through version 2 must never stop and
  commit `version = 3` over already-v4-shaped tables — that would be a
  version row lying about the shape it just wrote, and the original
  `_MIGRATION_3_TO_4`'s `ALTER TABLE` statements would then collide with
  columns already present. Fixed with a dedicated `_MIGRATION_2_TO_4` (builds
  the observability tables and the spans table in one transaction, straight
  to version 4, no intermediate `version = 3` commit); `_MIGRATION_3_TO_4`'s
  `ALTER TABLE` statements now run only against a genuine on-disk version-3
  database, which is exactly the shape they were written for.
  `_MIGRATION_2_TO_3` is left in the file, unused by `init_schema` — the
  amendment table doesn't list it as changed, so deleting it would be an
  unlisted edit; it is the dead-but-deliberate v3-terminal migration, not an
  oversight. Caught by `T-V160-TRC-07`'s own 1→4 and 2→4 chain tests and
  confirmed against the pre-existing (unlisted, untouched)
  `test_t_v1_sum_01_migration_from_version_one`.
- `storage.recent_traces`'s `GROUP BY` includes `root.id` alongside the
  displayed columns: without it, a `GROUP BY` under SQLite's relaxed-column
  rule ties break arbitrarily whenever two traces share the same
  second-granularity `ts` (`utc_now_iso()`'s format), even though `ORDER BY`
  names `root.id DESC` as the tiebreak.
- `uv run --locked pytest` exits 0 with more than 857 passed (857 + 18 new =
  875), zero failures.
- `uv run --locked ruff check .` and `uv run --locked ruff format --check
  storage.py tests/test_v160_observability.py tracing.py` both exit 0.
- `uv run --locked python devtools/mutation_check.py` still kills all 72
  entries; storage.py's one mutation
  (`v11-storage-add-tool-turn-redacts`) still matches exactly once after the
  `add_tool_turn` split.

## Stop

If a test outside `tests/test_v160_observability.py` and the two `§15.1`-listed
lines breaks, stop and reconsider before editing it — unless, as happened
twice here, the breakage is a provable, mechanical consequence of the very
change the spec assigns this task (the `SCHEMA_VERSION` bump), in which case
fix the literal and make it the headline of the report rather than a silent
edit.
