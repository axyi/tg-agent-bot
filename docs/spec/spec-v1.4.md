# spec-v1.4 — close the v1.3 benchmark FAIL: honored reasoning control, S01 check repair, errata

The complete contract for a **patch release** on the delivered v1.3 state
(`main` at `3a0aa3d`). It is a **delta specification**: spec-v0 … spec-v1.3
remain in force except where a requirement here explicitly **amends**,
**supersedes** or **extends** them (section 2 is the authoritative amendment
table).

Every requirement has a stable `REQ-V14-*` id, tagged `MUST` (required for
acceptance), `SHOULD` (required unless a stated condition releases it, and the
release is declared in the report) or `NON-GOAL` (implementing it is a defect).
Requirements are cited here by short form (`BEN-03`, `POL-05`).

Platform **Linux**, language **Python**, package manager **uv**. Executor model
**claude-sonnet-5**: a bounded live experiment with a decision tree, over a
benchmark whose comparability rules are already mechanised in `devtools/bench.py`.
A larger model is not needed and must not be substituted for reading carefully.

**Provenance.** v1.3 shipped six token-economy optimizations and failed its own
§13.3 verdict on both gates (`docs/reports/bench-v1.3.md:166-178`; the figures
are recited once, in RPT-01 item 1). Its ranked lever list
(`report-v1.3.md:326-350`) puts a reasoning switch LM Studio actually honours at
**−31.6 % … −35.2 %** on its own — measured: reasoning is 71.8 % of completion
tokens, priced `$2.55/Mtok` against `$0.425/Mtok` for prompt. Levers 5 and 6 are
reliability. This release takes 1, 5 and 6, repairs S01 and re-baselines,
because each changes the measured treatment.

**Three problems, and nothing else.**

- **P1 — the gate.** Reach `C_plain ≤ 0.70 × B_v1.4` **and**
  `C_conservative ≤ 0.70 × B_v1.4` with the quality gate green, by controlling
  reasoning per call through a mechanism the running LM Studio honours.
- **P2 — the v1.2 cost erratum** and **P3 — the v1.3 prompt-count erratum**
  (RPT-04). Both are recorded in the new report, never rewritten in place.

**This is a patch release.** Behaviour changes only where a requirement below
says so: no new features, no refactoring beyond what a listed change requires,
no opportunistic cleanups; every v0…v1.3 acceptance property must still hold.
Appendix A maps problems to requirements, Appendix B is the acceptance scenario
set, Appendix C the cross-review log.

---

## 1. Execution contract

**REQ-V14-EC-01 (MUST)** Section 1 of spec-v0 … spec-v1.3 applies unchanged,
with these adjustments:

- "The gate commands" means the **six** commands of section 11, verbatim.
- The repair budget is **5 total** repair-and-rerun cycles (one cycle = one fix
  + one complete run of all gates from the first). Live benchmark steps are not
  gates and have their own retry rules (BEN-08).
- REQ-V1-EC-01 stands absolutely — the executor reads and writes **nothing
  outside the repository root** — with one exception: BEN-02's git worktree, a
  checkout of *this* repository at a named commit, created, used and removed by
  the executor; it reaches the repository's `.env` by absolute path (BEN-02
  item 3).
- The dependency set stays `httpx`, `python-dotenv`, plus the `docker` CLI as a
  host dependency. Everything this spec adds uses the standard library.

**REQ-V14-EC-02 (MUST)** Work test-first: write the tests of section 12 before
the production change they describe, observe them fail for the right reason,
then implement. Every new production branch of sections 6–9 gets a `v14-*`
entry in `devtools/mutation_check.py` (TST-05); gate 6 is the evidence.

**REQ-V14-EC-03 (MUST)** The v1.3 suite is **719 passing tests**
(`docs/plan.md:21`). No test may be deleted; existing tests may be modified
**only** where section 12.1 lists them, and that list is exhaustive. When a
change makes an unlisted test fail, the change is wrong — stop and reconsider,
do not edit the test. State the exact new count in the report.

**REQ-V14-EC-04 (MUST)** Secrets discipline is unchanged (REQ-V1-EC-04,
REQ-V11-EC-04, REQ-V12-EC-04): credential **values** are never printed, logged,
committed or quoted in `docs/`; presence checks are by key **name** only; tests
use the existing synthetic sentinel pattern. No task in this run opens `.env`,
`bot.db`, `exec_audit.jsonl` or `sandbox/` for content.

**REQ-V14-EC-05 (MUST)** Backward compatibility, as REQ-V12-EC-05: every new
parameter, config field and helper has a default reproducing v1.3 behaviour
when absent. `LLM_REASONING_POLICY`
ships as `model-default` until BEN-07 selects a winner; the flip to the winning
policy is the single post-benchmark change this spec authorises (BEN-09). One
internal exception, listed in AMEND-01: OBS-03's `complete()` return type.

**REQ-V14-EC-06 (MUST)** One prompt → one commit, on `main`, per `AGENTS.md`.
Each task of section 14 is one prompt file in `docs/prompts/` and one commit
referencing it (`(prompt: docs/prompts/NN-<slug>.md)`). Numbering continues the
chain: **`31-go-spec-v1.4.md`** is this run's `go` prompt; task prompts follow
from `32`. Never mix two prompts in one commit. No `git push` unless the `go`
prompt says so.

**REQ-V14-EC-07 (MUST)** Every prompt file carries the project's bullet header
**from the moment it is created**, never retro-fitted. Exactly the field set and
order of
`docs/prompts/30-v13-verify-run-fixes.md`:

```markdown
- **Date:** YYYY-MM-DD
- **Executor model:** <model> (<harness>)
- **Model reason:** <one line — why this model for this task>
- **Harness:** <harness>
- **Stage:** spec | generation | fix | review | docs
- **Owner of:** `<file>` … (the files this prompt may change)
- **REQ ids:** REQ-V14-…
```

**REQ-V14-EC-08 (MUST)** RLM discipline (lab rule 5) is unchanged: bulk reading
goes to a subagent with a brief of ≤ 8 lines plus REQ ids and its owned file
list, returning ≤ 15 lines — never a file dump, never `.env`. Code review runs
in a clean `code-reviewer` context (REV-01), never the writing context.

**REQ-V14-EC-09 (MUST)** Live steps are blocking: the run stops until the
artefact exists on disk, and an unfinished step is never assumed green. No
figure in any report is estimated where a measurement was specified; an unavoidable estimate is labelled `(ESTIMATE)`
with its derivation.

---

## 2. Amendments to spec-v1.3 — authoritative table

**REQ-V14-AMEND-01 (MUST)** Apply exactly these changes. Requirements not
listed here stay in force verbatim.

| id | Status | Replacement / change |
|---|---|---|
| REQ-V13-RSN-01, RSN-02 | **superseded** | `LLM_REASONING=auto\|on\|off` is not resurrected; reasoning control is re-specified as `LLM_REASONING_POLICY` + `LLM_REASONING_ON_PURPOSES` (POL-01…07), gated on a spike (RSN-01…06). The name `LLM_REASONING` MUST NOT appear in `config.py`, `.env.example` or `README.md`; `meta.env_flags.LLM_REASONING` keeps holding `null` (BEN-05) |
| REQ-V13-BEN-12 (frozen scenarios) | **amended** | the freeze is lifted once, for S01 only (SCN-03). That changes `scenarios_sha256`, so every v1.3 benchmark file becomes incomparable and a fresh baseline is mandatory (BEN-01); afterwards the file is frozen again (BEN-10) |
| REQ-V13-BEN-01 (locked meta) | **extended** | the ten locked fields are unchanged and MUST all match; added are the obligations that keep them matched across a two-tree measurement — `constants` (BEN-04), `config_sha256` (POL-06), `skipped_scenarios` (BEN-06) |
| REQ-V13-BEN-10 (`env_flags`, seven keys) | **extended** | the key set becomes **nine**, adding `LLM_REASONING_POLICY` and `LLM_REASONING_ON_PURPOSES`. `bench.py:1031-1032` already validates against `ENV_FLAG_KEYS`; only its stale message ("the seven documented keys") is corrected (BEN-05) |
| `bench.py` row validation (`:159-160`, `:1087`) | **amended** | `LLM_ROW_KEYS`/`TOOL_ROW_KEYS` derive from the *running* tree's storage columns, so a file from an older tree can never be read back. Replaced by a frozen-minimum / current-maximum rule (BEN-03) |
| REQ-V13-CCH-02(a) (prefix-extension) | **extended, not weakened** | the mechanism MUST NOT ride inside the message array in a way that varies between rounds of one `run_agent` invocation (POL-05) |
| REQ-V13-OBS-04 (`llm_calls` schema) | **extended** | two columns, `reasoning_requested` and `reasoning_honored`, via `SCHEMA_VERSION 3 → 4` (OBS-01) |
| `LLMClient.complete()` return type (`llm/base.py:66-77`) | **amended** | returns `LLMCompletion`, not `LLMResponse`, so every failover attempt is recordable (OBS-03); on the failure path it may raise `LLMCompletionError`, an `LLMError` **subclass**, so the error contract is extended, never replaced. Supersedes EC-05 for this internal type only: no env var, `Config` field, column or artefact shape changes, and all five call sites plus §12.1's test files move in the same commit |
| `config.py` `_parse_timeout` default `120` | **amended** | becomes `240`, so the shipped pair satisfies REL-01's new consistency check; supersedes EC-05 for `llm_timeout_s` only |
| REQ-V13-RTE-01 (`LLM_SUMMARY_MODEL`) | **unchanged, stays disabled** | MUST be empty in every benchmark run (`bench.py:1264-1265` refuses otherwise). Its call-purpose axis is *not* reused verbatim — see POL-02 |
| `report-v1.2.md`, `report-v1.3.md`, `llm-usage.md` rows 1…31 | **frozen** | byte-unchanged; both errata are recorded **only** in the new report (RPT-04) |
| `AGENTS.md` gates and benchmark commands | **unchanged** | reproduced verbatim in sections 11 and 10 |
| `docs/plan.md` § "v1.4 (next)" | **superseded** | replaced by the delivered status plus the remaining candidates (RPT-07) |

Everything else in v0…v1.3 — isolation posture, redaction choke points,
failover, structured memory, commands, rate limiting, the error matrix, the
token budget, observability, pricing, dashboard, mutation gate — is unchanged
and MUST keep working.

---

## 3. Preconditions (verify before writing any code)

**REQ-V14-PRE-01 (MUST)** Verify each item; on failure stop and emit the
blocker template (spec-v0 §7.2) instead of guessing.

1. Branch `main`, clean tree, HEAD at `3a0aa3d`.
2. All six gates green **before** you change anything, gate 5 and its
   `lmstudio` check included. v1.2's "record the failure and proceed"
   exception stays withdrawn: an unreachable LM Studio is a blocked run.
3. `.env` exists (git-ignored) and contains `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_BOT_NAME`, `ALLOWED_TG_IDS`, `LLM_PROVIDER`, `LMSTUDIO_BASE_URL`,
   `LMSTUDIO_MODEL`, `LMSTUDIO_CONTEXT_LENGTH`, `OPENROUTER_API_KEY`,
   `OPENROUTER_MODEL`. Validate **presence by key name only**; printing a value
   is forbidden. Do not create or overwrite `.env`.
4. `docker version` succeeds without `sudo`; the sandbox image is present
   locally (`docker image inspect`).
5. `docs/assets/bench/` is writable; `.bench/` is git-ignored scratch, wiped at
   each `bench.py run`.

**REQ-V14-PRE-02 (MUST)** Record the **LM Studio version** and the loaded model
identifier before any live step, in `report-v1.4.md`: without the version a later
reader can neither reproduce nor refute the spike. Quote it verbatim from the UI
or the CLI. The model MUST be `qwen/qwen3.8-27b` with
`LMSTUDIO_CONTEXT_LENGTH=42496`, matching every v1.3 file
(`bench-v1.3.md:12-13`); a different model or context length is a blocker, not
an adaptation.

**T0 creates the file.** `docs/reports/report-v1.4.md` is initialized in T0 —
the skeleton plus this version string and PRE-03's vendor citations — **before**
SCN-01 or any other live step. T10 completes that existing file; it never
creates it, and no task records the version retrospectively.

**REQ-V14-PRE-03 (MUST)** Verify against the vendor's own current documentation
— not from memory — the request-field names each spike candidate needs, and
cite what you read in the report:

- LM Studio's OpenAI-compatible `/v1/chat/completions`: whether unknown
  top-level body keys are forwarded to the chat template, and whether a
  `reasoning` / `reasoning_effort` field is accepted for a Qwen3-class model,
  **and whether that field documents a disable value** (RSN-02 candidate b) —
  record its exact spelling. LM Studio documents `reasoning.effort`
  (`low|medium|high`) for gpt-oss-class models; whether it binds on Qwen3 is
  **unknown and must be measured**, and if the live docs still list no disable
  value, candidate b is `unsupported`.
