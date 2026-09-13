# tg-agent-bot v1.9.3 -- patch report

Operator's decision (`docs/spec/task-briefs/v193-T1.md`, verbatim,
2026-09-13): "1. Делай [pre-push → mutation-all]. 3. Закрывай хвосты все
сейчас, бамп версии 1.9.3!" Three tails `docs/reports/report-v1.9.2.md`
disclosed, closed on this order: **T1** -- pre-push runs `mutation-all`
instead of five subset gates, and the gate-timeout/SIGKILL-leaves-a-mutated-
tree hazard (report-v1.9.2.md disclosure b) is fixed; **T2** -- the rerank
third-attempt tail (three lines at the top of every gate-7 log since
v1.9.1 T3) is diagnosed and fixed; **T3** -- the ruff rule-family proposal
table is decided and applied. **T4** closes the patch (version bump,
paperwork, tag). Baseline: `5e62a4a` (tag `v1.9.2`, pushed, clean).

## T1 -- pre-push

Contract: `docs/spec/task-briefs/v193-T1.md` commit A (prompt 173).

`config/quality_gates.yaml`'s `pre-push` profile now runs `mutation-all`
instead of `mutation-v15, mutation-v160, mutation-v170, mutation-v180,
mutation-v190` -- one authoritative all-entries mutation run per push
instead of five partial subset runs. The five gate definitions are not
deleted: they stay useful `--select <prefix>` measurement units (this
release's own T2 and T3 tasks re-measure their touched subsets with them).
Removing them from every *hook* profile (pre-commit/pre-push/full) would
leave them unreferenced by any `profiles:` entry, which
`devtools/checks.py:540-552`'s `_validate_profiles` (the orphan check
itself at `:549-551`) rejects outright ("gate(s) named by no profile") --
discovered by running `checks.py doctor` against the first draft of this
edit. Fixed with a new, intentionally inert `mutation-subsets` profile
naming the five gates: `checks.py run --profile` only accepts
`pre-commit`/`pre-push`/`full` (`devtools/checks.py:1714`'s argparse
`choices`), so this profile is
structurally unreachable from any hook or CLI invocation -- it exists
purely to satisfy the loader's "every gate belongs to some profile"
invariant, never to run anything.

