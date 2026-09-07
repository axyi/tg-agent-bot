# tg-agent-bot — implementation specification v1.7.0 (reasoning policy, a summary wall-clock budget and the cost gate)

Complete contract for a **minor release** on the implemented v1.6.0 state
(`main` at `89786ef`, tag `v1.6.0` on `0d33af4`). It is a **delta
specification**: spec-v0 … spec-v1.6.0 remain in force except where a
requirement here explicitly **amends**, **supersedes** or **extends** them (§2
is the authoritative amendment table). Mechanisms already shipped are cited by
`REQ` id and `file:line` and are **never restated**; where this spec and an
earlier one disagree, this one wins for the requirement it names and nowhere
else.

Every requirement has a stable `REQ-V170-*` id and is tagged `MUST` or
`NON-GOAL`; v1.7.0 ids never collide with v0…v1.6.0 ids. `MUST` = required for
acceptance; `NON-GOAL` = out of scope, and implementing it is a defect.
Requirement groups: **EC** (execution contract), **AMEND**, **PRE**, **TREE**,
**RSN** (stage A — the mechanism spike), **POL** (stage B — the policy), **OBS**
(what the policy records), **SUM** (the summary wall-clock budget), **BEN**
(stage C — candidates, comparability and the gates), **CAR** (carried items),
**VER**, **RPT**, **GATE**, **TST**, **ACC**, **REV**, **ORD**, **NG**.

Target platform: **Linux only**. Language **Python 3.14**, package manager
**uv**.

Executor: **claude-sonnet-5**. Reviewer: **sonnet in a clean context**. A larger
model is not needed: every env var, enum value, column name, function
signature, candidate payload shape, gate formula and test id is written out
below.

**What this release is.** Four things and nothing else:

1. a **reasoning policy per call purpose** — the mechanism found by stage A,
   applied by the policy of stage B (§5, §6);
2. a **wall-clock budget for the whole summary path**, so the S15/S18 family
   cannot spend `LLM_TIMEOUT_S` twice (§8);
3. a **cost gate of −30 %** against `docs/assets/bench/baseline-v1.6.0.json`
   with the quality gate green and **S13…S18 each back at a blocking 3/3**, S15
   and S18 included (§9);
4. the **carried items** of v1.6.0 (§10).

Nothing else may change bot behaviour (REQ-V170-EC-06).

**Provenance**, cited where used: v1.4's `RSN-06 STOP` — the spike design of
`docs/spec/spec-v1.4.md` §5–§7 and §10 is reused **verbatim in vocabulary**, and
its measurements (`docs/reports/report-v1.4.md:213-303`) are the prior, taken on
LM Studio **0.4.23** and therefore not binding on Bionic 1.1.x; v1.6.0's errata
2, 3, 5 and 6, which named the reasoning budget of `qwen/qwen3.8-27b` as this
release's subject and deferred S15 and S18 here; `baseline-v1.6.0.json` (54
runs, 53 successes, 93 m 16 s, $0.185776, recorded at `ca9c656`); and the three
**dormant** `env_flags` keys already carved into `devtools/bench.py:117,121,122`.
Appendix A maps every requirement to source and verifying artefact.

---

## 1. Execution contract

**REQ-V170-EC-01 (MUST)** Section 1 of every earlier spec applies unchanged,
with these adjustments:

- "the gate commands" means §13's set — the six of `AGENTS.md` plus the
  `config/quality_gates.yaml` profiles, with one gate added
  (REQ-V170-GATE-02);
- the repair budget is **5 total** repair-and-rerun cycles (one cycle = one fix
  + a complete run of all gates from the first); exhausted → stop and report;
- **no project or lab file outside the repository root may be read or written.**
  The only permitted external effects are the LM Studio
  discovery/preflight/TTFT traffic, PRE-03's read-only HTTPS requests to the
  named LM Studio and OpenRouter documentation sources, stage A and stage C
  inference traffic, S17's `wttr.in` fetch, and tool-owned caches. The list is
  **exhaustive**, and PRE-03's documentation reads are inside it precisely
  because they are not LM Studio inference traffic and the round-2 allowlist
  therefore forbade the very reads PRE-03 mandates. The lab ledger
  `economics.md` lives
  above the root: the operator writes it, never the executor
  (REQ-V170-RPT-01);
- the **runtime** dependency set is unchanged and MUST stay so: `httpx`,
  `python-dotenv`, and the `docker` CLI as a host dependency. **Zero new Python
  dependencies** (REQ-V170-NG-06). The **developer** tool set of v1.5/v1.6.0
  (ruff, gitleaks, semgrep, trivy, skylos, rtk, pytest) is unchanged and no pin
  moves.

**REQ-V170-EC-02 (MUST)** Test-first: write §14's tests, watch them fail for the
right reason, then implement in §16's order. Every `MUST` in §§5–12 has a named
unit test, a negative test, a Gherkin scenario in Appendix B, or a recorded
artefact; Appendix A is the map and is complete. The high-risk mechanisms of
§14.4 additionally require mutation proof through `devtools/mutation_check.py`.

**REQ-V170-EC-03 (MUST)** The v1.6.0 suite is **1016 collected tests**
(`uv run --locked pytest --collect-only -q`, measured 2026-09-06 at `89786ef`).
`AGENTS.md:103` still says **1004**, the count as of v1.6.0's T12; it is stale
and REQ-V170-RPT-04 corrects it. The executor **re-measures at HEAD** at T0 and
records the number; if it differs, the measured number is the floor. No test may
be deleted; tests may be modified **only** where §14.1 lists them, and that list
is exhaustive. A change making an unlisted test fail means the change is wrong —
stop and reconsider, do not edit the test.

**REQ-V170-EC-04 (MUST) — secrets discipline, and the four permitted `.env`
machine reads.** REQ-V160-EC-04 applies verbatim: credential **values** are
never printed, logged, committed or quoted in `docs/`; presence checks are by
key **name** only; tests use the synthetic sentinel pattern; `data/`,
`sandbox/`, `*.db` and `exec_audit.jsonl` are never opened, printed or quoted by
any task of this run.

`.env` contents and values are never emitted — not printed, logged, `cat`-ed,
diffed, quoted or pasted into any file. **Four** machine reads are permitted,
each yielding only an exit status or an in-process value:

1. `grep -q '^KEY=' .env` — named-key presence **or, on a non-zero status,
   proved absence**: REQ-V170-PRE-01 item 9 uses exactly this idiom, and no
   other, to prove that `LLM_REASONING_POLICY` and `LLM_REASONING_ON_PURPOSES`
   are **not** in the file;
2. `grep -q '^KEY=<expected>$' .env` — **value confirmation without
   disclosure**, used by REQ-V170-PRE-04 to prove the instrument's
   `LLM_MAX_TOKENS=4096` and `LLM_TIMEOUT_S=600` without printing either;
3. `python-dotenv` loading by the bot and the bench commands;
4. PRE-03's `sed -i 's|^LMSTUDIO_BASE_URL=.*|LMSTUDIO_BASE_URL=<url>|' .env`
   followed by the confirming `grep -q` of read 2.

Idiom 4's `sed -i` is permitted for the `LMSTUDIO_BASE_URL` line **and for no
other key**: a policy key found present at T0 is reported as a blocker by name
(REQ-V170-PRE-01 item 9) — never rewritten, never deleted, never disclosed.

Any other read, by the executor or a subagent, is a defect, and **no backup copy
may be made**: a `.env.bak*` file is itself a secrets-discipline defect. **No
new key is ever written into `.env`** — REQ-V170-POL-01's two variables are
documented in `.env.example` with their defaults, which apply when the keys are
absent (REQ-V170-EC-05). Stage A and stage C set the treatment by a
**process-environment prefix on the command** (REQ-V170-BEN-04); `load_config`
reads `os.environ` after `dotenv.load_dotenv(..., override=False)`
(`config.py:202-203`), so the prefix wins by construction and nothing is edited.

**REQ-V170-EC-05 (MUST)** Backward compatibility as in REQ-V1-EC-05: every new
parameter, config field, environment variable and helper defaults to **current
behaviour** when absent, so unlisted tests and fakes keep passing. In particular
`LLM_REASONING_POLICY` defaults to `model-default`, which sends a byte-identical
request to today's (REQ-V170-POL-03), and the summary budget of §8 is inert
until a request would actually exceed it.

**The reasoning defaults are a compatibility default with an expiry, and
REQ-V170-POL-07 is what expires it.** *"Until T12, the implementation default is
`model-default`, preserving v1.6.0 behavior for stage-C measurement. When T12 is
permitted, REQ-V170-POL-07 explicitly supersedes this compatibility default and
changes the absent-value defaults to the selected treatment."* The two
requirements are therefore **ordered, not contradictory**: this one binds every
commit up to and including T11, so stage C measures v1.6.0's behaviour from an
unprefixed tree, and POL-07 binds the single post-measurement selection commit
and everything after it. An executor reading both has one rule, not two, and
the round-2 spec's unqualified "defaults to current behaviour" no longer
licenses ignoring POL-07.

**REQ-V170-EC-06 (MUST) — this release is benchmark-affecting, and it
*satisfies* the `AGENTS.md` before/after rule rather than superseding it.**
`AGENTS.md:149-155` requires a behaviour change touching tokens to be
accompanied by a benchmark run **before and after**, compared with `report
--candidate`. That is exactly what §9 does: `baseline-v1.6.0.json` is the
"before", each candidate of REQ-V170-BEN-05 is an "after", and REQ-V170-BEN-07
compares them with `report --gate`. **The report states that the rule is
satisfied**, names the pair and quotes the verdict — the opposite of
REQ-V160-EC-06, which declared it superseded because no comparable "before"
existed. Copying that supersession wording here would be a defect.

Two behaviour changes are declared **before** implementation:

1. **REQ-V170-POL-04**, the per-purpose reasoning field on the request body —
   the treatment the gate measures;
2. **REQ-V170-SUM-02/-03**, the shared summary budget and the skipped retry —
   token-affecting (a skipped retry spends nothing) but **prompt-neutral**: no
   message, system prompt or tool schema changes, so
   `meta.prompt_tools_sha256` is byte-identical and the pair stays comparable.

If a *further* benchmark-affecting change is proposed or discovered: (1) stop
the task that proposed it; (2) record it and its trigger in the report under
"Benchmark-affecting changes"; (3) either drop it and hand it to v1.8.0, or fold
it in **before** the first candidate run (T11). Recording a candidate and *then*
changing behaviour voids it.

**REQ-V170-EC-07 (MUST) — the RLM execution rule.** REQ-V160-EC-07 applies
verbatim: a task exceeding **one** of these thresholds is delegated to a
subagent — more than one file or folder **to explore beyond the files and line
ranges the task's own reading map names**; a single read over **100 lines** or
**8 KB**; more than **10 edits** to one file in a task; applying a review or
critique to a spec. The subagent gets a **≤ 5-line brief** with no history and
MUST return a **summary only**, never a raw file dump. In the main context reads
use `Read` with `offset`/`limit` or `grep`/`find` with line context — never a
whole-file read, never a directory walk. §13.1's map is authoritative for the
file-count threshold; the report records **per task** whether the executor
delegated and to what.

**REQ-V170-EC-08 (MUST)** Every prompt file carries the seven-bullet header
(`Date`, `Executor model`, `Model reason`, `Harness`, `Stage`, `Owner of`,
`REQ ids`) then exactly four level-2 blocks in order — `## Goal`,
`## Constraints`, `## Acceptance`, `## Stop` — per REQ-V15-PRM-01 and
`docs/prompts/TEMPLATE.md`, unchanged by this release. `checks.py lint-docs`
enforces it in the `full` profile, but only once REQ-V170-RPT-02 has repointed
its `report_path`.

**REQ-V170-EC-09 (MUST) — `--no-verify` stays forbidden, and one prompt is one
commit.** REQ-V15-EC-09 and REQ-V160-EC-10 apply unchanged: no commit or push in
this run may use `git commit --no-verify`, `git push --no-verify`, `-n`, or any
other bypass (environment switches, a temporary `core.hooksPath` change, `git
config --unset`, deleting and restoring a hook). The report MUST contain the
sentence *"No commit or push in this run used `--no-verify` or any other hook
bypass."* — and MUST omit it, with an explanation, if that is untrue.
`devtools/checks.py replay --range <base>..<implementation-tip>` supplies the
evidence; the two historical exceptions v1.5.1 documented are expected to
persist. Each task of §16 is one prompt file under `docs/prompts/` and one
commit whose body carries `(prompt: docs/prompts/NN-….md)`. The installed
`.githooks/` chain is live from the first commit of this run;
`devtools/install_hooks.py --check` must exit 0 at T0. A whole-spec solo run may
commit to `main`, where the branch-name gate is warn-only.

---

## 2. Amendments to spec-v0 … spec-v1.6.0 — authoritative table

**REQ-V170-AMEND-01 (MUST)** Apply exactly these; unlisted requirements stay in
force verbatim.

| id | Status | Change |
|---|---|---|
| `llm.base.LLMClient.complete` (llm/base.py:67-73) | extended | gains **two** keyword-only parameters, `reasoning: ReasoningRequest = REASONING_DEFAULT` (REQ-V170-POL-04) and, second, `timeout_s: float \| None = None` (REQ-V170-SUM-03); both default to today's behaviour |
| `llm.base.ReasoningMechanism`, `llm.base.ReasoningRequest`, `llm.base.REASONING_MECHANISMS`, `llm.base.REASONING_DEFAULT` | new | two frozen dataclasses over an **immutable recursive JSON** representation (`FrozenJSON`: tuples of key/value tuples, never a `dict`), the per-purpose table stage A fills — **keyed by tag and holding off mechanisms only** — and the neutral request object every existing caller keeps sending (REQ-V170-POL-03). `MappingProxyType` comes from the stdlib `types` module — no new dependency (REQ-V170-NG-06) |
| `llm/lmstudio.py:35`, `llm/openrouter.py:72`, `llm/failover.py:50`, `bot.py:1071` (`_SelftestLLM`) `complete`; `llm/failover.py:73` `_try_other` | extended | the same two parameters, forwarded at the **five** invocation sites `llm/failover.py:60`, `:83`, `agent.py:335`, `agent.py:1094`, `devtools/bench.py:2186`. `_try_other` carries the `ReasoningRequest` positionally, exactly as it already carries `max_tokens`. The last site is the bench warm-up probe (`max_tokens=1`) and passes the defaults explicitly (REQ-V170-POL-04) |
| `llm.base.build_payload` (llm/base.py:112-129) | extended | gains keyword-only `reasoning_fields: dict \| None = None`, merged into the payload **after** the existing keys and **only** when not `None`; the `tools`/`tool_choice` branch is untouched |
| `llm.base.REQUEST_DEFAULTS` (llm/base.py:85-89) | unchanged | stays exactly `{"temperature": 0, "stream": False, "tool_choice": "auto"}`. It is embedded verbatim in `meta.constants`, which is a **locked** meta field (`devtools/bench.py:151`), and `tests/test_v14_patch.py:89-92` asserts no `reasoning` key in either. Adding one voids every baseline **and** fails gate 3 (REQ-V170-NG-05) |
| `bench.constants()` (devtools/bench.py:278) | unchanged | same reason; the summary-budget floor of REQ-V170-SUM-02 is an `agent.py` module constant and is deliberately **not** added here |
| `bench.ENV_FLAG_FIELDS` (devtools/bench.py:113-123) | clarified | already carries `LLM_REASONING_POLICY` and `LLM_REASONING_ON_PURPOSES`; both become **live** once REQ-V170-POL-01's `Config` fields exist, with no edit to this dict. The comment at `:109-112` says "the last two" are dormant; **three** are (`LLM_REASONING` never gained a field either) and the comment is corrected in the same commit |
| `bench.CONFIG_HASH_EXCLUDED` (devtools/bench.py:140-147) | extended | gains `llm_reasoning_policy` and `llm_reasoning_on_purposes`, beside `llm_reasoning`, with a comment naming REQ-V170-BEN-02. `config_sha256` is locked; without this every candidate is non-comparable |
| `bench.comparability` stage-C clause (devtools/bench.py:1451-1460) | **superseded** | the rule "`env_flags.<STAGE_C_KEY>` must be null on the baseline side" was written for v1.3's four-commit stage-C contract and makes **`baseline-v1.6.0.json` non-comparable with itself** (measured: it returns `env_flags.HISTORY_TOOL_STUB must be null on the baseline side`). Replaced by REQ-V170-BEN-02's equality rule |
| `bench.LOCKED_META_FIELDS` (devtools/bench.py:149-163) | unchanged | all sixteen entries stay; `env_flags` is **not** among them, which is what lets a treatment-only pair compare (REQ-V170-BEN-02) |
| `bench._generation_settings` (devtools/bench.py:2262-2275) | unchanged | stays the sampling literal and stays locked. The reasoning mechanism is recorded in the **new, unlocked** `meta.reasoning` block (REQ-V170-BEN-03) |
| `devtools/bench_scenarios.py` | **frozen** | `meta.scenarios_sha256` is locked and the baseline pins `f2b6c41c…1972`. Not one byte of this file changes — no new scenario, no ceiling moved, no turn edited (REQ-V170-NG-01) |
| REQ-V160 errata 3 and 6 (S15 / S18 non-blocking) | **superseded** | S15 and S18 re-enter the blocking 3/3 through REQ-V170-BEN-06's **executable** rule. The exemption never lived in code — verified by exhaustive grep of `devtools/` and `tests/`, whose only S15/S18 mentions are the catalogue itself and `tests/test_v160_bench.py`'s id/ceiling assertions — so nothing is *removed*; the re-entry is *added*, as the module constant `GATE_REQUIRED_FULL_SCENARIOS` and the `report --gate` check that reads it. `devtools/bench_scenarios.py` still does not change |
| `storage.SCHEMA_VERSION = 4` (storage.py:18) | amended | → `5`; `_MIGRATION_4_TO_5` added and chained after `_MIGRATION_2_TO_4` / `_MIGRATION_3_TO_4`; the accepted tuple at `storage.py:289` becomes `(1, 2, 3, 4, SCHEMA_VERSION)` (REQ-V170-OBS-01) |
| REQ-V13-OBS-03 / REQ-V160-TRC-05 (`llm_calls` shape) | extended | two nullable columns appended, `reasoning_requested` and `reasoning_honored`. No column is removed, renamed or retyped, and the `CHECK (purpose IN ('agent','summary'))` constraint (storage.py:63) is **not** touched — the reasoning tag is a separate, derived value (REQ-V170-POL-02) |
| `tracing._TG_AGENT_ATTRIBUTE_KEYS` (tracing.py:65-80) | extended | gains exactly one member, `tg_agent.reasoning.requested` (REQ-V170-OBS-02); the honored verdict is derivable from the existing `gen_ai.usage.reasoning.output_tokens` and needs no second key |
| `agent.SUMMARY_MAX_TOKENS = 512` (agent.py:46) | unchanged | stays the first-attempt budget; REQ-V160-TQ-02's `retry_max_tokens` pair is unchanged |
| `agent.summarize_conversation` (agent.py:1022-1030) | extended | gains keyword-only `budget_s: float \| None = None` and `clock: Callable[[], float] = time.monotonic`; `_ask_for_summary` (agent.py:1070) gains `timeout_s: float \| None = None`. Both default to today's behaviour (REQ-V170-SUM-01) |
| `config._check_timeout_budget` (config.py:377-395) | extended | unchanged in formula and in message; REQ-V170-SUM-05 adds the second, **budget-level** check. At the 1.7.0 instrument (`LLM_MAX_TOKENS=4096`, `LLM_SUMMARY_MAX_TOKENS=1536`) the existing floor is `21.1 + 0.093 × 4096 = 402.028 s`, comfortably under `LLM_TIMEOUT_S=600` |
| `bot.py:730-734`, `:753-755` summary call sites | extended | each additionally passes `budget_s=cfg.llm_timeout_s`; nothing else about either call changes (REQ-V170-SUM-01) |
| `bench.py` `run --tag` → `shutil.rmtree` (devtools/bench.py:2323-2325) | amended | `--tag` is validated against `^[A-Za-z0-9._-]{1,64}$` and rejected when it is `.` or `..`, **before** any path is built (REQ-V170-CAR-01) |
| `config/quality_gates.yaml:313` `report_path` | amended | `docs/reports/report-v1.5.md` → `docs/reports/report-v1.7.0.md`. It was never repointed for v1.6.0, so REQ-V160-RPT-01's claim that `lint-docs` enforced that report's ledger row was untrue (REQ-V170-RPT-02) |
| `config/quality_gates.yaml` profiles | extended | one new gate `mutation-v170` in `pre-push`; `mutation-all`'s `timeout_seconds` re-measured (REQ-V170-GATE-02). No existing gate's command is edited, reordered or removed |
| `AGENTS.md` Gates / Stack / configuration / Benchmark | extended | the new gate, the two new environment variables, the corrected test count (1004 → measured) and the corrected mutation-entry count, each in the same commit as the change it describes |
| `README.md`, `.env.example`, `docs/plan.md` | extended | the two new variables with defaults and ranges, the reasoning-policy section, the milestone and test count |
| Appendix B `E13` of spec-v1.6.0 | superseded | refreshed as Appendix B `E9` here, with S15 and S18 at a blocking 3/3 (REQ-V170-CAR-02) |

Everything else in v0…v1.6.0 — Docker isolation, the redaction choke points,
the SSRF allowlist, failover, structured memory, commands, rate limiting, the
error matrix, the token budget, the pricing resolver, tracing, the dashboard,
the hook chain and the four scanners — is unchanged and MUST keep working.

---

## 3. Preconditions

**REQ-V170-PRE-01 (MUST)** Verify each; on failure stop and emit the blocker
template (v0 §7.2) instead of guessing.

1. **Repository**: branch `main`, clean tree, HEAD carrying the delivered
   v1.6.0 (`docs/spec/spec-v1.6.0.md`, `docs/reports/report-v1.6.0.md`,
   `docs/assets/bench/baseline-v1.6.0.json`) **and this spec, already
   committed**: `docs/spec/spec-v1.7.0.md` and
   `docs/prompts/102-v170-spec-authoring.md` exist at HEAD, `102` is the
   highest-numbered prompt, and the spec's `sha256` is recorded at T0 and MUST
   NOT change during the run — the executor materialises nothing. **Record the
   starting HEAD SHA as `<base>`** before the first commit; it is the lower
   bound of every `--since` and `replay --range` in this run.
2. **Tags**: `git tag -l` shows `v1.3`, `v1.3-baseline` and `v1.6.0`. None is
   moved or deleted (REQ-V170-NG-13).
3. **The offline gates green before anything changes**: at T0,
   `python3 devtools/checks.py run --profile full --since <base>` exits 0 **with
   its live member deferred**, and gates 1–4 and 6 of §13 exit 0 in their own
   right. An already-red gate is a blocker, not something to fix silently here.
   Gate 5 (`bot.py --selftest-live`) and the `full` profile's live member run at
   **T1**, after PRE-03 and PRE-04. An unreachable LM Studio is therefore not a
   T0 blocker — it is a T1 blocker.
4. **Test count re-measured** at HEAD: `uv run --locked pytest --collect-only
   -q`. Record the number; it is the floor of REQ-V170-EC-03.
5. **Hooks**: `python3 devtools/install_hooks.py --check` exits 0 and
   `python3 devtools/checks.py doctor` exits 0 against the six pinned tools.
6. **Credentials**: the git-ignored `.env` exists with the keys spec-v1.2 §3.3
   lists, plus `LMSTUDIO_BASE_URL`. Presence is established **only** by
   `grep -q '^KEY=' .env` per key name (REQ-V170-EC-04).
7. **Docker**: `docker version` succeeds without `sudo`; the digest-pinned
   `python:3.14-slim` image of REQ-V15-IMG-01 is locally present.
8. **The baseline is readable and self-consistent**: `uv run --locked python
   devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json` exits 0.
9. **Neither policy key is already in `.env`**, proved by the first idiom of
   REQ-V170-EC-04 and by nothing else:
   `grep -q '^LLM_REASONING_POLICY=' .env` and
   `grep -q '^LLM_REASONING_ON_PURPOSES=' .env` MUST **both return non-zero**.
   Presence is a **blocker**, reported by key **name** only: the executor may
   neither disclose nor rewrite these keys (REQ-V170-EC-04), and a key already
   in the file would override the shipped default REQ-V170-POL-07 selects —
   `load_config` reads `os.environ` after
   `dotenv.load_dotenv(..., override=False)` (`config.py:202-203`), so a
   candidate's process-environment prefix beats `.env` during measurement while
   `.env` beats a changed source literal afterwards, for the deployed bot.
   **This check is what makes the final-tree equivalence test meaningful.**
   `T-V170-ACC-03` resolves `load_config()` with no `LLM_REASONING_*` in the
   process environment and without the deployment `.env`, so it proves what the
   *tree* resolves to; that proof carries to the running bot only while these
   two keys are absent, and the report restates this check beside
   REQ-V170-ACC-03's candidate-metadata check. This is **not** the rejected
   objection to the bot's and the bench's ordinary `.env` loading (Appendix C,
   R1-1): it is one precondition on the two keys this release newly activates.

**REQ-V170-PRE-02 (MUST) — the operator inputs arrive in the `go` request's own
text, and block at T0.** Per the lab's `go` protocol (`AGENTS.md:157-173`) and
the REQ-V160-PRE-04 precedent, three values are supplied by the operator in the
text that starts the run and are copied **verbatim** into the T0 report
skeleton's `## Operator inputs` section:

| value | rule |
|---|---|
| LM Studio version | a non-empty string. It MUST equal `meta.lmstudio_version` of the baseline, `"Bionic v1.1.1"`, or REQ-V170-BEN-01's STOP fires |
| loaded context length | a **positive integer**. It MUST equal `42496` |
| current LM Studio address | one of `192.168.0.145`, `172.16.50.233`, `192.168.178.170`, or another the operator names. A named address MUST be a **literal IPv4 address** matching `^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$` with every octet ≤ 255 — no hostname, no scheme, no port, no path; anything else is rejected at T0 with the blocker template rather than interpolated. PRE-03 probes the three fixed addresses first, in the order written here, and the operator's address last if it is distinct from all three |

A missing version, or a context length that is not a positive integer, **stops
the executor at T0** — blocker template, no T1. A value that is present but
disagrees with the baseline is **not** a T0 blocker: it is REQ-V170-BEN-01's
instrument STOP at T1, which is a different, reported outcome.

**REQ-V170-PRE-03 (MUST) — LM Studio, reached without reading `.env`; the
documentation reads; and the one probe that is itself an inference.** This
requirement runs in **two phases, and the whole of REQ-V170-PRE-04 stands
between them**:

- **phase 1 — no inference**: the address probe, the single-line `.env`
  rewrite, the served-model-id read and the **three documentary** `VERIFY`
  reads below;
- **phase 2 — one inference**: the OpenAI-route **TTFT-shape probe** of the
  fourth `VERIFY` marker, issued **only after every one of REQ-V170-PRE-04's
  seven checks has passed** — its item 7 being the first inference of the run —
  and **before any stage-A pair**.

An instrument that cannot be compared must never be probed further, and the
round-2 order — the whole of PRE-03 before PRE-04 — could spend an inference,
and warm a cache, on an instrument PRE-04 was about to reject. REQ-V170-ORD-01's
T1 states the same order as an execution sequence.

**Phase 1.** Probe, in order, until one answers:

```bash
for h in 192.168.0.145 172.16.50.233 192.168.178.170 <operator-ip-if-distinct>; do
  curl -sS -m 3 "http://$h:1234/v1/models" >/dev/null && echo "$h" && break
done
```

