# tg-agent-bot v1.9.2 -- patch report

## T1 -- whole-tree static analysis and fixes

Operator's decision (`docs/spec/task-briefs/v192-handoff.md`, verbatim):
"полный глубокий анализ кода проекта тулами skylos, trivy и прочее, не
только diff, но весь код; исправление всех проблем". Contract:
`docs/spec/task-briefs/v192-T1.md` (prompt 164 for §A/§C, prompt 165 for
§B). Baseline: `7a97f29` (tag `v1.9.1`).

### Inventory (verbatim from the task brief, measured 2026-09-12 on `7a97f29`)

| Tool (pin) | Invocation | Exit | Findings |
|---|---|---|---|
| ruff 0.16.6 `check .` | project rule set `E,F,I` | 0 | **0** |
| ruff 0.16.6 `format --check .` | whole tree | 1 | **75 files would be reformatted** (63 `.py` outside `docs/`); §B |
| skylos 4.35.0 `--gate --strict` | whole tree | 1 | **27**: 2 unused functions, 6 unused variables, 19 unused parameters; 0 imports / classes / files |
| semgrep 1.176.0 `--severity ERROR` | `.semgrep/` rules, target `.` | 0 | **0** at ERROR; 3 below threshold: 2 x INFO inside `.semgrep/p-security-audit.yaml` itself, 1 x WARNING `storage.py:439 insecure-file-permissions` |
| gitleaks 8.30.1 `dir` | `git archive HEAD` tree | 0 | **0** in tracked files |
| trivy 0.74.0 `fs vuln,misconfig,secret` | all severities | 0 | **0** |
| pip-audit (ad hoc) | `uv export --locked` | 0 | **0** known vulnerabilities |
| ruff, non-selected rules | `--select B,S,UP,SIM,C4,PERF,RUF,PL,PIE,RET,ARG,PTH,T20,DTZ,TRY,BLE,A,N` | - | 5490 (3689 `S101` in tests, 474 `PLR2004`, 277 `TRY003`, 362 `ARG*`); outside `tests/`, the bug-class families give **398**, dominated by 225 `TRY003` and 31 `RUF100` |

### Re-measured after this prompt's fixes (commit 1, prompt 164)

