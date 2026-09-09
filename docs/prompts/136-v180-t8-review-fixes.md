# Prompt 136 — v1.8.0 T8 review-finding fixes

- **Date:** 2026-09-10
- **Executor model:** claude-sonnet-5
- **Model reason:** two small, fully-specified fixes against exact call sites
  and an exact discipline to mirror (`_StatusMessage`'s catch-log-disable
  pattern, `T-V180-CHAT-07`'s test shape) — mechanical correction against a
  verified tree, not open design search.
- **Harness:** Claude Code
- **Stage:** T8
- **Owner of:** `dashboard_server.py`, `bot.py`, `tests/test_v160_dashboard.py`,
  `tests/test_v180_chat.py`, `docs/prompts/136-v180-t8-review-fixes.md`
- **REQ ids:** REQ-V180-DSH-05, REQ-V180-CHAT-06

## Goal

Implement `docs/spec/task-briefs/v180-T8-fixes.md` end to end, in one commit:
fix REQ-V180-REV-01's two clean-context review findings. (1) Wire
`dashboard_render.reading_strip_section` into `dashboard_server.py`'s
`_page_usage` — built and unit-tested (T4) but never called from the `/`
route — using the same `totals` dict `_usage_totals()` already computes,
prepended to `body` before `usage_section`'s own totals table. (2) Guard
`bot.py`'s `_TypingIndicator.start()`: `threading.Thread.start()` can raise
`RuntimeError` under thread-resource exhaustion and today that propagates
out of `process_update`, violating REQ-V180-CHAT-06; wrap it in try/except
matching `_StatusMessage`'s catch-one-redacted-warning-then-disable
discipline, leaving `stop()` safe to call afterward.

## Constraints

- Only `dashboard_server.py`, `bot.py`, and the one test file each fix
  needs.
- No file outside this repository read or written (EC-01).
- No `docs/spec/` delta: both fixes bring existing code into conformance
  with already-specified behaviour (REQ-V180-DSH-05, REQ-V180-CHAT-06)
  rather than changing it.

## Acceptance

`uv run --locked ruff check .` exits 0. `uv run --locked pytest` is green
except one pre-existing, unrelated failure confirmed pre-existing by
`git stash`: `tests/test_v170_bench.py::test_t_v170_rpt_02_lint_docs_repointed_to_this_release`
(stale since prompt 135's T7 repointed `config/quality_gates.yaml`'s
`lint-docs.report_path` to `report-v1.8.0.md`; out of this prompt's file
map, left untouched per the brief's "STOP and report back rather than
fixing it yourself"). New tests: `tests/test_v160_dashboard.py::test_t_v180_dsh_05_reading_strip_renders_on_the_usage_page`
asserts the reading strip's markup in `/`'s live rendered output;
`tests/test_v180_chat.py::test_t_v180_chat_08_thread_start_raising_disables_indicator_without_raising`
mirrors `T-V180-CHAT-07`'s shape with a fake `threading.Thread` whose
`start()` raises `RuntimeError`, asserting `start()` itself never raises,
`_thread` stays `None`, one redacted warning is logged, and `stop()`
afterward is a safe no-op.

## Stop

The one pre-existing test failure above was investigated (via
`git stash`/`git stash pop`) rather than fixed, per the brief's explicit
instruction not to fix a pre-existing broken test file myself.
