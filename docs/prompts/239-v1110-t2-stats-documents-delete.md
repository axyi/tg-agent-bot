# Prompt 239 — v1.11.0 T2: `/stats` and `/documents` as tables, `/delete #id`

- **Date:** 2026-09-22
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (EC-04), brief
  `docs/spec/task-briefs/v1110-T2.md`; test-first source/test work, within
  this one subagent's single context.
- **Harness:** Claude Code (subagent)
- **Stage:** T2
- **Owner of:** `bot.py`, `tests/test_v1110_sta.py` (new),
  `tests/test_v1110_doc.py` (new), `tests/test_observability.py`,
  `tests/test_v160_observability.py`, `tests/test_pricing.py`,
  `tests/test_v190_commands.py`, `tests/test_v1100_sanitization.py`,
  `README.md`, `docs/prompts/239-v1110-t2-stats-documents-delete.md`,
  `docs/llm-usage.md` (row 150), `docs/reports/report-v1.11.0.md` (`## T2`)
- **REQ ids:** REQ-V1110-STA-01, REQ-V1110-DOC-01, REQ-V1110-DOC-02,
  REQ-V1110-DOC-03

## Goal

Build `/stats` and `/documents` as `<pre>`-wrapped tables over T1's
`send_pre`/`tables.render_table`, `/delete #<id>` alongside the existing
exact-filename form, and the three-way refusal-wording split
(`DocxArchiveTooLargeError`/`PdfTooManyPagesError`/`ExtractedTextTooLargeError`
onto their own reply strings), per `docs/spec/spec-v1.11.0.md` sec.4-5 and
brief `docs/spec/task-briefs/v1110-T2.md`.

**Test-first (EC-02), stated at the granularity that actually happened, not
as one blanket claim**: `tests/test_v1110_sta.py` and
`tests/test_v1110_doc.py` were written and run *before* any `bot.py`
change — except `T-V1110-DOC-03`'s two `#`-guard sub-cases (`#²`, a
25-digit id), added later, post-implementation (see below).
`T-V1110-STA-01`, `-02` and `T-V1110-DOC-01` all went red on the same
first assertion in their shared `<pre>`/`parse_mode` check
(`assert None == 'HTML'` — `/stats` and `/documents` still used the plain
`_send`/`reply_parts` path), so the label-order, wrap-width, fit-marker and
size/truncation assertions further down those same test bodies never
themselves executed red — the test file as a whole ran red for the right
reason, but not every individual assertion in it did.
`T-V1110-STA-03` went red on a missing README label (`AssertionError`).
`T-V1110-DOC-03`'s original cases (own id/foreign id/non-digit/filename/
bare usage) went red on the still-old `DELETE_USAGE_REPLY` text
(`AssertionError`), so its `#<id>` assertions likewise never ran on their
own before the fix. `T-V1110-DOC-04`'s three parametrized cases: the DOCX
and PDF-pages variants went red on `AttributeError` (the two new reply
constants did not exist yet); the extracted-text variant went red on an
`AssertionError` (the old "500,000" wording). `T-V1110-DOC-02`
(`DOCUMENTS_EMPTY_REPLY` on the plain path) **never ran red** — the empty
case was already correct before this task and stayed unchanged; it is a
regression guard, not a red-then-green test.

**`T-V1110-DOC-03`'s two `#`-guard sub-cases are also not red-then-green
tests.** The guards they test (`id_part.isascii()`, `_DELETE_MAX_ID`) were
in `_handle_delete`'s *first* version — an earlier advisor review, before
any code existed, flagged the two crash paths and the fix went straight
into the implementation, so `bot.py` never shipped without them. The two
test cases were added afterward, against an already-correct
implementation, so they passed immediately and never ran red through
EC-02's own sequence. Their ability to catch a real regression was
verified separately: each guard was temporarily reverted in `bot.py`, the
new assertion watched fail (`ValueError`/`OverflowError`, uncaught), then
the guard restored and the suite re-confirmed green — a mutation-kill-style
proof, not test-first implementation. All 7 test functions (9 collected
items, `T-V1110-DOC-04` parametrized ×3) are green now.

## Constraints

Do not run gate 5 (`bot.py --selftest-live`), `devtools/mutation_check.py`,
`devtools/rag_eval.py` or `devtools/agent_eval.py` — gates 1-4 only. Do not
run `ruff format` (whole-file reformat risk), only `ruff check .`. Never
print, quote or commit either of this repo's two secret values
(`config.py:351`, `:379`). `--no-verify` never used.

## Acceptance

