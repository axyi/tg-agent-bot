# tg-agent-bot v1.11.0 — Telegram tables, sessions, the `/model` menu and a background ingest worker

Seven bundled changes to the bot's Telegram surface: an HTML `<pre>` table
path for five read-only commands (agent replies stay byte-identical plain
text), `/stats`/`/documents` as tables and `/delete #<id>`, session
list/switch (`/sessions`, `/session <id>`, no schema change),
`callback_query` handling behind a two-step `/model` provider→model menu,
and document ingest caps raised to the Bot API's 20 MB ceiling behind a new
background `IngestWorker` with `/cancel`. Spec:
`docs/spec/spec-v1.11.0.md`. `<base>` = `295b01f` (the commit the spec's
`file:line` citations describe); `git diff --name-only 295b01f HEAD` at T0
touches only `docs/handoff-v1.11.0.md`, `docs/llm-usage.md`,
`docs/prompts/235-v1110-spec-authoring.md` and `docs/spec/spec-v1.11.0.md`
— no source, test or config file differs from `295b01f`, so every spec
`file:line` citation holds unchanged. Spec `sha256`:
`98a4af264196138b1b3ee01d16e63fa3a052fba3e7a1891e7dfed5037de5b4a5`.

This file is filled progressively: T0 (this skeleton), T1 (tables.py +
HTML pre-text plumbing), T2 (/stats, /documents tables, /delete #id), T3
(sessions), T4 (/model menu, callback_query), T5 (IngestWorker, raised
caps, /cancel), T6 (commands registration, bench waiver, pins), T7
(mutation entries, review, gates 1-8), T8 (version bump, evidence commit,
tag). Sections not yet reached read "not reached: T\<n\>".

## T0 — preconditions, gates 1-5, measurements, pin inventory

`<base>` = `295b01f`. Spec `sha256` as above. `Status: ready for \`go\`` —
present once (`grep -c`).

### Preconditions (EC-05)

- `git rev-parse HEAD` = `c29d53384b4d0f854a782a39fd5d4c08c64de1da`
  (`git describe --tags` = `v1.10.4-6-gc29d533`) — six commits ahead of
  `295b01f`, all four docs-only (the spec's own authoring pipeline: draft,
  3 cross-review rounds, handoff) plus two more (a ledger-row correction,
  the handoff+usage-row commit) — matches `docs/handoff-v1.11.0.md`'s
  stated precondition ("tree at `8695b52` or later on `main`"), which
  supersedes EC-05's literal `295b01f`-exact wording for this detail; this
  is expected drift from the spec-authoring process itself, not a spec
  ambiguity — recorded here, not treated as a repair cycle.
- `git status --porcelain` — empty (even cleaner than EC-05's expected
  `?? .README.md.swp`; no untracked file present at all).
- `git stash list` — empty, recorded.
- `test -f .env` — exit 0.
- `docs/prompts/235-v1110-spec-authoring.md` and `docs/llm-usage.md` row
  145 present in `HEAD` — confirmed (row 146 is the spec-authoring row
  itself; row 145 is the prior ledger-row correction).
- `git diff --exit-code HEAD -- docs/spec/spec-v1.11.0.md` — exit 0
  (committed, unmodified).
- **LM Studio address**: `go` text named `192.168.0.145`. Probed
  `curl -sS -m 3 http://192.168.0.145:1234/v1/models` before `go` was
  issued — reachable, catalogue includes the project's pinned
  `qwen/qwen3.8-27b`. Applied the one permitted `sed -i` to `.env`'s
  `LMSTUDIO_BASE_URL` line (value never printed; confirmed only by
  `grep -c` exit status matching the expected pattern
  `LMSTUDIO_BASE_URL=http://192.168.0.145:1234/v1` — `/v1` suffix added to
  match `config.py:359`'s default shape, since the bare `host:port` the
  operator supplied would not have matched the OpenAI-compatible base-url
  convention the client expects).
- **Override precondition (MOD-05)**: the one permitted programmatic
  `data/` read —
  `SELECT COUNT(*) FROM bot_state WHERE key = 'provider_override' OR key
  LIKE 'model_override:%'` — printed `0`. No blocked run.

### Gates 1-5

- Gate 1 (`uv sync --locked`): resolved 25 packages, checked 23 — exit 0.
- Gate 2 (`ruff check .`): all checks passed — exit 0.
- Gate 3 (`pytest`): exit 0, 100% collected/run, no failures.
- Gate 4 (`bot.py --selftest`): `selftest: OK`.
- Gate 5 (`bot.py --selftest-live`): `OK config`, `OK db`,
  `OK docker (29.8.1)`, `OK telegram`, `OK embeddings`, `OK openrouter`;
  `SKIP lmstudio (no route uses it)` — disclosed, non-blocking (AGENTS.md's
  gate-5 rule: a provider no route names SKIPs cleanly). Exit 0.

### Measurements

- Test-collection floor:
  `uv run --locked pytest --collect-only -q -o addopts="" | grep -c '::'`
  = **2311** (matches `AGENTS.md:161` / `tests/test_v190_agents.py:146-149`).
- Baseline node-id list written to
  `docs/spec/task-briefs/v1110-T0-nodeids.txt` (2311 lines, sorted).
- `len(devtools.mutation_check.MUTATIONS)` = **144**.
- The v190 `find` string
  (`    if isinstance(file_size, int) and file_size > DOCUMENT_MAX_BYTES:`,
  `v190-size-precheck-disabled`, `devtools/mutation_check.py:1218`) occurs
  **exactly once** in `bot.py` (`grep -cF`).

### Pin inventory (PIN-01)

Delegated (one general-purpose subagent, brief `v1110-T0.md`, EC-04),
landed at `docs/spec/task-briefs/v1110-T0-pin-inventory.md` (129 lines,
built by grepping the live tree at `c29d533`, not copied from the spec).
55 pin-table rows (source-definition + test-assertion + README-table
sites) plus one explanatory note on STA-01's "43 pins" figure (12 grouped
rows covering 24 individually located `/stats` assertion sites plus the
renderer; the remainder of the 43 not itemised one-by-one, disclosed
rather than padded), 4 measurement rows (cited, not re-derived), 2 rename
mapping entries.

