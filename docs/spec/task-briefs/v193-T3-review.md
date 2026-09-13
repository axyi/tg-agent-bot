# v1.9.3 T3 — clean-context review findings to close (prompt 179, one commit)

Review of `acd373a` + `6fcf1fc` (opus, clean context): behaviour preserved
at every one of the 14 checks (ISC004 21 sites byte-identical, PLW1510 16
sites correct, SIM105/117 exception sets and enter/exit order identical,
FURB192/RUF007/PERF401/RUF005 equivalent, drift 114/114, re-derived entry
killed). No 🔴. One 🟠 and seven 🟡 — all paperwork/placement. Close in
**one commit** `docs: T3 review findings -- TRY400 tally, citations,
placement (v1.9.3)`, prompt `docs/prompts/179-v193-t3-review-findings.md`,
llm-usage row 89. Do not rewrite the two reviewed commits.

1. 🟠 TRY400 tally is 7 adopted / 9 kept in the report, llm-usage row 88,
   prompt 178 and the `6fcf1fc` commit body; the tree and the report's own
   per-site list say **10 adopted** (`bot.py` ×3, `dashboard_server.py` ×2,
   `devtools/bench.py` ×5) / **6 kept** (`bot.py` ×4, `tools.py` ×2). Fix
   the count everywhere it is written (the commit body via an erratum
   line in the report's T3 section, not a rewrite); "three `devtools/bench.py`
   failures" → five.
2. 🟡 llm-usage row 88: `load_document` sites kept `ValueError` with
   `# noqa: TRY004`, not `TRY400`.
3. 🟡 Report PLW1510 per-site list: `devtools/mutation_check.py:1565` is in
   `_collect_count` (def `:1547`, call `:1563`), not `_shrink_counts`; the
   quoted docstring is `_collect_count`'s.
4. 🟡 Per-site line citations in the report resolve on neither base nor
   head commit — re-derive every `file:line` in the T3 section against the
   current tree (`grep -n` each; do not trust memory): `bot.py` 659/686,
   1447/2008/2081, 1498/1536/1996/2020; `tools.py` 1245/1482;
   `devtools/dashboard.py` 98/106/108; `tracing.py` 102 — verify these too.
5. 🟡 `pyproject.toml`: the 13-row never/not-now comment block (`:60-77`)
   now sits under `[tool.ruff.lint.per-file-ignores]` (`:53`); move it back
   directly under `[tool.ruff.lint]` where `select` lives, above the
   per-file-ignores table.
6. 🟡 `acd373a` rewrote `docs/spec/task-briefs/v193-T3.md` (prompt numbers,
   entry count) without saying so: one disclosure sentence in the report's
   T3 section (the coordinator staged that renumbering before the task; the
   executor committed it — say that).
7. 🟡 `tracing.py:102` `ValueError` → `TypeError` (TRY004) is a public
   exception-type change from `set_attribute`'s validator; nothing catches
   it (30 call sites, none `except ValueError`; `spec-v1.6.0.md:487` says
   only "anything else raises"; `T-V160-TRC-09` covers the unknown-key
   `ValueError` at `:99`, untouched). Either revert that one site to
   `ValueError` with `# noqa: TRY004 -- <why: the validator's two branches
   must raise one type>` **or** keep `TypeError` and add a test pinning it
   plus a one-line spec-delta note. Pick the revert unless the report can
   argue the split is deliberate — it cannot, so revert.
8. 🟡 `log.exception` at the 10 adopted sites logs the exception's own line
   and any chained context without passing through `redact()`; no
   logging-layer filter exists (`bot.py:1966` plain `basicConfig`). The
   reviewer checked every site: no registered secret can reach those
   exception objects today (`TelegramError` built from redacted strings,
   `from None` at `bot.py:167/190` breaks the httpx-URL chain, the rest are
   `sqlite3.Error`/`OSError`/config failures). Add that sentence to the
   report's TRY400 paragraph — `redact(str(exc))` in those calls now looks
   protective and is not — and list it as a v1.10.0 hardening candidate
   (a redacting `logging.Filter`).

After any amend or added commit, re-read every place a count or hash is
named. Acceptance, sequential: `ruff check .` 0; `ruff format --check .` 0;
`pytest` 0 (item 7 may add a test: report the count); `checks.py lint-docs`
0; drift script 114/114. Return the commit hash and exit codes only.
