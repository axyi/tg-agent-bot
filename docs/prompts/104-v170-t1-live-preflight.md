# Prompt 104 — spec-v1.7.0 T1: live preflight

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prompt 103 — engineering plumbing against a fully
  written-out spec, no design judgement beyond following the fixed order
- **Harness:** Claude Code
- **Stage:** T1 — live preflight (conditional exit)
- **Owner of:** `docs/reports/report-v1.7.0.md` (T1 section), `.env`
  (`LMSTUDIO_BASE_URL` line only, via the permitted `sed -i` idiom),
  `docs/prompts/104-v170-t1-live-preflight.md` (new)
- **REQ ids:** REQ-V170-PRE-03, REQ-V170-PRE-04, REQ-V170-BEN-01,
  REQ-V170-GATE-01 (T1)

## Goal

Run REQ-V170-ORD-01's T1 row in its written order: PRE-03 phase 1 (ordered
address probe, single-line `.env` rewrite, served-model read, the three
documentary VERIFY reads), then PRE-04 items 1-6 (no inference), then PRE-04
item 7 (the one-completion preflight — first inference of the run), then
PRE-03 phase 2 (the TTFT-shape probe — second inference of the run), then
gate 5. Determine whether any of REQ-V170-BEN-01's six instrument values
mismatch the frozen `baseline-v1.6.0` and, separately, whether
`stats.time_to_first_token` is available on the OpenAI-compatible route —
the fact that decides whether REQ-V170-RSN-07's summary-only fallback binds
the whole run.

## Constraints

- No source file is touched. The only permitted `.env` write is the
  single-line `LMSTUDIO_BASE_URL` rewrite (REQ-V170-EC-04 idiom 4).
- `.env` values are never printed, logged or quoted; presence/value checks
  use `grep -q` exit statuses only.
- Only two inferences are permitted in this task: PRE-04 item 7's preflight
  and PRE-03 phase 2's TTFT probe, issued in that order and no other.
- No live OpenRouter call (REQ-V170-NG-08) — the preflight goes through
  `llm.build_llm_client`, whose failover only reaches OpenRouter if the LM
  Studio primary fails.
- The TTFT probe's system prompt must begin with a fresh random 32-hex
  nonce, and the nonce itself is never recorded (only its length).
- One prompt -> one commit, referencing this file.

## Acceptance

- The three fixed addresses are probed in the written order; the winner is
  recorded and `.env`'s `LMSTUDIO_BASE_URL` line is rewritten and confirmed.
- Exactly one served-model id compares equal (string equality) to both
  `qwen/qwen3.8-27b` and `cfg.lmstudio_model`.
- All three documentary VERIFY reads are resolved with URL, date and exact
  quoted spelling; no remembered spelling is substituted for a live read.
- PRE-04 items 1-6 all pass before item 7 is issued.
- PRE-04 item 7 (preflight) returns a non-empty assistant message.
- PRE-03 phase 2 (TTFT probe) is issued only after item 7, and its verdict
  on `stats.time_to_first_token` availability is recorded verbatim.
- Gate 5 (`bot.py --selftest-live`) exits 0.
- `docs/reports/report-v1.7.0.md`'s T1 section records every check above.

## Stop

Any mismatch among REQ-V170-BEN-01's six instrument values (version,
served-model-id uniqueness/equality, context length, `LLM_MAX_TOKENS`,
`LLM_TIMEOUT_S`, `obs_capture_content`) STOPS the run here, before a line of
code is written, finalised through the `T-STOP` procedure
(REQ-V170-ORD-02) — no T2.
