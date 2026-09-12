"""Aggregates over `llm_calls` and `tool_calls` (REQ-V13-OBS-08).

One implementation, three readers: `/stats`, the benchmark report and the
dashboard. The functions are pure over rows — every one of them either takes a
connection and reads through `storage`, or takes a sequence of row-like
mappings (an `sqlite3.Row` and a plain `dict` from a benchmark file behave the
same under `row["column"]`).
"""

import bisect
import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import storage

TOP_TOOLS_LIMIT = 5

# The buckets of `llm_calls.prompt_chars_by_role`.
PROMPT_ROLE_KEYS = ("system", "tools", "user", "assistant", "tool")

# v1.6.0 additions (REQ-V160-MET-03..07): every cap REQ-V160-MET-07 names.
USAGE_BY_CAP = 500
ERROR_BREAKDOWN_CAP = 100
TOOL_HEALTH_CAP = 50
HISTOGRAM_CAP = 20

# OpenTelemetry GenAI metrics contract (REQ-V160-MET-04), verified 2026-09-04
# against the recommended explicit bucket boundaries in
# open-telemetry/semantic-conventions-genai.
DURATION_BOUNDARIES = (
    0.01,
    0.02,
    0.04,
    0.08,
    0.16,
    0.32,
    0.64,
    1.28,
    2.56,
    5.12,
    10.24,
    20.48,
    40.96,
    81.92,
)
TOKEN_BOUNDARIES = (
    1,
    4,
    16,
    64,
    256,
    1024,
    4096,
    16384,
    65536,
    262144,
    1048576,
    4194304,
    16777216,
    67108864,
)


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
    return {role: float(last.get(role, 0) - first.get(role, 0)) for role in PROMPT_ROLE_KEYS}


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
    return [(tool, tokens, tokens / grand if grand else 0.0) for tool, tokens in ranked[:limit]]


def turn_timeline(conn: sqlite3.Connection, conv_id: int, turn_id: int | None = None) -> list[dict]:
    """The rounds of one exchange: the agent calls from the one that produced
    `turn_id` up to (not including) the next round-1 call, each with the tool
    calls of its own turn. `turn_id` defaults to the most recent exchange."""
    calls = [row for row in storage.fetch_llm_calls(conn, conv_id) if row["purpose"] == "agent"]
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
            break  # the next user message starts here
        timeline.append(
            {
                "round": row["round"],
                "prompt_tokens": row["prompt_tokens"],
                "completion_tokens": row["completion_tokens"],
                "tools": tools_by_turn.get(row["turn_id"], []),
                "final": row["tool_calls_n"] == 0,
            }
        )
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


# ============================================================================
# v1.6.0 additions (REQ-V160-MET-01..07): the aggregate functions the
# dashboard pages and JSON API share with /stats -- no parallel implementation
# anywhere else (T-V160-MET-08).
# ============================================================================


@dataclass(frozen=True)
class UsageRow:
    """One row of `usage_by`. Only the fields for its own grouping are set;
    the rest stay `None` (REQ-V160-MET-03) -- no consumer parses `key` apart."""

    provider: str | None
    model: str | None
    purpose: str | None
    scenario: str | None
    day: str | None
    key: str
    calls: int
    errors: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    reasoning_tokens: int
    cost_usd: float
    cost_basis: str | None
    cache_hit_share: float | None
    reasoning_share: float | None


@dataclass(frozen=True)
class ErrorBreakdown:
    by_finish_reason: dict[str, int]
    by_error_kind: dict[str, int]
    total: int
    error_rate: float


@dataclass(frozen=True)
class Histogram:
    name: str
    unit: str
    attributes: tuple[tuple[str, str], ...]
    boundaries: tuple[float, ...]
    counts: tuple[int, ...]
    total: int
    sum: float
    p50: float
    p95: float


@dataclass(frozen=True)
class ToolHealthRow:
    tool: str
    calls: int
    ok: int
    error: int
    budget: int
    rejected: int
    refused_repeat: int
    error_rate: float
    p50_ms: float
    p95_ms: float
    max_consecutive_repeats: int
    output_tokens_est: int


@dataclass(frozen=True)
class SummaryHealth:
    attempts: int
    ok: int
    truncated: int
    retried: int
    failed: int


def _since_ok(ts: str, since: date | None) -> bool:
    """Lexicographic on the fixed-width ISO-8601 UTC strings `storage.utc_now_iso`
    writes: a bare date string is a prefix of same-day timestamps, so the
    boundary day is included (REQ-V160-MET-03)."""
    return since is None or ts >= since.isoformat()


def _fetch_llm_rows(conn: sqlite3.Connection, since: date | None) -> list[sqlite3.Row]:
    return [row for row in storage.fetch_llm_calls(conn) if _since_ok(row["ts"], since)]


