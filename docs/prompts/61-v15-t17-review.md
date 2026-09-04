# Prompt 61 — spec-v1.5 T17: code review, fix or waive

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** REQ-V15-REV-01 names the three review checks
  verbatim; the judgment calls were dispatching the `code-reviewer`
  subagent in a genuinely clean context, deciding fix-vs-waive for
  each of its five findings with a defensible reason, and verifying
  each fix empirically (a live `replay` run, a hand-applied mutation)
  rather than trusting the diff alone
- **Harness:** Claude Code
- **Stage:** T17
- **Owner of:** `devtools/checks.py` (`_replay_one_commit`),
  `tests/test_v15_standards.py` (`test_v15_scan_10_severity_membership`),
  `AGENTS.md` (Local quality gates paragraph), `docs/reports/report-v1.5.md`
  (Review section, RLM row, Deviations item 5),
  `docs/prompts/61-v15-t17-review.md` (new)
- **REQ ids:** REQ-V15-REV-01

## Goal

Review the full T0-T16 diff via the `code-reviewer` subagent in its own
clean context, then close every finding — fixed and re-verified, or
waived with a recorded reason — before T18.

## Constraints

- The reviewer runs in a clean context: no prior conversation, briefed
  only with the spec, the diff range and the three REQ-V15-REV-01
  checks; its verdict is not pre-judged by this session's own account
  of the work.
- A fix is not "done" on the diff looking plausible: each must be
  re-verified against real behaviour (a live command, a hand-applied
  mutation, a re-run gate), not just re-read.
- Waiving a finding requires a reason the report records, not silence.

## Acceptance

- `docs/reports/report-v1.5.md`'s Review (T17) section lists every
  finding with its fix-or-waive disposition and reasoning.
- `uv run --locked ruff check .`, the full `uv run --locked pytest`
  suite, `uv run --locked python bot.py --selftest`,
  `uv run --locked python bot.py --selftest-live` and
  `uv run --locked python devtools/mutation_check.py` all exit 0
  (72 mutations, 72 killed, 0 survived/errored/drifted).
- A live `checks.py replay --range HEAD~1..HEAD` against the real
  repository still reports `[PASS]` after the replay-argv fix.

## Stop

If a finding cannot be resolved within this task without exceeding
its own scope (e.g. it would require redesigning code the spec froze
elsewhere), waive it here with the reason and let a later spec version
pick it up — do not let one hard finding block closing the others.
