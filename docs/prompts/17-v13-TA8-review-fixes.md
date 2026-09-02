# Prompt 17 — v1.3 TA8: fix the stage-A review findings

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Input:** the TA7 (`code-reviewer`) finding list, § 13.5 one fix round
- **REQ ids:** REQ-V13-BEN-01/02/13/14, REQ-V13-RSN-02 (its decision input),
  REQ-V13-OBS-08

## Brief as sent (abridged — the full finding text was pasted inline)

```
Fix TA7's findings 1, 2, 3, 4, 6, 7, 8, 9 (the two RED ones block the B1
baseline run). Finding 5 (README /stats row) is deferred to C3 by
REQ-V13-RPT-03, which assigns the Commands section to TC9 — record, do not fix.
Finding 10 is recording-only. Finding 11 is carried into the audit text.
Tests must fail before each fix and pass after. Keep ruff/pytest/mutation green.
```
