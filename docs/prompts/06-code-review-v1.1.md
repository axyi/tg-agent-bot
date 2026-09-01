# Prompt 06 — code review of the spec-v1.1 implementation

Agent: `code-reviewer` subagent (`.claude/agents/code-reviewer.md`), clean
context, read-only tools.
Date: 2026-09-01

## Prompt as sent

```
Review the uncommitted working-tree diff of this repository: the complete
implementation of docs/spec/spec-v1.1.md, a patch release on top of the
delivered spec-v1 baseline (commits c9f7912, c1f27c3, 782a378).

The spec is the contract. Read AGENTS.md and docs/spec/spec-v1.1.md first —
it is a delta spec over spec-v0 and spec-v1; section 2's amendment table is
authoritative. Then review every changed file: config.py, storage.py,
tools.py, agent.py, bot.py, tests/test_docker.py, tests/test_v1_guardrails.py,
tests/test_v11_patch.py (new), .env.example, .gitignore, README.md,
docs/spec/spec-v1.md (doc-fix notes only).

All five gates already pass (uv sync --locked; uv run --locked ruff check .;
uv run --locked pytest -> 251 passed, up from 203; uv run --locked python
bot.py --selftest -> selftest: OK; uv run --locked python bot.py
--selftest-live -> 6/6 OK), and pytest was independently re-run with `docker`
removed from PATH to confirm the suite never shells out to a real daemon, so
do not re-derive what the linter and the tests already prove.

Focus on:
1. Spec violations - any REQ-V11-* whose stated behaviour differs from the
   code, including exact error strings, exact orderings, the exact
   `docker run` argv additions (label, resolv mount, timeout wrapper) and the
   exact redaction order (decode -> redact -> strip_secret_fragment ->
   re-encode -> cut -> decode).
2. REQ-V11-RED-01/02: is there any write path into SQLite or the outgoing
   LLM payload that model-authored content or tool-call arguments can reach
   without going through `config.redact`? Check `agent.py`'s tool round,
   all four storage writers, and the summary path.
3. REQ-V11-TRN-01/02: does `strip_secret_fragment` handle overlapping/nested
   secrets correctly, and does the headroom actually prevent every
   split-secret case, not just the one the tests construct?
4. REQ-V11-ORP-01..04 / REQ-V11-WIR-01: confirm the startup seam is the only
   path that shells out to `docker` at startup, that it is a true no-op when
   `docker_ok` is false, and that the 124 exit-code mapping in
   `run_command_docker` cannot collide with the DOCKER_CLIENT_EXIT_CODES
   branch or with the outer-timeout `timed_out` path.
5. REQ-V11-QTA-01..05: does `sandbox_usage` ever double-count, mis-handle a
   race between the pre-check and the run, or leak `sandbox_over_quota` into
   the model-facing envelope through any path other than the one
   `_run_exec`'s pop covers?
6. REQ-V11-CFV-01/02: are there SSRF-shaped or path-traversal-shaped inputs
   the new validators miss (IPv4-mapped IPv6, unusual bracket forms, a
   symlinked EXEC_WORKDIR)?
7. Tests that assert something weaker than the T-V11-* row they implement,
   or that would still pass against a wrong implementation — the four
   corrected v1 tests (T-V1-VIS-01 companion, the Telegram-boundary
   redaction test, T-V1-FT-02's streaming-stop assertion, T-V1-DK-05's
   outer-timeout assertion) were each proven with a manual mutation
   (temporarily break the production line, confirm red, restore, confirm
   green) — sanity-check that the four assertions still actually depend on
   the line they claim to guard.
8. Section 9.1's claim of exhaustiveness: did any test outside that list get
   modified, or any existing test get deleted?
9. README.md and .env.example accuracy against the delivered behaviour.
10. Non-goals (section 12) implemented by accident.

Report findings with file:line, severity and a concrete failure scenario.
```

No runtime data is recorded here — REQ-EC-10 (carried by REQ-V11-EC-04).

## Outcome

Verdict: **request changes**, scoped to reporting completeness — no code-level
spec violation, hallucinated behaviour or security gap was found; two
independently-reproduced mutation checks (removing `redact(...)` from
`bot._status_line`; removing `config.redact(response.content or "")` from
`agent.py`'s tool round) matched the report's claimed evidence exactly.

Findings and disposition:

- 🔴 `docs/reports/report-v1.1.md` listed `docs/reports/tg-post-v1.1.md` and
  `docs/llm-usage.md` as delivered while the review was reading the tree
  mid-flight (both were written concurrently, in the same working directory,
  by documentation steps that ran after the review was launched). `llm-usage.md`
  genuinely had no v1.1 rows yet at that point — **fixed**: rows 25–26 appended
  with the measured session transcript totals. `tg-post-v1.1.md` existed by
  the time the review's snapshot was taken but apparently after the
  reviewer's read — no further action needed once the race is accounted for.
- 🟢 `tools.py`'s `DOCKER_CLIENT_EXIT_CODES` branch (docker exit 125/126/127)
  did not re-check the sandbox quota before returning, unlike the
  `timed_out` and normal-completion paths — **fixed**: `_record_sandbox_quota`
  is now called on that branch too, matching REQ-V11-QTA-03's "after a
  container finishes" wording. No existing test's exact key-set assertion
  changed (an empty test sandbox never crosses the quota).
- 🟢 `config._reject_ssrf_shaped_domain` cannot catch BSD/glibc shorthand IPv4
  (`127.1` for `127.0.0.1`) — REQ-V11-CFV-01's four enumerated checks do not
  cover it. This is a gap in the spec's own enumeration, not an implementation
  deviation, and the reviewer did not claim it is exploitable (`getaddrinfo`
  generally needs `AI_NUMERICHOST` to accept that form). **Not fixed** — a
  patch release implements exactly what the spec lists; recorded as a note
  for the next spec delta in `docs/reports/report-v1.1.md`.
- 🟢 T-V1-FT-01 needed no edit under section 9.1's conditional wording
  ("*if* it pins `URL_NOT_HTTPS`..."); confirmed the v1 test never had such a
  case, so the condition was correctly false. No action; noted for the
  record.
- 🟢 `fetch_url`'s post-redaction cut can trim bytes even when `truncated`
  stays `False` (the redaction placeholder is longer than a short secret).
  Confirmed spec-blessed by REQ-V11-TRN-02 step 3. No action.

Fix cycle 1/5 used. All five gates re-confirmed green after the fix
(251 passed).
