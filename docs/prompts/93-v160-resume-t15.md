# Prompt 93 — resume spec-v1.6.0 from T15 under errata 2–5

- **Date:** 2026-09-06
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** assigned by spec-v1.6.0's header; what remains is T15–T18 as specified plus one mechanical fix (REQ-V160-BEN-08) — no design decision is left open
- **Harness:** Claude Code
- **Stage:** T15 (repeated under the errata) → T16 → T17 → T18
- **Owner of:** `devtools/bench_scenarios.py` (S13 ceiling only, erratum 2), `devtools/bench.py` and `tests/test_v160_bench.py` (REQ-V160-BEN-08 only), `docs/assets/bench/baseline-v1.6.0.json`, `docs/assets/dashboard-v1.6.0.html`, `docs/reports/report-v1.6.0.md`, `docs/reports/tg-post-v1.6.0.md`, `docs/llm-usage.md`, prompts `94-…` onward
- **REQ ids:** REQ-V160-BEN-08 (new), REQ-V160-TQ-05 (errata 2 and 3), REQ-V160-BEN-05 (erratum 5), REQ-V160-BEN-06, REQ-V160-BEN-07, REQ-V160-PRE-03, REQ-V160-PRE-04, REQ-V160-VER-04, REQ-V160-ACC-03, REQ-V160-RPT-01 … RPT-04

## Goal

Resume the run closed at T15 (commit `65146f0`) and carry it to acceptance
under the four lab errata disclosed in `docs/spec/spec-v1.6.0.md` after the
close: set S13's ceiling to the measured reference (erratum 2), take S15 out
of the blocking 3/3 for this baseline while still executing and recording it
(erratum 3), stop `bench.py run` from wiping sibling tag directories
(erratum 4, REQ-V160-BEN-08), and treat the operator's `LLM_MAX_TOKENS=4096`
/ `LLM_TIMEOUT_S=600` as the 1.6.0 instrument (erratum 5). Then reproduce a
complete `smoke-v160` document, record `baseline-v1.6.0`, finalise the
report and create the annotated `v1.6.0` tag.

## Constraints

- The spec as committed by the lab, errata included, is the contract; record
  its `sha256` at the start of this prompt exactly as the T0 record did, and
  keep it unchanged from here to the tag.
- Source, test and scenario changes are limited to two commits, both before
  any inference: (1) `tool_calls_max(5)` on S13; (2) REQ-V160-BEN-08 with
  `T-V160-BEN-08`. Nothing else in source, tests or config changes. After the
  baseline only report and evidence files change (REQ-V160-BEN-07).
- Operator inputs: reuse the LM Studio version and loaded context length
  recorded at T0 in `docs/reports/report-v1.6.0.md` unless the `go` message
  that starts this prompt supplies new values. PRE-03 (address probe) and
  PRE-04 (served model id, inference preflight at `cfg.llm_max_tokens`) are
  live checks and run again.
- `.env` discipline of REQ-V160-EC-04 unchanged: never read, printed or
  quoted; the operator-set `LLM_MAX_TOKENS` / `LLM_TIMEOUT_S` are not changed.
- The smoke document stays uncommitted (REQ-V160-BEN-07) but must survive:
  keep `.bench/smoke-v160/` on disk (REQ-V160-BEN-08 now guarantees it) and
  record its per-scenario outcomes, tool-call counts and durations in the
  report before any further run.
- No `--no-verify`. Every commit references this file or the per-task prompt
  files `94-…` onward, one prompt → one commit.

## Acceptance

1. `smoke-v160.json` complete: all six of S13–S18 executed, none skipped;
   S13, S14, S16, S17, S18 green; S15's outcome recorded whatever it is.
2. `docs/assets/bench/baseline-v1.6.0.json` committed; `bench.py check` exit
   0; 18 scenarios × 3 repeats; `meta` carries the six locked fields and
   `generation_settings.agent.max_tokens = 4096`; S13, S14, S16, S17, S18 at
   3/3, S15 recorded per repeat with `finish_reason` and durations.
3. T16–T18 per §17: `docs/assets/dashboard-v1.6.0.html` rendered from the
   committed copy, the informational v1.4 comparison, the report finalised
   with the `economics.md` ledger row and the measured baseline wall-clock,
   `tg-post-v1.6.0.md`, the evidence-only commit, then the annotated tag
   `v1.6.0` on it; `checks.py run --profile full --since 65146f0` exit 0.

## Stop

S13 above 5 calls in any repeat; any of S14, S16, S17, S18 below 3/3; a
failed preflight or unreachable LM Studio; a baseline run that would need a
source change — stop, report, no tag. S15 never stops the run (erratum 3).
