# Handoff — v1.10.0, ready for `go`

What the `go` session reads first. Authored 2026-09-13 in the lab session;
the run happens in a different session (`standards/workflow.md` §14).

## The `go` line

```text
go docs/spec/spec-v1.10.0.md
```

No operator input is required (REQ-V1100-EC-05 after lab amendment A1):
the judge route resolves from a `LLM_JUDGE_MODEL=…` line in the request
text if one is given, otherwise from `.env`. **The defaults were chosen and
written by the lab on 2026-09-13:**

| Role | Value | Where it lives | Why |
|---|---|---|---|
| Model under test | `lmstudio` / `qwen/qwen3.8-27b` (the production chat route) | `.env` `LLM_PROVIDER`, `LMSTUDIO_MODEL`, `LMSTUDIO_BASE_URL=http://192.168.0.145:1234/v1` (live and loaded on 2026-09-13) | the spec tests the deployed route, not a fixed model; the report records the actual `describe()` pair |
| Judge | `openrouter:openai/gpt-4.1` | `.env` `LLM_JUDGE_MODEL` (written), `.env.example` default line (T3 writes it), README/AGENTS env lines | GA, no reasoning mode (the protocol sends `reasoning=off`), structured outputs supported on OpenRouter, stronger than a 27B, $2/$8 per Mtok — five judge calls cost under a cent |
| Judge fallback | `openrouter:openai/gpt-5.6-sol` | Stage 0 rule 5 of amendment A1 | only on a `response_format`/schema rejection at Stage 0 check 4; recorded in `## Operator inputs` |

The judge must be **different** from the chat model — the runner refuses
equality (`describe()` inequality); "stronger" is the lab's choice above.
Preconditions: `.env`'s `LMSTUDIO_BASE_URL` points at the box's **current**
address (probe the three known addresses first, memory
`reference-lmstudio-endpoints`), the chat model named by `LMSTUDIO_MODEL`
is loaded, and `OPENROUTER_API_KEY` is set for the judge route.

Live work this release needs (everything else is offline against fakes):
gate 5 (`--selftest-live`), gate 7 (`rag-eval`), T0's five preflight checks
(judge line present → `/models` lists the chat model → one plain chat turn
timed → one strict-schema judge call → `uv lock` no-op), and **gate 8
(`agent-eval`) exactly once, at the end of T9** — 23 bot turns on the
production route, 5 judge calls, 5 streaming TTFT probes. An unreachable
box or judge route is a **blocked run** under the stop route, never a
repair cycle. A red gate 8 caused by model behaviour (a level-2 case or the
judge mean) is Stage B′: report, no bump, no tag — no live case is ever
rerun.

**Timing to expect.** The chat model on the box is a reasoning-class model
measured at 100–200 s per turn in gate 7's smoke; gate 8's expected
wall-clock is roughly 23 × t_turn plus judge and probe time — order of one
to two hours. Its `timeout_seconds` is computed at T0 as
`ceil_to_100(1.5 × 219 × t_turn)` (219 = 23 × `HTTP_ATTEMPT_LIMIT` + 12,
floor 1800, no cap — a hang guard, not an estimate). Gates 6, 7 and 8 never
run concurrently (one box).

## Models and effort

- **Executor: `claude-sonnet-5`**, orchestrator effort high, subagents
  default (`standards/workflow.md` §3; sonnet-5 executed v1.5–v1.9.5 end to
  end in this repository). Escalation rule as before: if a single task burns
  two of the four repair cycles, stop and hand off rather than continue.
- **Reviewer:** the project's `code-reviewer` subagent as pinned
  (`.claude/agents/code-reviewer.md:4`, `sonnet`), clean context, after
  implementation (REV-01); the operator has used `claude-opus-5` for the
  v1.9.x patch reviews — override at `go` time is the operator's call, not
  the spec's.
