# Prompt 62 — spec-v1.5 T18: provisional report, post, usage rows

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** REQ-V15-RPT-02 names every element explicitly except
  item 4's tip SHA; the judgment calls were choosing a consistent,
  defensible definition of "bug" for the ledger row's count (review/
  testing-discovered defects, not every documentation gap a task was
  itself scoped to fix), and pulling fresh live evidence (a real
  `checks.py run --profile full --since <base>`, a real `skylos` run)
  rather than reusing stale per-task numbers where the two could differ
- **Harness:** Claude Code
- **Stage:** T18
- **Owner of:** `docs/reports/report-v1.5.md` (Gates table, skylos
  promotion judgement, Review section evidence, Bugs enumeration,
  Ledger row, header/status lines), `docs/reports/tg-post-v1.5.md`
  (new), `docs/llm-usage.md` (rows 38-41 + Σ), `docs/prompts/
  62-v15-t18-report.md` (new)
- **REQ ids:** REQ-V15-RPT-01, REQ-V15-RPT-02, REQ-V15-RPT-03,
  REQ-V15-RPT-04

## Goal

Land the provisional `report-v1.5.md` — every REQ-V15-RPT-02 element
except item 4's `<implementation-tip>` SHA and T19's evidence, ledger
row included — plus `tg-post-v1.5.md` and `docs/llm-usage.md` rows. This
commit's own SHA becomes `<implementation-tip>` per REQ-V15-ACC-04.

## Constraints

- No self-referential SHA: this commit cannot know or claim its own
  hash. The `<implementation-tip>` line stays a forward reference to
  T19's evidence-only commit.
- The ledger row's every cell is filled from this run's own evidence —
  no `TBD`, no placeholder (REQ-V15-RPT-01).
- `docs/llm-usage.md` rows are appended, never a headerless fragment.
- `tg-post-v1.5.md` is Russian and under 1500 characters by `wc -m`.

## Acceptance

- `uv run --locked python devtools/checks.py lint-docs` exits 0 (the
  ledger-row placeholder that blocked it through T17 is now filled).
- `wc -m docs/reports/tg-post-v1.5.md` recorded in the report, under 1500.
- The Gates (§14) table lists all 18 config gates plus the six
  `AGENTS.md` verbatim commands with real measured exit codes, not
  assumed ones.
- `uv run --locked ruff check .`, the full `uv run --locked pytest`
  suite, `bot.py --selftest`, `bot.py --selftest-live` and
  `devtools/mutation_check.py` all exit 0.

## Stop

If any RPT-02 element's real value cannot be measured directly (rather
than assumed or copied from an earlier, possibly-stale task section),
stop and measure it live before writing the cell — a wrong ledger row
is worse than a slow one.
