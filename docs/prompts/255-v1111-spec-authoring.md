# Prompt 255 — authoring spec-v1.11.1

- **Date:** 2026-09-23
- **Executor model:** claude-fable-5-1 (lab session: one read-only defect-inventory subagent, one drafting subagent, one citation-audit subagent, one applying subagent per cross-review round)
- **Model reason:** spec authoring is the stage where an error multiplies
  downstream, so `standards/workflow.md` §3 sends it to the strongest model;
  the executor that later runs this spec is named in the spec's Execution
  contract (`claude-sonnet-5`)
- **Harness:** Claude Code (lab session), `spec-authoring` skill
- **Stage:** authoring — no task in this spec; the run it describes starts at
  prompt 256
- **Owner of:** `docs/spec/spec-v1.11.1.md`,
  `docs/prompts/255-v1111-spec-authoring.md`
- **REQ ids:** none implemented; this prompt produces the file that defines
  REQ-V1111-* and T-V1111-*

## Goal

Write the patch specification for v1.11.1 so an autonomous executor can
run it end-to-end via `go` in a session with no access to this
conversation. The v1.11.0 run shipped and was verified by the lab's
`/verify-run` (FAIL 4/8: prompt 239 reused by three T2 commits, the
ledger row missing, the LM Studio LAN address literal in the paperwork,
one `config/quality_gates.yaml` hunk labelled "commands only"); its
clean-context review waived two should-fix findings; its report
disclosed a handful of small leftovers. This spec collects every known
defect into one patch: the plain-text fallback narrowed to HTTP 400, the
`/documents` id column widened so `/delete #<id>` round-trips, the
`/model` status label untruncated, an empty-state reply for `/sessions`,
`DOC_LIMIT_REPLY` naming both delete forms, one embedding batch constant,
dispatch-level tests for six error-matrix rows, an autouse fixture that
kills the xdist-order flake, three stale docstrings, README and
`docs/plan.md` drift, an AGENTS.md ruling on RFC1918 addresses, and the
v1.11.0 report/tg-post corrections. No new mechanism, no new mutation
entry, gate 8 exactly once, version 1.11.1 tagged locally, no push.

## Constraints

- Authoring only: no code changes, no live model calls beyond the Codex
  cross-review; `.env`, `data/`, `bot.db`, `sandbox/` never opened; LAN
  addresses written as `<addr>` everywhere in the authoring artefacts.
- Drafted from a frozen brief (decisions D1–D18 plus one facts file the
  lab session established by read-only reconnaissance), then audited
  citation by citation, then cross-reviewed against OpenAI Codex
  `gpt-5.6-sol` for up to three rounds; every finding is ruled on by the
  lab before a clean-context subagent applies it; Appendix C records every
  verdict.
- Spec size is a lab decision (`standards/workflow.md` §12); the file
  references v1.11.0's mechanisms by id instead of restating them.

## Acceptance

- `docs/spec/spec-v1.11.1.md` exists; Appendix A is a bijection between MUST
  ids and traceability rows, every test id and Gherkin id is cited, and
  the tails traceability table maps every inventory item to a requirement
  or a NON-GOAL; every task has a reading-map row with a `delegate` cell;
  no `[[VERIFY: …]]` marker is left without a decision rule.
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
