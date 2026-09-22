# Prompt 236 — v1.11.0 T0: preconditions, gates 1–5, measurements, pin inventory

- **Date:** 2026-09-22
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only orchestration task (T0's own §14.1
  exemptions: *commands only* for the precondition checks and the
  measurements, *artefacts only* for the prompt file and the report
  skeleton); the pin-inventory construction is delegated to one
  general-purpose subagent per EC-04.
- **Harness:** Claude Code (background session)
- **Stage:** T0
- **Owner of:** `docs/prompts/236-go-spec-v1.11.0.md`,
  `docs/reports/report-v1.11.0.md` (skeleton),
  `docs/spec/task-briefs/v1110-T0.md`,
  `docs/spec/task-briefs/v1110-T0-pin-inventory.md`,
  `docs/spec/task-briefs/v1110-T0-nodeids.txt`, `.env` (one line,
  `LMSTUDIO_BASE_URL` only), `docs/llm-usage.md` (row 147)
- **REQ ids:** REQ-V1110-EC-01, REQ-V1110-EC-03, REQ-V1110-EC-04,
  REQ-V1110-EC-05, REQ-V1110-EC-06, REQ-V1110-EC-07, REQ-V1110-PIN-01

## Goal

Run `spec-v1.11.0.md`'s T0: verify the EC-05 preconditions (tree state,
`.env` presence by exit status, the `go` text's LM Studio address written
into `LMSTUDIO_BASE_URL` by one `sed -i`, the `bot_state` override count),
run gates 1–5 on the otherwise-unchanged tree, re-measure the test-collection
floor and `len(MUTATIONS)`, write the baseline node-id list, delegate and
land the frozen-pin inventory (PIN-01), and write the report skeleton.

## Constraints

Commands only for the preconditions/gates/measurements; artefacts only for
this prompt file and the report skeleton — no source, test or config file
written this task. `.env` is never opened/printed beyond `test -f` and the
one `sed -i` line, whose value is never echoed. Only the pin-inventory
construction is delegated (one subagent, brief `v1110-T0.md`, writing to the
distinct artefact `v1110-T0-pin-inventory.md`). `--no-verify` never used.

## Acceptance

Every EC-05 precondition holds (tree ancestry confirmed with only docs-only
drift since `295b01f`, `.env` present, LM Studio reachable and its address
written, override count `0`). Gates 1–5 exit 0 (`pytest` 2311/2311, `bot.py
--selftest` OK, `bot.py --selftest-live` all-green with the disclosed
`lmstudio SKIP`). Collected count = 2311 (the floor); `len(MUTATIONS) ==
144`; the v190 `find` string occurs exactly once in `bot.py`. The delegated
subagent lands `docs/spec/task-briefs/v1110-T0-pin-inventory.md` with a
complete pin table and rename mapping, no drift beyond 5 lines left
unresolved. `git diff --exit-code` clean after the commit (only the
artefacts listed above plus `.env`'s one line staged).

## Stop

Any precondition failing, or any gate 1–5 line other than the disclosed
`lmstudio SKIP` going red, is a T0 blocker: the run stops, no task
proceeds, no stop route needed (nothing has been built yet) — the operator
fixes the address or environment and re-issues `go`.
