# Benchmark report — baseline vs optimized

## Meta

| field | baseline | candidate |
|---|---|---|
| tag | baseline | optimized |
| started_at | 2026-09-02T16:33:54Z | 2026-09-02T21:09:18Z |
| finished_at | 2026-09-02T17:34:02Z | 2026-09-02T21:47:39Z |
| git_commit | 69ebc7575550731b981e6799f55dfd5eaaec8317 | c11f590def31912af4b9460d1b122a59895bcaab |
| provider | lmstudio | lmstudio |
| model | qwen/qwen3.8-27b | qwen/qwen3.8-27b |
| context_length | 42496 | 42496 |
| repeats | 3 | 3 |
| timeout_s | 1800.0 | 1800.0 |
| scenarios_sha256 | 586ed397cae5caef1ef464d41addde3963803e27b559443bbea5e31e5a0d0a48 | 586ed397cae5caef1ef464d41addde3963803e27b559443bbea5e31e5a0d0a48 |
| skipped_scenarios | [] | [] |
| constants | {"CONTEXT_WINDOW_MESSAGES": 30, "EXEC_MAX_STREAM_BYTES": 4096, "FETCH_MAX_BYTES": 65536, "HTTP_ATTEMPT_LIMIT": 9, "REQUEST_DEFAULTS": {"stream": false, "temperature": 0, "tool_choice": "auto"}, "ROUND_LIMIT": 8, "TOOL_EXECUTION_LIMIT": 12, "TOOL_ROUND_LIMIT": 7} | {"CONTEXT_WINDOW_MESSAGES": 30, "EXEC_MAX_STREAM_BYTES": 4096, "FETCH_MAX_BYTES": 65536, "HTTP_ATTEMPT_LIMIT": 9, "REQUEST_DEFAULTS": {"stream": false, "temperature": 0, "tool_choice": "auto"}, "ROUND_LIMIT": 8, "TOOL_EXECUTION_LIMIT": 12, "TOOL_ROUND_LIMIT": 7} |
| config_sha256 | 754a468695063016a03f79cc58d01230daa2d46fd51f616908dbe6a11d54c91e | 754a468695063016a03f79cc58d01230daa2d46fd51f616908dbe6a11d54c91e |
| only | n/a | n/a |
| prefix_tokens | 1126 | 842 |
| env_flags.HISTORY_TOOL_STUB | n/a | on |
| env_flags.EXEC_OUTPUT_DEFAULT_CHARS | n/a | 1500 |
| env_flags.FETCH_INLINE_DEFAULT_CHARS | n/a | 5000 |
| env_flags.LLM_REASONING | n/a | n/a |
| env_flags.LLM_SUMMARY_MODEL | n/a |  |
| env_flags.LLM_FAILOVER | off | off |
| env_flags.LLM_MAX_TOKENS | 2048 | 2048 |
| pricing.basis | reference:qwen/qwen3.8-27b | reference:qwen/qwen3.8-27b |
| pricing.model | qwen/qwen3.8-27b | qwen/qwen3.8-27b |
| pricing.input_usd_per_mtok | 0.425 | 0.425 |
| pricing.output_usd_per_mtok | 2.55 | 2.55 |
| pricing.cached_input_usd_per_mtok | 0.085 | 0.085 |
| pricing.fetched_at | 2026-09-02T16:33:54Z | 2026-09-02T21:09:18Z |

## Per scenario

