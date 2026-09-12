# Prompt 162 — v1.9.1 T2: version bump, paperwork, gates, tag

- **Date:** 2026-09-12
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded, well-specified patch-closing task against an
  existing task brief (`docs/spec/task-briefs/v191-T2.md`) — a version
  literal, documentation that tracks it, and release paperwork; no open-ended
  design decision, no logic change.
- **Harness:** Claude Code
- **Stage:** v1.9.1 T2 (patch, no new spec file — precedent v1.5.1)
- **Owner of:** `pyproject.toml`, `uv.lock`, `tests/test_v191_version.py`,
  `tests/test_v190_version.py`, `tests/test_v190_agents.py`,
  `tests/test_v170_bench.py`, `config/quality_gates.yaml`, `AGENTS.md`,
  `README.md`, `docs/reports/report-v1.9.1.md`,
  `docs/reports/tg-post-v1.9.1.md`, `docs/llm-usage.md`
- **REQ ids:** REQ-V190-VER-01 (patch-release convention), REQ-V190-EC-03,
  REQ-V190-RPT-01, REQ-V190-RPT-02, REQ-V190-RPT-03

## Goal

Close the v1.9.1 patch: `pyproject.toml`'s `project.version` moves
`1.9.0` → `1.9.1`, `uv.lock` regenerated to match, and
`tests/test_v191_version.py` proves it (`T-V191-VER-01`, red before the
bump — `AssertionError: assert '1.9.0' == '1.9.1'` — then green after).
Following this repo's established version-pin convention exactly:
`tests/test_v190_version.py` is repointed to the frozen `v1.9.0` git-tag
blob (the same treatment `tests/test_v180_version.py` received at v1.9.0
T12), never deleted, per REQ-V190-EC-03. `AGENTS.md`'s gate-3/gate-6
count-bearing lines and `tests/test_v190_agents.py`'s pinning test move to
the release's real, final numbers. `docs/reports/report-v1.9.1.md`
(started by T1) is finished with the seven-gate table, the clean-context
review record, the mutation proof, the two required disclosures, the
per-task delegation record, and the Ledger row. `docs/reports/tg-post-v1.9.1.md`
and `docs/llm-usage.md` rows for prompts 160–162 close the reporting. All
seven gates run verbatim, in order, on the final tree; only then the
annotated tag `v1.9.1`.

## Constraints

- One prompt → one commit: this is prompt 162.
- No logic changes — version, tracking documentation, and paperwork only.
- `docs/reports/report-v1.9.0.md` and the v1.9.0 record stay untouched.
- `.env` is never read, printed or committed. Never `--no-verify`.
- Do not push — the operator pushes.

## Acceptance

All seven gates from `AGENTS.md` exit 0, on the final tree, in order:
`uv sync --locked`, `uv run --locked ruff check .`,
`uv run --locked pytest`, `uv run --locked python bot.py --selftest`,
`uv run --locked python bot.py --selftest-live`,
`uv run --locked python devtools/mutation_check.py`,
`uv run --locked python devtools/rag_eval.py`. Evidence recorded in
`docs/reports/report-v1.9.1.md`. Annotated tag `v1.9.1` created on the
release commit once all seven are green.

## Stop

If a gate fails for a reason that needs a code change, stop and report
rather than fixing it inside a version-bump commit.

## Deviation — `config/quality_gates.yaml`'s `report_path` repoint

Not named in the task brief; found via a pre-flight grep for pins the
version bump would break (`grep -rn 'report-v1\.9' tests/ config/`).
`REQ-V190-RPT-01` (`tests/test_v170_bench.py`'s own
`test_t_v190_rpt_01_lint_docs_repointed_to_this_release`, T10-era) states
plainly that `checks.py lint-docs`'s `report_path` "tracks the current
release and is repointed again at each one." v1.9.0 T10 repointed it
1.8.0 → 1.9.0; nothing repointed it 1.9.0 → 1.9.1 for this patch (T1's
scope was the rerank contract, not paperwork routing), so left alone
`lint-docs` would keep validating `docs/reports/report-v1.9.0.md`'s
Ledger row forever and never see this release's own report. Repointed to
`docs/reports/report-v1.9.1.md` in `config/quality_gates.yaml`, with both
pinning tests (`tests/test_v170_bench.py`, `tests/test_v190_agents.py`)
updated and renamed to the same `test_t_v191_*` convention this task
already applies elsewhere. Documentation/config only, no gate depends on
the old value having stayed, no logic touched.