`T-V1110-STA-01`…`-03`, `T-V1110-DOC-01`…`-04` all green. The pin-rewrite
work the spec's §12 sums to 43 sites: this task actually rewrote 9 test
functions across three files touching the `/stats` render (7 in
`tests/test_observability.py`, plus `stats_text`'s own helper —
`test_obs07_stats_layout`, `_reports_no_pricing`,
`_basis_is_mixed_when_the_rows_disagree`, `_on_an_empty_database`,
`_separates_this_conversation_from_all_time`,
`_reports_cached_and_reasoning_when_present`,
`_drops_whole_lines_before_it_cuts_one`; 1 in `tests/test_v160_observability.py`
— `test_stats_gains_two_lines_appended`; 1 in `tests/test_pricing.py` —
`test_prc03_every_basis_form_is_stored_and_rendered`), all now
presence/contiguity, never a whole-line equality. The two `/status`-line
sites T0's inventory also listed (`test_obs07_status_carries_the_token_line`,
`test_obs07_status_token_line_without_a_conversation`) were checked and
left unchanged — `/status` is out of this task's scope. README's `### /stats`
and the `## Commands` table rows for `/documents`/`/delete` updated to match
the new table output. Gates 1-4 green, each run verbatim (no added flags —
an earlier doubled `-q` had suppressed pytest's own summary line in
several runs during this task; the report's `## T2` section has the
account): `uv sync --locked` (25 resolved, 23 checked), `uv run --locked
ruff check .` (all checks passed), `uv run --locked pytest` (`2328 passed,
1 skipped, 2 xfailed in 24.17s` — 2331 collected, 2322 baseline at T1's
`2b2dd4e` + 9 new this task), `uv run --locked python bot.py --selftest`
(`selftest: OK`).

## Stop

A cited `file:line` drifting more than 5 lines from the live tree, or a
cited mechanism being absent, stops the task for a report rather than a
guess (none triggered this task — see the report's drift note; two ~3-line
drifts disclosed, both well inside tolerance, measured against the brief's
own re-grepped locations as instructed, not against the spec's `295b01f`
citations T1 already shifted).

Two advisor reviews happened at different points, and an earlier draft of
this section wrongly attributed all four fixes below to one review "called
after gates 1-4 first went green" — true only for the last two. **First
review**, before any test or implementation code existed: flagged (1) a
`cost_basis` value wider than the "cost basis" column's 16-unit `max_width`
truncates like any other cell, so `test_prc03_every_basis_form_is_stored_and_rendered`
was written from the start comparing against `tables._truncate_cell`'s own
truncation rather than the raw value, and
`test_obs07_stats_drops_whole_lines_before_it_cuts_one`'s premise (a long
`cost_basis` forcing the whole-body overflow) doesn't hold any more —
written from the start as a presence check noting `T-V1110-STA-02` owns
the overflow case; (2) `/delete #<id>`'s two crash paths — a non-ASCII
decimal digit (`"²".isdigit()` is `True` but `int("²")` raises
`ValueError`) and an id past sqlite3's signed 64-bit `INTEGER` ceiling
(`OverflowError`) — built into `_handle_delete`'s first version
(`id_part.isascii() and id_part.isdigit()`, `_DELETE_MAX_ID`), so `bot.py`
never shipped without them. **Second review**, after gates 1-4 first went
green on that implementation, before the first commit: (3) the row_5b test
(`tests/test_v190_commands.py`, found by a file-by-file sweep, not by
advisor) needed its reply-mapping split for REQ-V1110-DOC-03, but renaming
it or re-parametrizing it would have silently dropped three ids from T0's
committed baseline node-id list (`docs/spec/task-briefs/v1110-T0-nodeids.txt`,
reconciled by T8's `comm -23` check, not this task's) — kept the original
name and the original single-`exc` parametrize (same
`[exc0]`/`[exc1]`/`[exc2]` ids), with a `type(exc) -> reply attribute`
lookup instead of a second parametrize column; (4) the two guards from (2)
had no dedicated regression-guard test — two cases added to
`T-V1110-DOC-03`, each confirmed to actually catch the regression by
temporarily reverting the guard, watching the new assertion fail, then
restoring it (their only "red," never through EC-02's own red-before-green
sequence, since the guarded code they test already existed and was
already correct — see `## Goal` above).

Separately, `tests/test_v1100_sanitization.py`'s
`test_t_v1100_out_03_split_message_used_only_inside_reply_parts` asserted
`reply_parts(` appears at 5+ call sites outside its own `def`; found by a
full, whole-suite `pytest -q` run (own initiative, not advisor-prompted).
Moving `/stats` and `/documents` off `reply_parts` onto the table path
drops that to 3 (`/status`, the agent-turn reply, `/summary`) — the floor
lowered to 3 with a comment explaining why, confirmed still true on the
live tree, not guessed.

Three further disclosures, not drift or a repair cycle, recorded in the
report's `## T2` section: README's `## Error behaviour` table still shows
the old "500,000 characters" wording and has no DOCX/PDF-pages rows (T5's
scope, not T2's, per T0's pin inventory) — README and the live bot
disagree on these three strings until T5 lands; no `/documents` sample
block existed in README before this task, so only the `## Commands` table
rows were updated, not a new sample; `/documents`' `#` column, pinned at
width 3 by the spec, truncates an id ≥1000 (e.g. `12…`) — a spec-level
property flagged for T7's reviewer, not changed here.
