# Prompt 86 — spec-v1.6.0 T12: version bump and documentation catch-up

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §14.1 marks T12 "delegate: yes" -- the reading
  spans four large documentation files (README.md 706 lines, AGENTS.md 192
  lines, docs/plan.md 260 lines, plus pyproject.toml), past this run's RLM
  delegation threshold
- **Harness:** Claude Code
- **Stage:** T12
- **Owner of:** `pyproject.toml` (the `project.version` line only),
  `README.md`, `AGENTS.md`, `docs/plan.md`, this prompt file; plus, forced
  by the version bump itself and applied by this same run after discovering
  it during gate verification (see Stop), one line of `uv.lock` (the
  `tg-agent-bot` package's own recorded `version`, regenerated with `uv
  lock` -- no dependency changed)
- **REQ ids:** REQ-V160-VER-01, -02, -05, -06, REQ-V160-RPT-04

## Goal

Move `pyproject.toml`'s `project.version` from the placeholder `"0.1.0"` to
`"1.6.0"` -- the single source of truth `bot.py --version` (already
implemented in T7) reads at call time -- and bring the project's
documentation up to date with everything T0-T11 shipped: a new `##
Versioning` section in `README.md` (the SemVer policy table, the historic
label -> SemVer map, the `--version`/tag-convention note), a new `##
Dashboard` section describing the live read-only HTTP dashboard, four new
environment-variable rows (`OBS_CAPTURE_CONTENT`, `DASHBOARD_ENABLED`,
`DASHBOARD_PORT`, `LLM_SUMMARY_MAX_TOKENS`), `--version`/`--no-dashboard`
mentioned where CLI usage is documented and `/status`'s new eighth line
noted; `AGENTS.md`'s project-layout list gaining `tracing.py`,
`dashboard_render.py`, `dashboard_server.py`, and its gate section gaining
the re-measured `pytest` count; and `docs/plan.md` gaining an in-progress
`## Status` row and a `## v1.6.0 (in progress)` narrative section for the
still-unfinished release.

## Constraints

- Own exactly `pyproject.toml` (version line only), `README.md`,
  `AGENTS.md`, `docs/plan.md`, and this prompt file. Do not touch `bot.py`,
  `config.py`, any Python source or test file, or
  `config/quality_gates.yaml` -- the CLI grammar, dashboard lifecycle and
  `/status` line are already implemented (T7) and out of scope here.
- No git tag (REQ-V160-VER-04 is T18's job, months from now in this run).
- No live LLM call, no `bot.py --selftest-live` -- pure documentation task.
- Do not add or imply a `mutation-v160` gate anywhere in `AGENTS.md` -- it
  does not exist in `config/quality_gates.yaml` yet (T13's job). This is not
  a spec/brief conflict: REQ-V160-VER-06 itself closes with "each in the
  same commit as the change it describes, per the spec-sync rule," so the
  gate's `AGENTS.md` mention belongs in T13's own commit, the one that
  actually adds the gate -- describing it here, before it exists, would be
  the spec-drift the spec-sync rule itself forbids, not a use of it.
- Do not touch the existing "72 entries as of spec-v1.5" sentence in
  `AGENTS.md`'s "Local quality gates" section -- that is the *mutation*
  registry count, a later task's number, not this task's *pytest* count.
- Do not commit; leave the tree unstaged for the orchestrator. No new
  dependencies.

## Acceptance

- `uv run --locked python devtools/checks.py lint-docs` -- clean.
- `uv run --locked pytest -k "version" -q` -- passes (T7's existing
  `--version` tests, unaffected by a docs-only change).
- `uv run --locked python bot.py --version` prints exactly
  `tg-agent-bot 1.6.0`.
- `uv run --locked ruff check .` and `uv run --locked pytest` stay exactly
  as green as before this change (1004 passed, 0 failed -- no new tests,
  since this task adds none).

## Stop

`uv sync --locked` (gate 1, run before anything else) failed immediately
after the `pyproject.toml` edit: `uv.lock` records the local
(`source = { virtual = "." }`) `tg-agent-bot` package's own version
(`0.1.0` at the time), which the version bump left out of sync, so
`--locked` refused to proceed. This is a mechanical consequence of
REQ-V160-VER-01 itself, not a new file ownership decision -- `uv lock`
regenerated exactly one line (`version = "0.1.0"` -> `version = "1.6.0"`
inside the `tg-agent-bot` package block; `git diff --stat uv.lock` shows
`1 file changed, 1 insertion(+), 1 deletion(-)`, no dependency touched).
Flagged here explicitly since `uv.lock` is not among this task's named
owned files.

Two places named in the task brief for verification, both resolved by
reading rather than assuming: (1) `AGENTS.md` does **not** enumerate
individual environment variables anywhere -- it only references
`.env`/`.env.example` in passing (the "Secrets" section) -- so the "four
new environment variables" bullet for `AGENTS.md` does not apply; the
four rows went into `README.md`'s `## Configure` table only (renamed from
"Output windows, history and pricing" to "Output windows, history,
pricing and observability" to stay accurate once `OBS_CAPTURE_CONTENT`/
`DASHBOARD_ENABLED`/`DASHBOARD_PORT` joined it -- the same table shape,
`| Variable | Default | Effect |`, was kept). (2) `OBS_CAPTURE_CONTENT`'s
README row was written to *not* claim it affects the dashboard's served
content: `dashboard_render.py`'s `served_span()` strips every
`CONTENT_ATTRIBUTE_KEYS` entry unconditionally (confirmed by reading the
module), so the flag only changes what is written to the `spans` table,
never what any dashboard route can serve -- an earlier draft of that row
implied otherwise and was corrected before writing the file.

Section placement, both a judgement call rather than a fact to verify:
`## Dashboard` was placed immediately after `## Observability` (both
describe the same underlying instrumentation, one via `/stats`, one via
a browser) and before `## Switch provider`. `## Versioning` was placed
after `## Error behaviour` and before `## Token economy`, per the task
brief's own hint to look near `## Safety`/`## Limits`/`## Error
behaviour` -- it closes out the operational-meta cluster before the
file's benchmark/testing sections begin.

`docs/reports/report-v1.6.0.md` (T0's provisional skeleton) was read only
to confirm the 843-tests-at-T0 figure cited in `docs/plan.md`'s new
sections; it was not edited -- it is not in this task's owned-file list
and any staleness in it belongs to T17, not here.
