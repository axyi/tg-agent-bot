# tg-agent-bot v1.9.5 -- patch report

User's decision, relayed by the coordinator: push this out as a tagged
release ("Push + PR + tag v1.9.x"), not a bare bug-fix commit. Patch
release, no spec file (precedent v1.5.1, v1.9.1-v1.9.4). Two tasks: **T1**
-- fix GitHub issue #3 (`vec_chunks`/`rag.embedding` never bound at
`bot.py` startup on a RAG-configured deployment) plus its clean-context
review closure; **T2** -- version bump and paperwork close. Baseline:
`877127c` (tag `v1.9.4`, committed locally but never successfully pushed
-- see Disclosures).

## T1 -- bind the embedding pair at every `init_schema` call site

Contract: `docs/spec/task-briefs/v195-T1.md`, prompt 188. Fixes GitHub
issue #3 (axyi/tg-agent-bot).

**The bug.** `storage.init_schema(conn, *, embedding_dim=None,
embedding_model="")` creates `vec_chunks` and writes the `rag.embedding`
state key only when `embedding_dim` is passed -- `None` is the documented
RAG-off no-op (REQ-V190-EC-05). All three of `bot.py`'s call sites
(`main()`, `run_selftest()`, `_live_db()`) called it bare, even though
`cfg.embedding_dim`/`cfg.embedding_model` were one line away. On a
RAG-configured deployment, `vec_chunks` was therefore never created, and
every document upload failed with "Storage error. The document was not
saved." (`OperationalError: no such table: vec_chunks`).

**The fix.** One shared helper, `_init_startup_schema(conn, cfg)`, that
all three call sites now use exclusively -- they can no longer drift
apart. `main()`'s call site gained a `try`/`except ConfigError` wrapped
around it, matching `_startup_docker_wiring`'s own sibling pattern
(redacted log, close what is open so far, exit 2): this makes
`_bind_new_embedding_pair`'s/`_rebind_embedding_pair`'s `ConfigError`
(orphaned `vec_chunks`, or the pair changed while documents exist)
reachable from `main()` for the first time. `run_selftest()`'s
placeholder `Config` never sets the pair, so routing it through the same
helper stayed a no-op there (gate 4 stayed offline, confirmed); `_live_db
()`'s existing `except Exception` already turned a rebind refusal into a
normal `live: FAIL db` line.

**Tests.** Two new tests in `tests/test_routing.py`'s "Startup wiring
(bot.main)" section, through `bot.main` -- not a hand-built connection:
`test_v195_main_binds_vec_chunks_and_the_rag_state_key` (the AC's own
regression test -- red on pre-fix HEAD, `assert None is not None` on
`vec_chunks` in `sqlite_master`; green after) and
`test_v195_main_exits_2_when_startup_schema_binding_refuses` (the new
`ConfigError`->exit-2 path, via a monkeypatched raise). One new mutation
entry, `v195-init-schema-drops-the-pair`, anchored on `main()`'s call
site next to its own `except ConfigError` line (the bare call text alone
is a substring of the other two, more-indented call sites -- verified
`count==1` and that the mutated source still compiles); killed via
`--only` and again in the full run.

**Paperwork.** `docs/spec/spec-v1.9.0-delta-2.md` records REQ-V190-STO-04
as `bot.py`'s responsibility too, not only `storage.init_schema`'s.
`README.md`'s Storage/Limitations wording already described
`init_schema`'s own mechanics correctly and needed no change.

**Environment issue hit mid-task.** Before gate 3 could run, this
session's local `core.hooksPath` was found set to an absolute path
instead of the relative `.githooks` the doctor gate expects. Confirmed
pre-existing and unrelated to this fix (reproduced identically on a
clean stash back to `877127c`, and `.git/config`'s mtime postdated that
commit by ~35 minutes, consistent with leftover tooling state, not a
deliberate choice). Fixed by the user running the repo's own
`devtools/install_hooks.py` -- no raw `git config` edit by the assistant.
Also explains why `877127c` (v1.9.4) was never pushed: `git push`'s own
pre-push hook runs the same doctor-style gate and would have refused on
the same absolute-path config, so v1.9.4 stayed local until this session.

**Delegation record.** Executor model: `claude-sonnet-5` (Claude Code).
Delegated, brief `docs/spec/task-briefs/v195-T1.md`; commit `3f884ef`
(bind the embedding pair at every `init_schema` call site).

## T1 review closure -- exc_info proof, real ConfigError proof, usage row

Clean-context review of `3f884ef`: no 🔴, two request-changes and one
should-fix, all closed in one follow-up commit.

