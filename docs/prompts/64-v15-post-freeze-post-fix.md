# Prompt 64 — spec-v1.5 post-freeze: prompt-reference correction

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a straightforward process-compliance fix — the
  judgment call was recognising, from an `advisor()` call after
  believing the run done, that `346a67b` (the `tg-post-v1.5.md`
  correction) had reused prompt 63's reference rather than getting its
  own, matching this repository's own v1.4 precedent
  (`42-v14-t10-advisor-followup.md`, `43-v14-verify-run-fixes.md`, each
  a post-freeze correction commit with its own dedicated prompt) for
  how to close it
- **Harness:** Claude Code
- **Stage:** post-freeze (after T19)
- **Owner of:** `docs/reports/report-v1.5.md` (Deviations item 6,
  Ledger row's Prompts/Bugs cells), `docs/llm-usage.md` (row 43),
  `docs/prompts/64-v15-post-freeze-post-fix.md` (new) — evidence-only,
  no source/test/config file touched
- **REQ ids:** AGENTS.md's "one prompt → one commit" rule

## Goal

Fix `346a67b`'s commit message, which cited
`docs/prompts/63-v15-t19-acceptance.md` — T19's own prompt, not a
prompt describing that commit's actual work (the `tg-post-v1.5.md`
number correction) — by giving that correction its own dedicated
prompt file in this new commit, and recording the mismatch as a
Deviation rather than silently re-counting as if it never happened.

## Constraints

- No git history rewrite: `346a67b` is not amended (a pushed,
  hook-verified commit; the fix is a forward correction, not a
  retroactive one).
- No source, test or config file touched — this correction is itself
  bound by the same evidence-only scope REQ-V15-ACC-03 permits.

## Acceptance

- `docs/reports/report-v1.5.md`'s Deviations section names the
  mismatch and this fix.
- The Ledger row's Prompts cell counts 21 files (44–64) and its Bugs
  cell grows to 14 (the two found this pass: `tg-post-v1.5.md`'s
  staleness, and `346a67b`'s prompt-reference mismatch).
- `uv run --locked python devtools/checks.py lint-docs` exits 0.
- Commit-msg checks and the pre-commit profile run live through this
  commit's own hooks.

## Stop

If closing this mismatch required amending or reordering existing
commits, stop and record the deviation instead — a git history rewrite
is out of scope for a documentation correction.
