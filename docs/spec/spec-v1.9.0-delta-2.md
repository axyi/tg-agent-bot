# spec-v1.9.0-delta-2 — REQ-V190-STO-04 is bot.py's responsibility too

Companion to `docs/spec/spec-v1.9.0.md`; same status as
`spec-v1.9.0-delta-1.md`, never `spec-v1.9.1.md`. Fixes GitHub issue #3
(v1.9.5 T1, `docs/spec/task-briefs/v195-T1.md`): every document upload
failed with `Storage error. The document was not saved.` on a bot started
with `EMBEDDING_MODEL`/`EMBEDDING_DIM` configured, because `vec_chunks` and
the `rag.embedding` state key were never created.

## The gap REQ-V190-STO-04 left open

REQ-V190-STO-04 (`spec-v1.9.0.md:662-694`) specifies `init_schema`'s own
mechanics — the transaction, the orphan-table branch, the atomic
empty-index rebind — entirely in terms of the `embedding_dim`/
`embedding_model` keywords it is *given*. It says nothing about who is
responsible for giving them, because at v1.9.0 every test called
`init_schema` directly with `embedding_dim=` passed explicitly
(`tests/test_v190_e2e.py`, `tests/test_v190_errors.py`,
`tests/test_v190_isolation.py`) — nothing exercised `bot.py`'s own three
call sites (`main()`, `run_selftest()`, `_live_db()`), which all called
`storage.init_schema(conn)` bare, even though `cfg.embedding_dim`/
`cfg.embedding_model` were one line away. The `vec_chunks` DDL and the
`rag.embedding` write never ran; `documents.index_document`'s later
`INSERT INTO vec_chunks` then raised `OperationalError: no such table:
vec_chunks`, which `_handle_document`'s `except sqlite3.Error` clause
turned into the generic storage-error reply — a config-shaped defect
disguised as a runtime one.

## The amendment

**REQ-V190-STO-04 extends to `bot.py`: passing the configured pair at
every `init_schema` call site is `bot.py`'s responsibility, not only
`storage.init_schema`'s.** Concretely, `bot.py` gains one shared helper,

```python
def _init_startup_schema(conn: sqlite3.Connection, cfg: Config) -> None:
    storage.init_schema(conn, embedding_dim=cfg.embedding_dim, embedding_model=cfg.embedding_model)
```

and its three call sites (`main()`, `run_selftest()`, `_live_db()`) call
only this helper, never `storage.init_schema` directly — so the three
sites cannot drift apart from each other again. This also makes
`_bind_new_embedding_pair`'s and `_rebind_embedding_pair`'s `ConfigError`
(an orphaned `vec_chunks` next to a document, or the pair changed while
documents exist) reachable from `main()` for the first time; `main()`
handles it exactly like every other startup config refusal (REQ-V12-ERR-01):
log the redacted message, close the connection opened so far, exit 2 — no
new behaviour class, the same `except ConfigError` shape `load_config`'s
own catch and `_startup_docker_wiring`'s already use. `run_selftest()`'s
placeholder `Config` never sets `embedding_dim`/`embedding_model`, so
routing it through the same helper is a no-op there (gate 4 stays offline);
`_live_db()`'s existing `except Exception` already turns a `ConfigError`
from a rebind refusal into a normal `live: FAIL db — …` line, which is
already the right behaviour for gate 5.

No test table or gate matrix entry changes: the regression is covered by a
new pair of tests in `tests/test_routing.py`'s existing "Startup wiring
(bot.main)" section (through `bot.main`, not a hand-built connection) and
one new mutation entry, `v195-init-schema-drops-the-pair`, both cited in
`docs/prompts/188-vec-chunks-startup-binding.md`.
