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

**Erratum on row 8 (docs/prompts/166, clean-context review):**

- `6c9a904`'s own commit message still reads the pre-amend text ("1 left
  unsuppressed ... skylos 1 finding"): the coordinator's ruling on
  `_MIGRATION_2_TO_3` landed after prompt 164's first pass wrote that
  message, and this task-brief's own instruction is to close the finding
  by erratum rather than rewrite `6c9a904`/`d25d664` (docs/spec/task-briefs/
  v192-T1-review.md: "the erratum path is cheaper than re-citing"). The
  commit **diff**, not the message, is authoritative: row 8 above and this
  report's totals reflect what `6c9a904` actually contains -- 7 deleted,
  20 suppressed, 0 unsuppressed, skylos 0.
- The deletion supersedes a named non-goal: `docs/spec/spec-v1.7.0.md:2413`,
  **REQ-V170-NG-14** -- "Deleting `storage._MIGRATION_2_TO_3` or any other
  pre-existing dead code found in passing" is out of scope there because
  "pre-existing dead code is reported, never removed as a side effect (lab
  rule 3)". That non-goal does not bind here: this deletion is not a side
  effect stumbled into while working on something else -- it is the
  operator's own whole-tree cleanup order (handoff, verbatim: "исправление
  всех проблем"), applied deliberately through §A.3's (a)(b)(c) procedure,
  the same distinction §A.3's own text already draws between passive
  discovery and an explicit cleanup mandate.

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

**Disposition on the brief's §B.4 doc-update instruction** ("update
`AGENTS.md:30` and `:213-215` ... and any README line that says format is
shadow"): instruction moot -- neither line, nor any README line, ever said
`ruff format` was shadow (both cited spots describe `skylos`, not
`ruff-format`; grepped for "shadow" and for "ruff format"/"ruff-format" in
both files to confirm). Nothing there needed changing. `skylos (shadow)`
wording is kept as-is, per §C.5 above (skylos stays non-blocking).

### C. Beyond skylos

