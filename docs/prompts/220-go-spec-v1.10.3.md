# Prompt 220 — v1.10.3 T0: preflight, Stage 0's seven checks, gates 1–5+7, EC-02 inventory

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only orchestration task (T0's own §13.1
  exemption: *commands only*); no delegation.
- **Harness:** Claude Code (background session)
- **Stage:** T0
- **Owner of:** `docs/prompts/220-go-spec-v1.10.3.md`,
  `docs/reports/report-v1.10.3.md` (skeleton), `data/run-v1103.db`
  (already present, schema-initialised, proved empty), `docs/llm-usage.md`
  (row 131)
- **REQ ids:** REQ-V1103-EC-01, REQ-V1103-EC-02, REQ-V1103-EC-04,
  REQ-V1103-INS-01, REQ-V1103-GATE-01, REQ-V1103-REV-04 (Stage 0),
  REQ-V1103-RPT-01

## Goal

Run `spec-v1.10.3.md`'s Stage 0 preflight — the seven checks in order,
offline checks 1/2/7 against the already-synced locked environment, check 6
with its judge≠chat assertion and single INS-01 fallback — then gates 1–5
and 7 on the unchanged `636a281`-based tree (gates 6 and 8 not run),
re-measure the test-collection floor and `len(MUTATIONS)`, run EC-02's T0
inventory (the `grep -rn` hit list over `tests/`, the plain/escaped `rg`
pin search, the five-symbol reference inventory) and reconcile it against
EC-02's exhaustive 19-row amendment table and the "verified unaffected"
list, and write the report skeleton with `## Operator inputs`, the
attempt log, `## T0 — preflight` with T0's own delegation bullet, and a
ledger-row block.

## Constraints

Commands only — no source, test or config file written this task. The
executor never opens `.env` directly, never prints a secret value (only
`bool(openrouter_api_key)` and `describe()` pairs), and never touches the
operator's own database — `data/run-v1103.db` is the run's own file,
already pointed to by `.env`'s `DB_PATH` (an operator-side precondition
satisfied before this prompt started), proved empty by the offline
storage preflight before any network call. `--no-verify` never used.

## Acceptance

All seven Stage 0 checks pass (no blocker); `db_empty=True` recorded;
`uv lock --offline` produces no diff and `git diff --stat 636a281 --
pyproject.toml uv.lock` is empty; the re-measured collection count is
2170 (the floor); `len(MUTATIONS) == 139`; gates 1–4 green (2169
passed/1 skipped); gate 5 all-green (`config`/`db`/`docker`/`telegram`/
`embeddings`/`openrouter` OK, `lmstudio` SKIP); gate 7 green (`hybrid:
recall@5=1.000`; first invocation hit a transient rerank 429 on one item,
the second invocation under `REQ-V1102-GATE-01`'s transient rule passed
clean — 1 of the ≤2 allowed re-invocations used; the advisory
conversation-aware smoke fails are non-blocking, NG-07-equivalent).
EC-02's T0 inventory hit list is reconciled against the spec's 19-row
amendment table and verified-unaffected list.

## Stop

Any Stage 0 check failing, or any gate-5 line other than the disclosed
`lmstudio SKIP` going red (`db` in particular), is a Stage 0 blocker: the
run stops and finalises per REV-04 Stage 0 — no source or test file
exists, no version bump, no tag.