**Drift**: none exceeding 5 lines. One 1-line drift disclosed:
`tests/test_v15_standards.py` cited `:1824`, actual
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` is at
`:1823` — recorded per EC-02, not a repair cycle.

**Amendments disclosed beyond the brief's starting list** (PIN-01: not a
repair cycle, no budget consumed):
1. A third `report_path` pin site, `tests/test_v190_agents.py:290-303`
   (`test_t_v1100_ec_01_quality_gates_yaml_repoints_report_path`) — same
   T6/VER-03 repoint, function name deliberately kept stable (not added
   to the rename mapping).
2. `README.md:828`/`:831` and the `:511-516` prose sentence — the
   *unchanged-unless-the-ceiling-moves* numbers (`10,485,760`, `300 s`)
   inside T5's block, alongside the two the spec names (`500,000`,
   `500 pages`), flagged so a careless table edit doesn't clobber them.
3. Four source-definition sites (`bot.py:1132` `_render_stats`, `:221`
   `allowed_updates` payload, `:1381` typing-ceiling call, `:1483`
   `Your documents (N):`) added so the inventory names both source and
   test for each literal.

Independently reconfirmed the measurements during this pass: `len(MUTATIONS)
== 144`; the v190 `find` string exactly once, at `bot.py:1355`; node-id
baseline 2311 lines — all match T0's own direct measurements above.

## T1 — the outbound table path

Delegated (brief `docs/spec/task-briefs/v1110-T1.md`, EC-04).

**EC-02 correction** (disclosed by the subagent's own hand-back, not by a
later audit): the task was **not** run fully test-first as originally
claimed. `tables.py` was written *before* `tests/test_v1110_out.py`, so
`T-V1110-OUT-01` (`render_table`) never went red for the right reason — it
ran against the already-built implementation and only caught a bug in the
test's own rule-line assertion (fixed; not a production-code defect). The
two fatal-401 negative cases added to `T-V1110-OUT-05`/`-08` (see the
mid-task correction below) were written *after* the `exc.fatal` fix
landed and never ran red at all. What genuinely went red for the right
reason first — `AttributeError` on the not-yet-existing
`bot.send_pre`/`edit_pre`, the `tables` module or
`FakeTelegram.send_message_html` — before its own production code landed:
`T-V1110-OUT-02`, `-03`, `-04`, `-05` (minus the 401 case), `-06`, `-07`,
`-08` (minus the 401 case). This is an EC-02 process deviation on one test
and two sub-cases, not a correctness defect — all eight tests are green
and match the spec's assertions; recorded accurately here rather than left
as the original overstated claim in this section and in
`docs/prompts/237-v1110-t1-table-path.md`'s `## Goal` and
`docs/llm-usage.md` row 148 (both corrected alongside this section, same
pass, docs-only).

