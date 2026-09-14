# tg-agent-bot v1.10.0 -- report skeleton (T0)

Assignment 7 in full: a test suite for the agent's core, in three levels
(deterministic/contract, red-team, judge+latency), implemented as offline
`pytest` additions plus one new live gate, `devtools/agent_eval.py`
(gate 8, `agent-eval`). Spec: `docs/spec/spec-v1.10.0.md`. Base: `c84d739`
(tag `v1.9.5` at the same commit lineage; `<base>` for `replay --range` is
`c84d739`, current `HEAD` before this run's first commit — the spec
header's `a3e0a93` is stale, superseded by the four spec-authoring commits
that landed after it; `T-V1100-EC-01` compares against the `v1.9.5` **tag**
blob, unaffected by this correction).

This file is filled progressively: T0 (this skeleton), T4 (dataset
`sha256`s), T9 (the one live gate-8 run and its tables), T10 (version bump,
provisional report), T11 (final evidence-only commit). Sections not yet
reached read "not reached: T<n>".

## T0 — preflight

`<base>` = `c84d739`. Spec `sha256`:
`9023da66f8cc1ec70054f88ef62f03bde27bc5905964ebef14b44ed1d022a303`.

### Stage 0 — five checks, in order

1. **Judge route resolved and distinct.** `LLM_JUDGE_MODEL` is not yet a
   `Config` field (CFG-01 lands T3) and `build_llm_client` has no
   `purpose="judge"` branch yet (also T3) — resolved on the unchanged tree
   by reading the raw `LLM_JUDGE_MODEL` value through `parse_routed_model`
   and constructing the routed client directly via `llm._client_for`, the
   same primitives T3 wires into `build_llm_client`. Value:
   `openrouter:openai/gpt-4.1`, source **`.env`** (no `go`-request line).
   `judge.describe() = ('openrouter', 'openai/gpt-4.1')`,
   `chat.describe() = ('lmstudio', 'qwen/qwen3.8-27b')` — distinct. PASS.
2. **`GET {LMSTUDIO_BASE_URL}/models` lists `LMSTUDIO_MODEL`.** `qwen/qwen3.8-27b`
   present among 16 models listed. PASS.
3. **One timed plain chat turn on the production route.** Question
   «Ответь одним словом: столица Нидерландов?», reply `"\n\nАмстердам"`,
   elapsed **24.90s** (well under `cfg.llm_timeout_s` = 600s). PASS.
   `t_turn = 24.90s`.
4. **One strict-schema judge call**, §8's two labelled spec-block fences
   (`judge-protocol-1`, `judge-protocol-2`) copied verbatim into a heredoc,
   on the fixed sample (question/reference/reply as REV-04 Stage 0 specifies).
   `openai/gpt-4.1` accepted `response_format` on the first attempt — **no
   fallback to `gpt-5.6-sol` was needed**. Parsed reply:
   `{"politeness": 1, "accuracy": 1, "conciseness": 1, "reason": "Ответ
   вежливый, точный и краткий. Указана правильная столица без лишней
   информации."}`. `describe()` pairs as in check 1, unequal. PASS.
5. **`uv lock` no-op.** `uv lock` on the unchanged tree, then
   `git diff --exit-code -- uv.lock`: empty diff. PASS.

No Stage 0 blocker. The run proceeds past T0.

### EVAL-01 timeout computation

`R = HTTP_ATTEMPT_LIMIT = 9` (`agent.py:45`); `max_calls = 23 * 9 + 12 = 219`;
`t_turn = 24.90s` (check 3); `timeout_seconds = ceil_to_100(1.5 * 219 * 24.90)
= ceil_to_100(8179.65) = 8200`, floor 1800, no cap → **`agent-eval.timeout_seconds
= 8200`** (T6 writes this into `config/quality_gates.yaml`).

### Gates 1-7 on the unchanged tree (gate 8 n/a — script does not exist yet)

Nothing else on the box during gate 6; gate 6 and gate 7 not run
concurrently.

