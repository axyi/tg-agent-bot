# Prompt 189 — v1.9.5 T1 review findings: close 1-3, paperwork only for the rest

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** three narrow, well-specified review findings against
  code the reviewer already located precisely (test name, the exact
  structural flaw in each assertion, and the exact missing artefact) --
  no design decision, bounded fix-and-test-and-paperwork work.
- **Harness:** Claude Code
- **Stage:** v1.9.5 T1 review close-out (clean-context code review of
  commit `3f884ef`, GitHub issue #3)
- **Owner of:** `tests/test_routing.py`, `docs/llm-usage.md` (rows 98-99),
  this prompt file
- **REQ ids:** none new (review remediation against REQ-V190-STO-04's
  existing scope, no behaviour change)

## Goal

Close the clean-context review's two request-changes findings and one
should-fix finding against `3f884ef` ("fix: bind the embedding pair at
every init_schema call site"): finding 1, `getMessage()` never renders
`exc_info` so `test_v195_main_exits_2_when_startup_schema_binding_refuses`'s
traceback assertion could never fail even if the except clause used
`log.exception(...)`; finding 2, that same test only proves main()'s own
`except ConfigError` wiring via a monkeypatched raise, not that a *real*
`_bind_new_embedding_pair`/`_rebind_embedding_pair` `ConfigError` reaches
it end to end; finding 3, `docs/llm-usage.md` never got the row the brief
and the issue's own DoD checklist required for prompt 188/commit `3f884ef`.
Everything else in the review (the `devtools/bench.py` bare `init_schema`
call, AC-1 verified transitively, `_live_db`'s newly-effective production
write, the stale 1634/119 counts) was 🟢 informational, correctly out of
scope or already correctly disclosed, and stays untouched.

## Constraints

- Test-only + docs changes: no production code (`bot.py`, `storage.py`,
  `devtools/mutation_check.py`) touched, since none of the three findings
  require it.
- Leave `tests/test_v12_patch.py:743-760`'s identical pre-existing
  `getMessage()`/"Traceback" pattern alone -- out of scope, a sibling
  finding for a different commit.
- Do not touch `docs/reports/report-v1.9.4.md`, `AGENTS.md`'s gate-3/gate-6
  count lines, `config/quality_gates.yaml`, or the GitHub issue.
- New commit, not an amend of `3f884ef` -- one prompt, one commit.

## Acceptance

Test-only, no production code touched, no mutation-entry `find` strings
moved and no RAG-path file touched -- same acceptance-gate profile
`docs/llm-usage.md` row 96 / `docs/prompts/186-v194-review-findings.md`
used for the v1.9.4 review close-out of the same shape:

- `uv run --locked ruff check .` exit 0.
- `uv run --locked ruff format --check .` exit 0.
- `uv run --locked pytest` exit 0, including the strengthened/new cases in
  `tests/test_routing.py`.
- `uv run --locked python bot.py --selftest` exit 0.
- `uv run --locked python devtools/checks.py lint-docs` exit 0.

## Stop

Stop and report instead of forcing a workaround if seeding a real
orphaned-`vec_chunks`-with-a-document or pair-changed-with-a-document
database cannot be made to raise the real `ConfigError` through
`storage.init_schema` the way `T-V190-STO-04`'s own negative test already
proves it does.
