# Prompt 07 — implement spec-v1.2

- **Date:** 2026-09-01
- **Executor model:** Claude Sonnet 5
- **Model reason:** not recorded
- **Harness:** Claude Code
- **Stage:** not recorded
- **Owner of:** not recorded
- **REQ ids:** REQ-V1-EC-10, REQ-V12-EC-04, REQ-V12-REP-02

## Prompt as sent

```
go docs/spec/spec-v1.2.md
```

## Standing context this expands to

`go <spec>` is defined in `AGENTS.md` as: execute that spec end-to-end
following its own Execution contract (section 1 of the spec). For spec-v1.2
concretely — verify the section-3 preconditions (repo on `main`, clean tree,
HEAD at the delivered v1.1 state, all five v1.1 gates green before any edit,
`.env` key presence checked by **key name only**, Docker reachable with the
sandbox image present, stdlib `shutil`/`socket`/`ipaddress` importable); write
the section-10.2 tests and apply the section-10.1 amendments to the existing
suite first, observing the expected failures; build `devtools/mutation_check.py`
and its own tests before the fixes it will verify; implement in the order of
section 9 (config, storage, agent, tools, bot, then docs); run the **six**
gate commands of section 11 verbatim, including the new mutation gate, with a
repair budget of 5 total repair-and-rerun cycles; execute this spec's
Appendix B against the live bot plus spec-v1.1's scenarios C1, C3, C4 and C6
as a regression check; have the implementation reviewed by the
`code-reviewer` subagent in a clean context; log prompts here, tokens in
`docs/llm-usage.md`, and finish with the report template — including the
process-honesty requirements of REQ-V12-REP-02 (at least two commits, and the
Deviations section states for every acceptance scenario whether it was driven
by a real Telegram message or a script).

spec-v1.2 is a **delta** spec over spec-v0, spec-v1 and spec-v1.1: all three
stay in force except where section 2's amendment table says otherwise. This
is a **patch release** closing findings from two independent post-v1.1
audits (an adversarial security probe, W-1…W-8, and an 83-mutation
spec-compliance review, G-1…G-11) — behaviour changes only where a
requirement says so, no opportunistic cleanups.

No runtime data (Telegram messages, model payloads, tool output, environment
values, tokens) is recorded in this directory — REQ-V1-EC-10 (carried by
REQ-V12-EC-04). Credential presence was verified by key name; no secret value
was ever displayed, logged or copied. Appendix B's throwaway synthetic secret
(`SYNTHETIC-V12-CANARY-<random hex>`) is not a live credential and is
discarded with the scratch directory it was generated into; `.env` itself was
never created, overwritten or read out loud — throwaway values were passed as
process environment overrides.

## Outcome

See `docs/reports/report-v1.2.md`.
