# Prompt 141 — authoring spec-v1.9.0

- **Date:** 2026-09-10
- **Executor model:** claude-fable-5-1 (lab session: drafting and citation-audit subagents); claude-opus-5 (applying subagents)
- **Model reason:** spec authoring is the stage where an error multiplies
  downstream, so `standards/workflow.md` §3 sends it to the strongest model;
  the executor that later runs this spec is chosen separately in the handoff
- **Harness:** Claude Code (lab session), `spec-authoring` skill
- **Stage:** authoring — no task in this spec; the run it describes starts at
  prompt 142
- **Owner of:** `docs/spec/spec-v1.9.0.md`,
  `docs/prompts/141-v190-spec-authoring.md`
- **REQ ids:** none implemented; this prompt produces the file that defines
  REQ-V190-* and T-V190-*

## Goal

Write the release specification for v1.9.0 so an autonomous executor can run
it end-to-end via `go` in a session with no access to this conversation. The
release implements course assignment 6 in full — a from-scratch RAG pipeline
over documents a user sends through Telegram (`.txt`, `.md`, `.docx`,
`.pdf`): download, text extraction, chunking, embeddings, storage in SQLite +
sqlite-vec, a `search_documents(query)` tool the agent calls itself, the
`/documents` and `/delete <filename>` commands, per-user isolation, source
attribution, an error matrix, an evaluation dataset — plus all five bonuses
(progress stages, PDF page numbers, hybrid search, reranking,
conversation-aware RAG).

The operator's decisions frozen into the spec: the version is **1.9.0**
(a minor: new user-facing functionality); embeddings come from LM Studio's
`/v1/embeddings` through the bot's own HTTP transport, with the model name
and dimension supplied by the operator at `go` time; the five new runtime
dependencies are permitted and pinned (`sqlite-vec`, `pypdf`, `python-docx`,
`rank-bm25`, `snowballstemmer`); the evaluation is a live gate; the reviewer
stays `sonnet`; every implementation task is delegated and briefed by a
task-brief file.

## Constraints

- Authoring only: no code changes, no live model calls beyond the Codex
  cross-review, `.env` and `data/` never opened.
- Drafted from a frozen brief (decisions D1–D18 and the repository facts the
  lab session established), then audited citation by citation, then
  cross-reviewed against OpenAI Codex `gpt-5.6-sol` for up to three rounds;
  every finding is ruled on by the lab before a clean-context subagent
  applies it; Appendix C records every verdict.
- Spec size is a lab decision (`standards/workflow.md` §12); the file carries
  a per-task reading map because it exceeds the 80 KB ceiling.

## Acceptance

- `docs/spec/spec-v1.9.0.md` exists; Appendix A is a bijection between MUST
  ids and traceability rows; every task has a reading-map row with a
  `delegate` cell; no `[[VERIFY: …]]` marker is left without a decision rule.
- Every `file:line` citation was opened and confirmed by the audit pass.
- Appendix C names the challenger, the rounds, the termination reason and
  the accept/reject tally.
- `uv run --locked python devtools/checks.py lint-docs` accepts this prompt
  file (header bullets and the four blocks in order).

## Stop

The lab session stops and reports when the Codex seam cannot be reached
after a real attempt (recorded in Appendix C with what stood in for it), or
when the citation audit surfaces a contradiction between the frozen
decisions and the repository that the operator has to resolve.
