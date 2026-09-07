# Prompt 109 — spec-v1.7.0 T5: complete() wiring, provider forms, OBS

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T5
- **Owner of:** `llm/base.py`, `llm/lmstudio.py`, `llm/openrouter.py`,
  `llm/failover.py`, `bot.py`, `agent.py`, `tracing.py`,
  `devtools/mutation_check.py` (one find-string sync),
  `devtools/bench.py` (warm-up probe explicit defaults),
  `tests/fakes.py`, `tests/test_observability.py`, `tests/test_bench.py`,
  `tests/test_failover.py` (§14.1 signature amendments),
  `tests/test_v160_dashboard.py` (one line, disclosed erratum instance),
  `tests/test_v170_reasoning.py` (extended), `.env` (`LMSTUDIO_BASE_URL`
  re-resolved mid-task, permitted idiom),
  `docs/prompts/109-v170-t5-complete-wiring-obs.md` (new)
- **REQ ids:** REQ-V170-POL-04, -05, -06, REQ-V170-OBS-02, -03, -04

## Goal

Carry `reasoning`/`timeout_s` through all five `complete()` definitions and
five invocation sites; apply the two provider forms from `mechanism`/`value`
alone; extend `build_payload` with `reasoning_fields`; wire the honored
verdict and the span attribute through `_record_llm_call` into
`storage.add_llm_call`; verify the exactly-six-rows property against the
real agent loop, summarizer and a real `FailoverLLMClient`, not fakes of
fakes.

## Constraints

- No provider ever reads `request.tag`; the per-purpose lookup happened
  once, in `resolve_reasoning` (T4).
- `_try_other` forwards `reasoning` positionally, unchanged, exactly as it
  already forwards `max_tokens`.
- `reasoning_honored` is three-valued; `NULL` must never be read as `0`
  anywhere in this task's own tests (asserted with `is`, not `==`).
- Only the seven test-double signatures §14.1 names are touched in
  `tests/fakes.py`/`test_observability.py`/`test_bench.py`/`test_failover.py`;
  no other line in any of those files changes.
- `.env`'s only permitted rewrite remains the single-line
  `LMSTUDIO_BASE_URL` idiom, re-applied only because the GPU box's address
  itself changed (a live infrastructure event, not a source change).
- One prompt -> one commit, referencing this file.

## Acceptance

- `tests/test_v170_reasoning.py` green (78 tests total: 39 from T4 + 39
  from this task).
- Full suite green: `uv run --locked pytest` (1094 collected).
- `uv run --locked ruff check .` exits 0.
- `uv run --locked python bot.py --selftest` exits 0 with
  `reasoning_requested`/`tg_agent.reasoning.requested` populated.
- `uv run --locked python bot.py --selftest-live` exits 0 (address
  re-resolved as needed; instrument re-verified unchanged).
- `uv run --locked python devtools/mutation_check.py` exits 0 (83/83
  killed).
- `uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json`
  exits 0.

## Stop

None triggered.
