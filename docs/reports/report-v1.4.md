# Implementation report — spec-v1.4

**Status: IN PROGRESS.** This file is initialized at T0 (REQ-V14-PRE-02's
"T0 creates the file" rule) and completed at T10 — it is never created
retroactively. Sections below are filled in as their owning task lands;
pending sections say so explicitly rather than being silently absent.

Executor model: **claude-sonnet-5** (Claude Code harness, background
session), pinned by spec-v1.4's own preamble.
Prompt: `go docs/spec/spec-v1.4.md` — logged as
`docs/prompts/31-go-spec-v1.4.md`, task prompts from `32`.

Commits on `main` (grows per task; ORD-01 order):

| commit | task | contents |
|---|---|---|
| `30c7a16` | T0 | preconditions, this report's skeleton (`docs/prompts/31-…`, `32-…`) |
| `f6e634d` | T1 | S01 root cause: H1 classified, check repaired, `s01-repro`/`s01-verify` (`docs/prompts/33-…`) |
| `51ac747` | T2 | harness readiness: BEN-03 row-key rule, BEN-04 guards, BEN-05 nine `env_flags` keys, BEN-02 item 5 dry run (`docs/prompts/34-…`) |
| `818bbde` | T3 | `baseline-v1.4`: 35/36 successes, `B_plain = $0.003008745` (`docs/prompts/35-…`) |
| `485fcc5` | T4 | RSN spike: a/c/d probed live, b `unsupported`, e no control found — **STOP, no honored+shippable mechanism** (`docs/prompts/36-…`) |
| `e5fc230` | T6 | Reliability, STOP branch: REL-01 (timeout/budget consistency, default 120→240); REL-03 released (`docs/prompts/37-…`) |
| `718e4eb` | T8 | Default selection, STOP branch: `.env.example` `LLM_TIMEOUT_S=240`, README `## Benchmark` baseline-v1.4 paragraph; BEN-09 released (`docs/prompts/38-…`) |
| _pending_ | T9 | Mutations, STOP branch: two `v14-*` entries (BEN-03 unknown-column, REL-01 boundary), stale header comment fixed — **67 mutations, 67 killed** (`docs/prompts/39-…`) |

## Preconditions (T0 — REQ-V14-PRE-01…05)

### LM Studio version and model (PRE-02)

- **Model:** `qwen/qwen3.8-27b` (`LMSTUDIO_MODEL`, confirmed live via
  `GET /v1/models`), context length `LMSTUDIO_CONTEXT_LENGTH=42496` — both
  match every v1.3 file (`bench-v1.3.md:12-13`).
- **LM Studio server version: `0.4.23`.** Operator-supplied: this session has
  no SSH access and no version-reporting endpoint on the remote LM Studio
  host, so the version could not be self-observed and was read by the human
  operator from the LM Studio UI/CLI on request. See
  `docs/prompts/32-v14-t0-preconditions.md` § 6 for the full provenance
  note.

### Vendor documentation read live, 2026-09-03 (PRE-03)

**LM Studio** — `https://lmstudio.ai/docs/developer/openai-compat/chat-completions`
and `https://lmstudio.ai/docs/developer/api-changelog`:

- The documented Chat Completions body parameters are `model`, `top_p`,
  `top_k`, `messages`, `temperature`, `max_tokens`, `stream`, `stop`,
  `presence_penalty`, `frequency_penalty`, `logit_bias`, `repeat_penalty`,
  `seed`. No statement on whether unknown top-level keys reach the chat
  template — candidate **a** (`chat_template_kwargs: {"enable_thinking":
  false}`) is undocumented behaviour and must be measured (RSN-01).
- Changelog: **0.3.29** added `reasoning.effort` (`low|medium|high`) for
  `openai/gpt-oss-20b` only; **0.3.23** moved `gpt-oss` reasoning content to
  `choices.message.reasoning` / `choices.delta.reasoning`; **0.3.9**
  introduced separate `reasoning_content`. Nothing through the running
  `0.4.23` documents `reasoning.effort` for a Qwen3-class model, and nothing
  documents a disable value at any point — only `low|medium|high`. Per
  RSN-02, this points candidate **b** toward `unsupported`; T4 still probes
  it live, since the spike — not this reading — is what settles it.