**Built**: `tables.py` (new, repository root) — `utf16_length` (moved
from `bot.py`, `bot.py` re-imports it so `bot.utf16_length` keeps its name
and its one existing caller, `bot.py:909`), `render_table` (cells
`str()`-ed with `None` -> `n/a`; alignment `"r"` when `align` says so or
every non-`n/a` cell is `int`/`float`, else `"l"`; astral-safe truncation
to `max_width` reserving one UTF-16 unit for `…`; header + ASCII `-` rule
line + rows, joined by two spaces, no trailing newline; `ValueError` over
the 72-unit ceiling; returns raw, unescaped text), `fit_lines` (whole
lines dropped from the end plus a final `… N more` line, the `_fit`
pattern over lines rather than characters, never a hard slice inside a
line). `bot.py` gains `_pre_text` (redact -> fit -> escape -> wrap, in
that order, returning both the HTML `text` and the fitted plain `fitted`
body), `send_pre`/`edit_pre` (the only production callers of the two new
`TelegramClient` methods `send_message_html`/`edit_message_html`, payload
exactly `{chat_id, text, parse_mode: "HTML"}` / `{chat_id, message_id,
text, parse_mode: "HTML"}` plus `reply_markup` when given), and the
one-time plain-text fallback on a non-fatal table-path failure (a fatal
401/404 skips the fallback entirely and returns `None` directly — see the
mid-task correction below). `reply_parts`/`_send`/`TelegramClient.send_message`
are byte-unchanged; `send_message`'s signature still takes only
`{self, chat_id, text}`. `tests/fakes.py`'s `FakeTelegram` grows
`sent_payloads`, `edited_payloads`, `callback_answers`, `commands_set` and
`fail_html_with` (fake recorders only for `answer_callback_query`/
`set_my_commands` — T4/T6 implement the production callers); `sent` still
holds `(chat_id, text)` for both send methods, unchanged for the hundreds
of existing tests that read it.

**Mid-task correction (advisor review)**: the first implementation of
`send_pre`/`edit_pre` caught every `TelegramError` from the HTML attempt
uniformly and always tried the plain fallback once. An advisor review
before declaring done flagged that REQ-V1110-OUT-04's parenthetical — "the
existing 401/404 fatal classification stands unchanged" — is a real
constraint, not a reassurance: a fatal error (a bad token or an
unreachable chat) is not a payload problem a differently-shaped resend
could fix, so the fallback must not fire for it. Fixed before the gate run
recorded below: both helpers now check `exc.fatal` first and return `None`
immediately (logged, same pattern as `_send`) without a second request.
Two new negative cases were added, one in `T-V1110-OUT-05` and one in
`T-V1110-OUT-08`: a 401 through the real `TelegramClient` + `MockTransport`
produces exactly one request and a `None` result.

