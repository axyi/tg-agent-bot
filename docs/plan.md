# Project plan — tg-agent-bot

Course assignment 3: turn a Telegram bot into an LLM agent — minimal harness
(agent loop with hard budgets), a universal `exec` console tool with bounded
mechanics, description-driven skills, `/new` context switching, SQLite dialog
storage with a turn-group context window, and a fail-closed Telegram user
whitelist. The specification is the primary authored artifact; the
implementation is produced by an AI agent from it.

## Status

| Milestone | State |
|---|---|
| Repository scaffold | done |
| `docs/spec/spec-v0.md` (implementation spec, 113 requirements) | done — reviewed, gate passed (0 high/medium findings, 3 review cycles) |
| v0 implementation (`bot.py`, `agent.py`, `llm/`, `tools.py`, `storage.py`, tests) | done — all four gates green on the first full run, 113 tests, 1 fix cycle of 5 (closing the code review's finding). No container isolation yet — `exec` was honestly documented as not a security boundary |
| `docs/spec/spec-v1.md` + implementation | done — adds the Docker sandbox (`exec` runs inside a disposable, network-isolated, non-root container instead of the bare host), the fetch tool with an allowlist, secret registration/redaction, storage schema v2 (summaries), and `--selftest-live`; five gates green, Appendix-B/C acceptance scenarios pass |
| `docs/spec/spec-v1.1.md` + implementation | done — closes the v1 security audit's findings (secret-truncation headroom, sandbox quota accounting, orphaned-container reap, resolv-file hardening) plus a mutation-testing pass that found 4 test-suite defects; five gates green, one fix cycle of 5 |
| `docs/spec/spec-v1.2.md` + implementation | done — closes two independent post-v1.1 audits (an adversarial security probe and an 83-mutation compliance review): minted tool-call ids, tri-state sandbox quota scanning, three-layer SSRF-resistant fetch allowlist, hardened resolv-file creation, ownership-aware container reap, audit-hook redaction, plus `devtools/mutation_check.py` as a standing gate; six gates green, 326 tests, 31/31 mutations killed, 0 repair cycles consumed |
| Live run against Telegram + LM Studio / OpenRouter | done as of v1's `--selftest-live` and the Appendix-B/C/D acceptance drivers; a real Telegram conversation with a live operator account has not been exercised — every acceptance run to date has been driven by a script standing in for the operator's messages (declared as a deviation in each run's report) |
| `docs/spec/spec-v1.3.md` + implementation | next — see below |

## How the implementation run works

An AI agent is started with a single instruction of the form
`go docs/spec/spec-vN.md`. Each spec opens with an Execution contract: repo
root, tests-first implementation order, acceptance gates verbatim, at most 5
repair-and-rerun cycles, report or blocker template at the end. Prompts are
logged under `docs/prompts/`, tokens/cost appended to `docs/llm-usage.md`.
From v1.2 on, a repair cycle only counts once a fix is followed by a complete
re-run of every gate from the first — bugs found and fixed during test-first
development, before that gate sequence starts, do not debit the budget.

## Acceptance gates (from the v1.2 spec, verbatim)

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
uv run --locked python devtools/mutation_check.py
```

Gates 1–4 are unconditional and offline. Gate 5 needs the live environment
(a provisioned `.env`, a reachable Docker daemon with the sandbox image
pulled, LM Studio and an OpenRouter key). Gate 6, added in v1.2, is the
custom stdlib-only mutation-testing gate: it reruns the full test suite once
per mutation entry (currently 31) and fails if any mutation survives, errors,
or drifts from its expected single occurrence in the source.

## Key design decisions (fixed across the specs)

- Plain Telegram Bot API long polling over httpx — no bot framework; Linux.
- Swappable inference plugin: `llm/lmstudio.py` + `llm/openrouter.py`
  (OpenAI-compatible chat-completions), selected via `LLM_PROVIDER`, with
  failover between them from v1.
- Hard budgets per user message: ≤8 logical rounds, ≤9 HTTP attempts
  (shared pool), ≤12 tool executions; round 8 exposes no tools.
- `exec(argv)` runs inside a disposable Docker container (from v1 on):
  `--network none`, non-root user, read-only root filesystem, capped tmpfs,
  dropped capabilities, `no-new-privileges`, a tri-state disk-quota scan that
  fails closed, and an empty read-only `/etc/resolv.conf` mount so the
  sandbox learns nothing about host DNS.
- Storage: conversations / messages (with `turn_id`, `tool_calls_json` +
  `json_valid` CHECK) / `bot_state` for the polling cursor / `summaries`
  (schema v2, v1) for long-conversation compression; at-most-once delivery
  semantics; context window of 30 messages selected as whole turn groups,
  token-budget-aware from v1.
- Secrets are registered at config load and redacted everywhere output can
  reach the model, storage or Telegram; a stream-truncation headroom plus a
  trailing-fragment stripper (v1.1) keep a secret from leaking half of itself
  across a byte cap.
- The fetch tool enforces a three-layer SSRF-resistant domain allowlist
  (v1.2): strict syntax validation at config load, one-time DNS resolution at
  startup, and a per-request resolution check before every hop including
  redirects.
- Tests are provably offline: FakeLLM, injected HTTP transport, injected
  command runner, an autouse DNS guard that fails any un-stubbed lookup;
  deterministic `--selftest`. `devtools/mutation_check.py` (v1.2) verifies the
  test suite itself actually kills the regressions its tests claim to guard.

## v1.3 (next)

Token economy for the agent's own code — folds in course assignment 5 (AI
Agent Token Audit; assignment text: `base/assignments/05-agent-token-audit.md`
in the lab repo, not this repo).

**Order matters, and the spec must enforce it in this sequence:**

1. **Observability/measurement layer first** — instrument LLM calls and tool
   calls (tokens in/out/cached/reasoning, latency, cost, per-turn breakdown)
   *before* anything else, so it establishes the "before" baseline that every
   later claim is measured against.
2. **Audit** — using that instrumentation, identify the token sinks (most
   expensive tools/turns, fastest-growing context category, how much input is
   re-sent context the model already saw).
3. **≥3 optimizations**, implemented and benchmarked against the same
   instrumentation, only after 1 and 2.

**Targets:** cost per task **−30% minimum** vs. the measured baseline;
success-rate drop **≤2 percentage points**.

**Deliverables:** dashboard (token/cost aggregates + per-run timeline) +
before/after report + PR with the implemented optimizations.

**Carry-over from the v1.2 audits, to fold into the v1.3 spec:**

- Startup-cleanup chmod-through-symlink fix (MEDIUM: `islink`-skip in
  `_remove_sandbox_entry`).
- Coverage tests for `owner=owner_key()` binding, `resolve`'s late binding,
  the `OSError`-only path in `resolve_host`, and the INF-01 uid+nlink+
  `O_NONBLOCK` clauses.
- README fixes: layer-2 refusal wording, the reap description, the
  entries-eat-disk note.
- `mutation_check.py --only` typo should exit 1, not silently no-op.
- chmod-000 test tmp-dir hygiene (wrap in try/finally).
- `docs/llm-usage.md`'s v1.2 row: replace "not computed" with the measured
  figure, ≈$33.11, from a local transcript.
- Assorted plan/report wording fixes.
