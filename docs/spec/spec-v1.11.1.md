# spec-v1.11.1 — the plain fallback narrowed to HTTP 400, two table widths, the `/sessions` empty state, one batch constant, the xdist-order flake, six untested error rows, and the v1.11.0 paperwork corrected

Status: draft — cross-review pending (Appendix C); the header reads
`` ready for `go` `` only once the rounds are applied.
Base: tag `v1.11.0` = `2431034` (`24310349ee95d703bb3b256443a4b5e1dd22b415`),
on `origin`; the lab's paperwork commits on top of it (prompt 255 and
this file, the cross-review rounds of Appendix C, the handoff,
`docs/llm-usage.md`) touch `docs/` only, so no source, test, config or
lock file differs from the tag — EC-04's precondition is that
structural fact, never a frozen `HEAD` sha; `docs/handoff-v1.11.1.md`
names the exact `HEAD` at `go` time (informational). The lab's defect
inventory of 2026-09-23 (A1…A4, B1…B4, C1…C16, E1…E9, F1…F5, G1…G6,
each mapped in Appendix A's tails table) is the scope. Earlier
mechanisms are
referenced by `REQ-V1110-*` id and `file:line` of `2431034`, never
restated. Target version: **1.11.1** — PATCH, **no new mechanism**;
`pyproject.toml:3` `1.11.0` → `1.11.1` in T6 only; annotated tag
`v1.11.1`, **local only — this run pushes nothing** (EC-01). One
subject: fix what the v1.11.0 run, its review and the lab's
`/verify-run` left on the table, and leave the v1.11.0 record truthful.
A DELTA specification on `2431034`.

Ids: `REQ-V1111-<GROUP>-NN`, `(MUST)` or `(NON-GOAL)`; tests
`T-V1111-<GROUP>-NN` named `tests/test_v1111_<group>.py::test_t_v1111_<group>_<nn>_<slug>`;
**no `v1111-*` mutation id** (NG-02); tasks T0…T6; task-brief files
`docs/spec/task-briefs/v1111-T<n>.md`. Authoring prompt **255**; run
prompts from **256** (T0 256, T1 257, T2 258, T3 259, T4 260 — the
report/post corrections, `report-v1.11.0.md` and `tg-post-v1.11.0.md`
only — and 261 — README, `docs/plan.md`, `AGENTS.md` and
`tests/test_v1111_doc.py`, delegated, carrying both prompts'
bookkeeping (EC-03);
T5 262, T6 263, one more per repair cycle); `docs/llm-usage.md` from row
**167** (166 is authoring; 165 is the last at `2431034`, `:315`).
Executor `claude-sonnet-5`; reviewer the pinned `code-reviewer`
(`.claude/agents/code-reviewer.md:4`, `model: sonnet`), clean context.

---

## 1. Execution contract

**REQ-V1111-EC-01 (MUST) — boundary, dependencies, network, budget, no
push, the benchmark rule.** `REQ-V1110-EC-01` (`docs/spec/spec-v1.11.0.md:57-95`)
applies unchanged with these bindings: **zero new dependencies**
(`pyproject.toml:6-14`, `:16-21` unchanged; `T-V1111-VER-02`); **the
network this release needs is exhaustive** — gate 5 at T0, T5 and T6,
gates 7 and 8 once each at T5, the `uv lock` of VER-01; no offline test
reaches a socket (`tests/conftest.py:10-28`); **the filesystem
boundary** — `.env`, `data/`, `bot.db`, `sandbox/`, `exec_audit.jsonl`,
`docs/assets/bench/*.json` never opened, the one programmatic
`bot_state` count of `REQ-V1110-EC-05` (`spec-v1.11.0.md:188-197`) the
only read exception. **The sole `.env` exception is EC-04's one
non-printing `sed -i` replacement of `LMSTUDIO_BASE_URL`; no command
may print, copy, diff, grep, or otherwise inspect `.env`.** Rerank
stays on OpenRouter; **the repair budget is ≤ 3
cycles per task** (one red gate of construction → one `fix:` commit
under its own prompt); exhausted → the stop route (REV-03); gates 7 and
8 are never rerun (GATE-01). **No push**: the operator pushes later.
**The benchmark rule is not triggered**: nothing token-bearing changes
(REV-01 item 5); the waiver chain of `AGENTS.md:274-282` gains one
sentence at T6 (NG-11); no bench run.

**REQ-V1111-EC-02 (MUST) — test-first; the carve-out by id; the floor;
the T0 pin inventory; a late pin is a disclosed amendment.** Write the
group's tests (§6), watch them fail for the right reason, then implement
in §10's order. **Carve-out by id** (`REQ-V1110-VER-01`'s form,
`spec-v1.11.0.md:1512-1518`): `T-V1111-VER-02`, `T-V1111-PIN-01` and
`T-V1111-PIN-02` are structural and may be green on first execution;
`T-V1111-DOC-03` is green on first execution **by T4's ordering** (its
artefacts-only report commit lands before the test's commit, EC-04);
the report records the initial result of all four. Every `MUST` in §§1–10 has a
named test, a Gherkin scenario or a recorded artefact; Appendix A is
the map. Every `file:line` cites `2431034`; a drift of ≤ 5 lines is a
disclosed amendment (`cited → actual`), a larger drift or an absent
mechanism is a spec ambiguity → the stop route (`REQ-V1110-EC-02`,
`:97-111`). **The floor**: `2431034` collects
**2384** tests by `uv run --locked pytest --collect-only -q -o addopts="" |
grep -c '::'` (`AGENTS.md:161`); T0 re-measures **on the unchanged
handoff tree, before `tests/test_v1111_pin.py` exists** (PIN-01: the
delegated T0 subagent writes that module only after the floor and the
node-id list are measured); **if T0 collects fewer than 2384 tests, the
run stops as a base-tree/precondition mismatch (REV-03, no repair
cycle); otherwise the measured count is recorded as `floor`** — so
`T-V1111-PIN-01`'s `≥ 2384` line-count assertion and the floor agree
(ERR-01 row 13); T6 asserts count ≥ floor + **27** (§6.1's 27
functions, `T-V1111-PIN-01` and `-PIN-02` among them — excluded from
the floor by construction; `T-V1111-TST-08` is a command). `[[VERIFY:
the collected-test floor — 2384 at authoring (`AGENTS.md:161`,
`tests/test_v1110_ver.py:57`); decision rule: a T0 count below 2384 is
a base-tree/precondition mismatch → the stop route, no repair cycle; at
or above it the measured count is the floor; T6 asserts count ≥ floor +
27; a lower T6 count is a §6 defect of the task Appendix A names, one
repair cycle, then the stop route — never a floor adjustment]]`. **The T0 pin inventory** is PIN-01. **A pin found after T0 is a
disclosed amendment** (file, line, rewrite, intent kept) in the
discovering task's commit body and bullet — never a repair cycle, never
a stop, no budget spent (`REQ-V1110-PIN-01`, `:1329-1333`).
`tests/test_v1110_inventory.py`'s frozen list (`_SPEC_TEST_FUNCTIONS`,
61 pairs) is **unchanged**: no `v1110` test is renamed (every pin is
rewritten in place under its name) and the `v1111` tests are **not**
added to it (`T-V1111-PIN-02`).

**REQ-V1111-EC-03 (MUST) — delegation is specified, briefed by file, and
recorded per commit.** `standards/workflow.md` §5.1 binds every task.
**Every task that writes source is `delegate: yes`**, briefed by
`docs/spec/task-briefs/v1111-T<n>.md` — written by the orchestrator
before dispatch, passed by path, never retyped, committed with the task.
A `no` cell in §10.1 carries one of the four §5.1 exemptions
**verbatim** (*commands only*; *artefacts only*; *a single edit under
every threshold*; *the task is itself the clean-context review*);
crossing the map live forces delegation from that point. T0's pin
inventory is delegated: the orchestrator writes `v1111-T0.md`, the
subagent the **distinct** `v1111-T0-pin-inventory.md` **and
`tests/test_v1111_pin.py`** (PIN-01; `REQ-V1110-EC-04`, `:157-165`).
**T4 is two commits by artefact class**: the first (prompt 260) is
*artefacts only* — DOC-03's five edits, restricted to the two files
`docs/reports/report-v1.11.0.md` and `docs/reports/tg-post-v1.11.0.md`,
no test, no bookkeeping; the second (prompt 261) is `delegate: yes`,
brief `v1111-T4.md` — README, `docs/plan.md`, `AGENTS.md` **and**
`tests/test_v1111_doc.py` (all three DOC tests). **Prompt 260's
bookkeeping has a landing commit**: `docs/prompts/260-*.md` and prompt
260's `docs/llm-usage.md` row land in T4's second commit as
orchestrator-authored artefacts bundled with the delegated files; its
body and report bullet disclose that bundling. Prompt 261's bookkeeping
lands in the same second commit. **The complete allowed path set of
T4's second commit** (nine): `README.md`, `docs/plan.md`, `AGENTS.md`,
`tests/test_v1111_doc.py`, `docs/prompts/260-*.md`,
`docs/prompts/261-*.md`, `docs/llm-usage.md`,
`docs/spec/task-briefs/v1111-T4.md`, `docs/reports/report-v1.11.1.md`
— nothing else. **The report's delegation record**
(lint-enforced: `_lint_report_delegation`, `devtools/checks.py:1672-1716`)
names, **for every commit**, the brief path or one exemption verbatim;
**a commit that bundles an orchestrator edit into a delegated commit
says so in its body and in the bullet** (the A4 lesson: `33729eb`,
`docs/reports/report-v1.11.0.md:1700`). The subagent returns a summary,
never file content.

