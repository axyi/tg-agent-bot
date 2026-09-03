# Implementation report — spec-v1.5

**Status: provisional skeleton, written at T0.** Sections below are filled in
as their owning task lands; each carries a `(T<n>, pending)` marker until
then. This header line is removed once the report is complete (T18/T19).

- **Spec:** `docs/spec/spec-v1.5.md`
- **Executor:** claude-sonnet-5 (Claude Code)
- **`<base>`** (HEAD before this run's first commit): `9ad3047d981b30005f81e15e09d2f02444b8009a`
- **`<implementation-tip>`:** recorded at T18 (a commit cannot contain its
  own SHA — REQ-V15-ACC-04)

## Operator inputs

LM Studio version: not supplied by the operator in this run. Per
REQ-V15-DEP-06 / RPT-02 item 9 this is recorded, not acted on, and blocks
nothing:

> LM Studio version not inspected: LM Studio is outside the repository
> boundary and unchanged by v1.5.

## Preconditions (T0 — REQ-V15-PRE-01, PRE-02)

All six v1.4 gates, run verbatim before any change in this run:

| # | gate | command | exit |
|---|---|---|---|
| 1 | uv sync | `uv sync --locked` | 0 |
| 2 | ruff check | `uv run --locked ruff check .` | 0 |
| 3 | pytest | `uv run --locked pytest` | 0 (728 collected, all pass) |
| 4 | selftest | `uv run --locked python bot.py --selftest` | 0 |
| 5 | selftest-live | `uv run --locked python bot.py --selftest-live` | 0 — `config`, `db`, `docker (29.7.2)`, `telegram`, `lmstudio`, `openrouter` all OK |
| 6 | mutation | `uv run --locked python devtools/mutation_check.py` | 0 — 68 mutations, 68 killed, 0 survived, 0 errored, 0 drifted |

Tool availability, measured 2026-09-03 (matches REQ-V15-PRE-02's table
exactly): Python 3.14.7, uv 0.12.7, ruff 0.16.5, gitleaks 8.24.3, semgrep
1.167.0, trivy not installed, skylos not installed, rtk 0.46.0.

Docker: `docker version` 29.7.2, no `sudo` needed.
`docker image inspect --format '{{json .RepoDigests}}' python:3.13-slim`
→ `["python@sha256:881d80734ee05dca6f7f42dcb080975652a53c7eda9ba1f03bb8da31aa6a6ec2"]`
— matches REQ-V15-IMG-01's recorded outgoing digest exactly; no pull needed.
`python:3.14-slim` not yet present locally (T15 pulls it by digest).

`.env`: present, git-ignored, keys checked by name only —
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_NAME`, `ALLOWED_TG_IDS`, `LLM_PROVIDER`,
`LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`, `LMSTUDIO_CONTEXT_LENGTH`,
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `LLM_PRICE_REF_MODEL` present.
Values never read or printed.

`git --version`: 2.53.0 (≥ 2.9 required by REQ-V15-PRE-01.6).

Network: GitHub and PyPI both reachable (200) at T0 — the three sanctioned
steps (§3.5) are attempted in T2–T7 as scheduled, each step recorded there.

`docs/prompts/43-v14-verify-run-fixes.md` present, confirming this run's
`go` prompt is numbered 44 (REQ-V15-TREE-01's prompt-numbering rule).

## Gates (§14) — full table

(T12, T14, T19 — pending)

## Dependency and tooling refresh (T2–T6, T13 — REQ-V15-DEP-*)

(pending)

## Scanners (T7 — REQ-V15-SCAN-*)

(pending)

## Hook chain (T8 — REQ-V15-HOOK-*)

(pending)

## `checks.py doctor` (T9 — REQ-V15-GATE-03)

(pending)

## RTK project-local hook (T10 — REQ-V15-RTK-*)

(pending)

## Prompt format and lint-docs (T11 — REQ-V15-PRM-*)

(pending)

## Profile wiring, wall-clock and mutation coverage (T12 — REQ-V15-HOOK-04, TST-01)

(pending)

## Python 3.14 bump (T14 — REQ-V15-DEP-01)

(pending)

## Sandbox image digest pin and byte-compared exec smoke (T15 — REQ-V15-IMG-*)

(pending)

## `AGENTS.md` / `docs/plan.md` sync (T16 — REQ-V15-RPT-05)

(pending)

## Review (T17 — REQ-V15-REV-01)

(pending)

## Benchmark-affecting changes (REQ-V15-EC-06)

None discovered so far. Updated if T14 or T15 discovers one; the default
this release ships is "no benchmark run", `baseline-v1.4.json` unchanged.

## RLM delegation record, per task (REQ-V15-EC-07)

| task | crossed a threshold? | delegated? | to what |
|---|---|---|---|
| T0 | no (two mapped files, both under threshold) | no | — |

(rest of the table fills in as each task lands)

## `--no-verify` attestation (REQ-V15-EC-09)

(T19 — pending; `checks.py replay --range <base>..<implementation-tip>`
evidence lands in the T19 evidence-only commit)

## Fix cycles

(running total; 0 used of the 5-cycle budget so far)

## Deviations

None yet recorded at T0.

## Ledger row (paste into `economics.md`)

(T18/T19 — pending; filled once every cell has evidence)

## Verdict

(T19 — pending)
