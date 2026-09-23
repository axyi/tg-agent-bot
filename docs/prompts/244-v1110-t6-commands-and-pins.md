# Prompt 244 — v1.11.0 T6: COMMANDS, setMyCommands, /help, /start, pin repoints

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** a self-contained, precisely-specified feature-plus-pin
  task with several exact-string/rename requirements — matches the model
  used for every other delegated task this run.
- **Harness:** Claude Code (subagent, general-purpose)
- **Stage:** T6
- **Owner of:** `bot.py`, `config/quality_gates.yaml`, `AGENTS.md`,
  `README.md`, `tests/test_v170_bench.py`, `tests/test_v1104_gates.py`,
  `tests/test_v190_agents.py`, `tests/test_v15_standards.py`,
  `tests/test_v1110_sec.py`, `tests/test_v1110_pin.py` (new),
  `tests/test_v1110_ext.py` (new, disclosed amendment beyond this
  brief's own file list), `tests/test_v1101_gates.py`,
  `tests/test_v1102_gates.py`, `tests/test_v1103_gates.py`,
  `tests/test_v1104_docs.py`, `tests/test_routing.py`,
  `tests/test_v12_patch.py`, `tests/test_v1_guardrails.py`,
  `tests/test_v160_dashboard.py`, `docs/reports/report-v1.11.0.md`
- **REQ ids:** REQ-V1110-EXT-01, REQ-V1110-EXT-02, REQ-V1110-PIN-01,
  REQ-V1110-VER-02, REQ-V1110-VER-03, REQ-V1110-NG-11, the rest of
  REQ-V1110-SEC-01 (clauses 1, 2). (`T-V1110-EXT-03` and `T-V1110-PIN-02`
  are test ids satisfied by this work, not separate requirements — see
  spec-v1.11.0.md §14's requirement table.)

## Goal

Close out spec-v1.11.0 §10 and the release's remaining documentation/pin
work: a `COMMANDS` command table registered with Telegram's `setMyCommands`
at startup, `/help` and `/start` both rendering that table, the two
remaining `SEC-01` clauses this task owns, a new frozen-pin negative test
(`T-V1110-PIN-01`/`-02`), and every `report_path`/spec-file/README pin this
release still needs repointed to `v1.11.0` — following the brief at
`docs/spec/task-briefs/v1110-T6.md`.

## Constraints

Do not run gate 5 (`bot.py --selftest-live`), `mutation_check.py`,
`rag_eval.py`, `agent_eval.py` or `bench.py`. Do not run `ruff format`
(only `ruff check .`). Do not rename
`test_t_v1100_ec_01_quality_gates_yaml_repoints_report_path` (its own
docstring keeps the name stable across releases). Do not touch
`tests/test_v1104_gates.py:149,160,169` (unrelated fixture filenames for a
generic lint-docs mechanism test). Never print or quote the two secret
values in `config.py` (`:351`, `:379`).

### Test-first (EC-02) — an honest account, not a uniform claim

**Never red** (implementation-first — `COMMANDS`/`set_my_commands`/
`_handle_help`/the dispatch wiring were written first, against the
existing dispatch chain and `TelegramClient` conventions, then the tests
written against already-working code): `test_t_v1110_ext_01_commands_table_and_setmycommands`
(first failure was a test bug — `_stub_main_startup` recursively rebound
`httpx.Client` to itself, fixed by capturing the real class first),
`test_t_v1110_ext_02_help_and_start` (first failure was a hand-guessed,
wrong header string, fixed by comparing against `render_table`'s real
output), and SEC-01's two new clauses (clause 1's first failure was the
CANARY secret being long enough to get truncated before `redact()` ran,
fixed by shortening it; clause 2 passed first try — the CBQ-05 behaviour
it cross-references was already correct).

**Red for the right reason** (test-first): `test_t_v1110_ext_03_readme_commands_rows`
(red on `/cancel` missing from README's Commands table),
`test_t_v1110_pin_02_readme_limits_and_error_rows` (red on
`Usage: /session <id> (see /sessions)` missing from README's Error
behaviour section — six ERR-01 rows, 11-16, had never been documented),
and the three renamed/repointed `report_path` tests (edited to assert the
new path, run red against the still-unedited `quality_gates.yaml`, then
green after that file's edit).

**Never red, because the check was written after it was already true**:
`test_t_v1110_pin_01_no_retired_literal_in_tests` passed on its first
run — the one genuine trip it found (`test_v190_agents.py`'s docstring
naming four retired numbers in prose) was reworded *before* this file
existed, not discovered by watching it fail.
`tests/test_v190_agents.py:226-235`'s extension (every `COMMANDS` name
has a README row) was likewise written after README already had every
row.

**Stale after this task's own edit, not test-first** — pre-existing tests
this task's own config/doc edits broke as a foreseeable side effect,
found via a full `pytest` run, then fixed to match: the
`test_t_v1102_rpt_01_lint_docs_repointed_to_this_release`-family
functions in `tests/test_v1101_gates.py`/`test_v1102_gates.py`/
`test_v1103_gates.py` (broken by the `quality_gates.yaml` edit);
`tests/test_v1104_docs.py::test_t_v1104_doc_03_agents_md_brief_token_is_v1104_waiver_paragraph_unchanged`
(broken by the `AGENTS.md` sentence addition).

**Left open, disclosed**: `tests/test_v1110_err.py`'s canonical
`test_t_v1110_err_01_error_matrix_strings` still drives only ERR-01 rows
10 and 17 (T5's own). Rows 11-16 are now documented in README but no test
exercises the dispatch behaviour behind them — a gap for whichever task
next extends that same frozen function.

## Acceptance

`T-V1110-PIN-01`, `-02`, `T-V1110-EXT-01`…`-03`, the rest of
`T-V1110-SEC-01` all green. `lint-docs` green. `doctor` green. Gates 1-4
green, run verbatim.

## Stop

An exhausted repair budget on a genuine spec ambiguity, or a gate that
cannot be made green without touching something outside this task's
scope (in which case: disclose and ask, per this project's `AGENTS.md`
"go protocol").
