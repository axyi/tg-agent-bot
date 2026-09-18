# Prompt 229 — v1.10.4 T1: the frozen-pin rewrites and repoints

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (test-first rewrite of
  16 existing test sites plus two new test files); general-purpose
  subagent, briefed by file per §10.1/EC-03.
- **Harness:** Claude Code (background session, delegated subagent)
- **Stage:** T1
- **Owner of:** `tests/test_v1104_gates.py` (new), `tests/test_v1104_docs.py`
  (new), the 16 amendment-table sites (rows 1-14, 12b) across
  `tests/test_v1100_gates.py`, `tests/test_v1101_gates.py`,
  `tests/test_v1102_gates.py`, `tests/test_v1102_docs.py`,
  `tests/test_v1103_gates.py`, `tests/test_v1103_docs.py`,
  `tests/test_v170_bench.py`, `tests/test_v190_agents.py`,
  `tests/test_v15_standards.py`; `README.md` (v1.10.3 release row);
  `AGENTS.md:95`; `config/quality_gates.yaml` (`report_path`, gate-matrix
  cite); `docs/reports/report-v1.10.4.md` (`## T1` section)
- **REQ ids:** REQ-V1104-PIN-01, REQ-V1104-PIN-02, REQ-V1104-VER-01 (the
  v1.10.3 row), REQ-V1104-RPT-03 (T1 part), REQ-V1104-GATE-02 (the gate
  matrix repoint)

## Goal

Rewrite every frozen-list test pin that would stop the next release the
way v1.10.3's own unlisted pin stopped it — 15 sites (rows 1-14 plus
12b) rewritten from "ends here" / "no later row" assertions to
presence-contiguity-order assertions, plus the release-agnostic "is now"
anchor and the narrowed mutation-all comment-block helper. Add the
v1.10.3 release row to README's release table. Repoint `report_path`,
the brief-path token, and the gate-matrix parse target to this release.
Full detail in `docs/spec/task-briefs/v1104-T1.md`.

## Constraints

Test-first: write `tests/test_v1104_gates.py` and
`tests/test_v1104_docs.py`, watch them fail for the right reason, then
apply the rewrites. No production or evaluation-instrument source file
touched (NG-01). No "no later row" or "nothing follows" assertion may
survive in `tests/` after this task (NG-10). Gates 1-4 only — never
`bot.py --selftest-live`, `devtools/rag_eval.py`,
`devtools/agent_eval.py`, or `devtools/mutation_check.py` this task.
`--no-verify` never used.

## Acceptance

All 16 rewritten sites match the amendment table's shape; the two new
test files' ids all pass; `uv run --locked pytest -q` green, collection
≥ 2285 + new tests, no test deleted; `lint-docs` green against
`docs/reports/report-v1.10.4.md`; gates 1-4 green.

## Stop

A rewrite whose target site does not match the amendment table's stated
`file:line` (line drift beyond the amendment table's own tolerance) is a
disclosed EC-02 amendment in the report, not a blocker — record it and
continue. A test that cannot be made to pass without touching a
NG-01-listed instrument file is a stop: report back instead of widening
scope.
