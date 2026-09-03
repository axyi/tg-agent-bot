# Prompt 42 — v1.4 T10: advisor follow-up (report/ledger corrections)

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** continues the run's pinned model (prompt 31); a
  docs-only correction pass over the just-completed report, driven by
  `advisor()`'s review of the T10 deliverable, no new production code.
- **Harness:** Claude Code CLI
- **Stage:** report (correction)
- **Owner of:** `docs/reports/report-v1.4.md`, `docs/plan.md`,
  `docs/llm-usage.md`, `docs/prompts/42-v14-t10-advisor-followup.md` (new)
- **REQ ids:** REQ-V14-RPT-01 item 6 (fix cycles, a MUST element), RPT-04
  (errata evidence), RPT-05/RPT-07 (commit count)

## Advisor checkpoint

Consulted after committing `64aa5da` (T10's report/post/errata/ledger).
Four points raised, all acted on:

1. **Fix cycles missing from the report** — RPT-01 item 6 is a MUST
   element; the report only carried Appendix-B's negative ("no fix
   cycles consumed by Appendix-B execution"), not the two real
   fix-and-rerun events elsewhere in the run (T6's
   `tests/test_v1_guardrails.py` collision, T9's `v14-ben-03-...` first
   mutation attempt surviving). Re-read `docs/prompts/37-…`/`39-…` to
   confirm both happened inside an already-started formal six-gate run
   (not pre-gate test-first development, which `docs/plan.md`'s rule
   exempts) — both debit the budget. Added a "Fix cycles" section: 2 of
   5 consumed.
2. **Two verifications asserted but never executed** — the errata
   preamble's "`git diff --stat` confirms... starts at row 33" and E2's
   "`ls … | grep -c v13` would count 21 files" were both written in the
   conditional/unverified mood. Ran both for real:
   `git diff 3bc8e8b..HEAD -- docs/llm-usage.md` (row 33 unmodified
   context, first added line is row 34 — the preamble's "starts at row
   33" was itself imprecise, corrected to "row 34") and
   `ls docs/prompts/09-*.md docs/prompts/1[0-9]-*.md
   docs/prompts/2[0-9]-*.md | grep -v "v14\|3[0-9]-" | wc -l` → **21**,
   confirmed. Both rewritten to assertive mood citing the executed command.
3. **Commit count off by one** — `git log --oneline 3bc8e8b..HEAD` is
   **10**, not the 9 that `docs/plan.md` (two places) and
   `docs/llm-usage.md` (one place) stated. Corrected all three, and
   `llm-usage.md`'s hash list now names the tenth (`64aa5da`) explicitly
   instead of "plus this report... commit" (written before that commit
   existed). Also softened "six gates green throughout" to "six gates
   green at every commit" plus an explicit fix-cycle count, since T6/T9
   needed a fix within the gate sequence — "throughout" without
   qualification could read as "never failed once."
4. **Preconditions deviation 4 was stale** — still read "flagged for T10
   … not yet a blocker" after T10 had already resolved it (the
   "Deferred conflict, resolved" section). Added a forward pointer.

## Gates

All six, run sequentially, gate 6 alone, since this docs-only commit
becomes the new final tree (GATE-01's "and on the final tree" clause
applies regardless of the change being documentation-only, because it is
the tree the run ends on). Results: report's Gates table, final row.
