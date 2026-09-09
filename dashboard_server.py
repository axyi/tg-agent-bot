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
    {
        "/",
        "/traces",
        "/tools",
        "/api/health",
        "/api/usage",
        "/api/traces",
        "/api/tools",
        "/conversations",
        "/api/conversations",
    }
)
_TRACE_PAGE_RE = re.compile(r"^/traces/([0-9a-f]{32})$")
_TRACE_API_RE = re.compile(r"^/api/traces/([0-9a-f]{32})$")
_CONV_PAGE_RE = re.compile(r"^/conversations/([0-9]{1,10})$")
_CONV_API_RE = re.compile(r"^/api/conversations/([0-9]{1,10})$")

# REQ-V180-CONV-04: default 200/max 500 -- same bound as any other `limit`
# (_parse_limit), reused as-is (see task-brief v180-T6).
TRANSCRIPT_MESSAGE_CONTENT_MAX_CHARS = tracing.CONTENT_ATTRIBUTE_MAX_CHARS  # 2000, REQ-V160-TRC-09


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


_CURSOR_RE = re.compile(r"([0-9]{1,10})-([0-9]{1,10})")


def _parse_cursor(params: dict[str, str], *, is_api: bool) -> tuple[int, int] | None:
    """`_parse_conv`'s shape: absent -> `None` (the first page); present but
    not `re.fullmatch`-shaped -> 400. Only the *shape* is validated here --
    whether the pair names a real message of the conversation is
    `storage.conversation_messages`'s own `ValueError` (REQ-V180-CONV-04),
    which the route turns into the same 400."""
    if "cursor" not in params:
        return None
    match = _CURSOR_RE.fullmatch(params["cursor"])
    if not match:
        _bad_request("cursor", is_api=is_api)
        return None  # unreachable: _bad_request always raises
    return int(match.group(1)), int(match.group(2))


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


def _conversation_row_json(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tg_user_id": row["tg_user_id"],
        "created_at": row["created_at"],
        "active": bool(row["active"]),
        "message_count": row["message_count"],
        "last_activity": row["last_activity"],
    }


# ----------------------------------------------------------------------------
# REQ-V180-SEC-01/-02 item 1: the one place a `messages` row (from
# `storage.conversation_messages`) is redacted and per-message truncated,
# shared identically by both the HTML route (feeds
# `dashboard_render.conversation_transcript_section`, which only escapes)
# and the JSON route (serialized as-is -- `json.dumps` does its own
# escaping). `dashboard_render.py` stays pure and never imports `config`.
# ----------------------------------------------------------------------------


def _redact_message(row: Any) -> dict[str, Any]:
    """`config.redact()` on `content`, `role` and `tool_call_id` alike
    (REQ-V180-SEC-01 -- not `content` alone), then `content` cut to
    `TRANSCRIPT_MESSAGE_CONTENT_MAX_CHARS` characters of the *redacted*
    plain text, before any escaping, so both sinks cut at the identical
    boundary (REQ-V180-SEC-02 item 1). A truncation note is appended when
    (and only when) the cut actually happened -- additional to the 2000
    characters, counted only by the page's own byte budget. `tool_call_id`
    stays `None` when absent rather than becoming the string `"None"`."""
    role = config.redact(str(row["role"]))
    tool_call_id = row["tool_call_id"]
    if tool_call_id is not None:
        tool_call_id = config.redact(str(tool_call_id))
    content = config.redact(str(row["content"]))
    if len(content) > TRANSCRIPT_MESSAGE_CONTENT_MAX_CHARS:
        original_len = len(content)
        content = (
            content[:TRANSCRIPT_MESSAGE_CONTENT_MAX_CHARS]
            + f"\n… [truncated to {TRANSCRIPT_MESSAGE_CONTENT_MAX_CHARS} "
            f"of {original_len} characters]"
        )
    return {
        "turn_id": row["turn_id"],
        "id": row["id"],
        "role": role,
        "content": content,
        "tool_call_id": tool_call_id,
        "created_at": row["created_at"],
    }


