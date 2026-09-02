# Benchmark report — baseline

## Meta

| field | baseline |
|---|---|
| tag | baseline |
| started_at | 2026-09-02T16:33:54Z |
| finished_at | 2026-09-02T17:34:02Z |
| git_commit | 69ebc7575550731b981e6799f55dfd5eaaec8317 |
| provider | lmstudio |
| model | qwen/qwen3.8-27b |
| context_length | 42496 |
| repeats | 3 |
| timeout_s | 1800.0 |
| scenarios_sha256 | 586ed397cae5caef1ef464d41addde3963803e27b559443bbea5e31e5a0d0a48 |
| skipped_scenarios | [] |
| constants | {"CONTEXT_WINDOW_MESSAGES": 30, "EXEC_MAX_STREAM_BYTES": 4096, "FETCH_MAX_BYTES": 65536, "HTTP_ATTEMPT_LIMIT": 9, "REQUEST_DEFAULTS": {"stream": false, "temperature": 0, "tool_choice": "auto"}, "ROUND_LIMIT": 8, "TOOL_EXECUTION_LIMIT": 12, "TOOL_ROUND_LIMIT": 7} |
| config_sha256 | 754a468695063016a03f79cc58d01230daa2d46fd51f616908dbe6a11d54c91e |
| only | n/a |
| prefix_tokens | 1126 |
| env_flags.HISTORY_TOOL_STUB | n/a |
| env_flags.EXEC_OUTPUT_DEFAULT_CHARS | n/a |
| env_flags.FETCH_INLINE_DEFAULT_CHARS | n/a |
| env_flags.LLM_REASONING | n/a |
| env_flags.LLM_SUMMARY_MODEL | n/a |
| env_flags.LLM_FAILOVER | off |
| env_flags.LLM_MAX_TOKENS | 2048 |
| pricing.basis | reference:qwen/qwen3.8-27b |
| pricing.model | qwen/qwen3.8-27b |
| pricing.input_usd_per_mtok | 0.425 |
| pricing.output_usd_per_mtok | 2.55 |
| pricing.cached_input_usd_per_mtok | 0.085 |
| pricing.fetched_at | 2026-09-02T16:33:54Z |

## Per scenario

| scenario | file | success | prompt_tokens | completion_tokens | cached_tokens | reasoning_tokens | resent_tokens | new_tokens | tool_calls | tool_output_tokens_est | latency_ms | wall_ms | cost_usd | calls | failed_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | baseline | 3/3 | 1138 | 214 | 0 | 120 | 0 | 1138 | 0 | 0 | 45076 | 45372 | 0.001029 | 1 | 0 |
| S02 | baseline | 3/3 | 2406 | 96 | 0 | 44 | 1148 | 1258 | 1 | 52 | 40574 | 41165 | 0.001267 | 2 | 0 |
| S03 | baseline | 3/3 | 2492 | 765 | 0 | 644 | 1161 | 1331 | 1 | 61 | 118935 | 119534 | 0.003407 | 3 | 0 |
| S04 | baseline | 3/3 | 2474 | 329 | 0 | 219 | 1161 | 1313 | 1 | 104 | 64017 | 64712 | 0.00189 | 2 | 0 |
| S05 | baseline | 3/3 | 6581 | 527 | 0 | 439 | 1179 | 5402 | 1 | 1767 | 171820 | 172439 | 0.004141 | 2 | 0 |
| S06 | baseline | 3/3 | 3298 | 545 | 0 | 437 | 1167 | 2131 | 1 | 1361 | 101425 | 102094 | 0.002791 | 2 | 0 |
| S07 | baseline | 3/3 | 4151 | 459 | 0 | 158 | 2458 | 1693 | 4 | 397 | 85196 | 86192 | 0.002935 | 3 | 0 |
| S08 | baseline | 3/3 | 4201 | 254 | 0 | 176 | 2629 | 1572 | 2 | 368 | 67283 | 67698 | 0.002433 | 3 | 0 |
| S09 | baseline | 3/3 | 7124 | 814 | 0 | 520 | 5490 | 1634 | 2 | 120 | 186444 | 187384 | 0.00514 | 5 | 0 |
| S10 | baseline | 3/3 | 1142 | 323 | 0 | 236 | 0 | 1142 | 0 | 0 | 55182 | 55469 | 0.001309 | 1 | 0 |
| S11 | baseline | 3/3 | 1153 | 97 | 0 | 82 | 0 | 1153 | 0 | 0 | 35041 | 35333 | 0.000737 | 1 | 0 |
| S12 | baseline | 3/3 | 5703 | 1357 | 0 | 1107 | 4251 | 1452 | 2 | 120 | 203521 | 204373 | 0.005884 | 5 | 0 |

## Totals

| metric | baseline |
|---|---|
| calls | 88 |
| failed_calls | 1 |
| prompt_tokens | 126109 |
| completion_tokens | 16923 |
| cached_tokens | 0 |
| reasoning_tokens | 12144 |
| tool_calls | 45 |
| tool_output_tokens_est | 13116 |
| latency_ms | 3540575 |
| cost_usd | 0.09675 |
| resent_tokens | 62431 |
| new_tokens | 63678 |
| wall_ms | 3564244 |
| success_rate | 1 |
| cost_per_success | 0.002687 |
| tokens_per_success | 3973.1 |
| resent_share | 0.495056 |
| cache_hit_rate | n/a |
| avg_per_task.tokens | 3973.1 |
| avg_per_task.rounds | 2.333333 |
| avg_per_task.tool_calls | 1.25 |
| avg_per_task.latency_ms | 98349.3 |
| prefix_share | 0.785733 |

## Totals by purpose

| purpose | metric | baseline |
|---|---|---|
| agent | calls | 85 |
| agent | prompt_tokens | 124685 |
| agent | completion_tokens | 15539 |
| summary | calls | 3 |
| summary | prompt_tokens | 1424 |
| summary | completion_tokens | 1384 |

## Audit

| question | baseline |
|---|---|
| most expensive tool (output tokens) | exec (11523 tokens, 36 calls) |
| most expensive turn/round | S05-1 turn 3 round 2: 5402 prompt tokens |
| fastest-growing context category | tool (+1301.4 chars/run) |
| re-sent share | 0.495056 |

## Reasoning

### baseline

- reasoning observed: yes, max reasoning_tokens: 825, max reasoning_chars: 3265, Σ reasoning_tokens: 12144, reasoning share: 0.7176
- tool-exposed calls: calls: 84, reasoning observed: yes, max reasoning_tokens: 825, max reasoning_chars: 3265, Σ reasoning_tokens: 11081, reasoning share: 0.7131
- tools-withheld calls: calls: 3, reasoning observed: yes, max reasoning_tokens: 395, max reasoning_chars: 1721, Σ reasoning_tokens: 1063, reasoning share: 0.7681


## Latency

| scope | baseline |
|---|---|
| median latency_ms per call | 35158.0 |
| median latency_ms (agent) | 34704 |
| median latency_ms (summary) | 56975 |

## Failures

### baseline

none

