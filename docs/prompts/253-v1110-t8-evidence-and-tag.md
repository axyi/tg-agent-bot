# Prompt 253 — v1.11.0 T8: fresh gates, identity check, evidence commit, tag

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only orchestration (T8's own §14.1
  exemption: *artefacts only* for the evidence commit) — no delegation.
- **Harness:** Claude Code (background session, orchestrator)
- **Stage:** T8 (final)
- **Owner of:** `docs/llm-usage.md` (row 164), `docs/reports/report-v1.11.0.md`
  (final sections), `docs/reports/tg-post-v1.11.0.md`,
  `docs/prompts/253-v1110-t8-evidence-and-tag.md`
- **REQ ids:** REQ-V1110-VER-01, REQ-V1110-VER-03, REQ-V1110-REV-02

## Goal

On `44c34b0` (T8's bump + README-fix commits): re-run gates 1-6 fresh
plus gate 5 (no live tokens spent); run the gate 7/8 dependency-identity
check against `tested_tree=2c3c5aa` (T7's fix commit, where gate 8 last
ran); run the node-id floor check (EC-03(b)); run `checks.py replay
--range 295b01f..HEAD`; explicitly re-run Appendix B's fourteen
scenarios' implementing tests; finalize the report's Operator inputs,
Gate-8 attempt log, `tg-post-v1.11.0.md` and Ledger row; make the
evidence-only commit; create the local annotated tag `v1.11.0`.

## Constraints

Gates 6/7/8 never overlap with each other or any other gate (EC-07) —
gate 6 ran alone, nothing else touching the tree. Gates 7 and 8
themselves are **not rerun** — the identity check's `True` verdict
reuses T7's results. The evidence commit touches only
`docs/llm-usage.md`, this prompt file, `docs/reports/report-v1.11.0.md`
and `docs/reports/tg-post-v1.11.0.md` (the precedent set by
`6532d4c`, v1.10.4's own evidence commit — "`docs/reports/*` and
nothing else" is interpreted the same way that commit did: the report,
the tg-post, the usage row and the prompt log, no source/test/config
file). `--no-verify` never used.

## Acceptance

Gates 1-5 green (`pytest` 2381/2381, `selftest-live` all-green with
disclosed `lmstudio SKIP`). Gate 6 fresh: 152/152 killed, `W`=965.2s.
`doctor`/`lint-docs` green. Identity check:
`dependency_diff_is_version_only` over `git diff tested_tree HEAD --
$(agent_eval.py --print-dependencies)` is `True` — gates 7/8 reused, not
rerun. Node-id check: exactly the two declared renames missing, nothing
else. `replay --range 295b01f..HEAD`: 24/24 clean. Appendix B: 73/73
`tests/test_v1110_*.py` tests green, all 14 scenarios covered. Final
collected count 2384 ≥ floor(2311)+62. `git status -sb` shows `ahead`
after the evidence commit; `git tag -l v1.11.0` non-empty; **no push**.

## Stop

Not applicable — every check passed; the run completes successfully.
