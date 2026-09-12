# Handoff — v1.9.0, ready for `go`

What the `go` session reads first. Authored 2026-09-10 in the lab session;
the run happens in a different session (`standards/workflow.md` §14).

## The `go` line

```text
go docs/spec/spec-v1.9.0.md
Operator inputs: EMBEDDING_MODEL=<model id as listed by GET /v1/models>, EMBEDDING_DIM=<integer>
```

Two operator inputs travel **as text in the request** (REQ-V190-EC-04): the
embedding model id exactly as LM Studio's `GET /v1/models` lists it, and the
vector dimension it produces. They are not secrets; the executor quotes
them in `docs/reports/report-v1.9.0.md` `## Operator inputs`. The operator
must have the model loaded on the GPU box before `go`, and `LMSTUDIO_BASE_URL`
in `.env` must point at the box's **current** address (the floating-IP
problem of v1.6.0–v1.8.0: probe the three known addresses first, memory
`reference-lmstudio-endpoints`). Nothing else is needed in the request.

Live work this release needs (everything else is offline against fakes):
gate 5 (`--selftest-live`, now with an embeddings check), gate 7 (`rag-eval`,
the retrieval evaluation with the live reranker), T0's preflight (sqlite-vec
loads, the model is listed, one embeddings call returns `EMBEDDING_DIM`
floats), and the two benchmark runs of REQ-V190-EC-06 (the project's own
benchmark rule fires because the tool schema and the system prompt change;
the runs are reported, not gated). An unreachable box is a **blocked run**
under the stop route, never a repair cycle.

## Models and effort

- **Executor: `claude-sonnet-5`.** `standards/workflow.md` §3 sends execution
  against a finished spec to the cheapest model that passes acceptance, and
  sonnet-5 executed v1.5, v1.6.0, v1.7.0 and v1.8.0 end to end in this
  repository — v1.8.0 with 0 of 4 repair cycles drawn on the codebase.
  v1.9.0 is larger than v1.8.0 (14 tasks, five new dependencies, one schema
  migration, a live eval) but every design decision is frozen and every
  algorithm is written out normatively; the novelty is in the spec, not in
  the run. Escalation rule: if a single task burns two of the four repair
  cycles, the operator re-briefs that task's subagent on `claude-opus-5`
  rather than spending the remaining budget on the same model.
- **Reviewer: `sonnet`**, pinned in `.claude/agents/code-reviewer.md`
  (REQ-V190-REV-01); no override reason exists.
