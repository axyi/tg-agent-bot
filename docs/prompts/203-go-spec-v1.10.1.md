# Prompt 203 — v1.10.1 T0: preflight, Stage 0's seven checks, gates 1–7

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only orchestration task (T0's own §16.1
  exemption: *commands only*); no delegation.
- **Harness:** Claude Code (background session)
- **Stage:** T0
- **Owner of:** `docs/prompts/203-go-spec-v1.10.1.md`,
  `docs/reports/report-v1.10.1.md` (skeleton), `data/run-v1101.db` (created
  empty by `init_schema`), `docs/llm-usage.md` (row 113)
- **REQ ids:** REQ-V1101-EC-01, REQ-V1101-EC-02, REQ-V1101-EC-04,
  REQ-V1101-CFG-01, REQ-V1101-REV-04 (Stage 0), REQ-V1101-RUN-02,
  REQ-V1101-RPT-01

## Goal

Run `spec-v1.10.1.md`'s Stage 0 preflight — the seven checks in order,
offline checks 1/2/7 against the already-synced locked environment — then
gates 1–7 on the unchanged tree, record the disclosed exceptions (gate 5
`embeddings` red, gate 7 exit 2), re-measure the test-collection floor,
compute `agent-eval`'s timeout from a measured `t_turn`, and write the
report skeleton with `## Operator inputs` and the ledger-row block.

## Constraints

Commands only — no source, test or config file written this task. The
executor never opens `.env` directly, never prints a secret value (only
`bool(openrouter_api_key)` and `describe()` pairs), and never touches the
operator's own database. `data/run-v1101.db` is the run's own fresh file
(EC-04 precondition 3), proved empty by the storage preflight before any
network call. `--no-verify` never used.

## Acceptance

All seven Stage 0 checks pass (no blocker); `db_empty=True` recorded;
export proof prints the exported `LLM_JUDGE_MODEL`, not `.env`'s; `uv lock
--offline` produces no diff; the re-measured collection count is 1860
(matches the floor; the 1859-vs-1860 discrepancy is NG-06, not
investigated); gates 1–4 and 6 green; gate 5 exits 1 with only
`embeddings` red (`db`, `lmstudio SKIP (not configured)`, `docker`,
`telegram`, `openrouter`, `config` all OK — no `db` red, which would be a
Stage 0 blocker instead); gate 7 exits 2 on the embeddings 401 — both
disclosed and expected per G5-02's T0 exception, so neither spends the
3-cycle repair budget.

## Stop

Any Stage 0 check failing, or any gate-5 line other than `embeddings`
going red (`db` in particular), is a Stage 0 blocker: the run stops and
finalises per REV-04 Stage 0 — no source or test file exists, no version
bump, no tag.
