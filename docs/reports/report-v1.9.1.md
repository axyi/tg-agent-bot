# tg-agent-bot v1.9.1 — patch report

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

## The measured evidence this release rests on

T2's own re-measurement (broader than T1's original five-row table),
against the real `evals/rag/corpus`, gold passage planted outside the
top-5 so reranking has to do real work — a verbatim port of
`_RERANK_SYSTEM` / `_rerank_messages` / `_parse_rerank_reply`. 10
answerable questions per run (5 for the first row — an earlier probe
build matched corpus filenames strictly and skipped the `.docx`/`.pdf`
converted names; the per-call numbers are unaffected).

| Backend | Model | max_tokens | schema | parsed | recall@5 | median s/call | completion tokens |
|---|---|---|---|---|---|---|---|
| LM Studio (box) | `qwen/qwen3.8-27b` — **v1.9.0 production** | 2048 | no | 5/5 | 5/5 | **196.9** | 695–1152 |
| LM Studio | `qwen/qwen3.8-27b` | 64 | yes | 0/10 | — | 16.4 | 35, content empty |
| LM Studio | `google/gemma-4-e4b` | 2048 | no | 10/10 | 9/10 | 35.9 | 132–688 |
| LM Studio | `google/gemma-4-e4b` | 512 | yes | 4/10 | — | 34.9 | 6 of 10 hit the cap |
| LM Studio | `google/gemma-4-12b-qat` | 64 | yes | 0/10 | — | 8.5 | 64, capped |
| LM Studio | `google/gemma-4-12b-qat` | 512 | yes | 3/10 | — | 47.5 | 7 of 10 hit the cap |
| OpenRouter | **`google/gemma-3-12b-it`** — chosen | 64 | yes | **10/10** | **10/10** | **0.83** | 10–53 |
| OpenRouter | `mistralai/mistral-nemo` | 64 | yes | 10/10 | 9/10 | 1.61 | 10–35 |
| OpenRouter | `mistralai/mistral-nemo` | 64 | no | 9/10 | 6/10 | 0.96 | 4–7 |
| OpenRouter | `ibm-granite/granite-4.0-h-micro` | 64 | yes | 10/10 | 8/10 | 1.25 | 10–39 |

Three conclusions, stated plainly:

1. `_RERANK_TIMEOUT_S` was 120.0 against a production median of 196.9 s.
   Gate 7 was never flaky — it was arithmetically impossible: 10 items ×
   196.9 s ≈ 1970 s against a 600 s gate timeout.
2. **Every chat model on the box is a thinking model**, `gemma-4` included —
   both local gemmas return *empty content* when the budget is small and hit
   the cap mid-reasoning at 512. The box holds no non-thinking chat model, so
   "use a smaller local model" is not available; that is why rerank routes out.
3. A JSON schema carries half the quality, not just the parse: without it
   `mistral-nemo` replies with two-element arrays that parse cleanly and leave
   eight of ten candidates in RRF order, recall@5 9/10 → 6/10.

Cost of the chosen route, at the prices read live from
`openrouter.ai/api/v1/models` on 2026-09-12 (`google/gemma-3-12b-it`:
$0.050/Mtok in, $0.150/Mtok out): ≈ **$0.0035 per gate-7 run** (≈60k in /
3k out including the smoke). Gate 7's own measured wall clock after the
fix: 287.388 s.

## Clean-context review (of `b959a63`)

One 🔴 finding: `tests/test_v190_retrieval.py`'s rerank-schema assertion
compared the recorded `response_format` to `rag._rerank_response_format(3)`
— both sides of the comparison came from the function under test, so any
bug inside it (a renamed key, a wrong type, an off-by-one
`minimum`/`maximum`) would have kept the assertion green.

Fixed in `9299da5` (prompt 161): rewritten against independent literals —
asserting a schema is sent (`sent["type"] == "json_schema"`), and that it
is sized to the candidates actually passed (`order["items"]["maximum"] == 3`,
`order["maxItems"] == 3`), not to `_HYBRID_CANDIDATES`. The schema's full
shape stays pinned independently in
`tests/test_v191_rerank_contract.py::test_t_v191_rerank_response_format_schema_shape`.

Mutation proof that the rewrite actually bites: with `"maximum": n` mutated
to `"maximum": n - 1` in `rag.py`, `tests/test_v190_retrieval.py` **fails**
(`assert 2 == 3`); reverted, it passes. Before the rewrite, the same
mutation left the tautological assertion green — proving the finding was
real, not stylistic.

## T3 — a retryable 429 was silently swallowed

T2's own authoritative gate run (below) hit gate 7 red on three consecutive
attempts, each failing a *different* subset of the 10 answerable items,
with `git diff --stat` confirming zero production files touched by T2 —
not a regression from the version bump. T2 stopped and reported per its
own brief's Stop clause rather than diagnosing or fixing a code-shaped
problem itself. `docs/spec/task-briefs/v191-T3.md` (prompt 163, `0f697df`)
did that diagnosis and fix, ahead of T2 in the commit log but documented
here as T2's own paperwork, exactly as T1 and the review fix are.

