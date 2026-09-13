"""The static benchmark dashboard (spec-v1.3 section 8, REQ-V13-DSH-01…02).

`dashboard.py <bench.json> [--compare other.json] --out <file.html>` turns one
benchmark document (`bench_schema: 1` or `2`, section 7.4) into a single
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

REQ-V160-DSH-05: the render half (page assembly, tables, charts) moved to
top-level `dashboard_render.py` — the one module in the repository that emits
HTML (REQ-V160-DSH-01). This module keeps its data functions
(`load_document`, `scenario_runs`, `median_run`, `timeline_rows`,
`tool_breakdown`) unchanged and calls into `dashboard_render` for everything
that produces markup; it holds no HTML literal of its own. `dashboard_render`
never imports this module back (REQ-V160-TREE-03).
"""

from __future__ import annotations

import argparse
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

import dashboard_render  # noqa: E402
import metrics  # noqa: E402

# REQ-V160-BEN-03: `load_document` additionally accepts schema 2 (the spans-
# carrying shape T11 adds) so a document written by that release isn't
# rejected outright; wiring the spans data through is T11's job, not this
# task's. Superseded the single `BENCH_SCHEMA` constant this module used to
# compare against -- `devtools/bench.py`'s own `BENCH_SCHEMA` is unrelated
# and unaffected.
ACCEPTED_BENCH_SCHEMAS = frozenset({1, 2})

EXIT_OK = 0
EXIT_ERROR = 1

# Re-exports: existing callers (this project's own tests included) reach
# these through `dashboard.<name>` -- REQ-V160-DSH-05 keeps that surface.
TOTAL_ROWS = dashboard_render.TOTAL_ROWS
AVG_ROWS = dashboard_render.AVG_ROWS
fmt = dashboard_render.fmt
_esc = dashboard_render.esc

MEDIAN_KEY_COST = "cost_usd"
MEDIAN_KEY_TOKENS = "tokens"


# --------------------------------------------------------------------------
# document access -- unchanged data functions (REQ-V160-DSH-05 pins these in
# place: `load_document`, `scenario_runs`, `median_run`, `timeline_rows`,
# `tool_breakdown`)
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
    # v1.9.3 T3: the three type-check raises below keep ValueError, not
    # TypeError (noqa: TRY004 on each) -- this function's own docstring
    # and REQ-V160-DSH-05 pin its contract ("the benchmark file, or
    # ValueError with a one-line reason"), and main() below catches
    # `except ValueError` specifically to print a clean CLI error instead
    # of a traceback.
    if not isinstance(document, dict):
        raise ValueError(f"{path}: the document is not an object")  # noqa: TRY004
    if document.get("bench_schema") not in ACCEPTED_BENCH_SCHEMAS:
        expected = sorted(ACCEPTED_BENCH_SCHEMAS)
        raise ValueError(
            f"{path}: bench_schema {document.get('bench_schema')!r}, expected one of {expected}"
        )
    for key in ("meta", "summary"):
        if not isinstance(document.get(key), dict):
            raise ValueError(f"{path}: {key} is missing or not an object")  # noqa: TRY004
    if not isinstance(document.get("runs"), list):
        raise ValueError(f"{path}: runs is missing or not an array")  # noqa: TRY004
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
# glue: pre-computes the data `dashboard_render`'s relocated render half
# needs, so that render half never calls back into this module's data
# functions (REQ-V160-DSH-01's import direction). No HTML is built here.
# --------------------------------------------------------------------------


def _timeline_blocks(document: dict) -> list[dict]:
    """One dict per scenario -- the median run, its rank label, timeline rows
    and context growth -- everything `dashboard_render._timeline` needs to
    format."""
    grouped = scenario_runs(document)
    blocks = []
    for scenario in sorted(grouped):
        runs = grouped[scenario]
        key = median_key(runs)
        run = median_run(runs)
        if run is None:  # unreachable: a group is never empty
            continue
        blocks.append(
            {
                "scenario": scenario,
                "run": run,
                "runs_count": len(runs),
                "ranked": "cost" if key == MEDIAN_KEY_COST else "prompt + completion tokens",
                "rows": timeline_rows(run),
                "growth": metrics.context_growth(run["llm_calls"]),
            }
        )
    return blocks


def render(document: dict, compare: dict | None = None) -> str:
    """The whole page as one string, produced by `dashboard_render.render`
    (REQ-V160-DSH-01) — this function only gathers this module's own data
    (`tool_breakdown`, the per-scenario timeline blocks) and hands it over;
    it holds no HTML literal of its own."""
    breakdown = tool_breakdown(document["runs"])
    blocks = _timeline_blocks(document)
    return dashboard_render.render(document, compare, breakdown=breakdown, blocks=blocks)


def usage_rows_from_document(document: dict) -> list[metrics.UsageRow]:
    """Adapts a benchmark document's `summary.totals` into a single-row
    `UsageRow` list, named after the document's own tag: a benchmark file has
    no natural multi-group breakdown (REQ-V160-MET-01's per-provider grouping
    needs a live database), so its usage band is one row wide."""
    summary = document["summary"]
    totals = summary["totals"]
    tag = document["meta"].get("tag") or "(bench)"
    pricing = document["meta"].get("pricing") or {}
    return [
        metrics.UsageRow(
            provider=document["meta"].get("provider"),
            model=document["meta"].get("model"),
            purpose=None,
            scenario=None,
            day=None,
            key=str(tag)[:128],
            calls=totals["calls"],
            errors=totals["failed_calls"],
            input_tokens=totals["prompt_tokens"] or 0,
            output_tokens=totals["completion_tokens"] or 0,
            cached_tokens=totals["cached_tokens"] or 0,
            reasoning_tokens=totals["reasoning_tokens"] or 0,
            cost_usd=totals["cost_usd"] or 0.0,
            cost_basis=pricing.get("basis"),
            cache_hit_share=summary.get("cache_hit_rate"),
            reasoning_share=None,
        )
    ]


def usage_band(document: dict) -> str:
    """The bench report's usage table, over the single adapted row of
    `usage_rows_from_document`. Calls the exact same `dashboard_render.
    usage_section` the live dashboard server (T6) will use, so a fixture
    rendered through either caller is byte-identical (REQ-V160-DSH-01,
    `T-V160-DSH-02`). Not wired into `render()`'s output: `_aggregates`'s
    totals table already covers this ground for the bench report, and
    REQ-V160-DSH-05 pins `render()`'s bytes to the pre-refactor page."""
    rows = usage_rows_from_document(document)
    return dashboard_render.usage_section(rows, group="model", totals=rows[0])


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dashboard.py",
        description="Render a static HTML dashboard from a benchmark JSON document.",
    )
    parser.add_argument("bench", help="the benchmark document (bench_schema 1 or 2)")
    parser.add_argument(
        "--compare", default=None, help="a second document; adds the #compare section"
    )
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


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI test
    raise SystemExit(main())