def _fetch_tool_rows(conn: sqlite3.Connection, since: date | None) -> list[sqlite3.Row]:
    return [row for row in storage.fetch_tool_calls(conn) if _since_ok(row["ts"], since)]


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(p / 100 * (len(ordered) - 1))))
    return ordered[index]


def _scenario_by_chat_span(conn: sqlite3.Connection) -> dict[str, str | None]:
    """`chat` span_id -> its trace's root span's `tg_agent.scenario_id`, or
    `None` when the trace carries none (REQ-V160-MET-03 "scenario" group)."""
    rows = conn.execute(
        "SELECT chat.span_id AS span_id, root.attributes_json AS root_attrs "
        "FROM spans AS chat "
        "JOIN spans AS root "
        "  ON root.trace_id = chat.trace_id AND root.parent_span_id IS NULL "
        "WHERE chat.kind = 'CLIENT'"
    ).fetchall()
    result: dict[str, str | None] = {}
    for row in rows:
        attrs = json.loads(row["root_attrs"])
        result[row["span_id"]] = attrs.get("tg_agent.scenario_id")
    return result


def usage_by(conn: sqlite3.Connection, *, group: str, since: date | None = None) -> list[UsageRow]:
    if group not in ("model", "day", "purpose", "scenario"):
        raise ValueError(f"unknown usage_by group: {group!r}")
    rows = _fetch_llm_rows(conn, since)
    scenario_by_span = _scenario_by_chat_span(conn) if group == "scenario" else {}

    buckets: dict[tuple, list] = {}
    for row in rows:
        if group == "model":
            dims = (row["provider"], row["model"])
        elif group == "day":
            dims = (row["ts"][:10],)
        elif group == "purpose":
            dims = (row["purpose"],)
        else:
            dims = (scenario_by_span.get(row["span_id"]),)
        buckets.setdefault(dims, []).append(row)

    usage_rows = [_usage_row_for(group, dims, group_rows) for dims, group_rows in buckets.items()]
    usage_rows.sort(key=lambda r: r.key)
    if len(usage_rows) > USAGE_BY_CAP:
        head, tail = usage_rows[:USAGE_BY_CAP], usage_rows[USAGE_BY_CAP:]
        usage_rows = head + [_fold_usage_rows(tail)]
    return usage_rows


def _usage_row_for(group: str, dims: tuple, rows: list) -> UsageRow:
    provider = model = purpose = scenario = day = None
    if group == "model":
        provider, model = dims
        key = f"{provider or '(none)'}/{model or '(none)'}"
    elif group == "day":
        (day,) = dims
        key = day or "(none)"
    elif group == "purpose":
        (purpose,) = dims
        key = purpose or "(none)"
    else:
        (scenario,) = dims
        key = scenario or "(none)"
    return _build_usage_row(provider, model, purpose, scenario, day, key[:128], rows)


def _build_usage_row(provider, model, purpose, scenario, day, key: str, rows: list) -> UsageRow:
    priced = [row for row in rows if row["cost_usd"] is not None]
    bases = {row["cost_basis"] for row in rows if row["cost_basis"] is not None}
    cache_pairs = [
        (row["cached_tokens"], row["prompt_tokens"])
        for row in rows
        if row["cached_tokens"] is not None and row["prompt_tokens"] is not None
    ]
    cache_denominator = sum(p for _, p in cache_pairs)
    reasoning_pairs = [
        (row["reasoning_tokens"], row["completion_tokens"])
        for row in rows
        if row["reasoning_tokens"] is not None and row["completion_tokens"] is not None
    ]
    reasoning_denominator = sum(c for _, c in reasoning_pairs)
    return UsageRow(
        provider=provider,
        model=model,
        purpose=purpose,
        scenario=scenario,
        day=day,
        key=key,
        calls=len(rows),
        errors=sum(1 for row in rows if row["error_kind"] is not None),
        input_tokens=sum(row["prompt_tokens"] or 0 for row in rows),
        output_tokens=sum(row["completion_tokens"] or 0 for row in rows),
        cached_tokens=sum(row["cached_tokens"] or 0 for row in rows),
        reasoning_tokens=sum(row["reasoning_tokens"] or 0 for row in rows),
        cost_usd=sum(row["cost_usd"] for row in priced) if priced else 0.0,
        cost_basis=", ".join(sorted(bases)) if bases else None,
        cache_hit_share=(sum(c for c, _ in cache_pairs) / cache_denominator)
        if cache_denominator
        else None,
        reasoning_share=(sum(r for r, _ in reasoning_pairs) / reasoning_denominator)
        if reasoning_denominator
        else None,
    )


