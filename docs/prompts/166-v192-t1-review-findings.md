# Prompt 166 — v1.9.2 T1: close the clean-context review findings

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a fully enumerated documentation-correction task against
  an existing contract (`docs/spec/task-briefs/v192-T1-review.md`) — every
  finding names its exact fix; no code changes beyond one gate-config
  addition already specified line-for-line, no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.2 T1, post-review paperwork pass (patch, no new spec file)
- **Owner of:** `docs/llm-usage.md`, `docs/reports/report-v1.9.2.md`,
  `docs/spec/spec-v1.9.0-delta-1.md`, `config/quality_gates.yaml`,
  `docs/spec/task-briefs/v192-T1-review.md` (this prompt's own brief, now
  committed), `docs/prompts/166-v192-t1-review-findings.md`
- **REQ ids:** none new — closes documentation drift the review found
  against REQ-V15-NG-04's own paperwork, cites REQ-V170-NG-14

## Goal

Close all nine findings from the clean-context review of `6c9a904` +
`d25d664` (`docs/spec/task-briefs/v192-T1-review.md`) in one commit, without
rewriting either reviewed commit: the stale pre-amend description in
`docs/llm-usage.md` row 74 (🔴); an erratum on `docs/reports/report-v1.9.2.md`
§A row 8 naming both the stale commit message and the superseded
REQ-V170-NG-14 non-goal (🟠 x2); refreshed line citations in
`docs/spec/spec-v1.9.0-delta-1.md` (🟠); `ruff-format-all` added to the
`pre-commit` profile, with `ruff-format`'s own comment explaining why it
cannot simply retire (`replay`'s `blocking_paths` read) (🟠); a
`storage.py:439`→`:487` citation fix in report §C.1/§C.2 (🟡); a disposition
line on the brief's moot doc-update instruction (🟡); a delegation-record
note on the `Claude Sonnet 5` trailers (🟡); and one sentence on
`# skylos: ignore`'s def-line/function-name interaction, naming the eight
affected functions (🟡).

## Constraints

- `6c9a904` and `d25d664` are not rewritten — every correction is an
  erratum in the affected doc, never a `git commit --amend`/rebase.
- `pyproject.toml`'s `blocking_paths` on `ruff-format` stays (needed by
  `devtools/checks.py:892`'s `replay`); only the *profile membership* gains
  `ruff-format-all` alongside it in `pre-commit`.
- The spec-matrix table (`spec-v1.9.0-delta-1.md`) and its parser mapping
  (`tests/test_v15_standards.py`) are kept in sync: the `(tree)` row's
  `pre-commit` cell moves to `yes` to match the profile change, verified by
  `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`.
- Not pushed; no `--no-verify`.

## Acceptance

```
uv run --locked python devtools/checks.py lint-docs   # exit 0
uv run --locked pytest tests/test_v15_standards.py    # exit 0
uv run --locked ruff check .                          # exit 0
uv run --locked ruff format --check .                 # exit 0
uv run --locked python devtools/checks.py run --profile pre-commit   # exit 0
```

## Stop

None triggered — every finding had a named, unambiguous fix.
