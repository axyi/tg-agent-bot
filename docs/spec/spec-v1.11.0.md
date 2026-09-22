# spec-v1.11.0 — the Telegram surface: monospace tables, sessions, inline keyboards, a `/model` menu and large-document ingest off the polling loop

Status: ready for `go`.
Base: `v1.10.4` (tagged locally 2026-09-19, `6532d4c`; `main` at `295b01f`,
tree clean except an untracked vim swap file `.README.md.swp`, ignored;
tag not pushed). Nothing about v1.10.4 is reopened.
Target version: **1.11.0** — MINOR by `README.md:889-891` (new commands
`/sessions`, `/session`, `/cancel`, `/help`, `/start`; new environment
variables `LMSTUDIO_MODELS`, `OPENROUTER_MODELS`; no schema migration —
`SCHEMA_VERSION` stays 6). `pyproject.toml` `1.10.4` → `1.11.0`; annotated
tag `v1.11.0`, **no push**.

One subject: the bot's Telegram surface, which since v0 has been plain
text with eight commands and no keyboard. This release (1) adds one
HTML-`<pre>` **table path** for five read-only commands while the agent-reply
path stays byte-for-byte plain (§3); (2) renders `/stats` and `/documents`
as tables and lets `/delete` take an id (§4, §5); (3) lists and switches
sessions with no schema change (§6); (4) opens `callback_query` updates
and inline keyboards, narrowly (§7); (5) turns `/model` into a two-step
provider → model menu backed by env allowlists, with a text form kept
(§8); (6) raises the document caps to the Bot API ceiling and moves ingest
onto one worker thread with a per-user slot and `/cancel` (§9); (7) adds
`setMyCommands`, `/help` and `/start` as a lab-proposed extra (§10). This
is a DELTA specification on the implemented v1.10.4 state: earlier
mechanisms are referenced by REQ id and `file:line`, never restated. The
line numbers cite `295b01f`; EC-02's drift rule applies.

Requirement ids group by subject (`OUT` the outbound table path, `STA`
`/stats`, `DOC` `/documents` and `/delete`, `SES` sessions, `CBQ` callback
queries and inline keyboards, `MOD` the `/model` menu and the model
override, `ING` large-document ingest, `EXT` the lab-proposed extras,
`PIN` the frozen-pin inventory and rewrites, `MUT` mutation entries, `ERR`
the error matrix, `SEC` security) and by release mechanics (`EC` execution
contract, `REV` review, gates and the stop route, `VER` version, report
and ledger, `NG` non-goals — declared here, unlike `spec-v1.10.0.md:27-31`,
which used it undeclared). Ids are `REQ-V1110-<GROUP>-NN`, tagged MUST or
NON-GOAL; tests `T-V1110-<GROUP>-NN` in `tests/test_v1110_<group>.py`, one
file per group; mutations `v1110-<slug>` (exactly eight); tasks T0…T8
(nine tasks); task-brief files `docs/spec/task-briefs/v1110-T<n>.md`. The
authoring prompt is `docs/prompts/235-v1110-spec-authoring.md` (written
by the lab); the run's prompts start at **236**; `docs/llm-usage.md` rows
for the run start at **146**. Executor model **`claude-sonnet-5`**;
reviewer the project's pinned `code-reviewer` agent
(`.claude/agents/code-reviewer.md:4`, `model: sonnet`) in a clean
context. This file states forty-four MUST requirements, fourteen
`NON-GOAL` rows, forty-nine test ids, eight mutation ids, seventeen ERR-01
rows and thirteen Gherkin scenarios; Appendix A is in bijection with the
MUST ids.

---

## 1. Execution contract

**REQ-V1110-EC-01 (MUST) — boundary, dependencies, network, repair
budget.** Section 1 of every earlier spec applies unchanged, with these
adjustments:

- **the executor** is `claude-sonnet-5` (`standards/workflow.md:47`:
  execution against a finished spec runs on the smallest model that passes
  acceptance), orchestrator effort high; the reviewer is the pinned
  `code-reviewer` (`sonnet`), never the writing context (REV-01);
- **zero new dependencies**: `pyproject.toml:6-14` and `:16-21` do not
  change by one character; `uv.lock` changes only in the project's own
  entry (VER-01). Everything this release needs is stdlib — `html`,
  `threading`, `queue`, `dataclasses` — and `httpx`, already pinned. The
  course rule stands: the lecturer wants the project's own tests;
- **the network this release needs is exhaustive**: gate 5 (`bot.py
  --selftest-live`) at T0 and T7 (and T8, §12), gate 7 (`devtools/rag_eval.py`)
  once at T7, gate 8 (`devtools/agent_eval.py`) once at T7, the `uv lock`
  of VER-01. No other live call; no offline test reaches a socket
  (`tests/conftest.py:10-28`, `no_network`/`no_dns`, unchanged). The Bot API
  facts this spec relies on were fetched by the lab on 2026-09-22 and are
  quoted where used (§3, §7, §9, §10); the run does not re-fetch them;
- **the filesystem boundary**: `.env` is never read or printed by any
  task — presence checks are by exit status only (`test -f .env`); the
  one `LMSTUDIO_BASE_URL` write EC-05 permits is a one-line `sed` whose
  input and output are never printed. Nothing under `data/` is opened by
  the executor, with **one programmatic exception** stated in EC-05
  (the override-key count, read through `storage.connect_readonly` and
  printed as a single integer). `bot.db`, `sandbox/`, `exec_audit.jsonl`
  and `docs/assets/bench/*.json` (the frozen bench artefacts) are never
  opened or rewritten. Secret values are never printed — key **names**
  only (EC-06). Rerank stays on OpenRouter (`LLM_RERANK_MODEL`, untouched);
- **the repair budget is ≤ 3 repair cycles per task**; a cycle is one
  failing gate → one fix commit (its own prompt file, its own commit,
  named `fix:` and referencing the task's prompt in the body); exhausted →
  the stop route (REV-03). A repair cycle re-runs the failing gate and
  every gate before it; a source change after gate 8 has run re-runs gate
  8 once (REV-02). `T-V1110-VER-02` pins the dependency clause against the
  `v1.10.4` tag blob.

**REQ-V1110-EC-02 (MUST) — test-first; citations; the disclosed-amendment
rule for drift.** Write the group's tests (§11), watch them fail for the
right reason, then implement in §14's order. Every `MUST` in §§1–13 has a
named test, a negative test, a Gherkin scenario in Appendix B, or a
recorded artefact; Appendix A is the map and is complete. Every
`file:line` in this spec cites `295b01f`; **a drift of ≤ 5 lines between a
cited range and the mechanism it names is a disclosed amendment** — the
task's commit body and the report's per-task bullet record `cited → actual`
— never a repair cycle and never a stop. A drift beyond 5 lines, or a cited
mechanism that is absent, is a spec ambiguity: the task stops and reports
(REV-03), because the spec's picture of the tree is wrong.

**REQ-V1110-EC-03 (MUST) — the test floor and the pin inventory.** The
v1.10.4 suite is **2311 collected tests** (`AGENTS.md:161`, `tests/test_v190_agents.py:146-149`);
T0 re-measures with `uv run --locked pytest --collect-only -q -o addopts=""
| grep -c '::'` and the measured number is the floor. **The floor is a
release acceptance check at T8**, not a gate-3 mechanism: the final count
MUST be ≥ floor + 49 (the §11 table) — no test is deleted
(`REQ-V190-EC-03` carries). Tests may be modified only at the sites T0's
inventory names (PIN-01) plus the four release-mechanics sites of VER-01;
a site discovered later is a disclosed amendment (PIN-01), not a stop.
`[[VERIFY: the collected count after T0 is the floor; T8's collection
check reads floor + 49 or more, the exact number written into AGENTS.md by
T8; a count below floor + 49 means a §11 test was not landed — the task
that owns it (Appendix A) gets one repair cycle, then the stop route]]`.

**REQ-V1110-EC-04 (MUST) — delegation is specified, not hoped for.**
`standards/workflow.md` §5.1 binds every task. **Every task that reads or
writes source is delegated and briefed by a task-brief file**
`docs/spec/task-briefs/v1110-T<n>.md`, written by the orchestrator before
dispatch and passed by path — never retyped into a prompt. The brief
carries whatever load-bearing thing is already resolved (T0's pin table,
§3's payload rule, §7's `callback_data` grammar, §13's eight `find`
strings) by copying it from this spec or from an earlier task's output;
the executor never retypes a table into a prompt. Task-brief files are
committed with the task. §14.1's `delegate` column defaults to **yes** for
T1–T8; a `no` cell carries one of the four §5.1 exemptions **verbatim**
(*commands only*, *artefacts only*, *a single edit*, *is itself the
clean-context review*). Whatever the column says, a task whose actual
reading crosses a §5.1 trigger delegates from that point on, and the
report records map-versus-actual (VER-03 item 3). The subagent returns a
summary, never file content.

**REQ-V1110-EC-05 (MUST) — preconditions, operator inputs, the prompt
chain.** Before T0's first command: the tree is at `295b01f` = tag
`v1.10.4`'s successor (`git rev-parse HEAD` = `295b01f`, `git describe
--tags` starts with `v1.10.4`); `git status --porcelain` shows nothing but
`?? .README.md.swp`; `test -f .env` exits 0; `git stash list` is recorded;
`docs/prompts/235-v1110-spec-authoring.md` and `docs/llm-usage.md` row 145
exist in `HEAD`; this file is committed and unmodified (`git diff
--exit-code HEAD -- docs/spec/spec-v1.11.0.md`). **Gate 5 needs a
reachable LM Studio**: the `go` text names the box's current address; T0
writes it into `.env`'s `LMSTUDIO_BASE_URL` line with one `sed -i`
(pattern and replacement carry the address only, no other line is
touched, the file is never printed) **only when the `go` text carries an
address**; an unreachable LM Studio at gate 5 is a **blocked run** (the
report records the gate and the probe's redacted line; no task proceeds;
no stop route — the operator fixes the address and re-issues `go`).
**The override precondition (MOD-05)**: `bot_state` carries no
`provider_override` and no `model_override:*` row at T0 and at T7's gate
run — T0 checks it with the one permitted programmatic read of `data/`:
`uv run --locked python -c 'import config, storage; c = config.load_config();
conn = storage.connect_readonly(c.db_path); print(conn.execute("SELECT
COUNT(*) FROM bot_state WHERE key = ? OR key LIKE ?", ("provider_override",
"model_override:%")).fetchone()[0])'` (one integer printed; a fresh
database prints `0`; a missing database is `0` by the `storage.connect_readonly`
error, recorded); a non-zero count is a blocked run, reported with the
count only. Prompts: `docs/prompts/236-go-spec-v1.11.0.md` (T0) through
`244-v1110-t8-version-bump.md`, one per task, plus one per repair cycle;
one prompt → one commit, never mixed — with the **two explicit
exceptions** of `spec-v1.10.4.md`'s REV-02 form: T7's prompt carries two
commits (the source commit gate 8 tests, then the report-only commit) and
T8's prompt carries two (the bump commit, then the evidence-only commit,
VER-01). Commit header ≤ 72 characters, conventional type, body names the
prompt file (`AGENTS.md:115-127`); `--no-verify` is never used and the
report attests it.

**REQ-V1110-EC-06 (MUST) — secrets discipline.** Only two secret values
are ever registered (`config.py:351`, `:379`); the run never prints, quotes
or commits either. Briefs, the report, the tg-post and every test carry
env-variable **names** only. `RedactingFormatter` (`config.py:225`) stays
on every logger entry point (the v1.9.4 rule); the ingest worker logs
through the same root logger (SEC-01). `gitleaks-tree` is green on every
commit, the evidence commit included.

**REQ-V1110-EC-07 (MUST) — the order; the live gates never overlap.** Work
in §14's order; tests before the code they cover, inside the same task;
each task rewrites the pins T0's inventory assigns to it (PIN-01) so gate 3
is green at every commit. **Gates 6, 7 and 8 never run in parallel with
one another or with any other gate** (the lab's record: the mutation gate
mutates the tree in place and poisons concurrent readers). The version
bump is T8's and nowhere else, so a stop at any earlier point needs no
revert.

---

## 2. Non-goals, retired pins and things the executor should not look for

Out of scope; named so a task that drifts into one stops. Every row is a
`NON-GOAL`, each with its reason.

| id | NON-GOAL |
|---|---|
| `REQ-V1110-NG-01` | Live model enumeration (`GET /v1/models`) for the `/model` menu. The catalogue is the env allowlist (MOD-04): deterministic tests, no live call in gate 3. `bot.py --selftest-live` keeps probing LM Studio's `/models` for the *default* model (`bot.py:1883`) exactly as today. |
| `REQ-V1110-NG-02` | Per-user or per-chat provider/model overrides. `bot_state` is a bare `key TEXT PRIMARY KEY` table (`storage.py:267-270`) and the bot has one operator; the override stays global, like `provider_override` (`bot.py:56`, `:759-761`). |
| `REQ-V1110-NG-03` | Session rename, delete or pagination. `/sessions` shows the ten most recent and a trailing count (SES-02); rows are never deleted (`storage.py:646-662` only flips `active`). |
| `REQ-V1110-NG-04` | Streaming or edit-in-place model replies. `REQUEST_DEFAULTS` keeps `"stream": False` (`llm/base.py:201`); the agent-reply path is untouched (OUT-02). |
| `REQ-V1110-NG-05` | Media, inline mode, any update type but `message` and `callback_query`. `spec-v0.md:1958` (`REQ-NG-08`) and `spec-v1.md:1357` (`REQ-V1-NG-06`) are **retired by id for keyboards and callbacks only** (CBQ-01); their media and inline-mode clauses carry. |
| `REQ-V1110-NG-06` | Files above the Bot API `getFile` ceiling (20 MB) and a local Bot API server ("Download files without a size limit" needs the local server; out of scope). `DOCUMENT_MAX_BYTES` becomes the ceiling itself (ING-01). |
| `REQ-V1110-NG-07` | Retrieval-side changes: the per-query BM25 rebuild over every chunk of the user (`rag.py:100-115`, `storage.py:1122-1126`) is a scaling risk with 2,000,000-char documents and is noted in README's Limitations, not fixed. |
| `REQ-V1110-NG-08` | A delete button in `/documents`. Deletion stays a typed command; `/delete #<id>` (DOC-02) is the affordance. |
| `REQ-V1110-NG-09` | MarkdownV2 anywhere; `parse_mode` on any path but the table path; `entities`; entity-aware splitting. `REQ-V1100-OUT-02` and `REQ-V1100-NG-03` are **retired by id and replaced by OUT-01/OUT-02**: the payload pin now reads "the agent-reply path is `{chat_id, text}`; the table path is `{chat_id, text, parse_mode: "HTML"[, reply_markup]}` and nothing else". |
| `REQ-V1110-NG-10` | Refreshing `docs/plan.md`. It is historical — its last section is `## v1.6.0 (in progress)` (`docs/plan.md:215`) and it names spec-v1.7.0 as in progress (`:25`); no task reads it as a roadmap. |
| `REQ-V1110-NG-11` | A benchmark run. `AGENTS.md:266-268` keys the rule to prompts, tool schemas, tool output, history assembly and routing defaults; this release changes none (`SYSTEM_PROMPT`, `tools.tool_specs()`, `load_context_messages`, `REQUEST_DEFAULTS` byte-unchanged, REV-01 item 6). The waiver chain of `AGENTS.md:274-279` gains one sentence in T6: "v1.11.0 changes nothing token-bearing; the rule does not fire." |
| `REQ-V1110-NG-12` | Any new dependency (EC-01); any new `mutation-v1110` subset gate — the eight entries join `mutation-all` only (MUT-01), so the gate matrix keeps its 29 rows (§12) and `tests/test_v15_standards.py:1772-1802` gains no label. |
| `REQ-V1110-NG-13` | A schema change or migration of any kind. `SCHEMA_VERSION` stays 6 (`storage.py:21`); the session title is derived at list time (SES-01); the model override is a `bot_state` row (MOD-02). `init_schema` (`storage.py:491-521`) is byte-unchanged. |
| `REQ-V1110-NG-14` | Summarising the outgoing conversation on `/session` (a switch is reversible; the summary stays the `/new` hand-off for `recent_goals`, `storage.py:788-793`, `bot.py:1030-1046`); a change to gate 5, gate 7, `devtools/agent_eval.py`'s cases or floors. |

