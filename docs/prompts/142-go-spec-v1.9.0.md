# Prompt 142 — go spec-v1.9.0 (T0: preconditions and preflight)

- **Date:** 2026-09-10
- **Executor model:** claude-sonnet-5
- **Model reason:** `docs/handoff-v1.9.0.md` §Models and effort: sonnet-5
  executed v1.5, v1.6.0, v1.7.0 and v1.8.0 end to end in this repository;
  every design decision of v1.9.0 is frozen in the spec, so the novelty is
  in the run, not in the reasoning.
- **Harness:** Claude Code
- **Stage:** T0
- **Owner of:** `docs/prompts/142-go-spec-v1.9.0.md`,
  `docs/reports/report-v1.9.0.md` (skeleton),
  `docs/assets/bench/v190-baseline.json`
- **REQ ids:** REQ-V190-EC-01…-08, REQ-V190-EC-11 (T0 row), REQ-V190-EC-13
  (record only)

## Goal

Execute `go docs/spec/spec-v1.9.0.md`'s T0: resolve the operator's
`EMBEDDING_MODEL`/`EMBEDDING_DIM` pair (the `go` request carried the
handoff's unfilled template, not values — resolved by probing the three
known GPU-box addresses live and confirmed with the operator via
`AskUserQuestion`), confirm the six gates are green on the unchanged tree
(gate 7 *n/a*), confirm `doctor` and `install_hooks.py --check` are green,
re-measure the collected test count against the 1220 floor, record `<base>`
and the spec's `sha256`, run REV-04 Stage 0's three preflight checks
(the sqlite-vec seven-step reversible sequence, the embedding model listing,
the embedding dimension probe), run the `v190-baseline` benchmark only after
the reversible sequence's `git diff --exit-code` passed, and land this
prompt file plus the `report-v1.9.0.md` skeleton with `## Operator inputs`
copied verbatim.

## Constraints

No source or test file is touched in this task (T0 is *artefacts only*,
REQ-V190-EC-07 item 3 exemption). No `.env` value is printed or committed;
only presence-by-key-name checks and the already-correct
`LMSTUDIO_BASE_URL` value were used. The `pyproject.toml`/`uv.lock` pin-lock
step of REV-04 Stage 0 is reversible by construction: both files are backed
up into a `tempfile.mkdtemp()` directory before the pins land, restored
after the sqlite-vec check, and `git diff --exit-code` proves the tree is
byte-identical before the baseline benchmark runs. The backup directory is
removed before this task ends. Everything under §1 of the spec applies:
the five-pin exhaustive dependency list, the one authorised migration
(deferred to T1), secrets discipline (EC-04).

## Acceptance

- `uv sync --locked`, `uv run --locked ruff check .`, `uv run --locked
  pytest`, `uv run --locked python bot.py --selftest`, `uv run --locked
  python bot.py --selftest-live`, `uv run --locked python
  devtools/mutation_check.py` all exit 0 on the unchanged tree.
- `uv run --locked python devtools/checks.py doctor` exits 0.
- `uv run --locked python devtools/install_hooks.py --check` exits 0.
- `pytest --collect-only -q` totals 1220, matching the stated floor exactly
  — no drift.
- REV-04 Stage 0's three checks all pass: `vec_version()` returns `v0.1.9`
  through `storage.connect` with the extension loaded exactly as the
  preflight command specifies; `GET http://192.168.0.145:1234/v1/models`
  lists `text-embedding-nomic-embed-text-v1.5`; `POST …/embeddings` with
  `["preflight"]` returns exactly one vector of 768 floats.
- `git diff --exit-code` passes after steps 5–7 of the reversible sequence,
  before the baseline benchmark starts.
- `devtools/bench.py run --tag v190-baseline --repeats 3` exits 0 and writes
  `docs/assets/bench/v190-baseline.json`.
- `<base>` (`git rev-parse HEAD` before this run's first commit) and
  `sha256sum docs/spec/spec-v1.9.0.md` (and the delta file) are recorded.
- `docs/reports/report-v1.9.0.md` exists with the required skeleton fields
  and a verbatim `## Operator inputs` section.

## Stop

An unreachable GPU box, an absent embedding model, a dimension mismatch, or
a failed sqlite-vec load are each a REV-04 Stage 0 blocker — this run hit
none of them (the box answered at `192.168.0.145`, unchanged from v1.8.0's
last known-good pin). Any other red gate at T0 is a **STOP**: the tree is
unchanged, so no repair cycle applies.
