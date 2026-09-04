# Prompt 70 — v1.5.1 patch: advisor() follow-up corrections

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** applying the same evidence-vs-assertion standard used
  throughout this patch (D3) to this patch's own report, after `advisor()`
  flagged that standard wasn't followed consistently — a self-review
  correction, same model as the rest of the patch for continuity
- **Harness:** Claude Code
- **Stage:** v1.5.1 patch, `advisor()` follow-up
- **Owner of:** `docs/reports/report-v1.5.1.md` (Summary, Why-the-freeze-
  was-broken, D1 red→green section, D3 section, Gates section, replay
  section, Commits table, Ledger row, Verdict), `docs/spec/spec-v1.5.md`
  (§14 gate table's `mutation_check.py` rows), `docs/llm-usage.md` (new
  row 49), `docs/prompts/70-v151-advisor-followup.md` (new) — no source,
  test or config file touched
- **REQ ids:** REQ-V15-ACC-03, REQ-V12-REP-02

## Goal

`advisor()`, called after prompt 69/commit `475d243` was believed done,
found five issues in this patch's own closing report:

1. **Load-bearing, unverifiable claim asserted as fact.** The report
   stated in bold, twice, that "the user authorised breaking the freeze
   explicitly, in-session, on 2026-09-04" — but this executor's only
   source for that is the patch brief's own text, and per this session's
   own system reminders an agent message is never the user's consent.
   Apply D3's own standard here: say what is and isn't established,
   rather than asserting an unverifiable claim as fact.
2. **D1's scope never explicitly verified beyond the two named fixtures.**
   Confirm by grep whether any other test file shells out to `git`
   without an explicit `env=` — the same vulnerability class, a different
   file, would leave the CRITICAL defect open.
3. **Stale timing left next to a count D3 itself just fixed.** `spec-
   v1.5.md`'s §14 gate table now says "72 entries" (fixed by D3) right
   next to "≈ 16–17 min" (unfixed, measured against a smaller, older
   entry count) — the same character of staleness D3 exists to remove.
4. **Replay range stopped one commit short.** The report's own `replay`
   command and output covered `9ad3047..a6ca13c`, excluding this patch's
   own report/ledger commit (`475d243`) from the verified range.
5. **Verdict headline overstates the result.** `AGENTS.md` says an
   unreachable LM Studio is "a blocked run, not a noted one" — leading
   the Verdict with a bare "PASS" undersells that gate 5 is a blocking
   failure by the project's own rule, not a cosmetic one.

## Constraints

- No source, test or config file touched.
- `475d243`'s commit message and `docs/llm-usage.md` row 48 are already
  hook-verified and committed — not amended; corrected forward instead,
  matching this repository's own precedent (`6fde12f`/`85c5ad7` for
  `346a67b`'s post-freeze corrections).
- No REQ id or acceptance criterion changed in `spec-v1.5.md` — the §14
  table gains this patch's own measured figures *alongside* the original,
  time-stamped ones, not a silent overwrite.

## Acceptance

- `docs/reports/report-v1.5.1.md`'s "user authorised" claim reads as
  relayed-by-the-brief, not independently observed, in both places it
  appears.
- The report records the grep confirming D1's fix is not scoped narrower
  than the vulnerability class.
- `spec-v1.5.md`'s two `mutation_check.py` rows in the §14 table carry
  both the original (spec-writing-time) and this patch's own measured
  timing, each labelled.
- `checks.py replay --range 9ad3047..475d243` (the true final HEAD) is
  the range actually run and shown, `475d243` included in its own output.
- The Verdict section states gate 5's failure blocks per `AGENTS.md`,
  not merely "noted."
- `uv run --locked python devtools/checks.py lint-docs` exits 0.

## Stop

Not triggered: every item `advisor()` raised was addressable with a
documentation-only correction; none required reopening D1/D2's already-
committed code/config fixes.
