# Prompt 18 — v1.3 TB1: the token audit (stage B)

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Owner of:** `docs/reports/audit-v1.3.md` (new)
- **REQ ids:** REQ-V13-AUD-04, REQ-V13-RSN-01
- **Sources:** `docs/reports/bench-baseline.md` and
  `docs/reports/bench-openrouter-smoke.md` — markdown only, never the JSON
  (REQ-V13-EC-12)

## Brief as sent

```
Write docs/reports/audit-v1.3.md per REQ-V13-AUD-04, from the two generated
markdown reports ONLY (never the JSON, never the .log). Answer the assignment's
audit questions with the computed numbers, each citing the table it came from.
Include the ranked stage-C hypothesis list with an expected saving each, mapped
to section 10 REQ ids, and state which section-10 optimizations the data does
NOT justify. RSN-01: reasoning was observed, so record O5 exactly as
`applicable — pending validation` and nothing stronger.
```