**The probe list is ordered and deduplicated, and it is built before the loop
runs.** It is the three fixed addresses in the order written above, followed by
the address REQ-V170-PRE-02's operator input names **only when that address is
distinct from all three** — so a repeat of a fixed address is probed once, not
twice, and an operator address the round-1 spec would have ignored is now
reached. **Only a literal IP accepted by PRE-02's pattern may be interpolated
into the loop**: the value is validated against that pattern *before* the
command is built, and a value failing it is a T0 blocker, never a probed string.
When the operator named no address, or named one already in the fixed three, the
`<operator-ip-if-distinct>` placeholder is **dropped from the list** rather than
passed to `curl` as written.
Nothing else — no hostname, no operator-supplied scheme, port or path — is ever
substituted. Every address in the list is probed in order until one answers; all
of them failing is the T1 blocker of REQ-V170-GATE-01.

The winning address is written into `.env` by a **single-line rewrite only**:

```bash
sed -i 's|^LMSTUDIO_BASE_URL=.*|LMSTUDIO_BASE_URL=http://<addr>:1234/v1|' .env
```

confirmed by `grep -q '^LMSTUDIO_BASE_URL=http://<addr>:1234/v1$' .env`; a
non-zero status is a blocker, `sed -i` being silent when the key is absent
(REQ-V170-EC-04). The served model id is read from `GET
<LMSTUDIO_BASE_URL>/models`, field `data[].id`, exactly the read `_live_lmstudio`
already performs (bot.py:1308-1318); **exactly one** entry of that list MUST
equal `cfg.lmstudio_model` — see REQ-V170-PRE-04 item 3, which owns the rule and
the STOP that an ambiguous or duplicated match triggers.

Still in phase 1, and still without an inference, the executor performs the
**documentation reads** stage A candidate **b** depends on — read-only HTTPS
requests to the named LM Studio and OpenRouter documentation sources, which
REQ-V170-EC-01's allowlist names explicitly — and records, in the report, the
URL, the date and the exact spelling found:

`[[VERIFY: the per-request **disable** value LM Studio Bionic 1.1.x documents
for reasoning — an `enabled: false` form, or an effort value meaning *none*.
Decision rule, fixed in advance and not reopened at run time: a form that
switches reasoning **off** is candidate b's payload; a merely **smaller**
effort (`low`) is not an off-switch and never counts; if the documentation
offers only `low|medium|high`, candidate b is recorded `unsupported`, consumes
**no** pair of REQ-V170-RSN-05's budget, and probing continues at candidate c.
The executor MUST NOT substitute a remembered spelling for the read.]]`

`[[VERIFY: OpenRouter's documented per-request off form. The handoff carries
`"reasoning": {"enabled": false}`; REQ-V170-POL-05 requires it to be confirmed
against OpenRouter's live documentation in the same read, with URL and date in
the report. It is never exercised live in this release (REQ-V170-NG-08).]]`

`[[VERIFY: an LM Studio Bionic 1.1.x REST endpoint exposing the application
version and the loaded context length. Carried unresolved from
REQ-V160-PRE-04: if the executor finds one, the API value is recorded alongside
the operator value and the report names the endpoint and field; **on
disagreement the operator value wins** and both are recorded.]]`

**Phase 2 — the TTFT-shape probe, after the validated preflight.** The fourth
`VERIFY` marker below is not a documentary read: it is a live completion, the
**second inference of the run**, and it is issued only once every one of
REQ-V170-PRE-04's seven checks has passed and its item-7 preflight has returned
a non-empty message — and before stage A spends its first pair.

`[[VERIFY: whether LM Studio Bionic 1.1.x populates the non-standard response
field **`stats.time_to_first_token`** (TTFT) on the **OpenAI-compatible**
`POST <LMSTUDIO_BASE_URL>/chat/completions` route — the only route the bot's
client uses (`llm/lmstudio.py:35-53`) and therefore the only one stage A's
scratch harness sends through. LM Studio documents the populated `stats` object
(`tokens_per_second`, `time_to_first_token`, `generation_time`, `stop_reason`)
on its **native** `POST /api/v0/chat/completions`; on the OpenAI-compatible
route it has been reported as an empty `"stats": {}` (lmstudio-bug-tracker issue
#601). The check is therefore **live and shape-specific, not documentary**:
issue one completion through the bot's own client, with the harness's own
request shape, against `/v1/chat/completions`, and record whether
`stats.time_to_first_token` returns a positive number, an empty object, or
nothing at all. **The harness MUST NOT switch to the native endpoint** for this
probe or for any pair member: a different request shape, with unverified support
for the mechanism fields of REQ-V170-RSN-02, would measure a different
instrument (REQ-V170-BEN-01). Absent or empty on that route ⇒ REQ-V170-RSN-07's
**summary-only fallback** binds the whole run — no agent-tag cache evidence
exists and any mechanism found ships for `summary` only. That is the first of
the fallback's **two** triggers; the second is the warm proof of RSN-07's cold
calibration failing, which this probe cannot settle. The probe's system prompt
**begins with a fresh random 32-hex nonce** — REQ-V170-RSN-07's cold-calibration
prefix — so this one inference warms a prefix no later run shares and can never
warm the production prefix the confirming runs measure. The verdict, the route, the exact field path and the date go in the
report.]]`

**REQ-V170-PRE-04 (MUST) — the instrument is proved before it is used, and it
is proved without disclosure.** Before the first inference of stage A the
executor establishes all **seven** of these, and records each in the report. The
first six are REQ-V170-BEN-01's six instrument values and every one of them is
established **before** item 7, the first live inference of the run: an
instrument that cannot be compared must never consume a pair of stage A's
budget, and a mismatch discovered at T11 instead has already spent it.

1. `grep -q '^LLM_MAX_TOKENS=4096$' .env` exits 0;
2. `grep -q '^LLM_TIMEOUT_S=600$' .env` exits 0;
3. **the uniquely selected served model id equals exactly `qwen/qwen3.8-27b` and
   `cfg.lmstudio_model`; substring matching is insufficient.** The comparison is
   string equality against both, not `in`, not `startswith`, not a case-folded
   or slash-trimmed form: `qwen/qwen3.8-27b-mlx` and `qwen/qwen3.8-27b@q4` each
   *contain* the baseline's id and are each a different instrument. If the
   `data[].id` list holds **no** exact match, or **more than one** entry that
   compares equal, or the exact match is not the id `cfg.lmstudio_model` names,
   the selection is ambiguous and the run **STOPS** here with
   REQ-V170-BEN-01's instrument STOP — before the preflight of item 7 completes
   and therefore before any inference is spent;
4. the operator's LM Studio version string equals `"Bionic v1.1.1"`;
5. the operator's loaded context length equals `42496`;
6. `cfg.obs_capture_content is False`, read from the loaded `Config` and not
   from `.env`, **and** the bench metadata producer is dry-run — or its emitting
   line asserted offline — to prove it writes `meta.obs_capture_content: false`.
   The baseline pins `false` (REQ-V170-BEN-01) and it is a locked meta field, so
   a `true` here makes every candidate non-comparable; establishing it at T11,
   after three 3-repeat runs, wastes the whole of stage C;
7. the **inference preflight** — one chat completion against the resolved
   address with the resolved model, **no tools**, a fixed one-line prompt and
   `max_tokens = cfg.llm_max_tokens` (production's own budget; a fixed small
   literal is unsafe on a reasoning model, REQ-V160-PRE-04's erratum) returns a
   non-empty assistant message.

Reads 1 and 2 emit nothing but an exit status and are the second permitted
`.env` idiom of REQ-V170-EC-04; a `4096`/`600` mismatch is the instrument STOP
of REQ-V170-BEN-01, not a silent adjustment, and so is a failure of item 3, 4, 5
or 6. Items 1–6 are **all** evaluated before item 7 runs, and item 7 is the only
one of the seven that costs inference; a STOP therefore leaves the live budget
untouched. Item 7 is also the **first inference of the whole run**:
REQ-V170-PRE-03's phase-2 TTFT-shape probe is the second, issued only once item
7 has returned its non-empty assistant message, and no other inference precedes
stage A. Nothing here rewrites `.env` except PRE-03's `LMSTUDIO_BASE_URL` line.

---

## 4. Required file tree (delta)

**REQ-V170-TREE-01 (MUST)** New files:

```
tests/test_v170_reasoning.py        # §14.2  RSN-*, POL-*, OBS-*
tests/test_v170_summary_budget.py   # §14.2  SUM-*
tests/test_v170_bench.py            # §14.2  BEN-*, CAR-*, VER-*
docs/prompts/103-go-spec-v1.7.0.md  # the `go` prompt, created at T0
docs/prompts/104-v170-*.md …        # one per task of §16
docs/reports/report-v1.7.0.md
docs/reports/tg-post-v1.7.0.md
docs/reports/bench-v1.7.0.md              # §9, the gated comparison
docs/assets/bench/rsn17-<letter>-<n>-<purpose>-{default,off}.json   # §5 pairs
docs/assets/bench/rsn17-<letter>-mixed-{control,mixed}.json         # §5 RSN-07
docs/assets/bench/rsn17-<letter>-mixed-{control,mixed}-ttft.json    # §5 RSN-07 sidecar:
                                          #    the cold calibration and the per-call TTFTs
docs/assets/bench/cand-v170-<c>.json      # §9, one per candidate run
```

**REQ-V170-TREE-02 (MUST)** Changed files: `llm/base.py`, `llm/lmstudio.py`,
`llm/openrouter.py`, `llm/failover.py`, `agent.py`, `config.py`, `bot.py`,
`storage.py`, `tracing.py`, `devtools/bench.py`, `devtools/mutation_check.py`,
`config/quality_gates.yaml`, `.env.example`, `README.md`,
`AGENTS.md`, `docs/plan.md`, plus exactly the test files named in §14.1.
`pyproject.toml` is listed too, but it is **conditional**: its `project.version`
changes in the post-measurement selection commit of REQ-V170-POL-07 (T12) and
nowhere else, so on every branch that skips T12 the file is unchanged at the tip
(REQ-V170-VER-01).
`devtools/bench_scenarios.py` is **frozen** (REQ-V170-AMEND-01); `metrics.py`,
`dashboard_render.py`, `dashboard_server.py` and `devtools/dashboard.py` are
**not** changed — the existing per-purpose `reasoning_share`
(`metrics.py:397-416`, `group="purpose"` at `:379-381`) is the whole reporting
surface this release needs (REQ-V170-NG-04).

**Prompt numbering.** `101-v160-verify-run-fixes.md` closes v1.6.0 and
`102-v170-spec-authoring.md` is this spec's authoring prompt; both, and
`spec-v1.7.0.md` itself, are committed **before** this run and are therefore
neither new nor changed files here (PRE-01.1). `102` not being the highest
prompt at T0 is a precondition failure. This run's first artefact is the `go`
prompt `103-go-spec-v1.7.0.md`, created at T0; per-task prompts continue from
`104` as `NN-v170-t<k>-<slug>.md`, `<k>` running `0`…`14` over §16's fifteen
tasks. Numbering never restarts and no earlier file
is renamed.

---

## 5. Stage A — the reasoning mechanism spike (RSN)

v1.4 ran this spike on LM Studio **0.4.23** and it ended in `RSN-06 STOP`
(`report-v1.4.md:213-303`): **a** had no effect, **b** was `unsupported`, **c**
was honored 3/3 but rejected as unshippable, **d** was not honored, **e** had no
control to set. The instrument has since changed to **Bionic 1.1.1** and one
judgement has changed with this release: **shippability is now decided per
purpose** (REQ-V170-RSN-04). Everything else about the contract is v1.4's, reused
by reference to `docs/spec/spec-v1.4.md` §5.

**REQ-V170-RSN-01 (MUST) — the pair contract, and the two probe scenarios.** The
unit of evidence is a **pair**, named by file, exactly as REQ-V14-RSN-01 defines
it: one scratch, **uncommitted** patch selecting exactly one mechanism, one
`bench.py run --only <scenario> --repeats 1` per member, the `default` member
first and the `off` member second, from the identical scenario input, written to
`docs/assets/bench/rsn17-<letter>-<n>-<purpose>-default.json` and
`…-off.json` with their `.log` siblings. Two probe scenarios, and no others:

| purpose group | scenario | why |
|---|---|---|
| `tool-round` and `final` | **S05** (`big-output`, bench_scenarios.py:204) | one turn, one tool round, then a final tools-withheld round — both agent tags in one cheap run; v1.4's own probe |
| `summary` | **S12** (`summary`, bench_scenarios.py:262) | three turns ending in `/new`, whose `summary_exists` check proves a `purpose = 'summary'` row was written |

`--only S05` and `--only S12` set `meta.only`, which is a locked field, so **no
pair document is ever a benchmark candidate or a baseline** and none is compared
with `--gate`. After each candidate the tree is restored and `git diff` MUST be
empty before the next candidate begins; the report records the check. This is an
explicit, bounded exception to REQ-V170-EC-02's test-first rule and adds **no**
CLI flag and **no** `bench.py` option.

**REQ-V170-RSN-02 (MUST) — the candidates, in this fixed order, none skipped.**
Skipping an untried candidate is a defect. Probing stops at the first candidate
that is honored **and** shippable for the `summary` purpose (REQ-V170-RSN-04);
a candidate honored but unshippable for a purpose is recorded as such, consumes
its normal budget, and probing continues.

| # | mechanism | where it goes |
|---|---|---|
| **a** | `chat_template_kwargs: {"enable_thinking": false}` | a **top-level key of the JSON body** built by `build_payload` (llm/base.py:112-129) — the project posts raw JSON through `httpx`, so what an SDK would send as `extra_body` is a plain top-level key |
| **b** | the **vendor-documented disable value** read live at REQ-V170-PRE-03 | a top-level key of the JSON body. `unsupported` when the documentation offers only `low\|medium\|high`; a smaller effort is never an off-switch |
| **c** | assistant prefill `{"role": "assistant", "content": "<think>\n\n</think>\n\n"}` | **inside the message array, as the last element** |
| **d** | Qwen3's `/no_think` soft switch | inside the message array, appended to the **last user message**, in the slot REQ-V13-CCH-01 mutates with `(now: …)` |
| **e** | a model-level default in the LM Studio GUI or `lms` CLI | **not in the request at all** — environmental, informational only. It cannot express a per-purpose policy and therefore can never be a winner (REQ-V170-RSN-04); at most one `rsn17-e-info` note, outside the budget |

**REQ-V170-RSN-03 (MUST) — honored, per purpose.** For a given pair and a given
purpose tag, the mechanism is **honored** when, over the `llm_calls` rows of that
purpose in the two documents:

1. the `off` member has `Σ reasoning_tokens == 0` **and** `max reasoning_chars
   == 0` — both sources, `usage.completion_tokens_details.reasoning_tokens`
   (`llm/base.py:132-155`) and the locally computed `split_reasoning`
   (`llm/base.py:158-181`), because a provider that reports neither is not proof
   of anything;
2. the `default` member has **positive** `reasoning_tokens` **or** positive
   `reasoning_chars` — a mechanism that changes nothing on a model that was not
   reasoning is not evidence;
3. the scenario's own checks still pass in **both** members (S05 `1/1`, S12
   `1/1` including `summary_exists`).

If `reasoning_tokens` is absent from either member, the pair is `unknown`, never
`honored`, unless all three of REQ-V14-RSN-03's fallback conditions hold
(positive `reasoning_chars` on `default`, zero on `off`, and `off`'s completion
tokens **and** recomputed cost each ≥ 20 % below `default`'s). The 20 % is fixed
in advance and not tunable. A candidate is honored for a purpose only when
**every** pair probing that purpose is honored.

**REQ-V170-RSN-04 (MUST) — shippability is judged PER PURPOSE; that is what
changed since v1.4.** REQ-V14-POL-05 rejected **c** and **d** outright for
sitting inside the message array and disturbing REQ-V13-CCH-02's byte-stable
cache prefix. That still holds **for agent rounds**, whose messages share one
growing prefix across a turn. It does **not** hold for the summary call:
`_ask_for_summary` builds `load_context_messages(...) + [{"role": "user",
"content": SUMMARY_PROMPT}]` (agent.py:1045, `:1094`) with `tools=None` — a
**one-shot** list sharing no system-prompt-plus-tools prefix with any agent
round, and never extended. Therefore:

| mechanism | `tool-round` | `final` | `summary` |
|---|---|---|---|
| **a**, **b** (outside the array) | shippable | shippable | shippable |
| **c** (prefill, last element) | **not** shippable — breaks CCH-02(a) | not shippable | **shippable** |
| **d** (`/no_think`, last user message) | not shippable under `by-purpose`; shippable only when the resolved value is identical for every call of one `run_agent` invocation | same | **shippable** |
| **e** | never | never | never |

**That table is the message-array judgement alone, and it is necessary, not
sufficient.** A "shippable" cell for `tool-round` or `final` says only that the
mechanism does not sit inside the growing message prefix; agent-tag shippability
is established **additionally and only** by REQ-V170-RSN-07's confirming
mixed-policy run. Under RSN-07's **summary-only fallback** — the TTFT field
absent on the harness's route, **or** its cold calibration's warm proof failing
— no mechanism is agent-shippable at all, whatever this table says, and the
shipped mechanism table of REQ-V170-RSN-06 carries `none` for both agent tags.

The pair contract measures the price of the disturbance rather than asserting
it: for each pair the report records `totals.resent_tokens` and
`totals.new_tokens` per member and per purpose, and v1.4's measured
`338 → 634` resent-token blow-up on candidate d is quoted as the prior.

**REQ-V170-RSN-05 (MUST) — the budget, counted in live pairs.** At most **three**
pairs per candidate and at most **fifteen live pairs in total**. An `unsupported`
candidate consumes none. One re-run is permitted for a pair whose scenario failed
for a reason unrelated to reasoning (transport timeout, Docker hiccup); the
re-run replaces the **whole** pair, never one member, and does not raise the
budget. Per candidate the pairs are spent in this order and stop as soon as the
candidate is decided: pair 1 on **S05**, pair 2 on **S12**, pair 3 the
**confirming** pair — a repeat of pair 2 for a candidate that would ship only
for `summary`, and the **mixed-policy pair of REQ-V170-RSN-07** for a candidate
that would ship for either agent tag. **Under RSN-07's summary-only fallback — the TTFT field
absent, or a cold calibration's warm proof failing — no candidate can be
agent-shippable at all**, so pair 3 is then always the plain repeat of pair 2
and the mixed-policy pair is either never spent or abandoned before either
member runs. Two counting rules follow, stated here because otherwise the budget
cannot be counted: RSN-07's **cold-calibration requests are scratch and lie
outside the fifteen-pair budget entirely** — they are neither pair members nor
`bench.py` runs — and a confirming pair **abandoned because its calibration's
warm proof failed consumes no pair**, its slot reverting to the plain repeat of
pair 2. That is why the fallback costs no budget and changes no count here,
whichever of its two triggers fired. The mixed-policy pair replaces the plain
repeat in that one slot, so neither the three-per-candidate nor the fifteen-total
budget moves. The report
carries one table row **per pair member** — letter, ordinal, purpose group,
member, mechanism, LM Studio version, HTTP status, `Σ reasoning_tokens`, `max
reasoning_chars`, `reasoning share`, resent/new tokens, scenario result — with
the pair verdict stated once, on the `off` row, from the vocabulary `honored` /
`not honored` / `unknown` / `honored but unshippable` / `unsupported`.

**REQ-V170-RSN-06 (MUST) — the output, and the STOP rule.** Stage A ends with a
**per-purpose mechanism table** in the report:

| purpose | mechanism | evidence |
|---|---|---|
| `tool-round` | one of a, b, or `none` | the pair files |
| `final` | one of a, b, or `none` | the pair files |
| `summary` | one of a, b, c, d, or `none` | the pair files |

**If no mechanism is shippable for `summary`, the run STOPS after stage A**, and
it finalises through the shared `T-STOP` procedure of REQ-V170-ORD-02, which is
what makes the promises below executable rather than aspirational.
The `summary` purpose is the concrete target of this release — S18's lost run
was a starved, then timed-out summary, and S15's smoke failures were the same
reasoning-exhaustion family on the agent path — and a policy that cannot switch
it off does not earn the −30 % gate. On that branch the run still delivers: the
mechanism table, every pair artefact, the report, the `tg-post`, the ledger row,
and the verdict **STOP, cause: no summary-shippable reasoning mechanism on
Bionic 1.1.1**. §6, §7, §8 and §9 are declared **not-executed**,
`pyproject.toml` is **not** bumped, and **no tag is created**.

**The carried items go with the code, not with the report.** Under
REQ-V170-ORD-01's measurement-first order stage A runs *before* the code tasks,
so REQ-V170-CAR-01's `--tag` sanitiser — which lives in `devtools/bench.py`
alongside the stage-C work — has not been written when this branch fires and is
**deferred to v1.8.0 with the rest of §§6–9**, stated as such in the report.
REQ-V170-CAR-02 is unaffected either way: it is satisfied by this spec's own
Appendix B `E9` and needs no code.

**REQ-V170-RSN-07 (MUST) — an agent-shippable mechanism additionally needs one
confirming mixed-policy run.** RSN-01's pairs are **homogeneous**: each member
runs one treatment for every call of the run. That is enough to decide *honored*;
it does **not** exercise the pattern the shipped `by-purpose` policy actually
creates — the within-turn transition `tool-round` on/default → `final` off, in a
single `run_agent` invocation, over one growing message prefix. A top-level
`chat_template_kwargs` or reasoning field sits outside the message array yet can
still change template rendering or the served prefix, and no homogeneous pair can
see that. Without this requirement "shippable for the agent tags" stays a
judgement call and prefix damage can ship unnoticed.

A candidate may therefore be declared shippable for `tool-round` or for `final`
only after **one** confirming pair on **S05** — the scenario that *is* the
tool-round → final transition (`bench_scenarios.py:204`):

| member | file | treatment |
|---|---|---|
| control | `docs/assets/bench/rsn17-<letter>-mixed-control.json` | `LLM_REASONING_POLICY=model-default` — the untreated run, from the identical scenario input |
| mixed | `docs/assets/bench/rsn17-<letter>-mixed-mixed.json` | exactly the proposed by-purpose treatment — `by-purpose` with the `LLM_REASONING_ON_PURPOSES` the candidate would ship — applied inside **one** invocation of a multi-round scenario |

Both members are one `bench.py run --only S05 --repeats 1` under REQ-V170-RSN-01's
pair contract: scratch patch, uncommitted, tree restored and `git diff` empty
afterwards, `meta.only` set and therefore never a candidate or a baseline.

**The threshold, fixed in advance and derived from how `bench.py` computes these
numbers.** Two checks answer two different questions, and neither substitutes
for the other: **check 1** catches *prompt-token inflation* — a re-rendered
prefix the server had to re-read, which shows up in the token counts; **check 2**
catches *cache-key damage* — a prefix identical in token count that the server
nevertheless had to process cold, which shows up in nothing but time. A mixed
member ships for an agent tag only when it passes both.

**Check 1 — no prompt-token inflation.** `runs[].totals.resent_tokens` and `new_tokens` come from
`metrics.resent_tokens` (`metrics.py:75-91`) through `bench.totals_from_rows`
(`devtools/bench.py:461-482`): over the calls of one conversation ordered by
`id`, `new₁ = prompt₁` and `newᵢ = max(0, promptᵢ − promptᵢ₋₁)`, with
`resentᵢ = promptᵢ − newᵢ`. Both are a **pure function of the per-call
`prompt_tokens` sequence**, so an undisturbed prefix reproduces the control's
sequence and the only legitimate difference is the mechanism's own message-array
cost — zero for **a** and **b**, under 32 tokens for **c** and **d**. Both of
these hold, on the run totals:

1. `resent_tokens(mixed) ≤ 1.05 × resent_tokens(control)`;
2. `new_tokens(mixed) ≤ new_tokens(control) + 64`.

The 5 % and the 64 tokens are deliberately loose against the size of the failure
they exist to catch: v1.4 measured a `338 → 634` resent-token blow-up on
candidate **d**, **+87 %**, and a re-rendered prefix costs hundreds of tokens,
not tens.

**Check 2 — the prefix cache survived, evidenced by time to first token.**
Prompt-token counts cannot see this failure: a top-level reasoning or template
field can change the server's cache key or its rendered-prefix identity while
leaving every reported `prompt_tokens` exactly unchanged. **Latency *ratios*
between the control and the mixed member are not evidence and are dropped** —
one sample each passes through ordinary timing variance, so a ratio threshold
distinguishes neither cache preservation nor a lucky run. The direct signal is
LM Studio's own non-standard response field **`stats.time_to_first_token`**
(TTFT), recorded per call by the scratch harness of §16's T2 and verified live
by REQ-V170-PRE-03's **phase-2** probe — after the validated preflight and
before stage A spends a pair. TTFT is prompt-processing time, and a preserved
prefix is precisely the difference between reading a prefix and re-reading it.

**The rate is measured against a prefix that is cold by construction, and no
cache reset is assumed.** LM Studio's prefix cache survives across HTTP
requests, so a run's first call is **not** cold merely because nothing precedes
it *inside that invocation*: the preflight, the phase-2 shape probe and every
earlier pair may already have warmed the very prefix it sends, which would
depress the rate's denominator and let the verdict pass or fail artefactually.
This release has **no verified remote mechanism for clearing that cache** on the
roaming LM Studio box, so it assumes none and makes the prefix cold instead.

The rule is computed **per confirming member**, from that member's own
calibration and its own run, so no cross-run timing comparison is made anywhere:

- **the cold calibration.** Immediately before each confirming member — the
  control and the mixed member alike — the harness issues one **scratch**
  request whose system prompt **begins with a fresh random 32-hex nonce**. A
  prefix no server has ever seen cannot be cached, so that request is cold **by
  construction**, and `rate = prompt_tokens ÷ TTFT` of it, in prompt tokens per
  second;
- **the warm proof.** The **identical** request — same nonce, same bytes — is
  then issued once more, and its TTFT MUST be `≤ 0.35 ×` the first's. That is
  the evidence that this server caches prefixes at all and that TTFT can see the
  difference; without it a low ratio on the final round would prove nothing,
  because nothing would distinguish a preserved prefix from a server that never
  cached one;
- **both calibration requests go through the harness's own client, route and
  request shape** (`POST <LMSTUDIO_BASE_URL>/chat/completions`,
  REQ-V170-PRE-03), differing from a member call only in their nonce-prefixed
  one-line system prompt — a rate taken through a different route or shape would
  be a different instrument's number and the prediction below would be
  meaningless. They are **excluded from the member document**: they are scratch,
  never `bench.py` calls, never rows of `runs[]`, and they cost no pair of
  REQ-V170-RSN-05's budget;
- **when the warm proof fails** — the second TTFT above `0.35 ×` the first —
  this instrument's caching is not demonstrable, **check 2 is unavailable**, and
  the summary-only fallback below binds exactly as it does when the field is
  absent. The confirming pair is abandoned before either member runs and
  consumes no pair (REQ-V170-RSN-05);
- **the prediction.**
  `predicted_cold_TTFT(final round) = prompt_tokens(final round) ÷ rate` — what
  the final round would cost if its whole prefix had to be processed again;
- **the verdict.** The cache is **preserved** iff the measured
  `TTFT(final round) ≤ 0.35 × predicted_cold_TTFT(final round)`, and it MUST
  hold on **each** confirming run, never on an average across them.

`0.35` is fixed in advance and is not tuned at run time. It is loose in the safe
direction: a preserved prefix processes only the round's own new tokens and
lands one to two orders of magnitude under the prediction, while a prefix the
server had to re-read lands at the prediction itself, near `1.0`. Anything
between the two is a **fail** — the check refuses to call an ambiguous run
shippable.

**When check 2 is unavailable the conservative rule applies verbatim, and it
has two triggers.** Check 2 is unavailable when `stats.time_to_first_token` is
not populated on the endpoint and request shape the harness actually uses —
which REQ-V170-PRE-03's fourth `VERIFY` marker settles live at T1, after the
validated preflight and before stage A spends anything — **or** when the cold
calibration's warm proof above fails. In either case, absent non-null
cached-token data or a rendered-prefix/cache-key digest, **RSN-07 proves only
absence of prompt-token inflation and MUST NOT establish agent-tag cache
shippability. Such a mechanism may ship for `summary` only.** No latency
measurement rescues it, no repeat of the pair rescues it and no unverified cache
reset rescues it; the report names **which** of the two triggers fired and
records the fallback as the reason the agent tags shipped no mechanism. It
constrains **mechanisms**, not policy values: `"on"` and `"default"` send no
field at all (REQ-V170-POL-03), so REQ-V170-BEN-05's catalogue still runs — see
its C3 clause.

A member missing check 1, or missing check 2 where check 2 is available, is
**not shippable for the agent tags** whatever the homogeneous pair said; it may
still be shippable for `summary`, which is judged by REQ-V170-RSN-04. Every
measured number — both token figures, the per-run rate, the prediction, the
measured final-round TTFT and their ratio — and the verdict go in the report's
pair table.

**The TTFT sidecar: committed evidence, and deliberately not a bench document.**
`bench.py` records no TTFT field, so the scratch harness writes one sidecar per
mixed-pair member,
`docs/assets/bench/rsn17-<letter>-mixed-{control,mixed}-ttft.json`, holding
**three** parts in this order. First the member's **`calibration`** block, the
two nonce-prefixed scratch requests that produced the rate —
`{"nonce_hex_len": 32, "prompt_tokens", "first_ttft_s", "second_ttft_s",
"warm_ratio", "warm_proof": true|false}` — of which the **nonce itself is never
recorded**, only its length, and whose two calls are **not** members of the call
list. Then one object per LLM call of the member, in call order,
`{"index", "purpose", "prompt_tokens", "time_to_first_token_s"}`. Then that
member's computed `rate` — taken from `calibration`, **never** from the run's
own first call — with `predicted_cold_ttft_s`, `measured_ttft_s` and `ratio`. It carries **no `meta` block**, is never passed to `bench.py check`,
never compared with `--gate`, and is never a candidate or a baseline; it changes
not one byte of the pair documents beside it, so REQ-V170-RSN-01's `meta.only`
reasoning is untouched. A missing or empty TTFT value is written as `null`,
never omitted and never estimated.

**Measured, and recorded rather than followed: `cache_hit_rate` cannot be the
signal here.** All 153 `llm_calls` rows of `baseline-v1.6.0.json` carry
`cached_tokens = null`, so `summary.cache_hit_rate` is `null` on this instrument
and `bench.summarize` (`devtools/bench.py:527-533`) has nothing to divide. A
rendered-prefix digest is not available either — no bench field carries one.
That is why the cache evidence is taken from `stats.time_to_first_token` when
the OpenAI-compatible endpoint populates it, why the rate that interprets it is
calibrated against a nonce-cold prefix rather than against an assumed cache
reset this instrument offers no verified way to perform, and why, when either
the field or the warm proof is missing, the summary-only fallback above —
`summary` only — is the whole answer rather than a latency ratio this instrument
cannot make conclusive.

---

## 6. Stage B — the reasoning policy (POL)

Stage B is written only after stage A has named a summary-shippable mechanism.
The vocabulary is REQ-V14-POL-01…-05's, unchanged; what follows states the
deltas and the exact shapes.

**REQ-V170-POL-01 (MUST) — exactly two new environment variables.**

```python
llm_reasoning_policy = _parse_choice(
    source, "LLM_REASONING_POLICY", "model-default",
    ("model-default", "off", "by-purpose"))
llm_reasoning_on_purposes = _parse_purposes(
    source, "LLM_REASONING_ON_PURPOSES", "tool-round")
```

onto `Config.llm_reasoning_policy: str = "model-default"` and
`Config.llm_reasoning_on_purposes: frozenset[str] = frozenset({"tool-round"})`.
`LLM_REASONING_ON_PURPOSES` is a comma-separated list of the tags of
REQ-V170-POL-02, whitespace-trimmed, order-insensitive; the empty string is
legal and means "none". An unknown policy value or an unknown tag raises
`ConfigError` naming the variable **and** the offending token. Both variables are
inert unless the policy is `by-purpose`, and both are added to `.env.example`
with their defaults and their permitted values. `.env.example`'s **active
line always carries the current shipped default** — `tool-round` until T12, the
selected treatment after it, and the bare `LLM_REASONING_ON_PURPOSES=` if C2
wins — because that is the literal `T-V170-POL-07` compares the shipped default
against. Beside it, as a permitted-value note and not as the active value, the
file spells out that an **empty value means none**, so the empty set — what
REQ-V170-BEN-05's C2 measures and what REQ-V170-POL-07 would ship if C2 wins —
has one unambiguous documented form. **Neither key is
ever written into `.env`**, and REQ-V170-PRE-01 item 9 proves at T0 that neither
is already there (REQ-V170-EC-04).

**The two literals displayed above are the pre-T12 compatibility defaults, and
they are the only ones this spec writes down.** `"model-default"` and
`frozenset({"tool-round"})` are what REQ-V170-EC-05 preserves so that stage C
measures v1.6.0's behaviour from an unprefixed tree; REQ-V170-POL-07's single
post-measurement selection commit replaces **both** with exactly the selected
candidate's process-environment treatment — for C2 that is `"off"` and
`frozenset()`. The `Config` field defaults, the two `_parse_*` calls shown here,
every parser example in this spec and `.env.example`'s documented values move
together in that one commit and nowhere else, and `T-V170-POL-07` pins them only
against each other, never against a literal of its own.

**REQ-V170-POL-02 (MUST) — the purpose tag is a pure function, in one place.**
The database `purpose` column keeps exactly `'agent'` and `'summary'` under its
`CHECK` constraint (storage.py:63) and is **not** changed. The reasoning tag is
derived at request time, has three values, and lives in `llm/base.py` as the
single source of truth — never a hand-copied literal list in `config.py`,
`agent.py`, `devtools/` or a test:

```python
REASONING_TAGS = ("tool-round", "final", "summary")

def reasoning_tag(purpose: str, request_tools: list[dict] | None) -> str:
    if purpose == "summary":
        return "summary"
    return "tool-round" if request_tools else "final"
```

Pure: no I/O, no global state, no `Config`. `request_tools` being `None` **or**
empty means the round exposed no tool, which is the `final` round
(`agent.py:322` passes `None`); `_ask_for_summary` passes `None` with
`purpose = "summary"` (agent.py:1085, `:1094`), and `summary` wins over the
tools test.

**REQ-V170-POL-03 (MUST) — resolution is a second pure function, and it
returns one frozen request object.** Two frozen dataclasses and one table live
in `llm/base.py` beside `reasoning_tag`; nothing else in the tree defines a
reasoning shape, and no provider ever looks a purpose up:

```python
# An immutable, recursive JSON representation. An object is a tuple of
# (key, value) tuples; a value is a scalar or, recursively, another such tuple.
# `object` is never used: it would readmit a dict, and a dict inside a frozen
# dataclass behind a MappingProxyType is still mutable shared state.
FrozenJSON = str | int | float | bool | None | tuple[tuple[str, "FrozenJSON"], ...]

@dataclass(frozen=True, slots=True)
class ReasoningMechanism:
    label: str                                     # "<letter>:<payload summary>"
    fields: tuple[tuple[str, FrozenJSON], ...] = ()   # → build_payload(reasoning_fields=…)
    message_patch: tuple[str, str] | None = None   # ("append_assistant"|"suffix_last_user", text)

@dataclass(frozen=True, slots=True)
class ReasoningRequest:
    value: str                                     # "on", "off" or "default"
    mechanism: ReasoningMechanism | None           # None ⇔ send nothing, patch nothing
    tag: str                                       # one of REASONING_TAGS

REASONING_DEFAULT = ReasoningRequest("default", None, "final")

# Keyed by TAG ALONE and holding OFF mechanisms only: stage A probes nothing but
# forms that switch reasoning off (REQ-V170-RSN-02), so no "on" entry could ever be
# filled. Values come from stage A's per-purpose table (REQ-V170-RSN-06), a known
# literal by the time stage B is written (REQ-V170-ORD-01).
REASONING_MECHANISMS: Mapping[str, ReasoningMechanism | None] = MappingProxyType({…})

def resolve_reasoning(
    policy: str,
    on_purposes: frozenset[str],
    tag: str,
    mechanisms: Mapping[str, ReasoningMechanism | None] = REASONING_MECHANISMS,
) -> ReasoningRequest
```

The resolved **value** is v1.4's: `model-default` → `"default"` for every tag;
`off` → `"off"` for every tag; `by-purpose` → `"on"` when `tag in on_purposes`
else `"off"`.

**The lookup rule, and it is deliberately asymmetric.** `"default"` returns
`ReasoningRequest("default", None, tag)`. `"on"` returns
`ReasoningRequest("on", None, tag)`, because retaining the provider's own
reasoning requires **no** disabling mechanism: nothing is looked up and no field
is sent. Only `"off"` looks the table up, at `mechanisms.get(tag)`; when that
entry is `None` or absent — no **off** mechanism exists for that purpose — the
request **degrades to `ReasoningRequest("default", None, tag)`** and the
degradation is recorded in the report and is never silent.

The asymmetry is forced by stage A, not chosen: REQ-V170-RSN-02 discovers only
mechanisms that switch reasoning **off**, so an `"on"` key could never be filled,
and a symmetric `(tag, value)` lookup would degrade every `by-purpose` "on" tag
to `"default"`, record the wrong value in REQ-V170-OBS-01's column, and put C1
and C3 (REQ-V170-BEN-05) on the wire as something other than their declared
treatments. `"default"` and `"on"` therefore both carry `mechanism = None` and
MUST send **no** reasoning field at all, so their request bodies stay
byte-identical to v1.6.0's — that is what makes REQ-V170-EC-05 true and what
lets `meta.generation_settings` stay locked and unchanged.

**The mechanism is frozen all the way down, not one level deep.** Candidate
**a**'s payload is nested — `{"chat_template_kwargs": {"enable_thinking":
false}}` — and storing that inner mapping as a `dict` would leave mutable state
inside a `frozen=True` dataclass behind a `MappingProxyType`: `REASONING_MECHANISMS`
would be frozen in name only, and any caller holding a produced payload could
mutate the global policy for every later call and every later test. So the whole
value is `FrozenJSON`, and candidate **a** is stored as

```python
ReasoningMechanism("a:chat_template_kwargs.enable_thinking=false",
                   fields=(("chat_template_kwargs",
                            (("enable_thinking", False),)),))
