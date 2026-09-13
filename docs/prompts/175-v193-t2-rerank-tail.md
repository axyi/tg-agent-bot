# Prompt 175 — v1.9.3 T2: the rerank third-attempt tail, diagnosed then fixed

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a diagnosis-then-fix task against an existing task brief
  (`docs/spec/task-briefs/v193-T2.md`) — an in-process instrumented gate run
  located the exact wiring defect; the fix itself is a small, precisely
  scoped parameter threading, no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.3 T2 (patch, no new spec file), runs after T1
- **Owner of:** `devtools/rag_eval.py`, `devtools/mutation_check.py`,
  `tests/test_v190_eval.py`, `docs/reports/report-v1.9.3.md`,
  `docs/llm-usage.md`
- **REQ ids:** REQ-V190-EVAL-01..04, RET-06/-07

## Goal

Every clean gate-7 run since v1.9.1 T3 logged the same three lines at the
top of the captured output (two retry warnings, then a fallback or a
delayed success). The brief's own H1 (cold start)/H2 (item-bound) probe
found no reproducible slow call at all, in or out of process — because
neither hypothesis was the real one.

An in-process instrumented run of the real gate (`httpx.Client.post`
wrapped to log one line per rerank-shaped HTTP call, `rag_eval.main()`
called directly, three sequential runs) placed the tail precisely: not the
first rerank call of the process (an artefact of unbuffered stderr vs
buffered stdout — the warnings print first, chronologically they are
last), and not bound to any `questions.json` item — every one of the 36
deterministic per-item rerank calls across three runs was fast
(0.37–1.48s). The three ~15.0s timeouts, every run, attach to the
conversation-aware smoke turn's own agent-generated search query, with no
response body at all (`provider=None`) — and the identical query text,
reranked in isolation with the timeout raised to 60s, succeeds in
well under 1s. That rules out a genuinely slow upstream call.

The real defect: `devtools/rag_eval.py`'s `run()` builds its scored
`hybrid_rerank_searcher` with `llm=rerank_llm or llm` (the routed reranker
when `LLM_RERANK_MODEL` is configured — the same routing `bot.py:950-958`
uses for the live searcher), but `conversation_smoke()` took only `llm`
and built both of its own `rag.Searcher`s with `llm=llm` — the chat/agent
completion client, LM Studio primary via the failover wrapper. The smoke
turn's rerank calls were never reaching the fast, routed reranker at all;
they were reaching LM Studio (measured median 196.9s per rerank call,
v1.9.1), timing out at the gate's own 15.0s ceiling every time.

Fix: `conversation_smoke()` gains a `rerank_llm=None` parameter; both of its
`rag.Searcher` constructions use `llm=rerank_llm or llm`, the same
expression `run()`'s own `hybrid_rerank_searcher` (and `bot.py`'s live
searcher) already use. The call site passes `rerank_llm=rerank_llm`
through. New mutation entry `v193-smoke-reranks-on-chat-client` (reverts
`searcher1`'s routing back to the chat client), killed by
`test_t_v193_t2_conversation_smoke_reranks_via_rerank_llm_not_chat_llm`
(`tests/test_v190_eval.py`): two distinct `_DynamicRerankLLM` doubles as
`llm`/`rerank_llm`, asserting every rerank call reached `rerank_llm`
(`== 2`, one per turn — reverting either Searcher alone still fails this)
and the chat client received no rerank-shaped call at all.

`_RERANK_TIMEOUT_S`/`_RERANK_MAX_ATTEMPTS` are unchanged: this was never a
rerank-model or timeout-sizing problem.

## Constraints

Never read or print `.env`. Never open `evals/rag/corpus` files as
content. Nothing concurrent with gate 6 or any `--only`. No push.
`.env.example` unchanged (no new variable introduced).

## Acceptance

```
uv run --locked ruff check . ; uv run --locked ruff format --check .   # 0, 0
uv run --locked pytest                                                  # 0, 1605 collected
uv run --locked python bot.py --selftest                                # 0
uv run --locked python devtools/checks.py doctor                        # 0
uv run --locked python devtools/checks.py lint-docs                     # 0
<drift script>                                                          # 112/112
uv run --locked python devtools/mutation_check.py --only v193-smoke-reranks-on-chat-client   # killed
uv run --locked python devtools/rag_eval.py   x3                        # 0, 0, 0; zero retry lines; walls
```

## Stop

If a fresh three-run confirmation still shows any `rerank attempt … failed`
or `provider lmstudio failed` line during the smoke turn — stop and report
rather than declaring the fix proven.
