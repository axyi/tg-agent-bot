# tg-agent-bot v1.9.4 -- patch report

Operator's decision (`docs/spec/task-briefs/v194-T1.md`, verbatim,
2026-09-13): "Поехали 1.9.4 по всем трём предложенным пунктам и прочим
хвостам." Patch release, no spec file (precedent v1.5.1, v1.9.1-v1.9.3).
Five tasks: **T1** -- redaction at the logging layer (a `RedactingFormatter`
mechanism, closing the "no secret reaches a traceback today" guarantee-by-
inspection from the v1.9.3 T1+T2 review); **T2** -- gate-7 smoke; **T3** --
per-mutation timeout; **T4** -- the PTH/RUF043 ruff tail; **T5** -- version
bump and paperwork close. Baseline: `673f32f` (tag `v1.9.3`, pushed, clean).

## T1 -- redaction at the logging layer

Contract: `docs/spec/task-briefs/v194-T1.md`, prompt 181.

**The defect.** Redaction is call-site-only: `config.redact()` is called at
~105 sites by hand. At every `log.exception(...)` site, the traceback and
any chained `__cause__`/`__context__` are rendered by the `Formatter` from
`record.exc_info` and never pass through `redact()`. The v1.9.3 T1+T2 review
checked every site and found no registered secret reaching those exception
objects today -- a guarantee by inspection, not a mechanism.

**The seam.** `config.py` gains `class RedactingFormatter(logging.Formatter)`
whose `format()` renders through the base class, then returns `redact()` of
the rendered text -- because `Formatter.format` already renders the message,
its args, `exc_info` (via `formatException`) and `stack_info` into one
string, redacting that one rendered string covers all of them in one place.
Deliberately not a `logging.Filter`: a filter runs before the traceback is
rendered and would miss exactly the text this exists for. `redact()` reads
the live `_secrets` registry at format time, not a snapshot, so a secret
registered after the formatter is installed is still masked.
`config.install_redacting_logging(handler, fmt, datefmt=None)` is the one
call every entry point makes to attach it.

Four independent logging entry points, closed as follows:

- `bot.py`'s `main()` -- `logging.basicConfig(...)` replaced with the same
  guard `basicConfig` itself uses (act only when the root logger has no
  handler yet), building a `StreamHandler(sys.stderr)` and installing the
  redacting formatter on it explicitly. Format string, stream and level are
  unchanged.
- `devtools/bench.py`'s `_configure_logging` -- its own `FileHandler` (which
  already tears down every pre-existing root handler) now carries the
  redacting formatter instead of a plain one.
- `devtools/rag_eval.py`'s `main()` -- had no logging configuration of its
  own, so its records went to `logging`'s unredacted `lastResort` stderr
  handler. Gained a `basicConfig`-equivalent through the same helper, so
  gate 7's own warnings are covered too.
