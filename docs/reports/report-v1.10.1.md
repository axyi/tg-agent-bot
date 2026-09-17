# tg-agent-bot v1.10.1 — report skeleton (T0)

Closes every tail the v1.10.0 run and its `/verify-run` left, and moves
every live gate — 5, 7 and 8 — off LM Studio onto OpenRouter models the lab
chose. Spec: `docs/spec/spec-v1.10.1.md`. `<base>` = `1d96ca0` (the commit
before the five spec-authoring/handoff commits; `git diff --stat
1d96ca0..HEAD` at T0 touches only `docs/`, so every `file:line` the spec
pins holds unchanged). Spec `sha256`:
`6b6cd7371aaa8c673a89b681b704e9750b4ed8f6cd0d6f7cfb8596c43926a297`.

This file is filled progressively: T0 (this skeleton), T3 (dataset
`sha256`s), T4 (PRM-02's before/after table), T6 (the one live gate-8 run
and its tables), T7 (version bump, provisional report), T8 (final
evidence-only commit). Sections not yet reached read "not reached: T<n>".

## T0 — preflight

`<base>` = `1d96ca0`. Spec `sha256` as above. Test-collection floor
re-measured: `uv run --locked pytest --collect-only -q -o addopts="" | grep
-c '::'` = **1860** (matches `pyproject.toml`'s `addopts` count; the
v1.10.0 report's "1859" note is `NG-06`, not investigated further).

### Stage 0 — seven checks, in order (checks 1, 2 and 7 offline, against the
already-synced locked environment)

