# Prompt 185 — v1.9.4 T2 measurement addendum: three more gate-7 candidates

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded measurement task against the coordinator's own
  named candidates and env vars -- no design decision, no code change, just
  three more instrumented gate-7 runs and a report/table update.
- **Harness:** Claude Code
- **Stage:** v1.9.4 T2 addendum (docs-only follow-up, after the reviewed
  T2 commit `b5db300` already landed)
- **Owner of:** `docs/reports/report-v1.9.4.md`, `docs/llm-usage.md`
- **REQ ids:** none new (measurement only, no behaviour change)

## Goal

T2's own measurement (`docs/reports/report-v1.9.4.md`'s T2 section) tried
two OpenRouter models as the opt-in `LLM_EVAL_CHAT_MODEL` route:
`mistral-small-24b-instruct-2501` (cannot make a tool call at all --
HTTP 404, no endpoint on OpenRouter supports tool use for that model) and,
per the brief's own contingency, `mistral-nemo` (mechanically can call a
tool, but never called `search_documents` in either run). The coordinator's
review found this settles those two models, not the route question itself.
This addendum measures three more candidates, one gate-7 run each (the
local model run twice, reporting the second run as the intended steady
state), alone on the box, sequentially, `LLM_EVAL_CHAT_MODEL` set only in
the process environment (never written to `.env`), the same instrumented
per-turn timing technique (`agent.run_agent_outcome` / `rag.Searcher.search`
wrapped with timestamps):

1. `openrouter:openai/gpt-4o-mini` -- the reference tool-caller, to test
   whether a *strong, reliable* tool-calling model still goes silent on
   this smoke (which would indict the prompt, not the model).
2. `openrouter:google/gemini-2.5-flash`.
3. `lmstudio:qwen/qwen3.5-9b` -- a small local model already loaded on the
   box alongside the production model.

## Constraints

- Budget ≤ $0.20 for this addendum (separate from T2's own $0.30 cap,
  already spent).
- `.env` never read, printed, or written to; the env var lives only in the
  measuring process's own environment.
- Nothing else running on the box during any of the four runs; runs
  strictly sequential.
- Amend only `docs/reports/report-v1.9.4.md`'s T2 measurement table
  (extended) and its Recommendation paragraph (rewritten from the full,
  now sixteen-row table) plus `docs/llm-usage.md` (a new row) -- no code
  change, no re-opening of the already-reviewed T2 commit.
- Commit as a docs-only follow-up (this prompt file, the report edit, the
  llm-usage row) -- never amended into `b5db300`.

## Acceptance

Four live gate-7 runs (C1, C2, D1, D2), each printing both smoke verdicts
and exiting 0; per-turn timestamps captured from the instrumented probe's
own stdout; no `.env` write; total spend well under $0.20 (tallied by hand
from each run's own `llm_call` rows, since this harness does not attach
`cost_usd` on this path).

## Stop

Stop and report instead of forcing a workaround when: any run's wall
exceeds the `rag-eval` gate's own 1120s timeout without a real reason;
addendum spend approaches $0.20; the local model fails to load at all
after two attempts.
