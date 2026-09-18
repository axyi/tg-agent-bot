# Prompt 233 — v1.10.4 T5: version bump, uv lock, version tests, the paperwork

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task for the first of T5's
  two commits (version bump + paperwork); general-purpose subagent,
  briefed by file per §10.1/EC-03. The second (evidence) commit and the
  live gate sequence are commands-only, run by the orchestrator itself.
- **Harness:** Claude Code (background session, delegated subagent for
  commit one; orchestrator for the rest of T5)
- **Stage:** T5
- **Owner of (first commit only):** `pyproject.toml`, `uv.lock`,
  `tests/test_v195_version.py`, `tests/test_v1104_version.py` (new, or
  the version tests added to `tests/test_v1104_gates.py`), `README.md`
  (release table + gate-8 results table), `AGENTS.md` (count lines),
  `docs/reports/report-v1.10.4.md` (`## T5` version-bump part, provisional
  ledger row), `docs/reports/tg-post-v1.10.4.md` (provisional),
  `docs/llm-usage.md` (row 144)
- **REQ ids:** REQ-V1104-VER-01, REQ-V1104-RPT-01, REQ-V1104-RPT-02,
  REQ-V1104-RPT-03

## Goal

Bump the version to 1.10.4, regenerate `uv.lock` online, add the two new
version-identity tests (test-first, red before the bump, green after),
apply EC-02 rows 15-16, and land RPT-03's T5 paperwork (README's release
table and gate-8 results table, AGENTS.md's count lines) — all in one
commit, the first of T5's two. Full detail in
`docs/spec/task-briefs/v1104-T5.md`.

## Constraints

Test-first for `T-V1104-VER-02`, `T-V1104-DOC-02`, `T-V1104-DOC-04` —
each proven red before the corresponding edit, green after, both runs
recorded. No NG-01-listed instrument file touched. Only one commit this
task — the evidence commit is the orchestrator's, not yours. Gates 1-4
only — never `bot.py --selftest-live`, `devtools/rag_eval.py`,
`devtools/agent_eval.py`, or `devtools/mutation_check.py` this task.
`--no-verify` never used.

## Acceptance

The three named tests red-before/green-after with both runs recorded;
`uv.lock`'s diff is version-only; full pytest green, collection count
recorded; gates 1-4 green; report and tg-post written (provisional is
fine, but complete, no placeholder text).

## Stop

A need to touch any NG-01-listed file, or a version/dependency diff that
turns out not to be version-only, is a stop — report back rather than
improvising around it.