| scenario | file | success | prompt_tokens | completion_tokens | cached_tokens | reasoning_tokens | resent_tokens | new_tokens | tool_calls | tool_output_tokens_est | latency_ms | wall_ms | cost_usd | calls | failed_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | baseline | 3/3 | 1138 | 214 | 0 | 120 | 0 | 1138 | 0 | 0 | 45076 | 45372 | 0.001029 | 1 | 0 |
| S01 | candidate | 1/3 | 876 | 296 | 0 | 219 | 0 | 876 | 0 | 0 | 30636 | 31040 | 0.001127 | 1 | 0 |
| S01 | Δ |  | -262 (-23.0%) | 82 (+38.3%) | 0 (n/a) | 99 (+82.5%) | 0 (n/a) | -262 (-23.0%) | 0 (n/a) | 0 (n/a) | -14440 (-32.0%) | -14332 (-31.6%) | 0.000098 (+9.5%) | 0 (+0.0%) | 0 (n/a) |
| S02 | baseline | 3/3 | 2406 | 96 | 0 | 44 | 1148 | 1258 | 1 | 52 | 40574 | 41165 | 0.001267 | 2 | 0 |
| S02 | candidate | 3/3 | 1904 | 142 | 0 | 90 | 886 | 1018 | 1 | 75 | 23487 | 24335 | 0.001171 | 2 | 0 |
| S02 | Δ |  | -502 (-20.9%) | 46 (+47.9%) | 0 (n/a) | 46 (+104.5%) | -262 (-22.8%) | -240 (-19.1%) | 0 (+0.0%) | 23 (+44.2%) | -17087 (-42.1%) | -16830 (-40.9%) | -0.000096 (-7.6%) | 0 (+0.0%) | 0 (n/a) |
| S03 | baseline | 3/3 | 2492 | 765 | 0 | 644 | 1161 | 1331 | 1 | 61 | 118935 | 119534 | 0.003407 | 3 | 0 |
| S03 | candidate | 3/3 | 1952 | 540 | 0 | 452 | 899 | 1053 | 1 | 75 | 63827 | 64468 | 0.002207 | 2 | 0 |
| S03 | Δ |  | -540 (-21.7%) | -225 (-29.4%) | 0 (n/a) | -192 (-29.8%) | -262 (-22.6%) | -278 (-20.9%) | 0 (+0.0%) | 14 (+23.0%) | -55108 (-46.3%) | -55066 (-46.1%) | -0.0012 (-35.2%) | -1 (-33.3%) | 0 (n/a) |
| S04 | baseline | 3/3 | 2474 | 329 | 0 | 219 | 1161 | 1313 | 1 | 104 | 64017 | 64712 | 0.00189 | 2 | 0 |
| S04 | candidate | 3/3 | 3225 | 410 | 0 | 304 | 1974 | 1251 | 2 | 291 | 56525 | 57344 | 0.002416 | 3 | 0 |
| S04 | Δ |  | 751 (+30.4%) | 81 (+24.6%) | 0 (n/a) | 85 (+38.8%) | 813 (+70.0%) | -62 (-4.7%) | 1 (+100.0%) | 187 (+179.8%) | -7492 (-11.7%) | -7368 (-11.4%) | 0.000526 (+27.8%) | 1 (+50.0%) | 0 (n/a) |
| S05 | baseline | 3/3 | 6581 | 527 | 0 | 439 | 1179 | 5402 | 1 | 1767 | 171820 | 172439 | 0.004141 | 2 | 0 |
| S05 | candidate | 3/3 | 6099 | 450 | 0 | 351 | 917 | 5182 | 1 | 1792 | 141271 | 142022 | 0.003661 | 2 | 0 |
| S05 | Δ |  | -482 (-7.3%) | -77 (-14.6%) | 0 (n/a) | -88 (-20.0%) | -262 (-22.2%) | -220 (-4.1%) | 0 (+0.0%) | 25 (+1.4%) | -30549 (-17.8%) | -30417 (-17.6%) | -0.00048 (-11.6%) | 0 (+0.0%) | 0 (n/a) |
| S06 | baseline | 3/3 | 3298 | 545 | 0 | 437 | 1167 | 2131 | 1 | 1361 | 101425 | 102094 | 0.002791 | 2 | 0 |
| S06 | candidate | 3/3 | 2027 | 665 | 0 | 536 | 905 | 1122 | 1 | 128 | 75723 | 76769 | 0.002557 | 2 | 0 |
| S06 | Δ |  | -1271 (-38.5%) | 120 (+22.0%) | 0 (n/a) | 99 (+22.7%) | -262 (-22.5%) | -1009 (-47.3%) | 0 (+0.0%) | -1233 (-90.6%) | -25702 (-25.3%) | -25325 (-24.8%) | -0.000234 (-8.4%) | 0 (+0.0%) | 0 (n/a) |
| S07 | baseline | 3/3 | 4151 | 459 | 0 | 158 | 2458 | 1693 | 4 | 397 | 85196 | 86192 | 0.002935 | 3 | 0 |
| S07 | candidate | 3/3 | 3437 | 413 | 0 | 128 | 1934 | 1503 | 4 | 468 | 59720 | 61313 | 0.002513 | 3 | 0 |
| S07 | Δ |  | -714 (-17.2%) | -46 (-10.0%) | 0 (n/a) | -30 (-19.0%) | -524 (-21.3%) | -190 (-11.2%) | 0 (+0.0%) | 71 (+17.9%) | -25476 (-29.9%) | -24879 (-28.9%) | -0.000422 (-14.4%) | 0 (+0.0%) | 0 (n/a) |
| S08 | baseline | 3/3 | 4201 | 254 | 0 | 176 | 2629 | 1572 | 2 | 368 | 67283 | 67698 | 0.002433 | 3 | 0 |
| S08 | candidate | 3/3 | 3451 | 259 | 0 | 179 | 2105 | 1346 | 2 | 394 | 46283 | 46756 | 0.002127 | 3 | 0 |
| S08 | Δ |  | -750 (-17.9%) | 5 (+2.0%) | 0 (n/a) | 3 (+1.7%) | -524 (-19.9%) | -226 (-14.4%) | 0 (+0.0%) | 26 (+7.1%) | -21000 (-31.2%) | -20942 (-30.9%) | -0.000306 (-12.6%) | 0 (+0.0%) | 0 (n/a) |
| S09 | baseline | 3/3 | 7124 | 814 | 0 | 520 | 5490 | 1634 | 2 | 120 | 186444 | 187384 | 0.00514 | 5 | 0 |
| S09 | candidate | 3/3 | 9606 | 1012 | 0 | 694 | 7872 | 1734 | 4 | 372 | 145708 | 147463 | 0.006663 | 7 | 0 |
| S09 | Δ |  | 2482 (+34.8%) | 198 (+24.3%) | 0 (n/a) | 174 (+33.5%) | 2382 (+43.4%) | 100 (+6.1%) | 2 (+100.0%) | 252 (+210.0%) | -40736 (-21.8%) | -39921 (-21.3%) | 0.001523 (+29.6%) | 2 (+40.0%) | 0 (n/a) |
| S10 | baseline | 3/3 | 1142 | 323 | 0 | 236 | 0 | 1142 | 0 | 0 | 55182 | 55469 | 0.001309 | 1 | 0 |
| S10 | candidate | 3/3 | 880 | 136 | 0 | 58 | 0 | 880 | 0 | 0 | 16201 | 16506 | 0.000721 | 1 | 0 |
| S10 | Δ |  | -262 (-22.9%) | -187 (-57.9%) | 0 (n/a) | -178 (-75.4%) | 0 (n/a) | -262 (-22.9%) | 0 (n/a) | 0 (n/a) | -38981 (-70.6%) | -38963 (-70.2%) | -0.000588 (-44.9%) | 0 (+0.0%) | 0 (n/a) |
| S11 | baseline | 3/3 | 1153 | 97 | 0 | 82 | 0 | 1153 | 0 | 0 | 35041 | 35333 | 0.000737 | 1 | 0 |
| S11 | candidate | 3/3 | 891 | 173 | 0 | 158 | 0 | 891 | 0 | 0 | 19299 | 19649 | 0.00082 | 1 | 0 |
| S11 | Δ |  | -262 (-22.7%) | 76 (+78.4%) | 0 (n/a) | 76 (+92.7%) | 0 (n/a) | -262 (-22.7%) | 0 (n/a) | 0 (n/a) | -15742 (-44.9%) | -15684 (-44.4%) | 0.000082 (+11.2%) | 0 (+0.0%) | 0 (n/a) |
| S12 | baseline | 3/3 | 5703 | 1357 | 0 | 1107 | 4251 | 1452 | 2 | 120 | 203521 | 204373 | 0.005884 | 5 | 0 |
| S12 | candidate | 3/3 | 2078 | 753 | 0 | 614 | 1133 | 945 | 0 | 0 | 83756 | 85800 | 0.002803 | 3 | 0 |
| S12 | Δ |  | -3625 (-63.6%) | -604 (-44.5%) | 0 (n/a) | -493 (-44.5%) | -3118 (-73.3%) | -507 (-34.9%) | -2 (-100.0%) | -120 (-100.0%) | -119765 (-58.8%) | -118573 (-58.0%) | -0.003081 (-52.4%) | -2 (-40.0%) | 0 (n/a) |