**Fallback scope note (for T7's reviewer)**: `TelegramError` carries no
status code, only `.fatal`/`.retry_after`/`.transport`. So the one-time
plain-text fallback fires on *any* non-fatal `TelegramError` from the HTML
attempt — not literally only a 400; a 500, or an exhausted-retries 429 or
transport error, would also fall back once. This is the correct reading of
OUT-04's rule (a payload-shaped resend is worth trying whenever the failure
isn't a fatal token/chat problem) and is not a change to
`TelegramClient.call`'s own 401/404/429 classification.

**Hook episode**: the first commit attempt failed pre-commit's
`ruff-format-all` (a `send_pre` signature wrapped across 3 lines where
ruff wants 1); `ruff format` itself was denied by the sandbox's
destructive-action classifier (this repo's `feedback_ruff_format_whole_file_risk`
caution — a whole-file reformat is a real risk to review), so the
signature was collapsed by hand and verified with `ruff format --check
--diff` before re-committing. No `--no-verify` used; the failed attempt
produced no commit, so nothing needed reverting.

**Tests**: `T-V1110-OUT-01`..`-08` in `tests/test_v1110_out.py`, all
green — `-01` (`render_table` properties over 200 generated row sets
against an independent reference implementation, plus explicit
truncation/`ValueError`/raw-text edge cases), `-02` (payload shape and
escape through the real client), `-03` (redact-before-fit/escape,
negative, including the sentinel-secret-shifts-the-retained-line-boundary
case), `-04` (`fit_lines` at the 4096-unit boundary, built with `&` so the
raw entity-parsed length — not the escaped-HTML-string length — governs
the fit), `-05`/`-08` (the one-time plain fallback on 400, the fatal-401
skip, two-400s-returns-`None`, for send and edit respectively), `-06`
(the agent-reply path unchanged, negative — including
`test_t_v1100_out_04_send_payload_is_exactly_chat_id_and_text`,
`test_t_v1100_out_04_send_message_source_has_no_parse_mode_or_entities`
and `test_t_v1100_out_05_markdownv2_specials_delivered_verbatim` imported
from `tests/test_v1100_sanitization.py` and called directly, matching
`tests/test_v1103_gates.py`'s own precedent for that pattern), `-07`
(`FakeTelegram` growth). `tests/test_v1100_sanitization.py:293-323`
untouched.

**Drift (EC-02)**: one disclosed, ≤5 lines. The brief cites
`tests/test_v1100_sanitization.py:293-323` for the `T-V1100-OUT-04`
section; the second function's last assert is actually at `:324` (a
1-line overshoot) — used the actual location, no repair cycle. Every
other cited range in the brief's reading map matched the live tree
exactly, including `_fit` at `bot.py:1190-1197`. Process note: the
brief asked for this `cited → actual` line in the **commit body** too,
not only here — commit `239bd13`'s body does not carry it; recorded here
instead as the durable record, no amendment made (this project creates a
new commit rather than rewriting one, and a commit-message content gap
that doesn't affect correctness doesn't warrant a follow-up commit of its
own).

**Map vs actual**: read beyond the brief's stated map to understand the
surrounding contract before writing the fallback and the `/status`/
`/summary` assertions: `bot.py:111-140` (`TelegramError`'s fields, no
`status` attribute — settled how a 400 vs. a fatal 401/404 is
distinguished), `bot.py:813-940` (`process_update`'s command dispatch, for
`T-V1110-OUT-06`'s `/status`/`/summary` calls), `bot.py:1051-1076`
(`_handle_summary`, to confirm an empty conversation short-circuits
without an LLM call), `bot.py:1100-1200` (`_render_stats`/`_fit`, the
pattern `fit_lines` follows), `config.py:190-260` (`register_secret`/
`redact`/`RedactingFormatter`, `REDACTION`/`MIN_SECRET_LENGTH`),
`devtools/checks.py` and `config/quality_gates.yaml` (confirmed
`lint-docs`'s `report_path`/`delegation_record` gate still points at
`report-v1.10.4.md` this release, not this file, until T6), spec sec.7/
sec.11/sec.14/Appendix A (CBQ-03's three-method list, the T1 reading-map
row, the traceability table), `tests/test_v1100_sanitization.py:1-260`
and `tests/conftest.py` (existing `make_cfg`/`update`/`process` helper
conventions and fixtures).

- T1 | delegated: yes | to: general-purpose subagent (claude-sonnet-5) | brief: docs/spec/task-briefs/v1110-T1.md | map vs actual: matches the reading map, plus one disclosed 1-line EC-02 drift (`tests/test_v1100_sanitization.py:293-323`'s cited range, actual last assert `:324`) and the additional reads listed above (`bot.py:111-140`, `:813-940`, `:1051-1076`, `:1100-1200`; `config.py:190-260`; `devtools/checks.py`; `config/quality_gates.yaml`; spec sec.7/11/14/Appendix A; `tests/test_v1100_sanitization.py:1-260`; `tests/conftest.py`)

**Gates 1-4** (gate 5/6/7/8 intentionally not run this task, per the
brief): `uv sync --locked` — 25 resolved, 23 checked, exit 0. `uv run
--locked ruff check .` — all checks passed, exit 0. `uv run --locked
pytest` — 2322 collected (2311 baseline + 8 new `test_v1110_out.py`
functions + 3 pytest-recollected imported `test_*` functions, the same
double-collection pattern `tests/test_v1103_gates.py` already uses), 0
failed, exit 0. `uv run --locked python bot.py --selftest` — `selftest:
OK`, exit 0 (a pre-existing, unrelated warning — `'_SelftestTelegram'
object has no attribute 'call'` — was confirmed present before this
task's changes too, via `git stash`).

## T2 — /stats and /documents as tables, /delete #id

Delegated (brief `docs/spec/task-briefs/v1110-T2.md`, EC-04).

**EC-02, stated at the granularity that actually happened**: both new test
files (`tests/test_v1110_sta.py`, `tests/test_v1110_doc.py`) were written
in full and run before any `bot.py` change. `T-V1110-STA-01`, `-02` and
`T-V1110-DOC-01` share a helper that asserts the table path first
(`parse_mode == "HTML"`); all three went red on that same first assertion
(`assert None == 'HTML'` — `/stats` and `/documents` still used the plain
`_send`/`reply_parts` path), so the label-order, wrap-width, fit-marker,
size-formatting and truncation assertions later in those same test bodies
never themselves executed red before the fix — the test *file* ran red for
the right reason, not every assertion inside it individually.
`T-V1110-STA-03` went red on a missing README label. `T-V1110-DOC-03` went
red on the still-old `DELETE_USAGE_REPLY` text, so its `#<id>` assertions
never ran on their own before the fix either. `T-V1110-DOC-04`'s three
parametrized cases: the DOCX-bounds and PDF-pages variants went red on
`AttributeError` (the two new reply constants did not exist yet); the
extracted-text variant went red on an `AssertionError` (the old "500,000"
wording, not "2,000,000"). `T-V1110-DOC-02` (`DOCUMENTS_EMPTY_REPLY` on the
plain path) **never ran red at all** — that behaviour is unchanged by this
task; it is a regression guard, not a red-then-green test, and is recorded
as such rather than folded into the test-first claim.

**Built**: `_render_stats` (`bot.py`) now builds a three-column
`metric`/`this conv`/`all time` table via `tables.render_table` (`max_width`
`[22, 16, 16]`) over the ten paired rows the spec names, in order, followed
by a blank line and the four single-value lines (`Top tools: …`,
`Last turn: …`, `Errors: …`, `Summaries: …` — the label on the first
shortened from the old "Top tools by output tokens (all time): " to match
the spec's own literal bullet text at `spec-v1.11.0.md:410`, an
interpretive reading since three of the spec's four shorthand labels
already matched the pre-existing code verbatim and only this one didn't;
disclosed here as a judgment call). New `_wrap_line`/`_break_point` wrap
(never truncate) a single-value line past `tables.MAX_TABLE_LINE_UNITS`
(72): continuation lines indented by two spaces, every line UTF-16-safe
and within budget, breaking at the last space in budget when one exists.
`tables.fit_lines` (not the old `_fit`) applies the `STATS_MAX_CHARS`
(3500) cap over the assembled line list, whole lines dropped from the end,
`… N more` appended. Cell-content semantics are unchanged: `_cell` (→
`n/a`), `_render_cost` (→ `n/a (no pricing)`), `_render_share` (the percent
form) all reused verbatim; only their caller changed from string
concatenation to table cells. `_handle_documents` now builds a
`#`/`file`/`type`/`size`/`chunks`/`pages`/`added` table (`max_width`
`[3, 24, 4, 8, 6, 5, 10]`, summing with six two-space separators to exactly
72 units, the hard ceiling) via a new `_render_size` helper (decimal KB/MB,
one decimal, `0.0 KB` for zero, matching neither IEC 1,048,576 nor any
other binary unit); the body's first line is
`Your documents (N of 20):` (`documents.DOCUMENT_LIMIT`, already
imported); the empty case is unchanged, still the plain `DOCUMENTS_EMPTY_REPLY`
path. `_render_document_line` removed — grepped first, its one caller was
this handler, confirmed no other caller exists anywhere in the tree.
`_handle_delete` gained the `#<id>` form (`argument.startswith("#")`, then
`id_part.isascii() and id_part.isdigit()` before `int()` — see the
advisor-review fix below): `storage.delete_document`'s own
`user_id`-scoped predicate is the *only* ownership check (per the spec,
never a second one), its `True`/`False` return distinguishing nothing
between "an id the caller doesn't own" and "no such id at all" — both
render `No document named #<id>.`; a `#` followed by non-digits gets the
same shape with the raw argument echoed. `DELETE_USAGE_REPLY` becomes
`Usage: /delete <filename> | /delete #<id>`. Three refusal strings split
(the `except` clause order and exception classes unchanged):
`DOC_DOCX_BOUNDS_REPLY` and `DOC_PDF_PAGES_REPLY` are new constants;
`DOC_TEXT_TOO_LARGE_REPLY`'s number moves to "2,000,000 characters" —
forward-referencing T5's constant rename by design, per the spec's own
task split (§14 T2/T5 rows), not itself a defect. `_fit`/`_pair` removed
as orphans once their one caller (the old flat `/stats` body) was gone —
confirmed via grep before deletion.

**Tests**: `T-V1110-STA-01`…`-03` in `tests/test_v1110_sta.py` (3
functions), `T-V1110-DOC-01`…`-04` in `tests/test_v1110_doc.py` (6
collected items — `-04` parametrized ×3), all green; see the EC-02 note
above for which assertions genuinely ran red first. Eight pre-existing
`/stats`-rendering test functions rewritten from whole-line equality to
presence/contiguity (REQ-V1110-PIN-01), against T0's pin inventory:
`tests/test_observability.py`'s `stats_text` helper (now passes a real
`FakeTelegram` — the file's default `RecordingTelegram` has no
`send_message_html` — and strips/unescapes the `<pre>` wrapper) plus
`test_obs07_stats_layout`, `_reports_no_pricing`,
`_basis_is_mixed_when_the_rows_disagree`, `_on_an_empty_database`,
`_separates_this_conversation_from_all_time`,
`_reports_cached_and_reasoning_when_present`, and
`_drops_whole_lines_before_it_cuts_one`; `tests/test_v160_observability.py`'s
`test_stats_gains_two_lines_appended`; `tests/test_pricing.py`'s
`test_prc03_every_basis_form_is_stored_and_rendered`. T0's inventory also
named two `/status`-line sites (`test_obs07_status_carries_the_token_line`,
`test_obs07_status_token_line_without_a_conversation`) — checked and left
unchanged, `/status` is untouched by this task. This is 8 functions, not
"43 pins" — the spec's 43 count is individual assertion sites (T0's own
inventory located 24 of those, grouped into the rows above); every located
site was rewritten.

**Amendments beyond T0's pin inventory** (the brief's own staging list
also omitted the five test files these touch — `test_observability.py`,
`test_pricing.py`, `test_v160_observability.py`, `test_v190_commands.py`,
`test_v1100_sanitization.py` — necessary per the reading map and
acceptance criteria regardless):

- `tests/test_v190_commands.py:593-594`'s two `"a.txt — txt, 2 chunks,
  …"`/`"b.pdf — pdf, 4 chunks, 3 pages, …"` line-format asserts — the old
  `_render_document_line` shape, gone with the table — rewritten to
  presence checks on the table's cell content instead.
- `tests/test_v190_commands.py`'s row_5b test
  (`test_t_v190_err_01_row_5b_variants_map_to_the_same_reply`): needed a
  reply-mapping split for REQ-V1110-DOC-03, but renaming the function or
  adding a second parametrize column would have silently dropped three
  node ids from T0's committed baseline list
  (`docs/spec/task-briefs/v1110-T0-nodeids.txt`, reconciled by T8's
  `comm -23` check — not this task's, but a downstream requirement this
  task must not break). Kept the original name and the original
  single-`exc` parametrize (identical `[exc0]`/`[exc1]`/`[exc2]` ids), with
  a `type(exc) -> bot attribute name` lookup dict instead — the same
  name-preserved-despite-content-change pattern
  `test_t_v1100_ec_01_quality_gates_yaml_repoints_report_path` already
  uses elsewhere in the same file.
- `tests/test_v1100_sanitization.py::test_t_v1100_out_03_split_message_used_only_inside_reply_parts`
  asserted `reply_parts(` appears at 5+ call sites outside its own `def`.
  Moving `/stats` and `/documents` off `reply_parts` onto the table path
  drops that to 3 (`/status`, the agent-turn reply, `/summary`) — the
  direct, foreseeable consequence of REQ-V1110-STA-01/DOC-01, not a defect.
  Floor lowered to 3, with a comment naming which three call sites remain
  and why the number moved.

**Advisor-review fixes** (all applied in this same prompt, before the
commit, none discovered by a later audit):

1. A long `cost_basis` now truncates at the "cost basis" column's 16-unit
   `max_width` like any other cell, so `test_prc03_every_basis_form_is_stored_and_rendered`'s
   equality assertion needed the same truncation (`tables._truncate_cell`,
   reused rather than reimplemented) applied to its own expected value —
   "content preserved verbatim" (REQ-V13-OBS-07) still holds as *cell
   content*, but a value wider than the column now truncates like any
   other long cell, which is new, disclosed behaviour, not a bug.
   `test_obs07_stats_drops_whole_lines_before_it_cuts_one`'s premise (a
   4000-character `cost_basis` forcing the whole-body overflow) no longer
   holds for the same reason — rewritten to a presence/no-crash check with
   a docstring noting `T-V1110-STA-02` (a 5000-character `top tools`
   value) owns the whole-line-drop overflow case now.
