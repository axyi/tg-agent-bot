# Prompt 36 — v1.4 T4: RSN spike (REQ-V14-RSN-01…06)

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** continues the run's pinned model (prompt 31); the spike
  is a mechanical trial protocol plus a documentation read, no judgment
  beyond the spec's own decision rules (RSN-02/03/06).
- **Harness:** Claude Code CLI
- **Stage:** generation
- **Owner of:** 14× `docs/assets/bench/rsn-*.json`/`.log`, 14×
  `docs/reports/bench-rsn-*.md`, `docs/reports/report-v1.4.md` (RSN spike
  section), `docs/prompts/36-v14-t4-rsn-spike.md` (new)
- **REQ ids:** REQ-V14-RSN-01, RSN-02, RSN-03, RSN-04, RSN-05, RSN-06

## Brief as sent (self-directed, per ORD-01's T4 row)

```
RSN-01: pair contract — for each candidate a-d, a temporary uncommitted
patch to llm/base.py / llm/lmstudio.py / agent.py, applied only while
probing that candidate; a driver script calls devtools/bench.py's
main(argv) twice in one Python process (module-level bool toggled
between calls) — first model-default, then off, both --only S05
--repeats 1 --tag rsn-<letter>-<n>[-default|-off]. No subprocess, no new
CLI flag, no new env var. Restore the tree (git checkout) and confirm
`git diff` empty before the next candidate.
RSN-02: try a, b, c, d, e in this fixed order; stop only at a candidate
that is both honored (RSN-03) and shippable (POL-05) — a shippable
candidate was never found, so every candidate was tried.
RSN-05: 2 pairs for a failing candidate, 3 for a passing one, 0 for
`unsupported`, at most 1 informational run each for b-low and e — both
optional and outside every gate/budget.
RSN-06: if nothing both honored and shippable, STOP — no optimization
commit; still deliver the mechanism table, name every honored-but-
unshippable and unsupported/no-control candidate, verdict FAIL.
```

## Trial log

### Candidate a — `chat_template_kwargs: {"enable_thinking": false}`

Patch: `llm/lmstudio.py`'s `LMStudioClient.complete()`, after
`build_payload()` returns, `if llm_base.RSN_SPIKE_OFF: payload["chat_template_kwargs"]
= {"enable_thinking": False}`; `llm/base.py` gained a scratch module-level
`RSN_SPIKE_OFF = False`.

Driver: `LLM_FAILOVER=off LLM_SUMMARY_MODEL= LLM_TIMEOUT_S=240
LLM_MAX_TOKENS=2048 uv run --locked python <driver> a 1
docs/assets/bench`, then `a 2`.

| pair | default Σrt/max rc | off Σrt/max rc | S05 (both members) |
|---|---|---|---|
| a-1 | 345 / 1102 | 345 / 1103 | 1/1, 1/1 |
| a-2 | 299 / 938 | 463 / 1585 | 1/1, 1/1 |

Both pairs: `off` is unchanged or *higher* than `default`. The
undocumented top-level key has no observable effect on this LM Studio
build (PRE-03 found no statement either way on unknown top-level keys
reaching the chat template — this is the live answer). **Not honored,
0/2.** Budget: 2 pairs for a failing candidate (RSN-05) — met, stop.

Tree restored: `git checkout -- llm/base.py llm/lmstudio.py`; `git status
--short` showed only the new `rsn-a-*` artefacts.

### Candidate b — vendor-documented disable value

No live patch — PRE-03's documentation read (T0, confirmed again here)
settles it before any probe: LM Studio's changelog (`docs/developer/api-changelog`)
adds `reasoning.effort ∈ {low, medium, high}` at **0.3.29**, for
`openai/gpt-oss-20b` only; nothing through the running `0.4.23` documents
a disable value (`none`/`enabled:false`) for *any* model, and nothing
documents `reasoning.effort` for a Qwen3-class model at all. Per RSN-02:
"If PRE-03's live reading finds only `low|medium|high` and no disable
value, candidate b is recorded `unsupported` — it consumes no probe
pair". **Unsupported. 0 pairs (RSN-05).**

