# Prompt 183 — v1.9.4 T3: a hung mutation is reported by id, not by the gate's timeout

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded, well-specified extension against an existing
  task brief (`docs/spec/task-briefs/v194-T3.md`) -- one new module
  constant, one `proc.wait(timeout=...)` bound reusing an existing
  terminate helper, and their tests; no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.4 T3 (patch, no new spec file — precedent v1.5.1, v1.9.1–v1.9.4 T1/T2)
- **Owner of:** `devtools/mutation_check.py`, `tests/test_mutation_check.py`,
  `AGENTS.md`
- **REQ ids:** none new for this patch (precedent: v1.9.1 T3, v1.9.2 T3,
  v1.9.4 T1/T2 also landed patch fixes with no new REQ id)

## Goal

The only timeout around a mutation run was the gate's own
(`config/quality_gates.yaml` `mutation-all.timeout_seconds`, 1530s): if one
`pytest` invocation hangs, the whole gate runs to 1530s and the output names
no mutation -- the operator cannot tell "one hung" from "the box was slow".
This task bounds each mutation's own child to `_MUTATION_TIMEOUT_S` (180.0),
terminates it the same way a signal already does
(`_terminate_current_child`, reused, not reimplemented) on a timeout, and
reports it as `ERRORED` with the mutation id and elapsed time -- the
outcome vocabulary (`KILLED`/`SURVIVED`/`ERRORED`/`DRIFTED`) and every
downstream parser of the summary line stay exactly as they are.

## Constraints

- No fifth outcome string; the timeout path maps to `ERRORED` purely via a
  sentinel exit code (`_HUNG_EXIT_CODE`, neither `0` nor `1`) that
  `run_one`'s existing exit-code mapping already classifies -- no changes
  to `run_one` or `run_all`.
- Tree restoration on a hang goes through the existing `finally:
  restorer.restore_one(path)` in `run_one`, exactly like every other
  outcome -- no second restore path.
- `--list`/`--only`/`--select`, the shrink guard and the dirty-tree refusal
  unchanged.
- Do not run `devtools/mutation_check.py`'s full/`--select`/`--only`
  mutation runs (a bounded, self-contained test invocation is fine and
  required); do not touch `.env`; no git add/commit/push.
- The two new mutation entries
  (`v194-mutation-hang-unbounded`,
  `v194-mutation-hang-reported-as-killed`) are added but not run via
  `--only` -- left for the coordinator, since `mutation_check.py` is itself
  a mutation path and needs a clean committed tree first.

## Acceptance

```
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python devtools/checks.py lint-docs
uv run --locked python devtools/checks.py doctor
```

All five exit 0, including the suite's collected count (every existing test
plus the two new ones in `tests/test_mutation_check.py`:
`test_t_v194_t3_hang_is_errored_with_id_and_tree_restored` and
`test_t_v194_t3_normal_kill_within_timeout_unaffected_by_hang_guard`). A
bounded sanity sub-run,
`uv run --locked pytest tests/test_mutation_check.py -k hang -v`, completes
in well under 30s wall.

## Stop

Stop and report instead of forcing a workaround when: the real-child hang
test cannot be made deterministic under its own bound; the timeout path
leaves the working tree dirty on any run (`git status --short` after the
test run is non-empty).
