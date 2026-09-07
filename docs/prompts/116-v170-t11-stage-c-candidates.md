# Prompt 116 — spec-v1.7.0 T11: Stage C candidates, comparability and the gates

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts; no reasoning spent choosing an
  executor for a live-benchmark stage
- **Harness:** Claude Code
- **Stage:** T11
- **Owner of:** `docs/assets/bench/cand-v170-*.json` (+ `.log` siblings),
  `docs/reports/report-v1.7.0.md` (T11 section),
  `docs/reports/bench-v1.7.0.md` (gated comparison),
  `docs/prompts/116-v170-t11-stage-c-candidates.md` (new)
- **REQ ids:** REQ-V170-BEN-01, REQ-V170-BEN-02, REQ-V170-BEN-03,
  REQ-V170-BEN-04, REQ-V170-BEN-05, REQ-V170-BEN-06, REQ-V170-BEN-07,
  REQ-V170-BEN-08

## Goal

Run REQ-V170-BEN-05's candidate catalogue against the resolved instrument —
C1 (`by-purpose`/`tool-round`) then C2 (`off`/``, explicit empty) — verify
comparability and the quality/cost gates per REQ-V170-BEN-06/-07, decide C3
per its own skip rule, and produce the gated comparison report.

## Constraints

- **Tree frozen from the first candidate**: no source, test or config
  change from the moment C1's process starts until T12 (conditional).
- Same instrument as the frozen baseline — REQ-V170-BEN-01's six locked
  fields re-verified before the first candidate's first inference (address
  re-probe already current from T10's own gate-5 re-pin, served model id
  re-confirmed as the sole exact match, `.env`'s `LLM_MAX_TOKENS=4096` /
  `LLM_TIMEOUT_S=600` re-confirmed, `obs_capture_content` absent from
  `.env` hence `False` by `Config`'s own default).
- Each candidate command carries `--repeats 3 --timeout-s 1800`
  unconditionally and both `LLM_REASONING_POLICY`/`LLM_REASONING_ON_PURPOSES`
  as an explicit process-environment prefix, `.env` untouched
  (REQ-V170-EC-04).
- C3 runs only if neither C1 nor C2 passes quality **and** its resolved
  treatment differs from C1's on the wire — T3's own per-purpose mechanism
  table (`tool-round -> none`, `final -> none`, `summary -> c`) already
  establishes analytically that C1 and C3 resolve identically (both leave
  `tool-round` and `final` at "on", degrading for lack of a shippable
  mechanism), so this is decided without spending a third run unless that
  analysis is contradicted by C1/C2's actual documents.
- Each candidate's merged document copied to `docs/assets/bench/<tag>.json`
  immediately, `bench.py check` re-confirmed, then committed.

## Acceptance

- `bench.py check` exits 0 for every candidate document produced.
- `bench.py report --gate` against the shipped candidate names the
  quality and cost verdicts explicitly (PASS / FAIL-cost / FAIL-quality /
  `EXIT_NOT_COMPARABLE`) and states the reason in each case.
- The T11 report section states, per candidate: prefix, invocation count,
  `meta.reasoning`, quality-gate disposition (incl. S13…S18 3/3), cost
  figures against the baseline's price snapshot, and latency (BEN-08,
  reported only, never gated).
- C3's run/skip decision is stated with its reasoning.

## Stop

None triggered. Four things surfaced and were handled without a full stop:

1. **`bench.py run` was invoked without `--lmstudio-version`,
   `--served-model-id` and `--lmstudio-context-length`** for both C1 and
   C2, so `_instrument_meta` (`devtools/bench.py:2368-2384`) wrote all
   three as `null` — a CLI-flag omission, not an instrument difference
   (confirmed: every self-derived `LOCKED_META_FIELDS` entry, including
   `config_sha256`, already matched the baseline byte-for-byte). Patched
   post-hoc via a scratch script, each value corroborated rather than
   asserted (`served_model_id` against every `llm_calls` row's own
   `model` field, both docs; `lmstudio_context_length` already matched
   via the self-derived `meta.context_length`; `lmstudio_version` has no
   live corroboration, same epistemic footing as the CLI flag would have
   carried). `bench.py check` then 0 on both.
2. **C2 (`off`) aborted mid-run**: `S13` repeat 2 failed a real
   `tool_calls_max` check (6 > 5, not a harness artefact) and `S15`
   repeat 1 timed out at 1800s with zero tool call and no answer,
   triggering `meta.aborted`. Reassembled per REQ-V170-BEN-04's "aborts,
   and the merge" procedure across three invocations (partA: S01-S14 +
   one aborted S15 attempt; partB1: S15 alone, isolated, repeat 1
   succeeded, repeat 2 timed out again; partB2: S16-S18, fresh) — merged
   via a scratch script calling `bench.summarize()` on the combined
   `runs` list, never by hand, `meta.only` set to `null`, `meta.aborted`
   dropped, every `LOCKED_META_FIELDS` entry but `repeats`/`only`
   verified byte-identical across parts. `bench.py check` then 0.
3. **A documentation defect found under freeze, not fixed under freeze**:
   both `.env.example`'s comment and `README.md`'s Reasoning-policy table
   (both authored at T8) describe `LLM_REASONING_ON_PURPOSES` backwards —
   "which purposes get reasoning turned off" — while `llm/base.py:143-156`
   (and the spec's own POL-03 prose, `spec-v1.7.0.md:962`) has it the
   other way: listed purposes stay `"on"` (untouched), unlisted purposes
   get an `"off"` attempt. ACC-03's freeze forbids editing either file
   now; both are in T12's five-file allowlist, so the correction rides
   there.
4. **The wire-identity finding**: given T3's per-purpose mechanism table
   (`tool-round -> none`, `final -> none`, `summary -> c`), C1 and C2
   resolve to the same request bytes for every purpose (confirmed
   empirically from `reasoning_requested`/`reasoning_honored` on every
   `llm_calls` row of both documents) — the three-candidate catalogue
   could not have discriminated between C1/C2/C3 this run. Recorded as
   the T11 section's leading finding rather than left implicit.

No instrument mismatch and no unresolved `EXIT_NOT_COMPARABLE` occurred.
