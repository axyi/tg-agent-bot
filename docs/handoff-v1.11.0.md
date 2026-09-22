# Handoff — v1.11.0, ready for `go`

What the `go` session reads first. Authored 2026-09-22 in the lab session;
the run happens in a different session (`standards/workflow.md` §14).

## The `go` line

```text
go docs/spec/spec-v1.11.0.md — LM Studio at http://<ip>:1234
```

**One operator input**: the LM Studio box's current address (its IP
roams; the lab's last known candidates are `172.16.50.233`,
`192.168.0.145`, `192.168.178.170`, port 1234 — probe with
`curl -sS -m 3 http://<ip>:1234/v1/models` before issuing `go`). When the
`go` text carries an address, T0 writes it into `.env`'s
`LMSTUDIO_BASE_URL` line with one `sed -i` (the file is never printed);
when it carries none, `.env` is left as is. Gate 5 (`selftest-live`) on an
unreachable box is a **blocked run**, not a stop route — fix the address
and re-issue `go` (spec §1, EC-05).

Everything else in `.env` stays as the v1.10.4 run left it: OpenRouter
embeddings and rerank, `OPENROUTER_MODEL=openai/gpt-4.1` as the model
under test, `LLM_JUDGE_MODEL=openrouter:anthropic/claude-sonnet-5`,
`DB_PATH` unchanged (T0 checks that `bot_state` carries no
`provider_override` / `model_override:*` row through the one permitted
programmatic read — a single integer printed, spec MOD-05). The new
variables `LMSTUDIO_MODELS` / `OPENROUTER_MODELS` are **optional** and
default to the single configured model each; the run does not need them.

Preconditions: tree at `8695b52` or later on `main` with `git describe
--tags` starting `v1.10.4`; `git status --porcelain` empty except the
untracked `.README.md.swp`; `.env` present (exit status only); Docker
reachable; `OPENROUTER_API_KEY` set. **No push in this run**: the operator
pushes `main` and the tag `v1.11.0` afterwards (pre-push runs
`mutation-all`, ~15–20 min at 152 entries; use the SSH keepalive from the
lab memory and write the push output to a file).

## Models and effort

- **Executor: `claude-sonnet-5`**, orchestrator effort high, subagents
  default. **Reviewer:** the pinned `code-reviewer` (`sonnet`), clean
  context, T7.
- Every task T1–T8 that writes source is `delegate: yes` in the spec's
  §14.1 reading map; the orchestrator writes
  `docs/spec/task-briefs/v1110-T<n>.md` and passes the path. T0 is
  delegated for the pin inventory (it writes the separate
  `v1110-T0-pin-inventory.md`) and *commands only* for the measurements.
- Live cost: gates 5 and 7 at T0 and T7; **gate 8 exactly once, at T7**
  on the shipping tree, reused at T8 by the version-only identity check
  (a `False` verdict at T8 is a repair that reverts the hunk — never a
  rerun); gate 6 once at T7 (152 entries; the 1640 s gate timeout is
  recalibrated the v1.10.4 way if the measured wall exceeds 1300 s).
  Gates 6, 7 and 8 never run in parallel.

## What it is

The Telegram surface release the operator asked for on 2026-09-22, plus
one lab-proposed group:

1. **The outbound table path (OUT)** — one new helper pair `send_pre` /
   `edit_pre` over a shared `_pre_text` (redact → fit to 4096 UTF-16
   units → `html.escape` → exactly one `<pre>` block, `parse_mode=HTML`),
   a one-time plain fallback of the *same fitted body* on a 400; the
   agent-reply path stays byte-identical `{chat_id, text}`. The v1.10.0
   pin "no `parse_mode`, ever" (OUT-02, NG-03) is retired by id and
   narrowed to that path. `tables.render_table` — monospace columns, every
   line ≤ 72 UTF-16 units, UTF-16-safe truncation with `…`.
2. **`/stats` (STA)** — the same ten facts as a three-column table plus
   four wrapped single-value rows; `STATS_MAX_CHARS = 3500` and the
   whole-line `_fit` kept. There was no unmerged `/stats` spec — the
   README sample was two lines stale, fixed in passing.
3. **`/documents` (DOC)** — a seven-column table with the id and the size
   (the README promised size since v1.9.0 and never showed it);
   `/delete #<id>`; the DOCX/PDF refusal wording split into two honest
   strings; an in-flight `⏳ indexing …` line when the caller has a job
   running.
4. **Sessions (SES)** — `/sessions` (ten most recent, derived title from
   the first user message, active marker) and `/session <id>` over the
   existing `conversations` rows; `activate_conversation` follows the
   `BEGIN IMMEDIATE` clear-then-set recipe under the partial unique index;
   ownership enforced in the query; `/new` now prints the id. **No schema
   migration** — `SCHEMA_VERSION` stays 6.
