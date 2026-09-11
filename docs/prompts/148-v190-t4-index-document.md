# Prompt 148 — v1.9.0 T4: index_document

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for spec-driven implementation tasks in this run (T1-T3 used the same model).
- **Harness:** Claude Code
- **Stage:** T4
- **Owner of:** `documents.py` (extended, not rewritten); `tests/test_v190_storage.py` (extended); `tests/test_v190_errors.py` (new)
- **REQ ids:** REQ-V190-DOC-04, REQ-V190-DOC-05

## Goal

Implement `documents.index_document` (DOC-05): the classify -> extract ->
chunk -> embed -> store pipeline on top of T3's `classify`/`extract`/
`chunk_text` and T1's storage API, with DOC-04's limits (500,000-char text
cap, 20-non-whitespace-char empty floor), its 300 s wall-clock budget
(checked between every stage and between PDF pages), and the one storage
transaction that re-checks the 20-document limit immediately before the
insert and replaces an existing same-filename document in place.

## Constraints

Test-first. Build only on `documents.py` (T3's) and `storage.py` (T1's) --
read their real signatures, never reinvent them. `index_document` never
touches Telegram; `progress` is its only side channel besides the return
value and exceptions. Exactly three progress strings (`📄 extracted: …`,
`📄 chunked: N`, `📄 embedding: i/n`); classify and store emit nothing. No
`rag.embedding` or `vec_chunks` lifecycle statement anywhere in this module
-- only `storage.add_vectors`. Do not implement the Telegram-facing error
strings, `_handle_document`, or CMD-03's pre-check -- that is T7's. Do not
run `devtools/mutation_check.py` or any live gate.

## Acceptance

`uv run --locked ruff check .`, `uv run --locked pytest` (1378 collected,
up from 1362 before this task), `uv run --locked python bot.py --selftest`
all exit 0. A failure at every stage (extraction, chunking, embedding,
budget, 20-doc-recheck, sqlite error) leaves zero rows -- covered by
`tests/test_v190_errors.py`. Every budget check reads
`monotonic() - started_at`. `grep`-verified: no `rag.embedding`/`vec_chunks`
statement in `documents.py`.

## Stop

Discovered and reported rather than resolved: (1) `documents.IndexBudgetExceeded`
did not exist anywhere in the tree despite the brief describing it as
"already partially wired by T3 inside the PDF per-page loop" -- T3 shipped
DOC-02 (spec lines 336-342) without that hook, so this is a T3 erratum;
T4 defined the exception and wired the loop itself, since the brief's own
instructions ("thread the same check between every other stage boundary
too") already scoped that work to this task. (2) A structurally reachable
zero-chunk hole -- a multi-page PDF whose total non-whitespace count clears
DOC-04's 20-char floor but whose *individual* pages each fall under
`chunk_text`'s own per-call floor stores a `documents` row with
`chunk_count=0`, no chunks, no vectors, and no error -- reported to the
orchestrator, not resolved, since DOC-04's exact three-check order doesn't
mention a post-chunking guard and adding one unlisted would be scope
creep on this task.
