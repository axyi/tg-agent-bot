# spec-v1.4 — close the v1.3 benchmark FAIL: honored reasoning control, S01 check repair, errata

The complete contract for a **patch release** on the delivered v1.3 state
(`main` at `3a0aa3d`). It is a **delta specification**: spec-v0 … spec-v1.3
remain in force except where a requirement here explicitly **amends**,
**supersedes** or **extends** them (section 2 is the authoritative amendment
table). Everything needed to implement, test and accept the work is in this
file, in the earlier specs, or in files this spec tells you to change.

Every requirement has a stable `REQ-V14-*` id, never colliding with an earlier
one, tagged `MUST` (required for acceptance), `SHOULD` (required unless a
stated condition releases it, and the release is declared in the report) or
`NON-GOAL` (implementing it is a defect, not a bonus). Requirements are cited
inside this file by their short form (`BEN-03`, `POL-05`).

Platform **Linux**, language **Python**, package manager **uv**. Executor model
**claude-sonnet-5**: the difficulty here is a bounded live experiment with a
decision tree and a benchmark whose comparability rules are already mechanised
in `devtools/bench.py`. A larger model is not needed and must not be
substituted for reading this spec carefully.

**Provenance.** v1.3 shipped six token-economy optimizations and failed its own
§13.3 verdict on both gates (`docs/reports/bench-v1.3.md:166-178`): `B_plain
$0.002687`; `C_plain $0.002492` (**−7.3 %**, target −30 %); threshold
`0.70 × B_plain = $0.001881`; success rate `1.0000 → 0.9444`; regressed
scenario `S01 3/3 → 1/3`; verdict **FAIL**. Its ranked lever list
(`report-v1.3.md:326-350`) puts a reasoning switch LM Studio actually honours
at **−31.6 % … −35.2 %** of the candidate's cost on its own — reasoning is
71.8 % of completion tokens, and completion is priced at `$2.55/Mtok` against
`$0.425/Mtok` for prompt. That was measured, not guessed. Levers 5 and 6 are
reliability, not saving. This release takes 1, 5 and 6, repairs S01, and
re-baselines, because every one of those changes the measured treatment.

**Three problems, and nothing else.**

- **P1 — the gate.** Reach `C_plain ≤ 0.70 × B_v1.4` **and**
  `C_conservative ≤ 0.70 × B_v1.4` with the quality gate green, by controlling
  reasoning per call through a mechanism the running LM Studio honours.
- **P2 — the v1.2 cost erratum.** `docs/llm-usage.md` row 27 says tokens were
  "not computed"; they were later reconstructed. Recorded, not rewritten.
- **P3 — the v1.3 prompt-count erratum.** `report-v1.3.md:14` and
  `docs/llm-usage.md` row 31 say "19 prompt files 09–27" / "18 of 19"; the run
  logged 21 files, `09-…` through `29-…`. Recorded, not rewritten.

**This is a patch release.** Behaviour changes only where a requirement below
says so: no new features, no refactoring beyond what a listed change requires,
no opportunistic cleanups. Every v0…v1.3 acceptance property must still hold.
Appendix A maps every problem to requirements; Appendix B is the acceptance
scenario set, written before the code.

---

## 1. Execution contract

**REQ-V14-EC-01 (MUST)** Section 1 of spec-v0 … spec-v1.3 applies unchanged,
with these adjustments:

- "The gate commands" means the **six** commands of section 11, verbatim.
- The repair budget is **5 total** repair-and-rerun cycles (one cycle = one fix
  + one complete run of all gates from the first). Live benchmark steps are not
  gates and have their own retry rules (BEN-08).
- REQ-V1-EC-01 stands absolutely — the executor reads and writes **nothing
  outside the repository root** — with one mechanical exception this spec
  creates: the git worktree of BEN-02, a checkout of *this* repository at a
  named commit, created, used and removed by the executor. It carries no
  secrets of its own and reads the repository's `.env` by absolute path.
- The dependency set stays `httpx`, `python-dotenv`, plus the `docker` CLI as a
  host dependency. Everything this spec adds uses the standard library.

**REQ-V14-EC-02 (MUST)** Work test-first: write the tests of section 12 before
the production change they describe, observe them fail for the right reason,
then implement. Every new production branch of sections 6–9 gets a `v14-*`
entry in `devtools/mutation_check.py` (TST-05); gate 6 is the evidence, not a
hand-written table.

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
when absent, so unlisted tests and fakes keep passing. `LLM_REASONING_POLICY`
ships as `model-default` until BEN-07 selects a winner; the flip to the winning
policy is the single post-benchmark change this spec authorises (BEN-09).

**REQ-V14-EC-06 (MUST)** One prompt → one commit, on `main`, per `AGENTS.md`.
Each task of section 14 is one prompt file in `docs/prompts/` and one commit
referencing it (`(prompt: docs/prompts/NN-<slug>.md)`). Numbering continues the
chain: **`31-go-spec-v1.4.md`** is this run's `go` prompt; task prompts follow
from `32`. Never mix two prompts in one commit. No `git push` unless the `go`
prompt says so.

**REQ-V14-EC-07 (MUST)** Every prompt file carries the project's bullet header
**from the moment it is created** — not retro-fitted, which is what prompt 30
had to do for the whole v1.3 chain. Exactly the field set and order of
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
goes to a subagent with a brief of ≤ 8 lines plus REQ ids plus its owned file
list, returning ≤ 15 lines — never a file dump, never `.env`. Code review runs
in a clean `code-reviewer` context (REV-01), never in the writing context.

**REQ-V14-EC-09 (MUST)** Live steps are blocking: the run stops until the
artefact exists on disk, and an unfinished step is never assumed green. No
figure in any report is estimated when a measurement was specified; an
unavoidable estimate is labelled `(ESTIMATE)` with its derivation, as v1.3 did.

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
| REQ-V13-OBS-04 (`llm_calls` schema) | **extended** | two columns: `reasoning_requested`, `reasoning_honored` (OBS-01) |
| REQ-V13-RTE-01 (`LLM_SUMMARY_MODEL`) | **unchanged, stays disabled** | MUST be empty in every benchmark run (`bench.py:1264-1265` refuses otherwise). Its call-purpose axis is *not* reused verbatim — see POL-02 |
| `report-v1.2.md`, `report-v1.3.md`, `llm-usage.md` rows 1…31 | **frozen** | byte-unchanged; both errata are recorded **only** in the new report (RPT-04) |
| `AGENTS.md` gates and benchmark commands | **unchanged** | reproduced verbatim in sections 11 and 10 |
| `docs/plan.md` § "v1.4 (next)" | **superseded** | replaced by the delivered status plus the remaining candidates (RPT-07) |

Everything else in v0…v1.3 — the Docker isolation posture, the redaction choke
points, failover, structured memory, commands, rate limiting, the error matrix,
the token budget, the observability layer, the pricing resolver, the dashboard,
the mutation gate — is unchanged and MUST keep working.

---

## 3. Preconditions (verify before writing any code)

**REQ-V14-PRE-01 (MUST)** Verify each item; on failure stop and emit the
blocker template (spec-v0 §7.2) instead of guessing.

1. Branch `main`, clean tree, HEAD at `3a0aa3d`.
2. All six gates green **before** you change anything, gate 5 and its
   `lmstudio` check included. The v1.2 "record the LM Studio failure and
   proceed" exception was withdrawn in v1.3 and stays withdrawn: an
   unreachable LM Studio is a blocked run, because the benchmark measures
   against it.