- OpenRouter's documented reasoning request field, for provider parity
  (POL-07). As of this spec's writing (OpenRouter docs, "Reasoning tokens"
  guide, read 2026-09-03) the request-body object is
  `"reasoning": {"enabled": false}` (equivalently `"effort": "none"`);
  `"exclude": true` only hides reasoning from the response and still bills
  the tokens, so it MUST NOT be used as the off-switch. Re-read the guide at
  run time and cite the date; if the field changed, follow the live docs and
  record the difference in the report.

**REQ-V14-PRE-04 (MUST)** Prove the two-tree measurement is mechanically
possible **before** the full run — the dry run of BEN-02 item 5.

**REQ-V14-PRE-05 (MUST)** `git worktree` is available and the tree clean, so
`git worktree add` at `69ebc75` succeeds and can be removed without touching
`main`.

---

## 4. Required file tree (delta)

**REQ-V14-TREE-01 (MUST)** New files:

```
tests/test_v14_patch.py              # every new test of section 12.2
docs/prompts/31-go-spec-v1.4.md      # this run's go prompt
docs/prompts/32-*.md …               # one file per task of section 14
docs/reports/bench-v1.4.md           # baseline-v1.4 vs the winning candidate
docs/reports/bench-<tag>.md          # one per committed <tag>.json (RPT-08)
docs/reports/report-v1.4.md
docs/reports/tg-post-v1.4.md
```

Changed: `config.py`, `agent.py`, `llm/base.py`, `llm/lmstudio.py`,
`llm/openrouter.py`, `llm/failover.py`, `llm/__init__.py`, `storage.py`,
`devtools/bench.py`, `devtools/bench_scenarios.py`, `devtools/mutation_check.py`,
`.env.example`, `README.md`, `docs/llm-usage.md`, `docs/plan.md`, plus exactly
the test files of section 12.1.

Benchmark artefacts land in `docs/assets/bench/<tag>.json` with a sibling
`<tag>.log` (`bench.py:73`, `:2059-2061`) and are **committed** (RPT-08);
`.bench/` stays git-ignored scratch. No new module, package or dependency.

---

## 5. RSN — the mechanism spike

v1.3's O5 ended `attempted_removed`: the probe showed an unchanged reasoning
share of `0.7373` (`report-v1.3.md:208-225`, `bench-reasoning-probe.md:94`) —
*that* mechanism on *that* build did not bind, so the optimization is
implemented-and-removed, **not disproven**. This section finds a mechanism that
binds, or proves none of the five does.

**REQ-V14-RSN-01 (MUST) — the probe and the pair contract.** The probe is
v1.3's probe, unchanged in shape, so its output stays comparable with
`bench-reasoning-probe.md`. **The unit of evidence is a pair, named by file.**
For each ordinal `<n>`, RSN-02's scratch patch executes S05 **twice
sequentially in one Python process** — first `model-default`, then `off` — from
the identical serialized scenario input, and writes two ordinary artefacts,
`rsn-<letter>-<n>-default.json` and `rsn-<letter>-<n>-off.json`, with their
`.log` siblings:

```bash
uv run --locked python devtools/bench.py run --only S05 --repeats 1 --tag rsn-<letter>-<n>
uv run --locked python devtools/bench.py report --baseline docs/assets/bench/rsn-<letter>-<n>-default.json --out docs/reports/bench-rsn-<letter>-<n>-default.md
uv run --locked python devtools/bench.py report --baseline docs/assets/bench/rsn-<letter>-<n>-off.json --out docs/reports/bench-rsn-<letter>-<n>-off.md
```

One `run` invocation per ordinal; the patch appends `-default` / `-off` to
`--tag`. The report compares those two **named files** and **never** infers pair
membership from the tool-exposed / tools-withheld groups — S05 is one turn with
one tool round, so both kinds of call happen inside *each* member, and no
request outside the two members counts. `<n>` is the pair ordinal, so no pair
overwrites another's evidence. `--only` already exists (`bench.py:1773`); **no
new CLI flag or `bench.py` option is added**.

**REQ-V14-RSN-02 (MUST)** Try these candidates **in this order**, one live probe
each. **Stop at the first candidate that passes RSN-03 *and* is shippable under
POL-05.** A candidate that passes RSN-03 but is rejected by POL-05 is recorded
as `honored but unshippable`, consumes its normal probe budget, and probing
**continues** down the order. Trying a later candidate after a shippable one
passed is out of scope; skipping an untried one is a defect.

| letter | mechanism | where it lands |
|---|---|---|
| a | `chat_template_kwargs: {"enable_thinking": false}` | a **top-level key of the JSON body** built by `llm/base.py:build_payload` — the repo posts raw JSON with `httpx` and has no OpenAI SDK, so what an SDK sends as `extra_body` is a plain top-level key here |
| b | the **vendor-documented disable value** of `reasoning` / `reasoning_effort` — exact spelling read live from LM Studio's docs under PRE-03 (an `effort` value meaning *none*, or an `enabled: false` form), never a merely smaller effort | top-level key of the JSON body |
| c | assistant prefill of an empty think block — a final `{"role": "assistant", "content": "<think>\n\n</think>\n\n"}` | **inside the message array**, as the last element |
| d | Qwen3's `/no_think` soft switch on the **last user message** | inside the message array, in the slot REQ-V13-CCH-01 already mutates with `(now: …)`. First establish **where v1.3 put it** (`report-v1.3.md:208-225`) and report whether this attempt differs |
| e | a model-level default set in LM Studio (GUI or `lms` CLI) | not in the request at all |

**Trial protocol — this is what makes the spike executable.** For **a**–**d**,
T4 applies a temporary, uncommitted patch selecting exactly one mechanism and
driving RSN-01's pair contract, runs pairs `rsn-<letter>-1`, `-2` and — while
still eligible — `-3`, then restores the tree and verifies `git diff` is empty
before the next candidate. That scratch patch is an explicit exception to EC-02
(the shipped implementation is still test-first in T5); it adds no third
environment variable and no `bench.py` option.

**Candidate b needs a documented *disable* value, not a smaller one.**
`"effort": "low"` requests *reduced* reasoning; a zero-token response under it is
an accident and MUST NOT be labelled `reasoning_requested='off'` or shipped as
an off-switch. If PRE-03's live reading finds only `low|medium|high` and no
disable value, candidate **b** is recorded **`unsupported`** — it consumes no
probe pair, can never be classified `honored`, and the report names the
documentation read and its date. **One optional informational run** is then
permitted at the lowest effort, as **one pair** under RSN-01's contract — tag
`rsn-b-low-info`, artefacts `rsn-b-low-info-default.json` and
`rsn-b-low-info-off.json`: excluded from every gate, never passed to
`report --gate --candidate`, labelled "reduced, not disabled" wherever its
figures appear, outside RSN-05's budget, and never a winning mechanism.

Candidate **e** is **environmental evidence only**: not per-request, so it
cannot express a `by-purpose` policy, is not reproducible from this repository,
**cannot pass RSN-03 and cannot authorize T5 or T7**. If only **e** suppresses
reasoning, RSN-06 is invoked. **One optional informational run** is permitted,
tag `rsn-e-info`: excluded from every gate, never passed to
`report --gate --candidate`, labelled "out-of-repo setting" wherever its figure
appears. The control (a per-model LM Studio setting or an `lms` load-time
option) is version-dependent: look it up for the version recorded under PRE-02,
name it in the README note and the report, and do not guess.

**REQ-V14-RSN-03 (MUST)** A candidate **passes** only when all three hold. The
"three runs" are three of item 3's **pairs**, not three isolated `off` runs.

1. **Honored, 3 of 3.** The `off` member of each pair shows, on the
   `## Reasoning` → `tool-exposed calls:` line, `reasoning observed: no` —
   `Σ reasoning_tokens == 0` **and** `max reasoning_chars == 0`. Both, because
   they come from different sources: `reasoning_tokens` from
   `usage.completion_tokens_details.reasoning_tokens` (`llm/base.py:149-153`),
   `None` when the provider omits it; `reasoning_chars` computed locally from
   `reasoning_content` / `reasoning` / `<think>` blocks (`:158-182`), so a
   provider that stops *reporting* reasoning cannot pass on tokens alone. Read
   the verdict off the rendered markdown only, as REQ-V13-RSN-02 did. An
   honestly reported zero satisfies this item directly. If either pair member
   renders a **`reasoning_tokens: absent` marker** (OBS-04), this item is
   satisfied only when that pair meets the omitted-token fallback in item 3;
   otherwise the pair is `unknown`.
2. **Still correct.** S05 shows `1/1` in `## Per scenario` (its
   `tool_used("exec")` and `answer_regex(r"\b332\b")` checks passed) in each
   pair. A mechanism that suppresses reasoning by breaking the model has not
   passed.
3. **Per-request switchable, proven live.** The pair is RSN-01's, read off the
   two named files: the `-default.json` member MUST show positive
   `reasoning_tokens` **or** positive `reasoning_chars`; the `-off.json` member
   MUST show zero for both. If `reasoning_tokens` is omitted in **either**
   member the pair stays **`unknown`, never honored**, unless all three hold:
   (a) the `-default` member has positive `reasoning_chars`; (b) the `-off`
   member has zero `reasoning_chars`; (c) the `-off` member's completion tokens
   **and** its recomputed cost are each **at least 20 % below** the `-default`
   member's. Cost is recomputed for both members at the **`-default` member's
   price snapshot**, and that member is the denominator of both comparisons. The
   rule is applied independently to each pair and **all three pairs MUST satisfy
   it**. The 20 % is fixed here in advance and is not tunable during the run.
   Both files and both rendered reports are preserved (RPT-08);
   comparison with v1.3's `0.7373` share is context, never proof. This is the
   **spike's** classification only — OBS-01's runtime derivation is unchanged
   and keeps `reasoning_chars` as its second source. Also proven offline against
   a fake transport (T-V14-POL-03).

**REQ-V14-RSN-04 (MUST)** Record every candidate's outcome — failures included
— in a table in `report-v1.4.md`, **one row per pair member**: letter, ordinal,
member (`default` / `off`), mechanism, LM Studio version, HTTP status or error
text if rejected, `Σ reasoning_tokens`, `max reasoning_chars`, `reasoning
share`, S05 result. The pair verdict — `honored` / `not honored` / `unknown` /
`honored but unshippable` / `unsupported` (RSN-02) — is stated once per pair, on
its `off` row; an `unsupported` candidate has no pair and takes a single row
naming the documentation read. Every pair tried has its artefacts and reports
committed (RPT-08).

**REQ-V14-RSN-05 (MUST)** Probe budget: **a**–**d** at two pairs each for the
failing ones and three for the passing one, and none for a candidate recorded
`unsupported`; at most one `rsn-e-info` run and one `rsn-b-low-info` pair, both
outside this budget (RSN-02); one re-run of any probe whose S05 check failed for a reason unrelated
to reasoning (transport timeout, Docker hiccup). The budget counts **pairs**: a
re-run replaces the whole pair, never one member, and OBS-05's sentinel is
outside it. Beyond that, stop: the spike has an answer, and it may be "none".

**REQ-V14-RSN-06 (MUST) — the STOP rule.** If no candidate passes RSN-03 **and
is shippable under POL-05**, **there is no optimization commit.** The run still
delivers in full: the S01 repair (section 8), baseline-v1.4 (BEN-02), both
errata (RPT-04), REL-01, the mechanism table (RSN-04), `rsn-e-info` /
`rsn-b-low-info` if they were run, and a report whose verdict is **FAIL, cause:
no honored reasoning mechanism**, naming every `honored but unshippable` and
`unsupported` candidate. Section 6, the two
new columns of section 7 and section 10's candidate runs are declared
not-executed.

**What section 9 does on this branch, stated once:** execute **REL-01 and REL-03
only**; do **not** execute REL-02, T-V14-REL-02, T-V14-REL-03 or REL-02's
mutation. T6 becomes `REL-01 and REL-03 (STOP branch)` and its acceptance omits
the `FINISH-LENGTH:` assertion. REL-03 stays a **SHOULD** here and may itself be
released under its own condition, its disposition recorded either way. The
report lists those exact released ids; **GATE-02** governs acceptance. Shipping
a knob the runtime ignores, or reporting a saving the measurement does not
support, is worse than this FAIL.

---

## 6. POL — the reasoning policy

**REQ-V14-POL-01 (MUST)** Two new environment variables, and no more:

| variable | values | default |
|---|---|---|
| `LLM_REASONING_POLICY` | `model-default` \| `off` \| `by-purpose` | `model-default` |
| `LLM_REASONING_ON_PURPOSES` | comma-separated reasoning-purpose tags (POL-02) | `tool-round` |

Both are `Config` fields (`llm_reasoning_policy: str`,
`llm_reasoning_on_purposes: frozenset[str]`) validated in `load_config`: an
unknown policy value or purpose tag raises `ConfigError` naming the variable
and the offending token. An empty `LLM_REASONING_ON_PURPOSES` is legal and
means "no purpose keeps reasoning", exactly `off`; the variable is inert unless
the policy is `by-purpose`, and the README says so. Both appear in
`.env.example` with their defaults (RPT-06).

