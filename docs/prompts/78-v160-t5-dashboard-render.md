# Prompt 78 — spec-v1.6.0 T5: dashboard_render.py, bench report refactor

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code, a general-purpose
  subagent delegated per REQ-V160-EC-07's RLM rule since T5's own reading
  map in §14.1 spans `devtools/dashboard.py:259-630` (~370 lines) plus a
  large new module)
- **Model reason:** §14.1 marks T5 "delegate: yes"; the reading map alone
  (the render half of `devtools/dashboard.py` plus the full new
  `dashboard_render.py` surface) crosses REQ-V160-EC-07's threshold, and the
  task is a mechanical-but-careful relocation (verbatim byte-identity on one
  side, a brand-new generic rendering API on the other) rather than a
  high-risk control-flow change that would argue for direct execution the
  way T3 did.
- **Harness:** Claude Code
- **Stage:** T5
- **Owner of:** `dashboard_render.py` (new, top-level), `devtools/dashboard.py`
  (refactored: render half moved out, data functions and CLI unchanged),
  `tests/test_v160_dashboard.py` (new), `tests/test_dashboard.py` (two forced
  fixture-literal amendments), `tests/test_v160_observability.py` (one-line
  widening of `test_t_v160_trc_01_module_resolves_to_a_py_file_not_a_package`'s
  tuple)
- **REQ ids:** REQ-V160-DSH-01, -02, -03, -04, -05, -06, -07, -08, -09

## Goal

Build `dashboard_render.py` as the one HTML-emitting module in the
repository (REQ-V160-DSH-01): `page`, `usage_section`, `histogram_svg`,
`bar_svg`, `trace_list_section`, `trace_tree_section`, `gantt_svg`,
`tool_health_section`, `compare_section`, `served_span`,
`SERVED_SPAN_ATTRIBUTE_KEYS`, `error_page`, `response_too_large_page`,
`invalid_host_page`, `esc` — pure functions, no I/O, no database handle, no
`Path`, no `print`. Refactor `devtools/dashboard.py`'s render half (`_esc`,
`fmt`, `_header`, `_aggregates`, `_cache`, `_bar`, `_tools`, `_timeline`,
`_compare`, `render`) behind it (REQ-V160-DSH-05), keeping the data
functions (`load_document`, `scenario_runs`, `median_run`, `timeline_rows`,
`tool_breakdown`) and the CLI contract exactly where they are and byte-for-
byte unchanged in output.

## Constraints

- **Import direction never reverses** (REQ-V160-TREE-03): `dashboard_render.py`
  imports nothing from `devtools/`; `devtools/dashboard.py` imports
  `dashboard_render`. Verified by static source inspection
  (`test_t_v160_dsh_01_*`), not just code review.
- **The relocated render half must not call back into `devtools/dashboard.py`'s
  own data functions.** `_tools` and `_timeline` originally called
  `tool_breakdown`/`scenario_runs`/`median_key`/`median_run`/`timeline_rows`
  directly — those five stay in `devtools/dashboard.py` per REQ-V160-DSH-05's
  exact line pins, so they cannot be called from `dashboard_render.py`
  without reversing the import direction. Resolved by having
  `devtools/dashboard.py` pre-compute the data those two functions need
  (`tool_breakdown(document["runs"])`, and a new `_timeline_blocks(document)`
  glue function assembling one dict per scenario from `scenario_runs`,
  `median_key`, `median_run`, `timeline_rows` and `metrics.context_growth`)
  and hand it to `dashboard_render._tools`/`_timeline` as plain data —
  `devtools.dashboard.render()` becomes a three-line orchestration wrapper
  around `dashboard_render.render()`. This was not anticipated by the
  originating brief and was worked out during implementation; it is a
  forced mechanical consequence of REQ-V160-DSH-05's own line pins, not
  scope creep.
- **REQ-V160-DSH-02's byte-identity vs. `render()`'s own byte-identity
  requirement.** The brief's "the bench report's aggregates/totals band
  should call `usage_section`" cannot be reconciled with "`render()`'s
  output matches the pre-refactor page byte-for-byte" — `_aggregates`
  already emits a different table shape (`TOTAL_ROWS`/`m-<key>` cells) than
  `usage_section`'s `UsageRow` columns, and routing `_aggregates` through
  `usage_section` would break `test_aggregate_totals_match_the_fixture_summary`
  and several neighbours. Resolved by NOT wiring `usage_section` into
  `render()`'s output: `devtools/dashboard.py` instead gains
  `usage_rows_from_document(document)` (an adapter to a single-row
  `UsageRow` list) and `usage_band(document)` (calls
  `dashboard_render.usage_section` on that row) as available, tested,
  functions that satisfy "the rendering call goes through `usage_section`,
  not a second bespoke implementation" without touching `render()`'s bytes.
  `T-V160-DSH-02` asserts `dashboard.usage_band(doc)` is byte-identical to a
  direct `dashboard_render.usage_section(...)` call on the same rows.
