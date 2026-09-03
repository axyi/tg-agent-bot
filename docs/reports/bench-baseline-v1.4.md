# Benchmark report — baseline-v1.4

## Meta

| field | baseline |
|---|---|
| tag | baseline-v1.4 |
| started_at | 2026-09-03T11:01:29Z |
| finished_at | 2026-09-03T12:04:51Z |
| git_commit |  |
| provider | lmstudio |
| model | qwen/qwen3.8-27b |
| context_length | 42496 |
| repeats | 3 |
| timeout_s | 1800.0 |
| scenarios_sha256 | d0d9e3f658d1ad6b36d1048b98d39f3a180468c484e9c549163b8bcb4ac0aeae |
| skipped_scenarios | [] |
| constants | {"CONTEXT_WINDOW_MESSAGES": 30, "EXEC_MAX_STREAM_BYTES": 4096, "FETCH_MAX_BYTES": 65536, "HTTP_ATTEMPT_LIMIT": 9, "REQUEST_DEFAULTS": {"stream": false, "temperature": 0, "tool_choice": "auto"}, "ROUND_LIMIT": 8, "TOOL_EXECUTION_LIMIT": 12, "TOOL_ROUND_LIMIT": 7} |
| config_sha256 | 8a9cf9040f2df068fe4f7dd27d205fc1dc3174897ecfce901e7ec14b94caa5a9 |
| only | n/a |
| prefix_tokens | 1126 |
| env_flags.HISTORY_TOOL_STUB | n/a |
| env_flags.EXEC_OUTPUT_DEFAULT_CHARS | n/a |
| env_flags.FETCH_INLINE_DEFAULT_CHARS | n/a |
| env_flags.LLM_REASONING | n/a |
| env_flags.LLM_SUMMARY_MODEL | n/a |
| env_flags.LLM_FAILOVER | off |
| env_flags.LLM_MAX_TOKENS | 2048 |
| env_flags.LLM_REASONING_POLICY | n/a |
| env_flags.LLM_REASONING_ON_PURPOSES | n/a |
| pricing.basis | reference:qwen/qwen3.8-27b |
| pricing.model | qwen/qwen3.8-27b |
| pricing.input_usd_per_mtok | 0.425 |
| pricing.output_usd_per_mtok | 2.55 |
| pricing.cached_input_usd_per_mtok | 0.085 |
| pricing.fetched_at | 2026-09-03T11:01:29Z |

## Per scenario

| scenario | file | success | prompt_tokens | completion_tokens | cached_tokens | reasoning_tokens | resent_tokens | new_tokens | tool_calls | tool_output_tokens_est | latency_ms | wall_ms | cost_usd | calls | failed_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | baseline | 3/3 | 1138 | 214 | 0 | 120 | 0 | 1138 | 0 | 0 | 45848 | 46220 | 0.001029 | 1 | 0 |
| S02 | baseline | 3/3 | 2406 | 96 | 0 | 44 | 1148 | 1258 | 1 | 52 | 42247 | 42921 | 0.001267 | 2 | 0 |
| S03 | baseline | 3/3 | 3812 | 801 | 0 | 680 | 2436 | 1376 | 2 | 105 | 115153 | 116106 | 0.003663 | 3 | 0 |
| S04 | baseline | 3/3 | 2474 | 324 | 0 | 226 | 1161 | 1313 | 1 | 104 | 63666 | 64513 | 0.001878 | 2 | 0 |
| S05 | baseline | 3/3 | 6581 | 457 | 0 | 369 | 1179 | 5402 | 1 | 1767 | 165334 | 166004 | 0.003962 | 2 | 0 |
| S06 | baseline | 3/3 | 3298 | 453 | 0 | 345 | 1167 | 2131 | 1 | 1361 | 93253 | 94022 | 0.002557 | 2 | 0 |
| S07 | baseline | 3/3 | 4153 | 443 | 0 | 158 | 2458 | 1695 | 4 | 397 | 83911 | 85102 | 0.002895 | 3 | 0 |
| S08 | baseline | 3/3 | 4201 | 256 | 0 | 176 | 2629 | 1572 | 2 | 368 | 67551 | 68112 | 0.002438 | 3 | 0 |
| S09 | baseline | 3/3 | 7124 | 840 | 0 | 571 | 5490 | 1634 | 2 | 120 | 187278 | 188401 | 0.00517 | 5 | 0 |
| S10 | baseline | 3/3 | 1142 | 335 | 0 | 238 | 0 | 1142 | 0 | 0 | 56382 | 56759 | 0.00134 | 1 | 0 |
| S11 | baseline | 3/3 | 1153 | 97 | 0 | 82 | 0 | 1153 | 0 | 0 | 34997 | 35385 | 0.000737 | 1 | 0 |
| S12 | baseline | 2/3 | 5643 | 1723 | 0 | 1481 | 4211 | 1432 | 2 | 116 | 236309 | 237373 | 0.006792 | 5 | 0 |