- **Effort: high for the orchestrator, default for the implementation
  subagents.** The spec is the reasoning artefact — three rounds of
  cross-review removed the ambiguity — so maximum effort would re-derive
  what the spec states (§3's waste). High is for the three places where
  care pays: the migration rebuild of `llm_calls` (STO-03), the atomic
  `vec_chunks` creation/rebind (STO-04), and the offset-based chunker with
  its 1,200-char invariant (DOC-03). As in v1.8.0 this is reasoned, not
  measured: no prompt file in this repository records an effort level.
- A spec-internal contradiction is a **STOP**, never a cue to raise effort.

## What it is

Course assignment 6 in full (`base/assignments/06-rag-for-agent.md` in the
lab — provenance only, not read by the run): a from-scratch RAG pipeline
over documents a user sends through Telegram — `.txt`, `.md`, `.docx`,
`.pdf` — download, extraction, chunking, embeddings, storage in SQLite +
sqlite-vec, a `search_documents(query)` tool the agent calls itself,
`/documents` and `/delete <filename>`, per-user isolation, source
attribution, an error matrix, a retrieval evaluation — plus all five
bonuses: progress stages, PDF page numbers, hybrid search, LLM reranking,
conversation-aware RAG.

## Frozen decisions the run must not reopen (D1–D18 of the authoring brief)

- **D1** Version **1.9.0** (minor); bump after the gates; tag after final
  acceptance.
- **D2** Whole assignment, all five bonuses; non-goals: OCR, images, other
  formats, sharing between users, re-embedding after a model change, a
  dashboard page for documents, the cost/benchmark **machinery** of v1.7.0,
  the stale `docs/plan.md`.
- **D3** Embeddings from LM Studio's `/v1/embeddings` through the bot's own
  httpx transport (`llm/embeddings.py`); `EMBEDDING_MODEL`/`EMBEDDING_DIM`
  required as a pair, both absent = RAG disabled; `FakeEmbedder` offline.
- **D4** Same SQLite file, schema **6**, `sqlite-vec 0.1.9`; `documents`,
  `chunks`, `vec_chunks` (vec0, `user_id integer partition key`, cosine);
  extension loaded on every connection; re-upload of a filename replaces.
- **D5** Character-based paragraph-aware chunking: 1,000 target, 1,200 hard
  maximum (overlap included), 200 overlap, 50-char minimum; a PDF chunk
  never spans pages.
- **D6** Vector top-20 + BM25 top-20 (`rank-bm25` + `snowballstemmer`
  russian) → RRF k=60 → top-10 → rerank → K=5; no similarity threshold.
- **D7** Reranker = LLM listwise call, purpose `rerank`, reasoning off; any
  failure falls back to the RRF order; recorded in `llm_calls`.
- **D8** Tool `search_documents(query)`; `user_id` injected by the runtime
  through a `Searcher` seam, never by the model; one prompt rule line.
- **D9** Structural `Sources:` line validation and fallback.
- **D10** Synchronous document flow; parsed from memory, never on disk;
  10 MiB cap before download; 500,000-char text cap; 20 documents per user;
  300-s budget checked between stages and PDF pages; progress through the
  v1.8.0 status message; English fixed strings.
- **D11** Error matrix with exact strings, one outer exception boundary.
- **D12** Owner predicate on every runtime statement; ≥ 7 `v190-*` mutation
  entries; `mutation-v190` gate.
- **D13** Live gate 7 `rag-eval`: committed corpus, ≥ 10 questions with
  `expected_evidence`, hybrid recall@5 ≥ 0.8 blocking, hashes frozen at the
  first live run, the reranker must run without fallback.
- **D14** Tests on every level with generated fixtures; gate 3 stays offline.
- **D15** Delegation mandatory, briefed by `docs/spec/task-briefs/v190-T<N>.md`.
- **D16** Exactly five new runtime dependencies (`sqlite-vec==0.1.9`,
  `pypdf==6.18.0`, `python-docx==1.2.0`, `rank-bm25==0.2.2`,
  `snowballstemmer==3.1.1`), permission given by the operator 2026-09-10.
- **D17** Reviewer stays `sonnet`.
- **D18** Report, tg-post, README `## Documents (RAG)` with the assignment's
  seven subsections, ledger row, `lint-docs` repointed.

## Repository facts folded in during authoring

- `tools.tool_specs()` serialises to 1,388 of the 1,400 chars
  `tests/test_prefix.py:29` allows, and the system prompt is at 532 of 550
  — both limits are amended by the spec (1,800 and 700).
- `llm_calls.purpose` has `CHECK (purpose IN ('agent','summary'))`
  (`storage.py:70`); recording `rerank` needs the rename-copy rebuild in the
  5→6 migration. No table or trigger references `llm_calls`; the only
  dependent object is `idx_llm_calls_conv`.
- A fresh database is seeded at schema **4** and migrated to 5
  unconditionally (`storage.py:147`, `:329-330`); the 5→6 step slots into
  that chain.
- `reasoning_tag("rerank", None)` returns `"final"` — off by default under
  the by-purpose policy; the reranker still forces `off` explicitly.
- `TelegramClient.call` is JSON-POST only; the binary file download is a
  new `download_file` method. `FakeTelegram` had only `send_message`.
- `tests/test_v15_standards.py:1728-1747` parses the gate matrix from
  `spec-v1.8.0-delta-1.md`; the v1.9.0 delta carries the new matrix and the
  test is repointed by the gates task.
- Pre-existing drift surfaced, not fixed: `README.md` says `LLM_TIMEOUT_S`
  defaults to 120 s while `config.py` says 240; `AGENTS.md:51-52` still
  says `/conversations` is "gained in this release"; `docs/plan.md` stops at
  v1.6.0; `_STATIC_ROUTES` is still dead.

## State

- Spec: `docs/spec/spec-v1.9.0.md`, 174,186 bytes; delta
  `docs/spec/spec-v1.9.0-delta-1.md`, 30,222 bytes (gate matrix, test table,
  assignment traceability, Appendix B). Both exceed the brief's caps (110 KB
  / 25 KB); the overrun is recorded in §1 and Appendix C, paid in prose,
  never by deleting normative content.
