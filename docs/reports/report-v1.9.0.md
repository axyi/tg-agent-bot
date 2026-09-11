# Implementation report — spec-v1.9.0

**Status: T4 complete, run in progress.**

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
| T2 | yes | general-purpose subagent (+ one follow-up erratum subagent) | matched map |
| T3 | yes | general-purpose subagent (+ one follow-up test-strengthening subagent) | matched map |
| T4 | yes | general-purpose subagent (+ one follow-up erratum subagent) | matched map |

(Filled in as each task lands.)

## T4 — the indexing pipeline (REQ-V190-DOC-04, -05)

Commit `2221543`. 16 new tests (4 storage-side, 12 in new
`tests/test_v190_errors.py`). `pytest --collect-only -q` = **1378**
(1362 + 16). Gates: `ruff check .` 0, `pytest` 0, `bot.py --selftest` 0.

**Cross-task note, not an erratum**: DOC-02's between-PDF-pages
`IndexBudgetExceeded` check (normatively T3's own requirement, §3 lines
336-342) was not wired by T3 — T4 found it missing and implemented it
within its own already-granted scope ("thread the same check between
every other stage boundary" — this task-brief's own instruction), rather
than stopping. No operator decision needed: this fills a spec requirement
exactly as written, it does not deviate from one.

**Disclosed gap — a silently unsearchable zero-chunk document (operator-
ratified fix).** T4 found, while writing a PDF test, that a multi-page PDF
can pass DOC-04's "≥20 non-whitespace chars" empty-refusal (checked on the
**summed** extracted text) while each individual page's `chunk_text` call
(DOC-03 chunks **per page** for PDFs) independently yields zero chunks —
resulting in a stored `documents` row with `chunk_count=0`, visible in
`/documents`, permanently unsearchable, and no error surfaced. The spec's
DOC-04 text does not address this interaction between the aggregate
extraction-time check and per-page chunking. The orchestrator put this to
the operator, who chose to add a post-chunking guard: zero total chunks
after chunking → the same ERR-01 row 4 ("no readable text") refusal,
document rejected, nothing stored — reusing the existing empty-text
exception class rather than inventing a second one for the same outcome.
Implemented as a follow-up commit (see below once landed), test
reproducing the exact scenario T4 hit by accident.

**Exception classes this task established (for T7's brief, already
updated with these names)**: `EmptyDocumentError` (row 4, extraction-time
and now also post-chunking), `ExtractedTextTooLargeError` (row 5b, a
`DocumentTooLargeError` subclass alongside T3's `DocxArchiveTooLargeError`/
`PdfTooManyPagesError`), `IndexBudgetExceeded` (row 10c, must be caught
before any pypdf-corruption clause), `DocumentLimitExceededError` (row 13,
also reusable by T7's own CMD-03 pre-check for the identical string;
`documents.DOCUMENT_LIMIT = 20` exported for that reuse). Note for T7:
`index_document` assumes `classify()` already returned non-`None` — an
unknown extension reaching it surfaces as a plain `ValueError` (ERR-01 row
15), not row 1; CMD-03 must filter by extension **before** calling
`index_document`, exactly as T7's brief already specifies.

## T3 — document parsing and chunking (REQ-V190-DOC-01…03, -06)

Commit `c53becf`, strengthened by erratum commit `771466d` (4 more
tests). Test ids `T-V190-DOC-01…06`, 59 new tests total. `pytest
--collect-only -q` = **1362** (1304 + 55 + 4, re-measured directly).
Gates: `ruff check .` 0, `pytest` 0, `bot.py --selftest` 0.

