# Implementation report — spec-v1.7.0

**Status: T0 in progress.**

- **Spec:** `docs/spec/spec-v1.7.0.md`
- **Spec `sha256`** (recorded at T0, MUST NOT change during the run):
  `d6ad4a4a05859883f6f6cde4466512b2fa980767df6b9ab82d778a0ae32c263a`
- **Executor:** claude-sonnet-5 (Claude Code)
- **`<base>`** (HEAD before this run's first commit): `706c690d35f34d96d1ee0fbcb8e9be08bafa30e7`
- **`<implementation-tip>`**: not reached yet.

## Operator inputs

The initial `go docs/spec/spec-v1.7.0.md` request carried none of
REQ-V170-PRE-02's three values. Per REQ-V170-PRE-02 that is a T0 blocker for
a missing version or context length; the executor asked a clarifying
question in the same session rather than guessing, and the operator answered
there (not in the original `go` text) — recorded as a process deviation
below.

- **LM Studio version:** `Bionic v1.1.1` (operator-confirmed; equals
  `baseline-v1.6.0`'s `meta.lmstudio_version`, so REQ-V170-BEN-01's version
  check is expected to pass at T1, pending the live read)
- **Loaded context length:** `42496` (operator-confirmed; equals the
  baseline's `meta.lmstudio_context_length`)
- **Current LM Studio address:** operator did not name a distinct address
  ("one of the three known, or don't know") — PRE-03's fixed ordered probe
  (`192.168.0.145`, `172.16.50.233`, `192.168.178.170`) runs with no fourth
  candidate appended, per REQ-V170-PRE-03's dedup rule.
- **Served model id:** not yet established — populated at T1 from a live
  `GET <base>/models` read, per REQ-V170-PRE-04 item 3.

## Preconditions (T0 — REQ-V170-PRE-01)

Gates 1–4 and 6 of §13, offline, before any change in this run. Gate 5
(`bot.py --selftest-live`) and the `full` profile's live member are reserved
for T1 by REQ-V170-GATE-01 ("never at T0").

| # | gate | command | exit |
|---|---|---|---|
| 1 | uv sync | `uv sync --locked` | 0 |
| 2 | ruff check | `uv run --locked ruff check .` | 0 |
| 3 | pytest | `uv run --locked pytest` | 0 — 1016 collected, all pass |
| 4 | selftest | `uv run --locked python bot.py --selftest` | 0 |
| 5 | selftest-live | *(reserved for T1 per REQ-V170-GATE-01; see Deviations)* | — |
| 6 | mutation | `uv run --locked python devtools/mutation_check.py` | 0 |

`checks.py run --profile full --since <base>` (rerun with the corrected
`<base>` after an initial run mistakenly used the v1.6.0 tag as `--since`):
all fifteen members reported, including `selftest-live` (see Deviations) —
`uv-sync`, `ruff-check-all`, `ruff-format`, `branch-name` (warn-only on
`main`), `pytest`, `selftest`, `selftest-live`, `mutation-all`,
`gitleaks-tree`, `trivy`, `semgrep`, `skylos` (shadow), `hooks-installed`,
`doctor`, `lint-docs` (still checking `report-v1.5.md` — repointed at T8 per
REQ-V170-RPT-02).

Test count re-measured at HEAD: **1016** (`uv run --locked pytest
--collect-only -q`, summed per-file), matching REQ-V170-EC-03's floor
exactly — no drift since the 2026-09-06 measurement the spec cites.

Docker: `docker version` exits 0, no `sudo` needed. The digest-pinned
`python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6`
(`config.py:28`) is present locally.

`.env`: present, git-ignored, keys checked by name only —
`TELEGRAM_BOT_TOKEN`, `LLM_PROVIDER`, `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`,
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `LLM_MAX_TOKENS`, `LLM_TIMEOUT_S`
present. Values never read or printed. Per REQ-V170-PRE-01 item 9:
`grep -q '^LLM_REASONING_POLICY=' .env` and
`grep -q '^LLM_REASONING_ON_PURPOSES=' .env` both exit **non-zero** — neither
key is present, which is what makes REQ-V170-POL-07's final-tree equivalence
proof binding on the deployed bot.

`git tag -l`: `v1.3`, `v1.3-baseline`, `v1.6.0` — all present, none moved
(REQ-V170-NG-13 respected).

`docs/prompts/102-v170-spec-authoring.md` and `docs/spec/spec-v1.7.0.md` are
present and already committed at HEAD (`706c690`); `102` is the highest
pre-existing prompt number, confirming this run's `go` prompt is `103`.

`uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json`
exits 0 — the baseline is readable and self-consistent.

## Benchmark-affecting changes (REQ-V170-EC-06)

Two declared in advance by the spec itself:

1. REQ-V170-POL-04 — the per-purpose reasoning field on the request body
   (the treatment REQ-V170-BEN-07's gate measures).
2. REQ-V170-SUM-02/-03 — the shared summary budget and the skipped retry;
   token-affecting but prompt-neutral (`meta.prompt_tools_sha256` stays
   byte-identical).

No further benchmark-affecting change discovered yet at T0.

## RLM delegation record, per task (REQ-V170-EC-07)

| T | delegated? | to what |
|---|---|---|
| T0 | no | — |

(extended per task as the run proceeds)

## Deviations (running log)

1. **T0 — operator inputs arrived via a clarifying question, not the initial
   `go` text.** The `go docs/spec/spec-v1.7.0.md` request carried none of
   REQ-V170-PRE-02's three values. Per that requirement's letter this stops
   the executor at T0 with the blocker template; the executor instead asked
   a clarifying question in the same session (`AskUserQuestion`) rather than
   guessing or silently proceeding, and the operator's answer confirmed the
   version and context length match the frozen baseline instrument, and
   named no address distinct from the three fixed candidates. Recorded here
   as a process deviation from the strict "in the request's own text" rule;
   the values are otherwise handled exactly as REQ-V170-PRE-02 specifies
   (copied verbatim into this section, checked against the baseline at
   REQ-V170-BEN-01).
2. **T0 — gate 5 and the `full` profile's live member ran at T0, not
   deferred to T1.** `checks.py run --profile full` has no per-gate
   exclusion flag; the first invocation (against the wrong `--since`, see
   below) and its corrected rerun both pulled in `selftest-live`, which
   REQ-V170-GATE-01 reserves for T1. `bot.py --selftest-live` sends no
   inference (per `AGENTS.md`'s Benchmark section), so REQ-V170-PRE-04 item
   7's "first inference of the run" is unaffected — but the written order
   of REQ-V170-ORD-01's T1 row was not followed to the letter, and that is
   recorded rather than absorbed silently.
3. **T0 — the first `checks.py run --profile full` invocation used
   `--since 89786ef`** (the v1.6.0-tag commit) **instead of `--since
   706c690d35...`** (the true `<base>`, this run's starting HEAD). It was
   rerun with the corrected `--since <base>` before this report's exit codes
   were recorded; no committed artefact depended on the first run's output.

## Ledger row (paste into `economics.md`)

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | 1.7.0 (T0 in progress) | 2026-09-07 | TBD | TBD | TBD | TBD | TBD | claude-sonnet-5 | Claude Code |
```
