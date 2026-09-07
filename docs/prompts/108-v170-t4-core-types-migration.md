# Prompt 108 — spec-v1.7.0 T4: core types, config, migration

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T4
- **Owner of:** `config.py`, `llm/base.py`, `storage.py`,
  `devtools/bench.py` (one small companion fix, `env_flags`),
  `tests/test_v170_reasoning.py` (new),
  `tests/test_observability.py` (amended per §14.1, plus the authorised
  erratum), `tests/test_summary.py`, `tests/test_v160_observability.py`,
  `tests/test_bench.py`, `tests/test_v14_patch.py` (authorised errata),
  `docs/prompts/108-v170-t4-core-types-migration.md` (new)
- **REQ ids:** REQ-V170-POL-01, -02, -03, REQ-V170-OBS-01, REQ-V170-SUM-05

## Goal

Land the reasoning-policy vocabulary stage A decided at T3: `config.py`'s
two new env vars and the SUM-05 timeout-floor check; `llm/base.py`'s
`REASONING_TAGS`, `reasoning_tag`, the two frozen dataclasses,
`REASONING_MECHANISMS` filled from T3's per-purpose table (summary-only,
candidate c), `resolve_reasoning` and `json_fields`; `storage.py`'s schema
4 -> 5 migration, chained after the existing 1/2/3 -> 4 migrations without
touching them.

## Constraints

- No mechanism, purpose or policy literal duplicated outside `llm/base.py`
  (REQ-V170-POL-02's single-source-of-truth rule).
- `config.py` cannot import `llm.base` at module level (a real cycle via
  `llm/__init__.py`); `_parse_purposes` uses a local import instead.
- `_MIGRATION_2_TO_4`/`_MIGRATION_3_TO_4` byte-identical; the new
  `_MIGRATION_4_TO_5` never double-adds a column on any path.
- No unlisted test is edited except the erratum the operator explicitly
  authorised (prompt 107's blocker, its extension, and the same-class
  instance found during implementation — all three recorded in this
  prompt's own report section).
- One prompt -> one commit, referencing this file.

## Acceptance

- `tests/test_v170_reasoning.py` green (39 tests): POL-01, -02, -03,
  OBS-01 (chained 1/2/3/4 -> 5, idempotent, unsupported versions), SUM-05,
  N1, N2, N3, N8.
- Full suite green: `uv run --locked pytest` (1055 collected).
- `uv run --locked ruff check .` exits 0.
- `uv run --locked python bot.py --selftest` exits 0, with
  `reasoning_requested`/`reasoning_honored` both `null` in the log line
  (today's callers don't supply them yet -- T5's job).
- `uv run --locked python devtools/mutation_check.py` exits 0 (83/83
  killed) -- confirms the self-caught `find`-string collision
  (`v14-rel-01-timeout-budget-boundary-disabled`) stayed fixed.
- `uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json`
  exits 0 after `storage.LLM_CALL_COLUMNS` widened.

## Stop

None triggered. The T4 blocker (prompt 107) already ran its course and was
resolved by the operator before this prompt started.