`docs/spec/spec-v1.9.0-delta-1.md`'s gate matrix table (read directly by
`tests/test_v15_standards.py:1735`,
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`) is updated
to match: the five `mutation_check.py --select vNNN-` rows' `pre-push`
cell moves `yes` -> `—`; the `mutation_check.py` (all) row's `pre-push`
cell moves `—` -> `yes`. Every row stays present (the test also asserts
every label in `_GATE_MATRIX_LABEL_TO_NAME` is a row in the table).

One test pinned pre-push membership literally rather than through the
spec-table parser:
`tests/test_mutation_check.py::test_t_v160_gate_02_mutation_v160_gate_mirrors_mutation_v15`
asserted `"mutation-v160" in config["profiles"]["pre-push"]`. Repointed
(not deleted) to `"mutation-v160" in config["profiles"]["mutation-subsets"]`
plus an explicit `not in` check against `pre-push`, with a comment naming
why.

Grepped `AGENTS.md`/`README.md` for `pre-push`, `mutation-v`, `five`,
`subsets` per the brief's own instruction: the only hits (`AGENTS.md:137,
209, 222`) are about branch-name hook enforcement and the
`checks.py run --profile` CLI -- no sentence in either file claims
pre-push runs the five subsets, so nothing there needed changing. The
claim lived only in the YAML and the spec table, both fixed above.

Proof (per the brief's own note -- the real ~11-minute `mutation-all` run
happens when the operator pushes, not inside this prompt):
`checks.py doctor` exit 0; `pytest tests/test_v15_standards.py -k
"profile_matrix or gate_05"` exit 0; full `pytest` exit 0, 1601 collected
(unchanged); `ruff check .` / `ruff format --check .` exit 0/0;
`checks.py lint-docs` exit 0; `bot.py --selftest` exit 0.

## T1 -- gate timeout safety

Contract: `docs/spec/task-briefs/v193-T1.md` commit B (prompt 174). Closes
a v1.10.0 item `docs/reports/report-v1.9.2.md` disclosed.

**The defect, precisely:** `devtools/checks.py:1098-1110` ran every gate
with `subprocess.run(argv, timeout=…)`. On `TimeoutExpired`, Python
SIGKILLs the **direct child** -- for gate 6 that is `uv`, not
`mutation_check.py` -- so the runner is orphaned, never signalled (its
SIGINT/SIGTERM handler at the time never fires), its in-memory `_Restorer`
snapshot dies with it, and the mutated source file stays on disk with no
survivor id ever printed.

**Fix 1 (primary, survives any kill):** before the first mutation,
`mutation_check.py` now checks every distinct `mutation["path"]` against
the committed blob (`git show HEAD:<path>`, the same git-objects-only
source of truth `checks.py`'s own `replay` command reads) via the new
`_dirty_mutation_paths` function. Any path whose working-tree bytes differ
from `HEAD` is named and the run refuses to start (exit 1) rather than
silently overwriting what could be an operator's own uncommitted edit.
Skipped for `--list`; placed in `main()` after the `--only`/`--select`
id/prefix checks (an invalid selector still fails instantly) and before
the v1.9.2 shrink guard (no point paying its collect-only cost on a tree
this run refuses to touch anyway). New mutation entry
`v193-mutation-dirty-tree-unchecked` (`if dirty:` -> `if False:`), killed
by two tests: `test_t_v193_dirty_mutation_paths_detects_a_byte_difference_from_head`
(a real temp git repo, direct unit test of the blob comparison) and
`test_t_v193_mutation_dirty_tree_check_blocks_before_running_anything`
(mirrors the shrink-guard tests' own shape -- fakes the check, asserts
`run_all` is never reached). The three pre-existing shrink-guard tests
that call `mc.main(...)` in-process against the real `MUTATIONS`/
`REPO_ROOT` now also fake `_dirty_mutation_paths` (bypassing it, since
they test a different guard) -- without this they would have started
failing for the wrong reason the moment this commit's own edits made
`devtools/checks.py`/`devtools/mutation_check.py` legitimately differ from
`HEAD` mid-development. The seven pre-existing `run_all(root=tmp_path)`
tests needed no change at all: the check lives in `main()`, never in
`run_all` itself, so they never reach it (the brief's own "corner" --
distinguishing the runner's in-process tests from a real dirty tree --
dissolves at this placement rather than needing to be solved).

**Fix 2 (complementary):** `devtools/checks.py:run_argv` now launches its
child with `subprocess.Popen(..., start_new_session=True)` and waits with
`proc.communicate(timeout=timeout_seconds)`; on `TimeoutExpired`, the new
`_terminate_process_group` helper sends `SIGTERM` to the whole process
group (`os.killpg`, guarded against `ProcessLookupError`), waits
`_TERMINATE_GRACE_S` (5.0s, a module constant) via `communicate`, then
`SIGKILL`s the group if still alive, then reaps. `CommandResult`'s shape
and the exact `"timed out after {timeout_seconds}s"` message are
unchanged, so every existing caller and the pre-existing
`test_v15_scan_03_fail_closed_timeout` pass unmodified.
`mutation_check.py`'s own `default_runner` now runs its `pytest` child the
same way (`Popen(..., start_new_session=True)`), tracked in the new
module-level `_CURRENT_CHILD` for the run's duration; `_install_signal_handlers`'s
handler now calls `_terminate_current_child()` (same
SIGTERM-grace-SIGKILL shape, its own `_TERMINATE_GRACE_S = 5.0`, kept
local rather than importing `checks` per REQ-V12-TREE-01/NG-05) before
restoring the tree and exiting -- closing the gap the brief named: the
handler previously restored the tree but left `pytest` running. New test
`test_v193_t1_fix2_timeout_sends_sigterm_before_sigkill`
(`tests/test_v15_standards.py`): a child that only traps SIGTERM and
writes a marker file, never exiting on its own, can only leave the marker
if it actually received SIGTERM -- a SIGKILL-only path would kill it with
no marker written. `_TERMINATE_GRACE_S` patched to 0.3s for the test so
the whole timeout+grace path stays at ~1.3s, under the brief's 2s budget.

**Measurement that closes the timeout tail:** `mutation-all` re-measured
once, alone, nothing else on the box, on this commit's tree (`07bb158`,
111 entries, both new mutation entries included): **111 mutations, 111
killed, 0 survived, 0 errored, 0 drifted** -- real=13m34.449s (814.449s).
`timeout_seconds` re-sized by the file's own rule (2x measured wall + 70s
survivor floor, rounded up to 10s): `1440s -> 1700s`
(2x814.449s + 70s = 1698.898s, rounded up). Up from 1440s at 110 entries;
not attributable to Fix 1's dirty-tree check itself (one `git show` per
distinct mutation path, once per invocation -- sub-second total, not
per-mutation, per the T1+T2 review's own finding 5), consistent instead
with this box's own documented shared/contended-machine variance
(`config/quality_gates.yaml`'s own history of re-measurements). Comment in
`config/quality_gates.yaml` updated accordingly; this measurement was
landed by amending the pre-amend commit whose tree was actually measured
into its final form, `07bb158` (an amend that only adds this paperwork
necessarily produces a new hash, since the amend changes the commit's own
content), per the brief's own "re-read every count/hash
after an amend" instruction -- the fast gates (`ruff`,
`checks.py doctor`, `checks.py lint-docs`) were re-run green against the
amended tree; an 11+-minute `mutation-all` re-run was not judged necessary
to validate a comment-and-timeout-number-only follow-up edit (the number
above is this commit's own real, freshly-measured wall, unaffected by the
follow-up edit itself).

## T2 -- rerank tail

Contract: `docs/spec/task-briefs/v193-T2.md` (prompt 175). Runs after T1
landed (`07bb158`).

### The evidence, and why the brief's own H1/H2 probe found nothing

The brief's own probe (`Searcher`/`cfg` built the same way
`devtools/rag_eval.py:596` does, `rag_rerank` off, real candidates fed to
`rag.rerank`) ran the ten `questions.json` items in gate-7 order, then
reverse order, then repeated the first item 5x with the timeout raised to
60s: **25/25 calls fast (0.38-0.96s)**, one provider throughout
(`DeepInfra`), `completion_tokens` 7-28 against the 128 budget. Neither H1
(cold start -- the tail is not the first call) nor H2 (item-bound -- the
same content is fast) was reproducible this way, because neither was the
real defect: the probe's own `Searcher` never runs the conversation-aware
smoke turn, and that turn constructs its own, differently-wired
`Searcher`s.

An in-process instrumented run of the real gate closed the gap:
`httpx.Client.post` wrapped (filtered on the `response_format` payload key
-- rerank's own fingerprint, no other call in this codebase sets it) to
log one line per rerank-shaped HTTP attempt, then `devtools.rag_eval.main()`
called directly -- the real gate, unmodified -- three sequential runs,
alone on the box.

| run | question (first 40 chars) | http_s | completion_tokens | provider | outcome |
|---|---|---|---|---|---|
| 1-3 | (all 12 deterministic items: 10 answerable + 2 null, x3 runs = 36 calls) | 0.37-1.48 | 7-28 | DeepInfra | ok |
| 1 | `отпуск количество дней в год` (smoke turn's own agent-generated query) | 15.068 / 15.083 / 15.108 | None / None / None | None / None / None | timeout x3, then a DNS error on a 4th, unrelated call |
| 2 | `отпуск количество дней в год` | 15.032 / 15.147 / 15.082 | None / None / None | None / None / None | timeout x3, then 0.698 ok (Google) on an independent follow-up call |
| 2 | `количество недель отпуска в год` (turn 2's own query) | 0.485 | 11 | Google | ok |
| 3 | `отпуск количество дней в год` | 15.042 / 15.108 / 15.134 | None / None / None | None / None / None | timeout x3, then 0.714 ok (Google) |
| 3 | `количество недель отпуска в год` | 0.572 | 11 | Google | ok |

Every timeout sits at the gate's own 15.0s ceiling, `provider=None` (no
response body ever arrived to parse -- not a slow response, no response at
all). Runs 2-3 also logged `provider lmstudio failed 3 times (LLMError);
serving from openrouter` in the same window -- the *agent's own chat
completion* failing over from LM Studio, a separate client entirely. That,
plus the exact 15.0s ceiling, pointed away from "OpenRouter routes this
content badly" and toward "this call is reaching the wrong client."

Targeted follow-up: the exact agent-generated query text
(`'отпуск количество дней в год'`), reranked in isolation with the timeout
raised to 60s (the same seam the brief's probe uses), against the same
retrieval funnel: **5/5 succeeded in 0.76-1.25s, all DeepInfra**. The
content is not slow. The chronological position (last call of the run,
appearing first in captured output only because `log.warning`'s stderr is
unbuffered while `print_fn`'s stdout is not -- confirmed by the timestamps
above, which put the timeouts at the *end* of each run) is not cold start
either.

### The defect

`devtools/rag_eval.py`'s `run()` builds its scored `hybrid_rerank_searcher`
with `llm=rerank_llm or llm` (`:438`) -- routes to the fast, configured
reranker (`LLM_RERANK_MODEL`) exactly as `bot.py:950-958`'s live searcher
does. `conversation_smoke()` (`:310-377`) took only a plain `llm` parameter
and built *both* of its own `rag.Searcher`s with `llm=llm` -- the chat/
agent completion client, LM Studio primary via the failover wrapper
(`llm/failover.py`). The smoke turn's rerank calls never reached the
routed reranker at all: they reached LM Studio, whose measured median
per-rerank-call latency (v1.9.1 T1, `qwen/qwen3.8-27b`) is 196.9s --
timing out at the gate's own 15.0s ceiling on every attempt, every run.

### The fix

`conversation_smoke()` gains a `rerank_llm=None` parameter; both
`rag.Searcher` constructions now use `llm=rerank_llm or llm`, the same
expression `run()`'s own scored searcher and `bot.py`'s live searcher
already use. The call site (`:531-539`) passes `rerank_llm=rerank_llm`
through. `_RERANK_TIMEOUT_S`/`_RERANK_MAX_ATTEMPTS` are unchanged -- this
was never a rerank-model or timeout-sizing defect.

New mutation entry `v193-smoke-reranks-on-chat-client` (reverts
`searcher1`'s routing back to the chat client -- the file's own `find`
string is unique to that one Searcher's block), killed by
`test_t_v193_t2_conversation_smoke_reranks_via_rerank_llm_not_chat_llm`
(`tests/test_v190_eval.py`): two distinct `_DynamicRerankLLM` doubles as
`llm` (chat, scripted with the smoke's own two-turn agent script) and
`rerank_llm` (bare); asserts `rerank_llm._rerank_calls == 2` (one per
turn -- reverting either Searcher alone drops this to 1, still failing)
and that the chat client never received a rerank-shaped call
(`tool_definitions is None`).

### Three consecutive clean gate-7 runs (proof)

Run on the fixed, committed tree (`aa8d576`), sequential, alone on the box,
never concurrent with gate 6:

| run | exit | wall | `rerank attempt … failed` lines | `provider lmstudio failed` lines | hybrid recall@5 | hybrid+rerank recall@5 |
|---|---|---|---|---|---|---|
| 1 | 0 | 268.800s | 0 | 0 | 1.000 | 1.000 (mrr 0.900) |
| 2 | 0 | 233.347s | 0 | 0 | 1.000 | 1.000 (mrr 0.850) |
| 3 | 0 | 250.700s | 0 | 0 | 1.000 | 1.000 (mrr 0.850) |

All three: `gate-7: PASS`. The conversation-aware smoke's own advisory
token-sharing check (TOOL-06, unrelated to this fix) still shows its
pre-existing intermittent "fail" disposition in all three runs here (`turn
2 recorded no search_documents call sharing a token with turn 1's
question`) -- advisory, never gate-blocking, and out of this task's scope
(it is about whether the follow-up turn's own query shares a token with
turn 1's, not about which client reranks). The mutation-fix's own scope --
zero retry lines, zero failover lines, the smoke turn's rerank calls
routed to the fast reranker -- is fully confirmed.

### Cost

25 calls (brief's own probe) + 5 (targeted 60s repeat) $\approx$ \$0.012,
plus three live gate-7 runs' own inference (the reranker plus the
advisory conversation-aware smoke, at reference OpenRouter prices, no real
spend tracked or exposed to this session) -- under the \$0.20 budget.

### Acceptance (T1+T2 review finding 11, added after `aa8d576`)

`ruff check .`/`ruff format --check .` 0/0; `pytest` 0, 1605 collected (1
new test); `bot.py --selftest` 0; `checks.py doctor` 0; `checks.py
lint-docs` 0; drift script 112/112; `mutation_check.py --only
v193-smoke-reranks-on-chat-client` killed. `AGENTS.md`'s gate-3/gate-6
count-bearing lines and `tests/test_v190_agents.py`'s own pinning test
move at T4 (version bump), the same precedent v1.9.2 T1/T2 set and T3
closed -- not this task's or T2's scope.

## T1+T2 review

Contract: `docs/spec/task-briefs/v193-T12-review.md` (prompt 176). A
clean-context review of `bff8dc4`+`07bb158`+`aa8d576` (opus): no 🔴, three
🟠, eight 🟡. All eleven closed in this one commit, none of the three
reviewed commits rewritten.

### 🟠 findings

1. **SIGTERM test proved only direct-child signalling.** The original
   marker-file test's child received SIGTERM either way `_terminate_process_group`
   signals it (`os.killpg` or `os.kill(pid)`), since the marker-writing
   process *was* the direct child -- swapping to pid-only signalling (the
   pre-fix defect) still passed it. Rewritten with a **grandchild**: the
   direct child spawns a subprocess (no `start_new_session`, so it joins
   the same process group `start_new_session=True` gave the direct child)
   that traps SIGTERM and writes the marker; the direct child polls a
   "ready" flag (bounded, deterministic) before it too sleeps past the
   timeout. New mutation `v193-gate-timeout-kills-direct-child-only`
   (`devtools/checks.py`, the SIGTERM `os.killpg` call only ->
   `os.kill(proc.pid, ...)`), killed by the rewritten test.
2. **`_CURRENT_CHILD`/`_terminate_current_child`/the handler's call to it
   had no coverage.** Two new unit tests
   (`tests/test_mutation_check.py`): `_terminate_current_child` sends
   `SIGTERM` to the tracked child's pid via `os.killpg` (a fake
   `Popen`-shaped double, `os.killpg` monkeypatched -- no real process) and
   is a no-op when `_CURRENT_CHILD` is `None` or already exited; the
   installed signal handler calls `_terminate_current_child()` **before**
   `restorer.restore_all()` and `sys.exit(1)` (asserted by call order, both
   monkeypatched). New mutation `v193-signal-handler-leaves-child-running`
   (drops the handler's call to `_terminate_current_child()`), killed by
   the ordering test.
3. **Undisclosed pre-push consequence: a failed `exit_status` gate
   swallowed its child's stderr.** `git push` with WIP edits on any
   mutation path now fails at pre-push as `gate mutation-all exited 1`
   with no further detail, since `checks.py`'s `exit_status` branch only
   ever reported the exit code. Fixed: the last five non-empty stderr
   lines of the failed child are appended to the gate message (plain, not
   `config.redact`-passed -- that would pull `python-dotenv` into this
   standard-library-only module for a secrets registry it never
   populates, since it never calls `config.load_config()`/reads `.env`),
   with a new test (`tests/test_v15_standards.py`) proving the tail is
   bounded to five lines, stdout is never included, and the exit-code
   message is preserved. `AGENTS.md`'s gate-6 paragraph and `README.md`'s
   mutation-gate paragraph each gain one sentence: pre-push now refuses a
   tree with uncommitted edits to a mutation path, and what to do
   (`git restore --staged --worktree <path>` for a leftover mutation).

### 🟡 findings

4. The refusal message's own guidance was fixed to `git diff HEAD --
   <path>` / `git restore --staged --worktree <path>` (`git diff <path>`
   shows nothing for a staged edit, and `git checkout -- <path>` then
   restores from the index -- a loop for exactly that case).
5. `config/quality_gates.yaml`'s and this report's own 680->814s
   explanation wrongly attributed part of the jump to "two `git show`
   calls per mutation path"; the dirty-tree check is one `git show` per
   *distinct* path, once per invocation -- sub-second total, not
   per-mutation. Both comments now cite only the box's own documented
   shared/contended-machine variance.
6. **Slow-phase measurement (rag-eval gate).** See below.
7. **Conversation-smoke investigation.** See below.
8. Stale citations repointed to the current tree: `devtools/checks.py:538-550`
   -> `:540-552` (orphan check `:549-551`), `:1657` -> `:1714` (the
   `choices` argparse); the amended-away hashes `ceb4a11`/`0fde4c3` ->
   `07bb158`/`aa8d576` everywhere they appeared in `config/`/`docs/`.
9. `docs/prompts/174-...md`'s own title said "restores a leftover mutated
   tree"; the implementation refuses and reports, never silently
   restores. Title corrected, with a note that the task brief's own
   commit-B title (which does say "restores") stays unchanged as history
   in `docs/spec/task-briefs/v193-T1.md`.
10. `tests/test_mutation_check.py`'s dirty-tree-check killer test now
    fakes `_shrink_counts` too (like its shrink-guard sibling tests) --
    without this, a *mutated* run (the check neutered) fell through to
    the real, subprocess-shelling `_shrink_counts` (two real
    `pytest --collect-only` runs) before reaching the also-faked
    `run_all` -- still killed correctly, but not offline while doing it.
11. Report gains a T2 acceptance line (see T2's own "Acceptance"
    subsection above); `AGENTS.md`/`tests/test_v190_agents.py`'s
    count-bearing lines move at T4 by precedent, not here. The mutation id
    `v193-smoke-reranks-on-chat-client` is kept as landed (renaming a
    landed id is churn).

### Finding 6 -- slow-phase measurement

The three T1.../T2 gate-7 walls (268.8/233.3/250.7s) plus the reviewer's
own independent re-run (232.4s) all run longer than v1.9.2's 186.998s. One
fresh gate-7 run, instrumented from outside (three seams wrapped with
wall-clock timestamps -- `agent.run_agent_outcome`, `rag.Searcher.search`,
`devtools.rag_eval.index_corpus`; `rag.py`/`devtools/rag_eval.py`
themselves untouched), saved in full at
`/home/akh/.claude/jobs/45feeee3/tmp/v193/gate7_phased_run.log`:

| phase | span | duration |
|---|---|---|
| `index_corpus` (embedding ingest) | +0.203s -> +2.382s | 2.18s |
| 12 deterministic `Searcher.search` calls (10 answerable + 2 null) | +2.487s -> +14.694s | 12.21s |
| smoke turn 1, first chat completion (before any tool call) | +14.695s -> +126.648s | 111.95s |
| smoke turn 1's own rerank call (`Searcher.search #13`, now routed correctly) | +126.648s -> +128.726s | 2.08s |
| smoke turn 1, second chat completion (after the tool result, final reply) | +128.726s -> +225.586s | 96.86s |
| smoke turn 2, one chat completion, no tool call | +225.586s -> +267.815s | 42.23s |
| **total wall** | | **267.821s** |