1. **Request-changes.** `test_v195_main_exits_2_when_startup_schema_
   binding_refuses`'s `all("Traceback" not in r.getMessage() for r in
   caplog.records)` was structurally incapable of catching a traceback
   leak -- `LogRecord.getMessage()` is only `msg % args`, it never renders
   `exc_info`, so the assertion would stay green even under
   `log.exception(...)`. Fixed to `all(r.exc_info is None for r in
   caplog.records)`. `tests/test_v12_patch.py:743-760`'s identical
   pre-existing pattern for the sibling `load_config` catch is left
   alone, out of scope.
2. **Should-fix.** That same test only proved `main()`'s `except
   ConfigError` wiring via a monkeypatched raise, never that a *real*
   `_bind_new_embedding_pair`/`_rebind_embedding_pair` `ConfigError`
   reaches it end to end. Added
   `test_v195_main_exits_2_on_a_real_pair_change_refusal`: seeds a real
   database (`storage.init_schema` under one pair plus one indexed
   document via `storage.add_document`, then `bot.main([])` started
   under a different configured pair), asserting the real STO-04 rebind
   refusal reaches exit 2 with no traceback and that the stored pair and
   the document both survive untouched -- independently verified by hand
   that `storage.init_schema` alone raises the real `ConfigError` in this
   exact setup.
3. **Request-changes.** Backfilled `docs/llm-usage.md` row 98 for prompt
   188/commit `3f884ef` (missing despite the brief's and the issue's own
   DoD checklist requiring it); row 99 covers the closure prompt itself.

Everything else in the review (`devtools/bench.py`'s bare `init_schema`
call, AC-1 verified transitively, `_live_db`'s newly-effective production
write, the stale 1634/119 counts) was 🟢 informational, correctly out of
scope or already correctly disclosed, left untouched.

**Acceptance** (test-only + docs, no production code touched, no
mutation-entry `find` string moved, no RAG-path file touched -- the
lighter gate-subset precedent `docs/llm-usage.md` row 96 used for the
v1.9.4 review close-out of the same shape): `ruff check .`/`ruff format
--check .` 0/0; `pytest` 0, 1637 collected (1636 passed, 1 skipped);
`bot.py --selftest` 0; `checks.py lint-docs` 0.

**Delegation record.** Executor model: `claude-sonnet-5` (Claude Code).
Delegated (the coordinator's review comment is this closure's own
contract, no separate brief file); commit `88745d1` (exc_info proof,
usage row).

## T2 -- version bump, paperwork, authoritative gates, tag

Contract: this task, prompt 190 (coordinator's own chat message; no
separate task-brief file this time -- precedent v1.9.4 T5).

**Version.** `pyproject.toml`'s `project.version` 1.9.4 -> 1.9.5,
`uv.lock` regenerated to match (`uv lock`). `tests/test_v195_version.py`
(`T-V195-VER-01`) red before the bump (`AssertionError: assert '1.9.4' ==
'1.9.5'`), green after. `tests/test_v194_version.py` repointed to the
frozen `v1.9.4` git-tag blob (`git show v1.9.4:pyproject.toml`), the same
convention `tests/test_v180_version.py` through `tests/test_v193_
version.py` already carry, never deleted (REQ-V190-EC-03).

**Count-bearing lines**, measured after every other edit in this task:
1638 tests (`pytest`, 1637 passed + 1 skipped), 120 mutation entries
(unchanged by this task's own edits -- the one new `v195-*` entry was
already landed by T1). `AGENTS.md`'s gate-3 line moved 1634 -> 1638, its
gate-6 line moved 119 -> 120 with the narrative extended to name the one
new `v195-*` entry, attributed to "v1.9.5 T1". `tests/test_v190_agents.
py`'s and `tests/test_v170_bench.py`'s own count-bearing/`report_path`
tests renamed (`test_t_v194_*` -> `test_t_v195_*`) and repointed to
assert 1638/120 and `report-v1.9.5.md`. README's release table gained a
`v1.9.5` row; the `v1.9.4` row's own "this release" clause dropped.
`config/quality_gates.yaml`'s `lint-docs.report_path` repointed
`report-v1.9.4.md` -> `report-v1.9.5.md` (REQ-V190-RPT-01).

**Delegation record.** Executor model: `claude-sonnet-5` (Claude Code).
Delegated; this commit (version bump, count-bearing lines, paperwork,
seven gates, tag).

## Gates (T2, final tree, verbatim from AGENTS.md, in order)

Nothing else on the box during gate 6; gate 6 and gate 7 not run
concurrently. Gate 7 on the production route (`LLM_EVAL_CHAT_MODEL`
unset). Full runs throughout -- no `--only`/`--select` subset, this being
the release-closing commit.

| # | Gate | Exit | Wall |
| --- | --- | --- | --- |
| 1 | `uv sync --locked` | 0 | 0.047s |
| 2 | `ruff check .` | 0 | 0.130s |
| 3 | `pytest` | 0 | 59.397s (1637 passed, 1 skipped, 1638 collected) |
| 4 | `bot.py --selftest` | 0 | 0.607s |
| 5 | `bot.py --selftest-live` | 0 | 2.790s (all seven live checks OK, including `lmstudio`) |
| 6 | `mutation_check.py` (no `--select`) | 0 | 767.739s (120/120 killed, 0 survived, 0 errored, 0 drifted) |
| 7 | `rag_eval.py` | 0 | 392.066s (PASS: hybrid recall@5=1.000, hybrid+rerank recall@5=1.000; one rerank 429 retried and succeeded on attempt 2; advisory conversation-aware smoke -- TOOL-06 pin: fail, turn 2 answered from turn-1 context with no `search_documents` call, the same non-defect model-behaviour prior releases document; context-proof: pass, turn 3 returned the gold source `vacation_policy.md`) |

## Delegation record

Every executor model named: T1 implementer `claude-sonnet-5`; T1 review
closure implementer `claude-sonnet-5`; T2 (this task) implementer
`claude-sonnet-5`.

- T1 -- delegated, brief `docs/spec/task-briefs/v195-T1.md`; executor
  `claude-sonnet-5`; commit `3f884ef` (bind the embedding pair at every
  `init_schema` call site).
- T1 review closure -- delegated (the review comment is the contract, no
  separate brief file); executor `claude-sonnet-5`; commit `88745d1`
  (exc_info proof, usage row).
- T2 -- delegated (coordinator's chat message is the contract, no
  separate brief file, precedent v1.9.4 T5); executor `claude-sonnet-5`;
  this commit (version bump, count-bearing lines, paperwork, seven gates,
  tag).

## Disclosures

- **Trailer string.** Every commit in this release carries
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`, matching the
  session's own named attribution string exactly -- no mismatch to
  disclose this release.
