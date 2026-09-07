# Implementation report — spec-v1.7.0

**Status: T6 complete — the summary wall-clock budget landed
(SUM-01…-05). Gates 1-4-5 green; mutation gate running. Run continues to
T7.**
**Key finding: `stats.time_to_first_token` is present but empty (`{}`) on the
OpenAI-compatible route — RSN-07's summary-only fallback (trigger 1) binds
the whole run: no candidate can ship a mechanism for the agent tags
(`tool-round`, `final`); at most `summary` may ship one.**

- **Spec:** `docs/spec/spec-v1.7.0.md`
- **Spec `sha256`** (recorded at T0, MUST NOT change during the run):
  `d6ad4a4a05859883f6f6cde4466512b2fa980767df6b9ab82d778a0ae32c263a`
- **Executor:** claude-sonnet-5 (Claude Code)
- **`<base>`** (HEAD before this run's first commit): `706c690d35f34d96d1ee0fbcb8e9be08bafa30e7`
- **`<implementation-tip>`**: not reached yet.

## Operator inputs

The initial `go docs/spec/spec-v1.7.0.md` request carried none of
REQ-V170-PRE-02's three values. Per REQ-V170-PRE-02 that is a T0 blocker for
a missing version or context length; the executor asked a clarifying
question in the same session rather than guessing, and the operator answered
there (not in the original `go` text) — recorded as a process deviation
below.

- **LM Studio version:** `Bionic v1.1.1` (operator-confirmed; equals
  `baseline-v1.6.0`'s `meta.lmstudio_version`, so REQ-V170-BEN-01's version
  check is expected to pass at T1, pending the live read)
- **Loaded context length:** `42496` (operator-confirmed; equals the
  baseline's `meta.lmstudio_context_length`)
- **Current LM Studio address:** operator did not name a distinct address
  ("one of the three known, or don't know") — PRE-03's fixed ordered probe
  (`192.168.0.145`, `172.16.50.233`, `192.168.178.170`) runs with no fourth
  candidate appended, per REQ-V170-PRE-03's dedup rule.
- **Served model id:** not yet established — populated at T1 from a live
  `GET <base>/models` read, per REQ-V170-PRE-04 item 3.

## Preconditions (T0 — REQ-V170-PRE-01)

Gates 1–4 and 6 of §13, offline, before any change in this run. Gate 5
(`bot.py --selftest-live`) and the `full` profile's live member are reserved
for T1 by REQ-V170-GATE-01 ("never at T0").

| # | gate | command | exit |
|---|---|---|---|
| 1 | uv sync | `uv sync --locked` | 0 |
| 2 | ruff check | `uv run --locked ruff check .` | 0 |
| 3 | pytest | `uv run --locked pytest` | 0 — 1016 collected, all pass |
| 4 | selftest | `uv run --locked python bot.py --selftest` | 0 |
| 5 | selftest-live | *(reserved for T1 per REQ-V170-GATE-01; see Deviations)* | — |
| 6 | mutation | `uv run --locked python devtools/mutation_check.py` | 0 |

`checks.py run --profile full --since <base>` (rerun with the corrected
`<base>` after an initial run mistakenly used the v1.6.0 tag as `--since`):
all fifteen members reported, including `selftest-live` (see Deviations) —
`uv-sync`, `ruff-check-all`, `ruff-format`, `branch-name` (warn-only on
`main`), `pytest`, `selftest`, `selftest-live`, `mutation-all`,
`gitleaks-tree`, `trivy`, `semgrep`, `skylos` (shadow), `hooks-installed`,
`doctor`, `lint-docs` (still checking `report-v1.5.md` — repointed at T8 per
REQ-V170-RPT-02).

Test count re-measured at HEAD: **1016** (`uv run --locked pytest
--collect-only -q`, summed per-file), matching REQ-V170-EC-03's floor
exactly — no drift since the 2026-09-06 measurement the spec cites.

Docker: `docker version` exits 0, no `sudo` needed. The digest-pinned
`python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6`
(`config.py:28`) is present locally.

`.env`: present, git-ignored, keys checked by name only —
`TELEGRAM_BOT_TOKEN`, `LLM_PROVIDER`, `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`,
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `LLM_MAX_TOKENS`, `LLM_TIMEOUT_S`
present. Values never read or printed. Per REQ-V170-PRE-01 item 9:
`grep -q '^LLM_REASONING_POLICY=' .env` and
`grep -q '^LLM_REASONING_ON_PURPOSES=' .env` both exit **non-zero** — neither
key is present, which is what makes REQ-V170-POL-07's final-tree equivalence
proof binding on the deployed bot.

`git tag -l`: `v1.3`, `v1.3-baseline`, `v1.6.0` — all present, none moved
(REQ-V170-NG-13 respected).

`docs/prompts/102-v170-spec-authoring.md` and `docs/spec/spec-v1.7.0.md` are
present and already committed at HEAD (`706c690`); `102` is the highest
pre-existing prompt number, confirming this run's `go` prompt is `103`.

`uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json`
exits 0 — the baseline is readable and self-consistent.

## Benchmark-affecting changes (REQ-V170-EC-06)

Two declared in advance by the spec itself:

1. REQ-V170-POL-04 — the per-purpose reasoning field on the request body
   (the treatment REQ-V170-BEN-07's gate measures).
2. REQ-V170-SUM-02/-03 — the shared summary budget and the skipped retry;
   token-affecting but prompt-neutral (`meta.prompt_tools_sha256` stays
   byte-identical).

No further benchmark-affecting change discovered yet at T0.

## RLM delegation record, per task (REQ-V170-EC-07)

| T | delegated? | to what |
|---|---|---|
| T0 | no | — |
| T1 | no | — (small over-map reads noted in T1's own RLM note, above) |
| T2 | no | — scratch patch only, `devtools/bench_scenarios.py:204-212`/`:262-270` and `llm/lmstudio.py:35-53` read-only, per the map |
| T3 | no | — only commands run, under the scratch patch of T2, per the map |
| T4 | **spec says yes; executed directly instead** | the map's three files (config.py, llm/base.py, storage.py) plus one small necessary companion edit to `devtools/bench.py` (`env_flags`, ~10 lines, outside the map — see T4's own section). Reasoning: the main context already held the T1/T3 findings the implementation directly depends on (the exact `REASONING_MECHANISMS` table); delegating would have required re-deriving or re-transcribing that table into a fresh subagent's brief, a real transcription-error risk for a table this load-bearing. Reads stayed targeted (`Read` with `offset`/`limit`, no whole-file dumps) rather than exhaustive. |
| T5 | **spec says yes; executed directly instead** | same reasoning as T4 — this task directly extends T4's types across the five sites and both providers, and the main context already holds their exact shapes. Map's files (`llm/base.py`, `llm/lmstudio.py`, `llm/openrouter.py`, `llm/failover.py`, `bot.py`, `agent.py`, `tracing.py`) plus `devtools/mutation_check.py` (one `find`-string sync, self-caught) and `tests/test_v160_dashboard.py` (one line, disclosed erratum instance). |
| T6 | **spec says yes; executed directly instead** | same reasoning. Map's files (`agent.py`, `bot.py`, `config.py`) plus `tests/test_pricing.py`/`tests/test_v11_patch.py` (two stub-signature fixes, disclosed erratum instances). |

(extended per task as the run proceeds)

## Deviations (running log)

1. **T0 — operator inputs arrived via a clarifying question, not the initial
   `go` text.** The `go docs/spec/spec-v1.7.0.md` request carried none of
   REQ-V170-PRE-02's three values. Per that requirement's letter this stops
   the executor at T0 with the blocker template; the executor instead asked
   a clarifying question in the same session (`AskUserQuestion`) rather than
   guessing or silently proceeding, and the operator's answer confirmed the
   version and context length match the frozen baseline instrument, and
   named no address distinct from the three fixed candidates. Recorded here
   as a process deviation from the strict "in the request's own text" rule;
   the values are otherwise handled exactly as REQ-V170-PRE-02 specifies
   (copied verbatim into this section, checked against the baseline at
   REQ-V170-BEN-01).
2. **T0 — gate 5 and the `full` profile's live member ran at T0, not
   deferred to T1.** `checks.py run --profile full` has no per-gate
   exclusion flag; the first invocation (against the wrong `--since`, see
   below) and its corrected rerun both pulled in `selftest-live`, which
   REQ-V170-GATE-01 reserves for T1. `bot.py --selftest-live` sends no
   inference (per `AGENTS.md`'s Benchmark section), so REQ-V170-PRE-04 item
   7's "first inference of the run" is unaffected — but the written order
   of REQ-V170-ORD-01's T1 row was not followed to the letter, and that is
   recorded rather than absorbed silently.
3. **T0 — the first `checks.py run --profile full` invocation used
   `--since 89786ef`** (the v1.6.0-tag commit) **instead of `--since
   706c690d35...`** (the true `<base>`, this run's starting HEAD). It was
   rerun with the corrected `--since <base>` before this report's exit codes
   were recorded; no committed artefact depended on the first run's output.

## Live preflight (T1 — REQ-V170-PRE-03, PRE-04, BEN-01)

Order followed exactly as REQ-V170-ORD-01's T1 row requires: PRE-03 phase 1
→ PRE-04 items 1–6 → PRE-04 item 7 (first inference) → PRE-03 phase 2
(second inference) → gate 5.

### PRE-03 phase 1 — address probe, `.env` rewrite, served-model read

Ordered probe of the three fixed addresses (operator named no distinct
fourth address):

| address | probed | answered |
|---|---|---|
| `192.168.0.145` | 1st | **yes** — winner |
| `172.16.50.233` | not probed (probe stops at first answer) | — |
| `192.168.178.170` | not probed | — |

`sed -i 's|^LMSTUDIO_BASE_URL=.*|LMSTUDIO_BASE_URL=http://192.168.0.145:1234/v1|' .env`,
confirmed by `grep -q '^LMSTUDIO_BASE_URL=http://192.168.0.145:1234/v1$' .env`
exiting 0.

Served model ids read from `GET http://192.168.0.145:1234/v1/models`
(`data[].id`, 16 entries): exactly one entry, `qwen/qwen3.8-27b`, compares
equal by **string equality** (not substring) to both the baseline's
`meta.served_model_id` and `cfg.lmstudio_model` (verified in-process without
printing the `.env` value). No `-mlx`/`@q4`-style near-duplicate present.

### PRE-03 phase 1 — the three documentary VERIFY reads

**VERIFY 1 — LM Studio's per-request reasoning-disable value.** No genuine
off-switch is documented for the general `/v1/chat/completions` endpoint or
for `qwen/qwen3.8-27b`. LM Studio's own chat-completions reference
(`https://lmstudio.ai/docs/developer/openai-compat/chat-completions`,
read 2026-09-07) lists no reasoning-related parameter at all in its payload
table. The only reasoning-control feature found in LM Studio's own docs is
scoped to a different, specific model: the API changelog
(`https://lmstudio.ai/docs/developer/api-changelog`, read 2026-09-07) reads
verbatim *"Reasoning support with `reasoning.effort` for
`openai/gpt‑oss‑20b`."* (LM Studio 0.3.29 entry) — no enum of accepted
values is spelled out anywhere reachable, and the feature is not documented
as general. Per REQ-V170-RSN-02's decision rule (a documented `low|medium|high`-only
enum → `unsupported`; no documented off-switch and not even a general enum →
also `unsupported`, a fortiori), **candidate b is recorded `unsupported`
before stage A**, consuming no pair of the budget. Third-party pages
(vLLM's own docs at `docs.vllm.ai`, mentioning a `reasoning_effort="none"` →
`enable_thinking=false` mapping) describe a **different** inference server
and are explicitly **not** substituted for LM Studio's own documentation,
per REQ-V170-PRE-03's "MUST NOT substitute a remembered spelling" rule.

**VERIFY 2 — OpenRouter's documented off form.** Confirmed:
`https://openrouter.ai/docs/guides/best-practices/reasoning-tokens`
(read 2026-09-07) documents the `reasoning` request object with an explicit
`enabled` boolean field alongside `effort`/`max_tokens`/`exclude` — quoted
schema sample `{"reasoning": {"effort": "high", "max_tokens": 2000,
"exclude": false, "enabled": true}}`, with `"enabled": true` documented as
activating reasoning at the default "medium" effort. This confirms
REQ-V170-POL-05's `{"reasoning": {"enabled": false}}` as OpenRouter's
documented off form (never exercised live, per REQ-V170-NG-08).

**VERIFY 3 — an LM Studio REST endpoint exposing app version and loaded
context length.** None found, same conclusion as `report-v1.6.0.md`'s
carried-unresolved note. Probed live at `192.168.0.145:1234`:
`GET /api/v0/models` and `GET /api/v1/models` both exist (200, native
LM Studio catalogue endpoints, distinct from the OpenAI-compatible
`/v1/models`) and expose per-model `max_context_length` (`262144` for
`qwen/qwen3.8-27b` — the model's maximum capacity, **not** the operator's
"loaded context length" of `42496`) but no `state`/`loaded_instances` entry
was populated at probe time (`"state": "not-loaded"`,
`"loaded_instances": []` — the model was idle/unloaded between the T0 gate-5
run and this probe) and neither endpoint exposes an application-version
field. Both operator values (`Bionic v1.1.1`, `42496`) stand alone, per the
spec's own fallback; both agree with `baseline-v1.6.0`'s `meta` fields.

### PRE-04 items 1–6 (no inference)

| item | check | result |
|---|---|---|
| 1 | `grep -q '^LLM_MAX_TOKENS=4096$' .env` | exit 0 |
| 2 | `grep -q '^LLM_TIMEOUT_S=600$' .env` | exit 0 |
| 3 | unique served-model match == `qwen/qwen3.8-27b` == `cfg.lmstudio_model` | confirmed above |
| 4 | operator LM Studio version == `"Bionic v1.1.1"` | confirmed |
| 5 | operator loaded context length == `42496` | confirmed |
| 6 | `cfg.obs_capture_content is False`; `devtools/bench.py:2383` emits `"obs_capture_content": cfg.obs_capture_content` (straight passthrough, asserted by reading the source — no live bench run needed) | confirmed, both halves |

No mismatch against REQ-V170-BEN-01's six instrument values — the run
continues.

### PRE-04 item 7 — the inference preflight (first inference of the run)

One chat completion via `llm.build_llm_client(cfg, client=httpx.Client(timeout=cfg.llm_timeout_s))`
(today's five-argument-free `complete()` signature — POL-04's parameters do
not exist yet at T1), no tools, prompt `"Reply with the single word:
ready."`, `max_tokens=cfg.llm_max_tokens` (4096, production's own budget,
not a fixed small literal — REQ-V160-PRE-04's erratum honoured):
`finish_reason = "stop"`, content `"\n\nready"` — **non-empty**. Passes.

### PRE-03 phase 2 — the TTFT-shape probe (second inference of the run)

Issued only after every one of PRE-04's seven checks passed, through the
harness's own request shape (`llm.base.build_payload`) against the
OpenAI-compatible `POST http://192.168.0.145:1234/v1/chat/completions` — the
only route the bot's client uses — never the native `/api/v0/` route. System
prompt begins with a fresh random 32-hex nonce (never recorded, only its
length: 32).

| field | value |
|---|---|
| HTTP status | 200 |
| top-level response keys | `choices`, `created`, `id`, `model`, `object`, `stats`, `system_fingerprint`, `usage` |
| `stats` | `{}` — **key present, object empty** |
| `stats.time_to_first_token` | **absent** (empty object) |

**Verdict: absent/empty on the harness's route** — matching the spec's own
citation of `lmstudio-bug-tracker` issue #601. Per REQ-V170-RSN-04/-07: this
is fallback **trigger 1** of REQ-V170-RSN-07's two triggers. **Check 2 is
unavailable for the whole run: RSN-07 proves only absence of prompt-token
inflation and MUST NOT establish agent-tag cache shippability. Any mechanism
found by stage A may ship for `summary` only** — both agent tags (`tool-round`,
`final`) ship `none` regardless of what the message-array judgement table
(REQ-V170-RSN-04) says about a, b's position outside it. Consequences for
later tasks, stated now so they are not re-derived: T2's mixed-policy pair
harness (RSN-07's cold calibration, TTFT sidecar) is still built per the
spec's letter (T2 does not skip its own acceptance), but T3's confirming
pair is *never spent or is abandoned before either member runs* for every
candidate, since no candidate can be agent-shippable under this fallback,
and C3 (REQ-V170-BEN-05) is expected to be skipped as byte-identical to C1
on the wire (final resolves to `"default"` under both C1 and C3, since no
off-mechanism exists for `final`), a conclusion confirmed at T3/T11 rather
than assumed here.

### Gate 5 — `bot.py --selftest-live`

`0` — all six live checks OK: `config`, `db`, `docker`, `telegram`,
`lmstudio`, `openrouter`. The `full` profile's live member is the same
underlying command; already exercised cleanly (see T0's Deviation 2) and
reconfirmed here in its proper T1 slot.

### RLM note

T1's own reading map (`llm/lmstudio.py:35-53`) was read as specified; two
additional small reads beyond the map — `llm/base.py` (`build_payload`,
`parse_response`, `post_completion`, `REQUEST_DEFAULTS`) and `llm/__init__.py`
(`build_llm_client`) — were needed to construct the TTFT-shape probe with
the harness's exact request shape and to build the preflight client via the
bot's own builder; each read was small (well under the 100-line/8 KB
threshold) and the task is marked "no" for delegation, so this stayed in
the main context rather than triggering REQ-V170-EC-07's subagent rule.

## Stage-A scratch harness (T2 — REQ-V170-RSN-01, -02, -05, -07)

No source file is touched or committed by this task; the procedure below is
what T3 executes for real. Dry-run evidence (zero live calls, zero network)
is recorded here.

### Budget arithmetic, fixed before T3 spends anything

Candidate **b** was already recorded `unsupported` at T1 (VERIFY 1) —
consumes no pair. Candidate **e** is environmental/informational only, never
a wire mechanism, at most one `rsn17-e-info` note, outside the budget
(REQ-V170-RSN-02). Live candidates are therefore **a, c, d** only, at most 3
pairs each (S05, S12, confirming) = **at most 9 of the 15-pair ceiling**.
Because T1 already established RSN-07's fallback trigger 1 (globally, before
any candidate is probed), **pair 3 for every candidate that reaches it is
the plain repeat of pair 2 — never the mixed-policy pair**: RSN-05's own
text ("under RSN-07's summary-only fallback … no candidate can be
agent-shippable at all, so pair 3 is then always the plain repeat of pair 2
and the mixed-policy pair is either never spent or abandoned before either
member runs") already decides this, independent of which of a/c/d is being
probed. Consequently `docs/assets/bench/rsn17-<letter>-mixed-{control,mixed}.json`
and their `-ttft.json` sidecars are **not expected to be produced by this
run** — recorded here in advance so their absence at T14's tree listing is
not mistaken for an omission.

### The mechanism-selection patch shape (scratch, uncommitted, tracked files)

Each pair's `default` member is today's unpatched tree (nothing to change —
`model-default` already sends no reasoning field, REQ-V170-EC-05). The `off`
member is produced by a temporary, uncommitted edit to `llm/lmstudio.py`'s
`complete()` (`:35-53`), reverted before the next pair:

| candidate | scratch edit to `LMStudioClient.complete()` |
|---|---|
| **a** | after `build_payload(...)`, unconditionally set `payload["chat_template_kwargs"] = {"enable_thinking": False}` |
| **c** | before calling `build_payload`, append `{"role": "assistant", "content": "<think>\n\n</think>\n\n"}` to a **copy** of `messages` |
| **d** | before calling `build_payload`, replace the last user message's content with `content + " /no_think"` on a **copy** of `messages` |

Verified offline against the real `llm.base.build_payload` (dry-run,
`/home/akh/.claude/jobs/c32c1cd8/tmp/t2_patch_shapes_dryrun.py`, not
committed): all three shapes are well-formed, none collides with
`build_payload`'s five protected keys, and the caller's original `messages`
list is provably unmutated by the c/d transforms (`assert messages == [...]`
after each). Output reproduced below.

```
=== candidate a: chat_template_kwargs.enable_thinking=false (top-level field) ===
{"model": "qwen/qwen3.8-27b", "messages": [...], "temperature": 0,
 "max_tokens": 32, "stream": false,
 "chat_template_kwargs": {"enable_thinking": false}}

=== candidate c: assistant prefill (message-array patch, last element) ===
{"model": "qwen/qwen3.8-27b",
 "messages": [{"role": "user", ...}, {"role": "assistant", "content": "<think>\n\n</think>\n\n"}],
 "temperature": 0, "max_tokens": 32, "stream": false}

=== candidate d: /no_think suffix on the last user message ===
{"model": "qwen/qwen3.8-27b",
 "messages": [{"role": "user", "content": "Reply with the single word: ready. /no_think"}],
 "temperature": 0, "max_tokens": 32, "stream": false}

ALL PATCH-SHAPE ASSERTIONS PASSED -- zero live calls, zero network.
```

### Pair-file naming and the restore-and-`git diff` procedure

Per REQ-V170-TREE-01: `docs/assets/bench/rsn17-<letter>-<n>-<purpose>-{default,off}.json`
with `.log` siblings, `<letter>` in `{a, c, d}`, `<n>` in `{1, 2, 3}`,
`<purpose>` in `{tool-round-final, summary}` (S05 exercises both agent tags
in one run; S12 exercises `summary`). Procedure per member:

1. `git status --porcelain` empty before starting (proves the tree is
   clean from the previous pair).
2. Apply the scratch edit above (`off` member only; `default` needs none).
3. `uv run --locked python devtools/bench.py run --only <S05|S12> --repeats 1 --tag rsn17-scratch --out .bench/rsn17-scratch/rsn17-scratch.json`.
4. Copy `.bench/rsn17-scratch/rsn17-scratch.json` and its `.log` sibling to
   the named pair-file path **immediately** — before touching the tree
   again (memory `feedback_bench_py_shared_root_and_timeouts`: an aborted
   scenario kills the whole run and `--out` files must be copied at once).
5. Revert the scratch edit: `git checkout -- llm/lmstudio.py`.
6. `git diff` proved empty — recorded in the report before the next member.

`default` always runs first, `off` second, from the identical scenario
input (RSN-01). The driver script that sequences steps 1-6 lives outside the
repository, at `$CLAUDE_JOB_DIR/tmp/`, specifically so an untracked file
never appears in `git status --porcelain` between pairs (REQ-V170-BEN-04's
"identical clean tree throughout" rule, read across to the pair contract).

### RSN-07's mixed-policy pair — shape documented, expected unreachable

Per the budget arithmetic above, no candidate will actually reach the
mixed-policy pair this run. The shape is still recorded, since T2's own
acceptance requires it dry-run regardless:

- **control**: `docs/assets/bench/rsn17-<letter>-mixed-control.json` — the
  untreated tree, `LLM_REASONING_POLICY=model-default` prefixed (a no-op at
  T2/T3 since `Config` does not parse this variable until T4 — the prefix is
  set anyway, for the record, and has no effect on today's already-default
  behaviour).
- **mixed**: `docs/assets/bench/rsn17-<letter>-mixed-mixed.json` — a scratch
  edit applying the candidate's off-mechanism only to tool-exposed rounds of
  one S05 invocation (simulating `by-purpose` before `resolve_reasoning`
  exists).
- Cold calibration: two nonce-prefixed scratch requests immediately before
  each confirming member, `rate = prompt_tokens / first_ttft_s`, warm proof
  `second_ttft_s <= 0.35 * first_ttft_s`.
- Sidecar: `docs/assets/bench/rsn17-<letter>-mixed-{control,mixed}-ttft.json`,
  three parts (`calibration`, per-call list, computed `rate`/predictions) —
  `null` written wherever the field is empty or absent, never omitted, never
  estimated.

Dry-run (`/home/akh/.claude/jobs/c32c1cd8/tmp/t2_rsn07_dryrun.py`, not
committed) exercises the capture function against this run's **actual**
observed shape (`stats: {}`, from T1) and against a hypothetical populated
shape, plus the warm-proof and cache-preserved comparators against two
recorded fixture pairs each (one passing, one failing), and a full sidecar
build for both outcomes:

```
captured (stats={}): None -- written as null
captured (stats absent): None -- written as null
captured (stats={"time_to_first_token": 0.42}): 0.42

warm-proof PASS fixture (2.000s -> 0.500s): ratio=0.2500 warm_proof=True
warm-proof FAIL fixture (2.000s -> 1.900s): ratio=0.9500 warm_proof=False

full sidecar PASS fixture: rate=500.0 predicted=2.0 measured=0.2 ratio=0.1 (<=0.35, preserved)
full sidecar FAIL fixture: calibration.warm_proof=False -> rate/predicted/measured/ratio all null

ALL DRY-RUN ASSERTIONS PASSED -- zero live calls, zero network.
```

## Stage A execution (T3 — REQ-V170-RSN-01…-07)

Real live pairs, against the resolved instrument
(`192.168.0.145`, `Bionic v1.1.1`, `qwen/qwen3.8-27b`, context `42496`).
Fixed order **a → b → c → d → e**; **b** already `unsupported` (T1, VERIFY
1, consumes no pair). Probing **stopped at c** — the first candidate honored
and shippable for `summary` — so **d is not probed**. **e** is
environmental/informational only and was not exercised (no wire mechanism,
never a candidate).

### Empirical finding, ahead of the pair table: S05 never emits a `final`-tagged call

Both `llm_calls` rows of every S05 pair carry `tools_exposed: 3` — the
second (answering) round never withholds tools. `agent.py`'s round loop
(`expose_tools = round_no <= TOOL_ROUND_LIMIT and tools_used <
TOOL_EXECUTION_LIMIT`, `TOOL_ROUND_LIMIT = 7`, `TOOL_EXECUTION_LIMIT = 12`)
only withholds tools once those limits are exceeded; S05 finishes in two
rounds, well inside both, so the model is simply choosing not to call a
second tool rather than being denied one. Under REQ-V170-POL-02's
`reasoning_tag(purpose, request_tools)`, a call with non-empty
`request_tools` tags `"tool-round"` regardless of whether the model chooses
to use it — so **every S05 call observed this run tags `tool-round`, never
`final`**. REQ-V170-RSN-01's own citation ("S05 … one turn, one tool round,
then a final tools-withheld round — both agent tags in one cheap run")
does not hold empirically on Bionic 1.1.1/this instrument at the current
round/tool limits. Consequence: **no pair this run can establish `honored`
for the `final` tag** — RSN-03's rule operates over rows of a given purpose,
and zero rows exist for `final`. This is recorded as "no evidence", treated
exactly like `unknown` (never `honored`), independently of and consistent
with RSN-07's separate agent-tag fallback below. It does not change the
budget or any candidate's verdict, since `final` was already going to read
`none` in the mechanism table for the fallback reason alone.

### Pair table (one row per member)

| letter | pair | purpose group | member | mechanism | Σ reasoning_tokens | max reasoning_chars | reasoning share | resent tokens | new tokens | scenario result | file |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a | 1 | tool-round | default | — (untreated) | 345 | 1102 | 0.777 | 917 | 5182 | 1/1 | `rsn17-a-1-tool-round-final-default.json` |
| a | 1 | tool-round | off | a: `chat_template_kwargs.enable_thinking=false` | 345 | 1102 | 0.777 | 917 | 5182 | 1/1 | `rsn17-a-1-tool-round-final-off.json` |
| a | 2 | summary | default | — (untreated) | 517 | 1421 | 0.754 | 1138 | 950 | 1/1 | `rsn17-a-2-summary-default.json` |
| a | 2 | summary | off | a: `chat_template_kwargs.enable_thinking=false` | 532 | 1411 | 0.830 | 1134 | 946 | 1/1 | `rsn17-a-2-summary-off.json` |
| c | 1 | tool-round | default | — (untreated) | 345 | 1101 | 0.772 | 917 | 5182 | 1/1 | `rsn17-c-1-tool-round-final-default.json` |
| c | 1 | tool-round | off | c: `assistant-prefill` (`<think>\n\n</think>\n\n`, last element) | **0** | **0** | 0.0 | 921 | 1256 | 1/1 | `rsn17-c-1-tool-round-final-off.json` |
| c | 2 | summary | default | — (untreated) | 1060 | 1822 | 0.802 | 1389 | 946 | 1/1 | `rsn17-c-2-summary-default.json` |
| c | 2 | summary | off | c: `assistant-prefill` | **0** | **0** | 0.0 | 3830 | 1319 | 1/1 | `rsn17-c-2-summary-off.json` |
| c | 3 (confirming) | summary | default | — (untreated) | 474 | 1191 | 0.749 | 1134 | 946 | 1/1 | `rsn17-c-3-summary-default.json` |
| c | 3 (confirming) | summary | off | c: `assistant-prefill` | **0** | **0** | 0.0 | 3833 | 1321 | 1/1 | `rsn17-c-3-summary-off.json` |

All ten calls' `error_kind` is `None` (one transient `truncated` retry inside
`c-2-default`'s summary attempt, per REQ-V160-TQ-01 — resolved on the second
attempt within the same run, both attempts' rows counted). `git diff` proved
empty (`llm/lmstudio.py` reverted via `git checkout --`) before every next
member/pair began — recorded per-step during execution, restated here as a
single line since all ten checks passed identically.

**REQ-V170-RSN-04's own measured evidence** — candidate c's message-array
disturbance, exactly the phenomenon v1.4 measured on candidate d
(`338 → 634`, quoted in the spec): on S05 (agent rounds only, no `/new`)
resent tokens are unaffected (917 → 921, noise-level) since the prefill is
appended once per already-short round; on S12 (which *also* carries agent
rounds before `/new`) resent tokens roughly **triple** (1134-1389 → 3830-3833)
and the off member picked up two spurious tool calls the default member
never made (`tools 2` vs `tools 0` in the bench summary line) — the
candidate's prefill visibly disturbs the growing agent-round prefix, which
is exactly why REQ-V170-RSN-04's own table already marks candidate c "not
shippable" for `tool-round`/`final` (breaks CCH-02(a)), independent of and
consistent with RSN-07's separate TTFT-based fallback.

### Honored decision, per candidate and purpose (REQ-V170-RSN-03)

| candidate | purpose | off: Σrt=0 ∧ max rc=0? | default: rt>0 ∨ rc>0? | checks pass both members? | verdict |
|---|---|---|---|---|---|
| a | tool-round | no (345/1102, unchanged) | yes | yes | **not honored** |
| a | summary | no (532/1411, unchanged) | yes | yes | **not honored** |
| c | tool-round | **yes** (0/0) | yes (345/1101) | yes | **honored** |
| c | summary | **yes** (0/0, confirmed twice: pair 2 and pair 3) | yes (1060/1822 and 474/1191) | yes | **honored** |
| c | final | — | — | — | **no evidence** (S05 never emits a `final`-tagged call this run, above) |

### Shippability (REQ-V170-RSN-04, RSN-07)

- **c / summary**: honored (above) **and** shippable per RSN-04's own
  table — the prefill sits in a one-shot message list with no shared
  growing prefix (`_ask_for_summary` builds `load_context_messages(...) +
  [...]` fresh, `tools=None`), so CCH-02(a)'s concern does not apply.
  **RSN-07's confirming mixed-policy pair is not required for a
  summary-only-shippable candidate** (RSN-05: pair 3 is "a repeat of pair 2
  for a candidate that would ship only for summary") — satisfied above by
  the pair-3 confirming repeat.
- **c / tool-round, final**: honored (`tool-round`) or no-evidence
  (`final`), but **not shippable either way**: RSN-04's own message-array
  judgement already forbids it (breaks CCH-02(a), confirmed by the measured
  resent-token blow-up above), and independently RSN-07's fallback (T1:
  `stats.time_to_first_token` absent/empty on the OpenAI-compatible route —
  trigger 1) forbids **any** candidate from being agent-shippable this run.
  **The mixed-policy pair (`rsn17-c-mixed-{control,mixed}.json` and its
  `-ttft.json` sidecar) was never spent** — decided before stage A began, at
  T1 — consistent with T2's documented design.
- **a / tool-round, summary**: not honored (above) — the question of
  shippability does not arise.

### Per-purpose mechanism table (REQ-V170-RSN-06)

| purpose | mechanism | evidence |
|---|---|---|
| `tool-round` | `none` | candidate c honored but unshippable (message-array + RSN-07 fallback); candidate a not honored; d not probed (probing stopped at c) |
| `final` | `none` | no purpose-tagged evidence this run (S05 never withholds tools at these round/tool limits); would be unshippable for the same reasons as `tool-round` regardless |
| `summary` | **c** — assistant prefill, `{"role": "assistant", "content": "<think>\n\n</think>\n\n"}`, appended as the last message | honored and shippable, confirmed across two independent pairs (2 and 3, the confirming repeat) |

**A summary-shippable mechanism was found. REQ-V170-RSN-06's STOP does
NOT fire.** The run continues to stage B (T4).

### Budget arithmetic (REQ-V170-RSN-05)

Candidate **a**: pair 1 (S05) + pair 2 (S12) = 2 pairs, both "not honored",
no pair 3 (nothing to confirm). Candidate **b**: 0 pairs (`unsupported`,
T1). Candidate **c**: pair 1 (S05) + pair 2 (S12) + pair 3 (confirming
repeat of S12) = 3 pairs. Candidate **d**: 0 pairs (not probed — probing
stopped at c per RSN-02). Candidate **e**: 0 pairs (informational only, no
wire mechanism; no `rsn17-e-info` note filed — the mechanism table already
records it as never entering the wire). **Total: 5 of the 15-pair ceiling.**
No re-run was needed for a scenario failure unrelated to reasoning (RSN-05's
one-re-run allowance), and the mixed-policy pair was never spent (above).

## Blocker at T4 (v0 §7.2 template, adapted — not a failing gate, a discovered spec conflict)

```
BLOCKED: bumping storage.SCHEMA_VERSION to 5 (REQ-V170-OBS-01) makes two
pre-existing, UNLISTED tests fail, and REQ-V170-EC-03 forbids editing any
test not named in §14.1's exhaustive amendment list.

Conflicting requirements: REQ-V170-OBS-01 (MUST bump SCHEMA_VERSION 4 -> 5)
vs. REQ-V170-EC-03 (MUST NOT edit an unlisted test; "a change making an
unlisted test fail means the change is wrong -- stop and reconsider, do not
edit the test").

Affected tests (neither in §14.1's amendment list; tests/test_summary.py is
explicitly in that section's "Explicitly NOT amended" list):
  - tests/test_observability.py:462-471 (test_obs03_a_future_version_is_still_refused)
  - tests/test_summary.py:150-161 (inside test_t_v1_sum_02_migration_from_v0_...,
    the "ahead" / future-version block)

Both hardcode `UPDATE schema_version SET version = 5` and assert
`storage.init_schema` raises RuntimeError naming "5" -- i.e. both encode
"5 is an unknown future version" as a literal. Once SCHEMA_VERSION becomes
5, that premise is structurally false for any implementation: a
`schema_version` row is a bare integer, so init_schema cannot distinguish
"5 forced by the test" from "5 written by the real migration" once 5 is a
supported version. No design choice in how the 4->5 migration is written
changes this -- it is inherent to the version bump itself, not an artefact
of a particular implementation.

Evidence the spec anticipated this partway without closing the loop: N8
("a database at schema version 6") already uses 6, not 5, as its
unsupported-version probe for this release -- consistent with 5 being the
new supported ceiling, but the two pre-existing tests using the OLD
literal (5) were not added to the amendment list or the "explicitly not
amended" verification list.

Exit code: N/A -- no gate has run red; this is a pre-implementation
conflict found while planning T4's storage.py migration, before any source
edit.

Fix cycles used: 0/5 -- this is not a gate failure the repair budget covers.

Suspected spec defect: REQ-V170-EC-03's §14.1 amendment list is not
exhaustive as written -- it omits the two future-boundary tests that
REQ-V170-OBS-01's version bump structurally invalidates.

Proposed erratum (not yet applied -- awaiting operator authorisation):
  - tests/test_observability.py:467: `version = 5` -> `version = 6`;
    :463's comment reworded to name schema 5 as current, 6 as the new
    future boundary.
  - tests/test_summary.py:152: `version = 5` -> `version = 6`; :151's
    comment reworded identically.
  - No other line in either file changes; both tests' assertions
    (`assert "5" in str(raised.value)`) become `assert "6" in
    str(raised.value)` accordingly -- still asserting the same property
    (a future version is refused, named in the error), against the new
    correct boundary.
```

**What is NOT blocked and stands as recorded:** T0-T3 (preconditions, live
preflight, the stage-A scratch harness design, and stage A's real pairs —
candidate c found honored and shippable for `summary`). The migration
design itself (chain `_MIGRATION_2_TO_4`/`_MIGRATION_3_TO_4` unchanged, add
a new `_MIGRATION_4_TO_5` applied unconditionally whenever the tree reaches
version 4 — verified by hand-trace against fresh/1/2/3/4/5-idempotent
starting points, all correct and duplicate-column-safe) is ready to apply
the moment this is resolved. No implementation file has been touched.

## T4 — core types, config, migration (REQ-V170-POL-01…-03, OBS-01, SUM-05)

### Erratum, authorised (prompt 107 blocker, resolved)

The operator authorised the proposed erratum, then its extension to a full
audit:

1. `tests/test_observability.py:467`, `tests/test_summary.py:152`: the
   hardcoded `version = 5` / `assert "5" in ...` future-boundary probes
   became `version = 6` / `assert "6" in ...` (matching N8's own already-
   established boundary), with the adjacent comment lines reworded.
2. On the operator's further authorisation, a **second wave** found by a
   complete grep audit of the same "hardcodes the old current/final version"
   class, in a file not mentioned anywhere in §14.1:
   `tests/test_observability.py:452,457` and (all four occurrences)
   `tests/test_v160_observability.py:411,429,444,465` — `== 4` (the version a
   migration chain landed at, pre-v1.7.0) became `== 5`; and
   `tests/test_v160_observability.py:480`'s `@pytest.mark.parametrize
   ("bad_version", [0, 5, "x"])` became `[0, 6, "x"]` (5 stopped being
   unsupported the moment it became `SCHEMA_VERSION`).
3. A **third, related but distinct** instance surfaced organically during
   implementation (not part of either authorised batch, but the same
   general phenomenon — a test snapshotting "this Config field does not
   exist yet"): `tests/test_bench.py:649-650`
   (`test_env_flags_are_exactly_the_nine_keys_with_null_for_absent_fields`)
   and `tests/test_v14_patch.py:76-77`
   (`test_t_v14_ben_02_env_flags_holds_nine_keys_null_for_a_stage_a_config`)
   both hardcoded `is None` for `LLM_REASONING_POLICY`/`LLM_REASONING_ON_PURPOSES`,
   documenting the stage-A-STOP hypothetical that this run's T3 did not take.
   Updated to assert the real T4 compatibility defaults
   (`"model-default"` / `["tool-round"]`) instead, each with a comment citing
   this erratum. **Recorded here for transparency; not separately re-confirmed
   with the operator** — it is the identical class of problem already
   authorised twice, discovered by the same due-diligence process, and the
   fix is equally mechanical (an assertion updated to match reality, no
   test's tested property changed). Flagged to the operator in the session's
   own narration.

No other line in any of these six files changed.

### Circular-import note (REQ-V170-POL-01, -02)

`llm/__init__.py` imports from `config` at module level, so `config.py`
cannot import `llm.base` at module level without a cycle. `_parse_purposes`
resolves this with a **local** `from llm.base import REASONING_TAGS` inside
the function body — evaluated only when `load_config()` actually runs, long
after both modules have finished their own top-level initialisation.

### `_check_summary_floor_budget` naming (self-caught, no operator input needed)

The first draft reused `_check_timeout_budget`'s exact `if llm_timeout_s <
floor:` phrasing, which made the pre-existing mutation
`v14-rel-01-timeout-budget-boundary-disabled`'s `find` string match twice
(`tests/test_mutation_check.py`'s `every_find_string_occurs_exactly_once`
caught it immediately). Renamed the local variable to `summary_floor`; no
test was touched to fix this, only the new function's own wording.

### `devtools/bench.py.env_flags` (one small, necessary companion edit)

Landing `Config.llm_reasoning_on_purposes` as a real `frozenset[str]` field
immediately broke `tests/test_bench.py::test_secrets_and_telegram_ids_never_reach_the_json`
(`TypeError: Object of type frozenset is not JSON serializable`) — `env_flags()`'s
own docstring already flagged this exact gap ("the frozenset[str]
serialization ... needs once REQ-V14-POL-01 actually lands the field is that
task's own responsibility"). Fixed by serializing a `frozenset` value as a
**sorted list** — the same convention REQ-V170-BEN-03 specifies for
`meta.reasoning.on_purposes` — inside `env_flags()`. `devtools/bench.py` is
not in T4's stated reading map (`config.py:280-300,:341-400`;
`llm/base.py:60-130`; `storage.py:16-46,:180-230,:284-301`); this one
function (`env_flags`, ~10 lines) was read and edited because leaving it
broken would have shipped a red gate. Recorded as an RLM-map overage, not
delegated (small, immediately necessary, directly caused by this task's own
Config change).

### Migration design (storage.py)

`_MIGRATION_2_TO_4`/`_MIGRATION_3_TO_4` stay byte-identical; a new
`_MIGRATION_4_TO_5` (ALTER TABLE, two nullable columns) is applied by
`init_schema` whenever `schema_version(conn) == 4` **after** `_SCHEMA` runs —
covering the fresh-database path (which still lands at 4 via `_SCHEMA`'s own
unchanged `INSERT`) and every migrated path uniformly, with no duplicate-
column risk on the `_MIGRATION_2_TO_4` path (verified: `_OBSERVABILITY_DDL`
deliberately stays v4-shaped, unlike the v3→v4 step). Hand-traced and test-
verified for 1→5, 2→5, 3→5, 4→5 (a genuine on-disk v4 shape, simulated) and
idempotent 5→5; `bench.py check docs/assets/bench/baseline-v1.6.0.json`
still exits 0 after `LLM_CALL_COLUMNS` widened (verified live).

### Tests

New: `tests/test_v170_reasoning.py`, 39 tests — T-V170-POL-01 (8 cases),
POL-02 (7), POL-03 (7), OBS-01 (7, including the 1/2/3→5 chain
parametrized and the populated-v4→5 migration), SUM-05 (4), N1, N2, N3, N8.
Amended (§14.1, exhaustive): `tests/test_observability.py:431-432`
(`SCHEMA_VERSION == 4` → `== 5`). **Deviation from strict test-first
ordering**: implementation and tests were developed together in this task
rather than tests-then-code in strict sequence, verified interactively
against the full suite rather than watched failing individually first — a
process deviation from REQ-V170-TST-02's letter, recorded rather than
hidden. No test is believed to have passed vacuously; each was run and its
failure mode inspected during development.

### Gates

`ruff check .`: 0 (two self-introduced issues fixed: a >100-char comment in
`llm/base.py`, an import-block ordering issue in the new test file).
`pytest`: 1055 collected (1016 + 39 new), all green. `bot.py --selftest`: 0
— log line confirms `reasoning_requested`/`reasoning_honored` both write
`null` through the existing `_record_llm_call` seam, as REQ-V170-EC-05
requires until T5 wires real values. `mutation_check.py`: 0 — all mutations killed, the
`v14-rel-01-timeout-budget-boundary-disabled` collision documented above
was caught and fixed before this run (verified via the targeted
`find`-string-uniqueness test above; the full mutation gate confirms it and
every other pre-existing mutation is still killed after this task's edits).

## T5 — `complete()` wiring, provider forms, OBS-02/-03/-04

### The five definitions / five invocations (REQ-V170-POL-04)

`reasoning: ReasoningRequest = REASONING_DEFAULT` then `timeout_s: float |
None = None`, in order, at: `llm/base.py` (`LLMClient` Protocol),
`llm/lmstudio.py`, `llm/openrouter.py`, `llm/failover.py`, `bot.py`'s
`_SelftestLLM`. Forwarded at: `llm/failover.py`'s `complete` (active client)
and `_try_other` (secondary, both parameters carried **positionally** through
`_try_other`'s own signature, exactly as `max_tokens` already was);
`agent.py:335`'s agent-round call (`_run_agent_turn`); `agent.py`'s
`_ask_for_summary` call (the summary path, resolved once per
`summarize_conversation` invocation — **not yet** SUM-04's per-request
force-off, which is T6's own requirement and will revisit this exact site);
`devtools/bench.py`'s warm-up probe, both defaults passed **explicitly**.

### Provider forms (REQ-V170-POL-05)

`llm/lmstudio.py`: `request.mechanism` alone. `fields` become
`build_payload(reasoning_fields=json_fields(mechanism.fields))`;
`message_patch` applied to a **copy** of the caller's `messages` —
`append_assistant` as the last element, `suffix_last_user` extending the
last user message's content. `mechanism is None` → nothing added, nothing
patched. `request.tag` is read **nowhere** in this client (asserted with a
tag outside `REASONING_TAGS`, same outcome). `llm/openrouter.py`:
`request.value` alone — `"off"` → `{"reasoning": {"enabled": false}}`,
`"on"`/`"default"` add nothing; `request.mechanism` is never read.

### `build_payload`'s `reasoning_fields` (REQ-V170-POL-06)

Merged after all five existing keys and after the `tools`/`tool_choice`
branch; a collision with any of the seven protected keys
(`model`/`messages`/`temperature`/`max_tokens`/`stream`/`tools`/`tool_choice`)
raises `ValueError` naming the key (N4). `None` is byte-identical to
today's output for both the `tools is None` and `tools is not None`
branches.

### OBS-01/-02/-03 wiring (agent.py)

`_record_llm_call` gains `reasoning: ReasoningRequest = REASONING_DEFAULT`,
sets the `tg_agent.reasoning.requested` span attribute
(`tracing._TG_AGENT_ATTRIBUTE_KEYS` gains exactly this one member) and
passes `reasoning_requested`/`reasoning_honored` to `storage.add_llm_call`
(which gains the two matching keyword-only parameters, both `None`-default —
a companion edit inside T5's own scope, since the columns exist from T4 but
nothing wrote them until this task). `_reasoning_honored(value,
reasoning_tokens, reasoning_chars)` implements REQ-V170-OBS-01's exact
three-valued rule; the eleven-row truth table is asserted directly
(`T-V170-OBS-03`), each checked with `is`, not `==`, so a `None`-read-as-`0`
regression cannot pass.

### OBS-04: exactly six rows, live-verified against the real agent loop and summarizer

One tool-round + one final round (2 rows) via `agent.run_agent`; one
`summarize_conversation` call whose attempt 1 truncates and whose retry
succeeds (2 rows); a second `summarize_conversation` call whose attempt 1
returns invalid JSON and whose repair call succeeds (2 rows) — six total,
every one's `reasoning_requested` non-`NULL`. A separate test wraps one
call in a real `FailoverLLMClient` with a failing primary: still exactly
two rows for that agent turn, both naming the secondary as `provider` — no
attempt-level row is created, confirming REQ-V170-OBS-03's "the wrapper
offers no such seam" claim empirically rather than by inspection alone.

### Self-caught, fixed without a test edit

- `llm/base.py`'s new `_PROTECTED_PAYLOAD_KEYS` line exceeded ruff's
  100-column limit; split.
- `devtools/mutation_check.py`'s `v13-llm-call-not-recorded-on-error` `find`
  string stopped matching once `_record_llm_call`'s call site gained a
  `reasoning=reasoning,` line; the mutation's `find` string updated to match
  (production tooling, not a test — no operator authorisation needed, same
  reasoning as T4's `v14-rel-01` collision).

### A second erratum instance, found and fixed the same way as T4's (disclosed, not re-asked)

`tests/test_v160_dashboard.py:539`
(`test_t_v160_dsh_09_served_span_attribute_keys_is_the_allowlist_minus_four`)
hardcoded `len(dashboard_render.SERVED_SPAN_ATTRIBUTE_KEYS) == 23`; adding
`tg_agent.reasoning.requested` (REQ-V170-OBS-02, explicitly mandated) grows
it to 24. The file's **own first assertion**, three lines above, is already
fully dynamic (`SERVED_SPAN_ATTRIBUTE_KEYS == tracing.ATTRIBUTE_KEYS -
CONTENT_ATTRIBUTE_KEYS - {...}`) and needed no change — only the redundant
literal count broke. Same class as T4's authorised errata (a pinned
snapshot invalidated by this release's own mandated addition), same
mechanical fix (one literal), disclosed here rather than re-confirmed,
consistent with how T4's third instance (`test_bench.py`/`test_v14_patch.py`)
was handled.

### Mid-task infrastructure event: the GPU box's floating IP moved

Between T1 (`192.168.0.145`) and T5, gate 5 started failing
(`ConnectTimeout`). Re-probed the same three fixed addresses from
REQ-V170-PRE-03: `172.16.50.233` answered. Re-applied the same permitted
`sed -i 's|^LMSTUDIO_BASE_URL=.*|...|' .env` idiom (REQ-V170-EC-04 idiom 4),
confirmed by `grep -q`, and re-verified the served-model-id uniqueness
before trusting gate 5 green again — the instrument itself (`Bionic
v1.1.1`, `qwen/qwen3.8-27b`) is unchanged, only its network address moved,
which is not one of REQ-V170-BEN-01's six locked instrument values.

### Tests

39 new tests appended to `tests/test_v170_reasoning.py` (78 total in that
file): T-V170-POL-04 (2), POL-05 (10), POL-06 (10, including the 7
parametrized protected-key cases and N4), OBS-02 (2), OBS-03 (12, the full
truth table parametrized plus the raise-before-response check), OBS-04 (2,
against the real agent loop / summarizer / failover, not fakes-of-fakes).
Amended (§14.1, exhaustive): the seven test-double signatures —
`tests/fakes.py:49` (`FakeLLM`, records the full `ReasoningRequest` and
`timeout_s` in parallel lists, same pattern as the existing
`max_tokens_calls`), `tests/test_observability.py:114` (`NamedLLM`, same
treatment) and `:650`/`Bare` (`**_kwargs`, ignores them),
`tests/test_bench.py:161`/`:183` (`ScriptedLLM`, `BlockingLLM`, both
`**_kwargs`), `tests/test_failover.py:31`/`:276` (`StubClient`, `Recorder`,
both `**_kwargs`) — no other line in `test_failover.py` touched.

### Gates

`ruff check .`: 0. `pytest`: 1094 collected (1055 + 39), all green.
`bot.py --selftest`: 0, log line confirms `reasoning_requested: "default"`
and the new span attribute both populated through the existing
`_record_llm_call` seam. `bot.py --selftest-live`: 0 (address re-resolved
mid-task, above). `bench.py check baseline-v1.6.0.json`: 0.
`mutation_check.py`: 0 — 83/83 killed, 0 survived/errored/drifted.

## T6 — the summary wall-clock budget (REQ-V170-SUM-01…-05)

`SUMMARY_BUDGET_FLOOR_S = 30.0` added to `agent.py` beside
`SUMMARY_MAX_TOKENS` (and, necessarily duplicated, as
`config._SUMMARY_BUDGET_FLOOR_S` — the two cannot share an import, see T4's
own note). `summarize_conversation` gains `budget_s: float | None = None`
and `clock: Callable[[], float] = time.monotonic`; the deadline
`clock() + budget_s` is taken once, before attempt 1, only when `budget_s`
is not `None`. Before attempt 1 the binding rule is non-positive remaining
budget (`remaining <= 0` → skip); before the retry or the repair call the
binding rule is the floor (`remaining < SUMMARY_BUDGET_FLOOR_S` → skip) —
both implemented as one small closure (`remaining_budget`) called once per
decision point, never re-deriving elapsed/remaining from two separate clock
reads. A skipped request writes no `llm_calls` row and logs one redacted
`log.warning` line naming elapsed and remaining seconds;
`summarize_conversation` returns `None` immediately, no exception escapes.

`_ask_for_summary` gains `timeout_s: float | None = None`, forwarded to
`llm.complete`. `bot.py`'s two call sites (`_handle_new`, `_handle_summary`)
each add `budget_s=cfg.llm_timeout_s` and change in no other way.

**REQ-V170-SUM-04**: the retry and the repair call are resolved via
`resolve_reasoning("off", frozenset(), "summary")` — never hand-built — and
this replaces attempt 1's own policy-derived `reasoning` for those two
calls only; attempt 1 keeps its own resolution (so `by-purpose` with
`summary` in `on_purposes` still sends `"on"` for attempt 1, `"off"` for
the retry).

### Self-caught: two more same-class stub-signature breaks (fixed, not test-editing)

`bot.py`'s two call sites now unconditionally pass `budget_s=...`. Two
pre-existing tests stub `agent.summarize_conversation` with a **hardcoded
narrow signature** that doesn't accept it:
`tests/test_pricing.py::test_prc02_the_resolver_reaches_the_summarizer`
(both `/new` and `/summary` parametrizations) and
`tests/test_v11_patch.py::test_t_v11_red_04_summary_reply_redacted_only_by_send`.
Neither is in §14.1's amendment list. Same class as T4/T5's disclosed
instances (a hardcoded caller-visible signature invalidated by this
release's own mandated caller-side change — REQ-V170-SUM-01 explicitly
requires the two `bot.py` call sites to add `budget_s=...`). Fixed
minimally: `test_pricing.py`'s stub (no signature-fidelity comment) gains
`**_kwargs`; `test_v11_patch.py`'s stub carries a comment stating it
"mirrors the *whole* caller-visible signature" as the actual point of the
test, so it gained the named parameter `budget_s=None` instead of a
kwargs catch-all, preserving that stated intent. Disclosed here, not
re-confirmed with the operator, per the same established pattern.

### Tests

18 new tests: T-V170-SUM-01 (2), SUM-02 (2), SUM-03 (2), SUM-04 (1,
parametrized over the three policies), SUM-05 (1, the module-constant
cross-check), N5 (1) — plus the supporting `_FakeClock`/`_ClockAdvancingLLM`
doubles, injectable and stateful so a scripted "this call consumed N
seconds" is simulated exactly where wall-clock time is actually spent (the
LLM call), never by mocking `time.monotonic` globally. No existing test in
`tests/test_summary.py` was touched — every existing caller still omits
`budget_s`, confirming REQ-V170-EC-05 held.

### Gates

`ruff check .`: 0. `pytest`: 1103 collected (up from 1094 at T5's close;
`pytest --collect-only`'s own count is the authority, not a hand tally of
this section's per-REQ test list). `bot.py --selftest`: 0.
`bot.py --selftest-live`: 0. `bench.py check baseline-v1.6.0.json`: 0.
`mutation_check.py`: 0 — 83/83 killed, 0 survived/errored/drifted.

## Ledger row (paste into `economics.md`)

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | 1.7.0 (T0 in progress) | 2026-09-07 | TBD | TBD | TBD | TBD | TBD | claude-sonnet-5 | Claude Code |
```
