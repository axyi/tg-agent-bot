# Prompt 15 — v1.3 TA6: mutations tagged A (stage A)

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Owner of:** `devtools/mutation_check.py` (the 20 A-tagged mutations only)
- **REQ ids:** section 12 of spec-v1.3 (rows tagged `A`)

## Brief as sent

```
Repo: /home/akh/aihome/coders-su/projects/tg-agent-bot (Python 3.13, uv). Read
docs/spec/spec-v1.3.md section 12 and add EXACTLY the 20 mutations tagged `A`
in that table, with the ids given there, following the existing v1.2 mutation
style in devtools/mutation_check.py (--list / --only semantics unchanged).
Every added mutation MUST be killed by the test named in its "killed by" column.
Verify with `uv run --locked python devtools/mutation_check.py` (slow, minutes)
and report the total count and that all are killed.
Do NOT add the 13 mutations tagged `C` (stage C, a later task).
Do NOT modify application source to make a mutation die — if a mutation
survives, report it; the fix belongs to the task that owns that code.
NEVER open .env. Return a <=15-line summary: ids added, total mutations, all
killed yes/no, runtime. Never paste file contents.
```