3. `.env` exists (git-ignored) and contains `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_BOT_NAME`, `ALLOWED_TG_IDS`, `LLM_PROVIDER`, `LMSTUDIO_BASE_URL`,
   `LMSTUDIO_MODEL`, `LMSTUDIO_CONTEXT_LENGTH`, `OPENROUTER_API_KEY`,
   `OPENROUTER_MODEL`. Validate **presence by key name only**; printing a value
   is forbidden. Do not create or overwrite `.env`.
4. `docker version` succeeds without `sudo`; the sandbox image is present
   locally (`docker image inspect`).
5. `docs/assets/bench/` is writable; `.bench/` is git-ignored scratch, wiped at
   the start of every `bench.py run`.

**REQ-V14-PRE-02 (MUST)** Record the **LM Studio version** and the loaded model
identifier before any live step, in `report-v1.4.md`. This is the most
load-bearing environmental fact in the release: v1.3's mechanism failed against
one build, and a later reader can neither reproduce nor refute the spike
without the version. Quote it verbatim from the UI or the CLI. The model MUST
be `qwen/qwen3.8-27b` with `LMSTUDIO_CONTEXT_LENGTH=42496`, matching every v1.3
file (`bench-v1.3.md:12-13`); a different model or context length is a blocker,
not an adaptation.

**REQ-V14-PRE-03 (MUST)** Verify against the vendor's own current documentation
— not from memory — the request-field names each spike candidate needs, and
cite what you read in the report:

- LM Studio's OpenAI-compatible `/v1/chat/completions`: whether unknown
  top-level body keys are forwarded to the chat template, and whether a
  `reasoning` / `reasoning_effort` field is accepted for a Qwen3-class model.
  LM Studio documents `reasoning.effort` (`low|medium|high`) for gpt-oss-class
  models; whether it binds on Qwen3 is **unknown and must be measured**.
- OpenRouter's documented reasoning request field, for provider parity
  (POL-07). As of this spec's writing (OpenRouter docs, "Reasoning tokens"
  guide, read 2026-09-03) the request-body object is
  `"reasoning": {"enabled": false}` (equivalently `"effort": "none"`);
  `"exclude": true` only hides reasoning from the response and still bills
  the tokens, so it MUST NOT be used as the off-switch. Re-read the guide at
  run time and cite the date; if the field changed, the executor follows the
  live docs and records the difference in the report.

**REQ-V14-PRE-04 (MUST)** Prove the two-tree measurement is mechanically
possible **before** spending an hour of live inference on it — the dry run of
BEN-02 item 4. A baseline the v1.4 report reader cannot load is an hour lost
and a run that cannot be salvaged.

**REQ-V14-PRE-05 (MUST)** `git worktree` is available and the tree is clean, so
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
docs/reports/report-v1.4.md
docs/reports/tg-post-v1.4.md
```

Changed: `config.py`, `agent.py`, `llm/base.py`, `llm/lmstudio.py`,
`llm/openrouter.py`, `llm/failover.py`, `llm/__init__.py`, `storage.py`,
`devtools/bench.py`, `devtools/bench_scenarios.py`, `devtools/mutation_check.py`,
`.env.example`, `README.md`, `docs/llm-usage.md`, `docs/plan.md`, plus exactly
the test files of section 12.1.

Benchmark artefacts land in `docs/assets/bench/<tag>.json` with a sibling
`<tag>.log` (`bench.py:73`, `:2059-2061`) and are **committed**; `.bench/` is
scratch and stays git-ignored. No new module, package or dependency.

---

## 5. RSN — the mechanism spike

v1.3's O5 ended `attempted_removed`: `chat_template_kwargs` was undocumented by
LM Studio, Qwen3's `/no_think` soft switch was used instead, and the probe
showed an unchanged reasoning share of `0.7373` (`report-v1.3.md:208-225`,
`docs/reports/bench-reasoning-probe.md:94`). That conclusion was correct and
narrow — *that* mechanism, on *that* build, did not bind — so the optimization
is implemented-and-removed, **not disproven**. This section finds a mechanism
that binds, or proves that none of the five available ones does.

**REQ-V14-RSN-01 (MUST)** The probe is v1.3's probe, unchanged in shape, so its
output is directly comparable with `bench-reasoning-probe.md`:

```bash
uv run --locked python devtools/bench.py run --only S05 --repeats 1 --tag rsn-<letter>
uv run --locked python devtools/bench.py report --baseline docs/assets/bench/rsn-<letter>.json --out docs/reports/bench-rsn-<letter>.md
```

S05 is a one-turn scenario with exactly one tool round, so a single run
exercises a tool-exposed call and a tools-withheld final call. `--only` already
exists (`bench.py:1773`); **no new CLI flag is added to `bench.py`**.

**REQ-V14-RSN-02 (MUST)** Try these candidates **in this order**, one live probe
each, stopping at the first that passes RSN-03. Trying a later candidate after
an earlier one passed is out of scope; skipping an untried one is a defect.

| letter | mechanism | where it lands |
|---|---|---|
| a | `chat_template_kwargs: {"enable_thinking": false}` | a **top-level key of the JSON body** built by `llm/base.py:build_payload`. The repo posts raw JSON with `httpx` and has no OpenAI SDK, so there is no `extra_body` wrapper: what an SDK sends as `extra_body` is a plain top-level key here |
| b | `reasoning: {"effort": "low"}`, and if rejected `reasoning_effort: "low"` | top-level key of the JSON body |
| c | assistant prefill of an empty think block — a final `{"role": "assistant", "content": "<think>\n\n</think>\n\n"}` | **inside the message array**, as the last element |
| d | Qwen3's `/no_think` soft switch on the **last user message** | inside the message array, in the slot REQ-V13-CCH-01 already mutates with `(now: …)`. First establish **where v1.3 put it** (`report-v1.3.md:208-225`) and report whether this attempt differs |
| e | a model-level default set in LM Studio (GUI or `lms` CLI) | not in the request at all |

Candidate **e** is a documented fallback only: it is **not per-request**, so it
cannot express a `by-purpose` policy and is not reproducible from this
repository. If it is the only thing that works, the shipped policy stays
`model-default` plus a README note, the cost figures are still measured, and
the report says plainly that the saving is bought with an out-of-repo setting.
The exact control (a per-model setting in the LM Studio GUI, or an `lms`
load-time option) is version-dependent: the executor looks it up in the LM
Studio docs for the version recorded under PRE-02, names it in the README
note and in the report, and does not guess.

**REQ-V14-RSN-03 (MUST)** A candidate **passes** only when all three hold:

1. **Honored, 3 runs of 3.** Each of three probe runs shows, on the
   `## Reasoning` → `tool-exposed calls:` line, `reasoning observed: no` —
   `Σ reasoning_tokens == 0` **and** `max reasoning_chars == 0`. Both are
   required because they come from different sources: `reasoning_tokens` is
   read from `usage.completion_tokens_details.reasoning_tokens`
   (`llm/base.py:149-153`) and is `None` when the provider omits it, while
   `reasoning_chars` is computed locally from `reasoning_content` / `reasoning`
   / `<think>` blocks (`llm/base.py:158-182`). A provider that stops
   *reporting* reasoning while still *emitting* it passes a token-only test and
   saves nothing. Read the verdict off the rendered markdown only, as
   REQ-V13-RSN-02 did.
2. **Still correct.** S05 shows `1/1` in `## Per scenario` (its
   `tool_used("exec")` and `answer_regex(r"\b332\b")` checks passed) in each of
   the three runs. A mechanism that suppresses reasoning by breaking the model
   has not passed.
