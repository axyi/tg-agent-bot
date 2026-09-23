# Task brief — v1.11.0 T7 review fix (REV-01 finding 1: cancel-before-commit race)

Spec: `docs/spec/spec-v1.11.0.md`, §9 `REQ-V1110-ING-04` (lines 977-1034),
`REQ-V1110-REV-01` (lines 1369-1408). Repo:
`/home/akh/aihome/coders-su/projects/tg-agent-bot`, branch `main`,
committed at `edbb4cd` (T0-T7 Phase B). Gates 1-4 are green on this tree.

## The finding (from the clean-context `code-reviewer` review, verbatim)

> 🔴 **Must-fix**: `documents.py:560-571` + `bot.py:2190-2196` — a
> `/cancel` landing between the last cancellation checkpoint and
> `before_commit()` is silently lost; the document commits anyway.
> `index_document`'s last `_check_budget` call is at the end of the
> embedding-batch loop. After the loop, `page_count`/`size_bytes`/
> `hashlib.sha256(data)` (up to 20 MB) are computed, then `before_commit()`
> runs, then `BEGIN IMMEDIATE` — with **no cancellation checkpoint in that
> gap**. `IngestWorker._mark_committing` (`bot.py:2190-2196`)
> unconditionally sets `job.phase = "committing"`; it never checks
> `job.cancel.is_set()`. Failure scenario: a user sends `/cancel` while
> their job's phase is still `"running"` and execution is anywhere in
> that gap. `IngestWorker.cancel()` sees phase `"running"`, sets the
> event and `cancel_reason = "user"`, and replies `Cancelling <name>…` —
> but the worker thread, already past every checkpoint, proceeds through
> `_mark_committing` → `BEGIN IMMEDIATE` → `COMMIT` and sends a `✅ …`
> success reply. This violates REQ-V1110-ING-04's own stated invariant
> ("the two outcomes, exclusive by phase") and ERR-01 row 8's "nothing
> stored" promise, and produces a user-visible contradiction (told
> "Cancelling…", then told success). No test exercises this window: both
> `T-V1110-ING-09` and the ERR-01 row-17 test invoke `/cancel` *from
> inside* the `before_commit` callable itself — i.e. only once phase is
> already `"committing"` — never in the gap before it runs.
>
> Suggested fix: have the `before_commit` callable (or `_mark_committing`)
> check `job.cancel.is_set()` under the lock and raise
> `documents.IndexCancelled` instead of transitioning, since it already
> runs before `BEGIN IMMEDIATE` and `IndexCancelled` is already handled
> cleanly by `_process`'s exception chain.

## The fix

`bot.py`'s `IngestWorker._mark_committing` (currently, at `bot.py:2190-2196`):

```python
def _mark_committing(self, job: IngestJob) -> None:
    """documents.index_document's before_commit callable (REQ-1110-
    ING-04): moves the job to committing under the lock, immediately
    before BEGIN IMMEDIATE -- so the transition is atomic with respect
    to /cancel's own lock-protected read; no checkpoint follows it."""
    with self._lock:
        job.phase = "committing"
```

Change it to check the cancel event **inside the same locked block**,
before transitioning, and raise instead of transitioning when it's
already set:

```python
def _mark_committing(self, job: IngestJob) -> None:
    """documents.index_document's before_commit callable (REQ-1110-
    ING-04): under the lock, either raises IndexCancelled -- when a
    /cancel already landed while this job was still 'running', in the
    gap after the last checkpoint and before this callable runs -- or
    moves the job to 'committing', atomically with respect to /cancel's
    own lock-protected read. Checking cancel here is what closes that
    gap: it is the last point before BEGIN IMMEDIATE, so a job cancelled
    anywhere before it is caught here instead of committing anyway."""
    with self._lock:
        if job.cancel.is_set():
            raise documents.IndexCancelled(f"cancelled before commit ({job.cancel_reason})")
        job.phase = "committing"
```

