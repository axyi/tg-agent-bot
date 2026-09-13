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
`devtools/checks.py:538-550`'s `_validate_profiles` rejects outright
("gate(s) named by no profile") -- discovered by running `checks.py
doctor` against the first draft of this edit. Fixed with a new,
intentionally inert `mutation-subsets` profile naming the five gates:
`checks.py run --profile` only accepts `pre-commit`/`pre-push`/`full`
(`devtools/checks.py:1657`'s argparse `choices`), so this profile is
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
once, alone, nothing else on the box, on this commit's tree (`ceb4a11`,
111 entries, both new mutation entries included): **111 mutations, 111
killed, 0 survived, 0 errored, 0 drifted** -- real=13m34.449s (814.449s).
`timeout_seconds` re-sized by the file's own rule (2x measured wall + 70s
survivor floor, rounded up to 10s): `1440s -> 1700s`
(2x814.449s + 70s = 1698.898s, rounded up). Up from 1440s at 110 entries:
one more entry plus this commit's own two new `git show` subprocess calls
per distinct mutation path (Fix 1's dirty-tree check) account for some of
the jump, the rest consistent with this box's own documented shared/
contended-machine variance (`config/quality_gates.yaml`'s own history of
re-measurements). Comment in `config/quality_gates.yaml` updated
accordingly; this measurement was landed by amending commit `ceb4a11`
(the tree actually measured -- the amend that follows only adds this
paperwork, so the amended commit's hash necessarily differs from the one
named here and above), per the brief's own "re-read every count/hash
after an amend" instruction -- the fast gates (`ruff`,
`checks.py doctor`, `checks.py lint-docs`) were re-run green against the
amended tree; an 11+-minute `mutation-all` re-run was not judged necessary
to validate a comment-and-timeout-number-only follow-up edit (the number
above is this commit's own real, freshly-measured wall, unaffected by the
follow-up edit itself).

## Delegation record

- T1 -- delegated, brief `docs/spec/task-briefs/v193-T1.md`.

## Ledger row (paste into `economics.md`)

<!-- filled at T4 (version bump), the same convention v1.9.2 T3 used -->

## Verdict

<!-- filled at T4 -->
