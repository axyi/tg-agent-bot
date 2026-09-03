# Benchmark report — rsn-d-2-default

## Meta

| field | baseline |
|---|---|
| tag | rsn-d-2-default |
| started_at | 2026-09-03T14:17:31Z |
| finished_at | 2026-09-03T14:19:03Z |
| git_commit | 818bbdea1121d42f7d6f0edfc0c1470a23b385c7 |
| provider | lmstudio |
| model | qwen/qwen3.8-27b |
| context_length | 42496 |
| repeats | 1 |
| timeout_s | 600 |
| scenarios_sha256 | d0d9e3f658d1ad6b36d1048b98d39f3a180468c484e9c549163b8bcb4ac0aeae |
| skipped_scenarios | [] |
| constants | {"CONTEXT_WINDOW_MESSAGES": 30, "EXEC_MAX_STREAM_BYTES": 4096, "FETCH_MAX_BYTES": 65536, "HTTP_ATTEMPT_LIMIT": 9, "REQUEST_DEFAULTS": {"stream": false, "temperature": 0, "tool_choice": "auto"}, "ROUND_LIMIT": 8, "TOOL_EXECUTION_LIMIT": 12, "TOOL_ROUND_LIMIT": 7} |
| config_sha256 | 8a9cf9040f2df068fe4f7dd27d205fc1dc3174897ecfce901e7ec14b94caa5a9 |
| only | ["S05"] |
| prefix_tokens | 842 |
| env_flags.HISTORY_TOOL_STUB | on |
| env_flags.EXEC_OUTPUT_DEFAULT_CHARS | 1500 |
| env_flags.FETCH_INLINE_DEFAULT_CHARS | 5000 |
| env_flags.LLM_REASONING | n/a |
| env_flags.LLM_SUMMARY_MODEL |  |
| env_flags.LLM_FAILOVER | off |
| env_flags.LLM_MAX_TOKENS | 2048 |
| env_flags.LLM_REASONING_POLICY | n/a |
| env_flags.LLM_REASONING_ON_PURPOSES | n/a |
| pricing.basis | reference:qwen/qwen3.8-27b |
| pricing.model | qwen/qwen3.8-27b |
| pricing.input_usd_per_mtok | 0.425 |
| pricing.output_usd_per_mtok | 2.55 |
| pricing.cached_input_usd_per_mtok | 0.085 |
| pricing.fetched_at | 2026-09-03T14:17:31Z |

## Per scenario

| scenario | file | success | prompt_tokens | completion_tokens | cached_tokens | reasoning_tokens | resent_tokens | new_tokens | tool_calls | tool_output_tokens_est | latency_ms | wall_ms | cost_usd | calls | failed_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S05 | baseline | 1/1 | 2169 | 436 | 0 | 338 | 917 | 1252 | 1 | 150 | 57898 | 58779 | 0.002034 | 2 | 0 |

## Totals

| metric | baseline |
|---|---|
| calls | 2 |
| failed_calls | 0 |
| prompt_tokens | 2169 |
| completion_tokens | 436 |
| cached_tokens | 0 |
| reasoning_tokens | 338 |
| tool_calls | 1 |
| tool_output_tokens_est | 150 |
| latency_ms | 57898 |
| cost_usd | 0.002034 |
| resent_tokens | 917 |
| new_tokens | 1252 |
| wall_ms | 58779 |
| success_rate | 1 |
| cost_per_success | 0.002034 |
| tokens_per_success | 2605.0 |
| resent_share | 0.422775 |
| cache_hit_rate | n/a |
| avg_per_task.tokens | 2605.0 |
| avg_per_task.rounds | 2 |
| avg_per_task.tool_calls | 1 |
| avg_per_task.latency_ms | 57898.0 |
| prefix_share | 0.776395 |

## Totals by purpose

| purpose | metric | baseline |
|---|---|---|
| agent | calls | 2 |
| agent | prompt_tokens | 2169 |
| agent | completion_tokens | 436 |
| summary | calls | 0 |
| summary | prompt_tokens | 0 |
| summary | completion_tokens | 0 |

## Audit

| question | baseline |
|---|---|
| most expensive tool (output tokens) | exec (150 tokens, 1 calls) |
| most expensive turn/round | S05-1 turn 3 round 2: 1252 prompt tokens |
| fastest-growing context category | tool (+574.0 chars/run) |
| re-sent share | 0.422775 |

## Reasoning

### baseline

- reasoning observed: yes, max reasoning_tokens: 327, max reasoning_chars: 1083, Σ reasoning_tokens: 338, reasoning share: 0.7752
- tool-exposed calls: calls: 2, reasoning observed: yes, max reasoning_tokens: 327, max reasoning_chars: 1083, Σ reasoning_tokens: 338, reasoning share: 0.7752
- tools-withheld calls: calls: 0, reasoning observed: no, max reasoning_tokens: 0, max reasoning_chars: 0, Σ reasoning_tokens: 0, reasoning share: n/a


## Latency

| scope | baseline |
|---|---|
| median latency_ms per call | 28949.0 |
| median latency_ms (agent) | 28949.0 |
| median latency_ms (summary) | n/a |

## Failures

### baseline

none

