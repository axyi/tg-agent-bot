# Handoff — v1.10.2, ready for `go`

What the `go` session reads first. Authored 2026-09-17 in the lab session;
the run happens in a different session (`standards/workflow.md` §14).

## The `go` line

```text
go docs/spec/spec-v1.10.2.md
```

No operator input. Everything the run needs is in the operator's
git-ignored `.env`, unchanged from the v1.10.1 run except one key the lab
rewrote on 2026-09-17 (checked at Stage 0 by exit status and by
`load_config()` — the executor never reads the file):

| Key | Value | Role |
|---|---|---|
| `LLM_PROVIDER` / `OPENROUTER_MODEL` | `openrouter` / `openai/gpt-4.1-mini` | the model under test, unchanged — no model switch this release whatever gate 8 returns (D2) |
| `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL` | empty | no LM Studio anywhere |
| `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` | OpenRouter, `openai/text-embedding-3-small`, `1536` | unchanged; **no embedder switch exists in this release** (Stage B″ stops the run) |
| `DB_PATH` | `data/run-v1102.db` | **rewritten by the lab** — a fresh, run-specific database; absent at handoff; Stage 0's storage preflight proves it empty (`db_empty=True`) before any network call |
| `LLM_JUDGE_MODEL` | `openrouter:openai/gpt-4.1` | unchanged |
| `LLM_RERANK_MODEL` | `openrouter:mistralai/mistral-small-24b-instruct-2501` | unchanged |

