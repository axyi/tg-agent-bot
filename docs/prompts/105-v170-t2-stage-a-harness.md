# Prompt 105 — spec-v1.7.0 T2: stage-A scratch harness

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prompt 103/104 — engineering plumbing against a
  fully written-out spec
- **Harness:** Claude Code
- **Stage:** T2 — stage-A scratch harness (no commit of the patch itself)
- **Owner of:** `docs/reports/report-v1.7.0.md` (T2 section),
  `docs/prompts/105-v170-t2-stage-a-harness.md` (new)
- **REQ ids:** REQ-V170-RSN-01, REQ-V170-RSN-02, REQ-V170-RSN-05,
  REQ-V170-RSN-07 (T2)

## Goal

Design and dry-run (zero live calls) the stage-A pair-running procedure T3
will execute for real: the mechanism-selection patch shape for candidates
a/c/d (b already `unsupported` per T1's VERIFY 1; e informational-only,
outside the budget), the pair-file naming and restore-and-`git diff`
procedure, and REQ-V170-RSN-07's mixed-policy pair shape including its TTFT
sidecar capture, cold-calibration and warm-proof logic — even though T1's
finding (`stats: {}` on the OpenAI-compatible route) means no candidate is
expected to actually reach the mixed-policy pair this run.

## Constraints

- No source, test or config file is changed or committed by this task — the
  scratch patch is designed and dry-run only, never applied to the tracked
  tree here.
- Zero live inference calls in this task; every check runs against recorded
  or hand-built fixtures.
- The driver mechanics (patch-apply/revert sequencing) are designed to live
  outside the repository (`$CLAUDE_JOB_DIR/tmp/`) so an untracked file never
  appears in `git status --porcelain` between pairs at T3.
- One prompt -> one commit, referencing this file; the commit touches only
  this prompt and the report.

## Acceptance

- The procedure is written down in `docs/reports/report-v1.7.0.md`'s T2
  section: patch shapes for a/c/d, pair-file naming, the six-step
  restore-and-diff procedure, the RSN-07 mixed-pair shape.
- The sidecar capture function is exercised offline against a fixture
  matching this run's actual observed shape (`stats: {}`), an absent-`stats`
  fixture, and a populated fixture — `null` written for the first two, the
  real value for the third.
- The warm-proof and cache-preserved comparators are exercised against two
  recorded fixture pairs each (one passing the `0.35` threshold, one
  failing), and a full sidecar is built for both outcomes.
- The three payload/message-patch shapes (a, c, d) are built through the
  real `llm.base.build_payload` and asserted well-formed, with the caller's
  original `messages` list proved unmutated for c and d.
- The budget arithmetic (a/c/d only, <= 9 of 15 pairs; b and e outside it)
  is stated in the report before T3 spends anything.

## Stop

None expected — this task is offline design work with no live dependency.
A discovery that the dry-run assertions fail against the spec's own stated
formulas would stop here and be reported as a spec ambiguity rather than
silently reconciled.
