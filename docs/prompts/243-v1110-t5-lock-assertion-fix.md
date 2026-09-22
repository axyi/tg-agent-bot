# Prompt 243 — v1.11.0 T5 follow-up: fix a vacuous lock-count assertion

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** a single, empirically-verified test-quality fix under
  every §5.1 threshold — orchestrator, main context, no delegation.
- **Harness:** Claude Code (background session, orchestrator)
- **Stage:** T5 (follow-up)
- **Owner of:** `tests/test_v1110_ing.py`
- **REQ ids:** REQ-V1110-ING-02, REQ-V1110-ING-03

## Goal

T5's delegated subagent (commit `3edc7fc`) found, via its own post-commit
advisor review, that `T-V1110-ING-02`'s lock-spy assertion
(`lock_spy.enter_count >= 2`) was vacuous: `worker.in_flight(USER_ID)`,
called later in the same test, also enters the spy, so the threshold was
satisfied even with `reserve()`'s lock removed. It left the fix
uncommitted (own guidance: one prompt → one commit, don't amend `3edc7fc`)
for a small follow-up, matching this run's established pattern (prompt
238's T1 record correction).

Snapshot `lock_spy.enter_count` immediately before `_handle_document` and
assert an exact delta of 2 immediately after (before any other
lock-touching call), instead of a loose `>=` threshold taken after
`in_flight()` had already contributed to the count.

## Constraints

Test-only change, one file. No production code touched. `lint-docs` must
stay green.

## Acceptance

`tests/test_v1110_ing.py::test_t_v1110_ing_02_worker_split_and_thread_owned_connection`
passes with the corrected assertion. **Bite empirically re-verified by the
orchestrator** (not just trusted from the subagent's report): `reserve`'s
`with self._lock:` removed by hand → this test fails
(`assert (1 - 0) == 2`) → `bot.py` restored via the untouched backup,
`git diff --stat bot.py` empty. Gates 1-4 green on the corrected tree
(`pytest`: 2368 passed, 1 skipped, 2 xfailed).

## Stop

Not applicable — this is itself the fix.
