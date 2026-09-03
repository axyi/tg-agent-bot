# Prompt 25 — v1.3 TC7: clean-context review of stage C

- **Date:** 2026-09-02
- **Executor model:** claude-opus-5
- **Model reason:** `code-reviewer` subagent, own clean context (AGENTS.md § Review — never self-review in the writing context); ran on claude-opus-5, this run's pin (docs/llm-usage.md row 31).
- **Harness:** Claude Code (`code-reviewer` subagent, own clean context, AGENTS.md § Review)
- **Stage:** TC7
- **Owner of:** review only — no owned paths (`code-reviewer` subagent, AGENTS.md § Review)
- **Scope:** the whole stage-C diff before commit
- **REQ ids:** section 13.5 ("after stage C, before D1")

## Brief as sent (abridged)

```
Review the uncommitted stage-C work against section 10, 11.5, section 12 rows
tagged C, and Appendix E. O5 ended `attempted_removed` — verify the strip is
COMPLETE and nothing dead was left behind. An optimized 36-run live benchmark
runs next and is gated against the committed baseline, so weight correctness of
the request-assembly path and tools.py highest.
Check especially: TOO-01 implemented literally and the length invariant; secret
handling (redact before compaction, strip_secret_fragment after every cut); the
fetch save sequence (no O_TRUNC, fail-closed); TOO-07's exact key set and order;
HST-01..05; CCH-01/02 byte-stability; PFX-01's nine mandatory statements;
RTE-01; any change to a meta.constants value; and test-stub signature drift of
the kind that silently voided REQ-V11-RED-04 in stage A.
```

## Outcome

1 🔴 (the `FETCH_MAX_BYTES` cut not followed by `strip_secret_fragment`, so a
secret fragment could reach the saved sandbox file the model is told to grep),
4 🟡, 6 🟢. Verdict: request changes. Fixed in TC8
(`docs/prompts/26-v13-TC8-review-fixes.md`).
