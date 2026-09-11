# Prompt 156 — v1.9.0 T10: docs and config catch-up

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for spec-driven implementation tasks in this run (T1-T9 used the same model).
- **Harness:** Claude Code
- **Stage:** T10
- **Owner of:** `README.md` (`## Documents (RAG)` and its seven subsections, the eval command/numbers table, the two new `## Commands` rows, the `## Limits` rows, the `## Error behaviour` rows, the gate-7-red sentence in `## Tests`); `AGENTS.md` (`## Stack`'s RAG dependency bullet, `## Project layout`'s `rag.py`/`documents.py`/`llm/embeddings.py`/`evals/rag/`/`devtools/rag_eval.py`/`devtools/pdf_fixture.py` bullets, `:82`'s brief-path token, the six-env-var clause); `config/quality_gates.yaml` (`report_path`); `docs/reports/report-v1.9.0.md` (Ledger row section only); `tests/test_v190_agents.py` (new); `tests/test_v170_bench.py` (one renamed test, operator-ratified, see Constraints)
- **REQ ids:** REQ-V190-RPT-01, REQ-V190-RPT-05, REQ-V190-EC-13, REQ-V190-ERR-03

## Goal

Implement RPT-01, RPT-05, EC-13's report/README sentences and ERR-03 end to
end: write README's new `## Documents (RAG)` section (Architecture,
Chunking, Embeddings, Retrieval, Storage, Security, Limitations, in that
order, plus the eval command and T8's actual measured numbers table), add
the `/documents`/`/delete` rows to `## Commands`, the RAG rows to
`## Limits`, the ERR-01 rows (1-7, 10a-c, 11, 13-15) to `## Error
behaviour`, and one sentence recording gate 7's honest red status in two
places (the eval subsection and `## Tests`); make the four narrow,
line-scoped `AGENTS.md` edits (stack, layout bullets, the brief-path token,
the env-var note) without touching `:146`/`:155`'s count-bearing lines
(T12's job); repoint `config/quality_gates.yaml`'s `report_path` to
`docs/reports/report-v1.9.0.md`; and add `tests/test_v190_agents.py`
proving `T-V190-EC-01`'s scope (AGENTS.md names the five RAG dependencies,
the seven-gate block, the `v190-T<N>.md` brief path; README's seven
subsections exist in order). Every number written (chunking constants,
config defaults, the six env var names, the error-table strings) was
spot-checked against `storage.py`, `documents.py`, `rag.py`, `config.py`,
`tools.py`, `bot.py` directly, not copied from the task brief's paraphrase.

## Constraints

`AGENTS.md:146`/`:155` (test count, mutation count) never touched — T12's
job. `.env.example` not touched — RPT-05's clause already satisfied at T2
(all six keys present, verified at `.env.example:90-106`). `docs/spec/`
files read-only. No live gate run this task (gates 5, 7, and
`mutation_check.py` are out of scope per the brief's Acceptance section).
`--no-verify` and any other hook bypass forbidden.

**One operator-ratified EC-03-class extension, uniquely self-precedented.**
`tests/test_v170_bench.py:284` (`test_t_v180_rpt_01_lint_docs_repointed_to_this_release`)
asserted the literal string `"docs/reports/report-v1.8.0.md"` against
`config/quality_gates.yaml`'s `lint-docs.report_path` — a value this task's
own REQ-V190-RPT-01 (MUST) repoints to `report-v1.9.0.md`. This test is
outside REQ-V190-EC-03's exhaustive amendment table (that list is
`SCHEMA_VERSION`-class breaks; this is an RPT-01-repoint-class break), so
per this task's own instructions the executor stopped and reported the
exact mechanical fix rather than applying it. The operator ratified it:
this is the cleanest possible case, since the test's own docstring already
discloses it gets renamed/repointed at every release (naming the
v1.7.0→v1.8.0 precedent explicitly) — expected, recurring, self-documented
behavior, not a new defect. Applied exactly as specified: renamed to
`test_t_v190_rpt_01_lint_docs_repointed_to_this_release`, docstring's
release/task references shifted (v1.8.0/T7 → v1.9.0/T10, predecessor
references shifted accordingly), the asserted path changed to
`"docs/reports/report-v1.9.0.md"`; the `ledger_header` assertion was left
unchanged (unaffected by the repoint).

**A second, smaller disclosed erratum, applied directly without a stop**
(docs-only, mechanically precedented, the *artefacts only* exemption —
not a fresh judgment call): repointing `report_path` also broke
`checks.py lint-docs`'s ledger-row structural check, because
`docs/reports/report-v1.9.0.md`'s "Ledger row" section was still prose
("Not yet reached...") rather than a fenced table row. This is the exact
situation `docs/reports/report-v1.8.0.md`'s own "Disclosed erratum 3"
section already documents and resolves (T0's report skeleton missing the
block, caught by a `lint-docs` repoint, fixed with "a provisional, all-`TBD`
row, structurally valid... same shape T9 will replace with the real row").
Applied the identical fix: a provisional 11-cell all-`TBD` fenced row,
to be replaced with the real row at T12 and de-provisionalised at T13,
per the same precedent.

## Acceptance

`uv run --locked ruff check .` exit 0. `uv run --locked pytest` exit 0 (was
red on the one pre-existing test above before the operator's ratification;
green after). `uv run --locked python bot.py --selftest` exit 0.
`uv run --locked python devtools/checks.py lint-docs` → `[PASS]`.
`tests/test_v180_agents.py` and `tests/test_v190_agents.py` both green.
`pytest --collect-only -q` total **1558** (1537 + 21 new tests in
`tests/test_v190_agents.py`).

## Stop

None outstanding. The one blocking finding this task surfaced
(`tests/test_v170_bench.py:284`, above) was reported to the orchestrator
per this task's own instructions, ratified, and resolved within this same
task/commit rather than deferred.
