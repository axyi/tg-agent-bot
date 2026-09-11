# Implementation report — spec-v1.9.0

**Status: T1 complete, run in progress.**

- **Spec:** `docs/spec/spec-v1.9.0.md`
- **Spec `sha256` at T0:** `619198899cb99bafe7f0fd0aed6b41a71fbf7df36849cec27803ec637d4ce52e`
- **Delta:** `docs/spec/spec-v1.9.0-delta-1.md` (§1's gate matrix, §11's test table,
  Appendix A's assignment traceability, Appendix B), `sha256`
  `5a34fed88431a6122ffaeefb47256a97de61a695b3c82592a69873a73661b1d0`
- **Handoff:** `docs/handoff-v1.9.0.md`
- **Executor:** claude-sonnet-5 (Claude Code)
- **`<base>`** (HEAD before this run's first commit): `d6c13124d8108d6ca23900b91ef30d27d95fc6fc`
- **`<implementation-tip>`**: not yet reached (T12's commit)
- **Final test count (RPT-02 item 2):** T0 floor **1220** (`AGENTS.md:146`'s
  stated figure — no drift); final count not yet reached.
- **Task-brief files written (RPT-02 item 4):** none yet (T0 is *artefacts
  only*, no brief needed per its own §15.1 row).
- **Benchmark rule (RPT-02 item 6, REQ-V190-EC-06): fires.** This release
  changes both `tool_specs()` (a fourth tool, REQ-V190-TOOL-01) and
  `SYSTEM_PROMPT` (one rule line, REQ-V190-TOOL-04), so
  `meta.prompt_tools_sha256` changes. T0's baseline run: tag
  `v190-baseline`, `docs/assets/bench/v190-baseline.json`. T11's candidate
  run and `docs/reports/bench-v190.md` not yet reached.
- **`--no-verify` attestation (RPT-02 item 12):** No commit or push in this
  run used `--no-verify` or any other hook bypass. Evidence:
  `checks.py replay --range <base>..<implementation-tip>` at T13.

## Operator inputs

The `go` request text, verbatim:

```text
go docs/spec/spec-v1.9.0.md
Operator inputs: EMBEDDING_MODEL=<id из GET /v1/models>, EMBEDDING_DIM=<int>
```

The request carried the handoff's unfilled placeholder template rather than
literal values. Per REQ-V190-EC-04, `EMBEDDING_MODEL`/`EMBEDDING_DIM` are
operator-supplied text, required as a pair (D3), and load-bearing for the
one authorised schema migration's DDL (`float[DIM]`) — not a value the
executor may pick on its own default judgement. The executor did what T0's
own preflight needed anyway: probed the three known GPU-box addresses
(`reference-lmstudio-endpoints`) — only `192.168.0.145:1234` answered — read
its `GET /v1/models` listing (one embedding-capable model:
`text-embedding-nomic-embed-text-v1.5`), made one live `POST …/embeddings`
call and measured the real vector length (768), then presented that
concrete `model:dim` pair to the operator via `AskUserQuestion` rather than
asking them to fill in the template blind. The operator confirmed:

**EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5, EMBEDDING_DIM=768**

## Preconditions (T0 — REQ-V190-EC-01, EC-11 row T0)

Six gates of §12, offline except gate 5, run on the unchanged tree before
any change in this run (gate 7, `rag-eval`, is *n/a* at T0 — it does not
exist until T8).

| # | gate | command | exit | note |
|---|---|---|---|---|
| 1 | uv sync | `uv sync --locked` | 0 | |
| 2 | ruff check | `uv run --locked ruff check .` | 0 | |
| 3 | pytest | `uv run --locked pytest` | 0 | 1219 passed, 1 skipped = 1220 |
| 4 | selftest | `uv run --locked python bot.py --selftest` | 0 | |
| 5 | selftest-live | `uv run --locked python bot.py --selftest-live` | 0 | config/db/docker(29.8.0)/telegram/lmstudio/openrouter all OK, no re-pin needed — `192.168.0.145` unchanged from v1.8.0's last known-good address |
| 6 | mutation_check.py | `uv run --locked python devtools/mutation_check.py` | 0 | 98 mutations, 98 killed, 0 survived, 0 errored, 0 drifted |

Also at T0: `uv run --locked python devtools/checks.py doctor` →
`[PASS] doctor: all tools at pin, hooks installed`.
`uv run --locked python devtools/install_hooks.py --check` →
`install_hooks.py --check: hooks installed correctly`.

**Test floor:** `pytest --collect-only -q` re-measured at `<base>` = **1220**,
matching `AGENTS.md:146`'s stated figure exactly — no drift, floor stays 1220.

## T0 preflight record (RPT-02 item 9 — REV-04 Stage 0)

The exact seven-step reversible sequence, in order:

1. `pyproject.toml` and `uv.lock` copied aside into a `tempfile.mkdtemp()`
   directory (`/tmp/tmpj51p2wkm`) — removed at the end of this step (see 5–7).
2. The five pins of EC-01 (`sqlite-vec==0.1.9`, `pypdf==6.18.0`,
   `python-docx==1.2.0`, `rank-bm25==0.2.2`, `snowballstemmer==3.1.1`) added
   to `pyproject.toml` in the working tree only.
3. `uv lock` (23 packages resolved; new: `sqlite-vec`, `pypdf`,
   `python-docx`, `rank-bm25`, `snowballstemmer`, plus transitive `lxml`
   (python-docx), `numpy` (rank-bm25), `typing-extensions` — no dependency
   beyond the five and their transitive closure), then `uv sync --locked`
   (8 packages installed).
4. Preflight check, run as the preflight command itself specifies (the
   unchanged `storage.connect` does not load the extension yet): opened a
   connection through `storage.connect` on a fresh `tempfile.mkdtemp()`
   file, then `conn.enable_load_extension(True); sqlite_vec.load(conn);
   conn.enable_load_extension(False)`, then `select vec_version()` →
   **`v0.1.9`**.
5. Both saved files restored over the working tree.
6. `uv sync --locked` on the restored tree (8 packages uninstalled, back to
   the base 15).
7. `git diff --exit-code` → **clean**. The `tempfile.mkdtemp()` backup
   directory (`/tmp/tmpj51p2wkm`) removed.

Then, only after step 7 passed:

- **(2)** `GET http://192.168.0.145:1234/v1/models` lists
  `text-embedding-nomic-embed-text-v1.5` — present.
- **(3)** `POST http://192.168.0.145:1234/v1/embeddings` with
  `{"model": "text-embedding-nomic-embed-text-v1.5", "input": ["preflight"]}`
  returned exactly **one** vector of **768** floats, matching
  `EMBEDDING_DIM` exactly.

All three checks passed; no REV-04 Stage 0 blocker fired.

## Benchmark: `v190-baseline` (REQ-V190-EC-06)

`devtools/bench.py run --tag v190-baseline --repeats 3` on the unchanged
tree, run only after the reversible sequence's `git diff --exit-code` had
passed. Provider `lmstudio`, model `qwen/qwen3.8-27b`, 89 calls, 0 failed at
the call level, wall 3572s, cost $0.0918 (reference pricing). Output:
`docs/assets/bench/v190-baseline.json`.

**Deviation — S13 (`multi-step-exec`) did not complete cleanly.** In the
canonical combined run (S01–S13 sequential, `--repeats 3`), S13 aborted on
timeout at its 600s default (`ABORTED: timeout:S13-1`), leaving the run at
36/37 successes (97.3%) and exit code 0 (`bench.py`'s aborted-scenario
handling records the abort and continues rather than wiping the whole run
— the wipe bug this memory once tracked is confirmed fixed). Two isolated
re-runs (`--only S13`, `--timeout-s 900` and `--timeout-s 700`) were tried
to get a clean measurement per the project's own "split timeout-prone
scenarios into their own invocations" lesson; both isolated re-runs
completed fast (~44s) but failed all 3 repeats on **checks**, not timeout
(`exec not called`, `pattern not found`) — a different failure mode than
the in-sequence run. This is read as pre-existing flakiness of this
scenario against this quantised model/box combination that depends on
run context (in-sequence vs. isolated), reproduced on the **unchanged**
base tree, and out of this release's scope to fix (`devtools/bench.py` and
its scenarios are NG-03, the frozen v1.7.0 machinery). The two isolated
probe outputs were discarded (not part of the canonical artefact set);
`docs/assets/bench/v190-baseline.json` — the single required invocation
the spec names — is what T11's candidate run will be compared against.
Per REQ-V190-EC-06, the benchmark delta is **reported, not gated**, so this
does not block T0 or any later task.

## Per-task delegation record (REQ-V190-EC-07 item 6)

| T | delegated? | to what | map vs actual |
|---|---|---|---|
| T0 | no — *artefacts only* | — | matched map |
| T1 | yes | general-purpose subagent | matched map |

(Filled in as each task lands.)

## T1 — storage and schema (REQ-V190-STO-01…05)

Commit `b84f524`. Test-first: `T-V190-STO-01…09`, `T-V190-SEC-02/-03/-05/-06`
(storage half) — 27 new tests (`tests/test_v190_storage.py`,
`tests/test_v190_isolation.py`). `pytest --collect-only -q` = **1247**
(1220 floor + 27). Gates run at this task: `ruff check .` 0, `pytest` 0,
`bot.py --selftest` 0 (mutation and live gates deferred to T9/T11 by
design).

**Disclosed erratum — REQ-V190-EC-03's amendment table was incomplete
(operator-ratified).** T1 found that `SCHEMA_VERSION` moving 5→6 (itself a
MUST) breaks a hardcoded literal in three test files EC-03's exhaustive
amendment table does not list: `tests/test_v170_reasoning.py`,
`tests/test_v160_observability.py`, `tests/test_summary.py` — the same
class of break the table already authorises for `tests/test_observability.py`.
The implementing subagent applied the identical mechanical fix (literal
`5`→`6`, future-boundary `6`→`7`) at these three additional sites,
disclosed each with an inline erratum comment, without weakening any
test's assertion or intent. This mirrors the repository's own precedent
(`tests/test_summary.py`'s pre-existing comment: "authorised by the
operator, prompt 107" for the identical v1.6.0→v1.7.0 case). The
orchestrator reviewed the diff line-by-line, confirmed no logic was
altered (version literals only), and put the question to the operator via
`AskUserQuestion` before continuing to T2; the operator ratified it as an
operator-authorised erratum, retroactively, in this session.

**Other disclosed deviations (T1's own prompt file,
`docs/prompts/143-v190-t1-storage-schema.md`, carries the full reasoning):**
`_DOCUMENTS_DDL` is kept as a standalone constant rather than folded into
`_SCHEMA`'s unconditional `executescript`, so a failed 5→6 migration can
still leave zero trace of `documents`/`chunks` (`T-V190-STO-09`'s
requirement) — `_SCHEMA`'s script runs outside any transaction and cannot
be rolled back, so concatenating would have broken the negative-migration
guarantee. A real pre-existing-in-this-task bug was found and fixed during
test-writing: `add_vectors`'s `executemany` was passing 2-tuples against a
3-column `INSERT`; fixed to build `(chunk_id, user_id, embedding)` triples
before any commit.

## Assignment checklist (RPT-02 item 8)

Not yet reached — filled in at T13 from the assignment-traceability table
in `docs/spec/spec-v1.9.0-delta-1.md`.

## Eval numbers (RPT-02 item 7)

Not yet reached — filled in at T8's first live `rag-eval` run.

## Pre-existing drift surfaced, not fixed (RPT-02 item 11)

- `README.md`'s `LLM_TIMEOUT_S = 120 s` against `config.py`'s `240` default.
- `AGENTS.md:51-52` still says `/conversations` is "gained in this release".
- `docs/plan.md` stops at v1.6.0 (NG-12) and is stale, not a handoff.

## `docs/llm-usage.md` numbering — a spec/file discrepancy, resolved from the file

§1 REQ-V190-EC-04 and REQ-V190-RPT-04 state the file's last row is 66 and
that the run appends "from 67". The file's actual last row, checked at T0,
is **67** (`spec-v1.9.0 authoring, prompt 141`, added when the authoring
commit landed after that spec text was written — a timing artefact inside
the spec itself, not a run defect). This run's usage rows therefore append
starting at **68**, matching `docs/handoff-v1.9.0.md`'s State section
("continues at row 68") rather than §1's stale citation. Disclosed per the
advisor-recommended practice of reading the cited line and taking what the
file says over either document's assertion.

## Formal lift of REQ-NG-05 / REQ-V1-NG-05 (RPT-02 item 11, EC-13)

Not yet reached — recorded at T10 alongside the README `## Documents (RAG)`
section it also lands in.

## `--no-verify` attestation (RPT-02 item 12)

No commit or push in this run has used `--no-verify` or any other hook
bypass, through T0 (T0 has made no commit yet — this is the first).

## Ledger row (paste into `economics.md`)

Not yet reached — filled in provisionally at T12, de-provisionalised at
T13.
