# Prompt 172 — v1.9.2 T3 erratum: ledger-row counts, sequencing disclosure

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a self-found paperwork correction (an `advisor()` call
  made before declaring T3 done) against T3's own just-written report
  section — arithmetic reconciliation against two already-committed review
  briefs, and a disclosure of edit-vs-gate sequencing already implicit in
  T3's own commit; no code change, no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.2 T3, post-completion paperwork pass (patch, no new spec
  file — precedent: prompt 166 for T1, prompt 169 for T2)
- **Owner of:** `docs/reports/report-v1.9.2.md`,
  `docs/prompts/172-v192-t3-erratum.md`, `docs/llm-usage.md`
- **REQ ids:** none new — corrects this release's own Ledger-row/report
  paperwork (REQ-V190-RPT-02/-03)

## Goal

`advisor()`, called before reporting T3 done, found two problems in
`c431987`'s own `docs/reports/report-v1.9.2.md`:

1. The Ledger row's Bugs column transcribed the T3 task brief's literal
   text ("T1 1 🔴 / 4 🟠 / 5 🟡, T2 0 🔴 / 3 🟠 / 6 🟡") without checking it
   against the two review briefs it summarizes. Counting
   `docs/spec/task-briefs/v192-T1-review.md` (items 1–9) and
   `v192-T2-review.md` (items 1–8) directly gives **9** (1🔴/4🟠/4🟡) and
   **8** (0🔴/3🟠/5🟡) findings respectively — matching `c21ffb3`'s own
   commit message ("closes all nine findings") and this report's T2
   delegation record ("closing all eight findings"), both written before
   T3 existed. The brief's own arithmetic was one 🟡 over on each side.
   Corrected in the "### The two clean-context reviews" summary and the
   Ledger row itself, with an erratum note directly above the row naming
   the discrepancy — the same erratum-not-rewrite convention `c21ffb3`
   already established for this release.
2. The seven-gate table's "final tree" framing did not disclose that five
   things landed in `c431987` *after* gate 7 finished, using gate 6's/7's
   own results as input: `config/quality_gates.yaml`'s
   `mutation-all.timeout_seconds` (7910→1440), the whole T3 report
   section itself, `tg-post-v1.9.2.md`, `llm-usage.md` row 81, and the
   Ledger row. No gate can be re-run against a tree containing its own
   report of itself — the same point v1.9.1's report made about a
   mutation gate only being as valid as the suite it ran against, and the
   family of finding `/verify-run` raised on v1.8.0. Added as disclosure
   (e), naming exactly what landed post-gate-7 and what *was* re-run
   afterward (`ruff check .`, `ruff format --check .`, `pytest`,
   `checks.py lint-docs` — all exit 0 again on the tree as actually
   committed) versus what was not (gates 4/5/6/7).

Also fixed in passing, found while re-reading disclosure (c) for this
erratum: it claimed gate 6 (invoked exactly as `AGENTS.md` lists it, `uv
run --locked python devtools/mutation_check.py` directly) "uses
`mutation-all`'s own single timeout" — false; that value only binds an
invocation made through `checks.py run --profile ...`, and this run went
through neither. Corrected, plus one sentence naming that the new 1440s
carries much less slack against this box's own documented
shared/contended variance than 7910s did, interacting with disclosure
(b)'s SIGKILL-on-timeout hazard — stated, decided by neither this prompt
nor the report.

## Constraints

- `c431987` is not amended or rebased — every correction is an erratum in
  `docs/reports/report-v1.9.2.md`, the same convention `c21ffb3` used for
  T1's own review findings.
- No code, test, or version file touched; no gate 4/5/6/7 re-run (gate 6
  in particular: re-running an 11m20s mutation pass to validate a
  comment-and-timeout edit was judged not worth it, and is disclosed as
  such rather than silently skipped).
- The `v1.9.2` tag is moved to this commit (the release commit), since it
  fixes that same commit's own paperwork before the operator sees it —
  not pushed.
- `.env` never read; `data/`, `evals/rag/corpus` never opened. No
  `--no-verify`. Do not push.

## Acceptance

`uv run --locked ruff check .` exit 0; `uv run --locked ruff format
--check .` exit 0; `uv run --locked pytest` exit 0 (1601 collected,
unchanged); `uv run --locked python devtools/checks.py lint-docs` exit 0.

## Stop

None triggered — both findings had a named, unambiguous fix (erratum +
disclosure, not a rewrite of prior facts).
