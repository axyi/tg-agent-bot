# Prompt 182 — v1.9.4 T2: gate 7's conversation smoke means something, and its wall is explained

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded, well-specified extension against an existing
  task brief (`docs/spec/task-briefs/v194-T2.md`) -- one new module constant,
  one new agent turn, a routing purpose mirrored verbatim from
  `LLM_RERANK_MODEL`, and their tests; no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.4 T2 (patch, no new spec file — precedent v1.5.1, v1.9.1–v1.9.3)
- **Owner of:** `devtools/rag_eval.py`, `config.py`, `llm/__init__.py`,
  `.env.example`, `devtools/mutation_check.py`, `tests/test_v190_eval.py`,
  `tests/test_routing.py`, `README.md`, `docs/reports/report-v1.9.4.md`,
  `docs/llm-usage.md`
- **REQ ids:** none new for this patch (precedent: v1.9.1 T3, v1.9.2 T3,
  v1.9.4 T1 also landed patch fixes with no new REQ id)

## Goal

Two independent problems with gate 7's advisory conversation smoke
(`docs/spec/task-briefs/v194-T2.md`'s two facts from v1.9.3): (1) turn 2's
token-overlap verdict cannot fail for a real reason today -- the model
answers "28 дней -- это 4 недели" from turn 1's own context without ever
calling `search_documents`, a *correct* answer the check reports as `fail`,
indistinguishable from a real REQ-V190-TOOL-06 regression; (2) the smoke
turn's chat completions (three turns' worth on the production LM
Studio-primary route), not retrieval, are gate 7's wall (253s of 268s in
the v1.9.3 T1+T2 review's instrumented run).

This task (offline half only; see Constraints): keeps turn 1 -> turn 2
exactly as shipped (route (a), REQ-V190-TOOL-06's pinned pair, still
advisory) and adds a third turn, `_SMOKE_FOLLOWUP_2` -- a paraphrase of
`evals/rag/questions.json`'s second answerable item ("Сколько дней отпуска
можно перенести на следующий год?", gold `vacation_policy.md`) phrased as a
follow-up that cannot be answered from turns 1-2's own context. Turn 3's
verdict (`pass` iff it made >= 1 `search_documents` call **and** at least
one call's returned passages carry the gold source, filename-equality --
the same convention `first_hit` uses) is meaningful pass/fail, never
advisory-by-construction. `conversation_smoke()` now returns
`(tool06_ok, tool06_detail, context_proof_ok, context_proof_detail)`;
`run()` prints both as separate advisory lines, neither affecting the exit
code. Also adds the opt-in `LLM_EVAL_CHAT_MODEL` routing purpose
(`config.py`/`llm/__init__.py`/`.env.example`, exactly `LLM_RERANK_MODEL`'s
shape) for the smoke turns' chat client, wired into `rag_eval.run()`/
`main()` behind a default-`None` parameter so the unset path is provably
identical to today.

## Constraints

- Offline only: no live LLM call (no `rag_eval.py` `main()`, no OpenRouter/
  LM Studio traffic, no `bot.py --selftest-live`), no `devtools/
  mutation_check.py`, `.env` never read/printed/edited, no git add/commit/
  push. A coordinator runs the live gate-7 measurement (production route
  and the new opt-in route), picks the recommendation, and finishes
  `docs/reports/report-v1.9.4.md`'s T2 section and `docs/llm-usage.md` row
  92 with real numbers.
- Turn 2's own verdict (advisory, token overlap) is unchanged in substance;
  only its printed label gains `(TOOL-06 pin)` alongside the new
  `(context-proof)` line.
- Do not edit `spec-v1.9.0.md` (shipped spec). `spec-v1.9.0-delta-1.md`
  gets one dated note only if it already carries a section for eval
  addenda in that style; otherwise leave it untouched (checked: it does
  not -- its per-change notes exist only for the gate matrix table, not
  for `T-V190-EVAL-*`/`TOOL-06` test behaviour, so this run leaves it
  untouched and the report's T2 section is the record).
- Never open `data/` or `evals/rag/corpus` as file content beyond what
  `evals/rag/questions.json` already requires.
- `--only v194-smoke-turn3-gold-unchecked` (the new mutation entry) is
  added but not run -- left for the coordinator.

## Acceptance

```
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python devtools/checks.py lint-docs
```

All five exit 0, including the existing smoke test
(`test_t_v190_eval_02_run_offline_exits_zero_with_correct_metrics`) now
green against three turns, and the new turn-3 cases in
`tests/test_v190_eval.py`
(`test_t_v194_t2_conversation_smoke_turn3_calls_search_and_hits_gold`,
`test_t_v194_t2_conversation_smoke_turn3_calls_search_and_misses_gold`,
`test_t_v194_t2_conversation_smoke_turn3_makes_no_call`) plus the
`LLM_EVAL_CHAT_MODEL`/`eval-chat` cases in `tests/test_routing.py`. The
live gate-7 measurement runs (production route and the opt-in
`LLM_EVAL_CHAT_MODEL` route, both A1/A2 and B1/B2 of the brief's table) are
performed by the coordinator after this offline work is verified, not by
this prompt.

## Stop

Stop and report instead of forcing a workaround when: the offline
pigeonhole synthetic corpus cannot express a genuine turn-3 miss (it can,
by omitting the gold source from the indexed set -- see
`test_t_v194_t2_conversation_smoke_turn3_calls_search_and_misses_gold`); or
any of the five acceptance commands cannot be made to pass without
touching `.env`, `devtools/mutation_check.py`'s execution, or a live LLM
call.
