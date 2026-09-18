# Handoff — v1.10.3, ready for `go`

What the `go` session reads first. Authored 2026-09-18 in the lab session;
the run happens in a different session (`standards/workflow.md` §14).

## The `go` line

```text
go docs/spec/spec-v1.10.3.md
```

No operator input. The run's `.env` was rewritten by the lab on
2026-09-18 (three keys; checked at Stage 0 through `load_config()` — the
executor never reads the file):

| Key | Value | Role |
|---|---|---|
| `OPENROUTER_MODEL` | `openai/gpt-4.1` | **the model under test, on the production route** — the operator's decision (a); tools, structured outputs, no reasoning mode; $2/$8 per Mtok (≈5× mini — the bot's own traffic moves with it; README `## Switch provider` says how to revert) |
| `LLM_JUDGE_MODEL` | `openrouter:anthropic/claude-sonnet-5` | the judge, another vendor; strict JSON schema verified live by the lab; the Stage-0 probe (check 6) has **one** fallback to `openrouter:openai/gpt-5.6-sol`, recorded in `## Operator inputs` — README/tg-post then name the *effective* judge |
| `DB_PATH` | `data/run-v1103.db` | fresh, absent at handoff; Stage 0 proves `db_empty=True` before any network call |
| `LLM_PROVIDER`, `EMBEDDING_*`, `LLM_RERANK_MODEL`, `LMSTUDIO_*` | unchanged from v1.10.2 | OpenRouter embeddings `text-embedding-3-small` 1536, rerank `mistral-small-24b-instruct-2501`, LM Studio empty |

Preconditions beyond `.env`: `OPENROUTER_API_KEY` set; the locked
environment synced; Docker reachable for gate 5's sandbox probe.
**Expected at T0 with the new `.env`**: gates 1–5 and 7 green on the
unchanged tree; gate 8 not run at T0; any red is a Stage 0 blocker.

**No push in this run.** The operator pushes `main` (now 60 commits ahead,
after this run more) and the tag `v1.10.3` together afterwards; the
pre-push hook reads the working-tree yaml, no shell variable needed.

## Models and effort

- **Executor: `claude-sonnet-5`**, orchestrator effort high, subagents
  default. **Reviewer:** the pinned `code-reviewer` (`sonnet`), clean
  context, T5.
- Briefs `docs/spec/task-briefs/v1103-T<n>.md` for T1–T4, T6 and T7
  (version commit); T5 only iff it delegates a fix; T0 *commands only*;
  T6's live gate sequence *commands only*; T7's evidence commit *artefacts
  only*.
- Live cost is minutes: gate 5/7 at T0, T6, T7; gate 8 **exactly once**,
  at T6 (≈1 min on `gpt-4.1`; 5 judge calls on `claude-sonnet-5`); gate 6
  once, directly, on a recorded `git write-tree` (v1.10.2's wall: 14m23.5s
  for 139 mutations) plus one `--select v1103-` calibration run.

## What it is

1. **The instrument (INS-01)** — `gpt-4.1` under test, `claude-sonnet-5`
   judge, one fallback; `judge_route_is_distinct(cfg)` helper + identity
   assertion before every probe; a green injection 5/5 is worded "on this
   run" — the lab's probe showed `gpt-4.1-mini` *not* calling a tool on
   INJ-04 either, so v1.10.2's `printenv` ×3 was non-deterministic.
2. **The `exec` guard (EXEC-01/02)** — in `_validate_exec_arguments`, before
   any runner: basename(argv[0]) ∈ {`env`, `printenv`}; any element whose
   basename is `.env` or starts with `.env.`; any element matching
   `^/proc/(?:self|\d+)/environ$`; refusal `exec refused: environment
   inspection is not available`; the existing refused audit record (argv
   redacted through `_audit`). **Narrow defense in depth** — bypassable via
   interpreters, multicall binaries, symlinks, path spellings (tests
   document these as *not* refused); the sandbox env is the boundary;
   clause (e) still fails the attempt.
