# Prompt 245 — v1.11.0 T6 follow-up: exact-quote the benchmark-waiver sentence

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** a single, spec-literal wording correction under every
  §5.1 threshold — orchestrator, main context, no delegation.
- **Harness:** Claude Code (background session, orchestrator)
- **Stage:** T6 (follow-up)
- **Owner of:** `AGENTS.md`, `docs/reports/report-v1.11.0.md` (`## T6`)
- **REQ ids:** REQ-V1110-NG-11

## Goal

T6's delegated subagent (commit `141a02d`) found, via its own post-commit
advisor review, that its first landing of the benchmark-waiver sentence
paraphrased `spec-v1.11.0.md:244`'s exact quote (wrapping the four
identifiers into the sentence itself) rather than reproducing it as one
continuous substring: `"v1.11.0 changes nothing token-bearing; the rule
does not fire."` T8's `T-V1110-VER-04` most plausibly checks for this
exact quote as a substring of `AGENTS.md`'s waiver paragraph. Left
uncommitted for a small follow-up, matching this run's established
pattern (prompts 238, 243).

## Constraints

Docs only — no source or test file touched, no gate re-run beyond
confirming the suite stays green. `lint-docs` must stay green.

## Acceptance

`AGENTS.md`'s waiver paragraph contains the literal substring `"v1.11.0
changes nothing token-bearing; the rule does not fire."` verbatim, with
the four-identifier clarification as a separate following sentence rather
than a parenthetical inside it. `docs/reports/report-v1.11.0.md`'s `## T6`
section quotes the corrected sentence. Gates 1-4 green on the corrected
tree.

## Stop

Not applicable — this is itself the fix.
