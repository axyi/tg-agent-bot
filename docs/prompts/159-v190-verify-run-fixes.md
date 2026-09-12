# Prompt 159 — v190 post-run: /verify-run documentation fixes

- **Date:** 2026-09-12
- **Executor model:** claude-opus-5
- **Model reason:** lab-session orchestrator work closing post-run
  verification findings; *artefacts only* per `standards/workflow.md` §5.1
  (three documentation files, no source, test or config file touched).
- **Harness:** Claude Code
- **Stage:** post-run (after T13, after the `v1.9.0` tag)
- **Owner of:** `docs/prompts/159-v190-verify-run-fixes.md`,
  `docs/llm-usage.md`, `docs/reports/report-v1.9.0.md` (RPT-02 item 4
  line, Per-task delegation record, Ledger row section)
- **REQ ids:** REQ-V190-EC-07 item 6, REQ-V190-RPT-02 items 4 and 13

## Goal

`/verify-run` against the closed v1.9.0 run returned **FAIL on 3 of 8**
checklist items. One of the three (item 1, gate 7 red) is the disclosed,
operator-accepted known limitation and is not a documentation defect —
it carries into v1.10.0's scope, not into this prompt. The other two are
documentation-only and are closed here and in the lab-repo commit that
follows:

1. **The Per-task delegation record is incomplete and one row is wrong.**
   `REQ-V190-EC-07` item 6 requires a row per task. The table covers
   **T0–T11 only — 12 of 14 tasks**; T12 and T13 have no row at all, and
   the "(Filled in as each task lands.)" caretaker line is still present
   on a table that has stopped being filled in. Add the two missing rows
   (T12 delegated — `docs/spec/task-briefs/v190-T12.md`, prompt 158,
   `docs/llm-usage.md` row 68 all corroborate it; T13 *artefacts only*,
   the exemption already stated correctly in prose at RPT-02 item 4's
   neighbourhood) and drop the caretaker line.

   **T9's row is the substantive one.** It reads "matched map", but the
   report's own T9 section records that after the implementing subagent's
   session hit an account-wide 429, the orchestrator finished the task
   **directly in main context** — and commit `7bc7121` shows that work
   wrote `devtools/mutation_check.py`, `config/quality_gates.yaml` and
   `tests/test_v15_standards.py`: files `ruff` and `pytest` run. That is
   §5.1's third trigger (*a task that writes source files*), and the
   reason given — "bounded, mostly-command remaining work" — is a
   paraphrase, not one of the four closed-list exemptions. The honest
   record is a **deviation**, not a match. It is written down as one.
   It is NOT to be rephrased into an exemption it does not meet: T5's
   row, by contrast, names "a single edit under every threshold
   (EC-07's fourth exemption)" verbatim and is clean, and the difference
   between the two rows is exactly what this record exists to preserve.

2. **RPT-02 item 4 overstates the task-brief files.** The line claims
   briefs `v190-T1.md` **through** `v190-T12.md`. `v190-T11.md` does not
   exist on disk and `git log --all -- docs/spec/task-briefs/v190-T11.md`
   is empty — it never existed. The claim is not a lost file: T11's
   delegation was the `code-reviewer` clean-context review, which is
   driven by the diff and this project's reviewer agent definition, not
   by a task-brief file. Correct the range to what was actually written
   and say why T11 is absent.

3. **The report's Ledger row is a `so far` snapshot.** Its `Prompts` cell
   reads "18 so far (141–158…)". The run is 141–**159** once this prompt
   lands, exactly as v1.8.0's prompt 140 closed 126–140. De-snapshot it
   and name this prompt's role, then paste the row into the lab's
   `economics.md` — which is a lab-repo commit and not part of this
   prompt.

## Constraints

- Documentation only: `docs/prompts/`, `docs/llm-usage.md`, and three
  sections of `docs/reports/report-v1.9.0.md`. No source, test or config
  file, no version bump, no new tag.
- The tag `v1.9.0` stays where it is. This commit lands after it, exactly
  as v1.8.0's prompt 140 and v1.7.0's prompt 124 did.
- The row pasted into `economics.md` is byte-identical to the report's
  Ledger row section — the two must not diverge.
- Gate 7's red exit is recorded as red. No waiver text is added to make
  it read otherwise; the operator decision that accepts it already exists
  at its own section and is not restated here.
- Never `--no-verify`.

## Acceptance

- `docs/llm-usage.md` has a row for every prompt of the run, 141 through
  159, with no gap.
- The report's Per-task delegation record has a row for all fourteen
  tasks T0–T13, carries no "(Filled in as each task lands.)" caretaker
  line, states T9 as a deviation rather than a match, and closes with the
  counts `11 delegated / 2 exempt / 1 unexplained`.
- RPT-02 item 4 names the eleven brief files that exist and says why T11
  has none.
- The report's Ledger row has `Ver` = `v1.9.0`, no provisional wording in
  its preamble, and a `Prompts` cell reading `19 (141–159; ...)`.
- The row pasted into the lab's `economics.md` is byte-identical to that
  section.
- `uv run --locked python devtools/checks.py lint-docs` exits 0.
- `ruff check .` and `pytest` still exit 0 — unchanged, since no source
  was touched.

## Stop

If any gate goes red on a documentation-only change, stop and report: that
would mean a doc gate binds something this prompt did not intend to change.

Gate 7 (`rag_eval.py`) is expected to stay red at its known limitation and
is out of this prompt's scope — do not "fix" it here and do not soften the
report's record of it.
