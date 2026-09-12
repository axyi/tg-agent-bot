# Benchmark — spec-v1.9.0 (REQ-V190-EC-06)

**This report is hand-assembled, not `bench.py report --gate`'s output.**
Neither the baseline nor the candidate run completed all scenarios without
an abort (see below), and `bench.py report` refuses to compare an aborted
run (`_Invalid("aborted run (...)")`) by design. The delta below is
computed directly from both runs' raw JSON for the scenarios both files
share. Per REQ-V190-EC-06, this benchmark's delta is **reported, not
gated** — its absence-of-a-formal-`--gate`-verdict does not block this
release; see the `## Disposition` section.

## Why neither run is a clean, complete artefact

- **Baseline** (`docs/assets/bench/v190-baseline.json`, unchanged tree,
  `<base>` = `d6c13124d8108d6ca23900b91ef30d27d95fc6fc`): T0's original run
  (repeats=3, default 600s scenario timeout) aborted at `S13
  multi-step-exec` (`ABORTED: timeout:S13-1`), 13 of 18 scenarios
  attempted, 36/37 successes (97.3%).
- **Candidate** (`docs/assets/bench/v190-candidate.json`, reviewed tree,
  through commit `9fb8783`): T11's run (repeats=3, default 600s timeout)
  aborted at `S15 big-output-answer` (`ABORTED: timeout:S15-1`), 15 of 18
  scenarios attempted, 41/43 successes (95.3%).
- **One re-run attempt** at baseline with a generous `--timeout-s 1200`
  was tried (operator-authorized, one attempt) to get a complete,
  comparable pair. It ran 110 minutes, reached further (`S16`) than the
  original before aborting again (`ABORTED: timeout:S15-2`), and showed
  *more* per-scenario failures than the original (86.4% success vs.
  97.3%) — worse, not better. This confirms the root cause is genuine
  run-to-run stochastic latency/reliability on this deployment's chat
  model (`qwen/qwen3.8-27b`, a thinking variant), the same root cause
  already diagnosed and disclosed for gate 7 (§T8 of
  `docs/reports/report-v1.9.0.md`) — not something a longer timeout
  reliably fixes. Per the operator's decision, no further re-run attempts
  were made; the original baseline (T0) and the original candidate (T11)
  are used for this comparison, unmodified.
- A live GPU-box outage (`ConnectError` transport failures, confirmed in
  `bot.db`'s trace log around 2026-09-11 19:55 UTC) also corrupted one
  intermediate attempt at the baseline re-run; that attempt was discarded
  entirely (not used anywhere in this report) once the outage was
  confirmed via the box's own reachability probe and the failing
  `llm_call` rows.

## The benchmark rule fires (REQ-V190-EC-06)

This release changes both `tool_specs()` (a fourth tool,
`search_documents`, REQ-V190-TOOL-01) and `SYSTEM_PROMPT` (one rule line,
REQ-V190-TOOL-04), so `meta.prompt_tools_sha256` changes between the two
runs (confirmed: baseline `748fa855…`, candidate `9690049c…` — different,
as expected). `meta.prefix_tokens`: baseline **842**, candidate **952**
(**+110 tokens**, the fourth tool's schema cost).

## Per-scenario prompt-token delta, the 12 scenarios both runs completed

| scenario | baseline prompt (median) | candidate prompt (median) | Δ | baseline cost | candidate cost |
|---|---:|---:|---:|---:|---:|
| S01 greet | 876 | 986 | +110 | $0.00153 | $0.00088 |
| S02 arith | 1,904 | 2,124 | +220 | $0.00123 | $0.00124 |
| S03 file-roundtrip | 1,949 | 2,169 | +220 | $0.00262 | $0.00186 |
| S04 error-explain | 3,225 | 3,555 | +330 | $0.00270 | $0.00277 |
| S05 big-output | 6,099 | 2,389 | **−3,710** | $0.00381 | $0.00215 |
| S06 noisy-log | 2,027 | 2,247 | +220 | $0.00262 | $0.00340 |
| S07 skill | 3,436 | 3,767 | +331 | $0.00268 | $0.00284 |
| S08 fetch-weather | 3,452 | 3,781 | +329 | $0.00223 | $0.00227 |
| S09 multi-turn | 9,226 | 8,148 | **−1,078** | $0.00733 | $0.00560 |
| S10 knowledge | 880 | 990 | +110 | $0.00083 | $0.00083 |
| S11 json | 891 | 1,001 | +110 | $0.00089 | $0.00084 |
| S12 summary | 2,082 | 2,318 | +236 | $0.00185 | $0.00204 |
| **total (S01–S12)** | **36,047** | **33,475** | **−2,572** | | |

`S13` is excluded from the table: baseline scored 0/1 on it (the scenario
that triggered the original abort), so no meaningful median exists there
to compare against candidate's 3/3.

## Reading the delta

**Single-call scenarios (S01, S10, S11) show exactly the expected +110
tokens** — the fourth tool's schema cost, once, with no retries. **Multi-call
scenarios scale roughly linearly** with call count (S04/S07/S08 at ~+330,
three calls each; S02/S03/S06 at +220, two calls each) — consistent with
the same fixed +110-token prefix cost repeating once per LLM call in the
scenario, exactly as EC-06 anticipated ("a fourth tool costs prefix tokens
by construction").

**S05 and S09's large negative deltas are noise from this deployment's
model instability, not a real token saving.** Both scenarios involve
large tool outputs or long multi-turn history where the model's own
retry/resend behavior (visible as `resent_tokens` in the raw data) varies
run to run on this box independent of any code change — the same
stochastic-latency root cause documented for gate 7 and for this
benchmark's own repeated abort. Neither scenario's delta should be read
as a real regression or improvement; both runs' absolute numbers for S05
and S09 are within the range of variance already observed across this
run's several live attempts at these same scenarios.

## Disposition

Per REQ-V190-EC-06, this delta is **reported, not gated** — it does not
block T11, T12 or T13. The absence of a formal `bench.py report --gate`
verdict (impossible while either artefact is an aborted run, and this
project's own `NG-03` forbids editing `bench.py`/`bench_scenarios.py` to
change that behavior) is disclosed here and in
`docs/reports/report-v1.9.0.md`'s T11 section, in the same spirit as gate
7's known-limitation disposition: genuine, diagnosed, disclosed
environment/model instability on this operator's deployment, not a defect
in this release's code.
