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

## Delegation record

- T1 -- delegated, brief `docs/spec/task-briefs/v193-T1.md`.
- T2 -- delegated, brief `docs/spec/task-briefs/v193-T2.md`; the diagnosis
  (H1/H2 probe finding nothing, then an in-process instrumented gate run,
  then a targeted 60s-timeout confirmation) and the fix were reached
  through two coordinator course-corrections after the probe's initial
  negative result -- recorded here since they changed the diagnosis from
  "no fix warranted" to a real, precisely located wiring defect.
- T1+T2 review -- delegated, brief
  `docs/spec/task-briefs/v193-T12-review.md`; a clean-context (opus)
  review of the three landed commits, closed in one follow-up commit
  without rewriting any of them.

## Ledger row (paste into `economics.md`)

<!-- filled at T4 (version bump), the same convention v1.9.2 T3 used -->

## Verdict

<!-- filled at T4 -->