2. `/delete #<id>` had two unguarded crash paths: a non-ASCII decimal
   digit (`"²".isdigit()` is `True` but `int("²")` raises `ValueError`,
   since Python's `int()` only accepts decimal-category digits, and
   U+00B2 SUPERSCRIPT TWO is a digit but not decimal) and an id past
   sqlite3's signed 64-bit `INTEGER` ceiling (`OverflowError` from the
   underlying C binding). Fixed with `id_part.isascii() and
   id_part.isdigit()` and a `_DELETE_MAX_ID = 2**63 - 1` bound, both
   short-circuiting to the ordinary "not found" reply rather than
   crashing. Both additions to `T-V1110-DOC-03` were confirmed to
   actually catch the regression, not just exercise a code path: each
   guard was temporarily reverted, the test watched fail
   (`ValueError`/`OverflowError` respectively, both uncaught, propagating
   out of `_handle_delete`), then the guard restored and the full suite
   re-confirmed green.
3. Grepped `devtools/mutation_check.py`'s `MUTATIONS` list for any `find`
   string touching `_fit`, `_pair`, `_render_document_line`,
   `_handle_delete`, `DELETE_USAGE_REPLY`, the two refusal `except`
   clauses, the `/stats` dispatch line, or `_render_stats`'s body — none
   found (18 entries touch `bot.py` at all; none overlap this task's
   edits). Gate 6 itself was not run (out of scope), so this is a static
   check, not a proof, but it rules out a silent gate-6 break.

