"""dashboard_render.py's visual rework -- spec-v1.8.0 section 5
(REQ-V180-DSH-01..06), section 5.1's frozen design plan (copied verbatim into
`docs/spec/task-briefs/v180-T4.md`).

Scope note (task-brief v180-T4): this file's map is `dashboard_render.py`
only. `dashboard_server.py` -- which owns route-level nav lists and would
wire `reading_strip_section` into `/` -- is T6's, out of this file's reading
map. Where REQ-V180-DSH-05's "every nav carries the four entries in order"
reads as a route-level assertion, `test_t_v180_dsh_04_*` below instead
asserts the structural property `page()` itself owns: any
`Sequence[tuple[str, str]]` nav renders as `<a>` tags in the given order,
inside one `<style>` block, with no `<script>` tag and no external resource
reference. Same scoping choice for the DSH-02/DSH-03 chrome scanners: they
cover `STYLE`, `PALETTE` and the live-page builders
(`usage_section`, `tool_health_section`, `trace_list_section`,
`trace_tree_section`, `reading_strip_section`, `page`) -- never
`render()`/`_header`/`_timeline`/`_compare`, the untouched static
bench-report renderer, which still joins its own meta strings with `middle
dot` and is explicitly out of this task's file map.

Offline, deterministic, no Docker, no network.
"""

from __future__ import annotations

import re

import dashboard_render
import metrics

SENTINEL = "ZQXJ"

# The eight colour literals REQ-V180-DSH-02/-03 allow: the six named palette
# tokens plus the two status colours (spec-v1.8.0-delta-1.md's frozen table).
ALLOWED_COLOURS = frozenset(
    {
        "#16181c",  # --ink
        "#eef0f2",  # --ground
        "#ffffff",  # --plate
        "#ccd2d8",  # --rule
        "#5f6873",  # --dim
        "#1f5fb0",  # --signal
        "#1c7a4a",  # ok
        "#b23636",  # fault
    }
)

# The closed list of rejected defaults REQ-V180-DSH-04 scans for, as literal
# substrings; `border-radius`, monospace/serif families and off-palette
# colours are checked structurally below, not by substring.
_FORBIDDEN_SUBSTRINGS = ("box-shadow", "text-transform: uppercase", "·", "→")


# ----------------------------------------------------------------------------
# fixture builders
# ----------------------------------------------------------------------------


def make_served_span(
    span_id,
    *,
    parent_span_id=None,
    name=SENTINEL,
    kind=SENTINEL,
    ts=SENTINEL,
    start_ns=0,
    duration_ms=1,
    status=SENTINEL,
    conv_id=1,
    turn_id=1,
    attributes=None,
):
    return dashboard_render.ServedSpan(
        span_id=span_id,
        parent_span_id=parent_span_id,
        name=name,
        kind=kind,
        ts=ts,
        start_ns=start_ns,
        duration_ms=duration_ms,
        status=status,
        conv_id=conv_id,
        turn_id=turn_id,
        attributes=attributes or {},
    )


def sentinel_usage_row():
    return metrics.UsageRow(
        provider=SENTINEL,
        model=SENTINEL,
        purpose=None,
        scenario=None,
        day=None,
        key=SENTINEL,
        calls=1,
        errors=1,
        input_tokens=1,
        output_tokens=1,
        cached_tokens=1,
        reasoning_tokens=1,
        cost_usd=1.0,
        cost_basis=SENTINEL,
        cache_hit_share=0.5,
        reasoning_share=0.5,
    )


def sentinel_tool_health_row():
    return metrics.ToolHealthRow(
        tool=SENTINEL,
        calls=1,
        ok=1,
        error=0,
        budget=0,
        rejected=0,
        refused_repeat=0,
        error_rate=0.1,
        p50_ms=1.0,
        p95_ms=1.0,
        max_consecutive_repeats=1,
        output_tokens_est=1,
    )


def sentinel_summary_health():
    return metrics.SummaryHealth(attempts=1, ok=1, truncated=0, retried=0, failed=0)


def sentinel_trace_row():
    return {
        "trace_id": SENTINEL,
        "ts": SENTINEL,
        "conv_id": 1,
        "turn_id": 1,
        "name": SENTINEL,
        "scenario_id": SENTINEL,
        "span_count": 1,
        "total_duration_ms": 1,
        "status": SENTINEL,
        "chat_count": 1,
        "execute_tool_count": 1,
    }


