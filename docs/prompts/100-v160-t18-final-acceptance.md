# Prompt 100 — spec-v1.6.0 T18: final acceptance

- **Date:** 2026-09-06
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** mechanical re-execution of already-specified acceptance
  commands (six gates, two `full` profile invocations, `replay`, Appendix
  B, ACC-02) against a tree already known byte-identical to the last
  measurement (`git diff --stat ca9c656..HEAD` showed only documentation
  and evidence files) — no design decision open; the one judgment call
  (whether to skip the expensive re-runs given the zero-diff evidence) was
  settled by `advisor()` before starting: re-run in full, per ACC-03's own
  text
- **Harness:** Claude Code
- **Stage:** T18
- **Owner of:** `docs/reports/report-v1.6.0.md` (header status, Ledger row,
  the new "T18 — final acceptance" section), this prompt file
- **REQ ids:** REQ-V160-ACC-01, -02, -03, -04, REQ-V160-VER-04

## Goal

Execute REQ-V160-ACC-03's final acceptance run against the tree at
`726771f` (`<implementation-tip>`, T17's own commit): the six verbatim
gates of §14, `checks.py run --profile full` under both `--since`
candidates left ambiguous between prompt 93's literal text and ACC-03's
`<base>` terminology (`d7e1d395…` and `65146f0`), `checks.py replay
--range <base>..<implementation-tip>`, Appendix B's fourteen scenarios
(REQ-V160-ACC-01) and the ACC-02 regression check. Land one evidence-only
commit recording the tip SHA, the replay output, the intended tag name and
the remaining evidence, then stop for the operator's explicit approval
before creating the annotated `v1.6.0` tag.

## Constraints

- REQ-V160-BEN-07's freeze is in force: no source, test, config, scenario,
  tool-schema, model-setting or inference-setting change. Only
  `docs/reports/*` may change in the evidence commit — per ACC-03's own
  text, a **deliberate** scope narrower than this project's general
  "owner of" convention.
- **Disclosed deviation from that scope, one file wide:** this prompt file
  (`docs/prompts/100-…`) is committed alongside `docs/reports/*` rather
  than left out, because `checks.py commit-msg`'s `check_prompt_reference`
  hard-blocks any commit whose body does not cite an **existing**
  `docs/prompts/NN-<slug>.md` — a project-wide, tool-enforced invariant
  this run cannot silently bypass — and because leaving a permanently
  untracked prompt file on disk (satisfying the hook without ever
  reaching version control) was judged the worse of the two available
  departures from ACC-03's literal wording. Recorded in the report's
  Deviations, not silently resolved.
- Gate 6 and the `full` profile's `mutation-all` member are re-run for
  real, not cited from the earlier resume-session measurement, despite a
  confirmed zero source/config diff since `ca9c656` — `advisor()` was
  consulted specifically on this point before starting and the answer was
  unambiguous: ACC-03 says "re-runs", this is the last check before an
  irreversible tag, and *predicted* redundancy is exactly what that
  wording exists to refuse.
- No git tag is created in this prompt's own scope; that is a separate,
  explicitly operator-gated action after this commit lands.

## Acceptance

- Gates 1–6 of §14: all green (gate 6: 83/83 killed, 0 survived/errored/
  drifted).
- `checks.py run --profile full --since d7e1d395…` and `--since 65146f0`:
  both all-PASS, recorded side by side.
- `checks.py replay --range d7e1d395…..726771f`: every commit in range
  `clean`.
- Appendix B E1–E14: pass/fail and how-driven recorded per scenario;
  E13's staleness against errata 3 and 6 flagged explicitly (task #10),
  not silently reinterpreted.
- ACC-02: spec-v1.2 D1/D2, spec-v1.4 S01, spec-v1.5 freeze properties all
  confirmed still holding, with concrete evidence (test ids, the recorded
  baseline's own S01 checks, the replay output).
- `git status --porcelain` after the evidence commit: clean.
- The evidence commit's message and the report both name `v1.6.0` as the
  **intended** tag, and neither claims the tag exists.

## Stop

None reached — every acceptance command passed on the first attempt; 0 of
5 repair cycles drawn (REQ-V160-ACC-04). The run stops here only for the
operator's required, separate approval before the tag-creation step
(REQ-V160-VER-04), per this project's own production/irreversible-action
approval gate.
