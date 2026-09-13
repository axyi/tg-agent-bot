# Prompt 184 — v1.9.4 T4: the "not now" ruff rows, now

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded, well-specified extension against an existing
  task brief (`docs/spec/task-briefs/v194-T4.md`) -- mechanical `os.*` ->
  `pathlib` rewrites at named sites plus one regex-escape fix, all with an
  inventory of exact hit counts and per-site notes already resolved; no open-
  ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.4 T4 (patch, no new spec file -- precedent v1.5.1, v1.9.1–v1.9.4 T1–T3)
- **Owner of:** `bot.py`, `storage.py`, `tools.py`, `pyproject.toml`,
  `devtools/mutation_check.py`, `tests/test_tool_output.py`,
  `tests/test_v170_bench.py`, `tests/test_v160_observability.py`,
  `tests/test_v12_patch.py`
- **REQ ids:** none new for this patch (precedent: v1.9.1 T3, v1.9.2 T3,
  v1.9.3 T4, v1.9.4 T1-T3 also landed patch fixes with no new REQ id)

## Goal

Close the two remaining "not now" rows of v1.9.3 T3's ruff decision table
(`pyproject.toml` `[tool.ruff.lint]` comment block): `PTH*` (18 hits --
`os.chmod`/`os.stat`/`os.unlink`/`os.path.islink`/`os.path.exists`/
`os.path.join`/`open()` sites in `bot.py`, `storage.py`, `tools.py` and three
test files) and `RUF043` (1 hit -- an ambiguous `pytest.raises(match=...)`
regex pattern in `tests/test_v160_observability.py`). `PLW0603` stays
"never" adopted -- its row is rewritten from "not now" to "never" with the
reason it protects (`_shutdown`/`_started_at`/`_dropped_spans` module-state
pattern), with no change to its lint behaviour. Both rules then join
`[tool.ruff.lint].select`.

## Constraints

- Every `storage.py` chmod/stat rewrite keeps identical semantics: the
  `Path(str(db_path) + suffix)` string-arithmetic (never
  `db_path.with_suffix`, which would replace the `.db` extension) and the
  exact `FileNotFoundError` suppression scope in `_restrict_permissions`.
- `bot.py`'s `_remove_sandbox_entry` keeps the exact "symlink -> chmod
  follows the target, so skip it" comment and reasoning (REQ-V13-CO-01);
  `tools.py`'s `append_audit` leaves the raw `os.open`/`os.fdopen` fd pair
  untouched -- it is not equivalent to `Path.open()` (explicit
  `O_WRONLY | O_APPEND | O_CREAT` flags with a `0o600` create mode).
- `devtools/bench_scenarios.py` is byte-hash-frozen (REQ-V13-BEN-12); it has
  no PTH/RUF043 hits, so no new `per-file-ignores` entry is needed.
- `tests/test_v170_bench.py`'s `T-V170-ACC-03` freeze is about test
  behaviour/assertions, not file bytes -- confirmed nothing hashes this
  file's own bytes before editing its three `open()` calls.
- Do not run `devtools/mutation_check.py`'s full/`--select`/`--only` mutation
  runs; do not touch `.env`; no git add/commit/push (the coordinator commits
  after independently verifying the diff, then runs `--only` on each
  re-derived mutation entry against the committed tree).
- Two mutation entries drifted after the `bot.py` rewrite
  (`sec-qta-03-chmod-and-retry`, `v13-symlink-chmod`, both matching the old
  `os.chmod(path, ...)` / `os.path.islink(path)` lines that no longer exist)
  and were re-derived against the new `p.chmod(...)` / `p.is_symlink()`
  shape with identical mutation semantics; left for the coordinator to run
  `--only` on each against the committed tree.

## Acceptance

```
uv run --locked ruff check .
uv run --locked ruff check . --select PTH,RUF043
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python devtools/checks.py lint-docs
```

All six exit 0 (the last two ruff invocations confirming PTH/RUF043 are both
clean and selected), plus a throwaway drift script confirming
`119/119 matched, 0 drifted` across `devtools/mutation_check.py`'s
`MUTATIONS` list. `uv run --locked pytest` collects 1631 passed, 1 skipped
(up two from 1629 passed after `tests/test_v12_patch.py`'s
`test_t_v12_orp_01_start_ticks_survives_a_space_in_comm` was adapted to
monkeypatch `Path.open` instead of the module-level `open` builtin it no
longer calls).

## Stop

Stop and report instead of forcing a workaround when: a `storage.py`
rewrite changes a mode bit or an exception path (then keep that one site as
`os.*` with `# noqa: PTHxxx -- <why>` and count it); a mutation cannot be
re-derived with identical semantics.
