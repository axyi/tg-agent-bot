"""The one HTML-emitting module in the repository (REQ-V160-DSH-01).

Every function here is pure: data in, `str` out, no I/O, no database handle,
no `Path`, no `print`. `dashboard_server.py` (T6) will call these for the live
pages; `devtools/dashboard.py` calls them for the static benchmark report
(REQ-V160-DSH-05) -- `devtools/dashboard.py` imports this module, never the
reverse (REQ-V160-TREE-03). `error_page`, `response_too_large_page` and
`invalid_host_page` are the only source of every HTML error body anywhere
(400/404/405/500/503); no other module holds an HTML literal of its own for
an error.

Offline, no script, no external anything (REQ-V160-DSH-02): a single inline
`<style>` block, no `<script>`, no inline event handler, no external
stylesheet, image, font or CDN. Charts are server-side inline `<svg>` built
as text (REQ-V160-DSH-04). Every value reaching HTML or SVG text goes
through `esc()` (REQ-V160-DSH-06) -- no `str.format`, f-string or
concatenation may place caller data into markup without it.

`served_span()` is the one gate every span crosses on its way out
(REQ-V160-DSH-09): it drops every attribute key outside
`SERVED_SPAN_ATTRIBUTE_KEYS`, truncates the strings it keeps to
REQ-V160-API-05's maxima, and never reads `status_message` -- the field does
not exist on `ServedSpan`, so nothing downstream can reach it even by
accident.

The second half of this module is the benchmark report's own renderer,
relocated verbatim from `devtools/dashboard.py` (REQ-V160-DSH-05): `fmt`,
`_header`, `_aggregates`, `_cache`, `_bar`, `_tools`, `_timeline`, `_compare`
and `render`. `render()`'s output is byte-for-byte what the pre-refactor
`devtools/dashboard.py` produced for the same input -- `_tools`/`_timeline`
now take pre-computed data (`breakdown`, `blocks`) instead of calling back
into `devtools/dashboard.py`'s own data functions (`tool_breakdown`,
`scenario_runs`, `median_key`, `median_run`, `timeline_rows`), which stay
there and must never be imported from here.
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

import metrics
import tracing

# ----------------------------------------------------------------------------
# escaping (REQ-V160-DSH-06) -- the one gate every string crosses
# ----------------------------------------------------------------------------


def esc(value: Any) -> str:
    """`html.escape(str(value), quote=True)` with `None` rendering as `""` --
    the pre-existing `_esc` semantics of `devtools/dashboard.py:259-260`."""
    return html.escape("" if value is None else str(value), quote=True)


def meta_line(text: Any) -> str:
    """One `<p class="meta">...</p>` fragment, escaped -- the generic form of
    the `<p class="meta">` pattern already used throughout this module (e.g.
    `tool_health_section`, `compare_section`). Added at T14
    (REQ-V160-DSH-01 review finding) so `dashboard_server.py`'s `/` page
    footer line (db basename + schema version) no longer needs to hold that
    one HTML literal itself."""
    return f'<p class="meta">{esc(text)}</p>'


# ----------------------------------------------------------------------------
# the named colour palette (REQ-V160-DSH-04) -- every chart also encodes its
# information in text, so removing colour never loses information
# ----------------------------------------------------------------------------

# REQ-V160-API-05: a safety bound for a malformed database, never a cap a
# legitimate trace can reach (the agent's own limits bound a legitimate
# trace at 35 spans -- T6 asserts 35 <= this constant).
MAX_SPANS_PER_TRACE = 64

PALETTE: dict[str, str] = {
    "kind_internal": "#5f6873",
    "kind_client": "#1f5fb0",
    "error_outline": "#b23636",
    "bar": "#1f5fb0",
    "bar_track": "#eef0f2",
}


# ----------------------------------------------------------------------------
# the page shell, shared by the live server and the static bench report
# ----------------------------------------------------------------------------

STYLE = """
:root { color-scheme: light;
        --ink: #16181c; --ground: #eef0f2; --plate: #ffffff; --rule: #ccd2d8;
        --dim: #5f6873; --signal: #1f5fb0; }
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem 1.5rem 4rem; background: var(--ground); color: var(--ink);
       font: 13px/1.5 ui-sans-serif, system-ui, "Segoe UI", Roboto, Helvetica, Arial,
       sans-serif; }
main { max-width: 68rem; margin: 0 auto; }
h1 { font-size: 22px; line-height: 1.25; font-weight: 600; letter-spacing: -0.01em;
     margin: 0 0 .75rem; padding-bottom: .5rem; border-bottom: 2px solid var(--ink); }
h2 { font-size: 16px; line-height: 1.3; font-weight: 600; margin: 2.5rem 0 .75rem;
     display: flex; align-items: baseline; gap: .75rem; }
h2::after { content: ""; flex: 1 1 auto; height: 1px; background: var(--rule);
            align-self: center; }
h3 { font-size: 13px; line-height: 1.35; font-weight: 600; margin: 1.5rem 0 .5rem; }
p.sub { margin: 0 0 1rem; color: var(--dim); font-size: 12px; line-height: 1.4; }
nav { margin: 1rem 0 0; font-size: 12px; line-height: 1.4; }
nav a { color: var(--signal); text-decoration: none; margin-right: 1rem; }
nav a:hover { text-decoration: underline; }
section { background: var(--plate); border: 1px solid var(--rule); border-radius: 2px;
          padding: 0 1rem 1rem; margin-top: 1rem; }
table { border-collapse: collapse; width: 100%; font-size: 13px; line-height: 1.5; }
caption { text-align: left; font-weight: 600; padding: .5rem 0; }
th, td { padding: .35rem .6rem; border-bottom: 1px solid var(--rule); text-align: left;
         vertical-align: top; }
