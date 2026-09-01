# Prompt 04 — code review of the spec-v1 implementation (reconstructed)

**This prompt was never logged during the spec-v1 run — that omission is
finding R-5 of the spec-v1.1 audit (REQ-V11-DOC-01). What follows is a
reconstruction after the fact, assembled from the outcome actually recorded
in `docs/reports/report-v1.md`'s Review section, in the shape of
`docs/prompts/02-code-review.md`. It is NOT a verbatim record of the prompt
sent to the `code-reviewer` subagent for the spec-v1 run — no verbatim record
exists.**

Agent: `code-reviewer` subagent (`.claude/agents/code-reviewer.md`), clean
context, read-only tools.
Date: 2026-08-31 (reconstructed; the run that produced `c1f27c3`)

## Prompt as reconstructed

```
Review commit c9f7912 on branch main of this repository: the complete
implementation of docs/spec/spec-v1.md on top of the delivered spec-v0
baseline.

The spec is the contract. Read AGENTS.md and docs/spec/spec-v1.md first
(spec-v1 is a delta spec over spec-v0 — section 2's amendment table is
authoritative), then review every changed source file (config.py,
storage.py, tools.py, agent.py, bot.py, llm/*.py), the two new skills, the
test suite and README.md.

The five gates already pass (uv sync --locked; uv run --locked ruff check .;
uv run --locked pytest -> 197 passed; uv run --locked python bot.py
--selftest -> selftest: OK; uv run --locked python bot.py --selftest-live ->
6/6 OK), so do not re-derive what the linter and the tests prove.

Focus on:
1. Spec violations - any REQ-V1-* whose stated behaviour differs from the
   code, including exact error strings, exact orderings, the exact Docker
   argv (REQ-V1-DK-03) and the exact system-prompt injection-defence text
   (REQ-V1-INJ-02).
2. Tests that assert something weaker than the T-V1-* row they implement, or
   that would still pass against a wrong implementation — in particular the
   main()-wiring tests that bind the exec runner, and the audit-log coverage
   of REQ-V1-AUD-01/02.
3. The v0 secret-exfiltration property (REQ-SEC-01/REQ-V1-DK-01): confirm no
   path from the exec sandbox reaches `.env`, the database, the audit log or
   the source tree, and that the redaction choke point (REQ-V1-SEC-01/02/06)
   has no gap — including the fetch tool and the structured-summary path.
4. Docker isolation (REQ-V1-DK-01..08): flag order, resource limits, the
   root-refusal guard, the timeout/kill path, the placement check in
   REQ-V1-CFG-03 (does it resolve symlinks the way the container mount
   does?).
5. Failover (REQ-V1-FO-*), structured memory (REQ-V1-MEM-*), the token
   budget (REQ-V1-TB-*) and the error matrix (REQ-V1-ERR-01) for gaps
   between the stated behaviour and the delivered one.
6. Non-goals implemented by accident.

Report findings with file:line, severity and a concrete failure scenario.
```

No runtime data is recorded here — REQ-EC-10 (carried by spec-v1's
REQ-V1-EC-04).

## Outcome (as recorded in `docs/reports/report-v1.md`)

Verdict: **request changes**. Nine findings, all fixed, none waived — see
`docs/reports/report-v1.md`'s Review section for the full table (one 🔴, six
🟡/🟢 severities) and the two robustness notes the executor raised on itself
in the same cycle. Commit `c1f27c3` carries the fixes. This is the 1/5 fix
cycle recorded against `docs/prompts/03-go-spec-v1.md` (reconciled wording
per REQ-V11-DOC-06).
