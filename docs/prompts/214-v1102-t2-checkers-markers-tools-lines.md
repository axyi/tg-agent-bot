# Prompt 214 — v1.10.2 T2: full clause reporting, the CASE/TOOLS evidence lines, marker widening

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (spec-v1.10.2 T2: `delegate?
  yes`); general-purpose subagent, briefed by
  `docs/spec/task-briefs/v1102-T2.md`.
- **Harness:** Claude Code (background session, subagent)
- **Stage:** T2
- **Owner of:** `devtools/agent_eval.py`, `evals/agent/red_team.json`,
  `tests/test_v1102_red_team.py` (new), `tests/test_v1102_runner.py` (new),
  `tests/test_v1100_red_team.py` (marker-list pin bump, precedent
  `526e19d`), `tests/test_v1101_red_team.py` (marker-count pin bump)
- **REQ ids:** REQ-V1102-RT-01..08, REQ-V1102-SEC-01, REQ-V1102-ERR-01
  rows 1-5

## Goal

`check_injection` now collects every violated clause's message (a)-(e),
joined with `"; "`, instead of returning only the first. A new `_safe_field`
sanitizer (redact, flatten control/format/line-separator/whitespace to a
space, collapse, strip, truncate) backs a parallel `tool_call_log` recorded
by `_record_tool`, rendered through a new `_tools_line`/`TOOLS_LINE_CAP`
(2300, derived from `TOOL_EXECUTION_LIMIT` x worst-case JSON escaping). The
per-step loop in `_run_level2_cases` now prints one `CASE <id> <step> --
<verdict> -- <detail> -- reply: <preview>` line immediately at verdict time
(when `record_tool_calls`), and one `TOOLS <id> <step> -- <entries|none>`
line right after for `injection` steps only, via a step cursor into
`tool_call_log` so each step shows only its own calls. `INJ_MARKERS` gains a
16th, gap-token marker (`не могу` + <=3 non-`не`, terminator-free words +
verb stem); `HAL_MARKERS` gains two more (`нет ... информации/данных/
сведений`, `не располагаю ... информацией/данными/сведениями`). INJ-05's and
HAL-03's `any_of` widen to match. Test-first per EC-02: both new test modules
were written and run red against the unedited tree (70/105 failures, all for
the expected reason — missing markers/functions) before any production edit
landed.

## Constraints

Offline only, no live call. `agent.py` untouched beyond what T1 already did.
No `v1102-*` mutation entries (T5's). `README.md`, `AGENTS.md`,
`.env.example`, `pyproject.toml`, `config/quality_gates.yaml` untouched.
`check_hallucination`, `_injection_clauses`'s five booleans, `check_step`'s
dispatch, `_matches_any`/`_matches_any_per_clause`, and the negation guard
unchanged — only `check_injection`'s detail-joining and the two marker
lists change. Every regex and JSON-encoding detail copied verbatim from the
task brief, verified empirically against the brief's own worked examples
before being trusted.

## Acceptance

Every id in the brief's Part F checklist green (`T-V1102-RT-01..12`,
`T-V1102-RUN-01..07`, `T-V1102-SEC-01`, `T-V1102-ERR-01`); full offline
suite green, 2152/2153 (1 pre-existing skip, unchanged), no test deleted;
`ruff check .` and `bot.py --selftest` green. `validate_datasets()` green on
the committed files; both dataset `sha256`s recorded in the report. The
dataset diff against `git show ccab5d7:evals/agent/red_team.json` touches
only INJ-05's and HAL-03's `any_of` arrays (confirmed by
`T-V1102-RT-10`'s own diff test).

## Stop

One brief-vs-code disagreement was found and resolved by trusting the code:
the brief's `_safe_field` worked example claims `_safe_field("\x1b[31mA\x1b[0m",
80)` yields `"[31mA[0m"`, but the brief's own verbatim algorithm run
empirically yields `"[31mA [0m"` (the two non-adjacent ESC bytes each
flatten to their own space; the collapse step only removes *runs* of
whitespace, not the single separating space this leaves between "A" and
"[0m"). The mandated code, not the prose example, was treated as
authoritative; the test fixture matches the code's actual, verified output.
Reported to the orchestrator rather than silently reconciled by changing the
algorithm.

Two pre-existing tests outside this brief's named file list
(`tests/test_v1100_red_team.py`'s `INJ_MARKERS`/`HAL_MARKERS` exact-list
pins, and `tests/test_v1101_red_team.py`'s exact-count pins) went red purely
because this task's marker lists grew — the same class of break the
identical v1.10.1 T3 commit (`526e19d`) already produced and fixed by
renaming+updating those same two tests from "eight" to "fifteen". Given
that exact precedent and the acceptance criterion "full offline suite
green, no test deleted," the four pins were bumped to sixteen/seventeen
(rename + content) rather than left red or silently ignored; flagged to the
orchestrator as a mechanical, precedented, out-of-explicit-brief-scope edit
for audit.
