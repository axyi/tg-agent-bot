# Prompt 106 — spec-v1.7.0 T3: stage A execution

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts — engineering plumbing against a
  fully written-out spec; the live pairs themselves need no design judgement,
  only the fixed candidate order and the honored/shippable rules the spec
  already states
- **Harness:** Claude Code
- **Stage:** T3 — stage A execution (conditional exit)
- **Owner of:** `docs/assets/bench/rsn17-*.json` (new, ten pair-member
  documents), `docs/reports/report-v1.7.0.md` (T3 section),
  `docs/prompts/106-v170-t3-stage-a-execution.md` (new). `llm/lmstudio.py`
  was edited and reverted ten times in this task via the T2 scratch
  procedure; it carries no diff at the commit.
- **REQ ids:** REQ-V170-RSN-01, -02, -03, -04, -05, -06, -07 (T3)

## Goal

Run the real live pairs of REQ-V170-RSN-02's candidate order (a, b, c, d, e)
under the T2 procedure, on the resolved instrument, to find (or fail to
find) a summary-shippable reasoning-disable mechanism, and to produce
REQ-V170-RSN-06's per-purpose mechanism table.

## Constraints

- Every pair member is a real `bench.py run --only <S05|S12> --repeats 1`
  against the live LM Studio instance resolved at T1 — no fabricated or
  estimated numbers.
- `llm/lmstudio.py` is the only source file touched, and only via the
  scratch procedure: apply, run, copy output out immediately, revert,
  `git diff` proved empty before the next member.
- Probing stops at the first candidate honored and shippable for `summary`
  (REQ-V170-RSN-02) — no further live candidate is probed past that point.
- At most 3 pairs per candidate, at most 15 total (REQ-V170-RSN-05).
- One prompt -> one commit, referencing this file; the commit adds only the
  ten pair-member `.json` documents (their `.log` siblings are
  `docs/assets/bench/*.log`-gitignored, as with every prior bench artefact
  in this repository) plus this prompt and the report section.

## Acceptance

- Every pair-member file follows REQ-V170-TREE-01's naming.
- `git status --porcelain` was empty before each scratch edit and
  `git diff` was empty after each revert — recorded per step during
  execution, restated as a summary line in the report.
- The honored decision is computed per REQ-V170-RSN-03's exact three-part
  rule, from the real `Σ reasoning_tokens`/`max reasoning_chars` figures.
- The per-purpose mechanism table (REQ-V170-RSN-06) is produced, with the
  STOP/no-STOP verdict stated explicitly.
- The pair-count arithmetic is stated against the 3-per-candidate/15-total
  ceiling.

## Stop

If no candidate is honored and shippable for `summary` after candidates
a-e are exhausted, the run STOPS here, finalised through the shared
`T-STOP` procedure (REQ-V170-ORD-02) — no T4. (Not triggered this run: see
the report's T3 section — candidate c was found honored and shippable for
`summary`.)
