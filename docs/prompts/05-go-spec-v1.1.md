# Prompt 05 — implement spec-v1.1

Agent: implementation agent (Claude Sonnet 5, Claude Code harness)
Date: 2026-09-01

## Prompt as sent

```
go docs/spec/spec-v1.1.md
```

## Standing context this expands to

`go <spec>` is defined in `AGENTS.md` as: execute that spec end-to-end
following its own Execution contract (section 1 of the spec). For spec-v1.1
concretely — verify the section-3 preconditions (repo on `main`, clean tree,
all five v1 gates green before any edit, `.env` key presence checked by
**key name only**, Docker reachable with the sandbox image present, the
image's GNU `timeout` probed); write the section-9.2 tests and apply the
section-9.1 amendments to the existing suite first, observing the expected
failures; for each of the four corrected tests (T-V1-VIS-01 companion, the
Telegram-boundary redaction test, T-V1-FT-02's streaming-stop assertion,
T-V1-DK-05's outer-timeout assertion), prove the defect by temporarily
breaking the production line the audit's mutation targeted, confirm red,
restore, confirm green; implement in the order of section 8; run the **five**
gate commands of section 10 verbatim; use at most 5 repair-and-rerun cycles;
execute this spec's Appendix B against the live bot plus spec-v1's Appendix B
scenarios B1, B3, B4 and B10 as a regression check; have the implementation
reviewed by the `code-reviewer` subagent in a clean context; log prompts
here, tokens in `docs/llm-usage.md`, and finish with the report template.

spec-v1.1 is a **delta** spec over spec-v0 and spec-v1: both stay in force
except where section 2's amendment table says otherwise. This is a **patch
release** — behaviour changes only where a requirement says so, no
opportunistic cleanups.

No runtime data (Telegram messages, model payloads, tool output, environment
values, tokens) is recorded in this directory — REQ-EC-10 (carried by
REQ-V11-EC-04). Credential presence was verified by key name; no secret value
was ever displayed, logged or copied. Appendix B's throwaway synthetic secret
(`SYNTHETIC-V11-CANARY-<random hex>`) is not a live credential and is
discarded with the scratch directory it was generated into.

## Outcome

See `docs/reports/report-v1.1.md`.
