# Prompt 240 — v1.11.0 T3: sessions — list and switch, no schema change

- **Date:** 2026-09-22
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (EC-04), brief
  `docs/spec/task-briefs/v1110-T3.md`; test-first source/test work, within
  this one subagent's single context.
- **Harness:** Claude Code (subagent)
- **Stage:** T3
- **Owner of:** `storage.py`, `bot.py`, `tests/test_v1110_ses.py` (new),
  `tests/test_telegram.py`, `tests/test_summary.py`,
  `tests/test_v1100_red_team.py`, `README.md`,
  `docs/spec/task-briefs/v1110-T3.md`,
  `docs/prompts/240-v1110-t3-sessions.md`, `docs/llm-usage.md` (row 151),
  `docs/reports/report-v1.11.0.md` (`## T3`)
- **REQ ids:** REQ-V1110-SES-01, REQ-V1110-SES-02, REQ-V1110-SES-03

## Goal

Add sessions — list and switch — with no schema change, per
`docs/spec/spec-v1.11.0.md` §6 and brief `docs/spec/task-briefs/v1110-T3.md`:
`storage.py` gains `list_conversations`, `count_conversations`,
`activate_conversation` (the last following `start_new_conversation`'s exact
`BEGIN IMMEDIATE`/two-`UPDATE`/`COMMIT`-or-`ROLLBACK` recipe); `bot.py`
dispatches `/sessions` (a table-path body) and `/session <id>` (a plain
switch reply), and `/new`'s reply now names the id
(`New conversation started (#<id>).`).

