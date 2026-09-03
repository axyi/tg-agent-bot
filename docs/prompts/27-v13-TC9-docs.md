# Prompt 27 — v1.3 TC9: README and AGENTS.md for stage C

- **Date:** 2026-09-02
- **Executor model:** claude-opus-5
- **Model reason:** inherits spec-v1.3's claude-opus-5 pin for this run (docs/llm-usage.md row 31); same judgment rationale as prompt 09, applied to this task.
- **Harness:** Claude Code (`general-purpose` subagent, clean context)
- **Stage:** TC9
- **Owner of:** `README.md`, `AGENTS.md`
- **REQ ids:** REQ-V13-RPT-03, REQ-V13-RPT-04

## Brief as sent (abridged)

```
Add the README sections "Observability", "Benchmark", "Token economy" (headline
numbers as the LITERAL placeholder `_measured in C4_`, no link — a later commit
replaces exactly that placeholder), the updated Configure table with all seven
new env vars (including the three LLM_PRICE_* that a stage-A review finding
deferred to this task), Commands (`/stats` and the new `/status` token line),
The fetch tool, and Limits.
AGENTS.md: layout gains metrics.py, llm/pricing.py, devtools/; gate 5 must be
FULLY green with the v1.2 exception named as withdrawn; a Benchmark section.
There is NO LLM_REASONING in this tree (O5 is `attempted_removed`) — do not
document it anywhere.
```