## Totals

| metric | baseline |
|---|---|
| calls | 91 |
| failed_calls | 0 |
| prompt_tokens | 130077 |
| completion_tokens | 19617 |
| cached_tokens | 0 |
| reasoning_tokens | 14908 |
| tool_calls | 47 |
| tool_output_tokens_est | 13198 |
| latency_ms | 3720306 |
| cost_usd | 0.105306 |
| resent_tokens | 66194 |
| new_tokens | 63883 |
| wall_ms | 3752910 |
| success_rate | 0.972222 |
| cost_per_success | 0.003009 |
| tokens_per_success | 4277.0 |
| resent_share | 0.508883 |
| cache_hit_rate | n/a |
| avg_per_task.tokens | 4158.2 |
| avg_per_task.rounds | 2.388889 |
| avg_per_task.tool_calls | 1.305556 |
| avg_per_task.latency_ms | 103341.8 |
| prefix_share | 0.787733 |

## Totals by purpose

| purpose | metric | baseline |
|---|---|---|
| agent | calls | 86 |
| agent | prompt_tokens | 127872 |
| agent | completion_tokens | 17427 |
| summary | calls | 5 |
| summary | prompt_tokens | 2205 |
| summary | completion_tokens | 2190 |

## Audit

| question | baseline |
|---|---|
| most expensive tool (output tokens) | exec (11605 tokens, 38 calls) |
| most expensive turn/round | S05-1 turn 3 round 2: 5402 prompt tokens |
| fastest-growing context category | tool (+1312.5 chars/run) |
| re-sent share | 0.508883 |

## Reasoning

### baseline

- reasoning observed: yes, max reasoning_tokens: 1816, max reasoning_chars: 6641, Σ reasoning_tokens: 14908, reasoning share: 0.7600
- tool-exposed calls: calls: 86, reasoning observed: yes, max reasoning_tokens: 1816, max reasoning_chars: 6641, Σ reasoning_tokens: 12938, reasoning share: 0.7424
- tools-withheld calls: calls: 5, reasoning observed: yes, max reasoning_tokens: 511, max reasoning_chars: 2275, Σ reasoning_tokens: 1970, reasoning share: 0.8995


## Latency

| scope | baseline |
|---|---|
| median latency_ms per call | 34997 |
| median latency_ms (agent) | 34698.0 |
| median latency_ms (summary) | 48737 |

## Failures

### baseline

| scenario | repeat | failure | checks | answers |
|---|---|---|---|---|
| S12 | 1 | checks | summary_exists: 0 summary row(s), no goal | 

Записал: проект Orion, дедлайн 15 октября. Учту это в нашем разговоре.

Важное уточнение: у меня нет постоянной памяти между сессиями, поэтому в новом чате мне нужно будет напомнить об этом. Если хочешь, могу записать это в файл в песочнице, чтобы сохранить на время работы. ⏎ 

Проект Orion, дедла |