3. **Per-request switchable.** Within one process, one call is issued with
   reasoning requested off and the next at the model default, and the two rows
   differ in `reasoning_chars`. This separates a request parameter from
   candidate **e** and is what a `by-purpose` policy needs. Proven by a unit
   test against a fake transport (T-V14-POL-03) **and** by item 1's live
   evidence against the v1.3 probe's `0.7373` share.

**REQ-V14-RSN-04 (MUST)** Record every candidate's outcome — failures included
— in a table in `report-v1.4.md`: letter, mechanism, LM Studio version, HTTP
status or error text if rejected, `Σ reasoning_tokens`, `max reasoning_chars`,
`reasoning share`, S05 result, verdict. A failed candidate is a result, not a
deleted attempt: the next person needs the negative evidence more than the
positive. Probe artefacts are committed for every candidate tried.

**REQ-V14-RSN-05 (MUST)** Probe budget: five candidates × two runs each for the
failing ones, three runs for the passing one, plus one re-run of any probe
whose S05 check failed for a reason unrelated to reasoning (transport timeout,
Docker hiccup). Beyond that, stop: the spike has an answer, and the answer may
be "none".

**REQ-V14-RSN-06 (MUST) — the STOP rule.** If no candidate passes RSN-03,
**there is no optimization commit.** The run still delivers, in full: the S01
repair (section 8), baseline-v1.4 (BEN-02), both errata (RPT-04), the
reliability fix that does not depend on the mechanism (REL-01), the mechanism
table (RSN-04), and a report whose verdict is **FAIL, cause: no honored
reasoning mechanism**. Section 6, the two new columns of section 7, the policy
half of section 9 and section 10's candidate runs are then not executed and are
declared not-executed. This is an acceptable outcome. Shipping a knob the
runtime ignores, or reporting a saving the measurement does not support, is
not.

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
means "no purpose keeps reasoning", which is exactly `off`; the variable is
inert unless the policy is `by-purpose`, and the README says so. Both appear in
`.env.example` with their defaults (RPT-06).

**REQ-V14-POL-02 (MUST) — the reasoning-purpose tag.** The database's `purpose`
column has exactly two values, `'agent'` and `'summary'`, under a SQLite
`CHECK` (`storage.py:54`), re-validated by the benchmark (`bench.py:1100`). It
does **not** distinguish a tool-selection call from a final-answer call: both
are `'agent'`, and the distinction lives only in the request-time locals
`expose_tools` / `request_tools` (`agent.py:241-247`). That column is **not**
changed here — a `CHECK` change is a migration, and a migration is a non-goal
(NG-05). Instead, define a **derived, request-time reasoning-purpose tag** with
exactly three values:

| tag | condition |
|---|---|
| `tool-round` | `purpose == "agent"` and the request carries tools (`request_tools` is not `None` and non-empty) |
| `final` | `purpose == "agent"` and tools are withheld (`request_tools is None`) |
| `summary` | `purpose == "summary"` |

The tag is a pure function of `(purpose, request_tools)` with no I/O and no
global state, lives in `llm/base.py`, and is the single source of truth for the
three-value set — never a hand-copied literal list in `config.py`, `agent.py`
or the tests. This mirrors REQ-V13-RSN-02, which defined `auto` on exactly
these three cases; v1.4 names them and makes them configurable.

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
`:83`. Site 5 is the one that gets forgotten, and forgetting it means the
failover secondary silently reasons at full price after the primary fails. Test
(T-V14-POL-04): a fake primary raising a retryable error and a recording
secondary — the secondary's request MUST carry the same mechanism fields as the
primary's; a `v14-*` mutation removes the forwarding at `:83` and MUST be
killed. Call sites pass the tag: `agent.py:253` (tag from `request_tools`) and
`agent.py:805` (tag `summary`).

**REQ-V14-POL-05 (MUST) — the mechanism must not disturb the cached prefix.**
REQ-V13-CCH-01 fixes the system prompt and the `tools` JSON byte-for-byte
across a conversation; REQ-V13-CCH-02(a) requires round *n*'s serialized
message list to be a prefix-extension of round *n−1*'s. Therefore:

1. The mechanism MUST NOT be written into the system prompt or the `tools`
   JSON under any policy (test T-V14-POL-05).
2. A mechanism carried **outside** the message array (candidates **a**, **b**)
   satisfies CCH-02 under every policy — the array is untouched.
3. A mechanism carried **inside** the array is constrained. Candidate **c**
   breaks CCH-02(a) under *every* policy: the prefill must be the last element,
   so as the array grows between rounds the element at the older array's final
   index changes from the prefill to a tool-call message, and the older list is
   no longer a prefix of the newer one. Candidate **d** satisfies CCH-02(a)
   only while the resolved value is the **same for every call of one
   `run_agent` invocation** — i.e. under `model-default` and `off`, but not
   under `by-purpose`, where a tool round and the final call would need
   different bytes at an early index.
4. Consequently: if the passing candidate is **c**, it does not ship — report
   it found-but-rejected with this reason and fall through to the next
   candidate in the RSN-02 order. If it is **d**, only `off` may be exercised
   as a benchmark candidate, `by-purpose` is out of scope for this release, and
   BEN-07's candidate order collapses to run A alone. Say which branch was
   taken.

**REQ-V14-POL-06 (MUST)** Both new `Config` fields are added to `bench.py`'s
`CONFIG_HASH_EXCLUDED` (`:132-139`), in the treatment group beside
`llm_reasoning`, with a comment naming this requirement. `config_sha256` is a
**locked** meta field (`:143`): if the policy fields were hashed, the baseline
and every candidate would differ by construction and `report --gate` would exit
2 before measuring anything.

**REQ-V14-POL-07 (SHOULD) — provider parity.** The policy is provider-agnostic:
POL-03's resolution is shared and only request building differs per provider.
LM Studio uses the spike's winning mechanism; OpenRouter uses its own
documented reasoning field (PRE-03). Proven by a bounded live smoke of **two
calls** — one with reasoning requested off, one at the model default — capped
by `--max-cost-usd 0.10`, following the precedent of
`docs/reports/bench-openrouter-smoke.md` (`--only S02 --repeats 1`,
`$0.000212`):

```bash
uv run --locked python devtools/bench.py run --provider openrouter --only S02 --repeats 1 --max-cost-usd 0.10 --tag openrouter-reasoning-smoke
```

Released only if the spike ended under RSN-06 (nothing to be at parity with) or
if OpenRouter's current API documents no such field, in which case the report
says so and the OpenRouter path keeps sending nothing. The smoke's two rows and
their `reasoning_chars` go in the report. It is **not** a benchmark candidate
and never enters a gate comparison.

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

**REQ-V14-OBS-02 (MUST)** `finish_reason` is already a column (`storage.py:30`,
written at `agent.py:695` from `choices[0].finish_reason`). No schema change;
it is surfaced (OBS-04) and asserted (REL-02).

**REQ-V14-OBS-03 (MUST)** Both new columns are recorded for **every** LLM call
including the summary call and every failover attempt, through the existing
`_record_llm_call` seam (`agent.py:650`), never a second write path.

