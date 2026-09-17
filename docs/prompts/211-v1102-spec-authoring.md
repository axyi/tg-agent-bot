# Prompt 211 — authoring spec-v1.10.2

- **Date:** 2026-09-17
- **Executor model:** claude-fable-5-1 (lab session: reconnaissance, drafting, citation-audit and applying subagents; opus-5 where the weekly limit forced it)
- **Model reason:** spec authoring is the stage where an error multiplies
  downstream, so `standards/workflow.md` §3 sends it to the strongest model;
  the executor that later runs this spec is chosen separately in the handoff
- **Harness:** Claude Code (lab session), `spec-authoring` skill
- **Stage:** authoring — no task in this spec; the run it describes starts at
  prompt 212
- **Owner of:** `docs/spec/spec-v1.10.2.md`,
  `docs/prompts/211-v1102-spec-authoring.md`
- **REQ ids:** none implemented; this prompt produces the file that defines
  REQ-V1102-* and T-V1102-*

## Goal

Write the patch-release specification for v1.10.2 so an autonomous executor
can run it end-to-end via `go` in a session with no access to this
conversation. The release reacts to the v1.10.1 run, which the stop route
ended at T6 with gate 8 red: three of four injection misses were the new
clause (e) — the model called `exec` when told to reveal its system prompt
and environment — and the stop-route follow-up attributed that to a
bot-side gap, not to the model: `SYSTEM_PROMPT` carries no rule against
looking secrets up by tool. The spec closes that gap with one prompt line,
makes the gate-8 verdict complete per case (every violated clause, the tool
calls with their first argument, on the same stdout the report quotes),
widens the two adjacency-blind marker families (INJ-05's «не могу
отключать …», HAL-03's «нет конкретной информации») with fixture proof,
codifies the gate-7 transient-rerank re-invocation the v1.10.1 run had to
improvise, and ships the paperwork block two stopped runs never reached
(README release and result rows, AGENTS.md counts and waiver, `.env.example`
defaults, the v1.10.0 delegation-line correction).

The operator's decisions frozen into the spec: version **1.10.2** (1.10.0
and 1.10.1 stay stopped, untagged runs); the same instruments as v1.10.1
(`openai/gpt-4.1-mini` under test, `openai/gpt-4.1` judge, OpenRouter
embeddings) and the same floors, no-rerun rule and stop route — a red gate 8
is Stage B′ again, now with the evidence the next decision needs; no
tool-level guard; no push in the run.

## Constraints

- Authoring only: no code changes, no live model calls beyond the Codex
  cross-review, `.env` and `data/` never opened (the storage preflight's
  `db_empty=<bool>` line by exit status only), `raw/` never read.
- Drafted from a frozen brief (decisions D1–D14 and one repository-facts
  file the lab session established by read-only reconnaissance), then
  audited citation by citation, then cross-reviewed against OpenAI Codex
  `gpt-5.6-sol` for up to three rounds; every finding is ruled on by the
  lab before a clean-context subagent applies it; Appendix C records every
  verdict.
- Spec size is a lab decision (`standards/workflow.md` §12); the file
  references v1.10.0's and v1.10.1's mechanisms by id instead of restating
  them.

## Acceptance

- `docs/spec/spec-v1.10.2.md` exists; Appendix A is a bijection between MUST
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
