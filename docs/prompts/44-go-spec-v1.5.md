# Prompt 44 — go docs/spec/spec-v1.5.md (T0: preconditions)

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** assigned by spec-v1.5 §"Executor: claude-sonnet-5";
  engineering plumbing with every decision already made in the spec, no
  algorithm design or judgement call that would warrant a different model
- **Harness:** Claude Code
- **Stage:** T0 — preconditions
- **Owner of:** `docs/reports/report-v1.5.md` (new skeleton),
  `docs/prompts/44-go-spec-v1.5.md` (new)
- **REQ ids:** REQ-V15-PRE-01, REQ-V15-PRE-02, REQ-V15-ORD-01 (T0)

First prompt of the spec-v1.5 run, following the `go docs/spec/spec-v1.5.md`
standing instruction (`AGENTS.md` § go protocol): execute the spec
end-to-end per its own Execution contract (§1), starting with T0's
preconditions (§3, §17).

## Goal

Verify every precondition §3 lists — the six v1.4 gates green, `.env` keys
present by name, Docker reachable with both images at their expected
digests, git ≥ 2.9, network reachable for the three sanctioned steps — and
record the starting `HEAD` SHA as `<base>`, the lower bound of every
`--since` and `replay --range` for the rest of this run. Create the
`docs/reports/report-v1.5.md` skeleton, `## Operator inputs` section
included.

## Constraints

- No source, test or config file is changed in this task — T0 is
  verification plus one new report skeleton and this prompt file.
- No project or lab file outside this repository is read or written
  (REQ-V15-EC-01).
- Credential values are never printed, logged or quoted; `.env` presence is
  checked by key name only.
- The outgoing sandbox image (`python:3.13-slim`) is inspected by digest,
  never pulled or mutated; the incoming `python:3.14-slim` is not touched
  here (T15's job).
- One prompt → one commit, referencing this file.

## Acceptance

- `uv sync --locked`, `uv run --locked ruff check .`, `uv run --locked
  pytest`, `uv run --locked python bot.py --selftest`, `uv run --locked
  python bot.py --selftest-live`, `uv run --locked python
  devtools/mutation_check.py` all exit 0 — recorded in the report.
- `docker image inspect --format '{{json .RepoDigests}}' python:3.13-slim`
  shows `sha256:881d80734ee05dca6f7f42dcb080975652a53c7eda9ba1f03bb8da31aa6a6ec2`.
- `git --version` ≥ 2.9; `.env` carries the spec-v1.2 §3.3 keys by name.
- `docs/reports/report-v1.5.md` exists with an `## Operator inputs` section
  and records `<base>` = the pre-commit `HEAD` SHA.
- `git status --short` shows only `docs/` files touched; exactly one commit
  is created.

## Stop

If any of the six v1.4 gates is red, stop and emit the §7.2 blocker
template instead of fixing it silently here — an already-red gate is a
blocker for this run, not something T0 repairs. If LM Studio is
unreachable, the run is blocked (REQ-V14-GATE-01's exception stays
withdrawn) — do not proceed and do not weaken gate 5.