**REQ-V1111-EC-04 (MUST) — preconditions, operator input, the prompt
chain, secrets, the gates never overlap.** Before T0's first command,
**the structural precondition** (no `HEAD` sha is frozen here — every
later paperwork commit would invalidate it): `git rev-parse
v1.11.0^{commit}` prints `24310349ee95d703bb3b256443a4b5e1dd22b415`;
`git merge-base --is-ancestor v1.11.0 HEAD` exits 0; `git describe
--tags --abbrev=0` prints `v1.11.0`; `git diff --name-only
v1.11.0..HEAD` lists only paths under `docs/` (this file, its prompt,
`docs/handoff-v1.11.1.md`, `docs/llm-usage.md`) — no source, test,
config or lock file changed since the tag; `git status --porcelain`
empty; `test -f .env` exits 0; `git stash list` recorded; the exact
`HEAD` at `go` time is the one `docs/handoff-v1.11.1.md` names
(informational, not a precondition); prompt 255 and `docs/llm-usage.md`
row 166 exist in `HEAD`;
this file is committed and unmodified (`git diff --exit-code HEAD --
docs/spec/spec-v1.11.1.md` exits 0) and its `Status:` reads `` ready
for `go` ``. **Gate 5 needs a reachable LM Studio**: `REQ-V1110-EC-05`'s
address rule (`spec-v1.11.0.md:180-187`) by reference — the `go` text
may carry the address, T0 writes it into `.env`'s `LMSTUDIO_BASE_URL`
line with one `sed -i` only then — **the sole `.env` exception: one
non-printing `sed -i` replacement of `LMSTUDIO_BASE_URL`; no command
may print, copy, diff, grep, or otherwise inspect `.env`** (EC-01,
NG-12, SEC-01); unreachable
at gate 5 is a **blocked run** (no task proceeds, no stop route; the
operator re-issues `go`). **The override precondition**: the `bot_state`
count (`:188-197`) prints `0` at T0 and just before gate 8 at T5;
non-zero is a blocked run. **Prompts**: one prompt → one commit, never
mixed, with **two exceptions by id**: T5's prompt 262 carries at most
three commits (the review's fix commit on a must-fix, ERR-01 row 7's
timeout hunk if `W > 1300 s`, then the report-only gate commit —
REV-02) and T6's prompt 263 carries two (the bump, then the
evidence-only commit — VER-01); T4 carries **two prompts and two
commits**, ordered by artefact class: **260 first** — DOC-03's five
report/post corrections, `docs/reports/report-v1.11.0.md` and
`docs/reports/tg-post-v1.11.0.md` only, *artefacts only*; **261
second** — DOC-01, DOC-02 and `tests/test_v1111_doc.py`, delegated
(EC-03) — and, because the first commit admits no other path,
`docs/prompts/260-*.md`, `docs/prompts/261-*.md` and both prompts'
`docs/llm-usage.md` rows land in the second commit as
orchestrator-authored artefacts bundled with the delegated files,
disclosed in its body and bullet (EC-03's nine-path set).
Commit header ≤ 72 characters, conventional type, body names the prompt
file (`AGENTS.md:115-127`); `--no-verify` never; the report attests it.
**Secrets**: only two values are ever registered (`config.py:370`,
`:400`); nothing prints, quotes or commits either; every artefact
carries env-variable **names** only and writes addresses as `<addr>`;
**immediately after every commit created by T0–T6, before another
commit is made, run the standalone `gitleaks-tree` block (GATE-01's
command) against that commit and require exit 0** — each result one
line (commit sha, exit code) in the report's per-task section, the
evidence commit's in the tag message (GATE-01, RPT-01). **Gates 6, 7 and 8 never run in parallel** with one another
or any other gate (`REQ-V1110-EC-07`, `:215-223`).

---

## 2. Non-goals

| id | NON-GOAL |
|---|---|
| `REQ-V1111-NG-01` | Any new command, feature or mechanism; any schema change (`SCHEMA_VERSION` stays 6); any change to gate 5, gate 7 or `devtools/agent_eval.py`'s cases, floors or judge. |
| `REQ-V1111-NG-02` | New `v1111-*` mutation entries or a `mutation-v1111` gate: `mutation-all` stays **152** (`config/quality_gates.yaml:738-740`) — no security-relevant mechanism changes; the v1.9.x/v1.10.4 precedent (`spec-v1.10.4.md:241`). Existing entries are still killed — gate 6 once at T5 (GATE-01). |
| `REQ-V1111-NG-03` | Re-adding `_TypingIndicator` to the document path (C3): dropped by design in v1.11.0 T5 (`report-v1.11.0.md:1022-1024`); the class stays on the text path (`bot.py:558`, `:1124`). |
| `REQ-V1111-NG-04` | Changing `/documents`' size unit to MiB (C6): `_render_size` (`bot.py:2333-2339`) stays decimal; README states the convention (DOC-01). |
| `REQ-V1111-NG-05` | Loosening the exact lock-spy delta in `tests/test_v1110_ing.py:288-303` (F1): the deliberate killer of the reserve-lock entry; a future admission-path lock rewrites it then, disclosed. |
| `REQ-V1111-NG-06` | Redacting the ≈ 70 pre-existing RFC1918 sites (A3/G1: `docs/handoff-v1.11.0.md:13-14`, `report-v1.11.0.md:50-56,1920-1923`, `docs/llm-usage.md:297`, earlier reports, prompts, specs, briefs, two test fixtures): pushed history; redacting only the v1.11.0 sites would be inconsistent; the ruling lands in `AGENTS.md` (DOC-02) and this run's paperwork writes `<addr>`. |
| `REQ-V1111-NG-07` | Editing any frozen spec: `docs/spec/spec-v1.md:135`'s "exactly five commands" (E6) stays; `spec-v1.11.0.md`'s DOC-01 (`:451-453`) and MOD-01 (`:658-659`) widths are **amended by reference here** (§3.2), never edited there. |
| `REQ-V1111-NG-08` | Any change to `docs/plan.md` beyond DOC-02's banner (C9/E7); `REQ-V1110-NG-10` otherwise carries. |
| `REQ-V1111-NG-09` | Changing `mutation-all.timeout_seconds` (1640, `config/quality_gates.yaml:752`) except by `REQ-V1110-MUT-01`'s rule when T5's `W` exceeds 1300 s (GATE-01). |
| `REQ-V1111-NG-10` | A fourth cross-review round on `spec-v1.11.0.md` (closed at `round_limit`, `:1795`); every accepted R3 change is in the code. |
| `REQ-V1111-NG-11` | A benchmark run, a fresh baseline, or any edit to `AGENTS.md:266-272`'s rule; the waiver paragraph (`:274-282`) gains exactly one sentence at T6: "v1.11.1 changes nothing token-bearing either; the rule does not fire." |
| `REQ-V1111-NG-12` | Any new dependency; any direct read of `.env`, `data/`, `bot.db`, `sandbox/` or `exec_audit.jsonl` (EC-01's `bot_state` count aside). The sole `.env` exception is EC-04's one non-printing `sed -i` replacement of `LMSTUDIO_BASE_URL`; no command may print, copy, diff, grep, or otherwise inspect `.env`. Rerank off OpenRouter; touching `docs/assets/bench/*.json`. |
| `REQ-V1111-NG-13` | Any `git push`; any change to a gate's `argv`, `result_mode`, `blocking`, `severity` or profile membership; invoking `checks.py run --profile full` at any point (the eight gates run as `AGENTS.md:150-158`'s commands; `REQ-V1110-REV-02`'s "never invoked as a whole" carries — C1). |
| `REQ-V1111-NG-14` | Editing mutation entry `v1110-table-path-escape-dropped`'s `why` (B4): the named killer `T-V1110-OUT-02` is correct; collection order is not a defect. |
| `REQ-V1111-NG-15` | Editing any earlier report, handoff, prompt or `docs/llm-usage.md` row **except** DOC-03's five named edits (the v1.10.4 prompt-234 precedent). |
| `REQ-V1111-NG-16` | Renaming any test that exists at `2431034`; adding a `v1111` pair to `tests/test_v1110_inventory.py`'s frozen list; deleting any test (`REQ-V190-EC-03` carries); a code change for B1. |
| `REQ-V1111-NG-17` | Action on the inventory items verified consistent: C4, C7, E1, E2, E4, E5, E8, E9, F2, F3, F5, G3 — re-checked by T0, none edited. |

---

## 3. The fixes

### 3.1 OUT — the fallback scope and three docstrings

**REQ-V1111-OUT-01 (MUST) — the plain fallback fires on HTTP 400 only;
`TelegramError` carries the status.** (B2, contradiction 5.)
`TelegramError` (`bot.py:176-188`) gains a keyword field
`status: int | None = None`, stored as `self.status`; **`TelegramClient.call`
(`bot.py:219-263`) sets it from `response.status_code` on every raise
that follows a response** — `:244` (fatal 401/404), `:246-248` (429),
`:250`, `:255`, `:256-262` — and leaves it `None` on the transport
raise (`:236-240`).
`_call_with_retry` (`:265-280`) is **byte-unchanged**: a 429 still
retries `SEND_ATTEMPT_LIMIT` times honouring `retry_after`, a transport
error still sleeps and retries, everything else raises at once; the
error that escapes carries its `status`. **`send_pre` (`:2540-2564`)
and `edit_pre` (`:2567-2585`) perform the one-time plain resend of the
fitted body only when `exc.status == 400`**; on any other
`TelegramError` — fatal, a 429 that outlived the budget, a 5xx, `None`
— the failure is logged (the existing `sending the reply failed` /
`editing the reply failed` lines) and `None` returned, **the outcome the
fatal branch has today and the outcome `_send` (`:2514-2525`) gives the
plain path**; the `fatal` check is subsumed (401/404 never equal 400).
**A failure of the plain resend itself** — any `TelegramError`, a 5xx
or a transport error included — is logged once at ERROR by the same
existing line (`:2563`, `:2584`), `None` returned, **never a third
request** (`T-V1111-OUT-02`'s 400 → 500 and 400 → transport cases).
At-most-once semantics, the `_pre_text` order (`:2528-2537`) and the
payload pin (`REQ-V1110-OUT-02`) are unchanged; `T-V1110-OUT-05`'s four
cases (`tests/test_v1110_out.py:359-422`) stay green unamended. README's
`## Error behaviour` gains DOC-01 (b)'s row (400 only).
`T-V1111-OUT-01…04`; `E1`.

**REQ-V1111-OUT-02 (MUST) — three docstrings say what the code does.**
(C13, C14, B1; contradictions 4, 5, 10.) (a) `bot.send_pre`'s docstring
(`bot.py:2541-2550`) is replaced verbatim by:

```
REQ-V1110-OUT-01/-04, narrowed by REQ-V1111-OUT-01: the table path, the
only production caller of `TelegramClient.send_message_html`. Never
splits: `_pre_text` already fit `body` to 4096 UTF-16 units. Exactly one
failure class gets the plain fallback: a `TelegramError` whose `status`
is 400 (the Bot API's "can't parse entities" family) -- the same fitted
body is resent once through the plain `send_message`. Every other
`TelegramError` -- fatal (401/404), a 429 that outlived
`_call_with_retry`'s budget, a 5xx, a transport error (`status is None`)
-- is logged and `None` returned, as `_send` treats the plain path; a
second failure on the fallback is logged, never a third attempt. The
classification is `TelegramError`'s own fields, not a line range.
```

`edit_pre`'s docstring (`:2570-2573`) says "the same 400-only rule" in
place of "the same fatal-skips-the-fallback rule … on a non-fatal
table-path failure". (b) `tables.fit_lines`'s docstring
(`tables.py:135-139`) drops the parenthetical `` the `_fit` pattern
(`bot.py:1190-1197`) but `` so the sentence reads "… appended until it
fits -- over lines, never a hard slice inside a line." (`_fit` was
removed by `743abc2`; `bot.py:1190` is inside `_handle_new`). (c)
`IngestJob`'s docstring (`bot.py:1918-1920`, first sentence) becomes:
"One admitted document upload. `phase` and `cancel_reason` are written
only under `IngestWorker`'s lock (REQ-V1110-ING-04); `cancel_reason`
may be read without it, because every writer sets it once **before**
setting the `threading.Event` `cancel` and every unlocked reader reads
it only **after** `cancel.is_set()` — the Event's own happens-before
edge publishes it (the v1.11.0 T7 review's finding-2 waiver,
`docs/reports/report-v1.11.0.md:1529-1541`; re-review under
free-threaded Python)." — the `monotonic` paragraph (`:1920-1928`), the
read sites (`bot.py:1959`, `:1969`, `:2123`) and the write sites
(`:2047`, `:2229`) unchanged (the waiver's own `:2222` is DOC-03's edit
5). `T-V1111-OUT-05`.

### 3.2 TAB — widths, the empty state, the refusal string, one constant

**Amendments by reference to `spec-v1.11.0.md`** (NG-07; the report's
amendment table lists both):

| spec site | was | is | id |
|---|---|---|---|
| `spec-v1.11.0.md:451-453` (DOC-01, `/documents`) | `#` 3, `file` 24 (72) | `#` 5, `file` 22 (72) | TAB-01 |
| `spec-v1.11.0.md:658-659` (MOD-01, `/model`) | `[12, 44]` (58) | `[16, 40]` (58) | TAB-02 |

**REQ-V1111-TAB-01 (MUST) — `/documents` ids render whole up to
99,999.** (C5, contradiction 7.) `_handle_documents`' `max_width`
(`bot.py:2376`) becomes `[5, 22, 4, 8, 6, 5, 10]` — sum 60 plus six
separators = 72 ≤ 72 (`tables.py:17`). `render_table` sizes columns to
content within `max_width` (`tables.py:96-111`), so README's sample
(`README.md:221-228`) changes only in the truncated second row and the
rule line: a 40-character filename renders as 21 `f` + `…` (22 units),
and `:217` reads "cut to 21 UTF-16 units + `…`"; T2 regenerates the
fenced sample from `T-V1110-DOC-01`'s fixture and `T-V1111-TAB-02` pins
it byte-equal. The pin `tests/test_v1110_doc.py:200-202` (`"f" * 23 +
"…"`, `== 24`) is rewritten in place to 21 / 22. `/sessions`' `#`/`msgs`
width 4 (`bot.py:2466`) is **not** widened (a listing, not a typed-back
argument). `T-V1111-TAB-01`, `T-V1111-TAB-02`;
`E2`.

**REQ-V1111-TAB-02 (MUST) — the `/model` status table never truncates
its own label.** (B3, contradiction 6.) `bot.py:1545` becomes
`tables.render_table(["field", "value"], rows, max_width=[16, 40])`:
`openrouter model` (16 units) renders whole; a value over 40 units
still truncates with `…`; sum 58 unchanged. README shows no
status-table sample (`README.md:323-368`); the pins T0 finds in
`tests/test_v1110_mod.py` are rewritten in place (the authoring grep
found none).
`T-V1111-TAB-03`; `E4`.

**REQ-V1111-TAB-03 (MUST) — `/sessions` with no sessions replies on the
plain path.** (C12.) A new constant next to `SESSIONS_LIST_LIMIT`
(`bot.py:140`):
`SESSIONS_EMPTY_REPLY = "No sessions yet. Send me a message to start one."`.
`_handle_sessions` (`bot.py:2448-2471`) gains, before `render_table`,
`if not rows: _send(tg, chat_id, [SESSIONS_EMPTY_REPLY]); return` — the
mirror of `_handle_documents`' branch (`bot.py:2359-2361`); with rows
nothing changes (`REQ-V1110-SES-02`, `spec-v1.11.0.md:528-539`). README
`:153-154` "A caller with no sessions yet sees the header and rule
only." becomes "A caller with no sessions yet gets a plain reply
instead: `No sessions yet. Send me a message to start one.`"; `## Error
behaviour` gains the row (ERR-01 row 1). `T-V1111-TAB-04`; `E3`.

**REQ-V1111-TAB-04 (MUST) — `DOC_LIMIT_REPLY` names both delete forms.**
(C15, contradiction 11.) `bot.py:109` becomes, one literal:
`DOC_LIMIT_REPLY = "Limit of 20 documents reached. Use /delete <filename> or /delete #<id>."`.
Both senders unchanged — `bot.py:2292`, `_handle_document`'s
pre-admission count check (`:2286-2293`, a plain `_send`), and
`bot.py:2128`, the worker's `except documents.DocumentLimitExceededError`
branch (`:2126-2129`; raised at `documents.py:574-577` when the count
has reached 20 by commit time; delivered by `_document_error_ending`,
`:1868-1876`, as an edit of the status message or a plain send) — and
**both are driven through `process_update` by `T-V1111-TAB-05`**, each
case asserting the exact new literal, no document, chunk or vector row
inserted for the upload and the document count unchanged; README's row
(`README.md:993`) carries it verbatim; the needle
`tests/test_v190_agents.py:300` is rewritten in place
(`tests/test_v1110_pin.py:114`'s prefix is `DELETE_USAGE_REPLY`'s,
unaffected). ERR-01 row 2. `T-V1111-TAB-05`.

**REQ-V1111-TAB-05 (MUST) — one embedding batch constant.** (C8/G4.)
`documents.py:386` (`EMBED_BATCH_SIZE = 32`) is **removed**;
`documents.py` gains `from llm.embeddings import BATCH_SIZE` (no cycle:
`llm/embeddings.py:8-13` imports `tracing` and `config` only among project modules) and the
loop at `documents.py:552-562` uses `BATCH_SIZE` in the five places
`EMBED_BATCH_SIZE` stood (`:552` twice, `:554`, `:555`, `:558`) — the outer loop, `total_batches`, `batch_no`
and the per-batch `_check_budget` checkpoint stay, so the progress and
cancel cadence stays at 32. `documents.BATCH_SIZE` is the monkeypatch
seam: the two patches `tests/test_v1110_ing.py:548` and
`tests/test_v1110_doc.py:378` (`monkeypatch.setattr(documents,
"EMBED_BATCH_SIZE", 1)` — an `AttributeError` once the name is gone)
are rewritten in place to `"BATCH_SIZE"`. README's paragraph (`README.md:538-543`) becomes: "Texts are
embedded in batches of `llm.embeddings.BATCH_SIZE` (32) — one constant:
the ingest pipeline imports it for its per-batch progress edit and
budget/cancel checkpoint, and `EmbeddingsClient.embed` uses it for its
per-request chunking, so the progress counter and the HTTP batch can
never diverge."; the pin `tests/test_v1110_ver.py:135` is rewritten in
place to assert `documents.EMBED_BATCH_SIZE` **absent**; `:136` stays.
**The HTTP-call invariant is tested, not inferred**: `T-V1111-TAB-06`
also drives a real `EmbeddingsClient` over `httpx.MockTransport`
(`tests/test_v1110_out.py:94-95`'s shape) with 65 inputs through the
ingest path and asserts exactly three embedding requests whose body
`input` sizes are `[32, 32, 1]`, alongside the progress edits
`1/3 … 3/3` — a request chunking that drifts from the progress counter
fails it. `T-V1111-TAB-06`; `E5`.

### 3.3 TST — the six rows and the flake

**REQ-V1111-TST-01 (MUST) — ERR-01 rows 11–16 of v1.11.0 get
dispatch-level tests.** (C10.) The drafter's choice: **a new module
`tests/test_v1111_tst.py`**, not an extension of the frozen
`test_t_v1110_err_01_error_matrix_strings` (`tests/test_v1110_err.py:119`)
— the v1110 function stays byte-unchanged. Six tests, one per row, each
driving `bot.process_update` through the `process`/`text_update`
helpers of `tests/test_v1110_err.py:81-109` with a hand-written update
dict, asserting the reply **byte-equal** to the string and the string
present in README's `## Error behaviour` (`_error_section()`,
`:112-116`; rows 14 and 16 in the `\|`-escaped form of `:975`, `:978`):

| row (`spec-v1.11.0.md:1138-1143`) | trigger | string (`bot.py`) |
|---|---|---|
| 11 | `/session` bare | `Usage: /session <id> (see /sessions)` (`:141`) |
| 12 | `/session 999999` | `No session #999999.` (`:2477`) |
| 13 | `/delete #999` | `No document named #999.` (`:2411`) |
| 14 | `/delete` bare | `Usage: /delete <filename> \| /delete #<id>` (`:129`) |
| 15 | a `callback_query` with data `zzz` from an allowed user | `answerCallbackQuery` `text` `Expired — send the command again.` (`:92`, `:1820-1825`; read from `FakeTelegram.callback_answers`, `tests/fakes.py:179`) |
| 16 | `/model openrouter nope`; `/model a b c` | `Unknown model for openrouter; see /model` (`:1636`); `Usage: /model [lmstudio\|openrouter\|auto] [<model>]` (`:88`) |

`T-V1111-TST-01…06`.

**REQ-V1111-TST-02 (MUST) — the secrets registry is restored after every
test; the xdist-order flake dies.** (C11/F4.) The registry is the
module-level set `config._secrets` (`config.py:98`, `_secrets: set[str]
= set()`), filled by `register_secret` (`:230-233`) and read at call
time by `redact` (`:239`) and the two helpers at `:294-296`, `:305`.
`tests/conftest.py` gains a context manager `secrets_registry_snapshot()`
(`saved = set(config_module._secrets)`; `yield`;
`config_module._secrets.clear(); config_module._secrets.update(saved)`
— **mutating the same set object, never rebinding it**) and an
**autouse** fixture `restore_secrets_registry` wrapping every test in
it, after `no_real_bind` (`tests/conftest.py:37`). **No test file other
than `tests/conftest.py` changes for this item**; the leaking test is
not hunted — the fixture makes the order irrelevant. `[[VERIFY: the
registry name — `config._secrets` at `config.py:98`, touched only
through `register_secret` (`:230-233`), `redact` (`:239`), the helpers
at `:294-296`, `:305` and `tests/test_v11_patch.py:53-56`'s own
clear/restore; decision rule: if T0's grep (`grep -n "_secrets"
config.py tests/conftest.py tests/test_v11_patch.py`) finds the registry
under another name or as a rebound object, the fixture snapshots and
restores **that** object in place and `v1111-T3.md` records `cited →
actual`; a registry that is not a mutable container is a spec ambiguity
→ the stop route]]`. **The autouse fixture itself is what
`T-V1111-TST-07` proves**, not only the context manager: the test
writes a two-test module to `tmp_path` (test A registers a sentinel
secret and does not clean up; test B asserts the sentinel is absent
from `config._secrets` and that the registry is the same object as
before) plus a `conftest.py` in `tmp_path` that loads the project's
fixture by import (`from tests.conftest import restore_secrets_registry`
— `[[VERIFY: `tests` is importable as a package at 2431034
(`tests/__init__.py` present or `rootdir` on `sys.path` under the
project's pytest config); confirmation = the nested run collects both
tests and passes; fallback = the nested `conftest.py` uses
`pytest_plugins = ("tests.conftest",)` and, if neither form imports,
TST-07 falls back to the two permanent ordered tests in
`tests/test_v1111_tst.py` under
`@pytest.mark.xdist_group("secrets_registry")` run with `--dist
loadgroup`, recorded as a disclosed amendment]]`), runs
`subprocess.run([sys.executable, "-m", "pytest", "-p",
"no:cacheprovider", "-p", "no:xdist", "-q", str(tmp_path)])` and asserts
exit code 0. The nested module never calls `secrets_registry_snapshot()`
itself — a fixture that is absent, misspelled or not `autouse=True`
fails the nested run. The direct context-manager assertions stay as
additional checks. Verification **by command, recorded in the report**
(`T-V1111-TST-08`): (1) `uv run --locked pytest
"tests/test_v1103_red_team.py::test_t_v1103_rt_06_leak_shape_fixture_still_fails_on_clause_c_only"
-o addopts=""` alone → passed; (2) `uv run --locked pytest -p xdist -n 4
-o addopts="" -q` **twice** → both green, the summary lines quoted.
`T-V1111-TST-07`, `T-V1111-TST-08`; `E6`.

### 3.4 DOC — paperwork and drift

**REQ-V1111-DOC-01 (MUST) — README.** (C6, C15, C16, G5, B2.) (a) `##
Limits` (`README.md:918-952`) gains the row `` | `/model` catalogue cap
| 20 entries per provider (`MODEL_CATALOGUE_MAX`; the rest dropped at
startup with a warning) | `` after the `rerank candidates` row, and one
line after the table: "Sizes shown by `/documents` are decimal (1 MB =
1,000,000 bytes); the exec and sandbox limits above are binary (MiB)."
(b) `## Error behaviour` (`:953-1002`) gains three rows: `` | `/documents`
with no documents uploaded | nothing sent on the table path | `No
documents yet. Send me a .txt, .md, .docx or .pdf file.` | ``; `` |
`/sessions` with no sessions | nothing sent on the table path | `No
sessions yet. Send me a message to start one.` | `` (TAB-03); `` |
Telegram 400 on a table-path send (`send_pre`/`edit_pre`) | one plain
resend of the same fitted body, no `parse_mode`; any other failure
(429 after the retry budget, 5xx, transport) is logged and never resent
| the table as plain text, or nothing | `` (OUT-01); the `Telegram 429
on send` row (`:967`) stays. (c) `## Versioning` (`:1008-1011`): "so a
`v1.6.0` tag does not exist until this release's own final commit
lands." becomes "so a release's tag — `v1.6.0` included — was created
only after that release's own final commit had landed." TAB-01's sample,
TAB-03's sentence, TAB-04's row and TAB-05's paragraph land in **T2**
with their code; (a)–(c) in **T4's second commit** (prompt 261, brief
`v1111-T4.md`). `T-V1111-DOC-01`.

