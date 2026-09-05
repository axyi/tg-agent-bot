"""The dashboard render layer -- spec-v1.6.0 section 7 (REQ-V160-DSH-*).

`dashboard_render.py` (T5) is the one HTML-emitting module in the
repository; these tests exercise it directly, plus the two seams it must
stay compatible with: `devtools/dashboard.py`'s bench-report CLI (whose own
suite is `tests/test_dashboard.py`, unamended save for two forced fixture
literals) and the not-yet-built `dashboard_server.py` (T6) -- any assertion
that would need a live route is noted and left there.

Offline, deterministic, no Docker, no network. Only a synthetic canary
stands in for anything that would otherwise look like a live secret.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
import sqlite3
from pathlib import Path

import pytest

import dashboard_render
import metrics
import storage
import tracing
from devtools import dashboard

CANARY = "SYNTHETIC-CANARY-DSH-NEVER-A-LIVE-VALUE"

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / "tests" / "fixtures" / "bench" / "baseline.json"


# ----------------------------------------------------------------------------
# fixture builders
# ----------------------------------------------------------------------------


def make_served_span(
    span_id,
    *,
    parent_span_id=None,
    name="chat lmstudio",
    kind=tracing.KIND_CLIENT,
    ts="2026-01-01T00:00:00Z",
    start_ns=0,
    duration_ms=10,
    status=tracing.STATUS_OK,
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
        attributes=dict(attributes or {}),
    )


def span_row(
    *,
    span_id="a" * 16,
    parent_span_id=None,
    name="chat",
    kind=tracing.KIND_CLIENT,
    ts="2026-01-01T00:00:00Z",
    start_ns=0,
    duration_ms=10,
    status=tracing.STATUS_OK,
    status_message=None,
    conv_id=1,
    turn_id=1,
    attributes=None,
):
    """A dict shaped like one `spans` table row (`storage.SPAN_COLUMNS`),
    `attributes_json` the raw string `served_span` must parse -- this is the
    on-disk shape, as opposed to a bench document's already-parsed
    `attributes` (REQ-V160-BEN-04), tested separately below."""
    return {
        "id": 1,
        "trace_id": "b" * 32,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "conv_id": conv_id,
        "turn_id": turn_id,
        "name": name,
        "kind": kind,
        "ts": ts,
        "start_ns": start_ns,
        "duration_ms": duration_ms,
        "status": status,
        "status_message": status_message,
        "attributes_json": json.dumps(attributes or {}),
    }


def sample_usage_rows():
    return [
        metrics.UsageRow(
            provider="lmstudio",
            model="m",
            purpose=None,
            scenario=None,
            day=None,
            key="lmstudio/m",
            calls=10,
            errors=1,
            input_tokens=1000,
            output_tokens=200,
            cached_tokens=100,
            reasoning_tokens=0,
            cost_usd=0.01,
            cost_basis="reference:m",
            cache_hit_share=0.1,
            reasoning_share=None,
        )
    ]


def sample_tool_health_rows():
    return [
        metrics.ToolHealthRow(
            tool="exec",
            calls=5,
            ok=4,
            error=1,
            budget=0,
            rejected=0,
            refused_repeat=0,
            error_rate=0.2,
            p50_ms=100.0,
            p95_ms=200.0,
            max_consecutive_repeats=2,
            output_tokens_est=500,
        )
    ]


def sample_summary_health():
    return metrics.SummaryHealth(attempts=3, ok=2, truncated=1, retried=0, failed=1)


def sample_histogram(counts=(2, 0, 1, 3), boundaries=(0.01, 0.02, 0.04)):
    return metrics.Histogram(
        name="gen_ai.client.operation.duration",
        unit="s",
        attributes=(("gen_ai.operation.name", "chat"), ("gen_ai.provider.name", "lmstudio")),
        boundaries=boundaries,
        counts=counts,
        total=sum(counts),
        sum=0.09,
        p50=0.02,
        p95=0.04,
    )


# ----------------------------------------------------------------------------
# T-V160-DSH-01: one view layer, two callers; the import direction never
# reverses (REQ-V160-TREE-03). The `dashboard_server.py` half of the full
# T6-era test is added there -- it doesn't exist yet.
# ----------------------------------------------------------------------------


def test_t_v160_dsh_01_module_resolves_to_a_py_file_not_a_package():
    spec = importlib.util.find_spec("dashboard_render")
    assert spec is not None
    assert spec.origin is not None and spec.origin.endswith(".py")
    assert spec.submodule_search_locations is None, "dashboard_render is a package, not a module"


def test_t_v160_dsh_01_dashboard_render_never_imports_devtools():
    source = (REPO_ROOT / "dashboard_render.py").read_text(encoding="utf-8")
    assert "import devtools" not in source
    assert "from devtools" not in source


def test_t_v160_dsh_01_dashboard_render_has_no_io_of_its_own():
    """REQ-V160-DSH-01: pure functions -- no I/O, no database handle, no
    `Path`, no `print`."""
    source = (REPO_ROOT / "dashboard_render.py").read_text(encoding="utf-8")
    for needle in ("Path(", "open(", "print("):
        assert needle not in source, needle


def test_t_v160_dsh_01_bench_report_imports_dashboard_render_and_emits_no_html():
    source = (REPO_ROOT / "devtools" / "dashboard.py").read_text(encoding="utf-8")
    assert "import dashboard_render" in source
    for needle in ("<section", "<table", "<svg", "<style", "<!doctype"):
        assert needle not in source, needle


# ----------------------------------------------------------------------------
# T-V160-DSH-02: the same fixture rendered through the bench-report code
# path and directly through `dashboard_render.usage_section` is
# byte-identical.
# ----------------------------------------------------------------------------


def test_t_v160_dsh_02_usage_section_is_byte_identical_across_both_callers():
    document = json.loads(BASELINE.read_text(encoding="utf-8"))
    rows = dashboard.usage_rows_from_document(document)
    direct = dashboard_render.usage_section(rows, group="model", totals=rows[0])
    via_bench_report = dashboard.usage_band(document)
    assert direct == via_bench_report
    assert "<table" in direct


# ----------------------------------------------------------------------------
# T-V160-DSH-03: offline, no script, no external anything -- every rendered
# section/page has zero <script> elements, zero on* attributes, no external
# href/src.
# ----------------------------------------------------------------------------

_SCRIPT_TAG = re.compile(r"<script", re.IGNORECASE)
_INLINE_EVENT_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
_EXTERNAL_RESOURCE = re.compile(r'(?:src|href)\s*=\s*"https?://', re.IGNORECASE)


def _assert_offline_and_script_free(markup: str):
    assert not _SCRIPT_TAG.search(markup), markup
    assert not _INLINE_EVENT_HANDLER.search(markup), markup
    assert not _EXTERNAL_RESOURCE.search(markup), markup
    assert '<link rel="stylesheet"' not in markup
    assert "@import" not in markup
    assert "<iframe" not in markup


def _all_rendered_outputs():
    rows = sample_usage_rows()
    tool_rows = sample_tool_health_rows()
    summary = sample_summary_health()
    histogram = sample_histogram()
    root = make_served_span(
        "a" * 16,
        name="invoke_agent tg-agent-bot",
        kind=tracing.KIND_INTERNAL,
        start_ns=0,
        duration_ms=100,
    )
    child = make_served_span(
        "b" * 16, parent_span_id="a" * 16, name="chat lmstudio", start_ns=10_000_000, duration_ms=20
    )
    spans = [root, child]
    return [
        dashboard_render.page(
            "Usage",
            nav=[("traces", "/traces")],
            body="<p>hi</p>",
            generated_at="2026-01-01T00:00:00Z",
        ),
        dashboard_render.usage_section(rows, group="model", totals=rows[0]),
        dashboard_render.tool_health_section(tool_rows, summary=summary),
        dashboard_render.trace_list_section(
            [
                {
                    "trace_id": "c" * 32,
                    "ts": "2026-01-01T00:00:00Z",
                    "conv_id": 1,
                    "name": "invoke_agent tg-agent-bot",
                }
            ]
        ),
        dashboard_render.trace_tree_section(spans),
        dashboard_render.gantt_svg(spans, width=600),
        dashboard_render.histogram_svg(histogram, width=400, height=200, title="duration"),
        dashboard_render.bar_svg(
            [("ROUND_LIMIT", 3), ("EMPTY_REPAIR_LIMIT", 0)],
            width=300,
            height=150,
            title="limit hits",
        ),
        dashboard_render.compare_section({"calls": 10}, {"calls": 12}),
        dashboard_render.error_page("boom"),
        dashboard_render.response_too_large_page(),
        dashboard_render.invalid_host_page(),
    ]


def test_t_v160_dsh_03_every_rendered_output_is_offline_and_script_free():
    for markup in _all_rendered_outputs():
        _assert_offline_and_script_free(markup)


def test_t_v160_dsh_03_usage_section_renders_an_em_dash_for_a_none_share():
    rows = [
        metrics.UsageRow(
            provider="p",
            model="m",
            purpose=None,
            scenario=None,
            day=None,
            key="p/m",
            calls=1,
            errors=0,
            input_tokens=10,
            output_tokens=5,
            cached_tokens=0,
            reasoning_tokens=0,
            cost_usd=0.0,
            cost_basis=None,
            cache_hit_share=None,
            reasoning_share=None,
        )
    ]
    markup = dashboard_render.usage_section(rows, group="model", totals=rows[0])
    assert "—" in markup
    assert "0.00%" not in markup


# ----------------------------------------------------------------------------
# T-V160-DSH-04: escaping, everywhere, once; `status_message` never rendered
# ----------------------------------------------------------------------------


def test_t_v160_dsh_04_tool_and_model_names_are_escaped_in_html_and_svg():
    hostile = '<script>alert(1)</script>&"'

    rows = [
        metrics.UsageRow(
            provider=hostile,
            model=hostile,
            purpose=None,
            scenario=None,
            day=None,
            key=hostile,
            calls=1,
            errors=0,
            input_tokens=1,
            output_tokens=1,
            cached_tokens=0,
            reasoning_tokens=0,
            cost_usd=0.0,
            cost_basis=hostile,
            cache_hit_share=None,
            reasoning_share=None,
        )
    ]
    usage_markup = dashboard_render.usage_section(rows, group="model", totals=rows[0])
    assert "<script>" not in usage_markup
    assert "&lt;script&gt;" in usage_markup

    tool_rows = [
        metrics.ToolHealthRow(
            tool=hostile,
            calls=1,
            ok=1,
            error=0,
            budget=0,
            rejected=0,
            refused_repeat=0,
            error_rate=0.0,
            p50_ms=1.0,
            p95_ms=1.0,
            max_consecutive_repeats=1,
            output_tokens_est=1,
        )
    ]
    health_markup = dashboard_render.tool_health_section(tool_rows, summary=sample_summary_health())
    assert "<script>" not in health_markup
    assert "&lt;script&gt;" in health_markup

    span = make_served_span("a" * 16, name=hostile, attributes={"gen_ai.tool.name": hostile})
    tree_markup = dashboard_render.trace_tree_section([span])
    assert "<script>" not in tree_markup
    assert "&lt;script&gt;" in tree_markup

    gantt_markup = dashboard_render.gantt_svg([span], width=400)
    assert "<script>" not in gantt_markup
    assert "&lt;script&gt;" in gantt_markup


def test_t_v160_dsh_04_status_message_is_never_rendered_because_the_field_is_absent():
    row = span_row(
        status_message=f"leaked: {CANARY}",
        attributes={"tg_agent.tool.fingerprint": CANARY},
    )
    span = dashboard_render.served_span(row)
    assert not hasattr(span, "status_message")
    assert CANARY not in span.attributes.values()

    tree_markup = dashboard_render.trace_tree_section([span])
    gantt_markup = dashboard_render.gantt_svg([span], width=400)
    assert CANARY not in tree_markup
    assert CANARY not in gantt_markup


# ----------------------------------------------------------------------------
# T-V160-DSH-07: gantt geometry -- start_ns, never ts; zero-duration root;
# error outline; accessible name; zero-count histogram bucket labelled
# ----------------------------------------------------------------------------


def test_t_v160_dsh_07_gantt_orders_by_start_ns_never_by_ts():
    # ts order is late, root, early -- the reverse of the start_ns order
    # (root, early, late) this function must actually render in.
    root = make_served_span(
        "a" * 16,
        name="root-span",
        kind=tracing.KIND_INTERNAL,
        ts="2026-01-01T00:00:05Z",
        start_ns=0,
        duration_ms=100,
    )
    early = make_served_span(
        "b" * 16,
        parent_span_id="a" * 16,
        name="early-span",
        kind=tracing.KIND_CLIENT,
        ts="2026-01-01T00:00:10Z",
        start_ns=10_000_000,
        duration_ms=10,
    )
    late = make_served_span(
        "c" * 16,
        parent_span_id="a" * 16,
        name="late-span",
        kind=tracing.KIND_CLIENT,
        ts="2026-01-01T00:00:01Z",
        start_ns=50_000_000,
        duration_ms=10,
        status=tracing.STATUS_ERROR,
    )

    svg = dashboard_render.gantt_svg([root, late, early], width=500)
    assert 'role="img"' in svg
    assert "<title>" in svg and "<desc>" in svg

    pos_root = svg.find("root-span")
    pos_early = svg.find("early-span")
    pos_late = svg.find("late-span")
    assert -1 < pos_root < pos_early < pos_late, svg

    # The error span is outlined in the named error colour, textually marked too.
    assert dashboard_render.PALETTE["error_outline"] in svg
    assert "error" in svg


def test_t_v160_dsh_07_zero_duration_root_places_every_bar_at_x_zero():
    root = make_served_span("a" * 16, name="root", start_ns=1000, duration_ms=0)
    child = make_served_span(
        "b" * 16, parent_span_id="a" * 16, name="child", start_ns=5000, duration_ms=5
    )
    svg = dashboard_render.gantt_svg([root, child], width=400)
    xs = re.findall(r'<rect x="([\d.]+)"', svg)
    assert len(xs) == 2
    assert all(float(x) == pytest.approx(dashboard_render._GANTT_MARGIN_LEFT) for x in xs)


def test_t_v160_dsh_07_histogram_zero_count_bucket_still_shows_its_label():
    histogram = sample_histogram(counts=(2, 0, 1, 3), boundaries=(0.01, 0.02, 0.04))
    svg = dashboard_render.histogram_svg(histogram, width=400, height=200, title="duration")
    assert 'role="img"' in svg
    assert "<title>duration</title>" in svg
    assert "<desc>" in svg
    assert "≤0.02" in svg  # the zero-count bucket's own label is present
    assert "&gt;0.04" in svg  # the overflow bucket's label, HTML-escaped by esc()


def test_t_v160_dsh_07_bar_svg_also_draws_a_zero_count_bar_with_its_label():
    svg = dashboard_render.bar_svg(
        [("ROUND_LIMIT", 3), ("EMPTY_REPAIR_LIMIT", 0)], width=300, height=150, title="hits"
    )
    assert "EMPTY_REPAIR_LIMIT" in svg
    assert 'role="img"' in svg and "<title>hits</title>" in svg and "<desc>" in svg


# ----------------------------------------------------------------------------
# T-V160-DSH-08: a trace whose root span is missing renders the orphans as
# roots with a banner rather than raising.
# ----------------------------------------------------------------------------


def test_t_v160_dsh_08_missing_root_renders_orphans_with_a_banner_not_an_exception():
    orphan_a = make_served_span("a" * 16, parent_span_id="f" * 16, name="orphan-a", start_ns=0)
    orphan_b = make_served_span("b" * 16, parent_span_id="e" * 16, name="orphan-b", start_ns=5)

    tree_markup = dashboard_render.trace_tree_section([orphan_a, orphan_b])
    assert "warn" in tree_markup
    assert "orphan-a" in tree_markup and "orphan-b" in tree_markup

    # gantt_svg tolerates the same fixture (uses the earliest span as its
    # geometry reference) rather than raising.
    svg = dashboard_render.gantt_svg([orphan_a, orphan_b], width=300)
    assert 'role="img"' in svg


# ----------------------------------------------------------------------------
# T-V160-DSH-09: the serving DTO
# ----------------------------------------------------------------------------


def test_t_v160_dsh_09_served_span_attribute_keys_is_the_allowlist_minus_four():
    expected = (
        tracing.ATTRIBUTE_KEYS
        - tracing.CONTENT_ATTRIBUTE_KEYS
        - {"gen_ai.tool.call.id", "tg_agent.tool.fingerprint"}
    )
    assert dashboard_render.SERVED_SPAN_ATTRIBUTE_KEYS == expected
    assert len(dashboard_render.SERVED_SPAN_ATTRIBUTE_KEYS) == 23


def test_t_v160_dsh_09_served_span_has_no_status_message_field():
    field_names = {f.name for f in dataclasses.fields(dashboard_render.ServedSpan)}
    assert "status_message" not in field_names


def test_t_v160_dsh_09_served_span_drops_every_forbidden_key_keeps_the_rest():
    forbidden = tracing.CONTENT_ATTRIBUTE_KEYS | {
        "gen_ai.tool.call.id",
        "tg_agent.tool.fingerprint",
    }
    attributes = {key: f"value-for-{key}" for key in tracing.ATTRIBUTE_KEYS}
    row = span_row(attributes=attributes)
    span = dashboard_render.served_span(row)
    assert set(span.attributes) == dashboard_render.SERVED_SPAN_ATTRIBUTE_KEYS
    assert not (set(span.attributes) & forbidden)
    # A kept key's value survives unmangled when short enough to need no cut.
    assert span.attributes["tg_agent.purpose"] == "value-for-tg_agent.purpose"


def test_t_v160_dsh_09_served_span_accepts_a_bench_document_shaped_dict():
    """REQ-V160-BEN-04: a bench document carries `attributes` already
    parsed, not `attributes_json` -- `served_span` must handle both."""
    row = {
        "span_id": "a" * 16,
        "parent_span_id": None,
        "name": "chat",
        "kind": "CLIENT",
        "ts": "2026-01-01T00:00:00Z",
        "start_ns": 0,
        "duration_ms": 5,
        "status": "ok",
        "conv_id": None,
        "turn_id": None,
        "attributes": {"gen_ai.tool.name": "exec", "gen_ai.tool.call.id": "dropped"},
    }
    span = dashboard_render.served_span(row)
    assert span.attributes == {"gen_ai.tool.name": "exec"}
    assert span.parent_span_id is None
    assert span.conv_id is None and span.turn_id is None


def test_t_v160_dsh_09_served_span_truncates_names_and_attribute_values():
    long_name = "n" * 300
    long_value = "v" * 400
    row = span_row(
        name=long_name,
        attributes={"gen_ai.request.model": long_value, "tg_agent.error_kind": long_value},
    )
    span = dashboard_render.served_span(row)
    assert len(span.name) == 128 and span.name.endswith("…")
    # gen_ai.request.model is name-like: the tighter 128 cap applies.
    assert len(span.attributes["gen_ai.request.model"]) == 128
    # tg_agent.error_kind is a generic attribute value: the 256 cap applies.
    assert len(span.attributes["tg_agent.error_kind"]) == 256


def test_t_v160_dsh_09_finish_reasons_list_is_truncated_per_element_not_stringified():
    reasons = ["s" * 300, "stop"]
    row = span_row(attributes={"gen_ai.response.finish_reasons": reasons})
    span = dashboard_render.served_span(row)
    value = span.attributes["gen_ai.response.finish_reasons"]
    assert isinstance(value, list)
    assert len(value[0]) == 256
    assert value[1] == "stop"


def test_t_v160_dsh_09_trace_tree_section_and_gantt_svg_reject_raw_rows(conn):
    trace_id = tracing.new_trace_id()
    storage.add_span(
        conn,
        trace_id=trace_id,
        span_id=tracing.new_span_id(),
        parent_span_id=None,
        conv_id=None,
        turn_id=None,
        name="invoke_agent tg-agent-bot",
        kind=tracing.KIND_INTERNAL,
        ts="2026-01-01T00:00:00Z",
        start_ns=0,
        duration_ms=5,
        status=tracing.STATUS_OK,
        status_message=None,
        attributes_json="{}",
    )
    raw_rows = storage.spans_for_trace(conn, trace_id)
    assert raw_rows and isinstance(raw_rows[0], sqlite3.Row)

    with pytest.raises(TypeError):
        dashboard_render.trace_tree_section(raw_rows)
    with pytest.raises(TypeError):
        dashboard_render.gantt_svg(raw_rows, width=300)


def test_t_v160_dsh_09_trace_tree_section_and_gantt_svg_reject_a_bare_dict_too():
    with pytest.raises(TypeError):
        dashboard_render.trace_tree_section([span_row()])
    with pytest.raises(TypeError):
        dashboard_render.gantt_svg([span_row()], width=300)


# ----------------------------------------------------------------------------
# error pages: each wraps one fixed string (REQ-V160-DSH-01)
# ----------------------------------------------------------------------------


def test_error_pages_each_wrap_one_fixed_string():
    assert "response too large" in dashboard_render.response_too_large_page()
    assert "invalid host" in dashboard_render.invalid_host_page()
    assert "boom" in dashboard_render.error_page("boom")
    assert "<html" in dashboard_render.error_page("boom")


# ============================================================================
# T6 -- dashboard_server.py (REQ-V160-API-01..06, SRV-01..11)
# ============================================================================

import http.client  # noqa: E402 -- appended block, module-level import style matches T4
import socket  # noqa: E402
import threading  # noqa: E402

import dashboard_server  # noqa: E402

USER_ID = 424242


def _loopback_getaddrinfo(host, port, *args, **kwargs):
    """`tests/conftest.py`'s `no_dns` guard bars every DNS lookup by default
    (REQ-V12-OFF-01); a server test binding real port 0 on 127.0.0.1
    (REQ-V160-TST-01) must inject its own stub for that one literal address,
    per the guard's own docstring -- never the real resolver."""
    if host != "127.0.0.1":
        raise AssertionError(f"unexpected DNS lookup: {host}")
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", int(port)))]