```

with **no `dict` and no `list` anywhere in the table**. A single helper in
`llm/base.py`, `json_fields(fields: tuple[tuple[str, FrozenJSON], ...]) -> dict`,
converts a mechanism's fields into **fresh dictionaries at every level** on
**every** call — a new `dict` per invocation, never a cached or shared one, and
never `copy.copy`. It is the only bridge from the frozen table to a wire
payload, and REQ-V170-POL-05's `lmstudio` client is its only caller. A mechanism
whose `fields` contain a `dict`, a `list` or a `set` is a defect
`T-V170-POL-05` catches.

The function is pure: no I/O, no global state beyond the frozen default table,
no `Config`. It is the **only** place a policy becomes a wire treatment, and the
one object it returns is what travels: `value` is what the OBS columns record,
`mechanism` is what a provider applies, and `tag` is what a failover forwards
unchanged. `MappingProxyType` is `types.MappingProxyType` from the stdlib
(REQ-V170-NG-06).

**REQ-V170-POL-04 (MUST) — one keyword-only parameter, carried through every
site.** `complete()` gains exactly **one** reasoning parameter,
`reasoning: ReasoningRequest = REASONING_DEFAULT` — the whole frozen object of
REQ-V170-POL-03, never a bare string and never a second `reasoning_tag`
parameter — in **five** definitions, and it is forwarded at **five**
invocations. `timeout_s` (REQ-V170-SUM-03) is the **second** keyword-only
parameter at every one of those sites:

| kind | site |
|---|---|
| definition | `llm/base.py:67` (`LLMClient` Protocol) |
| definition | `llm/lmstudio.py:35` |
| definition | `llm/openrouter.py:72` |
| definition | `llm/failover.py:50` |
| definition | `bot.py:1071` (`_SelftestLLM`, the offline double gate 4 drives through `agent.run_agent` — without it `--selftest` raises `TypeError`) |
| invocation | `llm/failover.py:60` (active client) |
| invocation | `llm/failover.py:83` (inside `_try_other` — the site that gets forgotten) |
| invocation | `agent.py:335` (the agent loop) |
| invocation | `agent.py:1094` (the summary path) |
| invocation | `devtools/bench.py:2186` (the warm-up probe at `max_tokens=1`) |

`_try_other` (llm/failover.py:73) carries the `ReasoningRequest` as a
positional through its own signature, exactly as it already carries
`max_tokens`, and forwards it **unchanged** — the same `value`, the same
`mechanism`, the same `tag` reach the secondary provider. That single forwarding
is the whole answer to "does the treatment survive a failover", and it is why
the tag lives on the request object rather than in a parameter of its own. The
bench warm-up probe passes the defaults **explicitly**, so a future signature
change cannot silently give the probe a different treatment from the run it
warms up. The mutation `v170-failover-drops-reasoning` removes the forwarding at
`llm/failover.py:83` and MUST be killed by `T-V170-POL-04`.

**Measured constraint, recorded rather than engineered around.**
`llm/failover.py` exposes no per-attempt seam of any kind (whole file read at
`054b103`: `complete` at `:50-71` and `_try_other` at `:73-94` call the client
and either return or raise, with no callback, no observer and no hook), so a
failover cannot re-resolve a mechanism for the provider that actually answers.
`REASONING_MECHANISMS` describes the **LM Studio** forms; `openrouter` ignores
`request.mechanism` entirely and emits its own documented form from
`request.value` (REQ-V170-POL-05). No measured path of this release ever mixes
the two: REQ-V170-BEN-02 requires `LLM_FAILOVER == "off"` on both sides of every
compared pair, and REQ-V170-NG-08 forbids any live OpenRouter call. The report
states this constraint; nothing in the code enforces it, and inventing an
attempt-level seam to enforce it is out of scope.

The agent loop resolves once per request from
`reasoning_tag(purpose, request_tools)`; `_ask_for_summary` resolves from
`reasoning_tag("summary", None)`, except where REQ-V170-SUM-04's rescue retry
overrides it.

**REQ-V170-POL-05 (MUST) — the provider forms, applied from `mechanism` alone.**
`resolve_reasoning` is shared; the request shape is not. **A provider never
reads `request.tag` and never consults `REASONING_MECHANISMS`** — the per-purpose
lookup happened once, in the pure function, and what reaches the client is
already provider-ready.

| provider | what it applies |
|---|---|
| `lmstudio` | `request.mechanism` and nothing else. `mechanism.fields` become `build_payload(reasoning_fields=json_fields(mechanism.fields))` — freshly built dictionaries at every nesting level, per call (REQ-V170-POL-03); `mechanism.message_patch`, when present, is applied to a **copy** of the caller's message list — `("append_assistant", text)` appends `{"role": "assistant", "content": text}` as the last element (candidate **c**), `("suffix_last_user", text)` appends `text` to the last user message's content (candidate **d**). `mechanism is None` → nothing added, nothing patched |
| `openrouter` | `request.value` and nothing else: `"off"` → `"reasoning": {"enabled": false}` as a top-level key, subject to PRE-03's VERIFY; `"on"` and `"default"` → nothing added, i.e. the provider default. It ignores `request.mechanism`, whose forms are LM Studio's |

Because the off-mechanism lookup is per **tag** inside `resolve_reasoning`, a mechanism
that ships only for `summary` and not for the agent tags needs no provider-side
branch at all: the agent rounds simply receive `mechanism = None`.

Neither form may be written into the system prompt or into the `tools` JSON
under any policy — that is REQ-V14-POL-05 item 1, and it is also why
`meta.prompt_tools_sha256` stays byte-identical to the baseline's
`748fa855…6500e3`. `T-V170-POL-05` asserts both.

**REQ-V170-POL-06 (MUST) — `build_payload` learns one optional argument.**
`build_payload(..., *, reasoning_fields: dict | None = None)`: when not `None`
its items are merged into the payload **after** the five existing keys and after
the `tools`/`tool_choice` branch, so a mechanism can never overwrite `model`,
`messages`, `temperature`, `max_tokens`, `stream`, `tools` or `tool_choice`. A
`reasoning_fields` mapping whose keys collide with any of those seven raises
`ValueError` naming the key. Candidate **c** and candidate **d** are **not**
`reasoning_fields`: they arrive as `ReasoningMechanism.message_patch`
(REQ-V170-POL-05) and are applied by the client before `build_payload` is
called, on a **copy** of the list the caller passed — `T-V170-POL-06` asserts
the caller's list is not mutated.

**REQ-V170-POL-07 (MUST) — the shipped default is decided by stage C, and it
lands in one narrowly defined commit.** `LLM_REASONING_POLICY`'s shipped default
and, when it is `by-purpose`, `LLM_REASONING_ON_PURPOSES`'s shipped default, are
set to exactly the process-environment treatment the selected candidate
(REQ-V170-BEN-05's cheapest quality-passing one) was run with, after the last
candidate run, in the **single post-measurement selection commit** of
REQ-V170-ACC-03. The treatment is read from the candidate's prefix, which always
carries **both** variables (REQ-V170-BEN-04): if C2 is selected the shipped
defaults become `"off"` and `frozenset()` — the explicit empty value, never an
inherited one — and `.env.example`'s `LLM_REASONING_ON_PURPOSES=` line is the
documented echo. REQ-V170-PRE-01 item 9's proof that neither key is present in
`.env` is what makes this flip reach the deployed bot at all; without it the
file would override the changed source literal and the measured treatment would
ship in name only.

**That commit exists only when a quality-passing candidate exists**
(REQ-V170-BEN-06). It changes **the two policy default literals in `config.py`,
`pyproject.toml`'s `project.version` from `1.6.0` to `1.7.0` (REQ-V170-VER-01),
and nothing else in the source, the tests or the configuration**, together with
the documentation echoes of those literals and of the version in `.env.example`,
`README.md` and `AGENTS.md`, which are the documentation-only corrections
REQ-V170-ACC-03 already permits. The version bump rides **here**, in this one
commit, rather than in T8, because REQ-V170-BEN-07 and REQ-V170-RSN-06 forbid it
on four branches and REQ-V170-ACC-03's freeze would forbid reverting it after
the first candidate; the exhaustive allowed-file list of the selection commit is
therefore `config.py`, `pyproject.toml`, `.env.example`, `README.md`,
`AGENTS.md` — five files, no more. Any other source, test or config difference
**voids stage C**.

**When no selection commit is made.** On the stage-A STOP (REQ-V170-RSN-06), on
the instrument STOP (REQ-V170-BEN-01), on `EXIT_NOT_COMPARABLE` that cannot be
resolved, and on the no-quality-passing-candidate verdict of REQ-V170-BEN-07,
T12 is **skipped**: the shipped defaults stay `model-default` /
`{"tool-round"}`, `pyproject.toml` stays at `1.6.0`, the failure report is
finalised, and no tag is created (REQ-V170-ORD-01).
The change is safe for the measurement because REQ-V170-BEN-02 puts both fields
in `CONFIG_HASH_EXCLUDED` and neither is a locked meta field — but safe is
**proved, not asserted**: `T-V170-ACC-03` proves the equivalence offline and
REQ-V170-ACC-03's candidate-metadata check records it against the selected
candidate's `meta.reasoning`. Exactly **one** test may pin the literal —
`T-V170-POL-07`, which compares the shipped defaults with the values
`.env.example` documents and therefore needs no edit when they move. The report
states that the default was flipped after measurement, naming the candidate.

---

## 7. What the policy records (OBS)

**REQ-V170-OBS-01 (MUST) — two additive columns, schema 4 → 5.** `llm_calls`
gains, appended to `storage.LLM_CALL_COLUMNS` after `span_id`:

| column | type | value |
|---|---|---|
| `reasoning_requested` | `TEXT` | `'on'`, `'off'` or `'default'` — `ReasoningRequest.value`, the value REQ-V170-POL-03 resolved. It records the **resolution**, not the wire form: `'on'` and `'default'` send no reasoning field at all, and only `'off'` carries a mechanism |
| `reasoning_honored` | `INTEGER` | `1`, `0` or `NULL` |

`reasoning_honored` is **three-valued, and `NULL` means "no evidence", never
"honored"**. Evaluated in this order:

1. `reasoning_requested` is `'default'`, or the call failed before a response →
   `NULL`. Nothing was asked for, or nothing came back.
2. reasoning **tokens are unavailable** — `usage.completion_tokens_details.
   reasoning_tokens` absent or `NULL` — **and** reasoning **chars are 0** →
   `NULL`. A provider that reports no reasoning usage and emits no visible
   `<think>` text has supplied no evidence in either direction, and reading that
   silence as success would let production metrics report policy compliance by
   construction. This release specifies **no** per-row fallback that could
   supply evidence in this case, so the `NULL` is unconditional at row level:
   REQ-V14-RSN-03's 20 % completion-token-and-cost rule is stage-A **pair**
   evidence over two whole runs (REQ-V170-RSN-03) and is never applied to a
   single row.
3. otherwise the truth table applies over the available positive-or-zero
   evidence: `'off'` → `1` when both are 0, else `0`; `'on'` → `1` when either
   is positive, else `0`.

This is exactly REQ-V170-RSN-03's own position — "a provider that reports
neither is not proof of anything" — carried into the column, and it is why
`NULL` may never be read as `0` anywhere downstream. The vocabulary is
REQ-V14-OBS-01's, unchanged.

**No column carries the tag.** `ReasoningRequest.tag` is already recoverable
from the row: `reasoning_tag(purpose, tools_exposed)` is exactly REQ-V170-POL-02's
own rule with the stored `tools_exposed > 0` standing in for a non-empty tools
list, and `purpose` and `tools_exposed` are both existing columns. That is why
the `CHECK (purpose IN ('agent','summary'))` constraint is untouched
(REQ-V170-NG-07) and why the migration adds two columns rather than three.

`SCHEMA_VERSION` becomes **5**; `_MIGRATION_4_TO_5` adds the two columns with
`ALTER TABLE llm_calls ADD COLUMN`; the accepted tuple at `storage.py:289`
becomes `(1, 2, 3, 4, SCHEMA_VERSION)`; the existing chain is extended so a
database at 1, 2, 3 or 4 reaches 5 in one `init_schema` call, and re-running
`init_schema` changes nothing. Pre-existing rows survive with `NULL` in both
columns. `_log_row("llm_call", LLM_CALL_COLUMNS, …)` (storage.py:572) picks the
two up by construction, so the structured log line and the row stay in bijection
(REQ-V13-OBS-06). Note for the reader, not a change: `_MIGRATION_2_TO_3`
(storage.py:195) is already unreferenced dead code — it is **left in place** and
recorded in the report, not deleted (REQ-V170-NG-14).

**REQ-V170-OBS-02 (MUST) — one span attribute.** `tracing.py`'s
`_TG_AGENT_ATTRIBUTE_KEYS` (`:65-80`) gains exactly one member,
`tg_agent.reasoning.requested`, carrying `ReasoningRequest.value` — the same
three-value string the column stores. No second key is added: the honored verdict is computed from
`gen_ai.usage.reasoning.output_tokens`, which the span already carries, under
REQ-V170-OBS-01's own three-valued rule — an absent attribute is *unknown*, and
a consumer that reads it as zero reproduces exactly the defect that rule exists
to prevent.
`set_attribute` rejects an unlisted key (`T-V160-TRC-09`), so the addition is
what makes the write legal.

**REQ-V170-OBS-03 (MUST) — one row per `llm.complete` invocation, through the
existing seam.** Both columns and the span attribute are written for **every**
LLM invocation — agent rounds, the final round, the summary attempt, its
truncation retry and its JSON-repair call — through `_record_llm_call`
(agent.py:830-848) and nowhere else; no second write path is created. A call that
raised before a response records its `reasoning_requested` and `NULL` honored.

**A failover attempt is not a row of its own, and that is a measured
constraint, not an omission.** `_record_llm_call` wraps exactly one
`llm.complete(...)` call (agent.py:335, agent.py:1094). When that client is
`FailoverLLMClient`, the failed primary attempt and the successful secondary
attempt both happen *inside* that single invocation, and the wrapper offers no
seam that could report them separately — the whole file was read at `054b103`:
`complete` (`llm/failover.py:50-71`) and `_try_other` (`:73-94`) call a client
and either return or raise, with no callback, no observer, no hook and no
attempt counter the caller can see. The row therefore describes the **logical
call**, and its `provider` and `model` name the client that actually served it,
because `_record_llm_call` reads `describe()` *after* the invocation for exactly
this reason (agent.py:859 and the function's own docstring). Inventing an
attempt-level observer is REQ-V170-NG-15.

The existing per-purpose aggregate `metrics.usage_by(group="purpose")` and its
`reasoning_share` (`metrics.py:397-416`) are the whole reporting surface: **no
new dashboard page, no new API endpoint and no new metrics function**
(REQ-V170-NG-04).

---

## 8. The summary wall-clock budget (SUM)

The concrete defect: in `baseline-v1.6.0`, S18 repeat 3 spent
`latency_ms = 205314` on a summary attempt that returned
`finish_reason = "length"` with `completion_tokens = 511` of which
`reasoning_tokens = 511` — the entire budget on hidden reasoning — and then
spent a **further** `latency_ms = 600089` on REQ-V160-TQ-01's retry, which ended
`error_kind = "transport"` at exactly `LLM_TIMEOUT_S = 600 000 ms`. The summary
path can therefore consume `LLM_TIMEOUT_S` once per attempt, not once in total,
because `_ask_for_summary` calls `llm.complete(messages, None,
max_tokens=max_tokens)` (agent.py:1094) with no timeout of its own and the
client's fixed `self.timeout_s` applies to each request independently
(`llm/lmstudio.py:52`, `llm/base.py:250`).

**REQ-V170-SUM-01 (MUST) — one budget for the whole path.**
`summarize_conversation` (agent.py:1022-1030) gains two keyword-only parameters:

```python
budget_s: float | None = None,
clock: Callable[[], float] = time.monotonic,
```

`budget_s is None` means today's behaviour exactly, so every existing caller,
fake and test is unaffected (REQ-V170-EC-05). `bot.py`'s two call sites
(`:730-734` in `_handle_new`, `:753-755` in `_handle_summary`) each add
`budget_s=cfg.llm_timeout_s` and change in no other way. The deadline is
`clock() + budget_s`, taken **once**, **before attempt 1 is issued**, and it
covers every request the path can make: attempt 1 at `SUMMARY_MAX_TOKENS`, and
then — the two branches being mutually exclusive (agent.py:1052-1062) — either
the truncation retry at `retry_max_tokens` or the JSON-repair call. Attempt 1 is
inside the budget, not outside it: the deadline is not "the budget for the
retries", it is the budget for the whole path (REQ-V170-SUM-03). `clock` is injectable so §14's
tests use a fake clock and make no live call (REQ-V170-TST-02).

**REQ-V170-SUM-02 (MUST) — the floor, and what happens below it.** A module
constant in `agent.py`, beside `SUMMARY_MAX_TOKENS`:

```python
SUMMARY_BUDGET_FLOOR_S = 30.0
```

It is a module constant and **not** a `Config` field and **not** a member of
`bench.constants()`: `config_sha256` and `meta.constants` are both locked meta
fields, and adding it to either would make every candidate non-comparable with
the baseline (REQ-V170-BEN-02).

Before **every** request the remaining budget is `deadline - clock()`, and no
request is issued when it is **non-positive** (REQ-V170-SUM-03). Before each
request **after the first** a second, stricter condition applies: when the
remaining budget is **below** `SUMMARY_BUDGET_FLOOR_S`, that request is **not
issued** — the floor is the binding condition for the later requests, the
non-positive rule the binding one for attempt 1. The turn then completes exactly as REQ-V160-TQ-01 item 3
already specifies — without a summary, with no exception escaping to the user
turn — and the outcome is recorded: an `llm_calls` row for the skipped request is
**not** written (no request was made, and a row must describe a request), and
instead the existing `log.warning` seam emits one redacted line naming the
elapsed and remaining seconds. `summarize_conversation` returns `None`.

**REQ-V170-SUM-03 (MUST) — every request's HTTP timeout is the remaining
budget, attempt 1 included.** `complete()` gains a second keyword-only
parameter, `timeout_s: float | None = None`, in the same five definitions and
forwarded at the same five invocations as REQ-V170-POL-04's. `None` means "use
the client's own `self.timeout_s`", which is today's behaviour and what every
caller but the summary path passes. `_ask_for_summary` gains
`timeout_s: float | None = None` and forwards it.

When `budget_s is not None`, `summarize_conversation` passes

```
timeout_s = max(0.0, deadline - clock())
```

to **every** request it issues, attempt 1 included, and **issues no request when
the remaining time is non-positive**. Attempt 1 does **not** pass `None`, and
the earlier reasoning that it could — "the whole budget is available, so the
client's own timeout is already right" — is **false whenever `budget_s` is
smaller than the client's timeout**, which the public signature explicitly
permits and `N5` explicitly exercises: `budget_s = 10` against a client
configured at `LLM_TIMEOUT_S = 600` would let the very first request run 600
seconds and blow the whole path's budget by a factor of sixty. No `min(...)`
against `self.timeout_s` is applied or implied — the client caps nothing, and
the remaining budget is by definition never larger than `budget_s`. The floor of
REQ-V170-SUM-02 stays the binding extra condition for the requests after the
first. The mutation `v170-summary-retry-ignores-budget` makes the retry pass
`None` and MUST be killed by `T-V170-SUM-03`.

**REQ-V170-SUM-04 (MUST) — the rescue retry runs with reasoning forced off.**
When a summary-shippable mechanism exists (REQ-V170-RSN-06) the truncation retry
and the JSON-repair call are issued with a `ReasoningRequest` whose `value` is
`"off"` — resolved by calling `resolve_reasoning("off", frozenset(), "summary")`,
never by hand-building the object — **regardless of `LLM_REASONING_POLICY`**. Rationale, from the evidence above: the retry exists
precisely because the first attempt spent its whole budget on reasoning, so
repeating the attempt with reasoning enabled is the one configuration known to
fail. Attempt 1 keeps the policy's own resolution. When no summary-shippable
mechanism exists this requirement is unreachable, because REQ-V170-RSN-06 has
already stopped the run. `T-V170-SUM-04` asserts the retry's resolved value is
`"off"` under all three policies including `model-default`.

**REQ-V170-SUM-05 (MUST) — `_check_timeout_budget` is amended, not removed.**
Its formula, its constants (`LATENCY_INTERCEPT_S = 21.1`,
`LATENCY_PER_TOKEN_S = 0.093`, config.py:50-51) and its message are unchanged,
and it keeps being called with
`max(llm_max_tokens, llm_summary_max_tokens)` (config.py:287). One **additional**
check is appended in `load_config`, after it: the summary path's own floor must
fit inside the budget it is given, i.e.

```
llm_timeout_s >= LATENCY_INTERCEPT_S + LATENCY_PER_TOKEN_S * llm_summary_max_tokens
                 + SUMMARY_BUDGET_FLOOR_S