**REQ-V1111-DOC-02 (MUST) — `docs/plan.md`'s banner; `AGENTS.md`'s
ruling.** (C9/E7, A3/G1.) `docs/plan.md` gets exactly these seven lines
inserted **before** its first line, then one blank line; nothing else in
the file changes (`T-V1111-DOC-02` compares the remainder to `git show
v1.11.0:docs/plan.md`):

```
> **Superseded.** Since v1.7.0 the roadmap lives in `docs/spec/spec-vN.md`
> (the contract) and `docs/handoff-vN.md` (the `go`-session handoff written
> by the lab for each release — what the run session reads first). This
> file is kept as history: its last release section is `## v1.6.0 (in
> progress)` and its status table stops at `spec-v1.7.0.md` marked in
> progress; every release since is specified in `docs/spec/spec-vN.md` and
> handed off in `docs/handoff-vN.md`.
```

Both of the banner's claims are true of `2431034`'s file, headings and
status table alike: `## v1.6.0 (in progress)` is its last release heading
(`docs/plan.md:215`) and its status table's last row is
`docs/spec/spec-v1.7.0.md`, marked **in progress** (`docs/plan.md:25`);
the banner cites neither line number, since its own insertion shifts them.

`AGENTS.md`'s `## Secrets` (`AGENTS.md:325-328`) gains one paragraph
after its existing one: "RFC1918 addresses of the operator's LM Studio
box (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) in reports,
prompts, task briefs and handoffs are operator input, not secrets: the
lab's `/verify-run` secrets scan treats them as out of scope, and no
historical artefact is redacted for them (ruled at spec-v1.11.1). New
paperwork writes `<addr>` anyway." Both in T4's second commit (prompt
261, brief `v1111-T4.md`). `T-V1111-DOC-02`.