**REQ-V14-POL-02 (MUST) — the reasoning-purpose tag.** The database's `purpose`
column has exactly two values, `'agent'` and `'summary'`, under a SQLite
`CHECK` (`storage.py:54`). Both the tool-selection and the final-answer call are
`'agent'`; the distinction lives only in the request-time locals
`expose_tools` / `request_tools` (`agent.py:241-247`). That column is **not**
changed here — a `CHECK` change is a migration (NG-05). Instead, define a
**derived, request-time reasoning-purpose tag** with exactly three values:

| tag | condition |
|---|---|
| `tool-round` | `purpose == "agent"` and the request carries tools (`request_tools` is not `None` and non-empty) |
| `final` | `purpose == "agent"` and tools are withheld (`request_tools is None`) |
| `summary` | `purpose == "summary"` |

The tag is a pure function of `(purpose, request_tools)` with no I/O and no
global state, lives in `llm/base.py`, and is the single source of truth for the
three-value set — never a hand-copied literal list in `config.py`, `agent.py`
or the tests.

**REQ-V14-POL-03 (MUST)** Policy resolution is a pure function
`resolve_reasoning(policy: str, on_purposes: frozenset[str], tag: str) -> str`
returning `"on"`, `"off"` or `"default"`: `model-default` → `"default"` for
every tag (nothing is added to the request); `off` → `"off"` for every tag;
`by-purpose` → `"on"` when `tag in on_purposes`, else `"off"`. `"on"` and
`"default"` are distinct — `"default"` sends no reasoning field at all
(byte-identical to a v1.3 request), while `"on"` sends the mechanism's explicit
enable form when it has one and otherwise degrades to `"default"`, and the
degradation is recorded in the report, never silent.

**REQ-V14-POL-04 (MUST)** The resolved value reaches the provider. `complete()`
gains one keyword-only parameter carrying the reasoning-purpose tag (or the
already-resolved request, at the implementer's choice, provided the choice is
the same in all five places). It MUST be added in **all five** sites or it is
silently dropped: `llm/base.py:67-73` (the `LLMClient` Protocol),
`llm/lmstudio.py:35-41`, `llm/openrouter.py:72-78`, `llm/failover.py:50-56`
(forwarded at `:60`), and `llm/failover.py:73-83` — `_try_other`, forwarded at
`:83`, the site that gets forgotten. Test
(T-V14-POL-04): a fake primary raising a retryable error and a recording
secondary — the secondary's request MUST carry the same mechanism fields as the
primary's; a `v14-*` mutation removes the forwarding at `:83` and MUST be
killed. Call sites pass the tag: `agent.py:253` (tag from `request_tools`) and
`agent.py:805` (tag `summary`).

**REQ-V14-POL-05 (MUST) — the mechanism must not disturb the cached prefix.**
REQ-V13-CCH-01 fixes the system prompt and `tools` JSON byte-for-byte across a
conversation; REQ-V13-CCH-02(a) requires round *n*'s message list to be a
prefix-extension of round *n−1*'s. Therefore:

1. The mechanism MUST NOT be written into the system prompt or the `tools`
   JSON under any policy (test T-V14-POL-05).
2. A mechanism carried **outside** the message array (candidates **a**, **b**)
   satisfies CCH-02 under every policy — the array is untouched.
3. A mechanism carried **inside** the array is constrained. Candidate **c**
   breaks CCH-02(a) under *every* policy: the prefill must be last, so as the
   array grows the older list stops being a prefix of the newer one. Candidate
   **d** satisfies CCH-02(a)
   only while the resolved value is the **same for every call of one
   `run_agent` invocation** — under `model-default` and `off`, but not under
   `by-purpose`, which would need different bytes at an early index.
4. Consequently **c** and **d** are both `honored but unshippable` (RSN-02):
   POL-01's mandatory `by-purpose` value cannot preserve CCH-02(a) for either,
   and restricting only the benchmark to `off` would still release a policy a
   user can select that breaks the cached prefix. Report the outcome
   found-but-rejected with this reason, fall through to the next candidate in
   the RSN-02 order, and say which branch was taken. **Neither c nor d can
   authorize T5 or T7.** `by-purpose` stays in POL-01's contract unchanged —
   removing it would amend an already-selected contract and is not the
   executor's call.

**REQ-V14-POL-06 (MUST)** Both new `Config` fields are added to `bench.py`'s
`CONFIG_HASH_EXCLUDED` (`:132-139`), in the treatment group beside
`llm_reasoning`, with a comment naming this requirement. `config_sha256` is a
**locked** meta field (`:143`): hashing the policy fields would make baseline
and candidate differ by construction, exiting 2 before anything is measured.

**REQ-V14-POL-07 (SHOULD) — provider parity.** The policy is provider-agnostic:
POL-03's resolution is shared, only request building differs per provider. LM
Studio uses the spike's winning mechanism; OpenRouter its own documented
reasoning field (PRE-03). Proven by a bounded live smoke of **two commands, one
call each and one policy transition between them** — capped at
`--max-cost-usd 0.05` each, **`$0.10` combined** (precedent:
`docs/reports/bench-openrouter-smoke.md`):

```bash
LLM_REASONING_POLICY=off uv run --locked python devtools/bench.py run \
  --provider openrouter --only S02 --repeats 1 --max-cost-usd 0.05 \
  --tag openrouter-reasoning-off
LLM_REASONING_POLICY=model-default uv run --locked python devtools/bench.py run \
  --provider openrouter --only S02 --repeats 1 --max-cost-usd 0.05 \
  --tag openrouter-reasoning-default
```

Released only if the spike ended under RSN-06 (nothing to be at parity with) or
if OpenRouter's current API documents no such field, in which case the report
says so and the OpenRouter path keeps sending nothing. **Both artefacts are
committed** (RPT-08) and the report quotes the two rows, their
`reasoning_requested` and their `reasoning_chars` side by side. Neither is a
benchmark candidate; neither ever enters a gate comparison.

---

## 7. OBS — observability for the policy

