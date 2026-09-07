# Prompt 112 — spec-v1.7.0 T8: docs and the gate config, no version bump

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T8
- **Owner of:** `.env.example`, `README.md`, `AGENTS.md`, `docs/plan.md`,
  `config/quality_gates.yaml` (`lint-docs.report_path` only),
  `docs/reports/report-v1.7.0.md` (the T0 ledger row's `|` count, plus a new
  T8 section), `tests/test_v170_reasoning.py` (extended),
  `docs/prompts/112-v170-t8-docs-gate-config.md` (new)
- **REQ ids:** REQ-V170-RPT-02, REQ-V170-RPT-04, REQ-V170-POL-01 (the
  documentation echo), REQ-V170-VER-01 (no bump), REQ-V170-ACC-03 (all three
  test halves), REQ-V170-REV-01 item 8

## Goal

Land every documentation and gate-config change this release owes before the
candidate freeze — `.env.example`'s two new keys, `README.md`'s Reasoning
policy section, `AGENTS.md`'s corrected test count and the two-variable
line, `docs/plan.md`'s new milestone row, and `config/quality_gates.yaml`'s
`lint-docs.report_path` repoint — and write the three REQ-V170-ACC-03 test
halves now, since REQ-V170-ACC-03's freeze forbids adding or editing any
test after the first candidate run. **`pyproject.toml` is not touched**;
the version bump belongs to T12's selection commit alone.

## Constraints

- No version literal appears anywhere outside `T-V170-ACC-03`'s own
  version half and the ledger row's `Ver` cell (REQ-V170-RPT-01) — not in
  `.env.example`, not in `README.md`'s new section, not in `AGENTS.md`.
- `.env.example`'s active `LLM_REASONING_POLICY`/`LLM_REASONING_ON_PURPOSES`
  lines carry the pre-T12 **compatibility** default
  (`model-default`/`tool-round`), never a candidate's treatment.
- `T-V170-ACC-03`'s equivalence and selection-commit-allowlist halves must
  skip, with a recorded reason, while their precondition does not exist yet
  (no committed `cand-v170-*.json`, no T12 commit); the version half never
  skips and asserts `1.6.0` at T8.
- The selection-commit locator and hunk validator are exercised now, before
  the freeze closes the door on ever testing them again, via synthetic
  fixtures (a throwaway git repo in `tmp_path`, reusing
  `tests/test_v15_standards.py`'s `_git` helper) — not left as dead code
  until T12.
- The selection commit's prompt-file citation the locator searches for is
  pinned to the pattern `docs/prompts/\d+-v170-t12-[\w.-]*\.md`; T12's own
  prompt file must match it.
- One prompt -> one commit, referencing this file.

## Acceptance

- `tests/test_v170_reasoning.py` green: 2 new tests (`T-V170-VER-01`,
  `T-V170-RPT-02`) plus `T-V170-ACC-03`'s three halves and six companion
  synthetic tests exercising their non-skip logic (11 new tests total).
- Full suite green: `uv run --locked pytest` (1133 collected, 2 skipped —
  `T-V170-ACC-03`'s equivalence and allowlist halves, both with a recorded
  skip reason).
- `uv run --locked ruff check .` exits 0.
- `uv run --locked python devtools/checks.py lint-docs` exits 0 against
  `report-v1.7.0.md`.
- `uv run --locked python bot.py --selftest` and `--selftest-live` both
  exit 0.
- `uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json`
  exits 0.
- `uv run --locked python devtools/mutation_check.py` exits 0 (83/83
  killed, 0 survived/errored/drifted).
- `git diff --stat pyproject.toml` empty.

## Stop

None triggered. One blocking discrepancy surfaced and fixed before writing
any test or doc: `checks.py lint-docs`, run immediately after the
`report_path` repoint (before it had ever been checked against a real
report), failed with `ledger row has 11 '|' but the header has 12` — the T0
skeleton's ledger row was one `TBD` cell short. Fixed by adding the missing
cell; not a freeze violation, since no candidate run has happened yet.