**REQ-V1111-DOC-03 (MUST) — the v1.11.0 report and post corrected, in
their own prompt.** (A1, A2, A4, G6, B1; contradictions 1–3.) T4's
**first** prompt (260) and commit, *artefacts only* —
`docs/reports/report-v1.11.0.md` and `docs/reports/tg-post-v1.11.0.md`
exclusively, no test file, no bookkeeping (prompt 260's prompt file
and usage row land in T4's second commit, EC-03) — edits exactly five
sites; `T-V1111-DOC-03`
lands with the other DOC tests in T4's second commit (261) and is green
by then (EC-02): (1)
`docs/reports/report-v1.11.0.md:1945` `| 17 (236-252) |` → `| 19
(236-254) |`; (2) `docs/reports/tg-post-v1.11.0.md:23` `промпты 236–252`
→ `промпты 236–254`; (3) one paragraph appended to `## T2` after its
"Delegated (brief …)" line (`report-v1.11.0.md:276`): "**Disclosed EC-05
deviation (recorded by spec-v1.11.1 T4, after the release):** prompt 239
is cited by three commits — `743abc2` (T2's source commit), `ef8e453` and
`09f8d8a` (record corrections after the fact, no source change). T1's
analogous correction got its own prompt (238 → `2b2dd4e`); T2's did not.
History is pushed and not rewritten; `docs/llm-usage.md` row 150 covers
all three."; (4) the T7 Phase A bullet (`:1700`) keeps its cells and
replaces the clause "the `quality_gates.yaml` comment fix and this
commit are the orchestrator's own commands-only work, not delegated"
with "commit `33729eb` bundles the delegated Phase A files with one
orchestrator-authored `config/quality_gates.yaml` comment hunk (`@@
-733,7 +733,14 @@`, outside the subagent's owned paths) — its commit
message discloses it; recorded here by spec-v1.11.1 T4" (no `|` inside
the cell, so `lint-docs` keeps parsing it); (5) the T7 review's finding-2
waiver (`report-v1.11.0.md:1529-1541`) cites the second `cancel_reason`
write site as `` `:2222` `` (`:1534`); the live tree has it at
`bot.py:2229` (`entry.cancel_reason = "shutdown"`, the first at `:2047`
is right) — that one token becomes `` `:2229` ``, nothing else in the
passage changes. The tg-post's `wc -m` stays ≤ 1500. `T-V1111-DOC-03`.

### 3.5 PIN — the T0 inventory

**REQ-V1111-PIN-01 (MUST) — structural, fail-closed, delegated,
distinct.** The delegated subagent (brief `v1111-T0.md`) greps the live
tree — never copies this list — and writes
`docs/spec/task-briefs/v1111-T0-pin-inventory.md`: a table `site
(file:line) | literal | task that rewrites it | rewrite form`, starting
from and extending: **T2's sites** — `tests/test_v1110_doc.py:200-202`
(the width), `:378` and `tests/test_v1110_ing.py:548` (the batch
patches), `tests/test_v190_agents.py:300` (`DOC_LIMIT_REPLY`),
`tests/test_v1110_ver.py:135` (the README batch name), whatever
`tests/test_v1110_mod.py` / `test_v1110_out.py` pin on the widths
(expected none); **T6's sites** — the eleven VER-01 lists; **listed to
prove they were checked** — `tests/test_v1110_pin.py:100-120`,
`tests/test_v1110_err.py:119-199` (rows 10 and 17),
`tests/test_v1110_ver.py:116-124` (the `; this release` pins, both still
true), `tests/test_v190_agents.py:285-306`'s other needles;
`tests/test_v1110_inventory.py` (`_SPEC_TEST_FUNCTIONS`) recorded
**unchanged**. Plus the measurements, by command: the collected count
(the floor) and the sorted node-id list to
`docs/spec/task-briefs/v1111-T0-nodeids.txt` (`uv run --locked pytest
--collect-only -q -o addopts="" | grep '::' | sort`) — **a count below
2384 stops the run as a base-tree/precondition mismatch (EC-02, ERR-01
row 13), at or above it the count is `floor`** — `len(MUTATIONS)` =
152, the `bot_state` count. **The rename mapping is empty** (NG-16):
T6's `comm -23 v1111-T0-nodeids.txt <after>` prints nothing
(`REQ-V1110-EC-03` (b), `spec-v1.11.0.md:127-134`); a line is a T6
repair cycle. Rewrite form: presence, contiguity, order; counts read
from the live tree; never a "nothing follows" assertion
(`REQ-V1104-NG-10`). **The module is T0's**: after measuring the
unchanged-tree floor and node IDs, the delegated T0 subagent writes
`tests/test_v1111_pin.py`; run PIN-01/-02 after the inventory artefacts
exist. These two tests are excluded from the T0 floor by construction
(EC-02). `T-V1111-PIN-01`, `T-V1111-PIN-02`.

---

## 4. Error matrix

**REQ-V1111-ERR-01 (MUST) — every new or changed user-visible string,
and every failure class this release adds or moves.** `REQ-V1110-ERR-01`'s
eighteen rows (`spec-v1.11.0.md:1119-1145`; rows 1–17 carry a string, row 18 is the 400 fallback) carry unchanged;
`REQ-V190-ERR-01` row 13's string (`spec-v1.9.0.md:1341`) is superseded
by row 2 below. Rows 1–4 are user-visible; rows 5–13 the executor's.

| # | where | condition | behaviour | reply / verdict |
|---|---|---|---|---|
| 1 | `/sessions` (TAB-03) | `list_conversations` returns no row | plain path, nothing on the table path | `No sessions yet. Send me a message to start one.` |
| 2 | upload at the document cap (TAB-04) | the caller has 20 documents (both check sites, `bot.py:2128`, `:2292`, each driven through `process_update` by `T-V1111-TAB-05`) | refused, nothing stored | `Limit of 20 documents reached. Use /delete <filename> or /delete #<id>.` |
| 3 | `send_pre`/`edit_pre` (OUT-01) | `TelegramError.status == 400` on the HTML request | one plain resend of the fitted body; a failure of that resend (5xx, transport, any `TelegramError`) is logged once at ERROR by the same line, `None` returned, never a third request (`T-V1111-OUT-02`'s 400 → 500 and 400 → transport cases) | the table as plain text, or nothing |
| 4 | `send_pre`/`edit_pre` (OUT-01) | any other `TelegramError` (fatal; 429 after `SEND_ATTEMPT_LIMIT`; 5xx; `status is None`) | logged, `None` returned, no resend | nothing (the plain path's own outcome) |
| 5 | after T0 (EC-02) | a test red on a pin the inventory missed | rewritten in place, intent kept, disclosed in the commit body and bullet | **no cycle, no stop** |
| 6 | T0, gate 5 (EC-04) | LM Studio unreachable, or the `bot_state` count ≠ 0 | the redacted probe line / the count recorded; no task proceeds | **blocked run** |
| 7 | T5, gate 6 (GATE-01) | `W > 1300 s` | `REQ-V1110-MUT-01`'s timeout hunk committed, gate 6 once more on that tree — all **before** `tested_tree` is set | recorded; `W > 2400 s` reported, not a stop |
| 8 | T5, review (REV-01) | a must-fix finding | fixed under brief `v1111-T5.md` as T5's first commit; the review prompt logged | closed or waived with a reason |
| 9 | T5, gate 8 | exit 1 (a floor or the judge mean) | the stop route; the capture quoted in full; never a rerun | stop, no bump, no tag |
| 10 | T6, identity check (GATE-01) | `dependency_diff_is_version_only` `False` — preliminary (bump commit) or definitive (post-evidence, pre-tag) | gate 8 **not** invoked; preliminary: the hunk reverted or corrected, gates 1–6 and the check rerun; definitive: the tag withheld | preliminary: a repair cycle, not restorable → the stop route; definitive: the stop route (a `True` verdict is recorded in the tag message, never in the report — GATE-01's evidence boundary) |
| 11 | T6, the collection check (EC-02) | count < floor + 27, a `comm -23` line, or a `v1110` inventory pair missing | the owning task's defect, one repair cycle | then the stop route |
| 12 | any task (NG-13, C1) | `--profile full` invoked, or a live gate started while gate 6/7/8 runs | disclosed as a process deviation; a gate that completed before the overlap keeps its result, another is rerun — **never gate 7 or 8** (a compromised record of theirs is the stop route) | recorded |
| 13 | T0, the floor (EC-02, PIN-01) | the collected count reads below 2384 | a base-tree/precondition mismatch: no repair cycle, no floor adjustment; the command and its output recorded | **stop** (REV-03), no task proceeds past T0 |

`T-V1111-TAB-04` (row 1), `T-V1111-TAB-05` (row 2), `T-V1111-OUT-02`
(row 3), `T-V1111-OUT-03`, `-04` (row 4), `T-V1111-DOC-01` (README);
rows 5–13 are recorded artefacts.

---

## 5. Security

**REQ-V1111-SEC-01 (MUST) — no secret value on any surface; the
boundary kept; nothing new reachable.** No unredacted secret value or
credential-shaped live value appears in this spec, the tests, fixtures,
briefs, reports, command output or commits; key **names** and the fake
`VALUE-abcdefgh12` are allowed; LAN addresses are `<addr>` in every
artefact this run writes (NG-06 for the historical ones);
**immediately after every commit created by T0–T6, before another
commit is made, the standalone `gitleaks-tree` block runs against that
commit and requires exit 0** (GATE-01's command, judged by its process
exit status; the evidence commit's exit in the tag message); the executor never opens `.env`, `data/`,
`bot.db`, `sandbox/`, `exec_audit.jsonl` (EC-01) — the sole `.env`
exception is EC-04's one non-printing `sed -i` replacement of
`LMSTUDIO_BASE_URL`; no command may print, copy, diff, grep, or
otherwise inspect `.env`. Nothing new is executed, written, reached or leaked
(`REQ-V1110-SEC-01`, `spec-v1.11.0.md:1159-1200`, carries): the `<pre>`
order redact → fit → escape is untouched (OUT-01 changes only the
exception predicate); the two new strings pass `redact()` through
`_send`; the batch constant changes no request body; the conftest
fixture only snapshots and restores an in-memory set (TST-02), never
logging or persisting it; `TelegramError.status` is an integer, the
message stays `redact`-ed (`bot.py:238`, `:244-262`). `gitleaks-tree`;
the command record; `E1`, `E7`.

---

## 6. Tests

**REQ-V1111-TST-03 (MUST) — the modules, the count, the table.** New
tests live in `tests/test_v1111_{out,tab,tst,doc,pin,ver}.py`, all
offline against `FakeTelegram`, `FakeEmbedder`, `httpx.MockTransport`
(`tests/test_v1110_out.py:94-95`'s `tg_client`) and `tmp_path`
databases; **27** new collected functions (T6: count ≥ floor + 27) plus
one verification by command; every id below appears in Appendix A;
`-VER-02`, `-PIN-01`, `-PIN-02` are EC-02's carve-out and `-DOC-03` is
green first by T4's ordering (EC-02).

### 6.1 The test table

| id | `module::function` | asserts | negative? |
|---|---|---|---|
| `T-V1111-OUT-01` | `tests/test_v1111_out.py::test_t_v1111_out_01_status_set_from_response` | `TelegramClient.call` over `MockTransport`: 400 → `status == 400`, `fatal False`; 401 → 401, `fatal True`; 429 (`retry_after` 0) → 429, `retry_after` set; 500 → 500; a handler raising `httpx.ConnectError` → `status is None`, `transport True`; 200 with `{"ok": false}` → 200 | — |
| `T-V1111-OUT-02` | `tests/test_v1111_out.py::test_t_v1111_out_02_fallback_on_400_send_and_edit` | `send_pre` over a 400-then-200 handler: exactly two requests, the second `{chat_id, text}` with `text == _pre_text(body)[1]`, no `parse_mode`; the same for `edit_pre` (`{chat_id, message_id, text}`); **the second failure**, on both `send_pre` and `edit_pre`: a 400-then-500 handler and a 400-then-`httpx.ConnectError` handler each see exactly two requests in total, the second without `parse_mode`, exactly one `sending the reply failed` / `editing the reply failed` line at ERROR, the helper returns `None`, no third request | yes (the second-failure cases) |
| `T-V1111-OUT-03` | `tests/test_v1111_out.py::test_t_v1111_out_03_no_fallback_on_429_after_budget` | `_sleep` replaced by a recorder; every response 429 (`retry_after` 0): `send_pre` returns `None`, exactly `SEND_ATTEMPT_LIMIT` requests, all with `parse_mode: "HTML"`, no plain resend, `SEND_ATTEMPT_LIMIT − 1` sleeps, one `sending the reply failed` log line | yes |
| `T-V1111-OUT-04` | `tests/test_v1111_out.py::test_t_v1111_out_04_no_fallback_on_5xx_or_transport` | a 500 handler → one request, `None`; a handler raising `httpx.ConnectError` every time → `SEND_ATTEMPT_LIMIT` HTML requests, no plain resend, `None`; `edit_pre` the same for 500 | yes |
| `T-V1111-OUT-05` | `tests/test_v1111_out.py::test_t_v1111_out_05_docstrings_current` | `bot.send_pre.__doc__` has `status`, `400`, not `bot.py:154-198`; `bot.edit_pre.__doc__` has `400-only`; `tables.fit_lines.__doc__` has no `bot.py:1190` and no `` `_fit` ``; `bot.IngestJob.__doc__` has `cancel.is_set()` and not `read and written only` | — |
| `T-V1111-TAB-01` | `tests/test_v1111_tab.py::test_t_v1111_tab_01_documents_id_width_five_round_trip` | a document with `id` `12345` (the executor's mechanism, recorded in `v1111-T2.md`) plus `T-V1110-DOC-01`'s two rows: `/documents` renders `12345` whole, every line ≤ 72 units, the 40-character name as `"f" * 21 + "…"` (22 units); `/delete #12345` through `process` deletes it (`document_count` −1, the reply names the file) | — |
| `T-V1111-TAB-02` | `tests/test_v1111_tab.py::test_t_v1111_tab_02_readme_documents_sample_byte_equal` | README's fenced `/documents` sample equals, line for line, `Your documents (2 of 20):`, a blank line and `render_table` over `T-V1110-DOC-01`'s fixture with `[5, 22, 4, 8, 6, 5, 10]`; `cut to 21 UTF-16 units` present, `23 UTF-16 units` absent | — |
| `T-V1111-TAB-03` | `tests/test_v1111_tab.py::test_t_v1111_tab_03_model_status_label_whole` | bare `/model`, both providers configured: the body has `openrouter model` and `lmstudio model` whole, no `…` in the `field` column; a 45-unit `openrouter_model` truncates to 40 with `…`; every line ≤ 72 units | — |
| `T-V1111-TAB-04` | `tests/test_v1111_tab.py::test_t_v1111_tab_04_sessions_empty_plain` | no `conversations` row: `tg.sent == [(USER_ID, bot.SESSIONS_EMPTY_REPLY)]`, no `parse_mode`; the constant equals TAB-03's string; after one message `/sessions` is a `<pre>` table with one data row; README's error section carries the string | — |
| `T-V1111-TAB-05` | `tests/test_v1111_tab.py::test_t_v1111_tab_05_doc_limit_reply_names_both_forms` | `bot.DOC_LIMIT_REPLY` equals TAB-04's string; **both admission paths through `process_update`**: (a) a caller at 20 documents uploading a 21st — `bot.py:2292`'s pre-admission site — gets exactly the literal as a plain send; (b) a caller admitted at 19 whose 20th document is inserted through `storage` before the worker commits — `bot.py:2128`'s `DocumentLimitExceededError` branch (the executor's mechanism, recorded in `v1111-T2.md`) — gets exactly the literal through `_document_error_ending`; in each case no document, chunk or vector row is inserted for the upload and `document_count` is unchanged; README's row carries it | — |
| `T-V1111-TAB-06` | `tests/test_v1111_tab.py::test_t_v1111_tab_06_single_batch_constant` | `not hasattr(documents, "EMBED_BATCH_SIZE")`; `documents.BATCH_SIZE is llm.embeddings.BATCH_SIZE == 32`; a size-recording `FakeEmbedder` over 65 chunks through `IngestWorker.run_one` saw `[32, 32, 1]` and the edits `📄 embedding: 1/3` … `3/3`; **and** a real `EmbeddingsClient` over `httpx.MockTransport` fed 65 inputs through the ingest path made exactly three embedding requests with body `input` sizes `[32, 32, 1]`, the same `1/3 … 3/3` edits alongside; README names `llm.embeddings.BATCH_SIZE`, not `documents.EMBED_BATCH_SIZE` | — |
| `T-V1111-TST-01` | `tests/test_v1111_tst.py::test_t_v1111_tst_01_err_row_11_session_usage` | TST-01 row 11, byte-equal, present in README | — |
| `T-V1111-TST-02` | `tests/test_v1111_tst.py::test_t_v1111_tst_02_err_row_12_session_unknown` | row 12 (`999999`); the active row unchanged | — |
| `T-V1111-TST-03` | `tests/test_v1111_tst.py::test_t_v1111_tst_03_err_row_13_delete_not_found` | row 13 (`#999`); `document_count` unchanged | — |
| `T-V1111-TST-04` | `tests/test_v1111_tst.py::test_t_v1111_tst_04_err_row_14_delete_usage` | row 14; README's `\|`-escaped form | — |
| `T-V1111-TST-05` | `tests/test_v1111_tst.py::test_t_v1111_tst_05_err_row_15_stale_callback` | row 15: `callback_answers[-1]["text"]`; nothing sent or edited; the cursor advanced | — |
| `T-V1111-TST-06` | `tests/test_v1111_tst.py::test_t_v1111_tst_06_err_row_16_model_unknown_and_usage` | row 16's two strings; no `bot_state` override row written | — |
| `T-V1111-TST-07` | `tests/test_v1111_tst.py::test_t_v1111_tst_07_secrets_registry_restored` | **the nested run**: a two-test module in `tmp_path` (A registers a sentinel and does not clean up; B asserts it absent from `config._secrets` and the registry `is` the same object) plus a `tmp_path` `conftest.py` importing `restore_secrets_registry` from `tests.conftest` (TST-02's VERIFY), never calling `secrets_registry_snapshot()`; `subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:xdist", "-q", str(tmp_path)])` exits 0; **plus the direct checks**: inside `conftest.secrets_registry_snapshot()` `register_secret("VALUE-abcdefgh12")` makes `redact` mask it; after the block the sentinel is gone, `redact` returns it unchanged, and `config._secrets` is the same object (`is`) | yes |
| `T-V1111-TST-08` | by command (no function): TST-02's two commands, recorded in T3's section | rt_06 alone passes; the suite under `-p xdist -n 4` passes twice | — |
| `T-V1111-DOC-01` | `tests/test_v1111_doc.py::test_t_v1111_doc_01_readme_limits_error_rows_versioning` | `## Limits` has the catalogue-cap row (`MODEL_CATALOGUE_MAX`) and the decimal/binary note; `## Error behaviour` has the `/documents` empty row (`DOCUMENTS_EMPTY_REPLY` verbatim), the `/sessions` row and the `Telegram 400 on a table-path send` row; `## Versioning` has DOC-01 (c)'s new clause and not the old one | — |
| `T-V1111-DOC-02` | `tests/test_v1111_doc.py::test_t_v1111_doc_02_plan_banner_and_agents_ruling` | `docs/plan.md` starts with the seven banner lines (the `go`-session handoff clause, `## v1.6.0 (in progress)`, `spec-v1.7.0.md`) and a blank line and the remainder equals `git show v1.11.0:docs/plan.md`; `AGENTS.md`'s `## Secrets` has `operator input, not secrets` and `treats them as out of scope` | — |
| `T-V1111-DOC-03` | `tests/test_v1111_doc.py::test_t_v1111_doc_03_v1110_report_and_post_corrected` | `report-v1.11.0.md` has `| 19 (236-254) |`, not `| 17 (236-252) |`; `## T2` names `743abc2`, `ef8e453`, `09f8d8a`; the T7 Phase A bullet names `33729eb` and `bundles`; `_lint_report_delegation` on it returns `[]`; the T7 waiver passage names `bot.py:2047` and `:2229` and has no `2222`; the tg-post has `236–254`, not `236–252`, `wc -m` ≤ 1500 | — |
| `T-V1111-PIN-01` | `tests/test_v1111_pin.py::test_t_v1111_pin_01_inventory_artefacts_exist` | `v1111-T0-pin-inventory.md` exists with the four-column header and names every site of PIN-01's list (literal in the test); `v1111-T0-nodeids.txt` exists, sorted, ≥ 2384 lines (EC-02: fewer is a precondition mismatch and the stop route, so the assertion and the floor agree), every line has `::` (carve-out) | — |
| `T-V1111-PIN-02` | `tests/test_v1111_pin.py::test_t_v1111_pin_02_no_v1110_test_renamed_or_listed` | every pair of `tests.test_v1110_inventory._SPEC_TEST_FUNCTIONS` resolves (import, `hasattr`); 61 entries; none names a `test_v1111_` module; `git diff v1.11.0 -- tests/test_v1110_inventory.py` empty | yes |
| `T-V1111-VER-01` | `tests/test_v1111_ver.py::test_t_v1111_ver_01_live_version_is_1_11_1` | the live `project.version == "1.11.1"`; `git show v1.11.0:pyproject.toml` reads `1.11.0` | — |
| `T-V1111-VER-02` | `tests/test_v1111_ver.py::test_t_v1111_ver_02_dependency_diff_version_only` | `git diff v1.11.0 -- pyproject.toml uv.lock` version-only under `dependency_diff_is_version_only` (`devtools/agent_eval.py:1279`); the dependency lists equal the tag blob's (carve-out) | — |
| `T-V1111-VER-03` | `tests/test_v1111_ver.py::test_t_v1111_ver_03_agents_md_and_release_row` | `AGENTS.md` carries T6's count and `152 entries`, both `as of spec-v1.11.1 T6`, the token `v1111-T<N>.md`, the NG-11 sentence; README has a `| v1.11.1 | 1.11.1 |` row ending `; this release |` and the `v1.11.0` row no longer does | — |
| `T-V1111-VER-04` | `tests/test_v1111_ver.py::test_t_v1111_ver_04_report_path_and_own_report_lint` | `lint-docs.report_path == "docs/reports/report-v1.11.1.md"`; `checks._lint_report_delegation` on that report returns `[]` | — |

---

## 7. Gates

**REQ-V1111-GATE-01 (MUST) — the eight gates verbatim; the schedule;
gate 8 exactly once at T5, reused at T6; the standalone `gitleaks-tree`
command; the gate-6 wall.** The eight commands of `AGENTS.md:150-158`
run **verbatim, in order, never through `checks.py run --profile
full`** (NG-13). **Schedule**: **T0** gates 1–5 on the unchanged
handoff tree, before any T0-generated file exists (gate 5 proves the
address; unreachable → blocked, ERR-01 row 6), then the standalone
`gitleaks-tree` below against T0's commit; **T1–T4**: gates 1–4 at each
commit, plus `checks.py lint-docs` and the standalone `gitleaks-tree`
below against each commit (T4: both); **the `gitleaks-tree` rule for
every task**: immediately after every commit created by T0–T6, before
another commit is made, run the standalone `gitleaks-tree` block
against that commit and require exit 0 — T5's fix, timeout and
report-only commits and T6's bump and evidence commits included; each
result is recorded as one line (commit sha, exit code) in the report's
per-task section, the evidence commit's in the tag message (RPT-01);
**T5**, after the review and its fix
commit (if any): run gates 1–6 and complete any timeout repair first
— gates 1–5, then **gate 6 once, alone on the box** (EC-04), its
direct wall `W` recorded with the `152/152` line —
`[[VERIFY: the gate-6 wall — v1.11.0's direct runs took 961.6 s (T7,
`report-v1.11.0.md:1669`) and 965.2 s (T8, `:1828`) at 152 entries
against `timeout_seconds: 1640`; decision rule: `W ≤ 1300 s` → the
value stays (NG-09); `W > 1300 s` → `REQ-V1110-MUT-01`'s hunk
(`ceil_to_100(1.25 × W)`, dated comment, brief `v1111-T5.md`) and gate 6
once more on that tree (ERR-01 row 7); `W > 2400 s` is reported, not a
stop]]`. **After all resulting commits, require a clean worktree
(empty `git status --porcelain`, recorded), set
`tested_tree=$(git rev-parse HEAD)`, then run gate 7, `doctor`,
`lint-docs`, the `bot_state` count re-read (`0`), and gate 8. No commit
or tracked change may occur between setting `tested_tree` and gate 8.**
Gate 8 runs **exactly once in the entire run**, the task's last live
action, its capture quoted in full; then the report-only commit.
T1–T2's `bot.py` changes are inside `GATE8_DEPENDENCIES`
(`devtools/agent_eval.py:1234-1242`), hence gate 8 at T5, never before. **T6**: run gates 1, 2, 3, 4, 5 and 6
once each, in that order, on the bump commit (gate 5 spends no tokens);
reuse gates 7 and 8 only after the identity check `git diff
<tested_tree> HEAD -- $(uv run --locked python devtools/agent_eval.py
--print-dependencies)` classified by `dependency_diff_is_version_only`
(`devtools/agent_eval.py:1279`): `True` → reused, recorded against
`tested_tree`; **`False` → gate 8 is not invoked: a T6 repair cycle
that reverts or corrects the hunk, reruns gates 1–6 and the check,
never gate 7 or 8** (`REQ-V1110-REV-02`, `spec-v1.11.0.md:1424-1435`;
ERR-01 row 10). **That T6 check on the bump commit is preliminary.
After T6's evidence-only commit and before the tag: re-run
`dependency_diff_is_version_only` from the gate-8 `tested_tree` to the
current `HEAD`; it MUST return `True`. This post-evidence check is the
definitive reuse verdict for the shipping tree; `False` withholds the
tag and enters REV-03** (E7; REV-02). **The evidence boundary**: the
report records everything available before the evidence commit — the
preliminary verdict, T5's gate-8 result, the per-commit `gitleaks-tree`
results up to and including T6's bump commit; the definitive
post-evidence verdict, E7's assertions, the final `lint-docs` and the
final `gitleaks-tree` exit are recorded in the **annotated tag message**
of `v1.11.1` (VER-01's six fields) and are never retroactively claimed
by the report. **The standalone
`gitleaks-tree` command** (C1): `devtools/checks.py`'s CLI has **no
single-gate form** — `run` accepts only `--profile
{pre-commit,pre-push,full}` (`devtools/checks.py:1876-1879`; `--only`
and `--select` are `devtools/mutation_check.py:2665-2666`'s, gate 6) —
so the gate's own `argv` (`config/quality_gates.yaml:140-141`) runs
directly against a tracked-only export, prompt 254's corrective form
(`docs/llm-usage.md:315`); verbatim, from the repository root:

```bash
tree_dir="$(mktemp -d)" &&
git archive HEAD | tar -x -C "$tree_dir" &&
gitleaks dir --no-banner --redact --config .gitleaks.toml \
  --report-format json --report-path "$tree_dir/gitleaks-tree.json" "$tree_dir"
rc=$?
rm -rf "$tree_dir"
echo "gitleaks-tree exit=$rc"
exit "$rc"
```

exit 0 = green, 1 = findings (`config/quality_gates.yaml:145-146`);
the block is run as one `bash` invocation (a script file or `bash -c`),
so `exit "$rc"` is the status its caller sees; the `echo` line is what
the report quotes, **but every gate invocation — this block and the
eight `AGENTS.md` commands alike — is judged by the process exit
status, never by parsing the echoed line.** `[[VERIFY: the single-gate
CLI form — absent at `2431034` (`grep -n "add_argument\|--only\|--gate\|--profile"
devtools/checks.py` shows `--profile` with three choices, no gate
selector); decision rule: a single-gate form found by T0's grep is
named in the report and replaces the block above; otherwise the block
is the only way `gitleaks-tree` runs alone and `--profile full` is
never typed]]`. **The gate matrix** of
`REQ-V1110-REV-02` (`spec-v1.11.0.md:1456-1486`, 29 rows) is unchanged
(NG-02, NG-13); `tests/test_v15_standards.py:1824` **stays pointed at
`spec-v1.11.0.md`**; this file carries no matrix. The gate tables at T0,
T5, T6; the reuse record; `E7`.

---

## 8. Version, reporting and the ledger

**REQ-V1111-VER-01 (MUST) — 1.11.1, where the bump lives, the release
rows, the local tag, no push.** `pyproject.toml:3` moves `1.11.0` →
`1.11.1` in **T6's first commit and nowhere else** (brief `v1111-T6.md`),
after T5's gates are green; `uv lock` regenerates `uv.lock` for the
literal only (`T-V1111-VER-02`); `tests/test_v1111_ver.py` lands in the
same commit (`-VER-01`, `-03` red before, green after). **Eleven pin
sites, rewritten in place under their names**: `tests/test_v1110_ver.py:75-78`
— **exactly as `REQ-V1110-VER-01` repointed `test_v1104_version.py`**
(`spec-v1.11.0.md:1521-1527`): only the live read becomes `git show
v1.11.0:pyproject.toml` == `"1.11.0"` (the `subprocess` shape of
`tests/test_v1104_version.py:60-67`), every other assertion stays;
`tests/test_v1110_ver.py:57`, `:106-112` (T6's count, `as of
spec-v1.11.1 T6`); `tests/test_v190_agents.py:138-162` (T6's numbers,
one history sentence); the `v1110-T<N>` token pins
`tests/test_v190_agents.py:92-99`, `tests/test_v1104_docs.py:141`,
`tests/test_v1102_docs.py:167`; the `report_path` pins
`tests/test_v190_agents.py:331-332`, `tests/test_v170_bench.py:329`,
`tests/test_v1102_gates.py:49`, `tests/test_v1104_gates.py:212-216`.
With them: `AGENTS.md:161-162`, `:172` → T6's count / `152 entries as
of spec-v1.11.1 T6`; `AGENTS.md:95` → `v1111-T<N>.md`; NG-11's
sentence; `config/quality_gates.yaml:797` `report_path` →
`docs/reports/report-v1.11.1.md`, so `lint-docs` runs against this
run's own report from T6's first commit on (`T-V1111-VER-04`). README's
release table (`README.md:1044-1047`) gains after the `v1.11.0` row,
which loses its `; this release` clause:

- `| v1.11.1 | 1.11.1 | the <pre> plain fallback narrowed to HTTP 400 (TelegramError.status); /documents ids render whole to 99,999 and the /model status label never truncates; /sessions empty state; DOC_LIMIT_REPLY names /delete #<id>; one embedding batch constant; ERR-01 rows 11-16 tested at dispatch; the secrets-registry fixture kills the xdist-order flake; README/plan/AGENTS drift and the v1.11.0 record corrected; mutation-all 152; model under test openai/gpt-4.1; shipped judge default anthropic/claude-sonnet-5; gate 8 judged by <effective judge>; gate 8 green on this run; this release |`

`<effective judge>` is `REQ-V1110-VER-01`'s row wording by reference
(`anthropic/claude-sonnet-5 (another vendor)` on the default route).
T6's second commit is the **evidence-only** commit (REV-02); the
annotated tag `v1.11.1` goes on **that** commit only, on green, as the
run's last action — **local, never pushed** (`git status -sb` shows
`ahead`; the report records the intent, the command record the tag).
**The tag message is the post-evidence record** (GATE-01's evidence
boundary): six required fields, one per line, exactly —
`tested_tree=<sha>`, `evidence_commit=<sha>`, `identity_verdict=True`,
`gitleaks_tree_exit=0`, `lint_docs=PASS`, `e7=PASS`; the tag is created
only when every field reads as above; any other value withholds the
tag and enters REV-03. Existing tags stay.
`T-V1111-VER-01…04`; `E7`.

**REQ-V1111-RPT-01 (MUST) — the report, the post, the usage rows, the
ledger.** `docs/reports/report-v1.11.1.md` carries `REQ-V1110-VER-03`'s
ten items (`spec-v1.11.0.md:1572-1600`) with this release's names — the
gate tables for T0, T5 (`W` and `152/152` and any timeout-hunk commit
first, then `tested_tree`, the empty porcelain, the override count, the
gate-8 capture in full) and T6 (gates 1–6 once each in order; 7 and 8
reused with the manifest and the preliminary verdict — **the report's
evidence boundary is the evidence commit**: the post-evidence verdict,
E7, the final `lint-docs` and the final `gitleaks-tree` exit live in
the annotated tag message (VER-01), never claimed by the report); the
collection
check (floor, final count, ≥ floor + 27, the empty `comm -23`); **the
delegation record per commit** (EC-03; every bundled orchestrator edit
named); the pin record (the inventory and every post-T0 amendment);
each task's "failed first" record; the review's dispositions;
`T-V1111-TST-08`'s two commands and summary lines; **the standalone
`gitleaks-tree` result per commit** — one line (commit sha, exit code)
in the per-task section for every commit of T0–T6 up to and including
T6's bump commit (the evidence commit's goes into the tag message);
**T4's second-commit bullet disclosing the bundled bookkeeping of
prompts 260 and 261** (EC-03); the `--no-verify` and "no push"
lines; the executor named in the report, in every `docs/llm-usage.md`
row (167 upward, one per prompt, the shape of rows 164–165) and in the
tg-post; **`## Operator inputs`** (the address as `<addr>`); **the
amendment table** (§3.2's rows plus any disclosed pin) — plus
`docs/reports/tg-post-v1.11.1.md`, **Russian**, ≤ 1500 characters by
`wc -m` (quoted), naming `claude-sonnet-5`, the link
`https://github.com/axyi/tg-agent-bot`, the spec and report paths,
"gate 8 green on this run"; and the ledger-row block (`ledger_header`
verbatim from `config/quality_gates.yaml:798`, `Ver` = `1.11.1`,
`Prompts` = the real count and range) — the operator appends it to the
lab's `economics.md` after the v1.11.0 row (found by name, never by
`tail`). The T0 skeleton carries `## Operator inputs`, `## T0 —
preflight` and the ledger block. The T0, T5 and T6 records;
`T-V1111-VER-04`; `T-V1111-DOC-03`.

---

## 9. Acceptance, review and the stop route

**REQ-V1111-REV-01 (MUST) — review in a clean context, before the gates
that matter.** Code review by the `code-reviewer` subagent
(`.claude/agents/code-reviewer.md:4`, `model: sonnet`) in **its own
clean context** at T5 — after T1–T4, before T5's gate run. Never
self-review in the writing context. Findings are fixed (delegated by
brief `v1111-T5.md` when they write source — T5's first commit) or
waived with a reason; the review prompt is logged. Beyond the standard
checklist: (1) `send_pre`/`edit_pre` resend only on `status == 400`,
`_call_with_retry` byte-unchanged, every `call` raise after a response
carries `status`; (2) the two width lists in place, sums 72 / 58,
README's sample regenerated; (3) `SESSIONS_EMPTY_REPLY` on the plain
path, `render_table` untouched for ≥ 1 row; `DOC_LIMIT_REPLY` one
literal; (4) `documents.EMBED_BATCH_SIZE` gone, the import in, the
checkpoint cadence unchanged, both monkeypatch sites repointed; (5)
`SYSTEM_PROMPT`, `tools.tool_specs()`, `REQUEST_DEFAULTS`,
`load_context_messages`, gate 5, gate 7, `devtools/agent_eval.py` and
its datasets byte-equal to `2431034` (NG-01, NG-11); no new dependency;
`SCHEMA_VERSION == 6`; (6) the conftest fixture mutates the registry in
place, no other test file changed for TST-02; (7) every v1110 pin
rewritten in place, nothing renamed or deleted, the inventory list
untouched; (8) every new or changed string in ERR-01 and README; no
secret value or LAN literal in anything this run wrote; (9) the three
docstrings match the code.

**REQ-V1111-REV-02 (MUST) — acceptance, the freeze, regression, the two
two-commit tasks, no push.** **T5 is one prompt (262)** and at most
three commits: the review's fix commit (only on a must-fix; brief
`v1111-T5.md`), ERR-01 row 7's timeout hunk (only if `W > 1300 s`),
then — after gates 1–6 and any timeout repair, a clean worktree,
`tested_tree`, gate 7, `doctor`/`lint-docs`/the count, and gate 8
(GATE-01's T5 sequence) — the **report-only** commit
(`docs/reports/report-v1.11.1.md`, `docs/prompts/262-*.md`,
`docs/llm-usage.md`); the standalone `gitleaks-tree` runs immediately
after each of these commits (GATE-01). **T6 is one prompt (263) and
two commits**, each followed at once by the standalone `gitleaks-tree`: the
first (brief `v1111-T6.md`: `pyproject.toml`, `uv.lock`, the yaml's one
line, the tests, the documentation) lands VER-01; then run gates 1, 2,
3, 4, 5 and 6 once each, in that order; the preliminary identity check
(reuse gates 7 and 8 only after it); the collection and node-id checks;
`checks.py replay --range v1.11.0..HEAD`; Appendix B's E1–E6 via
`pytest tests/test_v1111_*.py`, all recorded **before the evidence
commit**; **T6's second commit is evidence-only**, its path set exactly
four: `docs/reports/report-v1.11.1.md`,
`docs/reports/tg-post-v1.11.1.md`, the single `docs/prompts/263-*.md`,
`docs/llm-usage.md` — **no other path may differ**. After it and before
the tag: re-run `dependency_diff_is_version_only` from the gate-8
`tested_tree` to the current `HEAD`; it MUST return `True` — **the
definitive reuse verdict for the shipping tree; `False` withholds the
tag and enters REV-03** (the earlier T6 check is preliminary); then
`E7`, `lint-docs` and the standalone `gitleaks-tree` run against that
commit; **their results are not written into the report** (it lives
inside the commit they judge) but into the annotated tag message —
VER-01's six fields (`tested_tree`, `evidence_commit`,
`identity_verdict=True`, `gitleaks_tree_exit=0`, `lint_docs=PASS`,
`e7=PASS`); only when every field reads so is the annotated tag
`v1.11.1` created on that commit — **locally; `git push` is not a
command this run issues**; any other value withholds the tag and
enters REV-03. **Regression, no weakened posture**: every earlier release's
acceptance properties hold; every `T-V1110-*` test green with only
PIN-01's in-place rewrites; failures are fixed inside the 3-cycle
budget, never by a relaxed gate, a deleted test, a lowered floor, an
edited case or a model switch.

**REQ-V1111-REV-03 (MUST) — the stop route.** A stop at any task (an
exhausted repair budget, gate 8 exit 1, a spec ambiguity under EC-02,
a T0 collected count below 2384 — a base-tree/precondition mismatch,
no repair cycle (EC-02, ERR-01 row 13) — the preliminary identity check
not restorable at T6, the post-evidence identity check `False` or any
other VER-01 tag-message field not reading as required): (1) the
artefacts finalised
with the stop stated (stage, task, cause, the gate capture quoted); (2)
gates 1–4 re-run on the stopped tree; gates 5–8 not touched (recorded
results reused or `N/A`; **gate 8 never rerun**); (3) if the stop
occurs before T6's first commit, `pyproject.toml` remains `1.11.0`; if
it occurs after that commit, leave `1.11.1` in place rather than
rewriting history, but create no tag (`git tag -l v1.11.1` empty) and
use the stopped-release README row of (4); (4) README's
release table gains `| v1.11.1 | — | run stopped at T<n> … |` in the
form of `README.md:1044-1045`'s precedents; (5) the usage rows and the
ledger block filled (`Ver` = whatever `pyproject.toml` reads); (6) the
evidence commit touches `docs/reports/*`, README's one row,
`docs/llm-usage.md` and its prompt file only; `lint-docs` and
`gitleaks-tree` green against it, both exit statuses in the command
record (a stopped run has no tag message to carry them and the report
cannot claim them — GATE-01's evidence boundary); no `--no-verify`; no
later task runs.
A blocked run (ERR-01 row 6) is not a stop: only T0's prompt and
skeleton are committed and the operator re-issues `go`. The report's
stop section is the artefact; Gherkin has no scenario for it.

---

## 10. Implementation order

One prompt and one commit per task (256…263; the T4, T5 and T6
exceptions of EC-04); tests before the code they cover, in the same
task.

| T | task | acceptance |
|---|---|---|
| **T0** | Preflight: EC-04's structural preconditions (*commands only*); gates 1–5 on the unchanged handoff tree, before any T0-generated file exists; the measurements first (the floor, `v1111-T0-nodeids.txt`, `len(MUTATIONS)` 152, the `bot_state` count `0`); **the pin inventory delegated** (brief `v1111-T0.md` → `v1111-T0-pin-inventory.md`, PIN-01), **then the same subagent writes `tests/test_v1111_pin.py`** and runs PIN-01/-02 once the inventory artefacts exist; `docs/prompts/256-go-spec-v1.11.1.md`; the report skeleton (*artefacts only*); the standalone `gitleaks-tree` immediately after T0's commit | the precondition outputs recorded (the tag's 40-hex sha, the ancestor check, `describe`, the `docs/`-only name list, the empty porcelain); every item recorded; the floor measured before `tests/test_v1111_pin.py` existed (stated) and ≥ 2384 — fewer is the stop route (EC-02, ERR-01 row 13); the inventory complete, the rename mapping empty; `T-V1111-PIN-01`, `-02` green; `gitleaks-tree` exit 0 on T0's commit, recorded; no key value or address literal anywhere |
| **T1** | OUT-01, OUT-02 (brief `v1111-T1.md`): `tests/test_v1111_out.py` first (red for the right reason), then `TelegramError.status`, the `call` raises, the 400-only predicate, the three docstrings; gates 1–4, `lint-docs`, `gitleaks-tree` | `T-V1111-OUT-01…05` green; `T-V1110-OUT-05` green unamended; `_call_with_retry` byte-equal to `2431034`; `gitleaks-tree` exit 0 on the commit, recorded |
| **T2** | TAB-01…05 (brief `v1111-T2.md`, the T2 pin rows copied in): `tests/test_v1111_tab.py` first; the widths, the two strings, the batch import; README's sample regenerated, the `:217` and `:153-154` sentences, the `:993` row, the embeddings paragraph, TAB-03/TAB-04's error rows; PIN-01's five T2 pin rewrites in place; gates 1–4, `lint-docs`, `gitleaks-tree` | `T-V1111-TAB-01…06` green; the amendment table's two rows in the report; `documents.EMBED_BATCH_SIZE` absent; `T-V1111-TAB-05` drives both cap sites through `process_update`; `gitleaks-tree` exit 0 on the commit, recorded |
| **T3** | TST-01, TST-02 (brief `v1111-T3.md`): `tests/test_v1111_tst.py` (six rows + `TST-07`); `tests/conftest.py`'s context manager and autouse fixture; `T-V1111-TST-08`; gates 1–4, `lint-docs`, `gitleaks-tree` | the six rows byte-equal at dispatch and in README; rt_06 alone green; the xdist suite green twice, summaries quoted; no test file but `conftest.py` and the new module changed; `gitleaks-tree` exit 0 on the commit, recorded |
| **T4** | **First** DOC-03's five edits — prompt **260**, one commit (*artefacts only*: `docs/reports/report-v1.11.0.md` and `docs/reports/tg-post-v1.11.0.md` exclusively, no test, no bookkeeping); **then** DOC-01 (a)–(c), DOC-02 **and** `tests/test_v1111_doc.py` (all three DOC tests, written first; `-DOC-01`, `-02` red before their edits, `-DOC-03` green by the first commit, EC-02) — prompt **261**, one commit, delegated (brief `v1111-T4.md`), carrying as bundled orchestrator artefacts `docs/prompts/260-*.md`, `docs/prompts/261-*.md` and both `docs/llm-usage.md` rows, disclosed in its body and bullet (EC-03's nine-path set); gates 1–4, `lint-docs`, `gitleaks-tree` after each commit | `T-V1111-DOC-01…03` green; `docs/plan.md` differs from `v1.11.0` by the banner only; `lint-docs` green against `report-v1.11.0.md` (the T7 bullet parses); the first commit's `git show --stat` names exactly `docs/reports/report-v1.11.0.md` and `docs/reports/tg-post-v1.11.0.md`; the second commit's names only paths of EC-03's nine-path set; `gitleaks-tree` exit 0 on each commit, recorded |
| **T5** | **Review (REV-01) in a clean context**; a must-fix → the fix commit (brief `v1111-T5.md`); then gates 1–6 and any timeout repair (row 7's hunk committed, gate 6 once more); after all resulting commits a clean worktree, `tested_tree=$(git rev-parse HEAD)`, then gate 7, `doctor`/`lint-docs`/the count and **gate 8 once** — no commit or tracked change in between; the report-only commit (prompt 262); the standalone `gitleaks-tree` immediately after each of T5's commits | findings closed or waived; `152/152` with `W`; `tested_tree` set after the last T5 source commit; gate 8 exit 0, floors met, recorded against `tested_tree`; exit 1 → REV-03; `gitleaks-tree` exit 0 on every T5 commit, recorded |
| **T6** | VER-01 (brief `v1111-T6.md`): the bump, `uv lock`, `tests/test_v1111_ver.py`, the eleven in-place repoints VER-01 lists, `report_path`, README's row and the `v1.11.0` clause, AGENTS.md's count lines, token and NG-11 sentence; gates 1, 2, 3, 4, 5 and 6 once each, in that order; the preliminary identity check (reuse 7 and 8 only after it), the collection and node-id checks, `replay`, E1–E6; `gitleaks-tree` immediately after the bump commit (in the report); the evidence commit (*artefacts only*); **the post-evidence identity check** (`dependency_diff_is_version_only` from the gate-8 `tested_tree` to `HEAD`, the definitive verdict), E7, `lint-docs`, `gitleaks-tree` — their results into the annotated tag message (VER-01's six fields), never into the report; the tag; **no push** | `T-V1111-VER-01…04` (01/03 red before, green after); `dependency_diff_is_version_only` `True` on the bump commit **and** `True` again from `tested_tree` to the evidence commit before the tag (`False` → no tag, REV-03); gate 8 executed once; count ≥ floor + 27; `comm -23` empty; the evidence commit's `git show --stat` names exactly the four paths; `gitleaks-tree` exit 0 on the bump commit (recorded in the report) and on the evidence commit (`gitleaks_tree_exit=0` in the tag message); the tag message's six fields read exactly as VER-01 requires; no push in the command record |

### 10.1 Per-task reading map

The authority for EC-03; §1, §2 and §9 bind every task; a `no` cell
carries a §5.1 exemption **verbatim**; the report records map versus
actual per commit.

| T | spec sections | repository files and ranges | delegate? |
|---|---|---|---|
| **T0** | §1, §3.5, §4 (rows 6, 13), §7 (the T0 gates), §9 (the blocked-run clause), §6.1 (PIN) | `AGENTS.md:146-175`; `config/quality_gates.yaml:137-151`, `:738-752`, `:797-799`; `pyproject.toml:1-21`; `docs/prompts/TEMPLATE.md`; the grep hits PIN-01 lists (line context only); `tests/test_v1110_inventory.py` (the frozen list, read only); `tests/test_v1111_pin.py` (created, after the measurements) | **yes** for the pin inventory and `tests/test_v1111_pin.py` — brief `v1111-T0.md`; **no** — *commands only* — for the preconditions, gates and measurements (the floor measured before the module exists); **no** — *artefacts only* — for the prompt file and the report skeleton |
| **T1** | §3.1, §4 (rows 3–4), §6.1 (OUT) | `bot.py:176-188`, `:219-263`, `:265-280`, `:1917-1928`, `:2512-2585`; `tables.py:134-139`; `tests/test_v1110_out.py:94-95`, `:359-422`; `tests/test_v1111_out.py` (created) | **yes** — brief `v1111-T1.md` (OUT-02's docstring texts copied in) |
| **T2** | §3.2, §4 (rows 1–2), §6.1 (TAB) | `bot.py:109`, `:128-141`, `:1530-1546`, `:1868-1876`, `:2115-2130`, `:2280-2295`, `:2333-2380`, `:2445-2471`; `tables.py:17`, `:82-131`; `documents.py:386`, `:548-562`, `:570-578`; `llm/embeddings.py:8-15`, `:55-67`; `README.md:150-155`, `:213-232`, `:538-547`, `:953-1002`; the T2 pin sites (±5); `tests/test_v1110_out.py:94-95` (the `MockTransport` shape for TAB-06); `tests/test_v1111_tab.py` (created) | **yes** — brief `v1111-T2.md` (the widths, the strings, the README paragraph, the pin rows copied in) |
| **T3** | §3.3, §6.1 (TST) | `config.py:98`, `:230-241`, `:290-306`; `tests/conftest.py`; `tests/__init__.py` (presence) and `pyproject.toml`'s `[tool.pytest.ini_options]` (TST-07's VERIFY); `tests/test_v1110_err.py:50-116`; `tests/fakes.py:150-200`; `tests/test_v1103_red_team.py:340-353`; `bot.py:88-92`, `:1636`, `:1815-1826`, `:2405-2416`, `:2472-2490`; `tests/test_v1111_tst.py` (created) | **yes** — brief `v1111-T3.md` (the six rows and the fixture shape copied in) |
| **T4** | §3.4, §4 (README rows), §6.1 (DOC) | `README.md:918-1012`; `docs/plan.md:1-8`, `:25`, `:215`; `AGENTS.md:325-328`; `docs/reports/report-v1.11.0.md:274-280`, `:1529-1541`, `:1698-1700`, `:1945`; `docs/reports/tg-post-v1.11.0.md:23`; `tests/test_v1111_doc.py` (created) | **yes** — brief `v1111-T4.md` (second commit; prompt 260's and 261's prompt files and usage rows bundled as orchestrator artefacts, disclosed — EC-03's nine-path set); **no** — *artefacts only* (first commit: `docs/reports/report-v1.11.0.md` and `docs/reports/tg-post-v1.11.0.md` exclusively) |
| **T5** | §9 (REV-01, REV-02), §7, §4 (rows 7–9, 12) | the review's own reading map; otherwise only commands; `config/quality_gates.yaml:738-752` on row 7's branch only (its hunk committed before `tested_tree` is set) | **no** — *the task is itself the clean-context review*; **yes** for a source-writing fix or row 7's hunk — brief `v1111-T5.md`; **no** — *commands only* — for the gates (`tested_tree` set after the last source commit, nothing committed until gate 8 has run); **no** — *artefacts only* — for the report-only commit |
| **T6** | §8, §9 (REV-02), §7 (the identity check), §1 (the floor), §4 (rows 10–11) | `pyproject.toml:3`; VER-01's eleven pin sites (±5 lines) and `tests/test_v1104_version.py:55-67` (the shape); `config/quality_gates.yaml:790`; `README.md:1044-1047`; `AGENTS.md:92-97`, `:159-172`, `:274-282`; `tests/test_v1111_ver.py` (created); `v1111-T0-nodeids.txt` | **yes** for the bump commit — brief `v1111-T6.md`; **no** — *artefacts only* — for the evidence commit; **no** — *commands only* — for the gates in order, the preliminary and the post-evidence identity checks, the per-commit `gitleaks-tree` runs and the tag with its six-field message |

---

## Appendix A — requirement traceability

The **twenty-six** rows are in bijection with the twenty-six `MUST` ids
of §§1–10; never "by inspection"; every `T-V1111-*` id of §6.1 is cited
at least once.

| Requirement | Verified by |
|---|---|
| `REQ-V1111-EC-01` | `T-V1111-VER-02`; the gate tables and command record (no live gate outside GATE-01's schedule; no push); `T-V1111-VER-03` (the NG-11 sentence) |
| `REQ-V1111-EC-02` | the T0 count (measured before `tests/test_v1111_pin.py` exists; ≥ 2384 or the stop route, ERR-01 row 13) and T6 check; the carve-out ids' initial results and `T-V1111-DOC-03`'s; `T-V1111-PIN-01`, `T-V1111-PIN-02`; every post-T0 amendment in its bullet |
| `REQ-V1111-EC-03` | §10.1; the briefs `v1111-T0.md`, `-T1`, `-T2`, `-T3`, `-T4` (the second commit), `-T6`, `-T5` iff a fix or a timeout hunk; T4's first commit the two `docs/reports/*` files only, its second commit inside EC-03's nine-path set with the bundled bookkeeping of prompts 260 and 261 disclosed in its bullet (`git show --stat` on both); the per-commit record under `lint-docs` (`T-V1111-VER-04`) |
| `REQ-V1111-EC-04` | T0's structural precondition outputs (the tag's 40-hex sha, the ancestor check, `describe --abbrev=0`, the `docs/`-only name list, the empty porcelain); the `bot_state` count at T0 and T5; the report's prompt/commit table; `gitleaks-tree` immediately after every commit (the evidence commit's exit in the tag message); `E7` |
| `REQ-V1111-OUT-01` | `T-V1111-OUT-01`, `T-V1111-OUT-02` (the 400 → 200 and the second-failure cases), `T-V1111-OUT-03`, `T-V1111-OUT-04`; `T-V1110-OUT-05` unamended; `E1` |
| `REQ-V1111-OUT-02` | `T-V1111-OUT-05`; REV-01 item 9 |
| `REQ-V1111-TAB-01` | `T-V1111-TAB-01`, `T-V1111-TAB-02`; the amendment table; `E2` |
| `REQ-V1111-TAB-02` | `T-V1111-TAB-03`; the amendment table; `E4` |
| `REQ-V1111-TAB-03` | `T-V1111-TAB-04`; `E3` |
| `REQ-V1111-TAB-04` | `T-V1111-TAB-05` (both admission sites, `bot.py:2292` and `:2128`, through `process_update`) |
| `REQ-V1111-TAB-05` | `T-V1111-TAB-06` (the `FakeEmbedder` cadence and the `MockTransport` request count); `E5` |
| `REQ-V1111-TST-01` | `T-V1111-TST-01`, `T-V1111-TST-02`, `T-V1111-TST-03`, `T-V1111-TST-04`, `T-V1111-TST-05`, `T-V1111-TST-06` |
| `REQ-V1111-TST-02` | `T-V1111-TST-07` (the nested run proves the autouse fixture; the direct checks the context manager); `T-V1111-TST-08` (quoted in T3's record); `E6` |
| `REQ-V1111-DOC-01` | `T-V1111-DOC-01` (T4's second commit, brief `v1111-T4.md`); `T-V1111-TAB-02`, `T-V1111-TAB-04`, `T-V1111-TAB-05`, `T-V1111-TAB-06` (the T2 hunks) |
| `REQ-V1111-DOC-02` | `T-V1111-DOC-02` (T4's second commit, brief `v1111-T4.md`) |
| `REQ-V1111-DOC-03` | `T-V1111-DOC-03` (the five edits, `:2229` included; lands in T4's second commit, green by the first — EC-02); the first commit's `git show --stat` (the two `docs/reports/*` files only, *artefacts only*, no bookkeeping); `lint-docs` green against `report-v1.11.0.md` at T4 |
| `REQ-V1111-PIN-01` | `T-V1111-PIN-01`, `T-V1111-PIN-02` (`tests/test_v1111_pin.py`, written by the delegated T0 subagent after the measurements, in T0's commit); the inventory artefact; the T6 `comm -23` line |
| `REQ-V1111-ERR-01` | `T-V1111-TAB-04`, `T-V1111-TAB-05`, `T-V1111-OUT-02`, `T-V1111-OUT-03`, `T-V1111-OUT-04`, `T-V1111-DOC-01` (rows 1–4); the task records (rows 5–13) |
| `REQ-V1111-SEC-01` | `gitleaks-tree` immediately after every commit, judged by exit status (the evidence commit's exit in the tag message); the command record (no `.env` inspection beyond EC-04's one `sed -i`); `T-V1111-TST-07`; `E1`, `E7` |
| `REQ-V1111-TST-03` | the T6 collection check; `tests/test_v1111_*.py` present; Appendix A complete |
| `REQ-V1111-GATE-01` | the gate tables at T0, T5, T6; `tested_tree` set after the last T5 commit and the clean-tree proof; the gate-6 wall; the reuse record with the preliminary verdict in the report and the post-evidence verdict in the tag message; the `gitleaks-tree` line per commit; the annotated tag message's six fields; `E7` |
| `REQ-V1111-VER-01` | `T-V1111-VER-01`, `T-V1111-VER-02`, `T-V1111-VER-03`, `T-V1111-VER-04`; the tag message's six fields (`git tag -n99 v1.11.1`); `E7` |
| `REQ-V1111-RPT-01` | the report under `lint-docs` (`T-V1111-VER-04`); the evidence boundary kept (no post-evidence claim in the report; the per-commit `gitleaks-tree` lines up to the bump commit); `wc -m` quoted; the usage rows; the fenced ledger row; `T-V1111-DOC-03` |
| `REQ-V1111-REV-01` | the logged review prompt; findings closed or waived; `v1111-T5.md` iff a fix |
| `REQ-V1111-REV-02` | `git show --stat` on the evidence commit; E1–E6 before it; the post-evidence identity check and `E7` after it, before the tag, recorded in the tag message; `gitleaks-tree` after each T5/T6 commit; the full suite green |
| `REQ-V1111-REV-03` | the stage named in the report; the negative proofs (`pyproject.toml` `1.11.0` before T6's first commit or `1.11.1` after it, `git tag -l v1.11.1` empty, `git status -sb` ahead); the reused gate-8 record |

### Tails traceability

Every inventory item, mapped to the id that closes or declines it:

| item | tail | closed by |
|---|---|---|
| A1 | prompt 239 on three T2 commits | `DOC-03` (edit 3); `EC-04`; `NG-15` |
| A2 | 236–252 (17) vs 236–254 (19) | `DOC-03` (edits 1–2) |
| A3 | LAN literals, v1.11.0 and ≈ 70 older sites | `DOC-02`; `NG-06`; `EC-04`/`SEC-01` (`<addr>`) |
| A4 | `33729eb` bundles a yaml hunk; the record says "commands-only" | `DOC-03` (edit 4); `EC-03` |
| B1 | `cancel_reason` read outside the lock vs the docstring | `OUT-02` (c); `DOC-03` (edit 5); `NG-16` |
| B2 | the fallback fires on any non-fatal error | `OUT-01`; `OUT-02` (a); `ERR-01` rows 3–4; `DOC-01` (b) |
| B3 | `[12, 44]` truncates `openrouter model` | `TAB-02`; `NG-07` |
| B4 | the escape entry's `why` vs collection order | `NG-14` |
| C1 | `--profile full` run for `gitleaks-tree` | `GATE-01`; `NG-13`; `ERR-01` row 12 |
| C2 | the vacuous lock-spy assertion (fixed) | `NG-05` |
| C3 | `_TypingIndicator` off the document path | `NG-03` |
| C4 | the 72-unit ceiling holds | `NG-17` |
| C5 | `#` width 3 truncates ids ≥ 1000 | `TAB-01`; `E2` |
| C6 | decimal KB/MB vs MiB | `DOC-01` (a); `NG-04` |
| C7 | embeddings provider text | `NG-17` |
| C8 | two batch constants | `TAB-05`; `E5` |
| C9 | `docs/plan.md`'s last release section is v1.6.0 | `DOC-02`; `NG-08` |
| C10 | rows 11–16 untested | `TST-01` |
| C11 | the xdist-order flake | `TST-02`; `E6` |
| C12 | `/sessions` header-only | `TAB-03`; `ERR-01` row 1; `E3` |
| C13 | `fit_lines` cites `_fit` | `OUT-02` (b) |
| C14 | `send_pre` cites `bot.py:154-198` | `OUT-02` (a) |
| C15 | the empty-state row; `DOC_LIMIT_REPLY` | `DOC-01` (b); `TAB-04`; `ERR-01` row 2 |
| C16 | no catalogue-cap row | `DOC-01` (a) |
| E1 | commands table vs dispatch | `NG-17` |
| E2 | the samples | `NG-17`; `TAB-01` |
| E3 | Limits vs constants | `DOC-01` (a); `NG-17` |
| E4 | the release rows | `NG-17`; `VER-01` |
| E5 | AGENTS.md counts | `NG-17`; `VER-01` |
| E6 | `spec-v1.md:135` | `NG-07` |
| E7 | `docs/plan.md` "in progress" | `DOC-02`; `NG-08` |
| E8 | `.env.example` | `NG-17` |
| E9 | `## Switch provider` | `NG-17` |
| F1 | the exact lock-spy delta | `NG-05` |
| F2 | thread tests, bounded waits | `NG-17` |
| F3 | 2384 / 152 | `EC-02`; `NG-02`; `NG-17` |
| F4 | the one recorded instability | `TST-02` |
| F5 | fixture literals | `NG-06`; `NG-17` |
| G1 | `handoff-v1.11.0.md:13-14` | `NG-06`; `DOC-02` |
| G2 | two stale self-citations | `OUT-02` (a), (b) |
| G3 | escaped pipes | `NG-17`; `TST-01` |
| G4 | the duplicate batch constant | `TAB-05` |
| G5 | the v1.6.0-era sentence | `DOC-01` (c) |
| G6 | 17 vs 19 in the ledger rows | `DOC-03` (edit 1) |

---

## Appendix B — acceptance scenarios (Gherkin, written before code)

Offline; T6 records E1–E6 **before the evidence commit** (`pytest
tests/test_v1111_*.py`); E7 is the post-commit/pre-tag check, recorded
in the annotated tag message (GATE-01's evidence boundary).

```gherkin
Feature: E1 — the plain fallback fires on 400 only
  Scenario: the HTML sendMessage answers 400
    Given a TelegramClient over a MockTransport answering 400 then 200
    When send_pre sends a body
    Then exactly two requests were made, the second {chat_id, text} with the fitted body and no parse_mode
  Scenario: the HTML sendMessage answers 429 until the retry budget is spent
    Given _sleep recorded and every response 429
    When send_pre sends a body
    Then exactly SEND_ATTEMPT_LIMIT requests, all parse_mode HTML, no plain resend, None returned, one "sending the reply failed" line logged
  Scenario: a 5xx or a transport error
    Then no plain resend, None returned
  Scenario: the plain resend fails too
    Given a MockTransport answering 400 then 500, and another answering 400 then raising ConnectError
    When send_pre, and then edit_pre, sends a body over each
    Then exactly two requests in total, the second without parse_mode, one "sending the reply failed" / "editing the reply failed" line at ERROR, None returned, no third request

Feature: E2 — /documents ids round-trip through /delete #<id>
  Scenario: a document with id 12345 among the two fixture rows
    When the caller sends /documents, then /delete #12345
    Then 12345 rendered whole, no line over 72 units, the 40-character name as 21 f + …; the document, its chunks and vectors are gone and the reply names the file

Feature: E3 — /sessions with no sessions
  Scenario: a caller with no conversations row
    Then one plain message "No sessions yet. Send me a message to start one.", no parse_mode; after one message /sessions is a <pre> table with one data row

Feature: E4 — the /model status label is never truncated
  Scenario: both providers configured, bare /model
    Then the body has "openrouter model" and "lmstudio model" whole, no field cell ends in …, a 45-unit value is cut to 40 with …, every line ≤ 72 units

Feature: E5 — one embedding batch constant
  Scenario: 65 chunks through IngestWorker.run_one with a size-recording FakeEmbedder
    Then batches of [32, 32, 1], edits embedding: 1/3 … 3/3, documents has no EMBED_BATCH_SIZE and documents.BATCH_SIZE is llm.embeddings.BATCH_SIZE
  Scenario: 65 inputs through the ingest path with a real EmbeddingsClient over httpx.MockTransport
    Then exactly three embedding requests were made, their body input sizes [32, 32, 1], the edits 1/3 … 3/3 alongside

Feature: E6 — rt_06 is order-independent
  Scenario: a nested pytest run of two ordered tests under the project's autouse fixture
    Given a tmp_path module where test A registers a sentinel and never cleans up and test B asserts it absent and the registry the same object, and a tmp_path conftest.py importing restore_secrets_registry from tests.conftest
    When the module runs under python -m pytest -p no:cacheprovider -p no:xdist -q, never calling secrets_registry_snapshot()
    Then the nested run exits 0
  Scenario: a secret registered inside conftest.secrets_registry_snapshot()
    Then after the block the sentinel is gone, redact returns it unchanged, the registry is the same set object
  Scenario: the suite under pytest-xdist
    Then rt_06 passes alone and the full suite passes twice under -p xdist -n 4 (T-V1111-TST-08, by command)

Feature: E7 — the version, the freeze and the local tag
  Scenario: T6's first commit
    Then pyproject.toml reads 1.11.1, git show v1.11.0:pyproject.toml reads 1.11.0, the pyproject.toml/uv.lock diff is version-only, dependency_diff_is_version_only is True on tested_tree..HEAD, AGENTS.md reads "as of spec-v1.11.1 T6", the v1.11.1 row ends "this release" and the v1.11.0 row does not
  Scenario: run before the tag on T6's evidence commit
    Then dependency_diff_is_version_only from the gate-8 tested_tree to HEAD is True (the definitive reuse verdict; False withholds the tag, REV-03); its name-only diff is exactly the four REV-02 paths; git tag -l lists no v1.11.1 yet; git status -sb shows main ahead; gitleaks-tree exits 0 (the process status, not the echoed line)
  Scenario: the annotated tag is created
    Then its message carries exactly tested_tree=<sha>, evidence_commit=<sha>, identity_verdict=True, gitleaks_tree_exit=0, lint_docs=PASS, e7=PASS, one per line; report-v1.11.1.md claims none of them; any other value means no tag and REV-03
```

---

## Appendix C — cross-review log

**Rounds so far: 2** — termination pending. Placeholder: finalised by
the spec-authoring pipeline after the last round (at most three,
challenger OpenAI Codex), every finding ruled on before it is applied;
the termination reason and per-round counts recorded. Until then,
`Status:` stays `draft`.

### Round 1 of at most 3 — against the authoring draft (`8de5485`); 10 findings, 10 accepted (2 adapted), 0 rejected

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R1-1 | Crit | GATE-01, REV-02, REV-03, ERR-01 row 10, `E7` | accepted | After T6's evidence-only commit and before the tag, `dependency_diff_is_version_only` is re-run from the gate-8 `tested_tree` to `HEAD` and MUST be `True` — the definitive reuse verdict for the shipping tree; `False` withholds the tag and enters REV-03; the bump-commit check is preliminary. |
| R1-2 | Crit | GATE-01, EC-04, REV-02, ERR-01 row 7, §10 T5 | accepted | T5 runs gates 1–6 and completes any timeout repair first; after all resulting commits a clean worktree is required, `tested_tree=$(git rev-parse HEAD)` is set, then gate 7, doctor/lint/count and gate 8 run with no commit or tracked change in between (T5 is therefore at most three commits). |
| R1-3 | High | GATE-01, SEC-01, RPT-01 | accepted | The standalone `gitleaks-tree` block ends with `exit "$rc"` and is run as one `bash` invocation; every gate invocation is judged by its process exit status, never by parsing the echoed line. |
| R1-4 | High | EC-01, EC-04, NG-12, SEC-01 | accepted | The sole `.env` exception is EC-04's one non-printing `sed -i` replacement of `LMSTUDIO_BASE_URL`; no command may print, copy, diff, grep, or otherwise inspect `.env` — stated in all four places. |
| R1-5 | High | EC-02, EC-03, EC-04, DOC-01…03, §10 T4, §10.1, Appendix A | accepted, adapted | T4 keeps two prompts/commits but re-split by artefact class and ordered: 260 first, *artefacts only*, DOC-03's five report/post edits under `docs/reports/*` exclusively; 261 second, delegated under brief `v1111-T4.md`, README/plan/AGENTS edits and `tests/test_v1111_doc.py` with all three DOC tests (`T-V1111-DOC-03` green by then, recorded with the carve-out ids' initial results) — the finding's "either delegate T4 or split" became this fixed split. |
| R1-6 | High | PIN-01, EC-02, EC-03, §10 T0, §10.1, Appendix A | accepted | The delegated T0 subagent writes `tests/test_v1111_pin.py` after measuring the unchanged-tree floor and node IDs and runs PIN-01/-02 once the inventory artefacts exist; the two tests are excluded from the floor by construction, so floor + 27 stands. |
| R1-7 | Med | GATE-01, REV-02, §10 T6 | accepted | Every T6 occurrence reads "run gates 1, 2, 3, 4, 5 and 6 once each, in that order; reuse gates 7 and 8 only after the identity check". |
| R1-8 | Med | TST-02, `T-V1111-TST-07`, `E6`, §10.1 T3 | accepted, adapted | TST-07 gains a nested pytest run (a `tmp_path` two-test module — A registers a sentinel without cleanup, B asserts it absent and the registry the same object — plus a `tmp_path` `conftest.py` importing `restore_secrets_registry` from `tests.conftest`, run with `-p no:cacheprovider -p no:xdist`, exit 0, never calling `secrets_registry_snapshot()`), keeping the direct context-manager checks; the import form carries a new `[[VERIFY]]` with a `pytest_plugins` fallback and, failing both, two permanent ordered tests under `xdist_group` as a disclosed amendment — the fifth marker. |
| R1-9 | Med | TAB-05, `T-V1111-TAB-06`, `E5`, §10.1 T2 | accepted | TAB-06 also drives a real `EmbeddingsClient` over `httpx.MockTransport` with 65 inputs through the ingest path and asserts exactly three embedding requests with body input sizes `[32, 32, 1]` alongside the `1/3 … 3/3` edits. |
| R1-10 | Med | REV-03, Appendix A | accepted | A stop before T6's first commit leaves `pyproject.toml` at `1.11.0`; after it, `1.11.1` stays in place rather than rewriting history, no tag is created and the stopped-release README row is used. |

**Round 1: 10 findings, 10 accepted (2 adapted), 0 rejected.** New
requirements: none; new test ids: none (`T-V1111-TST-07` and
`T-V1111-TAB-06` extended in place); `[[VERIFY]]` markers 4 → 5.

### Round 2 of at most 3 — against the round-1 tree (`a96609b`); 7 findings, 7 accepted (2 adapted), 0 rejected

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R2-1 | Crit | EC-04, EC-02, GATE-01, §10 T0, header | accepted, adapted | The precondition is structural, no `HEAD` sha frozen: `git rev-parse v1.11.0^{commit}` prints `24310349ee95d703bb3b256443a4b5e1dd22b415`, `merge-base --is-ancestor v1.11.0 HEAD` exits 0, `describe --tags --abbrev=0` prints `v1.11.0`, `git diff --name-only v1.11.0..HEAD` lists `docs/` paths only, porcelain empty; the exact `HEAD` at `go` is named in `docs/handoff-v1.11.1.md` (informational); T0's gates 1–5 run on the unchanged handoff tree before any T0-generated file exists — the finding's frozen handoff sha was not adopted. |
| R2-2 | Crit | GATE-01, RPT-01, VER-01, REV-02, REV-03, ERR-01 row 10, §10 T6, `E7` | accepted, adapted | The report records everything available before the evidence commit (the preliminary verdict, T5's gate-8 result, per-commit `gitleaks-tree` up to the bump commit); the definitive post-evidence verdict, E7, the final `lint-docs` and `gitleaks-tree` exit are recorded in the annotated tag message's six required fields (`tested_tree`, `evidence_commit`, `identity_verdict=True`, `gitleaks_tree_exit=0`, `lint_docs=PASS`, `e7=PASS`), never claimed by the report; any other value withholds the tag and enters REV-03 — the finding's "terminal command record" alternative was narrowed to the tag message (the stop route keeps the command record). |
| R2-3 | High | EC-04, SEC-01, GATE-01, RPT-01, §10 T0–T6 | accepted | Immediately after every commit created by T0–T6, before another commit is made, the standalone `gitleaks-tree` block runs against that commit and requires exit 0; each result is one line (commit sha, exit code) in the report's per-task section, the evidence commit's in the tag message. |
| R2-4 | High | EC-03, EC-04, DOC-03, RPT-01, §10 T4, §10.1 T4, Appendix A | accepted | `docs/prompts/260-*.md` and prompt 260's `docs/llm-usage.md` row land in T4's second commit as orchestrator-authored artefacts bundled with the delegated files, disclosed in its body and bullet; prompt 261's bookkeeping lands there too; the second commit's allowed path set is exactly nine (README, plan, AGENTS, `tests/test_v1111_doc.py`, the two prompt files, `docs/llm-usage.md`, brief `v1111-T4.md`, `report-v1.11.1.md`); the first commit stays restricted to `report-v1.11.0.md` and `tg-post-v1.11.0.md`. |
| R2-5 | Med | EC-02, PIN-01, `T-V1111-PIN-01`, REV-03, ERR-01 row 13, §10 T0 | accepted | If T0 collects fewer than 2384 tests the run stops as a base-tree/precondition mismatch (REV-03, no repair cycle — ERR-01 row 13); otherwise the measured count is recorded as `floor`, so PIN-01's `≥ 2384` assertion and the floor agree. |
| R2-6 | Med | OUT-01, ERR-01 row 3, `T-V1111-OUT-02`, `E1` | accepted | `T-V1111-OUT-02` also covers 400 → 500 and 400 → transport on both `send_pre` and `edit_pre`: exactly two requests, the second without `parse_mode`, one ERROR line, `None` returned, no third request; OUT-01 states the rule and E1 has the scenario. |
| R2-7 | Med | TAB-04, ERR-01 row 2, `T-V1111-TAB-05`, §10.1 T2, Appendix A | accepted | `T-V1111-TAB-05` (extended in place, no new id) drives both admission paths through `process_update` — `bot.py:2292`'s pre-admission check and `bot.py:2128`'s `DocumentLimitExceededError` branch (lines re-verified at `2431034`) — asserting the exact new `DOC_LIMIT_REPLY`, no document/chunk/vector insertion and an unchanged document count in each case. |

**Round 2: 7 findings, 7 accepted (2 adapted), 0 rejected.** New
requirements: none; new test ids: none (`T-V1111-OUT-02` and
`T-V1111-TAB-05` extended in place); ERR-01 rows 12 → 13; negative
tests 4 → 5; Gherkin scenarios 13 → 15; `[[VERIFY]]` markers unchanged
at 5.
