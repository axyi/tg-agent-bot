# Prompt 09 — `go docs/spec/spec-v1.3.md`

- **Date:** 2026-09-02
- **Executor model:** claude-opus-5 (Claude Code, background session)
- **Model reason:** spec-v1.3 pins claude-opus-5 for this run (spec-v1.3.md, "Executor model for this run"): judgment calls — reading what the audit numbers mean, keeping four commits honest, driving subagents on minimal context — need a larger model.
- **Harness:** Claude Code CLI, working directory `projects/tg-agent-bot`
- **Standing instruction:** AGENTS.md § "go protocol"

## Prompt as sent

```
go docs/spec/spec-v1.3.md
```

## Interpretation (AGENTS.md § go protocol)

Execute `docs/spec/spec-v1.3.md` end-to-end, following its own § 1
"Execution contract":

- four sequential commits on `main` (C1…C4, § 1.2), all referencing this
  prompt file;
- gate commands of AGENTS.md run verbatim, in order, at C1/C3/C4 (1–4 at C2);
- the blocking live benchmark steps B1, B2, D1, D2 of § 13.2;
- bounded fix loops of § 1.4 — on exhaustion, stop and report;
- every subagent brief logged as its own `docs/prompts/NN-v13-*.md`
  (REQ-V13-EC-13);
- tokens/cost recorded in `docs/llm-usage.md`, run results in
  `docs/reports/`.

## Executor decisions recorded at the start of the run

1. **`LLM_PRICE_REF_MODEL = qwen/qwen3.8-27b`** (REQ-V13-PRE-04). OpenRouter
   publishes this exact model id, which is also `LMSTUDIO_MODEL`, so the
   reference price is the true cloud price of the model actually being
   benchmarked rather than an approximation. Set in `.env` once, before B1,
   and unchanged for the rest of the run (it is inside `meta.config_sha256`,
   so any later edit would make `report --gate` exit 2). Consequence: the
   primary metric of § 13.3 is **cost per successful task**, not the
   token-based fallback.
2. **Sequential subagents in the single working tree** (§ 15 default). File
   ownership overlaps across nearly every task (`bot.py`, `config.py`,
   `agent.py`, `tools.py`, `mutation_check.py`), so no work is parallelised
   and no worktrees are used.
3. **Explicit-path staging only.** An untracked `..env.swp` (a vim swap file
   of `.env`) exists in the tree; `git add -A`/`git add .` is never used in
   this run and `git diff --cached --name-only` is checked before each of
   the four commits (REQ-V13-EC-04).