**Drift (EC-02)**: two disclosed, both well under the 5-line stop
threshold, no repair cycle. `STATS_MAX_CHARS` cited `bot.py:58`, actual
`:61`. `DELETE_USAGE_REPLY`/`DOCUMENTS_EMPTY_REPLY` cited `bot.py:96-97`,
actual `:99-100`. Every other cited `file:line` in the brief's reading map
matched exactly, including `_render_stats` (`:1154`), `_render_errors_line`/
`_render_summaries_line` (`:1193`/`:1204`), `_fit` (`:1212`, before
removal), `_cell`/`_render_cost`/`_render_share` (`:1227`/`:1231`/`:1237`),
`_render_top_tools`/`_render_last_turn` (`:1241`/`:1248`),
`_render_document_line` (`:1493`, before removal), `_handle_documents`
(`:1500`), `_handle_delete` (`:1509`), the refusal-wording block
(`:1451-1461`), `storage.list_documents`/`document_id_for`/`delete_document`,
`documents.DOCUMENT_LIMIT` (`:381`), and `README.md:106-140`.

- T2 | delegated: yes | to: general-purpose subagent (claude-sonnet-5) |
  brief: docs/spec/task-briefs/v1110-T2.md | map vs actual: matches the
  reading map, two disclosed drifts ≤3 lines each (`STATS_MAX_CHARS`,
  `DELETE_USAGE_REPLY`/`DOCUMENTS_EMPTY_REPLY`), plus the additional test
  files listed above under "amendments beyond T0's pin inventory"

