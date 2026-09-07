# Implementation report — spec-v1.7.0

**Status: T1 live preflight complete — no instrument mismatch, run continues to T2.**
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

## Ledger row (paste into `economics.md`)

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | 1.7.0 (T0 in progress) | 2026-09-07 | TBD | TBD | TBD | TBD | TBD | claude-sonnet-5 | Claude Code |
```