- Every source-writing task is delegated and briefed by
  `docs/spec/task-briefs/v1100-T<n>.md`, written by the orchestrator
  before dispatch (REQ-V1100-EC-07; §16.1's `delegate` column). T0 and T11
  stay in the main context under the *artefacts only* / *commands only*
  exemptions.

## What it is

Course assignment 7 (`base/assignments/07-agent-test-suite.md`, issued at
lecture 10 on 2026-09-11) in full: a test suite for the agent's core, not
the Telegram interface, in three levels —

1. **Deterministic / contract (offline pytest):** whitespace-only input,
   the inbound cap counted in UTF-16 units like the outbound split,
   redact-before-split at every `split_message` call site, the plain-text
   outbound pin (no `parse_mode`, ever — MarkdownV2 escaping is satisfied
   by design and pinned by test), the tool-call argument coercion and the
   four `execute_tool` envelopes.
2. **Red team (dataset + parametrised offline test + live gate):**
   `evals/agent/red_team.json`, 12 cases — 5 prompt-injection (one in
   English), 4 hallucination (`HAL-01` law article, `HAL-02` person,
   `HAL-03` product version, `HAL-04` the Amsterdam/Germany false premise),
   3 multi-turn memory with a storage-level reset; deterministic checkers
   with committed marker lists, per-step fixtures, `validate_datasets()`
   before any live call; floors 5/5, ≥3/4, 3/3.
3. **LLM-as-a-judge + latency (live gate):** 5 open Russian questions with
   reference answers, a strict JSON-schema judge protocol (politeness,
   accuracy, conciseness; mean of 15 scores ≥ 0.8, blocking; the judge input
   is a JSON object of untrusted fields); latency RTT per turn and TTFT via
   a streaming re-post of the recorded request (LM Studio route only) —
   **advisory**, thresholds 4.0 s / 1.5 s reported, never blocking.

All of it with **zero new dependencies** (the lecturer asked for
hand-written tests; no `deepeval`). One new runner
`devtools/agent_eval.py` = gate 8 `agent-eval` in the `full` profile, exit
contract 0/1/2 like gate 7. One new config key `LLM_JUDGE_MODEL`
(`purpose="judge"` in `build_llm_client`). Version **1.10.0**, MINOR.

## Frozen decisions the run must not reopen (D1–D18 of the authoring brief)

The brief lives in the lab job directory (not in this repository); the
spec encodes every decision. The ones an executor is most tempted to
revisit:

- **Gate 3 stays offline.** `tests/conftest.py` bans the network; no live
  test is ever a pytest test. Everything live is `devtools/agent_eval.py`.
- **Gate 8 runs once per tree state**: T5 is offline-only; T9 records
  `tested_tree` and runs gate 8 last; T11 reuses that result after the
  dependency-identity check (`GATE8_DEPENDENCIES`, version-only exception
  for `pyproject.toml`/`uv.lock`), or re-runs once. `checks.py run
  --profile full` is never issued as a whole.
- **No retry of a live case, ever.** A failed case is a failed case; an
  `LLMError`/timeout is exit 2.
- **The reset is storage-level** (`storage.start_new_conversation`, the
  call `_handle_new` ends with); the goals carry-over (`GOALS_BLOCK` from
  the `/new` summary) is a NON-GOAL and unchanged. The offline test pins
  that after a full `/new` the next request carries no pre-reset
  user/assistant message.
- **Latency is advisory** on this instrument; the judge mean is blocking.
- **No change** to the system prompt, tool descriptions, tool schema,
  gate 5, gate 7, the summary mechanism or the Telegram transport — the
  benchmark rule does not fire.

## Repository facts folded in during authoring

Three read-only reconnaissance passes established the baseline the spec
cites (every citation audited: 240 checked, 23 corrected):

- Replies are sent as plain text — `bot.py:226-227`'s payload is
  `{"chat_id", "text"}`; no `parse_mode`, no escape function exists.
  Inbound: whitespace-only → `NON_TEXT_REPLY` (`bot.py:873-876`); cap
  `MAX_MESSAGE_CHARS = 4000` in code points (`bot.py:877-880`) while
  `split_message` counts UTF-16 units (`bot.py:287-303`); the agent reply is
  split before `_send` redacts each part (`bot.py:993` → `:1494`).
- Tool arguments: `execute_tool` never raises (`tools.py:1397-1409`);
  `parse_response` coerces object-valued/missing `arguments`
  (`llm/base.py:358-377`); the rerank JSON contract is the v1.9.1 precedent
  (`rag.py:148-200`).
- Memory: 30-message window + token-budget eviction, summary only on
  `/new`/`/summary`; no inactivity timeout exists; documents are keyed on
  `user_id` and survive `/new` by schema (`storage.py:203`).
- Guardrails on the reply: prompt-level only; `config.redact` masks exactly
  two registered values (`config.py:327`, `:355`); the sole injection test
  (`tests/test_v1_guardrails.py:829`) never runs a turn under injection.
- No streaming, no TTFT anywhere (`llm/base.py:201` `stream: False`);
  per-call latency is the `latency_ms` column (`agent.py:1000-1001`).
- Gate 7 (`devtools/rag_eval.py:700-781`) is the live-gate precedent:
  no CLI flags, thresholds in the script, exit 0/1/2, `full` profile only,
  advisory smoke never touches the exit code.
- 120 mutation entries (five-key dicts), 1638 collected tests, seven gates,
  `deepeval`/`tabulate`/`ollama` absent.

## State

- Spec: `docs/spec/spec-v1.10.0.md`, 166,464 bytes (the brief's 110 KB cap
  was overshot by the review rounds; growth is normative content, recorded
  in Appendix C).
- 45 MUST (EC 7, SAN 2, OUT 2, TC 1, CFG 1, RT 6, RUN 3, JDG 4, LAT 3,
  ERR 1, SEC 1, TST 1, GATE 3, EVAL 1, VER 1, RPT 4, REV 4) · 11 NON-GOAL ·
  12 tasks (T0–T11) · 60 `T-V1100-*` test ids (20 negative) · 7 mutation
  entries (`mutation-all` becomes 127) · 15 Gherkin scenarios · 1 new
  config key. Appendix A is a verified bijection in both directions.
- Ten of twelve tasks are delegated in §16.1's reading map (T0 *commands
  only*, T11 *artefacts only*).
