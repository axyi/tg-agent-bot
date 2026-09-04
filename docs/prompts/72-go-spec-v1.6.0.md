# Prompt 72 — go docs/spec/spec-v1.6.0.md (T0: preconditions)

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** assigned by spec-v1.6.0 §"Executor: claude-sonnet-5";
  engineering plumbing with every schema, route, attribute name, bucket
  boundary, check kind and test id already written out in the spec, no
  algorithm design or judgement call that would warrant a different model
- **Harness:** Claude Code
- **Stage:** T0 — preconditions
- **Owner of:** `docs/reports/report-v1.6.0.md` (new skeleton),
  `docs/prompts/72-go-spec-v1.6.0.md` (new)
- **REQ ids:** REQ-V160-PRE-01, REQ-V160-PRE-02, REQ-V160-PRE-04, REQ-V160-ORD-01 (T0)

First prompt of the spec-v1.6.0 run, following the `go docs/spec/spec-v1.6.0.md`
standing instruction (`AGENTS.md` § go protocol): execute the spec end-to-end
per its own Execution contract (§1), starting with T0's preconditions (§3,
§17).

## Goal

Verify every precondition §3 lists — offline gates green (gates 1-4 and 6 of
§14 in their own right; the `full` profile's non-live members; gate 5 and the
`full` profile's live member explicitly deferred to T15 per REQ-V160-PRE-04),
hooks installed, `doctor` green, the test count re-measured at HEAD, Docker
reachable with the digest-pinned sandbox image present, port `8765` free,
`.env` keys present by name. Record the starting `HEAD` SHA as `<base>` and
the committed spec's `sha256`. Create the `docs/reports/report-v1.6.0.md`
skeleton, `## Operator inputs` section included, with the two values the `go`
request supplied verbatim (LM Studio version, loaded context length) — the
served model id is excluded here, populated only at T15 from a live
`/models` read.

The initial `go` request (`go docs/spec/spec-v1.6.0.md`) carried neither
operator value; per REQ-V160-PRE-04 that stops the executor at T0 with the
blocker template. The operator supplied both in the immediately following
turn: LM Studio version `Bionic v1.1.1` at `http://192.168.0.145:1234/v1`,
served model `qwen/qwen3.8-27b`, loaded context length `42496`; port: no
override (`8765` confirmed free at T0). T0 resumes from that answer.

## Constraints

- No source, test or config file is changed in this task — T0 is
  verification plus one new report skeleton and this prompt file.
- No project or lab file outside this repository is read or written
  (REQ-V160-EC-01).
- Credential values are never printed, logged or quoted; `.env` presence is
  checked by key name only (`grep -q '^KEY=' .env`).
- Gate 5 (`bot.py --selftest-live`) and the `full` profile's live member are
  **not** run at T0 — REQ-V160-PRE-04 reserves them for T15, after PRE-03
  resolves the address and this task's instrument identification completes.
  This holds even though the operator's answer already names a reachable
  address: the ordering rule is about *when*, not *whether it would pass*.
- One prompt → one commit, referencing this file.

## Acceptance

- `uv sync --locked`, `uv run --locked ruff check .`, `uv run --locked
  pytest`, `uv run --locked python bot.py --selftest`, `uv run --locked
  python devtools/mutation_check.py` all exit 0 — recorded in the report.
  Gate 5 is not run here.
- `uv run --locked python devtools/install_hooks.py --check` and
  `uv run --locked python devtools/checks.py doctor` both exit 0.
- `uv run --locked python devtools/checks.py lint-docs` exits 0.
- `gitleaks dir` over the git-tracked tree (not the raw working directory,
  which also carries `.env` and other git-ignored paths) reports 0 leaks.
- `docker version` exits 0; `python:3.14-slim@sha256:cad9a2c8…` is present
  locally by digest.
- `docs/reports/report-v1.6.0.md` exists with an `## Operator inputs` section
  and records `<base>` = the pre-commit `HEAD` SHA and the spec's `sha256`.
- `git status --short` shows only `docs/` files touched; exactly one commit
  is created.

## Stop

If any of gates 1-4 or 6 is red, stop and emit the §7.2 blocker template
instead of fixing it silently here — an already-red gate is a blocker for
this run, not something T0 repairs. If the operator's `go` request (or its
immediate follow-up) is missing the LM Studio version or a positive-integer
loaded context length, stop at T0 with the blocker template — no T1.
