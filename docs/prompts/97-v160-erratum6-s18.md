# Prompt 97 — spec-v1.6.0 erratum 6: S18's `summary_exists` non-blocking

- **Date:** 2026-09-06
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** disclosing a lab-authorised spec correction after an
  operator decision — no design decision is open, the correction's content
  and scope were already decided by the operator's own choice
- **Harness:** Claude Code
- **Stage:** post-resume, before T16
- **Owner of:** `docs/spec/spec-v1.6.0.md` (erratum 6 block only),
  `docs/reports/report-v1.6.0.md` (the operator's verbatim answer and the
  resulting disposition, appended to "The operator's decision"), this
  prompt file
- **REQ ids:** REQ-V160-TQ-05, REQ-V160-TQ-01 (erratum 6)

## Goal

Disclose erratum 6 in place, extending erratum 3's non-blocking treatment
of S15 to S18's `summary_exists` check, on the operator's explicit
authorisation given after `docs/reports/report-v1.6.0.md`'s "Resume under
errata 2–5" section presented the finding and three options. The operator
chose option 1: authorise erratum 6, proceed on the baseline measurement
already in evidence, no re-run.

## Constraints

- Documentation-only: one new `[[ERRATUM 6: ...]]` block in
  `docs/spec/spec-v1.6.0.md`, immediately after erratum 3 (which it
  supersedes for S18 only), plus one superseding note appended to erratum
  3's own closing sentence. No other spec text, no source, test or config
  change.
- The operator's own words are quoted in `docs/reports/report-v1.6.0.md`
  (Russian: "вариант 1 (рекомендованный)") — this prompt paraphrases them
  in English for the header table only; the report is the source of record
  for the verbatim decision.

## Acceptance

- `uv run --locked python devtools/checks.py lint-docs` — clean.
- The erratum block is present and reads correctly against the actual
  baseline evidence already recorded in the report.
- `git status --porcelain` — exactly the spec file plus this prompt.

## Stop

None — a disclosed correction whose content and authorisation both already
exist.
