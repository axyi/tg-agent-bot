# Prompt 221 — v1103 T1: the `exec` guard (EXEC-01, EXEC-02)

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** source-writing task, delegated per EC-03 default.
- **Harness:** Claude Code (general-purpose subagent)
- **Stage:** T1
- **Owner of:** `tools.py`, `tests/test_v1103_exec.py`
- **REQ ids:** REQ-V1103-EXEC-01, REQ-V1103-EXEC-02, REQ-V1103-ERR-01
  (rows 1-2), REQ-V1103-SEC-01, REQ-V1103-NG-03, REQ-V1103-NG-04,
  REQ-V1103-NG-14

## Goal

Add three deny rules inside `_validate_exec_arguments` that refuse
`env`/`printenv`, `.env`-basename files and `/proc/<pid>/environ`
argv shapes before any runner is called — defense in depth, not a fix
(gate 8 clause (e) still fails the attempt regardless). Full detail in
`docs/spec/task-briefs/v1103-T1.md`.

## Constraints

Test-first. No shell parsing, no allow-list, no symlink/path
normalisation (NG-03, NG-04) — the documented bypass shapes must keep
running unrefused. Do not edit the `exec` tool description (NG-14,
catalog stays 1798/1800 chars). Do not touch `tests/test_exec.py` or
`tests/test_v1100_toolcall.py`. Do not run gates 5/6/7/8.

## Acceptance

See `docs/spec/task-briefs/v1103-T1.md`'s Acceptance section:
`uv run --locked pytest tests/test_v1103_exec.py -q` green; gates 1-4
green; refusal text byte-equal; near-misses and documented bypass
shapes run unrefused; catalog still 1798 chars.

## Stop

If a near-miss or documented bypass shape cannot be made to pass without
widening the deny rules beyond the three literal predicates, stop and
report rather than expanding scope.
