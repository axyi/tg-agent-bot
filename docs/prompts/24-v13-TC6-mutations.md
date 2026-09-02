# Prompt 24 — v1.3 TC6: mutations tagged C (stage C)

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Owner of:** `devtools/mutation_check.py` (the 13 C-tagged mutations)
- **REQ ids:** section 12 of spec-v1.3, rows tagged `C`

## Brief as sent (abridged)

```
Add the 13 C-tagged ids verbatim. Each MUST be killed by the test named in its
"killed by" column. O5 ended `attempted_removed`, so no LLM_REASONING code
exists — if any row required it, STOP and report rather than inventing a target
(none did). Do not modify application source or tests to make a mutation die.
Final tally must be >= 64, all killed, exit 0.
```

## Outcome

64 mutations (31 v1.2 + 20 stage A + 13 stage C), 64 killed, 0 survived,
runtime 923 s.
