# Prompt 137 — v180 T8 erratum 4: repoint the stale RPT self-check test

- **Date:** 2026-09-10
- **Executor model:** claude-sonnet-5
- **Model reason:** small, single-file, single-edit fix; orchestrator
  context, no delegation needed (under every `AGENTS.md` Context
  discipline threshold).
- **Harness:** Claude Code
- **Stage:** T8 (post-review gate run), disclosed erratum 4
- **Owner of:** `tests/test_v170_bench.py`
- **REQ ids:** REQ-V180-RPT-01

## Goal

T8's full `pytest` run (inside commit `934daec`'s own gate check) surfaced
one pre-existing failure:
`tests/test_v170_bench.py::test_t_v170_rpt_02_lint_docs_repointed_to_this_release`
hard-asserted `lint-docs.report_path == "docs/reports/report-v1.7.0.md"`.
T7 (commit `a3efd24`) correctly repointed that config value to
`report-v1.8.0.md` per REQ-V180-RPT-01, which this v1.7.0-named
self-check test never anticipated — a structurally unavoidable
consequence of every release's own repoint requirement, not a defect in
T7's change. Operator-authorized (session transcript, this run) to rename
the test to `test_t_v180_rpt_01_lint_docs_repointed_to_this_release` and
update its assertion to the current release's path, mirroring this run's
earlier erratum 1 disposition for an analogous EC-03-list gap.

## Constraints

Only `tests/test_v170_bench.py`, only this one test function. No other
file, no source change.

## Acceptance

`uv run --locked pytest tests/test_v170_bench.py -k rpt_01` passes. Full
suite stays green.

## Stop

N/A — completed in one step.
