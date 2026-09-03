# Benchmark report — s01-repro

## Meta

| field | baseline |
|---|---|
| tag | s01-repro |
| started_at | 2026-09-03T09:56:26Z |
| finished_at | 2026-09-03T10:00:02Z |
| git_commit | 30c7a16fb357854106b1c61b03da02d339314cf7 |
| provider | lmstudio |
| model | qwen/qwen3.8-27b |
| context_length | 42496 |
| repeats | 3 |
| timeout_s | 600 |
| scenarios_sha256 | 586ed397cae5caef1ef464d41addde3963803e27b559443bbea5e31e5a0d0a48 |
| skipped_scenarios | [] |
| constants | {"CONTEXT_WINDOW_MESSAGES": 30, "EXEC_MAX_STREAM_BYTES": 4096, "FETCH_MAX_BYTES": 65536, "HTTP_ATTEMPT_LIMIT": 9, "REQUEST_DEFAULTS": {"stream": false, "temperature": 0, "tool_choice": "auto"}, "ROUND_LIMIT": 8, "TOOL_EXECUTION_LIMIT": 12, "TOOL_ROUND_LIMIT": 7} |
| config_sha256 | 754a468695063016a03f79cc58d01230daa2d46fd51f616908dbe6a11d54c91e |
| only | ["S01"] |
| prefix_tokens | 842 |
| env_flags.HISTORY_TOOL_STUB | on |
| env_flags.EXEC_OUTPUT_DEFAULT_CHARS | 1500 |
| env_flags.FETCH_INLINE_DEFAULT_CHARS | 5000 |
| env_flags.LLM_REASONING | n/a |
| env_flags.LLM_SUMMARY_MODEL |  |
| env_flags.LLM_FAILOVER | off |
| env_flags.LLM_MAX_TOKENS | 2048 |
| pricing.basis | reference:qwen/qwen3.8-27b |
| pricing.model | qwen/qwen3.8-27b |
| pricing.input_usd_per_mtok | 0.425 |
| pricing.output_usd_per_mtok | 2.55 |
| pricing.cached_input_usd_per_mtok | 0.085 |
| pricing.fetched_at | 2026-09-03T09:56:26Z |

## Per scenario

| scenario | file | success | prompt_tokens | completion_tokens | cached_tokens | reasoning_tokens | resent_tokens | new_tokens | tool_calls | tool_output_tokens_est | latency_ms | wall_ms | cost_usd | calls | failed_calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | baseline | 3/3 | 876 | 344 | 0 | 228 | 0 | 876 | 0 | 0 | 35623 | 36133 | 0.001249 | 1 | 0 |

## Totals

| metric | baseline |
|---|---|
| calls | 3 |
| failed_calls | 0 |
| prompt_tokens | 2628 |
| completion_tokens | 1743 |
| cached_tokens | 0 |
| reasoning_tokens | 1451 |
| tool_calls | 0 |
| tool_output_tokens_est | 0 |
| latency_ms | 176361 |
| cost_usd | 0.005562 |
| resent_tokens | 0 |
| new_tokens | 2628 |
| wall_ms | 178079 |
| success_rate | 1 |
| cost_per_success | 0.001854 |
| tokens_per_success | 1457.0 |
| resent_share | 0 |
| cache_hit_rate | n/a |
| avg_per_task.tokens | 1457.0 |
| avg_per_task.rounds | 1 |
| avg_per_task.tool_calls | 0 |
| avg_per_task.latency_ms | 58787.0 |
| prefix_share | 0.961187 |

## Totals by purpose

| purpose | metric | baseline |
|---|---|---|
| agent | calls | 3 |
| agent | prompt_tokens | 2628 |
| agent | completion_tokens | 1743 |
| summary | calls | 0 |
| summary | prompt_tokens | 0 |
| summary | completion_tokens | 0 |

## Audit

| question | baseline |
|---|---|
| most expensive tool (output tokens) | none |
| most expensive turn/round | S01-1 turn 2 round 1: 876 prompt tokens |
| fastest-growing context category | system (+0.0 chars/run) |
| re-sent share | 0 |

## Reasoning

### baseline

- reasoning observed: yes, max reasoning_tokens: 995, max reasoning_chars: 4378, Σ reasoning_tokens: 1451, reasoning share: 0.8325
- tool-exposed calls: calls: 3, reasoning observed: yes, max reasoning_tokens: 995, max reasoning_chars: 4378, Σ reasoning_tokens: 1451, reasoning share: 0.8325
- tools-withheld calls: calls: 0, reasoning observed: no, max reasoning_tokens: 0, max reasoning_chars: 0, Σ reasoning_tokens: 0, reasoning share: n/a


## Latency

| scope | baseline |
|---|---|
| median latency_ms per call | 35623 |
| median latency_ms (agent) | 35623 |
| median latency_ms (summary) | n/a |

## Failures

### baseline

none

