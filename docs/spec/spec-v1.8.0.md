# spec-v1.8.0 — the operator's release: context discipline, chat manners, an instrument panel, and conversations

Status: ready for `go`.
Base: `v1.7.0` (tagged 2026-09-08). Nothing about v1.7.0 is reopened.
Target version: **1.8.0** — MINOR, because the release adds user-facing
functionality (SemVer). `pyproject.toml` `1.7.0` → `1.8.0`; tag `v1.8.0`.

Four subjects and no fifth: (1) **`AGENTS.md` and the project prompts** — the
process fix; the v1.7.0 run delegated 1 of 13 tasks because this repository's
`AGENTS.md` has no Context discipline section (`docs/reports/report-v1.7.0.md`,
"RLM delegation record"). (2) **Telegram chat UX** — the status message stops
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
| `tests/test_v15_standards.py:1685-1728` | `_GATE_MATRIX_LABEL_TO_NAME` (`:1685-1707`) gains the `mutation-v180` label; `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` reads `spec-v1.8.0-delta-1.md` in place of `spec-v1.7.0.md` at `:1728` | EC-10 puts `mutation-v180` in `pre-push`, so both the label map and the matrix table must carry it; a released spec is never edited, and this spec is at its size ceiling, so EC-12 puts the table in the delta file and the test follows it |

Two test doubles already define an unused `delete_message(self, chat_id,
message_id)` stub — `tests/test_pricing.py:128` and
`tests/test_observability.py:205` — so they need **no** amendment. A change
making any other test fail means the change is wrong: stop and reconsider,
never edit the test.

**REQ-V180-EC-04 (MUST) — secrets discipline.** REQ-V170-EC-04 applies,
narrowed: no `.env` write, no value confirmation. Credential **values** are
never printed, logged, committed or quoted in `docs/`; presence checks are by
key **name** only (`grep -q '^KEY=' .env`); tests use the synthetic sentinel
pattern; `data/`, `sandbox/`, `*.db` and `exec_audit.jsonl` are never opened,
printed or quoted. **No key is written into `.env`**, no `.env.bak*`, no
`sed -i`. §6's transcript reads the database through the existing read-only
handle at request time — the running bot's data path, not an executor read;
**no task of this run opens `bot.db`.**

**REQ-V180-EC-05 (MUST) — backward compatibility.** Every new parameter,
config field, environment variable and helper defaults to **current
behaviour** when absent, so unlisted tests and fakes keep passing. Concretely:
`_StatusMessage.finish` gains a keyword-only `ok: bool` with **no default** —
its call sites, the two that REQ-V180-CHAT-08's ordering creates around
`bot.py:707`, are written in the same commit, and an omission is a
`TypeError` at import-time coverage, not a silent revert. `_TypingIndicator`'s
`ceiling_s` follows the same no-default discipline (CHAT-05).
`bot.py` alone constructs the typing indicator (REQ-V180-CHAT-05);
`agent.run_agent`'s signature, the agent loop, the LLM layer, the tracing
layer and the storage schema are untouched.

**REQ-V180-EC-06 (MUST) — this release is not benchmark-affecting, and says
so.** `AGENTS.md:155-157` requires a token-affecting behaviour change to be
benchmarked before and after. **No change here reaches a model request**: no
message, system prompt, tool schema, token limit, timeout, retry or provider
path changes, so `meta.prompt_tools_sha256` and every token-affecting input
stay byte-identical to v1.7.0's. The report states that the rule **does not
fire**, names the reason and lists the touched modules (REQ-V180-RPT-02); no
baseline, no candidate run, no `docs/assets/bench/` write. A task that
discovers a change reaching a request stops, records it under
"Benchmark-affecting changes", and drops it to v1.9.0 — never folds it in.

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
   §5.1's palette — so nothing load-bearing is retyped into a prompt. The
   subagent gets the path plus a ~5-line instruction, no history, and returns
   a **summary** — findings, counts, `file:line` — never raw content. Brief
   files are committed with their task.
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
facts folded into this file, the decisions `D1`–`D14`, and the exact `go` line.
It is the only handoff artefact; `docs/plan.md` is a carried-candidates
document, not a handoff. Every prompt file carries the seven-bullet header
(`Date`, `Executor model`, `Model reason`, `Harness`, `Stage`, `Owner of`,
`REQ ids`) then exactly four level-2 blocks in order — `## Goal`,
`## Constraints`, `## Acceptance`, `## Stop` — per `docs/prompts/TEMPLATE.md`,
unchanged here. **126 is the highest pre-existing prompt number** (125 is
v1.7.0's operator acceptance, 126 this spec's own authoring prompt), so T0's
is `docs/prompts/127-go-spec-v1.8.0.md` and the run numbers upward. Each task
of §12 is one prompt file and one commit whose body carries `(prompt:
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
exist. **Round 1 of the cross-review used that escape**: the 21-row gate
matrix lives in the delta file (REQ-V180-EC-12), which is normative and is
read by `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`.

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
| `NG-06` | No change to the agent loop: `agent.py`'s branch structure, round cap, tool dispatch, summary path and fallback **texts** stay as they are. The only additions are REQ-V180-CHAT-04's `AgentOutcome` and `run_agent_outcome`; `run_agent` keeps its signature and its `str` return. |
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

**REQ-V180-AGT-03 (MUST) — the factual lines stay true, and each is written
once.** `AGENTS.md` is corrected where this release makes it wrong and
**nowhere else**, in **two tasks split by when the fact becomes true** — a
line whose value does not exist yet cannot be written truthfully, and writing
it twice puts the same factual line inside two tasks' acceptance boundaries:

- **T1 — the non-count edits only**: the `## Project layout` line for
  `dashboard_server.py` naming the conversations routes, alongside AGT-01's
  and AGT-02's new sections. T1 touches **no** count-bearing line.