`index_document` (`documents.py:566-571`) calls `before_commit()` with no
`try`/`except` around it — confirm this stays true (do not add one) — so
`IndexCancelled` propagates straight out of `index_document` to
`IngestWorker._process`'s existing `except documents.IndexCancelled:`
clause (`bot.py:~2108-2111`), which already calls
`_document_error_ending(..., _cancel_ending_reply(job))` and returns —
exactly the same "nothing stored, status → `❌ Cancelled.`/`❌ Interrupted
by restart.`" path every other cancellation point uses. **No other
production code should need to change** — this closes the gap entirely
within `_mark_committing`.

## New test: the gap window, closed

Add to `tests/test_v1110_ing.py` (alongside `T-V1110-ING-09`, which tests
the *other* half of this boundary — a `/cancel` arriving *after* the
phase is already `committing`):

`test_t_v1110_ing_12_cancel_in_the_gap_before_before_commit` (or fold
into `T-V1110-ING-09` as an added case if that reads more naturally to
you — your call, but the assertion must be distinct and unambiguous):
hook `IngestWorker._mark_committing` is **not** how you inject the
timing — instead, drive the race the way the finding describes it: use a
`FakeEmbedder` hook (the same mechanism `T-V1110-ING-05`/`-09` already use
to pause a job mid-run) that fires **after the last embedding batch
completes** (i.e., after the last `_check_budget` checkpoint inside
`index_document`, but the hook itself runs from inside `embedder.embed`,
so time it on the *last* batch) and, from that hook, calls `/cancel`
through `process_update` — before returning control to `index_document`,
which will then proceed to `before_commit()`. Assert: the reply from
`/cancel` is `Cancelling <name>…` (phase was still `"running"` when
`/cancel` ran); `run_one` then completes with the status edited to `❌
Cancelled.`; `documents`/`vec_chunks` gain **no new rows**; no `✅ …`
success reply is ever sent. This is the reverse timing of `T-V1110-ING-09`
(which cancels *after* `before_commit` has already run) — both must pass,
proving the boundary is race-free in both directions.

Also add a **unit-level** check directly on `_mark_committing` (fast,
no threads): construct a minimal `IngestWorker` and `IngestJob`, set
`job.cancel` before calling `worker._mark_committing(job)`, assert it
raises `documents.IndexCancelled` and `job.phase` stays `"running"`
(never transitions to `"committing"`); with `job.cancel` unset, assert it
transitions normally and raises nothing.

## Constraints

Test-first (EC-02): write the new test(s), watch them fail for the right
reason (the current code lets the job commit and send a success reply
instead of `❌ Cancelled.`), then apply the `_mark_committing` fix. Gates
1-4 must stay green. Do **not** run gate 5, `mutation_check.py`,
`rag_eval.py`, `agent_eval.py`, or `bench.py`. Do **not** run `ruff
format` (only `ruff check .`). Do not touch anything outside
`bot.py`/`tests/test_v1110_ing.py` unless you find the fix genuinely
requires it (if so, stop and report why rather than widening scope
silently).

## Acceptance

The new test(s) fail before the fix (for the right reason: a success
reply where `❌ Cancelled.` was expected, or rows present where none were
expected) and pass after. `T-V1110-ING-09` (the other half of this
boundary) still passes unamended. Gates 1-4 green.

## Delegation / secrets / commit

Delegated (EC-04, this is REV-01's "review fix", covered by T7's brief
per §14.1's "yes for the entries and any review fix"). When gates 1-4 are
green and the fix is verified test-first, commit it yourself:
- Stage: `bot.py`, `tests/test_v1110_ing.py`, this brief file.
- Write `docs/prompts/249-v1110-t7-review-fix-cancel-race.md` (check the
  actual next free prompt number first — 248 is already taken by the
  orchestrator's own review-findings-recording prompt) following
  `docs/prompts/TEMPLATE.md`'s shape. Stage `T7`, REQ ids
  `REQ-V1110-ING-04`, `REQ-V1110-REV-01`.
- Append one row to `docs/llm-usage.md` (check the actual next free row
  number first).
- Extend `docs/reports/report-v1.11.0.md`'s `## T7` section's Phase C/D
  area (read what's already there — the orchestrator has recorded the
  review's full findings list already; add your fix's own account under
  a `### Phase D — review fix (finding 1)` heading, not a new top-level
  section) describing the fix and the new test's before/after result.
- Run `uv run --locked python devtools/checks.py lint-docs` before
  committing.
- Commit message: conventional type (`fix:`), header ≤72 chars, body
  references the prompt file. Never `--no-verify`.
- `.env` is not yours to touch. Only two secret values exist in this repo
  (`config.py:351`,`:379`) — never print/quote/commit either.

Report back: commit hash, gate results, confirmation the new test
genuinely failed before the fix and passes after, and confirmation
`T-V1110-ING-09` still passes unamended. Do not paste full file contents
back.