```

so that a configuration in which the retry could never be attempted is refused at
startup rather than discovered in production. The `ConfigError` names
`LLM_TIMEOUT_S`, `LLM_SUMMARY_MAX_TOKENS` and the floor. **At the 1.7.0
instrument this is satisfied with room to spare** and no default moves:
`21.1 + 0.093 × 1536 + 30 = 193.9 s ≤ 600`, and the pre-existing check is
`21.1 + 0.093 × 4096 = 402.028 s ≤ 600`. At shipped defaults
(`LLM_TIMEOUT_S = 240`, `LLM_SUMMARY_MAX_TOKENS = 1536`) it is
`193.9 ≤ 240` — green, so REQ-V170-EC-05 holds and no existing deployment
breaks. The mutation `v170-summary-floor-check-removed` deletes the check and
MUST be killed by `T-V170-SUM-05`.

---

## 9. Stage C — candidates, comparability and the gates (BEN)

**REQ-V170-BEN-01 (MUST) — same instrument, no fresh baseline; a mismatch
STOPS.** `docs/assets/bench/baseline-v1.6.0.json` **is** the baseline: not
re-recorded, not regenerated, not superseded — a candidate measured against a
baseline recorded in the same run proves nothing, which is why REQ-V160-NG-02
handed this gate here. Six instrument values MUST match, and REQ-V170-PRE-04
items 1–6 establish **every one of them before the first live inference of the
run** — its own preflight included, so a mismatch costs no tokens at all:

| field | required value |
|---|---|
| `meta.lmstudio_version` | `"Bionic v1.1.1"` |
| `meta.served_model_id` | `"qwen/qwen3.8-27b"` — **exact string equality** with the uniquely selected served id and with `cfg.lmstudio_model`; a substring match, or two entries matching, is a STOP (REQ-V170-PRE-04 item 3) |
| `meta.lmstudio_context_length` | `42496` |
| `.env` `LLM_MAX_TOKENS` | `4096` (proved by REQ-V170-PRE-04's grep) |
| `.env` `LLM_TIMEOUT_S` | `600` (same) |
| `meta.obs_capture_content` | `false` — `cfg.obs_capture_content is False` **and** the metadata producer proved to emit `false` (REQ-V170-PRE-04 item 6) |

Any mismatch is a **STOP with a report**, not an adjustment: re-baselining costs
93 minutes of inference and is the operator's decision. What merges depends on
**where** the mismatch surfaces, and the two cases are not the same:

- at the **live preflight (T1)**, where these values are first established, not
  a line of §§6–8 exists yet — nothing merges, and the run delivers the
  preflight record, the report and the STOP verdict;
- if it surfaces later instead — at **T11**, or through REQ-V170-BEN-07's
  `EXIT_NOT_COMPARABLE` routing back here — the code of §§6–8 **still merges**,
  having already passed T10's gates.

In both cases `pyproject.toml` is **not** bumped — T12 is skipped, so the version
literal is never touched — and **no tag is created**. The first case is a
`T-STOP` branch (REQ-V170-ORD-02); the second finalises through T13 and T14 with
the failure report, since the code has already merged.

Three consequences of the locked fields, to be stated in the report as
constraints the run obeyed:

1. `meta.scenarios_sha256` is locked at `f2b6c41c…1972`, so
   `devtools/bench_scenarios.py` is **frozen** — no scenario, ceiling or turn
   changes, and S15/S18 re-enter the gate through REQ-V170-BEN-06's acceptance
   text, never through code;
2. `meta.prompt_tools_sha256` is locked at `748fa855…6500e3`, so the system
   prompt and the exposed tool schema are frozen and any "do not think"
   instruction inside either is a **NON-GOAL** (REQ-V170-NG-02);
3. `meta.generation_settings` is locked and stays the sampling literal
   `devtools/bench.py:2262-2275` produces (`agent.max_tokens = 4096`,
   `summary_initial 512`, `summary_retry 1536`, `temperature 0`) — the reasoning
   mechanism is not a sampling setting and is recorded in REQ-V170-BEN-03's
   block instead.

**REQ-V170-BEN-02 (MUST) — comparability must accept a treatment-only pair, and
today it accepts nothing at all.** Measured against the shipped code,
`bench.comparability(baseline-v1.6.0, baseline-v1.6.0)` returns
`"env_flags.HISTORY_TOOL_STUB must be null on the baseline side"`. The clause at
`devtools/bench.py:1451-1460` requires each `STAGE_C_KEYS` entry to be `null` on
the baseline side — true of v1.3's stage-C worktree contract, false of
`baseline-v1.6.0`, whose `env_flags` carry `HISTORY_TOOL_STUB: "on"`,
`EXEC_OUTPUT_DEFAULT_CHARS: 1500`, `FETCH_INLINE_DEFAULT_CHARS: 5000`.
**`report --gate` against this baseline is impossible until that clause is
amended**, so this release's cost gate is unreachable without this requirement.

The clause is replaced by an **equality** rule, which is what "same instrument"
means:

- for each `key` in `STAGE_C_KEYS`, `base_flags.get(key) == cand_flags.get(key)`,
  else `f"env_flags.{key} differs"`; `null` on one side and a value on the other
  is a difference, as it should be;
- the `LLM_FAILOVER == "off"`, `LLM_SUMMARY_MODEL in ("", None)` and
  `LLM_MAX_TOKENS` equality guards are **kept verbatim**;
- `LLM_REASONING_POLICY` and `LLM_REASONING_ON_PURPOSES` are deliberately **not**
  compared: they are the treatment, and `env_flags` is not a locked meta field
  (`devtools/bench.py:149-163`), so a pair differing only in them compares clean.

`llm_reasoning_policy` and `llm_reasoning_on_purposes` additionally join
`CONFIG_HASH_EXCLUDED` (devtools/bench.py:140-147), which keeps the **locked**
`config_sha256` stable across the treatment. `T-V170-BEN-02` asserts all four
properties: the baseline compares clean with itself; a treatment-only pair
compares clean; a pair whose `generation_settings` differ is **still** refused;
a pair whose `HISTORY_TOOL_STUB` differs is refused.

**REQ-V170-BEN-03 (MUST) — a new, unlocked `meta.reasoning` block.** `meta`
gains one key, `reasoning`, and it does **not** join `LOCKED_META_FIELDS`:

```json
{"policy": "by-purpose",
 "on_purposes": ["tool-round"],
 "mechanism": {"tool-round": "b:reasoning.enabled=false",
               "final": "b:reasoning.enabled=false",
               "summary": "c:assistant-prefill"},
 "provider_form": "lmstudio"}
```

`policy` and `on_purposes` come from `Config` (`on_purposes` serialised as a
**sorted list**, so equal sets serialise equally, the empty set serialising as
`[]` — which is exactly what REQ-V170-BEN-05's C2 records, never an absent key
and never a value inherited from `.env`); `mechanism` is stage A's
per-purpose **off-mechanism** table — what REQ-V170-POL-03 would apply if a
purpose resolved to `"off"`, not what each call actually sent, so the example
above stays truthful on C1, where `tool-round` resolves to `"on"` and sends
nothing at all; each value a short stable label `<letter>:<payload summary>`
and `null` for a purpose with no mechanism; `provider_form` names the provider
whose form was used. On a `model-default` run **produced by this release** the
block is present with empty values, never omitted.

**Schema compatibility, stated because the frozen baseline cannot carry any of
this.** `docs/assets/bench/baseline-v1.6.0.json` was recorded at `ca9c656`,
before these fields existed: measured at `054b103`, its `meta` has no
`reasoning` key and not one of its 153 `llm_calls` rows has
`reasoning_requested` or `reasoning_honored`. Therefore, for `bench_schema = 2`
documents:

- `meta.reasoning`, `llm_calls[].reasoning_requested` and
  `llm_calls[].reasoning_honored` are **optional additive** fields. The schema
  number does **not** move (REQ-V170-AMEND-01), and `check` already tolerates
  this by construction: `REQUIRED_LLM_ROW_KEYS` (`devtools/bench.py:190-196`) is
  a hand-written literal that does not gain the two columns, while the permitted
  set `LLM_ROW_KEYS` (`:172`) is derived from `storage.LLM_CALL_COLUMNS` and
  widens with the migration — so the baseline stays valid and a new-format
  candidate stays valid, with no edit to either constant;
- `comparability` treats an **absent** `meta.reasoning` on the baseline side as
  legacy metadata and returns no complaint for it. It is never synthesised,
  defaulted, back-filled or written into the baseline — the file is frozen
  (REQ-V170-NG-03) and any tool that rewrote it would void the gate;
- a **candidate** MUST carry `meta.reasoning`, and the earlier claim that "both
  sides of a pair always carry the same key set" does not hold and is not
  required to: `meta` is compared field by field against `LOCKED_META_FIELDS`,
  and `reasoning` is not among them.

Unlocked, it never blocks a comparison; present, it makes every candidate
self-describing.

**REQ-V170-BEN-04 (MUST) — the treatment is set by a process-environment prefix,
never by editing `.env`.** Every candidate command has the form

```bash
LLM_REASONING_POLICY=<policy> LLM_REASONING_ON_PURPOSES=<tags> \
  uv run --locked python devtools/bench.py run --tag <tag> \
  --repeats 3 --timeout-s 1800 --out .bench/<tag>/<tag>.json
```

`dotenv.load_dotenv(..., override=False)` at `config.py:202` means the prefix
wins over `.env`, so the file is untouched (REQ-V170-EC-04). **`--timeout-s
1800` is mandatory**: `meta.timeout_s` is a locked field and the baseline carries
`1800.0`; the default is 600 and a candidate run without the flag is
non-comparable no matter how good its numbers are. `--repeats 3` and no `--only`
are equally mandatory — `repeats` and `only` are both locked, and the baseline
carries `3` and `null`.

**Both variables appear in every candidate's prefix, `LLM_REASONING_ON_PURPOSES`
included and even when its value is empty.** C2's cell is the explicit
`LLM_REASONING_ON_PURPOSES=""`, not an omission (REQ-V170-BEN-05): an omitted key
would let `.env` or the source default decide half the treatment, which is
precisely what the prefix exists to prevent, and would leave
`meta.reasoning.on_purposes` and REQ-V170-POL-07's shipped default inherited
rather than determined. The report quotes each candidate's prefix in full, both
assignments included.

**Aborts, and the merge.** `run_bench` breaks **both** the repeat loop and the
scenario loop on the first aborted run (devtools/bench.py:756-764), sets
`meta.aborted`, and `_validate` then refuses the document with
`EXIT_NOT_COMPARABLE` (`:1147`) — which is why the v1.6.0 baseline needed
**five** invocations (`report-v1.6.0.md`, "resume"). A candidate may therefore be
assembled the same way, under the rules **v1.6.0's own T16** used and no others: identical clean
tree throughout (`git status --porcelain` empty), one shared `--tag`, `--only`
narrowing the parts, each part copied out of `.bench/` immediately, isolated
repeats relabelled `1/2/3`, the merged `runs` list re-summarised through
`bench.summarize()` rather than by hand, `meta.only` set to `null`,
`meta.aborted` absent, every `LOCKED_META_FIELDS` entry except `repeats` and
`only` verified byte-identical across all parts, and `bench.py check <merged>`
exiting 0. The report states, per candidate, how many invocations it took and
why.

**REQ-V170-BEN-05 (MUST) — at most three candidate runs, in this order.** Full
catalogue, 3 repeats, same instrument. No parameter sweep, no re-tuning between
runs, no fourth candidate.

| # | tag | `LLM_REASONING_POLICY` | `LLM_REASONING_ON_PURPOSES` | why |
|---|---|---|---|---|
| **C1** | `cand-v170-by-purpose-tool` | `by-purpose` | `tool-round` | the expected winner: reasoning kept where tool selection benefits from it, off for the final answer and off for the summary — the two purposes S15 and S18 died on |
| **C2** | `cand-v170-off` | `off` | `""` — an **explicit empty** process-environment value, serialised `[]` | the maximum saving, and the only way to establish that C1 is the cheaper of the two — which is why it is not conditional |
| **C3** | `cand-v170-by-purpose-tool-final` | `by-purpose` | `tool-round,final` | the fallback: summary-only off |

**C2 sets the second variable explicitly, and that is deliberate.** Under
`policy = off` the purpose set is inert on the wire (REQ-V170-POL-01), so
`LLM_REASONING_ON_PURPOSES=""` changes not one byte of any request; what it fixes
is the **record and the ship**. `meta.reasoning.on_purposes` serialises as `[]`
rather than as whatever `.env` or the source default happened to hold
(REQ-V170-BEN-03), and REQ-V170-POL-07's shipped default, should C2 be selected,
is the determined `frozenset()` documented in `.env.example` as
`LLM_REASONING_ON_PURPOSES=`. An `*(unset)*` cell left all three of those —
prefix, metadata and shipped default — inherited, and `T-V170-ACC-03`'s
"exactly one candidate matches" proof with them.

**C3 is skipped when it is C1 on the wire.** Under REQ-V170-RSN-07's
summary-only fallback, whichever of its two triggers fired — the TTFT field
absent on the harness's route, or a cold calibration's warm proof failing — and
in any other outcome leaving no `final` off mechanism — C1 resolves `final` to `"off"`, finds no mechanism and degrades to
`"default"` (REQ-V170-POL-03), while C3 resolves `final` to `"on"`, which also
sends no field: the two treatments are then **byte-identical on every call**,
and running C3 would spend a full 3-repeat run for no information. In that case
C3 is **not run**, the report records the resolved treatments side by side as
the reason, and the budget of three candidate runs is not otherwise re-spent.
The catalogue is still not swept and no fourth candidate exists.

**The sequence, which is not a judgement call.** Run C1, then C2
unconditionally. Run C3 only if neither C1 nor C2 passes quality **and** C3's
resolved treatment differs from C1's. Among all
candidates actually run that pass quality, ship the lowest `C_conservative`,
breaking ties by `C_plain`, then catalogue order.

That is also the definition of **"cheapest"** wherever this spec uses the word:
lowest `C_conservative`, ties broken by `C_plain`, ties broken again by
catalogue order (C1 before C2 before C3). Both figures are the shipped
formulas of `devtools/bench.py:1530-1549` (REQ-V170-BEN-07), computed against
the same baseline. The earlier wording — C2 "run only if C1 misses the cost
gate, or as the cheaper of two quality-passing candidates" — was circular: C2
must be run before anyone can know which of the two is cheaper.

Each candidate's document is copied to `docs/assets/bench/<tag>.json` and
committed. A candidate whose merged document fails `bench.py check` is
re-assembled, not reinterpreted.

**REQ-V170-BEN-06 (MUST) — the quality gate, with S13…S18 blocking at 3/3.**
A candidate passes the quality gate when **all four** hold:

1. `success_rate(C) >= success_rate(B) - QUALITY_GATE_SLACK`, the shipped rule
   at `devtools/bench.py:1554` with `QUALITY_GATE_SLACK = 0.02` (`:229`);
2. no per-scenario regression, the shipped rule at `:1565-1573` — a scenario
   losing **two or more** repeats fails the gate;
3. **each of S13, S14, S15, S16, S17 and S18 succeeds 3 of 3** on the
   **candidate** side, S15 and S18 included. This supersedes v1.6.0's errata 3
   and 6, and — unlike the exemption it replaces — it is **executable, not
   acceptance text**. Item 2 alone cannot enforce it: the shipped per-scenario
   rule only fails a scenario that loses **two or more** repeats
   (`devtools/bench.py:1565-1573`), so a candidate with S15 or S18 at 2/3 would
   still exit 0, and a manual assertion in a report cannot safely control an
   autonomous PASS. `devtools/bench.py` therefore gains exactly one module
   constant, beside `COST_GATE_FACTOR` and `QUALITY_GATE_SLACK` (`:228-229`):

   ```python
   GATE_REQUIRED_FULL_SCENARIOS = ("S13", "S14", "S15", "S16", "S17", "S18")
   ```

   and `report --gate` **refuses PASS** unless, for every id in that tuple, the
   candidate's `summary.per_scenario[id]` reads `success == of == 3`; a missing
   id counts as a violation. A violation clears the quality verdict, appends one
   line naming **every** failing scenario with its `success/of`, and the command
   exits **1**. `devtools/bench_scenarios.py` is not touched — the catalogue
   stays frozen (REQ-V170-NG-01) and the rule lives entirely in the gate. The
   constant joins **neither** `bench.constants()` **nor** `REQUEST_DEFAULTS`,
   for REQ-V170-SUM-02's reason: `meta.constants` is a locked meta field and
   adding to it voids every baseline (REQ-V170-NG-05);
4. the candidate document carries no `meta.aborted`.

Item 3 is the one clause that can fail for a reason outside the treatment's
control, and the report says so: `baseline-v1.6.0` recorded S15 at 3/3
(212/413/393 s) and S18 at 2/3, and both failures were traced to the very
reasoning-budget variance this release removes. A candidate that still loses S15
or S18 has **not** demonstrated the fix, whatever its cost number says.

Ship the **cheapest** candidate that passes the quality gate, "cheapest"
being REQ-V170-BEN-05's definition — lowest `C_conservative`, ties by
`C_plain`, then catalogue order.

**REQ-V170-BEN-07 (MUST) — the cost gate and the verdict.** The formulas are the
shipped ones at `devtools/bench.py:1530-1549` and are not re-derived here:
`B_plain = Σcost_B / successes_B`, `C_plain = Σcost_C / successes_C`,
`C_conservative = (Σcost_C + failed_C × mean_ok_C) / successes_C`, all costs
recomputed at the **baseline's** price snapshot
(`reference:qwen/qwen3.8-27b`, input 0.42, output 3.0, cached 0.085 USD/Mtok).
The cost gate passes when `C_plain <= 0.70 × B_plain` **and**
`C_conservative <= 0.70 × B_plain`, with `COST_GATE_FACTOR = 0.70`
(`devtools/bench.py:228`). The final comparison is one command:

```bash
uv run --locked python devtools/bench.py report \
  --baseline docs/assets/bench/baseline-v1.6.0.json \
  --candidate docs/assets/bench/<shipped-tag>.json \
  --gate --out docs/reports/bench-v1.7.0.md
