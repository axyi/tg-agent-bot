# Prompt 177 — v1.9.3 T3 commit A: ruff autofix tier

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a precisely-specified rule-by-rule autofix pass against
  an existing task brief (`docs/spec/task-briefs/v193-T3.md`) — named rules,
  a bounded review shape (read each unsafe-fix diff hunk before applying);
  no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.3 T3 commit A (`docs/spec/task-briefs/v193-T3.md`)
- **Owner of:** `pyproject.toml`, `storage.py`, `metrics.py`,
  `dashboard_render.py`, `devtools/dashboard.py`, `devtools/bench.py`,
  `devtools/mutation_check.py`, `rag.py`, `config.py`, `llm/base.py`,
  `bot.py`, `dashboard_server.py`, several `tests/*.py` files,
  `docs/reports/report-v1.9.3.md`, `docs/llm-usage.md`
- **REQ ids:** REQ-V15-NG-04

## Goal

Closes the ruff rule-family proposal table's mechanical, behaviour-preserving
tier: `UP037 UP017 UP031 C420 C408 SIM300 SIM102 RET501 RET503 RET504
FURB105 FURB110 FURB167 FURB187 FURB192 PIE810 RUF015 RUF059 PLW0108`,
applied via `ruff check --select <list> --fix` for the 8 safe-fixable rules,
then `--unsafe-fixes` after reading every diff hunk, with `RUF059` (rename
to `_name`, never drop the unpacking) and `FURB192` (`sorted(x)[0]` →
`min(x)`, verified no custom `key=` on any of the 4 sites, so tie-breaking
is unaffected) read individually per the brief. Three sites ruff would not
autofix (`UP031` one `%`-format, `SIM102` two nested-if pairs) were hand-
rewritten, checked for identical fall-through semantics. One orphan created
by the `UP017` fix (`storage.py`'s now-unused `timezone` import after the
rewrite to `UTC`) was removed. Every rule then added to `pyproject.toml`'s
`[tool.ruff.lint].select`, rule-level, plus a comment block closing the
whole v1.9.3 T3 decision table (the "never"/"not now" families, verbatim
from the brief) so the table itself needs no further carry-forward.

## Constraints

Rule-level `select` additions only, never family-level (no never-listed
sibling rule rides along). No drive-by refactors beyond the rule being
fixed. `devtools/bench_scenarios.py` untouched (confirmed: none of these 19
rules' hits land in that file). Nothing concurrent with any mutation run.
`.env`, `data/`, `evals/rag/corpus` untouched. No push.

## Acceptance

```
uv run --locked ruff check .                                            # 0
uv run --locked ruff format --check .                                   # 0
uv run --locked pytest                                                  # 0
uv run --locked python bot.py --selftest                                # 0
uv run --locked python devtools/checks.py lint-docs                     # 0
<drift script>                                                          # 114/114
```

## Stop

If an unsafe-fix diff for `RUF059` drops a tuple element instead of
renaming it, or a `FURB192` site carries a custom `key=` that changes
tie-breaking; if any of the 19 rules' hits land in
`devtools/bench_scenarios.py`; if the drift script reports any entry
drifted after the fixes land.