- Commits: `8f333f2` (draft, citations audited 240/23, six audit
  contradictions applied), `6b81e2a` (round 1), `116b265` (round 2),
  `2311834` (round 3). Authoring prompt:
  `docs/prompts/191-v1100-spec-authoring.md`. The run's own prompts start
  at **192**; `docs/llm-usage.md` continues at row 102.
- `[[VERIFY: …]]` markers: **2**, each with its decision rule — §9 LAT-02
  (which SSE delta key LM Studio streams for reasoning: `reasoning_content`
  or `reasoning`; the probe accepts either, else `ttft: n/a`, no repair
  cycle) and §13 EVAL-01 (T0's plain chat turn > `cfg.llm_timeout_s` →
  blocked run, never a repair cycle).

## Cross-review

Three rounds against OpenAI Codex `gpt-5.6-sol`. **28 findings, 28 accepted
(11 adapted), 0 rejected outright** — round-2 finding 1's proposed fix
(drop the English injection case) was rejected in substance and the rule
adapted: `INJ-02` stays as the single stated exception to "texts in
Russian". Termination is **`round_limit`**: round 3 still returned 1
Critical (`JUDGE_MAX_TOKENS` missing from the protocol block) and 4 High,
all applied. **Residual findings may exist.** Appendix C carries the full
log and every rationale.

Two operator-visible consequences worth knowing before `go`: gate 8 costs
one to two hours of box inference and runs once at T9 (a second time only
if T11's dependency diff is not version-only); and the judge mean ≥ 0.8 is
a **blocking** metric — a verbose chat model turns the release red through
the stop route, by design.

## Lab amendment A1 (2026-09-13, after the rounds closed)

The operator asked the lab to choose the models and write the defaults.
Judge `openrouter:openai/gpt-4.1` (fallback `openrouter:openai/gpt-5.6-sol`
on a schema rejection at Stage 0), model under test = the production route
`qwen/qwen3.8-27b`; `.env` carries the judge line; the `go` request needs
no input; Stage 0 check 1 verifies the resolved route and its inequality
with the chat model. Recorded in the spec's Appendix C as amendment A1.
