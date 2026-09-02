"""The static benchmark dashboard (spec-v1.3 section 8, REQ-V13-DSH-01…02).

`dashboard.py <bench.json> [--compare other.json] --out <file.html>` turns one
benchmark document (`bench_schema: 1`, section 7.4) into a single
self-contained HTML file: inline CSS, no JavaScript, no external resource of
any kind — the file opens from a file:// path on a machine with no network and
still renders every bar and every number.

Two rules keep it honest:

* **The document is the only input.** Live-bot figures come from `/stats`, not
  from here; nothing is read from the database, the network or the working
  tree. Everything `summary` already carries is displayed, never recomputed —
  `bench.py check` has verified those aggregates against the embedded rows, so
  recomputing them here would only invent a second, unverified arithmetic.
* **Shared aggregates come from `metrics`** (REQ-V13-OBS-08): the per-run
  context growth of the timeline is `metrics.context_growth`, the same
  implementation `/stats` and `bench.py report` use. The tool group-by below is
  not one of those: `metrics.top_tools` reads a live connection and returns
  shares for `/stats`, while a benchmark file has neither — and the dashboard
  additionally needs wall time per tool, which no shared aggregate computes.

Never imported by production code (REQ-V12-TREE-01).
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    # Invoked as a script, exactly like `bench.py`, so the project root is not
    # on `sys.path` by default.
    sys.path.insert(0, str(REPO_ROOT))

import metrics  # noqa: E402

BENCH_SCHEMA = 1

EXIT_OK = 0
EXIT_ERROR = 1

MEDIAN_KEY_COST = "cost_usd"
MEDIAN_KEY_TOKENS = "tokens"

# `summary.totals` keys in display order, with their label and format.
TOTAL_ROWS = (
    ("calls", "LLM calls", "int"),
    ("failed_calls", "failed calls", "int"),
    ("prompt_tokens", "prompt tokens", "int"),
    ("completion_tokens", "completion tokens", "int"),
    ("cached_tokens", "cached tokens", "int"),
    ("reasoning_tokens", "reasoning tokens", "int"),
    ("tool_calls", "tool calls", "int"),
    ("tool_output_tokens_est", "tool output tokens (est)", "int"),
    ("resent_tokens", "re-sent prompt tokens", "int"),
    ("new_tokens", "new prompt tokens", "int"),
    ("latency_ms", "LLM latency, ms", "int"),
    ("wall_ms", "wall clock, ms", "int"),
    ("cost_usd", "cost, USD", "cost"),
)

AVG_ROWS = (
    ("tokens", "tokens per task", "float"),
    ("rounds", "rounds per task", "float"),
    ("tool_calls", "tool calls per task", "float"),
    ("latency_ms", "LLM latency per task, ms", "float"),
)

SCENARIO_DELTA_KEYS = (
    ("prompt_tokens", "int"),
    ("completion_tokens", "int"),
    ("tool_calls", "int"),
    ("tool_output_tokens_est", "int"),
    ("latency_ms", "int"),
    ("cost_usd", "cost"),
)

STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem 1.5rem 4rem; background: #f6f7f9; color: #16191d;
       font: 15px/1.5 ui-sans-serif, system-ui, "Segoe UI", Roboto, Helvetica, Arial,
       sans-serif; }
main { max-width: 68rem; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
h2 { font-size: 1.15rem; margin: 2.5rem 0 .75rem; padding-bottom: .3rem;
     border-bottom: 2px solid #d8dce2; }
h3 { font-size: .95rem; margin: 1.5rem 0 .5rem; font-weight: 600; }
p.sub { margin: 0 0 1rem; color: #5a6472; font-size: .85rem; }
nav { margin: 1rem 0 0; font-size: .85rem; }
nav a { color: #1f5fb0; text-decoration: none; margin-right: 1rem; }
nav a:hover { text-decoration: underline; }
section { background: #fff; border: 1px solid #e2e6eb; border-radius: 8px;
          padding: .25rem 1.25rem 1.25rem; margin-top: 1rem; }
table { border-collapse: collapse; width: 100%; font-size: .875rem; }
caption { text-align: left; font-weight: 600; padding: .5rem 0; }
th, td { padding: .35rem .6rem; border-bottom: 1px solid #eceff3; text-align: left;
         vertical-align: top; }
th { font-weight: 600; color: #47505d; font-size: .8rem; text-transform: uppercase;
     letter-spacing: .02em; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums;
                 font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
tr:last-child td { border-bottom: none; }
.bar { background: #eef1f5; border-radius: 3px; height: .7rem; min-width: 6rem; }
.bar span { display: block; height: 100%; border-radius: 3px; background: #3f7fd0; }
.bar.time span { background: #d08a3f; }
.tag { display: inline-block; padding: .05rem .45rem; border-radius: 999px;
       font-size: .75rem; border: 1px solid #ccd3db; color: #47505d; }
.ok { color: #1c7a4a; }
.bad { color: #b23636; }
.warn { background: #fff4e5; border: 1px solid #e0b678; border-radius: 6px;
        padding: .6rem .9rem; margin: 1rem 0; font-size: .875rem; }
.meta { font-size: .8rem; color: #5a6472; }
.na { color: #8b95a3; }
footer { margin-top: 3rem; color: #8b95a3; font-size: .78rem; }
"""


