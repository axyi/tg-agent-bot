# Prompt 212 — v1.10.2 T0: preflight, Stage 0's seven checks, gates 1–5+7, EC-02 inventory

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only orchestration task (T0's own §12.1
  exemption: *commands only*); no delegation.
- **Harness:** Claude Code (background session)
- **Stage:** T0
- **Owner of:** `docs/prompts/212-go-spec-v1.10.2.md`,
  `docs/reports/report-v1.10.2.md` (skeleton), `data/run-v1102.db`
  (already present, schema-initialised, proved empty), `docs/llm-usage.md`
  (row 124)
- **REQ ids:** REQ-V1102-EC-01, REQ-V1102-EC-02, REQ-V1102-EC-04,
  REQ-V1102-GATE-01, REQ-V1102-REV-04 (Stage 0), REQ-V1102-RPT-01

## Goal

Run `spec-v1.10.2.md`'s Stage 0 preflight — the seven checks in order,
offline checks 1/2/7 against the already-synced locked environment — then
gates 1–5 and 7 on the unchanged `ccab5d7`-based tree (gates 6 and 8 not
run), re-measure the test-collection floor and `len(MUTATIONS)`, run
EC-02's T0 inventory (the `grep -rn` hit list over `tests/`, the
plain/escaped `rg` pin search, the five-symbol reference inventory) and
reconcile it against EC-02's exhaustive amendment table, and write the
report skeleton with `## Operator inputs`, the gate-7 attempt log and a
ledger-row block.

Before this task's own commands, one operator-facing decision was
resolved with the user (not derivable from the spec alone): `REQ-V1102-
GATE-02`'s T5 procedure ("stage the intended files, record `git
write-tree`, run gate 6, commit, assert `HEAD^{tree}` equality") is
unexecutable as literally written against the pre-existing v1.9.3
dirty-tree guard (`devtools/mutation_check.py:1983-2016`, invoked
unconditionally over all of `MUTATIONS` regardless of `--select`, and
`devtools/mutation_check.py` is itself already a target path of seven
existing entries) — any working-tree edit to add the six `v1102-*`
entries before commit trips "mutation runner refuses to start" on the
very first invocation. The user chose, explicitly: commit the six entries
and the `mutation-all` count/anchor edit first (the `v1.10.1` T6a
precedent, commits `4830039`→`8098aa7`), then run the `--select v1102-`
calibration and the full gate-6 run on the already-clean, committed tree.
This is a disclosed deviation from GATE-02's literal stage-then-commit
order, applied at T5, recorded here so T5's brief and the final report
both carry the same resolution.

## Constraints

Commands only — no source, test or config file written this task. The
executor never opens `.env` directly, never prints a secret value (only
`bool(openrouter_api_key)` and `describe()` pairs), and never touches the
operator's own database — `data/run-v1102.db` is the run's own file,
already pointed to by `.env`'s `DB_PATH` (an operator-side precondition
satisfied before this prompt started), proved empty by the offline
storage preflight before any network call. `--no-verify` never used.

## Acceptance

All seven Stage 0 checks pass (no blocker); `db_empty=True` recorded;
export proof prints the exported `LLM_JUDGE_MODEL`, not `.env`'s; `uv lock
--offline` produces no diff and `git diff --stat ccab5d7 -- pyproject.toml
uv.lock` is empty; the re-measured collection count is 2035 (the floor);
`len(MUTATIONS) == 133`; gates 1–4 green (2034 passed/1 skipped); gate 5
all-green (`config`/`db`/`docker`/`telegram`/`embeddings`/`openrouter` OK,
`lmstudio` SKIP — no `db` red, which would be a Stage 0 blocker); gate 7
exits 0, `hybrid: recall@5=1.000` (the advisory TOOL-06/context-proof
smoke fails are non-blocking, NG-07) — no v1.10.1-style expected red this
release (GATE-01: "Expected at T0 ... no v1.10.1-style expected red").
EC-02's T0 inventory hit list is reconciled against the spec's amendment
table; exactly one hit found outside it —
`tests/test_v1101_gates.py:254-256`
(`test_lint_docs_report_path_repointed_to_v1101`, pinning
`"docs/reports/report-v1.10.1.md"`) — recorded as a T0 EC-02 amendment,
closed before T1, to be re-pinned at T3 alongside the two already-listed
`report_path` sites.

## Stop

Any Stage 0 check failing, or any gate-5 line other than the disclosed
`lmstudio SKIP` going red (`db` in particular), is a Stage 0 blocker: the
run stops and finalises per REV-04 Stage 0 — no source or test file
exists, no version bump, no tag.