| # | Gate | Exit | Wall |
| --- | --- | --- | --- |
| 1 | `uv sync --locked` | 0 | ~0.9s (resolve) |
| 2 | `ruff check .` | 0 | fast, all checks passed |
| 3 | `pytest` | 0 | 1638 collected (re-measured floor, matches recorded baseline) |
| 4 | `bot.py --selftest` | 0 | `selftest: OK` |
| 5 | `bot.py --selftest-live` | 0 | all seven live checks OK, including `lmstudio` |
| 6 | `mutation_check.py` (no `--select`) | 0 | 120/120 killed, 0 survived/errored/drifted |
| 7 | `rag_eval.py` | 0 | hybrid recall@5=1.000, hybrid+rerank recall@5=1.000, PASS; advisory conversation-aware smoke -- TOOL-06 pin: pass, context-proof: pass (gold source `vacation_policy.md` returned) |
| 8 | `agent_eval.py` | n/a | script does not exist yet |

`doctor`: `[PASS] doctor: all tools at pin, hooks installed`. Hooks:
`install_hooks.py --check`: `hooks installed correctly`.

### Delegation record (T0)

T0 -- not delegated -- *commands only* (EC-04's exemption: the five Stage 0
checks and the seven gates are commands whose redacted output goes into
this skeleton; the skeleton, the prompt file and the ledger block are prose
no gate compiles, imports or runs). Executor model: `claude-sonnet-5`.

### Disclosure -- a transient false positive during gate 6

Mid-gate-6, an automated background security-review plugin flagged an
apparent SSRF regression in `tools.py` (the `_check_resolved_scope` guard
"removed"). Investigated immediately: `mutation_check.py` was actively
mid-cycle on its `v12-...` PID-reuse mutation (`_process_start_ticks`,
`devtools/mutation_check.py:253`), which mutates the tracked file in place
before reverting it (documented pre-existing behaviour). `git diff` at the
time showed only that mutation's edit, not the SSRF guard; `_check_resolved_scope`
was present and called at both of its call sites throughout. No SSRF
regression occurred; the tree was clean (`git status --porcelain` empty)
once gate 6 finished with 120/120 killed.

## Operator inputs

- **Resolved `LLM_JUDGE_MODEL`:** `openrouter:openai/gpt-4.1`
- **Source:** `.env` (the `go` request carried no `LLM_JUDGE_MODEL=` line)
- **Chat client `describe()`:** `('lmstudio', 'qwen/qwen3.8-27b')` (expected pair per lab amendment A1, confirmed)
- **Judge client `describe()`:** `('openrouter', 'openai/gpt-4.1')`
- **Stage 0 check-4 fallback used:** no

## T1 — inbound sanitisation and outbound text

Contract: `docs/spec/task-briefs/v1100-T1.md`, prompt 193. Delegated —
executor `claude-sonnet-5` (general-purpose subagent). Commit `a3b3f8a`.

`bot.py` gains `utf16_length()` (`:305-307`) and `reply_parts()` (`:310-312`,
`split_message(redact(text))`); the inbound cap (`:887`) now compares
`utf16_length(text) > MAX_MESSAGE_CHARS`; all five `split_message(` call
sites (`:911`, `:927`, `:1003`, `:1082`, `:1484`) now call `reply_parts(`.
`split_message(` occurs exactly twice in the final source (its own `def`
and inside `reply_parts`). New file `tests/test_v1100_sanitization.py`, 13
tests covering `T-V1100-SAN-01…03`, `T-V1100-OUT-01…03`, including a
boundary-straddling regression test empirically verified against a
`split_message(text)`-instead-of-`redact`-first mutation. Gates 1–4: all
exit 0 (pytest 1650 passed/1 skipped); `tests/test_v1_guardrails.py:556,
:571` and `tests/test_telegram.py:223` stay green, unamended.

**Finding carried to T7 (not a defect, a mutation-table correction):** the
delegate found that mutation `v1100-reply-parts-split-before-redact`'s
spec-table killer (`T-V1100-OUT-02`) does not actually kill it in isolation
— `agent.py:366`'s `finish()` already redacts the agent-reply path before
`bot.py` ever splits it, so `T-V1100-OUT-02`'s scenario passes unchanged
under that mutation. The mutation is killed by the new `T-V1100-OUT-01`
boundary-straddling test instead. T7 must verify the real killer
empirically when authoring the entry (GATE-02 already requires this) and
should record `T-V1100-OUT-01` as the killer of record, not `-OUT-02`.

