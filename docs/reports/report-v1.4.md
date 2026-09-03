# Implementation report — spec-v1.4

**Status: COMPLETE.** This file was initialized at T0 (REQ-V14-PRE-02's
"T0 creates the file" rule) and completed at T10, per its own §11 gates
run one final time on the tree this report describes. **Verdict: FAIL,
cause: no honored reasoning mechanism (RSN-06 STOP).**

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
| `3fe860a` | T9 | Mutations, STOP branch: two `v14-*` entries (BEN-03 unknown-column, REL-01 boundary), stale header comment fixed — **67 mutations, 67 killed** (`docs/prompts/39-…`) |
| `9a32cda` | T9 | REV-01 review: BEN-03's missing-column mutation added, dead `env_flags()` branch removed, one waiver formalized — **68 mutations, 68 killed** (`docs/prompts/40-…`) |
| `64aa5da` | T10 | Verdict (FAIL, no honored mechanism), GATE-02 enumeration, errata E1/E2, RPT-05 conflict resolved, Appendix-B (E5/E8/E10 PASS, D1/D3 regression PASS-by-unchanged-code, rest not-executed), known defects, `tg-post-v1.4.md`, `docs/llm-usage.md` rows 34–35, `docs/plan.md` (`docs/prompts/41-…`) |
| _this commit_ | T10 | `advisor()` follow-up: Fix cycles section (RPT-01 item 6), E1/E2 evidence commands executed (not just asserted), commit count 9→11 corrected in `docs/plan.md`/`docs/llm-usage.md`, preconditions deviation 4 forward-pointer (`docs/prompts/42-…`) |

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
   disagree. Not yet a blocker at T0 — T0…T9 are unaffected, and RPT-04's
   E1 already quotes `economics.md`'s existing figures without writing to
   it. **Resolved at T10, in favor of `EC-01`** — see "Deferred conflict,
   resolved" below.
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
| T9 (REV-01 review fixes) | rc=0 | rc=0, all checks passed | rc=0 — **728 passed** (no test change) | rc=0 | rc=0 — all six OK | rc=0 — **68 mutations, 68 killed**, 0 survived, 0 errored, 0 drifted (+1: `v14-ben-03-missing-column-accepted`, the sibling half of BEN-03's rule the review found uncovered) |
| T10 (report/post/errata/ledger) | rc=0 | rc=0, all checks passed | rc=0 — **728 passed** (no test change) | rc=0 | rc=0 — all six OK | rc=0 — **68 mutations, 68 killed**, 0 survived, 0 errored, 0 drifted — run alone, sequentially after every other T10 change, per GATE-01's "and on the final tree" clause |
| **T10 (advisor follow-up — final tree)** | rc=0 | rc=0, all checks passed | rc=0 — **728 passed** (no test change) | rc=0 | rc=0 — all six OK | rc=0 — **68 mutations, 68 killed**, 0 survived, 0 errored, 0 drifted — docs-only fix commit (Fix cycles section, E1/E2 verification executed, RPT-05 forward-pointer, 9→10 commit count in `plan.md`/`llm-usage.md`); run alone, sequentially, per the same clause |

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

## Mutations and review (T9 — REQ-V14-TST-05, REV-01; STOP branch)

**TST-05, narrowed.** GATE-02 reduces the mechanism-found branch's
six-entry minimum to the `v14-*` entries defending code this run actually
shipped: BEN-03's row-key rule and REL-01's timeout/budget boundary.
Header comment corrected (was stale at "64 in all" while 65 entries
already existed — confirmed by direct count — a discrepancy `GATE-01`'s
own text names). `tests/test_mutation_check.py` needed no change: its two
`v12`-era tests already iterate `mc.MUTATIONS` generically. Full trial
log, including a first BEN-03 attempt that survived (a vacuous mutation,
since `REQUIRED_LLM_ROW_KEYS == LLM_ROW_KEYS` on this tree with no
OBS-01 column added): `docs/prompts/39-v14-t9-mutations.md`.

**REV-01.** Code review by the `code-reviewer` subagent in a clean
context, on the T8 tree, per the spec's own requirement. Full brief and
findings: `docs/prompts/40-v14-t9-review.md`. Summary:

- **Two real, fixed findings.** (1) BEN-03's *missing*-required-column
  half had no mutation entry (the sibling half, *unknown*-column, did) —
  added `v14-ben-03-missing-column-accepted`, verified killed. Mutation
  total: 65 + 3 = **68**, all killed, 0 survived/errored/drifted. (2) The
  `env_flags()` frozenset-serialization branch added at T2 was dead code
  on this branch — `Config` never gains the field this run's STOP branch
  doesn't implement (T5 not-executed), so the branch never executed and
  had no coverage; `REQ-V14-BEN-05`'s own text confirms the plain
  field-absence→`None` fallback already satisfies the requirement here.
  Removed; `env_flags()` reduced to that fallback alone.
- **One waiver formalized, not reopened.** `tests/test_v1_guardrails.py`'s
  `LLM_MAX_TOKENS` literal change (T6, commit `e5fc230`) was disclosed as
  a deviation there but never logged as a REV-01 waiver. REL-01's own
  arithmetic makes the old `8192` value unreachable at any legal
  `LLM_TIMEOUT_S` — not an implementation choice to revisit. **Waived**,
  tier-3 (test-only, invalidates nothing).
- **`TOOL_ROW_KEYS` needs no separate REQUIRED constant** (BEN-03's own
  "or state in the report why not"): the `tool_calls` schema is untouched
  by this spec, so REQUIRED == current for that row type and one
  variable (`TOOL_ROW_KEYS`) already serves both bounds — no widening
  ever occurs for `tool_calls`, unlike `llm_calls` (which OBS-01 would
  widen, on the mechanism-found branch only).
- **One limitation recorded, not fixed:** S01's widened regex has the
  same substring/negation blind spot the original pattern always had
  (a refusal containing "инструмент" would still match) — pre-existing,
  not introduced by this repair, and `bench_scenarios.py` is now
  BEN-10-frozen (any further change forces a T3 re-baseline). Carried
  to the known-defects list (T10).
- Verdict was "request changes" at review time (the process gap of
  finding 1, since resolved by this section, and finding 2); no shipped
  correctness defect was found in REL-01, the RSN spike's STOP
  conclusion, or the baseline-v1.4 worktree procedure.

All six gates green throughout (see Gates table, T9 rows).

---

## Verdict (T10 — REQ-V14-RPT-01 item 1)

**FAIL, cause: no honored reasoning mechanism.** Per RSN-06: all five
candidates were tried; none is both honored (RSN-03) and shippable
(POL-05). There is no optimization commit, so **`C_plain`,
`C_conservative`, both gate outcomes and the honored rate are not
computed** — no candidate run exists to compute them from (T7
not-executed, GATE-02). No `DRIFT:`/`FINISH-LENGTH:` line either: both
belong to candidate reports (OBS-05, REL-02), neither of which was
produced.

What *is* measured: **`B_v1.4` = `baseline-v1.4.json`**, stage-A tree
(`69ebc75`) through the v1.4 harness — `B_plain = Σcost/successes =
$0.105306075 / 35 = $0.003008745`. The cost-gate threshold
(`0.70 × B_plain`) is `$0.0021061215`, quoted for completeness; it is
never evaluated against anything, since no `C_plain` exists to compare.

**Informational row (BEN-01): v1.3's own headline figures, $0.002687 /
$0.002492, are not this run's gate basis.** `B_v1.4` and v1.3's baseline
are measured on different scenario files (`scenarios_sha256` changed at
T1's S01 repair) — comparing v1.3's numbers against anything in this
report would silently mix two incomparable measurements. `B_v1.4` exists
so a *future* patch release has a same-scenario baseline to measure
against; it is not itself compared to v1.3 here.

**`docs/reports/bench-v1.4.md` does not exist and was not fabricated**
(RPT-08: "no artefact for a released or not-executed run is required,
and none may be fabricated") — it is `report --gate --candidate`'s
output, owned by T7. Anywhere this run's own traceability matrix (§14.2)
or `docs/plan.md` would normally point a reader at `bench-v1.4.md`,
the verdict instead lives in this report's Verdict/RSN-spike sections,
and `docs/plan.md`'s figures are sourced from `baseline-v1.4.json` /
this report, not from `bench-v1.4.md` — noted explicitly there.

### GATE-02 enumeration — every conditionally released REQ, test id, artefact, mutation

Per GATE-02: "the report states the actual counts and lists every
conditionally released REQ and test id."

| category | released (not-executed) |
|---|---|
| Requirements, section 6 (policy) | POL-01, POL-02, POL-03, POL-04, POL-05, POL-06, POL-07 |
| Requirements, section 7 (observability) | the two new `## Reasoning` columns (`reasoning_requested`/`reasoning_honored`) and all of OBS-01…05 that depend on them (OBS-01 runtime derivation, OBS-02 unchanged in shape but never exercises the new fields, OBS-03's `LLMCompletion` return-type change, OBS-04's honored-rate rendering, OBS-05's drift sentinel) |
| Requirements, section 9 (reliability) | REL-02 only (REL-01, REL-03 executed — see above) |
| Requirements, section 10 (benchmark) | BEN-07 (candidate run budget), BEN-08 (the verdict-computation machinery itself — nothing to compute), BEN-09 (default selection/flip) |
| Test ids (§12.2) | T-V14-POL-01…07, T-V14-OBS-01…03, T-V14-REL-02, T-V14-REL-03 |
| Artefacts (RPT-08) | `cand-*.json`/`.log`, `drift-<candidate>-*.json`/`.log`, `bench-v1.4.md`, `openrouter-reasoning-off.json`/`-default.json` (POL-07 was never executed, so these two OpenRouter smokes have no trigger), `rsn-e-info` (no control found to run it against), `rsn-b-low-info` (optional, not run — no evidentiary value once `b` is `unsupported`) |
| Mutations (TST-05) | the four of the mechanism-found branch's six that defend unshipped code: POL-03 (policy resolution `by-purpose`-as-`off`), POL-04 (failover-secondary forwarding), OBS-05 (drift-guard comparison), REL-02 (`summary`+`finish_reason=='length'` assertion) — the two that defend shipped code (BEN-03's row-key rule — both halves — and REL-01's boundary) were added, 68 total, 68 killed |

**Test count: 728 = 719 (v1.3 baseline, EC-03) + 1 (T1, S01 check repair)
+ 6 (T2, BEN-05 comparability ×2, BEN-03 unknown-column, T-V14-BEN-01/02/03)
+ 2 (T6, T-V14-REL-01, the new-default case).** GATE-01's `> 719` minimum
binds unconditionally and passes (728 > 719). GATE-01's `≥ 71` mutation
minimum (65 + TST-05's six) is explicitly **conditional on the
mechanism-found branch** (GATE-02) and therefore does not bind here — 68
(65 + the three v14-* entries actually defending shipped code) is the
correct, complete count for this branch, not a shortfall against 71.

---

## Errata to earlier reports (T10 — REQ-V14-RPT-04)

No edit to any earlier report or to `docs/llm-usage.md` rows 1…32, which
stay byte-unchanged — executed, not merely asserted:
`git diff 3bc8e8b..HEAD -- docs/llm-usage.md` shows row 33 (already
present before this `go` run, from spec-v1.4's own authoring) as
unmodified context, with the first added line being row 34.

- **E1 — the v1.2 cost, `docs/llm-usage.md` row 27.** That row's cost cell
  reads `≈$33.11`; the figure has since been reproduced exactly, as two
  concurrent `claude-sonnet-5` sessions: `49c2d3e6…` (2026-09-01T20:06–22:12Z,
  spec `7ab107a`) `$16.50` and `c32c1cd8…` (21:45–23:28Z, implementation
  `d83a49e` + report `55d7ea0`) `$16.61`, under the ledger formula
  (`$2`/`$10` per Mtok, cache write ×1.25, cache read ×0.1). The per-class
  token counts are quoted from `economics.md`, which already carries the
  reconciled figures (`130.88M / 447.0k`, `≈$33.11 ($16.50 spec + $16.61
  impl)`). Row 27 is **stale, not wrong** — not edited, per RPT-04.
- **E2 — the v1.3 prompt count.** `report-v1.3.md:14` ("19 prompt files
  09–27") and `docs/llm-usage.md` row 31 ("18 of 19") are stale: the v1.3
  `go` run logged **21** prompt files, `09-go-spec-v1.3.md` through
  `29-v13-TD2-tg-post.md` (28 and 29 are stage D of the same run — verified
  again here, executed: `ls docs/prompts/09-*.md docs/prompts/1[0-9]-*.md
  docs/prompts/2[0-9]-*.md | grep -v "v14\|3[0-9]-" | wc -l` → **21**.
  Row 32 already says 21, and `economics.md` already says
  "21 (+1 post-verify docs fix)". Row 31 is **not** edited — the corrected
  count lives in row 32 and here.

---

## Deferred conflict, resolved (T0 deviation 4 — RPT-05 / `economics.md`)

Flagged since T0: `REQ-V14-RPT-05` instructs "append the project's row to
lab-root `economics.md` after the report is written" — `economics.md`
sits outside this repository's root (the lab root, not `tg-agent-bot/`).
`REQ-V14-EC-01` states, absolutely, "the executor reads and writes
**nothing** outside the repository root," with exactly one enumerated
exception (BEN-02's `git worktree`, which reaches only `.env` by absolute
path and never `economics.md`); `AGENTS.md`'s context boundary
independently forbids it ("agents work inside this repository only").
§14.1 states §1 (which contains EC-01) binds every task without
exception.

**Resolved in favor of EC-01 — no write to lab-root `economics.md` was
made.** This is the disposition, not a silent omission: EC-01 is the
absolute, once-exception rule; RPT-05's instruction is a narrower §13
line that cannot open a second exception EC-01 itself does not name. So
nothing is lost, the row `economics.md` would have carried is reproduced
here instead — this run's own `docs/llm-usage.md` contribution (rows
33–42, below) summed and named by its executor model, `claude-sonnet-5`,
for whoever next reconciles `economics.md` by hand, outside this
repository, as prior versions' rows were.

---

## Appendix-B acceptance scenarios (T10 — REQ-V14-ACC-01)

Executed after all gates were green, against this run's actual shipped
code (not a draft). Per REQ-V12-REP-02 (still in force), how each was
driven is stated, not left unsaid.

| id | result | how driven |
|---|---|---|
| E1 (policy off suppresses reasoning) | **not-executed** | no policy exists to set — POL-01…07 not-executed (RSN-06) |
| E2 (by-purpose) | **not-executed** | same — no policy |
| E3 (default policy changes nothing) | **not-executed** | `LLM_REASONING_POLICY` doesn't exist as a variable; the property it asserts (no reasoning field in the request body, byte-identical system/tools JSON) holds vacuously by construction on this branch, since no code path was ever added that could violate it |
| E4 (bad policy value stops at startup) | **not-executed** | same — no variable to reject |
| **E5 (timeout/budget mismatch)** | **PASS** | scripted, direct call to the real `config.load_config` (not mocked): `LLM_TIMEOUT_S=120`/`LLM_MAX_TOKENS=2048` (the spec's own worked example) raised `ConfigError` naming both variables (`"LLM_TIMEOUT_S (120.0) is below the latency-model floor for LLM_MAX_TOKENS (2048): needs at least 211.564s..."`); the shipped defaults (240/2048, nothing overridden) started cleanly. Independently reconfirmed by every `--selftest-live` run this session passing its `config` check against the real `.env` pair |
| E6 (starved summary → FINISH-LENGTH) | **not-executed** | REL-02 not-executed (RSN-06/GATE-02) — no assertion exists to trigger |
| E7 (drift guard) | **not-executed** | OBS-05 not-executed — no candidate run to drift-check |
| **E8 (S01 measures capability, H1 branch)** | **PASS (already executed at T1)** | per REQ-V14's own text ("T-V14-SCN-01 and Appendix B E8 execute only once"), `s01-verify`'s 3/3 benchmark run **is** E8's execution: three fluent paraphrases that name no tool but describe capability, all pass; the pre-repair check's own two false negatives, both fluent and on-topic, are E8's failing-scenario evidence in reverse |
| E9 (baseline/candidate comparable) | **not-executed** | requires a candidate; none exists (T7 not-executed) |
| **E10 (no secret leaks)** | **PASS** | scripted `grep`/Python scan across all 74 files this run touched or created (the full `git diff --name-only 3bc8e8b..HEAD` list): authorization headers, URL user-info, credential key names in value positions, bare Telegram-bot-token shapes, generic API-key prefixes (`sk-`, `gsk_`, `ghp_`, `AKIA`) — every match found is a declared test/example sentinel (`.env.example`'s own documented placeholder, `tests/test_v1_guardrails.py`'s `sentinel-telegram-token-...`), never a real value; real credential values were neither read nor used as scanner inputs (`.env` was not opened). The "bench file's Telegram id is the redacted placeholder" clause does not apply to this release's artifact shape: the benchmark harness calls `bot.process_update` directly and no Telegram-identity field exists anywhere in the bench JSON schema (verified by walking every key of `baseline-v1.4.json`) |
| **D1 (regression — v1.2, secret in tool-call id)** | **PASS, by unchanged-code evidence** | `git diff --stat 3bc8e8b..HEAD -- storage.py tools.py bot.py agent.py` is **empty** — the redaction path D1 exercises (`storage.add_tool_call`, `config.redact`) received zero changes in this release. Combined with the full pytest suite (728/728, including the tests the `v11-storage-add-tool-turn-redacts` mutation entry defends) and the mutation gate (68/68 killed, including that entry) both passing unchanged, the posture D1 checks is provably unweakened — driven by the existing automated regression suite, not a fresh live walk-through, because the code it exercises was never touched |
| **D3 (regression — v1.2, sandbox self-recovery)** | **PASS, by unchanged-code evidence** | same reasoning: `tools.py`'s sandbox quota/clean-on-start logic (the `sec-qta-*` mutation-defended code) received zero changes; 728/728 and 68/68 confirm the posture is unweakened |

No fix cycles were consumed by Appendix-B execution — every scenario
either passed on the first live/scripted drive or was correctly
classified not-executed by construction.

---

## Known defects carried forward (T10 — REQ-V14-RPT-01 item 7)

- **REL-03 (SHOULD), released, not fixed.** `metrics.py:193`'s
  `sum(row["reasoning_tokens"] or 0 …)` conflates "reported nothing" with
  "reported zero" in `Stats.reasoning_tokens`. No gate depends on it
  (`bench.py`'s own rendering already distinguishes the two). Full
  reasoning: T6 section above.
- **S01's widened regex has the same substring/negation blind spot the
  original pattern always had** (a refusal containing "инструмент" would
  still match, uncaught) — pre-existing, not introduced by this run's
  repair (T1), and `bench_scenarios.py` is now BEN-10-frozen: any further
  change forces a fresh T3 baseline. Not fixed; recorded as a known
  limitation (T9, REV-01 note 5).
- **`meta.git_commit` reads `""` on a `git worktree`-measured baseline**
  (`baseline-v1.4.json`) — `_git_commit()`'s naive `.git/HEAD` read
  doesn't resolve through a linked worktree's redirect file. Harmless:
  `git_commit` is not a `LOCKED_META_FIELDS` entry. Not fixed (T3, out of
  scope, NG-08).
- **v1.2's accepted risks** (a real Telegram operator conversation has
  never been exercised — every acceptance run to date, including this
  one's E5/E10/D1/D3, is driven by a script standing in for the operator)
  and **v1.3's accepted risk** (O6 routing ships tested but disabled,
  since only one model fits the maintainer's GPU box) both carry forward
  unchanged — this run touched neither.

---

## Fix cycles

**2 of the 5-cycle repair budget consumed.** `docs/plan.md`'s rule: a
repair cycle counts "once a fix is followed by a complete re-run of every
gate from the first"; test-first failures caught before that gate
sequence starts do not debit it. Both events below happened inside a
formal, already-started six-gate run, not during test-first development —
so both count.

1. **T6 — `tests/test_v1_guardrails.py` collision (1 cycle).** REL-01's
   own test-first sequence (its two new/changed cases in
   `tests/test_v14_patch.py`/`test_config.py`) was already green before
   the six-gate sequence for the commit started. Gate 3's full-suite
   `pytest` run then failed a third, unrelated, pre-existing test
   (`test_new_config_variables_are_validated` — `LLM_MAX_TOKENS="8192"`
   became unreachable under the new timeout floor at any
   `LLM_TIMEOUT_S`). Fixed (see "Deviation" above); gates re-confirmed
   green end to end (`docs/prompts/37-v14-t6-reliability.md`'s closing
   "All six green").
2. **T9 — BEN-03's first mutation entry survived (1 cycle).** Not caught
   during authoring — the entry's own text says it surfaced in "the real
   gate run": `mutation_check.py` returned rc≠0 (67 mutations, 66 killed,
   1 survived), a formal gate-6 failure. Root-caused, retargeted to the
   entry's *unknown*-column half, and the full six-gate sequence re-run
   end to end (`docs/prompts/39-v14-t9-mutations.md`'s closing "All six
   green on the corrected entries," 67/67). The concurrent `--only`
   verification run described in the same prompt is a process note, not
   a third cycle — it produced a misleading reading on an unrelated,
   already-superseded check, not a gate failure of record.

No other task in this run (T0–T5, T8, T10) needed a fix after its formal
gate sequence had already started; each ran green on the first pass or is
recorded above as pre-gate test-first friction, which does not debit the
budget under `docs/plan.md`'s rule.

---

## Post and ledger (T10 — REQ-V14-RPT-02, RPT-03, RPT-05, RPT-07)

- **RPT-02:** no cumulative v1 → v1.4 section in this report by design —
  the cross-version view lives in `economics.md` and `docs/plan.md`
  (updated below), not here.
- **RPT-03:** `docs/reports/tg-post-v1.4.md` — Russian, `constraints →
  result → metrics → links`, executor model named, linking
  `https://github.com/axyi/tg-agent-bot`. **Measured length: 1449
  characters (`wc -m`)** — under the 1500-character ceiling.
- **RPT-05:** `docs/llm-usage.md` gains rows 34–35 (this run's
  implementation session, row 34; the T9 `code-reviewer` subagent, row
  35, 153,558 tokens aggregate) plus a Σ row and an explanatory note —
  see the deferred-conflict section above for why no row was appended to
  lab-root `economics.md` by this executor.
- **RPT-07:** `docs/plan.md`'s status table gains the `spec-v1.4.md` row;
  the "v1.4 (next) — candidates, none applied" section is replaced by
  the delivered outcome (mirroring this report's RSN spike) and renamed
  "v1.5 (next)", listing exactly the candidates RPT-07 names as still
  untried: O6 routing, tokenizer-accurate context budget, streaming,
  semantic cache, and levers 3, 4 and 7 of `report-v1.3.md`
  (`CONTEXT_WINDOW_MESSAGES`, `EXEC_OUTPUT_DEFAULT_CHARS`,
  `FETCH_INLINE_DEFAULT_CHARS`). Lever 6 (the starved-summary fragility,
  REL-02) is deliberately not re-listed there — RPT-07 does not name it,
  and it is already accounted for above as a released requirement, not a
  performance candidate. Numbers throughout come from `baseline-v1.4.json`
  and this report, never from v1.3 — and, per the Verdict section above,
  never from `bench-v1.4.md`, which does not exist on this branch.
