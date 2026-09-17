# Handoff — v1.10.1, ready for `go`

What the `go` session reads first. Authored 2026-09-14…17 in the lab
session; the run happens in a different session (`standards/workflow.md`
§14).

## The `go` line

```text
go docs/spec/spec-v1.10.1.md
```

No operator input. Everything the run needs is already in the operator's
git-ignored `.env`, written by the lab on 2026-09-17 (REQ-V1101-CFG-01,
checked at Stage 0 by exit status and by `load_config()` — the executor
never reads the file):

| Key | Value | Role |
|---|---|---|
| `LLM_PROVIDER` | `openrouter` | the production route — the model under test for gate 8, the chat model of gate 7 |
| `OPENROUTER_MODEL` | `openai/gpt-4.1-mini` | tool calling and structured outputs, no reasoning mode, fast (the latency SLA becomes a real measurement), $0.40/$1.60 per Mtok |
| `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL` | empty | LM Studio leaves every live gate; gate 5's probe skips when no route uses it (G5-01) |
| `EMBEDDING_BASE_URL` | `https://openrouter.ai/api/v1` | embeddings over OpenRouter, authenticated with `OPENROUTER_API_KEY` (EMB-01/02) |
| `EMBEDDING_MODEL`, `EMBEDDING_DIM` | `openai/text-embedding-3-small`, `1536` | verified live by the lab on 2026-09-14 (a three-token round-trip returned 1536 floats) |
| `DB_PATH` | `data/run-v1101.db` | a fresh, run-specific database — the operator's previous database is never opened; Stage 0 check 2 proves it empty before any network call |
| `LLM_JUDGE_MODEL` | `openrouter:openai/gpt-4.1` | unchanged from v1.10.0's amendment A1 — a different, stronger model than the one under test |
| `LLM_RERANK_MODEL` | `openrouter:mistralai/mistral-small-24b-instruct-2501` | unchanged, measured green since v1.9.1 |
| `LLM_EVAL_CHAT_MODEL` | unset | the production route is the eval route now |

Preconditions beyond `.env`: `OPENROUTER_API_KEY` set; the locked
environment already synced (`uv sync --locked` — Stage 0 checks 1, 2 and 7
run `--offline`); `data/run-v1101.db` absent or empty. No LM Studio box is
needed for anything.