**Gates 1-4** (gate 5/6/7/8 intentionally not run this task, per the
brief): `uv sync --locked` — 25 resolved, 23 checked, exit 0. `uv run
--locked ruff check .` — all checks passed, exit 0. `uv run --locked
pytest` — 2331 collected (2322 at T1's `2b2dd4e` + 9 new this task: 3 in
`tests/test_v1110_sta.py`, 6 in `tests/test_v1110_doc.py`), 0 failed, exit
0 (pytest's own final summary line does not render under this
environment's non-TTY `pytest-xdist -n auto`, a pre-existing quirk unrelated
to this task — the 2331/0-failed figures come from `--collect-only`
against both trees plus the full run's exit code, not from a printed
summary). `uv run --locked python bot.py --selftest` — `selftest: OK`,
exit 0.

## T3 — not reached

## T4 — not reached

## T5 — not reached

## T6 — not reached

## T7 — not reached

## T8 — not reached

## Operator inputs

- **Run configuration (EC-05), source `.env`** (operator-prepared ahead of
  `go`, opened only by the one permitted `sed -i` for `LMSTUDIO_BASE_URL`
  and never otherwise read/printed): `LMSTUDIO_BASE_URL` set to
  `http://192.168.0.145:1234/v1` at T0; all other `.env` values unchanged
  from v1.10.4.
- **`go` text**: `go docs/spec/spec-v1.11.0.md — LM Studio at
  http://192.168.0.145:1234`.

## Gate-8 attempt log

| task | attempt | exit | outcome |
| --- | --- | --- | --- |
| not reached | | | |

## `docs/reports/tg-post-v1.11.0.md`

Not written yet — written at T8 (or at the stop route, if triggered).

## Ledger row (paste into `economics.md`)

Not reached — filled at T8.