- 70 MUST (EC 13, DOC 6, STO 5, RET 8, TOOL 6, CMD 7, ERR 3, SEC 5, EVAL 4,
  TST 3, VER 1, RPT 5, REV 4) · 12 NON-GOAL · 14 tasks (T0–T13) · 62
  `T-V190-*` test ids (17 negative) · 7 mutation entries (`mutation-all`
  becomes 105) · 16 Gherkin scenarios · 6 config variables. Appendix A is a
  verified bijection in both directions.
- Twelve of fourteen tasks are delegated in §15.1's reading map (T0 and T13
  stay in the main context under the `artefacts only` exemption). Each
  delegated task is briefed by `docs/spec/task-briefs/v190-T<N>.md`, written
  by the orchestrator before the subagent is spawned.
- Commits: `060a5e7` (draft, citations audited: 280 checked, 14 corrected),
  `c820650` (round 1), `57dc746` (round 2), `457612d` (round 3). Authoring
  prompt: `docs/prompts/141-v190-spec-authoring.md`. The run's own prompts
  start at **142**; `docs/llm-usage.md` continues at row 68.
- `[[VERIFY: …]]` markers: **none** — the one the draft carried (vec0
  partition-key syntax) was resolved in round 1 from sqlite-vec's own docs.

## Cross-review

Three rounds against OpenAI Codex `gpt-5.6-sol`. **30 findings, 30 accepted
(12 adapted), 0 rejected** — one clause inside R1-8 (a blocking
`rerank MRR ≥ hybrid MRR − 0.05`) was rejected as gating a probabilistic
judgement. Plus 4 lab-audit items accepted. Termination is **`round_limit`**:
round 3 still returned 1 Critical and 6 High findings. The Critical one was
the lab's own artefact — the round-2 applying pass corrupted the 14 `BM25`
tokens with a global size-figure replacement — and is fixed; the six High
findings are applied. **Residual findings may exist.** Appendix C carries the
full log and every rationale.

Two operator-visible consequences of the review worth knowing before `go`:
the project's benchmark rule (`AGENTS.md` § Benchmark) fires for this
release because the tool schema and the system prompt change, so T0 and T11
each run a live benchmark (reported, not gated) — strike REQ-V190-EC-06
before `go` if that inference time is not wanted; and gate 7 is live and
cannot pass with the reranker off, so the chat model on the box must answer
the rerank prompts.

## Closing message (run closed 2026-09-12)

Run complete, T0–T13 all landed. `<base>` = `d6c13124d8108d6ca23900b91ef30d27d95fc6fc`,
`<implementation-tip>` = `5f9c58f3ad49bf3b609df90329db4c7a83296a1f` (T12).
T13's evidence-only commit: `02b9536a39a4c216b3e5f6fcd59abd46407a7e99`.
**Tag `v1.9.0` created on that commit**, object `a009dac74647c8b1ae32d6442a75ed2141d77c27`.

Final gate exit codes at T13: gates 1–6 and 8–15 of `checks.py run
--profile full` all `0`; gate 7 (`rag_eval.py`) **exit 2** — the disclosed,
diagnosed known limitation (recall@5=1.000 on every retrieval mode across
every live run; the LLM reranker's completion contract only, root-caused
to genuine run-to-run stochastic reasoning-length variance in the
deployed thinking chat model `qwen/qwen3.8-27b`, not this release's code).
`lint-docs` and `gitleaks-tree`, re-run against the evidence commit
specifically: both exit `0`. `checks.py replay --range <base>..<implementation-tip>`:
36/36 commits clean, no `--no-verify` anywhere.

**The operator explicitly accepted the release under gate 7's standing
FAIL** and authorised the tag — mirroring this project's own v1.7.0
precedent. Full detail, every disclosed erratum, and the complete
per-task history: `docs/reports/report-v1.9.0.md`.