**OpenRouter** — `https://openrouter.ai/docs/use-cases/reasoning-tokens`:
documented body is
`{"reasoning": {"effort": "high", "max_tokens": 2000, "exclude": false, "enabled": true}}`,
`effort ∈ {max, xhigh, high, medium, low, minimal, none}`. The page states
reasoning tokens are billed as output tokens and that `"exclude": true`
still lets the model reason, only hiding it from the response — confirming
`"exclude": true` MUST NOT be used as an off-switch (spec text) and that the
off-switch is `"enabled": false"` / `"effort": "none"`. Matches the spec's
own PRE-03 text; no drift found.

### Deviations recorded at T0

1. **HEAD precondition.** PRE-01 item 1 names `3a0aa3d`; actual HEAD at T0 is
   `3bc8e8b`. `git diff --stat 3a0aa3d..HEAD` — two files, both docs
   (`docs/spec/spec-v1.4.md` created, `docs/llm-usage.md` +1 line), zero
   production-code drift. Treated as satisfied in substance, not a blocker.
2. **LM Studio version is operator-supplied**, not self-read (see above) —
   PRE-02's obligation (recorded before any live step) is met regardless.
3. **`standards/reporting.md` is not opened** (outside the repository root,
   `AGENTS.md`'s context boundary). RPT-01's field list is instead
   reproduced from `docs/reports/report-v1.3.md`'s own structure, which
   already implements it.
4. **A spec / `AGENTS.md` conflict is flagged for T10**: RPT-05 asks for a
   row appended to lab-root `economics.md`, which sits outside the
   repository root; `AGENTS.md` says stop and ask when the spec and it
   disagree. Not yet a blocker — T0…T9 are unaffected, and RPT-04's E1
   already quotes `economics.md`'s existing figures without writing to it.
5. **T2: `tests/fixtures/bench/baseline.json`/`candidate.json` patched**,
   outside TREE-01's/§12.1's exhaustive change lists. Forced by BEN-05's two
   MUSTs (env_flags key set → nine; validation stays strict equality)
   colliding with the fixtures' 7-key shape — an `AGENTS.md`-style "unlisted
   test fails" trip-wire (`tests/test_dashboard.py`), resolved by patching
   the **data** (two `null` keys added, arithmetic untouched, `git diff`
   confirmed 4 lines) rather than the test's assertion, which stays
   untouched. Full reasoning: `docs/prompts/34-v14-t2-harness-readiness.md`.

## Gates

Six gates, run verbatim, in the order of `AGENTS.md` / §11. One row per
commit; T0's row is the pre-change tree (no commit yet at the time these
were run — the gates that PRE-01 item 2 requires before touching anything).

