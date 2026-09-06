# Prompt 96 — spec-v1.6.0 resume under errata 2–5: stopped again, at S18

- **Date:** 2026-09-06
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** continuation of prompt 93's resume — executing the
  scripted T15→T16 sequence and recording its outcome needed no design
  decision until S18's failure surfaced, at which point `advisor()` was
  consulted and the finding was handed to the operator rather than resolved
  unilaterally, matching this run's own S13 precedent
- **Harness:** Claude Code
- **Stage:** T15 (offline gates, PRE-03/PRE-04, `smoke-v160`) → T16
  (baseline measurement) → **STOP**, before T16's commit
- **Owner of:** `docs/reports/report-v1.6.0.md` (new sections only), this
  prompt file
- **REQ ids:** REQ-V160-PRE-03, REQ-V160-PRE-04, REQ-V160-BEN-07,
  REQ-V160-TQ-05, REQ-V12-REP-02

## Goal

Execute prompt 93's plan: resolve LM Studio, run the live preflight,
reproduce `smoke-v160`, and record the `baseline-v1.6.0` measurement. Report
the outcome exactly as measured, whether that outcome is T16's completion or
a new stop.

## Constraints

Same as prompt 93: no source/test/config change beyond the two already-
landed commits (`20f3200`, `ca9c656`); `.env` touched only via the PRE-03
single-line `sed`; no commit of `docs/assets/bench/baseline-v1.6.0.json`
unless T16's full acceptance is met.

## Acceptance

This prompt's own acceptance is the report being an accurate, evidence-
complete account of what was measured — see `docs/reports/report-v1.6.0.md`'s
new sections below this prompt's marker. `checks.py lint-docs` passes on the
updated report and this prompt file.

## Stop

**S18 repeat 3 failed `summary_exists` in the baseline measurement** (0
summary rows; both the summary call and its truncation retry hit
`finish_reason="length"` with the entire completion budget spent on hidden
reasoning — REQ-V160-TQ-01 and Appendix B's E10 working exactly as
specified, not a defect). Per prompt 93's own Stop clause ("any of S14, S16,
S17, S18 below 3/3 ... stop, report, no tag"), the run stops here, before
T16's commit. Full account, evidence inventory and the operator's three
options are in the report's new final section.
