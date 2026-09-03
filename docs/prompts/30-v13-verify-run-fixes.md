# Prompt 30 — v1.3 verify-run docs fixes

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** docs-only fixes from /verify-run; no code, no design
- **Harness:** Claude Code
- **Stage:** docs
- **Owner of:** `docs/reports/tg-post-v1.3.md` (trim), `docs/prompts/09-go-spec-v1.3.md`
  … `29-v13-TD2-tg-post.md` (`Model reason` bullets added), `docs/prompts/30-v13-verify-run-fixes.md`
  (new), `docs/llm-usage.md` (row 32)
- **REQ ids:** AGENTS.md § Reporting; `standards/reporting.md` § Prompt chain

## Brief as sent

```
Docs-only fixes from a /verify-run audit of the spec-v1.3 run.

Findings to fix:
A. `docs/reports/tg-post-v1.3.md` is 1522 chars (`wc -m`); the lab limit is
   < 1500. Trim wording only — keep structure, Russian, executor model name
   (claude-opus-5), metrics, and the GitHub repo link. Verify with `wc -m`
   < 1500.
B. All 21 v1.3 prompt files (`docs/prompts/09-go-spec-v1.3.md` and
   `10-…` through `29-…`) lack a `model_reason` entry required by the lab
   standard (`standards/reporting.md`). The project uses a bullet-style
   header (Date / Executor model / Harness) rather than YAML — keep that
   style: add one line `- Model reason: …` right after the executor-model
   line in each file. The reason must be truthful: for 09 (the `go` prompt)
   and the executor-side prompts, take the rationale from the spec (the spec
   pins claude-opus-5 by user decision at spec time); for any review prompt,
   name the reviewer model and why (clean-context review per lab standard).
   Keep each reason to one line.
```
