# v1.9.2 — handoff written before context compaction (2026-09-12)

Operator's decision, verbatim intent: "полный глубокий анализ кода проекта
тулами skylos, trivy и прочее, не только diff, но весь код; исправление всех
проблем; затем оптимизация времени выполнения не-LLM тестов — выкинуть
дублирующие и избыточные, найти, как сократить ещё время выполнения. Версию
поднимаем до 1.9.2." Starts on the operator's `go` after `/compact`.

## State at handoff

- `main` = `7a97f29`, tag `v1.9.1`, pushed, `ahead 0`, tree clean.
- Gates on that tree: all seven exit 0. pytest **1593 collected** (1592 passed,
  1 skipped) in 1m12s; mutation **108/108 killed** in 61m39s; gate 7 green in
  2m37s.
- Scanner gates pass in warn mode with findings left standing — the last
  pre-push log reads `[PASS] skylos: 15 in-scope finding(s), 12 out-of-scope`.
  Gate membership and pins: `config/quality_gates.yaml` (ruff 0.16.6, gitleaks
  8.30.1, semgrep 1.176.0, trivy 0.74.0, skylos 4.35.0).
- Known open tail from v1.9.1, out of this patch's scope unless it falls out
  of the analysis: one rerank call succeeds only on attempt 3 (~15.8 s against
  `_RERANK_TIMEOUT_S = 15.0`).
- Timings that define "slow": pytest 72 s; mutation gate ≈ 108 × one full
  suite run ≈ 60 min; `pre-push` profile 1793–8373 s measured (five mutation
  subsets + scanners); `full` profile adds two live gates.

## Phases — each its own task brief, delegated by file, reviewed in a clean context

### T1 — whole-tree static analysis and fixes

Run every scanner the repo pins over the **entire tree**, not the diff:
`skylos` (dead code), `trivy` (dependency and config vulnerabilities),
`semgrep`, `gitleaks`, `ruff` with the full rule set the project configures.
Inventory every finding first — tool, file:line, class, in-scope /
out-of-scope per `quality_gates.yaml` — and write the inventory to the report
before touching anything. Then fix all of them, one class of finding per
commit where that keeps the diff reviewable. Rules that bind:

- A skylos "unused" hit is not a deletion order. Check reflection, dynamic
  dispatch, `checks.py`/`mutation_check.py` `find` strings, test doubles and
  external callers before removing anything; anything uncertain stays and is
  listed as such. Pre-existing dead code that turns out to be load-bearing is
  reported, not deleted.
- Every mutation entry's `find` string must still match after the fixes —
  gate 6 `drifted` count must stay 0.
- Scanner exclusions are not fixes. If a finding is a true false positive,
  the suppression is inline, commented with why, and counted in the report.
- Version-pin and count-bearing tests are protected by `REQ-V190-EC-03`'s
  no-deletion rule; repoint, never delete.

### T2 — non-LLM test time

Goal is measured: pytest wall clock and, through it, the mutation gate
(108 × suite) and the pre-push hook. Order of levers, cheapest evidence first:

1. **Measure before cutting.** `pytest --durations=50` and a per-file
   timing; `--collect-only` to size the suite. Write the top-50 into the
   report. Anything under 0.1 s is not a target.
2. **Duplicates and redundancy.** A test is redundant only if a named other
   test fails on every mutation this one kills — prove it with
   `mutation_check.py --only <entry>` before and after, not by reading.
   Deleting a test that is the sole killer of a mutation entry is the
   regression this repo's whole gate design exists to prevent. Record each
   removal as `removed <test> — covered by <test>, mutation <entry> still
   killed`.
3. **Fixture cost.** Session/module-scoped fixtures where tests only read;
   real subprocess/docker/network/sleep in unit tests replaced with the
   fakes `tests/fakes.py` already provides; `tmp_path` DB setup shared
   where isolation is not the property under test.
4. **Parallelism.** `pytest-xdist` (`-n auto`) if the suite is
   isolation-clean — v1.5.1's D1 (fixtures leaking into the real repo) is
   the precedent for why that must be verified, not assumed. If adopted,
   pin it in `pyproject.toml`/`uv.lock` and in `quality_gates.yaml`'s gate
   argv.
5. **Mutation gate.** It reruns the whole suite per mutation. Levers, each
   measured: run only the test files that import the mutated module (with
   a fallback to the full suite when the map is empty), `-x` early exit on
   first failure (a killed mutation needs one failing test, not all),
   parallel mutations if the working-tree mutate/restore design allows it —
   it currently mutates in place, so parallel means worktrees or it does
   not happen. Keep `105 → 108 entries`, keep `0 drifted`.
6. **Pre-push profile.** Five mutation subsets run serially; after T2's
   measurements decide, with the operator, whether pre-push keeps all five
   or runs `mutation-v190` + a rotating one, with `full` still running all.

Every timing claim in the report carries the command and both numbers
(before/after). The gate timeouts in `quality_gates.yaml` follow the file's
own 2× rule from the new measurements.

### T3 — version 1.9.2, paperwork, authoritative gates, tag

Same shape as v1.9.1's T2 (`docs/spec/task-briefs/v191-T2.md`): version-pin
test convention (repoint `tests/test_v191_version.py` to the frozen tag blob,
new `test_v192_version.py` red-before/green-after), count-bearing lines in
README/AGENTS.md, `docs/reports/report-v1.9.2.md` with the per-task
delegation record, `tg-post-v1.9.2.md`, `docs/llm-usage.md` rows, Ledger
row; all seven gates verbatim on the final tree, **gate 6 and gate 7 never
concurrent**; annotated tag; the operator pushes.

## Process rules carried over

- Prompt numbering continues from 164. One prompt → one commit.
- Implementation is delegated by task-brief file; the main context
  coordinates and verifies; review runs in a clean-context subagent.
- Nothing is read or concluded about live gates, diffs or security while
  gate 6 is running (memory `project-mutation-gate-flaky`).
- `.env` is never read, printed or committed.
- Never `--no-verify`.
