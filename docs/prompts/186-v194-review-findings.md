# Prompt 186 — v1.9.4 review findings: close 1-3, paperwork only for the rest

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** three narrow, well-specified review findings against
  code the reviewer already located precisely (`file:line` for each) --
  no design decision, bounded fix-and-test work.
- **Harness:** Claude Code
- **Stage:** v1.9.4 review close-out (docs/spec/task-briefs/v194-review.md)
- **Owner of:** `devtools/rag_eval.py`, `config.py`, `devtools/mutation_check.py`,
  `tests/test_v194_redaction.py`, `tests/test_v190_eval.py`, this prompt file
- **REQ ids:** none new (review remediation, no behaviour change beyond the
  three findings' own scope)

## Goal

Close the clean-context review's 🟠 finding 1 and 🟡 findings 2-3 against
the five just-landed v1.9.4 commits: gate 7's root logger level (finding 1),
`RedactingFormatter`'s cached `record.exc_text` (finding 2), and turn 3's
gold-verdict matcher in `devtools/rag_eval.py`'s conversation smoke
(finding 3). Findings 4-8 are documentation-only (report/llm-usage/prompt
185/quality-gates wording) and are handled by the coordinator separately,
landing in the same commit as this prompt's code and tests:
`fix: rag_eval logs at WARNING; smoke turn 3 checks evidence; review
paperwork (v1.9.4)`.

## Constraints

- Do not touch `docs/reports/report-v1.9.4.md`, `docs/llm-usage.md`,
  `docs/prompts/185-v194-t2-measurement-addendum.md`, or
  `config/quality_gates.yaml` -- coordinator's share.
- Do not run `devtools/mutation_check.py`'s full/`--select`/`--only` modes,
  nor `devtools/rag_eval.py`'s `main()` (a live run) -- both are the
  coordinator's acceptance step.
- Do not touch `.env`; never read/print it.
- No `git add`/`commit`/`push` -- the coordinator commits code and docs
  together, one commit for prompt 186.

## Acceptance

- `uv run --locked ruff check .` exit 0.
- `uv run --locked ruff format --check .` exit 0.
- `uv run --locked pytest` exit 0, including the extended/new cases in
  `tests/test_v194_redaction.py` and `tests/test_v190_eval.py`.
- `uv run --locked python bot.py --selftest` exit 0.
- `uv run --locked python devtools/checks.py lint-docs` exit 0.
- The throwaway drift script (mutation `find` strings vs. the real repo,
  never committed) reports every entry matched, including the one
  re-derived here (`v194-redacting-formatter-skips-redact`, whose `find`
  text moved when `RedactingFormatter.format()` grew a second statement).

## Stop

Stop and report instead of forcing a workaround if the tightened turn-3
matcher (finding 3) cannot be made to pass without breaking an existing
offline test in a way not covered by the review brief's own instructions,
or if a mutation entry cannot be re-derived with identical semantics.
