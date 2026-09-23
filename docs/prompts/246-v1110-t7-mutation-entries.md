# Prompt 246 — v1.11.0 T7 Phase A: the eight `v1110-*` mutation entries

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (EC-04), brief
  `docs/spec/task-briefs/v1110-T7.md`, for the entries and their test;
  commands-only for the orchestrator's own `quality_gates.yaml` comment
  fix and this commit.
- **Harness:** Claude Code (background session; subagent for the entries,
  orchestrator for the comment fix and the commit)
- **Stage:** T7 (Phase A)
- **Owner of:** `devtools/mutation_check.py`, `tests/test_v1110_mut.py`
  (new), `config/quality_gates.yaml` (comment only),
  `docs/spec/task-briefs/v1110-T7.md`
- **REQ ids:** REQ-V1110-MUT-01

## Goal

Land the eight `v1110-*` mutation entries (`MUTATIONS` 144 → 152) and
`T-V1110-MUT-01`. **Procedural deviation from §14 T7's literal ordering,
following established precedent**: the spec's own text describes
verifying each entry in isolation *before* the source commit, but the
v1.9.3 dirty-tree guard (`devtools/mutation_check.py:2229`,
`_dirty_mutation_paths`) unconditionally refuses any `--only`/`--select`
invocation while a mutation path (`devtools/mutation_check.py` itself,
already the path of seven pre-existing entries) differs from the
committed `HEAD` blob — and it must differ to hold eight new entries at
all. This is not new: `docs/reports/report-v1.10.2.md`'s T5 section hit
the identical conflict and the operator resolved it the same way
`docs/reports/report-v1.10.1.md`'s T6a did before it — commit the entries
first, then run `--only`/`--select` verification against the clean,
committed tree. Applied here unchanged: commit now, verify next (a
separate commands-only prompt), fold any real discrepancy from the
placeholder `why` text into a follow-up correction if isolation
verification finds one.

Also fixes `config/quality_gates.yaml`'s `mutation-all` dated-comment
block so gate 3 stays green at this commit (the "is now 144" sentence
retired to "closed at 144", a new dated paragraph added reading "is now
152" — the entry-count update only; `timeout_seconds` stays untouched
until the actual gate-6 wall `W` is measured, per MUT-01's own rule).

## Constraints

The eight `find`/`replace` pairs were pre-verified character-for-character
unique against the live tree before the brief was written (both
single-`grep -cF` and Python `str.count()` checks). `bot.py`/`storage.py`/
`documents.py` are byte-identical to the prior commit — nothing was
mutated-and-left-applied; every `why` field is honestly marked "NOT YET
empirically verified via --only" rather than fabricating an observed
failure. `--no-verify` never used.

## Acceptance

`len(MUTATIONS) == 152`. `T-V1110-MUT-01` green. Gates 1-4 green
(`pytest`: 2374 passed, 1 skipped, 2 xfailed). `bot.py --selftest` OK.
`ruff check .` clean. The three previously-failing "is now 144" comment-
parity tests (`test_v1101_gates.py`, `test_v1102_gates.py`,
`test_v1104_gates.py` — 5 functions total) green again.

## Stop

Not applicable — Phase A's own scope ends here; isolation verification
and the code review are separate, subsequent prompts.
