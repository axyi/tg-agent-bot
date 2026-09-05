"""The live dashboard's HTTP server (REQ-V160-SRV-01..11, API-01..06).

Loopback-only, read-only, GET/HEAD only. `bot.py` (T7) constructs the server
via `build_server(...)` after `load_config`, starts it in a daemon thread
before the polling loop, and is responsible for the start/stop guard of
REQ-V160-SRV-07 -- this module raises plainly on a bind failure rather than
swallowing it, so the caller decides what "degraded start" means.

Every response -- 200, 400, 404, 405, 500, 503 -- carries the four security
headers of REQ-V160-SRV-04 and, for HTML, comes from `dashboard_render.py`
(REQ-V160-DSH-01): this module holds no HTML literal of its own. The server
opens one read-only connection per request (`storage.connect_readonly`),
closed in a `finally` block, and never writes.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import tomllib
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import config
import dashboard_render
import metrics
import storage
import tracing

log = logging.getLogger("dashboard")

DASHBOARD_BIND = "127.0.0.1"

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REQUEST_LINE_BYTES = 8 * 1024
MAX_HEADERS = 64

_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SECURITY_HEADERS = (
    ("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src data:"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
)

_STATIC_ROUTES = frozenset(
    {"/", "/traces", "/tools", "/api/health", "/api/usage", "/api/traces", "/api/tools"}
)
_TRACE_PAGE_RE = re.compile(r"^/traces/([0-9a-f]{32})$")
_TRACE_API_RE = re.compile(r"^/api/traces/([0-9a-f]{32})$")


def _project_version() -> str:
    """The single source of truth (REQ-V160-VER-01) -- read fresh each call,
    never cached, so `/api/health` always reports what's actually deployed."""
    path = config.PROJECT_ROOT / "pyproject.toml"
    with path.open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


class _FixedResponse(Exception):
    """Raised internally to short-circuit a handler to a specific status,
    body and content-type without more nesting."""

    def __init__(self, status: int, body: bytes, content_type: str) -> None:
        super().__init__(status)
        self.status = status
        self.body = body
        self.content_type = content_type