```

| outcome | meaning | what happens |
|---|---|---|
| **PASS** | the shipped candidate passes the quality gate **and** the cost gate; exit 0 | the release completes: T12 lands the selection commit, which is where `pyproject.toml` moves `1.6.0` → `1.7.0` (REQ-V170-POL-07, REQ-V170-VER-01), and the annotated tag `v1.7.0` is then created on the evidence-only commit (REQ-V170-VER-02) |
| **FAIL** | a quality-passing candidate exists but misses the cost gate; exit 1 | the code **still merges**: T12 runs, with the **cheapest** quality-passing candidate as the shipped default (REQ-V170-BEN-05's definition, REQ-V170-POL-07), and `pyproject.toml` **is** bumped to `1.7.0` inside that same selection commit. The run **STOPS before tagging**. No tag. The report states the shortfall as a number and the operator decides |
| **FAIL** | no candidate passes the quality gate | there is no candidate to select, so **T12 is skipped entirely**: the shipped default stays `model-default`, `pyproject.toml` stays at `1.6.0`, no tag, verdict `FAIL, cause: no reasoning policy satisfied the quality gate`. T13 and T14 still run and finalise the failure report |
| **exit 2** | `EXIT_NOT_COMPARABLE` | a **process** failure, never a verdict. Fix the comparability cause and re-run the comparison; if the cause is an instrument difference, REQ-V170-BEN-01's STOP applies. While it stands unresolved there is no comparable candidate and therefore no selection: **T12 is skipped**, `pyproject.toml` stays at `1.6.0`, no tag is created, and T13/T14 finalise the failure report naming the comparability message verbatim |

**REQ-V170-BEN-08 (MUST) — latency is reported, never gated.** For the baseline
and for each candidate the report carries, from the `spans` rows the documents
already contain (`bench_schema = 2`, REQ-V160-BEN-03): **p50 and p95 of
`chat`-span duration per purpose tag**, and **wall-clock per scenario** against
the baseline's. Nothing here is a gate and no threshold is introduced —
REQ-V160-GATE-05's precedent applies: a number that moves is reported as a
number, not fixed by demoting a gate. The baseline's own totals are the
comparison points: 54 runs, 53 successes, 93 m 16 s, $0.185776.

---

## 10. Carried items (CAR)

**REQ-V170-CAR-01 (MUST) — `--tag` is sanitised before any path is built.** The
v1.6.0 code review raised this as a 🟡 and it was waived, not fixed:
`devtools/bench.py:2323-2325` does `shutil.rmtree(BENCH_ROOT / arguments.tag,
ignore_errors=True)` with `arguments.tag` taken straight from `argparse`
(`:1959`), so `--tag ../../something` escapes `.bench/` and
`ignore_errors=True` hides the damage. The fix, applied **before** the path is
constructed and therefore before `_remove_run_dir` (`:1091`) and every other
`--tag`-derived path:

```python
_TAG_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
```

A `--tag` that fails the pattern, or that is exactly `.` or `..`, or that
contains `/` or `\` (already excluded by the pattern, asserted separately so the
intent survives a future edit), is refused with a message naming the flag and
the permitted charset, and `run` exits `EXIT_ERROR` **before** any filesystem
write. `T-V170-CAR-01` and the negative test `N7` cover it; the mutation
`v170-tag-sanitiser-removed` MUST be killed.

**REQ-V170-CAR-02 (MUST) — Appendix B's baseline scenario is refreshed.**
spec-v1.6.0's Appendix B `E13` asserts `each of S13…S18 succeeded 3 times out of
3` while its own errata 3 and 6 exempted S15 and S18 — the Gherkin was left
stale, deliberately and disclosedly, when the spec froze at the tag. Appendix B
`E9` of this spec is the corrected successor: it asserts the blocking 3/3 for all
six against a **candidate**, names the baseline as the fixed comparison side, and
carries the comparability and instrument preconditions REQ-V170-BEN-01 and -02
add. spec-v1.6.0's own text is **not** edited — it is a tagged historical record
(REQ-V170-NG-13).

The related documentation divergence is recorded, not repaired: spec-v1.6.0's
erratum 6 (`:1677`) still says S18's summary call "and its REQ-V160-TQ-01 retry
both returned `finish_reason="length"`", while `report-v1.6.0.md`'s prompt-101
correction establishes that only attempt 1 truncated and attempt 2 ended
`error_kind = "transport"` at 600 089 ms. §8's evidence uses the **report's**
figures.

---

## 11. Semantic versioning and the release (VER)

**REQ-V170-VER-01 (MUST) — a MINOR release, bumped in exactly one place.**
`pyproject.toml`'s `project.version` moves from `"1.6.0"` to `"1.7.0"` and
remains the single source of truth; `bot.py`'s `_read_version`
(REQ-V160-VER-01) reads it at call time, so `--version` prints
`tg-agent-bot 1.6.0` until the bump lands and `tg-agent-bot 1.7.0` after it.
MINOR is the right bump under
REQ-V160-VER-02's own table: new capability, two new environment variables, an
additive schema migration, no removed command and no incompatible semantics. The
version test compares the printed string against an independent `tomllib` read,
not a literal.

**The bump is conditional, and therefore it does not happen at T8.** It rides in
the **single post-measurement selection commit** of REQ-V170-POL-07 (T12), the
one commit that already exists only when a quality-passing candidate does, and
it is one of that commit's five permitted files. It lands only on the branches
REQ-V170-BEN-07 and REQ-V170-RSN-06 permit: **not** on the stage-A STOP, **not**
on the no-quality-passing-candidate branch, **not** on an unresolved
`EXIT_NOT_COMPARABLE`, and **not** on the instrument STOP of REQ-V170-BEN-01 —
each of those keeps `1.6.0` at the tip, skips T12 and finalises its failure
report without a tag. It **does** land on the cost-gate-FAIL branch, where the
code ships, a quality-passing candidate was selected, and only the tag is
withheld. Bumping at T8 instead would be unimplementable: T8 is before the
candidates, and REQ-V170-ACC-03's freeze permits no commit that could revert the
version afterwards.

**REQ-V170-VER-02 (MUST) — the tag is created last, on the evidence-only commit,
and only on PASS.** The order of REQ-V160-VER-04 is unchanged: T14 runs every
acceptance command against the final tree; the evidence-only commit lands,
touching `docs/reports/*` and nothing else, recording `<implementation-tip>`, the
replay output and the **intended** tag name `v1.7.0` — never a claim that the tag
already exists; then, and only then,

```bash
git tag -a v1.7.0 -m "tg-agent-bot 1.7.0 at <evidence-commit-sha>"
```

The tag is created **only** when REQ-V170-BEN-07's verdict is PASS. On the
cost-gate-FAIL branch the evidence-only commit still lands and still records the
verdict, the shortfall and the shipped default, and the run stops there with
`STOP before tagging — operator decides`. `v1.3`, `v1.3-baseline` and `v1.6.0`
are never moved or deleted, and nothing is pushed by the executor.

**REQ-V170-VER-03 (MUST) — naming.** Specs, reports and prompt slugs carry three
numbers: `docs/spec/spec-v1.7.0.md`, `docs/reports/report-v1.7.0.md`,
`docs/reports/tg-post-v1.7.0.md`, `docs/reports/bench-v1.7.0.md`,
`docs/prompts/NN-v170-*.md`. Existing two-number filenames are **not** renamed
(REQ-V170-NG-13).

---

## 12. Reporting (RPT)

**REQ-V170-RPT-01 (MUST) — the report carries the ledger row.** REQ-V170-EC-01
forbids the executor to write the lab-root `economics.md`, so
`docs/reports/report-v1.7.0.md` MUST contain a section **"Ledger row (paste into
`economics.md`)"** holding one fenced, ready-to-paste row matching the ledger's
column order exactly:

```
| Project | Ver | Date | Spec (tokens) | Prompts | First run | Bugs | Tokens ↑/↓ | Cost | Model | Harness |
```

`Ver` is **`1.7.0`**. The row uses the link form
`[tg-agent-bot](https://github.com/axyi/tg-agent-bot)` and, **at final
acceptance**, every cell is filled from this run's evidence — no `TBD`, no
placeholder. Before then the structurally complete row T0's skeleton carries
(REQ-V170-RPT-02) may hold provisional cells; `lint-docs` checks the shape, `E11`
checks the absence of placeholders, and only the second is a T14 assertion. "Spec (tokens)" carries both
the estimate and the measured byte count. The operator pastes it, never the
executor.

**REQ-V170-RPT-02 (MUST) — `lint-docs` is repointed, and this is why.**
`config/quality_gates.yaml:313` still reads `report_path:
docs/reports/report-v1.5.md`. It was never repointed for v1.6.0, so
REQ-V160-RPT-01's claim that "`checks.py lint-docs` enforces the section's
presence and the cell count" was **not true of `report-v1.6.0.md`** — the gate
was checking a two-release-old file. It becomes
`docs/reports/report-v1.7.0.md` in the **docs-and-version task (T8)**, together with
`T-V170-RPT-02` — deliberately **before** the candidate freeze, because
`config/quality_gates.yaml` is a config file and repointing it after the first
candidate run would violate REQ-V170-ACC-03. `_lint_report_ledger`
(`devtools/checks.py:1477-1495`) checks only that the file exists, holds a
"Ledger row (paste into …)" section, that the section holds a fenced block and
that the block's row has the header's `|` count — so the report skeleton T0
creates carries that section with a structurally complete fenced row from the
start, and its cells are filled in the report task. The absence of a placeholder
cell is asserted at final acceptance (`E11`), not by the gate. The report states
that the previous release's ledger row was unlinted. The `ledger_header` value
on the following line is unchanged. `T-V170-RPT-02` asserts the configured
`report_path` names this release's report.

**On a `T-STOP` branch the repoint has not happened**, because T1 and T3 both
exit before T8 and `T-STOP` permits no committed configuration change: the file
still names `docs/reports/report-v1.5.md` and `lint-docs` would check a
two-release-old report while claiming to check this one. REQ-V170-ORD-02 item 4
therefore changes **only** `lint-docs.report_path`, in the **working tree**,
runs the gate, restores the file and proves `git diff --
config/quality_gates.yaml` empty before the closing commit. No `--report-path`
option is added to `checks.py`: a source change on the one branch whose premise
is that no source changed would contradict the early-exit design.

**REQ-V170-RPT-03 (MUST) — the report.** Beyond the project standard,
`report-v1.7.0.md` carries:

1. the gates table — the six verbatim commands plus every gate of §13, with
   command, profile and exit code. **On a `T-STOP` branch gates 1–4 and 6 appear
   twice**: once with T0's exit codes and once with the fresh ones from the
   rerun against the finalised STOP tree (REQ-V170-ORD-02 item 5), and the three
   `N/A` rows carry their reasons;
2. the **measured** test count at HEAD before and after, against the 1016 floor,
   and the corrected `AGENTS.md` figure;
3. the mutation summary: `mutation-all` entry count (83 at v1.6.0), kills and
   wall clock, and the `mutation-v170` subset separately, with the
   **re-measured** timeouts and the arithmetic that produced them;
4. the committed spec's T0 `sha256`, unchanged at T14; the `.env` interaction
   record of REQ-V170-EC-04 naming each of the four permitted idioms actually
   used; the `--no-verify` attestation of REQ-V170-EC-09; `<base>`,
   `<implementation-tip>` and the `replay --range` output — the last two recorded
   by the evidence-only commit, not the provisional report;
5. per task, whether the RLM rule was applied and to what;
6. **Benchmark-affecting changes**: the two declared in REQ-V170-EC-06, plus any
   discovered, with the disposition of each, and EC-06's statement that the
   `AGENTS.md` before/after rule is **satisfied**, naming the pair and quoting
   the verdict;
7. **stage A**: the full pair table of REQ-V170-RSN-05, the per-purpose mechanism
   table of REQ-V170-RSN-06, the mixed-policy confirming pair of REQ-V170-RSN-07
   with check 1's two token figures against their two thresholds and, for check 2,
   the **cold-calibration record per member** — the two nonce-prefixed scratch
   TTFTs, their warm ratio against `0.35` and the rate derived from the first —
   followed by that member's predicted cold TTFT, measured final-round TTFT and
   their ratio against `0.35`; or, where check 2 was **unavailable**, which of
   its two triggers fired (the TTFT field absent on the harness's route, or the
   warm proof failing), the statement that RSN-07's summary-only fallback bound
   the run, that the confirming pair was never spent or was abandoned before
   either member ran, and that the agent tags shipped no mechanism; the resolved values of §3's **four** VERIFY markers with URLs,
   routes and dates; and the `git diff`-empty check after each candidate;
8. **stage C**: the six instrument values of REQ-V170-BEN-01 with their sources;
   per candidate, the tag, the treatment, the invocation count and why, the
   per-scenario successes with S13…S18 called out individually, tokens, cost and
   wall clock; the `comparability` result for each pair; the verdict block from
   `bench-v1.7.0.md`; and the latency table of REQ-V170-BEN-08;
9. the shipped default, the sentence that it was flipped **after** measurement
   (REQ-V170-POL-07), and REQ-V170-ACC-03's candidate-metadata check — the
   selected tag, its `meta.reasoning.policy` and `meta.reasoning.on_purposes`,
   and the final tree's unprefixed resolution beside them; the T0 record that
   neither policy key is present in `.env` (REQ-V170-PRE-01 item 9), which is
   what makes that resolution binding on the deployed bot; and, when T12 ran,
   the output of REQ-V170-REV-01 item 8's automated allowlist check —
   `git diff --name-only <T11-tip>..<T12-tip>` and its verdict;
10. the **intended** tag name `v1.7.0`, recorded as an intention and never as an
    accomplished fact — or, on the cost-gate-FAIL branch, the explicit statement
    that no tag was created and why;
11. scanner summary: gitleaks, trivy, semgrep findings and skylos shadow
    findings, each **fixed, not suppressed**; any suppression quoted with the
    code comment citing its REQ id. The **19 skylos shadow findings in
    `dashboard_server.py`** carried from v1.6.0 are restated as informational and
    are explicitly **not** refactored (REQ-V170-NG-12);
12. fix cycles used against the budget of 5;
13. **Deviations**, per REQ-V12-REP-02, process deviations included; "None" only
    when true.

**REQ-V170-RPT-04 (MUST) — the other artefacts, and the docs that must not
drift.** Usage rows are appended per prompt to `docs/llm-usage.md`'s existing
table, never as a headerless fragment. `docs/reports/tg-post-v1.7.0.md` is
**Russian**, **under 1500 characters** by `wc -m` (the report quotes the count),
names the executor model, and links
`https://github.com/axyi/tg-agent-bot`. `AGENTS.md`'s Gates, Stack, project
layout and Benchmark sections — **including the stale `1004` test count at
`:103` and the mutation-entry count at `:112`** — `README.md`'s new sections and
`.env.example`'s two new keys, and `docs/plan.md`'s milestone, are updated in the
same commits as the changes they describe.

---

## 13. Gates

**REQ-V170-GATE-01 (MUST) — the six existing gates, verbatim and in order.**
Restated from `AGENTS.md:95-100`; **not one character changes**:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
uv run --locked python devtools/mutation_check.py
```

Gates 1–4 and 6 are unconditional and offline. Gate 5 requires the §3
preconditions and is executed at **T1** — the live preflight, against the
still-unchanged tree — again at **T10** once every source change has landed, and
again at **T14**; never at T0. An unreachable LM Studio at T1 is a **blocked
run**. The T10 and T14 runs belong to a code path a `T-STOP` branch never
enters: on the STOPs of REQ-V170-BEN-01 and REQ-V170-RSN-06 gate 5 is **not
required** after T1 and is recorded `N/A` with that reason, exactly as
REQ-V170-ORD-02 item 5 states; that is the only exception to this requirement,
and it removes no gate from any branch that reaches T10 — gates 1–4 and 6 stay
unconditional on every branch. On a `T-STOP` branch they are therefore
**executed again**, against the finalised STOP tree and before the closing
commit, with fresh exit codes recorded (REQ-V170-ORD-02 item 5): T0's run proves
the tree it ran on, not the tree that ships, and this branch adds prompts, a
finalised report, usage rows and — on a T3 STOP — every stage-A artefact after
it. The test count MUST exceed the
number measured at T0 (floor 1016); state the exact number in the report. **On a
`T-STOP` branch it MUST *equal* that number instead** — no test was added because
no code was written, and REQ-V170-EC-03's "no test may be deleted" makes the
equality the assertion.

**REQ-V170-GATE-02 (MUST) — one new gate, and two re-measured timeouts.**
`config/quality_gates.yaml` gains exactly one gate:

```yaml
  mutation-v170:
    kind: command
    argv: [uv, run, --locked, python, devtools/mutation_check.py, --select, v170-]
    result_mode: exit_status
    blocking: true
    timeout_seconds: <2 x measured, rounded up to the next 10 s>
```

placed in the **`pre-push`** profile, mirroring `mutation-v160` exactly. No
existing gate's `argv`, `result_mode`, `blocking`, `severity` or profile
membership changes. Two timeouts are **re-measured**, not guessed, per the
2×-a-measured-run rule already documented in that file: `mutation-v170` itself,
and `mutation-all`, which grows from v1.6.0's 83 entries by at least the nine of
§14.4 **and** reruns a larger suite once per entry.

**REQ-V170-GATE-03 (MUST) — the profile matrix, and findings are fixed, not
suppressed.** REQ-V160-GATE-03's matrix is the authoritative one and is amended
in exactly two cells: `mutation_check.py --select v170-` joins the `pre-push`
column, and `checks.py lint-docs` now points at this release's report
(REQ-V170-RPT-02). `tests/test_v15_standards.py`'s matrix test is repointed at
**this** file (§14.1) and `_GATE_MATRIX_LABEL_TO_NAME` gains the new label.
Every other row stands.

Any new gitleaks, trivy, semgrep or skylos finding introduced by this release is
**fixed**. A suppression requires a code comment on the suppressing line citing
the REQ id that justifies it, and the report quotes both. The 19 pre-existing
skylos shadow findings in `dashboard_server.py` are neither fixed nor suppressed
here: they are shadow, they are recorded, and refactoring that module is a
NON-GOAL (REQ-V170-NG-12).

### 13.1 Per-task reading map

Navigation aid **and** the authority for REQ-V170-EC-07's file-count threshold;
reading more is never a defect, reading less never releases a requirement. §1
(EC-01…09), §2 (AMEND-01), §4 (TREE-01…02) and §17 (NG-*) bind every task and are
not repeated per line.

| T | spec sections | repository files and ranges | delegate? |
|---|---|---|---|
| **T0** | §3, §13 | `AGENTS.md:90-120`, `config/quality_gates.yaml:280-317` | no |
| **T1** | §3 (PRE-03, -04), §9 (BEN-01), §13 | `llm/lmstudio.py:35-53` read-only — the request shape and route the TTFT `VERIFY` marker must probe through; otherwise only commands run | no |
| **T2** | §5 (RSN-01…05, -07) | the scratch patch only; `devtools/bench_scenarios.py:204-212`, `:262-270` and `llm/lmstudio.py:35-53` read-only — the latter is where the TTFT capture reads `stats.time_to_first_token` off the OpenAI-compatible response | no |
| **T3** | §5 (RSN-01…07) | none — only commands run, under the scratch patch of T2 | no |
| **T4** | §6 (POL-01…03), §7 (OBS-01) | `config.py:280-300`, `:341-400`; `llm/base.py:60-130`; `storage.py:16-46`, `:180-230`, `:284-301` | **yes** |
| **T5** | §6 (POL-04…06), §7 (OBS-02, -03) | `llm/base.py:66-130`, `llm/lmstudio.py:30-53`, `llm/openrouter.py:66-98`, `llm/failover.py:44-95`, `bot.py:1065-1080`, `agent.py:325-350`, `:830-960`, `tracing.py:60-100` | **yes** |
| **T6** | §8 (SUM-01…05) | `agent.py:40-50`, `:1022-1115`; `bot.py:720-760`; `config.py:280-300`, `:363-400` | **yes** |
| **T7** | §9 (BEN-02, -03, -06), §10 (CAR-01) | `devtools/bench.py:105-200`, `:225-280`, `:660-740`, `:1430-1470`, `:1520-1580`, `:1950-1990`, `:2260-2290`, `:2310-2330` | **yes** |
| **T8** | §11, §12 (RPT-02, -04), §15 (ACC-03) | `.env.example`, `README.md`, `AGENTS.md`, `docs/plan.md`, `config/quality_gates.yaml:288-317` — **not** `pyproject.toml`, whose version moves only at T12 (REQ-V170-VER-01) | **yes** |
| **T9** | §13, §14.4 | `devtools/mutation_check.py` **tail only** (`MUTATIONS` entries and `main()`), `config/quality_gates.yaml:200-235` | **yes** |
| **T10** | §13, §15 (REV-01) | the review's own reading map; otherwise only commands run | no |
| **T11** | §9 (BEN-01, -04…-08) | none — the tree is frozen; only commands run | no |
| **T12** | §6 (POL-07), §11 (VER-01), §15 (ACC-03) | `config.py` (the two default literals only), `pyproject.toml` (`project.version` only), `.env.example`, `README.md`, `AGENTS.md` | no |
| **T13** | §12, §15 | this run's own artefacts | no |
| **T14** | §15 (ACC-03), Appendix B | this run's own artefacts | no |

Any task whose actual reading exceeds its map crosses REQ-V170-EC-07 and is
delegated; the report records it either way.

---

## 14. Tests

**REQ-V170-TST-01 (MUST)** New tests live in `tests/test_v170_reasoning.py`,
`tests/test_v170_summary_budget.py` and `tests/test_v170_bench.py` unless stated
otherwise. They are **offline and deterministic** and touch no Docker daemon, no
network, no `.env` and no LLM (REQ-V12-OFF-01's `conftest.py` guard, extended by
REQ-V160-SRV-05's bind guard). Every LLM in a test is a fake; every clock is a
fake; databases are `tmp_path` fixtures. **No test may call the network** — a
test that would need a live model asserts against a recorded fixture instead.

**REQ-V170-TST-02 (MUST)** Test-first: each test below is written and observed to
fail **for the right reason** before its implementation exists; the report
records any case where a test passed before its code was written. Test values
come from this spec or from an independent literal, never re-derived from the
implementation (`standards/workflow.md` §4).

### 14.1 Amendments to existing tests (exhaustive)

This list is **complete**; any other existing test that fails means the change
is wrong.

| file:line | change | driven by |
|---|---|---|
| `tests/test_observability.py:431-432` | `assert storage.SCHEMA_VERSION == 4` → `== 5` and `assert storage.schema_version(conn) == 4` → `== 5`; the table loop is unchanged (no new table) | REQ-V170-OBS-01 |
| `tests/fakes.py:49`, `tests/test_observability.py:114`, `:639`, `tests/test_bench.py:161`, `:183`, `tests/test_failover.py:31`, `:276` | every test double's `complete()` accepts the two new keyword-only parameters in order — `reasoning: ReasoningRequest = llm.base.REASONING_DEFAULT`, then `timeout_s: float \| None = None` — with the production defaults; a double that records requests records the whole `ReasoningRequest` (all three fields) and the `timeout_s`, a double that ignores them may take `**kwargs`. Without this every call site of POL-04 raises `TypeError` in the suite | REQ-V170-POL-04, REQ-V170-SUM-03 |
| `tests/test_storage.py:44` | already compares against `storage.SCHEMA_VERSION`; **verify** it still passes, do not edit | REQ-V170-OBS-01 |
| `tests/test_v15_standards.py:1697` | `_GATE_MATRIX_LABEL_TO_NAME` gains ``"`mutation_check.py --select v170-`": "mutation-v170"`` | REQ-V170-GATE-02 |
| `tests/test_v15_standards.py:1726` | the matrix test reads the committed `docs/spec/spec-v1.7.0.md` instead of `spec-v1.6.0.md` | REQ-V170-GATE-03 |
| `tests/test_bench.py` | the `comparability` cases asserting the stage-C **null-on-baseline** rule become equality cases | REQ-V170-BEN-02 |

**Explicitly NOT amended**, each verified against the test as written:
`tests/test_v14_patch.py:84-96` (`bench.constants()` and `REQUEST_DEFAULTS` stay
reasoning-free — REQ-V170-AMEND-01 keeps both untouched, and this test passing
unamended is the proof); `tests/test_v160_bench.py:170-240` (S13…S18 ids and
ceilings — `bench_scenarios.py` is frozen); `tests/test_observability.py:593`
(summary rows keep `turn_id is None`); `tests/test_bench.py:111` and
`tests/test_dashboard.py:136` (`bench_schema` follows the constant, which does
not move); `tests/test_summary.py` (every existing caller omits `budget_s`, so
the path is unchanged).

**`tests/test_failover.py` is amended only at the test-double signatures listed
in §14.1** — `:31` and `:276`, and nothing else in the file; all test behaviour
and assertions otherwise remain unchanged. It is therefore neither in the
not-amended list above nor open to any other edit: the round-1 spec said both
that §14.1 required those two lines and that the file stayed unamended, which no
executor could satisfy under REQ-V170-EC-03's ban on unlisted test edits.

### 14.2 New unit tests — the mechanisms

| id | asserts |
|---|---|
| `T-V170-POL-01` | `LLM_REASONING_POLICY` accepts exactly `model-default`, `off`, `by-purpose` and raises `ConfigError` naming the variable **and** the token otherwise; `LLM_REASONING_ON_PURPOSES` parses a comma list order-insensitively into a `frozenset`, accepts the empty string as the empty set, rejects an unknown tag naming it, and defaults to `{"tool-round"}`; both are absent-safe |
| `T-V170-POL-02` | `reasoning_tag` over the full cross product of `purpose ∈ {"agent","summary"}` and `request_tools ∈ {None, [], [spec]}`: `("agent", None) → "final"`, `("agent", []) → "final"`, `("agent", [spec]) → "tool-round"`, `("summary", *) → "summary"`; the function reads no `Config` and no module global |
| `T-V170-POL-03` | `resolve_reasoning` over all 3 × 3 combinations of policy and tag, plus `on_purposes` empty and full: it returns a **frozen** `ReasoningRequest` (mutating a field raises), `.tag` always equals the tag argument, `model-default` yields `value == "default"` with `mechanism is None` for every tag and looks nothing up; `"on"` yields `("on", None, tag)` for every tag and looks **nothing** up either — asserted against a mechanism table that would raise on any lookup, so a regression to a `(tag, value)` table is caught; only `"off"` reads `mechanisms.get(tag)`, and an `"off"` whose tag entry is `None` or absent degrades to `("default", None, tag)`; a table holding a mechanism for `"summary"` but not for `"tool-round"` yields the mechanism on the summary tag alone, and under `by-purpose` with `on_purposes == {"tool-round"}` yields `("on", None, "tool-round")` and `("off", <summary mechanism>, "summary")` |
| `T-V170-POL-04` | with a fake primary raising a retryable `LLMError` and a recording secondary, the secondary receives the **same `ReasoningRequest` object** the caller passed — equal `value`, equal `mechanism`, equal `tag`, including a non-`default` tag such as `"summary"` — which is the `_try_other` forwarding at `llm/failover.py:83`; and `devtools/bench.py:2186`'s warm-up probe passes `reasoning=REASONING_DEFAULT` and `timeout_s=None` explicitly |
| `T-V170-POL-05` | under every policy, neither the system prompt nor the `tools` JSON contains any mechanism string; `prompt_tools_sha256` computed over a treated tree equals the untreated value; the `lmstudio` client applies `request.mechanism` alone — `fields` reach the payload, `("append_assistant", …)` becomes the last message, `("suffix_last_user", …)` extends the last user message, `mechanism is None` adds nothing — and reads `request.tag` **nowhere** (asserted by passing a `ReasoningRequest` whose `tag` is a value outside `REASONING_TAGS` and getting the same payload); the `openrouter` client branches on `request.value` alone, its off form is exactly `{"reasoning": {"enabled": false}}`, and `"on"`/`"default"` add nothing. **Deep immutability**: no value reachable from `REASONING_MECHANISMS` is a `dict`, `list` or `set` (asserted by a recursive walk); mutating a produced payload — including its **nested** `chat_template_kwargs` mapping — leaves `REASONING_MECHANISMS` byte-equal to its pre-call state **and** leaves a payload produced by a second, later call byte-equal to the first's original value; and two successive calls return payloads that are equal but not the same object at any nesting level |
| `T-V170-POL-06` | `build_payload(reasoning_fields=None)` is byte-identical to today's output for both the `tools is None` and `tools is not None` branches; a mapping is merged after the existing keys; a mapping colliding with any of the seven protected keys raises `ValueError` naming it; neither `message_patch` form mutates the caller's `messages` list, and the list the caller still holds after the call compares equal to the one it passed |
| `T-V170-POL-07` | the shipped defaults of both variables equal the literals `.env.example` documents — the single permitted pin |
| `T-V170-OBS-01` | migration 4 → 5 on a populated v4 database: both columns appear nullable, pre-existing rows read `NULL`, the version reads 5; chained 1 → 5, 2 → 5 and 3 → 5; idempotent on re-`init_schema`; an unsupported version (0, 6, `"x"`) still raises the existing `RuntimeError` naming it |
| `T-V170-OBS-02` | `storage.LLM_CALL_COLUMNS` equals `PRAGMA table_info(llm_calls)`; the `llm_call` log payload's key set equals it too; `tracing.ATTRIBUTE_KEYS` contains `tg_agent.reasoning.requested` and `set_attribute` still rejects an unlisted key |
| `T-V170-OBS-03` | the three-valued honored table in full, as `(requested, reasoning_tokens, reasoning_chars) → honored`: `('default', *, *)` → `NULL`; `('off', NULL, 0)` → **`NULL`**, the unknown case, **not** `1`; `('on', NULL, 0)` → **`NULL`** for the same reason; `('off', 0, 0)` → 1; `('off', NULL, 5)` → 0; `('off', 1, 0)` → 0; `('off', 0, 5)` → 0; `('on', 0, 0)` → 0; `('on', 7, 0)` → 1; `('on', NULL, 5)` → 1; a call raising before a response → the requested value and `NULL`. The two `NULL` rows are asserted to be `NULL` and not falsy-equal to 0, so a `is None` regression cannot pass |
| `T-V170-OBS-04` | every `llm.complete` invocation writes both columns — **exactly six rows** and six non-`NULL` `reasoning_requested` values, through `_record_llm_call` only (asserted by patching `storage.add_llm_call` to count calls). The six are derived from the call structure, not asserted from a number: one `run_agent` turn issues one invocation per round (`agent.py:335`), so the tools-exposed round and the tools-withheld final round are **two**; `summarize_conversation` issues attempt 1 and then **either** the truncation retry **or** the JSON-repair call — `if truncated:` / `elif parsed is None and reason is not None:` at `agent.py:1052-1062` are mutually exclusive and one invocation can never produce both — so the scenario drives **two** summary invocations, one truncating and one returning invalid JSON, for **four**. A failover inside any of the six adds **no** row (REQ-V170-OBS-03): the test wraps one of them in a `FailoverLLMClient` whose primary raises, and asserts the count is still six and that row's `provider` names the secondary |
| `T-V170-SUM-01` | with a fake clock and `budget_s=100`, attempt 1 consuming 40 s and the retry 50 s, both are issued and the deadline is taken once, before attempt 1; with `budget_s=None` the behaviour is byte-identical to v1.6.0's, proved against a recorded call log |
| `T-V170-SUM-02` | with `budget_s=100` and attempt 1 consuming 80 s, the truncation retry is **not issued** (remaining 20 s < 30 s floor), `summarize_conversation` returns `None`, no exception escapes, exactly **one** `llm_calls` row exists, and one redacted warning names the elapsed and remaining seconds; the same for the JSON-repair branch |
| `T-V170-SUM-03` | a fake client records the `timeout_s` of every request it receives: **attempt 1's** equals the remaining budget, not `None` and not the client's own — with `budget_s=10` against a client configured at `timeout_s=600` the first recorded value is `10`, not `600` — and the retry's equals the budget remaining at that moment; no `min` against the client's timeout is applied anywhere; a request whose remaining budget is non-positive is not issued at all |
| `T-V170-SUM-04` | the truncation retry and the JSON-repair call are issued with a `ReasoningRequest` whose `value` is `"off"` under `model-default`, `off` **and** `by-purpose` with `summary` in `on_purposes`, and whose `tag` is still `"summary"`; attempt 1 under `by-purpose` with `summary` on still resolves to `"on"` |
| `T-V170-SUM-05` | `load_config` raises `ConfigError` naming `LLM_TIMEOUT_S`, `LLM_SUMMARY_MAX_TOKENS` and the floor when `llm_timeout_s < 21.1 + 0.093 × llm_summary_max_tokens + 30`; it does **not** raise at shipped defaults (240 / 1536 → 193.9) nor at the 1.7.0 instrument (600 / 1536); the pre-existing check's message is unchanged |
| `T-V170-BEN-01` | `meta.reasoning` is present on every run this release produces, including `model-default`, `on_purposes` serialises sorted, a purpose with no mechanism is `null`, and `reasoning` is **not** in `LOCKED_META_FIELDS`. Additive-optionality is proved against the **real committed** `docs/assets/bench/baseline-v1.6.0.json`, never a hand-built stand-in: it carries no `meta.reasoning` and no `reasoning_requested`/`reasoning_honored` on any row, and `bench.py check` on it still exits 0 after the migration widens `storage.LLM_CALL_COLUMNS`; a candidate-shaped document carrying `meta.reasoning` and both new row fields also passes `check`; and nothing in the run writes `meta.reasoning` into a document that lacks it |
| `T-V170-BEN-02` | `comparability(baseline-v1.6.0, baseline-v1.6.0)` returns `None`; a candidate differing only in `env_flags.LLM_REASONING_POLICY`/`_ON_PURPOSES` and `git_commit` returns `None`; a pair whose `generation_settings` differ returns the locked-field message; a pair whose `HISTORY_TOOL_STUB` differs returns `env_flags.HISTORY_TOOL_STUB differs`; `LLM_FAILOVER != "off"` and a non-empty `LLM_SUMMARY_MODEL` are still refused on either side |
| `T-V170-BEN-03` | `config_sha256` is byte-identical for two `Config` objects differing **only** in the two new fields, and differs when any non-excluded field differs |
| `T-V170-BEN-04` | `report --gate` exits 0 when both gates pass, 1 when the cost gate fails, 1 when a scenario loses two repeats, **1 when S18 reads 2/3 while every other gate passes** — the executable rule of REQ-V170-BEN-06 item 3, whose message names S18 — and `EXIT_NOT_COMPARABLE` (2) when `timeout_s` differs, the `--timeout-s 1800` trap of REQ-V170-BEN-04. Every case runs `check`, `comparability` and `report --gate` with the **real committed** `docs/assets/bench/baseline-v1.6.0.json` on the baseline side; the candidate side is a copy of it carrying `meta.reasoning`, the two new row fields and the treatment `env_flags`, mutated per case. A 2-of-3 S18 alone is not caught by item 2, which needs a two-repeat loss — the test asserts that too, so the new rule is proved to be the thing doing the work |
| `T-V170-BEN-05` | `GATE_REQUIRED_FULL_SCENARIOS` is exactly `("S13","S14","S15","S16","S17","S18")`, lives in `devtools/bench.py` beside `COST_GATE_FACTOR` and `QUALITY_GATE_SLACK`, and appears in neither `bench.constants()` nor `REQUEST_DEFAULTS`; the gate reads `summary.per_scenario` of the **candidate** side only and fails when any listed id is below 3/3 or missing, naming every failing id in one line; a candidate at 3/3 across all six passes it; `devtools/bench_scenarios.py` is byte-unchanged |
| `T-V170-CAR-01` | `--tag` accepts `baseline-v1.6.0`, `cand-v170-off`, `a`, and a 64-character name; rejects `..`, `.`, `a/b`, `../x`, `a\\b`, the empty string, a 65-character name and a name with a space — each with `EXIT_ERROR` and **no** filesystem write, asserted by patching `shutil.rmtree` to fail the test if called |
| `T-V170-RPT-02` | `config/quality_gates.yaml`'s `lint-docs.report_path` names `docs/reports/report-v1.7.0.md` and its `ledger_header` is unchanged |
| `T-V170-VER-01` | `bot.main(["--version"])` prints `tg-agent-bot <v>` where `<v>` equals an independent `tomllib` read of `pyproject.toml`, and returns 0 |
| `T-V170-ACC-03` | the post-measurement selection commit is equivalent to the measured treatment: with no `LLM_REASONING_*` in the process environment, `load_config()` on the final tree yields `(llm_reasoning_policy, sorted(llm_reasoning_on_purposes))` equal to the `meta.reasoning` `policy`/`on_purposes` of **exactly one** committed `docs/assets/bench/cand-v170-*.json`; the same pair equals what `.env.example` documents; and the test names no policy literal of its own, so the selection commit never edits it. It additionally asserts the version invariant of REQ-V170-VER-01 **without a literal**: an independent `tomllib` read of `pyproject.toml` equals `1.7.0` exactly when such a matching candidate document exists and `1.6.0` when none does — the offline proof that the bump rode in T12's selection commit and in no other. The test is **three halves**: the **equivalence** half skips, with a recorded reason, while no candidate document exists (T8, and the stage-A / instrument-STOP branches); the **version** half never skips, so at T8 it asserts `1.6.0` and after T12 it asserts `1.7.0`. `sorted(llm_reasoning_on_purposes)` of the empty set is `[]`, which is exactly what C2's `meta.reasoning.on_purposes` carries, so the explicit empty treatment (REQ-V170-BEN-05) matches like any other. **A third half — the selection-commit allowlist check of REQ-V170-REV-01 item 8**: it locates the selection commit as the single commit whose body cites T12's prompt file, records `git diff --name-only` from that commit's first parent to itself, fails on any path outside the five permitted files, and asserts the permitted hunks structurally — `config.py` lines carrying one of the two variable names, `pyproject.toml`'s `version` line alone, the three documentation files' lines carrying a variable name or a version string — naming no literal of its own. It invokes `git` through `subprocess` — permitted by REQ-V170-TST-01, which forbids Docker, the network, `.env` and any LLM and not a local process call, and precedented by `tests/test_v15_standards.py:35-62`'s sanitised-environment `git` helper — reaches no network, and **skips with a recorded reason** while no such commit exists. **All three halves are written at T8**, before the freeze; none is added later |

### 14.3 Negative tests — the mechanisms must be able to fail

| id | scenario | expected |
|---|---|---|
| `N1` | `LLM_REASONING_POLICY=aggressive`, and `=OFF` (wrong case) | `ConfigError` at `load_config` naming the variable and the token; the bot does not start |
| `N2` | `LLM_REASONING_ON_PURPOSES=tool-round,summry` | `ConfigError` naming the variable and `summry`; the valid token is not silently accepted |
| `N3` | `LLM_REASONING_ON_PURPOSES=summary` under `by-purpose` | accepted — it is a legal configuration, and REQ-V170-SUM-04 still forces the **retry** off. The bot starts |
| `N4` | a `reasoning_fields` mapping containing `"messages"` | `ValueError` naming `messages`; the payload is not built |
| `N5` | the summary path with `budget_s=10` against a client configured at `timeout_s=600` | attempt 1 **is** issued — 10 s remain, which is positive, and the 30 s floor guards only the later requests — but with `timeout_s=10`, never `None` and never 600; no retry follows, since the remaining budget is then below the floor; the turn completes |
| `N6` | a candidate document carrying `meta.aborted` | `check` refuses it, `report --gate` exits `EXIT_NOT_COMPARABLE`, and the quality-gate helper refuses it before reading `per_scenario` |
| `N7` | `bench.py run --tag ../escape` | `EXIT_ERROR`, a message naming `--tag` and the permitted charset, and `shutil.rmtree` never called |
| `N8` | a database at schema version 6 | the existing `RuntimeError` naming the version; no DDL runs |

### 14.4 Mutation coverage

**REQ-V170-TST-03 (MUST)** Add **at least nine** `v170-*` entries to
`devtools/mutation_check.py`'s `MUTATIONS` list, each a dict with the existing
five keys (`id`, `path`, `find`, `replace`, `why`), each breaking a security- or
correctness-critical mechanism and killed by a named test:

| id | mutation | killed by |
|---|---|---|
| `v170-failover-drops-reasoning` | the `reasoning=` forwarding at `llm/failover.py:83` is removed | `T-V170-POL-04` |
| `v170-summary-retry-ignores-budget` | the retry passes `timeout_s=None` instead of the remaining budget | `T-V170-SUM-03` |
| `v170-summary-floor-ignored` | `SUMMARY_BUDGET_FLOOR_S = 30.0` → `0.0` | `T-V170-SUM-02` |
| `v170-summary-floor-check-removed` | the second `load_config` check of REQ-V170-SUM-05 is deleted | `T-V170-SUM-05` |
| `v170-rescue-retry-keeps-reasoning` | the retry's forced `"off"` becomes the policy's own resolution | `T-V170-SUM-04` |
| `v170-honored-treats-null-as-positive` | the unknown case of REQ-V170-OBS-01 rule 2 is removed — `reasoning_tokens is None` is read as a known count instead of as absent evidence, so `('off', NULL, 0)` yields `1` and `('on', NULL, 0)` yields `0` where both MUST be `NULL` | `T-V170-OBS-03` |
| `v170-tag-sanitiser-removed` | the `--tag` pattern check of REQ-V170-CAR-01 always returns `True` | `T-V170-CAR-01`, `N7` |
| `v170-config-hash-includes-treatment` | `llm_reasoning_policy` is removed from `CONFIG_HASH_EXCLUDED` | `T-V170-BEN-03` |
| `v170-gate-ignores-3of3` | the `report --gate` check over `GATE_REQUIRED_FULL_SCENARIOS` is skipped, so a candidate with S18 at 2/3 exits 0 | `T-V170-BEN-04`, `T-V170-BEN-05` |

**REQ-V170-TST-04 (MUST)** Every entry's `find` string must match its target file
**exactly once**; `mutation_check.py --list` is run and its output recorded
before the gate is trusted. The whole-tree `ruff format` reformat stays a
NON-GOAL (REQ-V15-NG-04) so existing `find` strings stay valid.

---

## 15. Acceptance, review and report

**REQ-V170-ACC-01 (MUST)** After the `full` profile is green, execute Appendix B
against the repository, the running bot and the recorded documents. Record pass
or fail per scenario and, per REQ-V12-REP-02, **how** each was driven.

**REQ-V170-ACC-02 (MUST)** Regression check: spec-v1.2's D1 and D2, spec-v1.4's
S01 acceptance, spec-v1.5's freeze properties and spec-v1.6.0's tracing,
dashboard and tool-quality properties still hold. No earlier security posture is
weakened; in particular the exec sandbox, the redaction choke points, the SSRF
domain allowlist, the loopback-only dashboard and the `.env` handling are
untouched by this release.

**REQ-V170-ACC-03 (MUST) — the final acceptance run, the frozen tip, and the
freeze.** On a `T-STOP` branch (REQ-V170-ORD-02) this requirement is **not
reached**: T13 and T14 are replaced by `T-STOP`'s own finalisation, there is no
`<implementation-tip>`, no evidence-only commit and no tag, and the report says
so. On every other branch the v1.5/v1.6.0 machinery applies unchanged:

- **T13 lands a provisional `report-v1.7.0.md`** carrying every REQ-V170-RPT-03
  item except item 4's `<implementation-tip>` SHA and every T14 artefact. That
  commit's resulting SHA **is** `<implementation-tip>`.
- **T14 re-runs against the final tree**: the six verbatim gates of §13,
  `checks.py run --profile full --since <base>`,
  `checks.py replay --range <base>..<implementation-tip>` and Appendix B. It then
  lands **one evidence-only commit** touching `docs/reports/*` and nothing else.
  That commit is not recursively required to replay against itself. **Only after
  it has landed**, and **only on REQ-V170-BEN-07's PASS**, is the annotated tag
  `v1.7.0` created on it; the tag is the last action of the run and no commit
  follows it.
- **After the first candidate run no source, test or config change is
  permitted** — that is REQ-V160-BEN-07's freeze, re-armed here for the
  candidates. There are exactly **two** exceptions, and each re-runs the
  `commit-msg` checks, the `pre-commit` profile, `lint-docs` and `gitleaks-tree`
  against the final tree:

  1. a **documentation-only** correction of the evidence the run produced;
  2. the **single post-measurement selection commit** of REQ-V170-POL-07,
     which exists **only when a quality-passing candidate exists** and whose
     allowed-file list is exhaustively `config.py` (the two policy default
     literals, set to exactly the selected candidate's process-environment
     treatment), `pyproject.toml` (`project.version` `1.6.0` → `1.7.0`,
     REQ-V170-VER-01), and the documentation echoes of both in `.env.example`,
     `README.md` and `AGENTS.md` — **five files, no sixth**. When no candidate
     passes quality, when the comparison stays `EXIT_NOT_COMPARABLE`, or when
     either STOP of REQ-V170-RSN-06 / REQ-V170-BEN-01 fired, this exception is
     simply not taken: the version stays `1.6.0` and no tag is created.

  Exception 2 is admitted only against proof, produced **before** acceptance:

  - `T-V170-ACC-03`, offline, loads every committed
    `docs/assets/bench/cand-v170-*.json`, reads each `meta.reasoning`, and
    asserts that an **unprefixed** `load_config()` on the final tree resolves to
    `(policy, sorted(on_purposes))` equal to **exactly one** of them. The three
    catalogue treatments of REQ-V170-BEN-05 are pairwise distinct, so "exactly
    one" pins the selection uniquely **without pinning a literal** — which is
    why the selection commit never has to edit the test. The same test asserts
    the **version invariant** of REQ-V170-VER-01 in the same breath, and still
    without a literal: `pyproject.toml`'s `project.version` reads `1.7.0` when a
    committed `cand-v170-*.json` matches, and `1.6.0` when none does, so a bump
    that escaped its one permitted commit fails offline; and, once T12 has
    landed, its **third half** — REQ-V170-REV-01 item 8's automated
    allowlist check, which records `git diff --name-only <T11-tip>..<T12-tip>`,
    rejects any path outside the five permitted files and checks the permitted
    hunks structurally, replacing the second general code review the round-2
    spec implied but could never schedule;
  - a recorded **candidate-metadata check**: the report names the selected tag
    and prints its `meta.reasoning.policy` and `meta.reasoning.on_purposes`
    beside the final tree's resolved pair.

  **The equivalence proof is only as good as its `.env` precondition.**
  `T-V170-ACC-03` resolves `load_config()` with no `LLM_REASONING_*` in the
  process environment **and without the deployment `.env`**, so what it proves
  is that the *tree* resolves to the measured treatment. That carries to the
  running bot only because REQ-V170-PRE-01 item 9 proved at T0, by key name and
  without disclosure, that neither `LLM_REASONING_POLICY` nor
  `LLM_REASONING_ON_PURPOSES` is present in `.env` — `load_dotenv(...,
  override=False)` would otherwise let the file beat the changed source literal
  for the deployed bot, and the release would ship a default it never measured.
  The report restates that T0 check beside the candidate-metadata check
  (REQ-V170-RPT-03 item 9).

  Any other source, test or config difference voids the candidates and stage C is
  executed again in full.

**REQ-V170-ACC-04 (MUST)** Failures are fixed and the whole set rerun inside the
**5-cycle** repair budget. Exhausting it means stopping and reporting, not
relaxing a gate, not deleting a test, not lowering a scenario's declared maximum
and not widening `QUALITY_GATE_SLACK` or `COST_GATE_FACTOR`.

**REQ-V170-REV-01 (MUST)** Code review by the `code-reviewer` subagent
(`.claude/agents/code-reviewer.md`) in a **clean context**, at the head of T10 —
after every code task and **before** both T10's own gate run and the first
candidate run, so the findings are fixed and the gates then run on the fixed
tree. Never self-review in the writing context, and never after the measurement,
when no fix could land.
Findings are fixed or waived with a reason in the report; log the review prompt
in `docs/prompts/`. Beyond the standard checklist the reviewer checks:

1. `reasoning_tag`, `resolve_reasoning`, `ReasoningRequest`,
   `ReasoningMechanism` and `REASONING_MECHANISMS` are pure and frozen **all the
   way down** — a recursive walk of the table reaches no `dict`, `list` or
   `set`, and `json_fields` builds fresh dictionaries per call — they live only
   in `llm/base.py`, and no purpose, policy or mechanism literal is duplicated
   anywhere else; the table is keyed by tag and holds **off** mechanisms only,
   `"on"` and `"default"` looking nothing up; **no provider reads
   `request.tag`**;
2. all five `complete()` definitions and all five invocation sites carry both
   new parameters in the documented order (`reasoning`, then `timeout_s`),
   `llm/failover.py:83` included, and `_try_other` forwards the
   `ReasoningRequest` unchanged;
3. no mechanism string can reach the system prompt, the tool schema,
   `REQUEST_DEFAULTS` or `bench.constants()` — `GATE_REQUIRED_FULL_SCENARIOS`
   included;
4. the summary deadline is taken exactly once, **before attempt 1**, and every
   request including attempt 1 derives its timeout from it; no request is issued
   on a non-positive remainder; no path can raise out of
   `summarize_conversation` into the user turn;
5. `--tag` is validated before **any** path is built from it;
6. each mechanism of §14.4 has a mutation entry whose `find` matches once;
7. the S13…S18 3/3 rule is enforced by `report --gate` itself, not by a helper
   only a human runs, and `devtools/bench_scenarios.py` is byte-unchanged;
8. **prospectively** — the reviewer sees no T12 commit, because none exists
   yet, and is not asked to — the **selection mechanism** REQ-V170-POL-07 and
   REQ-V170-ACC-03 define and its **five-file allowlist**: `config.py`'s two
   policy default literals, `pyproject.toml`'s `project.version`, and the
   documentation echoes of both in `.env.example`, `README.md` and `AGENTS.md`;
   that `T-V170-ACC-03` needs no edit to pass; and that the automated check
   named below is in place to police the commit when it lands. The version bump
   inside that commit is **expected**, not a freeze violation
   (REQ-V170-VER-01); a `1.7.0` appearing in `pyproject.toml` at T8 or in any
   other commit **is** one.

**The actual T12 commit is verified by machine, not by a second review.** The
round-2 spec asked this reviewer to check a commit that could not exist at T10,
and no review is permitted after the measurement, so the requirement was
unexecutable. Instead `T-V170-ACC-03` gains a third half: it **locates the
selection commit** as the single commit whose body cites T12's prompt file,
**records `git diff --name-only <T11-tip>..<T12-tip>`** — that commit's first
parent to itself — **rejects any path outside the five-file allowlist**, and
**checks the permitted hunks** structurally: every changed line in `config.py`
carries one of the two variable names, `pyproject.toml`'s diff touches only its
`version` line, and the three documentation files' diffs touch only lines
carrying one of the two variable names or a version string. It names **no policy
literal and no version literal of its own** — which is what keeps the selection
commit from having to edit it (REQ-V170-ACC-03) — it **skips with a recorded
reason** while no such commit exists, at T8 and on every branch that skips T12,
and it runs `git` locally and reaches no network (REQ-V170-TST-01). This half is
a **check, not a review**: it needs no reviewer and no clean context, so it is
not an exception to this requirement's rule that no review happens after the
measurement. No second general code review is required, and the report carries
the recorded diff (REQ-V170-RPT-03 item 9).

---

## 16. Implementation order

**REQ-V170-ORD-01 (MUST)** Work in this order; each task is one prompt and one
commit, with the reading map of §13.1 and the delegation rule of
REQ-V170-EC-07. Three tasks are **conditional exits** and are marked so; T1's
and T3's exits both finalise through the shared `T-STOP` procedure of
REQ-V170-ORD-02, and T12 is additionally a **conditional task**, run only when a
quality-passing candidate exists (REQ-V170-POL-07).

**The order is measurement-first, and that is what makes §5's STOP branch
truthful.** Stage A runs before one line of §§6–8 exists, so the "no
summary-shippable mechanism" branch really can deliver §6, §7, §8 and §9 as
*not executed*; and the per-purpose mechanism table stage A produces is a known
literal by the time `REASONING_MECHANISMS` is written (REQ-V170-POL-03), rather
than something a frozen provider would have to be retrofitted with. The freeze
is therefore stated once, here, and governs every later section: **all
source, test and config changes — every one except the explicitly specified
post-measurement default-selection commit — land after Stage A and before the
first Stage-C candidate.**

| T | task | acceptance |
|---|---|---|
| **T0** | Preconditions (§3), **offline only**: `full` profile green with the live member deferred, hooks installed, `doctor` green, test count re-measured, docker, `bench.py check` on the baseline. **Record `<base>` and the spec's `sha256`**, create `docs/prompts/103-go-spec-v1.7.0.md` and the `report-v1.7.0.md` skeleton — its `## Operator inputs` section copied verbatim from the `go` request, and its "Ledger row (paste into `economics.md`)" section already carrying a structurally complete fenced row (REQ-V170-RPT-02). | every item recorded; `102` is the highest pre-existing prompt and the spec is present and unchanged; `<base>` written before the first commit; **a missing version or a non-positive-integer context length stops the run here** |
| **T1** | **Live preflight — conditional exit.** In this order, and the order **is** the requirement: run PRE-03's **phase 1** — the address/model discovery, the single-line `.env` rewrite and the three documentary reads; then PRE-04 **items 1–6**, none of which costs an inference; then PRE-04 **item 7**, the one-completion preflight, which is the **first inference of the run**; and only then PRE-03's **phase 2**, the OpenAI-route TTFT-shape probe — so that probe runs **after the validated preflight and before any stage-A pair**. Then gate 5 (`bot.py --selftest-live`) and the `full` profile's deferred live member, both against the still-unchanged tree. No source file is touched. | every check recorded; the **four** VERIFY markers resolved with URL, route and date — the fourth, the only one that costs an inference, deciding live on the OpenAI-compatible endpoint whether `stats.time_to_first_token` is available and therefore whether REQ-V170-RSN-07's summary-only fallback binds the whole run, issued only after PRE-04's seven checks passed and carrying REQ-V170-RSN-07's nonce prefix so it warms nothing a confirming run later measures; **an instrument mismatch STOPS the run here** (REQ-V170-BEN-01), before a line of code is written and before that probe is issued, and the run finalises through `T-STOP` (REQ-V170-ORD-02) |
| **T2** | The **stage-A scratch harness**: the mechanism-selection patch shape, the pair-file naming of REQ-V170-TREE-01, the restore-and-`git diff` procedure, REQ-V170-RSN-07's mixed-policy pair, and — when T1 found the field — the per-call capture of `stats.time_to_first_token` from the OpenAI-compatible response into the TTFT sidecar, on that route only, together with REQ-V170-RSN-07's **cold calibration**: the two nonce-prefixed scratch requests issued before each confirming member, the nonce freshly generated per member, the warm-proof comparison and the sidecar's `calibration` block. **No commit of the patch itself** — this task commits only its prompt and the report scaffolding. | the procedure is written down and dry-run against the stub client with zero live calls; the sidecar shape exercised against a recorded response fixture, `null` written where the field is empty or absent, the `calibration` block present with the nonce's length and never the nonce, and the warm-proof comparison exercised offline against two recorded TTFT values |
| **T3** | **Stage A (§5) — conditional exit.** Candidates **a**…**e** in the fixed order under the pair contract and the budget; the honored decision per purpose; RSN-07's confirming mixed-policy pair, with both checks, for any mechanism proposed for an agent tag — or, under the summary-only fallback — the TTFT field absent, or a cold calibration's warm proof failing — `none` recorded for both agent tags, the confirming pair never spent or abandoned before either member ran, and no pair charged for it; the per-purpose mechanism table. | the mechanism table produced and every pair artefact committed, TTFT sidecars with their `calibration` blocks included where check 2 ran; `git diff` empty after each candidate; **no summary-shippable mechanism STOPS the run here** (REQ-V170-RSN-06), with §6, §7, §8 and §9 declared not executed, no version bump, and the run finalised through `T-STOP` (REQ-V170-ORD-02) |
| **T4** | `config.py` (two fields, two parsers, the SUM-05 check), `llm/base.py` (`REASONING_TAGS`, `reasoning_tag`, the two frozen dataclasses, `REASONING_MECHANISMS` filled from **T3's** table, `resolve_reasoning`), `storage.py` (`SCHEMA_VERSION = 5`, the two columns, `_MIGRATION_4_TO_5`, the accepted tuple). Tests `T-V170-POL-01`, `-02`, `-03`, `T-V170-OBS-01`, `T-V170-SUM-05`, `N1`, `N2`, `N3`, `N8`; amends `tests/test_observability.py:431`. | those tests green; migration tests green from v1, v2, v3 and v4 databases; `test_v14_patch` green **unamended** |
| **T5** | `llm/base.py` (`build_payload`'s `reasoning_fields`), the two new keyword-only parameters across five definitions (incl. `bot.py:1071`) and five invocations, the seven test doubles of §14.1, the two provider forms, `tracing.py`'s one new key, `agent.py`'s `_record_llm_call` wiring. Tests `T-V170-POL-04`, `-05`, `-06`, `T-V170-OBS-02`, `-03`, `-04`, `N4`. | those tests green; `tests/test_failover.py` green with **only** the two test-double signature amendments §14.1 lists (`:31`, `:276`) and no behaviour or assertion changed; `prompt_tools_sha256` unchanged |
| **T6** | `agent.py` summary budget (`budget_s`, `clock`, `SUMMARY_BUDGET_FLOOR_S`, the per-request timeout on **every** request, the rescue retry) and `bot.py`'s two call sites. Tests `T-V170-SUM-01`, `-02`, `-03`, `-04`, `N5`. | those tests green with a fake clock and no live call; `tests/test_summary.py` green unamended |
| **T7** | `devtools/bench.py`: `meta.reasoning`, the `comparability` equality rule, the two `CONFIG_HASH_EXCLUDED` entries, `GATE_REQUIRED_FULL_SCENARIOS` and the `report --gate` check that reads it, the `--tag` sanitiser, the corrected `ENV_FLAG_FIELDS` comment. Tests `T-V170-BEN-01`, `-02`, `-03`, `-04`, `-05`, `T-V170-CAR-01`, `N6`, `N7`; amends `tests/test_bench.py`'s comparability cases. | those tests green, `T-V170-BEN-01`/`-02`/`-04` driven through the **real committed** baseline; `bench_scenarios.py` byte-unchanged (`git diff --stat` proves it) |
| **T8** | Docs and the gate config, **no version bump**: `.env.example`, `README.md`, `AGENTS.md` (gate, variables, corrected test and mutation counts), `docs/plan.md`, and `config/quality_gates.yaml`'s `report_path` — repointed **here**, before the freeze, because it is a config file (REQ-V170-RPT-02). `pyproject.toml` is **not** touched: the bump belongs to T12's selection commit alone (REQ-V170-VER-01). Tests `T-V170-VER-01`, `T-V170-RPT-02`, `T-V170-ACC-03` — **all three of its halves written here**, because REQ-V170-ACC-03's freeze admits no test change after the first candidate: its equivalence half skipping, with the reason recorded, while no candidate document exists; its version half asserting `1.6.0`; and its selection-commit allowlist half (REQ-V170-REV-01 item 8) skipping, no such commit existing yet. | `lint-docs` green against the T0 skeleton's ledger section; docs match reality; `pyproject.toml` byte-unchanged, proved by `git diff --stat`; `T-V170-ACC-03` green with two halves skipped for their recorded reasons and the version half asserting `1.6.0` |
| **T9** | `mutation_check.py`: the nine `v170-*` entries; `config/quality_gates.yaml`: the `mutation-v170` gate and both re-measured timeouts; `--list` recorded. | `--select v170-` green; `mutation-all` green inside its new timeout; the matrix test green |
| **T10** | **Review (REQ-V170-REV-01) in a clean context, then every gate**: gates 1–4 and 6 verbatim, `checks.py run --profile full --since <base>`, and gate 5 re-run now that the source has changed. **Every source, test and config fix of this run lands here or earlier**; the single exception is T12. | findings closed or waived; every gate green; the tree entering stage C is final |
| **T11** | **Stage C (§9) — conditional exit.** C1, then **C2 unconditionally**, then C3 only if neither passed the quality gate (REQ-V170-BEN-05); the gated comparison into `bench-v1.7.0.md`. **The tree is frozen from the first candidate.** | each candidate document `check`-valid, `meta.aborted` absent, comparability `None` against the baseline; the cheapest quality-passing candidate identified by REQ-V170-BEN-05's rule; **a cost-gate FAIL continues to T12 but forbids the tag**; **no quality-passing candidate, or an unresolved `EXIT_NOT_COMPARABLE`, skips T12 entirely** — version stays `1.6.0`, no tag, and T13/T14 finalise the failure report (REQ-V170-BEN-07); an instrument mismatch surfacing here is REQ-V170-BEN-01's STOP on the same routing |
| **T12** | **The selection commit — conditional task, run only when a quality-passing candidate exists** (REQ-V170-POL-07, REQ-V170-VER-01, REQ-V170-ACC-03): the two policy default literals in `config.py` set to exactly the selected candidate's process-environment treatment, `pyproject.toml`'s `project.version` `1.6.0` → `1.7.0`, plus the documented echoes of both in `.env.example`, `README.md` and `AGENTS.md`. Nothing else. **Skipped whole** when no candidate passes quality, when the comparison stays `EXIT_NOT_COMPARABLE`, or when either STOP fired. | `T-V170-ACC-03` green against the committed candidate documents, its version half reading `1.7.0`; the candidate-metadata check recorded; its **third half** green — `git diff --name-only` from T11's tip to this commit lists only those **five** files and its hunks touch only the two variable names and the version (REQ-V170-REV-01 item 8) — so `git diff` against T11's tip shows only those **five** files — or, on a skipped T12, the report records the skip and its cause and `pyproject.toml` still reads `1.6.0` |
| **T13** | **Provisional** `report-v1.7.0.md` (RPT-03 minus item 4's tip SHA and T14 artefacts, ledger row included), `tg-post-v1.7.0.md` (RU, < 1500 chars), `docs/llm-usage.md` rows. | `lint-docs` green against the repointed `report_path`; `wc -m` recorded; no self-referential SHA claimed |
| **T14** | **Final acceptance (REQ-V170-ACC-03)**: six verbatim gates — with `T-V170-ACC-03`'s three halves green inside gate 3, its selection-commit half no longer skipping when T12 ran — `full --since <base>`, `replay --range <base>..<implementation-tip>`, Appendix B; the single evidence-only commit; then the annotated tag `v1.7.0` **on that commit, only on PASS**. | every gate green on the tree that ships; the tag recorded, or its deliberate absence recorded with the verdict that withheld it |

**REQ-V170-ORD-02 (MUST) — `T-STOP`, the one finalisation procedure both early
exits use.** T1's instrument STOP (REQ-V170-BEN-01) and T3's stage-A STOP
(REQ-V170-RSN-06) each promise a finished deliverable — a report, a Russian
tg-post, usage rows, a ledger row, committed evidence and a verdict — but
neither reaches T13 or T14, which is where all of that is otherwise written. The
round-1 spec said only "STOPS", leaving the prompt, the placeholder removal, the
branch-appropriate gates and the closing commit undefined. **`T-STOP` is that
missing tail. It is a procedure, not a numbered task** — §16 still has fifteen
tasks — and it is invoked, identically, by whichever of T1 or T3 fired.

**§13.1 has no `T-STOP` row because `T-STOP` is not a task; this requirement is
its reading map.** The only repository file it opens beyond this run's own
artefacts is `config/quality_gates.yaml`, for item 4's temporary repoint, so
REQ-V170-EC-07's file-count threshold is measured against that one file and the
report records the delegation decision for the procedure as it does for a task.
The steps:

1. **Finalise `docs/reports/report-v1.7.0.md`** from T0's skeleton: every
   REQ-V170-RPT-03 item that the branch reached, and for every item it did not,
   the explicit words *"not reached: <task> STOP"* — never a blank, never a
   `TBD`. The verdict is stated in REQ-V170-RSN-06's or REQ-V170-BEN-01's own
   vocabulary, with its cause.
2. **Finalise `docs/reports/tg-post-v1.7.0.md`** — Russian, under 1500
   characters by `wc -m` with the count quoted, per REQ-V170-RPT-04. A STOP is
   reported, not omitted.
3. **Append the usage rows** for every prompt of the run to
   `docs/llm-usage.md`'s existing table, and fill the **ledger row** section of
   REQ-V170-RPT-01 completely — `Ver` is `1.7.0`, the release identity, whatever
   `pyproject.toml` reads; no cell is left provisional. The operator pastes it.
4. **Run the branch-appropriate gates, and repoint `lint-docs` without
   committing the repoint.** T8 never ran on this branch, so
   `config/quality_gates.yaml:313` still names `docs/reports/report-v1.5.md`
   and `checks.py lint-docs` would check a two-release-old file while the
   procedure claimed it checked this release's report (REQ-V170-RPT-02).
   Therefore: change **only** `lint-docs.report_path`, to
   `docs/reports/report-v1.7.0.md`, in the **working tree**; run
   `python3 devtools/checks.py lint-docs`; **restore the file**; and prove
   `git diff -- config/quality_gates.yaml` is **empty** before the closing
   commit of item 6, the empty diff going in the report. No other key of that
   file is touched, no `--report-path` option is added to `checks.py`, and the
   repoint is in no commit. Then the secret scans — `gitleaks-tree` over the
   tree and the run's own artefacts. Both gates MUST exit 0.
5. **Account for every gate, one way or the other, on the tree that ships.**
   *"After all `T-STOP` artefacts are finalized and before the closing commit,
   rerun gates 1–4 and 6 against that final working tree and record their fresh
   exit codes. Gate 5's post-T1 repetition, replay, and mutation-v170 alone are
   N/A for the stated reasons."* Reusing T0's exit codes is **not** enough, and
   the round-2 spec was wrong to allow it: T0 is followed by this run's own
   prompts and commits, the finalised report, the usage rows and — on a T3
   STOP — every stage-A pair artefact and TTFT sidecar, so the tree those gates
   were green against is not the tree that ships, and a standards, secret or
   repository-shape failure caused by those artefacts would go unseen. Gates
   1–4 and 6 stay **unconditional** (REQ-V170-GATE-01) and are recorded twice:
   T0's exit codes and these fresh ones (REQ-V170-RPT-03 item 1). The three
   `N/A` records keep their reasons: live gate 5 (`bot.py --selftest-live`)
   after its T1 run and `checks.py replay --range`, because REQ-V170-GATE-01's
   T10 and T14 runs belong to a code path this branch never enters; and the
   `mutation-v170` profile gate, because T9 never created it. Nothing is
   silently skipped.
6. **Commit the permitted evidence artefacts and nothing else**: the report, the
   tg-post, the usage rows, and — on a T3 STOP — every stage-A pair artefact and
   TTFT sidecar, each sidecar carrying its `calibration` block (REQ-V170-RSN-07)
   and none carrying a nonce, with `git diff` proved empty of the scratch patch
   first (REQ-V170-RSN-01). No source, test or configuration file is in this commit.
   `--no-verify` is forbidden here as everywhere (REQ-V170-EC-09).
7. **Prove the negative**: `pyproject.toml` still reads `1.6.0`, `git tag -l`
   still shows exactly `v1.3`, `v1.3-baseline` and `v1.6.0`, and the report says
   so. **No bump, no tag, no evidence-only commit of REQ-V170-ACC-03** — that
   commit exists only on a branch that reached T14.
8. **Terminate.** No later task of §16 runs, and REQ-V170-CAR-01's carried
   sanitiser goes to v1.8.0 with the rest of §§6–9, stated as such
   (REQ-V170-RSN-06).

---

## 17. Non-goals for v1.7.0

Implementing any of these is a defect.

| ID | NON-GOAL | why |
|---|---|---|
| REQ-V170-NG-01 | Changing `devtools/bench_scenarios.py` in any way — a new scenario, a moved ceiling, an edited turn | `meta.scenarios_sha256` is locked; one byte voids `baseline-v1.6.0.json` and with it this release's only gate |
| REQ-V170-NG-02 | A "do not think" / "answer directly" instruction in the system prompt or a tool description | `meta.prompt_tools_sha256` is locked; and a prompt-level plea is not a mechanism |
| REQ-V170-NG-03 | A fresh baseline, a re-recorded `baseline-v1.6.0.json`, or gating against a baseline produced in this run | REQ-V170-BEN-01; gating on an instrument recorded in the same run is circular |
| REQ-V170-NG-04 | A new dashboard page, a new JSON endpoint, a new `metrics.py` function or a reasoning UI | the existing per-purpose `reasoning_share` (metrics.py:397-416) already answers the question |
| REQ-V170-NG-05 | Adding any reasoning key to `REQUEST_DEFAULTS` or to `bench.constants()` | both are embedded in the **locked** `meta.constants`, and `tests/test_v14_patch.py:89-92` forbids it |
| REQ-V170-NG-06 | Any new Python dependency, an OpenAI/LM Studio SDK, an OTLP exporter, a YAML or HTTP framework | REQ-V170-EC-01; stdlib plus `httpx` and `python-dotenv` |
| REQ-V170-NG-07 | A third `purpose` value in the `llm_calls` `CHECK` constraint | the reasoning tag is derived, not stored as `purpose` (REQ-V170-POL-02); widening the constraint is a migration nobody needs |
| REQ-V170-NG-08 | A live OpenRouter smoke run, or any paid inference | the off form is confirmed from documentation and asserted offline (`T-V170-POL-05`); v1.4's POL-07 smoke is not carried |
| REQ-V170-NG-09 | Tuning `LLM_MAX_TOKENS`, `LLM_SUMMARY_MAX_TOKENS`, `LLM_TIMEOUT_S`, `CONTEXT_WINDOW_MESSAGES`, `SUMMARY_MAX_TOKENS` or the sampling literal as a cost lever | they are the locked instrument; changing one makes the pair non-comparable, and REQ-V14-NG-01/-02 stand |
| REQ-V170-NG-10 | A second summary retry, a third attempt, or an exception surfaced to the user turn when the budget runs out | REQ-V160-TQ-01 item 4 stands; REQ-V170-SUM-02 records the outcome instead |
| REQ-V170-NG-11 | A feature flag for the summary budget or for the rescue retry | the benchmark measures the shipped configuration (REQ-V160-TQ-08) |
| REQ-V170-NG-12 | Refactoring `dashboard_server.py` to clear its 19 skylos shadow findings | shadow findings are informational; a refactor after the freeze would void the candidates, and this release does not touch that module |
| REQ-V170-NG-13 | Retroactive tags, renaming existing spec/report/prompt files, moving `v1.3`/`v1.3-baseline`/`v1.6.0`, or editing spec-v1.6.0's text | REQ-V160-VER-02 and -NG-16; a tagged spec is a historical record, errata included |
| REQ-V170-NG-14 | Deleting `storage._MIGRATION_2_TO_3` or any other pre-existing dead code found in passing | pre-existing dead code is **reported**, never removed as a side effect (lab rule 3) |
| REQ-V170-NG-15 | A per-failover-attempt `llm_calls` row, an attempt-level observer callback in `llm/failover.py`, or any second write path beside `_record_llm_call` | the wrapper exposes no such seam today (measured at `054b103`) and REQ-V170-OBS-03 records the logical call instead; building the seam is a v1.8.0 decision, not a side effect of a reasoning release |

---

## Appendix A — requirement traceability

Every `MUST` appears exactly once; the sixty-nine rows below are in bijection
with the sixty-nine `MUST` ids defined in §§1–16. NON-GOALs live in §17's table
and are not repeated here. "Verified by" names a test id, a negative test, a
Gherkin scenario or a recorded artefact — never "by inspection".

| Requirement | Source | Verified by |
|---|---|---|
| `REQ-V170-EC-01` — boundary, the **exhaustive** external-effects allowlist (PRE-03's documentation reads included), zero new deps, repair budget 5 | REQ-V160-EC-01; round-3 critique | `uv.lock` and `pyproject.toml` diffs show no new distribution; the report's external-effects record |
| `REQ-V170-EC-02` — test-first | REQ-V160-EC-02 | the report's per-task "failed first for the right reason" record |
| `REQ-V170-EC-03` — 1016-test floor, exhaustive §14.1 | measured at `89786ef` | `pytest --collect-only -q` at T0 and T14 |
| `REQ-V170-EC-04` — secrets discipline, four `.env` reads, idiom 1 proving absence as well as presence | REQ-V160-EC-04; round-3 critique | `gitleaks-tree`; the report's `.env` interaction record; `E10` |
| `REQ-V170-EC-05` — backward compatibility, binding until T12 and superseded there by POL-07 | REQ-V1-EC-05; round-3 critique | `T-V170-SUM-01`; §14.1's unamended-test list; `T-V170-ACC-03`'s version half |
| `REQ-V170-EC-06` — benchmark-affecting, rule **satisfied** | `AGENTS.md:149-155` | the report's "Benchmark-affecting changes"; `bench-v1.7.0.md` |
| `REQ-V170-EC-07` — RLM rule | REQ-V160-EC-07 | §13.1's map; the per-task delegation record |
| `REQ-V170-EC-08` — prompt format | REQ-V15-PRM-01 | `checks.py lint-docs`; `E11` |
| `REQ-V170-EC-09` — `--no-verify` ban, one prompt one commit | REQ-V15-EC-09, REQ-V160-EC-10 | `replay --range <base>..<implementation-tip>`; the attestation sentence |
| `REQ-V170-AMEND-01` — amendment table | this spec | §14.1's amended and not-amended lists |
| `REQ-V170-PRE-01` — preconditions, the two policy keys proved **absent** from `.env` | REQ-V160-PRE-01; round-3 critique | the T0 record; the blocker template on failure; `E10` |
| `REQ-V170-PRE-02` — operator inputs block at T0; a named address is a validated literal IP | REQ-V160-PRE-04, `AGENTS.md` `go`; round-2 critique | the report's `## Operator inputs`; `E10` |
| `REQ-V170-PRE-03` — two phases: the deduplicated ordered address probe and the documentary reads, then the live TTFT-shape probe **after** PRE-04 | REQ-V160-PRE-03; round-2 critique; round-3 critique | the report's URLs, routes, dates and the four resolved VERIFY values, the fourth recorded as the run's second inference; `E9`, `E10` |
| `REQ-V170-PRE-04` — the instrument proved without disclosure, and proved before any inference; item 7 is the run's first | erratum 5; REQ-V160-PRE-04; round-2 critique; round-3 critique | the seven recorded checks in order; `E9`, `E10` |
| `REQ-V170-TREE-01` — new files | this spec | the T14 tree listing |
| `REQ-V170-TREE-02` — changed files, `bench_scenarios.py` frozen | REQ-V170-NG-01 | `git diff --stat <base>..<tip>` |
| `REQ-V170-RSN-01` — pair contract, S05 and S12 | REQ-V14-RSN-01 | the pair artefacts under `docs/assets/bench/`; the `git diff`-empty record |
| `REQ-V170-RSN-02` — candidates a…e in fixed order | REQ-V14-RSN-02 | the report's pair table, one row per member |
| `REQ-V170-RSN-03` — honored, per purpose | REQ-V14-RSN-03 | the rendered `## Reasoning` sections of both members |
| `REQ-V170-RSN-04` — shippability judged per purpose | REQ-V14-POL-05; agent.py:1045 | the per-purpose shippability table; the resent/new token record |
| `REQ-V170-RSN-05` — budget, ≤ 3 per candidate, ≤ 15 total; calibration requests outside it and an abandoned confirming pair charged nothing | REQ-V14-RSN-05; round-3 critique | the pair count in the report against the budget |
| `REQ-V170-RSN-06` — mechanism table and the STOP rule | REQ-V14-RSN-06 | the per-purpose mechanism table; the STOP verdict if it fires |
| `REQ-V170-RSN-07` — the confirming mixed-policy pair: no token inflation, and a TTFT-evidenced cache whose rate comes from a **nonce-cold calibration** with a warm proof, else `summary` only | round-1 critique; round-2 critique; round-3 critique; metrics.py:75-91; LM Studio `stats.time_to_first_token` | the `rsn17-<letter>-mixed-{control,mixed}.json` artefacts and their `-ttft.json` sidecars with their `calibration` blocks; check 1's two figures and check 2's calibration, rate, prediction, measured value and ratio in the pair table, or the recorded fallback naming its trigger; `E13` |
| `REQ-V170-POL-01` — two environment variables, whose displayed literals are the pre-T12 compatibility defaults | REQ-V14-POL-01; round-3 critique | `T-V170-POL-01`, `T-V170-POL-07`, `N1`, `N2`, `N3` |
| `REQ-V170-POL-02` — the purpose tag, pure, in `llm/base.py` | REQ-V14-POL-02 | `T-V170-POL-02` |
| `REQ-V170-POL-03` — `resolve_reasoning` returns `ReasoningRequest` | REQ-V14-POL-03 | `T-V170-POL-03` |
| `REQ-V170-POL-04` — one `ReasoningRequest` parameter, five definitions, five sites | REQ-V14-POL-04 | `T-V170-POL-04`; mutation `v170-failover-drops-reasoning` |
| `REQ-V170-POL-05` — the two provider forms, applied from `mechanism`/`value` alone | REQ-V14-POL-07; PRE-03 | `T-V170-POL-05` |
| `REQ-V170-POL-06` — `build_payload`'s `reasoning_fields` | this spec | `T-V170-POL-06`, `N4` |
| `REQ-V170-POL-07` — the shipped default and the version bump follow stage C, in one five-file commit | REQ-V14-BEN-09 | `T-V170-POL-07`, `T-V170-ACC-03`; the report's flipped-after-measurement sentence |
| `REQ-V170-OBS-01` — two columns, schema 4 → 5 | REQ-V14-OBS-01 | `T-V170-OBS-01`, `N8`; `E3` |
| `REQ-V170-OBS-02` — one span attribute | REQ-V160-TRC-09 | `T-V170-OBS-02` |
| `REQ-V170-OBS-03` — one row per `llm.complete` invocation | REQ-V14-OBS-03; llm/failover.py at `054b103` | `T-V170-OBS-03`, `T-V170-OBS-04`; `E4` |
| `REQ-V170-SUM-01` — one budget for the whole path | report-v1.6.0 S18 | `T-V170-SUM-01`; `E5` |
| `REQ-V170-SUM-02` — the 30 s floor and the skipped request | this spec | `T-V170-SUM-02`, `N5`; mutation `v170-summary-floor-ignored` |
| `REQ-V170-SUM-03` — every request's timeout from the remaining budget, attempt 1 included | agent.py:1094; llm/base.py:250 | `T-V170-SUM-03`, `N5`; mutation `v170-summary-retry-ignores-budget` |
| `REQ-V170-SUM-04` — the rescue retry forces reasoning off | report-v1.6.0 S18 attempt 1 | `T-V170-SUM-04`; mutation `v170-rescue-retry-keeps-reasoning` |
| `REQ-V170-SUM-05` — `_check_timeout_budget` amended, not removed | REQ-V14-REL-01, REQ-V160-TQ-02 | `T-V170-SUM-05`; mutation `v170-summary-floor-check-removed` |
| `REQ-V170-BEN-01` — same instrument, mismatch STOPS | erratum 5; REQ-V160-BEN-05 | the six recorded instrument checks; `E9` |
| `REQ-V170-BEN-02` — comparability accepts a treatment-only pair | measured `comparability()` refusal | `T-V170-BEN-02`, `T-V170-BEN-03`; mutation `v170-config-hash-includes-treatment` |
| `REQ-V170-BEN-03` — the unlocked `meta.reasoning` block, additive under schema 2 | this spec; baseline-v1.6.0.json measured at `054b103` | `T-V170-BEN-01`, `T-V170-BEN-04`; the candidate documents |
| `REQ-V170-BEN-04` — process-env prefix carrying **both** variables always, `--timeout-s 1800`, the merge | config.py:202; bench.py:756-764; round-3 critique | `T-V170-BEN-04`, `N6`; the per-candidate invocation record quoting each prefix in full |
| `REQ-V170-BEN-05` — C1 and C2 unconditional with C2's **explicit empty** purpose set, C3 conditional, cheapest defined | user decision; round-1 critique; round-3 critique | the committed `cand-v170-*.json` documents and their `meta.reasoning.on_purposes`; the report's selection arithmetic |
| `REQ-V170-BEN-06` — quality gate, S13…S18 executably blocking at 3/3 | errata 3 and 6, superseded | `T-V170-BEN-04`, `T-V170-BEN-05`; mutation `v170-gate-ignores-3of3`; `E9` |
| `REQ-V170-BEN-07` — cost gate and the four verdicts | bench.py:1530-1549 | `bench-v1.7.0.md`'s verdict block; `E12` |
| `REQ-V170-BEN-08` — latency reported, never gated | REQ-V160-GATE-05 | the report's per-purpose p50/p95 and per-scenario wall-clock tables |
| `REQ-V170-CAR-01` — `--tag` sanitised before any path | v1.6.0 review 🟡, waived | `T-V170-CAR-01`, `N7`; mutation `v170-tag-sanitiser-removed` |
| `REQ-V170-CAR-02` — Appendix B refreshed for S15/S18 | spec-v1.6.0's stale Appendix B scenario 13 | Appendix B `E9` of this spec |
| `REQ-V170-VER-01` — MINOR bump, conditional, inside T12's selection commit alone | REQ-V160-VER-02 | `T-V170-VER-01`, `T-V170-ACC-03`'s version half; `pyproject.toml` at the tip; `E9` |
| `REQ-V170-VER-02` — tag last, on the evidence commit, only on PASS | REQ-V160-VER-04 | `E12`; `git tag -l` and the annotated-tag message |
| `REQ-V170-VER-03` — three-number naming | REQ-V160-VER-05 | the T14 tree listing |
| `REQ-V170-RPT-01` — the ledger row | REQ-V160-RPT-01 | `checks.py lint-docs`; `E11` |
| `REQ-V170-RPT-02` — `lint-docs` repointed | quality_gates.yaml:313 | `T-V170-RPT-02`; `E11` |
| `REQ-V170-RPT-03` — the report's thirteen items | `standards/reporting.md` | the report itself, item by item |
| `REQ-V170-RPT-04` — usage rows, tg-post, docs that must not drift | `standards/reporting.md` | `wc -m` on the tg-post; the `AGENTS.md` diff |
| `REQ-V170-GATE-01` — the six gates verbatim; 1–4 and 6 rerun on a `T-STOP` tree | `AGENTS.md:95-100`; round-3 critique | the gates table with exit codes, twice on a `T-STOP` branch |
| `REQ-V170-GATE-02` — one new gate, two re-measured timeouts | REQ-V160-GATE-02 | `mutation-v170` green; the re-measurement arithmetic |
| `REQ-V170-GATE-03` — the profile matrix, findings fixed not suppressed | REQ-V160-GATE-03/-04 | `tests/test_v15_standards.py:1726`; the scanner summary |
| `REQ-V170-TST-01` — offline, deterministic, no network | REQ-V12-OFF-01 | the `conftest.py` guard; the suite running with the network down |
| `REQ-V170-TST-02` — test-first, independent expected values | `standards/workflow.md` §4 | the report's per-test record |
| `REQ-V170-TST-03` — at least nine `v170-*` mutations | REQ-V160-TST-03 | `mutation_check.py --select v170-` |
| `REQ-V170-TST-04` — every `find` matches exactly once | REQ-V160-TST-04 | `mutation_check.py --list` output in the report |
| `REQ-V170-ACC-01` — Appendix B executed | REQ-V160-ACC-01 | the per-scenario pass/fail record |
| `REQ-V170-ACC-02` — regression check | REQ-V160-ACC-02 | the unamended-test list; gates 3 and 6 |
| `REQ-V170-ACC-03` — provisional report, frozen tip, freeze, one selection commit proved equivalent and policed by diff | REQ-V160-ACC-03; round-1 critique; round-3 critique | `T-V170-ACC-03`'s three halves; the candidate-metadata check; the T0 `.env` key-absence record; the evidence-only commit; `replay --range` |
| `REQ-V170-ACC-04` — the 5-cycle repair budget | REQ-V160-ACC-04 | the report's fix-cycle count |
| `REQ-V170-REV-01` — clean-context review before measurement; the T12 commit policed by an automated allowlist check, not a second review | `AGENTS.md:175-179`; round-3 critique | the review prompt in `docs/prompts/`; the findings table; `T-V170-ACC-03`'s third half and its recorded `git diff --name-only` |
| `REQ-V170-ORD-01` — the measurement-first order, fifteen tasks, three conditional exits, one conditional task | this spec; round-1 critique; round-2 critique | the commit sequence; `replay --range` |
| `REQ-V170-ORD-02` — `T-STOP`, the shared finalisation of both early exits, with the temporary `lint-docs` repoint and gates 1–4 and 6 rerun on the shipping tree | round-2 critique; round-3 critique; REQ-V170-RSN-06, REQ-V170-BEN-01 | on a STOP: the finalised report and tg-post, the ledger row, `lint-docs` and `gitleaks-tree` exit 0, the empty `git diff -- config/quality_gates.yaml`, the fresh exit codes of gates 1–4 and 6, the evidence commit, and `pyproject.toml` at `1.6.0` with `git tag -l` unchanged |

---

## Appendix B — acceptance scenarios (Gherkin, written before code)

```gherkin
# E1-E8 run offline against fakes, a fake clock and a temporary database in a
# tmp_path fixture. E9-E13 run against this repository, the live LM Studio and
# the recorded documents.
# SAFETY: no live credential is ever used as a test value; no scenario reads or
# prints .env contents; no scenario names or reads the private corpus.

Scenario: E1 — the tag is a pure function of purpose and exposed tools
  Given a request with purpose "agent" and a non-empty tools list
  Then reasoning_tag returns "tool-round"
  When the same request withholds tools, passing None or an empty list
  Then reasoning_tag returns "final"
  When the purpose is "summary"
  Then reasoning_tag returns "summary" whatever the tools argument is
  And the function reads no Config, no environment variable and no module global

Scenario: E2 — model-default sends a byte-identical request
  Given LLM_REASONING_POLICY is unset
  When one agent round and one summary call are built
    Then each payload is byte-identical to the payload v1.6.0 builds for the
       same inputs, and carries no reasoning key of any kind
  And meta.prompt_tools_sha256 over this tree equals the baseline's
  And bench.constants() and llm.base.REQUEST_DEFAULTS contain no key whose
      lower-case form holds "reasoning"

Scenario: E3 — a v4 database migrates without losing a row
  Given a database at schema version 4 holding llm_calls and tool_calls rows
  When init_schema runs
    Then the version reads 5, llm_calls carries reasoning_requested and
       reasoning_honored, and every pre-existing row survives with NULL in both
  And the same holds for databases starting at 1, 2 and 3
  And running init_schema again changes nothing

Scenario: E4 — every invocation records what it asked for, and a failover is
    one invocation
  Given a scripted turn with one tools-exposed agent round and one tools-withheld
      final round
  And two summary invocations, the first truncating into its retry and the
      second returning invalid JSON into its repair call — the two branches
      being mutually exclusive within one invocation
  And a failover inside one of those six invocations, whose primary raises and
      whose secondary answers
  When the turn completes
    Then exactly six llm_calls rows carry a non-NULL reasoning_requested, each
       written through _record_llm_call and no other path
  And the failover contributes no seventh row: its row names the secondary in
      provider and model, describe() being read after the invocation
  And a row whose call raised before a response carries its requested value and
      NULL honored
  And a row whose provider reported no reasoning tokens and produced no
      reasoning characters carries NULL honored, never 1 — absent evidence is
      never read as compliance
  And every row's reasoning tag is recoverable from its own purpose and
      tools_exposed columns, no column having been added for it
  And each row's span carries tg_agent.reasoning.requested with the same value

Scenario: E5 — the summary path spends one budget, not one per attempt
  Given budget_s is 100 seconds on a fake clock and the client's own timeout is
      600 seconds
  Then the deadline is taken before attempt 1, and attempt 1 is issued with an
      HTTP timeout of 100 seconds — neither None nor the client's 600
  When attempt 1 consumes 40 seconds and the response is truncated
    Then the retry is issued with an HTTP timeout of the remaining 60 seconds,
       not the client's own
  When budget_s is 10 against that same 600-second client
  Then attempt 1 is still issued, with an HTTP timeout of 10 seconds, and no
      request is ever issued on a non-positive remainder
  When attempt 1 consumes 80 seconds instead
  Then the retry is not issued at all, exactly one llm_calls row exists, the
      turn completes without a summary, no exception escapes, and one redacted
      warning names the elapsed and the remaining seconds

Scenario: E6 — the rescue retry never reasons
  Given a summary-shippable mechanism exists
  When the truncation retry is issued under LLM_REASONING_POLICY=model-default
  Then its ReasoningRequest.value is "off"
  And the same holds under off and under by-purpose with summary switched on
  And attempt 1 under by-purpose with summary switched on still resolves to "on"

Scenario: E7 — a tag cannot reach outside .bench/
  Given bench.py run is invoked with --tag ../escape
    Then it exits EXIT_ERROR with a message naming --tag and the permitted
       charset, and shutil.rmtree is never called
  And --tag "." and --tag ".." are refused the same way
  And --tag cand-v170-off is accepted

Scenario: E8 — the baseline is comparable with itself and with a treatment
  Given docs/assets/bench/baseline-v1.6.0.json
  When comparability is asked to compare it with itself
  Then it returns None
  When it is compared with a document differing only in env_flags'
      LLM_REASONING_POLICY, LLM_REASONING_ON_PURPOSES and git_commit
  Then it returns None
  When it is compared with a document whose generation_settings differ
  Then it returns the locked-meta-field message and report --gate exits 2
  And config_sha256 is unchanged by the two new Config fields alone

Scenario: E9 — a candidate is measured against a named, unchanged instrument
  Given every task through T10 is complete and the working tree is clean
  And .env was updated by a single-line sed, confirmed by a grep -q that prints
      nothing, and its contents were never emitted
  And grep -q proved LLM_MAX_TOKENS=4096 and LLM_TIMEOUT_S=600 without printing
  And exactly one served model id equals qwen/qwen3.8-27b and equals
      cfg.lmstudio_model — an equality, never a substring, two matches or none
      being a STOP — the version reads "Bionic v1.1.1" and the loaded context
      length reads 42496
  And cfg.obs_capture_content is False and the metadata producer is proved to
      emit meta.obs_capture_content false
  And all six of those instrument values were established before the first live
      inference, the one-completion preflight included
  And the one-completion preflight then returns a non-empty assistant message
  And the TTFT-shape probe is the run's second inference, issued only after that
      preflight returned and before any stage-A pair, its system prompt
      beginning with a fresh random 32-hex nonce
  When a candidate is run with the treatment set by a process-environment
      prefix, --repeats 3, no --only and --timeout-s 1800
    Then its meta matches every locked field of baseline-v1.6.0.json but
       env_flags and git_commit, meta.aborted is absent, and bench.py check
       exits 0
  And each of S13, S14, S15, S16, S17 and S18 succeeded 3 times out of 3 — S15
      and S18 included, superseding errata 3 and 6 — enforced by report --gate
      itself, which refuses PASS and exits 1 while any of the six is below 3/3
  And no scenario lost two or more repeats
  When C1 and C2 have both been run, and C3 only because neither passed quality
  Then the shipped candidate is the quality-passing one with the lowest
      C_conservative, ties broken by C_plain and then by catalogue order
  When the selection commit changes only the two policy default literals,
      pyproject.toml's project.version and their documented echoes — five files
    Then an unprefixed load_config on the final tree resolves to the policy and
       the sorted purpose set of exactly one committed candidate's
       meta.reasoning
  And pyproject.toml reads 1.7.0, bumped in that commit and in no earlier one
  And git diff --name-only from T11's tip to that commit lists exactly those
      five files, its config.py hunk touching only lines that carry one of the
      two variable names and its pyproject.toml hunk only the version line
  When no candidate passes quality instead, or the comparison stays
      EXIT_NOT_COMPARABLE
  Then the selection commit is never made, pyproject.toml still reads 1.6.0, no
      tag exists, and the failure report is finalised
  When any other source, test or config file is then modified
  Then the candidate is void and stage C is repeated in full

Scenario: E10 — the run never discloses a secret and never guesses the
    instrument
  Given the run is complete
    Then no report, prompt, spec or commit contains a credential value, a .env
       line, a private corpus name or a path under data/
  And the only .env interactions recorded are the four idioms EC-04 permits
  And no .env.bak file was ever created
  And grep -q proved at T0, by key name and without disclosure, that neither
      LLM_REASONING_POLICY nor LLM_REASONING_ON_PURPOSES is present in .env,
      a present key having been a blocker rather than something rewritten
  When the operator's version or context length disagrees with the baseline
  Then the run stopped with a report and created no tag

Scenario: E11 — the report carries a paste-ready ledger row that is actually
    linted
  Given the run is complete
  When checks.py lint-docs runs
    Then its configured report_path names docs/reports/report-v1.7.0.md, and
       that file holds a "Ledger row" section whose fenced row's cell count
       matches the ledger header's — the four things _lint_report_ledger
       actually checks
  And at final acceptance, which the gate cannot check, that row carries no
      placeholder cell
  And every prompt file numbered 103 and above has all seven bullets and four
      blocks

Scenario: E12 — the tag is created last, and only when the gate passed
  Given every gate of section 13 is green on the final tree
  When the evidence-only commit lands
    Then it records <implementation-tip>, the replay output and the intended tag
       name v1.7.0, and claims nowhere that the tag exists
  When bench.py report --gate returned PASS
  Then git tag -a v1.7.0 is created on that commit and nothing follows it
  When it returned FAIL on the cost gate instead
  Then no tag exists, pyproject.toml still reads 1.7.0, the report states the
      shortfall as a number, and the run stops for the operator
  And git tag -l still shows v1.3, v1.3-baseline and v1.6.0 unchanged
  And nothing is pushed

Scenario: E13 — the cache evidence is calibrated cold, or it is not used
  Given the fourth VERIFY marker found stats.time_to_first_token populated on
      the OpenAI-compatible route the harness uses
  And a confirming mixed-policy pair is about to run
  When the harness issues, immediately before each member, one scratch request
      whose system prompt begins with a fresh random 32-hex nonce
    Then that request is cold by construction, its rate is its prompt tokens
       divided by its time to first token, and the identical request issued once
       more returns a time to first token at most 0.35 times the first — the
       warm proof
  And both calibration requests go through the harness's own client, route and
      request shape, and neither appears in the member's bench document, in its
      runs list or in the fifteen-pair budget — only in the sidecar's
      calibration block, which records the nonce's length and never the nonce
  And the member's predicted cold TTFT for the final round is its prompt tokens
      divided by that rate, and the cache counts as preserved only when the
      measured final-round TTFT is at most 0.35 times the prediction, on each
      run and never on an average
  When the warm proof fails instead, or the field was absent on that route
    Then check 2 is unavailable, the confirming pair is abandoned before either
       member runs and consumes no pair, the summary-only fallback binds, both
       agent tags ship none, and the report names which of the two triggers
       fired
  And on that branch this scenario is recorded not applicable with that same
      reason, never as a failure
```

## Appendix C — cross-review log

**Rounds 1–3 of 3, termination: `round_limit`** — the lab's stop criterion (a
round without Critical/High findings) was not reached within the round budget;
challenger **OpenAI Codex `gpt-5.6-sol`**, called through the lab's file-based
cross-review seam with the spec passed by file. 28 findings, 27 accepted, 5
adapted where the repository, the instrument or a fixed execution decision
contradicted the premise, and 1 rejected — R1-1, the `.env` process-loading
objection, which contradicts the standing REQ-V160-EC-04 of spec-v1.6.0.

**Round 1 of at most 3** — challenger **OpenAI Codex `gpt-5.6-sol`**,
called through the lab debate loop's cross-review seam with the spec passed by
file. Ten findings, nine accepted, three of those adapted where the repository
or a fixed execution decision contradicted the premise, and one refused.

### Round 1 of at most 3 — against spec-v1.7.0 as committed (054b103); nine accepted (three adapted), one rejected

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R1-1 | Crit | EC-04, PRE-03, PRE-04, BEN-04 | rejected | The `.env` prohibition of REQ-V160-EC-04 binds the **agents**, not the bot and bench **processes**, which load `.env` through `python-dotenv` by design; supplying the live values as process-environment variables instead would put the Telegram token into the `go` request itself, so EC-04's four permitted machine reads, PRE-03's single-line `sed` plus confirming `grep -q`, PRE-04's two value confirmations and BEN-04's `load_dotenv(..., override=False)` argument — the very reason a command prefix wins without touching the file — all stand unchanged |
| R1-2 | Crit | ORD-01, §13.1, RSN-06, EC-06, ACC-03, `E9` | accepted, adapted | §16 reordered into fifteen measurement-first tasks — preconditions → live preflight → stage-A harness → stage A → the four code tasks → docs/version → mutations → review and every gate → stage C → the selection commit → the provisional report → final acceptance — with §13.1's per-task map, every body reference and Appendix B `E9` renumbered, and the freeze restated once in ORD-01: all source, test and config changes except the post-measurement default-selection commit land **after** stage A and **before** the first stage-C candidate, which is what makes RSN-06's "STOP, §§6–9 not executed" branch true and lets `REASONING_MECHANISMS` be written from a table that already exists |
| R1-3 | Crit | POL-03, POL-04, POL-05, POL-06, OBS-01…-03, AMEND-01, §14.1, `T-V170-POL-03`/`-04`/`-05`/`-06`, REV-01 | accepted, adapted | One keyword-only parameter carries a frozen `ReasoningRequest(value, mechanism, tag)` returned by `resolve_reasoning(policy, on_purposes, tag, mechanisms)` over a `(tag, value)`-keyed table of frozen `ReasoningMechanism`s; providers apply `mechanism` alone and never read the tag, `openrouter` branches on `value` alone, `_try_other` forwards the object unchanged so the same tag reaches the secondary, and no third parameter and no third column appear — the tag is recovered from the row's existing `purpose` and `tools_exposed` by `reasoning_tag`'s own rule |
| R1-4 | Crit | BEN-06, AMEND-01, `T-V170-BEN-04`, `T-V170-BEN-05`, REV-01, TST-03 | accepted | BEN-06 item 3 became executable: `devtools/bench.py` gains the module constant `GATE_REQUIRED_FULL_SCENARIOS` and `report --gate` refuses PASS while any of S13…S18 is below 3/3 on the candidate side, exiting 1 and naming every failing scenario; `T-V170-BEN-04` proves S18 = 2/3 → exit 1 **and** that item 2's two-repeat rule would not have caught it, the new mutation `v170-gate-ignores-3of3` guards the check, and `devtools/bench_scenarios.py` stays byte-frozen |
| R1-5 | High | SUM-01, SUM-02, SUM-03, `N5`, `T-V170-SUM-03`, `E5` | accepted | The deadline is taken before attempt 1 and **every** request, attempt 1 included, receives `timeout_s = max(0, deadline − clock())`, with none issued on a non-positive remainder; the false premise "`remaining ≤ budget_s = LLM_TIMEOUT_S` by construction" is deleted along with the `min`-not-applied assertion, the 30 s floor stays the binding condition for the later requests, and a fake-client test with `budget_s = 10` against a client configured at 600 asserts the first recorded timeout is 10 |
| R1-6 | High | OBS-03, **NG-15** (new), `T-V170-OBS-04`, `E4`, Appendix A | accepted, adapted | `llm/failover.py` was read whole and `agent.py:830-960` with it: no attempt-level seam exists — `complete` and `_try_other` call a client and either return or raise, with no callback, observer or hook — so OBS-03 now requires **one logical row per `llm.complete` invocation** naming the client `describe()` reports afterwards, and `T-V170-OBS-04` and `E4` both state **six** rows derived from the call structure (two agent rounds plus two summary invocations, the truncation-retry and JSON-repair branches being mutually exclusive at `agent.py:1052-1062`), a failover adding none; building the seam is now REQ-V170-NG-15 |
| R1-7 | High | **RSN-07** (new), RSN-05, TREE-01, RPT-03.7 | accepted | An agent-shippable mechanism additionally needs one confirming **mixed-policy** pair on S05 — the exact proposed by-purpose treatment in a single invocation against a `model-default` control from the identical input — passing `resent_tokens ≤ 1.05 ×`, `new_tokens ≤ +64` and final-round `latency_ms ≤ 1.30 ×` the control's, thresholds derived from `metrics.resent_tokens`'s `newᵢ = max(0, promptᵢ − promptᵢ₋₁)` and calibrated against v1.4's measured +87 % resent blow-up; it consumes the existing third pair slot, so no budget moves, and `cache_hit_rate` was measured unusable — all 153 baseline rows carry `cached_tokens = null` — and recorded rather than followed |
| R1-8 | High | BEN-05, BEN-06, BEN-07 | accepted | BEN-05's sequence replaced verbatim — run C1, then C2 **unconditionally**, C3 only if neither passes quality, and among all candidates actually run that pass quality ship the lowest `C_conservative`, ties by `C_plain` then catalogue order — which is also the definition of "cheapest" that BEN-06's closing line and BEN-07's cost-gate-FAIL row now cite instead of leaving it undefined |
| R1-9 | High | POL-07, ACC-03, **`T-V170-ACC-03`** (new), ORD-01 T12, RPT-03.9 | accepted | ACC-03 gained a second, narrowly defined exception to the post-candidate freeze — one post-measurement **selection commit** touching only the two policy default literals and their documented echoes in `.env.example`, `README.md` and `AGENTS.md` — admitted only against proof: `T-V170-ACC-03` asserts offline that an unprefixed final-tree `load_config()` resolves to the policy and sorted purpose set of **exactly one** committed `cand-v170-*.json`'s `meta.reasoning`, pinning the selection without pinning a literal, plus a recorded candidate-metadata check; POL-07 was rewritten to match and the commit became its own task |
| R1-10 | Med | BEN-03, `T-V170-BEN-01`, `T-V170-BEN-04`, Appendix A | accepted | `meta.reasoning`, `reasoning_requested` and `reasoning_honored` are declared **optional additive** under `bench_schema` 2 — measured true at `054b103`: the frozen baseline carries none of them, `REQUIRED_LLM_ROW_KEYS` (`devtools/bench.py:190-196`) is a literal that does not gain them while the permitted `LLM_ROW_KEYS` widens from `storage.LLM_CALL_COLUMNS`, so `check` accepts both shapes untouched — an absent baseline block is legacy metadata and is never synthesised, and the tests now drive the **real committed** `baseline-v1.6.0.json` through `check`, `comparability` and `report --gate` instead of hand-built documents alone |

**Round 1: 10 findings, 9 accepted (3 adapted), 1 rejected.** One requirement
added — **REQ-V170-RSN-07** — and one NON-GOAL, **REQ-V170-NG-15**; one test id,
`T-V170-ACC-03`; one mutation entry, `v170-gate-ignores-3of3`. The `MUST` count
moves 67 → 68, §14.4's entries 8 → 9, and §16's tasks 13 → 15.

**Round 2 of at most 3** — same challenger, same seam, the round-1 spec
(`8a87c75`) passed by file. Nine findings, all nine accepted, one of them
adapted where the repository offered a stronger signal than the critique assumed
was available.

### Round 2 of at most 3 — against the round-1 spec (8a87c75); all nine accepted, one adapted

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R2-1 | Crit | POL-03, POL-05, OBS-01, BEN-05, `T-V170-POL-03`, AMEND-01 | accepted | `REASONING_MECHANISMS` is keyed by **tag alone** and holds **off** mechanisms only, so the lookup is asymmetric: `"default"` and `"on"` both return `ReasoningRequest(value, None, tag)` and send no field — `"on"` needs no disabling mechanism — and only `"off"` reads `mechanisms.get(tag)`, degrading to `("default", None, tag)` and reporting it when the entry is absent; the old symmetric `(tag, value)` lookup silently turned C1's and C3's declared `"on"` into `"default"` |
| R2-2 | Crit | VER-01, POL-07, ACC-03, REV-01.8, TREE-02, BEN-01, BEN-07, ORD-01 T8/T11/T12, `T-V170-ACC-03`, §13.1, `E9` | accepted | The `pyproject.toml` bump leaves T8 entirely and rides in T12's post-measurement selection commit, whose exhaustive allowed-file list becomes five — `config.py`, `pyproject.toml`, `.env.example`, `README.md`, `AGENTS.md`; T12 itself runs only when a quality-passing candidate exists, and the no-candidate, `EXIT_NOT_COMPARABLE` and instrument-STOP branches now route explicitly: skip T12, keep `1.6.0`, finalise the failure report, no tag. `T-V170-ACC-03` gained a literal-free version half asserting `1.7.0` exactly when a matching candidate document exists |
| R2-3 | Crit | PRE-03, PRE-04, BEN-01, `E9`, Appendix A | accepted | PRE-04 became **seven** checks whose first six are BEN-01's six instrument values, all established before its own inference preflight: the uniquely selected served id must **equal** `qwen/qwen3.8-27b` and `cfg.lmstudio_model` — substring matching is insufficient, and no match, two matches or a mismatch with `cfg.lmstudio_model` is an instrument STOP — and `cfg.obs_capture_content is False` with the metadata producer proved to emit `false`, so a non-comparable instrument can no longer consume stage A's budget |
| R2-4 | High | RSN-04, RSN-07, PRE-03, TREE-01, BEN-05, RPT-03.7, ORD-01 T1/T2/T3, Appendix A | accepted, **adapted** | Latency ratios are dropped as evidence. The direct cache signal is LM Studio's non-standard `stats.time_to_first_token`, captured per call by the scratch harness into a committed `-ttft.json` sidecar that is never a bench document: within each confirming run, `rate = prompt_tokens ÷ TTFT` on the cold first call, `predicted_cold_TTFT = final-round prompt_tokens ÷ rate`, and the cache is preserved iff measured final-round TTFT `≤ 0.35 ×` that prediction, on **each** run. PRE-03's new fourth `VERIFY` marker settles the field's availability live on the **OpenAI-compatible** route the bot's client uses — LM Studio documents the populated `stats` object only on its native `/api/v0/` route, and issue #601 reports `"stats": {}` on `/v1/` — and forbids the harness from switching routes to obtain it. Absent or empty there, Codex's conservative rule binds verbatim: RSN-07 proves only the absence of prompt-token inflation, agent-tag shippability cannot be established, and the mechanism ships for `summary` only. BEN-05 gained the consequence: C3 is not run when its resolved treatment equals C1's |
| R2-5 | High | OBS-01, OBS-02, `T-V170-OBS-03`, §14.4, `E4` | accepted | `reasoning_honored` became genuinely three-valued: `'default'` or a failed call → `NULL`; reasoning tokens unavailable **and** reasoning chars 0 → `NULL`, with this release specifying no per-row fallback, so the `NULL` is unconditional at row level; otherwise the truth table. `T-V170-OBS-03` now expects `('off', NULL, 0) → NULL` rather than `1` and adds the `('on', NULL, 0) → NULL` case, and the mutation entry was reworded to name exactly that removal |
| R2-6 | High | POL-03, POL-05, `T-V170-POL-05`, AMEND-01, REV-01.1 | accepted | Mechanism fields carry an **immutable recursive JSON** representation, `FrozenJSON` — tuples of key/value tuples, no `dict`, `list` or `set` anywhere in the table — and a single `json_fields` helper builds fresh dictionaries at every nesting level on every call; `T-V170-POL-05` asserts that mutating a produced payload, its nested mapping included, alters neither `REASONING_MECHANISMS` nor a later payload |
| R2-7 | High | §14.1, ORD-01 T5 | accepted | The contradiction is resolved in the critique's own words: `tests/test_failover.py` is amended **only** at the test-double signatures §14.1 lists (`:31`, `:276`), all other behaviour and assertions unchanged; it left the "explicitly NOT amended" list and T5's acceptance now reads "green with only the listed signature amendments" |
| R2-8 | Med | PRE-02, PRE-03 | accepted | The probe list is ordered and deduplicated: the three fixed addresses in their stated order, then the operator's address only when distinct; a named address MUST be a literal IPv4 validated before the command is built, and only such a literal may be interpolated — a hostname, scheme, port or path is a T0 blocker, never a probed string |
| R2-9 | Med | **ORD-02** (new), RSN-06, BEN-01, GATE-01, ACC-03, ORD-01 T1/T3 | accepted | One shared `T-STOP` procedure, invoked identically by T1's instrument STOP and T3's stage-A STOP: finalise the report and the Russian tg-post, append the usage rows, fill the ledger row completely, run `lint-docs` and the secret scans, record every omitted gate as `N/A` with its reason — live gate 5 and `replay --range` being explicitly not required on those branches — commit the permitted evidence artefacts only, prove `1.6.0` and an unchanged `git tag -l`, and terminate. ACC-03 is not reached on those branches and says so |

**Round 2: 9 findings, 9 accepted (1 adapted), 0 rejected.** One requirement
added — **REQ-V170-ORD-02** (`T-STOP`) — and no NON-GOAL; no new test id, no new
negative test, no new mutation entry and no new Gherkin scenario, the round's
work landing inside `T-V170-POL-03`, `-05`, `T-V170-OBS-03` and `T-V170-ACC-03`.
One new artefact pattern, `rsn17-<letter>-mixed-{control,mixed}-ttft.json`, and
one new `[[VERIFY]]` marker, taking §3's markers 3 → 4. The `MUST` count moves
68 → 69 and Appendix A's rows with it; PRE-04's checks move 6 → 7; §14.4's nine
entries, §16's fifteen tasks, the fifteen NON-GOALs, the twenty-five
`T-V170-*` ids, `N1`…`N8` and `E1`…`E12` are all unchanged.

**Round 3 of 3** — same challenger, same seam, the round-2 spec (`c05b878`)
passed by file. Nine findings, all nine accepted, one of them adapted because
the instrument offers no verified mechanism for the protocol the critique
assumed.

### Round 3 of 3 — against the round-2 spec (c05b878); all nine accepted, one adapted

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R3-1 | Crit | PRE-03, PRE-04, ORD-01 T1, RSN-07, RPT-03.7, Appendix A, `E9` | accepted | PRE-03 is **two phases with the whole of PRE-04 between them**: phase 1 is the address/model discovery, the single-line `.env` rewrite and the three documentary reads; phase 2 is the OpenAI-route TTFT-shape probe, the run's **second** inference, issued only after PRE-04's items 1–6 and its item-7 preflight — the first — have passed, and before any stage-A pair. T1's cell states that order as the requirement, PRE-04's closing names item 7 as the first inference of the run, and the shape probe is now literally the fourth `VERIFY` marker. The round-2 order could spend an inference, and warm a cache, on an instrument PRE-04 was about to reject |
| R3-2 | Crit | RSN-07, RSN-04, RSN-05, PRE-03, TREE-01, BEN-05, RPT-03.7, ORD-01 T1/T2/T3, ORD-02.6, **`E13`** (new), Appendix A | accepted, **adapted** | No cache-reset protocol is assumed — there is no verified remote mechanism for clearing LM Studio's prefix cache on the roaming box, so the critique's "reset, then prove cold-versus-warm" is replaced by a prefix that is cold **by construction**. Before **each** confirming control or mixed member the harness issues one scratch request whose system prompt **begins with a fresh random 32-hex nonce**; `rate = prompt_tokens ÷ TTFT` of it, and the identical request repeated once MUST return `TTFT ≤ 0.35 ×` the first — the warm proof that this server caches at all. Both calibration requests use the harness's own client, route and shape, are excluded from the member document and cost no pair; a failed warm proof makes **check 2 unavailable**, abandons the confirming pair before either member runs and binds the summary-only fallback exactly as an absent field does — the fallback now has **two** named triggers wherever it is cited. PRE-03's phase-2 probe carries the same nonce prefix so it can never warm the production prefix. The `-ttft.json` sidecar gained a `calibration` block recording the nonce's **length** and never the nonce, and the `rate` is documented as coming from it rather than from the run's first call |
| R3-3 | High | EC-05, POL-01, POL-07 | accepted | EC-05 gained the verbatim replacement: the `model-default` default is a **compatibility default with an expiry** binding every commit through T11, and REQ-V170-POL-07 explicitly supersedes it in the single post-measurement selection commit. POL-01 carries the same qualification for its displayed `Config` defaults and its two parser calls, which move together with `.env.example` in that one commit and nowhere else. The two requirements are ordered, not contradictory, and an executor no longer has a legitimate choice of which to follow |
| R3-4 | High | BEN-03, BEN-04, BEN-05, POL-01, POL-07, ACC-03, ORD-01 T12, `T-V170-ACC-03` | accepted | C2's second treatment value is the **explicit** `LLM_REASONING_ON_PURPOSES=""`, serialised `[]`, and BEN-04 requires **both** variables in every candidate prefix even when one is empty. Under `policy = off` the value is inert on the wire; what it fixes is the record and the ship — `meta.reasoning.on_purposes` is `[]` rather than inherited, and POL-07's shipped default, should C2 win, is the determined `frozenset()` documented in `.env.example` as `LLM_REASONING_ON_PURPOSES=`. `T-V170-ACC-03` matches the empty set like any other, `sorted(frozenset())` being `[]` |
| R3-5 | High | PRE-01 (new item 9), EC-04, ACC-03, POL-07, RPT-03.9, `E10`, Appendix A | accepted | T0 gains a **named-key absence check** under EC-04's first idiom: `grep -q '^LLM_REASONING_POLICY=' .env` and `grep -q '^LLM_REASONING_ON_PURPOSES=' .env` MUST both return non-zero. Presence is a **blocker**, reported by name and neither disclosed nor rewritten — idiom 4's `sed` is for `LMSTUDIO_BASE_URL` alone. This is what makes the final-tree equivalence test meaningful: `T-V170-ACC-03` resolves without the deployment `.env`, so its proof carries to the running bot only while these two keys are absent, `load_dotenv(..., override=False)` otherwise letting the file beat the changed source literal. It is not the rejected R1-1 objection to ordinary `.env` loading; it is one precondition on the two keys this release newly activates |
| R3-6 | High | ORD-02.4, RPT-02 | accepted | `T-STOP` can now actually lint this release's report: it changes **only** `lint-docs.report_path` in the **working tree**, runs `checks.py lint-docs`, restores the file and proves `git diff -- config/quality_gates.yaml` empty before the closing commit. T8's permanent repoint never happens on a branch that exits at T1 or T3, and adding a `--report-path` option would be a source change on the one branch whose premise is that no source changed |
| R3-7 | High | ORD-02.5, GATE-01, RPT-03.1 | accepted | ORD-02 item 5 replaced verbatim: after all `T-STOP` artefacts are finalised and before the closing commit, gates 1–4 and 6 are **rerun against that final working tree** with fresh exit codes recorded; only gate 5's post-T1 repetition, `replay --range` and `mutation-v170` are `N/A`, with their reasons. Reusing T0's codes described a tree that no longer exists — prompts, the report, usage rows and, on a T3 STOP, every stage-A artefact land after it. The report's gates table carries both sets |
| R3-8 | High | EC-01, PRE-03 | accepted | EC-01's allowlist extended verbatim: the LM Studio discovery/preflight/TTFT traffic, **PRE-03's read-only HTTPS requests to the named LM Studio and OpenRouter documentation sources**, stage A and stage C inference traffic, S17's `wttr.in` fetch, and tool-owned caches. The round-2 list was exhaustive and omitted the documentation reads PRE-03 mandates, so the spec forbade its own instruction |
| R3-9 | High | REV-01.8, ACC-03, `T-V170-ACC-03`, ORD-01 T12/T14, RPT-03.9, Appendix A, `E9` | accepted | REV-01 item 8 split. At T10 the reviewer checks the **selection mechanism and its five-file allowlist prospectively**, and is told no T12 commit exists yet. After T12, `T-V170-ACC-03`'s **third half** locates the selection commit by its prompt citation, records `git diff --name-only <T11-tip>..<T12-tip>`, rejects any path outside the five files and checks the permitted hunks structurally — no policy or version literal of its own, so the commit still never has to edit the test — skipping with a recorded reason while no such commit exists. It is a check, not a review, so REV-01's "never after the measurement" stands; **no second general review** is required |

**Round 3: 9 findings, 9 accepted (1 adapted), 0 rejected.** Every finding had
an existing home, so **no requirement and no NON-GOAL was added**: the `MUST`
count stays **69** and Appendix A's rows with it, and there is no new test id, no
new negative test and no new mutation entry. One new Gherkin scenario, **`E13`**,
takes Appendix B from twelve scenarios to **thirteen**. REQ-V170-PRE-01 gains a
ninth precondition, REQ-V170-PRE-03 gains its two-phase structure, and
REQ-V170-ORD-02's `T-STOP` items 4 and 5 are rewritten; the `-ttft.json` sidecar
gains its `calibration` block without a new artefact name. §3's four `VERIFY`
markers, PRE-04's seven checks, §14.4's nine mutation entries, §16's fifteen
tasks, the fifteen NON-GOALs, the twenty-five `T-V170-*` ids and `N1`…`N8` are
all unchanged.
