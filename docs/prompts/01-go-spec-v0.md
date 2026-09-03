# Prompt 01 — implement spec-v0

- **Date:** 2026-08-28
- **Executor model:** Claude Opus 5
- **Model reason:** not recorded
- **Harness:** Claude Code
- **Stage:** not recorded
- **Owner of:** not recorded
- **REQ ids:** REQ-EC-10

## Prompt as sent

```
go docs/spec/spec-v0.md
```

## Standing context this expands to

`go <spec>` is defined in `AGENTS.md` as: execute that spec end-to-end following
its own Execution contract (section 1 of the spec). Concretely — bootstrap
`.python-version` / `pyproject.toml` / `.env.example` / `.gitignore` and run
`uv lock` once; write every test file from section 5 first and observe the
expected failures; implement component by component in the order of section 4;
run the four gate commands of section 6 verbatim; use at most 5 repair-and-rerun
cycles; log prompts here and tokens in `docs/llm-usage.md`; finish with the
report template of section 7.1 or the blocker template of 7.2.

No runtime data (Telegram messages, model payloads, tool output, environment
values, tokens) is recorded in this directory — REQ-EC-10.
