# Prompt 08 — code review of the spec-v1.2 implementation

- **Date:** 2026-09-02
- **Executor model:** not recorded
- **Model reason:** not recorded
- **Harness:** not recorded
- **Stage:** not recorded
- **Owner of:** review only — no owned paths (`code-reviewer` subagent, clean context, read-only tools)
- **REQ ids:** REQ-EC-10, REQ-V11-EC-04, REQ-V12-EC-01, REQ-V12-ID-01, REQ-V12-ID-02, REQ-V12-ID-03, REQ-V12-ID-04, REQ-V12-QTA-01, REQ-V12-QTA-02, REQ-V12-QTA-03, REQ-V12-SSR-01, REQ-V12-SSR-02, REQ-V12-SSR-03, REQ-V12-SSR-04, REQ-V12-ORP-02, REQ-V12-ORP-03, REQ-V12-AUD-01, REQ-V12-TST-01, REQ-V12-DOC-01, REQ-V12-DOC-02

## Prompt as sent

```
Review the uncommitted working-tree diff of this repository: the complete
implementation of docs/spec/spec-v1.2.md, a patch release on top of the
delivered spec-v1.1 baseline (commits b61b186, 40dd85f, 7ab107a).

The spec is the contract. Read AGENTS.md and docs/spec/spec-v1.2.md first —
it is a delta spec over spec-v0/v1/v1.1; sections 5 and 6 name every fix this
release makes. Then review every changed file: config.py, storage.py,
tools.py, agent.py, bot.py, devtools/mutation_check.py (new),
devtools/__init__.py (new), tests/test_docker.py, tests/test_v1_guardrails.py,
tests/test_v11_patch.py, tests/test_agent.py, tests/test_mutation_check.py
(new), tests/test_v12_patch.py (new), tests/conftest.py, .env.example,
README.md, AGENTS.md, docs/plan.md, docs/llm-usage.md,
docs/reports/report-v1.1.md, docs/reports/tg-post-v1.1.md.

All six gates already pass: uv sync --locked; uv run --locked ruff check .;
uv run --locked pytest -> 325 passed, up from 251; uv run --locked python
bot.py --selftest -> selftest: OK; uv run --locked python bot.py
--selftest-live -> 6/6 OK; uv run --locked python devtools/mutation_check.py
-> 29 mutations, 29 killed, 0 survived, 0 errored, 0 drifted (wall-clock
7m6s). Do not re-derive what the linter, the tests and the mutation gate
already prove — but your standing instruction "for critical logic ask which
test fails if this line changes?" now has a mechanical answer: gate 6. Report
any security-relevant line that has NO mutation entry in
devtools/mutation_check.py's MUTATIONS list as a finding, not an observation.

Focus on:
1. Spec violations — any REQ-V12-* whose stated behaviour differs from the
   code: the exact minted tool-call id format (call_{turn_id}_{index}), the
   exact tri-state sandbox-scan precedence (SCAN_INCOMPLETE must never be
   downgraded to SCAN_CUT_SHORT even if the entry limit is also crossed), the
   exact three SSRF layers (config-time shape/TLD check, one-time startup
   resolution, per-request resolution before every hop including redirects),
   the exact O_NOFOLLOW/O_TRUNC/O_NONBLOCK + fstat sequence in
   bot._ensure_empty_resolv, the exact owner_key/owner_is_alive pid+starttime
   scheme, and the audit-hook redaction boundary in tools._audit.
2. REQ-V12-ID-01..04: can a model-authored tool-call id or name ever reach
   storage or the outgoing LLM payload unminted/unsubstituted? Check every
   call site of normalize_tool_calls and _to_wire, and whether a fresh id is
   minted per round (not once before the while loop).
3. REQ-V12-QTA-01..03: does sandbox_usage's onerror handling ever race with
   the entry-limit counter in a way that could downgrade INCOMPLETE back to
   CUT_SHORT or OK? Does _remove_sandbox_entry's chmod-and-retry correctly
   handle Python 3.12+'s fd-based shutil.rmtree (not just call func(path)
   blindly on whatever onexc hands it)?
4. REQ-V12-SSR-01..04: are there still SSRF-shaped inputs the shape/TLD
   regex misses? Does the DNS-rebinding gap between the per-request resolve
   check and the actual connect get honestly documented rather than silently
   assumed closed?
5. REQ-V12-ORP-02/03: confirm the ownership check cannot be spoofed by a
   short-lived process reusing a recently-freed pid before its start-time tick
   changes, and that the 137 exit-code mapping cannot double-report a timeout
   that the outer _run_process kill already caught.
6. REQ-V12-AUD-01: is there any exec/fetch audit call site that bypasses
   tools._audit's redact-then-emit sequence?
7. devtools/mutation_check.py's own correctness: does default_runner's
   --deselect of test_mutation_check.py's real-repo find-string check
   actually prevent that test from poisoning every mutation's verdict, and
   is there any other test in the deselected file's neighbourhood that could
   do the same thing? Does run_one's restoration happen on every exit path
   (including the runner raising, and SIGINT/SIGTERM mid-run)?
8. Section 10.1's claim of exhaustiveness: did any test outside that
   amendment list get modified, or any existing test get deleted?
9. The two TRN-03 tests added to close REQ-V12-TST-01
   (test_t_v11_trn_03_fetch_url_headroom_strips_straddling_secret's added
   config.REDACTION assertion, and the new
   test_t_v11_trn_03_fetch_url_strips_a_fragment_left_by_a_short_response):
   do they actually isolate the two mutation entries they claim to
   (trn-03-secret-headroom-term, trn-03-strip-secret-fragment), or could a
   different, unrelated code change also make them pass/fail?
10. docs/reports/report-v1.1.md's and docs/reports/tg-post-v1.1.md's
    retroactive corrections (REQ-V12-DOC-02 items 3-4): are the corrections
    accurate to what actually happened, and does the trimmed tg-post-v1.1.md
    still read coherently in Russian?
11. README.md and .env.example accuracy against the delivered behaviour,
    including the new Verification section (REQ-V12-DOC-01) and the ownership-
    aware single-instance note.
12. Non-goals implemented by accident; opportunistic refactors beyond what
    the spec's fixes required (this is a patch release, not a cleanup pass).

Report findings with file:line, severity and a concrete failure scenario.
```

No runtime data is recorded here — REQ-EC-10 (carried by REQ-V11-EC-04 and
REQ-V12-EC-01).

## Outcome

Recorded in `docs/reports/report-v1.2.md`'s Review section.