3. **Markers (RT-01…03)** — an 18th HAL marker for the noun-before-«нет»
   order (gap ≤ 120 clause chars, no adversative); INJ-04's `any_of` with
   the dative form and «недоступ»; four adversarial marker+fabrication
   fixtures with four deterministic `none_of` widenings (HAL-01…04),
   written in the spec; twelve negatives asserted still red.
4. **Delegation lint (LINT-01)** — `lint-docs` gains `delegation_record:
   true`: every non-exempt `## T<n>` section needs a bullet
   `- T<n> | delegated: yes|no | to: … | brief: docs/spec/task-briefs/<vXYZ>-T<n>.md or — | map vs actual: …`
   (prefix derived from `report_path`); exemptions verbatim on `no`.
5. **Gates (GATE-01…03)** — gate 8 once per run; a false T7 identity check
   is an acceptance defect (repair, gates 1–7, no second gate 8); gate 7 red
   at T6 = Stage B″ (stop, no bump), at T7 = Stage B at T7 (bump retained,
   untagged); every gate-7 execution gets an attempt-log row; syntax-
   preserving mutations verified killed in isolation.
6. **Paperwork (RPT/VER)** — T4: README v1.10.2 stopped row, judge
   paragraph, `.env.example` defaults, waiver naming v1.10.3, brief token,
   `lint-docs` repoint; T7 (first commit): version 1.10.3, release row
   ("shipped judge default …; gate 8 judged by <effective judge>"),
   `pending (T9)` rows, AGENTS.md counts; T7 (evidence commit, exactly
   four paths): report, tg-post, ledger row, then E11 post-commit/pre-tag,
   then the tag.

25 MUST, 14 NON-GOAL, 8 tasks (T0–T7), 37 test ids (15 negative), 5
mutations (→ 144), 11 Gherkin, EC-02 19 rows + the T0 inventory (table +
T0 amendment table = the exhaustive set; a later unlisted pin = a repair
cycle, never a stop).

## Frozen decisions the run must not reopen (D1–D14)

- **1.10.3 is the version; 1.10.0–1.10.2 stay stopped, untagged runs.**
- **The instrument is decided** — no other model, no `LLM_EVAL_CHAT_MODEL`;
  floors, no-rerun rule, temperature 0 and the stop route stand.
- **The guard's three rules are decided** — not a shell parser, not a
  general blocklist, no `fetch` guard; the tool description is unchanged
  (catalog 1798 of 1800).
- **No marker, case or prompt edit during a red gate 8.**

## State

- Spec: `docs/spec/spec-v1.10.3.md`, 135,847 bytes (the 90 KB cap was
  overshot by the rounds; normative growth). Commits: `f3293c3` (draft,
  297 citations / 26 corrected, two regex fixtures fixed by the lab, five
  audit contradictions applied), `fa73481` (round 1), `60e8a5f` (round 2),
  `737afb3` (round 3). Authoring prompt `docs/prompts/219-…`; run prompts
  from **220**; `docs/llm-usage.md` from row 131.
- `[[VERIFY: …]]` markers: **3** — the `gpt-5.6-sol` retry with
  `reasoning: {enabled: false}` (a 4xx naming `reasoning` = blocked run);
  the HAL-02 fixture is the persisted 200-char preview (byte-equal); the
  `mutation-all` timeout (recompute only if T6's wall > 1640 s).

## Cross-review

Three rounds against OpenAI Codex `gpt-5.6-sol`: **20 findings, 20
accepted (6 adapted), 0 rejected outright**; two sub-points rejected with
rationale (retry-logic tests for a heredoc probe; a stop route on a missed
test pin). Termination **`round_limit`** — round 3 still returned one
Critical (E11's circular verification) and three High. **Residual
findings may exist.**

Operator-visible consequences before `go`: the bot now runs on
`openai/gpt-4.1` in production; `DB_PATH` points at `data/run-v1103.db`
(documents invisible until switched back); the judge is an Anthropic
model — five short calls per gate-8 run.
