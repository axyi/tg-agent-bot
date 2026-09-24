# Prompt 267 — v1.11.1 T6: version bump, evidence commit, local tag

- **Date:** 2026-09-24
- **Executor model:** claude-sonnet-5
- **Model reason:** the bump commit is a source-writing task
  (`pyproject.toml`, `uv.lock`, eleven-plus pin rewrites, `AGENTS.md`,
  README's release row, `tests/test_v1111_ver.py`) — delegated per
  §10.1's yes cell, brief `v1111-T6.md`; the evidence commit is
  *artefacts only* (four fixed paths) — the orchestrator's own
  commands-only/artefacts-only work, matching v1.11.0's own T8
  precedent.
- **Harness:** Claude Code (background session, orchestrator; one
  subagent for the bump commit)
- **Stage:** T6
- **Owner of:** `pyproject.toml`, `uv.lock`, eleven-plus pin sites
  (`docs/spec/task-briefs/v1111-T0-pin-inventory.md`'s T6 rows, 14 of
  them), `AGENTS.md`, `README.md`'s release table,
  `config/quality_gates.yaml:797`'s `report_path`,
  `tests/test_v1111_ver.py` (bump commit); `docs/reports/report-v1.11.1.md`,
  `docs/reports/tg-post-v1.11.1.md`, `docs/llm-usage.md` (evidence
  commit); this prompt file (bundled per EC-04, same pattern as
  `9d8dc0e`/prompt 261 — referenced by both commits, committed with
  neither's own diff until the bump commit lands it)
- **REQ ids:** REQ-V1111-VER-01, VER-02, VER-03, VER-04, RPT-01,
  GATE-01, REV-02

## Goal

Bump `pyproject.toml` from `1.11.0` to `1.11.1`, regenerate `uv.lock`
for the version literal only, rewrite all fourteen T6 pin sites in
place (the eleven the spec names plus the three the T0 pin-inventory
subagent found by tree-wide extension: `tests/test_v1101_gates.py:259`,
`tests/test_v1103_gates.py:61`, `tests/test_v1104_version.py:108`),
repoint `AGENTS.md`'s count lines and `config/quality_gates.yaml:797`'s
`report_path`, add README's `v1.11.1` release row (and drop `v1.11.0`'s
"; this release" clause), with `tests/test_v1111_ver.py` (four
functions, exact names at spec `:702-705`) written and red before
`pyproject.toml` changes. Then, after gates 1-6 fresh, the preliminary
identity check, the collection/node-id checks and `replay` all pass,
land the evidence-only commit recording T6's results, the ledger row
and `tg-post-v1.11.1.md`, and create the local annotated tag on green.

## Constraints

Test-first (EC-02): `tests/test_v1111_ver.py` written and run red
(`T-V1111-VER-01`, `-03` red before the bump; `-02`, `-04` structural,
carve-out, may be green on first execution) before `pyproject.toml`
changes. `uv lock`'s regenerated `uv.lock` diff must be confined to the
project's own `version = "..."` line — nothing else, or
`dependency_diff_is_version_only` returns `False` and the identity
verdict fails. Every pin site rewritten in place, nothing renamed or
deleted. The bump commit's diff must not touch the waived `/sessions`
README row (T5's should-fix, waived — out of scope for T6). `.env`,
`data/`, `bot.db`, `sandbox/`, `exec_audit.jsonl` never opened.
`--no-verify` never.

## Acceptance

`T-V1111-VER-01…04` green; count ≥ floor (2384) + 27 = **2411** exactly
(2407 + this task's 4 new functions); `comm -23` against
`v1111-T0-nodeids.txt` empty; `dependency_diff_is_version_only` `True`
on the bump commit; gates 1-6 fresh all green (gate 6 alone, `W`
recorded); `replay --range v1.11.0..HEAD` clean on every commit;
Appendix B's E1-E6 all pass via `pytest tests/test_v1111_*.py`; the
evidence commit's `git show --stat` names exactly
`docs/reports/report-v1.11.1.md`, `docs/reports/tg-post-v1.11.1.md`,
this prompt file, `docs/llm-usage.md`; the post-evidence identity check,
E7, the final `lint-docs` and the evidence commit's own `gitleaks-tree`
all pass, recorded **only** in the tag message's six fields, never in
the report; the annotated tag `v1.11.1` created locally, `git push` not
issued.

## Stop

`dependency_diff_is_version_only` `False` (preliminary or definitive), a
collection count below floor + 27, a non-empty `comm -23` line, gate 8
already exited 1 at T5 (it did not), or any VER-01 tag-message field not
reading as required, are each the stop route (REV-03) — none occurred
this task.
