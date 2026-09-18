# Prompt 222 — v1103 T2: markers, dataset, judge-route helper (RT-01, RT-02, RT-03)

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** source-writing task, delegated per EC-03 default.
- **Harness:** Claude Code (general-purpose subagent)
- **Stage:** T2
- **Owner of:** `devtools/agent_eval.py`, `evals/agent/red_team.json`,
  `tests/test_v1103_red_team.py`, plus the EC-02-authorized amendment
  sites for RT-01/RT-02 (see the brief)
- **REQ ids:** REQ-V1103-RT-01, REQ-V1103-RT-02, REQ-V1103-RT-03,
  REQ-V1103-INS-01 (the helper), REQ-V1103-NG-08, REQ-V1103-NG-09

## Goal

Widen `HAL_MARKERS` to 18 entries (the noun-before-«нет» form, last),
widen INJ-04's `any_of` to include «недоступен», add four adversarial
marker+fabrication fixtures with four matching `none_of` widenings, and
add the offline `judge_route_is_distinct(cfg)` helper. Full detail in
`docs/spec/task-briefs/v1103-T2.md`. **Offline only** — no live call, no
`.env` read, no gates 5/6/7/8.

## Constraints

Test-first. Do not touch `INJ_MARKERS` (stays 16, NG-08) or HAL-02's
`any_of`. Do not touch `check_hallucination`/`check_injection`'s
evaluation order. The dataset diff against `636a281` must be confined to
exactly 5 fields in 5 cases (INJ-04's `any_of`; HAL-01/02/03/04's
`none_of`) — no other dataset field changes. Do not lower any floor,
threshold or case count (NG-09).

## Acceptance

See the brief's Acceptance section — `validate_datasets()` green, the
12 negatives stay red, the 4 adversarial fixtures red through the
widened `none_of`, both dataset `sha256`s recorded, gates 1-4 green.

## Stop

If narrowing a `none_of` exclusion to fit its one target fixture would
also swallow a real positive/negative fixture, stop and report rather
than weakening the fixture set.