def _all_sentinel_chrome() -> str:
    """One render of every in-scope builder against a fixture whose every
    interpolated field is the fixed `SENTINEL` string (REQ-V180-DSH-04): the
    output *is* the chrome, so anything forbidden found in it is chrome by
    construction, never a false-fail on user-typed content."""
    usage_row = sentinel_usage_row()
    tool_row = sentinel_tool_health_row()
    span = make_served_span(SENTINEL, attributes={SENTINEL: SENTINEL})
    parts = [
        dashboard_render.STYLE,
        dashboard_render.page(
            SENTINEL,
            nav=[(SENTINEL, "/x")],
            body="<p></p>",
            generated_at=SENTINEL,
        ),
        dashboard_render.usage_section([usage_row], group=SENTINEL, totals=usage_row),
        dashboard_render.tool_health_section([tool_row], summary=sentinel_summary_health()),
        dashboard_render.trace_list_section([sentinel_trace_row()]),
        dashboard_render.trace_tree_section([span]),
        dashboard_render.reading_strip_section(
            calls=1, total_tokens=1, cost_usd=1.0, error_rate=0.1
        ),
    ]
    return "\n".join(parts)


def _rejected_defaults(chrome: str) -> list[str]:
    found = [needle for needle in _FORBIDDEN_SUBSTRINGS if needle in chrome]
    for radius in re.findall(r"border-radius:\s*(\d+)px", chrome):
        if int(radius) > 2:
            found.append(f"border-radius:{radius}px")
    if re.search(r"(?<!sans-)serif", chrome):
        found.append("a serif font-family")
    if "monospace" in chrome:
        found.append("a monospace font-family")
    off_palette = set(re.findall(r"#[0-9a-fA-F]{6}\b", chrome)) - ALLOWED_COLOURS
    if off_palette:
        found.append(f"colour outside the eight: {sorted(off_palette)}")
    return found


# ----------------------------------------------------------------------------
# table row parsing -- REQ-V180-DSH-03's declared-column-spec coverage
# ----------------------------------------------------------------------------

_CELL_RE = re.compile(r'<(th|td)( class="num")?>')


def _row_cells(row_html: str) -> list[tuple[str, bool]]:
    # `re.findall` returns `""` (not `None`) for an optional group that
    # didn't participate in the match, so truthiness -- not `is not None`
    # -- is the correct "does this cell carry class=\"num\"?" test.
    return [(tag, bool(cls)) for tag, cls in _CELL_RE.findall(row_html)]


def _tbody_rows(html: str) -> list[str]:
    rows: list[str] = []
    for tbody in re.findall(r"<tbody>\n?(.*?)\n?</tbody>", html, re.S):
        rows.extend(re.findall(r"<tr>.*?</tr>", tbody, re.S))
    return rows


def _thead_row(html: str) -> str:
    return re.search(r"<thead>(<tr>.*?</tr>)</thead>", html, re.S).group(1)


# ----------------------------------------------------------------------------
# T-V180-DSH-01 -- declared column-spec coverage, exact
# ----------------------------------------------------------------------------


def test_t_v180_dsh_01_style_declares_tabular_nums_and_no_monospace_family():
    assert "font-variant-numeric: tabular-nums" in dashboard_render.STYLE
    assert "monospace" not in dashboard_render.STYLE


def test_t_v180_dsh_01_usage_section_column_spec_is_exact():
    row = sentinel_usage_row()
    html = dashboard_render.usage_section([row], group="model", totals=row)
    expected_head = [("th", False)] + [
        ("th", kind == "num") for _, kind in dashboard_render.USAGE_COLUMNS
    ]
    assert _row_cells(_thead_row(html)) == expected_head

    expected_body = [("th", False)] + [
        ("td", kind == "num") for _, kind in dashboard_render.USAGE_COLUMNS
    ]
    rows = _tbody_rows(html)
    assert len(rows) == 2  # the Totals row and the one "model" row
    for row_html in rows:
        assert _row_cells(row_html) == expected_body


def test_t_v180_dsh_01_tool_health_section_column_spec_is_exact():
    row = sentinel_tool_health_row()
    html = dashboard_render.tool_health_section([row], summary=sentinel_summary_health())
    expected = [
        ("th" if index == 0 else "td", kind == "num")
        for index, (_, kind) in enumerate(dashboard_render.TOOL_HEALTH_COLUMNS)
    ]
    assert _row_cells(_thead_row(html)) == [
        ("th", kind == "num") for _, kind in dashboard_render.TOOL_HEALTH_COLUMNS
    ]
    rows = _tbody_rows(html)
    assert len(rows) == 1
    assert _row_cells(rows[0]) == expected


def test_t_v180_dsh_01_trace_list_section_column_spec_is_exact():
    html = dashboard_render.trace_list_section([sentinel_trace_row()])
    expected = [("td", kind == "num") for _, kind in dashboard_render.TRACE_LIST_COLUMNS]
    assert _row_cells(_thead_row(html)) == [
        ("th", kind == "num") for _, kind in dashboard_render.TRACE_LIST_COLUMNS
    ]
    rows = _tbody_rows(html)
    assert len(rows) == 1
    assert _row_cells(rows[0]) == expected