The slow phase is the conversation-aware smoke turn's own **chat**
completions (three of them, 42-112s each, all served by the configured
chat/LM-Studio-primary client) -- **not** the rerank call inside it (2.08s,
using the now-fixed `rerank_llm` routing) and not corpus/embedding ingest
or the ten deterministic items (14.7s combined). T1/T2 touched only the
rerank client's *routing*, never the chat client or the agent's own
completion path; the wall-length increase over v1.9.2's 186.998s is this
box's current LM Studio latency for chat completions, a pre-existing,
environment-side variable outside either fix's scope (consistent with
this lab's own recorded LM Studio floating-IP/reachability notes).
`config/quality_gates.yaml`'s `rag-eval.timeout_seconds` (580s) is kept
unchanged -- 2x the slowest of the four walls (268.8s) is 537.6s, still
under 580s with margin.

### Finding 7 -- conversation-smoke investigation

The same instrumented run captured turn 2's full outcome (see the log
above): `tool_calls=[]`, `failed=False`, `kind=None`,
`reply='\n\n28 календарных дней — это 4 недели.\n\nSource:
vacation_policy.md'`. Turn 1 had already answered "28 календарных дней
оплачиваемого отпуска в год" after one `search_documents` call; turn 2's
question is the literal `«а в неделях?»` ("and in weeks?") -- a unit
conversion of a fact already in turn 1's own context, answerable without
a fresh search.

