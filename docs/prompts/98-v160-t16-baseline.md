# Prompt 98 — spec-v1.6.0 T16: baseline recorded

- **Date:** 2026-09-06
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** mechanical recording of an already-measured, already-
  authorised baseline — no design decision open; the merge, the dashboard
  render and the comparison are all deterministic functions of evidence
  already in hand
- **Harness:** Claude Code
- **Stage:** T16
- **Owner of:** `docs/assets/bench/baseline-v1.6.0.json`,
  `docs/assets/dashboard-v1.6.0.html`, `docs/reports/report-v1.6.0.md` (the
  new "T16 — baseline recorded" section), this prompt file
- **REQ ids:** REQ-V160-BEN-01, -02, -05, -06, -07

## Goal

Record `docs/assets/bench/baseline-v1.6.0.json` from the five
sub-invocation documents already measured and preserved (partA/B1/B2/B3/C,
54 runs, authorised under erratum 6), render `docs/assets/dashboard-v1.6.0.html`
from that committed copy, produce the informational S01–S12 comparison
against `baseline-v1.4.json`, and land all three in T16's one commit.

## Constraints

- No re-measurement: the tree is unchanged since `ca9c656`, so the merge
  uses the evidence already gathered rather than spending another ≈90
  minutes of live inference.
- The merge recomputes `summary` via `bench.summarize()` on the combined
  `runs` list rather than hand-editing any aggregate field, so
  `bench.py check`'s own arithmetic recomputation (`_validate_arithmetic`)
  is the actual proof the merge is correct, not an assertion about it.
- `bench.py report`'s CLI has no scenario-narrowing flag (a known, already-
  flagged T11 gap) — the S01–S12 comparison uses the Python API directly
  (`bench.check_document` + `bench.render_report`), per T11's own recorded
  resolution options.
- After this commit, only report and evidence files may change
  (REQ-V160-BEN-07) — the tree is frozen.

## Acceptance

- `uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json` — exit 0, `valid`.
- 18 scenarios × 3 repeats (54 runs); `meta` carries the six locked
  instrument fields and `generation_settings.agent.max_tokens = 4096`.
- S01–S17 all 3/3 within `tool_calls_max` where applicable; S18 2/3
  (erratum 6, non-blocking).
- `docs/assets/dashboard-v1.6.0.html` exists, rendered from the committed
  baseline copy.
- The report's new "T16 — baseline recorded" section states the four-reason
  informational caption and the measured wall-clock total.
- `git status --porcelain` — exactly the three owned artefact paths plus
  this prompt.

## Stop

None — the measurement and its authorisation both already exist; this task
is the mechanical recording step.