1. **Configuration check (CFG-01) + export proof (EC-04).** `uv run
   --offline --locked python -` over `load_config()` asserted every CFG-01
   `asserted as` cell: `llm_provider="openrouter"`,
   `openrouter_model="openai/gpt-4.1-mini"`, `lmstudio_model=""`,
   `embedding_base_url="https://openrouter.ai/api/v1"`,
   `embedding_model="openai/text-embedding-3-small"`, `embedding_dim=1536`,
   `llm_rerank_model="openrouter:mistralai/mistral-small-24b-instruct-2501"`,
   `llm_judge_model="openrouter:openai/gpt-4.1"`, `llm_eval_chat_model=""`,
   `db_path` ending `data/run-v1101.db` — all True. `bool(openrouter_api_key)
   = True`. `chat.describe() = ('openrouter', 'openai/gpt-4.1-mini')`,
   `judge.describe() = ('openrouter', 'openai/gpt-4.1')` — distinct.
   Export proof: `LLM_JUDGE_MODEL=openrouter:openai/gpt-4.1-mini uv run
   --offline --locked python -c '...load_config().llm_judge_model'` printed
   `openrouter:openai/gpt-4.1-mini` (the exported value, not `.env`'s).
   PASS.
2. **Storage preflight (EC-04 precondition 3), offline, before any network
   call.** Opened `cfg.db_path` (`data/run-v1101.db`, a fresh file),
   `storage.init_schema(conn, embedding_dim=1536,
   embedding_model="openai/text-embedding-3-small")`, then
   `storage.document_count_all(conn) = 0` and `SELECT COUNT(*) FROM chunks`
   `= 0`. Printed `db_empty=True`. PASS.
3. **Model listings.** `GET https://openrouter.ai/api/v1/models` lists
   `openai/gpt-4.1-mini`; authenticated `GET
   https://openrouter.ai/api/v1/embeddings/models` lists
   `openai/text-embedding-3-small`. Both present. PASS.
4. **One timed plain chat turn** on the production route. Question «Ответь
   одним словом: столица Нидерландов?», reply `"Амстердам"`, elapsed
   **2.976s** (well under `cfg.llm_timeout_s` = 600s); no `LLMError`, no
   rejected `reasoning` field observed (default `ReasoningRequest`, no
   `reasoning=` kwarg sent — the tool-round reasoning policy is a no-op on
   this model per CFG-01). `t_turn = 2.976s`. PASS.
5. **One authenticated embeddings call.** `POST
   https://openrouter.ai/api/v1/embeddings` with
   `model=openai/text-embedding-3-small`, `input=["проверка"]`: status 200,
   1536 floats returned (`== cfg.embedding_dim`). PASS.
6. **One strict-schema judge call**, the two labelled spec-block fences
   (`judge-protocol-1`, `judge-protocol-2`) — extracted byte-identical from
   the already-implemented slice of `devtools/agent_eval.py` between `#
   BEGIN/END SPEC JUDGE PROTOCOL` (v1.10.0's `T-V1100-JDG-08` already pins
   that slice source-to-source against the spec fences) — on the fixed
   sample (question/reference/reply as REV-04 Stage 0 specifies). Parsed
   reply: `{"politeness": 1, "accuracy": 1, "conciseness": 1, "reason":
   "Ответ вежливый, точный и краткий. Указана правильная столица, без
   лишней информации."}`. `describe()` pairs as in check 1, unequal. **No
   fallback needed** (`openai/gpt-4.1` accepted `response_format` on the
   first attempt; EC-01 disallows the fallback this release regardless).
   PASS.
7. **`uv lock --offline` no-op.** `Resolved 25 packages` with no lockfile
   change; `git diff --exit-code -- uv.lock` empty. PASS.

No Stage 0 blocker. The run proceeds past T0.

### RUN-02 timeout computation

`R = HTTP_ATTEMPT_LIMIT = 9` (`agent.py:45`); `max_calls = 23 * 9 + 12 =
219`; `t_turn = 2.976s` (check 4); `timeout_seconds = ceil_to_100(1.5 * 219
* 2.976) = ceil_to_100(977.6) = 1000`, floor 1800, no cap → **`agent-eval.
timeout_seconds = 1800`** (the floor, as the handoff predicted; T6 writes
this into `config/quality_gates.yaml`).

### Gates 1-7 on the unchanged tree (gate 8 not run)

Gate 6 (mutation, ~13m44s) and gate 7 (rag_eval, <1s) run sequentially,
nothing else on the box during gate 6.

| # | Gate | Exit | Wall |
| --- | --- | --- | --- |
| 1 | `uv sync --locked` | 0 | fast — 25 packages resolved, 23 checked |
| 2 | `ruff check .` | 0 | fast, all checks passed |
| 3 | `pytest` | 0 | 20.87s, 1859 passed / 1 skipped, 1860 collected (matches re-measured floor) |
| 4 | `bot.py --selftest` | 0 | `selftest: OK` |
| 5 | `bot.py --selftest-live` | 1 | `live: OK config`, `OK db`, `OK docker (29.8.0)`, `OK telegram`, `SKIP lmstudio (not configured)`, **`FAIL embeddings — model openai/text-embedding-3-small is not loaded`**, `OK openrouter` — **disclosed expected** (G5-02's T0 exception: the embeddings client cannot authenticate to OpenRouter until T1); no other line red, `db` in particular OK |
| 6 | `mutation_check.py` (no `--select`) | 0 | 823.4s (13m43.4s), 127/127 killed, 0 survived/errored/drifted |
| 7 | `rag_eval.py` | 2 | 0.69s — `gate-7: FAIL indexing the corpus -- embeddings http 401` — **disclosed expected** (same cause as gate 5) |
| 8 | `agent_eval.py` | n/a | not run at T0 (GATE-01) |

`doctor`: `[PASS] doctor: all tools at pin, hooks installed`. Hooks:
`install_hooks.py --check`: `hooks installed correctly`.

Neither the gate-5 nor the gate-7 red spends the 3-cycle repair budget —
both are G5-02's disclosed T0 exception, recorded verbatim per RPT-01 item
1.

### Delegation record (T0)

T0 — not delegated — *commands only* (§16.1's exemption: the seven Stage 0
checks and the seven gates are commands whose redacted output goes into
this skeleton; the storage preflight is an offline `python -` one-liner
over existing `storage`/`config` APIs that writes no source or tracked
repository file — creating/initialising `cfg.db_path` is permitted; the
skeleton, prompt file and ledger block are prose no gate compiles, imports
or runs). Executor model: `claude-sonnet-5`. Map vs actual: matches §16.1
exactly.

## Operator inputs

- **Run configuration (CFG-01), source `.env` (lab-written 2026-09-17,
  never read directly by the executor — only through `load_config()`):**
  `LLM_PROVIDER=openrouter`, `OPENROUTER_MODEL=openai/gpt-4.1-mini`,
  `LMSTUDIO_BASE_URL`/`LMSTUDIO_MODEL` empty,
  `EMBEDDING_BASE_URL=https://openrouter.ai/api/v1`,
  `EMBEDDING_MODEL=openai/text-embedding-3-small`, `EMBEDDING_DIM=1536`,
  `LLM_RERANK_MODEL=openrouter:mistralai/mistral-small-24b-instruct-2501`,
  `LLM_JUDGE_MODEL=openrouter:openai/gpt-4.1`, `LLM_EVAL_CHAT_MODEL` unset,
  `DB_PATH=data/run-v1101.db`.
- **Chat client `describe()`:** `('openrouter', 'openai/gpt-4.1-mini')`
- **Judge client `describe()`:** `('openrouter', 'openai/gpt-4.1')`
- **Rerank route:** `openrouter:mistralai/mistral-small-24b-instruct-2501`
  (unchanged since v1.9.1)
- **Stage 0 check-6 fallback used:** no
- **REV-04 embedder switch (Stage B″):** not used (not reached)

## T1 — embeddings over OpenRouter, gate 5's route rules

`embedding_api_key` resolved from `OPENROUTER_API_KEY` through one
`is_openrouter_url(url)` helper in `config.py` (imported by
`llm/embeddings.py`, preserving the existing `llm → config` direction —
`T-V1101-CFG-05`'s fresh-interpreter smoke proves no import cycle).
`EmbeddingsClient` sends `Authorization: Bearer` only with a non-empty key
(`llm/embeddings.py:_post`); `describe()` is provider-aware over the same
helper, and the `gen_ai.provider.name` span attribute now reads
`self.describe()[0]`. The three T1 constructor sites
(`bot.py:_live_embeddings`, `bot.py:main()`, `devtools/rag_eval.py:main()`)
pass `api_key=cfg.embedding_api_key`; the fourth (gate 8's runner) is T3's
job. `_live_lmstudio` gained the route-rule SKIP; `_live_embeddings`
dropped the unauthenticated `/models` listing step, keeping only the
authenticated round-trip.

27 new tests: `tests/test_v1101_config.py` (9 — `is_openrouter_url`,
`embedding_api_key` resolution, `T-V1101-EC-02`'s offline storage-preflight
expression including the `ConfigError`-on-mismatched-pair case), `tests/
test_v1101_embeddings.py` (18 — the fresh-interpreter import smoke, the
header/describe()/error-message pins, the AST source pin on the three
constructor sites, `T-V1101-G5-01…03`). Two renames inside `tests/
test_v190_embeddings.py` (`:381-389`, `:404-409`) per EC-02's exhaustive
amendment list — nothing else in that file touched. `tests/
test_v1_guardrails.py:1425-1445` re-checked, green, unamended.

Gates 1-4 green offline (pytest: 1895 collected). Gate 5 and gate 7 live,
in sequence, nothing else concurrent:

| # | Gate | Exit | Wall | Detail |
| --- | --- | --- | --- | --- |
| 5 | `bot.py --selftest-live` | 0 | — | `OK config`, `OK db`, `OK docker (29.8.0)`, `OK telegram`, `SKIP lmstudio (no route uses it)`, `OK embeddings`, `OK openrouter` — capable-of-green rule (G5-02) now holds from this tree on |
| 7 | `rag_eval.py` | 0 | 35.4s | hybrid recall@5=1.000, mrr=1.000, page_hit_rate=1.000 (vector and hybrid+rerank likewise 1.000); advisory conversation-aware smoke — TOOL-06 pin **fail**, context-proof **fail** (no `search_documents` call on turns 2/3) — non-blocking (NG-07); PRM-01/02 (T4) targets exactly this pattern |

Not reused as PRM-02's "before" measurement (T4 runs its own pair). No
Stage B″ needed (`recall@5` green on the first live attempt with the new
embedder).

Delegated (general-purpose subagent, brief `docs/spec/task-briefs/v1101-T1.md`).
Commit `4b18804`. Map vs actual: matches §16.1 exactly.

## T2 — not reached: T1

## T3 — not reached: T1

## T4 — not reached: T1

## T5 — not reached: T1

## T6 — not reached: T1

## T7 — not reached: T1

## T8 — not reached: T1

## Ledger row (paste into `economics.md`)

Provisional — filled finally at T7/T8:

```
not reached: T0
```
