# Prompt 144 — spec-v1.9.0 T2 (embeddings client and config)

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** `docs/handoff-v1.9.0.md` §Models and effort: sonnet-5
  executed v1.5 through v1.8.0 end to end in this repository; every design
  decision of T2's embeddings client and config is frozen in the spec and
  the T2 task-brief, so the novelty is in the run, not in the reasoning.
- **Harness:** Claude Code
- **Stage:** T2
- **Owner of:** `llm/embeddings.py` (new), `config.py`, `tracing.py`,
  `tests/fakes.py`, `.env.example`, `bot.py`,
  `tests/test_v190_embeddings.py` (new), `tests/test_v190_config.py` (new),
  `tests/test_v160_dashboard.py` (one literal-count amendment, see
  Constraints), `docs/spec/task-briefs/v190-T2.md`
- **REQ ids:** REQ-V190-RET-01, REQ-V190-RET-02, REQ-V190-RET-08

## Goal

Implement spec-v1.9.0 §5's RET-01, RET-02 and RET-08 end to end, test-first:
`llm.embeddings.EmbeddingsClient` (batches of 32, one retry,
`EmbeddingTimeoutError(EmbeddingError)` raised `from exc` on an exhausted
timeout, one CLIENT span per request); the six `Config` fields
(`embedding_base_url`, `embedding_model`, `embedding_dim`,
`embedding_timeout_s`, `rag_top_k`, `rag_rerank`) plus the `rag_enabled`
property and the `EMBEDDING_MODEL`/`EMBEDDING_DIM` pairing rule; the
`FakeEmbedder` test double; and `bot._live_embeddings`, the live-selftest
embeddings check.

## Constraints

No dependency beyond the five pinned in T1. No `.env` read/write, no live
network — every test runs on `httpx.MockTransport`/`httpx.MockTransport`-backed
clients. `llm/lmstudio.py:17-80` and `llm/base.py:365-375` were read as
reference patterns only, not edited. `_parse_timeout` gained keyword-only
`key`/`default` (its one pre-existing caller, `LLM_TIMEOUT_S` at
`config.py:302`, is unchanged); `EMBEDDING_BASE_URL`'s own validation is
applied **only when the variable is explicitly set** — the inherited
`LMSTUDIO_BASE_URL` default is not re-validated, because
`LMSTUDIO_BASE_URL` itself is only validated when the lmstudio provider is
actually selected (`test_failover_auto_validates_both_provider_sets`
exercises exactly this: an unused, malformed `LMSTUDIO_BASE_URL` under
`LLM_FAILOVER=off`/`LLM_PROVIDER=openrouter` must keep loading).

Two disclosed items, both left for the orchestrator/operator to rule on
rather than resolved unilaterally:

1. **Amended, mechanical:** `tests/test_v160_dashboard.py:543` —
   `assert len(dashboard_render.SERVED_SPAN_ATTRIBUTE_KEYS) == 24` bumped to
   `== 26`, with a second erratum comment alongside the file's own existing
   one at `:539-542` (which already documents an identical prior collision:
   spec-v1.7.0 T5's `tg_agent.reasoning.requested` addition bumped this same
   literal 23 → 24). REQ-V190-RET-01 mandates registering
   `tg_agent.embeddings.batch_size` and `tg_agent.embeddings.dim` in
   `tracing._TG_AGENT_ATTRIBUTE_KEYS`; `:538`'s set-equality assertion is
   computed dynamically from `tracing.ATTRIBUTE_KEYS` and already stays
   green, only the pinned integer at `:543` was stale. This is the same
   amendment class T1 applied for `SCHEMA_VERSION` (mechanical, one line,
   no semantics changed, in-file precedent for the exact collision), not a
   new extension of REQ-V190-EC-03's list taken on this executor's own
   authority.
2. **Withheld, a real decision, NOT applied:** `bot.run_selftest_live`
   (`bot.py:1351-1382`) does **not** yet gain
   `failures += _live_embeddings(cfg, client)` after `_live_lmstudio`, as
   REQ-V190-RET-08 literally specifies. `_live_embeddings` itself is fully
   implemented and tested (`T-V190-RET-09`, against the function directly).
   Wiring the one line breaks two pre-existing tests in
   `tests/test_v1_guardrails.py` that are **not** in REQ-V190-EC-03's
   exhaustive amendment list: `test_t_v1_lv_01_all_checks_pass` (asserts
   `code == 0`, `out.count("live: OK") == 6`, `"live: FAIL" not in out`) and
   `test_t_v1_lv_01_missing_openrouter_key_is_a_skip` (asserts `code == 0`,
   `"live: FAIL" not in out`) — both build their `Config` via `make_cfg`
   (`tests/test_v1_guardrails.py:45-60`), which sets no embedding field, so
   `cfg.rag_enabled` is `False` and the new check fails unconditionally
   under D3's "required at deployment" rule (no SKIP path is permitted).
   Unlike item 1, fixing this requires changing fixture *semantics*
   (`make_cfg`/`live_cfg` gaining embedding fields, `live_handler` gaining
   an `/embeddings` branch, `count("live: OK") == 6` → `7`) — a decision,
   not a mechanical bump — so it is reported rather than applied.

## Acceptance

- `uv run --locked ruff check .` — exit 0.
- `uv run --locked pytest` — exit 0; `pytest --collect-only -q` totals 1304
  (1247 T1 floor + 28 in `test_v190_config.py` + 29 in
  `test_v190_embeddings.py`).
- `uv run --locked python bot.py --selftest` — exit 0.
- `T-V190-RET-01` (batching, ordering, retry/timeout classification, the
  dimension check, the malformed-response cases including a wrong element
  type inside an otherwise well-shaped vector, the span's five attributes),
  `T-V190-RET-02` (all six variables, the pairing rule, `rag_enabled`, the
  `EMBEDDING_BASE_URL` inheritance/validation split) and `T-V190-RET-09`
  (against `bot._live_embeddings` directly: the unset-pair line printed
  verbatim under a transport that raises on any request, and the
  configured/healthy, model-not-loaded, dimension-mismatch and
  models-endpoint-HTTP-error paths) all green.
- No test reaches a socket.

## Stop

`run_selftest_live`'s own wiring (REQ-V190-RET-08's literal one-line
addition) is the stop-and-report item above — left out of this commit,
pending the orchestrator's decision on amending
`tests/test_v1_guardrails.py`'s two fixtures. Everything else in RET-01,
RET-02 and RET-08's own `_live_embeddings` function is implemented, tested
and green.
