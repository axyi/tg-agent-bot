# Prompt 73 — spec-v1.6.0 T1: tracing.py core

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §"Executor: claude-sonnet-5"; every field,
  method signature and behaviour is already written out in §5
- **Harness:** Claude Code
- **Stage:** T1
- **Owner of:** `tracing.py` (new), `tests/test_v160_observability.py` (new),
  `config.py` (adds `obs_capture_content`)
- **REQ ids:** REQ-V160-TRC-01, -02, -03, -07, -09, RPT-relevant subset

## Goal

Build the self-built tracing layer: the `Span` frozen dataclass, the
contextvar-based tracer (`start_span`, `current_span`, `new_trace_id`,
`new_span_id`), the fail-closed `ATTRIBUTE_KEYS` allowlist (GenAI names +
four opt-in content attributes + `tg_agent.*`), the `SpanSink` protocol with
`NullSink` and `SqliteSpanSink`, the process-wide `dropped_spans()` counter,
and `set_run_context` for the bench harness. Add
`Config.obs_capture_content` (env `OBS_CAPTURE_CONTENT`, default `False`) in
the existing `_parse_bool` style.

## Constraints

- `tracing.py` is imported by nothing else yet (`agent.py` wiring is T3).
- No mutation of shared repo state across tests: `dropped_spans` and
  `set_run_context` are reset per test.
- `SqliteSpanSink.write` calls `storage.add_span`, which does not exist
  until T2 — T1's own test for propagation-on-failure exercises this via
  `monkeypatch.setattr(tracing.storage, "add_span", ..., raising=False)`,
  not a real database.
- `status_message`: redact **then** truncate to 200 characters — order
  matters, proven by a boundary test where a secret straddles position 200
  in the *unredacted* text.
- One prompt → one commit, referencing this file.

## Acceptance

- `tests/test_v160_observability.py` — T-V160-TRC-01 (tracing resolves to a
  `.py` module, no shadowing package; widens to cover `dashboard_render` /
  `dashboard_server` at T5/T6), -02, -09, -11, -12 — all green (14 tests).
- `uv run --locked ruff check .` and `uv run --locked ruff format --check
  tracing.py tests/test_v160_observability.py` both exit 0.
- `uv run --locked pytest` exits 0 with 857 passed (843 + 14 new).
- No RLM delegation needed for this task (§14.1: T1, delegate = no); reading
  stayed within `config.py:118-135`, `config.py:455-540` plus the new files
  themselves.

## Stop

If `ruff check .` or the full suite goes red for a reason unrelated to this
task's own files, stop and investigate before continuing — do not paper
over a regression by weakening an assertion.