**REQ-V14-OBS-01 (MUST)** `llm_calls` gains two columns, appended to
`storage.LLM_CALL_COLUMNS` after `reasoning_chars` so the row and the
structured log line stay in step (REQ-V13-OBS-06): `reasoning_requested`
(`TEXT`, `'on'` | `'off'` | `'default'` — POL-03's output for that call) and
`reasoning_honored` (`INTEGER`, `1` | `0` | `NULL`).

`reasoning_honored` is `NULL` when `reasoning_requested` is `'default'` (there
was nothing to honour) or the call failed before a response arrived; `1` when
`'off'` was requested and both `reasoning_tokens` (`NULL` treated as 0) and
`reasoning_chars` are 0; `0` when `'off'` was requested and either is greater
than 0. When `'on'` was requested it is `1` if either is greater than 0, else
`0`.

Existing databases migrate through the project's **versioned chained**
mechanism (`storage.py:142-160`, `init_schema` at `:200-215`), not ad-hoc DDL:
`SCHEMA_VERSION` goes `3 → 4`, a `_MIGRATION_3_TO_4` script adds the two columns
with `ALTER TABLE llm_calls ADD COLUMN`, and `init_schema`'s accepted tuple
`(1, 2, SCHEMA_VERSION)` becomes `(1, 2, 3, SCHEMA_VERSION)`. Existing rows keep
`NULL`; the version gate gives idempotence. The bump is part of OBS-01, **not**
the storage change NG-05 forbids.

**REQ-V14-OBS-02 (MUST)** `finish_reason` is already a column (`storage.py:30`,
written at `agent.py:695` from `choices[0].finish_reason`). No schema change;
it is surfaced (OBS-04) and asserted (REL-02).

**REQ-V14-OBS-03 (MUST)** Both new columns are recorded for **every** LLM call
including the summary call and every failover attempt, through the existing
`_record_llm_call` seam (`agent.py:644`), never a second write path.

**The data flow that makes "every failover attempt" reachable is specified, not
assumed.** `FailoverLLMClient.complete()` (`llm/failover.py:20`, `:50-71`)
returns only the winning `LLMResponse` and `agent.py` writes one row per
`complete()` call, so a failed primary attempt is invisible today. Therefore,
beside `LLMResponse` in `llm/base.py`, add two frozen dataclasses:

- `LLMAttempt(provider: str, response: LLMResponse | None, error_kind: str | None)`
- `LLMCompletion(response: LLMResponse, attempts: tuple[LLMAttempt, ...])`

**Every** implementation of the `LLMClient` Protocol (`llm/base.py:66-77`)
returns `LLMCompletion`, not only `FailoverLLMClient`: a direct client returns
exactly one successful attempt, and `FailoverLLMClient` concatenates its
attempted calls in order.

**A failing call carries its attempts too.** `LLMCompletion` requires a
successful `response`, so a raising call would otherwise lose every attempt it
made. Add **`LLMCompletionError(LLMError)`** in `llm/base.py` — a subclass of
the existing `LLMError` (`:56-63`), preserving its
`retryable` / `kind` classification unchanged and additionally carrying
`attempts: tuple[LLMAttempt, ...]`. Only `FailoverLLMClient` raises it: it
accumulates one `LLMAttempt` per side and, when **no** side succeeds, raises
`LLMCompletionError` with the last error's message, `retryable` and `kind`
(`:82-86`). Direct clients keep raising plain `LLMError` (`:248-281` unchanged),
and the **agent boundary** converts: the `except LLMError` handlers at
`agent.py:254` and `:806` build one failed
`LLMAttempt(provider, response=None, error_kind=getattr(exc, "kind", "http"))`
for a plain `LLMError` and take `exc.attempts` as they are for an
`LLMCompletionError`. Because the new type **is** an `LLMError`, both handlers,
their retry and malformed-re-ask logic and every `pytest.raises(LLMError)` catch
keep working unchanged — but the wrapper is a **new** instance, so
`test_failover.py`'s identity assertion (`:166`, `raised.value is last`) moves to
the carried message/`kind`, and `llm/failover.py`'s module docstring (`:3-5`),
which still promises "the caller sees the last `LLMError`", is corrected in the
same commit.

`agent.py` records **every** attempt it holds, success and failure alike — one
`_record_llm_call` per element, exactly once, before the existing error handling
(retry, malformed re-ask, `FALLBACK_LLM_ERROR`) runs — and consumes
`completion.response` for agent behaviour; **no recording happens inside a
provider client** (AMEND-01's EC-05 exception). The seam already accepts
`attempt` and `response: LLMResponse | None`, so its signature is unchanged —
but each row MUST name the provider that served *that* attempt, never
`active_provider_name` after `_try_other` promoted the secondary (`:91-93`).
T-V14-OBS-01 covers both attempt rows **and both failure cases**, not merely
keyword forwarding.

If routing the failed-call row through that loop rewrites the block
`devtools/mutation_check.py` pins at `:368-382`
(`v13-llm-call-not-recorded-on-error`), that entry's `find` string is updated to
the new text in the same commit, its `id`, `why` and kill obligation unchanged.
It is the **only** existing mutation entry OBS-03 may touch; TST-05 otherwise
appends.

**REQ-V14-OBS-04 (MUST)** `bench.py`'s `## Reasoning` section (`:1575-1618`)
gains, per side and per group (overall, tool-exposed, tools-withheld):
`Σ reasoning_tokens` and `max reasoning_chars` before and after (already there,
format unchanged so v1.3's files stay readable), plus
**`honored rate`** =
`count(reasoning_honored == 1) / count(reasoning_requested in ('on','off'))`,
rendered `n/a` when the denominator is 0.

**The two new columns MUST be read with a missing-key-tolerant accessor**, not
by direct indexing as `_reasoning_line` does for `reasoning_tokens` (`:1604`):
BEN-02's baseline is produced on the stage-A tree, whose rows carry the v1.3
column set and **no** `reasoning_requested`, which BEN-03 makes loadable but
does not conjure into existence. A row lacking the key is excluded from the
denominator; a side whose rows all lack it renders `n/a`.

**Absent is not zero.** `_reasoning_line` (`bench.py:1596-1620`) coerces a
`None` `reasoning_tokens` to `0` at `:1597`, so an omitted field is today
indistinguishable from an honestly reported zero in `max reasoning_tokens` and
`Σ reasoning_tokens`; the only existing signal is the `chars only` share branch
(`:1606-1607`), which fires solely when *every* row omits the field *and* some
`reasoning_chars` are positive. That line MUST therefore additionally render
**`reasoning_tokens: absent (<k> of <n> rows)`** — omitted when `k` is 0 —
distinctly from a reported `0`, per side and per group. RSN-03 items 1 and 3 and
OBS-05's sentinel read that marker.

**REQ-V14-OBS-05 (MUST) — the mechanism-drift guard.** In `bench.py`'s verdict
path: when the candidate's `meta.env_flags.LLM_REASONING_POLICY` is anything
other than `model-default` **and** the candidate's overall honored rate is
below `0.95`, the report prints a line beginning `DRIFT:` naming the measured
rate, and the verdict **cannot** be `PASS` — `passed` is forced `False` with
reason `reasoning mechanism drifted` — this is exactly what v1.3 hit: a knob
the runtime silently stops honouring. A `v14-*` mutation flips the comparison
and MUST be killed.

**Pre-candidate drift sentinel (MUST).** That guard alone misses the failure it
names: `reasoning_honored` treats an omitted `reasoning_tokens` as zero, so a
build that stops *reporting* reasoning while still doing it holds the rate at
`1.0`. So immediately before each candidate run of BEN-07, execute **one**
paired S05 control under RSN-01's pair contract with the winning mechanism:
artefacts `drift-<candidate tag>-default.json` and `-off.json`, their logs and
rendered reports. The `default` member MUST show positive reasoning from at
least one source and the `off` member MUST satisfy RSN-03 item 1 — including
its item-3 omitted-token fallback whenever either member renders
`reasoning_tokens: absent`. The sentinel
precedes any candidate document, so `bench.py`'s verdict path cannot judge it:
the verdict is read off the two rendered reports and recorded in
`bench-v1.4.md`'s preamble, citing both artefacts. If the pair is `unknown` or
not honored, **the full candidate run is not spent** — record a `DRIFT:` line
naming the sentinel pair and fail that candidate.

---

## 8. SCN — S01: root cause before repair

S01 is `greet`: one Russian turn, no tools, three checks — `no_tools`,
`answer_regex("exec|команд|скилл|skill|fetch|python")`, `answer_max_chars(900)`
(`devtools/bench_scenarios.py:149-158`). The baseline passed it 3/3; the
candidate 1/3, failing only `answer_regex: pattern not found`
(`bench-v1.3.md:158-163, 175`). The recorded answers are fluent, on-topic
Russian describing the bot's capabilities in general terms and naming none of
the six alternatives.

**REQ-V14-SCN-01 (MUST)** Reproduce first, at HEAD, before changing anything:

```bash
uv run --locked python devtools/bench.py run --only S01 --repeats 3 --tag s01-repro
uv run --locked python devtools/bench.py report --baseline docs/assets/bench/s01-repro.json --out docs/reports/bench-s01-repro.md
```

`--only` already exists; **no new flag is added**. Both artefacts are committed
as the evidence. The `answers` field of each `runs[]` record holds the model's
text and *is* the transcript meant by "keep transcripts": no separate transcript
file is created, and none may contain a credential.

**REQ-V14-SCN-02 (MUST)** Classify with named evidence, not assumption: the
report states which hypothesis the evidence supports, and why.

- **H1 — check defect.** The answer meets the scenario's intent, but the regex
  enumerates six surface tokens a fluent paraphrase need not contain: the check
  measures phrasing, not capability.
- **H2 — genuine regression.** The v1.3 prefix rewrite (O4/PFX) changed the
  system prompt: `prefix_tokens` fell `1126 → 842` (`bench-v1.3.md:21`). If the
  rewritten prompt no longer names the tools, the bot has actually got worse at
  describing itself.

The discriminating question MUST be answered explicitly in the report: **does
the v1.3 system prompt still name `exec`, `fetch` and the skill mechanism?**
Inspect the assembled system prompt directly (a unit-level assertion, not a
live call). The classification MUST also account for repeat 3 passing at
`temperature: 0` — identical inputs producing different text means the sampling
path is not deterministic end to end.

**REQ-V14-SCN-03 (MUST)** Repair according to the classification, and only
according to it:

- **H1** → change **only** S01's `checks` expression. `id`, `title` and `turns`
  stay byte-identical; no other scenario is touched; `no_tools` and
  `answer_max_chars(900)` stay. The replacement MUST stay faithful to the
  intent — it accepts a tool name **or** a capability phrase, so a correct
  paraphrase passes and an off-topic or refusing answer still fails. The exact
  diff (old pattern, new pattern, one sentence of rationale) goes in the report
  and in `bench-v1.4.md`'s preamble.
- **H2** → **stop before T2 with the blocker template.** Under H2 the check is
  untouched, `id`/`title`/`turns` stay byte-identical and no other scenario may
  change — so `bench_scenarios.py` cannot legally change, and this spec's
  mandated scenario-file change, BEN-01's re-baseline premise and the
  H1-specific tests are invalid for that root cause: they need a revised spec.
  **Never** manufacture a no-op scenario edit to move the hash.

On the H1 branch `bench_scenarios.py` changes, so `scenarios_sha256` changes and
BEN-01 applies. Do not fix both at once: a repaired check over a repaired
prompt measures neither. T-V14-SCN-01 and Appendix B E8 execute **only** once
H1 is established.

**REQ-V14-SCN-04 (MUST)** After the repair, re-run SCN-01's command with tag
`s01-verify` and require **3/3**; a repair that still fails a repeat is not a
repair — return to SCN-02. Both artefacts are committed. REQ-V13-BEN-08's
loading test (no `\|` two-character sequence in any pattern) MUST stay green.

---

## 9. REL — reliability

**REQ-V14-REL-01 (MUST) — lever 5, the timeout/budget mismatch.**
`LLM_TIMEOUT_S` defaults to `120` (`config.py:268`, `_parse_timeout`, range
`0 < t ≤ 600`) while `LLM_MAX_TOKENS` defaults to `2048` (`:271`, range
`1…8192`). At v1.3's measured latency model (`21.1 s + 0.093 s/token`,
`report-v1.3.md:340`) 120 s admits about 1 063 completion tokens, so a long
completion times out and is **retried with identical parameters**, re-sending
the whole prompt — this aborted v1.3's first baseline attempt.

Consistency becomes a checked property, not a comment: `load_config` raises
`ConfigError` when
`llm_timeout_s < LATENCY_INTERCEPT_S + LATENCY_PER_TOKEN_S × llm_max_tokens`,
with the two constants named, set to the values above, and cited to the report
line they come from. The operator resolves it by raising `LLM_TIMEOUT_S`
(ceiling 600, so `LLM_MAX_TOKENS ≤ 6224`) or lowering `LLM_MAX_TOKENS`.
`SUMMARY_MAX_TOKENS = 512` (`agent.py:45`) is unaffected because it is smaller.

**The shipped default changes with the check.** `21.1 + 0.093 × 2048 =
211.564 s`, so the documented pair `120` / `2048` would itself fail the check
and a configuration with both variables absent would no longer start. The
`LLM_TIMEOUT_S` default in `_parse_timeout` (`config.py:330`) therefore becomes
**`240`**; `LLM_MAX_TOKENS` stays `2048`. This safety correction **explicitly
supersedes EC-05 for `llm_timeout_s` only**, and is the one default this spec
changes outside BEN-09. `.env.example` ships the same pair.

**Benchmark constraint:** `llm_timeout_s` and `llm_max_tokens` are both hashed
into `config_sha256`, and `LLM_MAX_TOKENS` is additionally pinned equal by
`comparability()` (`bench.py:1266-1267`). Every baseline and candidate command
of section 10 therefore carries the **same** `LLM_TIMEOUT_S=240
LLM_MAX_TOKENS=2048` process environment (BEN-02 item 3); `.env` is neither
modified nor read for content (EC-04). Both values sit inside the stage-A
parser's ranges (`0 < t ≤ 600`, `1…8192`), so `69ebc75` is never patched.

**REQ-V14-REL-02 (MUST) — lever 6, the starved summary.** The tools-withheld
group has the highest reasoning share (`0.7681` / `0.8291`, `bench-v1.3.md`
`## Reasoning`), so a summary call with `SUMMARY_MAX_TOKENS = 512` can spend its
budget thinking and return empty content with `finish_reason=length` — observed
2 of 2 in v1.3's aborted first baseline. Two obligations:

1. Under any policy other than `model-default`, the `summary` tag resolves to
   `"off"`. Under `by-purpose` this means `summary` MUST NOT appear in
   `LLM_REASONING_ON_PURPOSES`; `load_config` rejects a value containing it,
   naming this requirement. Under `off` it follows from POL-03.
2. `bench.py` asserts it: in a **candidate** run (policy ≠ `model-default`),
   any `llm_calls` row with `purpose == 'summary'` and
   `finish_reason == 'length'` makes the report print a line beginning
   `FINISH-LENGTH:` naming the scenario and repeat, and forces the verdict to
   `FAIL` with reason `summary truncated by length`. Baseline runs are exempt —
   a baseline is allowed to exhibit the defect it is the baseline of.

A `v14-*` mutation weakens the assertion and MUST be killed.

**REQ-V14-REL-03 (SHOULD)** `metrics.py:193` aggregates
`sum(row["reasoning_tokens"] or 0 …)` into `Stats.reasoning_tokens: int = 0`,
so "reported nothing" and "reported zero" are indistinguishable in `/stats`
(`bot.py:818`), unlike the `None`-preserving token columns. `bench.py:1604`
handles it correctly, so no gate depends on it. Record it in the report's known
defects with a one-line disposition. Fixing
it is permitted **only** if it needs no change outside `metrics.py` and
`tests/`; released otherwise.

---

## 10. BEN — baseline, candidates, verdict

**REQ-V14-BEN-01 (MUST)** Because `bench_scenarios.py` changes on SCN-03's **H1
branch** (H2 stops the run before T2), `scenarios_sha256` changes, and it is a
locked meta field (`bench.py:143`, hashed from raw bytes at `:173-179`).
**Every v1.3 benchmark file is therefore incomparable with every v1.4 file**: no
v1.4 gate may be computed against `$0.002687`, and the v1.3 figures appear only
as labelled informational context.

**REQ-V14-BEN-02 (MUST) — baseline-v1.4.** The baseline is the **stage-A code**
at `69ebc75` (v1.3's pre-optimization tree, `bench-v1.3.md:10`), running the
**v1.4 scenario file** and the **v1.4 benchmark harness**, because
`comparability()` (`bench.py:1268-1277`) requires each stage-C key
(`HISTORY_TOOL_STUB`, `EXEC_OUTPUT_DEFAULT_CHARS`, `FETCH_INLINE_DEFAULT_CHARS`,
`LLM_REASONING`) to be `null` on the baseline side and at its stage-C default on
the candidate side, and only a pre-stage-C tree produces `null`. So the −30 %
target is cumulative over v1.3's −7.3 %.

1. `git worktree add <abs-path> 69ebc75` — a detached checkout outside the
   working tree, removed when the run ends. **Never commit to it, never amend
   `69ebc75`.**
2. Copy the v1.4 `devtools/bench.py`, `bench_scenarios.py` and `__init__.py`
   into the worktree; nothing else. Its product code (`agent.py`, `llm/`,
   `config.py`, `storage.py`, `tools.py`, `bot.py`) stays exactly as `69ebc75`
   shipped it — that is the treatment being measured. `meta.git_commit` reads
   `69ebc75` and is **not** locked, so the dirty tree costs nothing.
3. **Credentials and the runtime values come from different mechanisms.** The
   worktree has no `.env`, and `load_config` reads `PROJECT_ROOT/.env` with
   `override=False` (`config.py:178`), so credentials come from a temporary
   **symlink** in the worktree root pointing at `<main-root>/.env` by absolute
   path — creating a symlink does not open `.env` for content, so EC-04 holds —
   removed after the final run. `LLM_FAILOVER=off`, `LLM_SUMMARY_MODEL=` empty
   and REL-01's `LLM_TIMEOUT_S=240 LLM_MAX_TOKENS=2048` are passed as
   **process-environment overrides on every command** (`override=False` makes
   them win), identical for the baseline and every candidate; `.env` is never
   edited.
4. **Every worktree run writes into the main tree.** `DEFAULT_OUT_DIR` is the
   *running* tree's `docs/assets/bench/` (`bench.py:73`), so a worktree run
   would otherwise vanish with the worktree. Pass
   `--out <main-root>/docs/assets/bench/<tag>.json` (the flag exists, `:1776`);
   the `.log` sibling follows `out_path.parent` (`:2059-2061`). If a run
   nevertheless wrote inside the worktree, copy both files out and verify
   SHA-256 equality **before** removing it.
5. **Dry run first (PRE-04).** In the worktree,
   `bench.py run --only S01 --repeats 1 --tag dryrun-base --out <main-root>/docs/assets/bench/dryrun-base.json`;
   in the v1.4 tree, the same with `--tag dryrun-cand` and its own `--out`;
   then, from the v1.4 tree,
   `bench.py report --baseline docs/assets/bench/dryrun-base.json --candidate docs/assets/bench/dryrun-cand.json --gate --out /dev/null`.
   Exit 0 or 1 passes (the verdict is meaningless on one scenario); **exit 2 or
   3 is a blocker**. Both dry-run files share `--only` and `--repeats`, which
   are locked. Delete `docs/assets/bench/dryrun-*.json` and their `.log`
   siblings as the last step of this item: only `*.log` is git-ignored, so a
   leftover JSON would be swept into a commit by `git add -A`.
6. The full run, from inside the worktree:
   `bench.py run --tag baseline-v1.4 --repeats 3 --timeout-s 1800 --out <main-root>/docs/assets/bench/baseline-v1.4.json`.

**REQ-V14-BEN-03 (MUST) — the row-key rule that makes item 6 readable.**
`LLM_ROW_KEYS` and `TOOL_ROW_KEYS` are derived at import from the *running*
tree's storage columns (`bench.py:159-160`) and enforced as exact set equality
at `:1087`, so a stage-A baseline is rejected the moment the v1.4 `report` reads
it — after the hour is spent. Replace the equality with
`REQUIRED_LLM_ROW_KEYS ⊆ set(row) ⊆ LLM_ROW_KEYS`, where
`REQUIRED_LLM_ROW_KEYS` is a **literal frozen tuple** spelling out the v1.3
column set — deliberately *not* derived from `storage`, which would drift
forward with every schema change and guard nothing. Apply the same rule to
`TOOL_ROW_KEYS`, or state in the report why not (that schema is
unchanged here, so `REQUIRED == current`). A `v14-*` mutation restores `==` and
MUST be killed by the fixture test.

**REQ-V14-BEN-04 (MUST)** `meta.constants` is locked (`bench.py:143`) and
includes `REQUEST_DEFAULTS` (`llm/base.py:85-89`). The mechanism MUST NOT be
added to `REQUEST_DEFAULTS` or any other constant there; it is applied per call,
after `build_payload`. Adding it makes every candidate incomparable and surfaces
only as `locked meta field differs: constants`. Likewise `summarize()` (`:410`)
MUST NOT change: `_validate` recomputes it over a loaded file's `runs`
(`:1206`), so a changed aggregation makes the baseline unreadable.

**REQ-V14-BEN-05 (MUST)** `meta.env_flags` gains `LLM_REASONING_POLICY` and
`LLM_REASONING_ON_PURPOSES` (the latter serialized as a sorted comma-joined
string, so the JSON is stable). `LLM_REASONING` stays in the key set and stays
`null` on both sides — v1.4 does not resurrect it, and `comparability()`'s
`("auto", None)` allowance at `:1272-1275` continues to pass. `env_flags()`
(`:182-188`) already resolves a `Config` field absent at the running commit to
`None`, so the stage-A worktree emits both new keys as `null` with no code
change. The stale message at `:1031-1032` ("exactly the seven documented keys")
is corrected to name the count programmatically. Neither new key joins
`STAGE_C_KEYS`: their candidate values differ between runs A and B by design,
and pinning them would forbid run B.

**The baseline/candidate difference (`null` beside `off` or `by-purpose`) is
comparable by design, with no code change.** `meta.env_flags` is **not** one of
the ten `LOCKED_META_FIELDS` (`bench.py:141-150`), and `comparability()`
(`:1249-1278`) rules on it only through `LLM_FAILOVER`, `LLM_SUMMARY_MODEL`,
`LLM_MAX_TOKENS` and `STAGE_C_KEYS` — none of which covers either new key. **No
key-by-key comparison is introduced.** Fixtures pin it instead (§12.1): both
allowed pairs compare, and an unrelated `env_flags` difference
(`LLM_MAX_TOKENS`) still makes `report --gate` exit 2.

**REQ-V14-BEN-06 (MUST)** `skipped_scenarios` is locked and computed from a
live 5-second `HEAD` preflight against `https://wttr.in/` (`bench.py:77-78`,
`:638`), not from a flag. Both v1.3 runs recorded `[]`, with S08 executed 3/3
(`bench-v1.3.md:17`); v1.4 MUST match. Confirm reachability immediately before
each full run and confirm `[]` afterwards. A run whose preflight failed is
discarded and repeated once, never compared: a skip flip voids the pair with
`locked meta field differs: skipped_scenarios`. 36 runs per side (12 × 3).

**REQ-V14-BEN-07 (MUST) — candidate runs, at most two**, in order:

- **Run A — `LLM_REASONING_POLICY=off`**, tag `cand-off`. Maximum saving. If
  **both** gates pass (BEN-08), stop: `off` is the shipped default and there is
  no run B.
- **Run B — `LLM_REASONING_POLICY=by-purpose`**,
  `LLM_REASONING_ON_PURPOSES=tool-round`, tag `cand-by-purpose`. Run only if A
  failed a gate, and only if the winning mechanism permits a per-round-varying
  policy (POL-05 item 4). Reasoning is kept where the model needs it most,
  choosing which tool to call, and removed from the final answer and summary.

No third run, no parameter sweep, no re-tuning between runs (v1.3 §13.4's "no
tuning loop", carried forward). A REV-01 remeasurement replays an already-run
candidate unchanged in policy — against a regenerated baseline on REV-01's
tier 1 — and is not a third run. Each run is preceded by OBS-05's pre-candidate
drift sentinel, which can fail a candidate before its hour is spent. If neither
benchmark candidate passes BEN-08, the verdict is **FAIL, cause: honored
reasoning policy did not satisfy the cost and quality gates**, with the measured
figures; the default stays `model-default`. This is **not** the RSN-06 STOP
branch — the mechanism was honored and sections 6, 7, 9 and 10 all executed — so
**no** implemented requirement, test or mutation is released.

**REQ-V14-BEN-08 (MUST) — the gates, unchanged in formula.** Identical to
spec-v1.3 §13.3, evaluated against `B_v1.4`. With `B` the baseline file and `C`
a candidate, `successes_X = summary.successes`,
`failed_X = summary.totals.failed_calls`, `Σcost_X` the cost recomputed from
both files' token columns **at the baseline's price snapshot**, and
`mean_ok_X = Σcost_X / (summary.totals.calls − failed_X)` (`0` when the divisor
is `0`):

- `B_plain = Σcost_B / successes_B`; `C_plain = Σcost_C / successes_C`;
  `C_conservative = (Σcost_C + failed_C × mean_ok_C) / successes_C`.
  **Cost gate:** both `C_plain ≤ 0.70 × B_plain` and
  `C_conservative ≤ 0.70 × B_plain`.
- **Quality gate:** `success_rate(C) ≥ success_rate(B) − 0.02`, where
  `success_rate = successes / runs` and skipped repeats are not runs.
  Additionally gated: **no scenario loses more than one repeat**
  (`3/3 → 1/3` fails even when another scenario gains — a compensated aggregate
  must not hide a broken scenario). Any regressed run is investigated and
  documented.
- `successes == 0` on either side → FAIL, reason `no successful runs`.
- **PASS = cost gate and quality gate both pass, and no `DRIFT:` (OBS-05) and
  no `FINISH-LENGTH:` (REL-02) line was printed.**

Commands, verbatim from `AGENTS.md`:

```bash
uv run --locked python devtools/bench.py run --tag <tag> --repeats 3
uv run --locked python devtools/bench.py report --baseline A.json [--candidate B.json] --out docs/reports/bench-<name>.md
```

The final comparison is
`report --baseline docs/assets/bench/baseline-v1.4.json --candidate docs/assets/bench/<winning-tag>.json --gate --out docs/reports/bench-v1.4.md`.
Exit codes are read, not guessed: `0` pass, `1` fail, `2` not comparable, `3`
usage/missing, `4` aborted. An exit 2 is a **process** failure — fix the
comparability cause and re-run — never a verdict. Retry budget: one repeat of
any run that aborted for a transport or Docker reason (`meta.aborted` present,
which `check_document` refuses to gate anyway, `:993-994`); a second abort is a
blocker.

**REQ-V14-BEN-09 (MUST)** The shipped default of `LLM_REASONING_POLICY` becomes
the winning policy — the only **treatment-affecting change not requiring
remeasurement** permitted after the last candidate run (REV-01 governs the
fixes that do require it). It is safe: both policy fields are excluded from `config_sha256`
(POL-06) and neither is in `LOCKED_META_FIELDS`, so the measured files stay
comparable. Update `.env.example` and `README.md` in the same commit, re-run all
six gates, and state in the report that the default was flipped after
measurement and which figure justified it. If neither candidate passed, the
default stays `model-default` and the knob ships documented as
available-but-not-default.

**Exactly one test may pin that literal** — T-V14-POL-07's default assertion,
named in §12.1 as amendable by this requirement. It is the only exception to
EC-03 that BEN-09 creates: no other test, fake or fixture may assert the policy
default, and none may assert `.env.example`'s content.

**REQ-V14-BEN-10 (MUST)** Once the baseline exists, `bench_scenarios.py` is
frozen again (REQ-V13-BEN-12 re-armed): a further change invalidates
`baseline-v1.4.json` and is out of scope.

---

## 11. Gates

**REQ-V14-GATE-01 (MUST)** Run verbatim, in order, from the repository root:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
uv run --locked python devtools/mutation_check.py
```

**At every commit, gates 1–5 run in order. Gate 6 additionally runs at every
commit that changes production code, configuration behaviour, benchmark verdict
logic, tests or mutations, and on the final tree before acceptance.** That is
this run's only per-commit gate rule — ORD-01 cites it and never restates a
number. Gates 1–4 and 6 are offline. Gate 5 needs the live environment and MUST
be **fully green including its `lmstudio` check** (PRE-01 item 2). Gate 6 reruns
the suite once per mutation; budget minutes for it.

On the mechanism-found branch the test count MUST be **greater than 719** and
the mutation count **at least 71** (65 existing + the six of TST-05); state both
exact numbers, and correct the stale header comment in
`devtools/mutation_check.py` that says "64 in all" while 65 entries exist. Both
minima are conditional — GATE-02.

**REQ-V14-GATE-02 (MUST) — acceptance on the STOP branch.** If T4 ends under
RSN-06: T5 and T7 are not executed, REL-02 with its tests and mutation is
released (RSN-06 states section 9's branch once), and T8 reduces to the
mechanism-independent documentation of RPT-06's final paragraph — T5's half is
not executed, leaving REL-01's `.env.example` pair and the README lines that do
not describe the policy — with BEN-09 released. So the code
GATE-01's minima count does not exist. All six gates still run and exit 0 on the
final tree, gate 6 still kills **every** surviving mutation, the test count
still exceeds 719 by the tests of the requirements that *were* executed, and
TST-05's six-entry minimum reduces to the `v14-*` entries defending shipped code
(BEN-03's row-key rule, REL-01's boundary). The report states the actual counts
and lists **every** conditionally released REQ and test id.

Benchmark steps (section 10) are **blocking but not gates**: not run at every
commit, and a benchmark FAIL is a verdict to report, not a gate to repair.

---

## 12. Tests

### 12.1 Amendments to existing tests (exhaustive — nothing else may change)

| Test file | Change |
|---|---|
| `tests/test_observability.py` | the `llm_calls` column-set assertions gain the two new columns; the `purpose` `CHECK` assertions are **unchanged** (still exactly `'agent'`/`'summary'` — POL-02) |
| `tests/test_llm.py` | `complete()` signature assertions and fake clients gain POL-04's keyword (its default reproduces v1.3 behaviour) **and OBS-03's `LLMCompletion` return type** |
| `tests/test_failover.py` | the secondary-client fakes accept and record the new keyword (POL-04 site 5) and return `LLMCompletion` (OBS-03); the all-failed cases now raise `LLMCompletionError`, so their `pytest.raises(LLMError)` catches stand while the identity assertion at `:166` becomes one on the wrapper's message, `kind` and `attempts` |
| `tests/test_config.py` | the `Config` field-set assertion gains the two policy fields; the `LLM_TIMEOUT_S` / `LLM_MAX_TOKENS` cases gain REL-01's check **and its new `240` default** |
| `tests/test_bench.py` | `meta.env_flags` key-count expectations move from seven to nine; row-key validation tests follow BEN-03; the two comparability fixtures of BEN-05 are added |
| `tests/test_mutation_check.py` | the mutation-count assertion and `test_t_v12_mut_04_every_find_string_occurs_exactly_once_in_the_real_repo` cover the new `v14-*` entries; no change to the gate's own logic |
| `tests/fakes.py` | the fake LLM client accepts the new keyword — no behaviour change when it is absent — and returns `LLMCompletion` with exactly one attempt (OBS-03) |
| `tests/test_v14_patch.py` — **T-V14-POL-07's default assertion only** | the one literal BEN-09 is allowed to update when the shipped default is flipped to the winning policy. Nothing else in that file may be touched after T5 |

Nothing else (EC-03).

### 12.2 New tests (`tests/test_v14_patch.py`)

| ID | Asserts |
|---|---|
| T-V14-POL-01 | (POL-02) the truth table — all four `(purpose, request_tools)` combinations including `request_tools == []`, expected tags as literals |
| T-V14-POL-02 | (POL-03) `resolve_reasoning` over the full 3 × 3 policy × tag matrix plus empty `on_purposes`, expected values as literals |
| T-V14-POL-03 | (POL-04, RSN-03 item 3) request building: under `off` the mechanism's fields are present in the posted JSON body and absent under `model-default`; the bodies are otherwise byte-identical |
| T-V14-POL-04 | (POL-04 site 5) the keyword reaches the **failover secondary**: a primary raising a retryable error, a recording secondary, identical mechanism fields on both requests |
| T-V14-POL-05 | (POL-05 item 1) prefix integrity: two `run_agent` invocations under `off` and `model-default` give byte-identical system messages and byte-identical `tools` JSON |
| T-V14-POL-06 | (POL-06) `config_sha256` is equal for two `Config` values differing only in the policy fields, and differs when `llm_max_tokens` differs |
| T-V14-POL-07 | (POL-01) `load_config` rejects an unknown policy value, an unknown purpose tag, and accepts the empty-and-inert `on_purposes`, naming the variable and the token; the shipped default is asserted as a literal |
| T-V14-OBS-01 | (OBS-01, OBS-03) the `reasoning_requested` / `reasoning_honored` matrix, one case per row plus the failed-call `NULL` case, both columns present on the summary call, and **one failed-primary plus one successful-secondary** failover row, each labelled with the provider that served it. Plus both failure cases (OBS-03): a **failed direct call** — a plain `LLMError` converted at the boundary into exactly one failed attempt row — and an **all-providers-failed** failover — `LLMCompletionError` yielding one failed row per side, each naming its own provider — both with `reasoning_honored` `NULL` |
| T-V14-OBS-02 | (OBS-04) the honored rate, the `n/a` denominator-zero rendering, **and a fixture row shaped like a stage-A row** — the v1.3 column set, neither new column — which must render `n/a` rather than raise |
| T-V14-OBS-03 | (OBS-05) the drift guard: synthetic documents at `0.94` (DRIFT, verdict FAIL even with both gates otherwise green) and `0.96` (no DRIFT); a `model-default` candidate is never marked DRIFT |
| T-V14-REL-01 | (REL-01) the `LLM_TIMEOUT_S` / `LLM_MAX_TOKENS` boundary in both directions; the error text names both variables |
| T-V14-REL-02 | (REL-02 item 1) `summary` resolves to `"off"` under `off` and under `by-purpose`; `load_config` rejects `summary` in `LLM_REASONING_ON_PURPOSES` |
| T-V14-REL-03 | (REL-02 item 2) the `FINISH-LENGTH:` assertion — a candidate document with one `summary` + `length` row fails; one without does not; a baseline document with such a row does not |
| T-V14-BEN-01 | (BEN-03) the row-key rule — a v1.3-shaped fixture row validates, a row missing a required key is rejected naming it, a row with an unknown key is rejected |
| T-V14-BEN-02 | (BEN-05) `meta.env_flags` holds nine keys; a stage-A-shaped `Config` (both policy fields absent) yields `null` for both |
| T-V14-BEN-03 | (BEN-04) `meta.constants` is byte-equal between a `model-default` run and an `off` run, and `summarize()`'s output is unchanged for a v1.3-shaped document |
| T-V14-SCN-01 | (SCN-03) the repaired S01 check passes on each of the three recorded v1.3 candidate answers **and** on the baseline's passing answers, and still fails on an off-topic or refusing answer. Answers are inlined as literals, never read from a benchmark file. Written and run **only** on SCN-03's H1 branch |

**REQ-V14-TST-01 (MUST)** Offline discipline is unchanged: no new test touches
the network, DNS or a real Docker daemon; `tests/conftest.py`'s guards stay in
force; every LLM interaction in `pytest` is faked.

**REQ-V14-TST-02 (MUST)** Each asserted value comes from this spec or an
independent literal, never imported or re-derived from the implementation under
test. The reviewer's standing question — *which test fails if this line
changes?* — has a mechanical answer in gate 6
(`.claude/agents/code-reviewer.md:22-26`, `standards/workflow.md:73-79`).

**REQ-V14-TST-03 (MUST)** The three-value reasoning-purpose set and the
three-value policy set are each defined once and imported by the tests from
that single definition, while the **expected mappings** are written out as
literals. A test that builds its expectation from the function it is testing
proves nothing.

**REQ-V14-TST-04 (MUST)** No test asserts a live provider's behaviour. Whether
LM Studio honours the mechanism is established by the spike (section 5) and
re-confirmed by the benchmark's honored rate (OBS-04) — never by `pytest`, and
never by a host outside the repository.

**REQ-V14-TST-05 (MUST)** At least **six** new `v14-*` entries in
`devtools/mutation_check.py`, appended under a new banner comment in the
existing style, each a dict with exactly the keys `id`, `path`, `find`,
`replace`, `why` in that order, `id` of the form `v14-<kebab-description>` (no
numeric ordinal, matching the `v13-` family), `why` opening with the REQ id it
defends, and a `find` string occurring **exactly once** in its target file.
Minimum coverage: policy resolution with `by-purpose` treated as `off`
(POL-03); the failover secondary's forwarding at `llm/failover.py:83` (POL-04);
the drift-guard comparison flipped (OBS-05); the `summary` +
`finish_reason == 'length'` assertion (REL-02); the row-key rule with `⊆`
restored to `==` (BEN-03); the `honored` derivation with the `reasoning_chars`
half dropped (OBS-01). Each MUST make `uv run --locked pytest -x -q` exit
exactly `1` (KILLED); a `SURVIVED`, `ERRORED` or `DRIFTED` outcome fails
gate 6.

---

## 13. Acceptance, review and report

**REQ-V14-ACC-01 (MUST)** After the gates are green, execute Appendix B against
the live bot, plus spec-v1.2's D1 and D3 as a regression check that this patch
did not weaken the security posture. Record pass or fail per
scenario and — per REQ-V12-REP-02, still in force — **how** each was driven (a
real Telegram message, or a script standing in for one). "Driven by a script"
is acceptable; leaving it unsaid is not.

**REQ-V14-REV-01 (MUST)** Code review by the `code-reviewer` subagent in a
clean context, after the gates pass and before the final report, on the tree
that already carries BEN-09's default (ORD-01: T8 precedes T9). Findings are
fixed, or explicitly waived with a reason in the report. The review prompt is
its own numbered file in `docs/prompts/`. Any policy-selection or
verdict-affecting line with **no** mutation entry is a finding, not an
observation.

**A review fix invalidates the measurement it post-dates**, and how far back
depends on what it touches: a fix to the shared instrument invalidates the
baseline too, so replaying only candidates would compare them against a stale
`baseline-v1.4.json`.

1. **Baseline and candidates.** A fix affecting **scenario bytes** or benchmark
   **run-time collection or serialization** invalidates both sides: return to
   **T3**, regenerate the baseline through BEN-02's two-tree procedure (the
   worktree pinned at `69ebc75`), then replay **T7 → T8 → T9**. A scenario
   change after BEN-10 requires a revised spec unless it merely restores the
   already-authorized S01 diff (SCN-03).
2. **Candidates only.** A fix affecting candidate **product, configuration or
   provider behaviour** returns to **T7**: rerun the applicable sentinel and
   candidate run(s), regenerate `bench-v1.4.md`, repeat BEN-09 and rerun this
   review.
3. **Report only.** An **aggregation, comparability or verdict** fix that alters
   no stored artefact regenerates all affected reports and gates from the
   existing JSON files; it need **not** spend new live runs.

Documentation-, prompt-, test- and mutation-only fixes invalidate nothing. If
the benchmark cannot be rerun within budget, waive the finding or stop with a
blocker; **never** report a pre-fix measurement as evidence for the post-fix
tree. A tier-1 or tier-2 rerun is a **replay of the same treatment**, not a new
candidate: neither the replayed candidate runs nor a tier-1 re-baseline counts
against BEN-07's two-run cap or BEN-08's abort retry, and the fix plus its
replay is one EC-01 repair-and-rerun cycle.

**REQ-V14-RPT-01 (MUST)** `docs/reports/report-v1.4.md`, per
`standards/reporting.md` § "Run report" and `AGENTS.md` § Reporting — that
standard's full field list, with the **executor model always named** — plus:

1. **Verdict against `B_v1.4`** — `B_plain`, `C_plain`, `C_conservative`, the
   threshold, both gate outcomes, the honored rate, any `DRIFT:` or
   `FINISH-LENGTH:` line. The v1.3 figures `$0.002687` / `$0.002492` appear in a
   separate **informational** row saying why they are not the gate basis
   (BEN-01).
2. **The mechanism table** of RSN-04, with the LM Studio version.
3. **The S01 root cause** — hypothesis, evidence, the check diff if H1, the
   `temperature: 0` observation.
4. **Errata to earlier reports** (RPT-04).
5. Gates table with all six commands and the exact test count; the
   mutation-gate summary line, mutation count and wall-clock.
6. Appendix-B results with how each was driven; deviations (process ones
   included); fix cycles.
7. Known defects carried forward, incl. REL-03 and the accepted risks v1.2 and
   v1.3 already list.

**REQ-V14-RPT-02 (MUST)** There is **no** cumulative v1 → v1.4 section: this
report covers this release; the cross-version view lives in `economics.md` and
`docs/plan.md`.

**REQ-V14-RPT-03 (MUST)** `docs/reports/tg-post-v1.4.md`, Russian, structure
`constraints → result → metrics → links`, **strictly under 1500 characters by
`wc -m`** (state the measured count in the report), naming the executor model
and linking `https://github.com/axyi/tg-agent-bot`. Version matches the report;
regenerating replaces the file, never bumps the version.

**REQ-V14-RPT-04 (MUST) — Errata to earlier reports.** A section of
`report-v1.4.md` with exactly these two entries, and no edit to any earlier
report or to `docs/llm-usage.md` rows 1…31, which stay **byte-unchanged**:

- **E1 — the v1.2 cost, row 27 of `docs/llm-usage.md` (line 34).** The row says
  tokens were "not computed" and the cost `≈$33.11`. The figure has since been
  reproduced exactly, as two concurrent `claude-sonnet-5` sessions: `49c2d3e6…`
  (2026-09-01T20:06–22:12Z, spec `7ab107a`) `$16.50` and `c32c1cd8…`
  (21:45–23:28Z, implementation `d83a49e` + report `55d7ea0`) `$16.61`, under
  the ledger formula (`$2`/`$10` per Mtok, cache write ×1.25, cache read ×0.1).
  The per-class token counts are quoted from `economics.md`, which already
  carries the reconciled figures (`130.88M / 447.0k`,
  `≈$33.11 ($16.50 spec + $16.61 impl)`); row 27 is stale, not wrong.
- **E2 — the v1.3 prompt count.** `report-v1.3.md:14` ("19 prompt files 09–27")
  and `docs/llm-usage.md` row 31 (line 39, "18 of 19") are stale: the v1.3 `go`
  run logged **21** prompt files, `09-go-spec-v1.3.md` through
  `29-v13-TD2-tg-post.md` — 28 and 29 are stage D of the same run. Row 32
  (line 41) already
  says 21, and `economics.md` already says "21 (+1 post-verify docs fix)". Row
  31 is **not** edited: the corrected count lives here and in row 32.

**REQ-V14-RPT-05 (MUST)** `docs/llm-usage.md` gains rows starting at **33**,
appended after the current last data row (line 41), in the file's own
five-column shape (`| # | Stage | Model | Tokens | Cost |`; do not reshape the
table here). Every row names the executor model. Where the harness does not
expose counters, keep that note and add an estimate at public API prices,
marked as an estimate with its price source. Append the project's row to
lab-root `economics.md` after the report is written.

**REQ-V14-RPT-06 (MUST)** Documentation, in the same commit as the behaviour it
describes (`AGENTS.md`'s spec-drift rule): (1) `.env.example` —
`LLM_REASONING_POLICY` and `LLM_REASONING_ON_PURPOSES` with their shipped
defaults and a one-line comment each, beside the other `LLM_*` variables, plus
REL-01's `LLM_TIMEOUT_S=240`, and no third variable; (2) `README.md`
§ "Configure" and § "Token economy" — what the policy does, the three
reasoning-purpose tags, which mechanism the running LM Studio honours (with its
version), the measured saving and the caveat that it is model- and
runtime-specific; § "Observability" → "What is recorded" gains the two new
columns and § "Benchmark" the baseline-v1.4 procedure in one paragraph; (3) no
`LLM_REASONING` line anywhere (AMEND-01).

**The obligation splits across T5 and T8**, because the measured saving does not
exist at T5. **T5** writes, in the same commit as the implementation, the policy
contract, the three reasoning-purpose tags, the winning mechanism, the LM Studio
version, the two observability columns and the **initial `model-default`**
default. **T8** changes only the selected default and adds the measured outcome
and saving, and those edits accompany BEN-09's flip. On the RSN-06 STOP branch
neither half applies as written: T5 is not executed, and T8 keeps only the
mechanism-independent documentation — GATE-02 governs.

**REQ-V14-RPT-07 (MUST)** `docs/plan.md`: the status-table row for
`docs/spec/spec-v1.4.md`, and the § "v1.4 (next) — candidates, none applied"
section replaced by the delivered outcome plus the candidates that remain
untried (O6 routing, tokenizer-accurate budgets, streaming, semantic cache, and
levers 3, 4 and 7 of `report-v1.3.md`). Numbers come from `bench-v1.4.md`, not
from v1.3.

**REQ-V14-RPT-08 (MUST)** Committed benchmark artefacts, each with **its `.log`
sibling and its rendered `bench-*.md`**. **What is required depends on what was
executed.** Always: `baseline-v1.4`, `s01-repro`, `s01-verify`, **both members**
(`-default` / `-off`) of every *attempted* probe pair `rsn-<letter>-<n>`
(RSN-01), and, if run, `rsn-e-info` (a **single** run) and **both members** of
`rsn-b-low-info` (a **pair**, RSN-01's contract). On the mechanism-found
branch, additionally every *executed* candidate `cand-*` and both members of its
drift sentinel `drift-<candidate tag>` (OBS-05). The two OpenRouter smokes
`openrouter-reasoning-off` / `-default` are required **only when POL-07 was
executed**. No artefact for a released or not-executed run is required, and none
may be fabricated. The dry-run files of BEN-02 item 5 are scratch and are not
committed.

**One naming rule for the rendered reports.** For every committed `<tag>.json`,
render `docs/reports/bench-<tag>.md` with
`report --baseline docs/assets/bench/<tag>.json --out docs/reports/bench-<tag>.md`,
unless a specific comparison report is required for that tag. `bench-v1.4.md` is
*additionally* the baseline-versus-winning-candidate gate report (BEN-08) and
replaces neither side's standalone report. Losing candidates, both drift members
and both OpenRouter smokes each get a standalone report. The commands already
written out in RSN-01 and section 8 are this rule applied to their own tags; no
other naming may be invented.

`docs/assets/bench/*.log` is git-ignored and only `.json` files are tracked
there today, so `git add -A` has never satisfied the `.log` half of this
requirement — acceptance would silently miss the evidence. Each required log is
added with `git add -f docs/assets/bench/<tag>.log`, and **every** required
JSON/log pair is confirmed with `git ls-files` before the task is reported done.
Dry-run logs stay untracked, deleted with their JSON.

---

## 14. Implementation order and per-task acceptance

**REQ-V14-ORD-01 (MUST)** Follow this order. Each task is one prompt, one
commit, ending with the gates GATE-01 requires at that commit, green, before the
next begins. Task ids are distinct from prompt numbers and benchmark tags.

| id | task (owned files) | returns (acceptance) |
|---|---|---|
| T0 | Preconditions (PRE-01…05) **and the report skeleton** (`docs/reports/report-v1.4.md`): six gates on the untouched tree, credential presence by name, Docker, LM Studio **version recorded in that file**, worktree availability, vendor doc citations | the six exit codes; the LM Studio version string and the two doc citations **written into `report-v1.4.md`** before any live step; `git worktree add` dry-checked and removed |
| T1 | S01 root cause (`devtools/bench_scenarios.py`, `s01-*` artefacts) — SCN-01…04 | H1 or H2 with the named evidence incl. the system-prompt inspection and the `temperature: 0` note. **H1** → the check diff and `s01-verify` at 3/3. **H2** → the blocker template, and the run stops here (SCN-03) |
| T2 | Harness readiness (`devtools/bench.py`, `tests/test_bench.py`) — BEN-03, BEN-04, BEN-05 and BEN-02 item 5 | the row-key rule with its fixture tests; nine `env_flags` keys; the two comparability fixtures of BEN-05; the dry-run `report --gate` exit code (0 or 1, never 2/3) |
| T3 | Baseline-v1.4 (worktree at `69ebc75`, `baseline-v1.4.*`) — BEN-02, BEN-06 | the `meta` block quoted (locked fields, `skipped_scenarios: []`, `config_sha256`), 36 runs, `B_plain`, wall-clock, worktree removed |
| T4 | RSN spike (`llm/base.py`, `llm/lmstudio.py`, probe artefacts) — RSN-01…06 | the candidate table, **one row per pair member**, with the LM Studio version and each pair's verdict on its `off` row; a clean tree between candidates; PASS with the winning letter (never **e**), or STOP with `rsn-e-info` labelled out-of-repo |
| T5 | Policy + observability (`config.py`, `llm/*`, `agent.py`, `storage.py`, `devtools/bench.py`, `tests/test_v14_patch.py`, `.env.example`, `README.md`) — sections 6 and 7, RPT-06's T5 half | tests added and passing incl. the failover-secondary and prefix-integrity tests; the CCH-02 branch of POL-05 item 4 stated; the contract documented in the same commit with the **initial `model-default`** default |
| T6 | Reliability (`config.py`, `agent.py`, `devtools/bench.py`, tests) — REL-01…03; **on the STOP branch REL-01 and REL-03 only** (RSN-06) | the boundary tests; the `FINISH-LENGTH:` assertion, omitted on the STOP branch; REL-03's disposition |
| T7 | Candidate run(s) (`cand-*.*`, `drift-*.*`, `docs/reports/bench-v1.4.md`) — BEN-07, BEN-08, OBS-05's sentinel | per candidate: its sentinel pair verdict, then `C_plain`, `C_conservative`, threshold, both gate outcomes, honored rate, `report --gate` exit code; the winning tag or "neither" |
| T8 | Default selection and the measured outcome (`config.py`, `tests/test_v14_patch.py` — T-V14-POL-07's literal only, `.env.example`, `README.md`) — BEN-09, RPT-06's T8 half | the flip with the figure that justified it, or "stays `model-default`" and why; `.env.example` carrying both policy defaults **and** REL-01's `LLM_TIMEOUT_S=240`; the measured saving added to the README sections T5 created |
| T9 | Mutations + review (`devtools/mutation_check.py`, review prompt) — TST-05, REV-01 | the mutation count and gate-6 summary line; the review's findings with fixes or waivers |
| T10 | Report, post, errata, ledger (`report-v1.4.md` — completed, never created, `tg-post-v1.4.md`, `docs/llm-usage.md`, `docs/plan.md`, `economics.md`) — section 13 | `wc -m` of the post; the errata section; the ledger row; all six gates re-run green on the final tree |

T1 precedes T3 because the baseline must measure the repaired scenario file. T2
precedes T3 because a baseline the report reader cannot load is an hour lost.
T4 precedes T5 because there is nothing to configure until a mechanism is known
— and if T4 ends in the STOP rule, T5 and T7 are declared not-executed rather
than half-built, T6 narrows to REL-01 and REL-03 and T8 to its
mechanism-independent half, with **GATE-02** governing the test and mutation
counts. **T8 precedes T9** because BEN-09's flip is a verdict-affecting
production change and REV-01 reviews the shipped tree, not a draft of it; T9
precedes T10 because a report describes a reviewed tree. Two conditional
branches end the run early or narrow it: SCN-03's **H2** (blocker at T1) and
RSN-06's **STOP** (at T4). One branch reopens it: a T9 review fix reopens the
order by REV-01's tier — tier 1 back to **T3** for a fresh baseline and then
**T7 → T8 → T9**, tier 2 back to **T7**, tier 3 regenerating the affected
reports and gates from the existing JSON with no live run — a replay of the same
treatment on the fixed tree, never a new candidate (BEN-07).

### 14.1 Per-task reading map

Navigation aid, **not** a permission boundary: reading more is never a defect,
reading less never releases a requirement. §1 (EC-01…09), §2 (AMEND-01), §4
(TREE-01) and §15 (NG-01…08) bind every task and are not repeated per line.

- **T0** — reads §3, §11 (PRE-01…05, GATE-01)
- **T1** — reads §8, §10 opening (SCN-01…04, BEN-01)
- **T2** — reads §10, §12.1 (BEN-02 item 5, BEN-03, BEN-04, BEN-05)
- **T3** — reads §10 (BEN-02, BEN-06)
- **T4** — reads §5, §3, §6 (RSN-01…06, PRE-02, PRE-03, POL-05)
- **T5** — reads §6, §7, §12, §13 (POL-01…07, OBS-01…05, TST-01…04, RPT-06)
- **T6** — reads §9, §12 (REL-01…03, TST-01…04)
- **T7** — reads §10, §7, §13 (BEN-06…08, OBS-05, RPT-08)
- **T8** — reads §10, §13 (BEN-09, RPT-06)
- **T9** — reads §12, §13, §10 (TST-05, REV-01, BEN-09; BEN-02 and BEN-06
  because REV-01's tier 1 reopens T3)
- **T10** — reads §13, §11, Appendices A–B (RPT-01…08, ACC-01, GATE-01, GATE-02)

---

## 15. Non-goals for v1.4

Implementing any of these is a defect.

| ID | NON-GOAL | why |
|---|---|---|
| REQ-V14-NG-01 | Enabling O6 routing (`LLM_SUMMARY_MODEL`) or benchmarking a second model | two models do not fit in the maintainer's GPU box; measured ceiling −4.6 % |
| REQ-V14-NG-02 | Tuning `CONTEXT_WINDOW_MESSAGES`, `EXEC_OUTPUT_DEFAULT_CHARS`, `FETCH_INLINE_DEFAULT_CHARS` | ≈0 on this scenario set, or a trade against the quality gate that already failed |
| REQ-V14-NG-03 | Tokenizer-accurate context budgets, streaming, semantic cache | each needs a dependency or a redesign, and none is a token saving |
| REQ-V14-NG-04 | Changing any scenario's `id`, `title` or `turns`, or any check but S01's | the scenario set is the measuring instrument; changing it twice invalidates baseline-v1.4 |
| REQ-V14-NG-05 | A `purpose` column migration, a third database value, or any storage change beyond OBS-01's two columns | the reasoning-purpose tag is derived at request time and needs no persistence beyond `reasoning_requested` |
| REQ-V14-NG-06 | Editing `report-v1.2.md`, `report-v1.3.md` or `docs/llm-usage.md` rows 1…31 | those lines are stale, not false; the correction belongs in the new report |
| REQ-V14-NG-07 | An OpenRouter benchmark beyond POL-07's two-call smoke | it costs real money and measures a provider this project does not run on |
| REQ-V14-NG-08 | A third environment variable, a new module or dependency, or refactoring not required above | patch-release discipline |

---

## Appendix A — traceability

### A.1 Problems → requirements

| Problem | Requirements | Verified by |
|---|---|---|
| P1 reach the −30 % cost gate with quality green | RSN-01…06, POL-01…07, OBS-01…05, REL-01…03, BEN-01…10, GATE-02 | `bench-v1.4.md` `## Verdict`; `bench.py report --gate` exit code; `## Reasoning` honored rate |
| P2 v1.2 cost erratum | RPT-04 (E1) | the errata section of `report-v1.4.md`; `git diff` shows `docs/llm-usage.md` rows ≤ 31 unchanged |
| P3 v1.3 prompt-count erratum | RPT-04 (E2) | the errata section; `ls docs/prompts/09-*..29-*` counts 21 |

### A.2 v1.3 levers → disposition

Lever 1 (a reasoning switch LM Studio honours) → **taken**, sections 5–6;
levers 5 and 6 → **taken**, REL-01 and REL-02; lever 2 → NG-01; levers 3, 4 and
7 → NG-02. Source: `report-v1.3.md:326-350`.

### A.3 Mechanical hazards in the harness → requirements

`LLM_ROW_KEYS` derived from the running tree (`bench.py:159`, `:1087`) →
BEN-03; `meta.env_flags` fixed at seven keys (`:1031`) → BEN-05;
`config_sha256` locked and hashing every non-excluded `Config` field (`:132-143`)
→ POL-06; `meta.constants` locked and carrying `REQUEST_DEFAULTS` (`:143`) and
`summarize()` recomputed on load (`:1206`) → BEN-04; `skipped_scenarios` locked
and set by a live preflight (`:77-78`) → BEN-06; `comparability()`'s stage-C pin
(`:1268-1277`) → BEN-02; the five `complete()` sites → POL-04;
REQ-V13-CCH-02(a) versus in-message mechanisms → POL-05. **Round 1 added:**
`env_flags` **not** locked (`:141-150`, `:1249-1278`) → BEN-05;
`DEFAULT_OUT_DIR` bound to the running tree (`:73`) → BEN-02; `complete()`
returning only the winner (`llm/failover.py:50-71`) → OBS-03; versioned chained
migrations (`storage.py:142-160`) → OBS-01; `docs/assets/bench/*.log`
git-ignored → RPT-08. **Round 2 added:** S05's own tool-exposed /
tools-withheld groups mistakable for a probe pair → RSN-01's file-named pair
contract; `reasoning_honored` reading an omitted `reasoning_tokens` as zero →
OBS-05's pre-candidate sentinel. **Round 3 added:** `_reasoning_line` coercing
an absent `reasoning_tokens` to `0` (`bench.py:1597`) → OBS-04's `absent` marker
and RSN-03's 20 % rule; a post-measurement review fix silently invalidating the
benchmark → REV-01, BEN-09; artefacts demanded for runs the STOP branch never
executes → RPT-08's conditional list. **Round 4 added:** a review fix to the
shared instrument leaving `baseline-v1.4.json` measured with the old one →
REV-01's three-tier replay rule; a success-only completion envelope through
which a failed call carries nothing (`llm/base.py:56-63`,
`llm/failover.py:82-86`) → OBS-03's `LLMCompletionError`.

---

## Appendix B — acceptance scenarios (Gherkin, written before code)

```gherkin
# SAFETY RULE FOR EVERY SCENARIO BELOW: never use or print a live credential.
# Configuration scenarios use spec-v1.2 Appendix B's synthetic-canary pattern;
# the real .env is restored afterwards.

Feature: reasoning control that the runtime actually honours

  Scenario: E1 — the policy is off and the model stops thinking
    Given LLM_REASONING_POLICY is off
    And the winning mechanism of the spike is in place
    When the operator asks a question that needs one tool round
    Then the answer is correct
    And every llm_calls row of that turn has reasoning_requested = 'off'
    And every row has reasoning_chars = 0
    And reasoning_tokens is either an honestly reported 0, or NULL with the
        report rendering reasoning_tokens: absent (OBS-04) and the mechanism
        having satisfied RSN-03 item 3's omitted-token fallback
    And every row has reasoning_honored = 1 under OBS-01's runtime derivation

  Scenario: E2 — by-purpose keeps thinking exactly where it was asked for
    Given LLM_REASONING_POLICY is by-purpose
    And LLM_REASONING_ON_PURPOSES is tool-round
    When the operator asks a question that needs one tool round
    Then the tool-carrying request has reasoning_requested = 'on'
    And the tools-withheld final request has reasoning_requested = 'off'
    And the summary call, when one happens, has reasoning_requested = 'off'
    And the bot's answer is still correct

  Scenario: E3 — the default policy changes nothing
    Given LLM_REASONING_POLICY is model-default
    When the operator sends any message
    Then no reasoning field is present in the request body
    And reasoning_requested is 'default' and reasoning_honored is null
    And the system prompt and the tools JSON are byte-identical to the same
        request made under the off policy

  Scenario: E4 — a bad policy value stops the bot at startup
    Given LLM_REASONING_POLICY is set to a value that is not one of the three
    When the bot starts
    Then it exits with a configuration error naming the variable and the value
    And the same happens for an unknown tag in LLM_REASONING_ON_PURPOSES
    And the same happens when LLM_REASONING_ON_PURPOSES contains summary

  Scenario: E5 — the timeout and the token budget cannot disagree
    Given LLM_TIMEOUT_S is overridden to 120 and LLM_MAX_TOKENS is 2048
    When the bot starts
    Then it exits with a configuration error naming both variables
    And it starts normally on the shipped defaults, 240 and 2048 (REL-01)

  Scenario: E6 — a starved summary is a failure, not a quiet empty answer
    Given a scripted model whose summary call returns empty content with
          finish_reason length
    When a candidate benchmark run containing that call is reported
    Then the report prints a line beginning FINISH-LENGTH naming the scenario
    And the verdict is FAIL
    And the same row in a baseline file produces no such line

  Scenario: E7 — a drifting mechanism cannot be reported as a win
    Given a candidate run whose policy is not model-default
    And whose honored rate is below 0.95
    When the report is rendered with --gate
    Then it prints a line beginning DRIFT naming the measured rate
    And the verdict is FAIL even if both gates would otherwise pass

  Scenario: E8 — S01 measures capability, not phrasing (H1 branch only)
    Given SCN-02 classified the S01 failure as H1
    And the repaired S01 check
    When the bot answers the greeting with a fluent paraphrase that names no
         tool but describes what it can do
    Then the scenario passes
    And when the bot answers off-topic or refuses, the scenario fails

  Scenario: E9 — the baseline and the candidate are comparable or nothing
    Given baseline-v1.4.json produced on the stage-A tree with the v1.4
          scenario file and the v1.4 harness
    And a candidate produced on the v1.4 tree
    When report --gate compares them
    Then it does not exit 2
    And the ten locked meta fields are equal on both sides
    And skipped_scenarios is the empty list on both sides

  Scenario: E10 — nothing in this release leaks a secret
    Given the full set of committed v1.4 artefacts
    When they are scanned for the existing synthetic canary, for known
         credential key names in value positions, for URL user-info, for
         authorization headers and for unredacted Telegram identifiers
    Then no benchmark JSON, log, report, prompt file or spec matches
    And the bench file's Telegram id is the redacted placeholder
    And real credential values are neither read nor used as scanner inputs,
        so the scan stays inside EC-04
```

---

## Appendix C — cross-review log

Rounds **1–4 of 4**, termination: `round_limit` (the lab's default maximum);
challenger OpenAI Codex `gpt-5.6-sol` via the lab debate loop.

- **Round 1**, against spec-v1.4 at `5f05928`: all ten findings accepted, three
  **adapted** where the repository contradicted the premise.
- **Round 2**, against the round-1 tree: all ten accepted, one **adapted** —
  R2-8, where `AGENTS.md:71-93` requires gate 5 green at *every* commit, so the
  relaxation lands on gate 6 instead of gates 5 and 6.
- **Round 3**, against the round-2 tree: all seven accepted, two **adapted** —
  R3-3, where the fix generalizes to the existing candidate-**c** handling
  rather than amending POL-01's policy contract, and R3-6, where RSN-01 (`:252`)
  and SCN-01 already emit `bench-<tag>.md` names, so the new rule generalizes
  them instead of replacing them. Section 16 was deleted in this round as
  duplicated by §15 and Appendix C, and §14.1's reading map added.

| # | severity | REQ(s) touched | accepted | change |
|---|---|---|---|---|
| R1-1 | Critical | BEN-05 | adapted | `env_flags` is not locked and `comparability()` has no rule for the new keys, so no key-by-key comparison is added — the allowance is stated and pinned by fixtures |
| R1-2 | Critical | RSN-01…06, RPT-08, §14 | accepted | executable trial protocol (temporary patch per candidate, clean tree between them); tags `rsn-<letter>-<n>`; **e** demoted to environmental evidence with one gate-excluded `rsn-e-info` run |
| R1-3 | Critical | RSN-03 | accepted | item 3 becomes a live paired control; omitted `reasoning_tokens` → `unknown`, never honored; "3 runs of 3" = three pairs |
| R1-4 | Critical | BEN-02, BEN-03, PRE-04, §14 | adapted | worktree runs write into the main tree via the existing `run --out`; copy-then-verify kept as fallback; `.env` symlink specified |
| R1-5 | Critical | SCN-03, BEN-01, §14, E8 | accepted | H2 becomes a blocker before T2; the re-baseline premise and the H1-shaped tests are scoped to H1 |
| R1-6 | High | **GATE-02 (new)**, GATE-01, RSN-06 | accepted | conditional acceptance on the STOP branch: every mutation still killed, but the `> 719` / `≥ 71` minima bind only on the mechanism-found branch |
| R1-7 | High | REL-01, AMEND-01, E5, §12.1 | accepted | `211.564` confirmed against the spec's own formula; default `LLM_TIMEOUT_S` `120 → 240`, superseding EC-05 for that field; benchmark values move to process-env overrides |
| R1-8 | High | OBS-01, OBS-03, T-V14-OBS-01 | adapted | attempt-record envelope from `complete()`, each row naming its own provider; migration written as `SCHEMA_VERSION 3 → 4` + `_MIGRATION_3_TO_4`, the project's real mechanism |
| R1-9 | High | POL-07, RPT-08 | accepted | two commands with a real policy transition, `$0.05` each / `$0.10` combined, both artefacts committed |
| R1-10 | Medium | RPT-08 | accepted | benchmark logs are git-ignored: `git add -f` per required log, `git ls-files` verification of every pair |
| R2-1 | Critical | RSN-01…05, RPT-08, §14 | accepted | pair contract: two sequential S05 runs in one process, artefacts `rsn-<letter>-<n>-default/-off.json`, identical serialized input, never inferred from the tool-exposed groups |
| R2-2 | Critical | BEN-07 | accepted | "neither candidate passes BEN-08" is its own FAIL cause, not the RSN-06 branch; nothing is released |
| R2-3 | Critical | E10 | accepted | the secret scan matches the canary, key names in value positions, URL user-info, auth headers and Telegram ids; real values are never read (EC-04) |
| R2-4 | High | §14, REV-01, GATE-02 | accepted | BEN-09 moves into its own T8 before mutations/review; tasks renumber to T9 review, T10 report |
| R2-5 | High | OBS-03, AMEND-01, §12.1 | accepted | `LLMCompletion` / `LLMAttempt` in `llm/base.py`, returned by every `LLMClient`; EC-05 amendment row added for the internal return type |
| R2-6 | High | OBS-05, BEN-07, RPT-08 | accepted | pre-candidate drift sentinel: one paired S05 control per candidate, `drift-<tag>-default/-off.json`, cited in `bench-v1.4.md` |
| R2-7 | High | RSN-06, GATE-02, §14 | accepted | the STOP branch executes REL-01 and REL-03 only; REL-02, its two tests and its mutation are named as released, once |
| R2-8 | High | GATE-01, ORD-01 | adapted | gates 1–5 at every commit, gate 6 at commits touching code/config/verdict logic/tests/mutations and on the final tree — `AGENTS.md` forbids dropping gate 5 |
| R2-9 | Medium | RSN-02 | accepted | stop at the first candidate that is honored **and** shippable under POL-05; `honored but unshippable` consumes its budget and probing continues |
| R2-10 | Medium | PRE-02, §14 | accepted | T0 creates and initializes `report-v1.4.md` with the LM Studio version and vendor citations; T10 completes it |
| R3-1 | Critical | REV-01, BEN-09, BEN-07, §14 | accepted | a review fix touching code/config/payloads/checks/aggregation/verdict invalidates every earlier candidate measurement → replay T7→T8→T9; BEN-09 is the only treatment-affecting change *not* needing remeasurement; the replay is not a third run |
| R3-2 | Critical | RPT-08 | accepted | committed artefacts are conditional on execution: always baseline/`s01-*`/attempted pairs, candidates and drift sentinels only on the mechanism-found branch, OpenRouter smokes only when POL-07 ran; nothing fabricated |
| R3-3 | High | POL-05, RSN-02 | adapted | candidate **d** becomes `honored but unshippable` beside **c** and cannot authorize T5/T7 — `by-purpose` stays in POL-01's contract, since removing it would amend an already-selected contract |
| R3-4 | High | RSN-02, RSN-04, RSN-05, RSN-06, PRE-03 | accepted | candidate **b** is the vendor-documented *disable* value read live under PRE-03; only `low\|medium\|high` → `unsupported`, never an accidental zero; `effort: low` survives as the informational `rsn-b-low-info` pair, outside every gate and budget |
| R3-5 | High | RSN-03, OBS-04, E1 | accepted | omitted `reasoning_tokens` → `unknown` unless default has positive `reasoning_chars`, off has zero, and off's completion tokens **and** recomputed cost are ≥ 20 % below default at the default member's price snapshot, on all three pairs; `_reasoning_line` must render `reasoning_tokens: absent` distinctly from `0` |
| R3-6 | High | RPT-08, TREE-01 | adapted | one rule — `docs/reports/bench-<tag>.md` per committed `<tag>.json`, `bench-v1.4.md` additionally the gate report; RSN-01 and section 8 already followed it, so the rule generalizes rather than replaces; TREE-01 extended |
| R3-7 | Medium | RPT-06, §14 T5/T8 | accepted | T5 documents the contract and the initial `model-default` in its own commit, T8 only the selected default and the measured saving; owned-file lists updated, STOP branch deferred to GATE-02 |
| R4-1 | Critical | RSN-03, OBS-05 | accepted | item 1's `absent` marker no longer voids item 3's fallback: a pair rendering `reasoning_tokens: absent` satisfies item 1 **through** that fallback, else stays `unknown`; OBS-05's sentinel reads the same rule |
| R4-2 | Critical | OBS-03, AMEND-01, T-V14-OBS-01, §12.1 | adapted | `LLMCompletionError(LLMError)` carries a failing call's attempts; the class is `FailoverLLMClient` (`llm/failover.py:20`), not `FailoverClient`, and **only** it raises the new type — a direct client keeps raising plain `LLMError`, converted at the agent boundary into one failed attempt |
| R4-3 | High | REV-01, ORD-01, BEN-07, §14.1 | accepted | three-tier replay: a scenario-bytes or run-time collection/serialization fix → T3 re-baseline then T7→T8→T9; a candidate product/config/provider fix → T7; a report-only aggregation/comparability/verdict fix → regenerate from the existing JSON, no live runs |
| R4-4 | High | E1, RSN-03, OBS-01 | accepted | E1 asserts `reasoning_chars = 0` and `reasoning_honored = 1`, with `reasoning_tokens` an honest `0` **or** a `NULL` rendered `absent` that satisfied item 3's fallback |

Rounds 1–4: 31 findings, 31 accepted (7 adapted to repository facts, recorded
per row); nothing refused.
