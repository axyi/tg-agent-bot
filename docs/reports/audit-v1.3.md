# Token-economy audit — baseline (v1.3, stage B)

Written per REQ-V13-AUD-04 from markdown reports only. Sources:

- **`[baseline]`** — `docs/reports/bench-baseline.md` (generated, REQ-V13-AUD-03)
- **`[smoke]`** — `docs/reports/bench-openrouter-smoke.md` (generated, REQ-V13-AUD-03)

No benchmark JSON or log was opened (REQ-V13-EC-12). Every figure below carries
one of three citation classes:

| class | meaning |
|---|---|
| `[baseline · ## Section]` / `[smoke · ## Section]` | a named cell of a named table in a source report |
| `[spec REQ-…]` | a target or constant from `docs/spec/spec-v1.3.md`; used **only** in the hypotheses section, never to answer an audit question |
| `[derived]` | arithmetic over cited cells; the derivation is shown inline |

**Cost caveat (REQ-V13-PRC-03).** The baseline pricing basis is
`reference:qwen/qwen3.8-27b` [baseline · ## Meta] — an OpenRouter list price for
the same model id, applied to inference that actually ran locally on LM Studio
and was therefore free. **Every USD figure derived from the baseline is an
ESTIMATE** and is marked `(ESTIMATE)`. The only figure in this document computed
from a real list price against provider-reported usage is the smoke's
`cost_usd` (§5).

---

## 1. Run facts

| fact | value | source |
|---|---|---|
| runs | 36/36 successful, success rate 1 | [baseline · ## Totals], [baseline · ## Per scenario] |
| failures | `none` | [baseline · ## Failures] |
| LLM calls | 88, of which 1 failed | [baseline · ## Totals] |
| provider / model | lmstudio, `qwen/qwen3.8-27b` | [baseline · ## Meta] |
| context length | 42496 | [baseline · ## Meta] |
| prompt / completion tokens | 126 109 / 16 923 | [baseline · ## Totals] |
| estimated cost | $0.09675 (ESTIMATE) | [baseline · ## Totals] |
| pricing basis | `reference:qwen/qwen3.8-27b`, $0.425/$2.55 per Mtok in/out | [baseline · ## Meta] |

The single failed call (1 of 88 = **1.1 %**) is a transport timeout. It is a
reliability datum, **not** a token-economy finding: it produced no usage row that
distorts any figure below, and every scenario still passed 3/3
[baseline · ## Per scenario].

Arithmetic check of the pricing pipeline [derived]:
`126 109 × 0.425/10⁶ + 16 923 × 2.55/10⁶ = 0.05360 + 0.04315 = $0.09675`, which
reproduces the reported `cost_usd` cell exactly. The cost column is internally
consistent.

Consistency check of the scenario medians [derived]: the twelve
`prompt+completion` medians sum to **47 643**; `(126 109 + 16 923)/3 = 47 677`.
Medians ≈ means, so the three repeats of each scenario are low-variance and the
per-scenario table can be read as representative rather than as an outlier
sample.

---

## 2. Audit answers

### 2.1 Most expensive tool by output tokens

**`exec` — 11 523 tokens over 36 calls** [baseline · ## Audit].

Context [derived from baseline · ## Totals]:

- `exec` is **87.9 %** of all tool output (`11 523 / 13 116`).
- The other tools together produce 1 593 tokens over 9 calls
  (`13 116 − 11 523`; `45 − 36`).
- Mean `exec` output: **320 tokens/call** (`11 523 / 36`).
- All tool output is **10.4 %** of prompt tokens (`13 116 / 126 109`).

### 2.2 Most expensive turn/round

**`S05-1 turn 3 round 2` — 5 402 prompt tokens** [baseline · ## Audit].

That single call is **4.3 %** of the whole run's prompt tokens
(`5 402 / 126 109`) [derived]. It matches S05's median `new_tokens` of 5 402
[baseline · ## Per scenario], i.e. the round is expensive because of *new*
content — the 4096-byte `exec` capture of the 5000-line output — not because of
re-sent history. Its scenario carries the largest `tool_output_tokens_est`
median of the run, **1 767** [baseline · ## Per scenario].

### 2.3 Fastest-growing context category

**`tool` — +1301.4 chars/run** [baseline · ## Audit].

`context_growth` is the mean over runs of the `prompt_chars_by_role` delta
between a run's first and last `agent` call. The generated report renders only
the winning category, so **no cross-category comparison is available from the
permitted sources** — the audit can state that the `tool` role grows fastest and
by how much, but cannot rank `system`/`tools`/`user`/`assistant` against it. The
figure is deliberately left in characters: converting it to tokens would require
a chars-per-token ratio that neither report publishes.

### 2.4 Re-sent tokens

| quantity | value | source |
|---|---|---|
| re-sent share | **0.495056** (49.51 %) | [baseline · ## Totals] |
| re-sent tokens, absolute | **62 431** | [baseline · ## Totals] |
| new tokens, absolute | 63 678 | [baseline · ## Totals] |

New share = `63 678 / 126 109` = **0.504944** [derived].

> **Per 100 000 input tokens sent to the model, ~50 500 are new and ~49 500 are
> a re-send of tokens the model was already given on the previous call.**

Cost of the re-send at the reference price [derived]:
`62 431 × 0.425/10⁶ = $0.02653 (ESTIMATE)` — **27.4 %** of the run's estimated
cost.

**What the re-send actually consists of.** The metric is defined as
`resent_i = min(prompt_i, prompt_{i−1})` (REQ-V13-OBS-08), so every call after
the first in a conversation re-sends at least the invariant prefix. Counting
conversation groups: 36 runs, plus one extra group for each of the 3 S12 repeats
(the `/new` turn, Appendix C) = **39 groups**; 85 agent calls
[baseline · ## Totals by purpose] leaves **46 non-first agent calls**, each
re-sending ≥ 1 126 prefix tokens [baseline · ## Meta] → ≥ 51 796 tokens; the 3
summary calls average 475 prompt tokens each (`1 424 / 3`
[baseline · ## Totals by purpose]) → ≥ 1 425. Lower bound
**≥ 53 221 of 62 431 = ≥ 83 %** of all re-sent tokens are the fixed prefix
[derived]. (If the failed call is skipped for having no usage, the bound is
83.4 %; either way the conclusion is the same.)

This is the single most important finding of the audit: **the re-send problem is
mostly a prefix problem, not a history problem.**

### 2.5 Prefix share

**0.785733 (78.57 %)** [baseline · ## Totals], from `prefix_tokens = 1126`
[baseline · ## Meta] × 88 calls / 126 109 = 99 088 / 126 109 [derived].

Two refinements, both derived:

- **Absolute:** 99 088 prompt tokens of 126 109 are the invariant prefix; at the
  reference input price that is `$0.04211 (ESTIMATE)` — **43.5 %** of the run's
  estimated cost, spent on text that never changes.
- **Agent-only correction:** the metric's definition multiplies by *all* 88
  calls, but the 3 summary calls carry ~475 prompt tokens each and therefore do
  not carry the agent prefix. Over agent calls only the share is
  `1 126 × 85 / 124 685 = 76.8 %` [baseline · ## Totals by purpose]. The
  published 78.57 % is a slight overstatement; the honest range is **76.8–78.6 %**.
- `prefix_tokens` is measured with a `ping` calibration call (REQ-V13-BEN-06), so
  it includes a few tokens of chat-template markup and the `ping` message itself.

### 2.6 Reasoning

Verbatim from [baseline · ## Reasoning]:

```
- reasoning observed: yes, max reasoning_tokens: 825, max reasoning_chars: 3265, Σ reasoning_tokens: 12144, reasoning share: 0.7176
- tool-exposed calls: calls: 84, reasoning observed: yes, max reasoning_tokens: 825, max reasoning_chars: 3265, Σ reasoning_tokens: 11081, reasoning share: 0.7131
- tools-withheld calls: calls: 3, reasoning observed: yes, max reasoning_tokens: 395, max reasoning_chars: 1721, Σ reasoning_tokens: 1063, reasoning share: 0.7681
```

| figure | overall | tool-exposed | tools-withheld |
|---|---|---|---|
| calls (error-free) | 87 | 84 | 3 |
| reasoning observed | yes | yes | yes |
| max `reasoning_tokens` | 825 | 825 | 395 |
| max `reasoning_chars` | 3265 | 3265 | 1721 |
| Σ `reasoning_tokens` | 12 144 | 11 081 | 1 063 |
| reasoning share | 0.7176 | 0.7131 | 0.7681 |

**Reasoning share of all completion tokens: 71.8 %** (`12 144 / 16 923`, matching
the reported 0.7176) [derived].

Group identification [derived, consistent with — not proven by — the cells]:
`11 081 / 0.7131 = 15 539`, which equals the `agent` completion total, and
`1 063 / 0.7681 = 1 384`, which equals the `summary` completion total
[baseline · ## Totals by purpose]. Also `84 + 3 = 87 = 88 − 1 failed`
[baseline · ## Totals]. The tool-exposed group is therefore the 84 error-free
agent calls, and the tools-withheld group is exactly the 3 summary calls.

**Consequence for stage C:** the agent loop's own tools-withheld final call
(`expose_tools` false, `request_tools is None`) was **never exercised** in the
baseline — every error-free agent call carried tools. Under an `auto` policy the
addressable reasoning volume is the full **11 081 tokens** of the tool-exposed
group; the 1 063 tokens left alone belong to the summary path.

### 2.7 Per-scenario token sinks

Ranked by median `prompt + completion` per run [baseline · ## Per scenario;
ranking derived]. These are medians of 3 repeats, not sums.

| rank | scenario | prompt | completion | total | resent | resent % of prompt | tool out | dominant sink |
|---|---|---|---|---|---|---|---|---|
| 1 | S09 multi-turn | 7 124 | 814 | **7 938** | 5 490 | 77.1 % | 120 | re-sent history/prefix over 5 calls |
| 2 | S05 big-output | 6 581 | 527 | **7 108** | 1 179 | 17.9 % | **1 767** | one large `exec` capture |
| 3 | S12 summary | 5 703 | 1 357 | **7 060** | 4 251 | 74.5 % | 120 | re-send + the summary call's 1 357 completion |
| 4 | S07 skill | 4 151 | 459 | **4 610** | 2 458 | 59.2 % | 397 | 4 tool calls over 3 rounds |
| 5 | S08 fetch | 4 201 | 254 | **4 455** | 2 629 | 62.6 % | 368 | 2 tool calls over 3 rounds |
| 6 | S06 noisy-log | 3 298 | 545 | **3 843** | 1 167 | 35.4 % | **1 361** | 200 duplicate log lines |
| 7 | S03 file-roundtrip | 2 492 | 765 | **3 257** | 1 161 | 46.6 % | 61 | 644 reasoning tokens |
| 8 | S04 error-explain | 2 474 | 329 | **2 803** | 1 161 | 46.9 % | 104 | prefix ×2 calls |
| 9 | S02 arith | 2 406 | 96 | **2 502** | 1 148 | 47.7 % | 52 | prefix ×2 calls |
| 10 | S10 knowledge | 1 142 | 323 | **1 465** | 0 | 0 % | 0 | prefix only (1 call) |
| 11 | S01 greet | 1 138 | 214 | **1 352** | 0 | 0 % | 0 | prefix only (1 call) |
| 12 | S11 json | 1 153 | 97 | **1 250** | 0 | 0 % | 0 | prefix only (1 call) |

Readings:

- **The floor is the prefix.** S01/S10/S11 are single-call scenarios whose entire
  prompt (1 138–1 153 tokens) is essentially the 1 126-token prefix. Nothing but
  O4 can touch them.
- **Two tool-output sinks:** S05 (1 767) and S06 (1 361) are 3 128 of the 4 350
  summed median tool tokens — **71.9 %** of tool output is concentrated in two of
  twelve scenarios [derived].
- **Two re-send sinks:** S09 (5 490) and S12 (4 251) are the only scenarios with
  more than one non-command user turn, and both re-send ~75 % of their prompt.
  But their `tool_output_tokens_est` is only 120 each — see §4, hypothesis 4.
- **Reasoning is everywhere**, not concentrated: S03's 765 completion tokens are
  644 reasoning (84 %), S12's 1 357 include 1 107 (81.6 %)
  [baseline · ## Per scenario].

---

## 3. Latency (secondary, for ranking only)

| scope | value | source |
|---|---|---|
| median per call | 35 158 ms | [baseline · ## Latency] |
| median `agent` | 34 704 ms | [baseline · ## Latency] |
| median `summary` | 56 975 ms | [baseline · ## Latency] |
| total wall | 3 564 244 ms (≈ 59 min for 36 runs) | [baseline · ## Totals] |

The summary call is the slowest call type by ~64 % — relevant to O6.

---

## 4. What the OpenRouter smoke proves about live usage and cost accounting

Scope: one S02 run, 2 calls, `google/gemini-2.5-flash-lite` via OpenRouter,
`pricing.basis = openrouter-list` [smoke · ## Meta].

1. **Provider usage is parsed and lands in the totals.** `prompt_tokens 1500`,
   `completion_tokens 155` [smoke · ## Totals] — both present, which is what
   REQ-V13-AUD-01/EC-11 require the smoke to demonstrate.
2. **The cost formula is exact against a real list price.**
   `1500 × 0.1/10⁶ + 155 × 0.4/10⁶ = 0.00015 + 0.000062 = $0.000212`
   [derived from smoke · ## Meta + ## Totals], reproducing the reported
   `cost_usd 0.000212` to the digit. This is the **one non-estimated cost figure**
   in this audit and it validates the same code path that produces the baseline's
   labelled estimates.
3. **The cache field populates when the provider reports it.** The smoke shows
   `cache_hit_rate 0` — a reported *zero* — where the baseline shows
   `cache_hit_rate n/a` and `cached_tokens 0` [baseline · ## Totals]. LM Studio
   reports no caching at all, so locally there is no cached-token accounting to
   capture; on a provider that reports usage the field is populated and readable.
   The smoke proves **accounting**, not caching: a single S02 call need not hit a
   provider cache and AUD-01 makes no claim about `cached_tokens` from it.
4. **Reasoning accounting works on a cloud provider too**, and counts can arrive
   without text: `reasoning observed: yes, max reasoning_tokens: 137, max
   reasoning_chars: 0` [smoke · ## Reasoning] — the provider reports the count in
   usage while exposing no reasoning text.
5. **Re-send is a property of the harness/agent loop, not of the model.** Same
   scenario, different provider, different model, different tokenizer, yet
   `resent_share 0.485333` [smoke · ## Totals] vs `0.495056`
   [baseline · ## Totals] — within one percentage point. The optimizations that
   target re-send are therefore expected to transfer across providers.
6. **Limits of the smoke.** `prefix_tokens n/a` and `prefix_share n/a`
   [smoke · ## Meta, ## Totals]: no prefix calibration ran, so O4's measurement
   basis is the LM Studio baseline alone. Token counts are not comparable across
   the two files (S02 prompt 2 406 baseline vs 1 500 smoke is a tokenizer
   difference, not a saving).

---

## 5. Ranked hypotheses for stage C

**Ranking criterion:** expected saving on the v1.3 optimized run (D1), largest
first, with a confidence column. Ceilings are stated separately from realistic
bands. Percentages of cost are against the baseline's `$0.09675 (ESTIMATE)`
[baseline · ## Totals]. The savings are **not strictly additive** — O4 shrinks
the prompt that O1's tool output sits inside, and O5 acts on the completion side.

| # | opt | REQ ids | expected saving | confidence |
|---|---|---|---|---|
| 1 | **O5** reasoning control | REQ-V13-RSN-01, RSN-02 | up to −11 081 completion tokens (−65.5 % of Σcompletion), ≈ **−$0.0283 (ESTIMATE), −29 % of run cost** | **conditional** — mechanism unvalidated |
| 2 | **O4** prefix compression | REQ-V13-PFX-01, PFX-02, PFX-03 | −20 % … −29 % of Σprompt ≈ −25 000…−36 500 tokens, ≈ **−$0.011…−$0.016 (ESTIMATE), −11 %…−16 %** | **high** — deterministic char budgets |
| 3 | **O1** token-aware tool output | REQ-V13-TOO-01 … TOO-10 | ≈ −5 000…−8 000 prompt tokens (−4 %…−6 % of Σprompt), ≈ **−$0.003 (ESTIMATE), −3 %** | medium |
| 4 | **O2** stale tool-result stubs | REQ-V13-HST-01 … HST-05 | order **10² tokens**, ≲ 0.6 % of Σprompt on this baseline | high that it works, high that it is small |
| 5 | **O3** byte-stable prefix / caching | REQ-V13-CCH-01 … CCH-04 | **0 tokens, $0** on this baseline; latency only | high (that the token saving is zero) |
| 6 | **O6** routing by purpose | REQ-V13-RTE-01, RTE-02 | **0 realized** (not enabled); ceiling if enabled = 2 808 tokens, $0.00413 (ESTIMATE), 4.3 % | n/a — no candidate model configured |

Combined realistic effect of ranks 1–3 ≈ **−$0.044 of $0.09675 ≈ −45 %
(ESTIMATE)**, non-additive.

### Hypothesis 1 — O5, reasoning control (REQ-V13-RSN-01, REQ-V13-RSN-02)

**O5 state: `applicable — pending validation`.** See §6.

Reasoning is the largest single line in the run's estimated cost. Σ reasoning
12 144 of 16 923 completion tokens = 71.8 %; the tool-exposed group alone is
11 081 [baseline · ## Reasoning]. At the reference output price
`11 081 × 2.55/10⁶ = $0.02826 (ESTIMATE)` = **29.2 % of the run's estimated
cost** [derived] — more than the entire input side of any other hypothesis.

*If* the RSN-02 mechanism validates in the bounded probe, the ceiling is those
11 081 tokens, because all 84 error-free agent calls were tool-exposed (§2.6) and
the `auto` policy leaves only the 3 summary calls (1 063 tokens) untouched. This
is a ceiling, not a promise: the audit cannot know whether disabling thinking
costs answer quality, nor whether the model honours the switch. Secondary effect:
reasoning tokens are generated serially, so this is also the largest latency
lever against a 34 704 ms median agent call [baseline · ## Latency].

### Hypothesis 2 — O4, prefix compression (REQ-V13-PFX-01/02/03)

The highest-confidence saving, and — per §2.4 — also the largest lever on re-sent
tokens.

Data: prefix share **0.785733**, prefix 1 126 tokens × 88 calls = 99 088 of
126 109 prompt tokens [baseline · ## Totals, ## Meta]. Three of twelve scenarios
are *nothing but* prefix (§2.7), and ≥ 83 % of all re-sent tokens are prefix
re-sends (§2.4).

Targets [spec REQ-V13-PFX-01, REQ-V13-PFX-02]: system prompt 1 701 filled chars
→ ≤ 924 filled (the datetime line relocates to the user message under
[spec REQ-V13-CCH-01]); tool schema JSON 2 041 → ≤ 1 400 chars. Total prefix text
3 742 → ≤ 2 324 chars = **−37.9 %**.

Primary estimate [derived]: `prefix_share 0.785733 × 37.9 % ≈ 29.8 % of Σprompt`
≈ −37 550 tokens. Cross-check via the implied ratio
`3 742 chars / 1 126 tokens = 3.32 chars/token` → `1 418 chars ≈ 427 tokens/call
× 88 = 37 576` — the two routes agree to 0.1 %. Both routes assume the removed
prose tokenizes like the prefix average, which it need not (JSON schema text
tokenizes differently from prose), and `prefix_tokens` includes `ping` and
template markup, which makes the ratio slightly optimistic. Hence the band
**−20 % … −29 % of Σprompt**, i.e. **−$0.011 … −$0.016 (ESTIMATE)**.

### Hypothesis 3 — O1, token-aware tool output (REQ-V13-TOO-01 … TOO-10)

`exec` is 87.9 % of tool output (§2.1) and the effect is concentrated in exactly
two scenarios (§2.7):

- **S06 noisy-log**, 1 361 median tool tokens: the payload is 200 identical
  `INFO heartbeat ok` lines. The duplicate collapse of
  [spec REQ-V13-TOO-01] step 2 reduces them to one line plus a `[×200]` marker,
  leaving essentially only the traceback — an expected ~−1 200 tokens/run.
- **S05 big-output**, 1 767 median tool tokens from the 4096-byte capture: the
  head/tail window at `EXEC_OUTPUT_DEFAULT_CHARS = 1500`
  [spec REQ-V13-TOO-02, spec §2 constants] cuts the retained text to ~37 % — an
  expected ~−1 100 tokens/run.

Everything else is ~0 by construction: S07's 397 tokens are largely `load_skill`
output, which [spec REQ-V13-TOO-10] explicitly exempts from compaction; S08's
368 tokens of fetch output already sit under `FETCH_INLINE_DEFAULT_CHARS = 5000`;
S02/S03/S04/S09/S12 produce 52–120 tokens, far below any window. Scaled over 3
repeats: ≈ −6 900 of 13 116 tool-output tokens, ≈ **−5.5 % of Σprompt**,
≈ **−$0.003 (ESTIMATE)**. O1 also directly attacks the fastest-growing context
category (`tool`, +1301.4 chars/run, §2.3).

### Hypothesis 4 — O2, stale tool-result stubs (REQ-V13-HST-01 … HST-05)

**The data does not support expecting a measurable win from O2 on this
benchmark**, and the audit says so plainly while keeping it as a MUST
(the audit may re-rank, never drop).

[spec REQ-V13-HST-01] stubs tool-role messages **older than the current user
message**. Only S09 and S12 have more than one non-command user turn
(Appendix C), and their median `tool_output_tokens_est` is **120 each**
[baseline · ## Per scenario] — the smallest tool payloads in the run apart from
the no-tool scenarios. That 120 is the tool output *produced* per run, and a
stale result is re-sent on each later call of the same conversation (S09 and S12
are 5 calls each [baseline · ## Per scenario]), so the addressable volume is a
small multiple of it — but only the copies belonging to *earlier* turns qualify,
and the stub itself costs tokens ([spec REQ-V13-HST-01]: tool name, exit code,
char count, sha prefix, 120-char head). Even at a 3–4× multiplier the addressable
volume stays of **order 10² tokens** across the whole baseline,
**≲ 0.6 % of Σprompt** — at or below the noise floor of a 3-repeat run.

It stays in scope on structural grounds, not measured ones: the mechanism scales
with tool-output size across turns, and this baseline simply pairs its large
outputs (S05: 1 767, S06: 1 361) with single-turn scenarios and its multi-turn
scenarios with 120-token outputs. A workload that mixed the two — an S05-scale
capture followed by two more user turns — would re-send ~1 700 tokens per turn
that the stub would remove. O2 also feeds `prompt_chars_by_role.tool`
[spec REQ-V13-HST-05], the category that grows fastest (§2.3).

### Hypothesis 5 — O3, byte-stable prefix and caching (REQ-V13-CCH-01 … CCH-04)

**Expected token/cost saving on this baseline: exactly zero.**
`cached_tokens 0` and `cache_hit_rate n/a` [baseline · ## Totals] — LM Studio
reports no cache accounting, so there are no cached-price tokens to bill at the
$0.085/Mtok cached rate [baseline · ## Meta]. This is precisely what
[spec REQ-V13-CCH-04] requires the report to state honestly.

What O3 *can* deliver here is latency: 1 126 prefix tokens are re-processed on
each of 85 agent calls, against a 34 704 ms median agent call
[baseline · ## Latency]. The metric is a median-latency delta per call, not a
token delta. Note also that O2 invalidates the history portion of any prefix
cache once per user turn, so the stable portion is the prefix itself — which is
another argument for shipping CCH-01/CCH-02 alongside O4. CCH-03 (Anthropic
`cache_control`) cannot be measured in v1.3 at all: the only OpenRouter run
precedes stage C, so it is *implemented, unmeasured* by construction.

### Hypothesis 6 — O6, routing by purpose (REQ-V13-RTE-01, REQ-V13-RTE-02)

Config-only and not enabled during the benchmark, so the realized saving in v1.3
is **0**. The affected volume is exactly quantified:
`summary` = 3 calls, 1 424 prompt + 1 384 completion = **2 808 tokens**
[baseline · ## Totals by purpose] = 2.0 % of the run's 143 032 tokens. At the
reference prices that side costs
`1 424 × 0.425/10⁶ + 1 384 × 2.55/10⁶ = $0.00413 (ESTIMATE)` = **4.3 % of the
run's estimated cost** [derived] — a real ceiling, and one that would also cut
the slowest call type (56 975 ms median, §3).

Per [spec REQ-V13-RTE-02] the **saving estimate must be reported as
`estimate: n/a — no candidate model configured`**: `LLM_SUMMARY_MODEL` is `n/a`
[baseline · ## Meta] and no second model's price is in the pricing snapshot. The
inputs a future estimate needs are: the 1 424/1 384 token split above, and the
candidate model's input/output $/Mtok.

---

## 6. O5 state (REQ-V13-RSN-01)

The baseline's `## Reasoning` block reads `reasoning observed: yes`, with
`Σ reasoning_tokens: 12144` and `max reasoning_tokens: 825`
[baseline · ## Reasoning]. The decision rule of REQ-V13-RSN-01 is therefore
satisfied on the *applicable* branch, and this audit records:

> **O5: `applicable — pending validation`**

Per REQ-V13-RSN-01 the audit names only `not_applicable` or
`applicable — pending validation`. The two terminal states of O5 are decided in
stage C by the bounded live probe of REQ-V13-RSN-02 and named there, in
`report-v1.3.md` — this audit takes no position on them.

---

## 7. What the data does NOT justify

1. **O3 (10.3) as a token or cost measure.** `cached_tokens 0`,
   `cache_hit_rate n/a` [baseline · ## Totals]: LM Studio reports no caching, so
   no cached-token saving exists to capture. The data justifies O3 as a
   **latency** measure and as the byte-stability precondition for O4 — nothing
   more. Any claim of billed-token savings from prefix caching in v1.3 would be
   unsupported.
2. **CCH-03 as a measured result.** The only OpenRouter run is the pre-stage-C
   smoke, and it used a Google model, not an `anthropic/` one
   [smoke · ## Meta]. The `cache_control` request shape can only be reported as
   *implemented, unmeasured*; an estimate would be invention.
3. **O2 (10.2) as a headline saving.** Order 10² tokens, ≲ 0.6 % of Σprompt
   (hypothesis 4). It must ship — it is a MUST — but it must not be presented as
   a material contributor to the v1.3 result, and any post-run delta attributed
   to it will be indistinguishable from noise.
4. **A numeric saving estimate for O6 (10.6).** No candidate model is configured
   and no second price is in the snapshot; REQ-V13-RTE-02 mandates
   `estimate: n/a`. The 4.3 % figure above is a *ceiling on the affected volume*,
   not a saving.
5. **Any non-estimated cost claim about the baseline.** Basis
   `reference:qwen/qwen3.8-27b`; the inference was local and free
   [baseline · ## Meta]. Real-money savings cannot be claimed from this run
   (REQ-V13-PRC-03).
6. **Any cross-provider token comparison.** The smoke's 1 500 prompt tokens for
   S02 versus the baseline's 2 406 is a tokenizer and model difference
   [smoke · ## Meta vs baseline · ## Meta], not evidence of anything
   optimizable.
7. **A cross-category context-growth ranking.** The report names only the winning
   category (§2.3); a claim that `tool` grows *N times* faster than `assistant`
   or `user` cannot be made from the permitted sources.
8. **Reliability work driven by token economy.** The 1 failed call of 88 is a
   transport timeout with 36/36 runs still successful
   [baseline · ## Totals, ## Failures] — a reliability observation, outside the
   scope of section 10.
9. **Anything in 10.7.** Semantic cache, smart git diff, AgentHandoff, batch
   processing: nothing in the baseline data contradicts their NON-GOAL status.
