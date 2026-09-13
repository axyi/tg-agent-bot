# Prompt 167 — v1.9.2 T2: mutation runner orders test files by relevance

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a fully specified performance change against a measured,
  pre-derived contract (`docs/spec/task-briefs/v192-T2.md` section 2) — the
  ordering algorithm, the silent-shrink guard shape and the false-kill proof
  procedure were all fixed by the brief; no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.2 T2 (patch, no new spec file — precedent v1.5.1)
- **Owner of:** `devtools/mutation_check.py`, `tests/test_mutation_check.py`,
  `config/quality_gates.yaml`, `docs/spec/task-briefs/v192-T2.md` (brief,
  authored before this prompt), `docs/prompts/167-v192-mutation-order.md`,
  `docs/llm-usage.md` (row 77)
- **REQ ids:** none new — closes the REQ-V13-CO-06 / REQ-V15-GATE-04
  silent-shrink hole for the new ordering mechanism

## Goal

Gate 6 reruns the whole suite per mutation under `pytest -x`; pytest's
default alphabetical-by-file order means a `rag.py` mutation runs ~1400
tests before its killer test in `tests/test_v190_retrieval.py` is reached.
Implement exactly what the brief specifies: `ordered_test_files(mutation,
root)` builds the complete, ordered test-file list in five tiers (version
prefix, same-named module file, direct importers, one-hop importers,
everything else — never a subset, proven a permutation by an assertion in
the function itself), `default_runner(mutation)` uses it, `run_one` passes
`mutation` through to the runner, a once-per-invocation collect-count guard
in `main()` closes the silent-shrink hole an explicit file list opens, and
the new mutation entry `v192-mutation-order-shrink-unchecked` (with its
killer test) proves that guard is load-bearing.

## Constraints

- Everything the brief states verbatim is the contract, not a starting
  point for re-derivation: the five tiers, the `cov-` → `test_v12_patch.py`
  override, the once-per-invocation (not per-mutation) placement of the
  shrink check, the false-kill guard's "every distinct mutated path"
  scope.
- `pytest-xdist` adoption (brief section 3) is prompt 168's scope — this
  commit's `default_runner` does not add `-n 0` / `-p no:xdist`, since
  xdist is not yet a dependency; verified empirically (`-n 0` errors
  "unrecognized arguments" before xdist is installed).
- Commit only this task's files; `config/quality_gates.yaml`'s five
  `mutation-v*` gate `timeout_seconds` follow the file's own 2x-measured
  rule from this commit's own before/after numbers, nothing else in that
  file changes. No version bump, no tag, no push, never `--no-verify`.
- `.env` never read; `data/`, `evals/rag/corpus` never opened.
- The brief's own trailer instruction names `Claude Opus 5`; this run's
  actual executor is `claude-sonnet-5` — the trailer below is accurate to
  the real executor, and this discrepancy is recorded rather than silently
  resolved either way (see report section "T2 — gate 6").

## Acceptance

`uv run --locked ruff check .` and `ruff format --check .` exit 0;
`uv run --locked pytest` exit 0 (1598 collected, up from 1593 — five new
tests in `tests/test_mutation_check.py`); `uv run --locked python bot.py
--selftest` exit 0; `uv run --locked python devtools/checks.py lint-docs`
exit 0; the throw-away drift script (`/home/akh/.claude/jobs/45feeee3/tmp/
t2/drift_check.py`) reports 109/109 matched, 0 drifted;
`devtools/mutation_check.py --only v192-mutation-order-shrink-unchecked`
killed; `devtools/mutation_check.py --select v190-` killed 7/7; the
false-kill guard (18 distinct mutated paths — more than the brief's "about
a dozen" estimate, since this tree has 18 distinct paths across 109
entries — each run once on the unmutated tree under its ordering) all
exit 0; the five `--select` subsets (v15-, v160-, v170-, v180-, v190-)
measured before (old alphabetical order) and after (this commit), all
still killing the same n/n.

## Stop

If the false-kill guard finds any ordering under which the clean tree is
red, or the shrink check cannot be made to compare like with like, stop and
report rather than adjusting the ordering algorithm or the guard to make it
pass.
