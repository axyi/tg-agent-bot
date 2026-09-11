# Prompt 153 — v1.9.0 T8: the retrieval evaluation (gate 7)

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for spec-driven implementation tasks in this run (T1-T7 used the same model).
- **Harness:** Claude Code
- **Stage:** T8
- **Owner of:** `devtools/rag_eval.py` (new); `evals/rag/corpus/vacation_policy.md`, `evals/rag/corpus/onboarding.txt`, `evals/rag/corpus/expenses.docx.md`, `evals/rag/corpus/security_guidelines.pdf.txt`, `evals/rag/questions.json` (new); `tests/test_v190_eval.py` (new); `AGENTS.md:133-160`, `README.md:776-790`, `config/quality_gates.yaml:7-14,138-150` (gate 7 wiring); `rag.py` (`_RERANK_MAX_TOKENS`, operator-ratified, see Constraints); `tests/test_v190_retrieval.py` (matching assertion update)
- **REQ ids:** REQ-V190-EVAL-01, REQ-V190-EVAL-02, REQ-V190-EVAL-03, REQ-V190-EVAL-04

## Goal

Implement EVAL-01..04 end to end, test-first: the frozen four-document
eval corpus and 12-question set (`evals/rag/`), `devtools/rag_eval.py`
(gate 7 — indexes the corpus for synthetic user `-1` through the real
`documents.index_document` pipeline, measures `vector`/`hybrid`/
`hybrid+rerank` retrieval against the question set, plus an advisory
conversation-aware smoke test), and the gate-7 wiring into `AGENTS.md`,
`README.md`, `config/quality_gates.yaml`'s `full` profile.

## Constraints

Test-first: `tests/test_v190_eval.py` written and passing offline before
the first live call. Read `documents.py`/`storage.py`/`rag.py` directly for
exact signatures before use, no guessing. `rag_rerank`/`rag_top_k` forced
to `"on"`/`5` unconditionally inside `run()`, printed in the script's own
header output. The corpus/questions freeze (sha256, computed once, printed)
is never revised in response to a live result — only retrieval code/config
may change to fix a below-floor score.

**Operator-ratified deviation (mid-task):** after the first three live
runs all exited 2 on the same two items with identical
`rerank_failure='rerank returned no usable order'`, root-caused to the
operator's deployed `qwen/qwen3.8-27b` (a thinking-variant model) spending
`rag.py`'s `rerank()`'s fixed `max_tokens` on undisabled chain-of-thought
reasoning before ever emitting the JSON answer, the orchestrator explicitly
authorized raising `rag.py:_RERANK_MAX_TOKENS` beyond RET-06's literal
`128`, for this one call only — first to `1024`, then (still failing for
the same reason) to `2048` as an explicitly pre-authorized second and final
attempt. This is the one place this task touches `rag.py` (T5, otherwise
frozen this run); `tests/test_v190_retrieval.py`'s matching
`max_tokens_calls == [...]` assertion was updated in lockstep both times.
See Stop for the outcome and the new finding this surfaced.

## Acceptance

