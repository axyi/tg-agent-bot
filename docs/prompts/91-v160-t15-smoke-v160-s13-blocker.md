# Prompt 91 — spec-v1.6.0 T15: `smoke-v160`, S13 deterministic blocker, S15 reliability finding

- **Date:** 2026-09-06
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** direct continuation of the T15 orchestrator session
  (prompts 89, 90); the diagnostic sequence, the operator's own
  in-conversation decisions, and the corrected/retracted claims all depend
  on that accumulated context.
- **Harness:** Claude Code
- **Stage:** T15
- **Owner of:** `.env` (`LLM_MAX_TOKENS`, `LLM_TIMEOUT_S` lines only, via
  append since neither key existed before), `docs/reports/report-v1.6.0.md`,
  this prompt file. **Not** `devtools/bench_scenarios.py` — S13's
  `tool_calls_max(4)` is deliberately left untouched, see Stop.
- **REQ ids:** REQ-V160-BEN-07, REQ-V160-TQ-05, REQ-V160-TQ-06

## Goal

Execute REQ-V160-BEN-07's `smoke-v160` precondition (one run of all six new
scenarios, none skipped) as the last step of T15, following the resolved
preflight (prompt 90). Diagnose and resolve whatever the run surfaces, or —
if a finding is not resolvable within this task's own authority — record it
precisely enough for the operator to decide, rather than resolving it by
assumption.

## Constraints

- No change to any scenario's check thresholds (`tool_calls_max` values
  included) without the operator's own, explicit authorisation — this
  session does not have standing to decide a tool-quality ceiling from
  T10 is miscalibrated just because a live run failed it once
  (`QUALITY_GATE_SLACK` precedent, T10).
- Never run two `bench.py run` invocations without copying out the
  artefact from the first — `bench.py` wipes `.bench/` (its shared output
  root) at the start of every run. This was violated once, mid-task
  (see Stop); every artefact after that point was copied out of `.bench/`
  immediately.
- Any claim reported to the operator that later turns out incomplete or
  wrong must be corrected in the same report, not quietly left standing —
  this was needed once (S15's "1/1 at 4096 tokens" claim).
- A production `.env` change (not just a benchmark-only override) requires
  the operator's own explicit authorisation, stated for what it actually
  is: a change to the real bot's behaviour, not only to how the benchmark
  measures it.

## Acceptance

- A clear, evidence-backed disposition on whether T16 can start — this
  task does not manufacture a green result to reach T16; it reports what
  is actually true.
- Every diagnostic figure quoted in the report is either read directly
  from a surviving JSON file or was captured into this conversation before
  the file that would have backed it was destroyed (disclosed explicitly
  where that applies).
- `uv run --locked python devtools/checks.py lint-docs` — PASS.

## Stop

**T16 does not start.** Two independent findings, neither resolved by this
task on its own authority:

1. **S13 — deterministic.** `--repeats 3` at the shipped `LLM_MAX_TOKENS`
   (2048, unaffected by the S15 question below): 5/5/5 tool calls (ceiling
   4), correct final answer every time. `advisor()` consulted explicitly on
   whether to raise `tool_calls_max(4)`→`5`; guidance was **not to** — this
   is the check working as designed (REQ-V160-TQ-06), not a miscalibration,
   and this session does not have the standing to decide otherwise. T16
   requires 3/3 on every one of S13–S18 (R2-5); S13 cannot reach that with
   this model at this ceiling. Reported to the operator as their decision:
   accept the STOP, or explicitly authorise a scoped correction.

2. **S15 — probabilistic, and a retracted claim.** At the shipped
   `LLM_MAX_TOKENS=2048`, S15 reliably fails (`FALLBACK_EMPTY`, both LLM
   calls burning their entire budget on hidden reasoning). Raising to 4096
   was reported to the operator as "fixes it, 1/1" after one successful
   diagnostic run — **this was premature.** A second official 6-scenario
   attempt at the same setting timed out entirely (>1800s, a separate
   per-scenario ceiling this task discovered mid-diagnosis,
   `bench.py`'s own `--timeout-s`/`DEFAULT_TIMEOUT_S=600`, distinct from
   the per-HTTP-call `LLM_TIMEOUT_S`); a fourth solo attempt then
   succeeded. Real tally: 2/3 clean attempts succeed (584s, 655s), one
   exceeds a 30-minute ceiling entirely. The operator had already
   authorised the `.env` change (`LLM_MAX_TOKENS` unset→4096,
   `LLM_TIMEOUT_S` unset→600) on the overstated claim; the change is left
   standing (a real, operator-authorised production change, not this
   session's to silently revert) but the claim it rested on is corrected
   in the report.

A third, procedural finding compounds both: this task's own second
`bench.py run` invocation destroyed the first (complete, all-six-scenario)
`smoke-v160.json` via `.bench/`'s shared-root wipe, before it was copied
out. The two subsequent attempts to reproduce a complete six-scenario
document both aborted on S15's timeout before reaching S16–S18.
REQ-V160-BEN-07 precondition (3) — "one non-baseline smoke run executes
all six new scenarios, none skipped" — is therefore **unmet on the
documentary record right now**, independent of S13's own blocking status.

Full record, all figures, and the two questions posed to the operator are
in `docs/reports/report-v1.6.0.md`'s "`smoke-v160` and the S13 blocker"
section.
