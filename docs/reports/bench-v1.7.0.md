# Benchmark report — baseline-v1.6.0 vs cand-v170-by-purpose-tool

## Meta

| field | baseline | candidate |
|---|---|---|
| tag | baseline-v1.6.0 | cand-v170-by-purpose-tool |
| started_at | 2026-09-06T15:09:00Z | 2026-09-07T17:11:01Z |
| finished_at | 2026-09-06T16:43:33Z | 2026-09-07T18:27:51Z |
| git_commit | ca9c656d0e3f38fa22ecb5fff3a6173fc9173fa7 | 7f1b77ec3531016691efe8545e3ded4c8c19d1f6 |
| provider | lmstudio | lmstudio |
| model | qwen/qwen3.8-27b | qwen/qwen3.8-27b |
| context_length | 42496 | 42496 |
| repeats | 3 | 3 |
| timeout_s | 1800.0 | 1800.0 |
| scenarios_sha256 | f2b6c41c344b537fd370e839669fe2274d3b01810a5c450083a6dc399b391972 | f2b6c41c344b537fd370e839669fe2274d3b01810a5c450083a6dc399b391972 |
| skipped_scenarios | [] | [] |
| constants | {"CONTEXT_WINDOW_MESSAGES": 30, "EXEC_MAX_STREAM_BYTES": 4096, "FETCH_MAX_BYTES": 65536, "HTTP_ATTEMPT_LIMIT": 9, "REQUEST_DEFAULTS": {"stream": false, "temperature": 0, "tool_choice": "auto"}, "ROUND_LIMIT": 8, "TOOL_EXECUTION_LIMIT": 12, "TOOL_ROUND_LIMIT": 7} | {"CONTEXT_WINDOW_MESSAGES": 30, "EXEC_MAX_STREAM_BYTES": 4096, "FETCH_MAX_BYTES": 65536, "HTTP_ATTEMPT_LIMIT": 9, "REQUEST_DEFAULTS": {"stream": false, "temperature": 0, "tool_choice": "auto"}, "ROUND_LIMIT": 8, "TOOL_EXECUTION_LIMIT": 12, "TOOL_ROUND_LIMIT": 7} |
| config_sha256 | 1f32efc222f526a5a911f199f0c06e96f9f24ba81309c96b770dd8cd45f7eff1 | 1f32efc222f526a5a911f199f0c06e96f9f24ba81309c96b770dd8cd45f7eff1 |
| only | n/a | n/a |
| lmstudio_version | Bionic v1.1.1 | Bionic v1.1.1 |
| served_model_id | qwen/qwen3.8-27b | qwen/qwen3.8-27b |
| lmstudio_context_length | 42496 | 42496 |
| generation_settings | {"agent": {"max_tokens": 4096, "stream": false, "temperature": 0, "tool_choice": "auto"}, "provider_defaults": ["seed", "stop", "top_p"], "summary_initial": {"max_tokens": 512, "stream": false, "temperature": 0}, "summary_retry": {"max_tokens": 1536, "stream": false, "temperature": 0}} | {"agent": {"max_tokens": 4096, "stream": false, "temperature": 0, "tool_choice": "auto"}, "provider_defaults": ["seed", "stop", "top_p"], "summary_initial": {"max_tokens": 512, "stream": false, "temperature": 0}, "summary_retry": {"max_tokens": 1536, "stream": false, "temperature": 0}} |
| prompt_tools_sha256 | 748fa855c27a583a9ded6a1ba62b49158786a39bc7ccecef96be7052de6500e3 | 748fa855c27a583a9ded6a1ba62b49158786a39bc7ccecef96be7052de6500e3 |
| obs_capture_content | false | false |
| prefix_tokens | 842 | 842 |
| env_flags.HISTORY_TOOL_STUB | on | on |
| env_flags.EXEC_OUTPUT_DEFAULT_CHARS | 1500 | 1500 |
| env_flags.FETCH_INLINE_DEFAULT_CHARS | 5000 | 5000 |
| env_flags.LLM_REASONING | n/a | n/a |
| env_flags.LLM_SUMMARY_MODEL |  |  |
| env_flags.LLM_FAILOVER | off | off |
| env_flags.LLM_MAX_TOKENS | 4096 | 4096 |
| env_flags.LLM_REASONING_POLICY | n/a | by-purpose |
| env_flags.LLM_REASONING_ON_PURPOSES | n/a | ["tool-round"] |
| pricing.basis | reference:qwen/qwen3.8-27b | reference:qwen/qwen3.8-27b |
| pricing.model | qwen/qwen3.8-27b | qwen/qwen3.8-27b |
| pricing.input_usd_per_mtok | 0.42 | 0.42 |
| pricing.output_usd_per_mtok | 3 | 3 |
| pricing.cached_input_usd_per_mtok | 0.085 | 0.085 |
| pricing.fetched_at | 2026-09-06T15:09:00Z | 2026-09-07T17:11:01Z |