**Root cause.** `llm/base.py:401` already classifies an HTTP 429 as
`LLMError(retryable=True)`. `rag.rerank()` caught `LLMError` and returned
`None` without ever reading that flag — a transient, explicitly-retryable
upstream error degraded silently to RRF order and took gate 7 down with
it. A burst of 10 back-to-back rerank-shaped requests straight at
OpenRouter measured `google/gemma-3-12b-it` (T1's routed model) at 1/10 ok,
9× HTTP 429 — it is served by a single upstream that rate-limits a burst,
and gate 7 issues its rerank calls back to back.

**The fix.** `rerank()` now retries only when `LLMError.retryable` is
`True`, bounded by `_RERANK_MAX_ATTEMPTS = 3` with backoff `0.5s, 1.5s`
between attempts (module constants, not literals in the loop); a
non-retryable error or an unparsable reply is never retried (exactly one
call, same RRF fallback as before); exhausting all three attempts still
falls back to RRF with `rerank_succeeded=False` and a non-empty
`rerank_failure` — the gate can still see a real outage. Every retry, and
every successful retry, is logged with the attempt number (and elapsed
seconds on success). `.env.example`'s recommended
`LLM_RERANK_MODEL` moves to `openrouter:mistralai/mistral-small-24b-instruct-2501`
(10/10 on the same burst, best measured recall — 9/10 — among the models
that survive it). One new mutation entry, `v191-rerank-retry-dropped`
(drop the retry after the first retryable failure): killed. Gate 6 on
T3's own tree: 108/108.

**Disclosure (c) — a proposed model swap to `mistral-nemo` was measured
and withdrawn.** The 429 signal that first motivated considering
`mistral-nemo` instead of `mistral-small-24b-instruct-2501` came from a
gate-7 run that overlapped a mutation re-check
(`devtools/mutation_check.py` rewrites `rag.py` on disk per mutation and
restores it afterward — `rag.py` had the retry gate mutated out for ~73s,
restored 18:37:58) plus a burst of the coordinator's own probes against
the same upstream — both void runs, not evidence against the model. Three
clean, strictly sequential gate-7 runs afterwards, `rag.py`'s sha
`dbb834ae03af3597` verified identical before and after each, all exit 0,
zero 429s, 2m10–12s each. The swap was withdrawn on that evidence, not
kept as an unexamined footnote: `mistral-small-24b-instruct-2501` stays
the recommended route.

**Disclosure (d) — `_RERANK_TIMEOUT_S` 15.0 is itself measured, not
guessed.** Those same three clean runs all show one rerank call
succeeding only on its *third* attempt, after two 10.0s timeouts each —
every one of those passing gate-7 runs had zero retry budget left when it
finally passed. That is the measured basis for raising `_RERANK_TIMEOUT_S`
10.0 → 15.0 (worst case per item: `3*15.0 + (0.5+1.5) = 47.0s`, up from
32.0s) and for the successful-retry log line's existence: the gate was
passing on its last permitted attempt before this amendment landed.

**Gate 6 must never run concurrently with gate 7** (and vice versa):
`devtools/mutation_check.py` rewrites `rag.py` on disk per mutation and
restores it afterward, so a concurrent gate-7 run can import a
mid-mutation `rag.py` — exactly the void-run artifact disclosure (c)
describes. `config/quality_gates.yaml` is the sole authority on gate
membership, order and profile composition (`AGENTS.md`'s Local quality
gates section); its profiles run gates sequentially by construction — the
void runs were a manual, ad hoc concurrent invocation during T3's
investigation, not a defect in `checks.py run --profile full`'s own
ordering.

## Per-task delegation record

Required by `standards/reporting.md` § Run report whether or not a spec
asks for it (an incomplete record here is what `/verify-run` failed
v1.9.0 on):

- **T1** (`b959a63`, prompt 160) — delegated by task-brief file
  (`docs/spec/task-briefs/v191-T1.md`), per `AGENTS.md`'s Context
  discipline (writes source files across many modules — well past every
  threshold).
- **T1's clean-context review** — the review itself is one of the four
  closed-list exemptions verbatim: *the task is itself the clean-context
  review*.
- **The review-finding fix** (`9299da5`, prompt 161) — exemption verbatim:
  *a single edit under every threshold* (one assertion block, one test
  file, no production code).
- **T3** (`0f697df`, prompt 163) — delegated by task-brief file
  (`docs/spec/task-briefs/v191-T3.md`), per `AGENTS.md`'s Context
  discipline (writes source files — `rag.py`, two test files,
  `devtools/mutation_check.py` — well past every threshold). T2 (this
  task) was blocked on T3's gate-7 finding, resumed only after T3 landed,
  and documents T3 here as the paperwork owner, exactly as it documents
  T1 and the review fix.
- **T2** (this task, prompt 162) — delegated by task-brief file
  (`docs/spec/task-briefs/v191-T2.md`); this report's own delegation
  record names that brief as the delegation instrument, per the same
  convention T1 used.

Count: 3 delegated by task-brief file (T1, T3, T2) / 1 exempt (a single
edit under every threshold: the review fix) / 1 exempt (the task is
itself the clean-context review: T1's own review) / 0 unexplained.

## Gates — all seven, verbatim, in order

This is T2's own final, authoritative run — on the tree after T1
(`b959a63`), the review fix (`9299da5`), and T3 (`0f697df`), with every
version/paperwork edit already landed. Exit codes and wall clocks, not
verdict labels:

| # | gate | exit | wall clock | detail |
|---|---|---|---|---|
| 1 | `uv sync --locked` | 0 | 0.023s | resolved 23 packages, checked 21 |
| 2 | `uv run --locked ruff check .` | 0 | 0.041s | all checks passed |
| 3 | `uv run --locked pytest` | 0 | 1m12.127s | 1592 passed, 1 skipped (1593 collected) |
| 4 | `uv run --locked python bot.py --selftest` | 0 | 0.597s | `selftest: OK` |
| 5 | `uv run --locked python bot.py --selftest-live` | 0 | 11.363s | all seven live checks OK (config, db, docker 29.8.0, telegram, lmstudio, embeddings, openrouter) |
| 6 | `uv run --locked python devtools/mutation_check.py` | 0 | 61m38.574s | **108/108 killed**, 0 survived/errored/drifted (including `v191-rerank-retry-dropped`) |
| 7 | `uv run --locked python devtools/rag_eval.py` | 0 | 2m36.549s | `hybrid` recall@5=1.000, `hybrid+rerank` recall@5=1.000 (mrr 0.900), every answerable item's rerank flags both `True`; live log shows the retry loop firing for real — one call retried after an HTTP 429 and succeeded on attempt 2 (1.28s), another after two timeouts succeeded on attempt 3 (15.84s) |

**Gate 6 and gate 7 were run strictly sequentially, never concurrently**
(disclosure, T3 section above, explains why: `mutation_check.py` rewrites
`rag.py` on disk per mutation and restores it afterward, so a concurrent
gate 7 can import a mid-mutation `rag.py`). This is T2's *second* full
seven-gate run: the first (reported to the operator, not reproduced here)
hit gate 7 red three times in a row before T3's fix landed; this table is
the tree's final state, after T3, with all seven green.

Gate 7's advisory conversation-aware smoke **passed** this run ("turn 2
query 'количество недель отпуска в год' shares a token with turn 1's
question") — advisory only either way (`AGENTS.md`: "spends real
inference on the reranker **and an advisory** conversation smoke"), not
part of the exit code, and its earlier `fail` result in T1's own report
was already disclosed there as the main chat model's non-deterministic
tool-call choice, unrelated to rerank.

## Commit

One prompt → one commit, throughout this release:

- `b959a63` — T1 (prompt 160): the rerank contract.
- `9299da5` — T1's clean-context review fix (prompt 161): the tautological
  schema assertion.
- `0f697df` — T3 (prompt 163): the retryable-429 fix gate 7's own red run
  required, found by T2's authoritative gate run and out of a
  version-bump task's scope to fix directly.
- This task, T2 (prompt 162): the version bump and this release's
  paperwork, landed only after all seven gates are green on the final
  tree (below) — no self-referential SHA appears in this report, as it
  does not exist until after this commit.

## Ledger row (paste into `economics.md`)

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | v1.9.1 | 2026-09-12 | — (patch, no new spec; task briefs `docs/spec/task-briefs/v191-T1.md`, `-T2.md`, `-T3.md`) | 4 (160–163) | no — T2's first authoritative gate run hit a real gate-7 red (a retryable 429 silently swallowed by `rag.rerank()`), 1 of however-many-cycles-the-brief-permits repair cycles, fixed forward by T3 rather than inside T2 itself, then green on T2's re-run | 2 found / 2 fixed (gate 7 structurally red since v1.9.0 T8, fixed forward by T1; a retryable 429 silently degrading to RRF and failing gate 7, fixed forward by T3) | unknown (harness does not expose per-request usage) | unknown | claude-sonnet-5 (review fix: claude-opus-5) | Claude Code |
```

## Verdict

**All seven gates green, gate 7 green for real this time.** T1 fixed the
rerank contract (a `response_format` JSON schema, budgets sized to a
measured, non-thinking routed model); its clean-context review caught one
tautological test assertion, fixed in `9299da5`. T2's own first
authoritative gate run then found gate 7 genuinely red — not a version-bump
regression, but a pre-existing defect the version bump's own full-gate
discipline surfaced: `rag.rerank()` swallowed a retryable HTTP 429 instead
of retrying it, so a single-upstream model's burst-rate-limiting took the
whole gate down. T3 fixed that forward (a bounded, logged retry honouring
`LLMError.retryable`, plus a route change to a model that survives a
burst), with two of its own decisions backed by clean, contamination-free
evidence rather than the first (contaminated) signal: the model swap to
`mistral-nemo` was proposed, measured, and withdrawn; `_RERANK_TIMEOUT_S`
was raised from 10.0 to 15.0 on direct evidence of a too-tight budget, not
guessed. `docs/reports/report-v1.9.0.md`'s record of gate 7 shipping red
is untouched throughout, as the brief requires — this whole release fixes
it forward, never retroactively.
