# Prompt 152 — v1.9.0 T7: the document flow and the commands

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for spec-driven implementation tasks in this run (T1-T6 used the same model).
- **Harness:** Claude Code
- **Stage:** T7
- **Owner of:** `bot.py`; `tests/fakes.py` (`FakeTelegram` extension); `tests/test_v190_commands.py` (new); `tests/test_v190_e2e.py` (new)
- **REQ ids:** REQ-V190-CMD-01, REQ-V190-CMD-02, REQ-V190-CMD-03, REQ-V190-CMD-04, REQ-V190-CMD-05, REQ-V190-CMD-06, REQ-V190-CMD-07, REQ-V190-SEC-04 (the handler half)

## Goal

Implement CMD-01..07 and §8's Telegram-facing error-matrix rows end to
end, test-first: the document branch in `process_update` (after the
allow-list check, before the text-only guard), the per-turn `rag.Searcher`
wired from a process-wide `EmbeddingsClient` built in `main`; `TelegramClient.
get_file`/`download_file` (a capped streaming GET, with
`TelegramDownloadTimeout` raised before the generic `TransportError`
clause so a download timeout is never swallowed); `_handle_document`'s five
pre-checks in order (size, cleaned filename, type, the 20-document count,
then the status message and the download); `_StatusMessage.update` and the
four owned progress strings (only `"📄 received"` and both endings belong to
the handler; the other three come from `index_document`'s `progress`
callback); `/documents` and `/delete <filename>`; and the one outer
exception boundary so an unexpected failure never kills `poll_loop`.

## Constraints

Test-first: tests written and watched to fail before the implementation.
Exact user-facing strings only — no exception text interpolated except
row 1's `<ext>`, and that only in the log line. `classify` must run on the
already-cleaned filename, never the raw one (T3's ordering-hazard finding).
`documents.py`/`llm/embeddings.py` were read directly for the real
exception class names before writing any `except` clause; none guessed.
`DocumentTooLarge` (the mid-stream size-cap exception `TelegramClient.
download_file` raises) is a new `bot.py` exception, not a `TelegramError`
subclass — a size refusal, not a transport failure. `FakeTelegram` gained
its document-flow surface by extension, not a fork. No file write anywhere
in the handler (`inspect.getsource(bot._handle_document)`, AST-walked, not
a whole-file grep — `bot.py` legitimately uses `Path`/`tempfile`/`open`
elsewhere). `T-V190-SEC-04` stayed T6's (SEC-02); this task's own handler
check is named `test_t_v190_sec_04b_no_file_writes_in_the_document_handler`
to avoid the collision the brief discloses. Did not touch `README.md`
(T10's job) or `devtools/mutation_check.py`/any live gate.

## Acceptance

`uv run --locked ruff check .`, `uv run --locked pytest` (1521 collected,
up from 1463 before this task's two new files — 55 in
`tests/test_v190_commands.py`, 3 in `tests/test_v190_e2e.py`),
`uv run --locked python bot.py --selftest` all exit 0, fully offline (no
socket reached in any test — `T-V190-CMD-10`'s two tests use a real
`httpx.Client` wired to `httpx.MockTransport`, never the network). Every
ERR-01 row this task owns (1, 2, 3, 4, 5a, 5b, 6, 7, 10a, 10b, 10c, 11, 12,
13, 14, 15) has its own test. `poll_loop` survives an injected
`ZeroDivisionError` from a monkeypatched `documents.extract`, with a
second update in the same batch still processed
(`test_t_v190_cmd_08_exception_in_document_handler_lets_poll_loop_continue`).
The 20-document `COUNT` precedes the status message and `getFile`
(`test_t_v190_err_01_row_13_pre_check_limit_reached_plain_reply`).
`started_at` is the handler's first action, proved by a spy `monotonic`
(`test_t_v190_cmd_03_started_at_is_the_handlers_first_action`) and by
`T-V190-CMD-09`'s budget-counts-pre-index-time test. A download timeout
arrives as `TelegramDownloadTimeout`, matched by type at the real
`download_file` boundary, never by parsing a message
(`test_t_v190_cmd_10_download_timeout_via_the_real_boundary_raises_the_typed_exception`).

## Stop

Nothing stopped on. One collision disclosed and resolved per the task
brief's own instruction (not a self-authorized amendment): the brief
listed `tests/test_v190_errors.py` as a new file for this task, but that
path already exists — created by T4 for `documents.index_document`'s own
error-matrix rows, whose own docstring explicitly reserves the Telegram-
facing rows for "T7's own [file]". Wrote this task's ERR-01 tests into a
differently-named new file, `tests/test_v190_commands.py`, instead of
touching or overwriting T4's file.

Two smaller deviations from the brief's literal shape, each with its
reason:

- `T-V190-E2E-03`'s scenario, per `spec-v1.9.0-delta-1.md`'s test table,
  reads "`/delete` -> the same question -> `\"No passages matched.\"`
  reaches the model". Implemented against the real `rag.Searcher` (not a
  scripted `FakeSearcher`) for genuine end-to-end coverage; with the
  single uploaded document deleted, `documents_present` is `False` and the
  tool renders `tools.NO_DOCUMENTS_TEXT`, not `NO_PASSAGES_TEXT` — the
  latter needs `documents_present=True` with zero retrieved passages,
  which real hybrid retrieval cannot guarantee deterministically (vector
  KNN has no similarity floor: with >= 1 vector still present for the user
  it always returns *something*). The test's docstring records this; both
  empty-result strings share the one contract actually proved — zero
  passages, no source line, the scripted "not covered" reply passes
  through unchanged.
- `_handle_document` and `TelegramClient.get_file`/`download_file` gained
  an injectable `monotonic`/clock only where a test needs to control it
  (`_handle_document`'s `monotonic` parameter, defaulting to
  `time.monotonic`); not literally spelled out in the brief but matches
  the rest of the codebase's own injectable-clock convention
  (`RateLimiter`, `_TypingIndicator`, `index_document` itself) and is
  required to test `T-V190-CMD-09`/row 10c deterministically.

A pre-commit review (this run's `advisor` step) found one real correctness
gap and one spec-text gap, both fixed before this commit, with a test
each:

- The `file_path = tg.get_file(...)["file_path"]` line sat inside the
  same `try` as the docx clause (`except (..., KeyError)`); `file_path`
  is optional on Telegram's `File` object, so a `getFile` reply without it
  would have raised a bare `KeyError`, caught by the docx clause and
  reported as "Could not read this DOCX file." — row 3's string on a row
  11 condition, violating "matched by type, never parsed." Fixed: a
  missing/non-string `file_path` now raises `TelegramError` explicitly,
  mapped to row 11
  (`test_t_v190_err_01_row_11_get_file_without_a_file_path`).
  `FakeTelegram.download_file` also now raises `AssertionError` for an
  unseeded path instead of a bare `KeyError`, so a test bug can never
  impersonate an ERR-01 row.
- CMD-05's own text says "Filenames pass `redact()`"; `/documents` relied
  only on `_send`'s blanket redact rather than doing it explicitly at the
  render site. Added the explicit `redact()` call plus
  `test_t_v190_cmd_05_filenames_are_redacted`.

The `T-V190-CMD-03` started-at test was also strengthened to assert call
*order* (a shared markers list), not just that `monotonic` was called
once.