## T2 — outbound payload pin and the tool-call wire contract

Contract: `docs/spec/task-briefs/v1100-T2.md`, prompt 194. Delegated —
executor `claude-sonnet-5` (general-purpose subagent). Commit `fc88cdb`.
No production source changed (`git diff --stat` against the parent
touched only `tests/test_v1100_sanitization.py` and the new
`tests/test_v1100_toolcall.py`) — OUT-02 and TC-01 were already-correct
behaviour, pinned by 13 new tests (`T-V1100-OUT-04`, `-05`,
`T-V1100-TC-01…03`). Gates 1–4: all exit 0 (pytest 1663 passed/1 skipped).
First commit attempt was rejected by the `ruff-format-all` pre-commit
gate; fixed with `ruff format` on the two touched files (never
`--no-verify`) and re-committed fresh (no amend by the delegate — correct
per policy; the orchestrator then folded in this task's brief/prompt
files with one local amend, unpushed).

## T3 — the judge route configuration

Contract: `docs/spec/task-briefs/v1100-T3.md`, prompt 195. Delegated —
executor `claude-sonnet-5` (general-purpose subagent). Commit `b74a358`.
`Config.llm_judge_model` (`config.py:150-155`, default `""`), the
`LLM_JUDGE_MODEL` routing/validation block in `load_config`
(`config.py:429-446`, the exact `ConfigError` text
`"LLM_JUDGE_MODEL routes the judge to <provider>, which is not
configured"`), a `purpose == "judge"` branch in `llm.build_llm_client`
(`llm/__init__.py:64-68`, after `eval-chat`, identical shape, unset falls
through to the main client), and `.env.example:98-102` (the uncommented
default `LLM_JUDGE_MODEL=openrouter:openai/gpt-4.1`, `LLM_RERANK_MODEL`'s
convention, not `LLM_EVAL_CHAT_MODEL`'s commented-out one). New
`tests/test_v1100_config.py`, 12 tests (`T-V1100-CFG-01…04`). Gates 1–4
all exit 0. The real `.env` was never opened (confirmed gitignored,
absent from every diff). First commit attempt bounced on
`ruff-format-all`; fixed with `ruff format` on the one touched test file,
recommitted fresh.

## T4 — the red-team dataset and the checkers

Contract: `docs/spec/task-briefs/v1100-T4.md`, prompt 196. Delegated —
executor `claude-sonnet-5` (general-purpose subagent). Commit `7cbac85`.

New `devtools/agent_eval.py` (checkers and validation only, no runner yet
— imports cleanly): `INJ_MARKERS`, `HAL_MARKERS`, `ENV_KEY_NAMES`,
`check_injection`, `check_hallucination`, `check_memory_recall`,
`check_memory_reset`, `check_step`, `DatasetError`, `validate_datasets`.
New `evals/agent/red_team.json` (12 cases: `INJ-01…05`, `HAL-01…04`,
`MEM-01…03` — `INJ-04` is the env-name attack) and
`evals/agent/judge_questions.json` (5 questions). New
`tests/test_v1100_red_team.py`, 78 tests (≥ 30 parametrised over the
fifteen checked steps, plus dataset-shape and RT-03 worked-example pins).
Gates 1–4 all exit 0; the orchestrator independently re-ran
`tests/test_v1100_red_team.py` and spot-checked the canonical texts
(`INJ-01`, `MEM-01`'s four steps, the `HAL` id mapping) directly against
the committed JSON — all byte-exact.

**Dataset freeze (REV-02), recorded before any live gate-8 run ever
happens:**

```
adf6dcb52f6d1cc088085ce176cd8c0c7edc88fc0e926c2f0c9dca12ee6b35b4  evals/agent/red_team.json
71143395a92002bd063b8fdf6be36b44c80fb5a1863cf3ff4b18ca4d501cdf9c  evals/agent/judge_questions.json
```

**Design note carried to T8 (review), not a defect:** `check_memory_reset`
gained an additive, optional `question: str | None = None` keyword — when
supplied alongside `request_messages`, it also verifies the post-reset
user message *starts with* the post-reset question text (RT-04 clause (i)
in full); the default (unset, what `check_step`/`validate_datasets` use)
preserves the role-sequence-only check the spec's signature describes. The
env-name-attack case (`INJ-04`) names all three `ENV_KEY_NAMES` keys rather
than just one, so its `none_of` guard is exercised more strongly. T8's
review should confirm both are backward-compatible with the spec's stated
signature and intent, not silent scope creep.

## T5 — the gate-8 runner, offline

Contract: `docs/spec/task-briefs/v1100-T5.md`, prompt 197. Delegated —
executor `claude-sonnet-5` (general-purpose subagent). Commit `f86dfb9`.

Extended `devtools/agent_eval.py` with the whole runner: `RequestRecorder`/
`probe_headers`/`ttft_probe` (LAT-02/-03), `RecordingLLM`/`_refusing_runner`
(RUN-02), the judge protocol between `# BEGIN/END SPEC JUDGE PROTOCOL`
markers (`devtools/agent_eval.py:911-969`) — **independently re-verified
byte-identical** by the orchestrator against
`/home/akh/.claude/jobs/bdd457e0/tmp/judge-protocol.py` (the exact text
extracted from the spec at T0, used unchanged since), `worst_case_calls`/
`gate8_timeout_seconds`/`GATE8_DEPENDENCIES`/`dependency_diff_is_version_only`,
and `run()`/`main()` with the full `--select`/`--print-dependencies`/error-matrix
contract. New `tests/test_v1100_runner.py`, 86 tests, entirely offline
(`httpx.MockTransport`, scripted fakes, injected clocks) — independently
re-run by the orchestrator, all green. Gates 1–4 all exit 0.

`pyproject.toml` gained one `ruff` per-file-ignore (`TRY004`) and one
`ruff format` exclude entry for `devtools/agent_eval.py`, mirroring the
existing `devtools/bench_scenarios.py` precedent exactly (a frozen
byte-exact source slice that a lint/format autofix would otherwise
corrupt) — reviewed and judged in-scope, not drift.

## T6 — gate 8 registration and documentation

Contract: `docs/spec/task-briefs/v1100-T6.md`, prompt 198. Executor
`claude-sonnet-5`, this commit.

Registered `agent-eval` (gate 8) in `config/quality_gates.yaml` immediately
after `rag-eval`, with T0's measured `timeout_seconds: 8200` (see T0's
EVAL-01 computation above) and membership in the `full` profile only.
Repointed `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
(`tests/test_v15_standards.py`) at `docs/spec/spec-v1.10.0.md`'s own gate
matrix (§13) and added the `agent_eval.py`/`mutation_check.py --select
v1100-` labels. Repointed `lint-docs`'s `report_path` to this file and
renamed/repointed `tests/test_v170_bench.py`'s
`test_t_v1100_rpt_01_lint_docs_repointed_to_this_release` accordingly;
added a structurally valid, all-`TBD` ledger row below (the same precedent
as v1.8.0 T0's disclosed erratum 3 and v1.9.0 T10) so `lint-docs` stays
green against this in-progress report from this commit on. Landed the
eight-gate command block in `AGENTS.md` and README's `## Tests`, and wrote
README's new `## Agent evaluation (gate 8)` section (RPT-04) with a
placeholder numbers table (T10 fills it from T9's run). New
`tests/test_v1100_gates.py`, 14 tests (`T-V1100-EVAL-01..03`). Gates 1–4,
`checks.py doctor` and `checks.py lint-docs` all green.

**Brief-vs-spec conflict found and resolved, disclosed here:** the task
brief's step 1 instructed adding `mutation-v1100` to the `mutation-subsets`
profile in this task, before T7 defines the `mutation-v1100` gate entry.
Doing so breaks `_validate_profiles` (`devtools/checks.py:541-554`, an
"unknown gate" error) the moment any test calls `load_gate_config()` —
which most of `tests/test_v15_standards.py`, `tests/test_v1100_gates.py`
and others do directly, not merely at collection time, contradicting the
brief's own stated assumption. Spec §13 (REQ-V1100-GATE-02) states the gate
entry and its `mutation-subsets` membership are **one requirement, both at
T7** — "its name is added to the `mutation-subsets` profile … so
`_validate_profiles` … stays green" only holds when both land together.
Resolution: did **not** add `mutation-v1100` to `mutation-subsets` in this
commit (left for T7); added
`test_mutation_v1100_membership_is_t7s_job_not_yet_landed` to
`tests/test_v1100_gates.py` pinning its current absence. Also found and
fixed one collateral break outside the brief's touch list:
`tests/test_v190_agents.py`'s
`test_t_v195_ec_01_quality_gates_yaml_repoints_report_path` pinned the old
`report-v1.9.5.md` string (the same per-release repoint-tracking pattern as
the `test_v170_bench.py` test the brief did name) — renamed to
`test_t_v1100_ec_01_...` and repointed at `report-v1.10.0.md`, disclosed
here rather than silently expanded in scope.

## T7 — mutation entries for gate 8's machinery

Contract: `docs/spec/task-briefs/v1100-T7.md`, prompt 199. Delegated —
executor `claude-sonnet-5` (general-purpose subagent). Commit `f0ff228`
(squashed by the orchestrator from two local, unpushed commits into one,
per "one prompt → one commit" — the delegate's second commit was a
legitimate follow-up fix discovered during its own verification, not
scope creep, so folding it in loses nothing).

Seven `v1100-*` entries added to `devtools/mutation_check.py`'s
`MUTATIONS`, each verified to kill **empirically** rather than by trusting
the spec's stated test id:

| id | actual killer | vs. spec |
|---|---|---|
| `v1100-injection-checker-always-passes` | `test_t_v1100_rt_05_validate_datasets_on_real_files` | matches (RT-05) |
| `v1100-hallucination-any-of-vacuous` | `test_t_v1100_rt_03_worked_examples_against_the_invented_law_case` | matches (RT-03) |
| `v1100-memory-structural-check-dropped` | `test_t_v1100_rt_04_pre_reset_assistant_message_fails_structurally` | matches (RT-04) |
| `v1100-judge-floor-zeroed` | `test_judge_runtime_constants` | **discrepancy** — spec said JDG-05 |
| `v1100-judge-guard-dropped` | `test_run_judge_equal_to_chat_model_exits_2` | matches (JDG-02) |
| `v1100-reply-parts-split-before-redact` | `test_t_v1100_out_01_redacts_a_registered_secret_before_splitting` | **discrepancy** — spec said OUT-02; confirms and refines T1's earlier finding on this same mutation |
| `v1100-inbound-cap-code-points` | `test_t_v1100_san_02_astral_boundary_rejected` | matches (SAN-02) |

`mutation-v1100` registered in `config/quality_gates.yaml` —
`timeout_seconds: 110`, measured from a clean `--select "v1100-"` run
(19.759s real → 2×19.759+70 = 109.5s → 110s) — and added to
`mutation-subsets`. `T-V1100-GATE-01` added to `tests/test_v1100_gates.py`.

**Shared-machinery fix, disclosed (not scope creep):** the delegate found
`default_runner`'s single `_SELF_CHECK_NODE_ID` exclusion needed widening
to a `_SELF_CHECK_NODE_IDS` tuple — `T-V1100-GATE-01`'s own find-string
bookkeeping test could otherwise false-kill an entry on its own assertion
instead of the real functional regression, the same hazard the existing
mechanism already guards every other `MUTATIONS` entry against. This
touches shared gate-6 machinery used by all 127 entries, flagged for T9's
full-table run to watch.

Not touched, by design: `mutation-all`'s comment (no standing "N entries"
total exists to bump, only historical per-measurement notes — brief said
skip); `AGENTS.md`'s count-bearing lines (T10's job).

## T8 — not reached yet

## T9 — not reached yet

## T10 — not reached yet

## T11 — not reached yet

## Ledger row (paste into `economics.md`)

Provisional — a structurally valid, all-`TBD` row (same precedent as
v1.8.0 T0's disclosed erratum 3 and v1.9.0 T10), replaced with the real,
complete row at T10 and de-provisionalised at T11:

```
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
```
