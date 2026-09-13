# Prompt 180 — v1.9.3 T4: version bump, paperwork, authoritative gates, tag

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded, well-specified patch-closing task against an
  existing task brief (`docs/spec/task-briefs/v193-T4.md`) — a version
  literal, count-bearing documentation, and release paperwork; no open-ended
  design decision, no logic change.
- **Harness:** Claude Code
- **Stage:** v1.9.3 T4 (patch, no new spec file — precedent v1.9.2 T3)
- **Owner of:** `pyproject.toml`, `uv.lock`, `tests/test_v193_version.py`,
  `tests/test_v192_version.py`, `tests/test_v190_agents.py`,
  `tests/test_v170_bench.py`, `config/quality_gates.yaml`, `AGENTS.md`,
  `README.md`, `docs/reports/report-v1.9.3.md`,
  `docs/reports/tg-post-v1.9.3.md`, `docs/llm-usage.md`
- **REQ ids:** REQ-V190-VER-01 (patch-release convention), REQ-V190-EC-03,
  REQ-V190-RPT-01, REQ-V190-RPT-02, REQ-V190-RPT-03

## Goal

Close the v1.9.3 patch: `pyproject.toml`'s `project.version` moves
`1.9.2` → `1.9.3`, `uv.lock` regenerated to match, and
`tests/test_v193_version.py` proves it (`T-V193-VER-01`, red before the
bump — `AssertionError: assert '1.9.2' == '1.9.3'` — then green after).
Following this repo's established version-pin convention exactly:
`tests/test_v192_version.py` is repointed to the frozen `v1.9.2` git-tag
blob (the same treatment `tests/test_v180_version.py`, `tests/test_v190_version.py`
and `tests/test_v191_version.py` received at their own retirement), never
deleted, per REQ-V190-EC-03. `AGENTS.md`'s gate-3/gate-6 count-bearing
lines, the README release table, and the two `report_path` pinning tests
(`tests/test_v190_agents.py`, `tests/test_v170_bench.py`) move to the
release's real, final numbers, measured after every other edit in this
task: 1610 tests, 114 mutation entries.
`docs/reports/report-v1.9.3.md` (T1/T2/T3 wrote their own sections) is
finished with the consolidated seven-gate table, the gate-6 before/after
wall chain, the per-task delegation record with executor models and
commit hashes, a Disclosures section, an Open tail section, and the
Ledger row. `docs/reports/tg-post-v1.9.3.md` and `docs/llm-usage.md` row
90 close the reporting. All seven gates run verbatim, in order, on the
final tree, gate 6 and gate 7 never concurrent and nothing else running
on the box during gate 6; only then the annotated tag `v1.9.3`.

## Constraints

- One prompt → one commit: this is prompt 180.
- No logic changes — version, tracking documentation, and paperwork only.
- `docs/reports/report-v1.9.0.md`, `report-v1.9.1.md` and `report-v1.9.2.md`
  stay untouched.
- `.env` is never read, printed or committed; `data/`, `evals/rag/corpus`
  never opened. Never `--no-verify`. Do not push.

## Acceptance

All seven gates from `AGENTS.md` exit 0, on the final tree, in order:
`uv sync --locked`, `uv run --locked ruff check .`,
`uv run --locked pytest`, `uv run --locked python bot.py --selftest`,
`uv run --locked python bot.py --selftest-live`,
`uv run --locked python devtools/mutation_check.py`,
`uv run --locked python devtools/rag_eval.py`. Evidence recorded in
`docs/reports/report-v1.9.3.md`. Annotated tag `v1.9.3` created on the
release commit once all seven are green.

## Stop

If a gate fails for a reason that needs a code change, or gate 5/7 fails
for an environment reason, or gate 6 times out or reports a survivor —
stop and report rather than fixing it inside a version-bump commit.
