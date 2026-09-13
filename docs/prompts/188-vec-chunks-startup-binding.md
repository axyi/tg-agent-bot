# Prompt 188 — vec-chunks-startup-binding

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a scoped, well-specified bug fix (GitHub issue #3 already
  names the exact root cause and file:line ranges) — no exploratory design
  work needed, so the default coding model fits.
- **Harness:** Claude Code
- **Stage:** T1 (fixes GitHub issue #3; no release version bump — see
  Constraints)
- **Owner of:** `bot.py`, `tests/test_routing.py` (or a new
  `tests/test_v195_startup_binding.py`), `devtools/mutation_check.py`,
  `docs/spec/spec-v1.9.0-delta-2.md`
- **REQ ids:** REQ-V190-STO-04

## Goal

`storage.init_schema`'s three call sites in `bot.py` (`main()`,
`run_selftest`, `_live_db`) all call it bare, so on a bot started with
`EMBEDDING_MODEL`/`EMBEDDING_DIM` configured, `vec_chunks` and the
`rag.embedding` state key are never created — every document upload then
fails with `Storage error. The document was not saved.` (`OperationalError:
no such table: vec_chunks`). Fix: route all three call sites through one
shared helper that always passes the configured pair, so they cannot drift
apart again, with the new `ConfigError` path this opens up in `main()`
handled the same way every other startup config refusal already is (exit 2,
logged, redacted).

## Constraints

Full design is fixed in `docs/spec/task-briefs/v195-T1.md` — read it first,
it is the contract for this prompt, not a suggestion. In particular: no
version bump (`pyproject.toml` stays 1.9.4, no new
`docs/reports/report-*.md`); do not touch `README.md` unless its current
wording is actually wrong; branch `fix/vec-chunks-startup-binding`; no
`--no-verify`; confirm no other `mutation_check.py` process is running
before gate 6 (it needs exclusive repo access).

## Acceptance

All seven gates green, verbatim and in order (`uv sync --locked`; `ruff
check .`; `pytest`; `bot.py --selftest`; `bot.py --selftest-live`;
`devtools/mutation_check.py`; `devtools/rag_eval.py`); the new regression
test (through `bot.main`, not a hand-built connection) fails on pre-fix
`HEAD` and passes after; the new mutation entry
`v195-init-schema-drops-the-pair` killed via `--only`; `docs/spec/` delta
recording REQ-V190-STO-04 as `bot.py`'s responsibility.

## Stop

The regression test is green on current `HEAD` before the fix (the bug's
read is wrong — do not paper over it); binding the pair at `run_selftest`'s
site turns out not to be a no-op (contradicts this brief's read of
`Config`'s defaults, needs a design decision, not a workaround).
