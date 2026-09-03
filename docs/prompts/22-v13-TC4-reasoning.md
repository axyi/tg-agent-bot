# Prompt 22 — v1.3 TC4: O5 reasoning control (stage C) — ended `attempted_removed`

- **Date:** 2026-09-02
- **Executor model:** claude-opus-5
- **Model reason:** inherits spec-v1.3's claude-opus-5 pin for this run (docs/llm-usage.md row 31); same judgment rationale as prompt 09, applied to this task.
- **Harness:** Claude Code (`general-purpose` subagent, clean context)
- **Stage:** TC4
- **Owner of:** `agent.py`, `llm/lmstudio.py`, `config.py`, tests — all reverted
  when the probe failed; the surviving artifacts are
  `docs/assets/bench/reasoning-probe.json` and
  `docs/reports/bench-reasoning-probe.md`
- **REQ ids:** REQ-V13-RSN-01 (decided: applicable), REQ-V13-RSN-02

## Brief as sent (abridged)

```
RSN-01 is already decided from the committed baseline: reasoning observed,
Σ reasoning_tokens 12144 = 71.8% of completion, tool-exposed calls: calls: 84.
Implement LLM_REASONING=auto|on|off per RSN-02, using the mechanism the model's
own documentation specifies, verified via context7 (PRE-05) — never assumed.
Then run the bounded live probe (--only S05 --repeats 1 --tag reasoning-probe)
and read the state FROM THE GENERATED MARKDOWN ONLY. Conclusive iff S05 is 1/1
and `tool-exposed calls:` shows calls >= 1. reasoning observed: no ->
implemented; yes -> attempted_removed. Inconclusive -> re-run once, then
attempted_removed.
IF attempted_removed you MUST strip the knob back out entirely — no Config
field, no validation, no tests, no README/.env.example line — before returning.
```

## Outcome

Probe conclusive on the first run: S05 `1/1`, `tool-exposed calls: calls: 2,
reasoning observed: yes, … reasoning share: 0.7373`. LM Studio does not honour
Qwen3's documented `/no_think` soft switch, and its OpenAI-compat endpoint
documents no `chat_template_kwargs`. State = **`attempted_removed`**; the knob
was stripped and the tree restored byte-identical to its pre-TC4 state.
