# Prompt 127 — go spec-v1.8.0 (T0: preconditions)

- **Date:** 2026-09-09
- **Executor model:** claude-sonnet-5
- **Model reason:** `docs/handoff-v1.8.0.md` §Models: sonnet-5 executed v1.5,
  v1.6.0 and v1.7.0 end to end in this repository; v1.8.0 is smaller in scope
  and makes no live model call.
- **Harness:** Claude Code
- **Stage:** T0
- **Owner of:** `docs/prompts/127-go-spec-v1.8.0.md`, `docs/spec/task-briefs/`
  (created), `docs/reports/report-v1.8.0.md` (skeleton)
- **REQ ids:** REQ-V180-EC-01…-08, REQ-V180-EC-11 (T0 row)

## Goal

Execute `go docs/spec/spec-v1.8.0.md`'s T0: confirm the six gates are green
on the unchanged tree (including gate 5, live), confirm `doctor` and
`install_hooks.py --check` are green, re-measure the collected test count
against the 1133 floor, record `<base>` and the spec's `sha256`, create
`docs/spec/task-briefs/` and this prompt file, and land the
`report-v1.8.0.md` skeleton with `## Operator inputs` copied verbatim from
the `go` request.

## Constraints

No source or test file is touched in this task (T0 is *artefacts only*,
REQ-V180-EC-07 item 3). No `.env` value is printed or committed; the
LM Studio address fix for gate 5 (re-pinning `LMSTUDIO_BASE_URL` to the
reachable known IP, `192.168.0.145:1234`, after the other two known IPs
timed out) is a working-tree `.env` edit only, per the personal-org role's
documented recipe (point-edit one line, never `cat` the file) — `.env` is
git-ignored and is never staged or committed. Everything under §1 of the
spec applies: exhaustive dependency list, no schema migration, secrets
discipline (EC-04).

## Acceptance

- `uv sync --locked`, `uv run --locked ruff check .`, `uv run --locked
  pytest`, `uv run --locked python bot.py --selftest`, `uv run --locked
  python bot.py --selftest-live`, `uv run --locked python
  devtools/mutation_check.py` all exit 0.
- `uv run --locked python devtools/checks.py doctor` exits 0.
- `uv run --locked python devtools/install_hooks.py --check` exits 0.
- `pytest --collect-only -q` total equals or exceeds 1133; the measured
  number is recorded as the floor for this run.
- `<base>` (`git rev-parse HEAD` before this run's first commit) and
  `sha256sum docs/spec/spec-v1.8.0.md` are recorded.
- `docs/spec/task-briefs/` exists; this prompt file exists.
- `docs/reports/report-v1.8.0.md` exists with the required skeleton fields
  and a verbatim `## Operator inputs` section.

## Stop

An unreachable LM Studio blocks here (gate 5 acceptance) — resolved this run
by re-probing the known GPU-box IPs and re-pinning `.env` to the one that
answered. Any other red gate at T0 is a **STOP**: the tree is unchanged, so
no repair cycle applies — the run does not proceed to T1 until every T0 gate
is green.