| Tool | Exit | Findings |
|---|---|---|
| `ruff check .` | 0 | 0 (select now `E,F,I,B,RUF100`) |
| `ruff format --check .` | 1 | 75 files (unchanged -- §B is prompt 165's own commit) |
| `skylos . --gate --strict` | 1 | **0** (see §A #8: the operator ruled `_MIGRATION_2_TO_3` out too, superseding its own earlier retention note) |
| `semgrep scan --config .semgrep/ --exclude .semgrep ...` | 0 at `--severity ERROR`; **1** at any severity | `storage.py:439` only -- the 2 self-scan INFO findings are gone |
| `pytest` | 0 | 1593 collected, all passed, ~73s wall clock |
| `python bot.py --selftest` | 0 | `selftest: OK` |
| `python devtools/checks.py lint-docs` | 0 | -- |
| drift script (throwaway, imports `MUTATIONS` from `devtools/mutation_check.py`) | 0 | **108/108** find strings match exactly once |

### A. skylos -- all 27 findings, individually decided

Decision procedure (brief §A): (1) interface-mandated -> keep + inline
`# skylos: ignore` naming the interface; (2) referenced by a `find`
string/reflection -> keep + inline suppression naming the reference;
(3) genuinely dead, no reference anywhere, reason gone -> delete
(operator asked for the cleanup this task); (4) uncertain -> leave, list
as such. skylos 4.35.0 does support an inline pragma (`# skylos: ignore`,
verified against its installed source, `skylos/config.py`'s
`_SKYLOS_IGNORE_RE`), so step (1)'s pragma path applies throughout.

| # | Kind | Location | Decision | Reason (procedure step) |
|---|---|---|---|---|
| 1 | function | `dashboard_server.py:128 _service_unavailable` | **deleted** | (3) no reference anywhere (`grep -rn`), introduced with the module at v1.6.0 T6, never called, no report/spec disposition protecting it |
| 2 | function | `dashboard_server.py:272 _histogram_json` | **deleted** | (3) same as #1 -- a `metrics.Histogram`-to-JSON helper with no caller; `_span_json` (its sibling) is used, this one never was |
| 3 | variable | `agent.py:65 SUMMARY_KEYS` | **deleted** | (3) no reference anywhere; `_normalise_summary` (agent.py) already hardcodes the five keys individually with per-key type coercion, so the tuple never drove anything -- introduced alongside `SUMMARY_PROMPT` at spec-v1 (`c9f7912`) and never wired up |
| 4 | variable | `config.py:70 FORBIDDEN_SCOPES` | **kept, suppressed** | (2) `docs/reports/report-v1.2.md` already ruled this "not a defect": REQ-V12-SSR-02 requires the constant to exist as written, documenting `address_scope`'s return vocabulary even though the function returns its literal strings directly |
| 5 | variable | `dashboard_server.py:43 _TRACE_ID_RE` | **deleted** | (3) no reference anywhere; introduced with the module at v1.6.0 T6, immediately superseded by `_TRACE_PAGE_RE`/`_TRACE_API_RE` (route regexes that embed and validate the same 32-hex pattern via their capture groups) |
| 6 | variable | `dashboard_server.py:53 _STATIC_ROUTES` | **deleted** | (3) no reference anywhere; explicitly documented as pre-existing dead code across three releases (`docs/spec/spec-v1.8.0.md:753`, `docs/reports/report-v1.9.0.md:387`) -- the routing dispatch at `do_GET` uses an explicit `if path == "..."` chain that duplicates the same literals instead of consulting this set. Reason recorded each time was "not fixed, only recorded"; this task is the first with an explicit cleanup mandate |
| 7 | variable | `devtools/bench.py:177 PRICING_BASES_WITH_MODEL` | **deleted** | (3) no reference anywhere; introduced at spec-v1.3 stage A, never read by any pricing-base check in the file |
| 8 | variable | `storage.py:243 _MIGRATION_2_TO_3` | **deleted (operator ruling)** | (3), operator-ruled: initial disposition was "kept, unsuppressed" -- the flagged line (`_MIGRATION_2_TO_3 = """`) opens a triple-quoted SQL string, so no inline suppression comment is even mechanically possible there, and the constant's own comment block (`storage.py:236-242`) said it stays "only because deleting it is an unlisted edit the amendment table doesn't call for." The operator's whole-tree cleanup order supersedes that bookkeeping reason and directed deletion under §A.3: (a) `grep -rn _MIGRATION_2_TO_3` finds no reference outside `storage.py` itself; (b) the removed comment block already gave the history -- not reached by `init_schema`'s chain since `_MIGRATION_2_TO_4` became the real 2->4 step (confirmed by reading `init_schema`'s call sequence: it calls `_MIGRATION_1_TO_2`, `_MIGRATION_2_TO_4`, `_MIGRATION_3_TO_4`, `_MIGRATION_4_TO_5` -- never `_MIGRATION_2_TO_3`); (c) `grep -n _MIGRATION_2_TO_3 devtools/mutation_check.py` finds no `find` string touching it, confirmed empty by the drift script both before and after removal. Constant and its explanatory comment block both deleted |
| 9 | parameter | `agent.py:142 now` (`build_system_prompt`) | **kept, suppressed** | (1) interface-mandated by convention: the function's own docstring already states callers still pass it positionally (`devtools/bench.py`, the v1 tests) |
| 10 | parameter | `bot.py:1494 signum` | **kept, suppressed** | (1) `signal.signal` callback signature |
| 11 | parameter | `bot.py:1494 frame` | **kept, suppressed** | (1) same as #10 |
| 12 | parameter | `bot.py:1524 messages` (`_SelftestLLM.complete`) | **kept, suppressed** | (1) `LLMClient` is a `Protocol` (`llm/base.py:175`); `_SelftestLLM.complete` implements its `complete(...)` signature structurally |
| 13 | parameter | `bot.py:1525 tool_definitions` | **kept, suppressed** | (1) same as #12 |
| 14 | parameter | `bot.py:1527 max_tokens` | **kept, suppressed** | (1) same as #12 |
| 15 | parameter | `bot.py:1528 reasoning` | **kept, suppressed** | (1) same as #12 |
| 16 | parameter | `bot.py:1529 timeout_s` | **kept, suppressed** | (1) same as #12 |
| 17 | parameter | `dashboard_server.py:534 format` (`log_message`) | **kept, suppressed** | (1) `http.server.BaseHTTPRequestHandler.log_message`'s stdlib signature (already carried a `# noqa: A002` before this task; see RUF100 note below) |
| 18 | parameter | `dashboard_server.py:534 args` | **kept, suppressed** | (1) same as #17 |
| 19 | parameter | `dashboard_server.py:538 format` (`log_error`) | **kept, suppressed** | (1) same stdlib override, `log_error` |
| 20 | parameter | `dashboard_server.py:538 args` | **kept, suppressed** | (1) same as #19 |
| 21 | parameter | `devtools/checks.py:1510 profile` (`execute_builtin_gate`) | **kept, suppressed** | (1) uniform gate-executor call signature shared with `execute_command_gate` (both are invoked identically from `run_profile`'s per-gate loop; `execute_command_gate` uses `profile` for its artefact path template, `execute_builtin_gate` does not need it but must accept it) |
| 22 | parameter | `devtools/checks.py:1613 args` (`cmd_doctor`) | **kept, suppressed** | (1) `args.func(args)` dispatch (`devtools/checks.py:1679`) calls every `cmd_*` handler uniformly |
| 23 | parameter | `devtools/checks.py:1633 args` (`cmd_lint_docs`) | **kept, suppressed** | (1) same dispatch convention as #22 |
| 24 | parameter | `devtools/rag_eval.py:303 argv` (`_refusing_runner`) | **kept, suppressed** | (1) `CommandRunner` callback signature -- the stub always refuses, matching the `runner(argv) -> dict` contract other runners implement; already carried `# pragma: no cover -- never invoked` (coverage.py, unrelated to skylos), preserved alongside the new suppression |
| 25 | parameter | `tools.py:996 attrs` (`handle_starttag`) | **kept, suppressed** | (1) `html.parser.HTMLParser.handle_starttag` override |
| 26 | parameter | `tools.py:1007 attrs` (`handle_startendtag`) | **kept, suppressed** | (1) `html.parser.HTMLParser.handle_startendtag` override |
| 27 | parameter | `tracing.py:129 span` (`NullSink.write`) | **kept, suppressed** | (1) `SpanSink` `Protocol` (`tracing.py:123`) -- `NullSink` implements `write(self, span) -> None` by design, dropping every span |

**Totals: 7 deleted (2 functions, 5 variables), 20 kept-and-suppressed, 0
kept-unsuppressed.** Post-fix `skylos . --gate --strict` count: **0**.
(Finding #8, `_MIGRATION_2_TO_3`, was initially dispositioned "kept,
unsuppressed" and then deleted on the operator's explicit ruling after
this prompt's first pass -- see #8's own row for the (a)(b)(c) evidence;
`f421621` was amended to carry the deletion so commit 1 holds all of
§A's work.)

### B -- reformat (prompt 165)

`uv run --locked ruff format .` (project config, no extra flags) reformatted
63 non-`docs/` `.py` files. It also touched 11 `docs/*.md` files (spec-v1.5's
own reason: ruff reformats fenced code blocks in markdown); those were
reverted (`git checkout --`), and `docs/**` is now excluded in
`[tool.ruff.format]` so `ruff format --check .` honours that without
runner-side filtering going forward -- this formalises spec-v1.5's own
already-decided policy, not a new exception.

**The operator's two rulings, both applied:**

1. `devtools/bench_scenarios.py` -- **option (b)**: reverted to its
   pre-reformat bytes, permanently excluded from `[tool.ruff.format]`
   (`pyproject.toml`), commented and dated, citing REQ-V13-BEN-12
   (`devtools/bench.py:335-340`'s `scenarios_sha256()` hashes the file's raw
   bytes; that hash is pinned inside 15 committed
   `docs/assets/bench/*.json` artefacts -- frozen measurement records,
   never edited to match new bytes). Its mutation entry
   (`v13-bench-turn-zero-based`, `devtools/mutation_check.py`, path
   `devtools/bench_scenarios.py`) was left exactly as it was -- the file's
   bytes never changed, so nothing to re-derive. `ruff check` still lints
   the file; only the formatter skips it.
2. `storage.py:243 _MIGRATION_2_TO_3` -- **deleted**, under §A.3, with
   (a)(b)(c) evidence now in §A's table above (row 8). Commit 1
   (originally `f421621`) was amended to `6c9a904` to carry this, so
   commit 1 holds all 27 of §A's skylos decisions, not 26 of 27. The
   skylos post-fix count moved from 1 to **0**; §C.5 above is updated to
   match, and the "flip to blocking is one YAML line" note now applies
   cleanly (not flipped -- left to the operator).

**9 re-derived `find`/`replace` pairs** (mutation semantics unchanged, only
byte layout re-matched against the reformatted source):

| id | path | what changed under reformat |
|---|---|---|
| `cov-09-probe-user-flag` | `tools.py` | docker-argv list: one item per line instead of grouped pairs |
| `v13-compact-keeps-head-only` | `tools.py` | a space added before a slice colon: `lines[len(head) :]` |
| `v13-llm-call-not-recorded-on-error` | `agent.py` | `_record_llm_call(...)` call: one argument per line |
| `v170-summary-retry-ignores-budget` | `agent.py` | `_ask_for_summary(...)` call: one argument per line |
| `v13-bench-skipset-ignored` | `devtools/bench.py` | `LOCKED_META_FIELDS` tuple: one item per line |
| `v13-bench-scenario-hash-ignored` | `devtools/bench.py` | same tuple, same reformat (shares its find string with the row above) |
| `v170-config-hash-includes-treatment` | `devtools/bench.py` | `CONFIG_HASH_EXCLUDED` set literal: one item per line, one indent level deeper (now nested in `frozenset({...})`) |
| `v160-readonly-connection-writable` | `storage.py` | the `sqlite3.connect(...)` call in `connect_readonly` merged onto one line (98 chars, under the 100-char limit) |
| `v170-failover-drops-reasoning` | `llm/failover.py` | `self._clients[other].complete(...)` call: one argument per line |

One incidental fix the reformat forced, not itself a re-derivation:
`tests/test_v11_patch.py`'s `monkeypatch.setattr(agent, "summarize_conversation", lambda ...)`
had a lambda signature ruff's formatter cannot wrap across lines (Python
lambdas take no multi-line parameter list), leaving a 101-char `E501` after
the reformat. Converted to a small named nested function with the same
body and the same `monkeypatch.setattr` call; behaviour-preserving,
verified green.

**§B.4 -- `ruff format --check` now blocking whole-tree.** Added
`ruff-format-all` (`config/quality_gates.yaml`): the generic
`execute_command_gate` path, no `blocking_paths` key, `diff_scoped: false`,
`argv: [uv, run, --locked, ruff, format, --check, "."]` -- the same shape
`ruff-check-all` already uses next to diff-scoped `ruff-check`, confirmed
against `devtools/checks.py:1174-1215`. No runner code change, so no new
runner test. Wired into `pre-push`/`full` in place of the old diff-scoped
`ruff-format`, which now stays only in `pre-commit` (a fast per-commit
check on the staged diff; its `blocking_paths` partition still protects
`devtools/checks.py`, `devtools/install_hooks.py`,
`tests/test_v15_standards.py`). `docs/spec/spec-v1.9.0-delta-1.md`'s gate
matrix table split its one `` `ruff format --check` `` row into
`(staged)`/`(tree)`, the same split `` `ruff check` `` already has;
`tests/test_v15_standards.py`'s `_GATE_MATRIX_LABEL_TO_NAME` gained the
matching second entry (added, not replaced).

**§B.5 -- both exit 0.** `ruff check .`: exit 0. `ruff format --check .`:
exit 0, **92 files already formatted, 0 would reformat**.

**Drift, both before and after this prompt's changes:** throwaway script,
**108/108** find strings match exactly once.

**The nine `--only` reruns**, sequential, nothing else touching the tree:
all nine **killed** --
`cov-09-probe-user-flag`, `v13-compact-keeps-head-only`,
`v13-llm-call-not-recorded-on-error`, `v170-summary-retry-ignores-budget`,
`v13-bench-skipset-ignored`, `v13-bench-scenario-hash-ignored`,
`v170-config-hash-includes-treatment`, `v160-readonly-connection-writable`,
`v170-failover-drops-reasoning`. Each restored the mutated file exactly
(verified byte-for-byte by `mutation_check.py` itself); confirmed with a
final drift-script run and `ruff check`/`ruff format --check` re-run
afterward, both still clean. The full 108-entry `mutation_check.py` run
(gate 6) is out of scope for this task (T3's own gate run).

REQ-V15-NG-04 is closed.

### C. Beyond skylos

**C.1 semgrep scanning its own rule pack.** `config/quality_gates.yaml`'s
`semgrep` gate argv gained `--exclude, ".semgrep"` (least invasive: one
argv token, no new `.semgrepignore` file, no change to
`tests/test_v15_standards.py`'s own offline-semgrep test, which builds its
own literal argv independently and was already unaffected -- it asserts on
`--severity ERROR` behaviour that the two INFO-level self-scan findings
never touched). Verified: `semgrep scan --config .semgrep/ --exclude
.semgrep ...` now reports 0 findings under `.semgrep/` at any severity,
and 1 total (the already-reviewed `storage.py:439`).

**C.2 `storage.py:439` insecure-file-permissions (WARNING).** Reviewed,
dismissed, no code change: `os.chmod(parent, 0o700)` tightens permissions
(owner-only), which is the intended posture for the sqlite data directory.

**C.3 17 ruff bug-class hits, individually reviewed** (`ruff check . --select
S608,S311,S108,S110,RUF012,PLW0603,B905 --exclude tests --output-format
concise`):

| # | Rule | Location | Disposition | Reason |
|---|---|---|---|---|
| 1 | S608 | `storage.py:344` | dismissed | `_MIGRATION_5_TO_6`'s statements, split from a module-constant DDL string, never request-shaped |
| 2 | S608 | `storage.py:1005` | dismissed | `placeholders` is `", ".join("?" for _ in requested)` -- bind-parameter placeholders built from a count, not a value; all real values pass as `execute` params |
| 3 | S608 | `storage.py:1099` | dismissed | same placeholder-count pattern as #2 |
| 4 | S608 | `storage.py:1272` | dismissed | same placeholder-count pattern as #2 |
| 5 | S608 | `storage.py:1314` | dismissed | `table` is one of two literal, hard-coded names (`llm_calls`/`tool_calls`), already commented in-file as "never request-shaped" |
| 6 | S608 | `storage.py:1358` | dismissed | `_insert_row`'s `table`/`columns` come only from three call sites passing literal table names (`llm_calls`, `tool_calls`, `spans`) and a `row` dict built from fixed internal column sets, never from user input |
| 7 | S311 | `bot.py:1459` | dismissed | `random.uniform(0.0, 0.5)` is backoff jitter for the polling retry loop, not security-relevant |
| 8 | S108 | `tools.py:58` | dismissed | `CONTAINER_TMPFS = "/tmp:rw,size=..."` is a docker `--tmpfs` mount-spec string for the sandbox container, not host tempfile handling |
| 9 | S110 | `rag.py:413` | dismissed | guards the `log.warning` call itself inside the rerank fallback path; logging the exception here would risk the same failure it is defending against |
| 10 | S110 | `rag.py:526` | dismissed | same logger-guard pattern as #9, source-stripping warning |
| 11 | S110 | `tools.py:219` | dismissed | best-effort `stream.close()` in a `finally` block; the stream may already be closed, and a close failure here is not actionable |
| 12 | RUF012 | `dashboard_server.py:767 _CONVERSATIONS_NAV` | **fixed** | mutable `list` class attribute -> converted to a tuple of tuples, matching the file's own sibling pattern (`_SECURITY_HEADERS`, already a tuple) -- read-only nav data, never mutated |
| 13 | PLW0603 | `bot.py:1495 _shutdown` | dismissed | module-level shutdown flag, the signal-handler pattern this file already uses |
| 14 | PLW0603 | `bot.py:1886 _started_at` | dismissed | module-level process-start timestamp, same pattern |
| 15 | PLW0603 | `tracing.py:175 _dropped_spans` | dismissed | module-level counter guarded by `_dropped_spans_lock`, same pattern |
| 16 | B905 | `config.py:702` | **fixed** | `zip(keys, (raw_input, raw_output), strict=True)` -- both operands are always exactly length 2 by construction |
| 17 | B905 | `rag.py:111` | **fixed** | `zip(rows, scores, strict=True)` -- `bm25.get_scores()` always returns one score per row in the corpus |

**Totals: 3 fixed (1 RUF012, 2 B905), 14 dismissed with reasons, 0
scanner-exclusion-as-fix.**

**C.4 `RUF100` (unused noqa) and the select additions.** Order followed:
(1) fixed the 2 production `B905` sites above; (2) fixed the 13 additional
`B905` sites `--select B905` found in `tests/` (10 sliding-window
`zip(x, x[1:])` pairs across `tests/test_docker.py`,
`tests/test_v11_patch.py` and `tests/test_v190_chunking.py` -> `strict=False`,
since the two operands are deliberately different lengths by one; 3
same-length pairs across `tests/test_v190_agents.py`,
`tests/test_v190_embeddings.py`, `tests/test_v190_retrieval.py` ->
`strict=True`, since both operands are built together from the same
source); (3) one pre-existing `B007` (`tests/test_v1_guardrails.py:910`,
unused loop variable `i`) surfaced once `B` was added to `select` and was
renamed to `_i` (trivial, ruff's own suggested fix) so `--select B` was
clean before adding it to `pyproject.toml`; (4) added `"B"` to
`pyproject.toml`'s `select`; (4b) the full `pytest` run this surfaced a
second fallout, caught before commit: `tests/test_v15_standards.py`'s
`test_n6_pre_push_refused_when_pytest_fails` writes a synthetic failing
test file containing `assert False` into a disposable worktree and commits
it, to prove a red `pytest` gate blocks `pre-push` — but that worktree is
built from this repo's own `HEAD` (including the now-`B`-selected
`pyproject.toml`), so its own `pre-commit` hook's `ruff-check` step now
rejects `assert False` (`B011`) before the test's `git commit` call even
reaches the `pytest` gate under test. Fixed by changing the fixture's
synthetic content to `assert 1 == 2` (same deliberate-failure shape, no
`B`-family hit); (5) ran `ruff check . --extend-select
RUF100 --fix`, which removed 11 now-genuinely-unused `# noqa: CODE`
directives (10 x `BLE001`, 1 x `D102`, plus the 2 x `A002` on
`dashboard_server.py`'s `log_message`/`log_error` -- none of `BLE001`,
`D102`, `A002` are in this project's selected rule set, so these noqas
were dead weight the whole time, not something this task's own edits
caused); the fixer strips the entire trailing comment including its
explanatory suffix, so the explanatory text (e.g. "the fallback boundary",
"REQ-V160-SRV-07's broad startup guard") was hand-restored as a plain
comment (without the `noqa:` directive) at all 11 sites, and the 2
`dashboard_server.py` sites also gained the `# skylos: ignore` suppression
from §A (findings #17-20); (6) added `"RUF100"` to `select`; (7) confirmed
`ruff check .` still exits 0 under the final `E,F,I,B,RUF100` set.

**Proposal table -- the non-adopted families from the 5490-hit inventory
scan** (one row per family, count from the brief's own breakdown where
given, verdict for the operator):

| Family | Count | Verdict |
|---|---|---|
| `S101` (assert, in `tests/`) | 3689 | never -- assert is the point of a pytest suite; this rule is designed for production code, not test code |
| `PLR2004` (magic value comparison) | 474 | never -- too noisy at this codebase's numeric-literal density to be bug-shaped |
| `TRY003` (long message outside custom exception) | 277 (225 outside `tests/`) | never -- a style preference that would force a tree-wide custom-exception-class refactor for no measured defect class |
| `ARG*` (unused-argument family) | 362 | never -- duplicates skylos's own unused-parameter analysis, already exercised this task with a finer-grained (per-finding, not per-family) review |
| `B` (flake8-bugbear) | 17 (2 prod `B905` + 15 test `B905`/`B007`) | **adopted this task** |
| `RUF100`/`RUF012` | 11 + 1 | **adopted this task** (the rest of the `RUF` family is unreviewed) |
| `BLE` (blind except) | 10 sites reviewed this task (all pre-existing, all deliberate boundary comments) | adopt-later -- the sites seen this task were all intentional; a dedicated per-site pass over the rest of the family is needed before adopting it tree-wide |
| `DTZ` (naive datetime) | not separately counted | adopt-later -- could catch a real correctness class (naive vs. aware datetime); needs its own count and review, not reviewed this task |
| `PLW` (pylint warnings, `PLW0603` seen) | 3 reviewed this task | never -- matches this codebase's explicit module-level-state pattern (signal flag, start timestamp, dropped-span counter) |
| Everything else (`UP`, `SIM`, `C4`, `PERF`, `PIE`, `RET`, `PTH`, `T20`, `A`, `N`) | ~688 (5490 total minus the rows above) | adopt-later -- not reviewed this task; needs its own per-family count and review before any verdict |

**C.5 skylos gate stays `blocking: false`.** Whole-tree in-scope count
after §A's fixes (including the operator-ruled deletion of
`_MIGRATION_2_TO_3`, §A #8): **0**. Flipping the gate to `blocking: true`
is one YAML line (`blocking: false` -> `true` in
`config/quality_gates.yaml`'s `skylos:` block) now that the tree is
clean; this task does not flip it, leaving that call to the operator.

### Suppression count

**20** inline `# skylos: ignore` comments added this task (§A), each
naming the interface or reference it protects. **0** findings left without
a suppression comment: `_MIGRATION_2_TO_3` (§A #8) could not carry one
(the flagged line opens a triple-quoted SQL string) and was deleted
instead on the operator's explicit ruling. **0** scanner-exclusion-as-fix;
the one target
exclusion (`--exclude .semgrep`, §C.1) is a scan-scope correction (the
tool was scanning its own rule pack, not project code), not a suppression
of a real finding.

### Constraints verified

- Gate 6 `drifted` stays 0 after this commit: throwaway drift script,
  **108/108** find strings match exactly once.
- No version-pin or count-bearing test needed repointing this task.
- `.env`, `data/`, `evals/rag/corpus` were never opened.
- No `--no-verify`; not pushed.

### Delegation record

- T1 -- delegated, brief `docs/spec/task-briefs/v192-T1.md`.
