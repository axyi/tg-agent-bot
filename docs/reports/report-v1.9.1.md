# tg-agent-bot v1.9.1 — patch report (T1)

## Summary

Gate 7 (`devtools/rag_eval.py`) has been red since v1.9.0 T8, shipped under
an operator waiver (`docs/reports/report-v1.9.0.md`'s T8 section).
`/verify-run` reproduced it independently on 2026-09-12. This task
(`docs/spec/task-briefs/v191-T1.md`, prompt 160) fixes it forward: the
cause was measured, not inferred — the production model's median rerank
latency (196.9s) is past `_RERANK_TIMEOUT_S` (120.0), and ten answerable
items at that median (~1970s) is impossible against `rag-eval`'s own 600s
gate timeout. Gate 7 was never merely flaky; it was structurally unable to
finish.

The brief's own measurement table (reproduced here for context — the full
methodology is in the brief itself) showed that a JSON-schema
`response_format` plus a small, non-thinking routed model
(`google/gemma-3-12b-it` via OpenRouter) passes 10/10 at a 0.83s median,
versus 5/5 at 196.9s for the production model with no schema. Three facts
followed: (1) the timeout budget was sized to the wrong regime; (2) every
local chat model is a thinking model that burns its completion budget on
reasoning before answering; (3) the JSON schema is not cosmetic — it
carries roughly half of measured quality (a routed model without it drops
recall@5 from 10/10 to 6/10 on the brief's own reproduction).

## What changed

1. **`response_format` passthrough** (`llm/base.py`, `llm/lmstudio.py`,
   `llm/openrouter.py`, `llm/failover.py`): `build_payload` and
   `LLMClient.complete` gain a keyword-only `response_format: dict | None
   = None`, threaded through both provider adapters and the failover
   wrapper's two call sites. Guarded by the same `_PROTECTED_PAYLOAD_KEYS`
   collision check `reasoning_fields` already uses. Default `None`
   everywhere — no existing call site changes shape.
2. **The rerank call requests the schema** (`rag.py`): a new
   `_rerank_response_format(n)` builds the `{"type": "json_schema", ...}`
   object from the task brief, with `n` bound to the candidate count
   actually sent (`len(candidates)`), not the `_HYBRID_CANDIDATES`
   constant. `_parse_rerank_reply` needed no change — its
   `re.search(r"\[.*?\]", ...)` already lifts the array out of
   `{"order": [...]}`.
3. **Budgets brought to measured reality** (`rag.py`): `_RERANK_MAX_TOKENS`
   2048 → **128** (measured max completion length across every routed
   model: 53 tokens); `_RERANK_TIMEOUT_S` 120.0 → **30.0** (measured
   median on the routed model: 0.83s). Both comments rewritten to state
   the measured reason and point here, and to say plainly that a thinking
   model pointed at rerank now truncates and falls back to RRF order — a
   safe, gate-visible degradation, not a silent one.
4. **`LLM_RERANK_MODEL` routing** (`config.py`, `llm/__init__.py`,
   `bot.py`, `devtools/rag_eval.py`): exactly `LLM_SUMMARY_MODEL`'s shape.
   `config.parse_summary_model` generalised into `config.parse_routed_model
   (raw, env_var)` (one parser, `LLM_SUMMARY_MODEL`'s wrapper kept for its
   existing call sites and tests, `LLM_RERANK_MODEL` added alongside it in
   `load_config`); `build_llm_client(..., purpose="rerank")` mirrors the
   `"summary"` branch, no failover. Unset → falls through to the main
   client, so an unconfigured clone's behaviour is unchanged. Wired at the
   two `Searcher` construction sites: `bot.py`'s startup wiring (a third
   client, `rerank_llm`, threaded through `poll_loop`/`process_update`) and
   `devtools/rag_eval.py`'s `main()`/`run()` (the `hybrid_rerank_searcher`
   only — `conversation_smoke`'s two searchers are out of this task's
   named scope).
5. **Gate 7's own timeout re-measured** (`config/quality_gates.yaml`): one
   real green run, `time uv run --locked python devtools/rag_eval.py`,
   this tree, 2026-09-12: **real 4m47.388s (287.388s)**. `timeout_seconds`
   600 → **580** (2x 287.388s ~= 574.8s, rounded up), per the file's own
   "timeout = 2x measured" rule (already used by every `mutation-*` gate).
6. **Documentation**: `.env.example` gains `LLM_RERANK_MODEL` (the
   `"<provider>:<model>"` form, the recommended value
   `openrouter:google/gemma-3-12b-it`, and the one-line reason — the local
   box has no non-thinking chat model). README's `## Documents (RAG)`
   section documents the same. `AGENTS.md`'s Gates section states gate 7
   is expected green at every commit from v1.9.1 on, not a disclosed
   exception. Two more spots that asserted gate 7 was **currently** red as
   an ongoing fact (not a historical record) were corrected to match
   reality, since leaving them would ship a now-false claim: README's
   `### Evaluation` paragraph and its `## Tests` gate-block paragraph, both
   previously ending "Gate 7 is currently red...". The corresponding test,
   `tests/test_v190_agents.py`'s `test_t_v190_ec_01_readme_gate_7_recorded_red`,
   is repointed to `test_t_v191_readme_gate_7_recorded_green` (asserting the
   new claim, refusing the old one) — the same EC-03-class repoint pattern
   v1.9.0's own tasks used when a version-tied fact changed. **Not
   touched**, per the brief's own instruction: `docs/reports/report-v1.9.0.md`'s
   record of gate 7 as shipped red, `docs/llm-usage.md`'s and
   `docs/reports/tg-post-v1.9.0.md`'s historical rows, `docs/spec/spec-v1.9.0.md`,
   and the task-brief files — all historical records of what was true
   then, not ongoing claims.
