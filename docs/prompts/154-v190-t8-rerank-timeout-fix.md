# Prompt 154 — v1.9.0 T8: the rerank-timeout fix attempt (gate 7, cont.)

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for spec-driven implementation tasks in this run (T1-T7 used the same model); continuation of prompt 153's own investigation.
- **Harness:** Claude Code
- **Stage:** T8
- **Owner of:** `rag.py` (`_RERANK_TIMEOUT_S`, operator-ratified, see Constraints); `tests/test_v190_retrieval.py` (matching assertion update)
- **REQ ids:** REQ-V190-EVAL-03, REQ-V190-EVAL-04 (gate 7's own live acceptance)

## Goal

Prompt 153 diagnosed gate 7's live exit-2 down to two candidate causes:
`rag.py`'s `_RERANK_MAX_TOKENS` (already bumped 128 -> 1024 -> 2048,
operator-ratified, neither value fixed it) and `_RERANK_TIMEOUT_S=20.0` --
a direct reproduction showed a valid rerank answer arriving at 89.5s, past
the old 20s budget. This prompt applies the orchestrator's further
ratified fix (`_RERANK_TIMEOUT_S` -> `120.0`) and re-runs gate 7 live one
more time to see whether the timeout, not the token budget, was the real
constraint.

## Constraints

**Operator-ratified deviation:** `rag.py:_RERANK_TIMEOUT_S` raised from
RET-06's literal `20.0` to `120.0`, for this one call only -- same class
of narrowly-scoped, call-specific departure as the `_RERANK_MAX_TOKENS`
bump (prompt 153), authorized after the 89.5s reproduction made the token
budget alone an incomplete explanation. `tests/test_v190_retrieval.py`'s
matching `timeout_s_calls == [...]` assertion updated in lockstep.
**Live-latency trade-off, disclosed:** `Searcher.search`'s rerank step is
synchronous inside a real user's `search_documents` tool call -- with
reranking on and this operator's chat model reasoning heavily, a turn can
now take up to 120s (was 20s) before `rerank()` gives up and falls back to
the plain RRF order. The fallback itself is unchanged and still never
fatal (`Searcher.search`'s `try/except Exception` boundary is untouched);
only the *ceiling* on how long a turn can wait before that fallback fires
has moved. Per the orchestrator's explicit instruction: no third
token/timeout escalation attempt, no touching the reasoning-suppression
machinery, no model swap -- this is the last change this task makes to
`rag.py`.

## Acceptance

`uv run --locked python devtools/rag_eval.py` live, one more time, exit 0
expected if the timeout was the true bottleneck. **Not met** -- see Stop.
Offline gates re-confirmed unaffected: `ruff check .` exit 0,
`bot.py --selftest` exit 0, `pytest` 1535 passed / 1 skipped / 1 failed
(only the known, T9-owned `test_v15_gate_04_*`, unchanged from prompt
153).

## Stop

**Gate 7's live run still exits 2 -- new information, not resolved, no
further attempt made per the orchestrator's explicit cap.**

With `_RERANK_TIMEOUT_S=120.0`, the run completed (no hard timeout this
time) with identical `recall@5`/`MRR`/`page_hit_rate` to every prior run
(`vector`/`hybrid` 1.000/1.000/1.000, `hybrid+rerank` 1.000/0.950/1.000 --
unaffected, since a failed rerank falls back to the already-correct RRF
order). But the **set of items whose rerank failed changed**: this run it
was `'За сколько дней до отпуска нужно подать заявление?'`, `'Какие
суточные положены за командировку по России?'`, and `'How long must
passwords be, at minimum?'` (three items, all with
`rerank_failure='rerank returned no usable order'`) -- a *different* and
*larger* set than every prior run's consistent two vacation-days items.
Six `"rerank fell back to rrf order"` warnings total were logged (three
gating answerable-item failures, plus non-gating advisory failures among
the two null items and/or the conversation smoke's own rerank calls,
which are not in the exit-code-gating set).

This is the new information the orchestrator anticipated: raising the
timeout did not converge on a fixed, explicable set of failing prompts --
it changed *which* prompts fail, consistent with genuine run-to-run
stochastic variance in how much this thinking model reasons per call,
not a deterministic prompt-content or fixed-budget problem addressable by
another constant bump. Per the explicit instruction, stopping here: no
third attempt, `_RERANK_TIMEOUT_S` stays at `120.0` and
`_RERANK_MAX_TOKENS` stays at `2048` (both already committed in
`4d4e02a`, this prompt's own `rag.py`/test changes not yet committed --
the orchestrator did not instruct a commit for this "still exit 2"
branch, only a report), reasoning-suppression machinery and model
selection untouched.

Root-cause summary for the record: the operator's deployed
`qwen/qwen3.8-27b` is a thinking-variant model; `resolve_reasoning("off",
...)` degrades to `"default"` rather than truly suppressing reasoning (T5's
own disclosed erratum), so this model spends a stochastic, sometimes-large
number of tokens/seconds reasoning before answering rerank's fixed-format
prompt. Neither a wider token budget (2048) nor a wider timeout (120s)
reliably closes the gap, because the binding constraint moves with the
model's own per-call reasoning-length variance, not with either configured
ceiling alone. A durable fix needs either genuinely suppressing reasoning
for this model class (closing the T5 erratum at its root) or an operator
model choice that does not reason for the rerank purpose -- both outside
this task's ratified, narrowly-scoped deviation budget.