# ----------------------------------------------------------------------------
# REQ-V180-SEC-02 item 3, JSON sink: `/api/conversations/<id>` does not go
# through `dashboard_render.conversation_transcript_section` (the HTML
# builder) -- it applies the same atomic-turn-admission algorithm
# independently, against `_dumps`-shaped JSON bytes instead of HTML bytes.
# ----------------------------------------------------------------------------


def _json_message_bytes(msg: dict[str, Any]) -> int:
    return len(_dumps(msg))


def _admit_json_transcript(
    messages: list[dict[str, Any]],
    *,
    envelope_bytes: int,
    reader_next_cursor: tuple[int, int] | None,
    budget_bytes: int = dashboard_render.TRANSCRIPT_PAGE_BUDGET_BYTES,
    suffix_bytes: int = dashboard_render.TRANSCRIPT_PAGE_SUFFIX_BYTES,
) -> tuple[list[dict[str, Any]], tuple[int, int] | None]:
    """CONV-04's atomic turn admission, reimplemented against JSON bytes
    (`messages` already redacted/truncated by `_redact_message`, in
    `turn_id`/`id` order). `envelope_bytes` is the caller's measured size of
    the payload's fixed keys (`conv`/`limit`/`cursor`/`next_cursor`/
    `messages` skeleton, `messages` empty) -- the JSON analogue of
    `chrome_bytes`. Same per-turn order as the HTML side: (1) measure the
    whole turn; (2) fits -> admit whole; (3) doesn't fit, page already holds
    a turn -> stop; (4) doesn't fit, page empty -> split, admitting at least
    one message and marking it `continued`. Returns `(messages, next_cursor)`
    with the same reconciliation rule: a budget-forced stop's cursor always
    wins over `reader_next_cursor`, which is only ever the fallback."""
    accumulator = envelope_bytes + suffix_bytes

    groups: list[tuple[int, list[dict[str, Any]]]] = []
    for msg in messages:
        turn_id = msg["turn_id"]
        if groups and groups[-1][0] == turn_id:
            groups[-1][1].append(msg)
        else:
            groups.append((turn_id, [msg]))

    if not groups:
        return [], reader_next_cursor

    admitted: list[dict[str, Any]] = []
    next_cursor: tuple[int, int] | None = None

    for turn_id, turn_messages in groups:
        joiner = 1 if admitted else 0
        turn_bytes = (
            joiner
            + sum(_json_message_bytes(m) for m in turn_messages)
            + (len(turn_messages) - 1)  # commas between this turn's own messages
        )

        if accumulator + turn_bytes <= budget_bytes:
            admitted.extend(turn_messages)
            accumulator += turn_bytes
            continue

        if admitted:
            # case 3: the page already holds a turn -- stop here.
            next_cursor = (turn_id, turn_messages[0]["id"])
            break

        # case 4: the page is empty -- split this turn, admitting at least
        # one message so the page always advances.
        partial: list[dict[str, Any]] = []
        partial_bytes = 0
        withheld_cursor: tuple[int, int] | None = None
        for msg in turn_messages:
            msg_bytes = _json_message_bytes(msg) + (1 if partial else 0)
            if not partial or accumulator + partial_bytes + msg_bytes <= budget_bytes:
                partial.append(msg)
                partial_bytes += msg_bytes
            else:
                withheld_cursor = (turn_id, msg["id"])
                break
        if withheld_cursor is not None:
            partial[-1] = {**partial[-1], "continued": True}
        admitted.extend(partial)
        accumulator += partial_bytes
        if withheld_cursor is not None:
            next_cursor = withheld_cursor
            break
        # the whole turn ended up fitting message-by-message after all --
        # not a split, keep going (mirrors conversation_transcript_section).

    if next_cursor is None:
        next_cursor = reader_next_cursor
    return admitted, next_cursor


