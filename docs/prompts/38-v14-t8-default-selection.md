# Prompt 38 — v1.4 T8: default selection, STOP branch (documentation only)

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** continues the run's pinned model (prompt 31); a scoped
  documentation update with no judgment beyond RPT-06/GATE-02's own text.
- **Harness:** Claude Code CLI
- **Stage:** generation
- **Owner of:** `.env.example`, `README.md`, `docs/reports/report-v1.4.md`,
  `docs/prompts/38-v14-t8-default-selection.md` (new)
- **REQ ids:** REQ-V14-BEN-09 (released), REQ-V14-RPT-06 (T8 half,
  mechanism-independent only)

## Brief as sent (self-directed, per ORD-01's T8 row, GATE-02-narrowed)

```
STOP branch: BEN-09 (the default flip) is released — no mechanism to
flip to. T8 reduces to RPT-06's mechanism-independent documentation:
(1) .env.example gets REL-01's LLM_TIMEOUT_S=240 (no LLM_REASONING_POLICY
/ LLM_REASONING_ON_PURPOSES lines — that policy was never implemented);
(2) README.md gets only the RPT-06 item-2 lines that do not describe a
reasoning policy — the "§ Benchmark → baseline-v1.4 procedure in one
paragraph" line, nothing from "§ Configure"/"§ Token economy" (both
entirely about the policy) or "§ Observability" (the two new columns
don't exist without T5). docs/plan.md is T10's file, not touched here.
```

## Changes

`.env.example`: `LLM_TIMEOUT_S=120` → `LLM_TIMEOUT_S=240`, plus a
three-line comment stating REL-01's consistency formula and its
consequence (a timed-out completion is retried with identical
parameters, re-sending the whole prompt) — matching the file's existing
per-variable comment style (compare `EXEC_SANDBOX_MAX_BYTES`,
`EXEC_SANDBOX_CLEAN_ON_START`).

`README.md` § "Benchmark": one new paragraph, "Measuring a
pre-optimization baseline against the current harness," between the
`run`/`check`/`report` exit-code paragraph and "**The JSON**" paragraph
— explains why a `scenarios_sha256` change forces a fresh baseline, and
documents the `git worktree` procedure `baseline-v1.4.json` was produced
with (pre-optimization commit checked out, only `bench.py` /
`bench_scenarios.py` / `__init__.py` copied in from the current tree,
`.env` reached by symlink and never opened for content, `--out` into the
main tree). Links to `report-v1.4.md` for the full procedure and figures.
Nothing else in `README.md` touched — no `§ Configure`, `§ Token
economy` or `§ Observability` edit, since all three describe the
reasoning policy this run never shipped.

No test couples to either file's content (`grep -rl ".env.example"
tests/ devtools/` — empty), so no collateral test risk.

## Gates

Gates 1–5 green: `uv sync --locked` rc=0; `ruff check .` rc=0, all checks
passed; `pytest` rc=0 — 728 passed (unchanged, no test touched);
`bot.py --selftest` rc=0; `bot.py --selftest-live` rc=0, all six OK.
Gate 6 not required: this commit touches neither production code, tests
nor mutations, and is not the final tree (GATE-01) — same reasoning as
T3/T4's gate rows.
