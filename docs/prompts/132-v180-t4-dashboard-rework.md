# Prompt 132 — v1.8.0 T4 dashboard visual rework

- **Date:** 2026-09-09
- **Executor model:** claude-sonnet-5
- **Model reason:** a large, structural but fully-scoped visual rewrite with a frozen design plan and verified line numbers in the task brief; no open design search needed, only careful mechanical translation of the plan into `STYLE`/`PALETTE`/builders.
- **Harness:** Claude Code
- **Stage:** T4
- **Owner of:** `dashboard_render.py`, `tests/test_v180_dashboard.py`
- **REQ ids:** REQ-V180-DSH-02, REQ-V180-DSH-03, REQ-V180-DSH-04, REQ-V180-DSH-05 (builders only), REQ-V180-DSH-06

## Goal

Implement spec-v1.8.0 section 5's frozen visual rework (section 5.1, copied
verbatim into `docs/spec/task-briefs/v180-T4.md`) inside `dashboard_render.py`
only: rewrite `STYLE` to the frozen palette/type-scale/surface plan; give
`usage_section`, `tool_health_section` and `trace_list_section` an explicit,
declared `(heading, kind)` column spec so `class="num"` coverage is provable
rather than inferred; fix the two live rejected-pattern violations named in
the brief (the middle-dot join in `tool_health_section`'s summary line and
the uppercase `th` rule) plus a third found during implementation
(`trace_tree_section`'s `_render_span_node` also joined with `·`); add a new
pure `reading_strip_section` builder for the `/` page's four-value reading
strip; remap the five `PALETTE` literals to the frozen hex values.

## Constraints

- File map: `dashboard_render.py`, `tests/test_v180_dashboard.py`, this
  prompt file. Never `dashboard_server.py` or `devtools/dashboard.py`
  (T6's route wiring is out of scope; the bench-report renderer's own logic
  in the second half of `dashboard_render.py` — `render`, `_header`,
  `_aggregates`, `_cache`, `_tools`, `_timeline`, `_compare` — is untouched
  and inherits the `STYLE`/`PALETTE` rewrite only automatically).
- The frozen design plan is implemented, not redesigned: every hex, size,
  weight and layout rule not given by the plan (e.g. `.tag`'s border style,
  `.warn`'s remap off warm cream) is a minimal, non-arbitrary implementation
  choice inside the plan's stated constraints (hairline rules, the eight-colour
  budget, no shadow, ≤2px radius), never a new design decision.
- `page()`'s signature and one-`<style>`-block shape unchanged. Every SVG
  helper's signature, geometry constant and `<title>`/`<desc>` unchanged —
  only the five `PALETTE` string literals move.
- No existing test file may be edited. A pre-existing test going red from the
  `STYLE`/`PALETTE` rewrite is reported, not fixed.
- No import of `config`, `storage` or `sqlite3`; no I/O, `Path` or `print` in
  `dashboard_render.py`; every value reaching HTML/SVG text still through
  `esc()`.

## Acceptance

`uv run --locked ruff check .` exits 0. `uv run --locked pytest` exits 0,
1180 tests collected (1179 passed, 1 pre-existing skip unrelated to this
task), no failures. `tests/test_v180_dashboard.py`'s
`T-V180-DSH-01`/`-02`/`-03` proven red on the unmodified tree (via a
temporary `git stash` of only `dashboard_render.py`, restored before
committing) and green on the modified tree; `T-V180-DSH-04` written as a
structural test of `page()`'s own nav-rendering behaviour per the brief's
scope note, since route-level nav lists are `dashboard_server.py`'s (T6's).

## Stop

Any existing test file (`tests/test_dashboard.py`, `tests/test_v160_dashboard.py`,
or any other pre-existing file) going red from the rewrite: stop, report the
exact failing assertion, and leave it unmodified for the orchestrator to
decide. In this run no pre-existing test went red — neither file hard-codes a
`STYLE` fragment or a changing `PALETTE` hex value (only
`PALETTE["error_outline"]` is asserted anywhere, and it is unchanged at
`#b23636`).
