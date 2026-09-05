# Prompt 90 — spec-v1.6.0 T15: in-place PRE-04 erratum, preflight now passes

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** direct continuation of the T15 orchestrator session that
  recorded the STOP (prompt 89); the correction, its authorisation and the
  re-run all depend on that session's own accumulated context (the two
  measurements, the RSN-06 cross-reference, the operator's own words), so a
  fresh session would have to re-derive all of it first.
- **Harness:** Claude Code
- **Stage:** T15
- **Owner of:** `docs/spec/spec-v1.6.0.md` (PRE-04's preflight clause only),
  `docs/reports/report-v1.6.0.md`, this prompt file
- **REQ ids:** REQ-V160-PRE-04, REQ-V160-PRE-01.1, REQ-V160-VER-02

## Goal

Resolve prompt 89's STOP under the operator's own decision, reached in two
questions: (1) widen the preflight's token floor rather than swap the
loaded model or accept the stop; (2) having found that the first proposed
mechanism (editing `spec-v1.6.0.md` directly) conflicts with
REQ-V160-PRE-01.1's own `sha256` freeze, and that a brand-new
`spec-v1.6.1.md` file would itself conflict with this same spec's
REQ-V160-VER-02 ("PATCH: a fix with no new spec") and with the only
working precedent in this repository (`v1.5.1`, which corrected
`spec-v1.5.md` in place) — correct `spec-v1.6.0.md`'s PRE-04 clause in
place, disclose the resulting `sha256` break exactly as `v1.5.1` disclosed
its broken acceptance freeze, and re-run the preflight against the
corrected clause.

## Constraints

- No reinterpretation of the operator's own words as authorisation for
  more than what they said; the `sha256` break is recorded as deliberate
  and attributed to their explicit choice, not asserted as this session's
  own unilateral judgment.
- The original STOP section (prompt 89's evidence) stays in the report
  byte-for-byte, un-deleted and un-softened; the correction is a new,
  clearly separated subsection, not a rewrite of history — matching
  `v1.5.1`'s own D3 practice of adding a labelled new measurement
  alongside an old one rather than overwriting it.
- The spec correction is a single, minimal clause edit (the preflight's
  `max_tokens` value and one `[[ERRATUM: ...]]` disclosure block) — no
  other spec text touched, no scope creep into re-litigating other PRE-04
  values.
- No production, test or config file touched; T14's "no fix after T16"
  freeze is not engaged either way (this is a spec/report correction, not
  a source fix, and lands before T16 regardless).
- The re-run preflight call must be a fresh, real HTTP round trip against
  the live instrument — not a restatement of the earlier diagnostic figures
  under a new label.

## Acceptance

- `docs/spec/spec-v1.6.0.md`'s preflight clause reads
  `max_tokens = cfg.llm_max_tokens`, with the erratum block naming both
  `sha256` values, the RSN-06 cross-reference and this report's section.
- A fresh preflight call at `cfg.llm_max_tokens` against the resolved
  instrument returns `finish_reason == "stop"` and non-empty content.
- `docs/reports/report-v1.6.0.md`'s top status line and the new
  "Resolution" subsection both state the `sha256` break plainly, quote the
  operator's own choice, and record the fresh preflight result.
- `uv run --locked python devtools/checks.py lint-docs` — PASS (this
  prompt file and the report's ledger row still conform).

## Stop

Not applicable — this task resolves cleanly: the corrected preflight
passes on the first (and only) re-run, no repair loop needed. T15 now
proceeds to `smoke-v160` (REQ-V160-BEN-07).
