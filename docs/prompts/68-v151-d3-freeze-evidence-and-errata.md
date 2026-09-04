# Prompt 68 — v1.5.1 patch: D3, freeze evidence gap and mutation-count errata

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** two small, precise factual corrections — one needs a
  real, reproducible re-verification (not an assertion) of two already-
  landed commits via `checks.py replay`, the other a grep-verified digit
  fix; both are judgment-light, evidence-bound edits, matching the model
  used for every other prompt in this patch
- **Harness:** Claude Code
- **Stage:** v1.5.1 patch, D3 (docs-only)
- **Owner of:** `docs/reports/report-v1.5.md` (Deviations items 6(b) and 7),
  `docs/spec/spec-v1.5.md` (two "43 mutation entries" prose spots)
- **REQ ids:** REQ-V15-ACC-03, REQ-V12-MUT-01

## Goal

Close two documentation gaps found by post-run `/verify-run`. (a)
`docs/reports/report-v1.5.md` states the freeze-exception re-verification
("commit-msg, `pre-commit`, `lint-docs` and `gitleaks-tree` re-verified
against the final tree") only for post-freeze commit `346a67b`; commits
`6fde12f` and `85c5ad7` (both under the same REQ-V15-ACC-03 exception)
lack that sentence. Cannot establish whether an equivalent re-verification
was actually run for them at the time — say so plainly — and instead
perform a real re-verification now, using `checks.py replay` (reads git
objects only, never touches the working tree, exactly the tool built for
verifying a historical commit after the fact), and record its actual
output. (b) `docs/spec/spec-v1.5.md` still says the mutation suite has
"43 entries" in two prose spots (§ near "byte-exact find string" and the
§14 gate table); the real, current number is 72
(`grep -c '"id":' devtools/mutation_check.py`) — fix the stale digit in
both places, changing no REQ semantics.

## Constraints

- Documentation only: no source, test or config file touched.
- No REQ id, acceptance criterion or table structure changed in
  `spec-v1.5.md` — digit fix only.
- Do not touch report-v1.5.md's Ledger row, Verdict or any section other
  than Deviations items 6(b)/7.
- Every other "43" in `spec-v1.5.md` (prompt-file-numbering references:
  `docs/prompts/43-v14-verify-run-fixes.md`, the "≤ 43 exemption", "numbered
  ≥ 43") is unrelated to the mutation count and must be left untouched.

## Acceptance

- `docs/reports/report-v1.5.md` Deviations item 6(b) and item 7 each carry
  a truthful re-verification sentence for `6fde12f` and `85c5ad7`
  respectively, citing the actual `checks.py replay` command and its
  actual PASS/clean output.
- `grep -n "43 " docs/spec/spec-v1.5.md` shows no remaining "43 mutation
  entries" / "43 entries" occurrence; the two fixed spots now read "72".
- `uv run --locked python devtools/checks.py lint-docs` exits 0.

## Stop

If `checks.py replay` had produced anything other than a clean PASS for
either commit, or if that constituted a *new* replay failure not already
diagnosed in report-v1.5.md, stop and report instead of writing a
reassuring sentence anyway. Not triggered: both replayed clean.
