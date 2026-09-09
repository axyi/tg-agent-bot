# spec-v1.8.0 — the operator's release: context discipline, chat manners, an instrument panel, and conversations

Status: ready for `go`.
Base: `v1.7.0` (tagged 2026-09-08). Nothing about v1.7.0 is reopened.
Target version: **1.8.0** — MINOR, because the release adds user-facing
functionality (SemVer). `pyproject.toml` `1.7.0` → `1.8.0`; tag `v1.8.0`.

Four subjects and no fifth: (1) **`AGENTS.md` and the project prompts** — the
process fix; the v1.7.0 run delegated 1 of 13 tasks because this repository's
`AGENTS.md` has no Context discipline section, so the spec's reading map was
the only mechanism and it lost 4/4 (`docs/reports/report-v1.7.0.md`, "RLM
delegation record"). (2) **Telegram chat UX** — the status message stops
littering the chat, and the bot says it is working. (3) **The dashboard** — a
visual rework inside the existing hard constraints. (4) **Conversations** —
the list of the operator's "sessions", and one conversation's transcript.

Requirement ids group by subject (`AGT`, `CHAT`, `DSH`, `CONV`, `SEC`) and by
release mechanics (`EC`, `VER`, `RPT`, `REV`); a group's ids may appear in more
than one section — `EC` in §1, §9 and §12 — because the group names the
subject, not the section.

---

## 1. Execution contract

**REQ-V180-EC-01 (MUST) — boundary, dependencies, repair budget.** Section 1
of every earlier spec applies unchanged, with these adjustments:

- "the gate commands" means §9's set — the six of `AGENTS.md:92-101` plus the
  `config/quality_gates.yaml` profiles, with one gate added (REQ-V180-EC-10);
- the repair budget is **4 total** repair-and-rerun cycles (one cycle = one fix
  + a complete run of all gates from the first); exhausted → stop and report
  through §11's stop route;
- **no project or lab file outside the repository root may be read or
  written**, and this release needs no network beyond gate 5's live preflight
  and tool-owned caches — the list is **exhaustive**. The lab ledger
  `economics.md` lives above the root: the operator writes it, never the
  executor (REQ-V180-RPT-04);
- the **runtime** dependency set is unchanged and MUST stay so: `httpx`,
  `python-dotenv`, the `docker` CLI as a host dependency (NG-04). Everything
  here is reachable with the standard library and schema version 5
  (`storage.py:18`); **no schema migration is authorised**, and a requirement
  that appears to need one is a defect in this spec — surface it, do not work
  around it.

**REQ-V180-EC-02 (MUST) — test-first.** Write §8's tests, watch them fail for
the right reason, then implement in §12's order. Every `MUST` in §§1–12 has a
named unit test, a negative test, a Gherkin scenario in Appendix B, or a
recorded artefact; Appendix A is the map and is complete. §9's mechanisms
additionally require mutation proof through `devtools/mutation_check.py`.

**REQ-V180-EC-03 (MUST) — the test floor and the exhaustive amendment list.**
The v1.7.0 suite is **1133 collected tests** (`pytest --collect-only -q`,
measured 2026-09-09 at `HEAD` of `main`; `AGENTS.md:103` already says 1133 and
is **not** stale). T0 **re-measures at HEAD** and records the number; if it
differs, the measured number is the floor. No test may be deleted. Tests may
be modified **only** at these four sites, and the list is exhaustive:

| file:line | amendment | why |
|---|---|---|
| `bot.py:1211` | the status assertion: two edits ending in `STATUS_DONE` becomes one `⚙️ exec: ` edit plus exactly one recorded deletion of the status message | REQ-V180-CHAT-02 deletes the message instead of editing it to `"✅ done"` |
| `bot.py:1085-1103` (`_SelftestTelegram`) | gains a `deleted: list[tuple[int, int]]` recorder and a `delete_message` method that appends to it | the same |
| `tests/test_v12_patch.py:145` (`_FakeSelftestTg`) | the fabricated `edits` drops its `bot.STATUS_DONE` entry, leaving `[(424242, 1, "⚙️ exec: uname…")]`; the fake gains `deleted: list[tuple[int, int]]` seeded `[(424242, 1)]` — the **same attribute name, type and shape** as `_SelftestTelegram`'s | it feeds `bot._selftest_failure`, so it must satisfy the amended assertion byte-for-byte; two differently-shaped fakes would let the check pass against one and fail against the other |
| `tests/test_v15_standards.py:1685-1728` | `_GATE_MATRIX_LABEL_TO_NAME` (`:1685-1707`) gains the `mutation-v180` label; `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` reads `spec-v1.8.0.md` in place of `spec-v1.7.0.md` at `:1728` | EC-10 puts `mutation-v180` in `pre-push`, so both the label map and the matrix table must carry it; a released spec is never edited, so EC-12 reproduces the table here and the test follows it |

Two test doubles already define an unused `delete_message(self, chat_id,
message_id)` stub — `tests/test_pricing.py:128` and
`tests/test_observability.py:205` — so they need **no** amendment. A change
making any other test fail means the change is wrong: stop and reconsider,
never edit the test.

**REQ-V180-EC-04 (MUST) — secrets discipline.** REQ-V170-EC-04 applies,
narrowed: this release needs no `.env` write and no value confirmation.
Credential **values** are never printed, logged, committed or quoted in
`docs/`; presence checks are by key **name** only (`grep -q '^KEY=' .env`,
yielding an exit status and nothing else); tests use the synthetic sentinel
pattern; `data/`, `sandbox/`, `*.db` and `exec_audit.jsonl` are never opened,
printed or quoted. **No key is written into `.env`**, no `.env.bak*` is
created, no `sed -i` touches it. §6's transcript reads the database through
the existing read-only handle at request time — the running bot's data path,
not an executor read; **no task of this run opens `bot.db`.**

**REQ-V180-EC-05 (MUST) — backward compatibility.** Every new parameter,
config field, environment variable and helper defaults to **current
behaviour** when absent, so unlisted tests and fakes keep passing. Concretely:
`_StatusMessage.finish` gains a keyword-only `ok: bool` with **no default** —
its one call site (`bot.py:707`) is amended in the same commit, and an
omission is a `TypeError` at import-time coverage, not a silent revert.
`bot.py` alone constructs the typing indicator (REQ-V180-CHAT-05);
`agent.run_agent`'s signature, the agent loop, the LLM layer, the tracing
layer and the storage schema are untouched.

**REQ-V180-EC-06 (MUST) — this release is not benchmark-affecting, and says
so.** `AGENTS.md:155-157` requires a token-affecting behaviour change to be
benchmarked before and after. **No change here reaches a model request**: no
message, system prompt, tool schema, token limit, timeout, retry or provider
path changes, so `meta.prompt_tools_sha256` and every token-affecting input
stay byte-identical to v1.7.0's. The report states that the rule **does not
fire**, names the reason, and lists the touched modules to show none is on the
request path (REQ-V180-RPT-02); no baseline, no candidate run, no
`docs/assets/bench/` write. A task that discovers a change which would reach a
request stops, records it under "Benchmark-affecting changes", and drops it to
v1.9.0 — never folds it in.

**REQ-V180-EC-07 (MUST) — delegation is specified, not hoped for.** This is
the release's own process fix and it binds **this release's own run**.

1. **§12.1 is the per-task reading map** — files, line ranges, and an explicit
   `delegate` column.
2. The column is **`yes` by default** for every task that reads or writes
   source. A task that writes source files — code a gate compiles, imports or
   runs — delegates.
3. Every `no` cell carries **one of the four exemptions of
   `standards/workflow.md` §5.1, verbatim and in those words** — the closed
   list is quoted in REQ-V180-AGT-01 item 3. Free text in that cell is a
   defect; "the main context already holds what this needs" is **not** on the
   list.
4. **The hand-off goes by file.** Before spawning a subagent the orchestrator
   writes a **task-brief file** at `docs/spec/task-briefs/v180-T<N>.md` and
   passes its **path** (T0 creates the directory). The brief carries whatever
   the task depends on that was resolved earlier — a decided row shape,
   §5.1's palette, an earlier control-flow finding — so nothing load-bearing
   is retyped into a prompt. The subagent gets the path plus a ~5-line
   instruction, no history, and returns a **summary** — findings, counts,
   `file:line` — never raw content. Brief files are committed with their
   task.
5. **Crossing the map forces delegation regardless of the column.** A task
   whose actual reading exceeds its mapped files and ranges, or crosses any
   §5.1 trigger, delegates from that point on. A precomputed `no` is never a
   licence to keep reading in the main context.
6. **The run report carries a per-task delegation record** — `task |
   delegated? | to what | map vs actual` — per `standards/reporting.md` § Run
   report. A report without it cannot be verified (REQ-V180-RPT-02).

**REQ-V180-EC-08 (MUST) — the handoff, prompts, commits, and no bypass.** The
`go` session reads **`docs/handoff-v1.8.0.md`** first: the spec's authoring
commits, final counts, any unresolved `[[VERIFY: …]]` marker, the repository
facts folded into this file, the decisions `D1`–`D14`, and the exact `go` line
with every operator input the run needs in its request text. Written before the
run, it is the only handoff artefact; `docs/plan.md` is a carried-candidates
document, not a handoff. Every prompt file carries the seven-bullet header
(`Date`, `Executor model`, `Model reason`, `Harness`, `Stage`, `Owner of`,
`REQ ids`) then exactly four level-2 blocks in
order — `## Goal`, `## Constraints`, `## Acceptance`, `## Stop` — per
`docs/prompts/TEMPLATE.md`, unchanged here. **126 is the highest pre-existing
prompt number** — 125 is v1.7.0's operator acceptance, 126 this spec's own
authoring prompt, written before the run — so T0's is
`docs/prompts/127-go-spec-v1.8.0.md` and the run numbers upward. Each task of
§12 is one prompt file and one commit whose body carries `(prompt:
docs/prompts/NN-….md)`; results of different prompts are never mixed. No commit
or push may use `--no-verify`, `-n`, or any other bypass (an environment
switch, a temporary `core.hooksPath` change, `git config --unset`, deleting and
restoring a hook).
The report MUST carry the sentence *"No commit or push in this run used
`--no-verify` or any other hook bypass."* — and MUST omit it, with an
explanation, if that is untrue; `checks.py replay --range
<base>..<implementation-tip>` is the evidence. `devtools/install_hooks.py
--check` exits 0 at T0. A whole-spec solo run may commit to `main`, where the
branch-name gate is warn-only.

**The spec's own budget.** This file sits under `standards/workflow.md` §12's
~80 KB ceiling (`wc -c` ÷ 4 ≈ 20k tokens), so a cross-review round is applied
size-neutrally or net-negatively — new text paid for by tightening in the same
pass, before/after bytes reported. Overflow that will not fit goes to
`docs/spec/spec-v1.8.0-delta-1.md`, that exact filename, never
`spec-v1.8.1.md`, which would read as a released patch version that does not
exist.

---

## 2. Non-goals

Each is out of scope for v1.8.0 and named so a task that drifts into it stops.

| id | NON-GOAL |
|---|---|
| `NG-01` | Cost work of any kind: no pricing change, no cost model, no `COST_GATE_FACTOR` move. |
| `NG-02` | Reasoning-policy work. `LLM_REASONING_POLICY` / `LLM_REASONING_ON_PURPOSES` and their defaults are untouched. |
| `NG-03` | No benchmark baseline and no benchmark run (REQ-V180-EC-06); `devtools/bench.py` is not edited. |
| `NG-04` | No new runtime dependency, no new host dependency, no developer-tool pin move. |
| `NG-05` | **No JavaScript anywhere** — no `<script>`, no inline event handler, no external stylesheet, image, font or CDN. |
| `NG-06` | No change to the agent loop: `agent.py`'s control flow, round cap, tool dispatch, summary path and fallbacks stay as they are. The only additions are REQ-V180-CHAT-04's pure helper and the derived prefix it reads. |
| `NG-07` | No schema migration. `SCHEMA_VERSION` stays 5; no `ALTER TABLE`, no new table, no new index. |
| `NG-08` | No change to the exec sandbox, the SSRF allowlist, the rate limiter or access control. |
| `NG-09` | No refactor of `dashboard_server.py`; its 8 pre-existing skylos shadow findings are neither fixed nor suppressed. |
| `NG-10` | No change to trace content capture: `OBS_CAPTURE_CONTENT` stays `False` and `served_span()` keeps dropping content attributes (REQ-V180-SEC-03). |
| `NG-11` | No dark theme, no theme switch, no user-configurable styling: `color-scheme: light` and one inline `<style>` block. |
| `NG-12` | No write path on the dashboard: `GET`/`HEAD`, read-only, loopback-only. |

---

## 3. `AGENTS.md` and the project prompts

**REQ-V180-AGT-01 (MUST) — `AGENTS.md` gains a `## Context discipline`
section.** It is placed immediately after `## Project layout` (before
`## Commit format`), adapted from `templates/project/AGENTS.md` § Context
discipline, and MUST carry all four of:

1. **The delegation triggers, including the write trigger.** A subagent when
   **any one** of: more than one file or folder to explore; a single read over
   100 lines or 8 KB; **a task that writes source files — code a gate
   compiles, imports or runs**; more than ~10 edits within one task across
   every file it touches; applying a review or critique to a spec. The text
   MUST say this holds **inside a `go` run, per task**, not only in
   interactive work.
2. **Brief by file, never by retyping.** Anything load-bearing the
   orchestrator already resolved goes into a **task-brief file** and the
   subagent gets its **path**; re-dictating it into a prompt is a
   transcription risk. The brief is ~5 lines, carries no history, names files
   and line ranges; the subagent returns a summary — findings, counts,
   `file:line` — **never** raw content.
3. **The closed list of four exemptions, verbatim**: *commands only* (no file
   writes); *artefacts only* (docs, config, fixtures with no code-shape
   dependency — anything no gate compiles, imports or runs); *a single edit
   under every threshold*; or *the task is itself the clean-context review*.
   The section MUST state that the report names the exemption **in those
   words**, and that "the main context already holds what this needs" is NOT
   on the list.
4. **In the main context**: `Read` with offset/limit, `grep`/`find` with line
   context — never a whole-file read, never a directory walk. Absolute paths
   in shell.

A `<!-- SYNC: ... -->` comment names `standards/workflow.md` §5.1 as canonical,
matching the convention at `AGENTS.md:165` and `:76`.

**REQ-V180-AGT-02 (MUST) — `## Branch strategy` gains the ownership-zone
rule.** Appended to the existing bullets at `AGENTS.md:78-89`, adapted from
`templates/project/AGENTS.md:87-91`: *parallelism is decided by **edit scope,
not agent count** — split into ownership zones (a zone = files exactly one
agent may write); disjoint zones run in parallel, one worktree each;
**overlapping scopes run sequentially**, because separate worktrees only defer
the conflict to merge time.* No existing bullet is deleted or reworded.

**REQ-V180-AGT-03 (MUST) — the factual lines stay true.** In the same task,
`AGENTS.md` is corrected where this release makes it wrong, and **nowhere
else**: the gate-6 mutation-entry count (92 → the number after
REQ-V180-EC-10's additions), the `--select` example gaining `v180-`, the
`pytest` count if T0's re-measurement differs from 1133, and the
`## Project layout` line for `dashboard_server.py` naming the conversations
routes. Style edits, reorderings and rewrites of untouched paragraphs are a
defect.

**REQ-V180-AGT-04 (MUST) — the project prompts are reviewed, not rewritten.**
The project's only skill files are `skills/host-info.md` and
`skills/weather.md`; `CLAUDE.md` imports `AGENTS.md` with `@AGENTS.md` and
otherwise documents the rtk hook. All three are **read and judged against this
release**, and only what this release makes wrong is changed. An **unchanged
file is a legitimate outcome**. The report names each file, says whether it
changed and, when it did not, why it is still correct (REQ-V180-RPT-02).
Rewriting any of them for style, tone or length is a defect.

---

## 4. Telegram chat UX

Today `_StatusMessage.finish()` (`bot.py:264-266`) edits the one status message
to `STATUS_DONE` (`"✅ done"`, `bot.py:63`) and leaves it in the chat: every run
leaves a tombstone.

**REQ-V180-CHAT-01 (MUST) — `delete_message` on the Telegram client.**
`TelegramClient` gains, next to `edit_message_text` (`bot.py:171-175`):

```python
def delete_message(self, chat_id: int, message_id: int) -> dict:
    return self._call_with_retry("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
```

It goes through `_call_with_retry` exactly as its two neighbours do,
inheriting REQ-V1-SND-01's bounded retry (`bot.py:142-157`) and raising
`TelegramError` on a fatal result. No other method changes; the token still
never reaches a log record.

**REQ-V180-CHAT-02 (MUST) — on success the status message is deleted.**
`_StatusMessage.finish` becomes `finish(self, *, ok: bool) -> None`. When `ok`
is true, a message exists and status work is not disabled, it calls
`self._tg.delete_message(self._chat_id, self._message_id)` inside `_edit`'s
`try` discipline and, on success, sets `self._message_id = None` so no later
call can act on a deleted message. Nothing is edited to a "done"
line: **`STATUS_DONE` is deleted from `bot.py`** — nothing reads it afterwards
and an unused constant is what skylos is for. Its three other occurrences are
REQ-V180-EC-03's two amendments and its own definition.

**REQ-V180-CHAT-03 (MUST) — on failure the message is kept, with a final
line.** `bot.py` gains `STATUS_FAILED = "⚠️ failed"` beside `STATUS_WORKING`
(`bot.py:62`). When `ok` is false, `finish` calls `self._edit(STATUS_FAILED)`
and the message stays — the operator's record that the run happened and did
not land. Like every status text it is under `STATUS_MAX_CHARS = 64`.

**REQ-V180-CHAT-04 (MUST) — the failure signal is a closed table over the
`FALLBACK_*` constants.** `agent.run_agent` returns a `str` and **never raises
for a model failure** — it encodes failure as a `FALLBACK_*` constant
(`agent.py:71-83`), so a bare `try/except` at the call site would mark almost
every run successful. A structured return type was **rejected on cost**:
`run_agent` has one production call site (`bot.py:692`) and about 25 across
eleven test files, roughly half binding the return value — cheap in production,
a sprawl in tests, and the classification would still be written by hand.
**`run_agent` keeps returning `str`.**

The predicate is a **closed table over the constants themselves**, never a
heuristic over reply text. Every `agent` constant whose name begins
`FALLBACK_` appears here with a classification and a match rule:

| constant | classification | matched by |
|---|---|---|
| `FALLBACK_EMPTY` | failure | equality |
| `FALLBACK_NO_ANSWER` | failure | equality |
| `FALLBACK_INTERRUPTED` | failure | equality |
| `FALLBACK_LLM_ERROR` | failure | its **derived** prefix: the constant's text up to its first `{` |

All four are failures: in each the user did not get their answer, which is
exactly when the status message stays (REQ-V180-CHAT-03); the
"explicitly-not-a-failure" classification is open for a later constant, unused
today. A templated constant is matched by a prefix **computed from the constant
at import time**, never a retyped literal, so editing the message cannot desync
the matcher.

- `agent.py` gains one **pure module-level helper** and the derived prefix it
  reads, adjacent to those constants and touching no control flow (NG-06):

  ```python
  _LLM_ERROR_PREFIX = FALLBACK_LLM_ERROR.split("{")[0]   # derived, never retyped

  def is_failure_reply(text: str) -> bool:
      """True when `text` is one of run_agent's fallback replies rather than
      a model answer (REQ-V180-CHAT-04)."""
      return text in (FALLBACK_EMPTY, FALLBACK_NO_ANSWER, FALLBACK_INTERRUPTED) \
          or text.startswith(_LLM_ERROR_PREFIX)
  ```
- `bot.py`'s single call site (`bot.py:691-707`) becomes:

  ```python
  try:
      reply = agent.run_agent(...)
  except Exception:
      status.finish(ok=False)
      raise
  status.finish(ok=not agent.is_failure_reply(reply))
  ```

  Four added lines. The exception arm covers the paths that really do raise
  (`agent.finish`'s transactional write, `agent.py:288-292`), the table covers
  the four fallbacks, and no other behaviour of `process_update` changes.
  Inverting the `ok` expression MUST turn the suite red
  (`v180-status-signal-inverted`, §9).

**REQ-V180-CHAT-05 (MUST) — a typing indicator while the bot is processing.**
Telegram's `sendChatAction` with `action="typing"` clears itself after about
five seconds, so it is re-sent on an interval. Frozen numbers:

- **interval: 4.0 s** — `TYPING_INTERVAL_S = 4.0`, a named module constant in
  `bot.py`, inside Telegram's ~5 s window with margin for one slow round trip;
- **ceiling: `cfg.llm_timeout_s`** — no new timeout is invented. The indicator
  stops re-sending once that many seconds have elapsed since its first send,
  measured from an injected clock. `config.py:302` already parses and bounds
  `LLM_TIMEOUT_S` (> 0, ≤ 600), so the ceiling is a validated number the
  operator controls. A run that outlives it keeps the status message as its
  durable progress signal; the indicator simply stops. That trade is
  deliberate, so no executor extends it.

Mechanics: a `_TypingIndicator` class in `bot.py` starting one **daemon**
`threading.Thread` (`threading` is already imported, `bot.py:20`) looping on
`threading.Event.wait(TYPING_INTERVAL_S)`, so `stop()` wakes it immediately
rather than sleeping out the interval. `bot.py` starts it beside
`_StatusMessage` (`bot.py:691`) and stops it in a `finally` around the same
`run_agent` call, so no path leaves a thread running. It sends through the
same `TelegramClient`; `httpx.Client` is safe for concurrent use and the
indicator issues at most one request per interval. It **complements** the
status message and never replaces it.

**REQ-V180-CHAT-06 (MUST) — best-effort, in both directions, and proved by the
selftest.** `_StatusMessage`'s discipline (`bot.py:286-288`) extends unchanged
to both new mechanisms: **any** Telegram error disables further work of that
kind for that run via `_fail` — one `log.warning` with `config.redact()`
applied — and **never fails the run itself**:

- a failed `delete_message` **leaves the status message in the chat** — an
  accepted outcome, not a retry loop and not an error to the user; the run
  still delivers its reply;
- a failed `sendChatAction` disables the indicator for that run, nothing else;
- neither mechanism may raise out of `process_update`.

`--selftest` proves it offline: `_SelftestTelegram` (`bot.py:1085-1103`) gains
a `deleted` recorder and a `delete_message` method, and the assertion at
`bot.py:1211` becomes: exactly one recorded status send of `STATUS_WORKING`,
exactly one edit starting `"⚙️ exec: "`, and **exactly one recorded deletion**
of that message id — no `STATUS_DONE` edit, the constant no longer existing.
`--selftest` binds no port and makes no network call (`bot.py:1167`); the
indicator is driven in the unit tests with a fake clock and a fake event,
never a real sleep.

**REQ-V180-CHAT-07 (MUST) — the table is closed, and reflection proves it.**
`T-V180-CHAT-08` enumerates every `agent` attribute whose name begins
`FALLBACK_`, asserts the set equals REQ-V180-CHAT-04's table exactly, and
asserts every constant the table calls a failure is matched by
`is_failure_reply` (the templated one after `.format()`). A constant in `agent`
but absent from the table fails the test. Reason:
`v180-status-signal-inverted` kills an **inverted** signal; nothing kills an
**incomplete** one. A fallback added later would make `is_failure_reply` return
`False` on a failed run, silently deleting the status message on exactly the
runs the operator wants it kept — the requirement inverted, no test red.

---

## 5. Dashboard visual rework

**REQ-V180-DSH-01 (MUST) — the constraints that do not move.** Restated
because a visual rework is the task that erodes them; each binds every line
this release writes:

- `dashboard_render.py` stays **the only HTML/SVG-emitting module in the
  repository**; every function in it is pure — data in, `str` out, no I/O, no
  database handle, no `Path`, no `print` (`dashboard_render.py:1-10`);
- **offline only** (`dashboard_render.py:12-14`, NG-05);
- **one inline `<style>` block**, the single `STYLE` constant
  (`dashboard_render.py:92-130`), shared byte-identically by the live pages
  and the static bench report; charts are server-side inline `<svg>`;
- CSP `default-src 'none'; style-src 'unsafe-inline'; img-src data:` and the
  other three security headers (`dashboard_server.py:46-51`) unchanged;
- loopback-only bind (`dashboard_server.py:37`), read-only handle
  (`storage.py:276-287`), 2 MiB response cap (`dashboard_server.py:39`);
- every value reaching HTML or SVG text goes through `esc()`
  (`dashboard_render.py:53`).

**Therefore: a system font stack only.** No webfont is reachable, so the
existing stack (`ui-sans-serif, system-ui, "Segoe UI", Roboto, Helvetica,
Arial, sans-serif`) is the single face for the whole document.

**REQ-V180-DSH-02 (MUST) — §5.1 is a frozen plan; the executor implements it
and does not design.** Every hex value, size, weight and layout below is a
literal to be written into `STYLE` and the section builders; substituting a
palette, adding a value not in the table or introducing a second type face
fails this requirement. The plan is copied into T4's task-brief file
(REQ-V180-EC-07 item 4), so it is passed by path, not retyped.

### 5.1 The frozen design plan

**Direction.** An **operator's instrument panel** — *what did it cost, what
broke, what did it say* — a bench faceplate, not a SaaS analytics product:
hairline rules, not floating cards; one accent reserved for **measured
signal**; numbers in columns you read down; nothing on the page that is not a
measurement, a label for one, or a way to reach another.

**Palette — exactly six named values**, custom properties on `:root` inside
the one `STYLE` block:

| token | hex | role |
|---|---|---|
| `--ink` | `#16181c` | body text, headings, the one heavy rule under `h1` |
| `--ground` | `#eef0f2` | the page background: cool paper, never warm cream |
| `--plate` | `#ffffff` | the surface of a panel/section, flat |
| `--rule` | `#ccd2d8` | every hairline: panel edges, row rules, chart baselines, the `h2` scale line |
| `--dim` | `#5f6873` | secondary text: column headers, units, timestamps, footer |
| `--signal` | `#1f5fb0` | the single accent: bar fill, link, active nav item, focus ring — signal only |

Two status colours carry over unchanged and are the **only** other saturated
values: ok `#1c7a4a`, fault `#b23636`, on status text and an error-outlined
gantt bar, nowhere else. A ninth colour is a defect.

**The `PALETTE` dict is remapped onto those eight and gains no key.**
`dashboard_render.PALETTE` (`dashboard_render.py:79-85`) is the SVG helpers'
colour table: five keys today, the same five afterwards, with these literals.
This is what DSH-06 means by "only the colour literals move", and what makes
DSH-04's "every colour literal is one of the eight" satisfiable:

| key | new literal | role |
|---|---|---|
| `bar` | `#1f5fb0` (`--signal`) | bar fill |
| `bar_track` | `#eef0f2` (`--ground`) | bar track |
| `kind_client` | `#1f5fb0` (`--signal`) | a `CLIENT` span — the outbound call, the signal |
| `kind_internal` | `#5f6873` (`--dim`) | an `INTERNAL` span — structure, not signal |
| `error_outline` | `#b23636` (fault) | unchanged |

**Type scale — four sizes, two weights, one face**: REQ-V180-DSH-01's system
stack, for **everything including numbers**.

| element | size / line-height | weight | notes |
|---|---|---|---|
| `h1` | 22px / 1.25 | 600 | `letter-spacing: -0.01em`; one 2px `--ink` rule beneath, full content width |
| `h2` | 16px / 1.3 | 600 | sentence case; a 1px `--rule` line from the text's right edge to the content's right edge — a scale line, not decoration |
| `h3` | 13px / 1.35 | 600 | sentence case |
| body, `td` | 13px / 1.5 | 400 | |
| `th`, `.meta`, `footer`, units | 12px / 1.4 | 600 (`th`) / 400 (rest) | `--dim`; **sentence case, `text-transform: none`, `letter-spacing: 0`** |

Four sizes and no fifth: 22 → 16 → 13 → 12. `h3` is **deliberately body size
at the heavier weight** — weight is the distinction, not a fifth size and not a
collision. No 300 or 700 weight, no italic.

**Alignment — the answer to "the numbers slide".** The page is **one column**,
`max-width: 68rem`, centred, and *every* element — `h1`'s rule, each `h2`'s
scale line, every plate, table and `<svg>` — shares its left and right edges.
Text is left-aligned, nothing centred but a single empty-state line; **every
`class="num"` cell is right-aligned with `font-variant-numeric: tabular-nums`**
in the body face, so a column of numbers has one right edge and one glyph width
(REQ-V180-DSH-03 makes this checkable); units go in the column header, never
per cell; charts are drawn to the table's content width, so bar baselines line
up with table rules.

**Surfaces.** A `section` is a **plate**: `background: var(--plate)`, `border:
1px solid var(--rule)`, `border-radius: 2px`, **no `box-shadow` anywhere in the
sheet**, padding `0 1rem 1rem`. Table rows are separated by 1px `--rule`, the
last by none. A bar is a 0.6rem `--ground` track with a `--signal` fill, square
ends.

**Layout, per page.**

| page | concept |
|---|---|
| `/` (usage) | a **reading strip** across the top of the first plate: four measured values — calls, total tokens, cost, error rate — as label-above-number pairs on one baseline, split by 1px `--rule` verticals, numbers at 22px/600 tabular; then the totals table, then the by-group table |
| `/traces` | one full-width table, newest first; the duration column carries an inline `--signal` bar sized against the page's widest duration, drawn **inside** the number's own cell so magnitude and value read together |
| `/traces/<id>` | the gantt on its own plate first, span table beneath, both at content width so a bar sits above its row |
| `/tools` | the tool-health table on one plate, the limit-hits bar chart on the next, drawn to the same width |
| `/conversations` | one table: id, user, started, messages, active, last activity — **five of the six** (id, user, started, messages, last activity) carry `class="num"`, right-aligned and tabular; `active` does not, its content being the word `yes`/`no` (REQ-V180-DSH-03) |
| `/conversations/<id>` | a **two-column transcript**: a fixed 7rem left rail carrying role and turn (with the trace link when there is one), and a single measure column of message text; one left edge to track down, one 1px `--rule` between messages, no bubbles. In the rail, turn id and timestamp carry `class="num"`; the role word, the trace link and the message text do not |

**What this deliberately is not.** The plan rejects the generic defaults —
warm cream, a serif display face, soft grey card shadows, ALL-CAPS eyebrows,
middle-dot meta strings, monospace data, an arrow after link text.
REQ-V180-DSH-04 is that rejection made checkable; its list is the closed one.

**REQ-V180-DSH-03 (MUST) — tabular numerals, by coverage, not by
declaration.** `STYLE` already carries `font-variant-numeric: tabular-nums` on
`td.num, th.num` (`dashboard_render.py:115-116`), so a requirement merely
asserting the property is **green before the executor starts** and could never
fail. The requirement is therefore **coverage**, and this is the release's
**single definition of the class**: membership is decided by content, never by
column position. In the HTML of every section builder, **every cell whose
content is a number or a fixed-format timestamp — a count, duration, token
total, cost, percentage, id or ISO timestamp, anything whose digits should
align down the column — MUST carry `class="num"`** on both `<th>` and `<td>`,
and **every cell whose content is a word MUST NOT** (`active`'s `yes`/`no`, a
role, a label). `T-V180-DSH-01` renders each builder against a fixture and
fails on either miss; it MUST be red before the work and green after. In the
same change the `td.num, th.num` rule **drops its `font-family: ui-monospace,
...` declaration**: §5.1 forbids a monospace face for data, and tabular figures
in the body face do the alignment job.

**REQ-V180-DSH-04 (MUST) — the rejected defaults are absent, and asserted.**
`T-V180-DSH-02` reads `STYLE` and every builder's rendered output and fails on
any of: a `box-shadow`; `text-transform: uppercase`; `border-radius` over 2px;
a `font-family` naming a monospace or serif family; a colour literal outside
the eight of §5.1; a meta string joining fields with `·`; link text ending in
`→`. The middle-dot join is live today in `tool_health_section`
(`dashboard_render.py:429-436`) and the uppercase `th` rule at `:113-114`, so
the test is red before the work — a gate, not a decoration.

**REQ-V180-DSH-05 (MUST) — the pages get the plan's layout, and the nav gets
the new destination.** `page()` (`dashboard_render.py:133-149`) keeps its
signature and its one-`<style>`-block shape; `/`'s reading strip is a new pure
builder taking already-computed totals; `trace_list_section`,
`tool_health_section`, `usage_section` and the trace page are restyled to the
plan **without changing which data they show — no section gains or loses a
column.** Every page's `nav` gains `("conversations", "/conversations")`, in
the order usage, traces, tools, conversations, on every page including the two
new ones. `devtools/dashboard.py` still imports this module and never the
reverse, so the bench report picks up the same `STYLE` and `T-V160-DSH-02`'s
byte-identity property holds.

**REQ-V180-DSH-06 (MUST) — the existing SVG helpers are reused, not
replaced.** `_bar_chart_svg` (`dashboard_render.py:612`), `histogram_svg`
(`:649`), `bar_svg` (`:663`) and `gantt_svg` (`:672`) keep their signatures
and geometry, and `<title>`/`<desc>` stay on every chart. The only change is
the **five `PALETTE` literals**, remapped exactly as §5.1's table gives them;
`PALETTE` keeps its five keys and no colour literal is written inline in a
helper. No new charting helper, no interactive chart, no legend repeating the
axis labels.

---

## 6. Conversations and transcripts

**REQ-V180-CONV-01 (MUST) — the entity is a conversation, not a "session".**
The operator asked for a "list of sessions"; neither "session" nor
"transcript" exists in the source. The entity is already there:
`conversations(id, tg_user_id, created_at, active)` (`storage.py:144-151`),
one active row per user enforced by `idx_conversations_one_active`, started by
`/new`. **This release names it "conversation" in code, routes, JSON keys and
UI copy.** `/conversations` carries exactly one line of copy saying so — *"A
conversation is one `/new`-to-`/new` stretch of chat; this is the list of
them."* — and no parallel concept, alias, model or table is introduced.

**REQ-V180-CONV-02 (MUST) — three read functions in `storage.py`.** All mirror
`recent_traces` (`storage.py:700-726`): parameterized SQL, bounds as
parameters, `sqlite3.Row` results, no formatting.

- `recent_conversations(conn, *, limit)` — `id`, `tg_user_id`, `created_at`,
  `active`, `message_count` (`COUNT` over `messages`), `last_activity`
  (`MAX(messages.created_at)`, `NULL` for an empty conversation); ordered
  `created_at DESC, id DESC`, bounded by `limit`.
- `conversation_messages(conn, conv_id, *, limit, offset)` — `turn_id`,
  `role`, `content`, `tool_call_id`, `created_at`, `id`, ordered **`turn_id
  ASC, id ASC`** so a turn group is never reordered.
- `conversation_turn_traces(conn, conv_id)` — REQ-V180-CONV-05's link map.

A missing conversation yields an empty list; the caller decides the 404
(CONV-07).

**REQ-V180-CONV-03 (MUST) — `/conversations`, the list.** A page rendered by
the new pure builder `conversation_list_section(rows)` in
`dashboard_render.py`. Row shape, exactly: **id** (linking to `/conversations/<id>`), **user**
(`tg_user_id`), **started** (`created_at`), **messages** (count), **active**
(`yes`/`no`, ok colour for yes), **last activity** (`last_activity`, or `—`
when the conversation has no message). **Five of the six — id, user, started,
messages, last activity — carry `class="num"`**; `active` does not, its
content being a word (REQ-V180-DSH-03). Page size is bounded by the **`limit`
query parameter** through the existing `_parse_limit(params, 50, is_api=...)`
(`dashboard_server.py:168-177`): **default 50**, range **1–500**, anything
else a 400. An empty database renders one empty-state row, never a blank
table.

**REQ-V180-CONV-04 (MUST) — `/conversations/<id>`, the transcript.** A page
rendered by `conversation_transcript_section(...)` in `dashboard_render.py`,
laid out per §5.1's two-column plan. Per message, in `turn_id`/`id` order: the
**role** (`user` / `assistant` / `tool`, visible as text, not a colour alone),
the **turn id**, the **timestamp**, the **content**. Turn id and timestamp
carry `class="num"`; role and content do not (REQ-V180-DSH-03). Content comes
from `messages.content` — the text the bot already stores for the agent's own
memory — bounded and sanitised by §7. A `tool` row also shows its
`tool_call_id`. Pagination is by **`limit`** (`_parse_limit(params, 200,
is_api=...)`, default **200**, range 1–500) and **`offset`**: a new
`_parse_offset` sharing `_parse_conv`'s parse-and-reject shape —
`re.fullmatch(r"[0-9]+")`, a range check, `_bad_request` on either failure —
but **not** its bounds, the range being `0 ≤ n ≤ 2**31 - 1` with an absent
parameter `0`, because offset 0 is the first page whereas a conversation id
starts at 1. The page carries prev/next links built from the current
`limit`/`offset` and nothing else, and states the range it is showing.

**REQ-V180-CONV-05 (MUST) — the link to a trace, and the join that finds
it.** `messages` has **no `trace_id` column** (`storage.py:154-171`), so the
link is not a field lookup. `trace_id` lives on `llm_calls` and `tool_calls`,
both carrying `conv_id` and `turn_id`, so `conversation_turn_traces(conn,
conv_id)` returns a mapping `turn_id -> trace_id` from the **first non-null
`trace_id`** for that `(conv_id, turn_id)`, preferring `llm_calls` and falling
back to `tool_calls`. A turn in the mapping renders its rail entry as a link to
`/traces/<trace_id>`; a turn absent renders plain text — no dangling link, no
placeholder. Link text is the abbreviated trace id with **no arrow appended**
(§5.1).

**REQ-V180-CONV-06 (MUST) — the JSON mirrors.** `/api/conversations` and
`/api/conversations/<id>` mirror the two pages as `/api/traces` mirrors
`/traces` (`dashboard_server.py:579-593`): same query parameters, same bounds,
same rows, `_respond_json`, and a payload echoing the parameters (`{"limit":
..., "conversations": [...]}` and `{"conv": ..., "limit": ..., "offset": ...,
"messages": [...]}`). The JSON carries the **same redacted and capped
content** the HTML does (§7) — an API route is not a bypass. Errors use the
existing JSON error body, not an HTML page.

**REQ-V180-CONV-07 (MUST) — routing, and the two failure answers.** Two
compiled patterns join `_TRACE_PAGE_RE`/`_TRACE_API_RE` (`:56-57`):
`_CONV_PAGE_RE = re.compile(r"^/conversations/([0-9]{1,10})$")` and
`_CONV_API_RE = re.compile(r"^/api/conversations/([0-9]{1,10})$")`. `_route`
(`dashboard_server.py:407-428`) gains `/conversations` and
`/api/conversations` beside `/traces` and `/api/traces`, and the two
`match`-based arms beside the trace ones, **before** the closing `_not_found`.
An id outside `1 ≤ n ≤ 2**31 - 1`, or one no row matches, is a **404** through
the existing `_not_found(is_api=...)`; a malformed `limit` or `offset` is a
**400** through `_bad_request` (`dashboard_server.py:91-98`).
`_STATIC_ROUTES` (`dashboard_server.py:53-55`) is **pre-existing dead code,
referenced nowhere in the repository**; this release adds the two new static
routes so it does not grow *more* stale, does not otherwise touch or delete
it, and records the finding in the report (REQ-V180-RPT-02).

---

## 7. Security

The transcript is the first dashboard view showing what the user and the model
actually said. It gets its own group and its own mutation entries, because
redaction that silently stops working is the failure a green suite hides.

**REQ-V180-SEC-01 (MUST) — `redact()` then `esc()`, in that order, with no
path around it.** Every value this release renders from `messages` — content,
`tool_call_id`, any string derived from them — passes `config.redact()`
(`config.py:161-166`) **and then** `dashboard_render.esc()`
(`dashboard_render.py:53`). Order matters: escaping first would let an
HTML-encoded fragment of a registered secret survive `redact`'s literal
`str.replace`. Redaction happens in `dashboard_server.py` (which may import
`config`); escaping in `dashboard_render.py`, which stays pure. There is **no**
path writing message content into HTML or JSON without both, and the JSON
route redacts even though it does not escape.

**REQ-V180-SEC-02 (MUST) — the output is bounded twice, and the 2 MiB cap is
never what catches it.** `MAX_RESPONSE_BYTES` (`dashboard_server.py:39`) is a
backstop, not a design. Two bounds keep a long conversation off it:

1. **per message**: rendered content is truncated to **2000 characters *after*
   redaction and before escaping**, with a visible `…` marker and the original
   length stated — the number REQ-V160-TRC-09 already fixes for a captured
   content attribute, reused rather than reinvented;
2. **per page**: the `limit` of REQ-V180-CONV-04, default 200, maximum 500.

500 × 2000 characters is under 1 MiB before escaping and comfortably under the
cap after it. `T-V180-SEC-02` drives a conversation at both maxima through
both routes and asserts the response is produced normally — not through the
"response too large" path (`dashboard_server.py:663-673`).

**REQ-V180-SEC-03 (MUST) — this does not violate REQ-V160-TRC-09.**
REQ-V160-TRC-09 (`docs/spec/spec-v1.6.0.md:675-688`) governs the four **trace
content attributes** — `gen_ai.system_instructions`, `gen_ai.input.messages`,
`gen_ai.output.messages`, `gen_ai.tool.definitions` — which stay **opt-in and
off**: `OBS_CAPTURE_CONTENT` keeps defaulting to `False` and `served_span()`
keeps dropping every key outside `SERVED_SPAN_ATTRIBUTE_KEYS`
(`dashboard_render.py:240-287`). **Not one line of that path is touched**
(NG-10). The transcript is a **different source with its own rules**:
`messages.content`, under SEC-01's redact-then-escape, SEC-02's two bounds,
the loopback-only bind, the read-only handle and the unchanged headers.
`T-V180-SEC-03` asserts both halves at once.

**REQ-V180-SEC-04 (MUST) — the server's invariants are unchanged by the new
routes.** They are served through the same `_respond`/`_write` path, so they
inherit the four security headers (`dashboard_server.py:46-51`), the response
cap, `no-store` and the `Content-Length` discipline; they answer `GET` and
`HEAD` only; they use `storage.connect_readonly` through the existing
`self._connect()` and close it in a `finally`; `DASHBOARD_BIND` stays
`"127.0.0.1"`. No new header, none removed, no new method, no CORS, no cookie.

**REQ-V180-SEC-05 (MUST) — parameterized SQL, no exceptions.** Every query of
REQ-V180-CONV-02 binds `conv_id`, `limit` and `offset` as parameters; no
request value is interpolated by f-string, `%`, `.format()` or concatenation,
and no `LIKE` pattern is built from request input. `T-V180-SEC-04` drives an
id-shaped injection attempt through both routes and asserts a 400 or 404, an
unchanged database, and no query text containing the payload.

---

## 8. Tests

Written before the code they cover (REQ-V180-EC-02). Files:
`tests/test_v180_chat.py`, `tests/test_v180_dashboard.py`,
`tests/test_v180_conversations.py`. All offline, all against fakes, a fake
clock and a `tmp_path` database.

| id | asserts |
|---|---|
| `T-V180-CHAT-01` | `delete_message` posts `deleteMessage` via `_call_with_retry`; raises `TelegramError` on a fatal result |
| `T-V180-CHAT-02` | `finish(ok=True)` deletes, clears `_message_id`, issues no edit |
| `T-V180-CHAT-03` | `finish(ok=False)` edits to `STATUS_FAILED`, no delete; `STATUS_DONE` absent from `bot`'s namespace |
| `T-V180-CHAT-04` | `is_failure_reply` true for all four fallbacks incl. a formatted `FALLBACK_LLM_ERROR`; false for an answer and for one with `TRUNCATION_NOTICE` |
| `T-V180-CHAT-05` | negative: a raising `delete_message` leaves the message, logs once redacted, reply delivered |
| `T-V180-CHAT-06` | sends on start, once per 4.0 s of fake clock, nothing at/after `cfg.llm_timeout_s`; `stop()` ends it in one `wait` |
| `T-V180-CHAT-07` | negative: a raising `sendChatAction` disables the indicator only |
| `T-V180-CHAT-08` | reflection: `agent`'s `FALLBACK_*` attributes equal REQ-V180-CHAT-04's table exactly, and every one it calls a failure is matched |
| `T-V180-DSH-01` | coverage: every number/timestamp cell carries `class="num"`, no word cell does; `STYLE` declares `tabular-nums`, **no** monospace family |
| `T-V180-DSH-02` | negative: DSH-04's closed list of rejected defaults absent from `STYLE` and every builder's output |
| `T-V180-DSH-03` | exactly the six palette tokens plus two status colours; every colour literal is one of those eight |
| `T-V180-DSH-04` | every nav carries the four entries in order; `page()` emits one `<style>`, no `<script>`, no external URL |
| `T-V180-CONV-01` | `recent_conversations`: six fields, newest first, bounded; `last_activity` `NULL` when empty |
| `T-V180-CONV-02` | `conversation_messages` orders by `turn_id, id`; no turn group split at the default limit |
| `T-V180-CONV-03` | `conversation_turn_traces` maps to `llm_calls`, falls back to `tool_calls`, omits a turn with neither |
| `T-V180-CONV-04` | negative: the list renders the decided row shape; `limit=0`, `501`, `x` each give 400 |
| `T-V180-CONV-05` | negative: transcript in order, only traced turns linked, paginates by `limit`/`offset`; unknown id 404 |
| `T-V180-SEC-01` | negative: a registered secret is replaced on both routes; `<script>` in content is escaped, not served |
| `T-V180-SEC-02` | 500 × 8000 characters render under the cap, each truncated to 2000 with marker and original length |
| `T-V180-SEC-03` | content capture off: no served content attribute, while the same turn's transcript renders its text |
| `T-V180-SEC-04` | negative: an injection-shaped id gives 400/404, database unchanged, no query text holds the payload |
| `T-V180-AGT-01` | `AGENTS.md` carries Context discipline with the write trigger, four **verbatim** exemptions, and the ownership-zone rule |
| `T-V180-VER-01` | `pyproject.toml`'s `project.version` reads `1.8.0` |

---

## 9. Gates and mutation entries

**REQ-V180-EC-09 (MUST) — the six existing gates, verbatim and in order.**
Restated from `AGENTS.md:92-101`; **not one character changes**:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
uv run --locked python devtools/mutation_check.py
```

Gates 1–4 and 6 are unconditional and offline. Gate 5 needs the live
environment (a provisioned `.env`, a reachable Docker daemon with the sandbox
image pulled, LM Studio and an OpenRouter key) and runs at **T0** on the
unchanged tree, at **T8** once every source change has landed, and at **T10**
on the tree that ships; an unreachable LM Studio is a **blocked run**, not a
noted one. The test count MUST **exceed** T0's measured floor (1133) on every
branch reaching T8, and MUST **equal** it on a stop-route branch (§11), no code
having been written and no test deleted; state the exact number in the report.
Gates 1–4 and 6 are re-run against the final tree before the closing commit on
**every** branch, stop route included — T0's exit codes prove the tree T0 ran
on, not the tree that ships.

**REQ-V180-EC-10 (MUST) — the mutation entries, and one new profile gate.**
`devtools/mutation_check.py` gains **six** `v180-*` entries in its existing
`MUTATIONS` shape (`id`, `path`, `find`, `replace`, `why`). The code does not
exist when this spec is written, so each entry is specified by the **mechanism
it must break**, not by a literal; T6 authors the `find` string against the
shipped source, and each MUST match **exactly once** in its file:

| id | mechanism it breaks | must be killed by |
|---|---|---|
| `v180-status-signal-inverted` | the signal at `bot.py`'s call site: invert `ok` so a successful run keeps its message and a failed one deletes it | `T-V180-CHAT-02`, `-03`, `bot.py --selftest` |
| `v180-status-delete-skipped` | `finish(ok=True)`'s delete call: replace it with the old edit | `T-V180-CHAT-02`, `bot.py --selftest` |
| `v180-typing-ceiling-removed` | the `cfg.llm_timeout_s` ceiling in the indicator loop: remove the elapsed check so it types forever | `T-V180-CHAT-06` |
| `v180-transcript-redact-bypassed` | the `config.redact()` call on the transcript path: pass the raw content through | `T-V180-SEC-01` |
| `v180-transcript-cap-removed` | the 2000-character per-message truncation: render the full content | `T-V180-SEC-02` |
| `v180-dashboard-bind-widened` | the loopback bind: `DASHBOARD_BIND` `127.0.0.1` → `0.0.0.0` | the existing `T-V160-SRV-*` bind assertions plus `T-V180-SEC-04`'s route check |

`config/quality_gates.yaml` gains exactly one gate, placed in the **`pre-push`**
profile, with `mutation-v170`'s key set and key order
(`config/quality_gates.yaml:252-260`) — only the `--select` prefix and
`timeout_seconds` differ, the latter because it is re-measured:

```yaml
  mutation-v180:
    kind: command
    result_mode: exit_status
    argv: [uv, run, --locked, python, devtools/mutation_check.py, --select, "v180-"]
    placeholders: {}
    success_exit_codes: [0]
    blocking: true
    diff_scoped: false
    timeout_seconds: <2 x measured, rounded up to the next 10 s>
```

Two timeouts are **re-measured**, not guessed, per the 2×-a-measured-run rule
already documented in that file: `mutation-v180` itself, and `mutation-all`,
which grows from 92 entries to 98. No existing gate's `argv`, `result_mode`,
`blocking`, `severity` or profile membership changes. **Every gate formula
above must be checkable against a plausible bad run and go red** — an entry
whose `find` does not match, or that the named test does not kill, is a defect
in the entry, not a reason to relax the gate.

**REQ-V180-EC-12 (MUST) — the gate matrix moves into this spec.**
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
(`tests/test_v15_standards.py:1727-1741`) parses the table below out of the
spec it names and asserts it agrees with `profiles:` in
`config/quality_gates.yaml`. It reads `spec-v1.7.0.md` today; a released spec
is never edited, so T6 repoints it at **this** file (`:1728`) and adds the
`mutation-v180` label to `_GATE_MATRIX_LABEL_TO_NAME` (`:1685-1707`). Below is
REQ-V170-GATE-03's table, yes/— verbatim, plus the new row, minus the `note`
column the parser never reads. It is load-bearing markup: the parser finds the
header by the literal `| gate | pre-commit` and takes rows until the first line
not starting with `|`, and every label must match the map byte-for-byte.

| gate | pre-commit | pre-push | full |
|---|:---:|:---:|:---:|
| `ruff check` (staged) | yes | — | — |
| `ruff check .` (tree) | — | yes | yes |
| `ruff format --check` | yes | yes | yes |
| branch-name check | yes | yes | yes |
| `gitleaks git --staged` | yes | — | — |
| `gitleaks dir` (tree) | — | yes | yes |
| `uv sync --locked` | — | — | yes |
| `pytest` | — | yes | yes |
| `bot.py --selftest` | — | yes | yes |
| `bot.py --selftest-live` | — | — | yes |
| `mutation_check.py --select v15-` | — | yes | — |
| `mutation_check.py --select v160-` | — | yes | — |
| `mutation_check.py --select v170-` | — | yes | — |
| `mutation_check.py --select v180-` | — | yes | — |
| `mutation_check.py` (all) | — | — | yes |
| `trivy fs` | — | yes | yes |
| `semgrep scan` | — | yes | yes |
| `skylos` | — | yes | yes |
| `install_hooks.py --check` | — | yes | yes |
| `checks.py doctor` | — | yes | yes |
| `checks.py lint-docs` | — | — | yes |

---

## 10. Version, reporting and the ledger

**REQ-V180-VER-01 (MUST) — 1.8.0, and where the bump lives.**
`pyproject.toml`'s `project.version` moves `1.7.0` → `1.8.0` in **T7 and
nowhere else**; `T-V180-VER-01` is written in the same task, red before the
edit and green after. `README.md`'s Versioning section and `AGENTS.md` echo the
number in the same commit. The annotated tag `v1.8.0` is created **only** on
REQ-V180-REV-02's evidence-only commit, only when every gate is green, and is
the last action of the run — no commit follows it. Existing tags (`v1.3`,
`v1.3-baseline`, `v1.6.0`, `v1.7.0`) are untouched.

**REQ-V180-RPT-01 (MUST) — `lint-docs` points at this release's report.**
`config/quality_gates.yaml:336` reads `report_path:
docs/reports/report-v1.7.0.md`; T7 repoints it to
`docs/reports/report-v1.8.0.md`, before the review, it being a config file.
`checks.py lint-docs` is green against the T0 report skeleton from then on.

**REQ-V180-RPT-02 (MUST) — what `docs/reports/report-v1.8.0.md` carries.**
`standards/reporting.md` § Run report's required fields, plus, for this
release:

1. every gate of §9 with its exit code, recorded twice — T0's run and the
   final run against the tree that ships;
2. the T0 test count and the final one;
3. **the per-task delegation record** — `task | delegated? | to what | map vs
   actual` — every task that wrote source files either delegated or naming
   **one of the four exemptions verbatim** (REQ-V180-EC-07 item 6). This is
   what `/verify-run` item 8 checks, and this release exists partly to make it
   truthful;
4. the task-brief files written, by path;
5. `<base>` and `<implementation-tip>` SHAs, and the spec's `sha256` at T0;
6. the statement that `AGENTS.md:155-157`'s benchmark rule **does not fire**,
   with the reason and the touched modules (REQ-V180-EC-06);
7. the project-prompt review record: `skills/host-info.md`,
   `skills/weather.md`, `CLAUDE.md` each named, changed / unchanged, with the
   one-line reason when unchanged (REQ-V180-AGT-04);
8. the pre-existing dead code surfaced and **not** fixed: `_STATIC_ROUTES`
   (`dashboard_server.py:53-55`) and the 8 skylos shadow findings in the same
   module (NG-09);
9. the `--no-verify` attestation sentence of REQ-V180-EC-08.

**REQ-V180-RPT-03 (MUST) — the Telegram post.**
`docs/reports/tg-post-v1.8.0.md`, **Russian**, under 1500 characters by `wc
-m` with the count quoted; structured constraints → result → metrics (executor
model always named; spec tokens, prompts, first-run, bugs, tokens in/out, cost
— an estimate at public API prices, marked as such, when the harness exposes no
counters) → the GitHub link `https://github.com/axyi/tg-agent-bot`.
Regenerating it for the same run replaces the file; N is never bumped.

**REQ-V180-RPT-04 (MUST) — usage rows and the ledger row.** Every prompt of the
run gets a row in `docs/llm-usage.md`'s existing table. The report's "Ledger
row (paste into `economics.md`)" section carries a structurally complete fenced
row with `Ver` = `1.8.0` and no provisional cell; **the operator pastes it into
the lab ledger — the executor never writes above the repository root**
(REQ-V180-EC-01).

---

## 11. Acceptance, review and the stop route

**REQ-V180-REV-01 (MUST) — review in a clean context, before the gates that
matter.** Code review by the `code-reviewer` subagent
(`.claude/agents/code-reviewer.md`) in its **own clean context**, at the head
of T8 — after every code task and **before** T8's gate run, so findings are
fixed and the gates run on the fixed tree. **Never self-review in the writing
context.** Findings are fixed or waived with a reason in the report; the review
prompt is logged in `docs/prompts/`. Beyond the standard checklist:

1. `dashboard_render.py` is still pure — no import of `config`, `storage` or
   `sqlite3`, no I/O, no `Path` — and still the only module holding an HTML or
   SVG literal;
2. redaction happens **before** escaping on every transcript path, HTML and
   JSON alike, with no third path;
3. `served_span()`, `SERVED_SPAN_ATTRIBUTE_KEYS` and the `OBS_CAPTURE_CONTENT`
   default are byte-unchanged (NG-10);
4. every new SQL statement binds its parameters;
5. `_StatusMessage` and `_TypingIndicator` cannot raise into `process_update`,
   and the indicator's thread stops on every path including the exception one;
6. `agent.py` gained REQ-V180-CHAT-04's helper and its derived prefix constant
   and **nothing else** (NG-06), and the `FALLBACK_*` table is complete;
7. `STYLE` matches §5.1 literally: six tokens, two status colours, four sizes,
   two weights, no shadow, no monospace, no uppercase transform;
8. each of §9's six mutation entries has a `find` matching exactly once and a
   named killing test, and §9's gate-matrix table still agrees with
   `config/quality_gates.yaml`.

**REQ-V180-REV-02 (MUST) — acceptance, offline, and the freeze.** After the
`full` profile is green, execute **Appendix B** against the repository and the
recorded documents — every scenario against fakes, a fake clock and a temporary
database. **No live LLM call is needed to accept this release** and none is
made. Record pass or fail per scenario and, per REQ-V12-REP-02, **how** each
was driven. T9 lands a provisional `report-v1.8.0.md` carrying every
REQ-V180-RPT-02 item except item 5's tip SHA; that commit's SHA **is**
`<implementation-tip>`. T10 re-runs the six gates, `full --since <base>`,
`replay --range <base>..<implementation-tip>` and Appendix B against the final
tree, then lands **one evidence-only commit** touching `docs/reports/*` and
nothing else — not recursively required to replay against itself. **Only after
it lands** is the annotated tag `v1.8.0` created on it.

**REQ-V180-REV-03 (MUST) — regression, and no weakened posture.** spec-v1.2's
D1 and D2, spec-v1.4's S01 acceptance, spec-v1.5's freeze properties and
spec-v1.6.0's tracing, dashboard and tool-quality properties still hold. No
earlier security posture is weakened: exec sandbox, redaction choke points,
SSRF allowlist, loopback-only dashboard, read-only handle, security headers,
response cap and `.env` handling are untouched except where §7 **adds** a
constraint. Failures are fixed and the whole set rerun inside the **4-cycle**
repair budget; exhausting it means the stop route — not relaxing a gate, not
deleting a test, not lowering a bound.

**REQ-V180-REV-04 (MUST) — the stop route.** If a gate stays red after the
repair budget, or a spec-internal contradiction is found that cannot be
resolved without a decision, the run **stops and finalises** — it does not
half-ship. The procedure, invoked from wherever the run stands:

1. **Finalise `docs/reports/report-v1.8.0.md`** from T0's skeleton: every
   REQ-V180-RPT-02 item the branch reached, and for each it did not, the
   explicit words *"not reached: <task> stop"* — never a blank, never a `TBD`.
   The red gate is named with its exact command and exit code; the repair
   cycles spent are listed one per line.
2. **Finalise `docs/reports/tg-post-v1.8.0.md`** — Russian, under 1500
   characters by `wc -m` with the count quoted. A stop is reported, not
   omitted.
3. **Append the usage rows** for every prompt to `docs/llm-usage.md`, and fill
   the ledger row completely with `Ver` = whatever `pyproject.toml` reads.
4. **Run the gates that can run; account for the ones that cannot.** Gates 1–4
   and 6 are re-run against the finalised tree with fresh exit codes — the red
   one quoted. Gate 5 runs when the live environment is available and is
   recorded `N/A` with its reason when not; `checks.py replay --range` runs
   when `<base>` exists; `mutation-v180` is `N/A` when T6 never created it. If
   T7 never ran, `lint-docs`'s `report_path` still names v1.7.0: repoint it
   **in the working tree only**, run `python3 devtools/checks.py lint-docs`,
   restore the file, and prove `git diff -- config/quality_gates.yaml` is empty
   before the closing commit. `gitleaks` MUST exit 0. **Nothing is silently
   skipped.**
5. **Commit the permitted evidence and nothing else**: report, tg-post, usage
   rows, task-brief files. No source, test or config file is in this commit;
   `--no-verify` is forbidden here as everywhere.
6. **Prove the negative and terminate**: `pyproject.toml` still reads its
   pre-stop version, `git tag -l` shows no `v1.8.0`, and the report says so.
   **No bump, no tag, no evidence-only commit.** No later task of §12 runs.

---

## 12. Implementation order

**REQ-V180-EC-11 (MUST)** Work in this order; each task is one prompt and one
commit, with §12.1's reading map and REQ-V180-EC-07's delegation rule. Tests
come before the code they cover, inside the same task.

| T | task | acceptance |
|---|---|---|
| **T0** | Preconditions: six gates green on the unchanged tree, hooks installed, `doctor` green, **test count re-measured** (floor 1133), `<base>` and the spec's `sha256` recorded, `docs/prompts/127-go-spec-v1.8.0.md` and `docs/spec/task-briefs/` created, the `report-v1.8.0.md` skeleton landed with `## Operator inputs` copied verbatim from the `go` request and a complete ledger-row block | every item recorded; 126 is the highest pre-existing prompt; `<base>` written before the first commit; an unreachable LM Studio **blocks** here |
| **T1** | §3: Context discipline and the branch-zone rule; the factual lines corrected; `skills/*.md` and `CLAUDE.md` reviewed. Test `T-V180-AGT-01` | green; the four exemptions verbatim; the project-prompt record written for all three files |
| **T2** | §4 part 1: `delete_message`, `finish(ok=)`, `STATUS_FAILED`, `STATUS_DONE` removed, `is_failure_reply`, the call site. Tests `T-V180-CHAT-01…-05`, `-08`; amends `bot.py:1085-1103`, `:1211`, `tests/test_v12_patch.py:145` | green; `--selftest` green with the amended assertion; no other test amended |
| **T3** | §4 part 2: `_TypingIndicator`, `TYPING_INTERVAL_S`, the ceiling, start/stop around `run_agent`. Tests `T-V180-CHAT-06`, `-07` | green with a fake clock and event; no real sleep in the suite; `--selftest` still binds no port |
| **T4** | §5: `STYLE` rewritten to §5.1, the `num` coverage pass, the reading strip, the restyled sections, the nav entry, the SVG palette. Tests `T-V180-DSH-01…-04` | green — each **red before** the change, recorded so; `T-V160-DSH-02`'s byte identity holds |
| **T5** | §6 storage and render: the three read functions, `conversation_list_section`, `conversation_transcript_section`. Tests `T-V180-CONV-01…-03` | green; migration tests green from v1…v5; `SCHEMA_VERSION` still 5; `git diff` shows no DDL |
| **T6** | §6 server + §7: four routes, two regexes, `_parse_offset`, `_STATIC_ROUTES`, redact-then-escape, the two bounds; then the six `v180-*` entries, the `mutation-v180` gate with both re-measured timeouts, and §9's matrix test repointed (EC-12). Tests `T-V180-CONV-04`, `-05`, `T-V180-SEC-01…-04` | green; `--select v180-` green with every `find` matching once; `mutation-all` green inside its new timeout; the repointed matrix test green |
| **T7** | Docs, config and **the version bump**: `pyproject.toml` → `1.8.0`, `README.md` (Dashboard, Versioning), `AGENTS.md`'s counts, `docs/plan.md`, `report_path`. Test `T-V180-VER-01` | red before the bump, green after; `lint-docs` green on the T0 skeleton; docs match reality |
| **T8** | **Review (REQ-V180-REV-01) in a clean context, then every gate**: the six verbatim, `checks.py run --profile full --since <base>`. **Every source, test and config fix lands here or earlier** | findings closed or waived; every gate green; the count exceeds T0's floor; the tree is final |
| **T9** | **Provisional** `report-v1.8.0.md` (RPT-02 minus item 5's tip SHA), `tg-post-v1.8.0.md` (RU, `wc -m` quoted), `docs/llm-usage.md` rows | `lint-docs` green against the repointed `report_path`; no self-referential SHA claimed |
| **T10** | **Final acceptance (REQ-V180-REV-02)**: the six gates, `full --since <base>`, `replay --range <base>..<implementation-tip>`, Appendix B; the evidence-only commit; then the annotated tag `v1.8.0`, only on green | every gate green on the tree that ships; the tag recorded, or its absence recorded with the verdict withholding it |

### 12.1 Per-task reading map

Navigation aid **and** the authority for REQ-V180-EC-07's thresholds. Reading
more is never a defect; reading less never releases a requirement. §1
(EC-01…08), §2 (NG-*) and §11 bind every task and are not repeated per row. A
`no` cell carries one of the four exemptions **verbatim**.

| T | spec sections | repository files and ranges | delegate? |
|---|---|---|---|
| **T0** | §9, §10 | `AGENTS.md:92-121`, `config/quality_gates.yaml:330-340` | no — *commands only* |
| **T1** | §3 | `AGENTS.md` (whole), `skills/host-info.md`, `skills/weather.md`, `CLAUDE.md`, `templates` block quoted in §3 | no — *artefacts only* |
| **T2** | §4 (CHAT-01…-04, -06, -07) | `bot.py:45-70`, `:142-180`, `:241-295`, `:685-710`, `:1085-1115`, `:1200-1215`; `agent.py:66-86`; `tests/test_v12_patch.py:140-150` | **yes** |
| **T3** | §4 (CHAT-05, -06) | `bot.py:45-70`, `:100-180`, `:685-710`; `config.py:90-100`, `:296-330` | **yes** |
| **T4** | §5 (DSH-01…-06), §5.1 | `dashboard_render.py:88-150`, `:340-470`, `:600-700`; the task-brief file carrying §5.1 | **yes** |
| **T5** | §6 (CONV-01…-05) | `storage.py:140-175`, `:270-290`, `:695-730`; `dashboard_render.py:45-90`, `:440-470` | **yes** |
| **T6** | §6 (CONV-06, -07), §7, §9 (EC-10, -12) | `dashboard_server.py:30-60`, `:85-100`, `:160-195`, `:400-430`, `:470-495`, `:570-600`, `:655-700`; `config.py:155-175`; `devtools/mutation_check.py` **tail only** (`MUTATIONS` entries and `main()`); `config/quality_gates.yaml:200-260`, `:330-340`; `tests/test_v15_standards.py:1685-1741` | **yes** |
| **T7** | §10 | `pyproject.toml` (`project.version` only), `README.md:204-228`, `:609-642`, `AGENTS.md:102-121`, `docs/plan.md`, `config/quality_gates.yaml:330-340` | no — *artefacts only* |
| **T8** | §9, §11 (REV-01) | the review's own reading map; otherwise only commands run | no — *the task is itself the clean-context review* |
| **T9** | §10, §11 | this run's own artefacts | no — *artefacts only* |
| **T10** | §11, Appendix B | this run's own artefacts | no — *commands only* |

A task whose actual reading exceeds its map crosses REQ-V180-EC-07 item 5 and
delegates from that point on; the report records map versus actual either way
(REQ-V180-RPT-02 item 3).

---

## Appendix A — requirement traceability

Every `MUST` appears exactly once; the **fifty** rows below are in bijection
with the fifty `MUST` ids defined in §§1–12. NON-GOALs live in §2's table.
"Verified by" names a test id, a negative test, a Gherkin scenario or a
recorded artefact — never "by inspection". Provenance (the prior `REQ` a row
inherits from, the decisions `D1`–`D14`) lives in `docs/handoff-v1.8.0.md`.

| Requirement | Verified by |
|---|---|
| `REQ-V180-EC-01` — boundary; zero new deps; no migration; budget 4 | `uv.lock`/`pyproject.toml` diffs show no new distribution; `git diff` no DDL |
| `REQ-V180-EC-02` — test-first; Appendix A is the map | the report's per-task "failed first for the right reason" record |
| `REQ-V180-EC-03` — 1133-test floor; the four-site amendment list | `pytest --collect-only -q` at T0 and T10; the amended-file diff |
| `REQ-V180-EC-04` — secrets discipline; presence by key name only | `gitleaks-tree`; the report's `.env` record; `E14` |
| `REQ-V180-EC-05` — back-compat; `finish(ok=)` keyword-only, no default | `T-V180-CHAT-02`; §8's unamended-test set staying green |
| `REQ-V180-EC-06` — not benchmark-affecting; the rule does not fire | the report's "Benchmark-affecting changes" statement; `git diff --stat` |
| `REQ-V180-EC-07` — delegation: map, default `yes`, verbatim exemptions, brief file, live crossing, report record | §12.1's map; the committed `task-briefs/v180-T*.md`; the delegation record; `E13` |
| `REQ-V180-EC-08` — handoff file; prompt format; one prompt one commit; `--no-verify` ban; prompt 127 | `lint-docs`; `replay --range <base>..<implementation-tip>`; the attestation; the handoff committed before T0 |
| `REQ-V180-EC-09` — the six gates verbatim; the count floor; the final re-run | the report's two recorded exit-code sets |
| `REQ-V180-EC-10` — six mutation entries by mechanism; `mutation-v180`; two re-measured timeouts | `mutation_check.py --select v180-`; `--list` recorded; the matrix test |
| `REQ-V180-EC-11` — the implementation order; tests before code within a task | the commit sequence; the report's per-task record |
| `REQ-V180-EC-12` — the gate matrix reproduced here; the matrix test repointed, label map extended | `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` green on this file |
| `REQ-V180-AGT-01` — Context discipline: write trigger, brief-by-file, four verbatim exemptions | `T-V180-AGT-01`; `E13` |
| `REQ-V180-AGT-02` — the ownership-zone branch rule | `T-V180-AGT-01` |
| `REQ-V180-AGT-03` — the factual lines corrected and nothing else | `git diff -- AGENTS.md` reviewed at T8; the report's count record |
| `REQ-V180-AGT-04` — the three project prompts reviewed, not rewritten | the report's project-prompt record naming all three files |
| `REQ-V180-CHAT-01` — `delete_message` through `_call_with_retry` | `T-V180-CHAT-01` |
| `REQ-V180-CHAT-02` — success deletes the message; `STATUS_DONE` removed | `T-V180-CHAT-02`; `--selftest`; `v180-status-delete-skipped`; `E1` |
| `REQ-V180-CHAT-03` — failure edits to `STATUS_FAILED` and keeps it | `T-V180-CHAT-03`; `E2` |
| `REQ-V180-CHAT-04` — the signal: closed `FALLBACK_*` table, `is_failure_reply`, exception arm | `T-V180-CHAT-04`; `v180-status-signal-inverted`; `E2` |
| `REQ-V180-CHAT-05` — typing: 4.0 s, `cfg.llm_timeout_s` ceiling, daemon thread | `T-V180-CHAT-06`; `v180-typing-ceiling-removed`; `E4` |
| `REQ-V180-CHAT-06` — best-effort both ways; the selftest records deletions | `T-V180-CHAT-05`, `-07`; `--selftest`; `E3`, `E5` |
| `REQ-V180-CHAT-07` — the `FALLBACK_*` table is closed; reflection proves it | `T-V180-CHAT-08` |
| `REQ-V180-DSH-01` — the constraints that do not move; system font only | `T-V180-DSH-04`; `E7` |
| `REQ-V180-DSH-02` — §5.1 is frozen; the executor implements, never designs | `T-V180-DSH-03`; the committed T4 task-brief file |
| `REQ-V180-DSH-03` — tabular numerals by **coverage**; monospace dropped | `T-V180-DSH-01`, recorded red before T4; `E6` |
| `REQ-V180-DSH-04` — the rejected defaults are absent and asserted | `T-V180-DSH-02`, recorded red before T4; `E7` |
| `REQ-V180-DSH-05` — per-page layout; nav gains conversations; no column moves | `T-V180-DSH-04`; `T-V160-DSH-02` still green; `E8` |
| `REQ-V180-DSH-06` — the four SVG helpers reused, only their colours move | `T-V180-DSH-03`; `git diff` shows unchanged geometry |
| `REQ-V180-CONV-01` — the entity is a conversation; one line of copy says so | `T-V180-CONV-04`; `E8` |
| `REQ-V180-CONV-02` — three read functions, parameterized, mirroring `recent_traces` | `T-V180-CONV-01`, `-02`, `-03` |
| `REQ-V180-CONV-03` — `/conversations` row shape; `limit` 50, range 1–500 | `T-V180-CONV-04`; `E8` |
| `REQ-V180-CONV-04` — transcript: `turn_id`/`id` order, roles visible, `limit`/`offset` | `T-V180-CONV-05`; `E9` |
| `REQ-V180-CONV-05` — the trace link joins via `(conv_id, turn_id)` | `T-V180-CONV-03`, `-05`; `E9` |
| `REQ-V180-CONV-06` — the JSON mirrors carry the same redacted, capped content | `T-V180-CONV-04`, `T-V180-SEC-01`; `E10` |
| `REQ-V180-CONV-07` — routing, 404/400, the `_STATIC_ROUTES` disposition | `T-V180-CONV-04`, `-05`; the dead-code record; `E12` |
| `REQ-V180-SEC-01` — `redact()` then `esc()`, no third path | `T-V180-SEC-01`; `v180-transcript-redact-bypassed`; `E10` |
| `REQ-V180-SEC-02` — two bounds: 2000 chars per message, `limit` per page | `T-V180-SEC-02`; `v180-transcript-cap-removed`; `E11` |
| `REQ-V180-SEC-03` — REQ-V160-TRC-09 not violated; the sources are distinct | `T-V180-SEC-03`; `E13`'s content-attribute half |
| `REQ-V180-SEC-04` — headers, cap, read-only handle, loopback bind unchanged | `T-V180-SEC-04`; `v180-dashboard-bind-widened`; `E12` |
| `REQ-V180-SEC-05` — parameterized SQL; no interpolation of request input | `T-V180-SEC-04`; the T8 review item 4 |
| `REQ-V180-VER-01` — `1.7.0` → `1.8.0` at T7 only; the tag last, on green | `T-V180-VER-01`; `git tag -l` recorded |
| `REQ-V180-RPT-01` — `lint-docs` repointed at `report-v1.8.0.md` at T7 | `checks.py lint-docs` exit code recorded |
| `REQ-V180-RPT-02` — the report's nine items, delegation record included | `lint-docs`; `/verify-run` item 8 against the record |
| `REQ-V180-RPT-03` — the Russian tg-post under 1500 characters | `wc -m` quoted in the report |
| `REQ-V180-RPT-04` — usage rows; a complete ledger row the operator pastes | `lint-docs`'s ledger-row check; the `docs/llm-usage.md` rows |
| `REQ-V180-REV-01` — clean-context review at T8, eight extra checks | the logged review prompt; the findings-closed record |
| `REQ-V180-REV-02` — offline acceptance, evidence-only commit, then the tag | Appendix B's per-scenario record; `replay --range`; the tag |
| `REQ-V180-REV-03` — regression; no weakened posture; the 4-cycle budget | earlier suites staying green; the repair-cycle count |
| `REQ-V180-REV-04` — the stop route: what is finalised; no bump, no tag | the stop-route report section, or its recorded non-use |

---

## Appendix B — acceptance scenarios (Gherkin, written before code)

```gherkin
# Every scenario runs OFFLINE against fakes, a fake clock and a tmp_path
# database. No live LLM call, Telegram call or network request of any kind
# (REQ-V180-REV-02). SAFETY: no live credential is used as a test value; no
# scenario reads .env or opens the deployment database.

Scenario: E1 — a successful run leaves no status message behind
  Given a fake Telegram client and a run whose reply is an ordinary answer
  When the turn finishes
  Then exactly one status message was sent
  And exactly one deleteMessage was recorded for that message id
  And no message text "✅ done" was ever sent or edited

Scenario: E2 — a failed run keeps the status message with a failure line
  Given a fake LLM that makes run_agent return FALLBACK_LLM_ERROR
  When the turn finishes
  Then the last edit to the status message is "⚠️ failed"
  And no deleteMessage was recorded
  And the user still received the fallback reply

Scenario: E3 — a failed delete is accepted, never escalated
  Given a fake Telegram client whose delete_message always raises
  When a successful turn finishes
  Then the status message is still present in the chat
  And exactly one warning was logged with every registered secret redacted
  And process_update returned normally with the reply delivered

Scenario: E4 — the typing indicator re-sends on the interval and then stops
  Given a fake clock and a configured llm_timeout_s of 30 seconds
  When a turn runs for 60 seconds of fake time
  Then a typing chat action was sent once per 4.0 s of elapsed fake time,
       each send made only while elapsed < llm_timeout_s at that moment
  And no typing chat action was sent once elapsed reached 30 seconds
  And the indicator thread had stopped before the reply was sent

Scenario: E5 — a typing failure disables the indicator and nothing else
  Given a fake Telegram client whose sendChatAction raises on the first call
  When a turn runs to completion
  Then no further typing chat action was attempted
  And the status message still went through its normal states
  And the run returned its reply

Scenario: E6 — every numeric cell is a column, not a drift
  Given a fixture exercising every section builder in dashboard_render
  When each builder renders
  Then every cell holding a number or a fixed-format timestamp carries
       class "num", and no cell holding a word carries it
  And STYLE declares font-variant-numeric: tabular-nums for td.num and th.num
  And STYLE names no monospace family anywhere

Scenario: E7 — the rejected defaults are absent from the sheet and the markup
  Given the rendered output of every section builder and the STYLE constant
  Then no box-shadow and no text-transform: uppercase is present
  And no colour literal outside the six palette tokens and the two status
      colours is present
  And no meta string joins its fields with a middle dot
  And no link text ends with an arrow

Scenario: E8 — the conversations list is bounded and names the entity
  Given a temporary database holding 120 conversations
  When GET /conversations is served with no query parameters
  Then 50 rows are rendered, newest first
  And each row shows id, user, started, messages, active and last activity
  And class "num" is on every one of those columns except active
  And the page uses the word "conversation" and never the word "session"
  And GET /conversations?limit=501 is answered 400

Scenario: E9 — the transcript reads in order and reaches its traces
  Given a conversation of three turns where turn 2 has an llm_calls trace_id
  When GET /conversations/<id> is served
  Then the messages appear in turn_id then id order with their roles visible
  And turn 2 links to /traces/<trace_id>
  And turns 1 and 3 render their turn label as plain text, no dangling link

Scenario: E10 — content is redacted, then escaped, on both routes
  Given a registered secret and a message whose content contains it
       followed by "<script>alert(1)</script>"
  When GET /conversations/<id> and GET /api/conversations/<id> are served
  Then neither response body contains the secret
  And the HTML response contains no unescaped "<script>"
  And the JSON response carries the redacted text

Scenario: E11 — a long transcript paginates instead of hitting the cap
  Given a conversation of 500 messages of 8000 characters each
  When GET /conversations/<id>?limit=500 is served
  Then the response is under 2 MiB and is not the "response too large" body
  And each rendered message is truncated to 2000 characters with its marker
      and its original length stated

Scenario: E12 — the failure answers are the existing ones
  Given a running dashboard server bound to 127.0.0.1 only
  When GET /conversations/999999 is served for an id no row matches
  Then the response is 404 through the shared error page
  And GET /conversations/<id>?offset=-1 is answered 400
  And every response carries the four security headers unchanged

Scenario: E13 — the process fix is in the file, and trace content is still off
  Given AGENTS.md after this release
  Then it contains a "## Context discipline" section naming the write trigger
  And it lists the four exemptions verbatim: commands only; artefacts only;
      a single edit under every threshold; the task is itself the
      clean-context review
  And with OBS_CAPTURE_CONTENT unset, a served span carries none of the four
      content attributes

Scenario: E14 — the run left no secret anywhere
  Given the repository at the implementation tip
  When gitleaks scans the tracked set and the run's own artefacts
  Then it exits 0
  And no file under docs/ contains a credential value
  And no report, prompt or spec names the deployment database or its contents
```

---

## Appendix C — cross-review log

### Round 1

*(empty — no cross-review has been run yet. Each finding is recorded as: id,
severity, requirement touched, ruling (applied / rejected with reason), edit.)*

| # | severity | requirement | finding | ruling | edit |
|---|---|---|---|---|---|
| | | | | | |
