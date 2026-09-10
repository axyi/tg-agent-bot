# Prompt 139 — v180 T10: final acceptance

- **Date:** 2026-09-10
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only orchestrator work (REQ-V180-REV-02);
  no delegation needed (T10 is *artefacts only* per §12.1).
- **Harness:** Claude Code
- **Stage:** T10
- **Owner of:** `docs/reports/report-v1.8.0.md` (the evidence-only commit
  that follows this one)
- **REQ ids:** REQ-V180-REV-02

## Goal

Final acceptance: re-run the six gates verbatim against `<implementation-
tip>` (`30207af`, T9's commit; gate 5 needed one more GPU-box re-pin,
`192.168.0.145` → `172.16.50.233`), `checks.py run --profile full --since
<base>`, `checks.py replay --range <base>..<implementation-tip>`, and
Appendix B (driven by the already-green automated suite, per REQ-12-REP-02).
All green. Land one evidence-only commit touching `docs/reports/*` and
nothing else, then re-run `lint-docs` and `gitleaks-tree` against it, and,
both green, create the annotated tag `v1.8.0` on that commit.

## Constraints

The evidence-only commit touches `docs/reports/report-v1.8.0.md` only —
no source, test or config file. This prompt file is its own, separate
commit (docs/prompts/ is not docs/reports/).

## Acceptance

Six gates: 0 exit each, mutation 98/98. Full profile: 15/15. Replay:
12/12 (then 13/13 once this prompt's own commit joins the range). Appendix
B: 14/14. Post-commit `lint-docs` and `gitleaks-tree`: both green, only
then the tag.

## Stop

A red gate here would stop the run under REQ-V180-REV-04 — not reached;
every gate was green.