- `dashboard_server.py` -- gains no separate configuration. Its
  `log = logging.getLogger("dashboard")` (line 35) inherits whichever root
  config the hosting process installed: `bot.py` builds the dashboard server
  via `dashboard_server.build_server(...)` and starts it in a daemon thread
  (`bot.py`'s `main()`, around line 2077-2088) strictly after `main()`'s own
  logging setup above has already run, so the dashboard thread's log records
  pass through the same redacting formatter as the rest of the bot process.

**Tests** (`tests/test_v194_redaction.py`, `caplog` not used for any
assertion -- it captures records before the formatter runs; each test builds
its own logger with a `StringIO`-backed handler carrying the redacting
formatter and asserts on the emitted text):

1. `test_t_v194_red_01_message_args_masked_in_emitted_line` -- a registered
   secret passed as a `%s` message argument is masked in the emitted line.
2. `test_t_v194_red_02_exception_str_masked_in_traceback` -- a registered
   secret inside `str(exc)` of an exception logged via `log.exception` is
   masked in the rendered traceback text.
3. `test_t_v194_red_03_chained_cause_masked` -- a registered secret inside a
   chained `__cause__` (`raise X from Y` where `str(Y)` carries the secret)
   is masked in the traceback's "direct cause" section.
4. `test_t_v194_red_04_secret_registered_after_install_still_masked` -- a
   secret registered strictly after the formatter is constructed and one
   line already emitted is still masked in a later line, proving the
   formatter reads the live registry rather than a snapshot.
5. `test_t_v194_red_05_entry_points_install_redacting_formatter` -- with the
   root logger's handlers cleared and restored around each check,
   `bot.main(["--selftest"])`, `devtools.bench._configure_logging` and
   `devtools.rag_eval.main()` (its own `load_config` stubbed to raise
   immediately, so this test never touches `.env`) each install exactly one
   root handler whose `formatter` is `config.RedactingFormatter`.

**Mutation coverage** (`devtools/mutation_check.py`, left for the
coordinator to run via `--only` after commit):

- `v194-redacting-formatter-skips-redact` -- mutates
  `RedactingFormatter.format` to return the rendered text unredacted; killed
  by tests 1-3 (message-args, exception-str and chained-cause secrets all
  reach the emitted text unmasked once redaction is skipped).
- `v194-bench-logging-unredacted` -- mutates `devtools/bench.py`'s
  `_configure_logging` to attach a plain `logging.Formatter` instead of the
  redacting one; killed by test 5's bench assertion.

Every existing `redact()` call site is kept untouched -- removing them would
be a large diff with mutation-`find` fallout, and defence in depth (both the
call-site guards and the logging-layer mechanism active at once) is the
intended end state, not a replacement of one by the other.

**Correction (added at the v1.9.4 review, finding 2).** `RedactingFormatter.
format()` redacted only its own returned string; `logging.Formatter.format`
(stdlib) caches the unredacted traceback onto `record.exc_text` as a side
effect before this class's own `redact()` call ever sees it, so a second
handler on the same record with a plain `Formatter` would have read that
cached attribute back raw. Fixed: `format()` now also redacts `record.
exc_text` in place once populated. Latent today (every entry point installs
exactly one handler) but closed rather than left as a documented risk. New
test `test_t_v194_red_03b_second_plain_handler_reads_redacted_exc_text`
(two handlers on one logger, the second with a plain `Formatter`, same
chained-exception record -- both outputs masked). Mutation entry
`v194-redacting-formatter-skips-redact` re-derived (its `find` text moved
when `format()` grew a second statement); same semantics, killed again.

**Delegation record.** Executor model: `claude-sonnet-5` (Claude Code). This
subagent performed the implementation directly (seam, four entry points,
five tests, two mutation entries, paperwork) against
`docs/spec/task-briefs/v194-T1.md`; the coordinator verifies the report
against the brief and commits. Finding 2 (below) was closed later, at the
v1.9.4 review.

## T2 -- gate-7 smoke

Contract: `docs/spec/task-briefs/v194-T2.md`, prompt 182.

**The two facts from v1.9.3.** (1) Turn 2's token-overlap verdict cannot
fail for a real reason today: every run answers "28 дней -- это 4 недели"
from turn 1's own context without a `search_documents` call, a *correct*
answer the check reports as `fail`, indistinguishable from a real
REQ-V190-TOOL-06 regression. (2) The smoke turns' chat completions, not
retrieval, are gate 7's wall (253s of 268s in the v1.9.3 T1+T2 review's
instrumented run).

**Route (a) kept.** `spec-v1.9.0.md:1158-1164` (REQ-V190-TOOL-06) pins turn
1 -> turn 2 exactly as shipped; `spec-v1.9.0.md` itself is not edited. A
third turn is added instead of changing the pinned pair.

**Turn 3 -- context-proof.** `_SMOKE_FOLLOWUP_2 = "а сколько из них можно
перенести на следующий год?"` -- a paraphrase of `evals/rag/questions.json`
item 1 ("Сколько дней отпуска можно перенести на следующий год?", gold
`vacation_policy.md`), phrased so it cannot be answered from turns 1-2's own
context. `_RecordingSearcher` now also keeps each call's `SearchResult`.
Verdict: `pass` iff turn 3 made >= 1 `search_documents` call **and** at
least one call's returned passages carry the gold source **and** its gold
evidence (`_SMOKE_GOLD_EVIDENCE_2 = "не более 10 дней"`, tightened at the
v1.9.4 review's finding 3 -- originally filename-only, which any
vacation-related hit would satisfy since turn 1 already proves the same
file is reachable; `contains_evidence`, the same filename-AND-evidence
matcher `first_hit` uses for the scored questions) -- `fail` with the
recorded queries and top sources otherwise. This proves the third turn's
search actually retrieved the passage that answers the transfer question,
not merely that some vacation-related page was found; it still does not
prove the query *used* turns 1-2's context to get there (a query naming
the transfer rule directly, without drawing on prior-turn context, would
also pass) -- the TOOL-06 pin covers context carry, this verdict covers
"went to the documents for the new fact." Turn 2's own
verdict is unchanged in substance; `conversation_smoke()` now returns
`(tool06_ok, tool06_detail, context_proof_ok, context_proof_detail)` and
`run()` prints both as separate advisory lines (`conversation-aware smoke
(TOOL-06 pin): ...` / `conversation-aware smoke (context-proof): ...`),
neither affecting the exit code.

