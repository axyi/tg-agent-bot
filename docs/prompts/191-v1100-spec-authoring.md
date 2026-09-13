# Prompt 191 — authoring spec-v1.10.0

- **Date:** 2026-09-13
- **Executor model:** claude-fable-5-1 (lab session: reconnaissance, drafting and citation-audit subagents); claude-fable-5-1 (applying subagents)
- **Model reason:** spec authoring is the stage where an error multiplies
  downstream, so `standards/workflow.md` §3 sends it to the strongest model;
  the executor that later runs this spec is chosen separately in the handoff
- **Harness:** Claude Code (lab session), `spec-authoring` skill
- **Stage:** authoring — no task in this spec; the run it describes starts at
  prompt 192
- **Owner of:** `docs/spec/spec-v1.10.0.md`,
  `docs/prompts/191-v1100-spec-authoring.md`
- **REQ ids:** none implemented; this prompt produces the file that defines
  REQ-V1100-* and T-V1100-*

## Goal

Write the release specification for v1.10.0 so an autonomous executor can
run it end-to-end via `go` in a session with no access to this conversation.
The release implements course assignment 7 in full — a test suite for the
agent's core in three levels: deterministic and contract tests (input
sanitization, the plain-text outbound pin, the tool-call JSON contract),
behavioural red-team tests over a 12-case dataset (prompt injection,
hallucination and refusal, multi-turn memory with reset), and the optional
third level — an LLM-as-a-judge score over five open questions with a
blocking 0.8 mean, plus a measured, advisory latency SLA with a streaming
time-to-first-token probe.

The operator's decisions frozen into the spec: the version is **1.10.0**
(a minor: a new operational surface, gate 8, and a new config key); zero
new dependencies — no `deepeval`, no `jsonschema`, tests are written by
hand; gate 3 stays offline and every live check lives in one new runner,
`devtools/agent_eval.py`, registered as gate 8 `agent-eval` in the `full`
profile with gate 7's exit contract; the judge is a separate model supplied
by the operator at `go` time as `LLM_JUDGE_MODEL`, and the runner refuses a
judge equal to the model under test; the latency SLA is reported, never
blocking, because the box's chat model is a reasoning-class model; context
reset is the storage-level reset `/new` ends with, and the goals carry-over
is out of scope; every implementation task is delegated and briefed by a
task-brief file.

## Constraints

- Authoring only: no code changes, no live model calls beyond the Codex
  cross-review, `.env` and `data/` never opened, `raw/` never read.
- Drafted from a frozen brief (decisions D1–D18 and three repository-facts
  files the lab session established by read-only reconnaissance), then
  audited citation by citation, then cross-reviewed against OpenAI Codex
  `gpt-5.6-sol` for up to three rounds; every finding is ruled on by the lab
  before a clean-context subagent applies it; Appendix C records every
  verdict.
- Spec size is a lab decision (`standards/workflow.md` §12); the file carries
  a per-task reading map because it exceeds the 80 KB ceiling.

## Acceptance

- `docs/spec/spec-v1.10.0.md` exists; Appendix A is a bijection between MUST
  ids and traceability rows, and every test id is cited by a row; every task
  has a reading-map row with a `delegate` cell; no `[[VERIFY: …]]` marker is
  left without a decision rule.
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
