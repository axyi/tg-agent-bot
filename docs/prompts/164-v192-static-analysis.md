# Prompt 164 — v1.9.2 T1: whole-tree static-analysis findings fixed

- **Date:** 2026-09-12
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded, fully specified patch against an existing
  contract (`docs/spec/task-briefs/v192-T1.md`) — every skylos finding
  already has a named decision procedure, every ruff bug-class hit a named
  disposition path; no open-ended design decision, just per-finding
  archaeology (`grep`, `git log -S`) against a closed list.
- **Harness:** Claude Code
- **Stage:** v1.9.2 T1 (patch, no new spec file — precedent v1.5.1, v1.9.1)
- **Owner of:** `agent.py`, `bot.py`, `config.py`, `dashboard_server.py`,
  `devtools/bench.py`, `devtools/checks.py`, `devtools/rag_eval.py`,
  `rag.py`, `tools.py`, `tracing.py`, `pyproject.toml`,
  `config/quality_gates.yaml`, `tests/test_docker.py`,
  `tests/test_v11_patch.py`, `tests/test_v190_agents.py`,
  `tests/test_v190_chunking.py`, `tests/test_v190_embeddings.py`,
  `tests/test_v190_retrieval.py`, `tests/test_v1_guardrails.py`,
  `docs/spec/task-briefs/v192-handoff.md` (adding the untracked file),
  `docs/reports/report-v1.9.2.md`, `docs/llm-usage.md`
- **REQ ids:** REQ-V15-NG-04 (§B only — this prompt does not touch it;
  prompt 165 does)

## Goal

Fix every skylos, semgrep and named ruff bug-class finding the whole-tree
inventory (`docs/spec/task-briefs/v192-T1.md`) surfaced, one class of
finding per commit boundary where that keeps the diff reviewable: §A's 27
skylos findings each get an individual keep-and-suppress or delete
decision; §C's semgrep self-scan exclusion, the 17 reviewed ruff
bug-class hits (3 fixed, 14 dismissed with reasons), and the `RUF100`/`B`
select additions (with every zip() site given the strict= value its
surrounding code implies). The whole-tree reformat (REQ-V15-NG-04) is out
of scope for this prompt — it is prompt 165's own commit, so this diff
stays readable.

## Constraints

- A skylos "unused" hit is never a deletion order by itself — §A's four-step
  decision procedure (interface-mandated, referenced-by-string,
  genuinely-dead-with-evidence, uncertain) is applied per finding, in order,
  and the report records which step decided each one.
- No scanner exclusion counts as a fix. The `.semgrep/` self-scan exclusion
  is a target-scoping fix (semgrep was scanning its own rule pack), not a
  suppression of a real finding; it is named as such.
- Every inline suppression comment names the interface/reference it
  protects; `_MIGRATION_2_TO_3` could not carry one (the flagged line opens
  a triple-quoted SQL string — appending a comment there would corrupt the
  string). First pass left it unsuppressed and reported as unresolvable at
  this skylos pin; the operator then ruled it out under §A.3 instead
  (superseding the constant's own "kept, unlisted edit" comment), so it is
  deleted, with (a)(b)(c) evidence in the report. `f421621` was amended to
  carry this so commit 1 holds all of §A's work.
- Version-pin and count-bearing tests are repointed, never deleted
  (REQ-V190-EC-03) — none needed repointing this task; no test literal this
  task touches pins a count this task's own edits change.
- `.env` is never read, printed or committed; `data/`, `evals/rag/corpus`
  are never opened.
- Gate 6 `drifted` stays 0 — verified by the throwaway drift script, not
  assumed.
- No `--no-verify`. Do not push.

## Acceptance

```
uv run --locked ruff check .                      # exit 0
uv run --locked ruff format --check .             # report the count (75 files, unchanged by this prompt)
uv run --locked pytest                            # exit 0, report collected count and wall clock
uv run --locked python bot.py --selftest          # exit 0
skylos . --gate --strict --format json --output <artefact>   # report the count (0, after the operator's _MIGRATION_2_TO_3 ruling)
semgrep scan --config .semgrep/ --severity ERROR --error --metrics=off --disable-version-check .   # exit 0, 0 findings under .semgrep/ at any severity
uv run --locked python devtools/checks.py lint-docs   # exit 0
<throwaway drift script>                          # 108/108
```

## Stop

- a skylos deletion candidate turns out to be reachable in a way §A's
  procedure does not classify;
- an `S608` site really does interpolate a user-controlled value;
- any gate in the acceptance list is red after a repair budget of two
  attempts.

Neither triggered this run.
