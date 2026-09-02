"""Aggregates over `llm_calls` and `tool_calls` (REQ-V13-OBS-08).

One implementation, three readers: `/stats`, the benchmark report and the
dashboard. The functions are pure over rows — every one of them either takes a
connection and reads through `storage`, or takes a sequence of row-like
mappings (an `sqlite3.Row` and a plain `dict` from a benchmark file behave the
same under `row["column"]`).
"""

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

import storage

TOP_TOOLS_LIMIT = 5

# The buckets of `llm_calls.prompt_chars_by_role`.
PROMPT_ROLE_KEYS = ("system", "tools", "user", "assistant", "tool")


@dataclass(frozen=True)
class Stats:
    """One side of the `/stats` table. `None` means "the provider reported
    nothing", which is not the same as zero."""

    calls: int = 0
    errors: int = 0
    tokens_in: int | None = None
    tokens_out: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int = 0
    cost_usd: float | None = None
    cost_basis: str | None = None
    avg_prompt: int | None = None
    resent_share: float | None = None


def conversation_stats(conn: sqlite3.Connection, conv_id: int | None) -> Stats:
    if conv_id is None:
        return Stats()
    calls = storage.fetch_llm_calls(conn, conv_id)
    return _summarize(calls, [calls])


def global_stats(conn: sqlite3.Connection) -> Stats:
    calls = storage.fetch_llm_calls(conn)
    groups: dict[int, list] = {}
    for row in calls:
        groups.setdefault(row["conv_id"], []).append(row)
    # The re-sent metric is defined inside one conversation; walking every row
    # of the database in one sequence would count the jump between two of them.
    return _summarize(calls, list(groups.values()))


def resent_tokens(calls: Sequence) -> tuple[int, int]:
    """`(re-sent, new)` prompt tokens for calls of one conversation, ordered by
    `id`. `new_1 = prompt_1`, `new_i = max(0, prompt_i − prompt_{i−1})`; a call
    that reports no usage is skipped, so its successor is compared with the
    previous call that did report."""
    resent = 0
    new = 0
    previous = None
    for call in calls:
        prompt = call["prompt_tokens"]
        if prompt is None:
            continue
        fresh = prompt if previous is None else max(0, prompt - previous)
        new += fresh
        resent += prompt - fresh
        previous = prompt
    return resent, new


def context_growth(calls: Sequence) -> dict[str, float]:
    """How much each part of the prompt grew over one conversation or benchmark
    run: `prompt_chars_by_role` at the last `purpose='agent'` call minus the
    first (spec-v1.3 section 7.4, consumed by `bench.py report` as the mean over
    runs and rendered as the fastest-growing context category). A run with fewer
    than two agent calls grew by nothing and contributes 0 to every role."""
    agent_calls = [call for call in calls if call["purpose"] == "agent"]
    if len(agent_calls) < 2:
        return {role: 0.0 for role in PROMPT_ROLE_KEYS}
    first = _by_role(agent_calls[0])
    last = _by_role(agent_calls[-1])
    return {
        role: float(last.get(role, 0) - first.get(role, 0)) for role in PROMPT_ROLE_KEYS
    }


def _by_role(call) -> dict:
    """The column is TEXT in SQLite and already an object in a benchmark file."""
    value = call["prompt_chars_by_role"]
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else {}


def prefix_share(document: dict) -> float | None:
    """`prefix_tokens × calls / \u03a3 prompt_tokens` (spec-v1.3 section 7.8): how
    much of every prompt was the byte-stable prefix. `None` when the run
    recorded no prefix probe or sent no prompt at all. Takes a benchmark
    document, so `bench.py report` and the dashboard share one implementation
    (REQ-V13-OBS-08)."""
    prefix = document["meta"].get("prefix_tokens")
    totals = document["summary"]["totals"]
    prompt = totals["prompt_tokens"]
    if prefix is None or not prompt:
        return None
    return (prefix * totals["calls"]) / prompt


def top_tools(
    conn: sqlite3.Connection, limit: int = TOP_TOOLS_LIMIT
) -> list[tuple[str, int, float]]:
    """`(tool, output tokens, share of all tool output)`, biggest first. The
    share is of the grand total, so a truncated list still adds up honestly."""
    totals: dict[str, int] = {}
    for row in storage.fetch_tool_calls(conn):
        totals[row["tool"]] = totals.get(row["tool"], 0) + row["output_tokens_est"]
    grand = sum(totals.values())
    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    return [
        (tool, tokens, tokens / grand if grand else 0.0) for tool, tokens in ranked[:limit]
    ]


def turn_timeline(
    conn: sqlite3.Connection, conv_id: int, turn_id: int | None = None
) -> list[dict]:
    """The rounds of one exchange: the agent calls from the one that produced
    `turn_id` up to (not including) the next round-1 call, each with the tool
    calls of its own turn. `turn_id` defaults to the most recent exchange."""
    calls = [row for row in storage.fetch_llm_calls(conn, conv_id)
             if row["purpose"] == "agent"]
    if turn_id is None:
        turn_id = _last_exchange_turn(calls)
    start = next((index for index, row in enumerate(calls) if row["turn_id"] == turn_id), None)
    if start is None:
        return []

    tools_by_turn: dict[int, list[tuple[str, int]]] = {}
    for row in storage.fetch_tool_calls(conn, conv_id):
        tools_by_turn.setdefault(row["turn_id"], []).append((row["tool"], row["duration_ms"]))

    timeline = []
    for offset, row in enumerate(calls[start:]):
        if offset and row["round"] == 1:
            break                     # the next user message starts here
        timeline.append({
            "round": row["round"],
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "tools": tools_by_turn.get(row["turn_id"], []),
            "final": row["tool_calls_n"] == 0,
        })
    return timeline


def _last_exchange_turn(calls: Sequence) -> int | None:
    for row in reversed(list(calls)):
        if row["round"] == 1 and row["turn_id"] is not None:
            return row["turn_id"]
    return None


def _summarize(calls: Sequence, groups: Sequence[Sequence]) -> Stats:
    if not calls:
        return Stats()
    prompts = [row["prompt_tokens"] for row in calls if row["prompt_tokens"] is not None]
    completions = [
        row["completion_tokens"] for row in calls if row["completion_tokens"] is not None
    ]
    cached = [row["cached_tokens"] for row in calls if row["cached_tokens"] is not None]
    priced = [row for row in calls if row["cost_usd"] is not None]
    bases = {row["cost_basis"] for row in priced if row["cost_basis"] is not None}

    resent = 0
    new = 0
    for group in groups:
        group_resent, group_new = resent_tokens(group)
        resent += group_resent
        new += group_new
    total_prompt = resent + new

    return Stats(
        calls=len(calls),
        errors=sum(1 for row in calls if row["error_kind"] is not None),
        tokens_in=sum(prompts) if prompts else None,
        tokens_out=sum(completions) if completions else None,
        cached_tokens=sum(cached) if cached else None,
        reasoning_tokens=sum(row["reasoning_tokens"] or 0 for row in calls),
        cost_usd=sum(row["cost_usd"] for row in priced) if priced else None,
        cost_basis=_basis(bases),
        avg_prompt=round(sum(prompts) / len(prompts)) if prompts else None,
        resent_share=resent / total_prompt if total_prompt else None,
    )


def _basis(bases: set[str]) -> str | None:
    """One distinct basis names itself; several are `mixed`; none means the
    side has no price at all."""
    if not bases:
        return None
    return next(iter(bases)) if len(bases) == 1 else "mixed"
