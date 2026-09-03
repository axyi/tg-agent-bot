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
| `docs/spec/spec-v1.3.md` + implementation | done — token economy (assignment 5): observability layer, benchmark harness and dashboard, the baseline token audit, six optimizations O1–O6. Four commits, six gates green at C1 and C3, 719 tests, 65/65 mutations killed, two clean-context reviews. **Benchmark verdict: FAIL** — cost per successful task $0.002687 → $0.002492 (−7.3 %, target −30 %), success rate 100.0 % → 94.4 % (−5.6 pp, budget −2 pp). Prompt tokens −18.1 %, tool output −31.3 %, median latency −36.7 %. See `docs/reports/report-v1.3.md` |
| `docs/spec/spec-v1.4.md` + implementation | done — patch release: a bounded spike (RSN-01…06) tried all five candidate reasoning-off mechanisms LM Studio might honor, live, in strict order. **None both honored and shippable — verdict FAIL, cause: no honored reasoning mechanism (RSN-06 STOP).** `a` (`chat_template_kwargs.enable_thinking`) and `d` (Qwen3 `/no_think`) not honored; `b` (`reasoning.effort`) unsupported (LM Studio never documents a disable value); `c` (empty `<think>` prefill) honored 3/3 but rejected — breaks the byte-stable cached-prefix invariant (POL-05); `e` (an LM Studio GUI/`lms` CLI default) has no documented control for the running version at all. Per RSN-06/GATE-02, sections 6–7 (policy + observability) and candidate benchmarking are declared not-executed. Still delivered: the S01 check repair (H1 — the check measured phrasing, not capability), a fresh `baseline-v1.4` ($0.003009/success), REL-01 (the `LLM_TIMEOUT_S`/`LLM_MAX_TOKENS` consistency check, default 120→240), mutation coverage for the shipped code (68/68 killed), and a code review with two real, fixed findings. 11 commits, six gates green at every commit (2 of 5 repair cycles consumed — T6, T9), 728 tests (+9 over v1.3). Numbers come from `baseline-v1.4.json`/`docs/reports/report-v1.4.md` — `docs/reports/bench-v1.4.md` does not exist on this branch (it is `report --gate --candidate`'s output, and no candidate was ever produced). See `docs/reports/report-v1.4.md` |

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
per mutation entry (65 as of v1.3) and fails if any mutation survives, errors,
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

## v1.3 (done) — spec: `docs/spec/spec-v1.3.md`, report: `docs/reports/report-v1.3.md`

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
success-rate drop **≤2 percentage points**. **Neither was met** — the
benchmark verdict is FAIL and both gates failed:

| metric | baseline | optimized | target | result |
|---|---|---|---|---|
| cost per successful task (ESTIMATE, `reference:qwen/qwen3.8-27b`) | $0.002687 | $0.002492 | ≤ $0.001881 | **−7.3 %**, FAIL |
| success rate | 1.0000 (36/36) | 0.9444 (34/36) | ≥ −2 pp, and no scenario may lose a repeat net | **−5.6 pp**, S01 3/3 → 1/3, FAIL |
| prompt tokens | 126 109 | 103 236 | — | −18.1 % |
| tool output tokens | 13 116 | 9 014 | — | −31.3 % |
| median latency per call | 35 158 ms | 18 198 ms | — | −36.7 % |

**Why:** the audit's largest lever — reasoning, 71.8 % of all completion
tokens, ≈29 % of run cost — proved unavailable. LM Studio documents no
`chat_template_kwargs` passthrough and does not honour Qwen3's `/no_think`
soft switch; the bounded probe measured a 0.7373 reasoning share with the
directive in place, so O5 ended in the state `attempted_removed` (the knob is
not in the tree). The four input-side optimizations that remained cannot carry
a −30 % target on their own: output tokens are billed 6× input and are 48.2 %
of the optimized run's cost, so with the completion side untouched the input
side alone would have had to fall to ~54 k tokens, −57 % below the baseline.
Full analysis: `docs/reports/report-v1.3.md`.

**Deliverables:** dashboard (token/cost aggregates + per-run timeline) +
before/after report + PR with the implemented optimizations — all delivered
(`docs/assets/dashboard-v1.3.html`, `docs/reports/bench-v1.3.md`,
`docs/reports/report-v1.3.md`, commits `69ebc75`, `f0572c8`, `c11f590` and the
C4 documentation commit).

**Carry-over from the v1.2 audits — all folded into spec-v1.3 §5 and delivered
in C1 (`69ebc75`), including the `docs/llm-usage.md` v1.2 cost cell, which now
reads ≈$33.11:**

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

## v1.4 (done) — spec: `docs/spec/spec-v1.4.md`, report: `docs/reports/report-v1.4.md`

A bounded spike (lever 1 of v1.3's discovered list, below): does any
per-request mechanism exist that makes LM Studio actually honor a
"stop thinking" request, and can it ship without breaking the cached
prefix invariant? All five candidates the spec named were tried, live,
in strict order (RSN-01…06):

| candidate | mechanism | outcome |
|---|---|---|
| a | `chat_template_kwargs.enable_thinking=false` | not honored (2/2 live pairs) |
| b | vendor-documented `reasoning`/`reasoning_effort` disable value | unsupported — LM Studio documents only `low\|medium\|high`, never a disable value, never for a Qwen3-class model |
| c | assistant prefill of an empty `<think>` block | honored (3/3), but rejected — always breaks the byte-stable cached-prefix invariant |
| d | Qwen3's `/no_think` soft switch | not honored (2/2 live pairs) |
| e | an LM Studio GUI/`lms` CLI model-level default | no documented control exists for the running version at all |

**Verdict: FAIL, cause: no honored reasoning mechanism (RSN-06 STOP).**
No optimization commit ships; the policy/observability sections and any
candidate benchmark run are declared not-executed by the spec's own
STOP-branch rule (GATE-02). Lever 1 (below) is **tried and closed**, not
untried — reopening it needs either a different LM Studio version or a
different model, not a different mechanism at this one.

**What still shipped on this branch:** the S01 benchmark check's false
negative repaired (H1 — the check matched literal tokens, not
capability); a fresh `baseline-v1.4` measured via a temporary `git
worktree` against the pre-v1.4 code ($0.003009/success); lever 5 (below)
fixed — `LLM_TIMEOUT_S`/`LLM_MAX_TOKENS` can no longer silently disagree
(default 120→240); mutation coverage for everything actually shipped
(68/68 killed); one code review with two real, fixed findings. 11
commits, six gates green at every commit (2 of the 5-cycle repair
budget consumed — T6, T9; see report's Fix cycles), 728 tests. Full
detail: `docs/reports/report-v1.4.md`.

## v1.5 (next) — candidates, none applied

Two groups. The first is the plan's standing list; the second is what the
v1.3 run discovered, minus the two levers v1.4 closed (lever 1: tried,
FAIL — see above; lever 5: fixed, REL-01). Every one of them changes
either the measured treatment or the scenario set, so each costs a fresh
baseline before any comparison with v1.3's or v1.4's files is meaningful.

**Standing candidates (from the v1.3 spec's deliverables list):**

- **Tokenizer-accurate context budget** — the v1.3 budget is char-based; a real
  tokenizer would let the window be sized to the model's actual limit instead
  of a conservative approximation.
- **Routing enabled when a second model is available** — O6 ships tested but
  configuration-only, because one model at a time fits the GPU box. Enabling it
  is a one-variable change with a computed ceiling (below).
- **Streaming** — not implemented; would cut perceived latency, not tokens.
- **Semantic cache** — only if a dependency is ever allowed; today the
  dependency list forbids it, and it stays a NON-GOAL.

**Discovered by the v1.3 run, ranked by expected effect (levers 1 and 5
removed — closed by v1.4, above):**

1. **Enable O6 routing** (summaries to a cheap or non-reasoning model) —
   ceiling **−4.6 %** ($0.003904 on 762 prompt + 1 404 completion tokens), and
   it also cuts the slowest call type (summary median 49 179 ms vs 17 536 ms
   for agent calls). Needs a second model.
2. **`CONTEXT_WINDOW_MESSAGES` 30 → 20** — upper bound −4.7 %, realistically
   ~0 on the current scenario set: the longest conversation (S09) never
   reaches 20 messages, so the cut binds on nothing. Needs a
   longer-conversation scenario, and carries a direct quality risk.
3. **`EXEC_OUTPUT_DEFAULT_CHARS` 1500 → 1000** — upper bound −1.1 % (`exec` is
   76 % of tool output; a third narrower window removes at most a third of it).
   Trades against the quality gate that already failed.
4. **`FETCH_INLINE_DEFAULT_CHARS` 5000 → 3000** — ≈0 on the current scenario
   set: S08's fetch output already sits under the 5 000-char window.

(Lever 6, the reasoning-starved-summary fragility, is not listed as
untried here: v1.4 specified its fix in full — REL-02, the
`FINISH-LENGTH:` assertion — but it never shipped, released on the
RSN-06 STOP branch, since it only matters for a candidate run under a
policy, and no policy exists to run one under. It is listed among
`docs/reports/report-v1.4.md`'s released requirements, not carried here
as a performance candidate.)
