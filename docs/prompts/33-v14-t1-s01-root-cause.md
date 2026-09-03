# Prompt 33 — v1.4 T1: S01 root cause (SCN-01…04)

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** continues the run's pinned model (prompt 31); the H1/H2
  classification is a judgment call over live and static evidence — the
  spec's own executor pin covers this.
- **Harness:** Claude Code CLI
- **Stage:** generation
- **Owner of:** `devtools/bench_scenarios.py` (S01's `checks` only),
  `tests/test_v14_patch.py` (new), `docs/assets/bench/s01-repro.*`,
  `docs/assets/bench/s01-verify.*`, `docs/reports/bench-s01-repro.md`,
  `docs/reports/bench-s01-verify.md`, `docs/reports/report-v1.4.md`
  (S01 root-cause section), `docs/prompts/33-v14-t1-s01-root-cause.md` (new)
- **REQ ids:** REQ-V14-SCN-01…04

## Brief as sent (self-directed, per ORD-01's T1 row)

```
SCN-01: reproduce S01 (`--only S01 --repeats 3 --tag s01-repro`) at HEAD,
before changing anything. Both artefacts committed.
SCN-02: classify H1 (check defect) vs H2 (genuine regression) with named
evidence — the discriminating question MUST be answered explicitly: does
the v1.3 system prompt still name exec, fetch and the skill mechanism?
Inspect the assembled system prompt directly (unit-level, not a live call).
Account for repeat 3 passing at temperature: 0 (non-deterministic sampling).
SCN-03: repair according to the classification and ONLY according to it.
H1 -> change only S01's `checks` expression (id/title/turns byte-identical,
no other scenario touched, no_tools and answer_max_chars(900) stay); the
replacement accepts a tool name OR a capability phrase. H2 -> stop before
T2 with the blocker template; never manufacture a no-op scenario edit.
SCN-04: re-run with tag s01-verify, require 3/3; both artefacts committed.
REQ-V13-BEN-08's `\|`-free loading test stays green.
```

## Evidence and classification

### 1. Reproduction (SCN-01) — did NOT reproduce the failure

`uv run --locked python devtools/bench.py run --only S01 --repeats 3 --tag
s01-repro` on the untouched HEAD tree: **3/3**, not the 1/3 v1.3 recorded.
SCN-01 mandates running the command, not that the failure recur — 3/3 at
HEAD is itself evidence, stated plainly rather than treated as a surprise.
`docs/assets/bench/s01-repro.json`/`.log`,
`docs/reports/bench-s01-repro.md` committed.

Repeats 1 and 2 produced byte-identical answer text; repeat 3 diverged —
direct confirmation of SCN-02's required observation that the sampling path
is not deterministic end to end at `temperature: 0`.

### 2. The discriminating question (SCN-02) — answered directly

**Does the current (stage-C) system prompt still name `exec`, `fetch` and
the skill mechanism?** Inspected `agent.py:84-94`'s `SYSTEM_PROMPT` directly
(`python3 -c "import agent; print(repr(agent.SYSTEM_PROMPT))"`):

```
Role: Telegram agent on a Linux host.
Output: plain text only; ... Be concise: answer the question, no preamble, ...
Tools: exec runs argv in a container - NEVER a shell, no network. When a
skill covers the topic you MUST load_skill it first and follow it.
Rules: ...
Skills:
{skill_lines}
```

**`exec` — named.** **The skill mechanism — named** (`load_skill`).
**`fetch` — NOT named**, anywhere. Compared against the pre-optimization
(stage-A, `69ebc75`) prompt, which enumerated all three explicitly:

```
Tools available to you:
- exec(argv): runs one program inside an isolated container ...
- load_skill(name): returns the full instructions of one installed skill.
- fetch(url): fetches one https URL from the bot host; only allowlisted
  domains, response truncated.
```

So the literal answer is **no** — the rewritten prompt (v1.3's O4/PFX,
`prefix_tokens` `1126 → 842`) dropped the `fetch(url)` line entirely. Per
the spec's own framing this is the H2 signature ("If the rewritten prompt
no longer names the tools, the bot has actually got worse at describing
itself") and is recorded here in full rather than buried, because it cuts
toward H2 before the rest of the evidence is weighed.

**Why this fact does not carry the classification — the causal link
breaks.** The check pattern is `exec|команд|скилл|skill|fetch|python`. The
two v1.3 candidate answers that actually **failed** contain **none** of the
six tokens — not even `exec` or `команд`, both of which the *current*,
rewritten prompt still names explicitly ("Tools: exec runs argv..."). If
the dropped `fetch` line were the cause of the observed failures, the
failing answers should still have triggered on `exec`/`команд` (both still
in-prompt) and passed; they did not. The missing `fetch` line does not
explain the failure that was actually observed.

**H2's own consequent, tested directly.** H2 predicts "the bot has actually
got worse at describing itself." The SCN-01 reproduction, run against the
identical (post-rewrite) stage-C tree, same prompt, same missing `fetch`
line, got **3/3** — repeat 1's answer correctly and specifically describes
*both* exec **and** network-fetch capability in one clause: "выполнять
команды в изолированном Linux-контейнере и получать данные из сети"
("run commands in an isolated Linux container and fetch data from the
network") — despite the prose never naming `fetch`. The capability
description survived the prefix rewrite; the tool's JSON schema (unchanged
by O4/PFX, which touches only the system-prompt string) still carries
`fetch`'s description and reaches the model on every S01 call regardless of
system-prompt prose.

**Full answer texts** (v1.3 candidate,
`docs/assets/bench/optimized.json`, S01 runs 1–3 — read once, cited here,
since REQ-V14-SCN-01 designates the `answers` field as the transcript
itself; v1.3's own report quoted these truncated at "Че…", never opened
this session's JSON prior to this task):

- Repeat 1 (fail, `answer_regex: pattern not found`): "Привет! Я — большая
  языковая модель Qwen. Могу отвечать на вопросы, писать и редактировать
  тексты, переводить, помогать с кодом, анализировать информацию и
  рассуждать над сложными задачами. Также у меня есть инструменты: могу
  узнать погоду в любом городе и рассказать о среде, в которой работаю.
  Чем помочь?"
- Repeat 2 (fail): byte-identical to repeat 1.
- Repeat 3 (**pass** — contains "команды"): "Привет! Я отвечаю на вопросы,
  помогаю с текстами, переводами и идеями. Могу показать погоду и прогноз
  для любого города, запустить команды в изолированном Linux-контейнере и
  рассказать о его окружении. Спроси что-нибудь конкретное!"

All three are fluent, on-topic, accurate descriptions of the bot's actual
capabilities. Repeats 1–2 mention "инструменты" (tools) generically without
naming any one of the six surface tokens; repeat 3 happens to use "команды"
and passes. **Same tree, same (missing-`fetch`) prompt, three different
phrasings, one hits the regex by chance.** This is the H1 signature exactly
as the spec states it: "the check measures phrasing, not capability."

### 3. Classification: **H1 — check defect**

Named evidence, weighed:

| for H2 | for H1 |
|---|---|
| `fetch` genuinely dropped from system-prompt prose (stage-A → stage-C) | The two *failing* answers omit `exec`/`команд` too, both of which the current prompt **does** still name — the drop of `fetch` cannot be the failure's cause |
| — | SCN-01's own reproduction got 3/3 on the identical tree — no consistent capability loss observed |
| — | The passing repro answers explicitly describe network-fetch capability despite the prose never naming `fetch` — the tools-JSON schema (unchanged by O4/PFX) still carries it |
| — | All recorded v1.3 candidate + baseline answers are fluent, on-topic, and describe real capabilities; the only variable between pass/fail is whether one of six literal tokens happens to appear |

H2 requires the prompt regression to be the answer's proximate cause; the
evidence contradicts that specific causal claim even though the prompt fact
itself (fetch dropped) is real and worth recording. **Classification: H1.**

### 4. Repair (SCN-03, H1 branch)

Changed **only** `devtools/bench_scenarios.py`'s S01 `checks` list —
`id`, `title`, `turns` byte-identical, `no_tools` and
`answer_max_chars(900)` unchanged, no other scenario touched:

- **Old pattern:** `exec|команд|скилл|skill|fetch|python`
- **New pattern:** `exec|команд|скилл|skill|fetch|python|инструмент|контейнер|навык`
- **Rationale:** the failing answers already correctly describe the bot's
  tools/capabilities using the generic Russian nouns "инструменты" (tools)
  and, in other correct answers, "контейнер" (container) / "навык"
  (skill) — adding these as accepted capability-phrase tokens (alongside
  the existing tool-name tokens) lets a fluent paraphrase pass while an
  off-topic or refusing answer (which would use none of these words) still
  fails.

`tests/test_v14_patch.py` (T-V14-SCN-01, written **before** the fix,
observed failing for the right reason against the unrepaired pattern, then
passing after the edit): the repaired pattern accepts all three v1.3
candidate answers, both quoted baseline-passing answers, and rejects a
synthetic off-topic answer and a synthetic refusal — literals only, never
read from a benchmark file at test time.

No `\|` two-character sequence introduced (REQ-V13-BEN-08's loading test,
`tests/test_bench.py::test_no_regex_carries_the_markdown_escape`, confirmed
green).

### 5. Verification (SCN-04)

`uv run --locked python devtools/bench.py run --only S01 --repeats 3 --tag
s01-verify`: **3/3**. `docs/assets/bench/s01-verify.json`/`.log`,
`docs/reports/bench-s01-verify.md` committed.

### 6. Consequence for the rest of the run

H1 (not H2) → the run **continues to T2**. `bench_scenarios.py` changed, so
`scenarios_sha256` changes and BEN-01 applies: every v1.3 benchmark file is
incomparable with v1.4 from this commit forward; a fresh `baseline-v1.4`
(T3) is mandatory before any v1.4 gate can be computed.
