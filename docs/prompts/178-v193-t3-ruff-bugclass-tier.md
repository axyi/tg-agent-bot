# Prompt 178 — v1.9.3 T3 commit B: ruff bug-class tier

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a precisely-specified rule-by-rule review pass against
  an existing task brief (`docs/spec/task-briefs/v193-T3.md`) — named rules,
  a bounded per-site judgment shape (classified-vs-unexpected exception
  triage, intentional-vs-bug string-concat triage); no open-ended design
  decision.
- **Harness:** Claude Code
- **Stage:** v1.9.3 T3 commit B (`docs/spec/task-briefs/v193-T3.md`)
- **Owner of:** `pyproject.toml`, `bot.py`, `agent.py`, `tools.py`,
  `dashboard_server.py`, `devtools/bench.py`, `devtools/checks.py`,
  `devtools/dashboard.py`, `devtools/mutation_check.py`, `documents.py`,
  `llm/base.py`, `rag.py`, `storage.py`, `tracing.py`, several `tests/*.py`
  files, `docs/reports/report-v1.9.3.md`, `docs/llm-usage.md`
- **REQ ids:** REQ-V15-NG-04

## Goal

Closes the ruff rule-family proposal table's bug-class tier: `PLW1510
TRY400 ISC004 RUF005 RUF007 PERF401 SIM105 SIM117 TRY004 PLW2901`, each hit
read by hand per the brief. `PLW1510` (16 sites): every one already reads
`.returncode` afterward, or (one `_docker_kill` best-effort site) treats a
non-zero exit as expected — all 16 get explicit `check=False`, none needed
`check=True`. `TRY400` (16 sites): 10 adopted `log.exception` (genuinely
unexpected paths — a startup `KeyError`/`TypeError` mixed into a
`TelegramError` catch, `bot.py`'s own broad `except Exception`
dashboard-startup guard, `dashboard_server.py`'s two broad
`except Exception`/DB-error request guards, five `devtools/bench.py`
sites — one scenario-prep failure plus two DB-open/DB-read pairs, one
`sqlite3.Error` in the document handler), 6 kept
`log.error` with `# noqa: TRY400` and an inline reason (two `TelegramError`
sites, two `ConfigError` sites — the latter pinned by
`test_v12_patch.py`'s own "no Traceback in the log" assertion,
REQ-V12-ERR-01 — and two audit-log best-effort sites). `ISC004` (32 hits,
11 in the byte-hash-frozen `devtools/bench_scenarios.py` excluded per the
brief's own rationale generalised to this rule, see Constraints): the
remaining 21 all read as intentional long-string wraps (deliberate
canary/benchmark literals, HTML row builders, one SQL migration
statement, one stats-line builder) — none a missing comma — parenthesised
explicit via `ruff --unsafe-fixes`, diff read in full first.
`RUF005`/`RUF007`/`PERF401`/`PLW2901`: mechanical rewrites,
`--unsafe-fixes` where offered, hand-rewritten where not (all 19 `PERF401`
hits, all 6 `PLW2901` renames). `TRY004` (5 hits, per-site judgment, not
mechanical): 4 kept `ValueError` with `# noqa: TRY004` (0 adopted after
this task's own review corrected one site's initial `TypeError` adoption
back to `ValueError`), the fifth is the `bench_scenarios.py` exclusion.
`SIM105`/`SIM117`: every
`contextlib.suppress`/merged-`with` rewrite read for identical exception
set and identical enter/exit order (Python's own semantics for a
comma-joined `with` statement are provably identical to the nested form
when the outer body is solely the inner `with`, ruff's own precondition
for the rule). One orphan fixed in passing: `devtools/checks.py`'s two
`PERF401` rewrites left `findings = [...]; return findings` — collapsed to
a direct `return [...]` (`RET504`, now selected after commit A). One line
manually rewrapped after the `RUF005` autofix produced a >100-char line
inside an f-string implicit-concat (`agent.py`'s JSON-repair message).
Then all 10 rules added to `select`, rule-level; a `[tool.ruff.lint.per-
file-ignores]` table added for `devtools/bench_scenarios.py` (`TRY004`,
`ISC004`).

Mutation drift: one entry drifted after the `SIM105` rewrite of
`tools.py`'s fetch-save inode-reuse guard (`try`/`except FileNotFoundError`
→ `with contextlib.suppress(FileNotFoundError)`) — re-derived with
identical semantics (same statements dropped/kept, same `O_EXCL`→`O_TRUNC`
swap) and confirmed killed. See the report's own drift/re-derive record.

## Constraints

Rule-level `select` additions only, never family-level. `.env`, `data/`,
`evals/rag/corpus` untouched. Nothing concurrent with any mutation run. No
push. `devtools/bench_scenarios.py` excluded from the `TRY004`/`ISC004`
fixes (byte-hash-frozen, `REQ-V13-BEN-12`) — the brief named this exclusion
for `PERF401`/`SIM117` only (neither of which hits this file); the same
underlying reason generalises to the two rules that do, disclosed as a
beyond-brief generalisation in the report for the operator to review.

## Acceptance

```
uv run --locked ruff check .                                            # 0
uv run --locked ruff format --check .                                   # 0
uv run --locked pytest                                                  # 0 pre-commit (one drift-caused
                                                                         #   failure expected before the
                                                                         #   re-derive lands; 0 after)
uv run --locked python bot.py --selftest                                # 0
uv run --locked python devtools/checks.py lint-docs                     # 0
<drift script>                                                          # 114/114 after re-derivation
uv run --locked python devtools/mutation_check.py --only v13-fetch-save-reuses-inode   # killed, on the committed tree
```

## Stop

If an `ISC004` site is a real missing-comma bug whose fix changes
user-visible behaviour; if a `PLW1510` `check=True` would break a gate; if
a mutation cannot be re-derived with identical semantics; if a
`PERF401`/`SIM117`/`TRY004`/`ISC004` rewrite touches
`devtools/bench_scenarios.py` in a way the per-file-ignore cannot absorb.
None of these fired.