- **`core.hooksPath` environment issue.** This session's local git config
  had `core.hooksPath` set to an absolute path instead of the relative
  `.githooks` the doctor gate expects, blocking gate 3 mid-T1. Not a code
  change: fixed by the user running the repo's own
  `devtools/install_hooks.py`. No raw `git config` edit was made by the
  assistant at any point.
- **`origin/main` was still at v1.9.3 when this session started.**
  `v1.9.4` (`877127c`) had been committed locally but never successfully
  pushed -- its push almost certainly failed on the same `core.hooksPath`
  doctor gate this session hit and fixed mid-T1 (`git push`'s own
  pre-push hook runs the equivalent check). `origin/main` will be caught
  up to this release when the coordinator pushes.
- **Ledger row for the `3f884ef` review.** Clean-context review of
  `3f884ef`: 0 🔴, 2 request-changes + 1 should-fix, all three closed in
  `88745d1` (see "T1 review closure" above).

## Open tail

- No new open items surfaced by T1, its review closure, or T2. The
  v1.9.4 report's two carried-forward v1.10 candidates (LM Studio
  model-swap measurement; the smoke/agent prompt not compelling a
  document search) remain open, untouched by this release.

## Ledger row (paste into `economics.md`)

Review findings counted from the review comment itself, not from memory:
0 🔴, 2 request-changes + 1 should-fix (3 total), all closed in `88745d1`.

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | v1.9.5 | 2026-09-13 | -- (patch, no new spec; task brief `docs/spec/task-briefs/v195-T1.md`; T2 and the review closure had no separate brief file) | 3 (188-190) | yes -- all seven gates green on the authoritative run of the final tree | review 0 red / 2 request-changes / 1 should-fix (3) -- all fixed | unknown (harness does not expose per-request usage) | $0 marginal (Claude Code subscription-metered session; live inference only on gates 5/7, at reference/list prices, no metered spend tracked) | claude-sonnet-5 | Claude Code |
```

## Verdict

All seven gates green on the final tree (see "Gates (T2)" above): GitHub
issue #3 is fixed (`vec_chunks`/`rag.embedding` now bind at `bot.py`
startup through one shared `_init_startup_schema` helper on all three
call sites, closing every document-upload failure on a RAG-configured
deployment) and its review's three findings (two request-changes, one
should-fix) are closed without rewriting the reviewed commit. Version
bumped 1.9.4 -> 1.9.5, count-bearing lines at their real final numbers
(1638 tests, 120 mutation entries), annotated tag `v1.9.5` created on the
release commit, not pushed. No open items carried by this release beyond
the two v1.10 candidates already open since v1.9.4. PASS.