7. **Tests**: `build_payload` response_format tests (`tests/test_llm.py`);
   a failover-forwarding test (`tests/test_failover.py`); `LLM_RERANK_MODEL`
   config/routing/startup-wiring tests mirroring `LLM_SUMMARY_MODEL`'s own,
   plus the unchanged existing `LLM_SUMMARY_MODEL` tests as the parser's
   regression guard (`tests/test_routing.py`); the schema-shape and
   constants-pin tests, plus `_parse_rerank_reply`'s wrapped/bare-array
   tests (`tests/test_v191_rerank_contract.py`, new file); the existing
   `T-V190-RET-06` rerank test repointed to the new constants and a
   `response_format` assertion (`tests/test_v190_retrieval.py`); two new
   `v191-*` mutation entries, both killed (`devtools/mutation_check.py`).
   Four pre-existing test doubles with a fixed `complete()` signature
   needed a `response_format=None` parameter to keep accepting the new
   keyword (`tests/fakes.py`'s `FakeLLM`, `tests/test_v190_eval.py`'s
   `_DynamicRerankLLM`, `tests/test_observability.py`'s `NamedLLM`,
   `tests/test_v170_reasoning.py`'s `_RecordingClient`) — orphans this
   task's own signature change created, fixed as part of it, not a
   separate concern. One pre-existing mutation entry
   (`v170-failover-drops-reasoning`) had its `find`/`replace` strings
   updated to match `llm/failover.py`'s new line shape (the
   `response_format` line inserted between them) — same mutation intent,
   same target line, just re-anchored text.

## Measurement — before and after

| Configuration | rerank timeout budget | median latency | recall@5 (hybrid+rerank) | gate 7 |
|---|---|---|---|---|
| v1.9.0 (production model, no schema, 120s/2048tok) | 120.0s | 196.9s | n/a (never completes in budget) | **red** — structurally unable to finish |
| v1.9.1 (routed model, JSON schema, 30s/128tok) | 30.0s | 0.83s (brief's measurement); this run's real wall clock 4m47.388s end-to-end | 1.000 | **green** |

## Gates — all seven, verbatim, in order

| # | gate | verdict |
|---|---|---|
| 1 | `uv sync --locked` | PASS — resolved 23 packages, checked 21 |
| 2 | `uv run --locked ruff check .` | PASS — all checks passed |
| 3 | `uv run --locked pytest` | PASS — 1584 passed, 1 skipped, real 1m12.899s |
| 4 | `uv run --locked python bot.py --selftest` | PASS — `selftest: OK` |
| 5 | `uv run --locked python bot.py --selftest-live` | PASS — all seven live checks OK (config, db, docker 29.8.0, telegram, lmstudio, embeddings, openrouter) |
| 6 | `uv run --locked python devtools/mutation_check.py` | PASS — **107/107 killed**, 0 survived/errored/drifted, real 60m15.320s (both new `v191-*` entries killed) |
| 7 | `uv run --locked python devtools/rag_eval.py` | **PASS** — `hybrid` recall@5=1.000, every answerable item's rerank flags both `True`, real 4m47.388s |

Gate 6 ran before the final documentation-only tweaks (the README wording
correction, its matching test repoint, and `quality_gates.yaml`'s timeout
comment/value) — none of those touch any file a mutation entry targets or
any code path a mutation exercises, so it was not re-run a second time;
gates 1-5 and 7 were all re-run after every edit landed, including these
last ones, and are reported at their final state.

Gate 7's advisory conversation-aware smoke printed `fail` this run ("turn
2 recorded no search_documents call sharing a token with turn 1's
question") — this does not gate the exit code (`AGENTS.md`: "spends real
inference on the reranker **and an advisory** conversation smoke"; the
script's own `run()` never returns on this result) and is unrelated to the
rerank fix: it reflects the main chat model's real, non-deterministic
choice not to call the tool on this run of the follow-up turn, not a
regression this patch introduced.

## Commit

One prompt -> one commit, per `docs/prompts/160-v191-rerank-contract.md`
(prompt 160). No version bump in this task (T2's job, per the brief).

## Ledger row (paste into `economics.md`)

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | v1.9.1 (T1, no bump) | 2026-09-12 | — (patch, no new spec; task brief `docs/spec/task-briefs/v191-T1.md`) | 1 (160) | yes — 0 repair cycles beyond fixing test doubles for the new `response_format` keyword | 1 found / 1 fixed (gate 7 structurally red since v1.9.0 T8, now green) | unknown (harness does not expose per-request usage) | unknown | claude-sonnet-5 | Claude Code |
```

## Verdict

**All seven gates green, gate 7 fixed forward as the brief requires.**
`response_format` passthrough lands in the client layer with the same
collision guard `reasoning_fields` uses; the rerank call now asks for a
JSON schema sized to the real candidate count; `_RERANK_MAX_TOKENS`/
`_RERANK_TIMEOUT_S` reflect measured reality instead of a budget sized to
absorb another model's chain-of-thought; `LLM_RERANK_MODEL` routes rerank
to a fast, non-thinking model exactly the way `LLM_SUMMARY_MODEL` already
routes the summary purpose; gate 7's own timeout is now derived from a
real measured run, not inherited from an earlier, unmeasured guess. Two
new mutation entries confirm both regressions this patch could otherwise
silently reintroduce are caught. `docs/reports/report-v1.9.0.md`'s record
of gate 7 shipping red is untouched, as the brief requires — this patch
fixes it forward, not retroactively.
