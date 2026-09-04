# Prompt 77 — spec-v1.6.0 T4: metrics.py aggregates + /stats

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §"Executor: claude-sonnet-5"; every function
  signature, cap and SQL formula is already written out in §6
- **Harness:** Claude Code
- **Stage:** T4
- **Owner of:** `metrics.py` (eight new aggregate functions + five
  dataclasses), `bot.py` (`_render_stats` gains two lines),
  `tests/test_v160_observability.py` (T4's tests, appended)
- **REQ ids:** REQ-V160-MET-01..07

## Goal

Add `usage_by`, `error_breakdown`, `latency_histogram`, `token_histogram`,
`tool_health`, `limit_hits`, `retry_rate`, `context_pressure` and
`summary_health` to `metrics.py` — the one implementation `/stats`, the
dashboard and the JSON API all share (T-V160-MET-08). Revive the ten dead
columns REQ-V160-MET-02 names. Bound every aggregate per REQ-V160-MET-07
(`usage_by` 500 + `(other)`, `error_breakdown` 100 + `(other)` per
dictionary, `tool_health` 50, the two histograms 20 + a folded `(other)`
histogram). `/stats` gains two lines, built from `error_breakdown` and
`summary_health`, never their own SQL.

## Constraints

- No parallel metrics module; every new function lives in `metrics.py`
  alongside the seven existing ones.
- `/stats`'s first eight lines stay byte-identical in shape (appended-only).
- **Formatting discipline learned the hard way this task:** `ruff format
  metrics.py` (a pre-existing file) reformats the *whole* file, not just new
  code, silently violating the no-whole-tree-reformat convention and risking
  a mutation `find`-string collision. Caught via `git diff --stat` showing
  deletions in pre-existing functions; reverted and re-applied by hand-
  wrapping only the new lines that exceeded 100 characters. `ruff format` on
  a pre-existing file is unsafe in this repo; only run it on genuinely new
  files (or check `git diff --stat` shows zero deletions before trusting it).
- One prompt → one commit, referencing this file.

## Acceptance

- `tests/test_v160_observability.py`'s T4 section (16 new tests) covers
  T-V160-MET-02 (model-pair grouping, unknown group raises, `since` boundary),
  -03 (`cache_hit_share`/mixed cost basis), -04 (NULL bucketing), -05
  (1.28s boundary lands in the lower bucket, overflow bucket), -06 (per-type
  token histograms, sorted attribute keys), -07 (`max_consecutive_repeats`
  never crosses a turn boundary), -08 (`/stats` and `usage_by` agree), -09
  (`limit_hits` reports only the seven real names), -10 (the 500-cap
  `(other)` fold), -11 (the 100-cap `(other)` fold on both error
  dictionaries), plus `summary_health`'s five row-based formulas and
  `/stats`'s two new appended lines.
- `uv run --locked pytest` exits 0, 904 passed (888 + 16 new).
- `uv run --locked ruff check .` exits 0.
- `uv run --locked python devtools/mutation_check.py` exits 0, 72/72 killed.

## Stop

If a formatting pass ever shows deletions in a pre-existing file's `git diff
--stat`, stop before committing and revert — that is the discipline this
task's own near-miss (see Constraints) exists to prevent.