th { font-weight: 600; color: var(--dim); font-size: 12px; line-height: 1.4;
     text-transform: none; letter-spacing: 0; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tr:last-child td { border-bottom: none; }
.bar { background: var(--ground); height: .6rem; min-width: 6rem; }
.bar span { display: block; height: 100%; background: var(--signal); }
.reading-strip { display: flex; align-items: flex-end; gap: 1.5rem;
                  margin: 0 0 1rem; padding: .75rem 0 1rem; }
.reading-cell { display: flex; flex-direction: column; gap: .2rem;
                padding-left: 1.5rem; border-left: 1px solid var(--rule); }
.reading-cell:first-child { padding-left: 0; border-left: none; }
.reading-label { font-size: 12px; line-height: 1.4; color: var(--dim); }
.reading-value { font-size: 22px; line-height: 1.25; font-weight: 600;
                  font-variant-numeric: tabular-nums; }
.tag { display: inline-block; padding: .05rem .45rem; border-radius: 2px;
       font-size: 12px; border: 1px solid var(--rule); color: var(--dim); }
.ok { color: #1c7a4a; }
.bad { color: #b23636; }
.warn { background: var(--ground); border: 1px solid var(--rule); border-radius: 2px;
        padding: .6rem .9rem; margin: 1rem 0; font-size: 13px; color: #b23636; }
.meta { font-size: 12px; line-height: 1.4; color: var(--dim); }
.na { color: var(--dim); }
.turn-row { display: flex; gap: 1rem; padding: .6rem 0; border-bottom: 1px solid var(--rule); }
.turn-row:last-child { border-bottom: none; }
.rail { flex: 0 0 7rem; display: flex; flex-direction: column; gap: .15rem;
        color: var(--dim); font-size: 12px; line-height: 1.4; }
.rail .num { font-variant-numeric: tabular-nums; }
.msg { flex: 1 1 auto; white-space: pre-wrap; word-break: break-word; }
footer { margin-top: 3rem; color: var(--dim); font-size: 12px; line-height: 1.4; }
"""


def page(title: str, *, nav: Sequence[tuple[str, str]], body: str, generated_at: str) -> str:
    """The full document for a live dashboard page: one inline `<style>`
    block (the same `STYLE` the static bench report uses), a nav of
    `(label, href)` pairs, the pre-rendered `body`, and a footer naming the
    generation timestamp -- no script, no external resource of any kind
    (REQ-V160-DSH-02)."""
    nav_html = "".join(f'<a href="{esc(href)}">{esc(label)}</a>' for label, href in nav)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n<style>{STYLE}</style>\n</head>\n<body>\n<main>\n"
        f"<h1>{esc(title)}</h1>\n<nav>{nav_html}</nav>\n"
        f"{body}\n"
        f"<footer>Generated {esc(generated_at)}</footer>\n"
        "</main>\n</body>\n</html>\n"
    )


def error_page(message: str) -> str:
    """Every HTML error body in the repository wraps this one fixed string
    (REQ-V160-DSH-01): `dashboard_server.py` holds no HTML literal of its
    own for a 400/404/405/500/503."""
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Error</title>\n<style>{STYLE}</style>\n</head>\n<body>\n<main>\n"
        f"<h1>Error</h1>\n<p>{esc(message)}</p>\n</main>\n</body>\n</html>\n"
    )


def response_too_large_page() -> str:
    """REQ-V160-API-05: the fixed, content-free body for a response that
    would exceed 2 MiB -- no fragment of the real body, size or path."""
    return error_page("response too large")


def invalid_host_page() -> str:
    """REQ-V160-SRV-11: the fixed body for a request whose Host header is
    not the server's own bind address."""
    return error_page("invalid host")


# ----------------------------------------------------------------------------
# REQ-V160-DSH-09: the serving DTO -- a `spans` row is never served
# ----------------------------------------------------------------------------

SERVED_SPAN_ATTRIBUTE_KEYS: frozenset[str] = frozenset(
    tracing.ATTRIBUTE_KEYS
    - tracing.CONTENT_ATTRIBUTE_KEYS
    - {"gen_ai.tool.call.id", "tg_agent.tool.fingerprint"}
)

# REQ-V160-API-05's length maxima.
_NAME_MAX_CHARS = 128
_ATTR_VALUE_MAX_CHARS = 256

# The attribute keys that carry a name (tool/model/provider/agent) get the
# tighter 128 cap; every other served attribute value gets 256.
_NAME_LIKE_ATTRIBUTE_KEYS = frozenset(
    {
        "gen_ai.tool.name",
        "gen_ai.request.model",
        "gen_ai.response.model",
        "gen_ai.provider.name",
        "gen_ai.agent.name",
    }
)


def _truncate(value: str, limit: int) -> str:
    """A string over `limit` characters is cut to `limit - 1` characters plus
    a trailing `…`, so the result's own length is exactly `limit`."""
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _truncate_attribute_value(key: str, value: object) -> object:
    """Strings are truncated to their key's maximum; `gen_ai.response.finish_reasons`
    is a `list[str]` (REQ-V160-TRC-03's own validation), never `str()`-ed
    whole -- each element is truncated instead. Every other type (int, float,
    bool, None) passes through unchanged."""
    limit = _NAME_MAX_CHARS if key in _NAME_LIKE_ATTRIBUTE_KEYS else _ATTR_VALUE_MAX_CHARS
    if isinstance(value, str):
        return _truncate(value, limit)
    if isinstance(value, list):
        return [_truncate(item, limit) if isinstance(item, str) else item for item in value]
    return value


@dataclass(frozen=True)
class ServedSpan:
    span_id: str
    parent_span_id: str | None
    name: str
    kind: str
    ts: str
    start_ns: int
    duration_ms: int
    status: str
    conv_id: int | None
    turn_id: int | None
    attributes: dict[str, object]


def served_span(row_or_mapping: Any) -> ServedSpan:
    """The ONE constructor onto the wire DTO (REQ-V160-DSH-09).

    `row_or_mapping` is a `sqlite3.Row`-like object (the `spans` table's
    columns, `storage.SPAN_COLUMNS`) or a plain dict from a bench document
    (REQ-V160-BEN-04: `attributes` already parsed, not `attributes_json`).
    `.keys()` works the same way on both, which is how the two shapes are
    told apart -- a `sqlite3.Row`'s `in` operator tests *values*, not column
    names, so `.keys()` is the only reliable test.

    Every attribute key outside `SERVED_SPAN_ATTRIBUTE_KEYS` is dropped
    rather than raising; every value kept is truncated to REQ-V160-API-05's
    maxima. `status_message` is never read -- the field does not exist on
    `ServedSpan`, so no caller of this function can reach it even by
    accident.
    """
    keys = row_or_mapping.keys()
    if "attributes_json" in keys:
        raw = row_or_mapping["attributes_json"]
        parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
    elif "attributes" in keys:
        parsed = row_or_mapping["attributes"] or {}
    else:
        parsed = {}

    attributes = {
        key: _truncate_attribute_value(key, value)
        for key, value in parsed.items()
        if key in SERVED_SPAN_ATTRIBUTE_KEYS
    }

    parent_span_id = row_or_mapping["parent_span_id"]
    conv_id = row_or_mapping["conv_id"]
    turn_id = row_or_mapping["turn_id"]

    return ServedSpan(
        span_id=str(row_or_mapping["span_id"]),
        parent_span_id=None if parent_span_id is None else str(parent_span_id),
        name=_truncate(str(row_or_mapping["name"]), _NAME_MAX_CHARS),
        kind=str(row_or_mapping["kind"]),
        ts=str(row_or_mapping["ts"]),
        start_ns=int(row_or_mapping["start_ns"]),
        duration_ms=int(row_or_mapping["duration_ms"]),
        status=str(row_or_mapping["status"]),
        conv_id=None if conv_id is None else int(conv_id),
        turn_id=None if turn_id is None else int(turn_id),
        attributes=attributes,
    )


def _check_served_spans(spans: Sequence[Any]) -> None:
    """`trace_tree_section` and `gantt_svg` accept `ServedSpan` only
    (REQ-V160-DSH-09) -- a raw `sqlite3.Row` or mapping raises `TypeError`
    rather than silently rendering an unfiltered span."""
    for span in spans:
        if not isinstance(span, ServedSpan):
            raise TypeError(
                f"expected a sequence of ServedSpan, got {type(span).__name__}; "
                "build one with dashboard_render.served_span() first"
            )


# ----------------------------------------------------------------------------
# usage and tool-health tables (REQ-V160-DSH-03)
# ----------------------------------------------------------------------------


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Reads `name` off a `Mapping` or an object (a dataclass instance,
    typically) the same way -- callers may hand either shape as `totals`/
    `summary`."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _share_cell(value: float | None) -> str:
    """An explicit `—` where a share is `None`, never a misleading `0 %`
    (REQ-V160-DSH-03)."""
    return "—" if value is None else f"{value * 100:.2f}%"


# ----------------------------------------------------------------------------
# declared column specs (REQ-V180-DSH-03): `class="num"` is a property of the
# COLUMN, declared here as an ordered `(heading, kind)` sequence, never
# inferred from a cell's own content. `_th_cell`/`_td_cell`/`_row_th_cell` are
# the only three places that decide whether a cell carries `class="num"`, and
# all three decide it from the `kind` argument alone -- a placeholder cell
# (e.g. `_share_cell`'s `—`) is passed through the same `kind` as every other
# cell of its column, so it keeps the class.
# ----------------------------------------------------------------------------

ColumnSpec = tuple[str, str]  # (heading, "num" | "text")


def _num_class(kind: str) -> str:
    if kind not in ("num", "text"):
        raise ValueError(f"unknown column kind: {kind!r}")
    return ' class="num"' if kind == "num" else ""


def _th_cell(heading: Any, kind: str) -> str:
    return f"<th{_num_class(kind)}>{esc(heading)}</th>"


def _td_cell(inner_html: str, kind: str) -> str:
    return f"<td{_num_class(kind)}>{inner_html}</td>"


def _row_th_cell(inner_html: str, kind: str) -> str:
    """A body row's own `<th>` row-header cell (`usage_section`,
    `tool_health_section`) -- `inner_html` is already escaped/rendered by the
    caller, the same convention `_td_cell` uses, unlike `_th_cell` (which
    escapes a raw heading for `_head_row`)."""
    return f"<th{_num_class(kind)}>{inner_html}</th>"


def _head_row(spec: Sequence[ColumnSpec]) -> str:
    return "<tr>" + "".join(_th_cell(heading, kind) for heading, kind in spec) + "</tr>"


# The row-label column (the usage table's `group` heading, e.g. "model") is
# caller-supplied and always `"text"` -- it is declared inline where the
# heading text is built, not here.
USAGE_COLUMNS: tuple[ColumnSpec, ...] = (
    ("calls", "num"),
    ("errors", "num"),
    ("input tokens", "num"),
    ("output tokens", "num"),
    ("cached", "num"),
    ("reasoning", "num"),
    ("cost", "num"),
    ("cost basis", "text"),
    ("cache-hit share", "num"),
    ("reasoning share", "num"),
)


def _usage_row_html(key: Any, row: Any) -> str:
    cost = _field(row, "cost_usd", 0.0) or 0.0
    values = (
        esc(_field(row, "calls")),
        esc(_field(row, "errors")),
        esc(_field(row, "input_tokens")),
        esc(_field(row, "output_tokens")),
        esc(_field(row, "cached_tokens")),
        esc(_field(row, "reasoning_tokens")),
        esc(f"${float(cost):.6f}"),
        esc(_field(row, "cost_basis")),
        _share_cell(_field(row, "cache_hit_share")),
        _share_cell(_field(row, "reasoning_share")),
    )
    cells = "".join(
        _td_cell(value, kind) for value, (_, kind) in zip(values, USAGE_COLUMNS, strict=True)
    )
    return f"<tr><th>{esc(key)}</th>{cells}</tr>"


def usage_section(rows: Sequence[Any], *, group: str, totals: Any) -> str:
    """The `usage_by`-shaped table plus a totals band above it -- the SAME
    function `devtools/dashboard.py`'s bench report and (T6's)
    `dashboard_server.py` both call, so one fixture renders byte-identically
    through either caller (REQ-V160-DSH-01, `T-V160-DSH-02`)."""
    head = _head_row(((group, "text"), *USAGE_COLUMNS))
    body_rows = "\n".join(_usage_row_html(_field(row, "key", "?"), row) for row in rows)
    if not body_rows:
        colspan = len(USAGE_COLUMNS) + 1
        body_rows = f'<tr><td colspan="{colspan}">No usage recorded for {esc(group)}.</td></tr>'
    totals_table = (
        "<table><caption>Totals</caption><tbody>\n"
        + _usage_row_html("all", totals)
        + "\n</tbody></table>\n"
    )
    group_table = (
        f"<table><caption>By {esc(group)}</caption><thead>{head}</thead><tbody>\n"
        f"{body_rows}\n</tbody></table>\n"
    )
    return f'<section id="usage">\n<h2>Usage</h2>\n{totals_table}{group_table}</section>'


# ----------------------------------------------------------------------------
# the reading strip (REQ-V180-DSH-05): four measured values -- calls, total
# tokens, cost, error rate -- as label-above-number pairs on one baseline,
# split by 1px `--rule` verticals, numbers at 22px/600 tabular. Pure: takes
# already-computed totals, wired into a route by T6, not here.
# ----------------------------------------------------------------------------


def reading_strip_section(*, calls: Any, total_tokens: Any, cost_usd: Any, error_rate: Any) -> str:
    """The `/` page's reading strip: four already-computed totals rendered as
    label-above-number pairs on one baseline. Takes plain values, not a
    `totals`-shaped mapping/dataclass, so a caller that has already reduced
    its own totals to these four numbers (T6) never has to reach back into
    `_field`'s duck-typing."""
    cost = float(cost_usd or 0.0)
    rate = float(error_rate or 0.0)
    items = (
        ("calls", esc(calls)),
        ("total tokens", esc(total_tokens)),
        ("cost", esc(f"${cost:.6f}")),
        ("error rate", esc(f"{rate * 100:.2f}%")),
    )
    cells = "".join(
        f'<div class="reading-cell"><span class="reading-label">{esc(label)}</span>'
        f'<span class="reading-value">{value}</span></div>'
        for label, value in items
    )
    return f'<div class="reading-strip">{cells}</div>'


def error_breakdown_section(breakdown: Any) -> str:
    """The `/` page's error-breakdown fragment (REQ-V160-DSH-03: "the error
    breakdown by finish reason and by error kind"), relocated here from
    `dashboard_server.py` (REQ-V160-DSH-01, T14 review finding): the server
    held this one HTML literal of its own, in violation of "`dashboard_render.py`
    is the only module in the repository that emits HTML." Byte-identical to
    the fragment it replaces -- `esc()` applied to the whole dict, matching
    `ErrorBreakdown.by_finish_reason`/`.by_error_kind`'s existing `str(dict)`
    rendering rather than iterating pairs, so no rendered byte changes."""
    finish_reasons = _field(breakdown, "by_finish_reason")
    error_kinds = _field(breakdown, "by_error_kind")
    return (
        '<section id="errors"><h2>Errors</h2>'
        f"<p>finish reasons: {esc(finish_reasons)}</p>"
        f"<p>error kinds: {esc(error_kinds)}</p></section>"
    )


# The `tool` row-label column comes first and is always `"text"`.
TOOL_HEALTH_COLUMNS: tuple[ColumnSpec, ...] = (
    ("tool", "text"),
    ("calls", "num"),
    ("ok", "num"),
    ("error", "num"),
    ("budget", "num"),
    ("rejected", "num"),
    ("refused_repeat", "num"),
    ("error rate", "num"),
    ("p50 ms", "num"),
    ("p95 ms", "num"),
    ("max repeat run", "num"),
    ("output tokens", "num"),
)


def tool_health_section(rows: Sequence[Any], *, summary: Any) -> str:
    """The `tool_health` table (calls, the five-outcome split, error rate,
    p50/p95 duration, longest consecutive repeat run, output tokens) plus a
    `summary_health` band above it (REQ-V160-DSH-03's `/tools` page)."""
    head = _head_row(TOOL_HEALTH_COLUMNS)
    rows_html = []
    for row in rows:
        error_rate = _field(row, "error_rate", 0.0) or 0.0
        values = (
            esc(_field(row, "tool")),
            esc(_field(row, "calls")),
            esc(_field(row, "ok")),
            esc(_field(row, "error")),
            esc(_field(row, "budget")),
            esc(_field(row, "rejected")),
            esc(_field(row, "refused_repeat")),
            esc(f"{float(error_rate) * 100:.2f}%"),
            esc(_field(row, "p50_ms")),
            esc(_field(row, "p95_ms")),
            esc(_field(row, "max_consecutive_repeats")),
            esc(_field(row, "output_tokens_est")),
        )
        first_value, first_kind = values[0], TOOL_HEALTH_COLUMNS[0][1]
        rest = "".join(
            _td_cell(value, kind)
            for value, (_, kind) in zip(values[1:], TOOL_HEALTH_COLUMNS[1:], strict=True)
        )
        rows_html.append(f"<tr>{_row_th_cell(first_value, first_kind)}{rest}</tr>")
    body = (
        "\n".join(rows_html)
        if rows_html
        else f'<tr><td colspan="{len(TOOL_HEALTH_COLUMNS)}">No tool call recorded.</td></tr>'
    )
    summary_html = (
        '<p class="meta">'
        f"attempts {esc(_field(summary, 'attempts'))}, "
        f"ok {esc(_field(summary, 'ok'))}, "
        f"truncated {esc(_field(summary, 'truncated'))}, "
        f"retried {esc(_field(summary, 'retried'))}, "
        f"failed {esc(_field(summary, 'failed'))}"
        "</p>"
    )
    return (
        '<section id="tool-health">\n<h2>Tool health</h2>\n'
        f"{summary_html}\n"
        f"<table><thead>{head}</thead><tbody>\n{body}\n</tbody></table>\n</section>"
    )


# ----------------------------------------------------------------------------
# the trace list and one trace's tree (REQ-V160-DSH-03)
# ----------------------------------------------------------------------------


def _row_field(row: Any, name: str, default: Any = None) -> Any:
    """A `sqlite3.Row` raises `IndexError` for a missing column, a `dict`
    raises `KeyError` -- both mean "this row-like object doesn't carry that
    field", which `trace_list_section` tolerates (T6 may hand it a narrower
    projection than the full trace summary REQ-V160-DSH-03 describes)."""
    try:
        return row[name]
    except (KeyError, IndexError):
        return default


TRACE_LIST_COLUMNS: tuple[ColumnSpec, ...] = (
    ("trace", "text"),
    ("ts", "text"),
    ("conv", "num"),
    ("turn", "num"),
    ("root", "text"),
    ("scenario", "text"),
    ("spans", "num"),
    ("duration ms", "num"),
    ("status", "text"),
    ("chat", "num"),
    ("execute_tool", "num"),
)


def trace_list_section(traces: Sequence[Any]) -> str:
    """One row per trace, newest first (REQ-V160-DSH-03's `/traces`):
    timestamp, conversation id, turn id, root span name, scenario id when
    present, span count, total duration, status, and the `chat`/
    `execute_tool` child counts. `trace_id` is abbreviated to its first 12
    characters with the full value in the `title` attribute."""
    head = _head_row(TRACE_LIST_COLUMNS)
    rows_html = []
    for row in traces:
        trace_id = str(_row_field(row, "trace_id", ""))
        short = esc(trace_id[:12])
        link_html = f'<a href="/traces/{esc(trace_id)}" title="{esc(trace_id)}">{short}</a>'
        values = (
            link_html,
            esc(_row_field(row, "ts")),
            esc(_row_field(row, "conv_id")),
            esc(_row_field(row, "turn_id")),
            esc(_row_field(row, "name")),
            esc(_row_field(row, "scenario_id")),
            esc(_row_field(row, "span_count")),
            esc(_row_field(row, "total_duration_ms")),
            esc(_row_field(row, "status")),
            esc(_row_field(row, "chat_count")),
            esc(_row_field(row, "execute_tool_count")),
        )
        cells = "".join(
            _td_cell(value, kind)
            for value, (_, kind) in zip(values, TRACE_LIST_COLUMNS, strict=True)
        )
        rows_html.append(f"<tr>{cells}</tr>")
    body = (
        "\n".join(rows_html)
        if rows_html
        else f'<tr><td colspan="{len(TRACE_LIST_COLUMNS)}">No trace recorded.</td></tr>'
    )
    return (
        '<section id="traces">\n<h2>Traces</h2>\n'
        f"<table><thead>{head}</thead><tbody>\n{body}\n</tbody></table>\n</section>"
    )


def _fmt_attribute_value(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value) if value is not None else ""


def _build_span_tree(spans: Sequence[ServedSpan]) -> dict[str | None, list[ServedSpan]]:
    """`parent_span_id -> children`, siblings ordered by `start_ns` then
    `span_id`; a child whose declared parent isn't among `spans` is folded
    under the `None` (root) bucket alongside any orphan (REQ-V160-DSH-08)."""
    by_id = {span.span_id: span for span in spans}
    children: dict[str | None, list[ServedSpan]] = {}
    for span in spans:
        parent = span.parent_span_id if span.parent_span_id in by_id else None
        children.setdefault(parent, []).append(span)
    for siblings in children.values():
        siblings.sort(key=lambda span: (span.start_ns, span.span_id))
    return children


def _tree_preorder_index(spans: Sequence[ServedSpan]) -> dict[str, int]:
    """`span_id -> its position in a depth-first, start_ns-ordered walk` --
    the tie-break `gantt_svg` uses when two spans share `start_ns`
    (REQ-V160-DSH-03: "ordered by start_ns then tree order")."""
    children = _build_span_tree(spans)
    order: dict[str, int] = {}

    def walk(node: ServedSpan) -> None:
        order[node.span_id] = len(order)
        for child in children.get(node.span_id, []):
            walk(child)

    for root in children.get(None, []):
        walk(root)
    return order


def _render_span_node(
    span: ServedSpan, children: dict[str | None, list[ServedSpan]], depth: int
) -> str:
    indent = f"{depth * 1.25:.2f}rem"
    header = (
        f'<div class="span-row" style="margin-left:{indent}">'
        f'<span class="tag">{esc(span.kind)}</span> '
        f"<b>{esc(span.name)}</b> "
        f'<span class="meta">{esc(span.duration_ms)} ms, {esc(span.status)}'
        f", span {esc(span.span_id)}</span>"
        "</div>"
    )
    attr_indent = f"{(depth + 1) * 1.25:.2f}rem"
    attrs = "".join(
        f'<div class="meta" style="margin-left:{attr_indent}">'
        f"{esc(key)} = {esc(_fmt_attribute_value(value))}</div>"
        for key, value in sorted(span.attributes.items())
    )
    child_html = "".join(
        _render_span_node(child, children, depth + 1) for child in children.get(span.span_id, [])
    )
    return header + attrs + child_html


def trace_tree_section(spans: Sequence[ServedSpan]) -> str:
    """The span tree, indented by depth, each row carrying name, kind,
    duration, status and its served attributes as `key = value` pairs
    (REQ-V160-DSH-03). A trace whose root span is missing renders every
    span as its own root behind a banner rather than raising
    (REQ-V160-DSH-08)."""
    _check_served_spans(spans)
    if not spans:
        return (
            '<section id="trace-tree">\n<h2>Trace</h2>\n'
            '<p class="sub">No span recorded.</p>\n</section>'
        )
    children = _build_span_tree(spans)
    has_true_root = any(span.parent_span_id is None for span in spans)
    banner = ""
    if not has_true_root:
        banner = (
            '<p class="warn">This trace has no root span (no span with '
            "parent_span_id absent) -- every span below is rendered as its "
            "own root.</p>\n"
        )
    body = "".join(_render_span_node(root, children, 0) for root in children.get(None, []))
    return f'<section id="trace-tree">\n<h2>Trace</h2>\n{banner}{body}\n</section>'


# ----------------------------------------------------------------------------
# conversations and transcripts (REQ-V180-CONV-03, REQ-V180-CONV-04). Pure:
# no `import config`, no `import storage`, no `import sqlite3`, no I/O, no
# `Path` -- rows/messages arrive already fetched by `storage.py`'s readers
# (T5) and, for the transcript, already redacted and 2000-char-truncated by
# `dashboard_server.py` (T6, REQ-V180-SEC-01/-02 item 1).
# ----------------------------------------------------------------------------

CONVERSATION_LIST_COLUMNS: tuple[ColumnSpec, ...] = (
    ("id", "num"),
    ("user", "num"),
    ("started", "num"),
    ("messages", "num"),
    ("active", "text"),
    ("last activity", "num"),
)


def conversation_list_section(rows: Sequence[Any]) -> str:
    """One row per conversation (REQ-V180-CONV-03's `/conversations`), from
    `storage.recent_conversations`-shaped rows: **id** (linking to
    `/conversations/<id>`), **user** (`tg_user_id`), **started**
    (`created_at`), **messages** (`message_count`), **active** (`yes`/`no`,
    `ok` colour class for `yes` -- the only `"text"` column), **last
    activity** (`last_activity`, or `—` when the conversation holds no
    message -- the placeholder keeps the `"num"` class per `_td_cell`'s
    convention). An empty `rows` renders one empty-state row, never a blank
    table. The `/new`-to-`/new` page-copy line (REQ-V180-CONV-01) is left to
    the caller's page body, not this section fragment."""
    head = _head_row(CONVERSATION_LIST_COLUMNS)
    rows_html = []
    for row in rows:
        conv_id = _row_field(row, "id")
        active = bool(_row_field(row, "active"))
        active_word = "yes" if active else "no"
        active_html = f'<span class="ok">{esc(active_word)}</span>' if active else esc(active_word)
        last_activity = _row_field(row, "last_activity")
        last_activity_html = "—" if last_activity is None else esc(last_activity)
        id_html = f'<a href="/conversations/{esc(conv_id)}">{esc(conv_id)}</a>'
        values = (
            id_html,
            esc(_row_field(row, "tg_user_id")),
            esc(_row_field(row, "created_at")),
            esc(_row_field(row, "message_count")),
            active_html,
            last_activity_html,
        )
        cells = "".join(
            _td_cell(value, kind)
            for value, (_, kind) in zip(values, CONVERSATION_LIST_COLUMNS, strict=True)
        )
        rows_html.append(f"<tr>{cells}</tr>")
    body = (
        "\n".join(rows_html)
        if rows_html
        else (
            f'<tr><td colspan="{len(CONVERSATION_LIST_COLUMNS)}">'
            "No conversation recorded.</td></tr>"
        )
    )
    return (
        '<section id="conversations">\n<h2>Conversations</h2>\n'
        f"<table><thead>{head}</thead><tbody>\n{body}\n</tbody></table>\n</section>"
    )


TRANSCRIPT_PAGE_BUDGET_BYTES = 1_572_864  # 1.5 MiB (REQ-V180-SEC-02 item 3)
TRANSCRIPT_PAGE_SUFFIX_BYTES = 4096  # truncation marker + next/first-page links

_TRANSCRIPT_SECTION_OPEN = '<section id="conversation">\n<h2>Conversation</h2>\n'
_TRANSCRIPT_SECTION_CLOSE = "\n</section>"
_TRANSCRIPT_EMPTY_STATE = '<p class="meta">No messages in this conversation.</p>'
_TRANSCRIPT_CONTINUED_NOTE = (
    '<p class="meta">continued -- this turn was split across the byte budget</p>'
)


def _turn_groups(messages: Sequence[Any]) -> list[tuple[int, list[Any]]]:
    """Groups `messages` (already `turn_id, id` ordered -- CONV-02's own
    guarantee) into consecutive `(turn_id, [message, ...])` pairs, without
    re-sorting: a caller handing rows out of order gets groups split at every
    turn_id change, never silently re-merged."""
    groups: list[tuple[int, list[Any]]] = []
    for msg in messages:
        turn_id = _row_field(msg, "turn_id")
        if groups and groups[-1][0] == turn_id:
            groups[-1][1].append(msg)
        else:
            groups.append((turn_id, [msg]))
    return groups


def _trace_link_html(turn_id: int, trace_map: Mapping[int, str] | None) -> str:
    """Plain text with no arrow appended when the turn has no trace; an `<a
    href="/traces/{trace_id}">` of the abbreviated id (first 12 characters,
    matching `trace_list_section`'s convention) when it does (REQ-V180-CONV-05)."""
    trace_id = None if trace_map is None else trace_map.get(turn_id)
    if trace_id is None:
        return ""
    trace_id = str(trace_id)
    short = esc(trace_id[:12])
    return f'<a href="/traces/{esc(trace_id)}" title="{esc(trace_id)}">{short}</a>'


def _message_html(msg: Any, *, trace_link_html: str) -> str:
    """One message row: a fixed-width rail (turn id and timestamp are its
    `"num"` fields; role and the trace link are not -- REQ-V180-CONV-04) plus
    the message text column. The trace link, when the turn has one, is shown
    once per turn -- on the turn's first message only (`trace_link_html`
    empty for every other message of the turn) -- design choice: CONV-05
    speaks of "the turn's rail entry" in the singular, and repeating the link
    on every message of a multi-message turn would spend byte budget without
    adding information. A `tool` row also shows its `tool_call_id`."""
    role = esc(_row_field(msg, "role"))
    turn_id_html = esc(_row_field(msg, "turn_id"))
    ts_html = esc(_row_field(msg, "created_at"))
    content_html = esc(_row_field(msg, "content"))
    tool_call_id = _row_field(msg, "tool_call_id")
    tool_html = (
        f'<div class="meta">tool_call_id: {esc(tool_call_id)}</div>'
        if tool_call_id is not None
        else ""
    )
    rail = (
        '<div class="rail">'
        f"<div{_num_class('num')}>{turn_id_html}</div>"
        f"<div>{role}</div>"
        f"<div{_num_class('num')}>{ts_html}</div>"
        f"<div>{trace_link_html}</div>"
        f"{tool_html}"
        "</div>"
    )
    return f'<div class="turn-row">{rail}<div class="msg">{content_html}</div></div>'


def conversation_transcript_section(
    messages: Sequence[Any],
    *,
    chrome_bytes: int,
    reader_next_cursor: tuple[int, int] | None = None,
    trace_map: Mapping[int, str] | None = None,
    budget_bytes: int = TRANSCRIPT_PAGE_BUDGET_BYTES,
    suffix_bytes: int = TRANSCRIPT_PAGE_SUFFIX_BYTES,
) -> tuple[str, tuple[int, int] | None, bool]:
    """Renders `messages` (already redacted and 2000-char-truncated per
    message -- upstream, `dashboard_server.py`'s job, REQ-V180-SEC-02 item 1)
    under REQ-V180-CONV-04's atomic turn admission and REQ-V180-SEC-02 item
    3's whole-response byte budget. Pure: escaping (`esc()`) and admission
    only, no I/O, no `Path`, no `config`/`storage`/`sqlite3` import.

    `chrome_bytes` is the caller's measured size of `page()`-level chrome
    only (nav/style/headings/closing markup) -- this function adds its own
    wrapping `<section>`/`<h2>` open and close tags to the seed itself, since
    those bytes are emitted here and the caller cannot measure them before
    calling. The accumulator is seeded with
    `chrome_bytes + suffix_bytes + len(section wrapper bytes)` before any
    turn is admitted, so the budget bounds the whole response, not just the
    rows (REQ-V180-SEC-02 item 3).

    Atomic turn admission, per turn, in this exact order: (1) render the
    whole turn and measure its UTF-8 byte length; (2) it fits the remaining
    budget -> admit the entire turn; (3) it does not fit and the page already
    holds a turn -> stop, next cursor is that turn's first message; (4) it
    does not fit and the page is empty -> split it, admitting at least one
    message so the page always advances, marking it continued. This is the
    only case a turn is ever split.

    Returns `(html, next_cursor, split)`. `next_cursor` is this function's
    own reconciliation of the "two next-cursor" question: when every given
    message was admitted, the reader's own `reader_next_cursor` (the first
    message `conversation_messages` did not return, if any) is passed
    through unchanged; when this function's own byte-budget admission
    stopped the page before the input ran out, *that* earlier cursor always
    wins, since it is what was actually rendered -- `reader_next_cursor` is
    only ever a fallback, never mixed with or overridden by a later value.
    `split` is `True` exactly when case 4 forced a partial-turn render."""
    section_wrapper_bytes = len(
        (_TRANSCRIPT_SECTION_OPEN + _TRANSCRIPT_SECTION_CLOSE).encode("utf-8")
    )
    accumulator = chrome_bytes + suffix_bytes + section_wrapper_bytes

    groups = _turn_groups(messages)
    if not groups:
        return (
            _TRANSCRIPT_SECTION_OPEN + _TRANSCRIPT_EMPTY_STATE + _TRANSCRIPT_SECTION_CLOSE,
            reader_next_cursor,
            False,
        )

    rendered: list[str] = []
    next_cursor: tuple[int, int] | None = None
    split = False

    for turn_id, turn_messages in groups:
        trace_link_html = _trace_link_html(turn_id, trace_map)
        turn_html = "".join(
            _message_html(msg, trace_link_html=(trace_link_html if i == 0 else ""))
            for i, msg in enumerate(turn_messages)
        )
        turn_bytes = len(turn_html.encode("utf-8"))

        if accumulator + turn_bytes <= budget_bytes:
            rendered.append(turn_html)
            accumulator += turn_bytes
            continue

        if rendered:
            # case 3: the page already holds a turn -- stop here.
            first = turn_messages[0]
            next_cursor = (turn_id, _row_field(first, "id"))
            break

        # case 4: the page is empty -- split this turn, admitting at least
        # one message so the page always advances.
        partial_html: list[str] = []
        partial_bytes = 0
        withheld_cursor: tuple[int, int] | None = None
        for i, msg in enumerate(turn_messages):
            msg_html = _message_html(msg, trace_link_html=(trace_link_html if i == 0 else ""))
            msg_bytes = len(msg_html.encode("utf-8"))
            if not partial_html or accumulator + partial_bytes + msg_bytes <= budget_bytes:
                partial_html.append(msg_html)
                partial_bytes += msg_bytes
            else:
                withheld_cursor = (turn_id, _row_field(msg, "id"))
                break
        rendered.append("".join(partial_html))
        accumulator += partial_bytes
        if withheld_cursor is not None:
            split = True
            next_cursor = withheld_cursor
            break
        # the whole turn ended up fitting message-by-message after all
        # (possible when the whole-turn measurement's overhead differs from
        # the sum of its parts) -- not a split, keep going.

    if next_cursor is None:
        next_cursor = reader_next_cursor

    html = _TRANSCRIPT_SECTION_OPEN + "\n".join(rendered)
    if split:
        html += _TRANSCRIPT_CONTINUED_NOTE
    html += _TRANSCRIPT_SECTION_CLOSE
    return html, next_cursor, split


def transcript_page_footer(
    rendered: Sequence[Any],
    *,
    conv_id: int,
    limit: int,
    next_cursor: tuple[int, int] | None,
) -> str:
    """The range note, next link and first-page link REQ-V180-CONV-04
    requires beside the transcript rows. `conversation_transcript_section`
    itself renders only the rows and the continued note (it returns
    `next_cursor` as data, not markup) -- this is `dashboard_server.py`'s
    (T6) own render of that data, kept in this module rather than there
    because REQ-V160-DSH-01 forbids any HTML literal outside it; their
    combined byte cost is what `TRANSCRIPT_PAGE_SUFFIX_BYTES` reserves
    headroom for. `rendered` is the caller's own post-budget slice of the
    messages actually shown (`_row_field`-shaped, `turn_id`-bearing); an
    empty slice renders no range note -- the section's own empty-state text
    already covers that case. There is never a previous link (CONV-04)."""
    parts: list[str] = []
    if rendered:
        first_turn = _row_field(rendered[0], "turn_id")
        last_turn = _row_field(rendered[-1], "turn_id")
        count = len(rendered)
        parts.append(
            meta_line(
                f"Showing {count} message{'s' if count != 1 else ''} "
                f"(turn {first_turn} through turn {last_turn})."
            )
        )
    if next_cursor is not None:
        href = f"/conversations/{conv_id}?limit={limit}&cursor={next_cursor[0]}-{next_cursor[1]}"
        parts.append(f'<p class="meta"><a href="{esc(href)}">next</a></p>')
    first_page_href = f"/conversations/{conv_id}"
    parts.append(f'<p class="meta"><a href="{esc(first_page_href)}">first page</a></p>')
    return "".join(parts)


# ----------------------------------------------------------------------------
# SVG charts (REQ-V160-DSH-04): viewBox + width + height + role="img" +
# <title> (accessible name) + <desc> (metric, unit, total count); every
# chart also encodes its information in text so it stays legible with
# colour removed.
# ----------------------------------------------------------------------------

_CHART_MARGIN_TOP = 10
_CHART_MARGIN_BOTTOM = 32
_CHART_BAR_GAP = 4

_GANTT_ROW_HEIGHT = 22
_GANTT_MARGIN_TOP = 12
_GANTT_MARGIN_BOTTOM = 8
_GANTT_MARGIN_LEFT = 4
_GANTT_MARGIN_RIGHT = 4


def _fmt_boundary(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _bucket_labels(boundaries: Sequence[float]) -> list[str]:
    labels = [f"≤{_fmt_boundary(b)}" for b in boundaries]
    labels.append(f">{_fmt_boundary(boundaries[-1])}" if boundaries else "all")
    return labels


def _bar_chart_svg(
    labels: Sequence[str],
    counts: Sequence[int],
    *,
    width: int,
    height: int,
    title: str,
    desc: str,
) -> str:
    """The shared geometry behind `histogram_svg` and `bar_svg`: one bar per
    `(label, count)`, a zero-count bucket drawn as a zero-height bar with
    its label present (REQ-V160-DSH-04)."""
    n = len(counts)
    max_count = max(counts) if counts else 0
    chart_h = max(1, height - _CHART_MARGIN_TOP - _CHART_MARGIN_BOTTOM)
    slot_w = width / n if n else float(width)
    bar_w = max(1.0, slot_w - _CHART_BAR_GAP)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">',
        f"<title>{esc(title)}</title><desc>{esc(desc)}</desc>",
    ]
    for index, count in enumerate(counts):
        bar_h = 0.0 if not max_count else (count / max_count) * chart_h
        x = index * slot_w
        y = _CHART_MARGIN_TOP + (chart_h - bar_h)
        count_y = max(_CHART_MARGIN_TOP + 8, y - 2)
        parts.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{bar_h:.2f}" '
            f'fill="{PALETTE["bar"]}"/>'
            f'<text x="{x:.2f}" y="{count_y:.2f}" font-size="9">{esc(count)}</text>'
            f'<text x="{x:.2f}" y="{height - _CHART_MARGIN_BOTTOM + 14:.2f}" font-size="9">'
            f"{esc(labels[index])}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def histogram_svg(histogram: metrics.Histogram, *, width: int, height: int, title: str) -> str:
    """One bar per bucket of a `metrics.Histogram`; the `<desc>` names the
    metric, its unit and the total count (REQ-V160-DSH-04)."""
    labels = _bucket_labels(histogram.boundaries)
    attrs_text = ", ".join(f"{key}={value}" for key, value in histogram.attributes)
    desc = (
        f"{histogram.name} ({histogram.unit}), total {histogram.total}, "
        f"attributes {attrs_text or '(none)'}"
    )
    return _bar_chart_svg(
        labels, histogram.counts, width=width, height=height, title=title, desc=desc
    )


def bar_svg(pairs: Sequence[tuple[str, int]], *, width: int, height: int, title: str) -> str:
    """A generic labelled bar chart, e.g. `limit_hits` counts by constant
    name (REQ-V160-DSH-03's `/tools` page)."""
    labels = [str(label) for label, _ in pairs]
    counts = [int(count) for _, count in pairs]
    desc = f"{len(pairs)} categories, total {sum(counts)}"
    return _bar_chart_svg(labels, counts, width=width, height=height, title=title, desc=desc)


def gantt_svg(spans: Sequence[ServedSpan], *, width: int) -> str:
    """One bar per span: left edge and width scaled from `start_ns` offsets
    against the root's duration, never from `ts` (REQ-V160-DSH-03). A
    zero-duration root draws every bar at `x = 0` rather than dividing.
    Bars are ordered by `start_ns` then tree order, coloured by `kind`, and
    outlined in the error colour when `status == "error"`."""
    _check_served_spans(spans)
    if not spans:
        height = _GANTT_MARGIN_TOP + _GANTT_MARGIN_BOTTOM
        return (
            f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            'role="img"><title>Trace gantt</title>'
            "<desc>No span recorded.</desc></svg>"
        )

    true_roots = [span for span in spans if span.parent_span_id is None]
    reference = min(true_roots or spans, key=lambda span: span.start_ns)
    root_duration_ns = reference.duration_ms * 1_000_000

    preorder = _tree_preorder_index(spans)
    ordered = sorted(spans, key=lambda span: (span.start_ns, preorder.get(span.span_id, 0)))

    chart_width = max(1, width - _GANTT_MARGIN_LEFT - _GANTT_MARGIN_RIGHT)
    height = _GANTT_MARGIN_TOP + _GANTT_ROW_HEIGHT * len(ordered) + _GANTT_MARGIN_BOTTOM

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">',
        "<title>Trace gantt</title>",
        f"<desc>Gantt of {len(ordered)} span(s), scaled from start_ns offsets against a "
        f"{reference.duration_ms} ms root.</desc>",
    ]
    for index, span in enumerate(ordered):
        if root_duration_ns <= 0:
            x_frac, w_frac = 0.0, 0.0
        else:
            x_frac = (span.start_ns - reference.start_ns) / root_duration_ns
            w_frac = span.duration_ms * 1_000_000 / root_duration_ns
        x = _GANTT_MARGIN_LEFT + max(0.0, x_frac) * chart_width
        w = max(0.0, w_frac) * chart_width
        y = _GANTT_MARGIN_TOP + index * _GANTT_ROW_HEIGHT
        color = (
            PALETTE["kind_client"] if span.kind == tracing.KIND_CLIENT else PALETTE["kind_internal"]
        )
        outline = ""
        if span.status == tracing.STATUS_ERROR:
            outline = f' stroke="{PALETTE["error_outline"]}" stroke-width="2"'
        label = f"{span.name} — {span.kind}, {span.duration_ms}ms, {span.status}"
        parts.append(
            f'<rect x="{x:.2f}" y="{y}" width="{w:.2f}" height="{_GANTT_ROW_HEIGHT - 4}" '
            f'fill="{color}"{outline}><title>{esc(label)}</title></rect>'
            f'<text x="{_GANTT_MARGIN_LEFT}" y="{y + _GANTT_ROW_HEIGHT - 6}" font-size="10">'
            f"{esc(label)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


# ----------------------------------------------------------------------------
# a generic side-by-side comparison (REQ-V160-DSH-01; the bench-specific
# `_compare` below is the byte-identical legacy renderer `render()` uses)
# ----------------------------------------------------------------------------


def _as_mapping(obj: Any) -> dict:
    if isinstance(obj, Mapping):
        return dict(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    return {"value": obj}


def compare_section(baseline: Any, candidate: Any) -> str:
    """Two summary-shaped mappings or dataclass instances, side by side,
    with a numeric delta where both sides report a number."""
    left, right = _as_mapping(baseline), _as_mapping(candidate)
    keys = sorted(set(left) | set(right))
    rows = []
    for key in keys:
        left_value, right_value = left.get(key), right.get(key)
        delta = ""
        numeric = (int, float)
        if (
            isinstance(left_value, numeric)
            and not isinstance(left_value, bool)
            and isinstance(right_value, numeric)
            and not isinstance(right_value, bool)
        ):
            delta = f"{right_value - left_value:+g}"
        rows.append(
            f"<tr><th>{esc(key)}</th><td>{esc(left_value)}</td><td>{esc(right_value)}</td>"
            f"<td>{esc(delta)}</td></tr>"
        )
    head = "<tr><th>metric</th><th>baseline</th><th>candidate</th><th>Δ</th></tr>"
    return (
        '<section id="compare">\n<h2>Compare</h2>\n'
        f"<table><thead>{head}</thead><tbody>\n"
        + "\n".join(rows)
        + "\n</tbody></table>\n</section>"
    )


# ============================================================================
# the static benchmark report's own renderer (REQ-V160-DSH-05), relocated
# verbatim from `devtools/dashboard.py`. `render()`'s output is byte-for-byte
# what the pre-refactor module produced for the same input.
# ============================================================================

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


def fmt(value: Any, kind: str) -> str:
    """The one number formatter: exact digits for integers (a dashboard that
    abbreviates cannot be checked against the file it renders), fixed precision
    everywhere else, `n/a` for a value the run never reported."""
    if value is None:
        return "n/a"
    if kind == "int":
        # An integral count prints its exact digits; `summary.per_scenario[].median`
        # is `statistics.median`, so an even number of repeats yields the mean of
        # the two middle runs -- a half token is shown, never truncated away.
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
    return esc(value)


def _cell(value: Any, kind: str, *, cell_id: str | None = None) -> str:
    text = fmt(value, kind)
    classes = "num" if value is not None else "num na"
    ident = f' id="{esc(cell_id)}"' if cell_id else ""
    return f'<td class="{classes}"{ident}>{esc(text)}</td>'


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


def _header(document: dict, compare: dict | None) -> str:
    meta = document["meta"]
    pricing = meta.get("pricing") or {}
    bits = [
        f"tag <b>{esc(meta.get('tag'))}</b>",
        f"provider {esc(meta.get('provider'))}",
        f"model {esc(meta.get('model'))}",
        f"repeats {esc(meta.get('repeats'))}",
        f"commit {esc(str(meta.get('git_commit', ''))[:12])}",
        f"started {esc(meta.get('started_at'))}",
        f"prefix tokens {esc(meta.get('prefix_tokens'))}",
        f"pricing {esc(pricing.get('basis') or 'none')}",
    ]
    skipped = meta.get("skipped_scenarios") or []
    if skipped:
        bits.append(f"skipped {esc(', '.join(skipped))}")
    if meta.get("only"):
        bits.append(f"only {esc(', '.join(meta['only']))}")
    banner = ""
    if "aborted" in meta:
        banner = (
            f'<p class="warn">This run was aborted ({esc(meta["aborted"])}): the '
            f"figures below cover the runs that completed and are not comparable "
            f"with a full run.</p>"
        )
    nav = [
        '<a href="#aggregates">aggregates</a>',
        '<a href="#cache">cache</a>',
        '<a href="#tools">tools</a>',
        '<a href="#timeline">timeline</a>',
    ]
    if compare is not None:
        nav.append('<a href="#compare">compare</a>')
    return (
        f"<h1>Benchmark dashboard — {esc(meta.get('tag'))}</h1>\n"
        f'<p class="sub">{" · ".join(bits)}</p>\n'
        f"<nav>{''.join(nav)}</nav>\n{banner}"
    )


def _aggregates(document: dict) -> str:
    summary = document["summary"]
    totals = summary["totals"]
    rows = [
        f"<tr><th>{esc(label)}</th>{_cell(totals[key], kind, cell_id=f'm-{key}')}</tr>"
        for key, label, kind in TOTAL_ROWS
    ]
    rows.append(f"<tr><th>runs</th>{_cell(summary['runs'], 'int', cell_id='m-runs')}</tr>")
    rows.append(
        f"<tr><th>skipped runs</th>{_cell(summary['skipped'], 'int', cell_id='m-skipped')}</tr>"
    )
    rows.append(
        f"<tr><th>successes</th>{_cell(summary['successes'], 'int', cell_id='m-successes')}</tr>"
    )
    rows.append(
        f"<tr><th>success rate</th>"
        f"{_cell(summary['success_rate'], 'share', cell_id='m-success_rate')}</tr>"
    )
    rows.append(
        f"<tr><th>cost per success</th>"
        f"{_cell(summary['cost_per_success'], 'cost', cell_id='m-cost_per_success')}</tr>"
    )
    rows.append(
        f"<tr><th>tokens per success</th>"
        f"{_cell(summary['tokens_per_success'], 'float', cell_id='m-tokens_per_success')}</tr>"
    )

    averages = [
        f"<tr><th>{esc(label)}</th>"
        f"{_cell(summary['avg_per_task'][key], kind, cell_id=f'm-avg-{key}')}</tr>"
        for key, label, kind in AVG_ROWS
    ]

    growth = summary.get("context_growth") or {}
    growth_rows = [
        f"<tr><th>{esc(role)}</th>"
        f"{_cell(growth.get(role), 'float', cell_id=f'm-growth-{role}')}</tr>"
        for role in metrics.PROMPT_ROLE_KEYS
    ]
    top_turn = summary.get("top_turn")
    top_turn_line = (
        "no LLM call was recorded"
        if not top_turn
        else f"{esc(top_turn.get('scenario'))} repeat {esc(top_turn.get('repeat'))}, "
        f"turn {esc(top_turn.get('turn'))}, round {esc(top_turn.get('round'))} — "
        f"{esc(top_turn.get('prompt_tokens'))} prompt tokens"
    )

    return (
        '<section id="aggregates">\n'
        "<h2>Aggregates</h2>\n"
        '<p class="sub">Every figure below is the document\'s own '
        "<code>summary</code>, which <code>bench.py check</code> recomputes from the "
        "embedded rows. Live-bot figures live in <code>/stats</code>.</p>\n"
        f"<table><caption>Totals over {esc(document['summary']['runs'])} runs</caption>"
        f"<tbody>\n{_rows(rows)}\n</tbody></table>\n"
        f"<h3>Per task (per executed run)</h3>\n<table><tbody>\n{_rows(averages)}\n"
        "</tbody></table>\n"
        f"<h3>Context growth, chars per run</h3>\n<table><tbody>\n{_rows(growth_rows)}\n"
        "</tbody></table>\n"
        f'<h3>Most expensive turn</h3>\n<p class="meta" id="m-top_turn">{top_turn_line}</p>\n'
        "</section>"
    )


def _cache(document: dict) -> str:
    summary = document["summary"]
    share = metrics.prefix_share(document)
    cache_note = (
        "the provider reported no cached tokens"
        if summary["cache_hit_rate"] is None
        else "cached ÷ prompt tokens"
    )
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
    return (
        '<section id="cache">\n<h2>Cache and re-sent context</h2>\n'
        f"<table><tbody>\n{_rows(rows)}\n</tbody></table>\n</section>"
    )


def _bar(value: int, largest: int, css: str = "") -> str:
    width = 0.0 if largest <= 0 else min(100.0, value / largest * 100)
    return f'<div class="bar{css}"><span style="width:{width:.1f}%"></span></div>'


def _tools(breakdown: list[dict]) -> str:
    """`breakdown` is `devtools.dashboard.tool_breakdown(document["runs"])`,
    computed by the caller so this render half never calls back into that
    module's data functions (REQ-V160-DSH-01's import direction)."""
    if not breakdown:
        return (
            '<section id="tools">\n<h2>Tools</h2>\n'
            '<p class="sub">No tool call was recorded in this run.</p>\n</section>'
        )
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
            f"<tr><th>{esc(name)}</th>"
            f"{_cell(item['calls'], 'int', cell_id=ident + '-calls')}"
            f"{_cell(item['output_tokens_est'], 'int', cell_id=ident + '-tokens')}"
            f"<td>{_bar(item['output_tokens_est'], max_tokens)}</td>"
            f'<td class="num">{fmt(token_share, "share")}</td>'
            f"{_cell(item['duration_ms'], 'int', cell_id=ident + '-ms')}"
            f"<td>{_bar(item['duration_ms'], max_time, ' time')}</td>"
            f'<td class="num">{fmt(time_share, "share")}</td></tr>'
        )
    head = (
        '<tr><th>tool</th><th class="num">calls</th><th class="num">output tokens</th>'
        '<th>by output</th><th class="num">share</th><th class="num">time, ms</th>'
        '<th>by time</th><th class="num">share</th></tr>'
    )
    return (
        '<section id="tools">\n<h2>Tools</h2>\n'
        '<p class="sub">Every tool call of every run, by output tokens and by wall '
        "time.</p>\n"
        f"<table><thead>{head}</thead><tbody>\n{_rows(rows)}\n</tbody></table>\n</section>"
    )


def _timeline(blocks: list[dict]) -> str:
    """`blocks` is one dict per scenario, computed by
    `devtools.dashboard._timeline_blocks` from `scenario_runs`, `median_key`,
    `median_run` and `timeline_rows` -- data functions that stay in that
    module (REQ-V160-DSH-05), so this render half never calls them itself."""
    if not blocks:
        return (
            '<section id="timeline">\n<h2>Timeline</h2>\n'
            '<p class="sub">No run was executed.</p>\n</section>'
        )
    rendered = []
    for block in blocks:
        scenario = block["scenario"]
        run = block["run"]
        verdict = (
            '<span class="ok">success</span>'
            if run["success"]
            else f'<span class="bad">{esc(run["failure"])}</span>'
        )
        rows = []
        for entry in block["rows"]:
            tools = ", ".join(entry["tools"]) or "—"
            marker = (
                ""
                if entry["error_kind"] is None
                else f' <span class="bad">{esc(entry["error_kind"])}</span>'
            )
            rows.append(
                f'<tr><td class="num">{esc(entry["round"])}</td>'
                f'<td><span class="tag">{esc(entry["purpose"])}</span>{marker}</td>'
                f"{_cell(entry['prompt_tokens'], 'int')}"
                f"{_cell(entry['completion_tokens'], 'int')}"
                f"{_cell(entry['cached_tokens'], 'int')}"
                f"{_cell(entry['latency_ms'], 'int')}"
                f"<td>{esc(tools)}</td></tr>"
            )
        head = (
            '<tr><th class="num">round</th><th>purpose</th><th class="num">prompt</th>'
            '<th class="num">completion</th><th class="num">cached</th>'
            '<th class="num">latency, ms</th><th>tools called</th></tr>'
        )
        growth = block["growth"]
        growth_line = ", ".join(
            f"{role} {growth.get(role, 0.0):+.0f}" for role in metrics.PROMPT_ROLE_KEYS
        )
        ranked = block["ranked"]
        rendered.append(
            f'<h3 id="timeline-{esc(scenario)}">{esc(scenario)} — repeat '
            f'<span id="median-{esc(scenario)}">{esc(run["repeat"])}</span>, {verdict}</h3>\n'
            f'<p class="meta">median of {block["runs_count"]} run(s), ranked by {ranked}; '
            f"cost {fmt(run['totals']['cost_usd'], 'cost')}, "
            f"{run['totals']['prompt_tokens'] + run['totals']['completion_tokens']} tokens, "
            f"wall {run['totals']['wall_ms']} ms · context growth {esc(growth_line)}</p>\n"
            f"<table><thead>{head}</thead><tbody>\n{_rows(rows)}\n</tbody></table>"
        )
    return (
        '<section id="timeline">\n<h2>Timeline — the median run of every scenario</h2>\n'
        '<p class="sub">A scenario\'s runs are sorted ascending by cost (by prompt + '
        "completion tokens when any repeat reported no cost), ties keep execution "
        "order, and the run at index <code>n // 2</code> is shown.</p>\n"
        + "\n".join(rendered)
        + "\n</section>"
    )


def _success_ratio(entry: dict | None) -> str:
    """`k/n` for one scenario of one file; `—` when that file never ran it."""
    if not entry:
        return "—"
    return f"{entry['success']}/{entry['of']}"


def _compare(document: dict, other: dict) -> str:
    left, right = document["summary"], other["summary"]
    left_tag = esc(document["meta"].get("tag"))
    right_tag = esc(other["meta"].get("tag"))
    head = (
        f'<tr><th>metric</th><th class="num">{left_tag}</th><th class="num">{right_tag}</th>'
        '<th class="num">Δ</th><th class="num">Δ %</th></tr>'
    )

    rows = []
    for key, label, kind in TOTAL_ROWS:
        new, old = right["totals"][key], left["totals"][key]
        absolute, relative = _delta(new, old, kind)
        rows.append(
            f"<tr><th>{esc(label)}</th>{_cell(old, kind)}{_cell(new, kind)}"
            f'<td class="num">{esc(absolute)}</td>'
            f'<td class="num">{esc(relative)}</td></tr>'
        )
    for key, label, kind in (
        ("success_rate", "success rate", "share"),
        ("cost_per_success", "cost per success", "cost"),
        ("tokens_per_success", "tokens per success", "float"),
        ("resent_share", "re-sent share", "share"),
        ("cache_hit_rate", "cache hit rate", "share"),
    ):
        new, old = right.get(key), left.get(key)
        absolute, relative = _delta(new, old, kind)
        rows.append(
            f"<tr><th>{esc(label)}</th>{_cell(old, kind)}{_cell(new, kind)}"
            f'<td class="num">{esc(absolute)}</td>'
            f'<td class="num">{esc(relative)}</td></tr>'
        )
    for key, label, kind in AVG_ROWS:
        new, old = right["avg_per_task"][key], left["avg_per_task"][key]
        absolute, relative = _delta(new, old, kind)
        rows.append(
            f"<tr><th>{esc(label)} (avg)</th>{_cell(old, kind)}{_cell(new, kind)}"
            f'<td class="num">{esc(absolute)}</td>'
            f'<td class="num">{esc(relative)}</td></tr>'
        )

    scenarios = sorted(set(left["per_scenario"]) | set(right["per_scenario"]))
    scenario_rows = []
    for scenario in scenarios:
        here = left["per_scenario"].get(scenario)
        there = right["per_scenario"].get(scenario)
        cells = [f"<th>{esc(scenario)}</th>"]
        cells.append(f"<td>{esc(_success_ratio(here))} → {esc(_success_ratio(there))}</td>")
        for key, kind in SCENARIO_DELTA_KEYS:
            old = None if not here else here["median"].get(key)
            new = None if not there else there["median"].get(key)
            _, relative = _delta(new, old, kind)
            cells.append(
                f'{_cell(old, kind)}{_cell(new, kind)}<td class="num">{esc(relative)}</td>'
            )
        scenario_rows.append(f"<tr>{''.join(cells)}</tr>")
    scenario_head = (
        "<tr><th>scenario</th><th>success</th>"
        + "".join(f'<th class="num" colspan="3">{esc(key)}</th>' for key, _ in SCENARIO_DELTA_KEYS)
        + "</tr>"
    )

    flags_left = document["meta"].get("env_flags") or {}
    flags_right = other["meta"].get("env_flags") or {}
    differing = [
        name
        for name in sorted(set(flags_left) | set(flags_right))
        if flags_left.get(name) != flags_right.get(name)
    ]
    treatment = (
        ", ".join(
            f"{name}: {flags_left.get(name)!r} → {flags_right.get(name)!r}" for name in differing
        )
        or "the two files declare the same env flags"
    )
    same_config = document["meta"].get("config_sha256") == other["meta"].get("config_sha256")

    return (
        '<section id="compare">\n<h2>Compare</h2>\n'
        f'<p class="sub">Δ is <b>{right_tag}</b> minus <b>{left_tag}</b>; per-scenario '
        "figures are the medians the file itself carries. This section describes the two "
        "files, it does not gate them — <code>bench.py report --gate</code> does.</p>\n"
        f'<p class="meta">treatment: {esc(treatment)}<br>config hash: '
        f"{'identical' if same_config else 'different'}</p>\n"
        f"<table><thead>{head}</thead><tbody>\n{_rows(rows)}\n</tbody></table>\n"
        "<h3>Per scenario — median of each run total, "
        f"{left_tag} → {right_tag} → Δ %</h3>\n"
        f"<table><thead>{scenario_head}</thead><tbody>\n{_rows(scenario_rows)}\n"
        "</tbody></table>\n</section>"
    )


def render(
    document: dict,
    compare: dict | None = None,
    *,
    breakdown: list[dict],
    blocks: list[dict],
) -> str:
    """The whole benchmark-report page as one string: no external
    stylesheet, no script, no image (REQ-V160-DSH-02). `breakdown` and
    `blocks` are pre-computed by `devtools.dashboard.render` from its own
    data functions -- see the module docstring."""
    sections = [
        _aggregates(document),
        _cache(document),
        _tools(breakdown),
        _timeline(blocks),
    ]
    if compare is not None:
        sections.append(_compare(document, compare))
    title = f"Benchmark dashboard — {document['meta'].get('tag', 'bench')}"
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n<style>{STYLE}</style>\n</head>\n<body>\n<main>\n"
        f"{_header(document, compare)}\n"
        + "\n".join(sections)
        + "\n<footer>Generated by devtools/dashboard.py from benchmark JSON "
        "(spec-v1.3 section 8). Static file: no script, no network.</footer>\n"
        "</main>\n</body>\n</html>\n"
    )
