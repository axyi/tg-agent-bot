# Prompt 125 — v1.7.0 operator acceptance and the authorised tag

- **Date:** 2026-09-08
- **Executor model:** claude-opus-5 (lab session)
- **Model reason:** no design work and no code — the operator's decision is
  recorded verbatim and the two report artefacts are brought in line with
  it; the judgement needed is about what must be disclosed, which the lab
  session already holds in context
- **Harness:** Claude Code (lab session)
- **Stage:** post-run, after `/verify-run` on the finished v1.7.0 run
- **Owner of:** `docs/reports/report-v1.7.0.md` (a new "Operator decision"
  subsection under the verdict), `docs/reports/tg-post-v1.7.0.md` (title and
  the tag sentence), `docs/prompts/125-v170-operator-acceptance.md`
- **REQ ids:** none implemented; records a disclosed deviation from
  REQ-V170-VER-02

## Goal

The run ended with a cost-gate `FAIL`, and the executor correctly created no
tag, as `REQ-V170-VER-02` requires. The operator has since accepted the
release as it stands and authorised the tag. Record that decision where a
later reader will find it: an "Operator decision" subsection in the run
report, directly under the verdict it overrides, and a corrected sentence in
the Telegram post. The measurement itself is not touched — the −30 % goal
stays recorded as not met.

## Constraints

No code, tests, configuration or spec change. No number in the report is
edited: the verdict, the gate arithmetic and the shortfall stay exactly as
the run measured them. The Telegram post stays Russian and under 1500
characters. The tag is annotated and its message carries the same rationale,
so the tag is self-explaining without this file.

## Acceptance

`uv run --locked python devtools/checks.py lint-docs` exits 0; the report
carries the operator-decision subsection; `git tag -l` shows `v1.7.0` on the
commit this prompt creates; `wc -m docs/reports/tg-post-v1.7.0.md` stays
under 1500.

## Stop

If accepting the release required changing a measured number or a gate
result, stop and report instead: that would be rewriting the run, not
overriding its routing.
