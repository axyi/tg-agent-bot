"""Self-built tracing: spans, a contextvar tracer, and the sink seam.

Borrows OpenTelemetry GenAI's span shape and attribute names; none of its
code. `tracing.py` has no opinion on how spans reach storage beyond the
`SpanSink` protocol — `agent.py` wires `SqliteSpanSink` in, `devtools/bench.py`
rides along for free.
"""

from __future__ import annotations

import contextlib
import json
import logging
import secrets
import threading
import time
from collections.abc import Iterator, Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Protocol

import config
import storage

log = logging.getLogger("tracing")

KIND_INTERNAL = "INTERNAL"
KIND_CLIENT = "CLIENT"
STATUS_OK = "ok"
STATUS_ERROR = "error"

STATUS_MESSAGE_MAX_CHARS = 200
CONTENT_ATTRIBUTE_MAX_CHARS = 2000

# OpenTelemetry GenAI names, used verbatim as the naming contract.
_GENAI_ATTRIBUTE_KEYS = frozenset(
    {
        "gen_ai.operation.name",
        "gen_ai.provider.name",
        "gen_ai.request.model",
        "gen_ai.response.model",
        "gen_ai.response.finish_reasons",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.cache_read.input_tokens",
        "gen_ai.usage.reasoning.output_tokens",
        "gen_ai.conversation.id",
        "gen_ai.tool.name",
        "gen_ai.tool.call.id",
        "gen_ai.agent.name",
    }
)

# Content attributes: opt-in only, gated by `config.obs_capture_content`.
CONTENT_ATTRIBUTE_KEYS = frozenset(
    {
        "gen_ai.system_instructions",
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.tool.definitions",
    }
)

# Application-specific, namespaced tg_agent.*.
_TG_AGENT_ATTRIBUTE_KEYS = frozenset(
    {
        "tg_agent.purpose",
        "tg_agent.round",
        "tg_agent.attempt",
        "tg_agent.error_kind",
        "tg_agent.tool.outcome",
        "tg_agent.tool.fingerprint",
        "tg_agent.limit_hit",
        "tg_agent.summary.truncated",
        "tg_agent.cost_usd",
        "tg_agent.cost_basis",
        "tg_agent.scenario_id",
        "tg_agent.bench_tag",
        # v1.7.0 addition (REQ-V170-OBS-02): `ReasoningRequest.value`. The
        # honored verdict is derivable from the existing
        # gen_ai.usage.reasoning.output_tokens -- no second key.
        "tg_agent.reasoning.requested",
    }
)

ATTRIBUTE_KEYS: frozenset[str] = (
    _GENAI_ATTRIBUTE_KEYS | CONTENT_ATTRIBUTE_KEYS | _TG_AGENT_ATTRIBUTE_KEYS
)

_SCALAR_ATTRIBUTE_TYPES = (str, int, float, bool, type(None))


def _validate_attribute_value(key: str, value: object) -> None:
    if key == "gen_ai.response.finish_reasons":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"attribute {key!r} must be a list of str")
        return
    if not isinstance(value, _SCALAR_ATTRIBUTE_TYPES):
        raise ValueError(f"attribute {key!r} has a non-serialisable value: {type(value).__name__}")


@dataclass(frozen=True)
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: str
    start_ns: int
    end_ns: int
    ts: str
    status: str
    status_message: str | None
    attributes: dict[str, object]
    conv_id: int | None
    turn_id: int | None


class SpanSink(Protocol):
    def write(self, span: Span) -> None: ...


class NullSink:
    """Drops every span. The default wherever no sink is supplied."""

    def write(self, span: Span) -> None:
        return None


