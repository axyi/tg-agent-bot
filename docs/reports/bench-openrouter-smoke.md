# Benchmark report — openrouter-smoke

## Meta

| field | baseline |
|---|---|
| tag | openrouter-smoke |
| started_at | 2026-09-02T17:34:37Z |
| finished_at | 2026-09-02T17:34:42Z |
| git_commit | 69ebc7575550731b981e6799f55dfd5eaaec8317 |
| provider | openrouter |
| model | google/gemini-2.5-flash-lite |
| context_length | 131072 |
| repeats | 1 |
| timeout_s | 600 |
| scenarios_sha256 | 586ed397cae5caef1ef464d41addde3963803e27b559443bbea5e31e5a0d0a48 |
| skipped_scenarios | [] |
| constants | {"CONTEXT_WINDOW_MESSAGES": 30, "EXEC_MAX_STREAM_BYTES": 4096, "FETCH_MAX_BYTES": 65536, "HTTP_ATTEMPT_LIMIT": 9, "REQUEST_DEFAULTS": {"stream": false, "temperature": 0, "tool_choice": "auto"}, "ROUND_LIMIT": 8, "TOOL_EXECUTION_LIMIT": 12, "TOOL_ROUND_LIMIT": 7} |
| config_sha256 | 0c5886a2cbdef1a424819d96ac09616cd9aaa41194bdd2cfc1b2f10fe3918b4d |
| only | ["S02"] |
| prefix_tokens | n/a |
| env_flags.HISTORY_TOOL_STUB | n/a |
| env_flags.EXEC_OUTPUT_DEFAULT_CHARS | n/a |
| env_flags.FETCH_INLINE_DEFAULT_CHARS | n/a |
| env_flags.LLM_REASONING | n/a |
| env_flags.LLM_SUMMARY_MODEL | n/a |
| env_flags.LLM_FAILOVER | off |
| env_flags.LLM_MAX_TOKENS | 2048 |
| pricing.basis | openrouter-list |
| pricing.model | google/gemini-2.5-flash-lite |
| pricing.input_usd_per_mtok | 0.1 |
| pricing.output_usd_per_mtok | 0.4 |
| pricing.cached_input_usd_per_mtok | 0.01 |
| pricing.fetched_at | 2026-09-02T17:34:37Z |

## Per scenario

| scenario | file | success | prompt_tokens | completion_tokens | cached_tokens | reasoning_tokens | resent_tokens | new_tokens | tool_calls | tool_output_tokens_est | latency_ms | wall_ms | cost_usd | calls | failed_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S02 | baseline | 1/1 | 1500 | 155 | 0 | 137 | 728 | 772 | 1 | 52 | 2434 | 3054 | 0.000212 | 2 | 0 |

## Totals

| metric | baseline |
|---|---|
| calls | 2 |
| failed_calls | 0 |
| prompt_tokens | 1500 |
| completion_tokens | 155 |
| cached_tokens | 0 |
| reasoning_tokens | 137 |
| tool_calls | 1 |
| tool_output_tokens_est | 52 |
| latency_ms | 2434 |
| cost_usd | 0.000212 |
| resent_tokens | 728 |
| new_tokens | 772 |
| wall_ms | 3054 |
| success_rate | 1 |
| cost_per_success | 0.000212 |
| tokens_per_success | 1655.0 |
| resent_share | 0.485333 |
| cache_hit_rate | 0 |
| avg_per_task.tokens | 1655.0 |
| avg_per_task.rounds | 2 |
| avg_per_task.tool_calls | 1 |
| avg_per_task.latency_ms | 2434.0 |
| prefix_share | n/a |

## Totals by purpose

| purpose | metric | baseline |
|---|---|---|
| agent | calls | 2 |
| agent | prompt_tokens | 1500 |
| agent | completion_tokens | 155 |
| summary | calls | 0 |
| summary | prompt_tokens | 0 |
| summary | completion_tokens | 0 |

## Audit

| question | baseline |
|---|---|
| most expensive tool (output tokens) | exec (52 tokens, 1 calls) |
| most expensive turn/round | S02-1 turn 3 round 2: 772 prompt tokens |
| fastest-growing context category | tool (+235.0 chars/run) |
| re-sent share | 0.485333 |

## Reasoning

### baseline

- reasoning observed: yes, max reasoning_tokens: 137, max reasoning_chars: 0, Σ reasoning_tokens: 137, reasoning share: 0.8839
- tool-exposed calls: calls: 2, reasoning observed: yes, max reasoning_tokens: 137, max reasoning_chars: 0, Σ reasoning_tokens: 137, reasoning share: 0.8839
- tools-withheld calls: calls: 0, reasoning observed: no, max reasoning_tokens: 0, max reasoning_chars: 0, Σ reasoning_tokens: 0, reasoning share: n/a


## Latency

| scope | baseline |
|---|---|
| median latency_ms per call | 1217.0 |
| median latency_ms (agent) | 1217.0 |
| median latency_ms (summary) | n/a |

## Failures

### baseline

none

