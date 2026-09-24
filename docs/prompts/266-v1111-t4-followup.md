# Prompt 266 — v1.11.1 T4 follow-up: report completeness corrections

- **Date:** 2026-09-24
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only/artefacts-only orchestration; a
  self-disclosed documentation-completeness correction to T4's
  just-landed second commit, before T5 starts.
- **Harness:** Claude Code (background session)
- **Stage:** T4 (follow-up to prompt 262, commit `858cf22`)
- **Owner of:** this prompt file, `docs/reports/report-v1.11.1.md`,
  `docs/llm-usage.md` (row 176)
- **REQ ids:** REQ-V1111-EC-03, REQ-V1111-GATE-01

## Goal

Close five gaps in `858cf22`, all self-disclosed by the T4 subagent's
own post-commit `advisor` review of its finished report/prompt/usage
text (it had run `advisor` once, before drafting, not a second time to
verify the draft, per the brief's ask): (1) the "Pre-commit self-check"
section misrepresented its own history as fixing gaps in an existing
draft, when the single `advisor` call actually ran before any draft
existed — reworded to state plainly what happened; (2) the `AGENTS.md`
citation for the new Secrets paragraph, `:328`, corrected to `:330-334`
(verified via `grep -n RFC1918 AGENTS.md`); (3) `ruff format --check`'s
first-run result was understated as a clean `1 file already formatted`
pass, when the true first run said `1 file would be reformatted` and
needed `ruff format` to fix — disclosed, matching T3's own precedent
for disclosing a real formatting fix; (4) the `gitleaks-tree` table's
"same lag pattern as T0/T1/T2's own tables" claim corrected — T2 never
had its own table, `ebc2822`'s result landed inside T1's table instead,
which is the actual reason T3 needed a fresh table of its own. Also
disclosed as a clarification (not an error): the "line drift, cited →
actual" figures in T4's section were measured against the current tree
(`9d8dc0e`) rather than the base commit (`2431034`) the spec's
citations describe — checked directly against `2431034`, the spec's
citations are essentially exact; the apparent drift is explained by
T2's intervening edits, not spec staleness. And noted, not fixable: the
commit message's "before the edits landed" phrasing for the
`git stash` red-check is loose (the stash ran after the edits, to
revert them temporarily) — the evidence itself is genuine, only the
wording is imprecise, disclosed rather than rewritten (a history
rewrite would be more destructive).

## Constraints

Docs-only: `docs/reports/report-v1.11.1.md`, `docs/llm-usage.md`, this
prompt file. No source, test or config file touched. Same `.env`/`data/`
boundary as every other prompt this run.

## Acceptance

All five gaps closed (four corrections plus the clarification and the
disclosed-not-fixable note); `checks._lint_report_delegation` run
directly against `docs/reports/report-v1.11.1.md` still returns `[]`;
gates 1–4 (`uv sync --locked`, `uv run --locked ruff check .`,
`uv run --locked pytest`, `uv run --locked python bot.py --selftest`)
and `uv run --locked python devtools/checks.py lint-docs` all exit 0;
the standalone `gitleaks-tree` block run against this commit, exit 0,
recorded.

## Stop

None triggered — a documentation correction, not a repair cycle against
a red gate.