**REQ-V14-OBS-04 (MUST)** `bench.py`'s `## Reasoning` section (`:1575-1618`)
gains, per side and per group (overall, tool-exposed, tools-withheld):
`Σ reasoning_tokens` and `max reasoning_chars` before and after (already
present; the format is unchanged so v1.3's files stay readable), plus
**`honored rate`** =
`count(reasoning_honored == 1) / count(reasoning_requested in ('on','off'))`,
rendered `n/a` when the denominator is 0.

**The two new columns MUST be read with a missing-key-tolerant accessor**, not
by direct indexing as `_reasoning_line` does today for `reasoning_tokens`
(`:1604`). The baseline of BEN-02 is produced on the stage-A tree, whose
`llm_calls` rows carry the v1.3 column set and **no** `reasoning_requested` —
which BEN-03 makes loadable but does not conjure into existence. A row lacking
the key is excluded from the denominator; a side whose rows all lack it renders
`n/a`. Without this clause the first `KeyError` arrives at T7's final
`report --gate`, after the baseline hour and a full candidate run are already
spent.

**REQ-V14-OBS-05 (MUST) — the mechanism-drift guard.** In `bench.py`'s verdict
path: when the candidate's `meta.env_flags.LLM_REASONING_POLICY` is anything
other than `model-default` **and** the candidate's overall honored rate is
below `0.95`, the report prints a line beginning `DRIFT:` naming the measured
rate, and the verdict **cannot** be `PASS` — `passed` is forced `False` with
reason `reasoning mechanism drifted`. This guards against exactly what v1.3
hit: a knob the runtime silently stops honouring, producing a saving that
evaporates on the next model load. A `v14-*` mutation flips the comparison and
MUST be killed.

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

`--only` already exists (`bench.py:1773`); **no new flag is added**. Both
artefacts are committed as the evidence. The `answers` field of each `runs[]`
record holds the model's text and *is* the transcript this requirement means by
"keep transcripts"; no separate transcript file is created, and none may
contain a credential.

**REQ-V14-SCN-02 (MUST)** Classify with named evidence, not by assumption. The
report states which hypothesis the evidence supports and why:

- **H1 — check defect.** The answer meets the scenario's intent (a short,
  correct Russian answer to "hello, what can you do?") but the regex enumerates
  six surface tokens a fluent paraphrase need not contain, so the check
  measures phrasing, not capability.
- **H2 — genuine regression.** The v1.3 prefix rewrite (O4/PFX) changed the
  system prompt: `prefix_tokens` fell `1126 → 842` (`bench-v1.3.md:21`). If the
  rewritten prompt no longer names the tools, the model can no longer name them
  either, and the bot has actually got worse at describing itself.

The discriminating question MUST be answered explicitly in the report: **does
the v1.3 system prompt still name `exec`, `fetch` and the skill mechanism?**
Inspect the assembled system prompt directly (a unit-level assertion, not a
live call). The classification MUST also account for repeat 3 passing at
`temperature: 0` — identical inputs producing different text means the sampling
path is not deterministic end to end, and the winning hypothesis has to survive
that fact.

**REQ-V14-SCN-03 (MUST)** Repair according to the classification, and only
according to it:

- **H1** → change **only** S01's `checks` expression. `id`, `title` and `turns`
  stay byte-identical; no other scenario is touched; `no_tools` and
  `answer_max_chars(900)` stay. The replacement MUST stay faithful to the
  intent — it accepts a tool name **or** a capability phrase, so a correct
  paraphrase passes and an off-topic or refusing answer still fails. The exact
  diff (old pattern, new pattern, one sentence of rationale) goes in the report
  and in `bench-v1.4.md`'s preamble.
- **H2** → the check is **untouched**; the fix is in the prompt or prefix that
  lost the information, and it is a behaviour change section 10's baseline
  measures like any other.

Either way `bench_scenarios.py` changes, so `scenarios_sha256` changes and
BEN-01 applies. Do not fix both at once: a repaired check over a repaired
prompt measures neither.

**REQ-V14-SCN-04 (MUST)** After the repair, re-run SCN-01's command with tag
`s01-verify` and require **3/3**. A repair that still fails a repeat is not a
repair; return to SCN-02. Both artefacts are committed. The existing loading
test of REQ-V13-BEN-08 (no `\|` two-character sequence in any pattern) MUST
stay green.

---

## 9. REL — reliability

**REQ-V14-REL-01 (MUST) — lever 5, the timeout/budget mismatch.**
`LLM_TIMEOUT_S` defaults to `120` (`config.py:268`, `_parse_timeout`, valid
range `0 < t ≤ 600`) while `LLM_MAX_TOKENS` defaults to `2048`
(`config.py:271`, range `1…8192`). At the latency model measured in v1.3
(`21.1 s + 0.093 s/token`, `report-v1.3.md:340`) a 120 s timeout admits about
1 063 completion tokens, so a long completion times out and is **retried with
identical parameters**, re-sending the whole prompt at a cost v1.3 recorded as
unmeasured. This aborted v1.3's first baseline attempt.

Consistency becomes a checked property, not a comment: `load_config` raises
`ConfigError` when
`llm_timeout_s < LATENCY_INTERCEPT_S + LATENCY_PER_TOKEN_S × llm_max_tokens`,
with the two constants named, set to the values above, and cited to the report
line they come from. The operator resolves it by raising `LLM_TIMEOUT_S`
(ceiling 600, so `LLM_MAX_TOKENS ≤ 6224`) or lowering `LLM_MAX_TOKENS`.
`.env.example` ships a pair that satisfies the check; `SUMMARY_MAX_TOKENS = 512`
(`agent.py:45`) is unaffected because it is smaller.

**Benchmark constraint:** `llm_timeout_s` and `llm_max_tokens` are both hashed
into `config_sha256`, and `LLM_MAX_TOKENS` is additionally pinned equal by
`comparability()` (`bench.py:1266-1267`). Both runs of section 10 therefore use
the **same values**, set in `.env` before the baseline and unchanged until
after the last candidate. If the value the check demands exceeds the stage-A
parser's 600 s ceiling, lower `LLM_MAX_TOKENS` instead — do not patch
`69ebc75`.

**REQ-V14-REL-02 (MUST) — lever 6, the starved summary.** The tools-withheld
group has the highest reasoning share of any group (`0.7681` baseline, `0.8291`
candidate, `bench-v1.3.md` `## Reasoning`), so a summary call with
`SUMMARY_MAX_TOKENS = 512` can spend its whole budget thinking and return empty
content with `finish_reason=length` — observed 2 of 2 in v1.3's aborted first
baseline. Two obligations:

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
so "the provider reported nothing" and "the provider reported zero" are
indistinguishable in `/stats` (`bot.py:818`) — unlike `tokens_in`, `tokens_out`
and `cached_tokens`, which are `None`-preserving. `bench.py:1604` handles it
correctly, so no gate depends on it. Record it in the report's known-defects
list with a one-line disposition. Fixing it is permitted **only** if it needs no
change outside `metrics.py` and `tests/`, and is released otherwise: this
release does not expand into `/stats`.

---

## 10. BEN — baseline, candidates, verdict

