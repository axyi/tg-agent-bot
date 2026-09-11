# Prompt 145 — spec-v1.9.0 T2 erratum (wire `_live_embeddings` into `run_selftest_live`)

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** narrow, fully-specified follow-up to prompt 144's T2 run
  (docs/prompts/144-v190-t2-embeddings-config.md) — the wiring line, the
  fixture change and its test-value updates are pinned by REQ-V190-RET-08
  and by the operator's ratification decision; no new design work.
- **Harness:** Claude Code
- **Stage:** T2 (erratum)
- **Owner of:** `bot.py` (`run_selftest_live` wiring line,
  `_live_embeddings`'s docstring), `tests/test_v1_guardrails.py`
  (`live_cfg`, `live_handler`, `test_t_v1_lv_01_all_checks_pass`)
- **REQ ids:** REQ-V190-RET-08

## Goal

Apply the one item prompt 144 disclosed and withheld: wire
`failures += _live_embeddings(cfg, client)` into `run_selftest_live`
(`bot.py:1351-1384`) right after `_live_lmstudio`, exactly as
REQ-V190-RET-08 specifies, and amend the two `tests/test_v1_guardrails.py`
fixtures (`live_cfg`, `live_handler`) so the check has a valid embedding
pair and a mocked `/embeddings` endpoint to exercise, instead of
unconditionally failing every live-selftest test.

## Constraints

This erratum was **explicitly operator-ratified** after the orchestrator
disclosed it (prompt 144, Constraints item 2) — the same precedent class as
`tests/test_summary.py`'s existing "authorised by the operator, prompt 107"
comment (an operator sign-off extending REQ-V190-EC-03's exhaustive
test-amendment list to a case its own table missed). Scope is deliberately
narrow: only `bot.py`'s `run_selftest_live` wiring line and
`_live_embeddings`'s docstring, plus `tests/test_v1_guardrails.py`'s
`live_cfg`/`live_handler` fixtures and `test_t_v1_lv_01_all_checks_pass`'s
two assertions, are touched. `make_cfg` (shared by the whole file) is left
alone — only the `live_cfg` wrapper gains embedding defaults, so every
non-live test in the file is unaffected. `live_handler`'s new `/embeddings`
branch appends `embedding_model` to the `/models` response unconditionally
(rather than folding it into the `lmstudio_models` default), so a
hypothetical future test overriding `lmstudio_models` to force a lmstudio
FAIL would not also spuriously fail the embeddings check.
`tests/test_v190_embeddings.py`'s module docstring still describes the
now-superseded deferred-wiring state (it documents this exact decision by
name) — left untouched as out of this erratum's authorised scope, flagged
for a follow-up. No live gate was run; every test stays offline
(`httpx.MockTransport`).

## Acceptance

- `uv run --locked ruff check .` — exit 0.
- `uv run --locked pytest` — exit 0; 1303 passed, 1 skipped (unchanged from
  prompt 144's baseline); `pytest --collect-only -q` totals 1304, unchanged
  (fixtures/tests amended, none added or removed).
- `uv run --locked python bot.py --selftest` — exit 0.
- `test_t_v1_lv_01_all_checks_pass` now asserts `out.count("live: OK") == 7`
  and includes `"embeddings"` in its per-name loop.
- `test_t_v1_lv_01_missing_openrouter_key_is_a_skip`,
  `test_t_v1_lv_01_a_failing_check_exits_one` and
  `test_t_v1_lv_01_secrets_never_reach_the_output` pass unmodified — none of
  the three asserts an exact OK count, only specific FAIL/SKIP lines and
  `code`, so the new `live: OK embeddings` line (or the pre-existing FAIL
  paths those tests already exercise) does not disturb them.

## Stop

Not applicable — the erratum's one item (the wiring line and its two
fixture-owning tests) is fully applied and green; no further decision is
pending.
