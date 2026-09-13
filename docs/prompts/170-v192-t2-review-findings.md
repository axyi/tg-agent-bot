# Prompt 170 — v1.9.2 T2: close clean-context review findings

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a fully specified fix list against a clean-context
  review's own findings (`docs/spec/task-briefs/v192-T2-review.md`) — every
  defect, its root cause and its fix are already named; no open-ended
  design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.2 T2 (patch, no new spec file — precedent v1.5.1)
- **Owner of:** `devtools/mutation_check.py`, `tests/test_mutation_check.py`,
  `config/quality_gates.yaml`, `docs/reports/report-v1.9.2.md`,
  `docs/spec/task-briefs/v192-T2-review.md` (review brief, authored before
  this prompt, committed with it per the brief's own instruction),
  `docs/prompts/170-v192-t2-review-findings.md`, `docs/llm-usage.md`
  (row 80)
- **REQ ids:** none new — closes REQ-V13-CO-06 / REQ-V15-GATE-04's
  fail-loud contract for the new shrink guard

## Goal

A clean-context review of `92b667c` + `c3a38ea` + `260c7e1` found no 🔴, two
real 🟠 defects in the new mutation runner and its timeouts, and six 🟡.
Close every one of them in this single commit, per the review brief's own
instruction: (1) the shrink guard summed a verbosity-dependent output
format without ever checking the collect-only subprocess's returncode or
requiring a positive count, so a collection error or a stray verbosity
change would pass vacuously as "no shrink" — now `-qq` is explicit, both
returncodes and both counts are checked, with a new mutation entry and
killer test; (2) three mutation gate timeouts were sized only from the
killed-path wall, ignoring that a *surviving* mutation runs the whole
single-process suite (~70s) with nothing to trigger `-x`'s early exit — a
corrected, survivor-safe sizing rule replaces D2 for the mutation-* gates,
re-sizing all five subsets (`mutation-all` noted, not re-measured, T3's
job); (3) the report claimed no count-bearing test needed repointing, but
three now do (deferred to T3, reworded here); (4)-(8) six smaller
corrections — a `mutation-all` note, the pytest gate comment naming the
box, `_imports`/`_module_name`/tier-4 gaps that left the 34 `v13-` entries
(mostly `devtools/bench.py`) unable to use tier 3, the shrink guard's
placement ahead of id/prefix validation, and reproducible commands for the
duplicates scan.

## Constraints

- Everything the review brief states verbatim is the contract. The
  existing killer test for `v192-mutation-order-shrink-unchecked` is
  updated for the new 4-tuple `_shrink_counts` return shape, not rewritten
  — its own find string (`if explicit_count != bare_count:`) is untouched.
- `92b667c`, `c3a38ea` and `260c7e1` are not amended, not rebased, not
  force-pushed.
- Nothing else runs concurrently with any `--only`/`--select` mutation run.
- `.env` never read; `data/`, `evals/rag/corpus` never opened. No version
  bump, no tag, no push, never `--no-verify`.

## Acceptance

`uv run --locked ruff check .` and `ruff format --check .` exit 0;
`uv run --locked pytest` exit 0 (1600 collected, up from 1598 — two new
tests in `tests/test_mutation_check.py`); `uv run --locked python
devtools/checks.py lint-docs` exit 0; the throw-away drift script reports
110/110 matched, 0 drifted; `devtools/mutation_check.py --only
v192-mutation-order-shrink-zero-accepted` killed; `devtools/mutation_check.py
--only v192-mutation-order-shrink-unchecked` still killed;
`devtools/mutation_check.py --select v13-` killed n/n with wall recorded;
`devtools/mutation_check.py --select v15-` killed 4/4 with wall recorded.

## Stop

If either new mutation entry survives instead of being killed, or the
`--select v13-`/`--select v15-` re-runs kill a different n than before,
stop and report rather than adjusting the fix to force a green result.
