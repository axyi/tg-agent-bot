# spec-v1.9.0-delta-1 — the gate matrix, the test table, the assignment traceability, the acceptance scenarios

Companion to `docs/spec/spec-v1.9.0.md` (its size rule, §1 "The spec's own
budget"): four blocks that file declares normative and points at —
REQ-V190-EC-12, REQ-V190-TST-03, Appendix A's assignment column, and
REQ-V190-REV-02's Appendix B. Same status as the main file; never
`spec-v1.9.1.md`.

## The gate matrix (REQ-V190-EC-12)

REQ-V170-GATE-03's table, yes/— verbatim, as carried by
`spec-v1.8.0-delta-1.md:22-45`, plus the `rag_eval.py` and
`mutation_check.py --select v190-` rows this release adds, minus the `note`
column the parser never reads. It is load-bearing markup: the parser
(`tests/test_v15_standards.py:1711-1726`) finds the first line starting with
the header literal, skips the separator, and takes rows until the first line
not starting with `|`; every label must match `_GATE_MATRIX_LABEL_TO_NAME`
(`:1685-1707`) byte-for-byte.

| gate | pre-commit | pre-push | full |
|---|:---:|:---:|:---:|
| `ruff check` (staged) | yes | — | — |
| `ruff check .` (tree) | — | yes | yes |
| `ruff format --check` | yes | yes | yes |
| branch-name check | yes | yes | yes |
| `gitleaks git --staged` | yes | — | — |
| `gitleaks dir` (tree) | — | yes | yes |
| `uv sync --locked` | — | — | yes |
| `pytest` | — | yes | yes |
| `bot.py --selftest` | — | yes | yes |
| `bot.py --selftest-live` | — | — | yes |
| `rag_eval.py` | — | — | yes |
| `mutation_check.py --select v15-` | — | yes | — |
| `mutation_check.py --select v160-` | — | yes | — |
| `mutation_check.py --select v170-` | — | yes | — |
| `mutation_check.py --select v180-` | — | yes | — |
| `mutation_check.py --select v190-` | — | yes | — |
| `mutation_check.py` (all) | — | — | yes |
| `trivy fs` | — | yes | yes |
| `semgrep scan` | — | yes | yes |
| `skylos` | — | yes | yes |
| `install_hooks.py --check` | — | yes | yes |
| `checks.py doctor` | — | yes | yes |
| `checks.py lint-docs` | — | — | yes |

---

## The test table (REQ-V190-TST-03)

Each id names one test function or a small parametrised set; "negative"
tests prove a guard by violating it.

| id | asserts |
|---|---|
| `T-V190-DOC-01` | `classify` by lowercase extension for the four types and `None` for `.PDF.exe`, no extension, `mime_type` ignored; `clean_filename` strips separators and control chars, caps at 120, `None` for empty |
| `T-V190-DOC-02` | `extract`: utf-8-sig and cp1251 txt/md decode; DOCX paragraphs and table cells in document order; PDF per page with empty pages skipped and physical numbering kept |
| `T-V190-DOC-03` | negative: truncated PDF → the corrupted-PDF class; truncated DOCX → `BadZipFile`; a ZIP without `word/document.xml` → `PackageNotFoundError`/`KeyError` — each mapped to ERR-01 rows 2/3 |
| `T-V190-DOC-04` | `chunk_text`: every chunk ≤ 1200 (≤ 1250 after a tail merge); overlap of exactly 200 between consecutive chunks; paragraph boundaries preferred; a 5,000-char paragraph split on sentence ends; tail < 50 merged; determinism (two runs equal); offsets index the input |
| `T-V190-DOC-05` | PDF chunks never span pages; `page` is the 1-based physical page; non-PDF `page is None`; `chunk_index` monotonic across pages |
| `T-V190-DOC-06` | `write_pdf` output is read by `pypdf` with the right page count and text per page; non-ASCII and > 60 lines raise `ValueError` |
| `T-V190-STO-01` | `connect` and `connect_readonly` both answer `select vec_version()`; `init_schema()` without a dim creates no `vec_chunks`; with `dim=16` it does, idempotently |
| `T-V190-STO-02` | a seeded v5 database (built by executing v5's `_SCHEMA` + `_MIGRATION_4_TO_5` and inserting agent/summary `llm_calls` rows) migrates to 6: rows preserved (count and content), the `rerank` purpose now insertable, `documents`/`chunks` present, version 6; a fresh database is 6; version 7 refused (the EC-03 amendment) |
| `T-V190-STO-03` | `delete_document` removes vectors, chunks and the row in one transaction; a search afterwards returns nothing from it; a failing vector delete (monkeypatched) rolls the row back |
| `T-V190-STO-04` | negative: a stored `rag.embedding` of `m:16` and config `m:32` → `ConfigError` before any DDL; same pair → starts; no config + stored pair → starts; empty `documents` → the key is rewritten from config |
| `T-V190-STO-05` | `index_document` twice with the same filename replaces: one document row, new chunk ids, old vectors gone, `replaced=True`; the 21st distinct filename is refused and the 20th's replace is not |
| `T-V190-RET-01` | `EmbeddingsClient` batches 32 per request, orders by `index`, retries once on transport error, raises `EmbeddingError` on ≠ 200, malformed body, wrong dim; one CLIENT span per request with the five attributes, `conv_id=None` when indexing (`httpx.MockTransport`) |
| `T-V190-RET-02` | negative: `EMBEDDING_MODEL` without `EMBEDDING_DIM` (and vice versa) → `ConfigError`; `EMBEDDING_DIM=0`/`4097`/`x` → `ConfigError`; defaults: `rag_enabled` false, `rag_top_k` 5, `rag_rerank` `on`, `embedding_timeout_s` 60.0, `embedding_base_url` = the LM Studio URL |
| `T-V190-RET-03` | vector search over `FakeEmbedder`: the chunk sharing the query's tokens ranks first; `[]` with no rows |
| `T-V190-RET-04` | `tokenize` stems Russian and passes English through; `bm25_search` returns only score > 0, at most k, deterministic order; `[]` on an empty corpus |
| `T-V190-RET-05` | `rrf` reproduces assignment 4's ordering on a fixed pair of lists; the fused list is cut to 10; an empty BM25 list yields the vector order |
| `T-V190-RET-06` | rerank: a scripted `[3, 1, 2]` reply reorders; omitted numbers follow in RRF order; each candidate text cut to 600; `max_tokens == 128`, `timeout_s == 20.0`, `reasoning.value == "off"` on the fake's recorded call; the call is in `llm_calls` with purpose `rerank` |
| `T-V190-RET-07` | negative: `LLMError`, `"not json"`, `[9]`, `[1, 1]` each return `None`, the caller keeps the RRF order, one warning, and the answer still completes |
| `T-V190-RET-08` | `Searcher.search` returns ≤ `rag_top_k` hydrated passages, `documents_present` false with no rows, `calls` recorded; `RAG_RERANK=off` makes no LLM call |
| `T-V190-RET-09` | `_live_embeddings` (a stubbed `httpx.Client`): FAIL when the pair is unset; FAIL when the model is missing from `/models`; FAIL on a wrong-length vector; OK otherwise |
| `T-V190-TOOL-01` | the fourth entry is last, serialises ≤ 350 chars, the catalog ≤ 1800; `_known_tool_names()` contains it; `expected_structure()` equality (the EC-03 amendment) |
| `T-V190-TOOL-02` | envelope texts for no documents, no hits, N hits (header, per-passage format with and without page); the 6,000-char cap; `searcher=None` → the "not available" error; bad `query` refused |
| `T-V190-TOOL-03` | `searcher` reaches `execute_tool` from `run_agent_outcome` (a `FakeLLM` scripting one call); `run_agent`'s signature is unchanged (`inspect.signature` equality with a pinned parameter list) |
| `T-V190-TOOL-04` | the history stub for a `search_documents` message carries `query` and `passages`; the status line renders `⚙️ search_documents: <query>` |
| `T-V190-TOOL-05` | the prompt line is present, ≤ 140 chars, ASCII; the prompt ≤ 700; every mandatory statement of `test_prefix.py:205-233` still present |
| `T-V190-TOOL-06` | `attach_sources`: a reply naming no returned filename gets `Sources: a.pdf (page 2), b.md`; a reply naming one is untouched; max 5; pages grouped |
| `T-V190-TOOL-07` | negative: after a zero-passage search a reply carrying `Source: invented.pdf` loses that line with one warning; with no search call the reply is untouched; the conversation-aware two-turn script reaches the searcher with the previous subject in the query |
| `T-V190-CMD-01` | a document update is handled before the text guard, after the allow-list, through the limiter; `NON_TEXT_REPLY` is **not** sent; `embedder=None` → the not-configured line and no `getFile` |
| `T-V190-CMD-02` | negative: `file_size` over 10 MiB → refused with **no** `get_file` call; a stream over the cap → `DocumentTooLarge` → the same line |
| `T-V190-CMD-03` | `download_file` streams through `httpx.MockTransport`, stops at the cap, maps ≠ 200 and transport errors to `TelegramError` without the token in the message |
| `T-V190-CMD-04` | progress: the exact stage strings in order on the fake's `edited`, one deletion on success, one confirmation message with chunks (and pages for a PDF); on failure the last edit is the error line and no deletion |
| `T-V190-CMD-05` | `/documents` listing format and the empty line; `/delete` usage, unknown, success; both redact a sentinel in a filename |
| `T-V190-CMD-06` | the typing indicator is started with `ceiling_s=300.0` and stopped on the success, failure and exception paths (a recording fake indicator) |
| `T-V190-CMD-07` | the indexing budget: a fake clock jumping past 300 s between stages → the timed-out line, no rows |
| `T-V190-CMD-08` | negative: an unexpected exception type → the generic line, no traceback text in any sent message, the next update in the batch still processed |
| `T-V190-ERR-01` | one test per ERR-01 row 1–7, 10a–c, 11, 13–15: the exact user string, the log line prefix, and `documents`/`chunks`/`vec_chunks` counts unchanged |
| `T-V190-ERR-02` | negative: a registered secret in a filename and in an exception message reaches neither Telegram nor `caplog` unredacted |
| `T-V190-ERR-03` | row 12: a failing confirmation send leaves the document stored |
| `T-V190-SEC-01` | two users, same filename, different content: each user's search returns only own passages; user A's query never hits B's chunks (KNN and BM25 both) |
| `T-V190-SEC-02` | `/documents` for A lists only A's; `document_count` per user |
| `T-V190-SEC-03` | negative: A's `/delete <B's filename>` → "No document named"; B's rows intact |
| `T-V190-SEC-04` | negative: an extra `user_id` key in the tool arguments is ignored; `documents.py` and the handler source contain no `open(`, `Path(`, `tempfile` |
| `T-V190-SEC-05` | every SQL literal in `storage.py`/`rag.py` naming `documents`, `chunks` or `vec_chunks` contains `user_id`; every `execute` on them passes a parameter tuple (AST walk) |
| `T-V190-EVAL-01` | `questions.json` shape: 12 items, 10 answerable, ≥ 2 per source, 3 PDF pages, 2 nulls naming no file; every source exists in `corpus/` |
| `T-V190-EVAL-02` | `rag_eval` end-to-end with `FakeEmbedder`/`FakeLLM` on the real corpus: renders DOCX and PDF in memory, indexes for user −1, prints the table, exit 0/1 by the floor, 2 when the embedder raises |
| `T-V190-EVAL-03` | the metric functions: recall@5 and MRR on a scripted rank list equal hand-computed values; page hit-rate counts only PDF items |
| `T-V190-E2E-01` | upload (txt) → `/documents` → question → the scripted `FakeLLM` calls `search_documents` → the reply carries the filename; `Sources:` appended when it does not |
| `T-V190-E2E-02` | upload (PDF, 3 pages) → question → the returned passage carries the page → the reply's source line carries `(page N)` |
| `T-V190-E2E-03` | `/delete` → the same question → "No passages matched." reaches the model → the model's "not covered" reply, no source line |
| `T-V190-EC-01` | `AGENTS.md` names the five dependencies, the seven-gate block, the `v190-T<N>.md` brief path; `tests/test_v180_agents.py` still green |
| `T-V190-VER-01` | `pyproject.toml`'s `project.version` reads `1.9.0` |

---

## Assignment traceability (Appendix A of `spec-v1.9.0.md`)

| code | assignment item | REQ ids |
|---|---|---|
| R1 | formats `.txt` `.md` `.docx` `.pdf` | DOC-01, DOC-02 |
| R2 | chunking chosen and explained with the two risks | DOC-03, RPT-05 |
| R3 | embeddings: model, dimension, reason in README | RET-01, RET-02, RET-08, STO-04, RPT-05 |
| R4 | SQLite + sqlite-vec; `documents`/`chunks` minimum columns; the recoverable chain | STO-01, STO-02, STO-03 |
| R5 | K chosen and explained | RET-07, RPT-05 |
| R6 | RAG as an agent tool `search_documents(query)` | TOOL-01, TOOL-02, TOOL-03, RET-07, CMD-01 |
| R7 | several documents searched together | DOC-05 (one index per user, replace by filename), RET-07 |
| R8 | user isolation, shown in code and README | STO-05, SEC-01, SEC-02 |
| R9 | `/documents`, `/delete <filename>` | CMD-05, CMD-06 |
| R10 | ≥ 10 error cases, no crash, plain messages | ERR-01, ERR-02, CMD-02, CMD-03, CMD-07, DOC-04, SEC-03, SEC-04, RET-06 |
| R11 | source attribution, page or chunk | TOOL-04, TOOL-05 |
| R12 | no hallucination — says when the documents lack it | TOOL-04, TOOL-05 |
| R13 | ≥ 5 automated tests on several levels | TST-01, TST-02, TST-03, DOC-06 |
| R14 | evaluation dataset ≥ 5 questions | EVAL-01, EVAL-02, EVAL-03, EVAL-04 |
| R15 | README: Architecture, Chunking, Embeddings, Retrieval, Storage, Security, Limitations | RPT-05, ERR-03, STO-02 |
| A1 | accepts the four formats | DOC-01, CMD-01 |
| A2 | text extraction | DOC-02 |
| A3 | chunking | DOC-03 |
| A4 | embeddings per chunk | RET-01, DOC-05 |
| A5 | stored in SQLite + sqlite-vec | STO-01, STO-02, DOC-05 |
| A6 | vector search | RET-03 |
| A7 | the agent uses retrieval to answer | TOOL-01, TOOL-02, RET-07 |
| A8 | several documents | DOC-05, RET-07 |
| A9 | isolation between users | SEC-01, STO-05 |
| A10 | `/documents` | CMD-05 |
| A11 | document deletion | CMD-06, SEC-05 |
| A12 | deletion removes chunks and embeddings | SEC-05, CMD-06 |
| A13 | the answer carries a source | TOOL-05 |
| A14 | the agent does not invent what the documents lack | TOOL-05 |
| A15 | main errors handled | ERR-01, DOC-04, CMD-03, CMD-07 |
| A16 | ≥ 5 automated tests | TST-01, TST-03, EC-02 |
| A17 | evaluation dataset ≥ 5 questions | EVAL-01, EVAL-02, EVAL-03 |
| A18 | README with architecture and decisions | RPT-05, ERR-03, RPT-02 |
| B1 | progress stages | CMD-04 |
| B2 | PDF page numbers in the source | DOC-06 (exact pages in fixtures), EVAL-03 (page hit-rate) |
| B3 | hybrid search | RET-04, RET-05, EVAL-03 |
| B4 | reranking | RET-06, EVAL-03 |
| B5 | conversation-aware RAG | TOOL-06, EVAL-03 |

A8 shares its REQ ids with R7 and A5 with R4 by design: one mechanism, two
rubric lines.

---

## Appendix B — acceptance scenarios (Gherkin, written before code)

```gherkin
# Every scenario runs OFFLINE against FakeTelegram, FakeLLM, FakeEmbedder, a
# fake clock and a tmp_path database. No live LLM call, Telegram call or
# network request of any kind (REQ-V190-REV-02). SAFETY: no live credential
# is used as a test value; no scenario reads .env or opens the deployment
# database.

Scenario: E1 — a text document is received, indexed and confirmed
  Given a user on the allow-list sends a message.document named "policy.txt" of 3000 bytes
  And the fake Telegram serves those bytes for its file_path
  When process_update handles it
  Then getFile was called once and the bytes were never written to disk
  And the status message was edited through "📄 received", "📄 extracted: 2950 chars", "📄 chunked: 4", "📄 embedding: 1/1"
  And exactly one deleteMessage was recorded for the status message
  And one reply "✅ policy.txt: 4 chunks. Ask me about it." was sent
  And documents has one row for that user with chunk_count 4 and vec_chunks four rows

Scenario: E2 — a corrupted PDF is refused and nothing is stored
  Given the first half of a valid PDF's bytes named "broken.pdf"
  When process_update handles the document
  Then the status message's last edit is "Could not read this PDF file."
  And no deleteMessage was recorded
  And documents, chunks and vec_chunks are empty for that user

Scenario: E3 — chunks respect the size, the overlap and the page
  Given a 3-page PDF whose second page holds 2600 characters of text
  When it is indexed
  Then every chunk of page 2 is at most 1200 characters and carries page = 2
  And consecutive chunks of page 2 share exactly 200 characters
  And no chunk carries text from two pages

Scenario: E4 — re-uploading a filename replaces the old document
  Given "notes.md" indexed with 3 chunks
  When the same user uploads a different "notes.md" with 5 chunks
  Then documents has one "notes.md" row for that user with chunk_count 5
  And none of the three old chunk ids exists in chunks or vec_chunks

Scenario: E5 — a changed embedding pair refuses to start
  Given a database whose bot_state holds rag.embedding = "m:16"
  When init_schema runs with embedding_model "m" and embedding_dim 32
  Then a ConfigError is raised naming the stored pair before any DDL runs
  And the same call with "m" and 16 succeeds

Scenario: E6 — the embeddings client batches, retries once, and checks the dimension
  Given 70 chunk texts and a mock transport that fails the first request with a transport error
  When embed is called
  Then four requests were made (one retried) each with at most 32 inputs
  And a response vector of 15 floats for dim 16 raises EmbeddingError
  And each request emitted one CLIENT span named "embeddings <model>"

Scenario: E7 — an oversized file is refused before download
  Given a message.document with file_size 10485761
  When process_update handles it
  Then the reply is "File too large (over 10 MiB)."
  And getFile was never called

Scenario: E8 — hybrid retrieval finds the chunk BM25 alone would miss
  Given user U with two indexed documents under FakeEmbedder
  When Searcher.search runs a query sharing tokens only with a chunk of the second document
  Then the vector list contains that chunk, the RRF list ranks it first
  And search returns at most 5 passages, each hydrated with filename and chunk_index

Scenario: E9 — the reranker fails and the answer still completes
  Given a FakeLLM whose rerank reply is "not json"
  When Searcher.search runs with RAG_RERANK on
  Then the passages are in RRF order
  And one warning "rerank fell back to rrf order" was logged
  And llm_calls holds one row with purpose "rerank"

Scenario: E10 — the agent calls the tool and reads the envelope
  Given a FakeLLM scripted to call search_documents with {"query": "отпуск"} then answer
  When run_agent_outcome runs with a Searcher holding one indexed document
  Then the tool message starts with "Found 2 passages:" and each block carries "[n] policy.txt — chunk i:"
  And the second scripted call received that tool message

Scenario: E11 — the structural Sources line is appended
  Given a turn whose search returned passages from "policy.pdf" page 3
  And the model's final reply mentions no filename
  When attach_sources runs
  Then the delivered reply ends with "Sources: policy.pdf (page 3)"

Scenario: E12 — an invented source after an empty search is stripped
  Given a turn whose only search returned "No passages matched."
  And the model's reply ends with "Source: invented.pdf"
  When attach_sources runs
  Then the delivered reply carries no line starting with "Source:"
  And one warning "stripped an invented source line" was logged

Scenario: E13 — /documents lists own documents only
  Given user A with "a.txt" and user B with "a.txt"
  When A sends /documents
  Then the reply is "Your documents (1):" followed by one line for "a.txt"
  And B's row is absent

Scenario: E14 — /delete removes vectors, chunks and the row, own only
  Given user A with "a.txt" (3 chunks) and user B with "a.txt"
  When A sends "/delete a.txt"
  Then the reply is "Deleted a.txt."
  And A's chunks and vec_chunks rows are gone while B's remain
  And A's next search_documents returns "No documents uploaded for this user. Supported: .txt .md .docx .pdf"

Scenario: E15 — an unexpected exception yields a message, not a traceback
  Given extract is monkeypatched to raise ZeroDivisionError
  When process_update handles a document followed by a text message in the same batch
  Then the document's user sees "Something went wrong while processing the document."
  And no sent message contains "Traceback"
  And the text message was still answered

Scenario: E16 — cross-user search returns nothing
  Given user A's "secret.txt" indexed and user B with no documents
  When B's Searcher.search runs a query copied from A's text
  Then documents_present is false and the tool envelope is the "No documents uploaded" line
  And with one unrelated document of B's own, the passages never include A's chunk ids
```
