# Prompt 130 — v1.8.0 T2 erratum 1: test amendment

- **Date:** 2026-09-09
- **Executor model:** claude-sonnet-5
- **Model reason:** `docs/handoff-v1.8.0.md` §Models: sonnet-5 executed
  v1.5, v1.6.0, v1.7.0 and T2 of v1.8.0 end to end in this repository; this
  is a two-site, test-only follow-up to T2's own work, well inside the
  pattern sonnet-5 has already run for this codebase.
- **Harness:** Claude Code
- **Stage:** T2 erratum
- **Owner of:** `tests/test_pricing.py` (one amendment site),
  `tests/test_v1_guardrails.py` (one amendment site),
  `docs/prompts/130-v180-t2-erratum-1-test-amendment.md`
- **REQ ids:** REQ-V180-EC-03 (amendment-list erratum), REQ-V180-CHAT-02,
  REQ-V180-CHAT-04

## Goal

Execute `docs/spec/task-briefs/v180-T2-erratum-1.md` exactly as written.
T2 (commit `30d76b4`) implemented REQ-V180-CHAT-02 (delete-on-success,
`STATUS_DONE` removed) and REQ-V180-CHAT-04 (the production call site
moves to `agent.run_agent_outcome`) correctly per those MUSTs, and this
structurally broke two pre-existing tests that REQ-V180-EC-03's
four-site amendment list omitted — a disclosed spec erratum, not an
implementation defect. The operator was asked and authorized extending
the amendment list by exactly these two sites: this prompt is that
extension, not a new spec task and not a re-opening of T2's design.

## Constraints

Only `tests/test_pricing.py::test_prc02_the_resolver_reaches_run_agent`
and `tests/test_v1_guardrails.py::test_t_v1_vis_01_status_message` (plus
its `RecordingTelegram` fake) may be touched, only at the sites the brief
names. No `bot.py`/`agent.py` change — T2's implementation is correct and
final. No file outside this repository read or written (EC-01).

## Acceptance

`uv run --locked ruff check .` exits 0. The full `uv run --locked pytest`
run is green (no failures beyond the one pre-existing unrelated skip at
`test_v170_bench.py:553`).

## Stop

Stop and report instead of silently expanding scope if fixing either site
turns up a third test broken by the same T2 change — that would mean the
amendment list itself needs a further, separately authorized erratum, not
an in-place fix here.
