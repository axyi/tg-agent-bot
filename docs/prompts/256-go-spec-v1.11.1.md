# Prompt 256 — v1.11.1 T0: preconditions, gates 1–5, measurements, pin inventory

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only orchestration task (T0's own §10.1
  exemptions: *commands only* for the precondition checks, the gates and
  the measurements; *artefacts only* for the prompt file and the report
  skeleton); the pin-inventory construction and `tests/test_v1111_pin.py`
  are delegated to one subagent per EC-03/EC-04, not reached this prompt
  (blocked before dispatch — see Stop).
- **Harness:** Claude Code (background session)
- **Stage:** T0
- **Owner of:** `docs/prompts/256-go-spec-v1.11.1.md`,
  `docs/reports/report-v1.11.1.md` (skeleton), `.env` (one line,
  `LMSTUDIO_BASE_URL` only), `docs/llm-usage.md` (row 167)
- **REQ ids:** REQ-V1111-EC-01, REQ-V1111-EC-02, REQ-V1111-EC-03,
  REQ-V1111-EC-04, REQ-V1111-PIN-01

## Goal

Run `spec-v1.11.1.md`'s T0: verify the EC-04 structural precondition (tree
ancestry from `v1.11.0`, the sorted four-path docs-only drift, clean
porcelain), the `go` text's LM Studio address written into
`LMSTUDIO_BASE_URL` by one `sed -i`, and the `bot_state` override count;
then run gates 1–5 on the otherwise-unchanged tree, re-measure the
test-collection floor and `len(MUTATIONS)`, write the baseline node-id
list, delegate and land the frozen-pin inventory (PIN-01) plus
`tests/test_v1111_pin.py`, and write the report skeleton.

## Constraints

Commands only for the preconditions/gates/measurements; artefacts only for
this prompt file and the report skeleton — no source, test or config file
written this task. `.env` is never opened/printed beyond `test -f` and the
one `sed -i` line, whose value is never echoed; `data/`'s only read is the
one permitted `bot_state` override-count query, its integer result the
only thing recorded. Only the pin-inventory construction (when reached) is
delegated, one subagent, brief `v1111-T0.md`, writing to the distinct
artefact `v1111-T0-pin-inventory.md`. `--no-verify` never used.

## Acceptance

Every EC-04 precondition holds; the LM Studio address is reachable and its
pinned model is in the catalogue; the `bot_state` override count reads
`0`; gates 1–5 exit 0; the collected count is the floor (≥ 2384); the
delegated subagent lands `docs/spec/task-briefs/v1111-T0-pin-inventory.md`
and `tests/test_v1111_pin.py`, both green; `git diff --exit-code` clean
after the commit (only the artefacts listed above plus `.env`'s one line
touched).

## Stop

Any structural precondition failing is a precondition mismatch: stop
before T0, no repair cycle (ERR-01 row 14). An unreachable LM Studio, or a
non-zero `bot_state` override count, at this stage is a **blocked run**
(ERR-01 row 6) — not a stop route: no task proceeds past the check that
tripped it; only this prompt file and the report skeleton (with the block
recorded) are committed; the operator resolves the cause and re-issues
`go`.
