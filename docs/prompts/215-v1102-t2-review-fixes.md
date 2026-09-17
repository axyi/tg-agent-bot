# Prompt 215 — v1.10.2 T2 review fixes: RUN-06 prefix/table, cross-step pin

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** same delegated implementation task as prompt 214,
  closing an advisor review's findings before handback.
- **Harness:** Claude Code (background session, subagent)
- **Stage:** T2
- **Owner of:** `tests/test_v1102_runner.py`, `tests/test_v1102_red_team.py`
- **REQ ids:** REQ-V1102-RT-03, REQ-V1102-RT-05

## Goal

An advisor review of prompt 214's commit (`e8bbe38`) found `T-V1102-RUN-06`
built against `_run_level2_cases`'s raw output rather than the real
`gate-8: `-prefixed stdout `main()`/`run()` produce, and asserted pairing
counts rather than reconstructing the per-case table the brief names
(verdict, joined clause detail, the `tools` cell as the printed
representation, `n/a` for non-injection cases). It also found two brief-
mandated code paths with no direct test: the outcome-kind branch's own
`CASE`/`TOOLS`/legacy-`FAIL` lines (Part B4 step 2 names this branch
explicitly, alongside the checker branch already covered), and the
`CASE ... FAIL (e)` + `TOOLS ... -- none` shape a cross-step accumulation
produces (an exec call on an earlier *unchecked* step still fails clause
(e) on a later checked step, whose own `TOOLS` line is legitimately empty)
-- an easily-misread shape worth pinning before T5/T6 read this table.
This prompt closes all three, plus two report-quality nits: a second
explicit positive fixture for HAL-03's widened `any_of[-1]`, and an unused
`registered_secrets` fixture + `import config` left over in
`tests/test_v1102_red_team.py` from an earlier draft.

## Constraints

Test-only; no production code touched (the review confirmed
`devtools/agent_eval.py` and `evals/agent/red_team.json` need no change).
Offline only.

## Acceptance

`tests/test_v1102_runner.py::test_t_v1102_run_06_full_committed_dataset_case_tools_pairing`
now drives real `ae.run()` output (`gate-8: `-prefixed) through a genuine
table-reconstruction parser. Two new tests
(`test_t_v1102_run_02_outcome_kind_branch_also_prints_case_and_tools`,
`test_t_v1102_run_02_case_fails_e_while_its_own_tools_line_shows_none`)
pin the two previously-untested code paths. Full offline suite green
(2154 tests, 1 pre-existing skip, no test deleted), `ruff check .` and
`ruff format --check .` clean, `bot.py --selftest` green.

## Stop

None triggered; this was a bounded, fully-scoped fix-up with no new
production-behaviour risk.