`rsn-b-low-info` (the optional `effort:"low"` informational pair):
**not run.** It cannot become a winning mechanism under any outcome (an
`effort:"low"` zero-token response would still be an "accident", never a
documented off-switch, per RSN-02's own text) and every RSN-06 STOP
deliverable is satisfied without it. Skipped by choice, not oversight —
recorded here so the decision is auditable.

### Candidate c — assistant prefill of an empty think block

Patch: `llm/lmstudio.py`, before calling `build_payload()`: `if
llm_base.RSN_SPIKE_OFF: messages = [*messages, {"role": "assistant",
"content": "<think>\n\n</think>\n\n"}]`.

Driver: pairs `c 1`, `c 2`, `c 3` (candidate stayed eligible — RSN-01:
"runs pairs `rsn-<letter>-1`, `-2` and — while still eligible — `-3`").

| pair | default Σrt/max rc | off Σrt/max rc | S05 (both members) |
|---|---|---|---|
| c-1 | 345 / 1102 | 0 / 0 | 1/1, 1/1 |
| c-2 | 349 / 1132 | 0 / 0 | 1/1, 1/1 |
| c-3 | 345 / 1102 | 0 / 0 | 1/1, 1/1 |

All three: `off` reads exactly `0`/`0`, `default` stays in the usual
~300–350-token band, S05's `tool_used("exec")` and
`answer_regex(r"\b332\b")` checks pass on all six runs. RSN-03 items 1–3
all directly satisfied (no `reasoning_tokens: absent` on any member, so
item 3's 20%-fallback path was never needed) — **honored, 3/3.**

POL-05 item 4 (already spec-predetermined, verified against the actual
patch): the prefill is appended as the message array's **last** element.
REQ-V13-CCH-02(a) requires round *n*'s messages to be a prefix-extension
of round *n-1*'s; a prefill that must always be last cannot survive as
the array grows — every shipping policy (`always` or `by-purpose`) that
emits it would move or duplicate it round over round. **Honored but
unshippable.** Consumed its full 3-pair budget (RSN-05); per RSN-02,
probing continued to `d` rather than stopping here.

Tree restored: `git checkout -- llm/base.py llm/lmstudio.py`; confirmed
clean.

### Candidate d — Qwen3 `/no_think` on the last user message

First established where v1.3 put the equivalent line: `report-v1.3.md:208-225`
— `agent.py`'s `_append_now()` appends a `(now: …)` line to the most
recent user-role message each round (the slot REQ-V13-CCH-01 already
mutates). Patch mirrors that: `agent.py` gained `from llm import base as
llm_base`; inside `_append_now()`, `if llm_base.RSN_SPIKE_OFF: line =
f"{line}\n/no_think"` before the line is spliced in — same slot v1.3
used, confirming this attempt does not differ from the prior one in
placement.

Driver: pairs `d 1`, `d 2`.

| pair | default Σrt/max rc | off Σrt/max rc | S05 (both members) |
|---|---|---|---|
| d-1 | 345 / 1100 | 273 / 911 | 1/1, 1/1 |
| d-2 | 338 / 1083 | 634 / 2149 | 1/1, 1/1 |

Pair 1: a partial reduction (21% down) but nonzero — fails RSN-03 item 1's
exact-zero requirement outright; `reasoning_tokens` was reported (not
omitted) on both members, so item 3's 20%-fallback path does not apply
here either way. Pair 2: an *increase* (338→634) — no consistent
suppressive effect. **Not honored, 0/2.** Budget: 2 pairs for a failing
candidate — met, stop.

Tree restored: `git checkout -- llm/base.py llm/lmstudio.py agent.py`;
confirmed clean.

### Candidate e — model-level default (LM Studio GUI / `lms` CLI)

No live patch is possible — e is "not in the request at all" (RSN-02's
own table). Per RSN-02: "The control… is version-dependent: look it up
for the version recorded under PRE-02 [`0.4.23`], name it in the README
note and the report, and do not guess."

Documentation read, 2026-09-03:

- `https://lmstudio.ai/docs/cli/load` — `lms load`'s complete flag list:
  `[path]`, `--ttl`, `--gpu`, `--context-length`, `--identifier`,
  `--estimate-only`, `--host`. Nothing reasoning/thinking-related.
- `https://lmstudio.ai/docs/typescript/llm-prediction/parameters` — the
  documented Inference Parameters (`temperature`, `maxTokens`, `topP`,
  structured output) and Load Parameters (context length, GPU offload
  ratio) categories. No reasoning/thinking/chat-template field in either.
- A GitHub issue against LM Studio (surfaced by `WebSearch`, dated against
  v0.4.16) explicitly confirms there is no GUI slider or toggle for
  reasoning effort, even for the one model class (`gpt-oss`) that has a
  documented **per-request** `reasoning.effort` field. Nothing in the
  `0.4.23` changelog (already read under PRE-03) adds one later.

**Finding: no reasoning/thinking-related GUI setting or `lms load`
option is documented for LM Studio `0.4.23`.** This is the named answer
RSN-02 asks for — "look it up… name it… do not guess" is satisfied by
reporting the documented absence of a control, not by inventing one.
`rsn-e-info` (the optional informational run) **cannot be run**: there is
no control in this version to toggle, so no probe would measure anything.
e is categorically excluded from ever authorizing T5/T7 regardless
(RSN-02's own text — environmental, not per-request, not reproducible
from the repository).

**Why no `README.md` change accompanies this finding:** RSN-02's "name
it in the README note" sits inside the policy documentation that T5/T8
write (`README.md` is in T5's/T8's declared file scope per ORD-01, not
T4's). Since this run routes to RSN-06 STOP, T5 is not-executed and no
README policy section is ever created — there is nothing for a README
note to be appended to. The finding is recorded here and in
`report-v1.4.md` instead, which is where every other STOP-branch
finding lands.

## RSN-05 budget accounting

| candidate | pairs run | budget allowed | within budget |
|---|---|---|---|
| a | 2 | 2 (failing) | yes |
| b | 0 | 0 (unsupported) | yes |
| c | 3 | 3 (passing) | yes |
| d | 2 | 2 (failing) | yes |
| e | 0 (no control found) | ≤1 optional `rsn-e-info` | yes (0 ≤ 1) |
| — | `rsn-b-low-info` | ≤1 optional, not run | yes (0 ≤ 1) |

Every candidate a–e was tried (per RSN-02: "skipping an untried one is a
defect"); no candidate was skipped.

## RSN-06 verdict

No candidate is both honored (RSN-03) and shippable (POL-05):

- **a** — not honored.
- **b** — unsupported (no disable value documented for this LM Studio
  version, ever, for any model at Qwen3's class).
- **c** — honored, but unshippable (POL-05 item 4 — breaks CCH-02(a)).
- **d** — not honored.
- **e** — no control found for this LM Studio version; categorically
  disqualified from authorizing anything regardless.

**STOP. There is no optimization commit.** Section 6 (POL-01…07), the
two new `## Reasoning` columns of section 7, and section 10's candidate
benchmark runs (T7) are not-executed. T5 and T7 are not executed; REL-02
(with its tests and mutation) is released; T8 reduces to the
mechanism-independent documentation of RPT-06's final paragraph
(REL-01's `.env.example` `LLM_TIMEOUT_S=240` pair and the README lines
that do not describe a policy); BEN-09 is released (GATE-02). Final
verdict, to be stated in full at T10: **FAIL, cause: no honored
reasoning mechanism.**

## Artefacts

14 pair-member runs, each `.json` + `.log` (`git add -f`, RPT-08) and a
rendered `docs/reports/bench-rsn-<tag>.md`: `rsn-a-{1,2}-{default,off}`,
`rsn-c-{1,2,3}-{default,off}`, `rsn-d-{1,2}-{default,off}`. Secret-pattern
scan (credential key names in value positions, `authorization:` headers,
bot-token shapes) clean on all 28 files.

## Gates

Gates 1–5 (below). Gate 6 not run: this commit touches no production
code, test, configuration behaviour or mutation-relevant file (every
scratch patch to `llm/base.py`/`llm/lmstudio.py`/`agent.py` was reverted
before commit), and this is not the final tree (GATE-01).
