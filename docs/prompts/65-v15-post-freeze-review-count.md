# Prompt 65 — spec-v1.5 post-freeze: T17 finding-count errata

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a factual-accuracy fix — the judgment call was
  tracing *why* the miscount happened (the reviewer's own closing line
  said "all five findings above," miscounting its own six-item output,
  and the report inherited that number instead of counting the
  enumerated list directly) so the note records real provenance, not
  just a corrected digit
- **Harness:** Claude Code
- **Stage:** post-freeze (after T19)
- **Owner of:** `docs/reports/report-v1.5.md` (Review section header,
  RLM table's T17 row, Deviations item 6, Bugs section's v1.4-precedent
  clause, Ledger row's Prompts cell), `docs/plan.md` (T17 finding
  count), `docs/llm-usage.md` (row 44), `docs/prompts/
  65-v15-post-freeze-review-count.md` (new) — evidence-only, no
  source/test/config file touched
- **REQ ids:** REQ-V15-REV-01, REQ-V12-REP-02

## Goal

Correct a real factual error, found by `advisor()`: the T17 review
returned **six** findings (4 🟡, 2 🟢), not five — the report's Review
section header, the RLM table's T17 row and `docs/plan.md` all say
"5"/"3 fixed, 2 waived," undercounting finding 4 (the undisclosed
`mutation_check.py` reformat, recorded as a Deviation, not fixed).

## Constraints

- No git history rewrite: commits `cd88b35` and `6fde12f` already say
  "five" in their messages — immutable, corrected here as errata, not
  amended.
- No source, test or config file touched.
- Do not touch the Ledger row's Bugs cell (14, already correct and
  final) — only the Prompts cell moves, to reflect this new prompt file.

## Acceptance

- The Review section header reads "6 findings (4 🟡, 2 🟢)", matching
  its own six enumerated items.
- The RLM table's T17 row reads "6 findings returned: 3 fixed and
  re-verified, 1 recorded as a Deviation, 2 waived."
- `docs/plan.md`'s T17 mention matches.
- An errata note records that `cd88b35`/`6fde12f`'s commit messages say
  "five" and why (the reviewer's own closing line miscounted its own
  output).
- `uv run --locked python devtools/checks.py lint-docs` exits 0.

## Stop

If tracing the miscount's provenance turned up a second, different
error, record it rather than silently fold it into this same count fix.