def _fold_usage_rows(rows: list[UsageRow]) -> UsageRow:
    return UsageRow(
        provider=None,
        model=None,
        purpose=None,
        scenario=None,
        day=None,
        key="(other)",
        calls=sum(r.calls for r in rows),
        errors=sum(r.errors for r in rows),
        input_tokens=sum(r.input_tokens for r in rows),
        output_tokens=sum(r.output_tokens for r in rows),
        cached_tokens=sum(r.cached_tokens for r in rows),
        reasoning_tokens=sum(r.reasoning_tokens for r in rows),
        cost_usd=sum(r.cost_usd for r in rows),
        cost_basis=None,
        cache_hit_share=None,
        reasoning_share=None,
    )


def error_breakdown(conn: sqlite3.Connection, *, since: date | None = None) -> ErrorBreakdown:
    rows = _fetch_llm_rows(conn, since)
    finish_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    errors = 0
    for row in rows:
        finish_key = row["finish_reason"] or "(none)"
        finish_counts[finish_key] = finish_counts.get(finish_key, 0) + 1
        error_key = row["error_kind"] or "ok"
        error_counts[error_key] = error_counts.get(error_key, 0) + 1
        if row["error_kind"] is not None:
            errors += 1
    total = len(rows)
    return ErrorBreakdown(
        by_finish_reason=_cap_buckets(finish_counts),
        by_error_kind=_cap_buckets(error_counts),
        total=total,
        error_rate=errors / total if total else 0.0,
    )


def _cap_buckets(counts: dict[str, int]) -> dict[str, int]:
    if len(counts) <= ERROR_BREAKDOWN_CAP:
        return counts
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    result = dict(ranked[:ERROR_BREAKDOWN_CAP])
    result["(other)"] = sum(v for _, v in ranked[ERROR_BREAKDOWN_CAP:])
    return result


def _build_histogram(name, unit, attributes, boundaries, values: list[float]) -> Histogram:
    counts = [0] * (len(boundaries) + 1)
    for value in values:
        counts[bisect.bisect_left(boundaries, value)] += 1
    return Histogram(
        name=name,
        unit=unit,
        attributes=attributes,
        boundaries=tuple(boundaries),
        counts=tuple(counts),
        total=len(values),
        sum=sum(values),
        p50=_percentile(values, 50),
        p95=_percentile(values, 95),
    )


def _histograms_with_boundaries(
    groups: dict[tuple, list[float]], boundaries, name: str, unit: str
) -> list[Histogram]:
    items = sorted(groups.items(), key=lambda kv: kv[0])
    other: list[float] | None = None
    if len(items) > HISTOGRAM_CAP:
        items, tail = items[:HISTOGRAM_CAP], items[HISTOGRAM_CAP:]
        other = [value for _, values in tail for value in values]
    histograms = [
        _build_histogram(name, unit, attrs, boundaries, values) for attrs, values in items
    ]
    if other is not None:
        # REQ-V160-MET-04: the folded histogram's attributes are exactly this
        # one pair, regardless of the grouping dimensions used elsewhere.
        histograms.append(
            _build_histogram(name, unit, (("gen_ai.request.model", "(other)"),), boundaries, other)
        )
    return histograms


def latency_histogram(conn: sqlite3.Connection, *, since: date | None = None) -> list[Histogram]:
    rows = _fetch_llm_rows(conn, since)
    groups: dict[tuple, list[float]] = {}
    for row in rows:
        if row["latency_ms"] is None:
            continue
        provider = row["provider"] or "(none)"
        model = row["model"] or "(none)"
        attrs = (
            ("gen_ai.operation.name", "chat"),
            ("gen_ai.provider.name", provider),
            ("gen_ai.request.model", model),
        )
        groups.setdefault(attrs, []).append(row["latency_ms"] / 1000.0)
    return _histograms_with_boundaries(
        groups, DURATION_BOUNDARIES, "gen_ai.client.operation.duration", "s"
    )


def token_histogram(
    conn: sqlite3.Connection, *, token_type: str, since: date | None = None
) -> list[Histogram]:
    if token_type not in ("input", "output"):
        raise ValueError(f"unknown token_type: {token_type!r}")
    column = "prompt_tokens" if token_type == "input" else "completion_tokens"
    rows = _fetch_llm_rows(conn, since)
    groups: dict[tuple, list[float]] = {}
    for row in rows:
        value = row[column]
        if value is None:
            continue
        provider = row["provider"] or "(none)"
        model = row["model"] or "(none)"
        attrs = (
            ("gen_ai.operation.name", "chat"),
            ("gen_ai.provider.name", provider),
            ("gen_ai.request.model", model),
            ("gen_ai.token.type", token_type),
        )
        groups.setdefault(attrs, []).append(float(value))
    return _histograms_with_boundaries(
        groups, TOKEN_BOUNDARIES, "gen_ai.client.token.usage", "{token}"
    )