**`list_conversations`'s title column** is computed by a small SQL function
(`_derive_session_title`, registered on the connection via
`conn.create_function` inside `list_conversations`) rather than a Python
post-processing pass over fetched rows. This is a pattern new to this
codebase (no prior `create_function` call exists in `storage.py`), chosen
deliberately: it keeps `list_conversations` a single query returning real
`sqlite3.Row` objects — matching the brief's literal
`-> list[sqlite3.Row]` signature and `recent_conversations`'s own shape —
instead of either N synthetic per-row re-selects or a `list[dict]` that only
duck-types as a Row. `conversation_title` (the single-conversation lookup
`/session`'s switch reply uses) calls the same underlying
`_derive_session_title` function directly in Python, so the two call sites
share one implementation of the whitespace-collapse/truncate algorithm.

**`/session`'s huge-id guard is a deliberate addition beyond the brief's
literal text.** `_handle_session` reuses `_handle_delete`'s existing
`_DELETE_MAX_ID` (sqlite3's signed-64-bit `INTEGER` ceiling) guard: an
ASCII-digit argument past that ceiling is rejected with the ordinary
`No session #<id>.` reply instead of reaching `activate_conversation` and
raising an uncaught `OverflowError` when bound into the `UPDATE`. T2
(`docs/prompts/239-...md`) hit and fixed the identical bug for
`/delete #<id>`; `/session <id>` parses arguments the same way
(`isascii()`/`isdigit()`) and was exposed to the same class of crash, so the
guard was added and verified as a mutation-kill-style proof rather than left
as a known gap (see `## Stop` below) — it was not in the brief's own test
table.

**Test-first (EC-02), stated at the granularity that actually happened —
every one of the five tests in `tests/test_v1110_ses.py` was written and run
against the unmodified tree *before* `storage.py`/`bot.py` were touched, and
each did fail, but not every assertion inside every test body executed red,
and the failure mechanism differs by test:**

- `T-V1110-SES-01` (`test_t_v1110_ses_01_list_conversations_and_schema_6`):
  red with `AttributeError: module 'storage' has no attribute
  'list_conversations'` at the test's first call to that function. The two
  assertions above it in the test body (`SCHEMA_VERSION == 6`,
  `PRAGMA table_info(conversations)` has 4 columns) ran and passed on the
  unmodified tree — they are regression guards proving the schema really is
  untouched, not red-then-green assertions, and never ran red. Every
  assertion below the `list_conversations` call (title derivation, ordering,
  `limit`, `count_conversations`) never executed at all until the function
  existed.
- `T-V1110-SES-02` (`test_t_v1110_ses_02_activate_conversation_ownership`):
  red with `AttributeError: module 'storage' has no attribute
  'activate_conversation'` at the test's first call to that function.
  Nothing past that line (foreign id, missing id, the 50-alternating-switch
  loop) executed red.
- `T-V1110-SES-03` (`test_t_v1110_ses_03_sessions_table`): red on the very
  first `process(..., "/sessions")` call, but through an **indirect
  symptom**, not a direct assertion on the table body — `/sessions` was not
  a recognized command, so the message fell through the dispatch chain into
  the ordinary agent path, which called the scripted `FakeLLM` with no
  script queued, raising `AssertionError: FakeLLM script exhausted`. This is
  a genuine consequence of the missing dispatch entry (a real `/sessions`
  handler would never reach the LLM at all), but it is a symptom rather than
  a targeted assertion; none of the table-shape assertions (column headers,
  10-row cap, active marker, trailing-line count) or the 3-conversation
  no-trailing-line sub-case ever executed red.
- `T-V1110-SES-04` (`test_t_v1110_ses_04_session_switch_and_context`): red
  the same indirect way, on the first `process(..., "/session <id>")` call
  (`/session` also unrecognized, same `FakeLLM script exhausted` symptom).
  Everything written after that first call in the test body — the switch
  reply, the no-summary/no-`summaries`-row checks, the next-turn
  context-adoption check, the foreign-id and missing-id checks, the three
  usage-string sub-cases — never executed red. The huge-id sub-case (the
  `_DELETE_MAX_ID` guard reuse) is not a red-then-green case at all: the
  guard was written into `_handle_session`'s first version (same reasoning
  as T2's `/delete` guard), so the test passed immediately once written. Its
  ability to catch a real regression was verified separately and
  afterward — see `## Stop`.
- `T-V1110-SES-05` (`test_t_v1110_ses_05_new_reply_names_id`): red directly
  on its first assertion — `assert tg.sent == [(USER_ID, "New conversation
  started (#{first_id})."]` against the still-old literal
  `"New conversation started."` — the reason the test targets. The second
  `/new` sub-case (proving the id actually changes between calls) never
  executed red; it exists as an extra correctness check, not part of the
  red-before-green sequence.

**The five `NEW_CONVERSATION_REPLY` pin rewrites** (`bot.py:69`'s
definition and the four exact-string asserts in `tests/test_telegram.py:244`,
`tests/test_summary.py:190`/`:208`/`:244`, `tests/test_v1100_red_team.py:680`)
were rewritten proactively from T0's pin inventory, to
`.startswith("New conversation started (#")`, before `_handle_new`'s fix
landed — the standard PIN-01 procedure this run has followed since T1/T2, not
a red-then-green test in themselves. They were never run against the new
`/new` reply to watch them fail first; each was confirmed correct by running
the full suite (gate 3) after both the pin rewrite and the `_handle_new` fix
landed together.

## Constraints

Do not run gate 5 (`bot.py --selftest-live`), `devtools/mutation_check.py`,
`devtools/rag_eval.py` or `devtools/agent_eval.py` — gates 1-4 only. Do not
run `ruff format` (whole-file reformat risk), only `ruff check .`. Never
print, quote or commit either of this repo's two secret values
(`config.py:351`, `:379`). `--no-verify` never used.

## Acceptance

`T-V1110-SES-01`…`-05` all green (6 test functions, no parametrization).
`SCHEMA_VERSION` stays 6; `git diff -U0 storage.py | grep '^@@'` shows
exactly one hunk, a pure insertion (`@@ -664,0 +665,105 @@`) sitting entirely
after `start_new_conversation` — nowhere near `SCHEMA_VERSION` (`:21`) or
`_SCHEMA` (`:229-276`), so `_SCHEMA` is provably byte-unchanged, not merely
asserted. The five `NEW_CONVERSATION_REPLY` pins rewritten. README gains a
`## Sessions` section (after `## Commands`, before `## Observability`) with
a `/sessions` table sample and a `/session <id>` switch-reply sample, both
generated from a real run (`storage`/`tables`/`bot._render_last_activity`
against an in-memory-schema database) rather than hand-drawn, after an
advisor review caught two hand-drawn-sample mismatches (see `## Stop`).
Gates 1-4 green, each run verbatim: `uv sync --locked` (25 resolved, 23
checked), `uv run --locked ruff check .` (all checks passed — one `E501`
line-too-long on `list_conversations`'s multi-arg signature found and fixed
before this), `uv run --locked pytest` (`2333 passed, 1 skipped, 2 xfailed`
— 2328 baseline at T2's `09f8d8a` + 5 new this task), `uv run --locked
python bot.py --selftest` (`selftest: OK`).

## Stop

A cited `file:line` drifting more than 5 lines from the live tree, or a
cited mechanism being absent, stops the task for a report rather than a
guess. None triggered this task: every `file:line` the brief cited
(`storage.py:21`, `:229-276`/`:238-243`/`:245-246`/`:248-263`, `:632-643`,
`:646-662`, `:721-768`, `:1229-1245`; `bot.py:69`, `:926-982`, `:1048-1077`;
the four pin-rewrite test-file lines) matched the live tree exactly,
re-verified independently before writing any code.

**`T-V1110-SEC-01` does not belong to this task.** The spec's REQ-to-test
table (`docs/spec/spec-v1.11.0.md:1668`) lists `T-V1110-SEC-01` (a `<script>
&</script>` first-message case, spec line 539) against REQ-V1110-SES-02
alongside `T-V1110-SES-03`, which could look like a T3 test the brief
omitted. It is not: `tests/test_v1110_sec.py` itself is explicitly created
by **T5** (spec §14 T5's reading-map row: "`tests/test_v1110_{ing,err,sec}.py`
(created)") and finished by **T6** ("the rest of `T-V1110-SEC-01`" — spec
§14 T6 row); T3's own §14 row (line 1615) lists only `T-V1110-SES-01…05`.
`T-V1110-SEC-01` is a cross-cutting security test built incrementally across
several tasks' surfaces (T5's worker clauses, then T6's remainder), not a T3
deliverable — confirmed by grep, not assumed. The `<script>&</script>`
input is, incidentally, already safe through this task's own table path:
every `/sessions` cell (including `title`, `redact()`-ed) goes through
`send_pre`'s `_pre_text`, which HTML-escapes the whole fitted body before
wrapping it in `<pre>` — the same mechanism `/documents`' filenames already
relied on in T2 — but no dedicated test for it was added here, since that is
`T-V1110-SEC-01`'s job in a later task.

**One advisor review**, after gates 1-4 first went green and before any docs
were written, caught four things, all fixed before this commit: (1) the
README `## Sessions` sample table was hand-drawn and didn't match
`render_table`'s real output — the `#` column is content-width (1 unit for
single-digit ids, not the 4-unit cap drawn), and the hand-picked title `why
is the export cron failing on sundays only` collapses to 47 characters,
past the 40-character cut, so both the table cell and the switch-reply
sample needed the real `…`-truncated string, not the untruncated one;
replaced by running `storage.list_conversations`/`conversation_title` and
`tables.render_table` for real against a seeded in-memory-schema database
and pasting the output verbatim; (2) whether `T-V1110-SEC-01` was silently
dropped from this task's scope — checked against the spec's own task table
and confirmed it belongs to T5/T6, not T3 (above); (3) the `_SCHEMA`
byte-unchanged claim was asserted, not proven — `git diff -U0 storage.py |
grep '^@@'` run and quoted above; (4) the per-test EC-02 account in an
earlier draft of this file glossed over which individual assertions inside
each test body actually ran red versus which never executed — rewritten to
the assertion-level granularity above, matching this run's standing
requirement after two prior tasks' record corrections (T1's
`238-v1110-t1-record-correction.md`, T2's own corrected `## T2` report
section).

Separately, `tests/test_v1110_ses.py`'s huge-id sub-case originally used
`update_id=5 + hash(text) % 1000` for the usage-string loop — Python's
string hashing is salted per process by default, so a rerun (as
`devtools/mutation_check.py` does, once per mutation) would generate
different, non-reproducible `update_id` values run to run. Replaced with
`enumerate(..., start=5)` before this commit; not itself a correctness bug
(each `update_id` value only needs to be distinct within one test run), but
a reproducibility smell an advisor review flagged and this task fixed rather
than deferred.

A first commit attempt was rejected by the `pre-commit` hook
(`ruff-format-all`, `config/quality_gates.yaml`): one multi-line `assert` in
`tests/test_v1110_ses.py` (the `/session`-switch reply check, three lines)
didn't match `ruff format`'s canonical single-line form. This is a
whole-tree gate distinct from AGENTS.md's own gate 2 (`ruff check .`, which
this task's brief scoped to and which stayed green throughout); it is
mandatory on every commit (`--no-verify` forbidden) and was not bypassed.
Rather than running `ruff format` itself (forbidden by this task's own
brief, and the documented whole-file/whole-tree reformat risk), the one
flagged line was hand-edited to `ruff format --check .`'s suggested
single-line form; `ruff format --check .` then reported "127 files already
formatted" (no other file in the tree affected), `ruff check .` stayed
clean, and gates 1-4 were re-run and reconfirmed green before committing
again.