class SqliteSpanSink:
    """Inserts one row into `spans` through `storage.add_span`.

    Failures are never swallowed here: REQ-V160-TRC-07 puts this insert in
    the same transaction as the call row it belongs to, so a raising write
    must propagate unchanged.
    """

    def __init__(self, conn) -> None:
        self._conn = conn

    def write(self, span: Span) -> None:
        duration_ms = max(0, (span.end_ns - span.start_ns) // 1_000_000)
        storage.add_span(
            self._conn,
            trace_id=span.trace_id,
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            conv_id=span.conv_id,
            turn_id=span.turn_id,
            name=span.name,
            kind=span.kind,
            ts=span.ts,
            start_ns=span.start_ns,
            duration_ms=duration_ms,
            status=span.status,
            status_message=span.status_message,
            attributes_json=json.dumps(span.attributes, ensure_ascii=False, sort_keys=True),
        )


_dropped_spans_lock = threading.Lock()
_dropped_spans = 0


def dropped_spans() -> int:
    """Process-wide count of spans a non-sqlite sink failed to write."""
    with _dropped_spans_lock:
        return _dropped_spans


def _record_dropped_span(exc: BaseException) -> None:
    global _dropped_spans
    with _dropped_spans_lock:
        _dropped_spans += 1
    log.warning("span sink write failed: %s", config.redact(f"{type(exc).__name__}: {exc}"))


class MutableSpan:
    """The handle `start_span` yields: a span under construction."""

    def __init__(
        self,
        *,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None,
        name: str,
        kind: str,
        start_ns: int,
        ts: str,
        conv_id: int | None,
        turn_id: int | None,
        sink: SpanSink,
    ) -> None:
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.name = name
        self.kind = kind
        self.start_ns = start_ns
        self.ts = ts
        self.conv_id = conv_id
        self.turn_id = turn_id
        self.attributes: dict[str, object] = {}
        self.status = STATUS_OK
        self.status_message: str | None = None
        self._sink = sink
        self._finished = False

    def set_attribute(self, key: str, value: object) -> None:
        if key not in ATTRIBUTE_KEYS:
            raise ValueError(f"unknown span attribute key: {key!r}")
        _validate_attribute_value(key, value)
        self.attributes[key] = value

    def add_limit_hit(self, name: str) -> None:
        existing = self.attributes.get("tg_agent.limit_hit", "")
        names = set(filter(None, str(existing).split(",")))
        names.add(name)
        self.attributes["tg_agent.limit_hit"] = ",".join(sorted(names))

    def set_error(self, exc_or_kind: BaseException | str) -> None:
        self.status = STATUS_ERROR
        if isinstance(exc_or_kind, BaseException):
            message = f"{type(exc_or_kind).__name__}: {exc_or_kind}"
        else:
            message = str(exc_or_kind)
        message = config.redact(message)
        if len(message) > STATUS_MESSAGE_MAX_CHARS:
            message = message[:STATUS_MESSAGE_MAX_CHARS] + "…"
        self.status_message = message

    def finish(self) -> Span:
        if self._finished:
            raise RuntimeError(f"span already finished: {self.span_id}")
        self._finished = True
        span = Span(
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            name=self.name,
            kind=self.kind,
            start_ns=self.start_ns,
            end_ns=time.monotonic_ns(),
            ts=self.ts,
            status=self.status,
            status_message=self.status_message,
            attributes=dict(self.attributes),
            conv_id=self.conv_id,
            turn_id=self.turn_id,
        )
        if isinstance(self._sink, SqliteSpanSink):
            self._sink.write(span)
        else:
            try:
                self._sink.write(span)
            except Exception as exc:  # noqa: BLE001 -- best-effort sink, never masks the body
                _record_dropped_span(exc)
        return span


_current_span: ContextVar[MutableSpan | None] = ContextVar("_current_span", default=None)


def current_span() -> MutableSpan | None:
    return _current_span.get()


def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


_run_context: dict[str, str | None] = {"scenario_id": None, "bench_tag": None}


def set_run_context(scenario_id: str | None = None, bench_tag: str | None = None) -> None:
    """Set once per bench run; the bot never calls this."""
    _run_context["scenario_id"] = scenario_id
    _run_context["bench_tag"] = bench_tag


@contextlib.contextmanager
def start_span(
    name: str,
    kind: str,
    *,
    sink: SpanSink | None = None,
    attributes: Mapping[str, object] | None = None,
    conv_id: int | None = None,
    turn_id: int | None = None,
    trace_id: str | None = None,
) -> Iterator[MutableSpan]:
    if sink is None:
        sink = NullSink()
    parent = current_span()
    if parent is not None:
        resolved_trace_id = parent.trace_id
        parent_span_id: str | None = parent.span_id
    else:
        resolved_trace_id = trace_id or new_trace_id()
        parent_span_id = None
    span = MutableSpan(
        trace_id=resolved_trace_id,
        span_id=new_span_id(),
        parent_span_id=parent_span_id,
        name=name,
        kind=kind,
        start_ns=time.monotonic_ns(),
        ts=storage.utc_now_iso(),
        conv_id=conv_id,
        turn_id=turn_id,
        sink=sink,
    )
    if parent is None:
        if _run_context["scenario_id"] is not None:
            span.attributes["tg_agent.scenario_id"] = _run_context["scenario_id"]
        if _run_context["bench_tag"] is not None:
            span.attributes["tg_agent.bench_tag"] = _run_context["bench_tag"]
    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)
    token = _current_span.set(span)
    try:
        yield span
    except BaseException as exc:
        if not span._finished:
            span.set_error(exc)
        raise
    finally:
        _current_span.reset(token)
        if not span._finished:
            span.finish()


def set_content_attribute(span: MutableSpan, key: str, value: str, *, capture: bool) -> None:
    """Write one of the four opt-in content attributes, gated by `capture`.

    The caller (`agent.py`) resolves `capture` from `cfg.obs_capture_content`
    at call time; `tracing.py` holds no global config state of its own.
    """
    if not capture:
        return
    text = config.redact(value)
    if len(text) > CONTENT_ATTRIBUTE_MAX_CHARS:
        text = text[:CONTENT_ATTRIBUTE_MAX_CHARS] + "…"
    span.set_attribute(key, text)
