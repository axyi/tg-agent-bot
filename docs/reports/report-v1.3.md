# Implementation report — spec-v1.3

Commits on `main`, all four referencing `docs/prompts/09-go-spec-v1.3.md`:

| commit | stage | contents |
|---|---|---|
| `69ebc75` | C1, stage A | v1.2 carry-over fixes, the observability layer, the pricing module, the benchmark harness and the dashboard |
| `f0572c8` | C2 (tag `v1.3-baseline`) | the baseline benchmark artifacts and `docs/reports/audit-v1.3.md` — documentation only |
| `c11f590` | C3, stage C | the optimizations O1–O6 and the documentation that does not depend on the measured result |
| this commit | C4 (tag `v1.3`) | the optimized-run artifacts, this report, the measured README headline, `docs/plan.md`, `docs/llm-usage.md` |

Executor model: **claude-opus-5** (Claude Code harness).
Prompt: `go docs/spec/spec-v1.3.md` — logged as `docs/prompts/09-go-spec-v1.3.md`.
**19 prompt files** for this run: `docs/prompts/09-go-spec-v1.3.md` through
`docs/prompts/27-v13-TC9-docs.md`.

**Verdict: FAIL.** The cost gate and the quality gate both failed. Section
13.4 applies; the analysis and the ranked list of untried v1.4 levers are
below.

Citations follow the audit's convention: `[bench-v1.3 · ## Section]` names a
cell of a named table in `docs/reports/bench-v1.3.md`, `[baseline · …]` in
`docs/reports/bench-baseline.md`, `[smoke · …]` in
`docs/reports/bench-openrouter-smoke.md`, `[probe · …]` in
`docs/reports/bench-reasoning-probe.md`, `[audit · §N]` in
`docs/reports/audit-v1.3.md`. `[derived]` marks arithmetic over cited cells,
shown inline. No benchmark JSON or log file was opened (REQ-V13-EC-12).

## Gates

Six gates per commit, run verbatim and in the order of AGENTS.md / §13.1.
Each row records the gates as run on the tree **about to be committed**.

| commit | 1 `uv sync --locked` | 2 `ruff check .` | 3 `pytest` | 4 `--selftest` | 5 `--selftest-live` | 6 `mutation_check.py` |
|---|---|---|---|---|---|---|
| C1 `69ebc75` | rc=0 | rc=0 | rc=0 — **594 passed** | rc=0 | rc=0 — fully green, after one re-run (see Fix-loop iterations) | rc=0 — **51 mutations, 51 killed**, 0 survived |
| C2 `f0572c8` | rc=0 | rc=0 | rc=0 — 594 passed (test tree unchanged from C1; C2 touches `docs/` only) | rc=0 | not run — §13.1 runs gates 1–4 on the docs-only commit | not run — same clause |
| C3 `c11f590` | rc=0 | rc=0 | rc=0 — **719 passed** | rc=0 | rc=0 — fully green | rc=0 — **65 mutations, 65 killed**, 0 survived |
| C4 (staged tree) | rc=0 | rc=0 | rc=0 — **719 passed** | rc=0 | rc=0 — fully green | rc=0 — **65 mutations, 65 killed**, 0 survived — *confirmed by an unchanged re-run* |

The C4 row is written under the two-pass procedure of §13.1: every C4 file is
written with the row holding the literal placeholder `_pending_`, the six
gates are run, the placeholder is replaced with those results, every C4 file
is staged, and the six gates are run again **without changing any file**; the
tree tested by that second pass is byte-for-byte the tree committed. The row
is therefore labelled `C4 (staged tree)` and its recorded results are
**confirmed by an unchanged re-run**.

Gate 5 was fully green at C1 and C3. spec-v1.2's REQ-V12-PRE-01 item 2
exception ("record and proceed" when LM Studio is unreachable) is **withdrawn**
by REQ-V13-EC-10, so no commit of this run was made while gate 5 was red.

### Test and mutation growth

| point | tests | mutations |
|---|---|---|
| `1ecc35e` (v1.2 delivered state) | 326 | 31 |
| C1 `69ebc75` (stage A) | 594 | 51 |
| C3 `c11f590` (stage C) | **719** | **65** |

**+393 new tests** over the run against the spec's floor of +70 (final ≥ 396,
§11) — 719 clears it by 323. **65 mutations, all killed**, against the floor
of 64 (§12: the 31 of v1.2 plus the 33 new entries).

## Benchmark runs