5. **Callback queries (CBQ)** — `allowed_updates` gains `callback_query`;
   the same guard order as messages (private chat, human, allowlist,
   chat-id match, rate limit); every callback answered exactly once;
   `callback_data` ≤ 64 bytes with a namespaced grammar; the update cursor
   is the only `bot_state` write allowed before authorization.
6. **`/model` menu (MOD)** — provider buttons, then model buttons from
   env allowlists (`LMSTUDIO_MODELS`, `OPENROUTER_MODELS`, ≤ 20 entries,
   default model always present), a JSON-framed catalogue hash in
   `callback_data` against stale menus, one `model_display` helper on
   every surface; the text form `/model <provider> [<model>]` kept;
   overrides are global `bot_state` keys, cleared by `auto`.
7. **Large documents (ING)** — cap 20,000,000 bytes (the Bot API `getFile`
   ceiling), 2,000,000 extracted chars, 2,000 PDF pages, 1800 s budget;
   ingest on one daemon `IngestWorker` with a thread-owned SQLite
   connection (WAL), two-phase `reserve` / `enqueue` / `release`
   admission (four jobs, one per user), a job phase
   `queued/running/committing`, cooperative `/cancel` with checkpoints
   around `getFile`, the streamed download, extraction and every embedding
   batch, a shutdown sentinel that drains queued jobs with
   `❌ Interrupted by restart.`. Bytes stay in memory (the v1.9.0
   no-file-writes pin holds).
8. **EXT (lab-proposed, strikable as a group)** — `setMyCommands` at
   startup from one `COMMANDS` tuple, `/help` as a table, `/start` alias.

Counts: 44 MUST, 14 NON-GOAL rows, 9 tasks (T0–T8), 62 test ids (24
negative) across `tests/test_v1110_<group>.py`, 8 `v1110-*` mutation
entries (`mutation-all` 152), 14 Gherkin scenarios, 18 ERR-01 rows, five
`[[VERIFY: …]]` markers each with its decision rule (collected count
floor + 62; `EmbeddingsClient` thread-safety; the `mutation-all` wall;
`GATE8_DEPENDENCIES` without `tests/`; one inside the round-1 log row).

## Frozen decisions the run must not reopen (D1–D22 of the brief)

- **1.11.0 is MINOR; tag local; no push; no schema migration; no new
  third-party dependency.**
- **HTML only on the table path; MarkdownV2 never; the agent-reply path
  untouched.** Keyboards only for `/model` and `/sessions`; inline mode,
  media, streaming stay out.
- **Catalogue from env allowlists, never a live `/v1/models` call;
  overrides global, never per user.** Sessions: no rename, delete or
  pagination.
- **Files above the Bot API ceiling and a local Bot API server are out of
  scope.** Retrieval-side scaling (per-query BM25 rebuild) is noted, not
  touched.
- **Gate 8 exactly once; the benchmark rule is not triggered** (no
  prompt, tool schema, tool output, history assembly or routing-default
  change) — the waiver chain in `AGENTS.md` gains a v1.11.0 sentence.
- **T0's pin inventory is structural and fail-closed; a pin found later
  is a disclosed amendment, not a repair cycle and not a stop.**

## State

- Spec: `docs/spec/spec-v1.11.0.md`, 174,228 bytes (the brief's 110 KB
  cap was overshot by three rounds — each added 20–26 KB). Commits:
  `d56ae70` (draft: 291 citations opened, 25 line-drift corrections,
  three audit contradictions ruled and applied), `c9ad0e6` (round 1),
  `f55bfc7` (round 2), `8695b52` (round 3, Appendix C closed, header
  fact corrected). Authoring prompt `docs/prompts/235-…`; run prompts
  from **236** (T0–T8 = 236–244 if no repair prompt intervenes);
  `docs/llm-usage.md` from row 147 (146 is the authoring row).
- The brief, the four facts files, the critiques and the verdicts live
  in the lab job directory `~/.claude/jobs/45feeee3/tmp/spec-v1110/`
  (ephemeral); the spec's Appendix C carries every verdict.

## Cross-review

Three rounds against OpenAI Codex `gpt-5.6-sol`: **27 findings, 27
accepted (5 adapted), 0 rejected**, plus 3 lab items found by the
round-1 applier. Termination **`round_limit`** — round 3 still returned
six High (all applied). **Residual findings may exist.** Round themes:
the edit path bypassing the HTML helper; the SQLite connection created
on the wrong thread; gate-8 rerun contradictions; infeasible column
widths; cancel checkpoints missing before download; unbounded model
menus and stale indices; the test-count floor not proving the named
tests landed; an invalid one-site mutation; the reservation/status-send
race; the shutdown sentinel; control characters in model ids.

Operator-visible consequences before `go`: none beyond the LM Studio
address. After the run: push `main` + tag `v1.11.0`; then `/verify-run`
in a clean session; then the lab ledger (`economics.md`), `base/INDEX.md`.
