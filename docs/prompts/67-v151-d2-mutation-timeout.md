# Prompt 67 — v1.5.1 patch: D2, mutation gate timeout headroom

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a config-value fix gated on a real measurement --
  the model's job was to run the direct command, read the actual wall
  clock and apply a stated, reproducible rule, not to guess a number
- **Harness:** Claude Code
- **Stage:** v1.5.1 patch, D2
- **Owner of:** `config/quality_gates.yaml` (`mutation-v15` and
  `mutation-all` gates' `timeout_seconds` and the rule comment above them)
- **REQ ids:** REQ-V12-MUT-01, REQ-V15-GATE-04, REQ-V15-HOOK-04

## Goal

Fix the `mutation-all` gate's spurious timeout: `config/quality_gates.yaml`
set `timeout_seconds: 1200`, but `checks.py run --profile full --since
9ad3047` reported `mutation-all: could not run: timed out after 1200s` on
2026-09-04 even though `uv run --locked python devtools/mutation_check.py`
run directly on the same tree completes 72/72 killed, rc=0. Measure the
real wall clock of a direct run and set the timeout to roughly 2x it,
recording the rule and the measured number in the config comment. Check
`pre-push`'s `mutation-v15` member for the same fragility and fix it by
the same rule if needed.

## Constraints

- `config/quality_gates.yaml` only; no gate membership, argv or severity
  change -- timeout values and their explanatory comment only.
- The new timeout must be justified by an actually-measured direct run on
  this tree, not an assumed or copied number.

## Acceptance

- Measured directly on this tree: `mutation-all`'s underlying command
  (`uv run --locked python devtools/mutation_check.py`) real wall clock
  21m12.932s (~1273s), 72/72 killed; `mutation-v15`'s underlying command
  (`--select v15-`) real wall clock 1m39.497s (~100s), 4/4 killed.
- `mutation-all`'s `timeout_seconds` raised to 2600 (~2x measured,
  rounded up); `mutation-v15`'s raised to 220 (~2x measured, rounded up)
  -- the old 180s gave it under 2x headroom by the same rule.
- `python3 devtools/checks.py run --profile full --since 9ad3047d981b30005f81e15e09d2f02444b8009a`
  reports `mutation-all` as passed, not timed out.
- `uv run --locked pytest tests/test_v15_standards.py -k "gate_04 or matrix"`
  still exits 0 (the profile-matrix test is unaffected by a timeout value).

## Stop

Not triggered: this is a pure config-value change with no gate other than
the two mutation gates affected.