Preconditions beyond `.env`: `OPENROUTER_API_KEY` set; the locked
environment synced (`uv sync --locked`); Docker reachable for gate 5's
sandbox probe. **Expected at T0**: gates 1–5 and 7 green on the unchanged
tree (v1.10.1's T1 already landed the embeddings auth); gate 8 is not run
at T0. Gate 7 may exit 2 on a live rerank failure — the spec's GATE-01
predicate says exactly when a re-invocation is allowed (up to two, never
counted as a repair cycle) and when it is not.

**No push in this run.** The operator pushes `main` (now 40 commits ahead:
v1.10.0 run, spec-v1.10.1 + its run, spec-v1.10.2, this run) and the tag
`v1.10.2` together afterwards. The pre-push hook reads the working tree's
`config/quality_gates.yaml`, which already carries `SKYLOS_GREP_BUDGET=180`
for `skylos` — **no shell variable is needed any more** (v1.10.1's handoff
note is obsolete; the spec's push instruction omits it).

## Models and effort

- **Executor: `claude-sonnet-5`**, orchestrator effort high, subagents
  default. **Reviewer:** the pinned `code-reviewer` (`sonnet`), clean
  context, T4.
- Source-writing tasks T1, T2, T3, T5, T6 are delegated and briefed by
  `docs/spec/task-briefs/v1102-T<n>.md` (T4 gets a brief only iff it
  delegates a fix); T0 is *commands only*; T5's live gate sequence is
  *commands only*; T7 is *artefacts only* with no brief.
- Live cost is minutes: two gate-7 runs at T1 (PRM-02 before/after), gate 7
  + gate 8 once at T5 (gate 8 ≈ 1 min on `gpt-4.1-mini`), gate 5/7 at T7.
  Gate 6 runs **once, directly**, at T5 (v1.10.1's direct wall was 99m55.8s
  under load — the spec re-measures the `mutation-all` timeout there), plus
  one `--select v1102-` calibration run for `mutation-v1102`'s timeout.

## What it is

1. **The prompt line (PRM-01/02)** — one `Secrets:` line in
   `SYSTEM_PROMPT`, byte-exact in the spec, inserted between `Rules:` and
   `Docs:`; `PROMPT_LIMIT` 800 → 950 (governs the template with
   `{skill_lines}` removed); the rendered length is measured at T1
   (expected 939, VERIFY marker with its rule) and pinned; gate 7's advisory
   smoke measured before and after (exactly two runs).
2. **The gate-8 verdict (RT-01…03)** — `check_injection` reports every
   violated clause joined by `; ` (message texts unchanged); a `CASE` line
   per checked step of every category and a `TOOLS` line per injection step
   (the step's own calls, name + JSON-encoded sanitised first argument,
   `_safe_field`: redact → Unicode Cc/Cf/Zl/Zp and whitespace → space →
   collapse → truncate 80; line cap 2300 derived from
   `TOOL_EXECUTION_LIMIT = 12`); previews use the same helper (200). The
   gate-8 run at T5 is the exact five-line capture command in RT-03; the
   report's twelve-case table is built from that capture; a missing capture
   blocks the run (no re-run).
3. **Markers (RT-04…06)** — a sixteenth INJ marker and a widened HAL
   marker with bounded gaps (`(?:(?!не(?:\W|$))[^\s.?!;…]+\s){0,n}`),
   INJ-05's and HAL-03's `any_of` widened; ≥ 2/≥ 2 fixtures per marker,
   every one of the twelve `negative_reply` strings asserted still red;
   floors and the no-rerun rule untouched.
4. **Gate rules (GATE-01…03)** — the gate-7 transient re-invocation
   predicate (exact output shape from `rag_eval.py`, exact exclusion list,
   two worked captures); gate 6 once, directly, on a recorded `git
   write-tree`, timeout re-measured; six `v1102-*` mutations (139 total);
   `mutation-v1102` in `mutation-subsets`; the stop procedure reuses gate
   8's single T5 capture and never re-runs it.
5. **Paperwork (RPT-01…03, VER-01)** — at T3: README's two stopped-run
   rows, `## Configure`/`## Switch provider`, `AGENTS.md` "All eight" and
   the gate-5 sentence, the benchmark waiver naming v1.10.1 and v1.10.2,
   `.env.example` routing defaults, the v1.10.0 T6 delegation-line and
   llm-usage row-108 correction; at T6: version 1.10.2, the v1.10.2 release
   row, the five `pending (T9)` rows filled from T5's gate 8; at T7:
   report, tg-post, ledger row, local tag. The delegation record is the
   bullet shape (`task | delegated? | to what | brief path | map vs actual`).

26 MUST, 12 NON-GOAL, 8 tasks (T0–T7), 35 test ids (9 negative), 6
mutation entries, 11 Gherkin, EC-02 list of 15 rows plus a T0 grep
inventory (plain and escaped forms, five symbol references) whose hits
outside the list become the T0 amendment table before any live call.

## Frozen decisions the run must not reopen (D1–D14 of the authoring brief)

- **1.10.2 is the version; 1.10.0 and 1.10.1 stay stopped, untagged runs.**
- **Same instruments, same floors, same stop route.** A red gate 8 is
  Stage B′ again — finalised with the full per-case evidence; a red
  `recall@5` is Stage B″ and stops (no embedder switch in this release).
- **One prompt line, no tool-level guard, no `agent.py` signature change,
  no JSON artefact, no push.**
- **No checker, marker, case or prompt edit during a red gate 8** (v1.10.1
  RT-05/NG-04 stand); the marker work lands at T2, before any live run.

## Repository facts folded in during authoring

- `SYSTEM_PROMPT` at `agent.py:133-150`, rendered template 736 chars at
  `ccab5d7`, exact pin `tests/test_v1101_prompt.py:41-42`, limit
  `tests/test_prefix.py:31`; the eval's `exec` is a stub
  (`devtools/agent_eval.py:1072-1079`) — the production sandbox facts in
  `report-v1.10.1.md:679-684` describe production only.
- `check_injection` reported only the first violated clause
  (`devtools/agent_eval.py:313-340`); `_record_tool` kept the name only
  (`:1386-1387`); FAIL lines are stdout-only and `checks.py run` swallows
  gate stdout — hence the direct capture command.
- `tests/test_v1101_gates.py:343-356` parses the `mutation-all` count
  comment with the anchor `spec-v1.10.1 T6a` — re-anchored under EC-02.
- The pre-push hook reads the working-tree yaml (`devtools/checks.py:26`,
  `:1684`), so GC-01's `env:` pin already applies locally.
- Counts at `ccab5d7`: 2035 collected tests (2034 passed + 1 skipped),
  133 mutations, prompts end at 211 (this authoring prompt), llm-usage at
  row 123.

## State

- Spec: `docs/spec/spec-v1.10.2.md`, 144,113 bytes (the brief's 90 KB cap
  was overshot by the three rounds; the growth is normative content).
- Commits: `79f557d` (draft, citations audited ~340/19, three audit
  contradictions applied), `1a805bc` (round 1), `b651e7e` (round 2),
  `0d0a46b` (round 3), `d651b0d` (T0 inventory follow-up). Authoring prompt:
  `docs/prompts/211-v1102-spec-authoring.md`. The run's own prompts start
  at **212**; `docs/llm-usage.md` continues at row 124.
- `[[VERIFY: …]]` markers: **2**, each with its decision rule (the rendered
  prompt length 939; the `mutation-all` timeout re-measurement at T5).

## Cross-review

Three rounds against OpenAI Codex `gpt-5.6-sol`. **26 findings, 26
accepted (10 adapted), 0 rejected outright** — three sub-points rejected
inside adapted findings with rationale in Appendix C (a prompt-contract
fixture; a new `exit_cause=` output line in `rag_eval.py`; a gate-7 capture
parser). Termination **`round_limit`**: round 3 still returned two
Critical findings (Stage B″ importing v1.10.1's embedder switch; a
non-executable capture command), both applied. **Residual findings may
exist**; the known one is that a bare U+2028 with no sentence terminator
still acts as a token separator inside a marker's bounded gap.

Operator-visible consequence before `go`: the bot's `.env` now points at
`data/run-v1102.db` — the bot's documents are not visible until `DB_PATH`
is switched back after the run.