- **T7 — every claim whose value depends on work already landed**, written
  once and only there, after T6 has created the entries: the gate-6
  mutation-entry count (92 → 98 after REQ-V180-EC-10's six), the `--select`
  example gaining `v180-`, and the `pytest` count if it has moved off 1133.

Style edits, reorderings and rewrites of untouched paragraphs are a defect.

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
def delete_message(self, chat_id: int, message_id: int) -> bool:
    return self._call_with_retry("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
```

`-> bool`, not `-> dict`: every client method returns the **unwrapped
`result`** of the API envelope (`bot.py:140`), and `deleteMessage`'s `result`
is the JSON boolean `true` where `send_message`'s and `edit_message_text`'s
(`bot.py:167-175`) are Message objects — so the three annotations differ
legitimately. `_call_with_retry`'s own annotation (`bot.py:142`) widens to
`-> dict | bool` in the same commit; that is the whole edit — no behaviour, no
call site and no other annotation moves. It goes through `_call_with_retry`
exactly as its two neighbours do,
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

**REQ-V180-CHAT-03 (MUST) — on failure the message is kept, and the final
line is best-effort.** `bot.py` gains `STATUS_FAILED = "⚠️ failed"` beside
`STATUS_WORKING` (`bot.py:62`). When `ok` is false, `finish` **attempts**
`self._edit(STATUS_FAILED)` and the message stays — the operator's record that
the run happened and did not land. The attempt carries CHAT-06's discipline
and MUST never fail the run, so what is guaranteed is stated exactly: the bot
attempts the edit; if Telegram rejects it the **previous status text remains**
(`⚙️ working…`, or the last `⚙️ exec: ` line), one redacted `log.warning` is
emitted and the run delivers its reply unchanged. That stale line is an
**accepted outcome**, not a defect, not a retry loop and not an error shown to
the user; the invariant that never bends is that a failed run's status message
is never deleted. Like every status text `STATUS_FAILED` is under
`STATUS_MAX_CHARS = 64`.

**REQ-V180-CHAT-04 (MUST) — the failure signal is a structured outcome, not
a predicate over reply text.** `agent.run_agent` returns a `str` and **never
raises for a model failure** — it encodes failure as a `FALLBACK_*` constant
(`agent.py:71-83`), so a bare `try/except` at the call site would mark almost
every run successful. Reconstructing the verdict *from the reply* is worse
than useless: a model answer equal to a fallback, or a fallback that gains a
decoration or a truncation notice, is indistinguishable from the other. The
knowledge exists at the return site, so this release **carries it out**
instead of throwing it away and guessing it back:

```python
@dataclass(frozen=True)
class AgentOutcome:
    reply: str
    failed: bool
    kind: str | None    # "empty" | "no_answer" | "llm_error" | "interrupted" | None
```

- `agent.py` gains `AgentOutcome`, its `from dataclasses import dataclass`
  (standard library, no new distribution — EC-01), and
  **`run_agent_outcome(...) -> AgentOutcome`** carrying `run_agent`'s exact
  signature (`agent.py:226-241`). `run_agent_outcome` takes over the present
  body of `run_agent` — the root span and the delegation to `_run_agent_turn`
  — and `_run_agent_turn`'s inner `finish` (`agent.py:280-297`) gains
  keyword-only `failed: bool = False` and `kind: str | None = None` and
  returns an `AgentOutcome` where it returns a `str` today; its redaction and
  one-transaction discipline are byte-unchanged.
- The fallback return sites pass `failed=True` and their `kind`:
  `agent.py:328` `"interrupted"`, `:398` `"llm_error"`, `:405` and `:445`
  `"no_answer"`, `:412` `"empty"`. The site at `:415-418` is conditional and
  passes the **same condition** — `has_content` yields the answer and no
  `kind`, otherwise `FALLBACK_NO_ANSWER` and `"no_answer"`; `:403`'s answer
  path passes nothing and is `failed=False`. No branch, no round cap, no
  fallback text and no control flow moves (NG-06).
- **`run_agent` keeps its name, its signature and its `-> str`**, becoming a
  one-line wrapper: `return run_agent_outcome(...).reply`. Its ~25 call sites
  across eleven test files are **untouched** — zero test churn is what makes
  the structured outcome cheaper than the text predicate it replaces.
- `bot.py`'s single production call site (`bot.py:692-708`) is the only caller
  that moves: it calls `run_agent_outcome` and reads `outcome.failed`. The
  ordering around it is REQ-V180-CHAT-08's. Inverting that flag MUST turn the
  suite red (`v180-status-signal-inverted`, §9).

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
  deliberate, so no executor extends it;
- **join bound: 1.0 s** — `TYPING_JOIN_TIMEOUT_S = 1.0`, beside the interval.

Mechanics: a `_TypingIndicator` class in `bot.py` starting one **daemon**
`threading.Thread` (`threading` is already imported, `bot.py:20`) whose loop
waits on a `threading.Event` for `TYPING_INTERVAL_S`, so `stop()` wakes it
immediately rather than sleeping out the interval. Four properties are
requirements, not implementation taste:

1. **One unretried attempt per tick.** The worker calls
   `tg.call("sendChatAction", …, read_timeout=…)` — the single-attempt path
   at `bot.py:105` — and **never `_call_with_retry`**, which can block past
   the ceiling, fire after `stop()`, and issue several requests for one tick.
   One attempt per tick is what makes the ceiling arithmetic true: at most
   `ceil(cfg.llm_timeout_s / TYPING_INTERVAL_S)` requests per run, no bursts.
2. **Both guards are checked immediately before each attempt**, in order: the
   stop event (set → return without sending), then the elapsed clock (≥ the
   ceiling → return). No request is issued after either is true.
3. **Any error is terminal for the indicator**: one `log.warning` with
   `config.redact()` applied, the indicator disabled for that run, the thread
   exits, the run unaffected (CHAT-06). No retry, no second attempt.
4. **`stop()` sets the event and joins**, bounded by `TYPING_JOIN_TIMEOUT_S`;
   a timed-out join is logged once and the caller proceeds — the thread is a
   daemon and cannot block shutdown. The bounded join, not the daemon flag,
   is what stops the worker racing the reply. `stop()` is idempotent.

**The test seams are constructor parameters**, so the tested and the shipped
synchronisation paths are the same code:
`_TypingIndicator(tg, chat_id, *, ceiling_s: float, interval_s: float =
TYPING_INTERVAL_S, monotonic: Callable[[], float] = time.monotonic,
stop_event: threading.Event | None = None)` — `stop_event=None` constructs a
real `threading.Event`, and `ceiling_s` has **no default** so an omission is a
`TypeError`, not a silent forever-typing indicator (EC-05). The tests pass a
fake clock and a fake event and **no test sleeps in real time**. `bot.py`
starts it beside `_StatusMessage` (`bot.py:691`) and stops it in a `finally`
around the same `run_agent_outcome` call, so no path leaves a thread running.
It sends through the same `TelegramClient`; `httpx.Client` is safe for
concurrent use. It **complements** the status message and never replaces it.

**REQ-V180-CHAT-06 (MUST) — best-effort, in both directions, and proved by the
selftest.** `_StatusMessage`'s discipline (`bot.py:286-288`) extends unchanged
to both new mechanisms: **any** Telegram error disables further work of that
kind for that run — one `log.warning` with `config.redact()` applied — and
**never fails the run itself**:

- a failed `delete_message` **leaves the status message in the chat** — an
  accepted outcome, not a retry loop and not an error to the user; the run
  still delivers its reply;
- a failed `STATUS_FAILED` edit leaves the previous status text (CHAT-03);
- a failed `sendChatAction` disables the indicator for that run and nothing
  else — one attempt, no retry (CHAT-05 item 3);
- neither mechanism may raise out of `process_update`.

`--selftest` proves it offline: `_SelftestTelegram` (`bot.py:1085-1103`) gains
a `deleted` recorder and a `delete_message` method, and the assertion at
`bot.py:1211` becomes: exactly one recorded status send of `STATUS_WORKING`,
exactly one edit starting `"⚙️ exec: "`, and **exactly one recorded deletion**
of that message id — no `STATUS_DONE` edit, the constant no longer existing.
`--selftest` binds no port and makes no network call (`bot.py:1167`).

**REQ-V180-CHAT-07 (MUST) — the outcome contract, proved per return path.**
`T-V180-CHAT-08` drives `run_agent_outcome` down **each** fallback path with
fakes and asserts, for every one: `failed is True`, `kind` equal to that
path's literal, and `reply` identical to the matching `FALLBACK_*` constant
(the templated one after `.format()`). It asserts the answer path yields
`failed=False`, `kind is None` and the model's own text. The four `kind`
literals are the closed vocabulary — `"empty"`, `"no_answer"`, `"llm_error"`,
`"interrupted"` — and a fallback added later is classified at **its own return
site** instead of by a matcher that has to be kept in sync with it.

**REQ-V180-CHAT-08 (MUST) — the status is resolved after the reply is
delivered, never before.** Deleting the status message before the reply is out
leaves a failed send with no answer in the chat **and** no record that
anything happened. The order at `bot.py:692-708` is a requirement, not prose:

1. obtain the `AgentOutcome` from `run_agent_outcome`;
2. **send the reply** — `_send(tg, chat_id, split_message(outcome.reply))`,
   which gains an additive `-> bool`: `True` when every part went out,
   `False` when it stopped at a failed part. `_send` (`bot.py:964-971`) keeps
   catching `TelegramError`, logging it redacted and returning rather than
   raising, so none of its fifteen other call sites changes behaviour and
   EC-05 holds;
3. **only when the send returned `True` and `outcome.failed` is false**,
   `status.finish(ok=True)` — the deletion;
4. **otherwise** `status.finish(ok=False)` — the `STATUS_FAILED` edit of
   CHAT-03.

The exception arm stays: an exception out of `run_agent_outcome` — the paths
that really do raise, such as `finish`'s transactional write
(`agent.py:288-296`) — calls `status.finish(ok=False)` and re-raises.
`T-V180-CHAT-09` drives a `send_message` that raises `TelegramError` on the
reply and asserts the status message survives carrying `STATUS_FAILED` and
that no deletion was recorded. It asserts nothing about the typing indicator,
which does not exist until T3 — a test claim may never depend on work a later
task lands (AGT-03's rule, applied to tests).

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
**single definition of the class**: `class="num"` is a property of the
**column**, not of the individual cell. A column is **numeric** when its
**data cells** hold numbers or fixed-format timestamps — a count, duration,
token total, cost, percentage, id or ISO timestamp, anything whose digits
should align down the column. In the HTML of every section builder, **a
numeric column carries `class="num"` on its `<th>` and on every one of its
`<td>`s**, and a column whose data cells hold words (`active`'s `yes`/`no`, a
role, a label) carries it on neither. The heading's own text is a word in
every case — `id`, `user`, `started`, `messages` — and is **irrelevant**: the
class controls the column's alignment, not the content type of the cell it
sits on. `T-V180-DSH-01` renders each builder against a fixture, derives each
column's kind from its data cells and fails on either miss; it MUST be red
before the work and green after. In the
same change the `td.num, th.num` rule **drops its `font-family: ui-monospace,
...` declaration**: §5.1 forbids a monospace face for data, and tabular figures
in the body face do the alignment job.

**REQ-V180-DSH-04 (MUST) — the rejected defaults are absent from the
chrome, and asserted.** The check is scoped to the **static chrome** — the
`STYLE` constant and the markup the builders emit — and **excludes
interpolated content**: a user is free to type `box-shadow`, `#ff0000` or a
middle dot into a message, and a scan of the whole rendered page would
false-fail on their transcript. The seam is named so the test can be written
against it: every builder is rendered twice against the **same fixture**, once
with the fixture's message/label text and once with every interpolated field
replaced by a fixed sentinel; the **intersection** of the two outputs is the
chrome, and only the chrome is scanned. `T-V180-DSH-02` reads `STYLE` and each
builder's chrome and fails on any of: a `box-shadow`; `text-transform:
uppercase`; `border-radius` over 2px; a `font-family` naming a monospace or
serif family; a colour literal outside the eight of §5.1; a meta string
joining fields with `·`; link text ending in `→`. The middle-dot join is live
today in `tool_health_section` (`dashboard_render.py:429-436`) and the
uppercase `th` rule at `:113-114`, so the test is red before the work — a
gate, not a decoration.

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

**REQ-V180-CONV-02 (MUST) — four read functions in `storage.py`.** All mirror
`recent_traces` (`storage.py:700-726`): parameterized SQL, bounds as
parameters, `sqlite3.Row` results, no formatting.

- `conversation_row(conn, conv_id)` — the `conversations` row, or `None`. An
  **existence reader**: an empty conversation and an absent one are
  indistinguishable through the message query, and this is what tells them
  apart (CONV-04, CONV-07).
- `recent_conversations(conn, *, limit)` — `id`, `tg_user_id`, `created_at`,
  `active`, `message_count` (`COUNT` over `messages`), `last_activity`
  (`MAX(messages.created_at)`, `NULL` for an empty conversation); ordered
  `created_at DESC, id DESC`, bounded by `limit`.
- `conversation_messages(conn, conv_id, *, limit, offset)` — **pages by turn,
  never by row.** `ORDER BY turn_id, id` with `LIMIT`/`OFFSET` over messages
  would split a turn across two pages, which CONV-04 forbids, so the page is
  selected by turn and then filled:
  1. **the turn window** — `SELECT turn_id, COUNT(*) AS n FROM messages WHERE
     conv_id = ? GROUP BY turn_id ORDER BY turn_id ASC LIMIT ? OFFSET ?`,
     `offset` counting **turns** and the limit bound as `limit + 1`: a turn
     holds at least one message, so `limit` turns hold at least `limit`
     messages and the extra turn is the row beyond the page;
  2. **the page** — take turns in order while the running message count is
     `< limit`; the turn that crosses `limit` is taken **whole**, so a page is
     *up to `limit` messages, extended to the end of the last turn*;
  3. **the probe** — the first turn not taken. Its presence is the return's
     `has_more`; it is **discarded before rendering**;
  4. **the messages** — `SELECT turn_id, role, content, tool_call_id,
     created_at, id FROM messages WHERE conv_id = ? AND turn_id IN (…)
     ORDER BY turn_id ASC, id ASC`, one bound placeholder per taken turn.

  It returns `(rows, has_more)` — the one reader of the four returning more
  than a row list, `has_more` being unrecoverable from the rows.
- `conversation_turn_traces(conn, conv_id)` — REQ-V180-CONV-05's link map.

A missing conversation yields an empty list from the message query and `None`
from `conversation_row`; the caller decides the 404 (CONV-07).

**REQ-V180-CONV-03 (MUST) — `/conversations`, the list.** A page rendered by
the new pure builder `conversation_list_section(rows)` in
`dashboard_render.py`. Row shape, exactly: **id** (linking to `/conversations/<id>`), **user**
(`tg_user_id`), **started** (`created_at`), **messages** (count), **active**
(`yes`/`no`, ok colour for yes), **last activity** (`last_activity`, or `—`
when the conversation has no message). **Five of the six columns — id, user,
started, messages, last activity — are numeric columns and carry `class="num"`
on the `<th>` and on every `<td>`**; `active` is not one, its data cells
holding a word. That the five headings are themselves words is irrelevant
(REQ-V180-DSH-03). Page size is bounded by the **`limit`
query parameter** through the existing `_parse_limit(params, 50, is_api=...)`
(`dashboard_server.py:168-177`): **default 50**, range **1–500**, anything
else a 400. An empty database renders one empty-state row, never a blank
table.

**REQ-V180-CONV-04 (MUST) — `/conversations/<id>`, the transcript.** A page
rendered by `conversation_transcript_section(...)` in `dashboard_render.py`,
laid out per §5.1's two-column plan. Per message, in `turn_id`/`id` order: the
**role** (`user` / `assistant` / `tool`, visible as text, not a colour alone),
the **turn id**, the **timestamp**, the **content**. The rail's turn id and
timestamp are its numeric fields and carry `class="num"`; the role word, the
trace link and the content do not (REQ-V180-DSH-03). Content comes
from `messages.content` — the text the bot already stores for the agent's own
memory — bounded and sanitised by §7. A `tool` row also shows its
`tool_call_id`. **No turn is ever split across two pages** — CONV-02's
by-turn window is what guarantees it.

Pagination is by **`limit`** (`_parse_limit(params, 200, is_api=...)`, default
**200**, range 1–500, a bound on *messages*) and **`offset`** (a count of
*turns*, per CONV-02): a new `_parse_offset` sharing `_parse_conv`'s
parse-and-reject shape — `re.fullmatch(r"[0-9]+")`, a range check,
`_bad_request` on either failure — but **not** its bounds, the range being
`0 ≤ n ≤ 2**31 - 1` with an absent parameter `0`, because offset 0 is the
first page whereas a conversation id starts at 1. The **next link is emitted
if and only if `conversation_messages` returned `has_more`** — never on a row
count, which would either walk the operator into empty pages forever or hide
a real page when the last one holds exactly `limit` messages; its `offset` is
the current one plus the number of turns this page took. The prev link is
built from the same two values and nothing else, and the page states the
range it is showing.

**The 404 is decided by `conversation_row`, not by an empty result.** An
existing conversation with no messages renders the empty state at 200; only
`conversation_row(conn, conv_id) is None` is a 404 (CONV-07).

**REQ-V180-CONV-05 (MUST) — the link to a trace, and the join that finds
it.** `messages` has **no `trace_id` column** (`storage.py:154-171`), so the
link is not a field lookup. `trace_id` lives on `llm_calls` and `tool_calls`,
both carrying `conv_id` and `turn_id`, so `conversation_turn_traces(conn,
conv_id)` returns a mapping `turn_id -> trace_id`. "First" is defined, because
"the first non-null `trace_id`" is otherwise query-plan dependent and two
implementations could link the same turn to different traces: it is the
`trace_id` of the **lowest `id` in `llm_calls`** for that `(conv_id, turn_id)`
whose `trace_id` is non-null; if there is none, the **lowest `id` in
`tool_calls`** under the same condition; if there is still none, the turn is
absent from the mapping and gets no link. A turn in the mapping renders its
rail entry as a link to
`/traces/<trace_id>`; a turn absent renders plain text — no dangling link, no
placeholder. Link text is the abbreviated trace id with **no arrow appended**
(§5.1).

**REQ-V180-CONV-06 (MUST) — the JSON mirrors.** `/api/conversations` and
`/api/conversations/<id>` mirror the two pages as `/api/traces` mirrors
`/traces` (`dashboard_server.py:579-593`): same query parameters, same bounds,
same rows, `_respond_json`, and a payload echoing the parameters (`{"limit":
..., "conversations": [...]}` and `{"conv": ..., "limit": ..., "offset": ...,
"has_more": ..., "messages": [...]}`). `offset` is the **turn** offset of
CONV-02, echoed in the unit it was parsed in, and `has_more` is CONV-04's
probe result — without it an API client cannot tell whether another page
exists, the same defect the HTML next link avoids. The JSON carries the **same
redacted and capped content** the HTML does (§7) — an API route is not a
bypass, and SEC-02's byte budget binds it too. Errors use the existing JSON
error body, not an HTML page.

**REQ-V180-CONV-07 (MUST) — routing, and the two failure answers.** Two
compiled patterns join `_TRACE_PAGE_RE`/`_TRACE_API_RE` (`:56-57`):
`_CONV_PAGE_RE = re.compile(r"^/conversations/([0-9]{1,10})$")` and
`_CONV_API_RE = re.compile(r"^/api/conversations/([0-9]{1,10})$")`. `_route`
(`dashboard_server.py:407-428`) gains `/conversations` and
`/api/conversations` beside `/traces` and `/api/traces`, and the two
`match`-based arms beside the trace ones, **before** the closing `_not_found`.
An id outside `1 ≤ n ≤ 2**31 - 1`, or one for which `conversation_row` returns
`None`, is a **404** through the existing `_not_found(is_api=...)` — and an
existing conversation holding no messages is **not** one: it answers 200 with
the empty state. A malformed `limit` or `offset` is a **400** through
`_bad_request` (`dashboard_server.py:91-98`).
`_STATIC_ROUTES` (`dashboard_server.py:53-55`) is **pre-existing dead code,
referenced nowhere in the repository**; this release adds the two new static
routes so it does not grow *more* stale, does not otherwise touch or delete
it, and records the finding in the report (REQ-V180-RPT-02).

---

## 7. Security

The transcript is the first dashboard view showing what the user and the model
actually said. It gets its own group and its own mutation entries, because
redaction that silently stops working is the failure a green suite hides.

**REQ-V180-SEC-01 (MUST) — `redact()` always; `esc()` per sink.** The
invariant that admits no exception: **no message-derived value reaches any
sink without `config.redact()`** (`config.py:161-166`). Escaping is stated per
sink, the two sinks encoding differently:

- **HTML sink** — `redact()` **then** `dashboard_render.esc()`
  (`dashboard_render.py:53`), in that order. Order matters: escaping first
  would let an HTML-encoded fragment of a registered secret survive `redact`'s
  literal `str.replace`.
- **JSON sink** — `redact()` **only**. `json.dumps` performs its own escaping,
  and HTML-escaping a JSON string would corrupt the stored text on the way out:
  `<` served as `&lt;` is a different value from the database's, and CONV-06
  requires a faithful mirror.

Redaction happens in `dashboard_server.py` (which may import `config`);
escaping in `dashboard_render.py`, which stays pure. Both routes redact; the
API route is not a bypass.

**REQ-V180-SEC-02 (MUST) — the output is bounded three times, in bytes, and
the 2 MiB cap is never what catches it.** `MAX_RESPONSE_BYTES`
(`dashboard_server.py:39`) is a backstop, not a design. The cap is **not**
provable by character arithmetic: UTF-8 needs up to four bytes per character
and `esc()` expands one character to as many as six (`&quot;`), so
500 × 2000 characters is worst-case ~6 MB, not "under 1 MiB". The bound is
therefore **enforced, not proved**:

1. **per message**: rendered content is truncated to **2000 characters of the
   escaped text** — `redact()`, then `esc()`, then the cut — the number
   REQ-V160-TRC-09 already fixes for a captured content attribute, reused
   rather than reinvented. The `…` marker and the original-length note are
   **additional to** the 2000, not inside it: the cap governs the message text
   alone, and the two annotations are counted only by the page budget below.
   That is the per-row maximum every byte-exact test asserts;
2. **per page**: the `limit` of REQ-V180-CONV-04, default 200, maximum 500 —
   messages, extended to the end of the last turn (CONV-02);
3. **per response, on both sinks**: the builder accumulates **rendered
   bytes** and stops before the first row that would carry the response past
   **`TRANSCRIPT_PAGE_BUDGET_BYTES = 1_572_864`** (1.5 MiB, leaving room for
   the chrome and the cap's own margin), then emits the truncation marker and
   the next-page link. The JSON route does not go through the HTML builder, so
   it applies the same budget to its own serialized rows before
   `_respond_json`, dropping the trailing messages and reporting `has_more`
   true. A pathological conversation paginates on either route; it is never
   refused.

`T-V180-SEC-02` drives a conversation at both maxima through both routes with
a **worst-case fixture** — 4-byte characters (astral plane) mixed with
escape-expanding characters (`"`, `&`, `<`, `>`) — and asserts the byte budget
holds and the response is produced normally, not through the "response too
large" path (`dashboard_server.py:663-673`). An ASCII fixture does not
discharge this requirement.

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
`tests/test_v180_conversations.py`, `tests/test_v180_version.py`. All offline,
all against fakes, a fake
clock and a `tmp_path` database.

| id | asserts |
|---|---|
| `T-V180-CHAT-01` | `delete_message` posts `deleteMessage` via `_call_with_retry`; raises `TelegramError` on a fatal result |
| `T-V180-CHAT-02` | `finish(ok=True)` deletes, clears `_message_id`, issues no edit |
| `T-V180-CHAT-03` | `finish(ok=False)` edits to `STATUS_FAILED`, no delete; `STATUS_DONE` absent from `bot`'s namespace |
| `T-V180-CHAT-04` | `run_agent` returns exactly `run_agent_outcome(...).reply` — same inputs, same `str`, no signature change |
| `T-V180-CHAT-05` | negative: a raising `delete_message` leaves the message, logs once redacted, reply delivered |
| `T-V180-CHAT-06` | **one** unretried request per tick on the fake clock, nothing at/after `ceiling_s`, none after the event is set; `stop()` wakes and joins inside `TYPING_JOIN_TIMEOUT_S` |
| `T-V180-CHAT-07` | negative: a raising `sendChatAction` disables the indicator only |
| `T-V180-CHAT-08` | every fallback return path yields `failed=True` with its `kind` and the matching constant; the answer path yields `failed=False`, `kind is None` |
| `T-V180-CHAT-09` | negative: the reply send raises — the status message survives with `STATUS_FAILED`, no deletion recorded |
| `T-V180-DSH-01` | coverage by column: a column whose data cells are numbers/timestamps carries `class="num"` on `<th>` and every `<td>`, a word column on neither; `STYLE` declares `tabular-nums`, **no** monospace family |
| `T-V180-DSH-02` | negative: DSH-04's closed list absent from `STYLE` and from every builder's **chrome** — the sentinel-intersection seam, interpolated content excluded |
| `T-V180-DSH-03` | exactly the six palette tokens plus two status colours; every colour literal is one of those eight |
| `T-V180-DSH-04` | every nav carries the four entries in order; `page()` emits one `<style>`, no `<script>`, no external URL |
| `T-V180-CONV-01` | `recent_conversations`: six fields, newest first, bounded; `last_activity` `NULL` when empty |
| `T-V180-CONV-02` | `conversation_messages` orders by `turn_id, id`, pages by turn — no group split at the default limit — and returns `has_more` from the probe turn, which never appears in the rows |
| `T-V180-CONV-03` | `conversation_turn_traces` maps to `llm_calls`, falls back to `tool_calls`, omits a turn with neither |
| `T-V180-CONV-04` | negative: the list renders the decided row shape; `limit=0`, `501`, `x` each give 400 |
| `T-V180-CONV-05` | negative: transcript in order, only traced turns linked, paginates by `limit`/turn `offset` with the next link following `has_more`; unknown id 404, **existing-but-empty 200** |
| `T-V180-SEC-01` | negative: a registered secret is replaced on both routes; `<script>` in content is escaped, not served |
| `T-V180-SEC-02` | worst-case fixture (4-byte + escape-expanding characters), 500 × 8000 characters: the page holds under `TRANSCRIPT_PAGE_BUDGET_BYTES`, each message cut to 2000 escaped characters with the marker and original length **additional** |
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
branch reaching T8; on a stop-route branch (§11) it is **whatever the tree
has** — a stop after T2 has committed tests, and no test may be deleted to get
back to the floor. State the exact number in the report either way.
Gates 1–4 and 6 are re-run against the final tree before the closing commit on
**every** branch, stop route included — T0's exit codes prove the tree T0 ran
on, not the tree that ships.

**The gates run against the tree that ships, including the last commit.** T10
lands a docs-only commit *after* its gate run, so that commit would otherwise
carry the tag ungated. The rule: after the final docs-only commit, **re-run
`checks.py lint-docs` and tag that commit**. Gates 1–4 and 6 are **not**
re-run, for the reason stated in the same sentence — the commit changed no
file any of them reads, the rule the lab already applies to skipping the
mutation gate on a docs-only change. The report records `lint-docs`'s exit
code and the tagged sha (REQ-V180-RPT-02).

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
| `v180-transcript-budget-removed` | the transcript page builder's byte accumulation: remove the `TRANSCRIPT_PAGE_BUDGET_BYTES` check so it emits every row of the page | `T-V180-SEC-02` |

The sixth entry is deliberately **not** a mutation of the loopback bind: a
mutation must break a mechanism *this release introduces*, and
`DASHBOARD_BIND` is a pre-existing constant already covered by the
pre-existing `T-V160-SRV-*` assertions, so such an entry is green on day one
and proves nothing. The bind stays covered exactly as it is today (SEC-04);
the byte budget replaces it because removing that budget is precisely the
failure the 2 MiB cap must catch, and it does not exist until T6. Each of the
six MUST be confirmed **red before the work and killed after**.

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

**REQ-V180-EC-12 (MUST) — the gate matrix moves into this release's delta
file.** `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
(`tests/test_v15_standards.py:1727-1741`) parses the gate matrix out of the
spec file it names and asserts it agrees with `profiles:` in
`config/quality_gates.yaml`. It reads `spec-v1.7.0.md` today; a released spec
is never edited, so T6 repoints it (`:1728`) at
**`docs/spec/spec-v1.8.0-delta-1.md`** — this release's overflow file, per §1's
budget rule — and adds the `mutation-v180` label to
`_GATE_MATRIX_LABEL_TO_NAME` (`:1685-1707`). That file carries
REQ-V170-GATE-03's table, yes/— verbatim, plus the `mutation_check.py --select
v180-` row, minus the `note` column the parser never reads; it is **21 rows**
and it is load-bearing markup — the parser finds the header by the literal
`| gate | pre-commit`, takes rows until the first line not starting with `|`,
and every label must match the map byte-for-byte. The delta file holds the
matrix and nothing else; it is created in T6 and committed with it.

---

## 10. Version, reporting and the ledger

**REQ-V180-VER-01 (MUST) — 1.8.0, and where the bump lives.**
`pyproject.toml`'s `project.version` moves `1.7.0` → `1.8.0` in **T9 and
nowhere else** — the last task before tagging, and only **after T8's gates are
green**. This is the one carve-out from T8's "every source, test and config fix
lands here or earlier", named here and in §12 so the two do not contradict:
the version line and `T-V180-VER-01` are not a fix, they are the release
stamp, and T10 re-runs every gate over the tree that carries them. Putting the
bump last is also what makes the stop route honest — a stop at **any** earlier
point needs no revert, because `pyproject.toml` still reads `1.7.0` by
construction (REQ-V180-REV-04). `T-V180-VER-01` is written in the same task,
red before the edit and green after; `README.md`'s Versioning section and
`AGENTS.md` echo the number in the same commit. The annotated tag `v1.8.0` is created **only** on
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
9. the `--no-verify` attestation sentence of REQ-V180-EC-08;
10. the **tagged sha** and the exit code of the `lint-docs` run made against
    the tagged commit *after* it landed (REQ-V180-EC-09, REQ-V180-REV-02) —
    or, on the stop route, the stage and the last green commit
    (REQ-V180-REV-04).

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
2. **every** transcript path redacts, and the HTML paths escape after
   redacting while the JSON paths do not escape at all (SEC-01) — no third
   path, and no HTML-escaped value in a JSON body;
3. `served_span()`, `SERVED_SPAN_ATTRIBUTE_KEYS` and the `OBS_CAPTURE_CONTENT`
   default are byte-unchanged (NG-10);
4. every new SQL statement binds its parameters;
5. `_StatusMessage` and `_TypingIndicator` cannot raise into `process_update`,
   and the indicator's thread stops on every path including the exception one;
6. `agent.py` gained `AgentOutcome`, `run_agent_outcome` and `finish`'s two
   keyword-only arguments and **nothing else** (NG-06); `run_agent` is the
   one-line wrapper and its signature is byte-unchanged; every fallback return
   site carries a `kind`;
7. `STYLE` matches §5.1 literally: six tokens, two status colours, four sizes,
   two weights, no shadow, no monospace, no uppercase transform;
8. each of §9's six mutation entries has a `find` matching exactly once, a
   named killing test, and a **recorded red-before / killed-after** pair — no
   entry over a pre-existing, already-covered mechanism — and the delta file's
   gate-matrix table still agrees with `config/quality_gates.yaml`.

**REQ-V180-REV-02 (MUST) — acceptance, offline, and the freeze.** After the
`full` profile is green, execute **Appendix B** against the repository and the
recorded documents — every scenario against fakes, a fake clock and a temporary
database. **No live LLM call is needed to accept this release** and none is
made. Record pass or fail per scenario and, per REQ-V12-REP-02, **how** each
was driven. T9 lands VER-01's version bump and a provisional
`report-v1.8.0.md` carrying every REQ-V180-RPT-02 item except item 5's tip
SHA; that commit's SHA **is** `<implementation-tip>`. T10 re-runs the six gates, `full --since <base>`,
`replay --range <base>..<implementation-tip>` and Appendix B against the final
tree, then lands **one evidence-only commit** touching `docs/reports/*` and
nothing else — not recursively required to replay against itself. **After it
lands**, `checks.py lint-docs` is re-run against it and the annotated tag
`v1.8.0` is created on **that** commit, so the tagged tree is the one the
recorded documentation gate passed. Gates 1–4 and 6 are not re-run: the commit
changed no file any of them reads (EC-09). The report records the re-run exit
code and the tagged sha.

**REQ-V180-REV-03 (MUST) — regression, and no weakened posture.** spec-v1.2's
D1 and D2, spec-v1.4's S01 acceptance, spec-v1.5's freeze properties and
spec-v1.6.0's tracing, dashboard and tool-quality properties still hold. No
earlier security posture is weakened: exec sandbox, redaction choke points,
SSRF allowlist, loopback-only dashboard, read-only handle, security headers,
response cap and `.env` handling are untouched except where §7 **adds** a
constraint. Failures are fixed and the whole set rerun inside the **4-cycle**
repair budget; exhausting it means the stop route — not relaxing a gate, not
deleting a test, not lowering a bound.

**REQ-V180-REV-04 (MUST) — the stop route, in two stages.** If a gate stays
red after the repair budget, or a spec-internal contradiction is found that
cannot be resolved without a decision, the run **stops and finalises** — it
does not half-ship. What the route can promise depends on **where the run
stands**, because from T2 on code is committed and finalising does not
un-commit it:

- **Stage A — before T2.** Nothing of this release is committed. The
  procedure below runs and, additionally, the collected test count equals
  T0's measured floor and the report states that no code was written.
- **Stage B — from T2 on.** Commits exist. Then: **no revert, no test
  deletion, the tree stays exactly as committed**; the failing gate's output
  is the evidence; the collected test count is **whatever the tree has**
  (EC-09), never reduced toward the floor; no version bump and no tag —
  `pyproject.toml` still reads `1.7.0` **by construction**, VER-01 having put
  the bump in T9; and the report records the **last green commit by sha**.

The procedure, invoked from wherever the run stands, naming its stage:

1. **Finalise `docs/reports/report-v1.8.0.md`** from T0's skeleton: the stage,
   every REQ-V180-RPT-02 item the branch reached, and for each it did not, the
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
   rows, task-brief files. **This commit is permitted on the stop route and
   required by it** — it is how the evidence reaches the repository at all. No
   source, test or config file is in it; `--no-verify` is forbidden here as
   everywhere.
6. **Prove the negative and terminate**: `pyproject.toml` still reads its
   pre-stop version (`1.7.0` at every stage, per VER-01), `git tag -l` shows no
   `v1.8.0`, and the report says so. **No bump, no tag, and none of REV-02's
   closing sequence**: item 5's commit is *not* REV-02's evidence-only commit,
   is never tagged, and is the run's last action. The prohibition on an
   evidence-only commit governs the **normal** route — where the only one is
   REV-02's, created at T10 on a green tree — and does not reach item 5. No
   later task of §12 runs.

---

## 12. Implementation order

**REQ-V180-EC-11 (MUST)** Work in this order; each task is one prompt and one
commit, with §12.1's reading map and REQ-V180-EC-07's delegation rule. Tests
come before the code they cover, inside the same task.

| T | task | acceptance |
|---|---|---|
| **T0** | Preconditions: six gates green on the unchanged tree, hooks installed, `doctor` green, **test count re-measured** (floor 1133), `<base>` and the spec's `sha256` recorded, `docs/prompts/127-go-spec-v1.8.0.md` and `docs/spec/task-briefs/` created, the `report-v1.8.0.md` skeleton landed with `## Operator inputs` copied verbatim from the `go` request and a complete ledger-row block | every item recorded; 126 is the highest pre-existing prompt; `<base>` written before the first commit; an unreachable LM Studio **blocks** here |
| **T1** | §3: Context discipline and the branch-zone rule; the **non-count** factual line (the layout line) corrected; `skills/*.md` and `CLAUDE.md` reviewed. Test `T-V180-AGT-01` | green; the four exemptions verbatim; the project-prompt record written for all three files; **no count-bearing line touched** (AGT-03) |
| **T2** | §4 part 1: `delete_message` (`-> bool`), `finish(ok=)`, `STATUS_FAILED`, `STATUS_DONE` removed, `AgentOutcome` + `run_agent_outcome` + `finish`'s `failed`/`kind`, `_send -> bool`, the reordered call site. Tests `T-V180-CHAT-01…-05`, `-08`, `-09`; amends `bot.py:1085-1103`, `:1211`, `tests/test_v12_patch.py:145` | green; `run_agent`'s signature and its ~25 test call sites untouched; `--selftest` green with the amended assertion; no other test amended |
| **T3** | §4 part 2: `_TypingIndicator`, `TYPING_INTERVAL_S`, the ceiling, start/stop around `run_agent`. Tests `T-V180-CHAT-06`, `-07` | green with a fake clock and event; no real sleep in the suite; `--selftest` still binds no port |
| **T4** | §5: `STYLE` rewritten to §5.1, the `num` coverage pass, the reading strip, the restyled sections, the nav entry, the SVG palette. Tests `T-V180-DSH-01…-04` | green — each **red before** the change, recorded so; `T-V160-DSH-02`'s byte identity holds |
| **T5** | §6 storage and render: the **four** read functions (`conversation_row` included), the by-turn window, `conversation_list_section`, `conversation_transcript_section`. Tests `T-V180-CONV-01…-03` | green; migration tests green from v1…v5; `SCHEMA_VERSION` still 5; `git diff` shows no DDL |
| **T6** | §6 server + §7: four routes, two regexes, `_parse_offset`, `_STATIC_ROUTES`, redact-then-escape, the two bounds; then the six `v180-*` entries, the `mutation-v180` gate with both re-measured timeouts, and §9's matrix test repointed at the delta file (EC-12). Tests `T-V180-CONV-04`, `-05`, `T-V180-SEC-01…-04` | green; `--select v180-` green with every `find` matching once; `mutation-all` green inside its new timeout; the repointed matrix test green |
| **T7** | Docs and config, **no version bump**: `README.md` (Dashboard), `AGENTS.md`'s count-bearing lines written **once, here** (AGT-03), `docs/plan.md`, `report_path` (RPT-01) | `lint-docs` green on the T0 skeleton; the mutation count reads 98; docs match reality |
| **T8** | **Review (REQ-V180-REV-01) in a clean context, then every gate**: the six verbatim, `checks.py run --profile full --since <base>`. **Every source, test and config *fix* lands here or earlier** — the single exception is T9's release stamp (VER-01), which is not a fix and is re-gated at T10 | findings closed or waived; every gate green; the count exceeds T0's floor; the tree is functionally final |
| **T9** | **The version bump** (VER-01): `pyproject.toml` → `1.8.0`, `README.md`'s Versioning section and `AGENTS.md`'s echo, test `T-V180-VER-01` in `tests/test_v180_version.py`; then **provisional** `report-v1.8.0.md` (RPT-02 minus item 5's tip SHA), `tg-post-v1.8.0.md` (RU, `wc -m` quoted), `docs/llm-usage.md` rows | `T-V180-VER-01` red before the bump, green after; `lint-docs` green against the repointed `report_path`; no self-referential SHA claimed |
| **T10** | **Final acceptance (REQ-V180-REV-02)**: the six gates, `full --since <base>`, `replay --range <base>..<implementation-tip>`, Appendix B; the evidence-only commit; **then `lint-docs` re-run against it** and the annotated tag `v1.8.0` created on **that** commit, only on green | every gate green on the tree that ships; the post-commit `lint-docs` exit code and the tagged sha recorded, or the tag's absence recorded with the verdict withholding it |

### 12.1 Per-task reading map

Navigation aid **and** the authority for REQ-V180-EC-07's thresholds. Reading
more is never a defect; reading less never releases a requirement. §1
(EC-01…08), §2 (NG-*) and §11 bind every task and are not repeated per row. A
`no` cell carries one of the four exemptions **verbatim**.

| T | spec sections | repository files and ranges | delegate? |
|---|---|---|---|
| **T0** | §9, §10 | `AGENTS.md:92-121`, `config/quality_gates.yaml:330-340` | no — *commands only* |
| **T1** | §3 | `AGENTS.md` (whole), `skills/host-info.md`, `skills/weather.md`, `CLAUDE.md`, `templates` block quoted in §3 | no — *artefacts only* |
| **T2** | §4 (CHAT-01…-04, -06, -07, -08) | `bot.py:45-70`, `:100-115`, `:142-180`, `:241-295`, `:685-710`, `:960-975`, `:1085-1115`, `:1200-1215`; `agent.py:1-20`, `:66-86`, `:226-300`, `:320-330`, `:390-420`, `:440-450`; `tests/test_v12_patch.py:140-150` | **yes** |
| **T3** | §4 (CHAT-05, -06) | `bot.py:45-70`, `:100-180`, `:685-710`; `config.py:90-100`, `:296-330` | **yes** |
| **T4** | §5 (DSH-01…-06), §5.1 | `dashboard_render.py:88-150`, `:340-470`, `:600-700`; the task-brief file carrying §5.1 | **yes** |
| **T5** | §6 (CONV-01…-05), §7 (SEC-02) | `storage.py:140-175`, `:270-290`, `:695-730`; `dashboard_render.py:45-90`, `:440-470` | **yes** |
| **T6** | §6 (CONV-06, -07), §7, §9 (EC-10, -12) | `dashboard_server.py:30-60`, `:85-100`, `:160-195`, `:400-430`, `:470-495`, `:570-600`, `:655-700`; `config.py:155-175`; `devtools/mutation_check.py` **tail only** (`MUTATIONS` entries and `main()`); `config/quality_gates.yaml:200-260`, `:330-340`; `tests/test_v15_standards.py:1685-1741`; `docs/spec/spec-v1.8.0-delta-1.md` (created here) | **yes** |
| **T7** | §3 (AGT-03), §10 (RPT-01) | `README.md:204-228`, `AGENTS.md:102-121`, `docs/plan.md`, `config/quality_gates.yaml:330-340` | no — *artefacts only* |
| **T8** | §9, §11 (REV-01) | the review's own reading map; otherwise only commands run | no — *the task is itself the clean-context review* |
| **T9** | §10 (VER-01, RPT-02…04), §11 | `pyproject.toml` (`project.version` only), `README.md:609-642`, `AGENTS.md:102-121`; this run's own artefacts | **yes** — it writes `tests/test_v180_version.py`, which `pytest` runs |
| **T10** | §11, Appendix B | this run's own artefacts | no — *commands only* |

A task whose actual reading exceeds its map crosses REQ-V180-EC-07 item 5 and
delegates from that point on; the report records map versus actual either way
(REQ-V180-RPT-02 item 3).

---

## Appendix A — requirement traceability

Every `MUST` appears exactly once; the **fifty-one** rows below are in
bijection with the fifty-one `MUST` ids defined in §§1–12. NON-GOALs live in §2's table.
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
| `REQ-V180-EC-09` — the six gates verbatim; the count floor (stop route: whatever the tree has); the final re-run; `lint-docs` re-run on the tagged commit | the report's two recorded exit-code sets; the post-commit `lint-docs` code and the tagged sha |
| `REQ-V180-EC-10` — six mutation entries by mechanism; `mutation-v180`; two re-measured timeouts | `mutation_check.py --select v180-`; `--list` recorded; the matrix test |
| `REQ-V180-EC-11` — the implementation order; tests before code within a task | the commit sequence; the report's per-task record |
| `REQ-V180-EC-12` — the gate matrix in `spec-v1.8.0-delta-1.md`; the matrix test repointed, label map extended | `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` green on the delta file |
| `REQ-V180-AGT-01` — Context discipline: write trigger, brief-by-file, four verbatim exemptions | `T-V180-AGT-01`; `E13` |
| `REQ-V180-AGT-02` — the ownership-zone branch rule | `T-V180-AGT-01` |
| `REQ-V180-AGT-03` — the factual lines corrected and nothing else; each written once, counts in T7 | `git diff -- AGENTS.md` reviewed at T8; the report's count record |
| `REQ-V180-AGT-04` — the three project prompts reviewed, not rewritten | the report's project-prompt record naming all three files |
| `REQ-V180-CHAT-01` — `delete_message` through `_call_with_retry` | `T-V180-CHAT-01` |
| `REQ-V180-CHAT-02` — success deletes the message; `STATUS_DONE` removed | `T-V180-CHAT-02`; `--selftest`; `v180-status-delete-skipped`; `E1` |
| `REQ-V180-CHAT-03` — failure edits to `STATUS_FAILED` and keeps it | `T-V180-CHAT-03`; `E2` |
| `REQ-V180-CHAT-04` — the signal is `AgentOutcome`; `run_agent_outcome`; `run_agent` a one-line wrapper | `T-V180-CHAT-04`, `T-V180-CHAT-08`; `v180-status-signal-inverted`; `E2` |
| `REQ-V180-CHAT-05` — typing: 4.0 s, `cfg.llm_timeout_s` ceiling, one unretried attempt per tick, bounded join, injected clock and event | `T-V180-CHAT-06`; `v180-typing-ceiling-removed`; `E4` |
| `REQ-V180-CHAT-06` — best-effort both ways; the selftest records deletions | `T-V180-CHAT-05`, `-07`; `--selftest`; `E3`, `E5` |
| `REQ-V180-CHAT-07` — the outcome contract: every fallback path carries `failed` and its `kind` | `T-V180-CHAT-08` |
| `REQ-V180-CHAT-08` — reply first, then resolve the status; `_send -> bool` | `T-V180-CHAT-09`; `E1`, `E3` |
| `REQ-V180-DSH-01` — the constraints that do not move; system font only | `T-V180-DSH-04`; `E7` |
| `REQ-V180-DSH-02` — §5.1 is frozen; the executor implements, never designs | `T-V180-DSH-03`; the committed T4 task-brief file |
| `REQ-V180-DSH-03` — tabular numerals by **column coverage**; monospace dropped | `T-V180-DSH-01`, recorded red before T4; `E6` |
| `REQ-V180-DSH-04` — the rejected defaults are absent from the **chrome** and asserted | `T-V180-DSH-02`, recorded red before T4; `E7` |
| `REQ-V180-DSH-05` — per-page layout; nav gains conversations; no column moves | `T-V180-DSH-04`; `T-V160-DSH-02` still green; `E8` |
| `REQ-V180-DSH-06` — the four SVG helpers reused, only their colours move | `T-V180-DSH-03`; `git diff` shows unchanged geometry |
| `REQ-V180-CONV-01` — the entity is a conversation; one line of copy says so | `T-V180-CONV-04`; `E8` |
| `REQ-V180-CONV-02` — four read functions incl. `conversation_row`; the by-turn window and its probe | `T-V180-CONV-01`, `-02`, `-03` |
| `REQ-V180-CONV-03` — `/conversations` row shape; `limit` 50, range 1–500 | `T-V180-CONV-04`; `E8` |
| `REQ-V180-CONV-04` — transcript: `turn_id`/`id` order, no split turn, `limit`/turn `offset`, next link from `has_more`, 404 only on a missing row | `T-V180-CONV-05`; `E9` |
| `REQ-V180-CONV-05` — the trace link joins via `(conv_id, turn_id)`, lowest `id` first, `llm_calls` before `tool_calls` | `T-V180-CONV-03`, `-05`; `E9` |
| `REQ-V180-CONV-06` — the JSON mirrors carry the same redacted, capped content, the turn `offset` and `has_more` | `T-V180-CONV-04`, `T-V180-SEC-01`; `E10` |
| `REQ-V180-CONV-07` — routing, 404/400, the `_STATIC_ROUTES` disposition | `T-V180-CONV-04`, `-05`; the dead-code record; `E12` |
| `REQ-V180-SEC-01` — `redact()` on every sink; `esc()` on the HTML sink only | `T-V180-SEC-01`; `v180-transcript-redact-bypassed`; `E10` |
| `REQ-V180-SEC-02` — three bounds: 2000 escaped chars per message (marker additional), `limit` per page, 1.5 MiB of rendered bytes per response | `T-V180-SEC-02`; `v180-transcript-cap-removed`, `v180-transcript-budget-removed`; `E11` |
| `REQ-V180-SEC-03` — REQ-V160-TRC-09 not violated; the sources are distinct | `T-V180-SEC-03`; `E13`'s content-attribute half |
| `REQ-V180-SEC-04` — headers, cap, read-only handle, loopback bind unchanged | `T-V180-SEC-04`; the pre-existing `T-V160-SRV-*` bind assertions; `E12` |
| `REQ-V180-SEC-05` — parameterized SQL; no interpolation of request input | `T-V180-SEC-04`; the T8 review item 4 |
| `REQ-V180-VER-01` — `1.7.0` → `1.8.0` at T9 only, after T8's gates; the tag last, on green | `T-V180-VER-01`; `git tag -l` recorded |
| `REQ-V180-RPT-01` — `lint-docs` repointed at `report-v1.8.0.md` at T7 | `checks.py lint-docs` exit code recorded |
| `REQ-V180-RPT-02` — the report's ten items, delegation record included | `lint-docs`; `/verify-run` item 8 against the record |
| `REQ-V180-RPT-03` — the Russian tg-post under 1500 characters | `wc -m` quoted in the report |
| `REQ-V180-RPT-04` — usage rows; a complete ledger row the operator pastes | `lint-docs`'s ledger-row check; the `docs/llm-usage.md` rows |
| `REQ-V180-REV-01` — clean-context review at T8, eight extra checks | the logged review prompt; the findings-closed record |
| `REQ-V180-REV-02` — offline acceptance, evidence-only commit, `lint-docs` re-run, then the tag on that commit | Appendix B's per-scenario record; `replay --range`; the tagged sha |
| `REQ-V180-REV-03` — regression; no weakened posture; the 4-cycle budget | earlier suites staying green; the repair-cycle count |
| `REQ-V180-REV-04` — the stop route in two stages; what is finalised; no revert, no bump, no tag | the stop-route report section naming its stage, or its recorded non-use |

---

## Appendix B — acceptance scenarios (Gherkin, written before code)

```gherkin
# Every scenario runs OFFLINE against fakes, a fake clock and a tmp_path
# database. No live LLM call, Telegram call or network request of any kind
# (REQ-V180-REV-02). SAFETY: no live credential is used as a test value; no
# scenario reads .env or opens the deployment database.

Scenario: E1 — a successful run leaves no status message behind
  Given a fake Telegram client and a run whose outcome has failed = False
  When the turn finishes
  Then exactly one status message was sent
  And the reply was fully delivered before any deleteMessage was issued
  And exactly one deleteMessage was recorded for that message id
  And no message text "✅ done" was ever sent or edited

Scenario: E2 — a failed run keeps the status message with a failure line
  Given a fake LLM that drives run_agent_outcome down its llm_error path
  When the turn finishes
  Then the outcome carries failed = True and kind = "llm_error"
  And the last edit to the status message is "⚠️ failed"
  And no deleteMessage was recorded
  And the user still received FALLBACK_LLM_ERROR as the reply

Scenario: E3 — a failed delete, and a failed reply send, are both accepted
  Given a fake Telegram client whose delete_message always raises
  When a successful turn finishes
  Then the status message is still present in the chat
  And exactly one warning was logged with every registered secret redacted
  And process_update returned normally with the reply delivered
  And when instead the reply send raises TelegramError on a successful
      outcome, the status message is edited to "⚠️ failed", never deleted

Scenario: E4 — the typing indicator sends once per tick and then stops
  Given a fake clock, a fake stop event and a ceiling_s of 30 seconds
  When a turn runs for 60 seconds of fake time
  Then exactly one sendChatAction was issued per 4.0 s tick — never two for
       one tick, and never through the retry wrapper
  And every send was preceded by a stop-event check and an elapsed check
  And no typing chat action was sent once elapsed reached 30 seconds
  And stop() set the event and joined the worker within 1.0 s
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
  Then every column whose data cells hold numbers or fixed-format timestamps
       carries class "num" on its th and on every one of its td cells
  And no column whose data cells hold words carries it on either
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
  And class "num" is on the th and every td of all of those columns except
      active, whose data cells hold the word yes or no
  And the page uses the word "conversation" and never the word "session"
  And GET /conversations?limit=501 is answered 400

Scenario: E9 — the transcript reads in order, pages by turn, reaches traces
  Given a conversation of three turns where turn 2 has two llm_calls rows
       with non-null trace_id and turn 1 and 3 have none
  When GET /conversations/<id> is served
  Then the messages appear in turn_id then id order with their roles visible
  And turn 2 links to the trace_id of the lowest llm_calls id of that turn
  And turns 1 and 3 render their turn label as plain text, no dangling link
  And when limit is set so a page would end inside turn 2, the page is
      extended to the end of turn 2 and no turn appears on two pages
  And the next link is emitted only when the probe turn existed
  And GET /conversations/<id> for a conversation with no messages is 200
      with the empty state, while an id no row matches is 404

Scenario: E10 — content is redacted, then escaped, on both routes
  Given a registered secret and a message whose content contains it
       followed by "<script>alert(1)</script>"
  When GET /conversations/<id> and GET /api/conversations/<id> are served
  Then neither response body contains the secret
  And the HTML response contains no unescaped "<script>"
  And the JSON response carries the redacted text

Scenario: E11 — a long transcript paginates instead of hitting the cap
  Given a conversation of 500 messages of 8000 characters each, every message
       mixing 4-byte characters with escape-expanding ones
  When GET /conversations/<id>?limit=500 is served
  Then the rendered page is under TRANSCRIPT_PAGE_BUDGET_BYTES, the response
       is under 2 MiB, and it is not the "response too large" body
  And each rendered message is cut to 2000 characters of escaped text, with
      the marker and the original length additional to that 2000

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

### Round 1 of at most 3 — against the whole spec (`58d4553`); 24 findings, 24 accepted (7 adapted), 0 rejected

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R1-1 | Crit | CHAT-04, CHAT-07 | accepted, adapted | the signal is a frozen `AgentOutcome` returned by a new `run_agent_outcome`; `run_agent` stays a `-> str` one-line wrapper, so no test call site moves |
| R1-2 | High | CHAT-04, `T-V180-CHAT-04` | accepted, adapted | the same change removes text matching entirely: `is_failure_reply`, its closed table and `_LLM_ERROR_PREFIX` are gone, so decoration and truncation cannot mis-classify |
| R1-3 | High | CHAT-02, CHAT-04 | accepted | new REQ-V180-CHAT-08 fixes the order — outcome, then reply, then delete only when the send returned `True`; `_send` gains an additive `-> bool` |
| R1-4 | High | CHAT-03, CHAT-06 | accepted | CHAT-03 now promises only the attempt: a rejected edit leaves the previous status text, logs once, and is an accepted outcome |
| R1-5 | Med | CHAT-01 | accepted | `delete_message` is annotated `-> bool` and the client's unwrapped-`result` contract is stated; `_call_with_retry` widens to `-> dict \| bool` |
| R1-6 | High | CHAT-05, CHAT-06 | accepted | the typing worker makes one **unretried** `tg.call` per tick and checks the stop event and the elapsed clock immediately before each attempt |
| R1-7 | High | CHAT-05, `T-V180-CHAT-06` | accepted | `stop()` sets the event **and joins**, bounded by `TYPING_JOIN_TIMEOUT_S = 1.0`; a timeout is logged and the caller proceeds |
| R1-8 | Med | CHAT-05, CHAT-06 | accepted | one attempt per tick makes the ceiling arithmetic true: at most `ceil(llm_timeout_s / TYPING_INTERVAL_S)` requests, no bursts |
| R1-9 | Med | CHAT-05, `T-V180-CHAT-06` | accepted | the seams are named constructor parameters — `interval_s`, `ceiling_s`, `monotonic`, `stop_event` — with their production defaults, so no test sleeps |
| R1-10 | High | SEC-01, CONV-06 | accepted | SEC-01 is stated per sink: `redact()` everywhere, `esc()` on the HTML sink only, because `json.dumps` escapes and HTML-escaping would corrupt the mirror |
| R1-11 | Crit | SEC-02, `T-V180-SEC-02` | accepted, adapted | the bound is enforced, not proved: the page builder accumulates rendered **bytes** against `TRANSCRIPT_PAGE_BUDGET_BYTES = 1.5 MiB`, and the test uses a 4-byte / escape-expanding fixture |
| R1-12 | Med | SEC-02 | accepted | the 2000 governs the escaped message text alone; the marker and the original-length note are additional and counted by the byte budget |
| R1-13 | High | CONV-02, `T-V180-CONV-02` | accepted, adapted | the page is selected **by turn**: a turn window bounded `limit + 1`, turns taken whole, "up to `limit` messages, extended to the end of the last turn" |
| R1-14 | High | CONV-04 | accepted | the window fetches one turn beyond the page; that probe alone decides the next link and is discarded before rendering (`has_more`) |
| R1-15 | Med | CONV-04, CONV-07 | accepted | a fourth reader, `conversation_row`, decides the 404; an existing conversation with no messages answers 200 with the empty state |
| R1-16 | Med | CONV-05 | accepted | the link is the `trace_id` of the lowest `llm_calls` `id` for the turn with a non-null value, then the lowest in `tool_calls`, then none |
| R1-17 | High | DSH-03, CONV-03 | accepted | `class="num"` is a property of the **column**, decided by its data cells and carried on the `<th>` and every `<td>`; the word-valued-`<th>` prohibition is gone |
| R1-18 | Med | DSH-04, `T-V180-DSH-02` | accepted | the anti-pattern scan is scoped to the static chrome through a named sentinel-intersection seam, excluding interpolated message content |
| R1-19 | Med | EC-10 | accepted | `v180-dashboard-bind-widened` is replaced by `v180-transcript-budget-removed`, a mechanism this release introduces; the bind keeps its pre-existing `T-V160-SRV-*` coverage |
| R1-20 | High | AGT-03, T1, T7 | accepted | AGT-03 splits by when the fact becomes true: T1 writes the layout line only, T7 writes every count-bearing line once, after T6 |
| R1-21 | Crit | REV-04, EC-09 | accepted, adapted | the stop route has two stages; from T2 on there is no revert, no test deletion, and the collected count is whatever the tree has |
| R1-22 | Crit | REV-04, VER-01 | accepted, adapted | the version bump moves to T9, the last task before tagging, so a stop at any earlier point needs no revert and VER-01's stop evidence is true by construction |
| R1-23 | High | REV-04 items 5–6 | accepted, adapted | item 5's evidence commit is explicitly permitted on the stop route; the ban on an evidence-only commit is named as the normal route's rule |
| R1-24 | High | REV-02, EC-09, T10 | accepted | `lint-docs` is re-run against the final docs-only commit and the tag goes on **that** commit; the other gates are not re-run, and the spec says why |

**Round 1: 24 findings, 24 accepted (7 adapted), 0 rejected.** New
requirements: `REQ-V180-CHAT-08`; `REQ-V180-CHAT-07` was deleted and its id
reused for the outcome contract, and `T-V180-CHAT-09` is new.

**Two standing lab rulings were overturned in this round**, and are recorded
as such rather than quietly dropped:

- **R3 — "a structured return from `run_agent` is rejected on cost"** — that
  ruling measured only the cost of *changing* `run_agent`'s return type and
  missed the third shape: a new `run_agent_outcome` beside it. Zero test churn,
  so the cost that justified the rejection does not exist (R1-1, R1-2). The
  paragraph arguing for the rejected design is deleted; a spec that argues for
  a design it does not use is a trap.
- **The single-stage stop route** — written for a stop before any commit and
  impossible after one. It demanded the T0 test floor, an unwritten source
  tree, a pre-bump `pyproject.toml` and an evidence commit another item
  forbade (R1-21…R1-23).