**Disclosed spec defect — `T-V190-SEC-04` is assigned to two different
requirements, spec left unedited (operator decision).** Appendix A row
(`spec-v1.9.0.md:2120`) assigns test id `T-V190-SEC-04` to
REQ-V190-SEC-02 ("the model cannot choose the user" — T6's dispatch
test); separately §1/§3/§9 (lines 54, 345, 1419) and Appendix A row
`:2122` also cite `T-V190-SEC-04` for REQ-V190-SEC-04 ("no file on disk").
This contradicts the handoff's claim that "Appendix A is a verified
bijection in both directions." The orchestrator confirmed this directly
against Appendix A and the delta file (not a misreading) and put the
question to the operator, citing the project's own precedent for
mid-run spec corrections (v1.7.0 T9's gate-matrix-table blocker,
resolved by an authorised spec edit). **The operator's decision: do not
edit the spec file — record the defect here instead.** Resolution kept
for the implementation: `T-V190-SEC-04` stays assigned to REQ-V190-SEC-02
(T6's test, matching Appendix A's primary listing and the task table's own
T6 row); REQ-V190-SEC-04's "no file on disk" grep/`inspect.getsource`
check is implemented and tested under an unambiguous local test name by
T7 (the only task where both `documents.py` and the handler exist), not
reusing the colliding spec id. `spec-v1.9.0.md`'s `sha256` remains
`619198899cb99bafe7f0fd0aed6b41a71fbf7df36849cec27803ec637d4ce52e`
(T0's, unchanged — no edit was made).

**Disclosed test-strengthening erratum (operator-ratified).** T3's own
subagent flagged two of its new tests as weaker than DOC-03's "high
effort/high care" designation (handoff §Models) warrants: the overlap
test only exercised the common case, not the `hard_max`-priority clamp
in `_start_new_chunk` (a paragraph-separator edge case where the full
200-char overlap must shrink to keep a chunk ≤ 1200 chars — the
orchestrator reviewed the implementation directly and confirmed this
clamp is a correct reading of the spec's own stated priority, "1,200 is
the maximum everywhere... before and after a tail merge," not a bug); and
the corrupted-PDF test used a bare `pytest.raises(Exception)` that
wouldn't distinguish a genuine corruption error from a budget/limit
exception leaking through the wrong path. A follow-up subagent
strengthened both tests without touching production logic (commit
`771466d`): the overlap clamp is now proven to actually fire (numerically
verified: `char_start=802` vs. a naive unclamped `800`, overlap 198 not
200, chunk length exactly 1200) alongside a companion common-case test;
the corrupted-PDF test now asserts the specific `pypdf.errors.PdfStreamError`
type (confirmed empirically, stable across truncation lengths) and a new
negative test proves `PdfTooManyPagesError` is `isinstance`-distinct from
`pypdf.errors.PdfReadError` — the two failure classes are genuinely
separable by type, as DOC-02 requires.

**Other deviations (T3's own prompt file,
`docs/prompts/146-v190-t3-document-parsing.md`, carries full reasoning):**
exception classes `DocumentTooLargeError` (base), `DocxArchiveTooLargeError`,
`PdfTooManyPagesError` for the DOCX/PDF size-limit refusals (T4 consumes
these names). An ordering hazard T3 surfaced for T7: `classify` must run
on the **cleaned** filename, not the raw one (`clean_filename` strips
trailing whitespace that would otherwise break extension detection) — T7's
brief was updated to make this explicit before T7 starts.

## T2 — embeddings client and config (REQ-V190-RET-01, -02, -08)

Commit `aacf067` (client/config), then `92dcce2` (erratum). Test ids:
`T-V190-RET-01`, `-02`, `-09`. `pytest --collect-only -q` = **1304**
(1247 + 57 new tests across `test_v190_embeddings.py`/`test_v190_config.py`).
Gates: `ruff check .` 0, `pytest` 0, `bot.py --selftest` 0.

**Disclosed erratum — REQ-V190-RET-08's live wiring broke two more
unlisted tests (operator-ratified).** Wiring `_live_embeddings` into
`run_selftest_live` (a MUST) broke `test_t_v1_lv_01_all_checks_pass` and
`test_t_v1_lv_01_missing_openrouter_key_is_a_skip` in
`tests/test_v1_guardrails.py` — their shared `live_cfg`/`live_handler`
fixtures (local to that one file only, confirmed no wider blast radius)
didn't configure an embedding pair, and RET-08 mandates FAIL, not SKIP,
when `rag_enabled` is false (unlike the optional OpenRouter key). The T2
subagent correctly stopped rather than self-authorizing per its
instructions; the orchestrator reviewed the fixtures, confirmed the fix
was narrow and file-local, and put it to the operator, who ratified it as
a second EC-03 amendment-list extension. A follow-up subagent then: gave
`live_cfg` a default embedding pair, taught `live_handler` to answer
`/embeddings`, and updated the two tests' expected OK-line counts
(6→7). No other test was affected (verified — `run_selftest_live` and
`live_handler` have no other call sites in the suite).

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
