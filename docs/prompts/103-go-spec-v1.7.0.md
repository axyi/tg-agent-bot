# Prompt 103 — go docs/spec/spec-v1.7.0.md (T0: preconditions)

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** assigned by spec-v1.7.0 §"Executor: claude-sonnet-5";
  engineering plumbing with every env var, enum value, column name, function
  signature, candidate payload shape, gate formula and test id already
  written out in the spec, no algorithm design or judgement call that would
  warrant a different model
- **Harness:** Claude Code
- **Stage:** T0 — preconditions
- **Owner of:** `docs/reports/report-v1.7.0.md` (new skeleton),
  `docs/prompts/103-go-spec-v1.7.0.md` (new)
- **REQ ids:** REQ-V170-PRE-01, REQ-V170-PRE-02, REQ-V170-ORD-01 (T0)

## Goal

Verify every offline precondition §3 lists: gates 1-4 and 6 of §13 green in
their own right; hooks installed; `doctor` green; the test count re-measured
at HEAD; Docker reachable with the digest-pinned sandbox image present;
`.env` keys present by name only; neither `LLM_REASONING_POLICY` nor
`LLM_REASONING_ON_PURPOSES` present in `.env` (REQ-V170-PRE-01 item 9); the
baseline self-consistent (`bench.py check`); tags `v1.3`, `v1.3-baseline`,
`v1.6.0` present and unmoved. Record the starting `HEAD` SHA as `<base>` and
the committed spec's `sha256`. Create the `docs/reports/report-v1.7.0.md`
skeleton, `## Operator inputs` section included, and its "Ledger row (paste
into `economics.md`)" section already carrying a structurally complete
fenced row.

The initial `go` request (`go docs/spec/spec-v1.7.0.md`) carried none of
REQ-V170-PRE-02's three operator values (LM Studio version, loaded context
length, current address); per REQ-V170-PRE-02 that stops the executor at T0
with the blocker template. The operator supplied the first two via a
clarifying question in the same session, confirming the values match the
`baseline-v1.6.0` instrument: LM Studio version `Bionic v1.1.1`, loaded
context length `42496`; on the address, the operator did not name a distinct
one ("one of the three known, or don't know"), so PRE-03's fixed three-address
probe runs unmodified with no fourth candidate appended. T0 resumes from that
answer.

## Constraints

- No source, test or config file is changed in this task beyond the new
  report skeleton and this prompt file.
- No project or lab file outside this repository is read or written
  (REQ-V170-EC-01).
- Credential values are never printed, logged or quoted; `.env` presence is
  checked by key name only (`grep -q '^KEY=' .env`); the two policy keys'
  absence is proved by the same idiom returning non-zero.
- Gate 5 (`bot.py --selftest-live`) and the `full` profile's live member are
  reserved for T1 by REQ-V170-GATE-01 ("never at T0"). The CLI has no
  per-gate exclusion flag; running `checks.py run --profile full` as one
  invocation pulled `selftest-live` in at T0 as a side effect. It sends no
  inference (AGENTS.md: "spends no inference tokens"), so PRE-04 item 7's
  "first inference of the run" is not affected, but the deviation from the
  written order is recorded rather than silently absorbed.
- One prompt -> one commit, referencing this file.

## Acceptance

- `uv run --locked ruff check .`, `uv run --locked pytest`, `uv run --locked
  python bot.py --selftest`, `uv run --locked python devtools/mutation_check.py`
  all exit 0 - recorded in the report.
- `uv run --locked python devtools/install_hooks.py --check` and
  `uv run --locked python devtools/checks.py doctor` both exit 0.
- `uv run --locked python devtools/checks.py run --profile full --since <base>`
  exits 0 (live member included as the recorded deviation above).
- `docker version` exits 0; `python:3.14-slim@sha256:cad9a2c8...` is present
  locally by digest.
- `uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json`
  exits 0.
- `grep -q '^LLM_REASONING_POLICY=' .env` and
  `grep -q '^LLM_REASONING_ON_PURPOSES=' .env` both exit non-zero.
- `docs/reports/report-v1.7.0.md` exists with an `## Operator inputs` section
  and records `<base>` = the pre-commit `HEAD` SHA and the spec's `sha256`.
- `git status --short` shows only `docs/` files touched; exactly one commit
  is created.

## Stop

If any of gates 1-4 or 6 is red, stop and emit the v0 §7.2 blocker template
instead of fixing it silently here - an already-red gate is a blocker for
this run, not something T0 repairs. If the operator's `go` request (or its
immediate follow-up) is missing the LM Studio version or a positive-integer
loaded context length, stop at T0 with the blocker template - no T1.
