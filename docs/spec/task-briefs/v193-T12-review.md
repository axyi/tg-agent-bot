# v1.9.3 T1+T2 — clean-context review findings to close (prompt 176, one commit)

Review of `bff8dc4` + `07bb158` + `aa8d576` (opus, clean context; every
probe re-run; gate 7 re-run independently: 232.4 s, 0 retry lines, 0
failover lines — T2's fix confirmed). No 🔴; three 🟠, eight 🟡. Close all
in **one commit** `test: SIGTERM reaches the process group; child
termination covered; pre-push dirty-tree refusal surfaced (v1.9.3 T1+T2
review)`, prompt `docs/prompts/176-v193-t12-review-findings.md`,
llm-usage row 86. Do not rewrite the three commits. T3's ruff prompts move
to 177/178.

1. 🟠 `tests/test_v15_standards.py:634-654` proves SIGTERM reached the
   **direct** child only; swapping `os.killpg` for `os.kill(pid)` (the
   pre-fix defect) still passes. Rewrite with a **grandchild**: the direct
   child spawns a subprocess that traps SIGTERM and writes the marker, then
   both sleep past the timeout; assert the marker (grandchild's) exists.
   Under 2 s, deterministic (no sleep races: the grandchild writes a
   "ready" file before the parent may be considered started, or the test
   polls for readiness with a bounded loop). Add mutation entry
   `v193-gate-timeout-kills-direct-child-only` (`os.killpg(...)` →
   `os.kill(proc.pid, ...)` in `_terminate_process_group`) killed by it.
2. 🟠 `devtools/mutation_check.py:1611-1631`, `:1687` — `_CURRENT_CHILD`,
   `_terminate_current_child`, the handler call: no test, no mutation. Add
   tests in `tests/test_mutation_check.py`: a fake child object whose
   process group receives the terminate (monkeypatch `os.killpg`), the
   handler calls it **before** `restore_all` and `sys.exit(1)`; and
   mutation `v193-signal-handler-leaves-child-running` (drop the terminate
   call from the handler) killed by it.
3. 🟠 Undisclosed pre-push consequence: `git push` with WIP edits on any of
   the 19 mutation paths now fails at pre-push as `gate mutation-all exited
   1` — `checks.py:1289-1294` swallows the child's stderr for
   `exit_status` gates, so the refusal's path list and guidance never reach
   the operator. Two parts: (a) `checks.py`: for a failed `exit_status`
   gate, append the last five non-empty stderr lines of the child to the
   gate message (bounded, redacted through the existing `--redact`-style
   path if one exists for command output; if none exists, plain) — with a
   test; (b) `AGENTS.md` gate-6 paragraph and README: one sentence that
   pre-push refuses a tree with uncommitted edits to a mutation path, and
   what to do.
4. 🟡 Refusal message (`mutation_check.py:1783-1788`): for a staged edit
   `git diff <path>` shows nothing and `git checkout -- <path>` restores from
   the index — a loop. Say `git diff HEAD -- <path>` and `git restore
   --staged --worktree <path>` (and keep `git checkout -- <path>` out).
5. 🟡 `config/quality_gates.yaml:521-529` and report `:133-143` attribute
   680 → 814 s to "two `git show` calls per mutation path"; the check is
   one `git show` per distinct path, once per invocation (19 calls,
   sub-second). Keep only the box-variance explanation.
6. 🟡 `rag-eval` gate comment (`quality_gates.yaml:203-213`) still derives
   580 s from v1.9.1's 287.4 s; the three fixed-tree walls are 268.8 /
   233.3 / 250.7 s (+ reviewer's 232.4). 2× 268.8 = 537.6 ≤ 580: keep 580,
   re-derive the comment from this release's slowest wall. Report T2: add
   one sentence on why the walls are longer than v1.9.2's 187 s — measure,
   do not guess: the three saved logs have no timing per phase; re-run gate
   7 **once** with `2>&1` and timestamps per printed phase
   (`ts`/`date` prefix on each line via a wrapper, or the eval's own
   `print_fn` timings if it has them) and name the slow phase (embedding
   ingest? LM Studio chat JIT load on the smoke turn?). Save that log with
   stderr under `/home/akh/.claude/jobs/45feeee3/tmp/v193/` and cite it.
7. 🟡 Conversation smoke advisory prints `fail — turn 2 queries: []` in
   4/4 runs since the fix, vs `pass` in v1.9.2's run. That correlates with
   the change — investigate, do not label "intermittent": with
   `_RecordingSearcher`, capture turn 2's agent outcome (tool calls made,
   errors, the model's final text) in the gate-7 run from item 6. If turn 2
   no longer calls `search` because of something the fix changed (e.g. the
   chat client double-routing, a changed conv_id, an exception swallowed in
   the tool path), that is a defect → **stop and report** with the
   evidence; if the chat model simply answered from turn-1 context without
   a tool call (model non-determinism, advisory by design), write that with
   the captured outcome in the report and move on.
8. 🟡 Stale citations: `quality_gates.yaml:18-24` and the report cite
   `checks.py:538-550`/`:1657` (now `:540-552`, orphan check `:549-551`,
   `choices` `:1696`); hashes `ceb4a11`, `0fde4c3` are amended-away
   objects — replace with `07bb158` / `aa8d576` everywhere they appear
   (`grep -rn 'ceb4a11\|0fde4c3' docs config`).
9. 🟡 `docs/prompts/174-…md:1` title says "restores a leftover mutated
   tree"; the implementation refuses. Fix the title line (and the brief's
   own commit-B title stays as history — add a one-line note under it).
10. 🟡 `tests/test_mutation_check.py:352-370` does not fake
    `_shrink_counts` like its siblings → two real `--collect-only` runs
    under mutation. Fake it the same way.
11. 🟡 Report: add a T2 acceptance line (entries 112, collected 1605) like
    T1's; note that `AGENTS.md:167-170` / `tests/test_v190_agents.py:141-142`
    counts move at T4 by precedent. The mutation id
    `v193-smoke-reranks-on-chat-client` stays (renaming a landed id is
    churn).

After any amend or added commit, re-read every place a count or hash is
named. Acceptance, sequential, nothing concurrent: `ruff check .` 0;
`ruff format --check .` 0; `pytest` 0 (report collected); `checks.py
lint-docs` 0; `checks.py doctor` 0; `checks.py run --profile pre-commit`
0; drift script all entries (114); `--only` each of the two new entries →
killed; the item-1 test run 5× → 5/5; the single gate-7 run from item 6
(alone, not concurrent with any mutation run) → exit 0, wall. Return the
commit hash, exit codes, the slow-phase finding, the smoke-turn finding.
