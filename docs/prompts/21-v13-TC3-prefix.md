# Prompt 21 — v1.3 TC3: O3 byte-stable prefix + O4 prefix compression (stage C)

- **Date:** 2026-09-02
- **Executor model:** claude-opus-5
- **Model reason:** inherits spec-v1.3's claude-opus-5 pin for this run (docs/llm-usage.md row 31); same judgment rationale as prompt 09, applied to this task.
- **Harness:** Claude Code (`general-purpose` subagent, clean context)
- **Stage:** TC3
- **Owner of:** `agent.py` (prompt/prefix), `tools.py` `tool_specs`
  descriptions, `llm/openrouter.py`, `tests/test_prefix.py` (new), amended
  existing tests
- **REQ ids:** REQ-V13-CCH-01 … CCH-04, REQ-V13-PFX-01 … PFX-03

## Brief as sent (abridged)

```
The measured baseline shows prefix_share = 0.7857 — 78.6% of ALL prompt tokens
are the system prompt + tool schema, re-sent on every one of 88 calls. This is
the highest-value optimization in the release.
PFX-01: rewrite SYSTEM_PROMPT to <= 550 chars measured as
len(SYSTEM_PROMPT.replace("{skill_lines}", "")) (1325 today), Role/Output/Tools/
Rules/Skills, with nine listed statements surviving IN MEANING — each verified
by a test, including the prompt-injection defence — plus the new concision line.
PFX-02: json.dumps(tool_specs()) <= 1400 chars with every parameter name, type,
enum, min/max and `required` unchanged except O1's two additions.
CCH-01: the clock LEAVES the system prompt and is appended to the newest user
message at request-assembly time. CCH-02: round n is a prefix-extension of n-1;
tools JSON byte-identical across tool-exposing rounds.
CCH-03: anthropic/ models get cache_control on the system block; verify the
field shape via context7 and return the citation.
```
