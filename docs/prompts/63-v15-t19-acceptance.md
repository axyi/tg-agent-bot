# Prompt 63 — spec-v1.5 T19: final acceptance, freeze

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** REQ-V15-ACC-01..04 name the exact commands and
  evidence required; the judgment call was `replay`'s two historical
  failures — diagnosing each with a direct hypothesis test (`ruff
  format --diff` on the exact historical blob) rather than assuming an
  explanation, then reasoning from the spec's own text (`replay` is not
  a profile member, and the no-bypass statement "stays a process
  attestation with replay as consistency evidence") to conclude neither
  blocks acceptance nor needs a history rewrite
- **Harness:** Claude Code
- **Stage:** T19
- **Owner of:** `docs/reports/report-v1.5.md` (Final acceptance
  section, `--no-verify` attestation, RLM rows, Fix cycles, Ledger row
  finalization, Verdict, header), `docs/plan.md` (v1.5 status → complete),
  `docs/llm-usage.md` (row 42), `docs/prompts/63-v15-t19-acceptance.md`
  (new) — evidence-only, no source/test/config file touched
- **REQ ids:** REQ-V15-ACC-01, REQ-V15-ACC-02, REQ-V15-ACC-03,
  REQ-V15-ACC-04, REQ-V15-EC-09

## Goal

Run final acceptance against the tree that ships — the six verbatim
gates, `checks.py run --profile full --since <base>`, `checks.py
replay --range <base>..<implementation-tip>` and Appendix B — then land
the single evidence-only commit that records `<implementation-tip>`
and starts the freeze.

## Constraints

- Evidence-only commit: no change to any `.py`, `.yaml` or config file.
  A regression found here would need a documentation-only correction
  or, if not documentation-only, would void the run per REQ-V15-ACC-03's
  own text — the spec, not this prompt, decides which.
- `<implementation-tip>` cannot be self-referential; it names T18's own
  commit, already made.
- No history rewrite: `<implementation-tip>` is already load-bearing
  (REQ-V15-ACC-04, and 20 prompt files already reference these SHAs).

## Acceptance

- The six gates, the `full` profile (15/15) and all 12 Appendix-B
  scenarios PASS on the final tree.
- `checks.py replay`'s output is quoted in full in the report, whatever
  it shows — not summarised into a claim it doesn't support.
- `uv run --locked python devtools/checks.py lint-docs` exits 0.
- This commit re-runs (per REQ-V15-ACC-03's exception clause) the
  `commit-msg` checks, the `pre-commit` profile, `lint-docs` and
  `gitleaks-tree` against the final tree — all through the live hook
  chain, not asserted separately.

## Stop

If any of the six gates, the `full` profile or an Appendix-B scenario
fails on the final tree, fix and rerun inside the 5-cycle repair
budget; if the budget is exhausted, stop and report rather than land
the evidence-only commit. A `replay` failure alone, diagnosed and
confined to pre-hook-activation commits, is not grounds to stop.
