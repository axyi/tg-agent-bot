# Prompt 155 — v1.9.0 T9: mutation entries and the gate matrix

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for spec-driven implementation tasks in this run (T1-T8 used the same model).
- **Harness:** Claude Code
- **Stage:** T9
- **Owner of:** `devtools/mutation_check.py` (tail only — seven `v190-*` `MUTATIONS` entries); `config/quality_gates.yaml` (`mutation-v190` gate definition, `pre-push` profile membership, `mutation-all` timeout re-measurement); `tests/test_v15_standards.py` (`:1685-1745` — two new `_GATE_MATRIX_LABEL_TO_NAME` labels, the `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` target repoint); `docs/spec/task-briefs/v190-T9.md` (received, committed alongside per repo precedent for prior task briefs)
- **REQ ids:** REQ-V190-EC-10, REQ-V190-EC-12

## Goal

Implement EC-10 and EC-12 end to end: author and land the seven `v190-*`
mutation-gate entries the spec's section 12 table names (RAG-over-documents
per-user isolation for the KNN and BM25 queries, `list_documents` and
`document_id_for`'s owner predicates, the delete path's `vec_chunks`
cleanup, the upload size precheck, and the sources-fallback rendering),
wire a `mutation-v190` gate into `config/quality_gates.yaml`'s `pre-push`
profile with a directly measured timeout, and close the one pre-existing,
expected test failure this run carried forward from T8 —
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` — by
repointing its target file to `docs/spec/spec-v1.9.0-delta-1.md` and
extending the gate-matrix label map with the `mutation-v190`/`rag-eval`
rows T8's `full`-profile addition needed but did not itself carry.

## Constraints

Author each `find` string against the real shipped source (`storage.py`,
`bot.py`, `rag.py`), not the brief's mechanism prose; verify each matches
exactly once (`str.count`) before relying on it. Touch `storage.py`,
`bot.py`, `rag.py` only to the minimal degree needed to make a `find`
string unique — no logic changes (T1/T4/T5/T6/T7 already implemented the
mechanisms this task only proves). Do not edit `docs/spec/spec-v1.9.0.md`
or `docs/spec/spec-v1.9.0-delta-1.md`'s gate-matrix table (already correct,
carrying the `rag_eval.py`/`mutation_check.py --select v190-` rows).
`spec-v1.8.0-delta-1.md` is a released, frozen spec artefact — never edited
even though it still carries the `| gate | pre-commit` header literal (see
Stop). No live gate (`--selftest-live`, `rag_eval.py`) run this task; T11/
T13 own that re-run. `--no-verify` and any other hook bypass forbidden.

## Acceptance

`uv run --locked python devtools/mutation_check.py --select v190-` → 7/7
killed, each `find` matching exactly once. `uv run --locked python
devtools/mutation_check.py` (full, unfiltered) → 105/105 killed, 0
survived/errored/drifted. `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
green. `uv run --locked ruff check .`, `uv run --locked ruff format --check .`,
`uv run --locked pytest`, `uv run --locked python bot.py --selftest` all
exit 0.

## Stop

**1. The first `--select v190-` timing run was contaminated and discarded.**
Before fixing EC-12, `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
was red (T8's own disclosed, expected carry-over). `mutation_check.py`'s
runner is `pytest -x -q`, which stops at the *first* red test regardless of
whether it is the mutation's actual killer — so every "killed" verdict from
that first run was potentially killed by the unrelated, pre-existing
gate-04 failure, not by the named `T-V190-SEC-0x`/`STO-03`/`CMD-02`/
`TOOL-06` test. That run's timing (real=6m16.541s) was discarded as
meaningless; EC-12 was fixed first, then `--select v190-` was re-run clean
(real=8m29.464s, 7/7 killed, each genuinely by its named test) and that
number is what `config/quality_gates.yaml`'s `mutation-v190` timeout is
based on. Any `rag-eval`-in-`full` era mutation-gate measurement recorded
between T8's commit and this fix would carry the same suspicion; checked
`docs/reports/report-v1.9.0.md` for one — its only `mutation_check.py`
(full) row (98/98, 0 survived) is T0's pre-T8 baseline, so nothing in the
contaminated window was found recorded.

**2. `spec-v1.8.0-delta-1.md` left untouched — deviation from the brief's
literal item 4, with reason.** The brief asks to remove the leftover
`| gate | pre-commit` header literal from `spec-v1.8.0-delta-1.md` "if it
still does" carry it — it does, at `:22`. Not changed: `spec-v1.8.0-delta-1.md`
is part of a released spec (`spec-v1.8.0.md:166`, "that exact filename,
never [edited]" and `spec-v1.8.0.md:1263`, "a released spec is never
edited"), and `spec-v1.9.0-delta-1.md:11` cites `spec-v1.8.0-delta-1.md:22-45`
by line range as the provenance of the table it carries verbatim — deleting
those rows would break that citation. The brief's own stated purpose ("so
the parser finds the matrix only in the v1.9.0 delta file") is already
satisfied because `test_v15_gate_04...` now reads only
`spec-v1.9.0-delta-1.md`; the leftover header in the v1.8.0 file is inert
for that test. Flagging for orchestrator sign-off rather than silently
leaving it.

**3. Two stale prose counts noticed, out of this task's file scope, not
fixed:** `AGENTS.md`'s gates section says "98 entries" for the mutation
catalogue (now 105) and "1220 tests" for `pytest` (now TBD collected).
Left for the orchestrator/a docs task, per this prompt's `Owner of` list
not naming `AGENTS.md`.

**4. The T9 subagent's session was interrupted by an infra rate limit
partway through the full `mutation-all` re-measurement; the orchestrator
resumed directly.** One cosmetic ruff line-length fix applied
(`devtools/mutation_check.py:1100`, the `v190-knn-user-predicate-dropped`
entry's `replace` string wrapped to fit under 100 chars — no semantic
change). The orchestrator's own full `mutation-all` re-run measured
real=65m53.309s (higher than this task's own 60m58.865s measurement) —
the higher of the two same-day figures was used for the final
`timeout_seconds` (7910, up from the subagent's own provisional 7320),
per the same shared-machine-variance rationale as every earlier entry in
that comment block.

Offline gates, final: `ruff check .` exit 0. `ruff format --check .`:
72 files would be reformatted — pre-existing repo-wide drift (the
`ruff-format` pre-commit hook step is non-blocking/warn-only for exactly
this reason, confirmed via the hook's own `PASS: legacy: N file(s), would
reformat` output across this whole run), none of it touched by this task,
not fixed here. `pytest` exit 0, **1537 collected**, full suite green
(unchanged from T8's count — this task adds no new tests, only gate/config
wiring and mutation entries). `bot.py --selftest` exit 0.
`mutation_check.py --select v190-` → **7/7 killed**, 0
survived/errored/drifted (clean re-run after the EC-12 fix, see item 1).
`mutation_check.py` (full) → **105/105 killed**, 0 survived/errored/drifted.
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` green.
Everything for this task committed in one commit.
