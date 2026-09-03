# Prompt 03 — implement spec-v1

- **Date:** 2026-09-01
- **Executor model:** Claude Opus 5
- **Model reason:** not recorded
- **Harness:** Claude Code
- **Stage:** not recorded
- **Owner of:** not recorded
- **REQ ids:** REQ-EC-10

## Prompt as sent

```
go docs/spec/spec-v1.md
```

## Standing context this expands to

`go <spec>` is defined in `AGENTS.md` as: execute that spec end-to-end following
its own Execution contract (section 1 of the spec). For spec-v1 concretely —
verify the section-3 preconditions (`.env` key presence checked by **key name
only**, `docker version` without sudo, `docker pull python:3.13-slim`, LM Studio
model list, and an OpenRouter model choice appended to `.env`); write the new
tests of section 9.2 and apply the section-9.1 amendments to the v0 tests first,
observing the expected failures; implement in the order of section 8; run the
**five** gate commands of section 10 verbatim; use at most 5 repair-and-rerun
cycles; execute the Appendix-B acceptance scenarios against the live bot; have
the implementation reviewed by the `code-reviewer` subagent in a clean context;
log prompts here, tokens in `docs/llm-usage.md`, and finish with the report
template of v0 section 7.1 or the blocker template of 7.2.

spec-v1 is a **delta** spec: spec-v0 stays in force except where section 2's
amendment table says otherwise.

No runtime data (Telegram messages, model payloads, tool output, environment
values, tokens) is recorded in this directory — REQ-EC-10. Credential presence
was verified by key name; no secret value was ever displayed, logged or copied.

## Outcome

`[doc-fix v1.1]` — reconciled per REQ-V11-DOC-06 with `docs/reports/report-v1.md`,
which previously stated a different count for a different thing (fix cycles
spent after the review, not gate-repair cycles during the first run):

0/5 gate-repair cycles on the first full gate run; 1 additional fix round
applied after the clean-context code review.
See `docs/reports/report-v1.md`.
