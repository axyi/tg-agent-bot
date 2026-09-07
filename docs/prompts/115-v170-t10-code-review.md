# Prompt 115 — spec-v1.7.0 T10: clean-context review, then every gate

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts; the review itself ran on the
  `code-reviewer` subagent in its own clean context (REQ-V170-REV-01)
- **Harness:** Claude Code
- **Stage:** T10
- **Owner of:** `tests/test_v170_reasoning.py` (split, four corrected
  assertions), `tests/test_v170_summary_budget.py` (new, split out),
  `tests/test_v170_bench.py` (new, split out),
  `docs/reports/report-v1.7.0.md` (T10 section),
  `docs/prompts/115-v170-t10-code-review.md` (new)
- **REQ ids:** REQ-V170-REV-01, REQ-V170-TREE-01, REQ-V170-POL-01,
  REQ-V170-POL-07

## Goal

Run the clean-context code review REQ-V170-REV-01 mandates over the whole
T0–T9 diff, address every finding, then run every gate: gates 1–4 and 6
verbatim, gate 5 re-run now that source changed, `checks.py run --profile
full --since <base>`, `checks.py replay --range <base>..<tip>`.

## Constraints

- The review runs in a genuinely clean subagent context (no access to this
  session's own reasoning) — `.claude/agents/code-reviewer.md`'s own
  procedure.
- Every finding is either fixed or explicitly waived with a reason in the
  report; none is silently dropped.
- Test fixes preserve each test's stated intent — REQ-V170-POL-01's "absent
  env -> a default exists" property and REQ-V170-POL-07's "that default
  matches what `.env.example` documents" property, never a hand-picked
  literal that happens to match today.
- The REQ-V170-TREE-01 file split changes no test's behaviour or count —
  1133 collected, 1131 passed, 2 skipped, unchanged before and after.
- One prompt -> one commit, referencing this file.

## Acceptance

- The reviewer's eight REQ-V170-REV-01 checklist items each explicitly
  pass/fail; every 🔴/🟡 finding closed.
- Full suite green: `uv run --locked pytest` (1133 collected, 2 skipped).
- `uv run --locked ruff check .` exits 0.
- `uv run --locked python bot.py --selftest` and `--selftest-live` both
  exit 0.
- `uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json`
  exits 0.
- `uv run --locked python devtools/mutation_check.py` exits 0 (92/92
  killed, confirmed twice more after the review fixes landed).
- `uv run --locked python devtools/checks.py run --profile full --since <base>`
  exits 0, every one of its 15 gates PASS.
- `uv run --locked python devtools/checks.py replay --range <base>..<tip>`
  exits 0, every commit PASS.

## Stop

None triggered. Two things surfaced and handled without a full stop:

1. **The GPU box's LM Studio floating IP moved again** (third time this
   run, same class as the two prior instances): re-probed the three known
   addresses, `192.168.0.145` answered, `LMSTUDIO_BASE_URL` re-pinned via
   the single permitted `sed -i` idiom, gate 5 reconfirmed green.
2. **A stale figure, found while investigating skylos's summary line**:
   `docs/spec/spec-v1.7.0.md`'s own REQ-V170-NG-12 clause restates "the 19
   skylos shadow findings in `dashboard_server.py` carried from v1.6.0" —
   a direct re-measurement today shows 8, not 19, and this predates the
   whole v1.7.0 run (an artefact saved during T4/T5's own pre-push hooks
   already shows 8). `dashboard_server.py` is confirmed byte-unchanged
   since `<base>`, so the discrepancy is not something this run caused;
   it is disclosed in the T10 report rather than silently repeated, and
   NG-12's disposition (informational, not refactored) is unaffected by
   the exact count either way.
