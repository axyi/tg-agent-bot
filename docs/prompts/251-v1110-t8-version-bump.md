# Prompt 251 — v1.11.0 T8: the version-bump commit

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** a scoped, brief-driven paperwork/identity-test task
  (a version bump, two new frozen-list test files, three repointed pins,
  one missing documentation deliverable) — no architecture decision, no
  cross-file design tradeoff.
- **Harness:** Claude Code (delegated subagent)
- **Stage:** T8 (first commit — the bump; the evidence-only second commit
  is the orchestrator's own next step)
- **Owner of:** `pyproject.toml`, `uv.lock`, `tests/test_v1110_ver.py`
  (new), `tests/test_v1110_inventory.py` (new), `tests/test_v1104_version.py`,
  `tests/test_v190_agents.py`, `README.md`, `AGENTS.md`, and three sites
  discovered during this task, not in the brief's starting list (EC-02
  disclosed amendments): `tests/test_v1102_docs.py`,
  `tests/test_v1104_docs.py` (two functions)
- **REQ ids:** REQ-V1110-VER-01, REQ-V1110-VER-02, REQ-V1110-VER-04,
  REQ-V1110-EC-02, REQ-V1110-EC-03

## Goal

Land spec-v1.11.0 T8's bump commit per `docs/spec/task-briefs/v1110-T8.md`:
`pyproject.toml:3` 1.10.4 -> 1.11.0, `uv lock` regenerated (the one
permitted network call), `tests/test_v1110_ver.py` (four new tests,
`T-V1110-VER-01..04`), `tests/test_v1110_inventory.py` (the frozen
61-pair spec-test inventory, `T-V1110-INV-01`), `tests/test_v1104_version.py`
repointed (one function to a frozen `v1.10.4` tag-blob read, one function's
trailing live-tree literal bumped as a disclosed amendment),
`tests/test_v190_agents.py`'s count-lines pin repointed to T8's measured
figures, and the README/AGENTS.md documentation deliverables.

## Constraints

Gates 1-4 only (`uv sync --locked`, `ruff check .`, `pytest`,
`bot.py --selftest`) — no gate 5, no `mutation_check.py`, `rag_eval.py`,
`agent_eval.py`, no `ruff format`. Never print/quote/commit the two secret
values at `config.py:351`,`:379`. Measure the final collected test count
last, after every other edit, and use that one real number everywhere.

## Acceptance

`T-V1110-VER-01`/`-03` confirmed red on the unbumped tree, green after;
`T-V1110-VER-02`/`-04`/`T-V1110-INV-01` structural (EC-02 carve-out) —
`-02` was green on first execution (empty diff), `-04` was genuinely red
on first execution (the `/documents` sample block did not exist, despite
REQ-V1110-VER-02 naming it a T2 deliverable — T2's own report disclosed
dropping it), `T-V1110-INV-01` was green on first execution once its
61-pair list was written (structural, matches the brief's carve-out).
Both `tests/test_v1104_version.py` functions confirmed red immediately
after the bump, green after repointing; the second function's trailing
`"1.10.4"` -> `"1.11.0"` literal is a disclosed amendment the brief's own
text flagged as needing empirical verification (its docstring only
described the other function's change).

Three more disclosed amendments, found empirically (a full `pytest` run
after the bump + doc edits), not named in the brief's starting file list:
`tests/test_v1102_docs.py::test_t_v1104_rpt_03_agents_md_brief_path_token_is_v1104`,
`tests/test_v190_agents.py::test_t_v1104_rpt_03_agents_md_brief_path_token_is_v1104`
(a second, differently-scoped function of the same name in a different
module), and `tests/test_v1104_docs.py`'s
`test_t_v1104_doc_02_v1104_release_and_gate8_rows_landed_at_t5` (the
`_V1104_ROW` literal's trailing `"; this release"` clause, which moves to
the new `v1.11.0` row) and
`test_t_v1104_doc_03_agents_md_brief_token_is_v1104_waiver_paragraph_unchanged`
(the same brief-path token). All four repoint an AGENTS.md/README.md
literal that T8's own required edits (the brief-path token `v1104-T<N>.md`
-> `v1110-T<N>.md`, the v1.10.4 row's `; this release` clause moving) made
stale — permitted as disclosed amendments under REQ-V1110-EC-03 ("a site
discovered later is a disclosed amendment (PIN-01), not a stop"). None of
the four functions were renamed.

Final collected count: 2384 (`uv run --locked pytest --collect-only -q
-o addopts="" | grep -c '::'`), >= floor + 62 (2311 + 62 = 2373). Gates
1-4 green.

## Stop

Not applicable — every disclosed amendment stayed within EC-02/EC-03's
own allowance (a rewrite-in-place of a pre-existing pin, never a rename,
never a deletion); no repair cycle, no stop route triggered.
