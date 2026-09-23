# Handoff — v1.11.1, ready for `go`

What the `go` session reads first. Authored 2026-09-23 in the lab session;
the run happens in a different session (`standards/workflow.md` §14).

## The `go` line

```text
go docs/spec/spec-v1.11.1.md — LM Studio at http://<addr>:1234
```

**One optional operator input**: the LM Studio box's current address
(probe with `curl -sS -m 3 http://<addr>:1234/v1/models` first; the lab's
known candidates are in the lab memory, not here). With an address in the
`go` text, T0 rewrites `.env`'s `LMSTUDIO_BASE_URL` line with one
non-printing `sed -i` — the sole `.env` exception the spec permits;
without one, `.env` is left as is. Gate 5 on an unreachable box is a
**blocked run**, not a stop route (EC-04).

Everything else in `.env` stays as the v1.11.0 run left it. T0 checks
`bot_state` carries no override row through the one permitted
programmatic read (a single integer printed).

**Start precondition (EC-04, structural — no frozen HEAD sha):**
`git rev-parse v1.11.0^{commit}` = `24310349ee95d703bb3b256443a4b5e1dd22b415`;
`git merge-base --is-ancestor v1.11.0 HEAD` exits 0;
`git describe --tags --abbrev=0` = `v1.11.0`;
`git diff --name-only v1.11.0..HEAD` contains only
`docs/spec/spec-v1.11.1.md`, `docs/handoff-v1.11.1.md`,
`docs/llm-usage.md`, `docs/prompts/255-v1111-spec-authoring.md`;
`git status --porcelain` empty. Anything else is a precondition
mismatch before T0. At handoff HEAD is the commit that adds this file and
ledger row 166 (informational). **No push in this run**; the operator
pushes `main` + tag `v1.11.1` afterwards with `EIO_BACKEND=posix` and the
SSH keepalive (lab memory: the semgrep gate and the long pre-push).

## Models and effort

- **Executor: `claude-sonnet-5`**, orchestrator effort high, subagents
  default. **Reviewer:** the pinned `code-reviewer` (`sonnet`), clean
  context, T5.
- Every source-writing task is `delegate: yes`, briefed by
  `docs/spec/task-briefs/v1111-T<n>.md`; T0's pin inventory is delegated
  and lands in `v1111-T0-pin-inventory.md` (T0's subagent also writes
  `tests/test_v1111_pin.py` after the floor is measured); T4 is two
  prompts — the v1.11.0 report/tg-post corrections (artefacts only,
  `docs/reports/*` only), then the delegated README / `docs/plan.md` /
  AGENTS.md / `tests/test_v1111_doc.py` commit that also carries both
  prompts' bookkeeping.
- Live cost: gates 5 and 7 at T0 and T5; **gate 8 exactly once at T5** on
  the shipping tree (`tested_tree` set only after gates 1–6 and any
  timeout repair; no commit between it and gate 8), reused at T6 by the
  identity check — preliminary before the evidence commit, **definitive
  after it, recorded in the annotated tag message** (six fields:
  `tested_tree`, `evidence_commit`, `identity_verdict=True`,
  `gitleaks_tree_exit=0`, `lint_docs=PASS`, `e7=PASS`), never
  retroactively in the report. Gate 6 once at T5 (152 entries, v1.11.0's
  wall 961.6 s; `timeout_seconds` 1640 untouched unless W > 1300 s).
  `gitleaks-tree` runs standalone after **every** commit (the spec's
  block ends with `exit "$rc"`; `checks.py` has no single-gate form;
  `--profile full` is never typed). Gates 6/7/8 never in parallel.

## What it is

A PATCH collecting every known v1.11.0 leftover — 26 MUST, 17 NG, 7 tasks
(T0–T6), 28 test ids (27 functions + one by command; floor + 27), 16
Gherkin scenarios, 14 ERR-01 rows, 5 `[[VERIFY: …]]` markers, no new
mutation entry (`mutation-all` stays 152):

1. **OUT** — `TelegramError.status`; the plain fallback of
   `send_pre`/`edit_pre` fires on HTTP 400 only; every other error follows
   the plain path (5xx: exactly two requests; transport: `1 +
   SEND_ATTEMPT_LIMIT` attempts, one logical fallback, `None` returned);
   three docstrings corrected (`send_pre`, `tables.fit_lines`,
   `IngestJob`).
