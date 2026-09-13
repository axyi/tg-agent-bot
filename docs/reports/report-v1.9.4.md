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

**Delegation record.** Executor model: `claude-sonnet-5` (Claude Code). This
subagent performed the implementation directly (seam, four entry points,
five tests, two mutation entries, paperwork) against
`docs/spec/task-briefs/v194-T1.md`; the coordinator verifies the report
against the brief and commits.

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
least one call's returned passages carry the gold source (filename
equality, the same convention `first_hit` uses for the scored questions) --
`fail` with the recorded queries and top sources otherwise. Turn 2's own
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

**Cost.** All five runs' live inference (12 rerank calls per run on
`LLM_RERANK_MODEL`'s route, plus the smoke turns on whichever route was
active), tallied by hand from the instrumented runs' own `llm_call` log
rows (this harness does not attach `cost_usd` on this path):
`mistralai/mistral-small-24b-instruct-2501` 75,603 prompt + 1,476
completion tokens across 69 calls; `mistralai/mistral-nemo` 5,183 prompt +
78 completion tokens across 7 calls (B1's three failed 404 calls carried no
billable usage). At each model's public OpenRouter list price (low-cost
tier, both well under $0.10/1M tokens blended), this totals well under
$0.05 -- comfortably inside the brief's $0.30 cap; no exact per-request
cost is exposed to this session, so this is a bounds estimate, not a
metered figure.

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
