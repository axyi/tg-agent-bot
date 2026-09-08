# Prompt 122 — spec-v1.7.0: T13 provisional report closure

- **Date:** 2026-09-08
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T13 (provisional report + tg-post + usage rows)
- **Owner of:** `docs/reports/report-v1.7.0.md`, `docs/reports/tg-post-v1.7.0.md`
  (new), `docs/llm-usage.md`, `docs/prompts/122-v170-t13-report-closure.md`
  (new)
- **REQ ids:** REQ-V170-RPT-03, REQ-V170-RPT-04

## Goal

Close the REQ-V170-RPT-03 items the per-task sections (T0–T12) did not
already carry to completion: the three running sections (Benchmark-affecting
changes, RLM delegation record, Deviations) that stopped updating at T0/T7;
the consolidated gates table, mutation summary, scanner summary and fix-cycle
count (items 1, 3, 11, 12); the measured test count before/after against the
1016 floor (item 2); the intended-tag statement on the cost-gate-FAIL branch
(item 10); the Ledger row. Then write `docs/reports/tg-post-v1.7.0.md` per
REQ-V170-RPT-04 and append the remaining `docs/llm-usage.md` rows.

## Constraints

- Documentation-only: no source, test or config file touched.
- No re-run of any gate whose result is unchanged since T12's own clean run
  (nothing source-relevant changed between T12's tip and this prompt) —
  cite T12's recorded results rather than re-executing them.
- Item 4 (tip `sha256`, `<implementation-tip>`, `replay --range` output)
  stays open, explicitly, for T14's evidence-only commit — not fabricated
  here.
- The fix-cycle count (item 12) is derived from REQ-V170-EC-01's own
  definition ("one cycle = one fix + a complete run of all gates from the
  first"), not from an informal count of every self-caught issue.

## Acceptance

- `uv run --locked python devtools/checks.py lint-docs` exits 0.
- `docs/reports/report-v1.7.0.md` carries all thirteen REQ-V170-RPT-03 items,
  item 4 explicitly marked open for T14.
- `docs/reports/tg-post-v1.7.0.md` exists, Russian, under 1500 characters by
  `wc -m` (the report quotes the count), names the executor model, links
  `https://github.com/axyi/tg-agent-bot`.
- `docs/llm-usage.md`'s table carries a row for every prompt through 122.

## Stop

None.