| point | 1 `uv sync --locked` | 2 `ruff check .` | 3 `pytest` | 4 `--selftest` | 5 `--selftest-live` | 6 `mutation_check.py` |
|---|---|---|---|---|---|---|
| T0 (pre-change) | rc=0 | rc=0, all checks passed | rc=0 — **719 passed** | rc=0 | rc=0 — `config`/`db`/`docker (29.7.2)`/`telegram`/`lmstudio`/`openrouter` all OK | rc=0 — **65 mutations, 65 killed**, 0 survived, 0 errored, 0 drifted |
| T1 (S01 repair) | rc=0 | rc=0, all checks passed | rc=0 — **720 passed** (+1: `tests/test_v14_patch.py::test_t_v14_scn_01_s01_check_accepts_capability_paraphrase`) | rc=0 | rc=0 — all six OK | rc=0 — **65 mutations, 65 killed**, 0 survived, 0 errored, 0 drifted |
| T2 (harness readiness) | rc=0 | rc=0, all checks passed | rc=0 — **726 passed** (+6: BEN-05 comparability × 2, BEN-03 unknown-column, T-V14-BEN-01/02/03) | rc=0 | rc=0 — all six OK | rc=0 — **65 mutations, 65 killed**, 0 survived, 0 errored, 0 drifted |
| T3 (baseline-v1.4) | rc=0 | rc=0, all checks passed | rc=0 — **726 passed** (no test change) | rc=0 | rc=0 — all six OK | _not run — no production/test/mutation-relevant change (GATE-01)_ |
| T4 (RSN spike, STOP) | rc=0 | rc=0, all checks passed | rc=0 — **726 passed** (no test change; scratch patches to `llm/base.py`/`llm/lmstudio.py`/`agent.py` reverted before commit) | rc=0 | rc=0 — all six OK | _not run — same reason, and not the final tree_ |
| T6 (REL-01, STOP branch) | rc=0 | rc=0, all checks passed | rc=0 — **728 passed** (+2: `T-V14-REL-01`, `test_t_cfg_06_timeout_default_is_240_rel_01`) | rc=0 | rc=0 — all six OK | rc=0 — **65 mutations, 65 killed**, 0 survived, 0 errored, 0 drifted (unchanged count — no new `v14-*` entries authored yet; TST-05's STOP-narrowed minimum `{BEN-03, REL-01}` lands at T9) |
| T8 (default selection, docs only) | rc=0 | rc=0, all checks passed | rc=0 — **728 passed** (no test change) | rc=0 | rc=0 — all six OK | _not run — no production/test/mutation-relevant change, not the final tree (GATE-01)_ |
| T9 (mutations, STOP branch) | rc=0 | rc=0, all checks passed | rc=0 — **728 passed** (no test change; `tests/test_mutation_check.py`'s generic loops cover the two new entries) | rc=0 | rc=0 — all six OK | rc=0 — **67 mutations, 67 killed**, 0 survived, 0 errored, 0 drifted (65 existing + 2 new `v14-*`: `v14-ben-03-unknown-column-accepted`, `v14-rel-01-timeout-budget-boundary-disabled`) |

_(Further rows land as each task's commit completes — GATE-01's per-commit
rule: gates 1–5 always, gate 6 additionally at commits touching production
code, configuration behaviour, benchmark verdict logic, tests or mutations,
and on the final tree.)_

---

## S01 root cause (T1 — REQ-V14-SCN-01…04)

**Reproduction did not reproduce.** `bench.py run --only S01 --repeats 3
--tag s01-repro` on the untouched HEAD tree: **3/3**, not v1.3's 1/3.
Repeats 1–2 were byte-identical, repeat 3 diverged — direct confirmation
that sampling is not deterministic end to end at `temperature: 0`.
`s01-repro.json`/`.log`, `bench-s01-repro.md` committed.

**Discriminating question, answered directly:** does the current
(stage-C) system prompt still name `exec`, `fetch` and the skill
mechanism? Inspected `agent.py:84-94` directly — **`exec`: named.
Skill mechanism (`load_skill`): named. `fetch`: NOT named anywhere**,
though the pre-optimization (`69ebc75`) prompt enumerated all three. This
fact alone points toward H2, and is recorded honestly rather than omitted.

**Why it doesn't carry the classification.** The check pattern is
`exec|команд|скилл|skill|fetch|python`. The two answers that actually
*failed* in v1.3 contain **none** of the six tokens — not even `exec` or
`команд`, both of which the current prompt still names. The dropped
`fetch` line cannot be the failure's cause if the still-present `exec`
line didn't save it either. And the SCN-01 reproduction — same tree, same
missing-`fetch` prompt — got 3/3, with an answer explicitly describing
*both* exec and network-fetch capability ("выполнять команды в
изолированном Linux-контейнере и получать данные из сети") despite the
prose never naming `fetch` (the tools-JSON schema, untouched by the
prefix rewrite, still carries it). Three phrasings of one true fact, one
regex keyed to six literal surface tokens: **the check measures phrasing,
not capability.**

**Classification: H1 — check defect.** Full v1.3 candidate answers (from
`docs/assets/bench/optimized.json`, S01 runs 1–3 — designated as the
transcript by SCN-01, read once, cited here) are all fluent, on-topic,
accurate; the only variable between pass and fail is whether one of six
literal tokens happens to appear.

**Repair (H1 branch, `checks` only, `id`/`title`/`turns` unchanged, no
other scenario touched):**

- Old: `exec|команд|скилл|skill|fetch|python`
- New: `exec|команд|скилл|skill|fetch|python|инструмент|контейнер|навык`
- Rationale: the failing answers already correctly describe capabilities
  using the generic nouns "инструменты"/"контейнер"/"навык"; accepting
  those alongside the tool names lets a fluent paraphrase pass while an
  off-topic or refusing answer (using none of these words) still fails.

**Verification:** `s01-verify`, fresh 3-repeat run — **3/3**.
`s01-verify.json`/`.log`, `bench-s01-verify.md` committed.
REQ-V13-BEN-08's `\|`-free loading test stays green.

Full evidence, quoted answers and the H1/H2 evidence table:
`docs/prompts/33-v14-t1-s01-root-cause.md`.

**Consequence:** `bench_scenarios.py` changed → `scenarios_sha256` changed
→ BEN-01 applies: every v1.3 benchmark file is incomparable with v1.4 from
this commit forward. A fresh `baseline-v1.4` (T3) is mandatory.

---

## Baseline-v1.4 (T3 — REQ-V14-BEN-02, BEN-06)

Stage-A tree (`69ebc75`) measured through the v1.4 harness and scenario
file, via `git worktree` (removed after the run) — see
`docs/prompts/35-v14-t3-baseline-v14.md` for the full procedure.

- `prefix_tokens=1126` (pre-optimization, matches `bench-v1.3.md:21`).
- **35/36 successes (97.2 %)** — one S12 repeat lost `summary_exists`
  (baseline runs are exempt from candidate-only assertions, BEN-08).
- **`meta.skipped_scenarios == []`**, confirmed before and after the run
  (wttr.in reachable both times).
- `meta.env_flags`: all nine keys present, every stage-C key `null` on this
  side, `LLM_FAILOVER="off"`, `LLM_MAX_TOKENS=2048` — as BEN-05 predicts.
- **`B_plain = Σcost / successes = $0.105306075 / 35 = $0.003008745`.**
  **Cost-gate threshold (`0.70 × B_plain`) = `$0.0021061215`.**
- `meta.git_commit` is `""`, not `69ebc75` — `_git_commit()`'s naive
  `.git/HEAD` read doesn't resolve through a linked worktree's redirect
  file; harmless, since `git_commit` is not a `LOCKED_META_FIELDS` entry.
  Not fixed (out of scope, NG-08).
- Artefacts: `baseline-v1.4.json`/`.log`, `bench-baseline-v1.4.md`, all
  committed.

The full verdict (`C_plain`, `C_conservative`, gate outcomes, honored rate)
lands in T7/T8 once a candidate exists.

---

## RSN spike (T4 — REQ-V14-RSN-01…06)

All five RSN-02 candidates tried, in order. **None both honored and
shippable — RSN-06 STOP: there is no optimization commit.** Full trial
log, per-pair evidence and the candidate-e documentation search:
`docs/prompts/36-v14-t4-rsn-spike.md`.

Every `a`/`c`/`d` probe used a temporary, uncommitted patch to
`llm/base.py` / `llm/lmstudio.py` / `agent.py`, driven by a one-off
in-process script that calls `bench.main([...])` twice per pair (RSN-01's
pair contract: sequential, one Python process, no subprocess, no new CLI
flag or env var). `git diff` confirmed empty before each next candidate;
the tree carries no production change at this commit — only the
`rsn-*.json`/`.log`/`.md` artefacts.

**Mechanism table (RSN-04), one row per pair member, LM Studio `0.4.23`,
every HTTP exchange `200`/no error (`error_kind` null, `finish_reason` ∈
{`stop`,`tool_calls`} on all 28 probe calls):**

| letter | ord. | member | mechanism | Σreasoning_tokens | max reasoning_chars | reasoning share | S05 | verdict (on `off` row) |
|---|---|---|---|---|---|---|---|---|
| a | 1 | default | `chat_template_kwargs.enable_thinking=false` | 345 | 1102 | 77.7% | 1/1 | |
| a | 1 | off | (same) | 345 | 1103 | 77.2% | 1/1 | **not honored** — off unchanged from default |
| a | 2 | default | (same) | 299 | 938 | 74.6% | 1/1 | |
| a | 2 | off | (same) | 463 | 1585 | 81.9% | 1/1 | **not honored** — off *higher* than default |
| c | 1 | default | assistant prefill `<think>\n\n</think>\n\n` (last message) | 345 | 1102 | 77.2% | 1/1 | |
| c | 1 | off | (same) | 0 | 0 | 0.0% | 1/1 | **honored but unshippable** (POL-05 item 4 — breaks CCH-02(a)) |
| c | 2 | default | (same) | 349 | 1132 | 77.9% | 1/1 | |
| c | 2 | off | (same) | 0 | 0 | 0.0% | 1/1 | **honored but unshippable** |
| c | 3 | default | (same) | 345 | 1102 | 77.7% | 1/1 | |
| c | 3 | off | (same) | 0 | 0 | 0.0% | 1/1 | **honored but unshippable** |
| d | 1 | default | Qwen3 `/no_think` appended to the `(now: …)` line of the last user message | 345 | 1100 | 77.2% | 1/1 | |
| d | 1 | off | (same) | 273 | 911 | 73.6% | 1/1 | **not honored** — reduced, not zero |
| d | 2 | default | (same) | 338 | 1083 | 77.5% | 1/1 | |
| d | 2 | off | (same) | 634 | 2149 | 86.6% | 1/1 | **not honored** — off *higher* than default, no reliable effect |
| b | — | — | vendor-documented disable value of `reasoning`/`reasoning_effort` | — | — | — | — | **unsupported** — PRE-03 (2026-09-03): LM Studio's changelog documents `reasoning.effort ∈ {low,medium,high}` for `openai/gpt-oss-20b` only (added 0.3.29), never a disable value, never for a Qwen3-class model, through the running `0.4.23`. No probe pair consumed (RSN-05). `rsn-b-low-info` (optional, `effort:"low"` informational pair) **not run** — adds no evidence toward a winning mechanism since `b` is already conclusively `unsupported`, and every RSN-06 STOP deliverable is met without it. |
| e | — | — | model-level default set in LM Studio (GUI or `lms` CLI) | — | — | — | — | **no control found** — `https://lmstudio.ai/docs/cli/load` (2026-09-03): `lms load`'s only flags are `[path]`, `--ttl`, `--gpu`, `--context-length`, `--identifier`, `--estimate-only`, `--host` — nothing reasoning/thinking-related. `https://lmstudio.ai/docs/typescript/llm-prediction/parameters` (2026-09-03): the documented Inference Parameters (`temperature`, `maxTokens`, `topP`, structured output) and Load Parameters (context length, GPU offload) carry no reasoning/thinking/chat-template field. A GitHub issue against LM Studio (as of v0.4.16) confirms no GUI slider/toggle exists for reasoning effort even for `gpt-oss` models, the one class that has *any* documented per-request reasoning field. Per RSN-02 ("name it… and do not guess"): this **is** the named finding — no version-appropriate control exists for `0.4.23`, so `rsn-e-info` **cannot be run** (there is nothing to toggle). e is categorically excluded from authorizing T5/T7 regardless (RSN-02: "cannot pass RSN-03 and cannot authorize T5 or T7"). |

**Candidate a analysis.** Both pairs show the `off` member at or above the
`default` member's reasoning volume (345→345, 299→463) — the undocumented
top-level `chat_template_kwargs` key has no observable effect on this LM
Studio build; the server does not forward it to the chat template, or the
template ignores it. Not honored, 0/2.

**Candidate c analysis.** All three pairs: `off` reads exactly `0`/`0` on
both `reasoning_tokens` and `reasoning_chars`, `default` stays in the
usual ~300–350-token band, S05's checks (`tool_used("exec")`,
`answer_regex(r"\b332\b")`) pass on every one of the six runs. RSN-03
items 1–3 all satisfied directly (no omitted-token fallback needed) — the
only candidate that is genuinely `honored`. Rejected at POL-05 item 4
regardless: the prefill is appended as the message array's last element,
so it cannot survive as a fixed byte-for-byte prefix while the array
grows round over round — every policy (`always`/`by-purpose`) that would
ship it breaks REQ-V13-CCH-02(a)'s prefix-extension invariant.

**Candidate d analysis.** Pair 1 shows a partial reduction (345→273, 21%
down but nonzero — fails RSN-03 item 1's exact-zero requirement outright,
so the 20% omitted-token fallback in item 3 is moot: `reasoning_tokens`
was never omitted on either member). Pair 2 shows an *increase*
(338→634). `/no_think` on the `(now: …)` line has no consistent
suppressive effect on this model/server combination — not honored, 0/2.

**Why the README is not touched at T4.** RSN-02's "name it in the README
note" instruction for candidate e is part of the policy documentation
T5/T8 write (`README.md` is not in T4's declared file scope, ORD-01's
table row 1261). Since RSN-06 routes this run to the STOP branch, T5 is
declared not-executed (below) and no `README.md` policy section is ever
created for e — or any candidate — to be named in. The finding is
recorded here and in `docs/prompts/36-…` instead, which satisfies "name
it… and do not guess" without inventing a README section for a policy
that does not ship.

**RSN-06 STOP — verdict.** No candidate is both honored (RSN-03) and
shippable (POL-05): `a` not honored, `b` unsupported, `c` honored but
unshippable, `d` not honored, `e` no control found (and categorically
disqualified regardless). **There is no optimization commit.** Per
RSN-06, this run still delivers in full: the S01 repair (above),
`baseline-v1.4` (above), both errata (RPT-04, T10), REL-01 (T6), this
mechanism table, and a final verdict of **FAIL, cause: no honored
reasoning mechanism**. Section 6 (POL-01…07 implementation), the two new
`## Reasoning` columns of section 7 (`reasoning_requested` /
`reasoning_honored`) and section 10's candidate benchmark runs (T7) are
**not-executed**. T5 and T7 are not executed; REL-02 (with its tests and
mutation) is released; T8 reduces to the mechanism-independent
documentation of RPT-06's final paragraph (REL-01's `.env.example`
`LLM_TIMEOUT_S=240` pair and the README lines that do not describe a
policy); BEN-09 is released (GATE-02).

---

## Reliability (T6 — REQ-V14-REL-01, REL-03; STOP branch: REL-01/REL-03 only)

Full trial log and both deviations: `docs/prompts/37-v14-t6-reliability.md`.

**REL-01 — the timeout/budget mismatch, fixed.** v1.3's measured latency
model (`report-v1.3.md:340`, `21.1 s + 0.093 s/token`) means the old
`LLM_TIMEOUT_S` default (`120`) admits only ~1063 completion tokens — well
under `LLM_MAX_TOKENS`'s default (`2048`), so a long completion timed out
and was retried with identical parameters, re-sending the whole prompt
(this aborted v1.3's first baseline attempt). `load_config` now raises
`ConfigError` when `llm_timeout_s < 21.1 + 0.093 × llm_max_tokens`, naming
both variables. The default `LLM_TIMEOUT_S` becomes **`240`**
(`21.1 + 0.093 × 2048 = 211.564 s` — the old `120`/`2048` pair would itself
now fail the check); `LLM_MAX_TOKENS` stays `2048`. Supersedes EC-05 for
`llm_timeout_s` only, per the spec's own AMEND-01 entry.
Test-first (`T-V14-REL-01`, `tests/test_v14_patch.py`): both failure
directions plus the shipped default (240/2048) and the spec's own cited
ceiling pair (600/6224) load cleanly.

**Deviation — `tests/test_v1_guardrails.py` (not in section 12.1's
list).** `test_new_config_variables_are_validated` paired
`LLM_MAX_TOKENS="8192"` with no timeout override, expecting success.
Under REL-01 this pair can never be valid at any `LLM_TIMEOUT_S`
(`21.1 + 0.093 × 8192 = 782.956 s`, above even the `LLM_TIMEOUT_S` ceiling
of `600`) — REL-01's own text states this consequence directly ("ceiling
600, so `LLM_MAX_TOKENS ≤ 6224`"), so this is inherent to the requirement,
not an implementation choice. `advisor()` was attempted twice (unavailable,
overloaded both times); resolved on REL-01's own textual evidence. Fixed
by swapping in the spec's own cited maximum pair (`6224` / `600`) in place
of `8192`, updating only that one literal and its assertion — 8 lines
changed, nothing else in the test touched. Flagged here per this run's
standing practice for `AGENTS.md`/spec tensions (as for T2's fixture
patch and the RPT-05/`economics.md` conflict).

**REL-03 — released, not fixed (SHOULD).** `metrics.py:193`'s
`sum(row["reasoning_tokens"] or 0 …)` conflates "reported nothing" with
"reported zero" in `Stats.reasoning_tokens`, contradicting the `Stats`
class's own docstring. `bench.py`'s `## Reasoning` rendering already
distinguishes the two correctly, so no gate depends on it. A
`metrics.py`+`tests/`-only fix is possible in principle, but the only
fixture exercising this field
(`tests/test_observability.py::test_obs08_stats_aggregate_rows`, not
listed in 12.1) asserts the pre-fix value; unlike the REL-01 collision
above, nothing in the spec text acknowledges this specific test becoming
obsolete, and REL-03 is a SHOULD with its own explicit safe default
("released otherwise"). Given the genuine ambiguity, this executor did not
edit a second unlisted test on inferred authority. **Known defect, carried
forward, not fixed this run.**

**`.env.example` not touched at T6** — REL-01's `LLM_TIMEOUT_S=240` line
there is T8's job (GATE-02), not T6's; T6's own file scope never names it.

---

## Default selection (T8 — REQ-V14-BEN-09 released, RPT-06 T8 half)

**BEN-09 released** — no honored+shippable mechanism exists (RSN-06), so
there is no default to flip; the shipped policy stays what it has always
been (no reasoning-control env var at all — `LLM_REASONING` was already
superseded and never resurrected).

RPT-06's T8 half narrows to its mechanism-independent line only
(`GATE-02`): `.env.example`'s `LLM_TIMEOUT_S` default updated `120 → 240`
with a three-line comment stating REL-01's consistency formula, and one
new `README.md` § "Benchmark" paragraph documenting the `git worktree`
procedure `baseline-v1.4.json` was measured with. Every other RPT-06
item-2 line (`§ Configure`, `§ Token economy`, `§ Observability`'s two new
columns) describes the reasoning policy this run never shipped and is
correspondingly not-executed. `docs/plan.md` (RPT-07) is T10's file, not
touched here. Full change list: `docs/prompts/38-v14-t8-default-selection.md`.

---

## Sections pending later tasks

The following REQ-V14-RPT-01 items are written by the task that produces
their evidence and are placeholders until then:

1. **Full verdict against `B_v1.4`** (`C_plain`, `C_conservative`, both gate
   outcomes, honored rate, any `DRIFT:`/`FINISH-LENGTH:` line — `B_plain`
   itself is recorded above) — T7/T8/T10.
2. ~~The mechanism table (RSN-04)~~ — done above (T4). Verdict: **STOP**,
   no honored+shippable mechanism.
3. **Errata to earlier reports** (RPT-04, E1/E2) — T10.
5. **Gates table, full** and exact test/mutation counts — grows per commit,
   finalized T10.
6. **Appendix-B results**, how each was driven, deviations, fix cycles — T10.
7. ~~Known defects carried forward (incl. REL-03's disposition)~~ — REL-03
   recorded above (T6): released, not fixed. Final consolidated list at T10.