def _json_error(name: str) -> bytes:
    return json.dumps(
        {"error": "invalid parameter", "parameter": name}, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")


def _dumps(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _bad_request(name: str, *, is_api: bool) -> None:
    if is_api:
        raise _FixedResponse(400, _json_error(name), "application/json; charset=utf-8")
    raise _FixedResponse(
        400,
        dashboard_render.error_page("invalid parameter").encode("utf-8"),
        "text/html; charset=utf-8",
    )


def _not_found(*, is_api: bool) -> None:
    body = (
        json.dumps({"error": "not found"}, ensure_ascii=False).encode("utf-8")
        if is_api
        else dashboard_render.error_page("not found").encode("utf-8")
    )
    raise _FixedResponse(
        404, body, "application/json; charset=utf-8" if is_api else "text/html; charset=utf-8"
    )


def _service_unavailable(*, is_api: bool) -> None:
    body = (
        json.dumps({"error": "service unavailable"}, ensure_ascii=False).encode("utf-8")
        if is_api
        else dashboard_render.error_page("service unavailable").encode("utf-8")
    )
    raise _FixedResponse(
        503, body, "application/json; charset=utf-8" if is_api else "text/html; charset=utf-8"
    )


def _too_large(*, is_api: bool) -> None:
    body = (
        json.dumps({"error": "response too large"}, ensure_ascii=False).encode("utf-8")
        if is_api
        else dashboard_render.response_too_large_page().encode("utf-8")
    )
    raise _FixedResponse(
        500, body, "application/json; charset=utf-8" if is_api else "text/html; charset=utf-8"
    )


def _parse_query(query: str, allowed: frozenset[str], *, is_api: bool) -> dict[str, str]:
    """Every key must be in `allowed`; a duplicate or unknown key is a 400
    naming the key (REQ-V160-API-03), never the value."""
    pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=False)
    seen: dict[str, str] = {}
    for key, value in pairs:
        if key not in allowed:
            _bad_request(key, is_api=is_api)
        if key in seen:
            _bad_request(key, is_api=is_api)
        seen[key] = value
    return seen


def _parse_group(params: dict[str, str], *, is_api: bool) -> str:
    value = params.get("group", "model")
    if value not in ("model", "day", "purpose", "scenario"):
        _bad_request("group", is_api=is_api)
    return value


def _parse_since(params: dict[str, str], *, is_api: bool) -> date | None:
    if "since" not in params:
        return None
    value = params["since"]
    if not _SINCE_RE.match(value):
        _bad_request("since", is_api=is_api)
    try:
        return date.fromisoformat(value)
    except ValueError:
        _bad_request("since", is_api=is_api)
        raise  # unreachable, satisfies type checkers


def _parse_limit(params: dict[str, str], default: int, *, is_api: bool) -> int:
    if "limit" not in params:
        return default
    value = params["limit"]
    if not re.fullmatch(r"[0-9]+", value):
        _bad_request("limit", is_api=is_api)
    n = int(value)
    if not (1 <= n <= 500):
        _bad_request("limit", is_api=is_api)
    return n


def _parse_conv(params: dict[str, str], *, is_api: bool) -> int | None:
    if "conv" not in params:
        return None
    value = params["conv"]
    if not re.fullmatch(r"[0-9]+", value):
        _bad_request("conv", is_api=is_api)
    n = int(value)
    if not (1 <= n <= 2**31 - 1):
        _bad_request("conv", is_api=is_api)
    return n


def _usage_totals(rows: list[metrics.UsageRow]) -> dict[str, Any]:
    cache_num = sum(
        (r.cache_hit_share or 0.0) * (r.input_tokens) for r in rows if r.cache_hit_share is not None
    )
    return {
        "calls": sum(r.calls for r in rows),
        "errors": sum(r.errors for r in rows),
        "input_tokens": sum(r.input_tokens for r in rows),
        "output_tokens": sum(r.output_tokens for r in rows),
        "cached_tokens": sum(r.cached_tokens for r in rows),
        "reasoning_tokens": sum(r.reasoning_tokens for r in rows),
        "cost_usd": sum(r.cost_usd for r in rows),
        "cost_basis": ", ".join(sorted({r.cost_basis for r in rows if r.cost_basis})) or None,
        "cache_hit_share": (cache_num / sum(r.input_tokens for r in rows))
        if any(r.cache_hit_share is not None for r in rows) and sum(r.input_tokens for r in rows)
        else None,
    }


def _usage_row_json(row: metrics.UsageRow) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": row.key[:128],
        "calls": row.calls,
        "errors": row.errors,
        "gen_ai.usage.input_tokens": row.input_tokens,
        "gen_ai.usage.output_tokens": row.output_tokens,
        "gen_ai.usage.cache_read.input_tokens": row.cached_tokens,
        "gen_ai.usage.reasoning.output_tokens": row.reasoning_tokens,
        "cost_usd": row.cost_usd,
        "cost_basis": row.cost_basis,
        "cache_hit_share": row.cache_hit_share,
        "reasoning_share": row.reasoning_share,
    }
    if row.provider is not None:
        payload["gen_ai.provider.name"] = row.provider
    if row.model is not None:
        payload["gen_ai.request.model"] = row.model
    if row.purpose is not None:
        payload["tg_agent.purpose"] = row.purpose
    if row.scenario is not None:
        payload["tg_agent.scenario_id"] = row.scenario
    if row.day is not None:
        payload["day"] = row.day
    return payload


def _histogram_json(hist: metrics.Histogram) -> dict[str, Any]:
    return {
        "name": hist.name,
        "unit": hist.unit,
        "attributes": dict(hist.attributes),
        "boundaries": list(hist.boundaries),
        "counts": list(hist.counts),
        "total": hist.total,
        "sum": hist.sum,
        "p50": hist.p50,
        "p95": hist.p95,
    }


