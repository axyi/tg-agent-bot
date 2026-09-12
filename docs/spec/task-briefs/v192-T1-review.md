# v1.9.2 T1 — clean-context review findings to close (prompt 166, one commit)

Review of `6c9a904` + `d25d664` (reviewer: clean context, every mechanical
check re-run: AST proof over 63 files, 108/108 drift on both trees, nine
re-derived entries semantically identical, acceptance green). Code is clean.
The paperwork is not: the amend of commit 1 was never propagated to two
places, and four smaller items. Close all of them in **one commit**,
`docs: close the review findings on v1.9.2 T1` — prompt file
`docs/prompts/166-v192-t1-review-findings.md`, `docs/llm-usage.md` row 76.
Commits stay unpushed; do **not** rewrite `6c9a904`/`d25d664` — the report
cites both hashes and the erratum path is cheaper than re-citing.

1. 🔴 `docs/llm-usage.md` row 74 describes the pre-amend commit ("6 deleted …
   4 unused variables … 1 left unsuppressed, `_MIGRATION_2_TO_3` … skylos 1
   finding"). Rewrite it to what `6c9a904` actually contains: 7 deleted
   (2 functions, 5 variables), 20 suppressed, 0 unsuppressed, skylos 0.
2. 🟠 `6c9a904`'s commit body carries the same stale sentences. Add an
   erratum line to `docs/reports/report-v1.9.2.md` §A row 8 (the
   `_MIGRATION_2_TO_3` row): the commit message predates the amend that
   added this deletion; the diff, not the message, is authoritative.
3. 🟠 `_MIGRATION_2_TO_3` deletion supersedes a named non-goal:
   `docs/spec/spec-v1.7.0.md:2413` **REQ-V170-NG-14** ("never removed as a
   side effect"). Cite it in report §A row 8 and say why it no longer
   binds: it is not a side effect — it is the operator's whole-tree cleanup
   order (handoff, quoted) applied through §A.3's (a)(b)(c) procedure.
4. 🟠 `docs/spec/spec-v1.9.0-delta-1.md:13-15` cites
   `tests/test_v15_standards.py:1711-1726` / `:1685-1707`; on the current
   tree the dict is at `:1689` and the parser at `:1718`. Refresh the
   citations (verify the numbers yourself with `grep -n`).
5. 🟠 `config/quality_gates.yaml`: with the tree now formatted, `pre-commit`
   still runs only the partition-shadow `ruff-format`, so a misformatted
   staged file outside the three `blocking_paths` passes pre-commit and is
   caught only at pre-push. Add `ruff-format-all` to the `pre-commit`
   profile (sub-second). Keep `ruff-format` where it is and extend its
   comment with the real reason the `blocking_paths` key must stay:
   `devtools/checks.py:892` (`replay`) reads it for historical commits.
   Repoint any test that pins the `pre-commit` profile membership literally
   (`grep -n "pre-commit" tests/test_v15_standards.py`); never delete.
   Re-run `uv run --locked python devtools/checks.py pre-commit` (or
   whatever the runner's profile invocation is — see `checks.py --help`)
   and record the exit code.
6. 🟡 Report §C.1/§C.2 cite `storage.py:439` for the semgrep WARNING; after
   the reformat it is `storage.py:487`. Fix the citation.
7. 🟡 Brief §B.4 asked to update `AGENTS.md:30`/`:213-215` and README lines
   saying format is shadow; none exist. Add one disposition line to report
   §B: "instruction moot — no such line; `skylos (shadow)` wording kept per
   §C.5".
8. 🟡 Both trailers read `Co-Authored-By: Claude Sonnet 5`. Accurate to the
   executor; leave as is, note it in the report's delegation record.
9. 🟡 `# skylos: ignore` on a `def` line is line-scoped and also hides the
   function name from skylos (verified by the reviewer in skylos
   4.35.0's config). Add one sentence to report §A's suppression paragraph
   naming the eight functions this affects (`_handle_signal`, `cmd_doctor`,
   `cmd_lint_docs`, `log_message`, `log_error`, `handle_starttag`,
   `handle_startendtag`, `NullSink.write`) so a future dead-code pass knows
   to check them by hand.

Acceptance: `uv run --locked python devtools/checks.py lint-docs` exit 0;
`uv run --locked pytest tests/test_v15_standards.py` exit 0 (item 5);
`uv run --locked ruff check .` and `ruff format --check .` exit 0; the
pre-commit profile run from item 5 exit 0. Return the commit hash and the
exit codes only.
