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

## T2 -- duplicates

Section 4's three cheap scans, none requiring a `mutation_check.py
--only` proof run because none produced a removal candidate:

- **(a) REQ-id frequency.** `grep -oE "REQ-[A-Z0-9-]+" tests/*.py` counted
  each id's mentions; the highest, `REQ-V13-TOO-02` (10 mentions across
  5 files), was spot-checked by hand -- each occurrence covers a distinct
  sub-case (byte counts, envelope schema, guardrails, prefix windows),
  not a duplicate assertion of the same property.
- **(b) manual-parametrize candidates.** A test-name-family heuristic
  (strip a trailing `_<digits>` and group) found zero families of 4+
  near-identical names beyond what already uses
  `@pytest.mark.parametrize` (e.g. `test_t_ex_13_cap_boundary`).
- **(c) the brief's own top-10 `--durations` list.** Cross-checked: each
  of the ~10 real-tool/timeout tests (semgrep, gitleaks, the two
  `test_exec` grace tests, the nested-pytest pre-push test, the doctor
  real-config test, the two `test_v15_scan_03`/bench-snapshot tests)
  covers a distinct mechanism -- none is a faster stand-in for another.

**0 candidates removed with proof, 0 parametrize-merges found** -- the
suite's time is in section 1's ten tests, not in duplicates.

### Constraints verified

- Gate 6 `drifted` stays 0 after both commits: throwaway drift script,
  **109/109** find strings match exactly once (108 before commit 1,
  109 after -- the one new `v192-mutation-order-shrink-unchecked`
  entry).
- `mutation_check.py --list` output and `--only`/`--select` semantics
  unchanged; REQ-V13-CO-06 / REQ-V15-GATE-04 fail-loud behaviour
  unchanged; the self-check deselect (`_SELF_CHECK_NODE_ID`) unchanged.
- Nothing ran concurrently with any `--only`/`--select` run or with the
  false-kill guard.
- No count-bearing / version-pin test needed repointing.
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