def _span_json(span: dashboard_render.ServedSpan) -> dict[str, Any]:
    return {
        "span_id": span.span_id,
        "parent_span_id": span.parent_span_id,
        "name": span.name,
        "kind": span.kind,
        "ts": span.ts,
        "start_ns": span.start_ns,
        "duration_ms": span.duration_ms,
        "status": span.status,
        "conv_id": span.conv_id,
        "turn_id": span.turn_id,
        "attributes": dict(span.attributes),
    }


def _trace_row_json(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "trace_id": row["trace_id"],
        "ts": row["ts"],
        "name": row["name"],
        "status": row["status"],
        "conv_id": row["conv_id"],
        "span_count": row["span_count"],
        "total_duration_ms": row["total_duration_ms"],
    }


class DashboardHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def version_string(self) -> str:  # noqa: D102 -- overriding stdlib hook
        return "tg-agent-bot"

    # ------------------------------------------------------------------
    # request-line / header size guard (REQ-V160-SRV-03), before parsing
    # ------------------------------------------------------------------

    def parse_request(self) -> bool:
        if len(self.raw_requestline) > MAX_REQUEST_LINE_BYTES:
            self._matched_route = "(request-line-too-long)"
            self._send_fixed(400, b'{"error":"bad request"}', "application/json; charset=utf-8")
            self.close_connection = True
            return False
        ok = super().parse_request()
        if not ok:
            return False
        if len(self.headers.items()) > MAX_HEADERS:
            self._matched_route = "(too-many-headers)"
            self._send_fixed(400, b'{"error":"bad request"}', "application/json; charset=utf-8")
            self.close_connection = True
            return False
        return True

    # ------------------------------------------------------------------
    # any method other than GET/HEAD -> 405, known or exotic alike
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        if name.startswith("do_"):
            return self._method_not_allowed
        raise AttributeError(name)

    def _method_not_allowed(self) -> None:
        self._matched_route = "(method-not-allowed)"
        body = b'{"error":"method not allowed"}'
        self.send_response(405)
        self.send_header("Allow", "GET, HEAD")
        self._write(body, "application/json; charset=utf-8")

    # ------------------------------------------------------------------
    # GET / HEAD
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        self._handle(send_body=True)

    def do_HEAD(self) -> None:
        self._handle(send_body=False)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 -- stdlib signature
        route = getattr(self, "_matched_route", "?")
        log.debug("%s %s", self.command, route)

    def log_error(self, format: str, *args: Any) -> None:  # noqa: A002 -- stdlib signature
        pass  # never let the stdlib's own error logger print a raw path/value

    # ------------------------------------------------------------------
    # dispatch
    # ------------------------------------------------------------------

    def _handle(self, *, send_body: bool) -> None:
        self._matched_route = "(unmatched)"
        try:
            self._check_host()
            split = urlsplit(self.path)
            path = split.path
            is_api = path.startswith("/api/")
            self._matched_route = path
            self._route(path, split.query, is_api=is_api, send_body=send_body)
        except _FixedResponse as fixed:
            self._respond(fixed.status, fixed.body, fixed.content_type, send_body=send_body)
        except (sqlite3.Error, OSError) as exc:
            log.error(
                "dashboard: database error on %s: %s",
                config.redact(self._matched_route),
                config.redact(f"{type(exc).__name__}: {exc}"),
            )
            body = (
                json.dumps({"error": "service unavailable"}, ensure_ascii=False).encode("utf-8")
                if self._matched_route.startswith("/api/")
                else dashboard_render.error_page("service unavailable").encode("utf-8")
            )
            ctype = (
                "application/json; charset=utf-8"
                if self._matched_route.startswith("/api/")
                else "text/html; charset=utf-8"
            )
            self._respond(503, body, ctype, send_body=send_body)
        except Exception:  # noqa: BLE001 -- the fixed, content-free 500 REQ-V160-SRV-07 wants
            log.error("dashboard: unhandled error on %s", config.redact(self._matched_route))
            is_api = self._matched_route.startswith("/api/")
            body = (
                json.dumps({"error": "internal error"}, ensure_ascii=False).encode("utf-8")
                if is_api
                else dashboard_render.error_page("internal error").encode("utf-8")
            )
            ctype = "application/json; charset=utf-8" if is_api else "text/html; charset=utf-8"
            self._respond(500, body, ctype, send_body=send_body)

    def _check_host(self) -> None:
        values = self.headers.get_all("Host") or []
        port = self.server.server_address[1]
        expected = f"127.0.0.1:{port}"
        is_api = urlsplit(self.path).path.startswith("/api/")
        valid = (
            len(values) == 1
            and values[0] == expected
            and not any(c in values[0] for c in ("\t", "\n", "\r", " ", "@"))
        )
        # An absolute-form request target (`GET http://host/path HTTP/1.1`) is
        # rejected the same way -- checked here too since it names an origin
        # of its own, not this server's loopback bind.
        if self.path.startswith(("http://", "https://")):
            valid = False
        if not valid:
            self._matched_route = "(invalid-host)"
            body = (
                b'{"error":"invalid host"}'
                if is_api
                else dashboard_render.invalid_host_page().encode("utf-8")
            )
            ctype = "application/json; charset=utf-8" if is_api else "text/html; charset=utf-8"
            raise _FixedResponse(400, body, ctype)

    def _route(self, path: str, query: str, *, is_api: bool, send_body: bool) -> None:
        if path == "/":
            return self._page_usage(query, send_body=send_body)
        if path == "/traces":
            return self._page_traces(query, send_body=send_body)
        if path == "/tools":
            return self._page_tools(query, send_body=send_body)
        if path == "/api/health":
            return self._api_health(send_body=send_body)
        if path == "/api/usage":
            return self._api_usage(query, send_body=send_body)
        if path == "/api/traces":
            return self._api_traces(query, send_body=send_body)
        if path == "/api/tools":
            return self._api_tools(query, send_body=send_body)
        match = _TRACE_PAGE_RE.match(path)
        if match:
            return self._page_trace(match.group(1), send_body=send_body)
        match = _TRACE_API_RE.match(path)
        if match:
            return self._api_trace(match.group(1), send_body=send_body)
        _not_found(is_api=is_api)

    # ------------------------------------------------------------------
    # pages
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        return storage.connect_readonly(self.server.db_path)

    def _page_usage(self, query: str, *, send_body: bool) -> None:
        params = _parse_query(query, frozenset({"group", "since"}), is_api=False)
        group = _parse_group(params, is_api=False)
        since = _parse_since(params, is_api=False)
        conn = self._connect()
        try:
            rows = metrics.usage_by(conn, group=group, since=since)
            totals = _usage_totals(rows)
            breakdown = metrics.error_breakdown(conn, since=since)
            latency = metrics.latency_histogram(conn, since=since)
            tokens_in = metrics.token_histogram(conn, token_type="input", since=since)
            tokens_out = metrics.token_histogram(conn, token_type="output", since=since)
            schema = storage.schema_version(conn)
        finally:
            conn.close()
        nav = [
            ("model", "/?group=model"),
            ("day", "/?group=day"),
            ("purpose", "/?group=purpose"),
            ("scenario", "/?group=scenario"),
        ]
        body = [dashboard_render.usage_section(rows, group=group, totals=totals)]
        for hist in latency:
            body.append(
                dashboard_render.histogram_svg(hist, width=640, height=160, title="Latency")
            )
        for hist in tokens_in + tokens_out:
            body.append(dashboard_render.histogram_svg(hist, width=640, height=160, title="Tokens"))
        body.append(dashboard_render.error_breakdown_section(breakdown))
        footer = f"db: {Path(self.server.db_path).name} · schema v{schema}"
        html = dashboard_render.page(
            "Usage",
            nav=nav,
            body="\n".join(body) + "\n" + dashboard_render.meta_line(footer),
            generated_at=storage.utc_now_iso(),
        )
        self._respond(200, html.encode("utf-8"), "text/html; charset=utf-8", send_body=send_body)

    def _page_traces(self, query: str, *, send_body: bool) -> None:
        params = _parse_query(query, frozenset({"limit", "conv"}), is_api=False)
        limit = _parse_limit(params, 50, is_api=False)
        conv = _parse_conv(params, is_api=False)
        conn = self._connect()
        try:
            traces = storage.recent_traces(conn, limit=limit, conv_id=conv)
        finally:
            conn.close()
        html = dashboard_render.page(
            "Traces",
            nav=[("usage", "/"), ("tools", "/tools")],
            body=dashboard_render.trace_list_section(traces),
            generated_at=storage.utc_now_iso(),
        )
        self._respond(200, html.encode("utf-8"), "text/html; charset=utf-8", send_body=send_body)

    def _page_tools(self, query: str, *, send_body: bool) -> None:
        _parse_query(query, frozenset(), is_api=False)
        conn = self._connect()
        try:
            rows = metrics.tool_health(conn)
            summary = metrics.summary_health(conn)
            hits = metrics.limit_hits(conn)
        finally:
            conn.close()
        body = [
            dashboard_render.tool_health_section(rows, summary=summary),
            dashboard_render.bar_svg(
                sorted(hits.items()), width=640, height=160, title="Limit hits"
            ),
        ]
        html = dashboard_render.page(
            "Tools",
            nav=[("usage", "/"), ("traces", "/traces")],
            body="\n".join(body),
            generated_at=storage.utc_now_iso(),
        )
        self._respond(200, html.encode("utf-8"), "text/html; charset=utf-8", send_body=send_body)

    def _page_trace(self, trace_id: str, *, send_body: bool) -> None:
        conn = self._connect()
        try:
            rows = storage.spans_for_trace(conn, trace_id)
        finally:
            conn.close()
        if not rows:
            _not_found(is_api=False)
        if len(rows) > dashboard_render.MAX_SPANS_PER_TRACE:
            _too_large(is_api=False)
        spans = [dashboard_render.served_span(row) for row in rows]
        body = dashboard_render.gantt_svg(spans, width=640) + dashboard_render.trace_tree_section(
            spans
        )
        html = dashboard_render.page(
            f"Trace {trace_id[:12]}",
            nav=[("usage", "/"), ("traces", "/traces"), ("tools", "/tools")],
            body=body,
            generated_at=storage.utc_now_iso(),
        )
        self._respond(200, html.encode("utf-8"), "text/html; charset=utf-8", send_body=send_body)

    # ------------------------------------------------------------------
    # JSON API
    # ------------------------------------------------------------------

    def _api_health(self, *, send_body: bool) -> None:
        conn = self._connect()
        try:
            spans = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
            traces = conn.execute(
                "SELECT COUNT(DISTINCT trace_id) FROM spans WHERE parent_span_id IS NULL"
            ).fetchone()[0]
            schema = storage.schema_version(conn)
        finally:
            conn.close()
        payload = {
            "status": "ok",
            "version": _project_version(),
            "schema_version": schema,
            "spans": spans,
            "spans_dropped": tracing.dropped_spans(),
            "traces": traces,
            "generated_at": storage.utc_now_iso(),
        }
        self._respond_json(200, payload, send_body=send_body)

    def _api_usage(self, query: str, *, send_body: bool) -> None:
        params = _parse_query(query, frozenset({"group", "since"}), is_api=True)
        group = _parse_group(params, is_api=True)
        since = _parse_since(params, is_api=True)
        conn = self._connect()
        try:
            rows = metrics.usage_by(conn, group=group, since=since)
        finally:
            conn.close()
        payload = {
            "group": group,
            "since": since.isoformat() if since else None,
            "rows": [_usage_row_json(row) for row in rows],
            "totals": _usage_totals(rows),
        }
        self._respond_json(200, payload, send_body=send_body)

    def _api_traces(self, query: str, *, send_body: bool) -> None:
        params = _parse_query(query, frozenset({"limit", "conv"}), is_api=True)
        limit = _parse_limit(params, 50, is_api=True)
        conv = _parse_conv(params, is_api=True)
        conn = self._connect()
        try:
            traces = storage.recent_traces(conn, limit=limit, conv_id=conv)
        finally:
            conn.close()
        payload = {
            "limit": limit,
            "conv": conv,
            "traces": [_trace_row_json(row) for row in traces],
        }
        self._respond_json(200, payload, send_body=send_body)

    def _api_trace(self, trace_id: str, *, send_body: bool) -> None:
        conn = self._connect()
        try:
            rows = storage.spans_for_trace(conn, trace_id)
        finally:
            conn.close()
        if not rows:
            _not_found(is_api=True)
        if len(rows) > dashboard_render.MAX_SPANS_PER_TRACE:
            _too_large(is_api=True)
        spans = [dashboard_render.served_span(row) for row in rows]
        payload = {"trace_id": trace_id, "spans": [_span_json(span) for span in spans]}
        self._respond_json(200, payload, send_body=send_body)

    def _api_tools(self, query: str, *, send_body: bool) -> None:
        params = _parse_query(query, frozenset({"since"}), is_api=True)
        since = _parse_since(params, is_api=True)
        conn = self._connect()
        try:
            rows = metrics.tool_health(conn, since=since)
            hits = metrics.limit_hits(conn, since=since)
            summary = metrics.summary_health(conn, since=since)
            retried, total = metrics.retry_rate(conn, since=since)
            mean_messages, max_messages = metrics.context_pressure(conn, since=since)
        finally:
            conn.close()
        payload = {
            "since": since.isoformat() if since else None,
            "tools": [
                {
                    "tool": row.tool,
                    "calls": row.calls,
                    "ok": row.ok,
                    "error": row.error,
                    "budget": row.budget,
                    "rejected": row.rejected,
                    "refused_repeat": row.refused_repeat,
                    "error_rate": row.error_rate,
                    "p50_ms": row.p50_ms,
                    "p95_ms": row.p95_ms,
                    "max_consecutive_repeats": row.max_consecutive_repeats,
                    "output_tokens_est": row.output_tokens_est,
                }
                for row in rows
            ],
            "limit_hits": hits,
            "summary": {
                "attempts": summary.attempts,
                "ok": summary.ok,
                "truncated": summary.truncated,
                "retried": summary.retried,
                "failed": summary.failed,
            },
            "retry_rate": [retried, total],
            "context_pressure": [mean_messages, max_messages],
        }
        self._respond_json(200, payload, send_body=send_body)

    # ------------------------------------------------------------------
    # response plumbing (REQ-V160-API-05, SRV-04)
    # ------------------------------------------------------------------

    def _respond_json(self, status: int, payload: Any, *, send_body: bool) -> None:
        self._respond(
            status, _dumps(payload), "application/json; charset=utf-8", send_body=send_body
        )

    def _respond(self, status: int, body: bytes, content_type: str, *, send_body: bool) -> None:
        if len(body) > MAX_RESPONSE_BYTES:
            is_api = self._matched_route.startswith("/api/")
            body = (
                json.dumps({"error": "response too large"}, ensure_ascii=False).encode("utf-8")
                if is_api
                else dashboard_render.response_too_large_page().encode("utf-8")
            )
            content_type = (
                "application/json; charset=utf-8" if is_api else "text/html; charset=utf-8"
            )
            status = 500
        self.send_response(status)
        self._write(body, content_type, send_body=send_body)

    def _send_fixed(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self._write(body, content_type, send_body=True)

    def _write(self, body: bytes, content_type: str, *, send_body: bool = True) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in _SECURITY_HEADERS:
            self.send_header(name, value)
        self.end_headers()
        if send_body:
            self.wfile.write(body)


def build_server(*, db_path: Path, port: int, host: str = DASHBOARD_BIND) -> ThreadingHTTPServer:
    """Constructs and binds the server; raises `OSError` on a bind failure
    (a busy port, permission denied) rather than swallowing it -- the
    REQ-V160-SRV-07 degraded-start guard is the caller's (`bot.py`, T7)."""
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    server.daemon_threads = True
    server.db_path = db_path  # type: ignore[attr-defined]
    return server