Not a defect: T1/T2's fix changed only which client `Searcher`/`rerank()`
route rerank calls through; it touches no code on the agent's own
tool-decision path (`agent.py`'s completion loop, `conv_id`, message
history assembly, or the `search_documents` tool definition are all
unchanged by either fix), so there is no mechanism by which the fix could
have made the chat model less likely to call the tool. The most likely
explanation given the evidence: before the fix, turn 1's rerank calls
often degraded to a fallback RRF order or succeeded only on a delayed
retry (report-v1.9.2.md's own recurring open tail), which could leave
turn 1's answer less clean; now that rerank reliably succeeds fast, turn
1's answer is a clean, directly quotable fact, and the model reasonably
judges turn 2's simple arithmetic follow-up as answerable from context
without repeating the search. This is model behaviour, not a code defect,
and the check is advisory by design (TOOL-06's own docstring: it verifies
context-carryover *capability*, not that a tool call happens every time)
-- gate 7 exits 0 regardless, in this run and in every run this task
measured. No fix applied; recorded as an observation for the operator.

### Acceptance (this commit, on the amended-away-hash-free tree)

`ruff check .` 0; `ruff format --check .` 0; `pytest` 0, 1609 collected (4
new tests); `checks.py lint-docs` 0; `checks.py doctor` 0; `checks.py run
--profile pre-commit` 0; drift script 114/114 (112 -> 114, two new
entries); `mutation_check.py --only
v193-gate-timeout-kills-direct-child-only` killed; `mutation_check.py
--only v193-signal-handler-leaves-child-running` killed; the rewritten
grandchild SIGTERM test run 5x standalone, 5/5 green; the single
instrumented gate-7 run above, exit 0, wall 267.821s.

## T3 -- ruff families

Contract: `docs/spec/task-briefs/v193-T3.md`. Runs after T1+T2 landed
(`aa8d576`, the review commit that followed both). Closes
`docs/reports/report-v1.9.2.md`'s proposal table of ruff families the
project does not select: **adopt** what is mechanical and
behaviour-preserving, **never** what is noise or policy, decided per the
operator's ruling ("закрывай хвосты все сейчас").

### The decision table (verbatim from the brief)

| family | hits | verdict |
|---|---|---|
| `S101` | 3689 | never -- `assert` is pytest's contract; a per-file-ignore for `tests/` would still leave `S105/S106` (25 false positives on names like `LLM_RERANK_MODEL`) and `S603/S607` (27 intentional `subprocess` sites) |
| `PLR2004` | 474 | never -- magic-value noise |
| `TRY003` | 277 | never -- vanilla-args style, no defect class |
| `ARG001/002/005` | 362 | never -- protocol/callback signatures (skylos already audits unused params with per-site reasons) |
| `PLR09xx` complexity, `PLR0913/0917` | ~120 | never -- refactor policy, not a defect |
| `T20` | 61 | never -- `devtools/` CLIs print by design |
| `N818` | 6 | never -- renaming public exception classes is an API change |
| `BLE001` | 20 | never -- the bot's "never crash the loop" policy; each site logs |
| `PLC0415` | 28 | never -- lazy imports by design (start-up cost, optional deps) |
| `RUF001/002/003` | 72 | never -- Cyrillic in user-facing strings |
| `PTH*` | 24 | not now -- `os.chmod`/`os.stat` in `storage.py` are deliberate mode-bit code; pathlib rewrite is a v1.10 style task |
| `PLW0603` | 3 | not now -- module-level state pattern (`_shutdown`, `_started_at`, `_dropped_spans`) |
| `RUF043` | 1 | not now -- one `pytest.raises(match=)` pattern; fix when that test is next touched |

All thirteen rows landed as a comment block in `pyproject.toml`'s
`[tool.ruff.lint]`, closing the table -- no further carry-forward.

**Note on the brief's own inventory:** the brief's hit counts were measured
on `5e62a4a` (v1.9.2); this task runs on the post-T1/T2/review tree
(`aa8d576`+review), which already touched `devtools/checks.py`,
`devtools/mutation_check.py` and `devtools/rag_eval.py`. Re-measured on the
current tree before each commit (below); the never/not-now table's own
counts are historical (as the brief states) and unaffected by the verdict.

**Disclosure:** `acd373a` (commit A) also carries a renumbering edit to
`docs/spec/task-briefs/v193-T3.md` itself (prompt numbers 176/177 ->
177/178, the entry count 112 -> 114) -- the coordinator staged that edit
before this task started (per the run's own instructions, "the only
change in the tree is a staged renumbering edit ... that belongs in your
first commit"); the executor committed it as the first change in commit
A, unmodified, without a separate disclosure sentence at the time. Named
here per T3 review finding 6.

### Commit A -- prompt 177, `style: ruff autofix tier`

Rules: `UP037 UP017 UP031 C420 C408 SIM300 SIM102 RET501 RET503 RET504
FURB105 FURB110 FURB167 FURB187 FURB192 PIE810 RUF015 RUF059 PLW0108`.
Re-measured on this tree: 83 hits (vs. the brief's 5e62a4a-era count for the
same rules, materially unchanged -- these rules are untouched by T1/T2's
subprocess/rerank-routing edits).

- **Safe `--fix`** (8 rules, 31 hits): `UP037` (2), `UP017` (1), `FURB110`
  (1), `FURB105` (1), `RET501` (1), `FURB167` (17), `SIM300` (5), `C420`
  (3). All mechanical (`re.S`->`re.DOTALL`, `re.I`->`re.IGNORECASE`,
  `{k: None for k in x}`->`dict.fromkeys(x)`, quoted-annotation unquoting --
  verified every touched file already carries `from __future__ import
  annotations`, `return None`->`return`, yoda-condition flips).
- **`--unsafe-fixes`, each diff hunk read** (10 rules, 15 of 18 hits
  auto-fixed): `PIE810` (1, two `startswith` calls merged into one
  tuple-arg call), `RET504` (1, drops an intermediate `previous =` binding
  in `mutation_check.py:_install_signal_handlers` -- confirmed `previous`
  had no other use), `PLW0108` (3, `lambda x: f(x)`->`f` -- confirmed each
  callable's arity/signature matches the lambda's forwarding exactly:
  `sleeps.append`, `str`), `FURB192` (4, `sorted(x)[0]`->`min(x)` in
  `llm/base.py` x2, `config.py`, `devtools/bench.py` -- **all four read**:
  none carries a custom `key=`, so there is no tie-breaking difference
  between `sorted()[0]` and `min()`), `RUF015` (2, `[...][0]`->`next(...)`
  in two tests -- both post-assertion contexts already guarantee a
  non-empty match), `FURB187` (1, `list(reversed(x))`->`x.reverse()` in a
  test where `x` is a freshly-built list with no other alias), `C408` (2,
  `dict(...)`->`{...}` literal in two tests, same keyword args), `RET503`
  (1, `dashboard_server.py`'s `_route` gains an explicit trailing `return
  None`, matching its own `-> None` signature and every other branch's
  implicit `None`).
  - **`RUF059`** (34, all auto-fixed as rename-to-`_name`, never a dropped
    unpacking -- confirmed by reading the full diff: every hit keeps its
    tuple/unpacking shape, only the unused binding gains an `_` prefix).
    One orphan surfaced by the earlier `UP017` fix: `storage.py`'s
    `from datetime import datetime, timezone` gained `UTC` and left
    `timezone` unused (`F401`) -- removed (not part of any of the 19
    rules; a cleanup of an import this task's own edit made dead).
  - **3 hits ruff would not auto-fix**, hand-rewritten and checked for
    identical fall-through semantics: `UP031` (1,
    `tests/test_v160_dashboard.py:786`, `"localhost:%d" % port` ->
    `f"localhost:{port}"`); `SIM102` (2) -- `tests/test_v190_isolation.py`
    (a nested `if "user_id" in body and "documents" in body: continue`
    merged into its outer `if` with `and`; the outer `if`'s only body
    statement was the inner `if`, so merging changes nothing when the
    combined condition is false -- falls through to `offenders.append`
    either way) and `tests/test_v190_tool.py` (same shape, an
    `ast.Import`-guarded `any(...)` check merged with `and`).
- Then all 19 rules added to `pyproject.toml`'s `[tool.ruff.lint].select`,
  rule-level (never family-level, so no never-listed sibling rides along),
  alongside the never/not-now comment block above.

Acceptance: `ruff check .` 0; `ruff format --check .` 0; `pytest` 0, 1609
collected (1608 passed, 1 skipped, unchanged); `bot.py --selftest` 0;
`checks.py lint-docs` 0; drift script 114/114, 0 drifted.
`devtools/bench_scenarios.py` untouched (none of these 19 rules' hits land
there). README/AGENTS.md grepped for `E, F, I` / `select`: the only hits
(`AGENTS.md:183-184`) are about the mutation gate's own `--select <prefix>`
CLI flag, not the ruff rule set -- nothing there names the actual `select`
list, so nothing needed changing (the same "grepped, nothing to change"
outcome T1 recorded for its own grep).

### Commit B -- prompt 178, `fix: ruff bug-class tier`

Rules: `PLW1510 TRY400 ISC004 RUF005 RUF007 PERF401 SIM105 SIM117 TRY004
PLW2901`, each hit read by hand as the brief requires.

**Commit message deviation:** the brief's own commit-B title (`fix: ruff
bug-class tier (PLW1510, TRY400, ISC004, RUF005/007, PERF401, SIM105/117,
TRY004, PLW2901)`, 100 characters) exceeds `AGENTS.md`'s hard 72-character
header limit, enforced by the `commit-msg` hook -- the first commit attempt
was rejected by it. Landed as `fix: ruff bug-class tier (subprocess,
exceptions, concat)` (57 characters) instead, with the full rule list
moved into the body's first line. Commit A's brief-specified title (63
characters) fit and was used verbatim.

**`RUF005`/`RUF007`** (13/10 hits, re-measured on this tree): all 23
mechanical via `ruff --unsafe-fixes` (`list + [x]` -> `[*list, x]`,
`zip(x, x[1:], strict=False)` -> `itertools.pairwise(x)`); every diff hunk
read, none changes iteration order or count.

**`PERF401`** (19 hits, re-measured -- up from the brief's 5e62a4a-era
count of the T3 select list, since none of these 19 sites existed there
either; the rule has no autofix at all, all 19 hand-rewritten): 8 in
`devtools/bench.py` (report-table row builders: `rows = []` + `for key in
(...): rows.append(...)` -> a list comprehension for the first loop
populating an empty list, `.extend(genexpr)` for subsequent loops over the
same accumulator), 5 in `devtools/checks.py` (the four scanner-JSON
adapters: `gitleaks_json` unchanged shape kept as a comprehension it
already had is untouched; `trivy_json`'s two nested loops ->
`findings.extend(genexpr)` each; `semgrep_json`/`skylos_json`'s
single/nested loops -> a direct list comprehension), 2 in
`dashboard_server.py` (`body.append(...)` in a `for hist in ...:` loop ->
`body.extend(genexpr)`, twice), 2 in `tests/test_v170_bench.py` and 1 in
`tests/test_v180_dashboard.py` (conditional-append loops -> `.extend(genexpr
... if cond)`), 1 in `documents.py` (`rows.append((page_number, chunk))` in
a `for chunk in chunk_text(...):` loop -> `rows.extend(genexpr)`). One
orphan surfaced by the `devtools/checks.py` rewrites: `findings = [...]`
immediately followed by `return findings` is itself `RET504` (now
selected, from commit A) -- collapsed to a direct `return [...]` in both
`semgrep_json` and `skylos_json`.

**`SIM105`** (13 hits, re-measured; brief's 5e62a4a-era count was 9 --
T1/T2's new SIGTERM/SIGKILL and rerank-routing code added 4 more): 11 via
`ruff --unsafe-fixes` (`try: X except E: pass` -> `with
contextlib.suppress(E): X`, one exception type per site, read in full --
`_killpg`'s three-exception tuple, `checks.py`/`mutation_check.py`'s
process-group SIGTERM/SIGKILL pair, `tools.py`'s five fetch/probe
sites, `storage.py`'s chmod site); 2 in `rag.py` not auto-fixed (a
trailing `# a failing logger must not escape` comment on the `except
Exception:` line) -- hand-rewritten identically, comment preserved on the
new `with contextlib.suppress(Exception):` line.

**`SIM117`** (9 hits, all in `tests/test_v160_observability.py`): 3 via
`ruff --unsafe-fixes`, 6 hand-merged (a two-`as`-binding pattern and a
`caplog.at_level` + `start_span` pattern ruff's own fixer declined to
merge automatically). Every merge read for enter/exit order: a
comma-joined `with A as x, B as y:` statement is Python's own defined
equivalent of `with A as x: with B as y:` -- same enter order (A then B),
same exit order (B then A) -- which is exactly ruff's own precondition for
firing this rule (the outer `with`'s body must be solely the inner
`with`), so no site could have changed which exception is swallowed or
which context exits first; confirmed by re-running the full file green
after each merge.

**`TRY004`** (5 hits: 0 adopted, 4 kept, 1 excluded -- revised by T3 review
finding 7, see below). `devtools/dashboard.py:98,106,108`
(`load_document`'s three type-check raises) kept as `ValueError` with `#
noqa: TRY004` each: the function's own docstring ("the benchmark file, or
`ValueError` with a one-line reason", REQ-V160-DSH-05) and `main()`'s
`except ValueError as exc:` (prints a clean CLI error, `EXIT_ERROR`) both
depend on this exact type. `devtools/bench_scenarios.py:137` excluded (see
Constraints).

**Erratum (T3 review finding 7):** this task originally adopted `tracing.py:
102` (`_validate_attribute_value`'s scalar-type check) to `TypeError`,
reasoning that nothing caught `ValueError` there specifically. The review
found the same function's sibling branch (`:99`, the list-of-str check)
still raises `ValueError`, so the fix split one validator's two branches
across two exception types for no documented reason -- `spec-v1.6.0.md:487`
says only "anything else raises" (no type specified), and
`T-V160-TRC-09`'s existing test covers `set_attribute`'s own unrelated
"unknown key" `ValueError` at `:221`, not this one. Reverted to
`ValueError` with `# noqa: TRY004` and an inline reason (both branches must
raise the same type) -- the revert's own reformatting moved the `raise`
itself from `:102` to `:106` (the single-line form no longer fits under
100 chars once `ValueError` and the trailing `noqa` comment are both
back); `TRY004`'s own tally above corrected from "4 fixed" to "0 adopted,
4 kept".

**`PLW2901`** (6 hits, all mechanical loop-variable renames, semantics
unchanged): `devtools/bench.py` (`convert()`'s `row`/`selected`'s `row` ->
`raw_row`, rebound as `row = dict(raw_row)`), `devtools/checks.py`
(`parse_pre_push_stdin`'s `line` -> `raw_line`; `_partition_findings`'s
`finding` -> `raw_finding`), `llm/base.py` (`_parse_tool_calls`'s `entry`
-> `raw_entry`), `tests/test_v170_bench.py` (`chunk` -> `raw_chunk`).

**`PLW1510`** (16 hits, re-measured -- one less than the brief's 17
because T1's own `Popen`-based `run_argv` rewrite already removed one
`subprocess.run` site the brief's inventory counted): every site read for
whether the caller checks `.returncode` afterward. All 16 got explicit
`check=False`: `bot.py:659,686` (`_reap_orphaned_containers`, both
docker-ps/docker-rm calls, `.returncode` read immediately after);
`tools.py:562,579,603` (`docker_probe`, `docker_image_present`,
`image_has_timeout`, all read `.returncode`); `tools.py:876` (`_docker_kill`
-- no `.returncode` read at all, but its own docstring says "best effort:
the client is already dead, the container may not be", matching the same
non-fatal-by-design class); `devtools/mutation_check.py:1563`
(`_collect_count`'s own docstring, def `:1547`: "Returns `(count,
returncode)` -- the caller must check the returncode itself"); `tests/test_bench.py:1889`,
`tests/test_v13_carryover.py:214`, and all 7 `tests/test_v15_standards.py`
sites (gitleaks/semgrep/mutation-CLI subprocess assertions, every one
reads `.returncode` on the next line). **Zero `check=True` sites** -- no
non-zero exit anywhere in this list was ever treated as a bug; the
brief's other branch never fired.

**`TRY400`** (16 hits, unchanged from the brief's count): **10 adopted**
`log.exception` (`bot.py:1447` document-handler `sqlite3.Error` -- an
unexpected DB failure, unlike its sibling classified branches which already
`log.warning`; `bot.py:2008` `(TelegramError, KeyError, TypeError)` at
startup -- the latter two are real bugs, not classified failures, and this
runs once at boot, not in a hot loop; `bot.py:2081`
`dashboard_server.build_server`'s broad `except Exception` startup guard;
`dashboard_server.py:518,535` the request handler's DB-error and
unhandled-exception guards; `devtools/bench.py:933,1097,1108,1155,1161` --
one scenario-prep failure plus two DB-open/DB-read pairs (five sites, not
three), both devtools harness paths where a full traceback aids debugging
and there is no hot-loop noise concern). **6 kept** `log.error` with `#
noqa: TRY400` plus an inline reason comment: `bot.py:1498,1536` (both
`TelegramError` -- already-classified, retryable/fatal known from the
exception itself); `bot.py:1996,2020` (both `ConfigError` -- the second
already carried a `REQ-V12-ERR-01` comment this task cites verbatim: "a
configuration refusal must look like one, not an unhandled traceback",
`tests/test_v12_patch.py:759` asserts no `"Traceback"` text reaches the
log for this exact seam); `tools.py:1245,1482` (both audit-log
best-effort sites, "an audit failure is never fatal", a potentially hot
path on every exec call). No caplog test pinned a level/message this task
needed to repoint.

**Erratum (T3 review finding 1):** this paragraph, `docs/llm-usage.md` row
88, `docs/prompts/178-...md` and the `6fcf1fc` commit body all originally
stated "7 adopted / 9 kept" -- an arithmetic slip against this same
paragraph's own per-site list, which always totalled 10/6 (3 `bot.py` + 2
`dashboard_server.py` + 5 `devtools/bench.py` adopted; 4 `bot.py` + 2
`tools.py` kept). The tree was never wrong -- only the tally numeral, here
and in the other three places named above, all corrected by this review's
own commit (prompt 179) rather than by rewriting `6fcf1fc`.

**Finding 8 (redaction):** `log.exception`'s own traceback and chained
`__context__`/`__cause__` rendering are not passed through `redact()` --
no logging-layer filter exists (`bot.py`'s logging setup is a plain
`logging.basicConfig` call). Reviewed every one of the 10 adopted sites:
no registered secret can reach those exception objects today
(`TelegramError` is always built from already-redacted strings; the two
`from None` re-raises breaking the httpx-URL exception chain live at
`bot.py:171` (`except httpx.TransportError`) and `bot.py:190` (the
non-JSON response branch); every remaining site is a bare
`sqlite3.Error`/`OSError`/config-shape failure with no secret-bearing
payload). So this is not a live leak, but the `redact(str(exc))` argument
still passed into several of these `log.exception(...)` calls now reads
as protective when it is not (the traceback itself already carries the
unredacted exception text) -- listed here as a v1.10.0 hardening
candidate: a redacting `logging.Filter` installed once at the root
logger, rather than relying on every call site to redact its own
formatted message.

**`ISC004`** (32 hits total, 11 in `devtools/bench_scenarios.py` excluded
-- see Constraints; 21 reviewed). All 21 read as `intentional`: `bot.py`
(5, `_render_stats`/`_handle_model`'s wrapped f-string message lines),
`dashboard_render.py` (6, one SVG `<desc>` line, five HTML `<tr>` row
builders), `devtools/bench.py` (4, the console-summary line builders),
`storage.py` (1, one SQL statement in `_MIGRATION_5_TO_6`),
`tests/test_v14_patch.py` (5, recorded literal benchmark canary answers).
Zero bugs: every site's implicit concatenation forms exactly one logical
string as a single collection element, correctly comma-terminated before
the next element (verified by reading `ruff --unsafe-fixes --diff` in
full against this determination -- the tool's own parenthesisation matches
exactly, changing no string content). All 21 parenthesised explicit via
`ruff --unsafe-fixes --fix`, then `ruff format` reflowed the new
parenthesised multi-line strings to its canonical shape.

**One line manually rewrapped**, not itself an ISC004 hit (nested inside a
dict value inside a list, one level too deep for the rule to fire) but
made too long (>100 chars, `E501`) by commit A's own `RUF005` collapse:
`agent.py`'s JSON-repair message (`repair = [*messages, {...}]`) restored
to a multi-line list/dict literal, the implicit string concatenation kept
intact.

Then all 10 rules added to `pyproject.toml`'s `[tool.ruff.lint].select`,
rule-level.

### The `devtools/bench_scenarios.py` exclusion (beyond-brief generalisation)

The brief's own Stop condition names only `PERF401`/`SIM117` rewrites
touching this byte-hash-frozen file (`REQ-V13-BEN-12`,
`scenarios_sha256()` pinned inside every committed benchmark artefact).
Neither of those two rules has any hit inside it. `TRY004` (1 hit,
`:137`) and `ISC004` (11 hits, recorded canary-turn strings across five
scenario definitions) both do. Since the underlying reason -- any byte
change here invalidates every already-committed `docs/assets/bench/
*.json`'s pinned hash -- applies identically regardless of which rule
triggers the rewrite, the same treatment (exclude, disclose) is applied to
these two instead: a `[tool.ruff.lint.per-file-ignores]` table added for
`"devtools/bench_scenarios.py" = ["TRY004", "ISC004"]`, the file's bytes
untouched by this commit. Flagged here explicitly since it goes beyond the
brief's literal wording, for the operator to confirm or override.

### Mutation drift and re-derivation

Drift script (114 entries) run after this commit's fixes landed, before
committing: **113/114 matched, 1 drifted** --
`v13-fetch-save-reuses-inode` (`tools.py`), whose `find` string was the
pre-`SIM105`-fix `try:/except FileNotFoundError:/pass` block this commit's
own rewrite replaced with `with contextlib.suppress(FileNotFoundError):`.
Re-derived with identical mutation semantics (same two effects: the
`unlink` attempt dropped entirely, `os.O_EXCL` -> `os.O_TRUNC` in the
following `os.open` call) against the new `with`-statement shape; `--only
v13-fetch-save-reuses-inode` run on the committed tree (the T1 dirty-tree
check requires it -- run after this commit, not before, matching the
brief's own "after each commit" framing of its acceptance list): killed.
Drift script re-run after the re-derivation: **114/114 matched, 0
drifted**.

### Acceptance (this commit)

`ruff check .` 0; `ruff format --check .` 0; `pytest` 0, 1609 collected
(1608 passed, 1 skipped, unchanged -- one transient failure between
landing the lint fixes and re-deriving the drifted mutation entry, not
present in the final committed tree); `bot.py --selftest` 0; `checks.py
lint-docs` 0; drift script 114/114 (0 drifted, after re-derivation);
`mutation_check.py --only v13-fetch-save-reuses-inode` killed, run on the
committed tree per T1's own dirty-tree requirement.

## Gates (T4, final tree, verbatim from AGENTS.md, in order)

Nothing else on the box during gate 6; gate 6 and gate 7 not run
concurrently.

| # | Gate | Exit | Wall |
| --- | --- | --- | --- |
| 1 | `uv sync --locked` | 0 | 0.021s |
| 2 | `ruff check .` | 0 | 0.045s |
| 3 | `pytest` | 0 | 21.854s (1609 passed, 1 skipped, 1610 collected) |
| 4 | `bot.py --selftest` | 0 | 0.566s |
| 5 | `bot.py --selftest-live` | 0 | 1.751s (all seven live checks OK, including `lmstudio`) |
| 6 | `mutation_check.py` (no `--select`) | 0 | 727.799s (114/114 killed, 0 survived, 0 errored, 0 drifted) |
| 7 | `rag_eval.py` | 0 | 233.742s (PASS: hybrid recall@5=1.000, hybrid+rerank recall@5=1.000; advisory conversation-aware smoke read "fail" -- turn 2 issued no `search_documents` call sharing a token with turn 1, the same model-behaviour non-defect the T1+T2 review's finding 7 already documented, never blocking) |

**Gate-6 wall, chronological:** 680.49s @ 110 entries (v1.9.2 T3) ->
814.449s @ 111 entries (v1.9.3 T1 commit B, its own re-measurement) ->
727.799s @ 114 entries (this run, T4, the authoritative final-tree run).
Down from T1's own number despite three more entries, consistent with
this box's own documented shared/contended-machine variance (noted at
every re-measurement in `config/quality_gates.yaml`'s `mutation-all`
comment history) rather than any change in the mutation set itself.
`mutation-all.timeout_seconds` re-sized by the file's own survivor-safe
rule from this run's wall: 1700s -> 1530s (2x727.799s + 70s =
1525.598s, rounded up). Every other timeout touched this release
re-checked against this run's walls: `rag-eval.timeout_seconds` kept at
580s, re-checked against this run's own 233.742s (T1+T2 review's own
268.8s derivation for the same gate is also comfortably under it) --
unchanged.

## Delegation record

Every executor model named: T1/T2/T3 implementer `claude-sonnet-5`; both
reviews `claude-opus-5`; T4 (this task) implementer `claude-sonnet-5`.

- T1 -- delegated, brief `docs/spec/task-briefs/v193-T1.md`; executor
  `claude-sonnet-5`; commits `bff8dc4` (pre-push runs `mutation-all`),
  `07bb158` (dirty-tree refusal, SIGTERM-before-SIGKILL, `v193-mutation-
  dirty-tree-unchecked`).
- T2 -- delegated, brief `docs/spec/task-briefs/v193-T2.md`; executor
  `claude-sonnet-5`; commit `aa8d576` (gate-7 smoke turn reranks via
  `rerank_llm`, not the chat client). The diagnosis (H1/H2 probe finding
  nothing, then an in-process instrumented gate run, then a targeted
  60s-timeout confirmation) and the fix were reached through two
  coordinator course-corrections after the probe's initial negative
  result -- recorded here since they changed the diagnosis from "no fix
  warranted" to a real, precisely located wiring defect.
- T1+T2 review -- delegated, brief
  `docs/spec/task-briefs/v193-T12-review.md`; a clean-context
  (`claude-opus-5`) review of the three landed commits (no 🔴, three 🟠,
  eight 🟡), closed in one follow-up commit (`b630b3c`, prompt 176,
  executor `claude-sonnet-5`) without rewriting any of the three reviewed
  commits.
- T3 -- delegated, brief `docs/spec/task-briefs/v193-T3.md`; executor
  `claude-sonnet-5`; two sequential commits (`acd373a` prompt 177,
  `6fcf1fc` prompt 178), a mutation-drift re-derivation between them, and
  one beyond-brief generalisation (the `devtools/bench_scenarios.py`
  exclusion extended from `PERF401`/`SIM117` to the two rules that
  actually hit it, `TRY004`/`ISC004`) flagged for operator review (see
  Disclosures).
- T3 review -- delegated, brief
  `docs/spec/task-briefs/v193-T3-review.md`; a clean-context
  (`claude-opus-5`) review of `acd373a`+`6fcf1fc` (no 🔴, one 🟠, seven
  🟡), closed in one follow-up commit (`ec1cf5f`, prompt 179, executor
  `claude-sonnet-5`) without rewriting either reviewed commit -- the
  🟠 TRY400 tally correction and one 🟡 (`tracing.py`'s `TRY004` revert)
  touch behaviour-adjacent numbers/code; the rest is citation and
  placement paperwork.
- T4 -- delegated, brief `docs/spec/task-briefs/v193-T4.md`; executor
  `claude-sonnet-5`; this commit (version bump, count-bearing lines,
  paperwork, seven gates, tag).

## Disclosures

- **Trailer string.** Every commit in this release carries
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`, matching the
  session's own named attribution string exactly -- no mismatch to
  disclose this release (contrast v1.9.2's disclosure (a)).
- **Gate-6 SIGKILL hazard -- closed.** v1.9.2's disclosure (b) (a gate
  timeout SIGKILLed only the direct `uv` child, orphaning
  `mutation_check.py` with no chance to restore a mutated file) is fixed
  by T1 commit `07bb158`: the runner now refuses to start on a dirty
  mutation-path tree, and a timeout SIGTERMs the tracked child before any
  SIGKILL, giving it a chance to restore. No longer an open item.
- **Pre-push profile -- decided.** v1.9.2's disclosure (d) (five subsets
  vs. one `mutation-all` run) is resolved by the operator's own order
  (`docs/spec/task-briefs/v193-T1.md`, quoted at the top of this report):
  T1 commit `bff8dc4` switches `pre-push` to `mutation-all`. The five
  `mutation-v*` gate definitions stay, kept runnable via `--select` for
  future per-range work, but are no longer wired into any hook profile.
- **`devtools/bench_scenarios.py` exclusion -- beyond-brief, unconfirmed.**
  T3's own brief named only `PERF401`/`SIM117` for this file's exclusion;
  neither hit it, but `TRY004`/`ISC004` did, and T3 applied the same
  exclude-and-disclose treatment to both on the reasoning that the
  underlying reason (the file's bytes are hashed and pinned into
  committed benchmark artefacts) applies regardless of which rule
  triggers a rewrite. Already landed in `acd373a`; flagged here again for
  the operator to confirm or override.
- **Sequencing: seven things landed after gate 7 finished.** The same
  class v1.9.2's erratum (prompt 172) disclosed. Gate 6 and gate 7 ran on
  a tree that did not yet contain: `docs/prompts/180-v193-t4-version-bump.md`,
  this "Gates (T4)" table and the gate-6 wall-chain paragraph, this
  Disclosures section and the Open tail section, the Ledger row, the
  Verdict, `docs/reports/tg-post-v1.9.3.md`, and `docs/llm-usage.md` row
  90 -- all of them use gates 6/7's own results as input, so they could
  only be written afterward. `mutation-all.timeout_seconds`'s 1700s ->
  1530s resize also landed after gate 6, from that run's own wall.
  Re-run on the tree as committed, after all of the above: `uv sync
  --locked` 0, `uv run --locked ruff check .` 0, `uv run --locked pytest`
  0 (1609 passed, 1 skipped, unchanged), `checks.py lint-docs` 0 -- these
  four are the only gates a doc-only diff can reach (gate 3 reaches
  `AGENTS.md`'s and `config/quality_gates.yaml`'s text via
  `tests/test_v190_agents.py`/`tests/test_v170_bench.py`). Gates 4/5/6/7
  were **not** re-run: gate 4 (`bot.py --selftest`) and gate 5
  (`--selftest-live`) touch no file this task's trailing edits changed;
  re-running an 11-12 minute mutation pass and a live rag-eval to
  validate a comment/table/paperwork-only edit was judged not worth it,
  the same call v1.9.2 T3's own erratum made explicit.

## Open tail

- The v1.9.1/v1.9.2 open tail (one rerank call succeeding only on attempt
  3) is **closed**: T2 diagnosed and fixed it (`aa8d576`), and three
  consecutive gate-7 runs after the fix show zero retry lines (see "T2 --
  rerank tail" above).
- One genuinely open item, carried to v1.10.0: **redaction hardening**
  (T1+T2 review finding 8). `log.exception`'s traceback and chained
  `__context__`/`__cause__` rendering are not passed through `redact()` --
  reviewed and confirmed not a live leak at any of the 10 adopted
  `log.exception` sites today, but the `redact(str(exc))` argument at
  several call sites reads as protective when the traceback itself
  already carries the unredacted text. Proposed direction: a redacting
  `logging.Filter` installed once at the root logger, rather than relying
  on every call site. No code change this release.

## Ledger row (paste into `economics.md`)

Review findings counted from the review briefs themselves, not from
memory: `docs/spec/task-briefs/v193-T12-review.md` (no 🔴, three 🟠, eight
🟡 — 11 total) and `docs/spec/task-briefs/v193-T3-review.md` (no 🔴, one
🟠, seven 🟡 — 8 total), both closed.

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | v1.9.3 | 2026-09-13 | — (patch, no new spec; task briefs `docs/spec/task-briefs/v193-T1.md`, `-T2.md`, `-T12-review.md`, `-T3.md`, `-T3-review.md`, `-T4.md`) | 8 (173–180) | yes — all seven gates green on the authoritative run of the final tree (see Disclosures: gates 1–3 plus `lint-docs` re-run once more after this task's own trailing doc edits, all green; gates 4/5/6/7 not re-run, not gate-reachable by a doc-only diff) | T1+T2 review 0 🔴 / 3 🟠 / 8 🟡 (11), T3 review 0 🔴 / 1 🟠 / 7 🟡 (8) — all fixed | unknown (harness does not expose per-request usage) | $0 marginal (Claude Code subscription-metered session; live inference on gates 5/7 and T2's diagnostic probe calls, at reference prices, no real spend tracked) | claude-sonnet-5 (both reviews: claude-opus-5) | Claude Code |
```

## Verdict

All seven gates green on the final tree (see "Gates (T4)" above); the
three tails the operator ordered closed are closed (pre-push now runs
`mutation-all` and the gate-timeout/SIGKILL hazard is fixed, T1; the
rerank third-attempt tail is diagnosed and fixed, T2; the ruff
rule-family proposal is decided and applied, T3); the v1.9.1/v1.9.2 open
tail (the rerank attempt-3 tail) is closed; one genuinely open item is
carried to v1.10.0 (redaction hardening, see Open tail); one flagged
item awaits operator confirmation (the `bench_scenarios.py` `TRY004`/
`ISC004` exclusion, see Disclosures). Version bumped 1.9.2 → 1.9.3,
count-bearing lines at their real final numbers (1610 tests, 114
mutation entries), annotated tag `v1.9.3` created on the release commit.
PASS.
