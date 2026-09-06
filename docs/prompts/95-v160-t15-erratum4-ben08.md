# Prompt 95 — spec-v1.6.0 T15 resume, erratum 4: REQ-V160-BEN-08

- **Date:** 2026-09-06
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a small, well-scoped bug fix (one wrong `rmtree` target)
  plus its one covering test — no design decision open, the fix is fully
  specified by the erratum
- **Harness:** Claude Code
- **Stage:** T15 (resumed, prompt 93)
- **Owner of:** `devtools/bench.py` (`_cmd_run`'s wipe-before-write step
  only), `tests/test_v160_bench.py` (new test `T-V160-BEN-08`), this prompt
  file
- **REQ ids:** REQ-V160-BEN-08 (new, erratum 4)

## Goal

Stop `bench.py run --tag <tag>` from deleting the entire `.bench/` root
before writing; it must delete only `.bench/<tag>/`, leaving sibling tag
directories and any `--out` document written directly under `.bench/`
(the `smoke-v160.json` shape) untouched. The old behaviour destroyed the
first complete `smoke-v160.json` when a second diagnostic `run` followed it
at the original T15 (`docs/reports/report-v1.6.0.md`, "Evidence lost").

## Constraints

- Touch only `devtools/bench.py`'s `_cmd_run` (the `if BENCH_ROOT.exists():
  shutil.rmtree(BENCH_ROOT, ...)` block becomes a tag-scoped
  `BENCH_ROOT / arguments.tag` wipe) and `tests/test_v160_bench.py` (one new
  test). No other function, gate, scenario or config change.
- `runs_root=BENCH_ROOT / arguments.tag` (already the value passed to
  `run_bench`) needs no change; `_run_config`'s own
  `workdir.mkdir(parents=True, exist_ok=True)` already creates `BENCH_ROOT`
  and the tag directory as needed, so nothing upstream of the wipe has to
  pre-create `BENCH_ROOT`.
- No inference call in this prompt.

## Acceptance

- `T-V160-BEN-08` (`test_run_removes_only_its_own_tag_directory`): under the
  stub client, two consecutive `run` invocations with different tags leave
  both `.bench/<tag>/` documents on disk, and a sibling `--out`-shaped
  document written directly under `.bench/` survives; a third run reusing
  the first tag replaces only that tag's own directory, leaving the second
  tag's directory and the sibling document untouched.
- `uv run --locked ruff check .` — clean.
- `uv run --locked pytest -q` — all green (1006 tests), no new failures.
- `git status --porcelain` — exactly the two owned files plus this prompt.

## Stop

None encountered.