def tool_health(conn: sqlite3.Connection, *, since: date | None = None) -> list[ToolHealthRow]:
    rows = _fetch_tool_rows(conn, since)
    by_tool: dict[str, list] = {}
    by_conv_turn: dict[tuple, list] = {}
    for row in rows:
        by_tool.setdefault(row["tool"], []).append(row)
        by_conv_turn.setdefault((row["conv_id"], row["turn_id"]), []).append(row)

    consecutive_by_tool: dict[str, int] = {}
    for turn_rows in by_conv_turn.values():
        ordered = sorted(turn_rows, key=lambda r: r["id"])
        current_tool, current_run = None, 0
        for row in ordered:
            current_run = current_run + 1 if row["tool"] == current_tool else 1
            current_tool = row["tool"]
            if current_run > consecutive_by_tool.get(current_tool, 0):
                consecutive_by_tool[current_tool] = current_run

    results = []
    for tool, tool_rows in by_tool.items():
        durations = [row["duration_ms"] for row in tool_rows]
        errors = sum(1 for row in tool_rows if row["outcome"] == "error")
        results.append(
            ToolHealthRow(
                tool=tool,
                calls=len(tool_rows),
                ok=sum(1 for row in tool_rows if row["outcome"] == "ok"),
                error=errors,
                budget=sum(1 for row in tool_rows if row["outcome"] == "budget"),
                rejected=sum(1 for row in tool_rows if row["outcome"] == "rejected"),
                refused_repeat=sum(1 for row in tool_rows if row["outcome"] == "refused_repeat"),
                error_rate=errors / len(tool_rows) if tool_rows else 0.0,
                p50_ms=_percentile(durations, 50),
                p95_ms=_percentile(durations, 95),
                max_consecutive_repeats=consecutive_by_tool.get(tool, 0),
                output_tokens_est=sum(row["output_tokens_est"] for row in tool_rows),
            )
        )
    results.sort(key=lambda r: (-r.calls, r.tool))
    return results[:TOOL_HEALTH_CAP]


# REQ-V160-TRC-10's seven budget constants -- the only names `limit_hits` may
# report (T-V160-MET-09 asserts `MAX_TOOL_CALLS_ACCEPTED` never appears).
_LIMIT_HIT_NAMES = frozenset(
    {
        "ROUND_LIMIT",
        "TOOL_ROUND_LIMIT",
        "HTTP_ATTEMPT_LIMIT",
        "TOOL_EXECUTION_LIMIT",
        "MAX_TOOL_CALLS_PER_RESPONSE",
        "MALFORMED_RETRY_LIMIT",
        "EMPTY_REPAIR_LIMIT",
    }
)


def limit_hits(conn: sqlite3.Connection, *, since: date | None = None) -> dict[str, int]:
    rows = conn.execute(
        "SELECT ts, attributes_json FROM spans WHERE parent_span_id IS NULL"
    ).fetchall()
    counts: dict[str, int] = {}
    for row in rows:
        if not _since_ok(row["ts"], since):
            continue
        attrs = json.loads(row["attributes_json"])
        raw = attrs.get("tg_agent.limit_hit", "")
        # Each name counts once per turn even if the stored string somehow
        # repeats one -- `MutableSpan.add_limit_hit` already dedupes via a
        # set, this is a second, cheap line of defence.
        for name in set(filter(None, raw.split(","))):
            if name in _LIMIT_HIT_NAMES:
                counts[name] = counts.get(name, 0) + 1
    return counts


def retry_rate(conn: sqlite3.Connection, *, since: date | None = None) -> tuple[int, int]:
    rows = _fetch_llm_rows(conn, since)
    return sum(1 for row in rows if row["attempt"] > 1), len(rows)


def context_pressure(conn: sqlite3.Connection, *, since: date | None = None) -> tuple[float, int]:
    rows = [row for row in _fetch_llm_rows(conn, since) if row["purpose"] == "agent"]
    if not rows:
        return 0.0, 0
    values = [row["messages_n"] for row in rows]
    return sum(values) / len(values), max(values)


def summary_health(conn: sqlite3.Connection, *, since: date | None = None) -> SummaryHealth:
    rows = [row for row in _fetch_llm_rows(conn, since) if row["purpose"] == "summary"]
    return SummaryHealth(
        attempts=len(rows),
        ok=sum(1 for row in rows if row["error_kind"] is None),
        truncated=sum(1 for row in rows if row["error_kind"] == "truncated"),
        retried=sum(1 for row in rows if row["attempt"] == 2),
        failed=sum(
            1
            for row in rows
            if (row["error_kind"] is not None and row["error_kind"] != "truncated")
            or (row["attempt"] == 2 and row["error_kind"] == "truncated")
        ),
    )