## Totals

| metric | baseline | candidate | Δ | Δ% |
|---|---|---|---|---|
| calls | 88 | 89 | 1 | +1.1% |
| failed_calls | 1 | 0 | -1 | -100.0% |
| prompt_tokens | 126109 | 103236 | -22873 | -18.1% |
| completion_tokens | 16923 | 16021 | -902 | -5.3% |
| cached_tokens | 0 | 0 | 0 | n/a |
| reasoning_tokens | 12144 | 11680 | -464 | -3.8% |
| tool_calls | 45 | 47 | 2 | +4.4% |
| tool_output_tokens_est | 13116 | 9014 | -4102 | -31.3% |
| latency_ms | 3540575 | 2241492 | -1299083 | -36.7% |
| cost_usd | 0.09675 | 0.084729 | -0.012021 | -12.4% |
| resent_tokens | 62431 | 53947 | -8484 | -13.6% |
| new_tokens | 63678 | 49289 | -14389 | -22.6% |
| wall_ms | 3564244 | 2275011 | -1289233 | -36.2% |
| success_rate | 1 | 0.944444 | -0.055556 | -5.6% |
| cost_per_success | 0.002687 | 0.002492 | -0.000195 | -7.3% |
| tokens_per_success | 3973.1 | 3507.6 | -465.552288 | -11.7% |
| resent_share | 0.495056 | 0.52256 | 0.027504 | +5.6% |
| cache_hit_rate | n/a | n/a | n/a | n/a |
| avg_per_task.tokens | 3973.1 | 3312.7 | -660.416667 | -16.6% |
| avg_per_task.rounds | 2.333333 | 2.388889 | 0.055556 | +2.4% |
| avg_per_task.tool_calls | 1.25 | 1.305556 | 0.055556 | +4.4% |
| avg_per_task.latency_ms | 98349.3 | 62263.7 | -36085.6 | -36.7% |
| prefix_share | 0.785733 | 0.72589 | -0.059843 | -7.6% |