2. **TAB** — `/documents` `#` 3 → 5 units, `file` 24 → 22 (sum 72);
   `/model` status widths `[16, 40]`; `SESSIONS_EMPTY_REPLY`;
   `DOC_LIMIT_REPLY` names both delete forms (both admission sites
   tested); one embedding batch constant (`llm.embeddings.BATCH_SIZE`,
   three HTTP requests of `[32, 32, 1]` for 65 inputs).
3. **TST** — dispatch-level tests for v1.11.0 ERR-01 rows 11–16; an
   autouse `tests/conftest.py` fixture restoring `config._secrets` (kills
   the `rt_06` xdist-order flake; proven by a nested pytest run of two
   ordered tests plus two xdist runs).
4. **DOC** — README (`/model` cap row, decimal-MB note, two empty-state
   rows, the v1.6.0-era sentence, the 400-only wording), `docs/plan.md`
   superseded banner, AGENTS.md ruling on RFC1918 LM Studio addresses (no
   historical redaction), and the v1.11.0 report/tg-post corrections the
   lab's `/verify-run` asked for (prompt range 236–254, the prompt-239
   disclosure, the `33729eb` yaml-hunk wording, one stale citation).
5. **PIN / VER** — structural T0 inventory (fewer than 2384 collected
   tests = precondition stop; otherwise the measured count is the floor);
   1.11.1 in T6 only, `tests/test_v1111_ver.py`, `test_v1110_ver.py`'s
   live-tree read repointed, README release row, AGENTS.md counts, tag
   local.

## Frozen decisions the run must not reopen (D1–D18 of the brief)

- **PATCH, no new mechanism, no new mutation id, no push; the benchmark
  rule is not triggered** (AGENTS.md waiver chain gains a v1.11.1
  sentence).
- **400-only fallback; the plain path's retry semantics stay
  byte-unchanged.**
- **No historical address redaction; the AGENTS.md ruling instead.**
  v1.11.1's own paperwork writes `<addr>`.
- **`docs/spec/spec-v1.md` stays frozen; `docs/plan.md` gets only the
  banner; size units stay decimal (documented).**
- **T0 is structural and fail-closed; a pin found later is a disclosed
  amendment.** A stop after the evidence commit gets one stop-record
  commit and no tag.

## State

- Spec: `docs/spec/spec-v1.11.1.md`, 110,779 bytes (the brief's 70 KB cap
  overshot by three rounds). Commits: `8de5485` (draft: 135 unique
  citations opened, 31 corrections, three audit contradictions ruled and
  applied), `a96609b` (round 1), `a4262de` (round 2), `495ac39` (round 3,
  Appendix C closed, status set). Authoring prompt `docs/prompts/255-…`;
  run prompts from **256** (T0–T6, T4 = 260 + 261, +1 per repair prompt);
  `docs/llm-usage.md` from row **167** (166 is the authoring row).
- The brief, the facts file, the critiques and the verdicts live in the
  lab job directory `~/.claude/jobs/45feeee3/tmp/spec-v1111/`
  (ephemeral); Appendix C carries every verdict.

## Cross-review

Three rounds against OpenAI Codex `gpt-5.6-sol`: **23 findings, 23
accepted (5 adapted), 0 rejected**. Termination **`round_limit`** —
round 3 still returned one Critical (the 400→transport expectation
against the unchanged retry path) and five High, all applied.
**Residual findings may exist.** Round themes: the gate-8 identity check
on the tagged tree and the self-referential evidence commit (now the tag
message carries the terminal results); `tested_tree` after the gate-6
timeout branch; the `gitleaks-tree` block's exit status and per-commit
schedule; the `.env` exception; T4's artefact class; the pin-test
ownership; the nested-run proof of the autouse fixture; the HTTP-call
invariant of the batch constant; the start precondition's exact path set.

After the run: push `main` + tag `v1.11.1`; `/verify-run` in a clean
session; the lab ledger (`economics.md`) and `base/INDEX.md`.
