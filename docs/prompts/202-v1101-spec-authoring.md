# Prompt 202 — authoring spec-v1.10.1

- **Date:** 2026-09-14
- **Executor model:** claude-fable-5-1 (lab session: reconnaissance, drafting, citation-audit and applying subagents)
- **Model reason:** spec authoring is the stage where an error multiplies
  downstream, so `standards/workflow.md` §3 sends it to the strongest model;
  the executor that later runs this spec is chosen separately in the handoff
- **Harness:** Claude Code (lab session), `spec-authoring` skill
- **Stage:** authoring — no task in this spec; the run it describes starts at
  prompt 203
- **Owner of:** `docs/spec/spec-v1.10.1.md`,
  `docs/prompts/202-v1101-spec-authoring.md`
- **REQ ids:** none implemented; this prompt produces the file that defines
  REQ-V1101-* and T-V1101-*

## Goal

Write the patch-release specification for v1.10.1 so an autonomous executor
can run it end-to-end via `go` in a session with no access to this
conversation. The release closes every tail the v1.10.0 run and its
`/verify-run` left — the injection checker's echo and negation false
positives and its missing refusal markers, the hallucination rule that
missed honest "cannot verify" replies, the model's tool call under attack,
the T6 delegation-record contradiction, the stale count lines, the skylos
grep budget that broke the pre-push hook, the system prompt that never
compelled a document search — and, by the operator's decision, moves every
live gate off LM Studio onto OpenRouter models the lab chose: chat under
test `openai/gpt-4.1-mini`, judge `openai/gpt-4.1`, embeddings
`openai/text-embedding-3-small`, rerank unchanged.

The operator's decisions frozen into the spec: version **1.10.1** (patch;
1.10.0 stays a stopped, untagged run); zero new dependencies; the
embeddings client learns to authenticate and gate 5 probes only the
providers the configuration routes to; a gate-level `env:` key pins
`SKYLOS_GREP_BUDGET`; the dataset floors and the no-rerun rule stand; the
benchmark rule is waived for this release because the instrument changed;
no push in the run — the operator pushes everything together.

## Constraints

- Authoring only: no code changes, no live model calls beyond the Codex
  cross-review and two lab probes of OpenRouter's public and authenticated
  model listings (an embeddings round-trip of three tokens), `.env` and
  `data/` never opened, `raw/` never read.
- Drafted from a frozen brief (decisions D1–D14 and one repository-facts
  file the lab session established by read-only reconnaissance), then
  audited citation by citation, then cross-reviewed against OpenAI Codex
  `gpt-5.6-sol` for up to three rounds; every finding is ruled on by the
  lab before a clean-context subagent applies it; Appendix C records every
  verdict.
- Spec size is a lab decision (`standards/workflow.md` §12); the file
  references v1.10.0's mechanisms by id instead of restating them.

## Acceptance

- `docs/spec/spec-v1.10.1.md` exists; Appendix A is a bijection between MUST
  ids and traceability rows, every test id is cited by a row, and the tails
  traceability table maps every recorded tail to a requirement or a
  NON-GOAL; every task has a reading-map row with a `delegate` cell; no
  `[[VERIFY: …]]` marker is left without a decision rule.
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
