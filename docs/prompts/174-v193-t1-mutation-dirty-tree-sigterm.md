# Prompt 174 — v1.9.3 T1 commit B: mutation runner restores a leftover mutated tree on start-up; gate timeouts terminate before they kill

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a precisely-specified defect fix against an existing
  task brief (`docs/spec/task-briefs/v193-T1.md`) — exact line references,
  named functions, a bounded fix shape (SIGTERM-before-SIGKILL, a startup
  dirty-tree check); no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.3 T1 commit B (patch, no new spec file)
- **Owner of:** `devtools/mutation_check.py`, `devtools/checks.py`,
  `tests/test_mutation_check.py`, `tests/test_v15_standards.py`,
  `config/quality_gates.yaml`, `docs/reports/report-v1.9.3.md`,
  `docs/llm-usage.md`
- **REQ ids:** REQ-V12-MUT-02, REQ-V15-GATE-06/07/08

## Goal

Fixes the defect `docs/reports/report-v1.9.2.md` disclosed as a v1.10.0
item, pulled into this patch by the operator: `devtools/checks.py:1098-1110`
`subprocess.run(argv, timeout=…)` SIGKILLs only the *direct* child on
`TimeoutExpired` — for gate 6 that is `uv`, not `mutation_check.py` — so
the runner is orphaned, never signalled, and a mutated source file can be
left on disk with no survivor id printed.

Fix 1 (primary, survives any kill): before the first mutation,
`mutation_check.py` refuses to start (exit 1) if any distinct mutation
path's working-tree bytes differ from the committed `HEAD` blob (`git show
HEAD:<path>`, the same git-objects-only source of truth `checks.py`'s own
`replay` uses), naming the offending path(s) and how to recover. Skipped
for `--list`; placed after the `--only`/`--select` id/prefix checks and
before the shrink guard. New mutation entry
`v193-mutation-dirty-tree-unchecked` with two killer tests: a direct
git-repo-backed unit test of `_dirty_mutation_paths`, and a `main()`-level
test (mirrors the shrink-guard tests' own shape) proving `run_all` is
never reached.

Fix 2 (complementary): `checks.py:run_argv` now runs its child via
`Popen(..., start_new_session=True)` + `communicate(timeout=…)`; on
`TimeoutExpired` it SIGTERMs the whole process group, waits
`_TERMINATE_GRACE_S` (5.0s), SIGKILLs the group if still alive, then reaps
— result semantics (`CommandResult` shape, the `"timed out after …s"`
message) unchanged. `mutation_check.py`'s own `default_runner` now runs
its `pytest` child the same way, tracked in `_CURRENT_CHILD`; its
SIGINT/SIGTERM handler terminates that child's process group before
restoring the tree and exiting, closing the gap the brief named (the
handler restored the tree but left `pytest` running).

Measurement: with both fixes in, `mutation-all` re-measured once, alone,
on this commit's tree; `mutation-all.timeout_seconds` re-sized by the
file's own 2x-plus-70s-floor rule from the fresh wall, comment updated.

## Constraints

Gate 6 `drifted` 0 (111/111, up from 110 — this commit's own new entry).
`--list`/`--only`/`--select` fail-loud semantics and the shrink guard
unchanged. Nothing runs concurrently with any mutation run. `.env` never
read; `data/`, `evals/rag/corpus` never opened. No push, no `--no-verify`.

## Acceptance

```
uv run --locked ruff check . ; uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python devtools/checks.py doctor
uv run --locked python devtools/checks.py lint-docs
<drift script>                                                  # 111/111
uv run --locked python devtools/mutation_check.py --only v193-mutation-dirty-tree-unchecked
uv run --locked python devtools/mutation_check.py               # all killed, wall recorded
```

Run on the committed tree (the dirty-tree check itself requires it — see
report); `quality_gates.yaml`'s `mutation-all.timeout_seconds` and this
report's own numbers are amended onto this commit once the measurement
lands, per the brief's own "re-read every count/hash after an amend" rule.

## Stop

If the dirty-tree check cannot distinguish the runner's own in-process
tests from a real dirty tree without weakening it; if a gate-timeout test
cannot be made deterministic under 2s; if the `mutation-all` run reports a
survivor or drift.