## Totals by purpose

| purpose | metric | baseline | candidate |
|---|---|---|---|
| agent | calls | 85 | 86 |
| agent | prompt_tokens | 124685 | 102474 |
| agent | completion_tokens | 15539 | 14617 |
| summary | calls | 3 | 3 |
| summary | prompt_tokens | 1424 | 762 |
| summary | completion_tokens | 1384 | 1404 |

## Audit

| question | baseline | candidate |
|---|---|---|
| most expensive tool (output tokens) | exec (11523 tokens, 36 calls) | exec (6854 tokens, 35 calls) |
| most expensive turn/round | S05-1 turn 3 round 2: 5402 prompt tokens | S05-1 turn 3 round 2: 5182 prompt tokens |
| fastest-growing context category | tool (+1301.4 chars/run) | tool (+925.6 chars/run) |
| re-sent share | 0.495056 | 0.52256 |

## Reasoning

### baseline

- reasoning observed: yes, max reasoning_tokens: 825, max reasoning_chars: 3265, Σ reasoning_tokens: 12144, reasoning share: 0.7176
- tool-exposed calls: calls: 84, reasoning observed: yes, max reasoning_tokens: 825, max reasoning_chars: 3265, Σ reasoning_tokens: 11081, reasoning share: 0.7131
- tools-withheld calls: calls: 3, reasoning observed: yes, max reasoning_tokens: 395, max reasoning_chars: 1721, Σ reasoning_tokens: 1063, reasoning share: 0.7681

### candidate

- reasoning observed: yes, max reasoning_tokens: 701, max reasoning_chars: 2629, Σ reasoning_tokens: 11680, reasoning share: 0.7290
- tool-exposed calls: calls: 86, reasoning observed: yes, max reasoning_tokens: 701, max reasoning_chars: 2629, Σ reasoning_tokens: 10516, reasoning share: 0.7194
- tools-withheld calls: calls: 3, reasoning observed: yes, max reasoning_tokens: 388, max reasoning_chars: 1758, Σ reasoning_tokens: 1164, reasoning share: 0.8291


## Latency

| scope | baseline | candidate |
|---|---|---|
| median latency_ms per call | 35158.0 | 18198 |
| median latency_ms (agent) | 34704 | 17536.0 |
| median latency_ms (summary) | 56975 | 49179 |

## Failures

### baseline

none

### candidate

| scenario | repeat | failure | checks | answers |
|---|---|---|---|---|
| S01 | 1 | checks | answer_regex: pattern not found | 

Привет! Я — большая языковая модель Qwen. Могу отвечать на вопросы, писать и редактировать тексты, переводить, помогать с кодом, анализировать информацию и рассуждать над сложными задачами. Также у меня есть инструменты: могу узнать погоду в любом городе и рассказать о среде, в которой работаю. Че |
| S01 | 2 | checks | answer_regex: pattern not found | 

Привет! Я — большая языковая модель Qwen. Могу отвечать на вопросы, писать и редактировать тексты, переводить, помогать с кодом, анализировать информацию и рассуждать над сложными задачами. Также у меня есть инструменты: могу узнать погоду в любом городе и рассказать о среде, в которой работаю. Че |


## Verdict

- metric: cost per successful task
- price snapshot (baseline): qwen/qwen3.8-27b as of 2026-09-02T16:33:54Z
- B_plain: $0.002687 (failed_B 1)
- C_plain: $0.002492 (failed_C 0)
- C_conservative: $0.002492
- gate threshold (0.70 x B_plain): $0.001881
- success rate: 1.0000 → 0.9444 (-5.6 pp; the assignment's headline is 2 pp, but at 36 runs one flipped run is already 2.8–3.0 pp, so the candidate may lose no run net)
- regressed scenarios: S01 3/3 → 1/3
- cost gate: FAIL
- quality gate: FAIL
- verdict: **FAIL**
