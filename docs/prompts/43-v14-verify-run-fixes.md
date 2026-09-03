# Prompt 43 — v1.4 verify-run docs fixes

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** docs-only fixes from /verify-run; no code, no design
- **Harness:** Claude Code
- **Stage:** docs
- **Owner of:** `docs/prompts/40-v14-t9-review.md` (`Model reason` bullet
  added), `docs/reports/report-v1.4.md` (three inaccuracies fixed in
  place), `docs/llm-usage.md` (row 36), `docs/prompts/43-v14-verify-run-fixes.md`
  (new)
- **REQ ids:** AGENTS.md § Reporting; `standards/reporting.md` § Prompt chain

First prompt file in this project written in the lab's four-block body
format (`## Goal` / `## Constraints` / `## Acceptance` / `## Stop`)
rather than the free-form prose sections (most commonly "Brief as
sent") used by earlier prompt files in this project; the bullet-style
header above is unchanged.

## Goal

Fix three docs inaccuracies surfaced by `/verify-run`'s audit of the
spec-v1.4 run — prompt 40 missing its required `Model reason` bullet;
`report-v1.4.md`'s stale commit-count line, an overstated
`llm-usage.md` row range, and a missing ready-to-paste `economics.md`
ledger row in the Deferred-conflict section — and log this fix pass
itself.

## Constraints

- Docs only: `docs/spec/` is untouched (another task is writing a new
  spec there concurrently); no `.py` file is touched; no secret values,
  `.env`, or `data/` are read.
- `report-v1.4.md`: correct the three findings in place, do not
  restructure the report.
- Prompt 40's new bullet must be truthful, one line, in the header's
  canonical position (Date / Executor model / **Model reason** / …),
  matching prompt 39's shape.
- One prompt → one commit, referencing this file per `AGENTS.md`'s
  commit-format rule.

## Acceptance

- `docs/prompts/40-v14-t9-review.md` carries a `- **Model reason:**`
  bullet right after `Executor model`.
- `report-v1.4.md`'s gate-table line reads "9→11 commit count", matching
  the already-correct "9→11" sentence elsewhere in the report (`git log
  --oneline 3bc8e8b..HEAD | wc -l` → 11).
- `report-v1.4.md`'s Deferred-conflict paragraph says "rows 34–35" (not
  "33–42") — `git diff 3bc8e8b..HEAD -- docs/llm-usage.md` shows only
  rows 34 and 35 were added by this run — and now carries a fenced,
  ready-to-paste `economics.md` row plus one sentence noting the lab
  applied it as commit `3c12cc9` and that future run reports MUST carry
  this row.
- `docs/llm-usage.md` has a new row (36) for this prompt, tokens marked
  `unknown`, model `claude-sonnet-5`.
- `git status --short` shows only docs files touched; exactly one commit
  is created.

## Stop

Do not run the six-gate block — docs-only change, and another agent is
using this tree. Do not touch `docs/spec/` or any `.py` file. Do not
push. If any of the three `report-v1.4.md` findings turns out to
already match the git evidence on inspection, leave it unedited and say
so rather than editing for the sake of editing.