# ----------------------------------------------------------------------------
# REQ-V180-CONV-04 HTML sink: the subset of `messages` this page actually
# rendered, decided by `next_cursor` -- data only (no HTML literal, so this
# stays in this module; the footer markup itself is
# `dashboard_render.transcript_page_footer`, REQ-V160-DSH-01).
# ----------------------------------------------------------------------------


def _rendered_page_messages(
    messages: list[dict[str, Any]], next_cursor: tuple[int, int] | None
) -> list[dict[str, Any]]:
    """Everything before the message `next_cursor` names, or all of
    `messages` when there is no next_cursor, or it names nothing in
    `messages` (the reader's own next-page cursor rather than a byte-budget
    stop)."""
    if next_cursor is None:
        return messages
    for i, msg in enumerate(messages):
        if (msg["turn_id"], msg["id"]) == next_cursor:
            return messages[:i]
    return messages


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
        if path == "/conversations":
            return self._page_conversations(query, send_body=send_body)
        if path == "/api/health":
            return self._api_health(send_body=send_body)
        if path == "/api/usage":
            return self._api_usage(query, send_body=send_body)
        if path == "/api/traces":
            return self._api_traces(query, send_body=send_body)
        if path == "/api/tools":
            return self._api_tools(query, send_body=send_body)
        if path == "/api/conversations":
            return self._api_conversations(query, send_body=send_body)
        match = _TRACE_PAGE_RE.match(path)
        if match:
            return self._page_trace(match.group(1), send_body=send_body)
        match = _TRACE_API_RE.match(path)
        if match:
            return self._api_trace(match.group(1), send_body=send_body)
        match = _CONV_PAGE_RE.match(path)
        if match:
            conv_id = int(match.group(1))
            if not (1 <= conv_id <= 2**31 - 1):
                _not_found(is_api=is_api)
            return self._page_conversation(conv_id, query, send_body=send_body)
        match = _CONV_API_RE.match(path)
        if match:
            conv_id = int(match.group(1))
            if not (1 <= conv_id <= 2**31 - 1):
                _not_found(is_api=is_api)
            return self._api_conversation(conv_id, query, send_body=send_body)
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
            ("conversations", "/conversations"),
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
            nav=[("usage", "/"), ("tools", "/tools"), ("conversations", "/conversations")],
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
            nav=[("usage", "/"), ("traces", "/traces"), ("conversations", "/conversations")],
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
            nav=[
                ("usage", "/"),
                ("traces", "/traces"),
                ("tools", "/tools"),
                ("conversations", "/conversations"),
            ],
            body=body,
            generated_at=storage.utc_now_iso(),
        )
        self._respond(200, html.encode("utf-8"), "text/html; charset=utf-8", send_body=send_body)

    _CONVERSATIONS_NAV = [
        ("usage", "/"),
        ("traces", "/traces"),
        ("tools", "/tools"),
        ("conversations", "/conversations"),
    ]

    def _page_conversations(self, query: str, *, send_body: bool) -> None:
        params = _parse_query(query, frozenset({"limit"}), is_api=False)
        limit = _parse_limit(params, 50, is_api=False)
        conn = self._connect()
        try:
            rows = storage.recent_conversations(conn, limit=limit)
        finally:
            conn.close()
        body = dashboard_render.meta_line(
            "A conversation is one `/new`-to-`/new` stretch of chat; this is the list of them."
        ) + dashboard_render.conversation_list_section(rows)
        html = dashboard_render.page(
            "Conversations",
            nav=self._CONVERSATIONS_NAV,
            body=body,
            generated_at=storage.utc_now_iso(),
        )
        self._respond(200, html.encode("utf-8"), "text/html; charset=utf-8", send_body=send_body)

    def _page_conversation(self, conv_id: int, query: str, *, send_body: bool) -> None:
        params = _parse_query(query, frozenset({"limit", "cursor"}), is_api=False)
        limit = _parse_limit(params, 200, is_api=False)
        cursor = _parse_cursor(params, is_api=False)
        conn = self._connect()
        try:
            conv_row = storage.conversation_row(conn, conv_id)
            if conv_row is None:
                _not_found(is_api=False)
            try:
                rows, reader_next_cursor = storage.conversation_messages(
                    conn, conv_id, limit=limit, cursor=cursor
                )
            except ValueError:
                _bad_request("cursor", is_api=False)
                return  # unreachable: _bad_request always raises
            turn_ids = sorted({row["turn_id"] for row in rows})
            trace_map = storage.conversation_turn_traces(conn, conv_id, turn_ids)
        finally:
            conn.close()

        messages = [_redact_message(row) for row in rows]
        title = f"Conversation {conv_id}"
        generated_at = storage.utc_now_iso()

        # Pass 1: the page shell with an empty body -- REQ-V180-SEC-02 item 3
        # requires the accumulator's chrome seed to be *measured*, not
        # estimated.
        placeholder_html = dashboard_render.page(
            title, nav=self._CONVERSATIONS_NAV, body="", generated_at=generated_at
        )
        chrome_bytes = len(placeholder_html.encode("utf-8"))

        transcript_html, next_cursor, _split = dashboard_render.conversation_transcript_section(
            messages,
            chrome_bytes=chrome_bytes,
            reader_next_cursor=reader_next_cursor,
            trace_map=trace_map,
        )

        # `conversation_transcript_section` renders the rows and the
        # continued-note only -- the range note, next link and first-page
        # link are `transcript_page_footer`'s job, sized within
        # TRANSCRIPT_PAGE_SUFFIX_BYTES's headroom (REQ-V180-CONV-04).
        rendered = _rendered_page_messages(messages, next_cursor)
        body = transcript_html + dashboard_render.transcript_page_footer(
            rendered, conv_id=conv_id, limit=limit, next_cursor=next_cursor
        )
        html = dashboard_render.page(
            title, nav=self._CONVERSATIONS_NAV, body=body, generated_at=generated_at
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

    def _api_conversations(self, query: str, *, send_body: bool) -> None:
        params = _parse_query(query, frozenset({"limit"}), is_api=True)
        limit = _parse_limit(params, 50, is_api=True)
        conn = self._connect()
        try:
            rows = storage.recent_conversations(conn, limit=limit)
        finally:
            conn.close()
        payload = {
            "limit": limit,
            "conversations": [_conversation_row_json(row) for row in rows],
        }
        self._respond_json(200, payload, send_body=send_body)

    def _api_conversation(self, conv_id: int, query: str, *, send_body: bool) -> None:
        params = _parse_query(query, frozenset({"limit", "cursor"}), is_api=True)
        limit = _parse_limit(params, 200, is_api=True)
        cursor = _parse_cursor(params, is_api=True)
        conn = self._connect()
        try:
            conv_row = storage.conversation_row(conn, conv_id)
            if conv_row is None:
                _not_found(is_api=True)
            try:
                rows, reader_next_cursor = storage.conversation_messages(
                    conn, conv_id, limit=limit, cursor=cursor
                )
            except ValueError:
                _bad_request("cursor", is_api=True)
                return  # unreachable: _bad_request always raises
        finally:
            conn.close()

        # REQ-V180-CONV-06's payload has no trace_id field -- unlike the HTML
        # rail, the JSON mirror does not compute `conversation_turn_traces`.
        messages = [_redact_message(row) for row in rows]
        cursor_echo = f"{cursor[0]}-{cursor[1]}" if cursor is not None else None
        envelope_bytes = len(
            _dumps(
                {
                    "conv": conv_id,
                    "limit": limit,
                    "cursor": cursor_echo,
                    "next_cursor": None,
                    "messages": [],
                }
            )
        )
        admitted, next_cursor = _admit_json_transcript(
            messages, envelope_bytes=envelope_bytes, reader_next_cursor=reader_next_cursor
        )
        next_cursor_echo = f"{next_cursor[0]}-{next_cursor[1]}" if next_cursor is not None else None
        payload = {
            "conv": conv_id,
            "limit": limit,
            "cursor": cursor_echo,
            "next_cursor": next_cursor_echo,
            "messages": admitted,
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