- **Mutation-check pre-flight**: `grep -n "dashboard" devtools/mutation_check.py`
  returns no hits — none of the 72 mutation entries target
  `devtools/dashboard.py`'s render half, so no `find`-string update was
  needed as a forced consequence of this refactor (unlike T3's one
  pre-existing entry).
- REQ-V160-API-05's length maxima applied inside `served_span`: span/tool/
  model/provider names ≤ 128 chars, any other served attribute value ≤ 256,
  truncated values get a trailing `…` such that the *result's* length is
  exactly the cap. `gen_ai.response.finish_reasons` (a `list[str]`) is
  truncated per element, never `str()`-ed whole. `parent_span_id` shape
  validation (hex/length) is explicitly out of scope here — REQ-V160-API-05's
  identifier-dropping is T6/T7's job over the JSON API; `served_span` here
  passes it through as a plain string or `None`.
- Two authorized amendments only, per §15.1: `tests/test_dashboard.py`'s
  `document()` helper's `"bench_schema": 1` → `bench.BENCH_SCHEMA`, and the
  parametrised unreadable-document case's `"bench_schema": 2` → `3`.
  `tests/test_v160_observability.py`'s widening is the one line the T1-era
  test already comments as reserved for T5/T6.
- Zero new dependencies; stdlib only, plus `tracing`/`metrics` (already
  dependencies of this project).
- One prompt → one commit, referencing this file.
- **Deviation from REQ-V160-TST-02 (test-first), recorded in
  `docs/reports/report-v1.6.0.md`'s Deviations log**: `dashboard_render.py`
  and the `devtools/dashboard.py` refactor were written before
  `tests/test_v160_dashboard.py`, not observed to fail against an absent
  implementation first. The refactor's primary correctness signal was the
  pre-existing `tests/test_dashboard.py` suite (REQ-V160-DSH-05's
  byte-identity requirement), which only made sense to check after the
  relocation; the new suite was then written against the spec text and
  caught two real mistakes on its first run (an over-broad "no `devtools`
  substring anywhere" check tripping on this module's own docstring, and a
  histogram label assertion that didn't account for `esc()`'s own escaping
  of `>`) — both fixed in the test, not the implementation.

## Acceptance

- `tests/test_v160_dashboard.py` (23 new tests) covers T-V160-DSH-01 (import
  direction, no devtools import, no I/O primitives, no HTML literal left in
  `devtools/dashboard.py`), -02 (byte-identical `usage_section` fragments),
  -03 (offline/script-free sweep over every public render function, the
  em-dash share rule), -04 (escaping in HTML and SVG alike, the
  `status_message` canary proven unreachable because `ServedSpan` has no
  such field), -07 (gantt geometry: `start_ns` order survives a reversed
  `ts` fixture, zero-duration root places every bar at `x = 0`, the error
  outline colour, a zero-count histogram bucket's label), -08 (a
  missing-root trace renders orphans with a banner, no exception), -09 (the
  exact `SERVED_SPAN_ATTRIBUTE_KEYS` set, the absent `status_message` field,
  `served_span`'s drop/truncate behaviour over both the `attributes_json`
  and the bench-document `attributes` shapes, `TypeError` on a raw
  `sqlite3.Row` and on a bare dict).
- `uv run --locked ruff check .` exits 0.
- `uv run --locked ruff format --check dashboard_render.py
  tests/test_v160_dashboard.py` exits 0 (new files only — no whole-file
  reformat of `devtools/dashboard.py`, `tests/test_dashboard.py` or
  `tests/test_v160_observability.py`; verified via `git diff --stat`
  showing only the two/one authorized line changes in each).
- `uv run --locked pytest` exits 0, 927 passed (904 + 23 new).
- `uv run --locked python bot.py --selftest` and `--selftest-live` both
  exit 0 (the live gate's `docker` check required pulling
  `python:3.14-slim@<pinned digest>` into this environment first — an
  environment provisioning step, not a code change).
- `uv run --locked python devtools/mutation_check.py` exits 0, 72/72 killed.

## Stop

If `render()`'s output had changed by even one byte for the fixtures
`tests/test_dashboard.py` already exercises, that would be a defect worth
stopping over — it did not: the existing 37-test suite passed unamended
(save the two authorized fixture-literal edits) against the refactored
module on the first run after the `_tools`/`_timeline` data-precomputation
redesign.
