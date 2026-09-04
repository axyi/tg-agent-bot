"""Tracing layer -- spec-v1.6.0 section 5 (REQ-V160-TRC-*), T1's own tests.

Offline, deterministic, no Docker, no network. Only synthetic canaries are
used as secrets, registered through `config.register_secret`.
"""

from __future__ import annotations

import importlib.util
import logging

import pytest

import config
import tracing

CANARY = "SYNTHETIC-CANARY-TRC-NEVER-A-LIVE-VALUE"


@pytest.fixture(autouse=True)
def _reset_tracing_state():
    tracing._dropped_spans = 0
    tracing.set_run_context(None, None)
    yield
    tracing.set_run_context(None, None)


# --- T-V160-TRC-01 -----------------------------------------------------


def test_t_v160_trc_01_module_resolves_to_a_py_file_not_a_package():
    # dashboard_render and dashboard_server are added at T5/T6; this check
    # widens to cover them once those modules exist (REQ-V160-TREE-03).
    for name in ("tracing",):
        spec = importlib.util.find_spec(name)
        assert spec is not None, name
        assert spec.origin is not None and spec.origin.endswith(".py"), name
        assert spec.submodule_search_locations is None, f"{name} is a package, not a module"


# --- T-V160-TRC-02 -------------------------------------------------------


def test_t_v160_trc_02_ids_are_fixed_width_hex_and_unique():
    trace_id = tracing.new_trace_id()
    span_id = tracing.new_span_id()
    assert len(trace_id) == 32
    assert all(c in "0123456789abcdef" for c in trace_id)
    assert len(span_id) == 16
    assert all(c in "0123456789abcdef" for c in span_id)
    assert tracing.new_span_id() != tracing.new_span_id()


def test_t_v160_trc_02_nested_span_inherits_trace_and_records_parent():
    with tracing.start_span("outer", tracing.KIND_INTERNAL) as outer:
        with tracing.start_span("inner", tracing.KIND_CLIENT) as inner:
            assert inner.trace_id == outer.trace_id
            assert inner.parent_span_id == outer.span_id
            assert inner.span_id != outer.span_id


# --- T-V160-TRC-09 ---------------------------------------------------------


def test_t_v160_trc_09_set_attribute_rejects_unlisted_key():
    with tracing.start_span("s", tracing.KIND_INTERNAL) as span:
        with pytest.raises(ValueError, match="bogus.key"):
            span.set_attribute("bogus.key", "x")


def test_t_v160_trc_09_content_attributes_absent_when_capture_is_false():
    with tracing.start_span("s", tracing.KIND_CLIENT) as span:
        for key in tracing.CONTENT_ATTRIBUTE_KEYS:
            tracing.set_content_attribute(span, key, "some content", capture=False)
        assert not (tracing.CONTENT_ATTRIBUTE_KEYS & span.attributes.keys())


def test_t_v160_trc_09_content_attributes_present_when_capture_is_true():
    with tracing.start_span("s", tracing.KIND_CLIENT) as span:
        for key in tracing.CONTENT_ATTRIBUTE_KEYS:
            tracing.set_content_attribute(span, key, "some content", capture=True)
        assert tracing.CONTENT_ATTRIBUTE_KEYS <= span.attributes.keys()


# --- T-V160-TRC-11 -----------------------------------------------------


def test_t_v160_trc_11_status_message_is_redacted_then_truncated(monkeypatch):
    config.register_secret(CANARY)
    captured = {}
    monkeypatch.setattr(
        tracing.NullSink, "write", lambda self, span: captured.__setitem__("span", span)
    )
    with pytest.raises(RuntimeError):
        with tracing.start_span("s", tracing.KIND_INTERNAL):
            raise RuntimeError("boom: " + CANARY)
    message = captured["span"].status_message
    assert CANARY not in message
    assert config.REDACTION in message


def test_t_v160_trc_11_secret_straddling_the_boundary_does_not_survive(monkeypatch):
    # redact-then-truncate order matters exactly here: "RuntimeError: " (14
    # chars) + 180 filler puts the secret's 32 characters spanning position
    # 200 in the *unredacted* text. A truncate-first bug would leave a
    # fragment of the raw secret sitting in the 200-character result,
    # unmatched by redact()'s whole-string replacement.
    config.register_secret(CANARY)
    captured = {}
    monkeypatch.setattr(
        tracing.NullSink, "write", lambda self, span: captured.__setitem__("span", span)
    )
    padding = "x" * 180
    with pytest.raises(RuntimeError):
        with tracing.start_span("s", tracing.KIND_INTERNAL):
            raise RuntimeError(padding + CANARY)
    message = captured["span"].status_message
    assert CANARY not in message
    assert CANARY[:16] not in message
    assert CANARY[-16:] not in message


# --- T-V160-TRC-12 -----------------------------------------------------


def test_t_v160_trc_12_exception_sets_error_and_reraises():
    with pytest.raises(ValueError):
        with tracing.start_span("s", tracing.KIND_INTERNAL) as span:
            raise ValueError("boom")
    assert span.status == tracing.STATUS_ERROR
    assert span.status_message is not None


def test_t_v160_trc_12_no_sink_uses_null_sink(monkeypatch):
    calls = []
    monkeypatch.setattr(tracing.NullSink, "write", lambda self, span: calls.append(span))
    with tracing.start_span("s", tracing.KIND_INTERNAL):
        pass
    assert len(calls) == 1


def test_t_v160_trc_12_non_sqlite_sink_failure_is_swallowed_and_counted(caplog):
    class FlakySink:
        def write(self, span):
            raise RuntimeError("sink is down")

    before = tracing.dropped_spans()
    with caplog.at_level(logging.WARNING, logger="tracing"):
        with tracing.start_span("s", tracing.KIND_INTERNAL, sink=FlakySink()):
            pass
    assert tracing.dropped_spans() == before + 1
    assert any("sink is down" in r.message or "RuntimeError" in r.message for r in caplog.records)


def test_t_v160_trc_12_non_sqlite_sink_failure_does_not_mask_body_exception():
    class FlakySink:
        def write(self, span):
            raise RuntimeError("sink is down")

    with pytest.raises(ValueError, match="body raised this"):
        with tracing.start_span("s", tracing.KIND_INTERNAL, sink=FlakySink()):
            raise ValueError("body raised this")


def test_t_v160_trc_12_sqlite_sink_failure_propagates(monkeypatch):
    def failing_add_span(conn, **kwargs):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(tracing.storage, "add_span", failing_add_span, raising=False)
    sink = tracing.SqliteSpanSink(conn=object())
    with pytest.raises(RuntimeError, match="insert failed"):
        with tracing.start_span("s", tracing.KIND_CLIENT, sink=sink):
            pass


def test_t_v160_trc_12_second_finish_raises():
    with tracing.start_span("s", tracing.KIND_INTERNAL) as span:
        pass
    with pytest.raises(RuntimeError):
        span.finish()