**There is no unmerged `/stats` specification.** Both `/stats` specs —
`REQ-V13-OBS-07` (`spec-v1.3.md:469-488`) and `REQ-V160-MET-05`
(`spec-v1.6.0.md:856-871`) — are implemented at `bot.py:1132-1164`; only
the README sample (`README.md:127-140`) is two lines short. The executor
does not go looking for one; STA-01 and VER-02 cover it.

**Retired by id, this release** (a pin is retired by name, never
contradicted silently): `REQ-V1100-OUT-02` and `REQ-V1100-NG-03` → OUT-01,
OUT-02; `REQ-NG-08` (spec-v0) and `REQ-V1-NG-06` (spec-v1), the keyboard,
callback, `setMyCommands`, `/start` and `/help` clauses only → CBQ-01,
EXT-01, EXT-02. `spec-v1.md:135`'s "exactly five commands exist" is
already stale (eight dispatch at `bot.py:904-953`) — noted, not edited.

---

## 3. The outbound table path

**REQ-V1110-OUT-01 (MUST) — one new send helper, the table path.**
`bot.py` gains **`send_pre(tg, chat_id, body, *, reply_markup=None) ->
dict | None`** — the only production site that ever sets `parse_mode`. It
builds `text = "<pre>" + html.escape(redact(body), quote=False) + "</pre>"`
— **redact before escape, escape before wrapping** — and calls the new
`TelegramClient.send_message_html(chat_id, text, reply_markup=None)`
(CBQ-03), whose payload is exactly `{"chat_id", "text", "parse_mode":
"HTML"}` plus `"reply_markup"` when one is given, and nothing else: no
other tag, no MarkdownV2, no `entities`. The Bot API rule this satisfies:
"All `<`, `>` and `&` symbols that are not a part of a tag or an HTML
entity must be replaced with the corresponding HTML entities"; `<pre>` is
a supported tag. **The table path never splits.** Its body is fitted
before sending by `tables.fit_lines(lines, limit=MESSAGE_LIMIT)`: the
entity-parsed length — tags do not count, an escaped `&lt;` counts as one
unit, `utf16_length` (`bot.py:305-307`) counts the rest — must stay ≤ 4096
("1-4096 characters after entities parsing"); whole lines are dropped
from the end and a final `… N more` line appended until it fits, the
`_fit` way (`bot.py:1190-1197`) but over lines, never a hard slice inside
a line. The table path is used by **`/stats`, `/documents`, `/sessions`,
`/model` (the menu text) and `/help`/`/start` only**; `/status`, `/summary`,
`/new`, `/session`, `/delete`, `/cancel`, `/reload_skills`, every ERR-01
string and every agent reply stay on the plain path. `send_pre` returns
the `sendMessage` result (the `message_id` a keyboard edit needs) or
`None` after OUT-04's fallback also failed. `T-V1110-OUT-02`, `-03`, `-04`.

**REQ-V1110-OUT-02 (MUST) — the agent-reply path is unchanged and its
pin is narrowed, not deleted.** `reply_parts` → `_send` → `TelegramClient.send_message`
(`bot.py:310-312`, `:1500-1511`, `:226-227`) do not change by one character;
`send_message(chat_id, text)`'s signature gains no `parse_mode` and no
`reply_markup` keyword — the new kwargs live on `send_message_html` and
`edit_message_html` only (CBQ-03) — so **`tests/test_v1100_sanitization.py:293-323`
stays green unamended**: `T-V1100-OUT-04` already asserts the key set of
one plain `sendMessage` body and greps `inspect.getsource(bot.TelegramClient.send_message)`
alone (`:319-323`), which is exactly the agent-reply builder; `T-V1100-OUT-05`
(byte-equality of model output) is kept. The lab brief expected that test
to need a rewrite — it does not; the report says so. What the release
adds is `T-V1110-OUT-06`: `inspect.signature(bot.TelegramClient.send_message)`
has parameters `{chat_id, text}` only, `_send`'s payload through
`httpx.MockTransport` is `{chat_id, text}`, and `/status` and `/summary`
replies carry no `parse_mode` in `FakeTelegram.sent_payloads`. Mutation
`v1110-agent-reply-gains-parse-mode` (§13) proves the pin bites.