## Per scenario

| scenario | file | success | prompt_tokens | completion_tokens | cached_tokens | reasoning_tokens | resent_tokens | new_tokens | tool_calls | tool_output_tokens_est | latency_ms | wall_ms | cost_usd | calls | failed_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | baseline | 3/3 | 876 | 290 | 0 | 217 | 0 | 876 | 0 | 0 | 30316 | 30624 | 0.001238 | 1 | 0 |
| S01 | candidate | 3/3 | 876 | 689 | 0 | 618 | 0 | 876 | 0 | 0 | 68256 | 68575 | 0.002435 | 1 | 0 |
| S01 | Δ |  | 0 (+0.0%) | 399 (+137.6%) | 0 (n/a) | 401 (+184.8%) | 0 (n/a) | 0 (+0.0%) | 0 (n/a) | 0 (n/a) | 37940 (+125.1%) | 37951 (+123.9%) | 0.001197 (+96.7%) | 0 (+0.0%) | 0 (n/a) |
| S02 | baseline | 3/3 | 1904 | 142 | 0 | 90 | 886 | 1018 | 1 | 75 | 22600 | 23195 | 0.001226 | 2 | 0 |
| S02 | candidate | 3/3 | 1904 | 142 | 0 | 90 | 886 | 1018 | 1 | 75 | 23030 | 23601 | 0.001226 | 2 | 0 |
| S02 | Δ |  | 0 (+0.0%) | 0 (+0.0%) | 0 (n/a) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 430 (+1.9%) | 406 (+1.8%) | 0 (+0.0%) | 0 (+0.0%) | 0 (n/a) |
| S03 | baseline | 3/3 | 1952 | 699 | 0 | 615 | 899 | 1053 | 1 | 75 | 75348 | 75950 | 0.002916 | 2 | 0 |
| S03 | candidate | 3/3 | 1949 | 484 | 0 | 400 | 899 | 1050 | 1 | 75 | 57162 | 57768 | 0.002271 | 2 | 0 |
| S03 | Δ |  | -3 (-0.2%) | -215 (-30.8%) | 0 (n/a) | -215 (-35.0%) | 0 (+0.0%) | -3 (-0.3%) | 0 (+0.0%) | 0 (+0.0%) | -18186 (-24.1%) | -18182 (-23.9%) | -0.000645 (-22.1%) | 0 (+0.0%) | 0 (n/a) |
| S04 | baseline | 3/3 | 3225 | 489 | 0 | 383 | 1974 | 1251 | 2 | 291 | 62851 | 63669 | 0.002821 | 3 | 0 |
| S04 | candidate | 3/3 | 3225 | 433 | 0 | 327 | 1974 | 1251 | 2 | 291 | 58841 | 59667 | 0.002654 | 3 | 0 |
| S04 | Δ |  | 0 (+0.0%) | -56 (-11.5%) | 0 (n/a) | -56 (-14.6%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | -4010 (-6.4%) | -4002 (-6.3%) | -0.000168 (-6.0%) | 0 (+0.0%) | 0 (n/a) |
| S05 | baseline | 3/3 | 6099 | 447 | 0 | 345 | 917 | 5182 | 1 | 1792 | 140684 | 141304 | 0.003819 | 2 | 0 |
| S05 | candidate | 3/3 | 6099 | 447 | 0 | 345 | 917 | 5182 | 1 | 1792 | 155805 | 156394 | 0.003903 | 2 | 0 |
| S05 | Δ |  | 0 (+0.0%) | 0 (+0.0%) | 0 (n/a) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 15121 (+10.7%) | 15090 (+10.7%) | 0.000084 (+2.2%) | 0 (+0.0%) | 0 (n/a) |
| S06 | baseline | 3/3 | 2027 | 860 | 0 | 732 | 905 | 1122 | 1 | 128 | 92570 | 93340 | 0.003431 | 2 | 0 |
| S06 | candidate | 3/3 | 2027 | 787 | 0 | 661 | 905 | 1122 | 1 | 128 | 86502 | 87318 | 0.003211 | 2 | 0 |
| S06 | Δ |  | 0 (+0.0%) | -73 (-8.5%) | 0 (n/a) | -71 (-9.7%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | -6068 (-6.6%) | -6022 (-6.5%) | -0.00022 (-6.4%) | 0 (+0.0%) | 0 (n/a) |
| S07 | baseline | 3/3 | 3436 | 420 | 0 | 128 | 1934 | 1502 | 4 | 468 | 60081 | 60991 | 0.002703 | 3 | 0 |
| S07 | candidate | 3/3 | 3435 | 419 | 0 | 134 | 1934 | 1501 | 4 | 468 | 60930 | 61965 | 0.0027 | 3 | 0 |
| S07 | Δ |  | -1 (-0.0%) | -1 (-0.2%) | 0 (n/a) | 6 (+4.7%) | 0 (+0.0%) | -1 (-0.1%) | 0 (+0.0%) | 0 (+0.0%) | 849 (+1.4%) | 974 (+1.6%) | -0.000003 (-0.1%) | 0 (+0.0%) | 0 (n/a) |
| S08 | baseline | 3/3 | 3451 | 257 | 0 | 179 | 2105 | 1346 | 2 | 394 | 43529 | 44011 | 0.00222 | 3 | 0 |
| S08 | candidate | 3/3 | 3451 | 257 | 0 | 179 | 2105 | 1346 | 2 | 394 | 46144 | 46572 | 0.00222 | 3 | 0 |
| S08 | Δ |  | 0 (+0.0%) | 0 (+0.0%) | 0 (n/a) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 2615 (+6.0%) | 2561 (+5.8%) | 0 (+0.0%) | 0 (+0.0%) | 0 (n/a) |
| S09 | baseline | 3/3 | 9606 | 943 | 0 | 625 | 7872 | 1734 | 4 | 372 | 136796 | 138401 | 0.006864 | 7 | 0 |
| S09 | candidate | 3/3 | 5939 | 778 | 0 | 558 | 4533 | 1406 | 2 | 167 | 111568 | 112517 | 0.004828 | 5 | 0 |
| S09 | Δ |  | -3667 (-38.2%) | -165 (-17.5%) | 0 (n/a) | -67 (-10.7%) | -3339 (-42.4%) | -328 (-18.9%) | -2 (-50.0%) | -205 (-55.1%) | -25228 (-18.4%) | -25884 (-18.7%) | -0.002035 (-29.7%) | -2 (-28.6%) | 0 (n/a) |
| S10 | baseline | 3/3 | 880 | 147 | 0 | 61 | 0 | 880 | 0 | 0 | 16907 | 17205 | 0.000811 | 1 | 0 |
| S10 | candidate | 3/3 | 880 | 145 | 0 | 58 | 0 | 880 | 0 | 0 | 17151 | 17432 | 0.000805 | 1 | 0 |
| S10 | Δ |  | 0 (+0.0%) | -2 (-1.4%) | 0 (n/a) | -3 (-4.9%) | 0 (n/a) | 0 (+0.0%) | 0 (n/a) | 0 (n/a) | 244 (+1.4%) | 227 (+1.3%) | -0.000006 (-0.7%) | 0 (+0.0%) | 0 (n/a) |
| S11 | baseline | 3/3 | 891 | 173 | 0 | 158 | 0 | 891 | 0 | 0 | 19287 | 19606 | 0.000893 | 1 | 0 |
| S11 | candidate | 3/3 | 891 | 173 | 0 | 158 | 0 | 891 | 0 | 0 | 19538 | 19853 | 0.000893 | 1 | 0 |
| S11 | Δ |  | 0 (+0.0%) | 0 (+0.0%) | 0 (n/a) | 0 (+0.0%) | 0 (n/a) | 0 (+0.0%) | 0 (n/a) | 0 (n/a) | 251 (+1.3%) | 247 (+1.3%) | 0 (+0.0%) | 0 (+0.0%) | 0 (n/a) |
| S12 | baseline | 3/3 | 2082 | 813 | 0 | 645 | 1135 | 947 | 0 | 0 | 88948 | 89255 | 0.003313 | 3 | 0 |
| S12 | candidate | 3/3 | 2086 | 397 | 0 | 263 | 1139 | 947 | 0 | 0 | 51550 | 51844 | 0.002067 | 3 | 0 |
| S12 | Δ |  | 4 (+0.2%) | -416 (-51.2%) | 0 (n/a) | -382 (-59.2%) | 4 (+0.4%) | 0 (+0.0%) | 0 (n/a) | 0 (n/a) | -37398 (-42.0%) | -37411 (-41.9%) | -0.001246 (-37.6%) | 0 (+0.0%) | 0 (n/a) |
| S13 | baseline | 3/3 | 7902 | 1051 | 0 | 763 | 6224 | 1678 | 5 | 470 | 135800 | 137577 | 0.00647 | 6 | 0 |
| S13 | candidate | 3/3 | 7902 | 904 | 0 | 620 | 6221 | 1678 | 5 | 470 | 123542 | 125528 | 0.006021 | 6 | 0 |
| S13 | Δ |  | 0 (+0.0%) | -147 (-14.0%) | 0 (n/a) | -143 (-18.7%) | -3 (-0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | -12258 (-9.0%) | -12049 (-8.8%) | -0.000449 (-6.9%) | 0 (+0.0%) | 0 (n/a) |
| S14 | baseline | 3/3 | 2120 | 309 | 0 | 219 | 924 | 1196 | 2 | 181 | 43125 | 44147 | 0.001817 | 2 | 0 |
| S14 | candidate | 3/3 | 2120 | 311 | 0 | 221 | 924 | 1196 | 2 | 181 | 43813 | 44948 | 0.001823 | 2 | 0 |
| S14 | Δ |  | 0 (+0.0%) | 2 (+0.6%) | 0 (n/a) | 2 (+0.9%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 688 (+1.6%) | 801 (+1.8%) | 0.000006 (+0.3%) | 0 (+0.0%) | 0 (n/a) |
| S15 | baseline | 3/3 | 5857 | 3385 | 0 | 3269 | 912 | 4945 | 1 | 1706 | 392713 | 393318 | 0.012615 | 2 | 0 |
| S15 | candidate | 3/3 | 3414 | 2406 | 0 | 2294 | 912 | 2502 | 1 | 700 | 332901 | 333500 | 0.009678 | 2 | 0 |
| S15 | Δ |  | -2443 (-41.7%) | -979 (-28.9%) | 0 (n/a) | -975 (-29.8%) | 0 (+0.0%) | -2443 (-49.4%) | 0 (+0.0%) | -1006 (-59.0%) | -59812 (-15.2%) | -59818 (-15.2%) | -0.002937 (-23.3%) | 0 (+0.0%) | 0 (n/a) |
| S16 | baseline | 3/3 | 3154 | 139 | 0 | 67 | 1960 | 1194 | 2 | 242 | 28206 | 28732 | 0.001742 | 3 | 0 |
| S16 | candidate | 3/3 | 3154 | 139 | 0 | 67 | 1960 | 1194 | 2 | 242 | 28562 | 29153 | 0.001742 | 3 | 0 |
| S16 | Δ |  | 0 (+0.0%) | 0 (+0.0%) | 0 (n/a) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 356 (+1.3%) | 421 (+1.5%) | 0 (+0.0%) | 0 (+0.0%) | 0 (n/a) |
| S17 | baseline | 3/3 | 3148 | 835 | 0 | 735 | 1960 | 1188 | 2 | 147 | 92805 | 93478 | 0.003827 | 3 | 0 |
| S17 | candidate | 3/3 | 3148 | 404 | 0 | 304 | 1960 | 1188 | 2 | 147 | 53587 | 54343 | 0.002534 | 3 | 0 |
| S17 | Δ |  | 0 (+0.0%) | -431 (-51.6%) | 0 (n/a) | -431 (-58.6%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | 0 (+0.0%) | -39218 (-42.3%) | -39135 (-41.9%) | -0.001293 (-33.8%) | 0 (+0.0%) | 0 (n/a) |
| S18 | baseline | 2/3 | 3334 | 1740 | 0 | 1592 | 2365 | 969 | 0 | 0 | 235687 | 236075 | 0.00662 | 5 | 1 |
| S18 | candidate | 3/3 | 3065 | 390 | 0 | 246 | 2096 | 969 | 0 | 0 | 50211 | 50631 | 0.002457 | 4 | 0 |
| S18 | Δ |  | -269 (-8.1%) | -1350 (-77.6%) | 0 (n/a) | -1346 (-84.5%) | -269 (-11.4%) | 0 (+0.0%) | 0 (n/a) | 0 (n/a) | -185476 (-78.7%) | -185444 (-78.6%) | -0.004163 (-62.9%) | -1 (-20.0%) | -1 (-100.0%) |

## Totals

| metric | baseline | candidate | Δ | Δ% |
|---|---|---|---|---|
| calls | 153 | 146 | -7 | -4.6% |
| failed_calls | 4 | 0 | -4 | -100.0% |
| prompt_tokens | 179210 | 172870 | -6340 | -3.5% |
| completion_tokens | 36836 | 33095 | -3741 | -10.2% |
| cached_tokens | 0 | 0 | 0 | n/a |
| reasoning_tokens | 29915 | 26231 | -3684 | -12.3% |
| tool_calls | 84 | 80 | -4 | -4.8% |
| tool_output_tokens_est | 16407 | 16683 | 276 | +1.7% |
| latency_ms | 5514362 | 4511054 | -1003308 | -18.2% |
| cost_usd | 0.185776 | 0.17189 | -0.013886 | -7.5% |
| resent_tokens | 98640 | 91374 | -7266 | -7.4% |
| new_tokens | 80570 | 81496 | 926 | +1.1% |
| wall_ms | 5552247 | 4548858 | -1003389 | -18.1% |
| success_rate | 0.981481 | 1 | 0.018519 | +1.9% |
| cost_per_success | 0.003505 | 0.003183 | -0.000322 | -9.2% |
| tokens_per_success | 4076.3 | 3814.2 | -262.172956 | -6.4% |
| resent_share | 0.550416 | 0.528571 | -0.021845 | -4.0% |
| cache_hit_rate | n/a | n/a | n/a | n/a |
| avg_per_task.tokens | 4000.9 | 3814.2 | -186.685185 | -4.7% |
| avg_per_task.rounds | 2.666667 | 2.592593 | -0.074074 | -2.8% |
| avg_per_task.tool_calls | 1.555556 | 1.481481 | -0.074074 | -4.8% |
| avg_per_task.latency_ms | 102117.8 | 83538.0 | -18579.8 | -18.2% |
| prefix_share | 0.718855 | 0.711124 | -0.007731 | -1.1% |

## Totals by purpose

| purpose | metric | baseline | candidate |
|---|---|---|---|
| agent | calls | 144 | 140 |
| agent | prompt_tokens | 177078 | 171258 |
| agent | completion_tokens | 32135 | 32621 |
| summary | calls | 9 | 6 |
| summary | prompt_tokens | 2132 | 1612 |
| summary | completion_tokens | 4701 | 474 |

## Audit

| question | baseline | candidate |
|---|---|---|
| most expensive tool (output tokens) | exec (13542 tokens, 66 calls) | exec (13818 tokens, 62 calls) |
| most expensive turn/round | S05-1 turn 3 round 2: 5182 prompt tokens | S05-1 turn 3 round 2: 5182 prompt tokens |
| fastest-growing context category | tool (+1130.5 chars/run) | tool (+1149.8 chars/run) |
| re-sent share | 0.550416 | 0.528571 |

## Reasoning

### baseline

- reasoning observed: yes, max reasoning_tokens: 3414, max reasoning_chars: 11363, Σ reasoning_tokens: 29915, reasoning share: 0.8121
- tool-exposed calls: calls: 144, reasoning observed: yes, max reasoning_tokens: 3414, max reasoning_chars: 11363, Σ reasoning_tokens: 25708, reasoning share: 0.8000
- tools-withheld calls: calls: 5, reasoning observed: yes, max reasoning_tokens: 759, max reasoning_chars: 3056, Σ reasoning_tokens: 4207, reasoning share: 0.8949

### candidate

- reasoning observed: yes, max reasoning_tokens: 3696, max reasoning_chars: 11909, Σ reasoning_tokens: 26231, reasoning share: 0.7926
- tool-exposed calls: calls: 140, reasoning observed: yes, max reasoning_tokens: 3696, max reasoning_chars: 11909, Σ reasoning_tokens: 26231, reasoning share: 0.8041
- tools-withheld calls: calls: 6, reasoning observed: no, max reasoning_tokens: 0, max reasoning_chars: 0, Σ reasoning_tokens: 0, reasoning share: 0.0000


## Latency

| scope | baseline | candidate |
|---|---|---|
| median latency_ms per call | 17289 | 17029.0 |
| median latency_ms (agent) | 16720.5 | 17763.0 |
| median latency_ms (summary) | 53629 | 12720.5 |

## Failures

### baseline

| scenario | repeat | failure | checks | answers |
|---|---|---|---|---|
| S18 | 3 | checks | summary_exists: 0 summary row(s), no goal | 

Принято: проект Vega, дедлайн 3 ноября. Учту в рамках этого разговора, но постоянного хранилища у меня нет — напомни, если понадобится позже. ⏎ 

Vega ⏎ 

3 ноября 2026 |

### candidate

none


## Verdict

- metric: cost per successful task
- price snapshot (baseline): qwen/qwen3.8-27b as of 2026-09-06T15:09:00Z
- B_plain: $0.003505 (failed_B 4)
- C_plain: $0.003183 (failed_C 0)
- C_conservative: $0.003183
- gate threshold (0.70 x B_plain): $0.002454
- success rate: 0.9815 → 1.0000 (+1.9 pp; the assignment's headline is 2 pp, but at 54 runs one flipped run is already 1.9 pp, so the candidate may lose no run net)
- cost gate: FAIL
- quality gate: pass
- verdict: **FAIL**