**C.1 semgrep scanning its own rule pack.** `config/quality_gates.yaml`'s
`semgrep` gate argv gained `--exclude, ".semgrep"` (least invasive: one
argv token, no new `.semgrepignore` file, no change to
`tests/test_v15_standards.py`'s own offline-semgrep test, which builds its
own literal argv independently and was already unaffected -- it asserts on
`--severity ERROR` behaviour that the two INFO-level self-scan findings
never touched). Verified: `semgrep scan --config .semgrep/ --exclude
.semgrep ...` now reports 0 findings under `.semgrep/` at any severity,
and 1 total (the already-reviewed `storage.py:487` -- `:439` before
prompt 165's whole-tree reformat moved it).

**C.2 `storage.py:487` insecure-file-permissions (WARNING).** Reviewed,
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
instead on the operator's explicit ruling. A `# skylos: ignore` comment is
line-scoped (skylos 4.35.0's own `config.py`), so on a `def` line it also
hides that function's own name from skylos's unused-*function* check, not
only the parameter finding it was added for -- this affects the eight
functions where the suppression sits on the `def` line itself:
`_handle_signal`, `cmd_doctor`, `cmd_lint_docs`, `log_message`,
`log_error`, `handle_starttag`, `handle_startendtag`, `NullSink.write`; a
future dead-code pass should check these eight by hand rather than trust
skylos to still catch them if they ever become genuinely unreferenced.
**0** scanner-exclusion-as-fix; the one target
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
- Both `6c9a904` and `d25d664` carry `Co-Authored-By: Claude Sonnet 5`;
  accurate to the executor model for this task (verified against the
  session's own model-identity reminder), left as-is.

## T2 -- gate 6

Contract: `docs/spec/task-briefs/v192-T2.md` section 2 (prompt 167,
commit `92b667c`). Baseline: `c21ffb3` (T1 closed), 108 mutation entries,
`default_runner` running `pytest -x -q` over pytest's default
alphabetical-by-file order.

### The change

`ordered_test_files(mutation, root)` builds the complete, ordered list of
every test file (`tests/**/test_*.py`), tiered by relevance to the mutated
module -- never a subset, a permutation of the bare glob by construction
(asserted in the function itself):

1. test files whose name carries the entry's version prefix
   (`test_{prefix}_*.py`; `cov-` overridden to `test_v12_patch.py`, the
   only file naming `cov_0*` test ids);
2. the test file named after the mutated module (`storage.py` ->
   `test_storage.py`);
3. test files that import the mutated module directly;
4. test files importing a first-party top-level module that imports it
   (one hop, mirroring the brief's own scratch simulator);
5. every remaining test file.

`default_runner(mutation)` uses this ordering; `run_one` now calls
`runner(mutation)` instead of `runner()` to carry it through. A
once-per-invocation collect-count guard in `main()` (`_shrink_counts`,
before the `--only`/`--select` dispatch, skipped only under `--list`)
compares `pytest --collect-only -q` node counts between the explicit
ordered file list and the bare `testpaths` invocation, closing the
silent-shrink hole an explicit file list opens (REQ-V13-CO-06 /
REQ-V15-GATE-04): a future `tests/sub/test_x.py`, or a renamed pattern,
would otherwise fall out of every tier while the gate kept reporting
green over a smaller set. The new mutation entry
`v192-mutation-order-shrink-unchecked` mutates that check into a no-op;
its killer test (`tests/test_mutation_check.py
::test_t_v192_mutation_order_shrink_check_blocks_before_running_anything`)
fakes both `_shrink_counts` (a fabricated mismatch) and `run_all` (a
spy), and asserts `main()` returns 1 without ever calling `run_all` --
never shells out to real pytest, so applying the mutation for real never
risks the recursive full-suite run a naive killer test would trigger.

### False-kill guard

Per section 2.1: ran the **unmutated** tree once under each distinct
ordering the runner produces. The brief estimated "about a dozen"
(one per distinct mutated path); this tree has **18** distinct mutated
paths across the (then-)109 entries. All 18 exit 0:

| mutated path | representative entry | exit | wall |
|---|---|---|---|
| agent.py | cov-07-finish-redacts | 0 | 80.3s |
| bot.py | cov-01-live-docker-sandbox-max-bytes | 0 | 79.5s |
| config.py | sec-ssr-01-shape-check | 0 | 80.7s |
| dashboard_render.py | v180-transcript-budget-removed | 0 | 79.3s |
| dashboard_server.py | v160-bind-address-widened | 0 | 81.7s |
| devtools/bench.py | v13-bench-gate-threshold | 0 | 82.0s |
| devtools/bench_scenarios.py | v13-bench-turn-zero-based | 0 | 81.5s |
| devtools/checks.py | v15-severity-comparison-inverted | 0 | 81.4s |
| devtools/mutation_check.py | v13-only-typo-exit0 | 0 | 82.0s |
| llm/__init__.py | v13-routing-agent-too | 0 | 81.3s |
| llm/base.py | v13-usage-parse-none | 0 | 82.2s |
| llm/failover.py | v170-failover-drops-reasoning | 0 | 80.8s |
| llm/pricing.py | v13-cost-drops-output | 0 | 80.0s |
| metrics.py | v13-resent-formula | 0 | 80.2s |
| rag.py | v190-sources-fallback-dropped | 0 | 81.9s |
| storage.py | v11-storage-add-tool-turn-redacts | 0 | 81.1s |
| tools.py | cov-02-pre-run-refusal-incomplete | 0 | 82.2s |
| tracing.py | v160-content-redact-bypassed | 0 | 82.0s |

All 18 exit 0 -> every kill this reordering produces is attributable to
the real mutation, not to an ordering artefact under `-x`.

### Measured, before (`c21ffb3`, old alphabetical order) vs. after (this commit)

Each `--select` subset run alone, sequential, nothing else running:

| subset | entries | before | after | ratio |
|---|---|---|---|---|
| v15- | 4 | 98.33s | 14.04s | 7.0x |
| v160- | 11 | 590.26s | 101.19s | 5.8x |
| v170- | 9 | 565.75s | 25.46s | 22.2x |
| v180- | 6 | 476.95s | 117.09s | 4.1x |
| v190- | 7 | 495.91s | 23.41s | 21.2x |
| **total** | **37** | **2227.2s** | **281.19s** | **7.9x** |

All five subsets killed the same n/n before and after (4/4, 11/11, 9/9,
6/6, 7/7) -- the ordering changed only which test ran first, never the
killed set. `config/quality_gates.yaml`'s five `mutation-v*`
`timeout_seconds` re-measured by the file's own 2x rule from the after
numbers: v15 220s->30s, v160 1190s->210s, v170 1070s->60s, v180
810s->240s, v190 1020s->50s. `mutation-all` is untouched -- T3's own
re-measurement, per the brief's explicit boundary.

Operator-facing estimate for a future full `mutation-all` run under this
reordering (not run here): the measured subsets averaged 7.60s/entry
(281.19s / 37 entries); scaled to the pre-T2 108-entry gate, ~=820s
(~13.7min), versus the last directly measured `mutation-all` wall (T9,
105 entries, 3953.309s ~= 66min) scaled the same way to 108 entries
(~=4066s ~= 67.8min) -- a rough ~5x projected speedup. Caveat: 71 of the
108 entries (mostly the 34 `v13-` entries) were not measured directly
and may not track the sampled average; the tightest of the five
re-measured timeouts (`mutation-v170` at 60s, `mutation-v190` at 50s)
sit at absolute values where this run's own single measurement leaves
less headroom against machine-load variance than the file's earlier,
much larger timeouts did -- worth a second measurement at T3's
authoritative run rather than trusted blind.

### Deviation: commit trailer model

`docs/spec/task-briefs/v192-T2.md` section 6 names
`Co-Authored-By: Claude Opus 5` for both commits. The actual executor
for this task is `claude-sonnet-5` (per this session's own
model-identity reminder). Both commits carry
`Co-Authored-By: Claude Sonnet 5` -- accurate to the real executor,
per the same precedent T1's report already recorded for its own
commits, rather than the brief's literal (and in this case incorrect)
text.

### Review findings closed (prompt 170)

Clean-context review (`docs/spec/task-briefs/v192-T2-review.md`) of
`92b667c` + `c3a38ea` + `260c7e1`: no 🔴, two 🟠 (both closed below, both
in the new runner), six 🟡.

**🟠 Finding 1 -- shrink guard fails open.** `_collect_count` summed
`path: N` lines that pytest prints only at verbosity -2; the original
code reached that verbosity only because `pyproject.toml`'s `addopts`
(`-q`) plus the invocation's own explicit `-q` happened to add up to
`-qq` -- an implicit dependency a future `addopts` change could break
silently, and the code never read `completed.returncode`, so a real
collection error (or a stray verbosity change) would sum to 0 on both
sides and the guard would pass vacuously (0 == 0, "no shrink"). Fixed:
`-qq` is now passed explicitly on both collect-only invocations (never
relying on `addopts`); `_collect_count` returns `(count, returncode)`;
`main()`'s guard now requires both returncodes `== 0` and both counts
`> 0` before even comparing them, failing loudly naming which condition
tripped. New mutation entry `v192-mutation-order-shrink-zero-accepted`
(drops the `> 0` condition) with its own killer test (fakes `(0, 0, 0,
0)`, mocks `run_all`, asserts `main()` returns 1 without calling it);
a second new unit test covers the non-zero-returncode case directly
(fakes `(1598, 1598, 2, 0)`, asserts rejection and that the stderr names
`rc=2`). `--only v192-mutation-order-shrink-zero-accepted` killed;
`--only v192-mutation-order-shrink-unchecked` still killed (its own find
string, `if explicit_count != bare_count:`, is untouched by this fix --
the 4-tuple return shape changed, but that specific comparison line did
not move).

**🟠 Finding 2 -- three mutation timeouts could not report a survivor.**
`mutation-v15` (30s), `mutation-v170` (60s) and `mutation-v190` (50s)
were sized purely by D2's "2x a measured *killed*-path run" rule --
correct for a kill (a `-x` run stops at the first failing test) but
wrong for a *survivor*: nothing fails, so the mutated tree runs the
*whole* suite, single-process (`default_runner`'s own `-n 0`), which
costs one full single-process suite run (measured directly, `time uv
run --locked pytest -q -n 0`, this tree: 66.22s and 65.33s, two runs --
close to the review's own ~69s estimate; the brief's literal "70 s,
measured" figure is used in the rule and the comment, as instructed).
All three of those timeouts sat below that ~70s floor: a surviving
mutation would hit the gate timeout before the run could even print
"survived", `checks.py` would SIGKILL `mutation_check.py` (which traps
only `SIGINT`/`SIGTERM`), and the mutated file would stay on disk with
no survivor id ever printed -- silently worse than a red gate. Fixed:
`config/quality_gates.yaml` now states the corrected rule once, above
`mutation-v15` (D2's own comment block, extended, not replaced):
`timeout = 2 x measured killed-path wall + one full single-process suite
run (70s, measured), rounded up to 10s`. Re-sized under it: `mutation-v15`
30s -> **100s**, `mutation-v160` 210s -> **280s**, `mutation-v170` 60s ->
**130s**, `mutation-v180` 240s -> **310s**, `mutation-v190` 50s ->
**120s** (superseding the "Measured, before vs. after" table's numbers
above, which reflected D2 alone). `mutation-all` is not re-measured
under the corrected rule in T2 -- a note on that gate says so and points
to T3. The SIGKILL-traps-only-SIGINT/SIGTERM hazard itself is
pre-existing `checks.py` behaviour, out of this fix's scope by the
review's own instruction -- noted here as a **v1.10.0 item**: a mutation
gate timeout should ideally distinguish "survivor, ran out of time" from
"hung", but `checks.py`'s SIGKILL path does not currently tell the two
apart, and a survivor that happens to run past the timeout is reported
identically to a hang.

**🟡 Finding 6 -- ordering missed common import shapes.** `_imports`
only matched `import <module>` / `from <module> import ...` with the
dotted name spelled out verbatim, anchored to true line-start -- it
missed `from devtools import bench` / `from llm import pricing` (the
`from <pkg> import <submodule>` shape, which never spells the dotted
name out) and indented imports (inside a function or a
`TYPE_CHECKING` block); `_module_name` mapped `llm/__init__.py` to
`llm.__init__` (code never imports that -- it imports `llm`, the
package); tier 4's one-hop scan covered only top-level `*.py`, missing
`llm/*.py` and `devtools/*.py` intermediaries. This mattered most for
the 34 `v13-` entries, most of which mutate `devtools/bench.py` --
every one of them fell through tier 3 empty before this fix. Fixed:
`_imports` now also matches `from <pkg> import <sub>` (word-bounded, so
`bench` doesn't false-match inside `bench_scenarios`) and allows leading
whitespace; `_module_name` strips a trailing `.__init__`; tier 4 now
scans `llm/*.py` and `devtools/*.py` too. Tiers re-printed for the two
named entries (`ordered_test_files`, first 6 files):

| entry | module | first 6 files |
|---|---|---|
| `v13-bench-gate-threshold` | `devtools.bench` | `test_v13_carryover.py`, `test_bench.py`, `test_dashboard.py`, `test_v14_patch.py`, `test_v160_bench.py`, `test_v170_bench.py` |
| `v13-routing-agent-too` | `llm` (was `llm.__init__`) | `test_v13_carryover.py`, `test_agent.py`, `test_bench.py`, `test_failover.py`, `test_history_stub.py`, `test_llm.py` |

`test_dashboard.py`, `test_v14_patch.py`, `test_v160_bench.py`,
`test_v170_bench.py` (all `from devtools import bench...`) and
`test_agent.py`/`test_bench.py`/`test_failover.py`/`test_history_stub.py`
/`test_llm.py` (all `from llm import ...`) are now found by tier 3 --
before this fix, none of them were, for either entry. Re-measured
`--select v13-` once, alone, nothing concurrent, this tree: **34/34
killed, real=3m30.542s (210.542s)** -- replacing the report's earlier
rough "~=820s" projection for a full-108-entry run with an actual
number for this, the largest single prefix: 210.542s / 34 entries =
6.19s/entry, *faster* than the five-subset sample's blended 7.60s/entry
average, consistent with tier 3 now catching these entries directly
instead of falling through to tier 5.

**🟡 Finding 7 -- shrink guard ran before id/prefix validation.**
`_shrink_counts()` ran immediately after the `--list` check, before the
unknown-`--only`-id and empty-`--select`-prefix checks -- so `--only
typo` paid the collect-only overhead (two `pytest --collect-only`
subprocess calls) before failing, instead of failing instantly as it did
before this feature existed. Moved the shrink guard to run after both
validation checks; behaviour for a valid id/prefix is unchanged.

## T2 -- gate 3

Contract: `docs/spec/task-briefs/v192-T2.md` sections 3-4 (prompt 168,
commit `c3a38ea`).

### xdist adoption

`pytest-xdist` 3.8.0 (latest stable on PyPI, verified via `pip index
versions pytest-xdist` at implementation time) added as a dev
dependency; `pyproject.toml`'s `addopts` changed from `"-q"` to
`"-q -n auto"` -- the brief's own measured plateau at 8 workers holds on
this 16-core box. `devtools/mutation_check.py:default_runner` gained an
explicit `-n 0` to stay single-process (xdist worker start-up cost would
dominate the smallest kills the reordering above produces, some under
3s); this flag could only be added in *this* commit, once xdist was an
installed dependency -- added a commit earlier it makes pytest exit 4,
"unrecognized arguments: -n" (verified empirically before the fix).

Isolation proof (v1.5.1 D1 precedent -- fixtures leaking into the real
repo): five consecutive `pytest -q` (`-n auto`) runs, all exit 0:
23.42s, 24.80s, 24.57s, 25.23s, 24.83s; `git status --short` compared
byte-for-byte across all five (`diff` of run 1 vs. run 5: identical) --
only this run's own in-progress edits, no test-leaked files. Plus one
`--dist loadfile` run: 38.82s, exit 0, same clean status.

`config/quality_gates.yaml`'s `pytest` gate `timeout_seconds`
re-measured by the file's 2x rule from the worst of the five isolation
runs: 25.23s -> 2x ~=50.46s -> 60s (down from 120s, which had been set
for the old ~70-80s serial run and was already under the file's own 2x
rule even before this task).

### Fixture cost (section 3.1)

`live_server`'s `serve_forever` (three call sites: `test_v160_dashboard
.py:705,859`, `test_v180_conversations.py:479`) now passes
`poll_interval=0.01` instead of the default 0.5s -- fixture-only, no
property under test changes.

### Grace-period costs (section 3.2)

`test_t_ex_04_term_ignoring_child_is_killed` monkeypatches
`tools.EXEC_KILL_GRACE_S` from the production 5.0s down to 0.5s and
scales its `elapsed <` bound from 12.0 to 4.0 (measured 6.00s -> 1.51s,
real headroom against the bound, not tuned to the observation).
`test_t_ex_05_grandchild_holding_pipes_does_not_hang` is the one kept at
the real production `EXEC_DRAIN_GRACE_S` (2.0s, measured 4.04s,
unchanged) -- both tests' own comments say which is which and why, per
the brief's "say which one in the report" instruction: `test_t_ex_04`'s
constant is patched because it is the larger single test (bigger
absolute saving), leaving `test_t_ex_05` to keep the real production
value exercised somewhere in the suite.

### Review finding closed (prompt 170)

**🟡 Finding 5 -- the pytest gate's `60s` timeout comment didn't say
whose box.** The 2x figure it is derived from (a `-n auto` run) is
specific to this operator's 16-core machine; a smaller runner reading
only "60s" has no way to know that number does not transfer. Reworded
the comment to name the box explicitly and give this task's own
worker-count reference points from the same tree (section 3.3's own
sweep): serial (`-n 0`) ~70-80s, 4 workers 26.9s, 8 workers ~22-23s
(plateau) -- so a 4-core operator knows to re-measure near the
4-worker figure, not assume 60s.

## T2 -- duplicates

Section 4's three cheap scans, none requiring a `mutation_check.py
--only` proof run because none produced a removal candidate:

- **(a) REQ-id frequency.**
  `grep -oREh "REQ-[A-Z0-9-]+" tests/*.py | sort | uniq -c | sort -rn`
  counted each id's mentions; the highest, `REQ-V13-TOO-02` (10 mentions
  across 5 files, `grep -n "REQ-V13-TOO-02" tests/*.py` to list them), was
  spot-checked by hand -- each occurrence covers a distinct sub-case (byte
  counts, envelope schema, guardrails, prefix windows), not a duplicate
  assertion of the same property.
- **(b) manual-parametrize candidates.** T2 review finding 8: command
  added --
  `grep -hoE "^def test_[a-z0-9_]+" tests/*.py | sed -E 's/_[0-9]+$//' | sort | uniq -c | sort -rn | awk '$1>=4'`
  (strip a trailing `_<digits>` off every test function name, group, keep
  families of 4+) found zero output -- zero families of 4+ near-identical
  names beyond what already uses `@pytest.mark.parametrize` (e.g.
  `test_t_ex_13_cap_boundary`).
- **(c) the brief's own top-10 `--durations` list.** T2 review finding 8:
  the list itself is reproduced by `uv run --locked pytest -q
  --durations=50` (brief section 1's own command); this scan is a manual
  cross-check against that output, not a script -- each of the ~10
  real-tool/timeout tests it names (semgrep, gitleaks, the two
  `test_exec` grace tests, the nested-pytest pre-push test, the doctor
  real-config test, the two `test_v15_scan_03`/bench-snapshot tests) was
  read and covers a distinct mechanism -- none is a faster stand-in for
  another.

**0 candidates removed with proof, 0 parametrize-merges found** -- the
suite's time is in section 1's ten tests, not in duplicates.

### Constraints verified

- Gate 6 `drifted` stays 0 after every commit: throwaway drift script,
  **110/110** find strings match exactly once (108 before commit 1, 109
  after it -- the new `v192-mutation-order-shrink-unchecked` entry, 110
  after prompt 170's own review-findings commit -- the new
  `v192-mutation-order-shrink-zero-accepted` entry).
- `mutation_check.py --list` output and `--only`/`--select` semantics
  unchanged; REQ-V13-CO-06 / REQ-V15-GATE-04 fail-loud behaviour
  unchanged; the self-check deselect (`_SELF_CHECK_NODE_ID`) unchanged.
- Nothing ran concurrently with any `--only`/`--select` run or with the
  false-kill guard.
- T2 review (finding 3): stale count-bearing lines at `AGENTS.md:160`
  (1593 tests), `AGENTS.md:169` (108 entries) and
  `tests/test_v190_agents.py:139-140` (pinning both figures) now trail
  the tree (1600 tests, 110 entries after this commit) -- deferred to
  T3's version-bump commit, which owns them, rather than repointed here
  (T2's own scope is performance, not the version-bump paperwork).
- `.env`, `data/`, `evals/rag/corpus` were never opened; no `--no-verify`,
  not pushed.
- Pre-push profile membership (five subsets vs. `mutation-all`) is
  unchanged, per the brief's explicit reservation of that decision for
  the operator at T3.

### Delegation record

- T2 -- delegated, brief `docs/spec/task-briefs/v192-T2.md`.
- Both `92b667c` and `c3a38ea` carry `Co-Authored-By: Claude Sonnet 5`;
  accurate to the executor model for this task (see the "Deviation:
  commit trailer model" note under "T2 -- gate 6" -- the brief's own
  text named a different model).
- T2 review -- delegated, brief
  `docs/spec/task-briefs/v192-T2-review.md` (prompt 170, one commit
  closing all eight findings: two 🟠 in "Review findings closed
  (prompt 170)" under "T2 -- gate 6", one 🟡 under "T2 -- gate 3", the
  remaining 🟡s under "T2 -- gate 6" and the Constraints-verified /
  duplicates sections above).

## T3 -- version bump, paperwork, authoritative gates, tag

Contract: `docs/spec/task-briefs/v192-T3.md` (prompt 171). No logic
changes: version literal, count-bearing documentation, and release
paperwork only, on top of `b9e5174` (T1 + T2 + T2 review, seven commits
ahead of `origin/main`).

### Version

`pyproject.toml`'s `project.version` 1.9.1 -> 1.9.2, `uv.lock` regenerated
(`uv lock`, 25 packages resolved). `tests/test_v192_version.py`
(`T-V192-VER-01`) proves it: run against the pre-bump tree, red --
`AssertionError: assert '1.9.1' == '1.9.2'`; run again after the bump,
green. `tests/test_v191_version.py` repointed to the frozen `v1.9.1`
git-tag blob (`git show v1.9.1:pyproject.toml`, `subprocess.run` +
`tomllib.loads`), the identical convention `tests/test_v180_version.py`
and `tests/test_v190_version.py` already carry -- never deleted, per
REQ-V190-EC-03. All four version tests (`v180`, `v190`, `v191`, `v192`)
green together after the repoint.

### Count-bearing lines (measured after every other T3 edit)

- `pytest --collect-only -q`, final tree: **1601** tests (1600 in v1.9.2
  T2's own close + this task's own new `tests/test_v192_version.py`).
  `AGENTS.md`'s gate-3 line moved 1593 -> 1601, named as of "spec-v1.9.2
  T3" instead of "spec-v1.9.1 T2".
- Mutation entries: **110** (unchanged since v1.9.2 T2's review-findings
  commit `b9e5174` -- T3 added no mutation entries). `AGENTS.md`'s gate-6
  paragraph moved 108 -> 110, its narrative extended to name v1.9.2 T2's
  two new entries (`v192-mutation-order-shrink-unchecked`,
  `v192-mutation-order-shrink-zero-accepted`) alongside the reorder,
  and to cite this report file.
- `tests/test_v190_agents.py`'s own count-bearing test renamed
  `test_t_v191_rpt_05_agents_md_count_lines_landed_at_t2` ->
  `test_t_v192_rpt_05_agents_md_count_lines_landed_at_t3`, asserting
  `"1601"` / `"110 entries"` (T2 review's own finding 3 deferred exactly
  this repoint to T3, rather than naming it in the T3 brief).
- README's release-history table: added a `v1.9.2` row (skylos 27 -> 0,
  75 files reformatted; mutation runner reorder + `pytest-xdist`); the
  `v1.9.1` row's own "; this release" clause removed, since v1.9.2 is now
  the current release.
- `config/quality_gates.yaml`'s `lint-docs.report_path` repointed
  `report-v1.9.1.md` -> `report-v1.9.2.md` (REQ-V190-RPT-01, repointed
  every release since T10); its two pinning tests
  (`tests/test_v190_agents.py::test_t_v192_ec_01_quality_gates_yaml_repoints_report_path`,
  `tests/test_v170_bench.py::test_t_v192_rpt_01_lint_docs_repointed_to_this_release`)
  renamed and repointed the same way, following the `test_t_v192_*`
  convention this task applies everywhere else. Found via the same
  pre-flight-grep discipline v1.9.1 T2 and T2's own review used (`grep
  -rn 'report-v1\.9\.1' tests/ config/`), not named in the T3 brief's own
  "What to do" list.

### Seven-gate table (this run, final tree, in order; nothing else on the
box during gate 6; gate 6 and gate 7 run sequentially, never concurrent)

| # | gate | command | exit | wall |
|---|---|---|---|---|
| 1 | uv sync | `uv sync --locked` | 0 | 0.021s |
| 2 | ruff check | `uv run --locked ruff check .` | 0 | 0.035s |
| 3 | pytest | `uv run --locked pytest` | 0 | 22.912s (1600 passed, 1 skipped -- 1601 collected) |
| 4 | selftest | `uv run --locked python bot.py --selftest` | 0 | 0.542s |
| 5 | selftest-live | `uv run --locked python bot.py --selftest-live` | 0 | 1.732s (config/db/docker(29.8.0)/telegram/lmstudio/embeddings/openrouter all OK) |
| 6 | mutation (all) | `uv run --locked python devtools/mutation_check.py` | 0 | **680.49s (11m20.49s)** -- 110 mutations, 110 killed, 0 survived, 0 errored, 0 drifted |
| 7 | rag-eval | `uv run --locked python devtools/rag_eval.py` | 0 | 186.998s (3m6.998s) -- hybrid recall@5=1.000, hybrid+rerank recall@5=1.000, both `hit@<=5` on every answerable item; PASS |

**Gate-6 before/after:** v1.9.1's own authoritative gate-6 run (pre-T2,
`docs/spec/task-briefs/v192-handoff.md:13`) was **61m39s (3699s) at 108
entries**. This run: **680.49s (11m20.49s) at 110 entries** -- **~5.44x**
faster, on the tree T2's reordering (and the two new entries) already
landed on. This full-run ratio is lower than T2's own ~7.9x sampled ratio
(five `--select` subsets, 37/108 entries, `docs/reports/report-v1.9.2.md`
§"T2 -- gate 6") because the full run also carries every `v13-`/`v11-`/etc.
entry the sample never re-measured directly -- see disclosure (c) below.

### The two clean-context reviews (summarised; full detail already lives
in the T1/T2 sections above -- cross-referenced here, not duplicated)

- **T1 review** (`c21ffb3`, contract `v192-T1-review.md`, prompt 166):
  **1 🔴 / 4 🟠 / 4 🟡 (9 findings)** -- 🔴 a stale ledger row / commit body
  predating an amend; 🟠 x4 -- the same erratum's REQ-V170-NG-14 citation,
  `spec-v1.9.0-delta-1.md` line-ref drift, and the `ruff-format-all`
  pre-commit gap; plus 4 🟡 findings (full breakdown: "### Erratum on row
  8" and the "### Delegation record" under "## T1 -- whole-tree static
  analysis and fixes" above). All closed in one commit, neither reviewed
  commit rewritten.
- **T2 review** (`b9e5174`, contract `v192-T2-review.md`, prompt 170):
  **0 🔴 / 3 🟠 / 5 🟡 (8 findings)** -- 🟠 the shrink guard failing open on
  a zero/error count; 🟠 three mutation-gate timeouts unable to report a
  survivor before SIGKILL; 🟠 a report claim about count-bearing
  repointing that was already stale; plus 5 🟡 findings (full breakdown:
  "### Review findings closed (prompt 170)" under "## T2 -- gate 6"
  above). All closed in one commit,
  none of the three reviewed commits rewritten.

### Disclosures

- **(a) Commit-trailer model.** Every sonnet commit this release
  (`6c9a904`, `d25d664`, `92b667c`, `c3a38ea`, `260c7e1`, and this task's
  own commit) carries `Co-Authored-By: Claude Sonnet 5` -- accurate to
  the actual executor model, non-conforming to whatever model string a
  given task brief's own text named (T1's brief named none explicitly;
  T2's brief section 6 named `Claude Opus 5`, recorded as a deviation in
  its own report section). Both review commits (`c21ffb3`, `b9e5174`)
  carry the same trailer, also accurate -- the reviewer model is
  `claude-opus-5`, but the commit's own author/executor closing the
  findings was `claude-sonnet-5` in both cases.
- **(b) Gate-6 SIGKILL hazard on timeout.** Pre-existing:
  `devtools/mutation_check.py` traps only `SIGINT`/`SIGTERM`, not
  `SIGKILL` -- a gate-6 timeout leaves the mutated file on disk with no
  survivor id ever printed (first disclosed in T2's own review, finding
  2). Not fixed this task (no logic changes permitted in a version-bump
  commit) -- listed as a **v1.10.0 item**.
- **(c) Tightest mutation-\* timeouts, confirmed against the total.**
  This run's gate 6 is the unselected `mutation-all` invocation, which
  prints no per-subset wall (only a final per-mutation `id / outcome /
  exit` table and the 110/110/0/0/0 summary line) -- there is no
  per-subset wall from *this* run to re-check T2's review-time claim
  against, so confirming against the total instead: 110 killed in
  680.49s, **6.19s/entry average**, 0 survived/errored/drifted. That
  average is consistent with T2 review's own individually re-measured
  `--select` walls for the two named subsets (`mutation-v170` 25.46s/9
  entries, `mutation-v190` 23.41s/7 entries) that back their corrected
  timeouts (130s, 120s respectively, per the survivor-safe rule) --
  neither timeout was exercised by this run -- **erratum**: gate 6 was
  invoked exactly as `AGENTS.md` lists it, `uv run --locked python
  devtools/mutation_check.py` directly, not through `checks.py run
  --profile ...`; no `quality_gates.yaml` timeout applied to this
  invocation at all, `mutation-all`'s 1440s included (that value only
  binds a run made through the `checks.py` gate executor). The five
  named subset timeouts bind only their own `--select` invocations under
  the `pre-push`/`full` profiles, never this direct one either.
  `mutation-v15`'s own corrected timeout (100s) sits at an even smaller
  margin above the 70s survivor floor (30s) than either named subset
  (60s/50s) by this same arithmetic; not re-litigated here since v1.9.2
  T2's review already closed that finding and T3 changes no per-subset
  timeout. One more note while on this topic: this file's own history
  documents the box as shared and contended (`mutation-all`'s comment
  block: 5040s/4690s/5620s/7910s across four earlier releases, moving
  both up and down run to run with no code change) -- `mutation-all`'s
  new 1440s carries much less slack against that variance than 7910s
  ever did, so a loaded run overrunning it lands on disclosure (b)'s
  SIGKILL-leaves-a-mutated-file path where 7910s practically never
  could. Stated, not fixed -- the operator's call together with (d).
- **(d) Pre-push profile: five subsets vs. `mutation-all`.** The
  `pre-push` profile still runs only the five named `mutation-v*`
  subsets (`mutation-v15`, `-v160`, `-v170`, `-v180`, `-v190` -- 37 of
  110 entries; every `v11-`/`v12-`/`v13-`/`v170-other`/`v191-`/`v192-`
  entry outside those five prefixes is *not* covered at push time, only
  under `full`/`mutation-all`). This run's own `mutation-all` wall:
  **680.49s** for all 110 entries. The five subsets' own summed wall
  (T2's measurement, `docs/reports/report-v1.9.2.md` §"T2 -- gate 6"):
  **281.19s** for 37 entries. The operator's two options, numbers written,
  decision left to them: (1) keep `pre-push` as five partial subsets
  (~281s, 34% entry coverage, fastest); (2) switch `pre-push` to
  `mutation-all` itself (680.49s, 100% entry coverage, ~2.4x slower than
  option 1 but still ~5.4x faster than v1.9.1's own 3699s baseline).
- **(e) The seven-gate table is not quite "the final tree."** Five
  things landed in this same commit *after* gate 7 finished, using gate
  6's and gate 7's own results as their input: `config/quality_gates.yaml`'s
  `mutation-all.timeout_seconds` (7910->1440, computed from gate 6's own
  wall); this report's whole "T3" section (including this table and
  every disclosure in it); `docs/reports/tg-post-v1.9.2.md`;
  `docs/llm-usage.md` row 81; and the ledger row below. None of the
  seven gates can be re-run against a tree that includes its own report
  of itself -- the same structural point v1.9.1's report made ("a
  mutation gate is only as valid as the suite it ran against") and the
  v1.8.0 `/verify-run` finding this task's own brief cites. What *was*
  re-run, after the `quality_gates.yaml` edit, on the tree as actually
  committed: `ruff check .` (0), `ruff format --check .` (0), `pytest`
  (0, 1601 collected, same as the table above -- no test reads
  `mutation-all.timeout_seconds`), `checks.py lint-docs` (0). Gates 4/5/6/7
  were not re-run (gate 6 in particular is the one gate the changed value
  could even apply to, and re-running the authoritative 11m20s mutation
  pass a second time to validate a comment-and-timeout edit was judged
  not worth it -- flagged here instead of silently asserted).

### Open tail carried from v1.9.1

v1.9.1's report disclosed one rerank call succeeding only on attempt 3.
This run's gate-7 log shows the same thing again: `rerank attempt 1
failed, retrying: llm request timed out` / `rerank attempt 2 failed,
retrying: llm request timed out` / `provider lmstudio failed 3 times
(LLMError); serving from openrouter` / `rerank succeeded on attempt 3
after 15.72s`. The retry loop (v1.9.1 T3) did exactly what it was built
for -- gate 7 still exits 0 -- but the underlying LM Studio-then-fallback
latency pattern recurs run to run; not a regression, still an open tail,
carried forward rather than investigated further (out of scope for a
version-bump task). The advisory conversation-aware smoke, which failed
in v1.9.1 T2's own run, **passed** in this run ("turn 2 query
'количество недель отпуска в год' shares a token with turn 1's
question") -- consistent with it being the main chat model's
non-deterministic tool-call choice, not a regression either way.

### Delegation record

- T3 -- delegated, brief `docs/spec/task-briefs/v192-T3.md`, prompt 171,
  commit `c431987`.
- T3 erratum (this section's own finding-count fix, disclosure (e), and
  the disclosure-(c) correction) -- prompt 172, *artefacts only* (report,
  ledger row, prompt log, tg-post -- no code or test file touched, no
  gate re-run required by the exemption itself; gate 3 was re-run anyway,
  see disclosure (e)), one of the four closed-list exemptions from
  `standards/workflow.md` §5.1, this commit.
- T1 -- delegated, brief `docs/spec/task-briefs/v192-T1.md`; T1 review --
  clean-context review, delegated by brief `v192-T1-review.md`.
- T2 -- delegated, brief `docs/spec/task-briefs/v192-T2.md`; T2 review --
  clean-context review, delegated by brief `v192-T2-review.md`.
- Every executor model named: T1/T2 implementer `claude-sonnet-5`; both
  reviewers `claude-opus-5`; T3 and its erratum (this task) implementer
  `claude-sonnet-5`.

### Constraints verified

- `.env` never read, printed or committed (`.env` grepped only for a
  precondition line count, never opened); `data/`, `evals/rag/corpus`
  never opened.
- No `--no-verify`; not pushed (operator pushes).
- Nothing else ran on the box during gate 6; gate 6 and gate 7 ran
  sequentially, never concurrently.

**Erratum on the Bugs column below (found while assembling this section,
prompt 172):** the T3 task brief's own text (`v192-T3.md`, "What to
do" §3) reads "T1 1 🔴 / 4 🟠 / 5 🟡, T2 0 🔴 / 3 🟠 / 6 🟡", summing to 10
and 9 findings respectively. Counting the two review briefs directly
(`docs/spec/task-briefs/v192-T1-review.md` items 1-9,
`v192-T2-review.md` items 1-8) gives **9** (1/4/4) and **8** (0/3/5) --
matching `c21ffb3`'s own commit message ("closes all nine findings")
and this report's T2 delegation record ("closing all eight findings"),
both written before this task existed. The row below uses the counted
figures, not the brief's; the brief's arithmetic is one 🟡 over on each
side, source not identified.

## Ledger row (paste into `economics.md`)

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | v1.9.2 | 2026-09-13 | — (patch, no new spec; task briefs `docs/spec/task-briefs/v192-handoff.md`, `-T1.md`, `-T1-review.md`, `-T2.md`, `-T2-review.md`, `-T3.md`) | 9 (164–172) | yes — all seven gates green on the first authoritative run of the final tree (see disclosure (e): a handful of paperwork-only edits landed in the same commit after gate 7, none of them gate-reachable except gate 3, which was re-run green) | T1 1 🔴 / 4 🟠 / 4 🟡 (9), T2 0 🔴 / 3 🟠 / 5 🟡 (8) — all fixed | unknown (harness does not expose per-request usage) | $0 marginal (Claude Code subscription-metered session; live inference only on gates 5/7, at reference prices, no real spend tracked) | claude-sonnet-5 (both reviews: claude-opus-5) | Claude Code |
```

## Verdict

**All seven gates green on the final tree; annotated tag `v1.9.2`
created.** T1 closed 27 skylos findings and reformatted 75 files
whole-tree (REQ-V15-NG-04); T2 cut gate 6's wall ~5.4x (61m39s -> 680.49s
at 108->110 entries) and gate 3's wall ~3x (70s -> ~23-25s) via a
relevance-ordered mutation runner and `pytest-xdist`; both phases'
clean-context reviews closed everything they found, neither reviewed
commit rewritten. T3 (this task) closed the patch: version 1.9.1 ->
1.9.2, all count-bearing lines moved to the tree's real final numbers,
and this report's own paperwork. The rerank retry tail from v1.9.1
recurs (gate 7 still green); the gate-6 SIGKILL-on-timeout hazard and the
pre-push five-subsets-vs-`mutation-all` tradeoff are both left as
disclosed, undecided items for the operator.
