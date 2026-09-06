# Prompt 94 — spec-v1.6.0 T15 resume, erratum 2: S13's ceiling becomes 5

- **Date:** 2026-09-06
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a one-line mechanical change to a literal already decided
  by the lab's erratum 2 (`docs/spec/spec-v1.6.0.md`, committed `28363b2`) —
  no design decision is open
- **Harness:** Claude Code
- **Stage:** T15 (resumed, prompt 93)
- **Owner of:** `devtools/bench_scenarios.py` (S13's `tool_calls_max` only),
  `tests/test_v160_bench.py` (the matching hardcoded expectation), this
  prompt file
- **REQ ids:** REQ-V160-TQ-05 (erratum 2)

## Goal

Set S13's `tool_calls_max` ceiling from 4 to 5, matching the measured
reference cost recorded at the original T15 (5/5/5 `exec` calls, 5050 every
time — a deterministic instrument cost, not scenario variance) and disclosed
as erratum 2 in the spec.

## Constraints

- Touch only `devtools/bench_scenarios.py` line 279
  (`checks=[tool_used("exec"), answer_regex(r"\b5050\b"), tool_calls_max(4)]`
  → `tool_calls_max(5)`) and the one hardcoded expectation in
  `tests/test_v160_bench.py::test_s13_to_s18_each_carry_exactly_one_tool_calls_max_check`
  (`"S13": 4` → `"S13": 5`).
- No other scenario, check, mutation entry or production module changes.
  Grepped first: no mutation entry in `devtools/mutation_check.py` references
  S13 or `tool_calls_max`; no other test hardcodes S13's ceiling or a real
  `scenarios_sha256` value (the fixture files use synthetic all-zero/all-`f`
  hashes, unaffected by this byte change).
- This edit changes `devtools/bench_scenarios.py`'s bytes and therefore the
  live `scenarios_sha256()` — expected and required (REQ-V160-BEN-01): every
  prior baseline document is already non-comparable by construction since
  S13…S18 were added.
- No inference call in this prompt.

## Acceptance

- `uv run --locked ruff check .` — clean.
- `uv run --locked pytest -q` — all green, no new failures.
- `git status --porcelain` — exactly the two owned files plus this prompt.

## Stop

None encountered — a mechanical one-line change plus its one dependent test
literal.
