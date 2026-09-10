# Prompt 140 — v180 post-run: /verify-run documentation fixes

- **Date:** 2026-09-10
- **Executor model:** claude-opus-5
- **Model reason:** lab-session orchestrator work closing a post-run
  verification finding; *artefacts only* per `standards/workflow.md` §5.1
  (three documentation files, no source, test or config file touched).
- **Harness:** Claude Code
- **Stage:** post-run (after T10, after the `v1.8.0` tag)
- **Owner of:** `docs/prompts/140-v180-verify-run-fixes.md`,
  `docs/llm-usage.md`, `docs/reports/report-v1.8.0.md` (Ledger row
  section), `AGENTS.md` (Gates section test count)
- **REQ ids:** REQ-V180-RPT-04

## Goal

Close the two `REQ-V180-RPT-04` violations that `/verify-run` raised against
the closed v1.8.0 run. Both are documentation-only:

1. **No `docs/llm-usage.md` row for prompt 139.** RPT-04 requires a row per
   prompt of the run. Rows 63 and 64 cover prompts 126 and 127–138; prompt
   139 (T10, final acceptance, commits `465c4d9` and `ee09c4d`) has none.
   This is the same failure the file already records for v1.7.0's prompt 125
   in row 62, where it is named as "a gap `/verify-run` item 3 would have
   raised on the next run" — it recurred one run later. Add row 65 for
   prompt 139 and row 66 for this prompt.
2. **The report's Ledger row is still provisional.** RPT-04 requires the
   "Ledger row (paste into `economics.md`)" section to carry `Ver` = the
   released version with **no provisional cell**; the row still reads
   `1.8.0 (T9 provisional; tag pending T10)` although T10 completed and the
   `v1.8.0` tag exists on `ee09c4d`. De-provisionalise it, correct the
   `Prompts` cell (the run is 126–140, not 127–138), and lead the `First
   run` cell with the `✅ yes` / `❌ no` verdict the ledger column uses in
   every other row.

3. **`AGENTS.md`'s stated test count is a mid-run snapshot.** The Gates
   section reads "gate 3, `pytest`, is 1217 tests as of spec-v1.8.0 T8".
   T7 wrote that number, and T8's erratum-4 rename and T9's version test
   added three more after it; the shipped release collects **1220**, which
   is what the report itself records under RPT-02 item 2. Not false as an
   as-of statement, but it is the gate documentation a future reader sizes
   gate 3 against, so it tracks the release, not the task that happened to
   touch it last. Found while verifying, not raised by the checklist —
   item 1 only records exit codes.

The corrected row is then pasted into the lab's `economics.md`, which is a
lab-repo commit and not part of this prompt.

## Constraints

- Documentation only: `docs/prompts/`, `docs/llm-usage.md`, the Ledger
  row section of `docs/reports/report-v1.8.0.md`, and one number in
  `AGENTS.md`. No source, test or config file, no version bump, no new
  tag.
- The tag `v1.8.0` stays on `ee09c4d`. This commit lands after it, exactly
  as v1.7.0's prompt 124 did.
- The row pasted into `economics.md` is byte-identical to the report's
  Ledger row section — the two must not diverge.
- Never `--no-verify`.

## Acceptance

- `docs/llm-usage.md` has a row for every prompt of the run, 126 through
  140, with no gap.
- The report's Ledger row has `Ver` = `v1.8.0`, no provisional cell, a
  `Prompts` cell reading `15 (126–140; ...)`, and a `First run` cell leading
  with `✅ yes`.
- `AGENTS.md`'s Gates section states 1220, matching
  `pytest --collect-only` on the tagged tree.
- `uv run --locked python devtools/checks.py lint-docs` exits 0.
- `ruff check .` and `pytest` still exit 0 — unchanged, since no source
  was touched.

## Stop

If any gate goes red on a documentation-only change, stop and report: that
would mean a doc gate binds something this prompt did not intend to change.
