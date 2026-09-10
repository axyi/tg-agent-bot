# Prompt 143 — spec-v1.9.0 T1 (storage and schema)

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** `docs/handoff-v1.9.0.md` §Models and effort: sonnet-5
  executed v1.5 through v1.8.0 end to end in this repository; every design
  decision of v1.9.0's storage layer is frozen in the spec and the T1
  task-brief, so the novelty is in the run, not in the reasoning.
- **Harness:** Claude Code
- **Stage:** T1
- **Owner of:** `storage.py`, `pyproject.toml`, `uv.lock`,
  `devtools/mutation_check.py` (one `find`/`replace` pair amended, see
  Constraints), `tests/test_v190_storage.py` (new),
  `tests/test_v190_isolation.py` (new), `tests/test_observability.py`,
  `tests/test_v170_reasoning.py`, `tests/test_v160_observability.py`,
  `tests/test_summary.py`
- **REQ ids:** REQ-V190-STO-01, REQ-V190-STO-02, REQ-V190-STO-03,
  REQ-V190-STO-04, REQ-V190-STO-05

## Goal

Implement spec-v1.9.0 §4 end to end, test-first: `sqlite_vec` loaded on
every `connect`/`connect_readonly` call; schema 6 (`documents`, `chunks`,
`vec_chunks`); the 5 → 6 migration's normative `_migrate_5_to_6` control
flow (the `llm_calls` rename-copy rebuild widening `purpose` to admit
`rerank`, `BEGIN IMMEDIATE`/`except BaseException: ROLLBACK`/
`finally: PRAGMA foreign_keys=ON`); `init_schema`'s new
`embedding_dim`/`embedding_model` parameters and the `rag.embedding` pair's
binding, rebind and orphan-recovery rules; and the storage API
(`add_document`, `add_chunks`, `add_vectors`, `document_id_for`,
`list_documents`, `delete_document`, `user_chunks`, `knn_chunk_ids`,
`chunks_by_ids`, `document_count`, `document_count_all`), every statement
scoped by user except the one named exemption.

## Constraints

Five dependency pins added to `pyproject.toml` permanently (`sqlite-vec`,
`pypdf`, `python-docx`, `rank-bm25`, `snowballstemmer`) and `uv.lock`
regenerated via `uv lock` — nothing else. `bot.py`'s three `init_schema`
callers are untouched (T6/T7's job); `devtools/bench.py:927`'s call stays
`None`. No `.env` read or write; no live network. `documents`/`chunks` are
deliberately **not** folded into `_SCHEMA`'s own concatenation the way
`_SPANS_DDL` is — `_SCHEMA`'s `executescript` runs unconditionally, outside
any explicit transaction, so anything it creates cannot be rolled back;
`T-V190-STO-09` requires a failed 5→6 migration to leave **no**
`documents`/`chunks` behind, so `_DOCUMENTS_DDL` is reused only by
`_MIGRATION_5_TO_6`, which the fresh-database path also reaches uniformly
via its own 4→5→6 chain. This is a one-line deviation from the brief's
literal "appended to `_SCHEMA` exactly as `_SPANS_DDL` is" — recorded below
and in the run report.

`devtools/mutation_check.py`'s `v160-readonly-connection-writable` entry's
`find`/`replace` strings are amended to include the three new
extension-load lines inserted into `connect_readonly` (both variants carry
them unchanged; the mutation is still only about `mode=ro` and the PRAGMA) —
required for `tests/test_mutation_check.py`'s own self-consistency check to
stay green; `devtools/mutation_check.py` itself is not run (T9's job).

`tests/test_v170_reasoning.py`, `tests/test_v160_observability.py` and
`tests/test_summary.py` hardcode `schema_version(conn) == 5` and
`SET version = 6` as their "future version" boundary — the same class of
literal `SCHEMA_VERSION` assertion REQ-V190-EC-03's amendment table already
authorises amending in `tests/test_observability.py`, but its own table
omits these three files. Since `SCHEMA_VERSION = 6` is itself a MUST
(REQ-V190-STO-02) and no implementation can keep those ten assertions green,
this is a disclosed erratum in EC-03's amendment table, not a reopened
decision: each site is amended mechanically (`5`→`6`, `6`→`7`), one-line
comment at each, no assertion semantics changed, no test deleted, no test
count changed.

## Acceptance

- `uv run --locked ruff check .` — exit 0.
- `uv run --locked pytest` — exit 0; `pytest --collect-only -q` totals 1247
  (1220 floor + 27 new: 20 in `test_v190_storage.py`, 7 in
  `test_v190_isolation.py`).
- `uv run --locked python bot.py --selftest` — exit 0.
- `select vec_version()` answers through the production `connect` and
  `connect_readonly` (`T-V190-STO-01`).
- A seeded v5 `tmp_path` database (`spans`, `tool_calls`, `messages` and
  `llm_calls` all seeded) migrates to 6 with all four tables preserved by
  count and content, `PRAGMA foreign_keys` = 1, `PRAGMA foreign_key_check`
  empty, `idx_llm_calls_conv` recreated, `rerank` now insertable,
  `documents`/`chunks` present (`T-V190-STO-02`); a failure injected
  mid-rebuild (`Exception` and `BaseException` alike) rolls back, leaving
  the schema-5 database intact, usable, with no `documents`/`chunks` and
  foreign keys restored (`T-V190-STO-09`).
- `T-V190-STO-03`/`-04`/`-05`/`-06`/`-07`/`-08` and the storage half of
  `T-V190-SEC-02`/`-03`/`-05`/`-06` all green.
- Do not run `devtools/mutation_check.py` or any `--selftest-live`/live gate
  (out of scope for this task; T0 already covered gate 5, T11 re-covers it).

## Stop

A schema-6 DDL or `_migrate_5_to_6` control-flow deviation from the spec's
verbatim text would be a stop-and-ask; none occurred. The `_SCHEMA`/
`_DOCUMENTS_DDL` placement deviation above and the EC-03 amendment-table gap
were each resolved in-run per AGENTS.md's auto-mode guidance (the reasonable
call, disclosed rather than silently taken) since both have exactly one
conforming resolution and blocking T1 on either would gain nothing.