**REQ-V1110-OUT-03 (MUST) — `render_table`, a pure function in a new
module `tables.py`.** Placed at the repository root (it joins
`GATE8_DEPENDENCIES` by the `*.py` glob, `devtools/agent_eval.py:1234-1242`,
which is correct — gate 8 runs once after it lands, REV-02). `tables.render_table(headers:
Sequence[str], rows: Sequence[Sequence[object]], *, align: Sequence[str] |
None = None, max_width: Sequence[int | None] | None = None) -> str`:
cells are `str()`-ed, `None` → `n/a`; a column's alignment is `"r"` when
`align` says so or when every non-`n/a` cell is an `int`/`float`, else
`"l"` (numbers right-aligned, text left-aligned); every text cell longer
than its column's `max_width` is cut to `max_width - 1` characters plus a
trailing `…`; each column is padded to its widest cell in UTF-16 units
(`utf16_length` moves to `tables.py` and `bot.py` re-imports it from
there — its behaviour and `bot.utf16_length`'s name are unchanged); the
header row is followed by one rule line of ASCII `-` per column
(`-` chosen over U+2500 for old clients); columns are joined by two
spaces. **Every line of the output has the same UTF-16 length, and the
total line width is ≤ 60 units** so phones do not scroll horizontally: the
caller's `max_width` values MUST satisfy it for every table this spec
defines (STA-01, DOC-01, SES-02, MOD-01, EXT-02 state theirs), and
`render_table` raises `ValueError` when the rendered width exceeds 60 —
the tests, not the user, see that. No `<`, `>` or `&` survives in the
payload: `render_table` returns raw text and `send_pre` escapes (OUT-01);
`T-V1110-OUT-01` (property-style over generated rows), `T-V1110-SEC-01`.

**REQ-V1110-OUT-04 (MUST) — one plain-text fallback on a table-path 400.**
When `send_message_html` raises `TelegramError` with status 400 (the
Bot API's "can't parse entities" family) and the error is not fatal
(`bot.py:154-198`'s 401/404 classification stands), `send_pre` sends **the
same body once more** through the plain `send_message(chat_id, redact(body))`
— no tags, no `parse_mode`, no `reply_markup` — and returns that result; a
second failure is logged through `_send`'s existing line and `None` is
returned; there is never a third attempt. The fallback exists only on the
table path and is exercised through the real `TelegramClient` over
`httpx.MockTransport`: `T-V1110-OUT-05` (two requests, the second without
`parse_mode`; a second 400 → no third request — negative).

**REQ-V1110-OUT-05 (MUST) — the fakes grow, compatibly.** `tests/fakes.py:143-198`
`FakeTelegram` keeps `sent` as `(chat_id, text)` (hundreds of tests read
it) and gains: `sent_payloads: list[dict]` (every `send_message` and
`send_message_html` call as the payload dict the real client would post,
`parse_mode`/`reply_markup` included when given), `edited_payloads:
list[dict]` (likewise for `edit_message_text` and `edit_message_html`),
`callback_answers: list[dict]` (`answer_callback_query` calls),
`commands_set: list[list[dict]]` (`set_my_commands` calls), `fail_html_with:
Exception | None` (scripts a raise on the next `send_message_html`, for
OUT-04 through the fake). `send_message_html` also appends to `sent` so
existing assertions over `sent` keep counting messages. `T-V1110-OUT-07`.

---

## 4. `/stats` as a table

**REQ-V1110-STA-01 (MUST) — same data, one `<pre>` block.** `_render_stats`
(`bot.py:1132-1164`) keeps its sources — `metrics.conversation_stats`,
`metrics.global_stats`, `metrics.error_breakdown`, `metrics.summary_health`,
`metrics.top_tools`, `metrics.turn_timeline`, never its own SQL
(`bot.py:1172`, `:1183` comments) — and `STATS_MAX_CHARS = 3500` (`bot.py:58`),
and returns one body for the table path (OUT-01): a three-column table
`metric | this conv | all time` (`max_width` 16 / 20 / 20) over the paired
rows in this order — `LLM calls`, `errors`, `tokens in`, `cached`,
`reasoning`, `tokens out`, `est. cost`, `cost basis`, `avg prompt/call`,
`re-sent share` — followed by a blank line and the four single-value lines
`Top tools: …`, `Last turn: …`, `Errors: …`, `Summaries: …` built by the
unchanged helpers (`_render_top_tools` `bot.py:1219-1223`, `_render_last_turn`
`:1226-1241`, `_render_errors_line` `:1171-1179`, `_render_summaries_line`
`:1182-1187`). The content semantics of `REQ-V13-OBS-07` and `REQ-V160-MET-05`
are preserved verbatim as **cell content**: `n/a` for a missing value
(`_cell`, `bot.py:1205-1206`), `n/a (no pricing)` for a side without a
basis (`_render_cost`, `:1209-1212`), `mixed` for several bases, the
percent rendering of `_render_share` (`:1215-1216`). The title line
`Stats (this conversation | all time)` becomes the table header; `_fit`
(`:1190-1197`) is replaced for this command by `tables.fit_lines` at the
3500-character cap, whole lines from the end. The "fixed layout, tests
assert labels" pin of `REQ-V13-OBS-07` is re-pinned on the labels above:
T0 inventories every assertion on the old line shapes (`tests/test_observability.py`,
`tests/test_v160_observability.py`, `tests/test_pricing.py` — 43 hits at
`295b01f`) and T2 rewrites each to presence of the label and the value in
the new body, never a whole-line equality (PIN-01). `T-V1110-STA-01`,
`-02`, `-03`; Gherkin `E11`.

---

## 5. `/documents` as a table; `/delete` by id; the refusal wording

**REQ-V1110-DOC-01 (MUST) — the table.** `_handle_documents` (`bot.py:1478-1484`)
keeps `storage.list_documents` (`storage.py:1081-1084`, ordered
`created_at, id`) and the empty case — `DOCUMENTS_EMPTY_REPLY` (`bot.py:96`)
verbatim on the **plain** path — and otherwise sends one table-path body
whose **first line is `Your documents (N of 20):`** (inside the `<pre>`,
`20` = `documents.DOCUMENT_LIMIT`, `documents.py:381`), a blank line, then
`render_table` over the columns `#` (`documents.id`), `file` (the
filename, `redact()`-ed as today at `bot.py:1474`, `max_width` 28),
`type`, `size` (`size_bytes` in human units: `< 1 MB` → `NNN.N KB`, else
`NN.N MB`, one decimal, decimal units, `0.0 KB` for zero), `chunks`,
`pages` (`n/a` for non-PDF rows, `page_count` otherwise), `added`
(`created_at[:10]`) — the README claim that size is shown (`README.md:116`)
becomes true. Width: `#` ≤ 4, `type` 4, `size` ≤ 8, `chunks` ≤ 6, `pages`
≤ 5, `added` 10 — with the two-space joins the line is ≤ 60 units
(OUT-03). `_render_document_line` (`bot.py:1471-1475`) is removed; its
one caller is this handler (T0 confirms no other). **The in-flight line**:
when the caller has a queued or running ingest job (ING-03), the body
ends with one line `⏳ indexing <name> — <stage>` where `<stage>` is the
job's last progress string without its `📄 ` prefix (`received`,
`extracted: …`, `chunked: N`, `embedding: i/n`) — wired in T5, after the
worker exists. `T-V1110-DOC-01`, `-02`; `T-V1110-SEC-01` (a filename
`<script>&</script>`).

**REQ-V1110-DOC-02 (MUST) — `/delete #<id>`.** `_handle_delete`
(`bot.py:1487-1497`) keeps `REQ-V190-CMD-06`'s exact-match filename
semantics and `DELETE_USAGE_REPLY` (`bot.py:97`, its text becomes
`Usage: /delete <filename> | /delete #<id>`, one literal, T0 inventories
its pins). An argument that starts with `#` is an id form: `#` followed by
ASCII digits only → `storage.delete_document(conn, user_id=from_id,
document_id=int)` (`storage.py:1087-1119`, whose `AND d.user_id = ?`
predicates scope it; the function returns `False` when nothing was
deleted) → `Deleted #<id>.` on `True`; `False` (an id the caller does not
own, or none at all — never distinguished), or `#` followed by anything
but digits → the existing shape `No document named <argument>.` with the
argument echoed through `redact()[:120]` as today. A filename that
happens to start with `#` is unreachable by name after this change — the
README row says so. `T-V1110-DOC-03` (own / foreign / non-integer /
filename form; negative), Gherkin `E4`.

**REQ-V1110-DOC-03 (MUST) — the refusal wording split.** `bot.py:1433-1440`
maps `DocxArchiveTooLargeError` and `PdfTooManyPagesError` onto
`DOC_TEXT_TOO_LARGE_REPLY`, so a 2,001-page PDF is told it has too many
characters (facts-B contradiction 6, `spec-v1.9.0.md:1331` row 5b). Two
new constants, `DOC_DOCX_BOUNDS_REPLY = "Document too large (DOCX archive
bounds)."` and `DOC_PDF_PAGES_REPLY = "Document too large (over 2,000
pages)."`, replace the string in those two clauses only; the clause
order and the exception classes are unchanged. `DOC_TEXT_TOO_LARGE_REPLY`
becomes `Document too large (over 2,000,000 characters).` (ING-01). ERR-01
rows 2–4; `T-V1110-DOC-04`.

---

## 6. Sessions: list and switch, no schema change

**REQ-V1110-SES-01 (MUST) — two storage helpers, derived titles, schema
6.** A session is a `conversations` row (`storage.py:238-243`; integer
ids; scoping `tg_user_id`; the partial unique index `storage.py:245-246`
allows one `active = 1` row per user). `storage.py` gains:

- `list_conversations(conn, tg_user_id: int, *, limit: int) -> list[sqlite3.Row]`
  — the columns of `recent_conversations` (`storage.py:1229-1245`: `id`,
  `created_at`, `active`, `message_count`, `last_activity`) **filtered by
  `tg_user_id`**, plus `title`: the content of the conversation's first
  `user` message (`messages` ordered `id`, `storage.py:248-263`),
  whitespace-collapsed (`" ".join(content.split())`), cut to 40
  characters with a trailing `…` when longer, `(empty)` when the
  conversation has no user message. Ordered `last_activity DESC NULLS
  LAST, id DESC`, bounded by `limit`. The title is computed at list time
  in SQL or Python and **never stored** — no column, no migration;
  `SCHEMA_VERSION` stays **6** (`storage.py:21`) and `_SCHEMA`
  (`storage.py:229-276`) is byte-unchanged (`T-V1110-SES-01` asserts both
  and that `PRAGMA table_info(conversations)` has four columns);
- `count_conversations(conn, tg_user_id) -> int` for the trailing line;
- `activate_conversation(conn, tg_user_id: int, conv_id: int) -> bool`
  following `start_new_conversation`'s recipe exactly (`storage.py:646-662`):
  `BEGIN IMMEDIATE`; `UPDATE conversations SET active = 0 WHERE tg_user_id
  = ? AND active = 1`; `UPDATE conversations SET active = 1 WHERE id = ?
  AND tg_user_id = ?`; when that second update's `rowcount` is 0 the
  transaction is **rolled back** (the caller's active row is restored by
  the rollback) and `False` returned; else `COMMIT`, `True`. A missing or
  foreign id therefore changes nothing. The transactional form is
  mandatory because of the partial unique index. `T-V1110-SES-02` (own /
  foreign / missing; exactly one active row after each — negative);
  mutation `v1110-activate-ownership-dropped`.

**REQ-V1110-SES-02 (MUST) — `/sessions`.** Dispatched in the command
block (`bot.py:896-953`, D14: added to the table, everything else still
falls through to the model at `:955`). Sends one table-path body:
`render_table` over `#` (id, ≤ 6), `●` (the marker column: `●` for the
active row, empty otherwise, width 1), `title` (`max_width` 28,
`redact()`-ed — it is user text), `msgs` (`message_count`), `last`
(`last_activity` as `YYYY-MM-DD HH:MM`, `n/a` when `NULL`) — ≤ 60 units —
over the **10** most recent by `last_activity` (`list_conversations(...,
limit=10)`); when `count_conversations` exceeds 10, a trailing line `N
older sessions not shown` (N = count − 10). Pagination is NG-03.
`T-V1110-SES-03`; `T-V1110-SEC-01` (a first message `<script>&</script>`).

**REQ-V1110-SES-03 (MUST) — `/session <id>`, and `/new` names its id.**
`/session` with exactly one argument of ASCII digits → `activate_conversation`;
`True` → plain reply `Switched to session #<id>: <title>` (the title as
SES-01 derives it, redacted); `False` → `No session #<id>.` (never
revealing whether the id exists for someone else); bare `/session`, more
than one argument, or a non-integer → `Usage: /session <id> (see
/sessions)`. Switching does **not** summarise the outgoing conversation
(NG-14) and does not write to `messages` or `summaries`; the agent's next
turn loads its context from the newly active conversation through the
unchanged `get_or_create_active_conversation` + `load_context_messages`
(`storage.py:632-643`, `:721-768`; `bot.py:955-1004`). `/new`
(`_handle_new`, `bot.py:1019-1048`) is unchanged except its reply:
`NEW_CONVERSATION_REPLY` becomes the format `New conversation started
(#{conv_id}).` using the id `start_new_conversation` returns
(`bot.py:1047`); T0 inventories its literal pins (`tests/test_telegram.py`,
`tests/test_summary.py`, `tests/test_v1100_red_team.py` — five hits at
`295b01f`) and T3 rewrites them to `startswith("New conversation started
(#")` (PIN-01). `T-V1110-SES-04` (own switch + the next turn's context;
foreign; usage; no summary call — negative), `T-V1110-SES-05`; Gherkin
`E2`, `E3`.

---

## 7. Callback queries and inline keyboards

**REQ-V1110-CBQ-01 (MUST) — the plumbing and the guards.** `get_updates`
(`bot.py:220-224`) sends `"allowed_updates": ["message", "callback_query"]`
(the pin at `tests/test_telegram.py:272` moves with it, PIN-01).
`process_update` (`bot.py:813-1004`) gains a **`callback_query` branch
before the message-only guard** (`:841-844`): when `update["callback_query"]`
is a dict it is handled by `_handle_callback(...)` and the function
returns. The branch applies **the same guards in the same order as
messages** (`:845-861`, `:891-894`): `callback_query.message.chat` must be
a `private` chat with an int id; `callback_query.from` must be a human
sender (`is_bot` false); `from.id in cfg.allowed_tg_ids` — **an
intruder's callback is answered with `answerCallbackQuery(callback_query_id)`
carrying no `text` and nothing else happens**: no log line beyond the
existing `unauthorized update from tg_id=%s` warning (`:860`), no state
read, no LLM, no second Telegram call (the intruder cost rule of
`REQ-V1-*`'s allowlist carries; the one acknowledgement is what stops
Telegram's client spinner and costs nothing); `message.chat.id` must equal
`from.id` (a private chat's id is its user's id — a mismatch is ignored
without an answer); the rate limiter charges one token (`RateLimiter.allow`,
`bot.py:315-343`) — a rate-limited callback is acknowledged with `text =
RATE_LIMIT_REPLY` and nothing else. The at-most-once cursor write
(`:834-839`) precedes everything, as for messages. `T-V1110-CBQ-01`,
`T-V1110-CBQ-02` (intruder — negative), `T-V1110-CBQ-03` (the other
guards); mutation `v1110-callback-allowlist-dropped`; Gherkin `E5`.

**REQ-V1110-CBQ-02 (MUST) — acknowledge once, first; the `callback_data`
grammar.** Every handled callback is acknowledged with
`answerCallbackQuery(callback_query_id)` **exactly once, before any other
Telegram call** (`FakeTelegram.callback_answers` gets its entry before
`edited_payloads`/`sent_payloads` grow). `callback_data` is ASCII, ≤ 64
bytes ("1-64 bytes"), of the form `<ns>:<verb>:<arg>` with `ns ∈ {mod,
ses}`; the complete verb list is:

| data | meaning | arg |
|---|---|---|
| `mod:prov:<name>` | show `<name>`'s model buttons (MOD-02 step 2) | `lmstudio` \| `openrouter` |
| `mod:model:<idx>` | select model `<idx>` of the provider currently shown (MOD-02) | decimal index into the rendered catalogue |
| `mod:auto:-` | clear both overrides (MOD-02) | literal `-` |
| `mod:back:-` | return to step 1 (MOD-01) | literal `-` |
| `ses:switch:<id>` | reserved for a later release; **not emitted** and treated as stale | — |

The namespace `ses` is reserved so the grammar is closed; no keyboard is
attached to `/sessions` in this release. **Stale or malformed data** —
unknown `ns`/`verb`, non-ASCII, over 64 bytes, a non-integer where an
integer is expected, an out-of-range model index, a provider that is not
configured, a `mod:model` selection whose message no longer shows a
provider — is acknowledged with `text = "Expired — send the command
again."` and **no state change** (no `bot_state` write, no `set_provider`
call, no edit). `callback_data` is never interpreted as a filename, a
path or SQL (SEC-01); the model index is bounds-checked against the
catalogue re-derived from `cfg` at handling time (MOD-02).
`T-V1110-CBQ-04`, `T-V1110-CBQ-05` (stale/malformed — negative),
`T-V1110-CBQ-07` (every emitted data string matches the grammar and is ≤
64 bytes even with long model ids); mutation `v1110-model-index-unbounded`;
Gherkin `E6`.

**REQ-V1110-CBQ-03 (MUST) — keyboards ride the table path; a selection
edits the same message; the client methods.** A keyboard is attached as
`reply_markup = {"inline_keyboard": [[{"text": …, "callback_data": …}],
…]}` on the table-path message (`send_pre(..., reply_markup=…)`, OUT-01),
one button per row unless MOD-01 says otherwise. After a selection the
**same** message is edited — `edit_message_html(chat_id, message_id,
text, reply_markup=None)` with a new `<pre>` body and the keyboard removed
(`reply_markup` omitted) or replaced — never a second message. `TelegramClient`
(`bot.py:142-269`) gains exactly three methods, each through
`_call_with_retry` (`:200-215`): `send_message_html(chat_id, text, *,
reply_markup=None)` → `sendMessage` with `parse_mode: "HTML"` (+
`reply_markup`); `edit_message_html(chat_id, message_id, text, *,
reply_markup=None)` → `editMessageText` likewise; `answer_callback_query(callback_query_id,
*, text=None)` → `answerCallbackQuery` with `text` only when given. The
existing `send_message`, `edit_message_text`, `delete_message`, `get_file`,
`download_file` are byte-unchanged (OUT-02); `set_my_commands` is EXT-01's.
`T-V1110-CBQ-06` (payload shapes over `httpx.MockTransport`; a selection
edits the original `message_id` and `sent` does not grow).

---

## 8. The `/model` menu and the model override

**REQ-V1110-MOD-01 (MUST) — step 1: the status block and the provider
keyboard.** Bare `/model` sends, through the table path, a `<pre>` status
block: `render_table` over `field | value` (`max_width` 12 / 44) with the
rows `provider` (`_active_provider`, as `bot.py:1261`), `override`
(`provider_override` or `none`), `model` per configured provider (one row
`lmstudio model` / `openrouter model`: the override model when
`model_override:<provider>` is set, else the configured default, marked
`(override)` when it is one), `failures` (`_render_failures`,
`bot.py:1248-1250`) — the content of today's bare reply (`:1253-1264`)
— with an inline keyboard of **one button per configured provider**
(`provider_is_configured`, `llm/__init__.py:22-28`; text = the provider
name, data `mod:prov:<name>`) and one `auto` button (`mod:auto:-`), all in
one row. `T-V1110-MOD-01`.

**REQ-V1110-MOD-02 (MUST) — step 2: the model buttons; selection sets two
keys; `auto` clears both.** On `mod:prov:<name>` the same message is
edited (CBQ-03) to a `<pre>` body `Models for <name>:` followed by the
catalogue (MOD-04) one per line as `<idx>. <model id>` (`redact()`-ed and
escaped like every user- or env-supplied string), with one button per
model (text = the model id cut to 32 characters, data `mod:model:<idx>`,
the index as rendered — the id itself may exceed 64 bytes, the index never
does) and a last row `← back` (`mod:back:-`). The provider shown is
carried by the message text, not by a server-side state: the handler
parses `Models for <name>:` back out of `callback_query.message.text`
(the plain text Telegram echoes) and re-derives the catalogue from `cfg`;
a missing or unparsable header, an unconfigured provider or an index
outside `range(len(catalogue))` is stale (CBQ-02). On a valid
`mod:model:<idx>`: `storage.set_state(conn, PROVIDER_OVERRIDE_KEY, name)`
**and** `storage.set_state(conn, f"model_override:{name}", model)` (the new
key family; global, NG-02), then `set_provider(name)` (MOD-05), then the
message is edited to `Provider: <name>, model: <model>` with the keyboard
removed. `mod:auto:-` (and the text form `/model auto`) deletes
`provider_override` **and every `model_override:*` row** (`DELETE FROM
bot_state WHERE key LIKE 'model_override:%'` — a new `storage.delete_state_prefix(conn,
prefix)` helper), calls `set_provider(None)`, and edits (button) or
replies (text) `Provider override cleared.` (`bot.py:1268-1272`'s string,
unchanged). `mod:back:-` edits back to step 1's body and keyboard.
`T-V1110-MOD-02`, `-03`; Gherkin `E7`.

**REQ-V1110-MOD-03 (MUST) — the text form, kept for scripts and tests.**
`/model <provider>` behaves exactly as today (`bot.py:1274-1283`: the
`MODEL_USAGE_REPLY` / `Provider <p> is not configured.` / `Provider
switched to <p>.` strings unchanged; it does not touch any
`model_override:*` key). `/model <provider> <model>` — the model must be
in `<provider>`'s catalogue (MOD-04), else `Unknown model for <provider>;
see /model` — sets both keys as MOD-02 and replies `Provider switched to
<provider>, model: <model>.`. `/model auto` as MOD-02. More than two
arguments → usage. `MODEL_USAGE_REPLY` (`bot.py:71`) becomes `Usage:
/model [lmstudio|openrouter|auto] [<model>]`; T0 inventories its pins
(`tests/test_failover.py`, one hit at `295b01f`; the README Commands row
`README.md:114`). The dispatch site (`bot.py:932-943`) passes
`parts[1:3]` instead of `parts[1]`. `T-V1110-MOD-04`; Gherkin `E8`.

**REQ-V1110-MOD-04 (MUST) — the catalogue is an env allowlist.**
`config.py` gains `lmstudio_models: tuple[str, ...]` and
`openrouter_models: tuple[str, ...]` next to `lmstudio_model` /
`openrouter_model` (`config.py:108-110`, parsed at `:360-362`): the
comma-separated `LMSTUDIO_MODELS` / `OPENROUTER_MODELS` env vars, each
entry stripped, empty entries dropped, **the configured default model
always first even when the list omits it**, then the list in env order,
deduplicated (first occurrence wins). Unset or empty → the one-entry tuple
`(default,)`, so an unchanged `.env` yields a one-entry catalogue; a
provider whose default model is empty has an empty catalogue. No live
enumeration (NG-01). `.env.example` gains the two variables, each with a
one-line comment, next to `LMSTUDIO_MODEL` / `OPENROUTER_MODEL`
(`.env.example:12-18`); README's `## Switch provider` section
(`README.md:237-266`) gains a short paragraph naming `LMSTUDIO_MODELS` and
`OPENROUTER_MODELS` (comma-separated allowlists; default = the single
configured model; the default always included; env order kept; duplicates
dropped) and the `/model <provider> <model>` text form. README has no
provider-variable table: the `README.md:75-91` table is the output
windows / history / pricing / observability sub-table and is **not
touched**. `T-V1110-MOD-05`.

**REQ-V1110-MOD-05 (MUST) — the override reaches the client; what
`llm_calls.model` records; the gate-time precondition.** `build_llm_client`
(`llm/__init__.py:30-110`) gains `model: str | None = None`, passed to
`_client_for(cfg, primary, client, model=model)` for the primary side only
(`:72-86`; the failover secondary keeps its configured default — the
override names one provider's model); `_client_for` already applies it
(`:89-110`, "everything else … stays the provider's": timeout, caps and
`*_CONTEXT_LENGTH` unchanged). `main()`'s `set_provider` (`bot.py:2079-2081`)
and the initial construction (`:2077`) read `model_override:<provider>`
through a new `load_model_override(conn, provider) -> str | None`
(beside `load_provider_override`, `bot.py:759-761`; a value not in the
provider's catalogue is ignored — stale env, negative case) at the same
moment they read the provider override, and pass it as `model=`; `get_llm`
(`:1565-1566`) is unchanged because `set_provider` rebuilds `live["llm"]`.
**What the cost and stats machinery sees**: `agent._record_llm_call`
reads `describe_client(llm)` *after* the call (`agent.py:1077`) and
stores that pair as `llm_calls.provider`/`.model` (`agent.py:1152-1163`,
`storage.py:818-850`); `LMStudioClient`/`OpenRouterClient.describe()`
return the model they were constructed with, so an override model is
recorded by its own id and priced by `resolve_cost(provider, model, usage)`
(`agent.py:1091`) exactly as a routed purpose model is today — no change
to `metrics.py` or `pricing.py`. **Precondition for gate 8 and any
benchmark**: `bot_state` holds no `provider_override` and no
`model_override:*` row at T0 and at T7's gate run (EC-05's read-only
count); the gate-8 tree is exercised with the configured defaults.
`T-V1110-MOD-06` (the override reaches `describe()` and `llm_calls.model`;
a stale override is ignored — negative); Gherkin `E7`.

---

## 9. Large documents: the caps and the ingest worker

**REQ-V1110-ING-01 (MUST) — the caps rise to the Bot API ceiling; one
`find` line survives.** `DOCUMENT_MAX_BYTES` (`bot.py:80`) becomes
`20_000_000` — decimal 20 MB, because the Bot API says of `getFile`: "bots
can download files of up to 20MB in size", and decimal stays under the
ceiling whichever unit Telegram means; no live test of a near-ceiling
file is required — the constant's comment (`bot.py:76-79`) cites that
sentence. Above it the upload is refused before `getFile` (`bot.py:1354-1358`,
unchanged logic) with `DOC_TOO_LARGE_REPLY = "File too large (over 20
MB)."`; the mid-stream cap (`download_file`, `bot.py:243-269`, `:1393`)
follows the constant. **Only the constant's value changes, on its own
line**: the line `    if isinstance(file_size, int) and file_size >
DOCUMENT_MAX_BYTES:\n` — the `find` of `v190-size-precheck-disabled`
(`devtools/mutation_check.py:1216-1224`) — survives verbatim and occurs
exactly once in `bot.py` (T0 checks with `grep -c -F`; `T-V1110-ING-01`
asserts it). `documents.MAX_EXTRACTED_TEXT_CHARS` `500_000` → `2_000_000`
(`documents.py:378`), `PDF_MAX_PAGES` `500` → `2_000` (`:109`),
`INDEX_BUDGET_S_DEFAULT` `300.0` → `1800.0` (`:380`, ING-05); the DOCX
archive bounds (`:104-107`), `DOCUMENT_LIMIT = 20` (`:381`), the chunker
(`chunk_text`, `:319-368`) and the embeddings batch constants are
unchanged. `DOC_BUDGET_EXCEEDED_REPLY` becomes `Indexing timed out (over
1800 s). Nothing was saved.`. Files above the ceiling are NG-06. The
literal pins (`tests/test_v190_agents.py:238-280`, `README.md:828-833`,
`:863-864`, `:511-517`) are T0's (PIN-01); `tests/test_v190_parsing.py`
and `tests/test_v190_errors.py` reference the constants symbolically and
track them. `T-V1110-ING-01` (20,000,001 refused before `getFile`;
20,000,000 accepted; mid-stream; the four constants; the DOCX bounds
untouched); mutation `v1110-document-cap-tenfold`; Gherkin `E9`.

**REQ-V1110-ING-02 (MUST) — `IngestWorker`: one daemon thread, a bounded
queue, its own connection, driven synchronously in tests.** Today
`_handle_document` runs inline in `poll_loop` and blocks every chat for
the whole ingest (`bot.py:1559-1582` calls `process_update` inline; the
offset advances only after it returns). New in `bot.py`: `class
IngestWorker` with `queue.Queue(maxsize=INGEST_QUEUE_MAX)` (`INGEST_QUEUE_MAX
= 4`), `submit(job) -> bool` (`put_nowait`; `False` on `queue.Full`),
`run_one() -> None` (one `get()` → process → mark done — **the thread
wrapper `_run` only loops over `run_one` until shutdown**), `cancel(from_id)
-> bool` and `in_flight(from_id) -> IngestJob | None` (ING-03, ING-04),
started as `threading.Thread(target=…, daemon=True)` in `main()` next to
the dashboard thread (`bot.py:2141`) **only in the real run** — `run_selftest`
(`bot.py:1669-1716`) constructs no worker. The split of `_handle_document`
(`bot.py:1331-1468`): the polling loop keeps `started_at = monotonic()` as
the handler's first action (`:1347`, `REQ-V190-CMD-03`) and the **five
pre-checks in their order** (`:1349-1378`: RAG configured, `file_size`
cap, `clean_filename`, `classify`, the 20-document count), each still a
plain synchronous reply with no status message and no `getFile`; then the
per-user and queue guards (ING-03); then it sends the status message
`📄 received` (`_StatusMessage.update`, `bot.py:368-380`) **from the loop
thread** — so the job carries a live `_StatusMessage` — enqueues
`IngestJob(chat_id, from_id, document, filename, status, started_at,
cancel=threading.Event())` and returns. `run_one` performs `getFile` +
`download_file` + `documents.index_document(...)` (with `progress=status.update`,
`cancel=job.cancel`, `budget_s=INDEX_BUDGET_S_DEFAULT`) + the final
reply (`_document_success_reply`, `bot.py:1322-1328`) or the ERR-01 clause
chain (`bot.py:1405-1468`, moved verbatim, DOC-03's two strings added)
— **on its own `storage.connect(cfg.db_path)` connection** opened once
when the worker is constructed (WAL is on, `storage.py:455`; the main
loop's connection is never touched from the worker: `IngestWorker`
receives `db_path`, never `conn`, `T-V1110-ING-02` asserts by
monkeypatching `storage.connect`) and the process-wide `EmbeddingsClient`
instance. `[[VERIFY: EmbeddingsClient thread-safety — at `295b01f` the
class holds no per-call mutable state (`llm/embeddings.py:32-47`: base
URL, model, dim, timeout, the shared `httpx.Client`, api key; `embed`
builds local lists only), `httpx.Client` is documented thread-safe, and
`tracing.start_span` uses a `ContextVar` (`tracing.py:271`), which a new
thread starts empty — so sharing the instance is safe and the worker's
CLIENT spans simply have no parent; confirmation = T5's brief records this
reading of `llm/embeddings.py:31-135` and `tracing.py:260-290`; if the
executor finds shared mutable state in `_post`/`_embed_batch` it constructs
a second `EmbeddingsClient` for the worker from the same `cfg` and says so
in the commit body — a disclosed amendment, not a stop]]`. The
exception boundary `REQ-V190-CMD-07` (`T-V190-CMD-08`, the loop survives a
handler exception) moves to `run_one`: any exception ends the job with
`DOC_HANDLER_FAILED_REPLY`, frees the slot, and the worker thread
continues. `T-V1110-ING-02` (the loop returns before `index_document`
runs; `run_one` completes the job; the pre-checks and `started_at`
unchanged — extends `T-V190-CMD-03`); Gherkin `E10`.

**REQ-V1110-ING-03 (MUST) — one in-flight job per user; a bounded queue.**
A second upload from a user whose job is queued or running → plain reply
`⏳ Still indexing <name>; wait for it to finish.` (`<name>` = the in-flight
job's filename, redacted), nothing enqueued; a different user's upload is
accepted. When the queue holds `INGEST_QUEUE_MAX` jobs → `Indexing queue is
full; try again later.`, nothing enqueued, no status message. Both guards
run after the five pre-checks and before the status message. The slot is
freed when `run_one` finishes the job on any path (success, ERR-01,
cancel, exception). `/documents` shows the in-flight line (DOC-01).
`T-V1110-ING-03` (second upload — negative), `T-V1110-ING-04` (queue
full — negative); mutation `v1110-inflight-guard-dropped`; Gherkin `E13`.

**REQ-V1110-ING-04 (MUST) — cooperative cancel.** `/cancel` (dispatched
like every command, D14) sets the caller's in-flight job's `cancel` event
and replies `Cancelling <name>…` on the plain path; with nothing in flight
→ `Nothing to cancel.`. `documents.index_document` gains `cancel:
threading.Event | None = None`, and `_check_budget` (`documents.py:431-436`)
gains the same parameter: at **every existing checkpoint** — after
extraction, between PDF pages (`documents.py:214-215`), after chunking,
after each embeddings batch (`:522`) — a set event raises the new
`documents.IndexCancelled` (a plain `Exception` subclass, like
`IndexBudgetExceeded`, `documents.py:404-410`, never folded into another
row). A cancelled job **stores nothing**: every checkpoint precedes
`BEGIN IMMEDIATE` (`documents.py:528`), so the transaction is never
opened; the worker maps `IndexCancelled` to a status edit `❌ Cancelled.`
(`_document_error_ending`, `bot.py:1311-1319`, the message kept) and frees
the slot. A `/cancel` that arrives after `BEGIN IMMEDIATE` has no
checkpoint left and the job completes — the reply text says `…` for that
reason. `T-V1110-ING-05` (cancel between embedding batches via a
`FakeEmbedder` hook; nothing stored; `Nothing to cancel.` — negative);
mutation `v1110-cancel-flag-ignored`; Gherkin `E11`.

**REQ-V1110-ING-05 (MUST) — the budget, the typing indicator, the
vectors, shutdown.** `INDEX_BUDGET_S_DEFAULT` is 1800 s (ING-01); the
budget origin stays the loop thread's `started_at`, carried in the job.
**The typing indicator is dropped from the document flow**: `_TypingIndicator`
(`bot.py:433-503`) is a thread of its own per run, and a second thread per
job on top of the worker buys nothing the four progress edits do not
already show — the worker performs the status-message edits only
(`REQ-V190-CMD-04`'s four strings unchanged, `documents.py:479-521`);
`tests/test_v190_commands.py:503-520` (`…typing_indicator_ceiling_is_the_index_budget`)
is rewritten by T5 to assert **no** `_TypingIndicator` is constructed on
the document path (PIN-01); the agent-turn indicator (`bot.py:957-958`)
is untouched. **Vectors**: `storage.add_vectors` (`storage.py:1045-1071`)
already inserts with one `executemany` per call (`:1068-1071`) — the lab's
recon recorded per-row inserts; it is wrong at `295b01f` and the spec
changes nothing here (transaction boundaries as today, `documents.py:528-563`).
**Shutdown**: `_handle_signal` (`bot.py:1589-1591`) sets `_shutdown`; the
worker is a daemon and an in-flight job is abandoned (nothing stored —
the checkpoints never reach `BEGIN IMMEDIATE` on a killed thread, and a
transaction in progress rolls back with the connection); a best-effort
edit of the job's status message to `❌ Interrupted by restart.` in
`main()`'s shutdown path is a **SHOULD**, not a MUST — no test, no
mutation, the report says whether it landed. `T-V1110-ING-01` (the
constant), `T-V1110-ING-02` (no typing indicator); Gherkin `E10`.

---

## 10. Lab-proposed extras — `setMyCommands`, `/help`, `/start`

Proposed by the lab; strike the group if unwanted. Small by design.

**REQ-V1110-EXT-01 (MUST) — one command table, registered at startup.**
`bot.py` gains a module-level `COMMANDS: tuple[tuple[str, str], ...]` —
`(name, description)` for every dispatched command, in the order of the
README Commands table (`/new`, `/status`, `/stats`, `/summary`, `/model`,
`/reload_skills`, `/documents`, `/delete`, `/sessions`, `/session`,
`/cancel`, `/help`), names without the slash and ≤ 32 characters
("1-32 characters"), descriptions ≤ 256 ("1-256 characters"), ASCII;
`/start` is not registered (it is an alias, EXT-02). `TelegramClient.set_my_commands(commands:
list[dict]) -> bool` posts `setMyCommands` with `{"commands": [{"command":
…, "description": …}, …]}` once through `_call_with_retry`. `main()` calls
it **once, immediately after `getMe`** (`bot.py:2058`); a `TelegramError`
or any exception there is logged (`log.warning("setMyCommands failed:
%s", redact(...))`) and is **never fatal** — the bot starts. `run_selftest`
(offline, `bot.py:1669-1716`) does not call it; `run_selftest_live`
(`:1772`) does not either. The README Commands table is hand-written; a
test asserts that every `COMMANDS` name has a README row and that
`/reload_skills` still precedes `/documents` (extending the order pin at
`tests/test_v190_agents.py:226-235`, which T0 inventories and T6 amends
in place). `T-V1110-EXT-01`, `T-V1110-EXT-03`; Gherkin `E12`.

**REQ-V1110-EXT-02 (MUST) — `/help` and `/start`.** Both dispatch to
`_handle_help`, which sends one table-path body: `render_table(("command",
"what it does"), COMMANDS, max_width=(14, 42))` (≤ 60 units). Neither is
stored in the conversation (commands never are, `bot.py:955-956`). Unknown
`/…` text still falls through to the model (`bot.py:955`, `README.md:119-120`).
`T-V1110-EXT-02`.

---

## 11. Error matrix, security and tests

### 11.1 Error matrix

**REQ-V1110-ERR-01 (MUST) — every new or changed user-visible string,
its trigger and what is stored.** Every string below is a module
constant or a format in `bot.py`; every one passes `redact()` before it
is sent; every row is on the plain path unless the table says otherwise.
Rows 1–5 replace `spec-v1.9.0.md:1330-1331,1338`'s 5a/5b/10c strings; the other
`REQ-V190-ERR-01` rows carry unchanged.

| # | trigger | reply | stored / state |
|---|---|---|---|
| 1 | `file_size` > 20,000,000 before download, or the stream exceeds it (ING-01) | `File too large (over 20 MB).` | nothing; no `getFile` on the pre-check |
| 2 | extracted text > 2,000,000 chars (ING-01) | `Document too large (over 2,000,000 characters).` | nothing |
| 3 | `DocxArchiveTooLargeError` (DOC-03) | `Document too large (DOCX archive bounds).` | nothing |
| 4 | `PdfTooManyPagesError`, > 2,000 pages (DOC-03) | `Document too large (over 2,000 pages).` | nothing |
| 5 | `IndexBudgetExceeded`, 1800 s from `started_at` (ING-05) | `Indexing timed out (over 1800 s). Nothing was saved.` | nothing |
| 6 | a second upload while the caller's job is queued or running (ING-03) | `⏳ Still indexing <name>; wait for it to finish.` | nothing enqueued |
| 7 | the queue holds 4 jobs (ING-03) | `Indexing queue is full; try again later.` | nothing enqueued |
| 8 | `/cancel` with a job in flight (ING-04) | `Cancelling <name>…`, then the status message edited to `❌ Cancelled.` at the next checkpoint | nothing stored; slot freed |
| 9 | `/cancel` with nothing in flight (ING-04) | `Nothing to cancel.` | — |
| 10 | shutdown with a job in flight (ING-05, SHOULD) | status edited to `❌ Interrupted by restart.` best-effort | nothing stored |
| 11 | `/session` bare, > 1 argument or non-integer (SES-03) | `Usage: /session <id> (see /sessions)` | — |
| 12 | `/session <id>` unknown or foreign (SES-03) | `No session #<id>.` | active row unchanged |
| 13 | `/delete #<id>` not owned, or `#` followed by non-digits (DOC-02) | `No document named <argument>.` (the existing shape, argument echoed, ≤ 120 chars) | nothing |
| 14 | `/delete` bare (DOC-02) | `Usage: /delete <filename> \| /delete #<id>` | — |
| 15 | stale or malformed `callback_data` (CBQ-02) | `answerCallbackQuery` `text = "Expired — send the command again."`; an intruder's callback: the acknowledgement with no text | no state change |
| 16 | `/model <provider> <model>` with a model outside the catalogue (MOD-03); `/model` with an unknown token or > 2 arguments | `Unknown model for <provider>; see /model` / `Usage: /model [lmstudio\|openrouter\|auto] [<model>]` | no state change |
| 17 | a 400 from Telegram on the table path (OUT-04) | the same body re-sent once as plain text; a second failure logged, no reply | — |

`setMyCommands` failing at startup (EXT-01) produces a log line and no
reply — not a row. `T-V1110-ERR-01` drives every string of rows 1–16 (row
17 has no string) through the fakes and asserts each appears verbatim in
README's `## Error behaviour` table (`README.md:839-874`, VER-02) — the
v1.9.0 form at `tests/test_v190_agents.py:258-280`, which T0 inventories
and T5/T6 amend for the five changed strings.

### 11.2 Security

**REQ-V1110-SEC-01 (MUST) — nothing new is executed, written, reached or
leaked.** (1) **Every user- or env-supplied string that reaches a `<pre>`
body** — filenames (DOC-01), session titles built from user messages
(SES-01), model ids from env (MOD-02), the `/help` descriptions — is
`redact()`-ed then `html.escape`-d (OUT-01): a filename and a first
message of `<script>&</script>` produce a payload containing
`&lt;script&gt;&amp;` and never the raw bytes; a registered sentinel secret
inside a session title is `***REDACTED***` in the payload. (2)
**`callback_data` is never interpreted as a filename, a path or SQL**: the
handler parses `<ns>:<verb>:<arg>` with `str.split(":", 2)`, checks `ns`
and `verb` against the closed table (CBQ-02), converts `arg` with `int()`
inside a `try`, bounds-checks the index — a data of `ses:switch:../x` or
`mod:model:1 OR 1=1` is stale (row 15). (3) **The intruder cost rule
extends to callbacks** (CBQ-01): one acknowledgement, no log beyond the
existing warning, no read. (4) **No new file writes**: document bytes stay
in memory on the worker as on the loop today (`bot.py:256-261`; 20 MB is
acceptable); `T-V190-SEC-04b` (`tests/test_v190_commands.py:1306`) is kept
and `T-V1110-SEC-01` repeats its `open`/`Path.write_*` monkeypatch around
`run_one`. (5) **No new network destinations**: the worker talks to
`TELEGRAM_API_HOST` and the configured embeddings endpoint only, through
the same `httpx.Client`. (6) **The worker thread has no access to the
main connection** (ING-02) and no access to `agent`, `llm` or the skills
registry — `IngestWorker.__init__` takes `(cfg, tg, embedder, db_path)`
and nothing else. (7) **`RedactingFormatter` stays on every logger entry
point** (`config.py:225`, `bot.py:1999-2003`): the worker logs through
`logging.getLogger("bot")`'s root handlers; `T-V1110-SEC-01` asserts a
sentinel secret in a worker log record is redacted. (8) `gitleaks-tree` is
green on every commit. `T-V1110-SEC-01` (negative in every clause);
mutation `v1110-table-path-escape-dropped`.

### 11.3 Tests

Written before the code they cover (EC-02). New files, all offline
against `FakeLLM`, `FakeTelegram` (OUT-05), `FakeEmbedder`
(`tests/fakes.py:205`), `httpx.MockTransport` (`tests/fakes.py:200-202`)
and a `tmp_path` database — one file per group, `tests/test_v1110_<group>.py`
(`out`, `sta`, `doc`, `ses`, `cbq`, `mod`, `ing`, `ext`, `pin`, `mut`,
`ver`, `sec`, `err`). No test sleeps or asserts timing: the worker is
driven by `run_one()` (ING-02) and the cancel event is set from a
`FakeEmbedder` hook. **Forty-nine** test ids; "negative" marks a test
whose main assertion is that something does **not** happen.

| test | file | asserts | negative |
|---|---|---|---|
| `T-V1110-OUT-01` | `out.py` | `render_table` over 200 generated row sets (mixed `int`/`str`/`None`, wide cells, U+1F600 cells): every line has the same `utf16_length`; `None` → `n/a`; numeric columns right-aligned, text left; a cell over `max_width` ends in `…` at `max_width`; the rule line is `-` only; width > 60 raises `ValueError` | — |
| `T-V1110-OUT-02` | `out.py` | `send_pre` over the real `TelegramClient` + `MockTransport`: one `sendMessage` body with key set exactly `{chat_id, text, parse_mode}` (+ `reply_markup` when given), `parse_mode == "HTML"`, `text` starts `<pre>` ends `</pre>`, `<script>&` in the body arrives as `&lt;script&gt;&amp;` | — |
| `T-V1110-OUT-03` | `out.py` | a registered sentinel secret containing `<` in the body is `***REDACTED***` in the payload and the raw secret is absent (redact before escape) | yes |
| `T-V1110-OUT-04` | `out.py` | a body whose entity-parsed length is 4097 units (built with escaped `&` so the raw text is longer) is fitted: whole lines dropped from the end, a final `… N more` line, exactly one `sendMessage`; a body of exactly 4096 units is sent unfitted | — |
| `T-V1110-OUT-05` | `out.py` | `MockTransport` answers the first `sendMessage` with 400 `can't parse entities`: exactly two requests, the second without `parse_mode`/`reply_markup` and with the plain body; two 400s → exactly two requests, `send_pre` returns `None` | yes |
| `T-V1110-OUT-06` | `out.py` | `inspect.signature(bot.TelegramClient.send_message).parameters` keys are `{self, chat_id, text}`; `_send` through `MockTransport` posts `{chat_id, text}`; `/status` and `/summary` through `process_update` leave no `parse_mode` in `FakeTelegram.sent_payloads`; `T-V1100-OUT-04`/`-05` still pass unamended (imported and called) | yes |
| `T-V1110-OUT-07` | `out.py` | `FakeTelegram.sent` keeps `(chat_id, text)` tuples for `send_message` and `send_message_html`; `sent_payloads`, `edited_payloads`, `callback_answers`, `commands_set` record the payload dicts; `fail_html_with` raises once | — |
| `T-V1110-STA-01` | `sta.py` | `/stats` through `process_update` over recorded `llm_calls` rows (the fixtures of `tests/test_v160_observability.py`): one table-path message; the ten paired-row labels and the four single-value labels present in order; `n/a`, `n/a (no pricing)`, `mixed` and the percent form present as cell content where the fixtures call for them | — |
| `T-V1110-STA-02` | `sta.py` | a `cost_basis` of 5,000 characters makes the body exceed 3,500 → whole lines dropped from the end, the header row kept, length ≤ 3,500 | — |
| `T-V1110-STA-03` | `sta.py` | README's `### /stats` block (`README.md:127-140`) contains every label of STA-01 including `Errors:` and `Summaries:`, in the renderer's order | — |
| `T-V1110-DOC-01` | `doc.py` | two documents (one PDF with pages, one `.md`) → one table-path body whose first line is `Your documents (2 of 20):`, columns `#`, `file`, `type`, `size`, `chunks`, `pages`, `added`; sizes `12.3 KB` / `1.5 MB`; `n/a` pages for the `.md`; a 40-character filename cut to 27 + `…`; an in-flight job for the caller adds `⏳ indexing <name> — embedding: 1/3` as the last line (T5) | — |
| `T-V1110-DOC-02` | `doc.py` | no documents → `DOCUMENTS_EMPTY_REPLY` on the plain path (no `parse_mode` in the payload) | — |
| `T-V1110-DOC-03` | `doc.py` | `/delete #<own id>` → `Deleted #<id>.`, row and vectors gone; `/delete #<other user's id>` → `No document named #<id>.`, nothing deleted; `/delete #abc` → same shape; `/delete <filename>` unchanged; bare → the new usage string | yes |
| `T-V1110-DOC-04` | `doc.py` | `DocxArchiveTooLargeError` → `Document too large (DOCX archive bounds).`; `PdfTooManyPagesError` → `Document too large (over 2,000 pages).`; `ExtractedTextTooLargeError` → `Document too large (over 2,000,000 characters).`; the status message kept (edited) | — |
| `T-V1110-SES-01` | `ses.py` | `list_conversations`: `id`, `created_at`, `active`, `message_count`, `last_activity`, `title` (first user message, whitespace-collapsed, 40 + `…`, `(empty)`); order `last_activity DESC`; `limit`; another user's rows absent; `SCHEMA_VERSION == 6`; `PRAGMA table_info(conversations)` has 4 columns; `count_conversations` | — |
| `T-V1110-SES-02` | `ses.py` | `activate_conversation`: own id → `True`, exactly one `active = 1` row for the user, the target; foreign id → `False`, the caller's active row unchanged, the owner's unchanged; missing id → `False`; the unique index still holds after 50 alternating switches | yes |
| `T-V1110-SES-03` | `ses.py` | `/sessions` with 12 conversations → one table-path body, 10 rows, `●` on the active row, `msgs` and `last` (`YYYY-MM-DD HH:MM`, `n/a` for an empty one), trailing `2 older sessions not shown`; with 3 → no trailing line | — |
| `T-V1110-SES-04` | `ses.py` | `/session <own id>` → `Switched to session #<id>: <title>`; the next text turn's `FakeLLM` request carries that conversation's messages and not the previous one's; `/session <foreign id>` and `/session 999` → `No session #<id>.`; `/session`, `/session x`, `/session 1 2` → usage; `agent.summarize_conversation` is not called and `summaries` has no new row | yes |
| `T-V1110-SES-05` | `ses.py` | `/new` reply equals `New conversation started (#<id>).` with the id `active_conversation_id` then returns | — |
| `T-V1110-CBQ-01` | `cbq.py` | `get_updates` body over `MockTransport` is `{"timeout": 50, "allowed_updates": ["message", "callback_query"], "offset": 41}` (amends `tests/test_telegram.py:272`); a `callback_query` update reaches `_handle_callback` and the message-only guard is not hit | — |
| `T-V1110-CBQ-02` | `cbq.py` | an intruder's callback: `callback_answers == [{"callback_query_id": …}]` (no `text`), `sent`/`edited_payloads` empty, `bot_state` unchanged, `FakeLLM.calls` empty, exactly one `unauthorized update` warning | yes |
| `T-V1110-CBQ-03` | `cbq.py` | a group chat, a bot sender, `message.chat.id != from.id` → ignored without an answer; the rate limiter at zero tokens → acknowledged with `RATE_LIMIT_REPLY`, nothing else; the cursor (`last_update_id`) written before any of it | yes |
| `T-V1110-CBQ-04` | `cbq.py` | for `mod:prov:lmstudio` the fake's call log shows `answer_callback_query` first and exactly once, then one `edit_message_html` | — |
| `T-V1110-CBQ-05` | `cbq.py` | parametrised over `zzz:prov:x`, `mod:zzz:1`, `mod:model:x`, `mod:model:99`, `mod:model:-1`, `mod:prov:openrouter` with OpenRouter unconfigured, `ses:switch:1`, a 65-byte data, `mod:model:１` (non-ASCII digit), `mod:model:1 OR 1=1`, `ses:switch:../x`: answered with the Expired text; no `bot_state` write; no `set_provider` call; no edit | yes |
| `T-V1110-CBQ-06` | `cbq.py` | `send_message_html`/`edit_message_html`/`answer_callback_query` over `MockTransport`: payload key sets exactly as CBQ-03; through the fake, a selection edits the `message_id` the menu was sent with and `sent` does not grow | — |
| `T-V1110-CBQ-07` | `cbq.py` | with a 200-character model id in `OPENROUTER_MODELS` every emitted `callback_data` matches `^(mod|ses):[a-z]+:[A-Za-z0-9_-]+$`, is ASCII and ≤ 64 bytes; button texts ≤ 32 characters | — |
| `T-V1110-MOD-01` | `mod.py` | bare `/model` → one table-path body with the `provider`, `override`, model and `failures` rows; keyboard = one button per configured provider + `auto` in one row; with LM Studio unconfigured its button is absent | — |
| `T-V1110-MOD-02` | `mod.py` | `mod:prov:openrouter` → the same message edited to `Models for openrouter:` + the catalogue lines + one button per model + `← back`; `mod:model:1` → `provider_override == "openrouter"`, `model_override:openrouter == <catalogue[1]>`, `set_provider` called with `"openrouter"`, the message edited to `Provider: openrouter, model: <m>` with no `reply_markup`; `mod:back:-` restores step 1 | — |
| `T-V1110-MOD-03` | `mod.py` | `mod:auto:-` and `/model auto` delete `provider_override` and every `model_override:*` row (two seeded), call `set_provider(None)`, and edit/reply `Provider override cleared.`; other `bot_state` keys untouched | — |
| `T-V1110-MOD-04` | `mod.py` | `/model lmstudio` → today's strings, no `model_override` write; `/model openrouter <catalogue model>` → both keys and `Provider switched to openrouter, model: <m>.`; `/model openrouter nope` → `Unknown model for openrouter; see /model`; `/model bogus` and `/model a b c` → the new usage string | — |
| `T-V1110-MOD-05` | `mod.py` | `load_config` with `OPENROUTER_MODELS=" b, a ,b,"` and `OPENROUTER_MODEL=a` → `("a", "b")`; unset → `("a",)`; with `OPENROUTER_MODEL=c` and `OPENROUTER_MODELS=a,b` → `("c", "a", "b")`; an empty default → `()`; `.env.example` carries `LMSTUDIO_MODELS=` and `OPENROUTER_MODELS=` lines, commented | — |
| `T-V1110-MOD-06` | `mod.py` | `model_override:openrouter = b` seeded → `build_llm_client(cfg, client=…, override="openrouter", model=load_model_override(conn, "openrouter")).describe() == ("openrouter", "b")`; through `agent` with a `FakeLLM` whose `describe()` is patched, `llm_calls.model` records `"b"`; a seeded `model_override:openrouter = nope` (not in the catalogue) → `describe()` reports the default | yes |
| `T-V1110-ING-01` | `ing.py` | `bot.DOCUMENT_MAX_BYTES == 20_000_000`; `file_size` 20,000,001 → `File too large (over 20 MB).`, no `get_file_calls`; 20,000,000 → accepted (`getFile` called); a 20,000,001-byte stream → `DocumentTooLarge` → the same string; `MAX_EXTRACTED_TEXT_CHARS == 2_000_000`, `PDF_MAX_PAGES == 2_000`, `INDEX_BUDGET_S_DEFAULT == 1800.0`; the DOCX bounds and `DOCUMENT_LIMIT` as at `295b01f`; `bot.py`'s source contains the v190 `find` line exactly once | — |
| `T-V1110-ING-02` | `ing.py` | `process_update` with a document returns with `status` sent (`📄 received`) and `index_document` not yet called (a spy); `worker.run_one()` then calls `getFile`, `download_file`, `index_document` and sends the success reply; the worker never receives the loop's `conn` (`storage.connect` monkeypatched to record its callers; `IngestWorker(...)` is constructed with `db_path`); no `_TypingIndicator` constructed; `started_at` is still the handler's first action; the five pre-checks reply synchronously with no job enqueued | — |
| `T-V1110-ING-03` | `ing.py` | a second document from the same user while the first is queued → `⏳ Still indexing <name>; wait for it to finish.`, queue length unchanged; another user's document is enqueued; after `run_one` the first user's next upload is accepted | yes |
| `T-V1110-ING-04` | `ing.py` | four queued jobs from four users → a fifth user's upload → `Indexing queue is full; try again later.`, no status message | yes |
| `T-V1110-ING-05` | `ing.py` | a `FakeEmbedder` hook sets the job's cancel event after batch 1 of 3 → `IndexCancelled` at the next checkpoint, `documents` and `vec_chunks` unchanged, the status edited to `❌ Cancelled.`, the slot freed; `/cancel` with a job → `Cancelling <name>…`; with none → `Nothing to cancel.`; a `run_one` whose job raises `RuntimeError` → `DOC_HANDLER_FAILED_REPLY` and the worker still processes the next job | yes |
| `T-V1110-EXT-01` | `ext.py` | `COMMANDS` names ≤ 32 chars without slash, descriptions ≤ 256 ASCII, every name dispatched by `process_update` (a probe update per name reaches its handler, not the model) and every dispatched command present; `main()`-level wiring: `set_my_commands` payload over `MockTransport` is `{"commands": [{"command", "description"}, …]}` in `COMMANDS` order; a 500 from `setMyCommands` → one warning and startup continues; `run_selftest()` leaves `commands_set` empty | — |
| `T-V1110-EXT-02` | `ext.py` | `/help` and `/start` → one table-path body each with the header `command  what it does` and one row per `COMMANDS` entry; `messages` gains no row | — |
| `T-V1110-EXT-03` | `ext.py` | README's `## Commands` section has a row for every `COMMANDS` name and `/reload_skills` precedes `/documents` (the amended `tests/test_v190_agents.py:226-235` form) | — |
| `T-V1110-PIN-01` | `pin.py` | no file under `tests/` (this file and the `git show <tag>:` blob-reading version tests excepted) contains the retired literals `"New conversation started."`, `over 10 MiB`, `over 500,000 characters`, `over 300 s`, `Usage: /model [lmstudio\|openrouter\|auto]"`, `10,485,760`, `"500 pages"`, `"300 s"`, `allowed_updates": ["message"]`; `docs/spec/task-briefs/v1110-T0.md` exists and names every site this test scans | yes |
| `T-V1110-PIN-02` | `pin.py` | README's `## Limits` rows carry `20,000,000`, `2,000,000`, `1800 s`, `2,000 pages`, `one job per user`, `/cancel`; the `## Error behaviour` rows carry ERR-01's seventeen strings (rows 1–16) — presence, never a frozen matrix | — |
| `T-V1110-MUT-01` | `mut.py` | the eight `v1110-*` ids are in `MUTATIONS` in §13's order; each `find` occurs exactly once in its `path` at `HEAD`; each `why` names its killing `T-V1110-*` test and that test exists; `len(MUTATIONS) == 152`; no `mutation-v1110` gate in `config/quality_gates.yaml` | — |
| `T-V1110-VER-01` | `ver.py` | the live tree's `pyproject.toml` `project.version == "1.11.0"` (the `v1.10.4` blob read is the repointed `tests/test_v1104_version.py`'s, not this test's) | — |
| `T-V1110-VER-02` | `ver.py` | `git diff v1.10.4 -- pyproject.toml uv.lock` is version-only under `dependency_diff_is_version_only`; the dependency lists equal the tag blob's | — |
| `T-V1110-VER-03` | `ver.py` | `AGENTS.md` carries T8's measured test count, `152 entries` and `as of spec-v1.11.0 T8`, not `2311`/`144 entries`; README's release table has a `v1.11.0 \| 1.11.0` row and the `v1.10.4` row no longer ends `; this release` | — |
| `T-V1110-VER-04` | `ver.py` | README: the `/documents` sample block, a `## Sessions` section, the `## Switch provider` paragraph naming `LMSTUDIO_MODELS` and `OPENROUTER_MODELS`, the ingest diagram line reads `embed (batched, OpenRouter by default)`, the batch-size paragraph names both `documents.EMBED_BATCH_SIZE` and `llm.embeddings.BATCH_SIZE`, the Limits row `indexing runs in a worker thread`; `AGENTS.md:274-279`'s waiver paragraph carries the v1.11.0 sentence | — |
| `T-V1110-SEC-01` | `sec.py` | SEC-01 clauses 1, 2, 4, 6, 7: the `<script>&</script>` filename and first message; the sentinel-secret title; the two hostile `callback_data` strings; no `open`/`Path.write_*` during `run_one`; `IngestWorker.__init__` signature `(cfg, tg, embedder, db_path)`; a worker log record with the sentinel is redacted by the root handler's formatter | yes |
| `T-V1110-ERR-01` | `err.py` | parametrised over ERR-01 rows 1–16: the trigger through the fakes produces the string verbatim; the string appears in README's `## Error behaviour` table | — |

---

## 12. Pins, mutation entries, gates, review and the stop route

**REQ-V1110-PIN-01 (MUST) — the frozen-pin inventory is T0, structural and
fail-closed; a late pin is a disclosed amendment.** Three releases were
stopped by pins the spec's list missed (`README.md:917`). T0 writes
`docs/spec/task-briefs/v1110-T0.md` — a table `site (file:line) | literal |
task that rewrites it | rewrite form` — by **grepping the live tree**, not
by copying this spec: every test asserting a literal this release changes,
starting from (and extending) this list: `NEW_CONVERSATION_REPLY`'s
literal (SES-03); `MODEL_USAGE_REPLY` (MOD-03); `DELETE_USAGE_REPLY`
(DOC-02); `File too large (over 10 MiB).`, `Document too large (over
500,000 characters).`, `Indexing timed out (over 300 s). Nothing was
saved.` (ING-01, DOC-03); the README limits literals `10,485,760` /
`500,000` / `300 s` / `500 pages` and the error-table strings
(`tests/test_v190_agents.py:238-280`, `README.md:828-833`, `:863-864`,
`:511-517`); every `/stats` line-shape assertion (`tests/test_observability.py`,
`tests/test_v160_observability.py`, `tests/test_pricing.py`; STA-01);
`Your documents (2):` (`tests/test_v190_commands.py:592`; DOC-01); the
`allowed_updates` body (`tests/test_telegram.py:272`; CBQ-01); the typing
ceiling test (`tests/test_v190_commands.py:503`; ING-05); the `/model`
reply strings in `tests/test_v1_guardrails.py` and `tests/test_failover.py`
(unchanged strings — listed to prove they were checked); the README
commands-order pin (`tests/test_v190_agents.py:226-235`; EXT-01);
`AGENTS.md`'s `2311` and `144 entries` lines (`tests/test_v190_agents.py:134-152`;
VER-01, T8); `config/quality_gates.yaml:790`'s `report_path` and its two
pins (`tests/test_v170_bench.py:327`, `tests/test_v1104_gates.py:209`;
VER-03); the gate-matrix reader (`tests/test_v15_standards.py:1824`;
REV-02); `spec-v1.md:135`'s "exactly five commands" (docs only — noted,
not edited). Plus the measurements: the collected count (EC-03),
`len(MUTATIONS)` = 144, the exact-once occurrence of the v190 `find`
string (ING-01), the override count (EC-05). **Rule**: a pin discovered
after T0 is a **disclosed amendment** — recorded in the discovering
task's commit body and the report's per-task bullet with its `file:line`
and rewrite — not a repair cycle, not a stop, no budget consumed.
**Rewrite form** (the v1.10.4 rule, `README.md:918`): presence,
contiguity and order — never equality with a frozen matrix; counts read
from the live tree; a test is renamed only when its name carries the
retired literal. `T-V1110-PIN-01` (negative), `T-V1110-PIN-02`.

**REQ-V1110-MUT-01 (MUST) — eight `v1110-*` entries; `mutation-all` at
152; the gate-6 wall.** Appended to `MUTATIONS` (`devtools/mutation_check.py:49`)
in T7, in this order, each with a `find` that occurs exactly once in its
`path`, a `replace`, and a `why` naming the killing test:

| id | path | `find` (the mechanism) → `replace` | killed by |
|---|---|---|---|
| `v1110-callback-allowlist-dropped` | `bot.py` | the callback branch's `if from_id not in cfg.allowed_tg_ids:` → `if False:` | `T-V1110-CBQ-02` |
| `v1110-activate-ownership-dropped` | `storage.py` | `activate_conversation`'s `WHERE id = ? AND tg_user_id = ?` → `WHERE id = ? AND 1 = ?` with the bound user replaced by `1` (the foreign row becomes switchable) | `T-V1110-SES-02` |
| `v1110-table-path-escape-dropped` | `bot.py` | `html.escape(redact(body), quote=False)` → `redact(body)` | `T-V1110-OUT-02` |
| `v1110-agent-reply-gains-parse-mode` | `bot.py` | `{"chat_id": chat_id, "text": text})` in `send_message` → the same dict with `"parse_mode": "HTML"` | `T-V1110-OUT-06` |
| `v1110-inflight-guard-dropped` | `bot.py` | the loop's `if worker.in_flight(from_id) is not None:` → `if False:` | `T-V1110-ING-03` |
| `v1110-cancel-flag-ignored` | `documents.py` | `_check_budget`'s `if cancel is not None and cancel.is_set():` → `if False:` | `T-V1110-ING-05` |
| `v1110-model-index-unbounded` | `bot.py` | `if not 0 <= idx < len(catalogue):` → `if False:` | `T-V1110-CBQ-05` |
| `v1110-document-cap-tenfold` | `bot.py` | `DOCUMENT_MAX_BYTES = 20_000_000` → `DOCUMENT_MAX_BYTES = 200_000_000` (its own line; the v190 `if` line untouched) | `T-V1110-ING-01` |

The exact `find` strings are copied from the landed source into
`v1110-T7.md` before the entries are written, never retyped. T7 verifies
each in isolation (`--only <id>`: mutate → red → revert), then runs
`mutation-all` once, **alone on the box** (EC-07), records **152/152
killed** and the direct wall `W`. The v1.10.4 reference is the gate's
`timeout_seconds: 1640` (`config/quality_gates.yaml:745`); when `W >
1300` T7 raises `timeout_seconds` to `ceil_to_100(1.25 × W)` in a dated
comment hunk (the `spec-v1.10.4.md` T4 calibration form) under the same
brief and re-runs gate 6 once on that tree; **a `W` over 2400 s is
reported, not a stop**. `[[VERIFY: the measured `mutation-all` wall —
confirmation is the wall printed by the direct run pasted into the report
with `152/152`; over 2400 s the report flags it in its gate table and the
release proceeds]]`. `AGENTS.md`'s count line echoes 152 in T8 (VER-01).
`T-V1110-MUT-01`.

**REQ-V1110-REV-01 (MUST) — review in a clean context, before the gates
that matter.** Code review by the `code-reviewer` subagent
(`.claude/agents/code-reviewer.md:4`, `model: sonnet`) in **its own clean
context** at T7 — after every code task (T1–T6) and after T7's mutation
entries, before T7's gate run. Never self-review in the writing context.
Findings are fixed (delegated by brief `v1110-T7.md` when they write
source) or waived with a reason in the report; the review prompt is
logged. Beyond the standard checklist and the test-independence checklist:
(1) `send_pre` is the only production site with `parse_mode`; `send_message`'s
signature and body byte-unchanged; (2) `activate_conversation` is one
`BEGIN IMMEDIATE` … `COMMIT`/`ROLLBACK` and the second `UPDATE` carries
`tg_user_id`; (3) every `<pre>` body passes `redact` then `html.escape`;
(4) `_handle_callback` acknowledges once, first; every stale branch
returns before any write; (5) the worker owns its connection, takes no
`conn`, and every ERR-01 clause of `bot.py:1405-1468` reappears in
`run_one` in the same order; (6) `SYSTEM_PROMPT`, `tools.tool_specs()`,
`REQUEST_DEFAULTS`, `load_context_messages`, gate 5, gate 7,
`devtools/agent_eval.py`'s datasets are byte-unchanged (NG-11, NG-14);
(7) each of the eight `find` strings matches once and its killing test
is named; (8) no new dependency; `SCHEMA_VERSION == 6`; (9) every new
string is in ERR-01 and README.

**REQ-V1110-REV-02 (MUST) — the gates: all eight, gate 8 once, the
identity check, the matrix.** The eight gate commands of `AGENTS.md:150-158`
verbatim, in order. **T0**: gates 1–5 on the unchanged tree (gate 5
proves the LM Studio address; unreachable → blocked run, EC-05). **Every
task T1–T6**: gates 1–4 green at its commit. **T7**, after the review
fixes and the mutation entries are committed (the source commit, EC-05's
first exception): `tested_tree=$(git rev-parse HEAD)` and an empty `git
status --porcelain` recorded; gates 1–5, gate 6 (MUT-01's direct run),
gate 7, `checks.py doctor`, `checks.py lint-docs`, then **gate 8 exactly
once**, as the task's last live action, with EC-05's override count `0`
re-read just before it; then T7's report-only commit. Gate 8 red on model
behaviour (exit 1) is the stop route, not a repair cycle; exit 2 from an
unreachable route is a blocked run; exit 2 from construction is a repair
cycle on the runner's inputs only. **T8**: gates 1–4 and 6 fresh on the
tree that ships; gate 5 fresh (no tokens); **gates 7 and 8 reused from T7
under the dependency identity check** — `git diff <tested_tree> HEAD --
$(uv run --locked python devtools/agent_eval.py --print-dependencies)`
classified by `dependency_diff_is_version_only` (`devtools/agent_eval.py:1279`
and its regex constants at `:1251-1256`): `True` → reused, recorded against `tested_tree`; `False`
→ gate 8 runs again once (and gate 7 with it). `[[VERIFY: GATE8_DEPENDENCIES
does not include `tests/` — at `295b01f` it is the root `*.py` glob, `llm/`,
`devtools/agent_eval.py`, `evals/agent/`, `config/quality_gates.yaml`,
`pyproject.toml`, `uv.lock` (`devtools/agent_eval.py:1234-1242`), so T8's
test edits (`tests/test_v1110_ver.py`, `tests/test_v1104_version.py`,
`tests/test_v190_agents.py`) and its docs edits are outside the manifest
and its `pyproject.toml`/`uv.lock` hunks are the version lines — the
verdict is `True`; confirmation = the printed manifest in T8's report and
the verdict line; a `False` verdict means T8 touched a root `*.py` or
`llm/` — forbidden by VER-01 — and is a repair cycle that reverts that
hunk, not a re-run]]`. `tables.py` is in the manifest, which is why gate 8
runs after T1 lands it (T7), never before. The `full` profile is never
invoked as a whole. **The gate matrix** — read by `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
(`tests/test_v15_standards.py:1824`, repointed to this file in T6) and by
`tests/test_v1104_gates.py:136-144` (which stays on `spec-v1.10.4.md`,
its own pin): every profile, every gate, unchanged membership,
`mutation-all` at 152 entries (144 → 152); load-bearing markup, in this
file exactly once.

| gate | pre-commit | pre-push | full |
|---|:---:|:---:|:---:|
| `ruff check` (staged) | yes | — | — |
| `ruff check .` (tree) | — | yes | yes |
| `ruff format --check` (staged) | yes | — | — |
| `ruff format --check` (tree) | yes | yes | yes |
| branch-name check | yes | yes | yes |
| `gitleaks git --staged` | yes | — | — |
| `gitleaks dir` (tree) | — | yes | yes |
| `uv sync --locked` | — | — | yes |
| `pytest` | — | yes | yes |
| `bot.py --selftest` | — | yes | yes |
| `bot.py --selftest-live` | — | — | yes |
| `rag_eval.py` | — | — | yes |
| `agent_eval.py` | — | — | yes |
| `mutation_check.py --select v15-` | — | — | — |
| `mutation_check.py --select v160-` | — | — | — |
| `mutation_check.py --select v170-` | — | — | — |
| `mutation_check.py --select v180-` | — | — | — |
| `mutation_check.py --select v190-` | — | — | — |
| `mutation_check.py --select v1100-` | — | — | — |
| `mutation_check.py --select v1101-` | — | — | — |
| `mutation_check.py --select v1102-` | — | — | — |
| `mutation_check.py --select v1103-` | — | — | — |
| `mutation_check.py` (all) | — | yes | yes |
| `trivy fs` | — | yes | yes |
| `semgrep scan` | — | yes | yes |
| `skylos` | — | yes | yes |
| `install_hooks.py --check` | — | yes | yes |
| `checks.py doctor` | — | yes | yes |
| `checks.py lint-docs` | — | — | yes |

**REQ-V1110-REV-03 (MUST) — the stop route.** A stop at any task before
T8 (an exhausted repair budget, gate 8 exit 1, a spec ambiguity under
EC-02): (1) `docs/reports/report-v1.11.0.md` and `docs/reports/tg-post-v1.11.0.md`
finalised with the stop stated (stage, task, cause, the gate capture
quoted); (2) gates 1–4 re-run on the stopped tree; gates 5–8 not touched
(the recorded results reused or `N/A`); (3) no version bump (`pyproject.toml`
still `1.10.4`), no tag (`git tag -l v1.11.0` empty); (4) README's release
table gains a `v1.11.0 | — | run stopped at T<n> …` row in the form of the
four `README.md:914-917` precedents; (5) `docs/llm-usage.md` rows and the
ledger block filled; (6) the evidence commit touches `docs/reports/*`,
`README.md`'s one row and `docs/llm-usage.md` only; `lint-docs` and
`gitleaks-tree` green against it; no `--no-verify`; no later task runs.
Gherkin has no scenario for the stop route; the report's stop section is
its artefact.

---

## 13. Version, reporting and the ledger

**REQ-V1110-VER-01 (MUST) — 1.11.0, and where the bump lives.**
`pyproject.toml:3` moves `1.10.4` → `1.11.0` in **T8 and nowhere else** —
after T7's gates are green — so a stop at any earlier point needs no
revert. In T8's first commit (brief `v1110-T8.md`): `uv lock` regenerates
`uv.lock` for the version literal only (the diff touches the project's own
entry; `T-V1110-VER-02`); `tests/test_v1110_ver.py` (`T-V1110-VER-01…04`,
red before the edit, green after — the live tree's `pyproject.toml` ==
`"1.11.0"` is asserted there and nowhere else); `tests/test_v1104_version.py:42-53`
repointed exactly so: at `295b01f` that test performs two reads — the
live tree (`pyproject.toml` == `"1.10.4"`, `:43`) and `git show
v1.9.5:pyproject.toml` == `"1.9.5"` (`:46-52`); T8 replaces **only** the
live-tree read with `git show v1.10.4:pyproject.toml` == `"1.10.4"`, the
`v1.9.5` assertion stays as is, and its `_BASELINE_COMMIT` diff test
`:55-78` is kept as the historical fact it already is; `tests/test_v190_agents.py:134-152`
renamed `test_t_v1110_ver_03_agents_md_count_lines_landed_at_t8` with the
two literals moved to T8's numbers and one history sentence added;
`README.md`'s release table (`README.md:897-918`) gains the `v1.11.0`
row and the `v1.10.4` row loses its `; this release` clause; `AGENTS.md`
echoes the numbers (`:161`, `:172`: the T8-measured test count, `152
entries as of spec-v1.11.0 T8`, the brief path `v1110-T<N>.md` at `:95`).
T8's second commit is the evidence-only commit (`docs/reports/*` and
nothing else); `lint-docs` and `gitleaks-tree` re-run against it; the
annotated tag `v1.11.0` goes on **that** commit, only on green, as the
run's last action; **no push** (`git status -sb` shows `ahead`; the
report records it). Existing tags stay.

**REQ-V1110-VER-02 (MUST) — the documentation deliverables inside the
run.** README: the Commands table (`README.md:106-119`: new rows
`/sessions`, `/session <id>`, `/cancel`, `/help` (`/start`), the `/model`
row's usage and the `/delete` row's `#<id>` form, the `/documents` row's
real columns) [T6]; the `/stats` sample (`:127-140`) replaced by STA-01's
rendering **including the `Errors:` and `Summaries:` lines** [T2]; a
`/documents` sample after it [T2]; a `## Sessions` section between
`## Commands` and `## Observability` (what a session is, `/sessions`,
`/session`, that `/new` prints the id, that a switch does not summarise)
[T3]; `## Switch provider` (`:237-266`): the menu, the text form, the
paragraph naming `LMSTUDIO_MODELS` / `OPENROUTER_MODELS` (MOD-04), "the
override is global" [T4] — the `:75-91` table is not touched; `## Documents
(RAG)` limits (`:806-837`): `20 MB (DOCUMENT_MAX_BYTES = 20,000,000
bytes)`, `2,000,000 characters`, `1800 s … indexing runs in a worker
thread; one job per user; /cancel`, `2,000 pages`; `### Limitations`
(`:494-517`): the worker paragraph and NG-07's BM25 note; `## Error
behaviour` (`:839-874`): ERR-01's rows [T5]; the embeddings diagram line
(`:400`, "LM Studio" → "OpenRouter by default") and the batch-constant
sentence (`:436-437`: both `documents.EMBED_BATCH_SIZE` and
`llm.embeddings.BATCH_SIZE` are 32 and independent — document, do not
refactor) as carried one-hunk fixes [T5]; the `## Versioning` release row
[T8]. `AGENTS.md`: the count lines and the brief path [T8]; the benchmark
waiver sentence (`:274-279`) [T6]; the layout line for `tables.py` [T1];
the env-vars paragraph [T4]. `docs/plan.md` untouched (NG-10). `.env.example`
[T4]. `T-V1110-STA-03`, `T-V1110-PIN-02`, `T-V1110-EXT-03`, `T-V1110-VER-04`.

**REQ-V1110-VER-03 (MUST) — the report, the post, the usage rows, the
ledger.** `standards/reporting.md`'s required fields, plus: (1) the
eight-gate table `| # | Gate | Exit | Wall |` recorded for T0, T7 (with
`tested_tree`, the empty `git status --porcelain`, the override count, the
gate-6 wall `W` and the 152/152 line, the gate-8 capture in full) and T8
(gates 1–6 fresh; 7 and 8 reused with the printed manifest and the
`dependency_diff_is_version_only` verdict); (2) the collection check
(EC-03: floor, final count, the ≥ floor + 49 verdict); (3) the delegation
record — a table `task | delegated? | to what` naming, for every `no`,
one of the four §5.1 exemptions verbatim, and map-versus-actual per task
(EC-04); (4) the pin record — T0's inventory table and every disclosed
amendment (PIN-01, EC-02) with `file:line`; (5) each task's "failed
first" record (EC-02); (6) the review's findings and their disposition
(REV-01); (7) the `--no-verify` attestation and the "no push" line; (8)
the executor model named in the report, in every `docs/llm-usage.md` row
(146 upward, one per prompt, the `| N | what | model | tokens | cost |`
shape of rows 142–145) and in the tg-post; (9) the Telegram post
`docs/reports/tg-post-v1.11.0.md` in Russian, ≤ 1500 characters, linking
`https://github.com/axyi/tg-agent-bot` and the spec/report paths; (10)
the ledger-row block (`checks.py lint-docs`'s `Ledger row (paste into …)`
section, `ledger_header` verbatim from `config/quality_gates.yaml:791`)
— the operator appends it to the lab's `economics.md` after row 31 (the
project's rows are found by name, never by `tail`). `config/quality_gates.yaml:790`
`report_path` → `docs/reports/report-v1.11.0.md` in T6, with
`tests/test_v170_bench.py:316-331` and `tests/test_v1104_gates.py:206-215`
repointed and renamed `…_v1110_rpt_01…` (PIN-01); `lint-docs` is green
against the T0 skeleton from T6 on.

---

## 14. Implementation order

Nine tasks, one prompt each (236…244), one commit each except T7 and T8
(two, EC-05); tests before the code they cover, in the same task; each
task rewrites the pins T0 assigns to it (PIN-01) and runs gates 1–4.

| T | task | acceptance |
|---|---|---|
| **T0** | Preconditions (EC-05: tree, `.env` by exit status, the `sed` only when `go` names an address, the override count), gates 1–5 on the unchanged tree, the measurements (collected count = floor, `len(MUTATIONS)` 144, the v190 `find` once), **the pin inventory brief `v1110-T0.md`** (PIN-01), `docs/prompts/236-go-spec-v1.11.0.md`, the `report-v1.11.0.md` skeleton with the ledger block | every item recorded; gate 5 green (else blocked); `git diff --exit-code` clean afterwards |
| **T1** | §3: `tables.py` (`render_table`, `fit_lines`, `utf16_length`), `send_pre`, the three `TelegramClient` methods (CBQ-03), OUT-04's fallback, OUT-05's fakes. `T-V1110-OUT-01…07` | green; `T-V1100-OUT-04`/`-05` unamended and green; `bot.py --selftest` green |
| **T2** | §4, §5: `/stats` table, `/documents` table (without the in-flight line), `/delete #<id>`, DOC-03's wording; README `/stats` and `/documents` samples. `T-V1110-STA-01…03`, `T-V1110-DOC-01…04` (DOC-01's in-flight clause deferred to T5) | green; the 43 `/stats` pins rewritten |
| **T3** | §6: the storage helpers, `/sessions`, `/session`, `/new`'s reply; README `## Sessions`. `T-V1110-SES-01…05` | green; `SCHEMA_VERSION` 6; the five `NEW_CONVERSATION_REPLY` pins rewritten |
| **T4** | §7, §8: `allowed_updates`, the callback branch and guards, `_handle_callback`, the `/model` menu, the text form, `config.py`'s two fields, `load_model_override`, `build_llm_client(model=)`, `set_provider`; `.env.example`, README's `## Switch provider` paragraph, `AGENTS.md`'s env paragraph. `T-V1110-CBQ-01…07`, `T-V1110-MOD-01…06` | green; `tests/test_telegram.py:272` rewritten; `/model lmstudio`'s strings unchanged |
| **T5** | §9: the caps and strings, `IngestWorker`, the loop split, `/cancel`, `IndexCancelled`, DOC-01's in-flight line, the typing-indicator pin; README limits/error/limitations rows, the diagram and batch-constant fixes. `T-V1110-ING-01…05`, `T-V1110-ERR-01`, `T-V1110-SEC-01` (its worker clauses) | green; the v190 `find` line untouched and once; `T-V190-SEC-04b` green |
| **T6** | §10, §11.2's remaining clauses, §13's docs: `COMMANDS`, `setMyCommands`, `/help`, `/start`; README Commands table; the waiver sentence; `report_path` repoint and its pins; the matrix reader repoint; `T-V1110-PIN-01`, `-02`, `T-V1110-EXT-01…03`, the rest of `T-V1110-SEC-01` | green; `lint-docs` green against the skeleton; `doctor` green |
| **T7** | §12: the eight `v1110-*` entries (each verified in isolation), `T-V1110-MUT-01`; **the review (REV-01)** and its fixes; the source commit; then `tested_tree`, gates 1–7 (gate 6 alone, `W` recorded, the timeout hunk if `W > 1300`), `doctor`, `lint-docs`, **gate 8 once**; the report-only commit | 152/152 killed with `W`; review findings closed or waived; gate 8 exit 0 with floors met, recorded against `tested_tree`; exit 1 → the stop route |
| **T8** | §13: the bump commit (VER-01: `pyproject.toml`, `uv lock`, `tests/test_v1110_ver.py`, `tests/test_v1104_version.py`'s live-tree read alone repointed to `git show v1.10.4:pyproject.toml` == `"1.10.4"` (its `v1.9.5` assertion kept), `tests/test_v190_agents.py:134-152` renamed, README release row, `AGENTS.md` lines), gates 1–6 fresh, gate 5 fresh, the identity check for 7/8, the collection check, `replay --range <base>..HEAD`, Appendix B replayed; then the evidence-only commit, `lint-docs`, `gitleaks-tree`, the tag; **no push** | `T-V1110-VER-01…04` red before, green after; verdict `True` (else one re-run); count ≥ floor + 49; the evidence commit's `git show --stat` names `docs/reports/*` only; `git tag -l v1.11.0` non-empty; `git status -sb` `ahead` |

### 14.1 Per-task reading map

The authority for EC-04's thresholds; §1, §2 and §12 bind every task. A
`no` cell carries a §5.1 exemption **verbatim**; crossing the map live
forces delegation; the report records map versus actual.

| T | spec sections | repository files and ranges | delegate? |
|---|---|---|---|
| **T0** | §1, §12 (PIN-01), §14 | `AGENTS.md:148-175`, `:256-279`; `config/quality_gates.yaml:7-31`, `:737-746`, `:790`; `tests/test_v190_agents.py:134-152`, `:226-280`; the grep hits PIN-01 lists (line context only); `docs/prompts/TEMPLATE.md`; `pyproject.toml:1-21` | no — *commands only* for the measurements and gates (no file writes), *artefacts only* for the brief, the prompt file and the skeleton (prose no gate compiles, imports or runs) |
| **T1** | §3, §11 | `bot.py:44-58`, `:142-269`, `:287-312`, `:1500-1511`; `tests/fakes.py:143-202`; `tests/test_v1100_sanitization.py:293-323`; `tests/test_telegram.py:20-75`; `tables.py`, `tests/test_v1110_out.py` (created) | **yes** — brief `v1110-T1.md` |
| **T2** | §4, §5, §11 | `bot.py:58`, `:81-97`, `:926-928`, `:947-953`, `:1132-1241`, `:1425-1497`; `documents.py:378-381`; `storage.py:1081-1119`; `tests/test_observability.py`, `tests/test_v160_observability.py`, `tests/test_pricing.py` (the inventoried lines ±5); `tests/test_v190_commands.py:555-720`; `README.md:106-140`; `tests/test_v1110_{sta,doc}.py` (created) | **yes** — brief `v1110-T2.md` (T0's `/stats` pin rows copied in) |
| **T3** | §6, §11 | `storage.py:21`, `:238-276`, `:632-662`, `:721-768`, `:1218-1245`; `bot.py:66`, `:896-956`, `:1019-1048`; `tests/test_telegram.py`, `tests/test_summary.py`, `tests/test_v1100_red_team.py` (the five inventoried lines ±5); `README.md:106-125`; `tests/test_v1110_ses.py` (created) | **yes** — brief `v1110-T3.md` |
| **T4** | §7, §8, §11 | `bot.py:56`, `:71`, `:220-224`, `:813-861`, `:891-953`, `:1248-1283`, `:759-761`, `:1565-1566`, `:2058`, `:2077-2081`; `config.py:26`, `:108-110`, `:355-366`, `:525-540`; `llm/__init__.py:22-110`; `agent.py:1047-1100`; `storage.py:1425-1439`; `.env.example:1-20`; `README.md:237-266`; `tests/test_telegram.py:265-282`; `tests/test_failover.py`, `tests/test_v1_guardrails.py` (the `/model` hits ±5); `tests/test_v1110_{cbq,mod}.py` (created) | **yes** — brief `v1110-T4.md` (the grammar table and the verb list copied in) |
| **T5** | §9, §5 (DOC-01's line), §11 | `bot.py:76-97`, `:243-269`, `:345-431`, `:433-470`, `:863-881`, `:1311-1468`, `:1514-1591`, `:1669-1716`, `:1996-2010`, `:2130-2145`; `documents.py:104-110`, `:378-381`, `:404-436`, `:453-563`; `storage.py:455`, `:1051-1070`; `llm/embeddings.py:31-135`; `tracing.py:260-290`; `tests/test_v190_commands.py:167-180`, `:336-372`, `:454-520`, `:827-900`, `:976-1010`, `:1178-1200`, `:1306-1312`; `tests/test_v190_agents.py:238-280`; `README.md:391-410`, `:428-440`, `:494-517`, `:806-874`; `tests/test_v1110_{ing,err,sec}.py` (created) | **yes** — brief `v1110-T5.md` (the thread-safety reading and the ERR-01 rows copied in) |
| **T6** | §10, §11.2, §12 (PIN-01, REV-02's matrix), §13 (VER-02, VER-03) | `bot.py:896-956`, `:2054-2062`; `tests/test_v190_agents.py:226-235`; `tests/test_v15_standards.py:1820-1830`; `tests/test_v170_bench.py:316-331`; `tests/test_v1104_gates.py:206-215`; `config/quality_gates.yaml:785-792`; `README.md:106-121`; `AGENTS.md:266-279`; `tests/test_v1110_{ext,pin}.py` (created) | **yes** — brief `v1110-T6.md` |
| **T7** | §12 (MUT-01, REV-01, REV-02) | `devtools/mutation_check.py:40-61` and its tail (`main()`); the eight landed lines the `find` strings target; `config/quality_gates.yaml:737-746` (the timeout hunk only); the review's own reading map; `tests/test_v1110_mut.py` (created) | **yes** for the entries and any review fix — brief `v1110-T7.md`; **no** for the review half — *the task is itself the clean-context review*; **no** for the gate run and the report-only commit — *commands only* |
| **T8** | §13, §12 (REV-02's T8 half) | `pyproject.toml:3`; `tests/test_v1104_version.py`, `tests/test_v190_agents.py:134-152`; `README.md:897-918`; `AGENTS.md:92-97`, `:159-172`; `tests/test_v1110_ver.py` (created); this run's artefacts | **yes** for the bump commit — brief `v1110-T8.md`; **no** for the evidence commit — *artefacts only* |

---

## Appendix A — requirement traceability

Every `MUST` appears exactly once; the **forty-four** rows are in
bijection with the forty-four `MUST` ids of §§1–13. NON-GOALs live in §2.
"Verified by" names a test id, a Gherkin scenario, a mutation id or a
recorded artefact — never "by inspection".

| Requirement | Verified by |
|---|---|
| `REQ-V1110-EC-01` — boundary, zero dependencies, the network list, the repair budget | `T-V1110-VER-02`; the report's gate tables and `.env` exit-status record |
| `REQ-V1110-EC-02` — test-first; the ≤ 5-line drift rule | the report's per-task "failed first" and amendment records |
| `REQ-V1110-EC-03` — the floor; ≥ floor + 49 at T8; no deletions | the T0 and T8 collection counts in the report; `T-V1110-VER-03` |
| `REQ-V1110-EC-04` — delegation by brief file; the map; verbatim exemptions | §14.1; the committed `v1110-T<n>.md` briefs; the delegation record |
| `REQ-V1110-EC-05` — preconditions, the override count, the address `sed`, prompts from 236, the two-commit exceptions | the report's precondition section; `replay --range`; the attestation |
| `REQ-V1110-EC-06` — secrets: names only, redacting loggers | `T-V1110-SEC-01` (clause 7); `gitleaks-tree` on the evidence commit |
| `REQ-V1110-EC-07` — the order; gates 6/7/8 sequential; the bump only at T8 | `replay --range`; `pyproject.toml` reading `1.10.4` until T8; the gate-table timestamps |
| `REQ-V1110-OUT-01` — `send_pre`: payload, escape order, no split, the five commands | `T-V1110-OUT-02`, `T-V1110-OUT-03`, `T-V1110-OUT-04`; `E1` |
| `REQ-V1110-OUT-02` — the agent-reply path unchanged; the pin narrowed | `T-V1110-OUT-06`; `v1110-agent-reply-gains-parse-mode` |
| `REQ-V1110-OUT-03` — `render_table` in `tables.py`; ≤ 60 units; equal lines | `T-V1110-OUT-01`; `T-V1110-SEC-01` |
| `REQ-V1110-OUT-04` — one plain resend on a 400 | `T-V1110-OUT-05`; `E1` |
| `REQ-V1110-OUT-05` — the fakes grow, compatibly | `T-V1110-OUT-07` |
| `REQ-V1110-STA-01` — `/stats` as a table; content semantics preserved | `T-V1110-STA-01`, `T-V1110-STA-02`, `T-V1110-STA-03`; `E11` |
| `REQ-V1110-DOC-01` — the `/documents` table; the in-flight line | `T-V1110-DOC-01`, `T-V1110-DOC-02`; `T-V1110-SEC-01` |
| `REQ-V1110-DOC-02` — `/delete #<id>` | `T-V1110-DOC-03`; `E4` |
| `REQ-V1110-DOC-03` — the refusal wording split | `T-V1110-DOC-04`; `T-V1110-ERR-01` |
| `REQ-V1110-SES-01` — the helpers; derived titles; schema 6 | `T-V1110-SES-01`, `T-V1110-SES-02`; `v1110-activate-ownership-dropped` |
| `REQ-V1110-SES-02` — `/sessions` | `T-V1110-SES-03`; `T-V1110-SEC-01` |
| `REQ-V1110-SES-03` — `/session <id>`; `/new` names its id; no summary | `T-V1110-SES-04`, `T-V1110-SES-05`; `E2`, `E3` |
| `REQ-V1110-CBQ-01` — the plumbing; the guards; the intruder | `T-V1110-CBQ-01`, `T-V1110-CBQ-02`, `T-V1110-CBQ-03`; `v1110-callback-allowlist-dropped`; `E5` |
| `REQ-V1110-CBQ-02` — ack once, first; the grammar; stale data | `T-V1110-CBQ-04`, `T-V1110-CBQ-05`, `T-V1110-CBQ-07`; `v1110-model-index-unbounded`; `E6` |
| `REQ-V1110-CBQ-03` — keyboards on the table path; edit the same message; the client methods | `T-V1110-CBQ-06` |
| `REQ-V1110-MOD-01` — step 1 | `T-V1110-MOD-01`; `E7` |
| `REQ-V1110-MOD-02` — step 2; two keys; `auto` clears both | `T-V1110-MOD-02`, `T-V1110-MOD-03`; `E7` |
| `REQ-V1110-MOD-03` — the text form; the usage string | `T-V1110-MOD-04`; `E8` |
| `REQ-V1110-MOD-04` — the env allowlist catalogue | `T-V1110-MOD-05` |
| `REQ-V1110-MOD-05` — the override reaches the client; `llm_calls.model`; the gate precondition | `T-V1110-MOD-06`; the T0/T7 override counts in the report |
| `REQ-V1110-ING-01` — the caps; the `find` line survives | `T-V1110-ING-01`; `v1110-document-cap-tenfold`; `E9` |
| `REQ-V1110-ING-02` — `IngestWorker`; own connection; `run_one` | `T-V1110-ING-02`; `E10` |
| `REQ-V1110-ING-03` — one job per user; the bounded queue | `T-V1110-ING-03`, `T-V1110-ING-04`; `v1110-inflight-guard-dropped`; `E13` |
| `REQ-V1110-ING-04` — cooperative cancel | `T-V1110-ING-05`; `v1110-cancel-flag-ignored`; `E11` |
| `REQ-V1110-ING-05` — the budget; no typing indicator; vectors; shutdown | `T-V1110-ING-01`, `T-V1110-ING-02`; the report's shutdown note |
| `REQ-V1110-EXT-01` — `COMMANDS`; `setMyCommands` non-fatal | `T-V1110-EXT-01`, `T-V1110-EXT-03`; `E12` |
| `REQ-V1110-EXT-02` — `/help`, `/start` | `T-V1110-EXT-02` |
| `REQ-V1110-ERR-01` — the matrix | `T-V1110-ERR-01` |
| `REQ-V1110-SEC-01` — escape, callbacks, no writes, no new hosts, the worker's isolation, redacting logs | `T-V1110-SEC-01`; `v1110-table-path-escape-dropped` |
| `REQ-V1110-PIN-01` — the T0 inventory; disclosed amendments; the rewrite form | `T-V1110-PIN-01`, `T-V1110-PIN-02`; the brief `v1110-T0.md`; the report's pin record |
| `REQ-V1110-MUT-01` — eight entries; 152; the wall | `T-V1110-MUT-01`; the 152/152 line and `W` in the report |
| `REQ-V1110-REV-01` — the clean-context review | the logged review prompt; the findings table |
| `REQ-V1110-REV-02` — all eight gates; gate 8 once; the identity check; the matrix | the T0/T7/T8 gate tables; the printed manifest and verdict; `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` |
| `REQ-V1110-REV-03` — the stop route | the report's stop section (when taken); `git tag -l` empty |
| `REQ-V1110-VER-01` — 1.11.0 at T8; the tag; no push | `T-V1110-VER-01`, `T-V1110-VER-02`, `T-V1110-VER-03`; `git status -sb` |
| `REQ-V1110-VER-02` — the documentation deliverables | `T-V1110-VER-04`; `T-V1110-STA-03`; `T-V1110-PIN-02`; `T-V1110-EXT-03` |
| `REQ-V1110-VER-03` — report, post, usage rows, ledger | `checks.py lint-docs`; the report's sections 1–10 |

---

## Appendix B — acceptance scenarios (Gherkin, written before code)

Thirteen scenarios, `E1`–`E13` (`E11` is shared by STA-01 and ING-04 as
marked); every one runs offline against the fakes, a
`tmp_path` database and `httpx.MockTransport` where a payload is asserted.

```gherkin
Feature: the table path
  Scenario: E1 a table-path 400 falls back to one plain resend
    Given MockTransport answers the first sendMessage with 400 "can't parse entities"
    When send_pre delivers a /stats body
    Then exactly two requests were posted, the second without parse_mode or reply_markup

Feature: sessions
  Scenario: E2 switching to an own session
    Given user U has conversations 1 (active) and 2 with two messages each
    When U sends "/session 2"
    Then the reply is "Switched to session #2: <title of 2>"
    And the next FakeLLM request carries conversation 2's messages only
    And no summary was written
  Scenario: E3 switching to a foreign session changes nothing
    Given conversation 7 belongs to user V
    When U sends "/session 7"
    Then the reply is "No session #7." and U's active row is unchanged
  Scenario: E4 deleting by id is owner-scoped
    When U sends "/delete #<V's document id>"
    Then the reply is "No document named #<id>." and V's document still exists

Feature: callbacks
  Scenario: E5 an intruder's callback costs one acknowledgement
    Given a callback_query from an id outside ALLOWED_TG_IDS
    When process_update handles it
    Then callback_answers holds one entry with no text, nothing else was sent or edited
    And bot_state and llm.calls are unchanged
  Scenario: E6 a stale callback is acknowledged and ignored
    Given a callback "mod:model:99" on a menu showing two models
    Then the answer text is "Expired — send the command again." and no key was written

Feature: the /model menu
  Scenario: E7 the two-step menu sets both overrides
    When U sends "/model", then "mod:prov:openrouter", then "mod:model:1"
    Then the same message_id was edited twice and sent holds one message
    And bot_state has provider_override=openrouter and model_override:openrouter=<catalogue[1]>
  Scenario: E8 the text form validates the model
    When U sends "/model openrouter nope"
    Then the reply is "Unknown model for openrouter; see /model" and no key was written

Feature: large documents
  Scenario: E9 the cap is the Bot API ceiling
    Given a document with file_size 20000001
    Then the reply is "File too large (over 20 MB)." and getFile was never called
  Scenario: E10 ingest leaves the polling loop
    Given a 3-batch document
    When process_update handles it
    Then it returns after "📄 received" with index_document not yet called
    And worker.run_one() completes the job and sends "✅ <name>: N chunks. Ask me about it."
  Scenario: E11 /cancel mid-embedding stores nothing (also STA-01's fit: a 5,000-char basis is cut by rows)
    Given the FakeEmbedder sets the cancel event after batch 1 of 3
    When worker.run_one() runs
    Then documents and vec_chunks are unchanged, the status reads "❌ Cancelled." and the slot is free

Feature: extras
  Scenario: E12 setMyCommands failure is not fatal
    Given MockTransport answers setMyCommands with 500
    When main() starts past getMe
    Then one warning is logged and the polling loop starts

Feature: the ingest guards
  Scenario: E13 second upload while one is indexing
    Given a job for user U is queued or running
    When U sends another document
    Then the reply is exactly "⏳ Still indexing <name>; wait for it to finish."
    And nothing is enqueued and the queue length is unchanged
    And the first job completes normally under worker.run_one()
```

---

## Appendix C — cross-review log

Cross-review log — filled by the lab after the rounds.
