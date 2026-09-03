# Prompt NN — <slug>

- **Date:** YYYY-MM-DD
- **Executor model:** the model id that ran this prompt
- **Model reason:** one sentence on why this model fit this task
- **Harness:** the tool that ran it, e.g. Claude Code
- **Stage:** the spec task id this prompt implements, e.g. T3
- **Owner of:** the repository-relative paths this prompt creates or edits, e.g. `devtools/checks.py`
- **REQ ids:** the requirement ids this prompt satisfies, e.g. REQ-V15-PRM-01

## Goal

One paragraph: what this prompt is for, in prose.

## Constraints

What the executor may not do: files it must not touch, rules it must obey, budgets.

## Acceptance

How the caller decides it is done: a named test (`test_example`), a command
(`` `uv run --locked pytest` ``) with its expected exit code, or an artefact
path such as `docs/reports/report-v1.5.md`.

## Stop

When the executor stops and reports instead of continuing: an exhausted
repair budget, a discovered benchmark-affecting change, a spec ambiguity.