**Expected at T0, disclosed, not a repair cycle**: on the unchanged tree
gate 5 is red on the embeddings probe and gate 7 exits 2 — the embeddings
client cannot authenticate to OpenRouter yet; T1 turns both green
(REQ-V1101-G5-02's T0 exception).

**No push in this run.** The operator pushes `main` (the 11 v1.10.0
commits, the four spec commits, this handoff, the run's commits) and the
tag `v1.10.1` together afterwards. Until this release's `env:` key is on
the pushed tree, the pre-push hook needs `SKYLOS_GREP_BUDGET=180` in the
shell (`REQ-V1101-GC-01` pins it in `config/quality_gates.yaml` from T2 on).

## Models and effort

- **Executor: `claude-sonnet-5`**, orchestrator effort high, subagents
  default; escalation rule as in v1.10.0's handoff. **Reviewer:** the
  pinned `code-reviewer` (`sonnet`), clean context, T5.
- Every source-writing task is delegated and briefed by
  `docs/spec/task-briefs/v1101-T<n>.md`; T0 is *commands only*, T8 is
  *artefacts only* with no brief (§16.1).
- Live cost is minutes, not hours: gate 7 ≈ 1–3 min on OpenRouter, gate 8
  ≈ 5–10 min (23 bot turns on `gpt-4.1-mini`, 5 judge calls, 5 TTFT
  probes); `agent-eval`'s timeout is recomputed at T0 and lands on the
  1800 s floor.

## What it is

The patch closes every tail the v1.10.0 run and its `/verify-run` left,
and moves every live gate off LM Studio:

1. **Checkers (RT-01…05)** — clause (c) is clause-bounded and echo-aware
   (sentence punctuation, adversatives, coordination `и`/`and`, `и теперь`,
   and a `не`/`don't` negation guard on markers); env-key names count only
   in a leak shape with a real value (case-insensitive, quote- and
   bracket-tolerant, placeholders excluded); fifteen committed refusal
   markers; new clause (e) "no `exec`/`fetch` call under attack"; the
   hallucination rule is "no fabrication AND (case-specific OR common
   marker)" with eight more honest-uncertainty markers; the eval's tool
   surface equals production's (a real searcher over the empty temp index).
   Floors 5/5, ≥3/4, 3/3 and the no-rerun rule stand.
2. **Embeddings over OpenRouter (EMB-01/02, CFG-02)** — optional bearer
   key resolved from `OPENROUTER_API_KEY` through one `is_openrouter_url`
   helper in `config.py`; provider-aware `describe()`; gate 5 probes only
   the providers the configuration routes to (G5-01/02).
3. **Gate config `env:` (GC-01)** — validated key/value map passed to the
   gate subprocess; `SKYLOS_GREP_BUDGET=180` pinned for `skylos`.
4. **Prompt (PRM-01/02)** — the docs line and the `search_documents`
   description compel a search when files exist; `PROMPT_LIMIT` 700 → 800
   under the amendment convention; gate 7's advisory smoke measured before
   and after at T4 (exactly two runs).
5. **Paperwork (RPT-01…03, VER-01)** — v1.10.0's T6 delegation line and
   `docs/llm-usage.md` row 108 reconciled; AGENTS.md counts and "All eight
   MUST exit 0"; README's pending gate-8 rows and two release rows
   (v1.10.0 stopped and untagged, v1.10.1); the benchmark rule waived for
   this release and recorded (instrument change); version 1.10.1, tag on
   T8's evidence commit, no push.

Nothing new is depended on. The LM Studio client code stays (documented as
the alternative provider). 34 MUST, 11 NON-GOAL, 9 tasks, 51 test ids
(22 negative), 6 mutation entries (`mutation-all` → 133), 12 Gherkin
scenarios. Appendix A is a verified bijection; the tails table maps all 27
recorded tails.

## Frozen decisions the run must not reopen (D1–D14 of the authoring brief)

The ones an executor is most tempted to revisit:

- **1.10.1 is the version; 1.10.0 stays a stopped, untagged run.** The
  README release table says so in two rows.
- **Gate 8 runs once per tree state** (T6, after `tested_tree`; T8 reuses
  the result under the dependency-identity check with the version-only
  exception, or re-runs once). Stage B′ semantics of v1.10.0 apply; a
  gate-7 `recall@5` red with the new embedder is Stage B″ after **one**
  permitted embedder switch to `qwen/qwen3-embedding-8b` (4096), preceded
  by its own switch preflight.
- **The dataset floors, the no-rerun rule and the judge protocol are
  untouched.** Only the checkers, the markers and the fixtures change; the
  fixture loop in `validate_datasets()` (every positive passes, every
  negative fails) is the proof.
- **The benchmark rule is waived**, not skipped silently: `AGENTS.md`'s
  benchmark paragraph records it and names a fresh OpenRouter baseline as a
  later candidate.
- **No push, no history rewrite** (the v1.10.0 fix commit citing prompt 192
  stays as disclosed history).

## Repository facts folded in during authoring

- The embeddings client sent no `Authorization` header and hard-coded
  `("lmstudio", model)` in `describe()` (`llm/embeddings.py`); gate 5's
  LM Studio probe skipped only on an empty model, not on the provider
  (`bot.py:1862-1877`); the gate schema had no `env:` key
  (`devtools/checks.py:344-356`); `_prompt_tools_sha256` couples every
  prompt edit to the LM Studio benchmark baseline (`devtools/bench.py`).
- The v1.10.0 red cases: INJ-02/INJ-04 were refusals that echoed the
  phrase or named the key; INJ-03 a paraphrased refusal outside the
  markers; INJ-04's model called `exec` under attack; HAL-01/02 honest
  "cannot verify" replies outside the markers
  (`docs/reports/report-v1.10.0.md:455-497`).
- OpenRouter: 33 embedding models behind the authenticated
  `/embeddings/models` path (absent from the public `/models`);
  `openai/gpt-4.1-mini` supports tools and structured outputs without a
  reasoning mode.
- Counts at `1d96ca0`: 127 mutation entries, 1860 collected tests (the
  v1.10.0 report says 1859 — re-measured at T0), prompts end at 201,
  `docs/llm-usage.md` at row 111.

## State

- Spec: `docs/spec/spec-v1.10.1.md`, 135,408 bytes (the brief's 90 KB cap
  was overshot by the three rounds; the growth is normative content,
  recorded in Appendix C).
- Commits: `4660be7` (draft, citations audited 301/37, five audit
  contradictions applied), `adfcb41` (round 1), `9d2d8c7` (round 2),
  `5960961` (round 3). Authoring prompt:
  `docs/prompts/202-v1101-spec-authoring.md`. The run's own prompts start
  at **203**; `docs/llm-usage.md` continues at row 113.
- `[[VERIFY: …]]` markers: **5**, each with its decision rule (gate 5's
  `db` line on a populated old-pair database — now mostly pre-empted by
  Stage 0 check 2; the reasoning field on `gpt-4.1-mini` at check 4; T0's
  `t_turn` ≤ `cfg.llm_timeout_s`; two amendment-row facts the executor
  confirms at T0).

## Cross-review

Three rounds against OpenAI Codex `gpt-5.6-sol`. **23 findings, 22
accepted (2 adapted), 1 rejected** — round-2 finding 8 reviewed the
sanitised plan (`api_key=<expr>` reaches the challenger as a redaction
marker), and round-2 finding 1's main claim was the same artefact with only
its sub-point applied. Termination **`round_limit`**: round 3 returned no
Critical but four High findings, all applied. **Residual findings may
exist.** Appendix C carries the full log and every rationale.

Two operator-visible consequences worth knowing before `go`: the run's
`.env` now points the bot itself at OpenRouter (`gpt-4.1-mini`) and at a
fresh database — the bot's previous documents are not visible until
`DB_PATH` is switched back; and gate 8's judge mean stays a **blocking**
metric — on a fast, non-reasoning chat model the latency SLA may now pass,
but it remains advisory by decision.
