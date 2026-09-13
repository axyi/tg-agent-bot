# Prompt 179 — v1.9.3 T3 review findings: TRY400 tally, citations, placement

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** closing a clean-context review's findings against an
  existing brief (`docs/spec/task-briefs/v193-T3-review.md`) — each finding
  names the exact file, the exact wrong value and the exact correction;
  one finding (7) is a bounded either/or decision the brief itself already
  resolves ("pick the revert"). No open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.3 T3 review (`docs/spec/task-briefs/v193-T3-review.md`)
- **Owner of:** `pyproject.toml`, `tracing.py`, `docs/reports/report-v1.9.3.md`,
  `docs/llm-usage.md`, `docs/prompts/178-v193-t3-ruff-bugclass-tier.md`
- **REQ ids:** REQ-V15-NG-04, REQ-V160-TRC-*

## Goal

Closes a clean-context (opus) review of `acd373a`+`6fcf1fc`: no 🔴, one 🟠,
seven 🟡, all paperwork/placement — behaviour was preserved at every one
of the review's 14 checks, so neither reviewed commit is rewritten.

1. **TRY400 tally (🟠).** The report, `llm-usage.md` row 88, prompt 178 and
   the `6fcf1fc` commit body all stated "7 adopted / 9 kept" — an
   arithmetic slip against the report's own per-site list, which always
   totalled **10 adopted** (`bot.py` ×3, `dashboard_server.py` ×2,
   `devtools/bench.py` ×5) / **6 kept** (`bot.py` ×4, `tools.py` ×2).
   Corrected directly in the report, `llm-usage.md` and prompt 178 (all
   three are plain docs); the `6fcf1fc` commit body itself is not rewritten
   — an erratum paragraph in the report's T3 section names the
   discrepancy and the correct numbers instead, per the brief's own
   instruction. "Three `devtools/bench.py` failures" corrected to five
   (one scenario-prep site plus two DB-open/DB-read pairs) wherever it was
   undercounted (`llm-usage.md` row 88, prompt 178).
2. **Wrong noqa id (🟡).** `llm-usage.md` row 88 said `load_document`'s
   sites keep `ValueError` with `# noqa: TRY400`; corrected to `# noqa:
   TRY004` (the rule actually being suppressed there).
3. **Misattributed site (🟡).** The report's `PLW1510` paragraph named
   `devtools/mutation_check.py:1565` as `_shrink_counts`; it is
   `_collect_count` (def `:1547`, the `subprocess.run` call `:1563`) —
   `_shrink_counts` is a different function entirely. Corrected, both the
   function name and the line number.
4. **Stale line citations (🟡).** Every `file:line` citation in the T3
   section re-derived against the current tree via `grep -n`, not memory:
   `bot.py` 659/686 (was 646/680), 1447/2008/2081 (was 1437/1998/2071),
   1498/1536/1996/2020 (was 1485/1521/1983/2007); `tools.py` 1245/1482
   (was 1242/1479) and 562/579/603 (was 562/578/601, not itself named by
   the brief but caught by the same re-derivation pass); `devtools/
   dashboard.py` 98/106/108 (was 91/99/101); `tracing.py` verified (see
   finding 7 — the revert itself moves this citation again, to `:106`).
5. **Never-list placement (🟡).** `pyproject.toml`'s 13-row never/not-now
   comment block had ended up under `[tool.ruff.lint.per-file-ignores]`;
   moved back directly under `[tool.ruff.lint]`, above the per-file-ignores
   table, where `select` itself lives.
6. **Undisclosed brief edit (🟡).** `acd373a` carried a renumbering edit to
   `docs/spec/task-briefs/v193-T3.md` (prompt numbers, entry count) that
   the coordinator had staged before the task started, with no disclosure
   sentence at commit time. One added to the report's T3 section, naming
   who staged it and that the executor committed it unmodified.
7. **`tracing.py:102` `ValueError` → `TypeError` (🟡).** Reverted: the
   commit's own `TRY004` fix split `_validate_attribute_value`'s two
   branches across two exception types for no documented reason (the
   sibling list-of-str check at `:99` still raises `ValueError`;
   `spec-v1.6.0.md:487` only says "anything else raises", no type
   pinned; `T-V160-TRC-09`'s test covers `set_attribute`'s own unrelated
   "unknown key" `ValueError` at `:221`, not this site; nothing catches
   `ValueError` here specifically either way). Back to `ValueError` with
   `# noqa: TRY004` and an inline reason; no test added (the revert path,
   not the keep-and-pin path). The single-line form no longer fits under
   100 chars once `ValueError` and the trailing `noqa` comment are both
   present, so the `raise` itself moved from `:102` to `:106` — the
   report's citation updated to match.
8. **Redaction note (🟡).** Added one paragraph to the report's `TRY400`
   section: `log.exception`'s own traceback and chained context are not
   passed through `redact()` (no logging-layer filter exists,
   `logging.basicConfig` only). Reviewed all 10 adopted sites: no
   registered secret can reach those exception objects today
   (`TelegramError` built from redacted strings; the two `from None`
   re-raises at `bot.py:171`/`bot.py:190` break the httpx-URL exception
   chain; the rest are bare `sqlite3.Error`/`OSError`/config failures) —
   not a live leak, but the `redact(str(exc))` argument at several of
   these `log.exception(...)` call sites now reads as protective when it
   is not. Listed as a v1.10.0 hardening candidate: a redacting
   `logging.Filter` at the root logger.

## Constraints

One commit. Neither `acd373a` nor `6fcf1fc` rewritten. Nothing concurrent
with any mutation run. No push. The review brief itself
(`docs/spec/task-briefs/v193-T3-review.md`) lands in this commit.

## Acceptance

```
uv run --locked ruff check .                # 0
uv run --locked ruff format --check .       # 0
uv run --locked pytest                      # 0, 1609 collected (unchanged --
                                             #   the revert path, no test added)
uv run --locked python devtools/checks.py lint-docs   # 0
<drift script>                              # 114/114, 0 drifted
```

## Stop

If item 7's revert cannot preserve behaviour (nothing does — no test or
caller depends on the `TypeError` this task is undoing); if the erratum
paragraph would require rewriting `6fcf1fc` itself (it does not — the
brief is explicit that the commit body is corrected via erratum, not
rewrite). Neither fired.