def test_t_v180_dsh_01_trace_tree_section_renders_no_table():
    """`trace_tree_section` is a `<div>` tree, not a table (REQ-V180-DSH-03's
    "if it renders a table" qualifier) -- there is no column spec to
    declare, and this asserts that stays true rather than silently skipping
    the builder."""
    span = make_served_span(SENTINEL)
    html = dashboard_render.trace_tree_section([span])
    assert "<table" not in html


def test_t_v180_dsh_01_placeholder_cells_keep_their_columns_class():
    """A `None` share renders `_share_cell`'s `—` placeholder, and it
    still sits in a `"num"` column and carries the class (REQ-V180-DSH-03)."""
    row = metrics.UsageRow(
        provider=SENTINEL,
        model=SENTINEL,
        purpose=None,
        scenario=None,
        day=None,
        key=SENTINEL,
        calls=1,
        errors=0,
        input_tokens=1,
        output_tokens=1,
        cached_tokens=0,
        reasoning_tokens=0,
        cost_usd=0.0,
        cost_basis=SENTINEL,
        cache_hit_share=None,
        reasoning_share=None,
    )
    html = dashboard_render.usage_section([row], group="model", totals=row)
    assert '<td class="num">—</td>' in html


# ----------------------------------------------------------------------------
# T-V180-DSH-02 -- the rejected-defaults scanner (negative)
# ----------------------------------------------------------------------------


def test_t_v180_dsh_02_sentinel_is_itself_clean():
    """Sanity: `SENTINEL` must not accidentally contain a forbidden literal,
    or this scanner would false-fail on its own fixture."""
    chrome = SENTINEL
    assert _rejected_defaults(chrome) == []


def test_t_v180_dsh_02_rejected_defaults_absent_from_the_chrome():
    chrome = _all_sentinel_chrome()
    findings = _rejected_defaults(chrome)
    assert findings == [], findings


# ----------------------------------------------------------------------------
# T-V180-DSH-03 -- exactly eight colour literals
# ----------------------------------------------------------------------------


def test_t_v180_dsh_03_exactly_eight_colour_literals_in_style_and_palette():
    style_hexes = set(re.findall(r"#[0-9a-fA-F]{6}\b", dashboard_render.STYLE))
    palette_hexes = set(dashboard_render.PALETTE.values())
    all_hexes = style_hexes | palette_hexes
    assert all_hexes == ALLOWED_COLOURS
    assert len(ALLOWED_COLOURS) == 8


# ----------------------------------------------------------------------------
# T-V180-DSH-04 -- page() nav/structural properties
# ----------------------------------------------------------------------------


def _extract_nav_pairs(html: str) -> list[tuple[str, str]]:
    nav_html = re.search(r"<nav>(.*?)</nav>", html, re.S).group(1)
    return [(label, href) for href, label in re.findall(r'<a href="([^"]*)">([^<]*)</a>', nav_html)]


def test_t_v180_dsh_04_page_renders_any_nav_sequence_in_order():
    """Scope note: DSH-04's "every nav carries the four entries in order" is
    a route-level property of `dashboard_server.py` (T6's, out of this
    file's map). This instead pins the structural property `page()` itself
    owns: any `Sequence[tuple[str, str]]` nav renders as `<a>` tags in the
    given order -- proven here with a four-entry nav (matching the shape
    REQ-V180-DSH-05 will wire in) and, separately, a differently-shaped one,
    so the property is about `page()`'s own rendering, not a hardcoded
    four-entry list."""
    four_entry_nav = [
        ("usage", "/"),
        ("traces", "/traces"),
        ("tools", "/tools"),
        ("conversations", "/conversations"),
    ]
    html = dashboard_render.page(
        "T", nav=four_entry_nav, body="<p>x</p>", generated_at="2026-01-01T00:00:00Z"
    )
    assert _extract_nav_pairs(html) == four_entry_nav

    other_nav = [("a", "/a"), ("b", "/b")]
    html2 = dashboard_render.page(
        "T", nav=other_nav, body="<p>x</p>", generated_at="2026-01-01T00:00:00Z"
    )
    assert _extract_nav_pairs(html2) == other_nav


def test_t_v180_dsh_04_page_emits_one_style_block_no_script_no_external_url():
    html = dashboard_render.page(
        "T",
        nav=[("usage", "/"), ("traces", "/traces")],
        body="<p>x</p>",
        generated_at="2026-01-01T00:00:00Z",
    )
    assert html.count("<style>") == 1
    assert "<script" not in html
    assert "http://" not in html
    assert "https://" not in html