**REQ-V14-BEN-01 (MUST)** Because `bench_scenarios.py` changes (SCN-03),
`scenarios_sha256` changes, and it is a locked meta field (`bench.py:143`,
hashed from the file's raw bytes at `:173-179`). **Every v1.3 benchmark file is
therefore incomparable with every v1.4 file**, and no v1.4 gate may be computed
against `$0.002687`. The v1.3 figures appear in the report as **informational
context only**, in a clearly labelled row, never as a gate basis.

**REQ-V14-BEN-02 (MUST) — baseline-v1.4.** The baseline is the **stage-A code**
at `69ebc75` (v1.3's pre-optimization tree, `bench-v1.3.md:10`), running the
**v1.4 scenario file** and the **v1.4 benchmark harness**. Not a stylistic
choice: `comparability()` (`bench.py:1268-1277`) requires each stage-C key
(`HISTORY_TOOL_STUB`, `EXEC_OUTPUT_DEFAULT_CHARS`, `FETCH_INLINE_DEFAULT_CHARS`,
`LLM_REASONING`) to be `null` on the baseline side and at its stage-C default on
the candidate side, and only a pre-stage-C tree produces `null`. The consequence
is deliberate and correct: v1.4's candidate is measured against the same
pre-optimization baseline v1.3 used, so the −30 % target is cumulative over
v1.3's −7.3 % plus whatever the reasoning control buys.

1. `git worktree add <abs-path> 69ebc75` — a detached checkout outside the
   working tree, removed when the run ends. **Never commit to it, never amend
   `69ebc75`.**
2. Copy the v1.4 `devtools/bench.py`, `bench_scenarios.py` and `__init__.py`
   into the worktree; nothing else. Its product code (`agent.py`, `llm/`,
   `config.py`, `storage.py`, `tools.py`, `bot.py`) stays exactly as `69ebc75`
   shipped it — that is the treatment being measured. `meta.git_commit` reads
   `69ebc75` and is **not** locked, so the dirty tree costs nothing.
3. `.env` is the repository's own, read by absolute path, with
   `LLM_FAILOVER=off`, `LLM_SUMMARY_MODEL=` empty, and REL-01's
   `LLM_TIMEOUT_S` / `LLM_MAX_TOKENS` pair — identical for the baseline and
   every candidate.
4. **Dry run first (PRE-04).** In the worktree,
   `bench.py run --only S01 --repeats 1 --tag dryrun-base`; in the v1.4 tree,
   the same with `--tag dryrun-cand`; then, from the v1.4 tree,
   `bench.py report --baseline docs/assets/bench/dryrun-base.json --candidate docs/assets/bench/dryrun-cand.json --gate --out /dev/null`.
   Exit 0 or 1 passes (the verdict is meaningless on one scenario); **exit 2 or
   3 is a blocker**. Four LLM calls prove `check_document` and
   `comparability()` accept the pair before an hour of inference is spent.
   Both dry-run files share `--only` and `--repeats`, which are locked. Delete
   `docs/assets/bench/dryrun-*.json` and their `.log` siblings as the last step
   of this item: only `*.log` is git-ignored, so a leftover JSON would be swept
   into a commit by `git add -A` (RPT-08 calls them scratch).
5. The full run, in the worktree:
   `bench.py run --tag baseline-v1.4 --repeats 3 --timeout-s 1800`.

**REQ-V14-BEN-03 (MUST) — the row-key rule that makes step 5 readable.**
`LLM_ROW_KEYS` and `TOOL_ROW_KEYS` are derived at import from the *running*
tree's storage columns (`bench.py:159-160`) and enforced as exact set equality
at `:1087`, so a baseline produced in the stage-A worktree carries stage-A row
keys and is rejected the moment the v1.4 `report` reads it — after the hour is
spent. Replace the equality with
`REQUIRED_LLM_ROW_KEYS ⊆ set(row) ⊆ LLM_ROW_KEYS`, where
`REQUIRED_LLM_ROW_KEYS` is a **literal frozen tuple** spelling out the v1.3
column set — deliberately *not* derived from `storage`, because a derived
minimum drifts forward with every schema change and guards nothing. Apply the
same rule to `TOOL_ROW_KEYS`, or state in the report why not (that schema is
unchanged here, so `REQUIRED == current`). A `v14-*` mutation restores `==` and
MUST be killed by the fixture test.

**REQ-V14-BEN-04 (MUST)** `meta.constants` is locked (`bench.py:143`) and
includes `REQUEST_DEFAULTS` (`llm/base.py:85-89`). The mechanism MUST NOT be
added to `REQUEST_DEFAULTS` or any other constant in `meta.constants`; it is
applied per call, after `build_payload`. Adding it there makes every candidate
incomparable and surfaces only as `locked meta field differs: constants`.
Likewise `summarize()` (`:410`) MUST NOT change: `_validate` recomputes it over
a loaded file's `runs` (`:1206`), so a changed aggregation makes the baseline
unreadable.

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

**REQ-V14-BEN-06 (MUST)** `skipped_scenarios` is locked and is computed from a
live 5-second `HEAD` preflight against `https://wttr.in/` (`bench.py:77-78`,
`:638`) — not from a flag. Both v1.3 runs recorded `[]`, with S08 executed 3/3
(`bench-v1.3.md:17`); v1.4 MUST match. Confirm reachability immediately before
each full run and confirm `[]` afterwards. A run whose preflight failed is
discarded and repeated once, not compared: a skip flip between the two full
runs voids the pair with `locked meta field differs: skipped_scenarios`.
36 runs per side (12 scenarios × 3 repeats).

**REQ-V14-BEN-07 (MUST) — candidate runs, at most two,** in this order:

- **Run A — `LLM_REASONING_POLICY=off`**, tag `cand-off`. Maximum saving. If
  **both** gates pass (BEN-08), stop: `off` is the shipped default and there is
  no run B.
- **Run B — `LLM_REASONING_POLICY=by-purpose`**,
  `LLM_REASONING_ON_PURPOSES=tool-round`, tag `cand-by-purpose`. Run only if A
  failed a gate, and only if the winning mechanism permits a per-round-varying
  policy (POL-05 item 4). Reasoning is kept where the model needs it most —
  choosing which tool to call — and removed from the final answer and the
  summary.

No third run, no parameter sweep, no re-tuning between runs: this is v1.3's
§13.4 "no tuning loop" rule carried forward. If neither passes, RSN-06's STOP
rule applies to the verdict: the report says FAIL with the cause and the
measured figures, and the default stays `model-default`.

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
the winning policy, and this is the **only** change permitted after the last
candidate run. It is safe: both policy fields are excluded from `config_sha256`
(POL-06) and neither is in `LOCKED_META_FIELDS`, so the measured files stay
comparable. Update `.env.example` and `README.md` in the same commit, re-run all
six gates, and state in the report that the default was flipped after
measurement and which figure justified it. If neither candidate passed, the
default stays `model-default` and the knob ships documented as
available-but-not-default.

**Exactly one test may pin that literal** — T-V14-POL-07's default assertion,
modelled on the existing `test_history_tool_stub_defaults_to_on`
(`tests/test_config.py:115`). That test is **named in §12.1 as amendable by
this requirement**, and it is the only exception to EC-03 that BEN-09 creates:
no other test, fake or fixture may assert the policy default, so the flip
touches one literal. No test asserts `.env.example`'s content today; none may
start.

**REQ-V14-BEN-10 (MUST)** Once the baseline exists, `bench_scenarios.py` is
frozen again for the remainder of the release (REQ-V13-BEN-12 re-armed). Any
further scenario change invalidates `baseline-v1.4.json` and is out of scope.

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

All six MUST exit 0 before any task is reported done, at every commit. Gates
1–4 and 6 are unconditional and offline. Gate 5 needs the live environment and
MUST be **fully green including its `lmstudio` check** (PRE-01 item 2). Gate 6
reruns the suite once per mutation and takes minutes; budget for it.

The test count MUST be **greater than 719**; state the exact number. The
mutation count MUST be **at least 71** (65 existing + the six of TST-05); state
the exact number, and correct the stale header comment in
`devtools/mutation_check.py` that says "64 in all" while 65 entries exist.

Benchmark steps (section 10) are **blocking but not gates**: they do not run at
every commit, and a benchmark FAIL is a verdict to report, not a gate to
repair.

---

## 12. Tests

### 12.1 Amendments to existing tests (exhaustive — nothing else may change)

| Test file | Change |
|---|---|
| `tests/test_observability.py` | the `llm_calls` column-set assertions gain the two new columns; the `purpose` `CHECK` assertions are **unchanged** (still exactly `'agent'`/`'summary'` — POL-02) |
| `tests/test_llm.py` | `complete()` signature assertions and fake clients gain POL-04's keyword; its default reproduces v1.3 behaviour |
| `tests/test_failover.py` | the secondary-client fakes accept and record the new keyword (POL-04 site 5) |
| `tests/test_config.py` | the `Config` field-set assertion gains the two policy fields; the `LLM_TIMEOUT_S` / `LLM_MAX_TOKENS` cases gain REL-01's check |
| `tests/test_bench.py` | `meta.env_flags` key-count expectations move from seven to nine; row-key validation tests follow BEN-03 |
| `tests/test_mutation_check.py` | the mutation-count assertion and `test_t_v12_mut_04_every_find_string_occurs_exactly_once_in_the_real_repo` cover the new `v14-*` entries; no change to the gate's own logic |
| `tests/fakes.py` | the fake LLM client accepts the new keyword; no behaviour change when it is absent |
| `tests/test_v14_patch.py` — **T-V14-POL-07's default assertion only** | the one literal BEN-09 is allowed to update when the shipped default is flipped to the winning policy. Nothing else in that file may be touched after T5 |

Nothing else. If another test fails, the production change is wrong.

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
| T-V14-OBS-01 | (OBS-01, OBS-03) the `reasoning_requested` / `reasoning_honored` matrix, one case per row plus the failed-call `NULL` case, and both columns present on the summary call and on a failover attempt |
| T-V14-OBS-02 | (OBS-04) the honored rate, the `n/a` denominator-zero rendering, **and a fixture row shaped like a stage-A row** — the v1.3 column set, neither new column — which must render `n/a` rather than raise |
| T-V14-OBS-03 | (OBS-05) the drift guard: synthetic documents at `0.94` (DRIFT, verdict FAIL even with both gates otherwise green) and `0.96` (no DRIFT); a `model-default` candidate is never marked DRIFT |
| T-V14-REL-01 | (REL-01) the `LLM_TIMEOUT_S` / `LLM_MAX_TOKENS` boundary in both directions; the error text names both variables |
| T-V14-REL-02 | (REL-02 item 1) `summary` resolves to `"off"` under `off` and under `by-purpose`; `load_config` rejects `summary` in `LLM_REASONING_ON_PURPOSES` |
| T-V14-REL-03 | (REL-02 item 2) the `FINISH-LENGTH:` assertion — a candidate document with one `summary` + `length` row fails; one without does not; a baseline document with such a row does not |
| T-V14-BEN-01 | (BEN-03) the row-key rule — a v1.3-shaped fixture row validates, a row missing a required key is rejected naming it, a row with an unknown key is rejected |
| T-V14-BEN-02 | (BEN-05) `meta.env_flags` holds nine keys; a stage-A-shaped `Config` (both policy fields absent) yields `null` for both |
| T-V14-BEN-03 | (BEN-04) `meta.constants` is byte-equal between a `model-default` run and an `off` run, and `summarize()`'s output is unchanged for a v1.3-shaped document |
| T-V14-SCN-01 | (SCN-03) the repaired S01 check passes on each of the three recorded v1.3 candidate answers **and** on the baseline's passing answers, and still fails on an off-topic or refusing answer. Answers are inlined as literals, never read from a benchmark file |

**REQ-V14-TST-01 (MUST)** Offline discipline is unchanged: no new test touches
the network, DNS or a real Docker daemon; `tests/conftest.py`'s guards stay in
force; every LLM interaction in `pytest` is faked.

**REQ-V14-TST-02 (MUST)** Every asserted value comes from this spec or an
independent literal, never imported or re-derived from the implementation under
test. For each new test the reviewer's standing question — *which test fails if
this line changes?* — has a mechanical answer in gate 6. The rule lives in
`.claude/agents/code-reviewer.md:22-26` and `standards/workflow.md:73-79`; it is
quoted here because it is the highest-value review target in a release whose
new logic is almost entirely branch selection.

**REQ-V14-TST-03 (MUST)** The three-value reasoning-purpose set and the
three-value policy set are each defined once and imported by the tests from
that single definition, while the **expected mappings** are written out as
literals. A test that builds its expectation from the function it is testing
proves nothing.

**REQ-V14-TST-04 (MUST)** No test asserts a live provider's behaviour. Whether
LM Studio honours the mechanism is established by the spike (section 5) and
re-confirmed by the benchmark's honored rate (OBS-04) — never by `pytest`,
which would make the suite depend on a host outside the repository.

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
the live bot, plus spec-v1.2's scenarios D1 and D3 as a regression check that
this patch did not weaken the security posture. Record pass or fail per
scenario and — per REQ-V12-REP-02, still in force — **how** each was driven (a
real Telegram message from the operator's account, or a script standing in for
one). "Driven by a script" is an acceptable answer; leaving it unsaid is not.

**REQ-V14-REV-01 (MUST)** Code review by the `code-reviewer` subagent in a
clean context, after the gates pass and before the final report. Findings are
fixed, or explicitly waived with a reason in the report. The review prompt is
its own numbered file in `docs/prompts/`. The reviewer MUST report any
policy-selection or verdict-affecting line with **no** mutation entry; such a
line is a finding, not an observation.

**REQ-V14-RPT-01 (MUST)** `docs/reports/report-v1.4.md`, per
`standards/reporting.md` § "Run report" and `AGENTS.md` § Reporting — including
that standard's own field list (spec size in tokens and the counting tool;
worked-first-try; prompt count and auxiliary-prompt quality; bugs fixed/left;
tokens in/out, cost, wall-clock; models, harness and self-imposed constraints
with the **executor model always named**; terminal capture in `docs/assets/`;
links to spec, prompts and commits) — plus:

1. **Verdict against `B_v1.4`** — `B_plain`, `C_plain`, `C_conservative`, the
   threshold, both gate outcomes, the honored rate, and any `DRIFT:` or
   `FINISH-LENGTH:` line. The v1.3 figures `$0.002687` / `$0.002492` appear in
   a separate, explicitly **informational** row with one sentence saying why
   they are not the gate basis (BEN-01).
2. **The mechanism table** of RSN-04, with the LM Studio version.
3. **The S01 root cause** — hypothesis chosen, the evidence, the check diff if
   H1, the `temperature: 0` observation.
4. **Errata to earlier reports** (RPT-04).
5. Gates table with all six commands and the exact test count; the
   mutation-gate summary line, mutation count and wall-clock.
6. Appendix-B results with how each was driven; deviations, process ones
   included; fix cycles.
7. Known defects carried forward, incl. REL-03 and the accepted risks v1.2 and
   v1.3 already list.

**REQ-V14-RPT-02 (MUST)** There is **no** cumulative v1 → v1.4 section. v1.3's
report carried one (RPT-07) and it is not repeated: this report covers this
release, and the cross-version view lives in `economics.md` and `docs/plan.md`.

**REQ-V14-RPT-03 (MUST)** `docs/reports/tg-post-v1.4.md`, Russian, structure
`constraints → result → metrics → links`, **strictly under 1500 characters by
`wc -m`** (state the measured count in the report), naming the executor model
and linking `https://github.com/axyi/tg-agent-bot`. Version matches the report
(`report-v1.4` → `tg-post-v1.4`); regenerating replaces the file, never bumps
the version.

**REQ-V14-RPT-04 (MUST) — Errata to earlier reports.** A section of
`report-v1.4.md` with exactly these two entries, and no edit to any earlier
report or to `docs/llm-usage.md` rows 1…31, which stay **byte-unchanged**:

- **E1 — the v1.2 cost, row 27 of `docs/llm-usage.md` (line 34).** The row says
  tokens were "not computed" and the cost `≈$33.11`. The figure has since been
  reproduced exactly, as two concurrent `claude-sonnet-5` sessions: `49c2d3e6…`
  (2026-09-01T20:06–22:12Z, spec `7ab107a`) `$16.50` and `c32c1cd8…`
  (21:45–23:28Z, implementation `d83a49e` + report `55d7ea0`) `$16.61`, under
  the ledger formula (`$2`/`$10` per Mtok, cache write ×1.25, cache read ×0.1).
  Combined tokens: **1 078** uncached input, **1 069 639** cache write,
  **129 807 141** cache read, **447 003** output. `economics.md` already carries
  the reconciled figures (`130.88M / 447.0k`,
  `≈$33.11 ($16.50 spec + $16.61 impl)`); this erratum records that the
  project-level row is stale, not wrong, and says where the split lives.
- **E2 — the v1.3 prompt count.** `report-v1.3.md:14` ("19 prompt files 09–27")
  and `docs/llm-usage.md` row 31 (line 39, "18 of 19") are stale: the v1.3 `go`
  run logged **21** prompt files, `09-go-spec-v1.3.md` through
  `29-v13-TD2-tg-post.md` — 28 is the TD1 report prompt and 29 the TD2
  Telegram-post prompt, both stage D of the same run. Row 32 (line 41) already
  says 21, and `economics.md` already says "21 (+1 post-verify docs fix)". Row
  31 is **not** edited: the corrected count lives here and in row 32.

**REQ-V14-RPT-05 (MUST)** `docs/llm-usage.md` gains rows starting at **33**,
appended after the current last data row (line 41), in the file's own
five-column shape (`| # | Stage | Model | Tokens | Cost |` — the project
collapsed the standard's separate in/out columns long ago; do not reshape the
table here). Every row names the executor model. Where the harness does not
expose counters, keep that note and add an estimate at public API prices,
marked as an estimate with its price source. Append the project's row to
lab-root `economics.md` after the report is written.

**REQ-V14-RPT-06 (MUST)** Documentation, in the same commit as the behaviour it
describes (`AGENTS.md`'s spec-drift rule): (1) `.env.example` —
`LLM_REASONING_POLICY` and `LLM_REASONING_ON_PURPOSES` with their shipped
defaults and a one-line comment each, beside the other `LLM_*` variables, and
no third variable; (2) `README.md` § "Configure" and § "Token economy" — what
the policy does, the three reasoning-purpose tags, which mechanism the running
LM Studio honours (with its version), the measured saving, and the honest
caveat that the mechanism is model- and runtime-specific, while § "Observability"
→ "What is recorded" gains the two new columns and § "Benchmark" gains the
baseline-v1.4 procedure in one paragraph; (3) no `LLM_REASONING` line anywhere
(AMEND-01).

**REQ-V14-RPT-07 (MUST)** `docs/plan.md`: the status-table row for
`docs/spec/spec-v1.4.md`, and the § "v1.4 (next) — candidates, none applied"
section replaced by the delivered outcome plus the candidates that remain
untried (O6 routing, tokenizer-accurate budgets, streaming, semantic cache, and
levers 3, 4 and 7 of `report-v1.3.md`). Numbers come from `bench-v1.4.md`, not
from v1.3.

**REQ-V14-RPT-08 (MUST)** Committed benchmark artefacts:
`docs/assets/bench/baseline-v1.4.json`, `cand-*.json`, the `rsn-<letter>` probe
files, `s01-repro` and `s01-verify`, their `.log` siblings, and the rendered
`bench-v1.4.md`, `bench-rsn-<letter>.md`, `bench-s01-repro.md`,
`bench-s01-verify.md`. The dry-run files of BEN-02 item 4 are scratch and are
not committed.

---

## 14. Implementation order and per-task acceptance

**REQ-V14-ORD-01 (MUST)** Follow this order. Each task is one prompt, one
commit, and ends with gates 1–4 green before the next begins; gates 5 and 6 run
at every commit touching production code. Task ids are distinct from prompt
numbers and benchmark tags.

| id | task (owned files) | returns (acceptance) |
|---|---|---|
| T0 | Preconditions (PRE-01…05): six gates on the untouched tree, credential presence by name, Docker, LM Studio **version recorded**, worktree availability, vendor doc citations | the six exit codes, the LM Studio version string, the two doc citations, `git worktree add` dry-checked and removed |
| T1 | S01 root cause (`devtools/bench_scenarios.py`, `s01-*` artefacts) — SCN-01…04 | H1 or H2 with the named evidence incl. the system-prompt inspection and the `temperature: 0` note; the check diff if H1; `s01-verify` at 3/3 |
| T2 | Harness readiness (`devtools/bench.py`, `tests/test_bench.py`) — BEN-03, BEN-04, BEN-05 and BEN-02 item 4 | the row-key rule with its fixture tests; nine `env_flags` keys; the dry-run `report --gate` exit code (0 or 1, never 2/3) |
| T3 | Baseline-v1.4 (worktree at `69ebc75`, `baseline-v1.4.*`) — BEN-02, BEN-06 | the `meta` block quoted (locked fields, `skipped_scenarios: []`, `config_sha256`), 36 runs, `B_plain`, wall-clock, worktree removed |
| T4 | RSN spike (`llm/base.py`, `llm/lmstudio.py`, probe artefacts) — RSN-01…06 | the candidate table with LM Studio version and per-candidate evidence; PASS with the winning letter, or the STOP rule invoked |
| T5 | Policy + observability (`config.py`, `llm/*`, `agent.py`, `storage.py`, `devtools/bench.py`, `tests/test_v14_patch.py`) — sections 6 and 7 | tests added and passing incl. the failover-secondary and prefix-integrity tests; the CCH-02 branch of POL-05 item 4 stated |
| T6 | Reliability (`config.py`, `agent.py`, `devtools/bench.py`, tests) — REL-01…03 | the boundary tests; the `FINISH-LENGTH:` assertion; REL-03's disposition |
| T7 | Candidate run(s) (`cand-*.*`, `docs/reports/bench-v1.4.md`) — BEN-07, BEN-08 | per run: `C_plain`, `C_conservative`, threshold, both gate outcomes, honored rate, `report --gate` exit code; the winning tag or "neither" |
| T8 | Mutations + review (`devtools/mutation_check.py`, review prompt) — TST-05, REV-01 | the mutation count and gate-6 summary line; the review's findings with fixes or waivers |
| T9 | Report, post, errata, docs (`report-v1.4.md`, `tg-post-v1.4.md`, `docs/llm-usage.md`, `docs/plan.md`, `README.md`, `.env.example`, `economics.md`) — section 13, BEN-09 | `wc -m` of the post; the errata section; the ledger row; the default flip with the figure that justified it and the six gates re-run green |

T1 precedes T3 because the baseline must measure the repaired scenario file. T2
precedes T3 because a baseline the report reader cannot load is an hour lost.
T4 precedes T5 because there is nothing to configure until a mechanism is known
— and if T4 ends in the STOP rule, T5, T7 and the policy half of T6 are
declared not-executed rather than half-built.

---

## 15. Non-goals for v1.4

Implementing any of these is a defect.

| ID | NON-GOAL | why |
|---|---|---|
| REQ-V14-NG-01 | Enabling O6 routing (`LLM_SUMMARY_MODEL`) or benchmarking a second model | two models do not fit in the maintainer's GPU box at once; measured ceiling −4.6 % |
| REQ-V14-NG-02 | Tuning `CONTEXT_WINDOW_MESSAGES`, `EXEC_OUTPUT_DEFAULT_CHARS`, `FETCH_INLINE_DEFAULT_CHARS` | ≈0 on this scenario set, or a direct trade against the quality gate that already failed |
| REQ-V14-NG-03 | Tokenizer-accurate context budgets, streaming, semantic cache | each needs a dependency or a redesign; the dependency list forbids the first, and none is a token saving |
| REQ-V14-NG-04 | Changing any scenario's `id`, `title` or `turns`, or any check other than S01's | the scenario set is the measuring instrument; changing it twice invalidates baseline-v1.4 |
| REQ-V14-NG-05 | A `purpose` column migration, a third database value, or any storage change beyond OBS-01's two columns | the reasoning-purpose tag is derived at request time and needs no persistence beyond `reasoning_requested` |
| REQ-V14-NG-06 | Editing `report-v1.2.md`, `report-v1.3.md` or `docs/llm-usage.md` rows 1…31 | the two errata are stale, not false; the correction belongs in the new report |
| REQ-V14-NG-07 | An OpenRouter benchmark beyond POL-07's two-call smoke | it costs real money and measures a provider this project does not run on |
| REQ-V14-NG-08 | A third new environment variable, a new module, a new dependency, or refactoring not required above | patch-release discipline |

---

## 16. Decisions taken and alternatives refused

Start here when challenging the design, rather than re-deriving it.

| decision | alternative refused | reason |
|---|---|---|
| A three-valued policy (`model-default`/`off`/`by-purpose`) | ship `off` only, as a boolean | reasoning is worth paying for where the model chooses tools; a boolean cannot express that, and the `by-purpose` run is the fallback that saves the release if `off` costs quality |
| Re-baseline against stage A (`69ebc75`) | keep the v1.3 baseline, compare against `$0.002687` | mechanically impossible: S01's check change moves `scenarios_sha256`, a locked field, so `report --gate` exits 2 before measuring. Also right on the merits — the v1.4 candidate carries v1.3's optimizations, so the honest denominator is the pre-optimization tree |
| Derive a reasoning-purpose tag from request-time state | reuse the database `purpose` column as the policy axis | `purpose` has two values under a SQLite `CHECK`, and both the tool-selection and the final-answer call are `'agent'`; using it would make `by-purpose` indistinguishable from `off` on the one axis that matters, and changing the `CHECK` is a migration |
| Five mechanisms in a fixed order, first pass wins | pick the one that "should" work from the documentation | v1.3 did exactly that and lost the release to it; the documentation said nothing about Qwen3 then and says nothing now |
| A STOP rule with a negative-result report | tune until something passes | a saving the measurement does not support is worse than a FAIL: the FAIL is recoverable, the false PASS is not |
| Record both errata in the new report | edit row 27 / row 31 and `report-v1.3.md` in place | v1.2 rewrote a shipped report because a line was **false**; these lines are **stale**, superseded by later rows and by the ledger, and rewriting them would destroy the audit trail showing when the better figure arrived |
| Reject spike candidate **c** outright | ship it if the probe happens to pass | an appended prefill cannot satisfy REQ-V13-CCH-02(a) under any policy; it trades a measured saving for an unmeasured prefix-cache cost |
| Two new environment variables | one combined variable, or per-purpose booleans | a combined string needs a parser and a grammar; three per-purpose booleans is three variables |

---

## Appendix A — traceability

### A.1 Problems → requirements

| Problem | Requirements | Verified by |
|---|---|---|
| P1 reach the −30 % cost gate with quality green | RSN-01…06, POL-01…07, OBS-01…05, REL-01…03, BEN-01…10 | `bench-v1.4.md` `## Verdict`; `bench.py report --gate` exit code; `## Reasoning` honored rate |
| P2 v1.2 cost erratum | RPT-04 (E1) | the errata section of `report-v1.4.md`; `git diff` shows `docs/llm-usage.md` rows ≤ 31 unchanged |
| P3 v1.3 prompt-count erratum | RPT-04 (E2) | the errata section; `ls docs/prompts/09-*..29-*` counts 21 |

### A.2 v1.3 levers → disposition

Lever 1 (a reasoning switch LM Studio honours) → **taken**, sections 5–6.
Levers 5 (`LLM_TIMEOUT_S`/`LLM_MAX_TOKENS` mismatch) and 6 (summary starved by
reasoning) → **taken**, REL-01 and REL-02. Lever 2 (O6 routing) → NG-01. Levers
3, 4 and 7 (`CONTEXT_WINDOW_MESSAGES`, `EXEC_OUTPUT_DEFAULT_CHARS`,
`FETCH_INLINE_DEFAULT_CHARS`) → NG-02. Source: `report-v1.3.md:326-350`.

### A.3 Mechanical hazards in the harness → requirements

`LLM_ROW_KEYS` derived from the running tree (`bench.py:159`, `:1087`) →
BEN-03; `meta.env_flags` fixed at seven keys (`:1031`) → BEN-05;
`config_sha256` locked and hashing every non-excluded `Config` field
(`:132-143`, `:191-204`) → POL-06; `meta.constants` locked and carrying
`REQUEST_DEFAULTS` (`:143`, `llm/base.py:85-89`) → BEN-04; `summarize()`
recomputed on load (`:1206`) → BEN-04; `skipped_scenarios` locked and set by a
live preflight (`:77-78`, `:638`) → BEN-06; `comparability()`'s stage-C pin
(`:1268-1277`) → BEN-02; the five `complete()` sites → POL-04;
REQ-V13-CCH-02(a) versus in-message mechanisms → POL-05.

---

## Appendix B — acceptance scenarios (Gherkin, written before code)

```gherkin
# SAFETY RULE FOR EVERY SCENARIO BELOW: never use a live credential as a test
# value, and never print one. Scenarios exercising configuration use the
# synthetic-canary pattern of spec-v1.2 Appendix B; the real .env is restored
# afterwards.

Feature: reasoning control that the runtime actually honours

  Scenario: E1 — the policy is off and the model stops thinking
    Given LLM_REASONING_POLICY is off
    And the winning mechanism of the spike is in place
    When the operator asks a question that needs one tool round
    Then the answer is correct
    And every llm_calls row of that turn has reasoning_requested = 'off'
    And every one of them has reasoning_tokens 0 and reasoning_chars 0
    And every one of them has reasoning_honored = 1

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
    Given LLM_TIMEOUT_S is 120 and LLM_MAX_TOKENS is 2048
    When the bot starts
    Then it exits with a configuration error naming both variables
    And it starts normally once either value is brought into range

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

  Scenario: E8 — S01 measures capability, not phrasing
    Given the repaired S01 check
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
    When they are scanned for the synthetic canary and for the real key values
    Then no benchmark JSON, log, report, prompt file or spec contains one
    And the bench file's Telegram id is the redacted placeholder
```