# --------------------------------------------------------------------------
# document access
# --------------------------------------------------------------------------

def load_document(path: Path) -> dict:
    """The benchmark file, or `ValueError` with a one-line reason."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{path}: {exc.strerror or exc}") from exc
    try:
        document = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(document, dict):
        raise ValueError(f"{path}: the document is not an object")
    if document.get("bench_schema") != BENCH_SCHEMA:
        raise ValueError(
            f"{path}: bench_schema {document.get('bench_schema')!r}, expected {BENCH_SCHEMA}"
        )
    for key in ("meta", "summary"):
        if not isinstance(document.get(key), dict):
            raise ValueError(f"{path}: {key} is missing or not an object")
    if not isinstance(document.get("runs"), list):
        raise ValueError(f"{path}: runs is missing or not an array")
    return document


def scenario_runs(document: dict) -> dict[str, list[dict]]:
    """The runs grouped by scenario, each group in execution order — the order
    the median rule is stable on."""
    grouped: dict[str, list[dict]] = {}
    for run in document["runs"]:
        grouped.setdefault(run["scenario"], []).append(run)
    return grouped


def median_key(runs: Sequence[dict]) -> str:
    """`cost_usd` when every run of the scenario is priced, else the token sum
    (REQ-V13-DSH-01). The fallback is per scenario, not per document: one
    scenario whose repeats died before the first priced call must not silently
    change how a fully priced neighbour is ranked."""
    if any(run["totals"]["cost_usd"] is None for run in runs):
        return MEDIAN_KEY_TOKENS
    return MEDIAN_KEY_COST


def _median_value(run: dict, key: str) -> float:
    totals = run["totals"]
    if key == MEDIAN_KEY_COST:
        return float(totals["cost_usd"])
    return float(totals["prompt_tokens"] + totals["completion_tokens"])


def median_run(runs: Sequence[dict]) -> dict | None:
    """The scenario's median run: its runs sorted ascending by `median_key`,
    stable on execution order, the element at index `n // 2` (REQ-V13-DSH-01).

    Deliberately *not* `statistics.median`: the timeline shows one real run, so
    an even count takes the upper middle element rather than averaging two runs
    that never happened.
    """
    runs = list(runs)
    if not runs:
        return None
    key = median_key(runs)
    # `sorted` is stable, and `runs` arrives in execution order, so tied runs
    # keep the order they were executed in.
    ordered = sorted(runs, key=lambda run: _median_value(run, key))
    return ordered[len(ordered) // 2]


def timeline_rows(run: dict) -> list[dict]:
    """One row per LLM call of the run, with the tool calls that call asked for.

    A tool row carries no reference to the call that requested it, so the rows
    of a turn are handed out in `id` order, `tool_calls_n` at a time; anything
    left over (a harness that recorded a tool call without a matching count)
    lands on the last call of its turn rather than disappearing.
    """
    pending: dict[tuple[Any, Any], list[dict]] = {}
    for row in sorted(run["tool_calls"], key=lambda row: row["id"]):
        pending.setdefault((row["conv_seq"], row["turn_id"]), []).append(row)

    rows = []
    last_of_turn: dict[tuple[Any, Any], dict] = {}
    for call in sorted(run["llm_calls"], key=lambda row: row["id"]):
        turn = (call["conv_seq"], call["turn_id"])
        queue = pending.get(turn, [])
        wanted = int(call["tool_calls_n"] or 0)
        taken = queue[:wanted]
        del queue[:wanted]
        entry = {
            "id": call["id"],
            "conv_seq": call["conv_seq"],
            "turn_id": call["turn_id"],
            "purpose": call["purpose"],
            "round": call["round"],
            "prompt_tokens": call["prompt_tokens"],
            "completion_tokens": call["completion_tokens"],
            "cached_tokens": call["cached_tokens"],
            "latency_ms": call["latency_ms"],
            "error_kind": call["error_kind"],
            "tools": [row["tool"] for row in taken],
        }
        rows.append(entry)
        last_of_turn[turn] = entry
    for turn, queue in pending.items():
        if queue and turn in last_of_turn:
            last_of_turn[turn]["tools"].extend(row["tool"] for row in queue)
    return rows


def tool_breakdown(runs: Sequence[dict]) -> list[dict]:
    """`[{name, calls, output_tokens_est, duration_ms}]` over every run, biggest
    output first — the two axes REQ-V13-DSH-01 asks `#tools` to show."""
    totals: dict[str, dict] = {}
    for run in runs:
        for row in run["tool_calls"]:
            entry = totals.setdefault(
                row["tool"],
                {"name": row["tool"], "calls": 0, "output_tokens_est": 0, "duration_ms": 0},
            )
            entry["calls"] += 1
            entry["output_tokens_est"] += int(row["output_tokens_est"] or 0)
            entry["duration_ms"] += int(row["duration_ms"] or 0)
    return sorted(totals.values(), key=lambda item: (-item["output_tokens_est"], item["name"]))


# --------------------------------------------------------------------------
# formatting
# --------------------------------------------------------------------------

def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def fmt(value: Any, kind: str) -> str:
    """The one number formatter: exact digits for integers (a dashboard that
    abbreviates cannot be checked against the file it renders), fixed precision
    everywhere else, `n/a` for a value the run never reported."""
    if value is None:
        return "n/a"
    if kind == "int":
        # An integral count prints its exact digits; `summary.per_scenario[].median`
        # is `statistics.median`, so an even number of repeats yields the mean of
        # the two middle runs — a half token is shown, never truncated away.
        number = float(value)
        return str(int(number)) if number.is_integer() else f"{number:.1f}"
    if kind == "cost":
        return f"${float(value):.6f}"
    if kind == "share":
        return f"{float(value) * 100:.2f}%"
    if kind == "float":
        return f"{float(value):.1f}"
    if kind == "delta_share":
        return f"{float(value) * 100:+.2f}%"
    return _esc(value)


def _cell(value: Any, kind: str, *, cell_id: str | None = None) -> str:
    text = fmt(value, kind)
    classes = "num" if value is not None else "num na"
    ident = f' id="{_esc(cell_id)}"' if cell_id else ""
    return f'<td class="{classes}"{ident}>{_esc(text)}</td>'


def _delta(new: Any, old: Any, kind: str) -> tuple[str, str]:
    """`(absolute, relative)` as display strings; `n/a` when either side is
    missing, `n/a` relative when the reference is zero."""
    if new is None or old is None:
        return "n/a", "n/a"
    absolute = float(new) - float(old)
    if kind == "int":
        shown = f"{absolute:+.0f}" if absolute.is_integer() else f"{absolute:+.1f}"
    elif kind == "cost":
        shown = f"{absolute:+.6f}"
    elif kind == "share":
        shown = f"{absolute * 100:+.2f}pp"
    else:
        shown = f"{absolute:+.1f}"
    relative = "n/a" if not float(old) else f"{absolute / float(old) * 100:+.1f}%"
    return shown, relative


def _rows(items: Sequence[str]) -> str:
    return "\n".join(items)


# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------

def _header(document: dict, compare: dict | None) -> str:
    meta = document["meta"]
    pricing = meta.get("pricing") or {}
    bits = [
        f"tag <b>{_esc(meta.get('tag'))}</b>",
        f"provider {_esc(meta.get('provider'))}",
        f"model {_esc(meta.get('model'))}",
        f"repeats {_esc(meta.get('repeats'))}",
        f"commit {_esc(str(meta.get('git_commit', ''))[:12])}",
        f"started {_esc(meta.get('started_at'))}",
        f"prefix tokens {_esc(meta.get('prefix_tokens'))}",
        f"pricing {_esc(pricing.get('basis') or 'none')}",
    ]
    skipped = meta.get("skipped_scenarios") or []
    if skipped:
        bits.append(f"skipped {_esc(', '.join(skipped))}")
    if meta.get("only"):
        bits.append(f"only {_esc(', '.join(meta['only']))}")
    banner = ""
    if "aborted" in meta:
        banner = (f'<p class="warn">This run was aborted ({_esc(meta["aborted"])}): the '
                  f"figures below cover the runs that completed and are not comparable "
                  f"with a full run.</p>")
    nav = ['<a href="#aggregates">aggregates</a>', '<a href="#cache">cache</a>',
           '<a href="#tools">tools</a>', '<a href="#timeline">timeline</a>']
    if compare is not None:
        nav.append('<a href="#compare">compare</a>')
    return (f"<h1>Benchmark dashboard — {_esc(meta.get('tag'))}</h1>\n"
            f'<p class="sub">{" · ".join(bits)}</p>\n'
            f"<nav>{''.join(nav)}</nav>\n{banner}")


def _aggregates(document: dict) -> str:
    summary = document["summary"]
    totals = summary["totals"]
    rows = [
        f"<tr><th>{_esc(label)}</th>{_cell(totals[key], kind, cell_id=f'm-{key}')}</tr>"
        for key, label, kind in TOTAL_ROWS
    ]
    rows.append(
        f"<tr><th>runs</th>{_cell(summary['runs'], 'int', cell_id='m-runs')}</tr>")
    rows.append(
        f"<tr><th>skipped runs</th>{_cell(summary['skipped'], 'int', cell_id='m-skipped')}</tr>")
    rows.append(
        f"<tr><th>successes</th>{_cell(summary['successes'], 'int', cell_id='m-successes')}</tr>")
    rows.append(f"<tr><th>success rate</th>"
                f"{_cell(summary['success_rate'], 'share', cell_id='m-success_rate')}</tr>")
    rows.append(f"<tr><th>cost per success</th>"
                f"{_cell(summary['cost_per_success'], 'cost', cell_id='m-cost_per_success')}</tr>")
    rows.append(
        f"<tr><th>tokens per success</th>"
        f"{_cell(summary['tokens_per_success'], 'float', cell_id='m-tokens_per_success')}</tr>")

    averages = [
        f"<tr><th>{_esc(label)}</th>"
        f"{_cell(summary['avg_per_task'][key], kind, cell_id=f'm-avg-{key}')}</tr>"
        for key, label, kind in AVG_ROWS
    ]

    growth = summary.get("context_growth") or {}
    growth_rows = [
        f"<tr><th>{_esc(role)}</th>"
        f"{_cell(growth.get(role), 'float', cell_id=f'm-growth-{role}')}</tr>"
        for role in metrics.PROMPT_ROLE_KEYS
    ]
    top_turn = summary.get("top_turn")
    top_turn_line = (
        "no LLM call was recorded" if not top_turn else
        f"{_esc(top_turn.get('scenario'))} repeat {_esc(top_turn.get('repeat'))}, "
        f"turn {_esc(top_turn.get('turn'))}, round {_esc(top_turn.get('round'))} — "
        f"{_esc(top_turn.get('prompt_tokens'))} prompt tokens"
    )

    return (
        '<section id="aggregates">\n'
        "<h2>Aggregates</h2>\n"
        '<p class="sub">Every figure below is the document\'s own '
        "<code>summary</code>, which <code>bench.py check</code> recomputes from the "
        "embedded rows. Live-bot figures live in <code>/stats</code>.</p>\n"
        f'<table><caption>Totals over {_esc(document["summary"]["runs"])} runs</caption>'
        f"<tbody>\n{_rows(rows)}\n</tbody></table>\n"
        f'<h3>Per task (per executed run)</h3>\n<table><tbody>\n{_rows(averages)}\n'
        "</tbody></table>\n"
        f"<h3>Context growth, chars per run</h3>\n<table><tbody>\n{_rows(growth_rows)}\n"
        "</tbody></table>\n"
        f'<h3>Most expensive turn</h3>\n<p class="meta" id="m-top_turn">{top_turn_line}</p>\n'
        "</section>"
    )


def _cache(document: dict) -> str:
    summary = document["summary"]
    share = metrics.prefix_share(document)
    cache_note = ("the provider reported no cached tokens"
                  if summary["cache_hit_rate"] is None else "cached ÷ prompt tokens")
    rows = [
        f"<tr><th>cache hit rate</th>"
        f"{_cell(summary['cache_hit_rate'], 'share', cell_id='m-cache_hit_rate')}"
        f"<td>{cache_note}</td></tr>",
        f"<tr><th>re-sent share</th>"
        f"{_cell(summary['resent_share'], 'share', cell_id='m-resent_share')}"
        "<td>prompt tokens already sent in an earlier call of the same conversation</td></tr>",
        f"<tr><th>prefix share</th>{_cell(share, 'share', cell_id='m-prefix_share')}"
        "<td>prefix tokens × calls ÷ prompt tokens</td></tr>",
        f"<tr><th>re-sent tokens</th>"
        f"{_cell(summary['totals']['resent_tokens'], 'int', cell_id='m-cache-resent_tokens')}"
        "<td>absolute</td></tr>",
        f"<tr><th>new tokens</th>"
        f"{_cell(summary['totals']['new_tokens'], 'int', cell_id='m-cache-new_tokens')}"
        "<td>absolute</td></tr>",
    ]
    return ('<section id="cache">\n<h2>Cache and re-sent context</h2>\n'
            f"<table><tbody>\n{_rows(rows)}\n</tbody></table>\n</section>")


def _bar(value: int, largest: int, css: str = "") -> str:
    width = 0.0 if largest <= 0 else min(100.0, value / largest * 100)
    return (f'<div class="bar{css}"><span style="width:{width:.1f}%"></span></div>')


def _tools(document: dict) -> str:
    breakdown = tool_breakdown(document["runs"])
    if not breakdown:
        return ('<section id="tools">\n<h2>Tools</h2>\n'
                '<p class="sub">No tool call was recorded in this run.</p>\n</section>')
    max_tokens = max(item["output_tokens_est"] for item in breakdown)
    max_time = max(item["duration_ms"] for item in breakdown)
    total_tokens = sum(item["output_tokens_est"] for item in breakdown)
    total_time = sum(item["duration_ms"] for item in breakdown)
    rows = []
    for item in breakdown:
        name = item["name"]
        ident = f"m-tool-{name}"
        token_share = item["output_tokens_est"] / total_tokens if total_tokens else 0.0
        time_share = item["duration_ms"] / total_time if total_time else 0.0
        rows.append(
            f"<tr><th>{_esc(name)}</th>"
            f'{_cell(item["calls"], "int", cell_id=ident + "-calls")}'
            f'{_cell(item["output_tokens_est"], "int", cell_id=ident + "-tokens")}'
            f'<td>{_bar(item["output_tokens_est"], max_tokens)}</td>'
            f'<td class="num">{fmt(token_share, "share")}</td>'
            f'{_cell(item["duration_ms"], "int", cell_id=ident + "-ms")}'
            f'<td>{_bar(item["duration_ms"], max_time, " time")}</td>'
            f'<td class="num">{fmt(time_share, "share")}</td></tr>'
        )
    head = ("<tr><th>tool</th><th class=\"num\">calls</th><th class=\"num\">output tokens</th>"
            "<th>by output</th><th class=\"num\">share</th><th class=\"num\">time, ms</th>"
            "<th>by time</th><th class=\"num\">share</th></tr>")
    return ('<section id="tools">\n<h2>Tools</h2>\n'
            '<p class="sub">Every tool call of every run, by output tokens and by wall '
            "time.</p>\n"
            f"<table><thead>{head}</thead><tbody>\n{_rows(rows)}\n</tbody></table>\n</section>")


def _timeline(document: dict) -> str:
    grouped = scenario_runs(document)
    if not grouped:
        return ('<section id="timeline">\n<h2>Timeline</h2>\n'
                '<p class="sub">No run was executed.</p>\n</section>')
    blocks = []
    for scenario in sorted(grouped):
        runs = grouped[scenario]
        key = median_key(runs)
        run = median_run(runs)
        if run is None:                       # unreachable: a group is never empty
            continue
        growth = metrics.context_growth(run["llm_calls"])
        verdict = ('<span class="ok">success</span>' if run["success"]
                   else f'<span class="bad">{_esc(run["failure"])}</span>')
        rows = []
        for entry in timeline_rows(run):
            tools = ", ".join(entry["tools"]) or "—"
            marker = ("" if entry["error_kind"] is None
                      else f' <span class="bad">{_esc(entry["error_kind"])}</span>')
            rows.append(
                f'<tr><td class="num">{_esc(entry["round"])}</td>'
                f'<td><span class="tag">{_esc(entry["purpose"])}</span>{marker}</td>'
                f'{_cell(entry["prompt_tokens"], "int")}'
                f'{_cell(entry["completion_tokens"], "int")}'
                f'{_cell(entry["cached_tokens"], "int")}'
                f'{_cell(entry["latency_ms"], "int")}'
                f"<td>{_esc(tools)}</td></tr>"
            )
        head = ("<tr><th class=\"num\">round</th><th>purpose</th><th class=\"num\">prompt</th>"
                "<th class=\"num\">completion</th><th class=\"num\">cached</th>"
                "<th class=\"num\">latency, ms</th><th>tools called</th></tr>")
        growth_line = ", ".join(
            f"{role} {growth.get(role, 0.0):+.0f}" for role in metrics.PROMPT_ROLE_KEYS)
        ranked = "cost" if key == MEDIAN_KEY_COST else "prompt + completion tokens"
        blocks.append(
            f'<h3 id="timeline-{_esc(scenario)}">{_esc(scenario)} — repeat '
            f'<span id="median-{_esc(scenario)}">{_esc(run["repeat"])}</span>, {verdict}</h3>\n'
            f'<p class="meta">median of {len(runs)} run(s), ranked by {ranked}; '
            f'cost {fmt(run["totals"]["cost_usd"], "cost")}, '
            f'{run["totals"]["prompt_tokens"] + run["totals"]["completion_tokens"]} tokens, '
            f'wall {run["totals"]["wall_ms"]} ms · context growth {_esc(growth_line)}</p>\n'
            f"<table><thead>{head}</thead><tbody>\n{_rows(rows)}\n</tbody></table>"
        )
    return ('<section id="timeline">\n<h2>Timeline — the median run of every scenario</h2>\n'
            '<p class="sub">A scenario\'s runs are sorted ascending by cost (by prompt + '
            "completion tokens when any repeat reported no cost), ties keep execution "
            "order, and the run at index <code>n // 2</code> is shown.</p>\n"
            + "\n".join(blocks) + "\n</section>")


def _success_ratio(entry: dict | None) -> str:
    """`k/n` for one scenario of one file; `—` when that file never ran it."""
    if not entry:
        return "—"
    return f"{entry['success']}/{entry['of']}"


def _compare(document: dict, other: dict) -> str:
    left, right = document["summary"], other["summary"]
    left_tag = _esc(document["meta"].get("tag"))
    right_tag = _esc(other["meta"].get("tag"))
    head = (f'<tr><th>metric</th><th class="num">{left_tag}</th><th class="num">{right_tag}</th>'
            '<th class="num">Δ</th><th class="num">Δ %</th></tr>')

    rows = []
    for key, label, kind in TOTAL_ROWS:
        new, old = right["totals"][key], left["totals"][key]
        absolute, relative = _delta(new, old, kind)
        rows.append(f"<tr><th>{_esc(label)}</th>{_cell(old, kind)}{_cell(new, kind)}"
                    f'<td class="num">{_esc(absolute)}</td>'
                    f'<td class="num">{_esc(relative)}</td></tr>')
    for key, label, kind in (("success_rate", "success rate", "share"),
                             ("cost_per_success", "cost per success", "cost"),
                             ("tokens_per_success", "tokens per success", "float"),
                             ("resent_share", "re-sent share", "share"),
                             ("cache_hit_rate", "cache hit rate", "share")):
        new, old = right.get(key), left.get(key)
        absolute, relative = _delta(new, old, kind)
        rows.append(f"<tr><th>{_esc(label)}</th>{_cell(old, kind)}{_cell(new, kind)}"
                    f'<td class="num">{_esc(absolute)}</td>'
                    f'<td class="num">{_esc(relative)}</td></tr>')
    for key, label, kind in AVG_ROWS:
        new, old = right["avg_per_task"][key], left["avg_per_task"][key]
        absolute, relative = _delta(new, old, kind)
        rows.append(f"<tr><th>{_esc(label)} (avg)</th>{_cell(old, kind)}{_cell(new, kind)}"
                    f'<td class="num">{_esc(absolute)}</td>'
                    f'<td class="num">{_esc(relative)}</td></tr>')

    scenarios = sorted(set(left["per_scenario"]) | set(right["per_scenario"]))
    scenario_rows = []
    for scenario in scenarios:
        here = left["per_scenario"].get(scenario)
        there = right["per_scenario"].get(scenario)
        cells = [f"<th>{_esc(scenario)}</th>"]
        cells.append(f"<td>{_esc(_success_ratio(here))} → {_esc(_success_ratio(there))}</td>")
        for key, kind in SCENARIO_DELTA_KEYS:
            old = None if not here else here["median"].get(key)
            new = None if not there else there["median"].get(key)
            _, relative = _delta(new, old, kind)
            cells.append(f"{_cell(old, kind)}{_cell(new, kind)}"
                         f'<td class="num">{_esc(relative)}</td>')
        scenario_rows.append(f"<tr>{''.join(cells)}</tr>")
    scenario_head = "<tr><th>scenario</th><th>success</th>" + "".join(
        f'<th class="num" colspan="3">{_esc(key)}</th>' for key, _ in SCENARIO_DELTA_KEYS
    ) + "</tr>"

    flags_left = document["meta"].get("env_flags") or {}
    flags_right = other["meta"].get("env_flags") or {}
    differing = [name for name in sorted(set(flags_left) | set(flags_right))
                 if flags_left.get(name) != flags_right.get(name)]
    treatment = ", ".join(
        f"{name}: {flags_left.get(name)!r} → {flags_right.get(name)!r}" for name in differing
    ) or "the two files declare the same env flags"
    same_config = document["meta"].get("config_sha256") == other["meta"].get("config_sha256")

    return (
        '<section id="compare">\n<h2>Compare</h2>\n'
        f'<p class="sub">Δ is <b>{right_tag}</b> minus <b>{left_tag}</b>; per-scenario '
        "figures are the medians the file itself carries. This section describes the two "
        "files, it does not gate them — <code>bench.py report --gate</code> does.</p>\n"
        f'<p class="meta">treatment: {_esc(treatment)}<br>config hash: '
        f"{'identical' if same_config else 'different'}</p>\n"
        f"<table><thead>{head}</thead><tbody>\n{_rows(rows)}\n</tbody></table>\n"
        "<h3>Per scenario — median of each run total, "
        f"{left_tag} → {right_tag} → Δ %</h3>\n"
        f"<table><thead>{scenario_head}</thead><tbody>\n{_rows(scenario_rows)}\n"
        "</tbody></table>\n</section>"
    )


def render(document: dict, compare: dict | None = None) -> str:
    """The whole page as one string: no external stylesheet, no script, no
    image — the grep of REQ-V13-DSH-01 finds neither a `<script src` nor an
    `http` URL in a `src=`/`href=` attribute because none is written."""
    sections = [
        _aggregates(document),
        _cache(document),
        _tools(document),
        _timeline(document),
    ]
    if compare is not None:
        sections.append(_compare(document, compare))
    title = f"Benchmark dashboard — {document['meta'].get('tag', 'bench')}"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(title)}</title>\n<style>{STYLE}</style>\n</head>\n<body>\n<main>\n"
        f"{_header(document, compare)}\n"
        + "\n".join(sections)
        + "\n<footer>Generated by devtools/dashboard.py from benchmark JSON "
          "(spec-v1.3 section 8). Static file: no script, no network.</footer>\n"
          "</main>\n</body>\n</html>\n"
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dashboard.py",
        description="Render a static HTML dashboard from a benchmark JSON document.",
    )
    parser.add_argument("bench", help="the benchmark document (bench_schema 1)")
    parser.add_argument("--compare", default=None,
                        help="a second document; adds the #compare section")
    parser.add_argument("--out", required=True, help="the HTML file to write")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        document = load_document(Path(arguments.bench))
        other = load_document(Path(arguments.compare)) if arguments.compare else None
    except ValueError as exc:
        print(f"dashboard: {exc}", file=sys.stderr)
        return EXIT_ERROR

    out = Path(arguments.out)
    try:
        if out.parent and not out.parent.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(document, other), encoding="utf-8")
    except OSError as exc:
        print(f"dashboard: {out}: {exc.strerror or exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"dashboard: {out} ({out.stat().st_size} bytes)")
    return EXIT_OK


if __name__ == "__main__":       # pragma: no cover - exercised through the CLI test
    raise SystemExit(main())
