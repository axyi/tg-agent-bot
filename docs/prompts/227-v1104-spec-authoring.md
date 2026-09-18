# Prompt 227 — authoring spec-v1.10.4

- **Date:** 2026-09-18
- **Executor model:** claude-fable-5-1 (lab session: reconnaissance, drafting, citation-audit and applying subagents; opus-5 where the weekly limit forced it)
- **Model reason:** spec authoring is the stage where an error multiplies
  downstream, so `standards/workflow.md` §3 sends it to the strongest model;
  the executor that later runs this spec is chosen separately in the handoff
- **Harness:** Claude Code (lab session), `spec-authoring` skill
- **Stage:** authoring — no task in this spec; the run it describes starts at
  prompt 228
- **Owner of:** `docs/spec/spec-v1.10.4.md`,
  `docs/prompts/227-v1104-spec-authoring.md`
- **REQ ids:** none implemented; this prompt produces the file that defines
  REQ-V1104-* and T-V1104-*

## Goal

Write the short follow-up specification for v1.10.4 so an autonomous
executor can run it end-to-end via `go` in a session with no access to
this conversation. The v1.10.3 run stopped at T6 before its single gate 8:
the spec's "exhaustive" test-edit list missed four pre-existing tests that
assert a list never grows (a mutation tail, a gate-label dict, an `.env`
fixture, sentence-boundary fixtures), three repair cycles went to them and
the fourth pin stopped the run by the letter of the budget rule. Its five
`v1103-*` mutation entries — authored and verified in isolation — sit in a
git stash. This spec lands those entries from the stash's two non-test
paths, rewrites every frozen-list pin into presence-and-order assertions,
replaces the per-pin budget rule with a structural T0 inventory and
disclosed amendments, repoints the report and spec pins, runs the live
gates with exactly one gate 8, and ships version 1.10.4 with the release
rows three stopped runs left pending. No mechanism, marker, prompt or
model changes; the benchmark rule is not triggered.

The operator's decisions frozen into the spec: version **1.10.4**
(1.10.0–1.10.3 stay stopped, untagged runs); the same instruments as
v1.10.3 (`openai/gpt-4.1` under test, `anthropic/claude-sonnet-5` judge
with the one fallback); the verifier's informational green gate 8 on the
stopped tree is evidence about the instrument, never a release verdict;
the stash is applied by path filter, never popped; no push in the run.

## Constraints

- Authoring only: no code changes, no live model calls beyond the Codex
  cross-review; the stash read with `git stash show -p` and checked with
  `git apply --check` only; `.env` and `data/` never opened (the storage
  preflight's `db_empty=<bool>` line by exit status only), `raw/` never
  read.
- Drafted from a frozen brief (decisions D1–D14 and one repository-facts
  file the lab session established by read-only reconnaissance), then
  audited citation by citation, then cross-reviewed against OpenAI Codex
  `gpt-5.6-sol` for up to three rounds; every finding is ruled on by the
  lab before a clean-context subagent applies it; Appendix C records every
  verdict.
- Spec size is a lab decision (`standards/workflow.md` §12); the file
  references the mechanisms of v1.10.0 through v1.10.3 by id instead of
  restating them.

## Acceptance

- `docs/spec/spec-v1.10.4.md` exists; Appendix A is a bijection between MUST
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
