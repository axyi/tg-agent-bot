# Prompt 165 — v1.9.2 T1 §B: whole-tree ruff format, REQ-V15-NG-04 closed

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a fully specified mechanical patch against an existing
  contract (`docs/spec/task-briefs/v192-T1.md` §B) plus two explicit
  operator rulings on the two items the first pass stopped on — no
  open-ended design decision, just careful byte-for-byte re-derivation and
  a gate-config change in the runner's own already-supported shape.
- **Harness:** Claude Code
- **Stage:** v1.9.2 T1 §B (patch, no new spec file — precedent v1.5.1, v1.9.1)
- **Owner of:** every `*.py` file the whole-tree `ruff format` touches
  (63 files), `devtools/mutation_check.py` (9 re-derived entries),
  `tests/test_v11_patch.py` (one lambda→def fix the reformat forced),
  `tests/test_v15_standards.py` (`_GATE_MATRIX_LABEL_TO_NAME`),
  `pyproject.toml`, `config/quality_gates.yaml`,
  `docs/spec/spec-v1.9.0-delta-1.md` (gate matrix row split),
  `docs/reports/report-v1.9.2.md`, `docs/llm-usage.md`
- **REQ ids:** REQ-V15-NG-04 (closed), REQ-V13-BEN-12 (the named exception)

## Goal

Close REQ-V15-NG-04: run `ruff format .` over the whole tree, re-derive
every mutation `find` string the reformat breaks, make `ruff format --check`
blocking whole-tree the way `ruff check` already is (`ruff-check`/
`ruff-check-all`), and leave both bare `ruff check .` and
`ruff format --check .` exiting 0.

The first pass stopped mid-task on two items neither the brief's own
inventory nor its own decision procedures resolved:

1. Reformatting `devtools/bench_scenarios.py` changes its bytes, and
   `devtools/bench.py:335-340`'s `scenarios_sha256()` hashes those bytes by
   explicit design (REQ-V13-BEN-12) — pinned inside 15 committed
   `docs/assets/bench/*.json` benchmark artefacts, 3 of them actively
   asserted against by `tests/test_v170_bench.py`. The operator ruled:
   frozen benchmark artefacts are measurement records, never edited to
   match new bytes (option b) — revert the reformat of that one file, add
   a `[tool.ruff.format] exclude` entry for it, named and dated in the
   comment.
2. `storage.py`'s `_MIGRATION_2_TO_3` (skylos finding §A #8) could not
   carry an inline suppression comment (the flagged line opens a
   triple-quoted SQL string) and was left "kept, unsuppressed" in the first
   pass. The operator ruled: the whole-tree cleanup order supersedes the
   constant's own bookkeeping note ("stays only because deleting it is an
   unlisted edit the amendment table doesn't call for") — delete it under
   §A.3, with (a)(b)(c) evidence. Commit 1 (`f421621`) was amended (now
   `6c9a904`) to carry this so it holds all of §A's work, not just most.

## Constraints

- `docs/` stays out of the reformat's scope (spec-v1.5's own reason: ruff
  reformats fenced code blocks in `docs/*.md`, and a tree-wide reformat
  there was never asked for) — the 11 `docs/*.md` files `ruff format .`
  touched were reverted, and `docs/**` is now excluded in
  `[tool.ruff.format]` so the bare `ruff format --check .` acceptance
  command honours that without runner-side filtering. This formalises
  spec-v1.5's already-decided policy; it is not a new exception.
- `devtools/bench_scenarios.py` is the one *new* named exception this
  prompt adds, for REQ-V13-BEN-12 (see Goal, item 1) — reverted to its
  pre-reformat bytes and excluded from `[tool.ruff.format]`, dated and
  reasoned in the pyproject.toml comment. `ruff check` still lints it.
- Every re-derived `find` string keeps the exact same mutation semantics
  (same statement, same mutation) — only the byte layout changed. Gate 6
  `drifted` stays 0 (throwaway drift script, not the full mutation gate,
  run before and after this prompt's own changes).
- Version-pin and count-bearing tests are repointed, never deleted
  (REQ-V190-EC-03): `tests/test_v15_standards.py`'s
  `_GATE_MATRIX_LABEL_TO_NAME` gained a second label/gate-name pair
  (`ruff-format-all`) alongside the existing one, matching the
  `ruff-check`/`ruff-check-all` precedent already in that same dict.
- The new `ruff-format-all` gate needed no runner code change: it is the
  generic `execute_command_gate` path with no `blocking_paths` key, the
  same shape `ruff-check-all` already uses next to diff-scoped
  `ruff-check` — confirmed against `devtools/checks.py:1174-1215`.
- `.env` is never read, printed or committed; `data/`, `evals/rag/corpus`
  are never opened.
- The nine `--only` mutation reruns are the only thing touching the tree
  while they run, sequentially, nothing concurrent (they mutate files in
  place, restoring afterward).
- No `--no-verify`. Do not push.

## Acceptance

```
uv run --locked ruff check .                         # exit 0
uv run --locked ruff format --check .                # exit 0 (92 files already formatted)
uv run --locked pytest                               # exit 0, report collected count and wall clock
<throwaway drift script>                             # 108/108, before and after
uv run --locked python devtools/mutation_check.py --only <id>   # x9, all killed
```

## Stop

- `ruff format` changes anything under `docs/` beyond what this prompt's
  own exclude already accounts for, or changes any test outcome beyond the
  two items this prompt's own operator rulings resolved;
- a re-derived `find` string cannot preserve identical mutation semantics;
- any gate in the acceptance list is red after a repair budget of two
  attempts.

Neither triggered after the two rulings landed.