Offline: `T-V190-EVAL-01..04` (16 tests in `tests/test_v190_eval.py`) all
green, `uv run --locked ruff check .` exit 0, `uv run --locked python
bot.py --selftest` exit 0. `uv run --locked pytest` exits 1, with exactly
one known, expected failure —
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` — see Stop
item 1 (orchestrator-confirmed as T9's own scope, not an EC-03 erratum;
left red on purpose). Live: `uv run --locked python devtools/rag_eval.py`
did **not** reach exit 0 this run — see Stop item 2.

## Stop

**1. `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` — not
resolved here, and not meant to be.** `REQ-V190-EVAL-04` mandates adding a
`rag-eval` gate to `config/quality_gates.yaml`'s `full` profile; that test
parses the gate matrix out of the frozen `docs/spec/spec-v1.8.0-delta-1.md`
and asserts the live `full` profile matches it exactly, so the addition
breaks it. Orchestrator confirmed this is **anticipated sequential
breakage**, not a fresh EC-03-style erratum: `REQ-V190-EC-12` already
assigns the fix (repointing the test at `spec-v1.9.0-delta-1.md`, adding
the `mutation-v190`/`rag-eval` labels) to **T9**, and it is already in T9's
own task-brief. Left red and disclosed, exactly as instructed — not this
task's file or scope to touch.

**2. Gate 7's live run: exit 2 on the RET-07 rerank-flag check, root cause
diagnosed, ratified `max_tokens` fix tried at two values, neither
resolved it — new finding, stopped per the orchestrator's own 2-3-attempt
cap rather than guessing further.**

Five live runs total against the real corpus/questions, all recall@5 =
1.000 / MRR ranging 1.000-0.950 / page_hit_rate = 1.000 on every mode —
retrieval itself is solid. All five failed the identical two items
(`'Сколько дней отпуска полагается сотруднику в год?'`,
`'Сколько дней отпуска можно перенести на следующий год?'`) with
`rerank_failure='rerank returned no usable order'`, `hybrid+rerank`
mrr=0.950 every time:

- Runs 1-3, `_RERANK_MAX_TOKENS=128` (the spec literal): direct
  reproduction of the exact failing call returned `content=''`,
  `finish_reason='length'`, `reasoning_chars=556` — the model's whole
  128-token budget spent on chain-of-thought before any answer. Confirmed
  model-specific, not corpus/prompt-specific: the identical prompt against
  `openrouter` (`google/gemini-2.5-flash-lite`) returned a valid `'[1]'`
  in 0.6s, `reasoning_chars=0`. A first hypothesis (the LM Studio box
  swapping its resident model between indexing's embeddings calls and the
  first chat call, needing a warm-up before reranking) was implemented,
  tested live, and **disproved** — warm-up succeeded in 15.8s served by
  lmstudio, and the very next rerank call still came back empty with
  `finish_reason='length'`, not a timeout. Removed again as dead code
  motivated by a wrong theory rather than left in.
- Run 4, `_RERANK_MAX_TOKENS=1024` (operator-ratified): same two items,
  same failure string, same 0.950 MRR to three decimals. A direct,
  generously-timed (240s) reproduction of the same call *did* eventually
  succeed — `reasoning_chars=1853`, a valid `'[1, 2, 3, 5, 4, 6, 7, 8]'`
  — but took **89.5s**, vastly over `rag.py`'s own hardcoded
  `_RERANK_TIMEOUT_S=20.0`. This is new information the orchestrator's
  authorization didn't have: token budget alone may not be the binding
  constraint — the 20s per-call timeout is a separate, un-ratified
  parameter this task was not authorized to touch, and reasoning length
  for these two specific prompts appears to vary run to run.
- Run 5, `_RERANK_MAX_TOKENS=2048` (the orchestrator's explicit "try once
  more" cap): still the identical two items, identical failure string,
  identical 0.950 MRR. Raising the token ceiling further did not change
  the outcome, which weighs against "token budget alone" as the full
  explanation and toward some combination of the tight 20s timeout and
  genuine run-to-run variance in how much this model reasons for these two
  prompts specifically — a question this task's authorized scope (`rag.py`
  `max_tokens` only) cannot resolve further without guessing at
  unauthorized parameters (`_RERANK_TIMEOUT_S`, the rerank system prompt,
  or reasoning suppression itself).

Per the orchestrator's own instruction ("don't spiral past 2-3 attempts"),
stopping here rather than trying a third token value or touching anything
else in `rag.py`. `_RERANK_MAX_TOKENS` is left at `2048` (the last
authorized value; harmless headroom even though it didn't resolve this
specific case) pending further direction — most likely candidates for a
real fix, for the orchestrator to route: raise/remove
`_RERANK_TIMEOUT_S` for this call (a second, still-un-ratified `rag.py`
deviation), make `resolve_reasoning`'s `"off"` actually suppress reasoning
for a thinking model (closing the disclosed T5 erratum at its root rather
than working around its symptom), or operator model selection (a
non-thinking model for the rerank purpose).

**Offline gates are green apart from item 1** (the one expected, T9-owned
failure): `ruff check .` exit 0, `pytest` 1535 passed / 1 skipped / 1
failed (the disclosed one), `bot.py --selftest` exit 0. Everything for
this task is committed in one commit per the orchestrator's instruction,
with this Stop section as the record of gate 7's own outstanding, not
self-resolved, live-acceptance gap.