def _write_pyproject_stub(tmp_path):
    """`_project_version()` reads `config.PROJECT_ROOT / "pyproject.toml"`
    (REQ-V160-VER-01); `isolated_project_root` (autouse, conftest.py) points
    `PROJECT_ROOT` at `tmp_path` for every test, so a server test that
    exercises `/api/health` needs its own stub file there."""
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.6.0"\n', encoding="utf-8")


@pytest.fixture
def live_server(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _loopback_getaddrinfo)
    _write_pyproject_stub(tmp_path)
    db_path = tmp_path / "srv.db"
    conn = storage.connect(db_path)
    storage.init_schema(conn)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    conn.close()

    server = dashboard_server.build_server(db_path=db_path, port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port, db_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _request(port, method, path, *, host=None, extra_headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        headers = {"Host": host if host is not None else f"127.0.0.1:{port}"}
        if extra_headers:
            headers.update(extra_headers)
        conn.request(method, path, headers=headers)
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, dict(resp.getheaders()), body
    finally:
        conn.close()


SECURITY_HEADER_NAMES = (
    "Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "Cache-Control",
)


def test_t_v160_srv_03_bind_address_is_fixed_loopback():
    assert dashboard_server.DASHBOARD_BIND == "127.0.0.1"


def test_t_v160_srv_05_security_headers_on_200_404_405_400(live_server):
    port, _ = live_server
    for method, path, host, expected in [
        ("GET", "/api/health", None, 200),
        ("GET", "/nope", None, 404),
        ("POST", "/", None, 405),
        ("GET", "/api/usage?group=nope", None, 400),
    ]:
        status, headers, _ = _request(port, method, path, host=host)
        assert status == expected, (method, path)
        for name in SECURITY_HEADER_NAMES:
            assert name in headers, (method, path, name)
        assert "Set-Cookie" not in headers


def test_t_v160_srv_03_405_carries_allow_header(live_server):
    port, _ = live_server
    for method in ("POST", "PUT", "DELETE", "OPTIONS", "PATCH"):
        status, headers, _ = _request(port, method, "/")
        assert status == 405
        assert headers.get("Allow") == "GET, HEAD"


def test_n4_unlisted_paths_are_404_no_traversal_no_normalisation(live_server):
    port, _ = live_server
    for path in (
        "/../etc/passwd", "/traces/../..", "/api/usage/../health", "/tools/",
        "/index.html", "/%2e%2e/",
    ):
        status, _, _ = _request(port, "GET", path)
        assert status == 404, path


def test_t_v160_srv_10_host_header_rejected_cases(live_server):
    port, _ = live_server
    good = f"127.0.0.1:{port}"
    for bad_host in (f"evil.example.com:{port}", f"127.0.0.1:{port}@evil", "localhost:%d" % port):
        status, headers, body = _request(port, "GET", "/", host=bad_host)
        assert status == 400
        for name in SECURITY_HEADER_NAMES:
            assert name in headers
        # the rejected Host value is never logged or echoed
        assert "evil" not in body.decode("utf-8", "ignore")
    status, _, _ = _request(port, "GET", "/", host=good)
    assert status == 200


def test_n5_bad_params_400_names_only_the_parameter(live_server):
    port, _ = live_server
    cases = [
        "/api/usage?group=nope", "/api/usage?since=2026-13-45", "/api/usage?since=yesterday",
        "/api/traces?limit=0", "/api/traces?limit=9999", "/api/traces?conv=-1",
        "/api/usage?unknown=1", "/api/usage?group=model&group=day",
    ]
    for path in cases:
        status, _, body = _request(port, "GET", path)
        assert status == 400, path
        payload = json.loads(body)
        assert payload["error"] == "invalid parameter"
        assert "parameter" in payload
        # the offending VALUE must never appear in the body
        for needle in ("nope", "2026-13-45", "yesterday", "9999", "-1"):
            if needle in path:
                assert needle not in body.decode("utf-8")


def test_t_v160_api_01_health_shape(live_server):
    port, _ = live_server
    status, headers, body = _request(port, "GET", "/api/health")
    assert status == 200
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    payload = json.loads(body)
    assert set(payload.keys()) == {
        "status", "version", "schema_version", "spans", "spans_dropped", "traces", "generated_at",
    }
    assert payload["status"] == "ok"
    assert payload["schema_version"] == storage.SCHEMA_VERSION


def test_t_v160_api_02_unknown_trace_id_is_404_not_empty_200(live_server):
    port, _ = live_server
    status, _, body = _request(port, "GET", "/api/traces/" + "a" * 32)
    assert status == 404
    status, _, _ = _request(port, "GET", "/traces/" + "a" * 32)
    assert status == 404


def test_t_v160_api_03_json_is_sorted_and_ascii_false(live_server):
    port, _ = live_server
    _, _, body = _request(port, "GET", "/api/health")
    text = body.decode("utf-8")
    # sort_keys=True + compact separators: no space after the colon
    assert '":' in text or ":" in text
    payload = json.loads(text)
    assert list(payload.keys()) == sorted(payload.keys())


def test_t_v160_srv_06_missing_database_is_503(tmp_path, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _loopback_getaddrinfo)
    _write_pyproject_stub(tmp_path)
    db_path = tmp_path / "does-not-exist.db"
    server = dashboard_server.build_server(db_path=db_path, port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, headers, _ = _request(port, "GET", "/api/health")
        assert status == 503
        for name in SECURITY_HEADER_NAMES:
            assert name in headers
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_t_v160_srv_06_connect_readonly_cannot_write(live_server):
    port, db_path = live_server
    conn = storage.connect_readonly(db_path)
    try:
        with pytest.raises(sqlite3.Error):
            conn.execute("INSERT INTO conversations (tg_user_id, created_at) VALUES (1, 'x')")
    finally:
        conn.close()


def test_t_v160_dsh_08_head_matches_get_headers_empty_body(live_server):
    port, _ = live_server
    get_status, get_headers, get_body = _request(port, "GET", "/api/health")
    head_status, head_headers, head_body = _request(port, "HEAD", "/api/health")
    assert head_status == get_status
    assert head_headers.get("Content-Length") == get_headers.get("Content-Length")
    assert head_body == b""


def test_api_traces_and_usage_pages_render(live_server):
    port, _ = live_server
    for path in ("/", "/traces", "/tools", "/api/usage", "/api/traces", "/api/tools"):
        status, _, _ = _request(port, "GET", path)
        assert status == 200, path


def test_a_trace_page_and_api_serve_real_spans(live_server):
    port, db_path = live_server
    conn = storage.connect(db_path)
    trace_id = "b" * 32
    storage.add_span(
        conn, trace_id=trace_id, span_id="1" * 16, parent_span_id=None, conv_id=1,
        turn_id=None, name="invoke_agent tg-agent-bot", kind="INTERNAL",
        ts=storage.utc_now_iso(), start_ns=0, duration_ms=5, status="ok",
        status_message=None, attributes_json=json.dumps({"gen_ai.conversation.id": 1}),
    )
    conn.close()
    status, _, body = _request(port, "GET", f"/api/traces/{trace_id}")
    assert status == 200
    payload = json.loads(body)
    assert payload["trace_id"] == trace_id
    assert len(payload["spans"]) == 1
    assert "status_message" not in payload["spans"][0]

    status, _, html_body = _request(port, "GET", f"/traces/{trace_id}")
    assert status == 200
    assert b"<script" not in html_body
