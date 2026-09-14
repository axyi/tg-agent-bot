# Prompt 201 — v1.10.0 T9: every gate, gate 8 last and once; stop route

- **Date:** 2026-09-14
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only orchestration task (T9's own EC-04
  exemption); no delegation.
- **Harness:** Claude Code (background session)
- **Stage:** T9
- **Owner of:** `docs/reports/report-v1.10.0.md` (finalised),
  `docs/reports/tg-post-v1.10.0.md`, `docs/llm-usage.md` (rows 102–111)
- **REQ ids:** REQ-V1100-GATE-01, REQ-V1100-REV-02, REQ-V1100-REV-04

## Goal

Run gates 1–7 verbatim, `doctor`, `lint-docs`, then gate 8 exactly once
against a recorded `tested_tree`, as T9's last live action. Note: one
repair cycle was needed before `tested_tree` was taken (gate 6 found a
survivor, `v11-send-redacts`, fixed in commit `7529e8a` which — by a minor
procedural slip — still cites prompt 192 rather than this one; disclosed
here since this prompt file is the accurate record of the task it belongs
to).

## Constraints

Commands only — no source/test/config file changes in this task beyond
the disclosed repair-cycle fix. `--no-verify` never used.

## Acceptance

Gate 8's result (`uv run --locked python devtools/agent_eval.py`) is
recorded verbatim in `docs/reports/report-v1.10.0.md`, whatever it is. A
red gate 8 on model behaviour (Stage B′) is not fixed, not rerun, not
argued with — the run finalises and stops per `REQ-V1100-REV-04`.

## Stop

Gate 8 exited 1 (`injection` 2/5 below floor 5, `hallucination` 2/4 below
floor 3) after a clean offline suite already proved the checkers, judge
parser and exit contract correct — Stage B′. No version bump, no tag, no
further task of §16 runs. The full result is in
`docs/reports/report-v1.10.0.md`'s T9 section.