**The opt-in route.** `LLM_EVAL_CHAT_MODEL` (`config.py`'s
`llm_eval_chat_model`, `llm/__init__.py`'s `purpose="eval-chat"`) mirrors
`LLM_RERANK_MODEL` exactly: unset (the default), `rag_eval.run()`'s smoke
turns build their chat client exactly as before (`eval_chat_llm or llm`,
provably `llm` when unset); set, they route to the given
`<provider>:<model>` instead. `.env.example` documents it commented out.

**Offline tests.** `tests/test_v190_eval.py`'s smoke script extended to
three turns, plus `test_t_v194_t2_conversation_smoke_turn3_calls_search_and_
hits_gold` / `..._and_misses_gold` / `..._makes_no_call`;
`tests/test_routing.py` gained the `eval-chat` purpose's config/routing
cases mirroring the existing `rerank` ones. Mutation entry
`v194-smoke-turn3-gold-unchecked` (the gold-source condition dropped from
turn 3's verdict) killed by the miss-gold test.

**Measurement.** Two fixed-tree runs per route (`505bbf7`), alone on the
box, nothing else running, instrumented from outside (`agent.
run_agent_outcome` and `rag.Searcher.search` wrapped with timestamps, the
same technique as the v1.9.3 T1+T2 review's `gate7_phased_smoke_probe.py`,
scratch script never committed):

| run | env | wall | smoke verdicts | retry lines |
|---|---|---|---|---|
| A1 | production route (unset) | 557.692s | TOOL-06 pin: pass; context-proof: pass | none |
| A2 | production route (unset) | 549.801s | TOOL-06 pin: pass; context-proof: pass | none |
| B1 | `LLM_EVAL_CHAT_MODEL=openrouter:mistralai/mistral-small-24b-instruct-2501` | n/a (all 3 turns errored) | TOOL-06 pin: fail (no call); context-proof: fail (no call) | none |
| B1' | `LLM_EVAL_CHAT_MODEL=openrouter:mistralai/mistral-nemo` (brief's contingency, tried once after B1 failed) | 18.116s | TOOL-06 pin: fail (no call); context-proof: fail (no call) | none |
| B2' | `LLM_EVAL_CHAT_MODEL=openrouter:mistralai/mistral-nemo` | 15.544s | TOOL-06 pin: fail (no call); context-proof: fail (no call) | none |
| C1 | `LLM_EVAL_CHAT_MODEL=openrouter:openai/gpt-4o-mini` (addendum, prompt 185) | 17.196s | TOOL-06 pin: fail (no call); context-proof: fail (no call) | none |
| C2 | `LLM_EVAL_CHAT_MODEL=openrouter:google/gemini-2.5-flash` (addendum) | 17.837s | TOOL-06 pin: fail (no call); context-proof: fail (no call) | none |
| D1 | `LLM_EVAL_CHAT_MODEL=lmstudio:qwen/qwen3.5-9b` (addendum, first/JIT run) | 121.923s | TOOL-06 pin: fail (no call, answered from context); context-proof: pass | none |
| D2 | `LLM_EVAL_CHAT_MODEL=lmstudio:qwen/qwen3.5-9b` (addendum, second/steady-state run) | 121.404s | TOOL-06 pin: fail (no call, answered from context); context-proof: pass | none |

`mistralai/mistral-small-24b-instruct-2501` cannot complete the agent loop's
tool-calling request at all through OpenRouter: every one of the three
smoke turns returned HTTP 404, `"No endpoints found that support tool
use. Try disabling \"exec\"."` -- a provider-routing limitation of that
model/quantization pairing on OpenRouter today, not a bug in this repo's
code (the same model completes gate 7's own rerank calls, purpose=
`"rerank"`, without tools, successfully in every run above). Per the
brief's contingency, `mistralai/mistral-nemo` was tried once (B1') and
mechanically can make tool calls (it called `exec('date')` once in B1'),
but never called `search_documents` in either nemo run -- both turn 3
verdicts read `fail` for a real reason (the model answered from its own
un-grounded guess: "21 рабочих дня в год", "14 дней", "6 рабочих дней",
none matching the corpus), not a harness defect.

**Addendum (prompt 185, docs-only follow-up commit, after this task's own
commit landed).** The coordinator's own review of the B-row results found
they settled the two named models, not the route: measure three more
candidates, one gate-7 run each (the local model run twice, JIT load on
first call), same instrumented technique, ≤ $0.20 budget. C1
(`openai/gpt-4o-mini`, the reference tool-caller) and C2
(`google/gemini-2.5-flash`) both **never called `search_documents` in any
of their three turns** -- C1 answered every turn from its own general
Labor-Code knowledge (ungrounded but fluent), C2 flatly declined all three
("no access to that information"). Since C1 is a strong, reliable
tool-caller in general use and still made zero tool calls here, **the
smoke's own turn-1 prompt does not compel a `search_documents` call for
every capable model** -- this is a property of the prompt/tool-exposure,
not evidence against any one model, exactly the addendum's own hypothesis.
D1/D2 (`lmstudio:qwen/qwen3.5-9b`, local, run twice) both called
`search_documents` on turns 1 and 3 and both turn-3 calls hit the gold
source (context-proof: pass on both runs) -- the smoke is meaningful on
this model -- but wall stayed ~121s on both D1 and D2, no JIT-load
speedup observed on the second run (the box appears to swap the loaded
LM Studio model between the embedding calls and this chat model within
one run, so every run re-incurs a load-like cost, not just the first).
No retry/429 lines in any of the four addendum runs.

Per-turn completion times (seconds, `smoke turn N: start`/`done` deltas):

| run | turn 1 | turn 2 | turn 3 |
|---|---|---|---|
| A1 (production) | 173.828 | 220.419 | 151.238 |
| A2 (production) | 203.718 | 182.731 | 149.292 |
| B1' (nemo) | 0.977 | 1.688 | 0.926 |
| B2' (nemo) | 0.877 | 0.612 | 0.521 |
| C1 (gpt-4o-mini) | 1.042 | 0.643 | 0.970 |
| C2 (gemini-2.5-flash) | 0.814 | 0.661 | 0.657 |
| D1 (qwen3.5-9b, run 1) | 52.318 | 12.773 | 44.799 |
| D2 (qwen3.5-9b, run 2) | 47.766 | 12.769 | 45.557 |

**Recommendation (revised, full table).** Leave `LLM_EVAL_CHAT_MODEL`
unset in `.env` -- still the right call, but for a sharper reason after
the addendum: no candidate tried across either round beats the production
route on *both* speed and a meaningful smoke simultaneously. The two
OpenRouter models that fail to call a tool at all (`mistral-small-24b`,
structurally, 404) or fail to call the *right* tool (`mistral-nemo`) are
joined by two more capable OpenRouter models (`gpt-4o-mini`,
`gemini-2.5-flash`) that also never call `search_documents` -- strong
evidence the smoke's own prompt, not model capability, is why the fast
OpenRouter route goes silent, so no OpenRouter substitute is likely to
fix this without a prompt change (out of this task's scope). The one
route that *did* stay meaningful, `lmstudio:qwen/qwen3.5-9b` (both
context-proof verdicts pass), bought no wall-time win at all (~121s vs.
production's ~550-560s is still a ~4.5x cut, but nowhere near the
OpenRouter routes' ~30x, and the local box already runs the production
model too, so this doesn't reduce contention). The production route
(`qwen/qwen3.8-27b` on LM Studio) stays the default, correctly exercising
both verdicts as `pass` on both A1 and A2. `config/quality_gates.yaml`'s
`rag-eval.timeout_seconds` is re-derived from A1/A2 (the production
route, the default) under the file's own rule: slowest wall 557.692s ->
2x ~1115.4s, rounded up to **1120s** (was 580s -- already only 22s above
A1's own wall, effectively unsafe with the third turn added) -- this
figure is unchanged by the addendum, which touched no OpenRouter/LM
Studio route the gate runs by default.

**Wall attribution (added at the v1.9.4 review, prompt 186 -- a hypothesis
with the numbers, not a finding).** The growth from v1.9.3's 268s to this
task's 557s (A1) is not cleanly "the third turn's fault": the per-turn
table above shows turns 1+2 *alone* already grew from v1.9.3's combined
253s to 394.247s (A1: 173.828+220.419) / 386.449s (A2: 203.718+182.731) --
a 133-141s growth with no turn added there at all -- while turn 3 itself
contributes ~150s (151.238s A1 / 149.292s A2) of the remaining delta.
133-141s of the ~289s total growth is therefore unattributed to any code
change in this release. The addendum's D1/D2 rows are the only direct
evidence available: `lmstudio:qwen/qwen3.5-9b` showed no JIT-load
speedup on its second run (121.923s -> 121.404s, essentially flat)
despite being "already loaded" from the first run, consistent with LM
Studio swapping the loaded chat model out between calls to a *different*
model (the embedding model, used before/between turns for retrieval) and
back, paying a reload-like cost on every call rather than only the first
one. This does not, however, cleanly explain turn 2's own growth in
particular: turn 2 makes no retrieval call at all (no embedding-model
swap should intervene) yet is the single slowest turn in A1 (220.419s).
Stated honestly as a hypothesis the numbers are consistent with, not a
proven mechanism -- **v1.10 candidate: instrument LM Studio's own loaded-
model state (or its request log) across a full gate-7 run to measure
model swaps directly**, rather than inferring them from wall time alone.

**v1.10 candidate (added at the v1.9.4 review, prompt 186): the smoke's
own prompt may not compel a document search.** The review's own
instrumented confirmation run (`gpt-4o-mini` route) found the same thing
this task's addendum found: `tools=4`, `tool_choice=auto` and identical
budgets reach the model correctly (this is not a route defect), yet
`gpt-4o-mini` -- a strong, reliable tool-caller in general use -- answers
turn 1 entirely from its own general knowledge instead of calling
`search_documents`: `"Согласно Трудовому кодексу Российской Федерации,
минимальная продолжительность е"` (80 characters, the instrumented
probe's own truncation; the full reply continues fluently and never
invokes a tool). The candidate for v1.10: the agent's system prompt / the
`search_documents` tool's own description does not compel a document
search for a user who has documents indexed and a question those
documents can answer -- a general-knowledge-capable model will answer
from its own training data instead when nothing forces it to check the
user's documents first. Out of this task's scope (a smoke-test
measurement task, not a system-prompt change), but worth a dedicated
v1.10 item.

**Cost (revised at the v1.9.4 review, prompt 186 -- corrected run count and
tally).** Ten live gate-7 runs' inference to date, not five: this task's
own A1/A2/B1/B1'/B2' (5), the addendum's C1/C2/D1/D2 (4, `docs/prompts/
185-v194-t2-measurement-addendum.md`), and the review's own confirmation
run on the `gpt-4o-mini` route (1, cited in `docs/spec/task-briefs/
v194-review.md`) -- tallied by hand from each run's own `llm_call` log rows
(this harness does not attach `cost_usd` on this path):

- `mistralai/mistral-small-24b-instruct-2501`, `rerank` purpose (every run
  above routes its 12 scored retrieval items' rerank through it,
  regardless of which route the smoke turns used): 135,177 prompt + 2,653
  completion tokens across 118 calls.
- `mistralai/mistral-small-24b-instruct-2501`, `agent` purpose (B1's three
  404 attempts): 0 billable tokens, 3 calls.
- `mistralai/mistral-nemo`, `agent` purpose (B1'/B2'): 5,183 prompt + 78
  completion tokens across 7 calls.
- `openai/gpt-4o-mini`, `agent` purpose, combined across this task's own
  C1 and the review's own repeat run: 3,155 prompt (1,576 + the review's
  1,579) + 267 completion tokens (131 + 136).
- `google/gemini-2.5-flash`, `agent` purpose (C2): 1,314 prompt + 90
  completion tokens across 3 calls.
- `lmstudio:qwen/qwen3.5-9b` (D1/D2): local, no token cost.

At each OpenRouter model's public list price (all low-cost tiers, well
under $0.10/1M tokens blended), this totals well under $0.10 across all
ten runs combined -- comfortably inside T2's own $0.30 cap and the
addendum's separate $0.20 cap; no exact per-request cost is exposed to
this session, so this remains a bounds estimate, not a metered figure.

**Delegation record.** Executor model: `claude-sonnet-5` (Claude Code). The
offline half (turn 3, the opt-in routing purpose, tests, mutation entry,
paperwork) was implemented by a subagent against
`docs/spec/task-briefs/v194-T2.md`, offline acceptance verified independently
by the coordinator; the coordinator then ran the five live measurement runs
above directly (real money, sequenced alone on the box), decided the
recommendation, re-derived the gate timeout, and finishes this report
section, `docs/llm-usage.md` row 92, and the commit.

## T3 -- hung mutation reported by id

Contract: `docs/spec/task-briefs/v194-T3.md`, prompt 183.

**The gap.** The only timeout around a mutation run was the gate's own
(`config/quality_gates.yaml`'s `mutation-all.timeout_seconds`, 1530s): if one
`pytest` invocation hangs, the whole gate runs to 1530s and the output names
no mutation at all -- the operator cannot tell "one hung" from "the box was
slow".

**The fix.** `devtools/mutation_check.py`'s `default_runner` now bounds its
child with `proc.wait(timeout=_MUTATION_TIMEOUT_S)` (`_MUTATION_TIMEOUT_S =
180.0`, sized at >2x the slowest legitimate single run measured on this box,
the ~70s single-process full-suite fallback for a survivor from v1.9.2 T2 --
also small enough that the gate's own 1530s budget still catches roughly 8
hung mutations before the gate itself trips). On `subprocess.TimeoutExpired`
it terminates the child via the existing `_terminate_current_child()` (the
same process-group SIGTERM-then-SIGKILL path a signal already uses --
reused, not reimplemented), prints the mutation id and elapsed time, and
returns a sentinel exit code (`_HUNG_EXIT_CODE = 124`, coreutils' own
`timeout` exit code) that `run_one`'s existing exit-code mapping (`1`
KILLED, `0` SURVIVED, anything else ERRORED) already classifies `ERRORED`
with no changes to `run_one`/`run_all`. No fifth outcome string. Tree
restoration goes through `run_one`'s existing `finally:
restorer.restore_one(path)`, confirmed unchanged -- no second restore path
was added.

One incidental fix during implementation: the new `_terminate_current_child()`
call site inside `default_runner` needed a distinguishing trailing comment,
since its bare call would otherwise have been byte-identical to the existing
`v193-signal-handler-leaves-child-running` mutation's own `find` string,
breaking that entry's "exactly once in the file" invariant -- no behaviour
change, confirmed by the drift script (119/119 matched after).

**Tests.** `tests/test_mutation_check.py` gains
`test_t_v194_t3_hang_is_errored_with_id_and_tree_restored` (a real child --
`sleep 30` substituted for the real pytest invocation via a monkeypatched
`Popen`, under `_MUTATION_TIMEOUT_S = 0.5` -- so the real SIGTERM/SIGKILL
group-terminate path is exercised; the run itself happens inside a
throwaway `python -c` subprocess bounded by `subprocess.run(timeout=5)`,
since `run_all` installs signal handlers via `signal.signal()`, which only
works on a process's main thread and so cannot be hosted in a plain
`threading.Thread` as the brief's own suggested mechanism assumed -- the
brief explicitly leaves the mechanism negotiable) and
`test_t_v194_t3_normal_kill_within_timeout_unaffected_by_hang_guard` (an
ordinary `KILLED` run is unaffected by the new guard). Mutation entries:
`v194-mutation-hang-unbounded` (`wait(timeout=...)` reverted to a bare
`wait()`) and `v194-mutation-hang-reported-as-killed` (the timeout branch's
sentinel mapped to `1`/KILLED instead) -- both killed by test 1, run by the
coordinator after commit (`mutation_check.py` is itself a mutation path).
`AGENTS.md`'s gate-6 paragraph gained one sentence naming this behaviour;
no count literal in it was touched.

**Acceptance record (added at the v1.9.4 review, finding 6): prompt 183's
own `--select v15-` acceptance run (4/4 killed, the real end-to-end path
with the new `wait(timeout=...)`) was performed at the time but its wall
was never recorded anywhere. Re-run once, alone, as part of this review's
own closure: see the "Review (prompt 186)" section's Acceptance below for
the wall.

**Delegation record.** Executor model: `claude-sonnet-5` (Claude Code). This
subagent performed the implementation and its own offline acceptance
directly against `docs/spec/task-briefs/v194-T3.md` (no live/paid
component); the coordinator independently re-ran acceptance, verified the
diff, and committed.

## T4 -- the "not now" ruff rows, now

Contract: `docs/spec/task-briefs/v194-T4.md`, prompt 184.

**Closed.** The two remaining "not now" rows of v1.9.3 T3's ruff decision
table: `PTH*` (18 hits: `os.chmod`/`os.stat`/`os.unlink`/`os.path.islink`/
`os.path.exists`/`os.path.join`/`open()` sites across `bot.py`, `storage.py`,
`tools.py` and three test files) and `RUF043` (1 hit: an ambiguous
`pytest.raises(match="bogus.key")` in `tests/test_v160_observability.py`,
`.` a regex metacharacter, fixed with `re.escape(...)`, discrimination
verified by hand against a mutated message before landing). Both now join
`[tool.ruff.lint].select`. `PLW0603`'s row moves from "not now" to "never"
(the module-state pattern `_shutdown`/`_started_at`/`_dropped_spans` rely
on) with no change to its lint behaviour.

**Per-rule tally:** PTH101 5 (`storage.py` `_restrict_permissions` x3,
`bot.py` `_remove_sandbox_entry` x1, `tools.py` `append_audit` x1); PTH116 5
(`bot.py` `_refuse_shared_parent` x1, `tests/test_tool_output.py`'s
hardlink/inode test x4); PTH123 4 (`tools.py` `_process_start_ticks`'s
`/proc/<pid>/stat` open, `tests/test_v170_bench.py` x3); PTH110/PTH114/
PTH118/PTH108 1 each (`tools.py`'s `append_audit`/`sandbox_usage`, `bot.py`'s
`_remove_sandbox_entry` x2); RUF043 1. **19/19 fixed, zero `noqa`** -- no
`storage.py` rewrite changed a mode bit or exception path, so the brief's
own escape hatch was never needed. Every rewrite kept identical semantics:
`storage.py`'s `Path(str(db_path) + suffix)` string-arithmetic (never
`.with_suffix`, which would replace the `.db` extension) and its exact
`FileNotFoundError` suppression scope; `tools.py`'s `append_audit` left its
raw `os.open`/`os.fdopen` fd pair (`O_WRONLY | O_APPEND | O_CREAT` with an
explicit `0o600` create mode) untouched -- not equivalent to `Path.open()`.
`devtools/bench_scenarios.py` (byte-hash-frozen, REQ-V13-BEN-12) has no
PTH/RUF043 hits, so no new `per-file-ignores` entry was needed.

One unplanned, in-scope adaptation: `tests/test_v12_patch.py`'s
`test_t_v12_orp_01_start_ticks_survives_a_space_in_comm` monkeypatched the
module-level `tools.open`, which `_process_start_ticks`'s rewrite
(`open(...)` -> `Path(...).open(...)`) no longer calls -- adapted to
monkeypatch `Path.open` instead, same fake-`io.StringIO` fixture, same
assertion, no behaviour change to the code under test. `pytest`'s collected
count moved 1631 -> 1631 passed (unchanged pass/skip split; no test added
or removed, only one adapted).

**Drift/re-derive record.** Two of 119 mutation entries drifted after
`bot.py`'s rewrite (both matched the old `os.chmod(path, ...)`/
`os.path.islink(path)` lines, which no longer exist verbatim):
`sec-qta-03-chmod-and-retry` (`find` re-derived to
`"            p.chmod(stat.S_IRWXU)\n"`) and `v13-symlink-chmod` (`find`
re-derived to `"            if p.is_symlink():\n                continue\n"`),
both with identical mutation semantics against the new pathlib shape.
Drift script after re-derivation: 119/119 matched, 0 drifted. Both
re-derived entries run by the coordinator via `--only` after commit (below).

README.md and AGENTS.md were grepped for "PTH"/"RUF043"/"PLW0603" -- neither
names a count for these rules, so neither needed an edit.

**Delegation record.** Executor model: `claude-sonnet-5` (Claude Code). This
subagent performed the implementation and its own offline acceptance
directly against `docs/spec/task-briefs/v194-T4.md`; the coordinator
independently re-ran acceptance, verified the diff and the two re-derived
mutation entries, and committed.

## Review (prompt 186) -- clean-context findings closed

Review of `505bbf7` `b5db300` `4667d16` `4253678` `fcb7ec8` (opus, clean
context; every probe re-run; six `--only` kills; one instrumented gate-7 run
on the `gpt-4o-mini` route). No 🔴. Contract: `docs/spec/task-briefs/
v194-review.md`, prompt 186. One commit closes all eight findings.

1. 🟠 `devtools/rag_eval.py` root logger at `INFO` -> `WARNING` (~88 INFO
   lines/run no longer bury `checks.py`'s stderr tail). Test extended.
2. 🟡 `RedactingFormatter` now also redacts the cached `record.exc_text`,
   not just its own returned string -- see T1 section's "Correction" above.
3. 🟡 Turn 3's gold matcher tightened to filename **and** evidence (`first_
   hit`'s own convention) -- see T2 section's "Turn 3 -- context-proof"
   paragraph above, updated in place.
4. 🟡 T2's Cost paragraph corrected: ten live runs, not five (see T2
   section's "Cost" paragraph, rewritten in place).
5. 🟡 `docs/llm-usage.md` row 94: "`PTH*` (19 hits" corrected to "18 hits,
   19 total with `RUF043`".
6. 🟡 T3's `--select v15-` acceptance wall, never recorded: see this
   section's own Acceptance below.
7. 🟡 Gate-7 wall attribution: a hypothesis-with-numbers paragraph added to
   T2 (turns 1+2 alone already grew 253s -> 386-394s, unexplained by the
   third turn; a v1.10 item to measure LM Studio model swaps directly, not
   infer them from wall time). `docs/prompts/185-...md`'s "sixteen-row"
   and `docs/llm-usage.md` row 95's "eight-row" both corrected to the
   table's real nine rows.
8. 🟡 The review's own `gpt-4o-mini` confirmation (tools reach the payload
   correctly; the model still answers from general knowledge) added to T2
   as a v1.10 candidate -- see T2 section's second new paragraph above.

**Delegation record.** Executor model: `claude-sonnet-5` (Claude Code).
Findings 1-3 (code + tests) were implemented by a subagent against this
review brief; findings 4-8 (documentation only) were closed directly by
the coordinator in parallel (disjoint files, no overlap); the coordinator
independently re-ran full acceptance, verified every diff, and committed
all eight findings in one commit.

**Acceptance** (sequential, nothing concurrent, self-excluding `pgrep`
checked before each live/mutation step): `ruff check .` 0; `ruff format
--check .` 0; `pytest` 0, 1633 collected (1632 passed, 1 skipped);
`bot.py --selftest` 0; `checks.py lint-docs` 0; drift 119/119;
`mutation_check.py --only v194-smoke-turn3-gold-unchecked` killed;
`mutation_check.py --only v194-redacting-formatter-skips-redact` killed;
`mutation_check.py --select v15-` 4/4 killed, wall 16.011s;
`devtools/rag_eval.py` (production route, alone) exit 0, wall 342.687s
(real; down from A1/A2's ~550-560s -- this run's own turn 2 happened to
answer from context again without a search call, the same non-defect
model behaviour documented throughout this task, so both a fast run and a
slow run are within the smoke's known variance), both smoke lines
printed: `conversation-aware smoke (TOOL-06 pin): fail -- turn 2 recorded
no search_documents call sharing a token with turn 1's question` /
`conversation-aware smoke (context-proof): pass -- turn 3 queries
['перенос отпуска на следующий год'] returned the gold source
'vacation_policy.md'` -- confirming finding 3's tightened matcher (filename
AND evidence) passes correctly against the real production corpus, and
finding 1's `WARNING` fix took effect: zero INFO-level lines in this run's
entire captured output (previously ~88/run).