Four benchmark steps ran, in the order of §13.2. **`skipped_scenarios: []` in
every one of them** — `wttr.in` was reachable throughout, so the network
scenario S08 ran in both full runs and no scenario was skipped on either side
[bench-v1.3 · ## Meta].

| step | tag | command | artifact |
|---|---|---|---|
| B1 | `baseline` | `bench.py run --tag baseline --repeats 3 --timeout-s 1800` | `docs/reports/bench-baseline.md` |
| B2 | `openrouter-smoke` | `bench.py run --provider openrouter --only S02 --repeats 1 --tag openrouter-smoke --max-cost-usd 0.50` | `docs/reports/bench-openrouter-smoke.md` |
| CP | `reasoning-probe` | `bench.py run --only S05 --repeats 1 --tag reasoning-probe` + `bench.py report` | `docs/reports/bench-reasoning-probe.md` |
| D1/D2 | `optimized` | `bench.py run --tag optimized --repeats 3 --timeout-s 1800`, then `bench.py report --baseline … --candidate … --gate` | `docs/reports/bench-v1.3.md` |

`--timeout-s 1800` on both full runs is the resolution of spec defect E.5
(below), not a change of treatment: `timeout_s` is a locked meta field, both
files carry `1800.0`, and it is the harness's abort threshold rather than a
bot setting [bench-v1.3 · ## Meta].

### Environment of both full runs

| field | value |
|---|---|
| provider / model | `lmstudio` / **`qwen/qwen3.8-27b`** — identical on both sides [bench-v1.3 · ## Meta] |
| context length | **42496** — the **configured** `LMSTUDIO_CONTEXT_LENGTH`, recorded as configuration, never read back as a measured server property [bench-v1.3 · ## Meta] |
| repeats | 3 (12 scenarios × 3 = 36 runs per side) |
| `scenarios_sha256` | `586ed397…0d0a48` — identical on both sides |
| `config_sha256` | `754a4686…4c91e` — identical on both sides |
| pricing basis | **`reference:qwen/qwen3.8-27b`**, $0.425 / $2.55 per Mtok in/out, cached $0.085 |
| price snapshot | **2026-09-02T16:33:54Z** (the baseline file's `meta.pricing`; both sides are recomputed against it by `report --gate`, §13.3) |

**Every USD figure in this report is an ESTIMATE (REQ-V13-PRC-03).** The
inference ran locally on LM Studio and was free; the basis is the OpenRouter
list price of the *same model id*, snapshotted before B1. The basis was chosen
by the executor before B1 precisely so that the assignment's primary metric —
cost per successful task — was computable at all, rather than falling back to
the tokens-per-task substitute §13.3 prescribes for a null pricing basis. The
one non-estimated cost figure produced by this run is the smoke's
`cost_usd 0.000212` against a real OpenRouter list price [smoke · ## Totals].

### B1 — baseline (36/36 successful)

| metric | value | source |
|---|---|---|
| runs / success rate | 36/36, **1.0** | [baseline · ## Totals] |
| LLM calls | 88, of which 1 failed | [baseline · ## Totals] |
| prompt / completion tokens | 126 109 / 16 923 | [baseline · ## Totals] |
| reasoning tokens | 12 144 (**71.8 %** of completion) | [baseline · ## Reasoning] |
| tool output (`tool_output_tokens_est`) | 13 116, of which `exec` 11 523 over 36 calls | [baseline · ## Totals, ## Audit] |
| re-sent share | 0.495056 | [baseline · ## Totals] |
| prefix tokens / share | 1 126 per call, 0.785733 | [baseline · ## Meta, ## Totals] |
| median latency per call | 35 158 ms | [baseline · ## Latency] |
| estimated cost / cost per success | $0.09675 / **$0.002687** (ESTIMATE) | [baseline · ## Totals] |

The audit built on this file ranked the levers O5 > O4 > O1 > O2 > O3 > O6 and
put the combined realistic effect of the top three at ≈ −45 % (ESTIMATE)
[audit · §5].

### B2 — OpenRouter smoke (accounting proof, not a comparison)

One S02 run, 2 calls, `google/gemini-2.5-flash-lite`, `pricing.basis
openrouter-list` [smoke · ## Meta]. It proves the accounting path end to end:
provider usage parses into the totals (1 500 prompt / 155 completion), the
cost formula reproduces `$0.000212` exactly from the list price, the
`cached_tokens` field populates where a provider reports it (`cache_hit_rate
0`, a reported zero, versus the baseline's `n/a`), and reasoning counts arrive
even with no reasoning text (`max reasoning_chars: 0`)
[smoke · ## Totals, ## Reasoning; audit · §4]. Token counts are **not**
comparable across the two
files — S02's 1 500 prompt tokens here versus 2 406 in the baseline is a
tokenizer and model difference, nothing more [audit · §7 item 6].

### D1/D2 — optimized run and verdict

| metric | baseline | candidate | Δ |
|---|---|---|---|
| success rate | 1.0 | 0.944444 | **−5.6 pp** |
| calls / failed calls | 88 / 1 | 89 / **0** | +1 / −1 |
| prompt tokens | 126 109 | 103 236 | −22 873 (**−18.1 %**) |
| completion tokens | 16 923 | 16 021 | −902 (−5.3 %) |
| reasoning tokens | 12 144 | 11 680 | −464 (−3.8 %) |
| tool output tokens | 13 116 | 9 014 | −4 102 (**−31.3 %**) |
| re-sent tokens / share | 62 431 / 0.495056 | 53 947 / 0.522560 | −8 484 / **+5.6 %** |
| prefix tokens / share | 1 126 / 0.785733 | 842 / 0.725890 | −284 / −5.98 pp |
| median latency per call | 35 158 ms | 18 198 ms | **−36.7 %** wall |
| estimated cost | $0.09675 | $0.084729 | −$0.012021 (−12.4 %) |

All rows from [bench-v1.3 · ## Totals, ## Latency, ## Meta].

**Verdict block, verbatim in substance from [bench-v1.3 · ## Verdict]:**

- metric: cost per successful task; price snapshot `qwen/qwen3.8-27b` as of
  2026-09-02T16:33:54Z
- `B_plain` **$0.002687** (failed_B 1) · `C_plain` **$0.002492** (failed_C 0) ·
  `C_conservative` **$0.002492**
- gate threshold (0.70 × B_plain): **$0.001881**
- success rate 1.0000 → 0.9444 (−5.6 pp; the assignment's headline is 2 pp,
  but at 36 runs one flipped run is already 2.8–3.0 pp, so the candidate may
  lose no run net)
- regressed scenarios: **S01 3/3 → 1/3**
- cost gate **FAIL** · quality gate **FAIL** · **verdict: FAIL**

`failed_C = 0`, so `C_conservative` equals `C_plain` exactly: the failure is
not an artifact of §13.3's conservative bound on unmeasured failed
invocations. Both limbs of the quality gate failed **independently** — the
aggregate limb (−5.6 pp against a −2 pp headline and a one-run resolution of
2.8–3.0 pp) and the per-scenario limb (S01 lost two of three repeats, which
the rule rejects even when the aggregate is compensated elsewhere).

### The combined before/after cost delta — the only causal claim

> **Cost per successful task fell from $0.002687 to $0.002492, −7.3 %
> (ESTIMATE); total estimated run cost fell from $0.09675 to $0.084729,
> −12.4 %.** The target was −30 % (threshold $0.001881).

O1–O4 were enabled together and there are no ablation runs (NG-05), so this
combined delta is the **only** causal statement this report makes about the
optimizations. Everything in the next section is correlation.

## Per-optimization observed supporting metric

> **Attribution is non-causal: each metric is consistent with its
> optimization, not proof of it.**

| optimization | its observed metric | before | after | reading |
|---|---|---|---|---|
| **O1** token-aware tool output | `tool_output_tokens_est` (total) | 13 116 | 9 014 | −4 102, −31.3 % [bench-v1.3 · ## Totals]. `exec` 11 523 over 36 calls → 6 854 over 35 calls [## Audit]; S06's duplicate-collapse target 1 361 → 128 (−90.6 %) and S05's window target 1 767 → 1 792 (+1.4 %) [## Per scenario] |
| **O2** stale tool-result stubs | `resent_tokens` / `prompt_tokens` on the multi-turn scenarios | S09 5 490/7 124 = **0.771**; S12 4 251/5 703 = **0.745** | S09 7 872/9 606 = **0.819**; S12 1 133/2 078 = **0.545** | moves in both directions and is **confounded by call count**: S12's calls fell 5 → 3 and its tool calls 2 → 0, S09's calls rose 5 → 7 [## Per scenario]. The audit predicted an addressable volume of order 10² tokens, ≲ 0.6 % of Σprompt [audit · §5 hyp. 4] — below this benchmark's resolution either way |
| **O3** byte-stable prefix / caching | median `latency_ms` **only** | 35 158 ms per call; agent 34 704 ms; summary 56 975 ms | 18 198 ms per call; agent 17 536 ms; summary 49 179 ms | [## Latency]. **No token or cost metric is claimed**: `cached_tokens` is 0 and `cache_hit_rate` `n/a` on both sides — LM Studio reports no cache accounting, so no cached-price token exists to bill (REQ-V13-CCH-04) |
| **O4** prefix compression | `prefix_tokens` | 1 126 | 842 | −284, −25.2 % per call [## Meta]. `prefix_share` 0.785733 → 0.725890 [## Totals] |
| **O5** reasoning control | applicability (REQ-V13-RSN-01) | `reasoning observed: yes`, Σ 12 144, share 0.7176; tool-exposed 84 calls, Σ 11 081, share 0.7131 [baseline · ## Reasoning] | **applicable** → implemented → probe inconclusive-free and negative → final state **`attempted_removed`** | see the next section |
| **O6** routing by purpose | **not benchmarked** | — | — | config-only by design (§10.6): only one model fits the GPU box, so no candidate model was configured: `env_flags.LLM_SUMMARY_MODEL` is `n/a` on the baseline side (the `Config` field does not exist on the C1 tree) and empty on the candidate side [## Meta] — the pair that spec defect E.6 had to be resolved to accept. REQ-V13-RTE-02 mandates `estimate: n/a — no candidate model configured`. The affected volume is exact: `summary` = 3 calls, 762 prompt + 1 404 completion tokens on the candidate side [## Totals by purpose] |

## O5 — the central finding

REQ-V13-RSN-01's decision rule read the baseline's `## Reasoning` block as
`reasoning observed: yes` (Σ 12 144 reasoning tokens, 71.8 % of all completion
tokens; 71.3 % on the tool-exposed group), so O5 was **applicable** and the
audit recorded `applicable — pending validation` [audit · §6]. It was the
audit's single largest lever: 11 081 tool-exposed reasoning tokens ≈ $0.02826
(ESTIMATE) ≈ **29.2 % of the baseline's estimated run cost** [audit · §5
hyp. 1]. O5 was therefore implemented, not skipped.

**Mechanism.** LM Studio's OpenAI-compatible endpoint documents no
`chat_template_kwargs` passthrough
(<https://lmstudio.ai/docs/developer/openai-compat/chat-completions>), so the
implementation used Qwen3's own documented soft switch, the `/no_think`
directive
(<https://github.com/QwenLM/Qwen3/blob/main/docs/source/inference/transformers.md>).

**Probe (step CP, REQ-V13-RSN-02).** One S05 run, conclusive on the first
attempt — no repeat was needed. S05 passed 1/1, and the report's `## Reasoning`
block reads `tool-exposed calls: calls: 2, reasoning observed: yes, …
reasoning share: 0.7373` [probe · ## Reasoning]. The switch is simply not
honoured: the model reasons at the same share with the directive in place.

**Final state: `attempted_removed`.** The knob is **not in the delivered
tree** — no `Config` field, no config validation, no test, no README line, no
`.env.example` line. The only surviving evidence is
`docs/assets/bench/reasoning-probe.json` and
`docs/reports/bench-reasoning-probe.md`.

This explains the one Meta-table discrepancy a reader will notice:
`env_flags.LLM_REASONING` is `auto` in [probe · ## Meta] and `n/a` on **both**
sides of [bench-v1.3 · ## Meta]. That `n/a` pair is not an omission — it *is*
the evidence for `attempted_removed`: the variable does not exist on either
measured tree, so neither the baseline nor the candidate could have been
influenced by it. The probe is the only artifact in which the knob ever
existed.

The consequence for the verdict: the largest lever the audit found —
≈ 29 % of run cost — was removed from the achievable set **before** D1 ran,
and nothing replaced it.

## Why the verdict is FAIL (§13.4)

### 1. The cost metric is dominated by the completion side, which O1–O4 do not touch

At the reference prices output is billed **6× input** ($2.55 vs $0.425 per
Mtok). Decomposing the two totals
[derived from bench-v1.3 · ## Totals and ## Meta]:

- baseline: `126 109 × 0.425/10⁶ = $0.053596` input + `16 923 × 2.55/10⁶ =
  $0.043154` output = **$0.096750** — reproducing the reported cell exactly;
- candidate: `103 236 × 0.425/10⁶ = $0.043875` input + `16 021 × 2.55/10⁶ =
  $0.040854` output = **$0.084729** — likewise exact.

O1, O2, O3 and O4 are all **input-side** optimizations. They delivered −18.1 %
on prompt tokens. But completion fell only −5.3 %, and completion is
**48.2 %** of the candidate's estimated cost (`0.040854 / 0.084729`)
[derived]. With the completion side effectively fixed, clearing the gate
required the input side alone to carry the whole −30 %: the target Σcost is
`0.001881 × 34 successes = $0.063954`, leaving an input budget of
`0.063954 − 0.040854 = $0.023100` = **54 354 prompt tokens** — a further
−47.4 % below the candidate's 103 236, and −56.9 % below the baseline's
126 109 [derived]. No combination of input-side levers in this spec reaches
that.

### 2. Reasoning is 73 % of the completion side and stayed there

Reasoning tokens fell 12 144 → 11 680 (−3.8 %) while the reasoning **share**
of completion *rose*, 0.7176 → 0.7290 [bench-v1.3 · ## Reasoning]. The small
absolute drop tracks the shorter prompts, not any reasoning control: O5's
mechanism was proven inert (above). The candidate spends
`11 680 × 2.55/10⁶ = $0.029784` (ESTIMATE) = **35.2 % of its own estimated
cost** on tokens the user never sees [derived].

> **Counterfactual arithmetic over published cells — not a measured result,
> and not part of the causal claim.** Had a working reasoning switch removed
> the candidate's reasoning volume with nothing else changing:
> `Σcost = 0.084729 − 0.029784 = $0.054945` → `$0.054945 / 34 successes =
> $0.001616` ≤ the `$0.001881` threshold — the **cost** gate would have
> passed. The **quality** gate would still have failed on S01 (3/3 → 1/3), so
> the verdict would still have been FAIL. This assumes no quality effect from
> suppressing reasoning, which is exactly what the run could not test.

### 3. O4 landed at the bottom of its predicted band, and the prefix still dominates

The audit's band for O4 was −20 % … −29 % of Σprompt [audit · §5 hyp. 2].
Measured: prompt tokens −18.1 % *for all four input-side optimizations
combined*, with `prefix_tokens` −25.2 % per call. The prefix remains **72.6 %**
of the candidate's prompt tokens (`842 × 89 / 103 236 = 0.72589`, matching the
reported `prefix_share`) [derived]. Three of twelve scenarios (S01, S10, S11)
are still essentially nothing but prefix [audit · §2.7].

### 4. Re-send got structurally worse, not better

`resent_share` rose 0.495056 → 0.522560 [bench-v1.3 · ## Totals] even though
absolute re-sent tokens fell 13.6 %: the prompt shrank faster than the
re-send did. The re-send is still overwhelmingly the prefix, not history —
on the candidate side, 39 conversation groups (36 runs plus one extra for each
of the 3 S12 `/new` turns) against 86 agent calls leave 47 non-first agent
calls, each re-sending ≥ 842 prefix tokens = ≥ 39 574, plus ≥ 762 for the
three summary calls: **≥ 40 336 of 53 947 = ≥ 74.8 %** of all re-sent tokens
are prefix re-sends [derived, same method as audit · §2.4].

### 5. The quality regression: S01

S01 fell 3/3 → 1/3. Both failures are `checks` failures with
`answer_regex: pattern not found` — not errors, not timeouts: the model
answered, and the answer is present in [bench-v1.3 · ## Failures]. In the same
scenario the completion grew 214 → 296 tokens (+38.3 %) and reasoning 120 →
219 (+82.5 %) [## Per scenario] — the simplest scenario in the set got *more*
verbose and *more* reasoning-heavy under the compressed prompt. O4 is the only
change in this run that rewrites the system prompt, so this is **consistent
with** the compression changing the shape of the answer; with no ablation run
it is not proof of it.

Two scenarios also became more expensive, both by taking more rounds: S04
`+27.8 %` cost with tool calls 1 → 2, and S09 `+29.6 %` cost with calls 5 → 7
and prompt tokens +34.8 % [## Per scenario]. A shorter prompt is not
monotonically cheaper when it changes how many rounds the model takes.

### 6. Two levers were zero by construction, and the audit said so in advance

O3 could not produce a token or cost saving on this provider (`cached_tokens`
0, `cache_hit_rate` `n/a` on both sides) and was never claimed to; O6 was not
enabled. Together they account for the gap between the audit's "top three ≈
−45 %" projection and the delivered −12.4 %: of the top three, O5 was
eliminated after the audit and O4 landed low.

## Ranked untried levers for v1.4

Ranked by expected effect on the **candidate's** estimated cost ($0.084729,
34 successes). Each row says whether it is derived from the two benchmark
tables (the §13.4 requirement) or from this run's execution evidence.
None of these was applied — §13.4 forbids a tuning loop after C3, and D1 was
not re-run.

| # | lever | source | expected effect | risk / precondition |
|---|---|---|---|---|
| 1 | **A reasoning switch LM Studio actually honours** — a provider-level parameter, a model whose thinking can be disabled, or a runtime that passes `chat_template_kwargs` through | benchmark tables ([bench-v1.3 · ## Reasoning]) | **−$0.0268 … −$0.0298 (ESTIMATE) = −31.6 % … −35.2 %** of candidate cost: the tool-exposed group is 10 516 reasoning tokens (`× 2.55/10⁶ = $0.026816`), all reasoning 11 680 (`= $0.029784`) [derived]. On the counterfactual above this alone clears the cost gate. **O5's ~29 % remains fully available if a mechanism is found** — the optimization is implemented-and-removed, not disproven | unknown quality cost: nothing in this run measures answer quality without reasoning. Requires a change of runtime or model, i.e. a new baseline |
| 2 | **Enable O6 routing** (summary calls to a cheap or non-reasoning model) | benchmark tables ([bench-v1.3 · ## Totals by purpose, ## Latency]) | ceiling **−$0.003904 (ESTIMATE) = −4.6 %** of candidate cost: the summary purpose is 762 prompt + 1 404 completion tokens (`762 × 0.425/10⁶ + 1 404 × 2.55/10⁶`) [derived]. Also cuts the slowest call type — median summary latency 49 179 ms vs 17 536 ms for agent calls | needs a second model; the maintainer's GPU box fits one at a time, which is exactly why O6 shipped as configuration only. Realized saving is 0 until that changes |
| 3 | **`CONTEXT_WINDOW_MESSAGES` 30 → 20** (spec-named candidate) | benchmark tables ([bench-v1.3 · ## Per scenario]) | upper bound **−$0.0040 (ESTIMATE) = −4.7 %**, and realistically ~0 on this scenario set. Only S09 and S12 have more than one non-command user turn. Their non-prefix re-send is at most `(7 872 − 6 × 842) + (1 133 − 1 × 842) = 2 820 + 291 = 3 111` tokens per repeat ≈ 9 333 over three repeats ≈ $0.0040 [derived] — and that is the bound for dropping *all* history, whereas a 30 → 20 cut binds only on conversations exceeding 20 messages, which the longest scenario here (S09, 7 calls) does not reach | measurable only against a longer-conversation scenario, which would change `scenarios_sha256` and require a new baseline. Direct quality risk: dropping context the model needs |
| 4 | **`EXEC_OUTPUT_DEFAULT_CHARS` 1500 → 1000** (spec-named candidate) | benchmark tables ([bench-v1.3 · ## Audit, ## Totals]) | upper bound **−$0.00097 (ESTIMATE) = −1.1 %**: `exec` is 6 854 of the candidate's 9 014 tool-output tokens (76.0 %, mean 196 tokens/call over 35 calls); a one-third narrower window can remove at most one third of that, ≈ 2 285 tokens at the input price [derived]. O1 already took tool output down 31.3 % | S05's checks depend on retained text; the head/tail window is what makes big captures answerable at all. A cut here trades directly against the quality gate that already failed |
| 5 | **Fix the `LLM_TIMEOUT_S` / `LLM_MAX_TOKENS` mismatch** | execution evidence (spec Appendix E.5; the aborted B1) | ~0 token saving; removes a whole failure class. At the measured latency `21.1 s + 0.093 s/token`, `LLM_TIMEOUT_S = 120` admits only ~1 063 completion tokens, while `LLM_MAX_TOKENS = 2048` needs `21.1 + 0.093 × 2048 ≈ 212 s` [derived]. A long completion therefore times out and is **retried with identical parameters**, re-sending the whole prompt at a cost §13.3 explicitly calls unmeasured. Either raise the timeout above ~212 s or lower `LLM_MAX_TOKENS` to fit | changes the measured treatment, so it invalidates comparison with this run's files and requires a fresh baseline. This is why it was recorded, not fixed, in v1.3 |
| 6 | **`SUMMARY_MAX_TOKENS` consumable entirely by reasoning** | execution evidence (the aborted B1) + benchmark tables | ~0 token saving; removes an intermittent correctness failure. The tools-withheld (summary) group has the highest reasoning share of any group — 0.7681 baseline, 0.8291 candidate [bench-v1.3 · ## Reasoning] — so a summary call can spend its entire budget thinking and emit nothing. **Stated as a fragility, not as breakage:** in the aborted first baseline 2 of 2 summary calls returned empty content with `finish_reason=length`, while in the complete baseline S12 passed 3/3 [baseline · ## Per scenario]. Fix by raising the summary budget, routing summaries away (lever 2), or suppressing reasoning on that path (lever 1) | changes the measured treatment; needs a fresh baseline |
| 7 | **`FETCH_INLINE_DEFAULT_CHARS` 5000 → 3000** (spec-named candidate) | benchmark tables ([bench-v1.3 · ## Per scenario]) | **≈ 0 on this scenario set.** S08 is the only fetch scenario and its whole tool output is 394 tokens on the candidate side — the audit already established that S08's fetch output sits under the 5 000-char window [audit · §5 hyp. 3], so a cut to 3 000 has nothing to bind on here. Absolute ceiling if it bound on everything: 394 tokens ≈ $0.00017 ≈ 0.2 % | would need a scenario fetching a page larger than the inline window before it could be measured at all |

**Ranking note.** Levers 1–4 and 7 are read off the two benchmark tables as
§13.4 requires; levers 5 and 6 were discovered during execution and are listed
alongside because they bound the *reliability* of any future measurement, not
because the tables suggested them. Levers 3–7 all change either the treatment
or the scenario set, so each one costs a fresh baseline — the honest sequencing
for v1.4 is lever 1 first (largest effect, and it needs a new baseline anyway),
with 5 and 6 folded into the same re-baseline.

## Spec defects found during execution

Six clauses of spec-v1.3 turned out to be inconsistent with the code they
describe or with each other. All six are recorded with their resolutions in
**Appendix E of `docs/spec/spec-v1.3.md`**, committed with the behaviour they
describe as AGENTS.md's spec-drift rule requires. None changed a target, a
gate threshold or the four-commit contract.

| id | defect | resolution |
|---|---|---|
| E.1 | REQ-V13-CO-02's illustrative sentence inverts the still-in-force REQ-V12-ORP-02: following it literally would let a second bot instance reap the first instance's **running** exec container — the exact v1.1 fault v1.2 fixed | CO-02's normative first clause (test the `owner=owner_key()` binding) implemented; the example sentence recorded as a defect; REQ-V12-ORP-02 survives unchanged |
| E.2 | REQ-V13-BEN-01's run-set rule made REQ-V13-AUD-03 and REQ-V13-RSN-02 unsatisfiable — a `--only` file could never pass `check`, so neither the smoke report nor the probe report could exist | `run` records the selection as `meta.only`; `check` validates against the selected set; `meta.only` joins the locked meta fields, so a `--only` file can never be gated against a full one. Both B1 and D1 carry `only: n/a` |
| E.3 | REQ-V13-BEN-14 splits the `## Reasoning` figures on `tools_exposed = 1`, but the column stores a **count** (3 for a normal agent round). The tool-exposed group would have been **empty on every real run**, and REQ-V13-RSN-02 would have forced O5 to `attempted_removed` on a **false** reading | the split reads `tools_exposed > 0` / `== 0`; the covering test was rewritten with production-shaped values (3 and 0). Found by the stage-A review (RED) |
| E.4 | REQ-V13-BEN-02 keys the OpenRouter cost-cap refusal on the `--provider` **flag**, so a plain `bench.py run --tag baseline` on a box whose `.env` selects OpenRouter would have spent 36 uncapped live scenarios | the refusal is keyed on the **effective** provider, evaluated before anything is spent. Found by the stage-A review (RED) |
| E.5 | REQ-V13-BEN-05 justifies its 600 s per-run cap as exceeding `LLM_TIMEOUT_S × HTTP_ATTEMPT_LIMIT × rounds`, but that product is `9 × 120 + 8 × 2 = 1 096 s` for a **single** user message — the stated property is arithmetically false | both full runs use `--timeout-s 1800`; `timeout_s` is locked and equal on both sides, so comparability is untouched. See the aborted-B1 note below |
| E.6 | REQ-V13-BEN-03 demands `LLM_SUMMARY_MODEL == ""` in **both** files while REQ-V13-BEN-10 requires `null` wherever the `Config` field does not exist — which is exactly the C1 baseline tree. The two clauses are unsatisfiable together, and D2 would have exited 2 with **no verdict** | the key is treated under the stage-C rule (baseline `null` or `""`, candidate `""`); a non-empty model id on either side remains a hard exit 2. Report-time validation only; no measured datum affected |

### The aborted first baseline (documented, not hidden)

The first B1 attempt hit the 600 s per-run cap on **S12 repeat 2** and exited
4. The root cause was **not** a hang: `LLM_MAX_TOKENS = 2048` is unreachable
within `LLM_TIMEOUT_S = 120` at the measured `21.1 s + 0.093 s/token`, so a
long completion times out and is retried with identical parameters, and S12
repeat 2 hit four consecutive 120 s read timeouts on one message. Both the
harness and the model were behaving exactly as designed; the cap's stated
construction was wrong (E.5). Both full runs were re-run with
`--timeout-s 1800`. **No measured treatment changed** — the flag is the
harness's abort threshold, not a bot setting, and §13.2 benchmark steps are
"blocking, not permanent gates". The re-run is counted as one benchmark
iteration of the §1.4 budget (below). The same aborted run is the source of
the summary-budget fragility recorded as v1.4 lever 6.

## Reviews

Two clean-context reviews by the `code-reviewer` subagent, per §13.5: after
stage A (before B1) and after stage C (before D1). Each was followed by
exactly one fix round, applied in the same stage's commit.

### Stage A — 11 findings (2 RED, 3 YELLOW, 6 GREEN)

Prompts `docs/prompts/16-v13-TA7-review-stage-a.md` and
`17-v13-TA8-review-fixes.md`.

Both REDs were spec defects, not implementation slips, and both are the E.3
and E.4 rows above:

- **RED — `tools_exposed = 1` split (E.3).** The literal spec reading would
  have rendered `tool-exposed calls: calls: 0` on every real run and forced O5
  to `attempted_removed` on a false reading — i.e. it would have produced this
  run's *final answer for O5* without ever probing the mechanism. Fixed to
  `> 0` / `== 0` with the covering test rewritten against production-shaped
  values.
- **RED — OpenRouter cost cap keyed on the flag (E.4).** Fixed to key on the
  effective provider.

The other nine findings were fixed in the same round, with **one exception
deferred by the spec itself**: the README `/stats` row, which REQ-V13-RPT-03
assigns to the stage-C documentation commit. It was written there, in C3.

### Stage C — 11 findings (1 RED, 4 YELLOW, 6 GREEN)

Prompts `docs/prompts/25-v13-TC7-review-stage-c.md` and
`26-v13-TC8-review-fixes.md`.

- **RED — a security regression introduced by O1.** The new `FETCH_MAX_BYTES`
  cut was not followed by `strip_secret_fragment`, so a **truncated prefix of
  a registered secret** taken from a fetched page could reach
  `<EXEC_WORKDIR>/fetch/<hash>.txt` — a file the exec container can read and
  which the tool description explicitly tells the model to grep. That widens
  secret exposure versus v1.2, where the same class of leak was closed
  (REQ-V11-TRN-02 / v1.2's `trn-03-*` mutations). Fixed with canary tests
  plus a new mutation entry (`v13-fragment-after-cut`), so the gate now fails
  if the call is removed again.

The remaining ten findings were addressed in the same fix round, inside C3.

### A coverage regression only the mutation gate could see

Worth recording as an argument for keeping gate 6. Adding the keyword-only
`resolve_cost=` parameter to `summarize_conversation` broke a test stub that
took four positional arguments. The resulting `TypeError` was swallowed by an
`except Exception` in the test's own path, so **the test kept passing** while
REQ-V11-RED-04 (redaction in `bot._send`) went entirely uncovered. Nothing in
`pytest`, `ruff`, either selftest or the diff showed it. It surfaced only
because the pre-existing mutation `v11-send-redacts` started **surviving** —
the mutation gate is the only gate in the six that can detect a test which
still passes but has stopped testing anything.

## Fix-loop iterations used (§1.4)

| loop | used | detail |
|---|---|---|
| gate 5 re-runs | **1** of 3 | during C1, the LM Studio GPU box became unreachable mid-gate (100 % packet loss, `ConnectTimeout`) and came back ~6 minutes later. The gate was re-run and passed. **C1 was not committed while gate 5 was red** — REQ-V13-EC-10 withdrew v1.2's "record and proceed" exception |
| benchmark re-runs | **1** | the aborted B1 (exit 4 on the 600 s cap, E.5), re-run with `--timeout-s 1800` |
| review fix rounds | **1 per review** | one after stage A, one after stage C |
| tuning loop after C3 | **0 — none exists** | §13.4 forbids it: no code, test or configuration default changed after C3, and D1 was not re-run |

## Amended existing tests (§11.6)

Section 11.6 authorizes amending only what the changed system prompt and tool
schemas break, plus what `<think>` stripping affects. Every amended file and
the reason:

| file | what was amended |
|---|---|
| `tests/test_storage.py` | assertions touched by the storage/summary changes |
| `tests/test_summary.py` | two tests plus the future-version fixture |
| `tests/test_v1_guardrails.py` | the `/status` schema line; `test_t_v1_inj_01_notices_and_system_prompt` (system-prompt text and the notice set); `test_history_budget_shrinks_the_window` |
| `tests/test_v11_patch.py` | `test_t_v11_red_04` — the stub signature (the `resolve_cost=` regression above) and a tightened assertion |
| `tests/test_v12_patch.py` | assertions on tool-description and envelope text |
| `tests/test_exec.py` | exec envelope and compaction assertions |
| `tests/test_agent.py` | `test_t_ag_13_system_prompt`; `T-AG-14` fetch-envelope assertions |
| `tests/test_observability.py` | `test_obs05` |
| `tests/fakes.py` | shared fake updated for the changed call signatures |

No test outside this list was modified, and no test was deleted.

## Accepted risks

Two risks are accepted rather than closed, and are stated here because neither
is visible in the benchmark numbers:

1. **The fetch envelope no longer carries `UNTRUSTED_NOTICE`.** This is
   correct per REQ-V13-TOO-07's exact key list, and `exec` keeps its own
   notice — but fetched web content is the highest-bandwidth prompt-injection
   channel in this bot, and its per-message marker is gone. The defence now
   rests entirely on the single compressed line in the system prompt. A future
   spec should either restore a per-envelope marker for `fetch` or prove the
   system-prompt line is sufficient.
2. **Nothing distinguishes "hit `FETCH_MAX_BYTES`" from "hit the inline
   window".** The file saved under `<EXEC_WORKDIR>/fetch/<hash>.txt` is
   presented as the full text, but when the byte cap fired it is itself
   truncated — so the "full text" the model is told to grep can be silently
   incomplete, with no marker distinguishing the two cases.

## Evidence for the C4 documentation requirements

**REQ-V13-RPT-03 — exactly one README line changed in C4.** The
`git diff HEAD -- README.md` captured right after the README edit (the working
tree against C3, which is what C4 commits):

```
diff --git a/README.md b/README.md
index 1e1681c..3f5298f 100644
--- a/README.md
+++ b/README.md
@@ -580,7 +580,7 @@ optimizations, measured against the benchmark below except where noted:
   ships tested but **was not enabled during the benchmark**; the reports carry
   the summary-purpose token total it would affect and never invent a saving.

-**Headline, baseline → optimized:** _measured in C4_
+**Headline, baseline → optimized:** cost per successful task $0.002687 → $0.002492 (**−7.3 %**), success rate 100.0 % → 94.4 % (**−5.6 pp**). The −30 % target was **not** met and the verdict is FAIL: the largest lever the audit found — suppressing reasoning, 71.8 % of all completion tokens — proved unavailable, because LM Studio does not honour the model's documented thinking switch. Prompt tokens still fell 18.1 %, tool output 31.3 % and latency 36.7 %. Full numbers and the analysis: [docs/reports/bench-v1.3.md](docs/reports/bench-v1.3.md).

 ## Benchmark
```

`git diff --stat HEAD -- README.md`: `README.md | 2 +-`, `1 file changed,
1 insertion(+), 1 deletion(-)` — the placeholder line and nothing else.

**REQ-V13-EC-07 — the commit split held.** After C2,
`git diff --stat HEAD~1 HEAD` touched only `docs/` (8 files, 6 022
insertions) — the baseline commit changed no production code. After C3,
`git diff HEAD~1 HEAD -- devtools/bench_scenarios.py` is **empty**: the
scenario set has been frozen since the baseline, which is what makes the two
files' identical `scenarios_sha256` meaningful rather than circular.

## Executor token usage

From `docs/llm-usage.md` (rows 30–31 and their Σ), reproduced here with its
`unknown` cells intact as REQ-V13-RPT-01 requires:

| # | Stage | Model | Tokens | Cost |
|---|---|---|---|---|
| 30 | v1.3 main session — the whole `go` run across the four commits | claude-opus-5 | unknown | unknown |
| 31 | v1.3 task subagents — 18 of the run's 19 prompt files (`10-…`–`27-…`; the 19th is row 30's own `09-go-spec-v1.3.md`), incl. two `code-reviewer` reviews and the audit subagent | claude-opus-5 | unknown | unknown |
| **Σ** (rows 30–31, one `go` run) | | claude-opus-5 | unknown | unknown |

**Prompts: 19 files** (`docs/prompts/09-go-spec-v1.3.md` …
`27-v13-TC9-docs.md`) — the one figure that is directly observable.

Every token and cost cell is the literal `unknown`, not an estimate: the
executor has no API to its own session usage and this harness displayed no
usage or cost line during the run, so there is no named source to cite
(REQ-V13-RPT-06). The measured values are filled in afterwards by the
maintainer from the lab's session transcripts (`tools/session-usage.py`) and
recorded in `economics.md`, which lives outside this repository. Inference the
*bot* itself spent is a separate matter and is fully reported above: the two
full benchmark runs cost $0.09675 + $0.084729 (ESTIMATE, local and actually
free), the probe $0.001876 (ESTIMATE), and the OpenRouter smoke $0.000212 —
the only real money this run spent, and the only non-estimated cost figure it
produced.

## Cumulative: v1 → v1.3

Built only from files in this repository: `docs/spec/`,
`docs/reports/report-v1*.md`, `docs/llm-usage.md`.

### (a) Per version

| version | spec (REQ ids, size) | delivered | executor model | tests after the run | gates | review findings / fixed | prompts |
|---|---|---|---|---|---|---|---|
| **v1** | 82 ids, 1 477 lines / 77 KB | Docker sandbox for `exec`, the fetch tool with an allowlist, secret registration and redaction, storage schema v2 with summaries, `--selftest-live` | claude-opus-5 | 203 | 5/5 green | 9 found / 9 fixed (1 🔴, 4 🟡, 4 🟢) | 2 |
| **v1.1** | 42 ids, 987 lines / 60 KB | closes the v1 security audit: secret-truncation headroom, sandbox quota accounting, orphaned-container reap, resolv-file hardening, plus a mutation pass that found 4 test-suite defects | claude-sonnet-5 | 251 | 5/5 green | 5 found / 2 fixed; 3 recorded without action (1 a gap in the spec's own enumeration, 2 spec-blessed) | 2 |
| **v1.2** | 40 ids, 1 221 lines / 74 KB | minted tool-call ids, tri-state sandbox quota scanning, three-layer SSRF-resistant fetch allowlist, hardened resolv creation, ownership-aware reap, audit-hook redaction, and `devtools/mutation_check.py` as a standing gate | claude-sonnet-5 | 326 | 6 gates; 1–4 and 6 green, gate 5 non-zero overall under the v1.2 LM Studio exception | 11 found / 9 fixed; 1 accepted as a documented risk, 1 judged not a defect | 2 |
| **v1.3** | 97 ids, 2 382 lines / 157 KB | observability layer, pricing module, benchmark harness and dashboard, the token audit, and six optimizations O1–O6 | claude-opus-5 | 719 | 6/6 green at C1 and C3; C4 under the §13.1 two-pass procedure | 22 found across two reviews (stage A 2 🔴 / 3 🟡 / 6 🟢; stage C 1 🔴 / 4 🟡 / 6 🟢); one fix round per review, in the same stage's commit; one stage-A finding deferred by the spec to stage C and closed there | 19 |

*REQ counting method:* unique requirement ids declared in bold
(`**REQ-…**`) in each spec file, counted by `grep`; the specs state no count of
their own. v1.3's 97 includes the **6 `REQ-V13-NG-*` non-goals** (91 ids carry
a MUST/SHOULD modality). Sizes are `wc -l` / `wc -c` of the spec file.

### (b) Per version — tokens and cost

Copied **verbatim** from the `Σ` rows of `docs/llm-usage.md`, including
`unknown` and `not computed` cells. Nothing here is re-estimated or
back-filled.

| version | Σ row | tokens | cost |
|---|---|---|---|
| **v1** | Σ (rows 15–24, one continuous session + the review subagent) | in 35.51M (280 uncached + 692k cache-write + 34.82M cache-read), out 243.3k — measured from the local session transcripts | ≈$27.82 (estimate at public API prices; actual billing: flat-rate subscription) |
| **v1.1** | Σ (rows 25–26, one `go` run) | 82,182,018 (row 25) + 158,889 aggregate (row 26) | ≈$19.92 + unknown (row 26) |
| **v1.2** | Σ (rows 27–28, one `go` run) | not computed | ≈$33.11 + unknown (row 28) |
| **v1.3** | Σ (rows 30–31, one `go` run) | unknown | unknown |

**Total over the computed cells only — a lower bound:**
`$27.82 + $19.92 + $33.11 = $80.85` **(ESTIMATE, lower bound)**. It excludes
the v1.1 and v1.2 review-subagent cells (`unknown`), the whole v1.3 run
(`unknown`), and the spec-authoring rows 1–2, 14 and 29, which are recorded
without a cost. It also excludes the v0 run's ≈$12.60: this section covers
v1 → v1.3, and there is no `report-v0`.

**No token lower bound is given.** The four Σ token cells are not additive:
v1's is a split (`in … / out …`), v1.1's is a single combined figure with a
second, differently-shaped aggregate beside it, v1.2's is `not computed` and
v1.3's is `unknown`. Adding them would produce a number in no consistent unit.

Where a cell is not computed, the measured value is recorded by the maintainer
in the lab ledger `economics.md`, outside this repository; this table copies
whatever `docs/llm-usage.md` says and never reconstructs it.
