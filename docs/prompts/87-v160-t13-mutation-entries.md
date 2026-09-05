# Prompt 87 — spec-v1.6.0 T13: mutation entries and the mutation-v160 gate

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §14.1 marks T13 "delegate: yes" -- constructing
  ten mutation entries that each prove a security/correctness-critical
  mechanism requires reading and cross-referencing several large production
  modules (`agent.py` ~1100 lines, `dashboard_server.py`, `storage.py`,
  `tracing.py`, `config.py`, `bot.py`) plus empirical hand-mutation
  verification of each candidate `find`/`replace` pair against the real test
  suite, past this run's RLM delegation threshold
- **Harness:** Claude Code
- **Stage:** T13
- **Owner of:** `devtools/mutation_check.py`, `config/quality_gates.yaml`,
  `tests/test_v15_standards.py` (two lines), `AGENTS.md` (one sentence),
  `tests/test_mutation_check.py`, this prompt file
- **REQ ids:** REQ-V160-TST-03, -04, REQ-V160-GATE-02, -03

## Goal

Add the ten `v160-*` mutation entries prescribed by spec-v1.6.0 §15.4 to
`devtools/mutation_check.py`'s `MUTATIONS` list, each proving a distinct
security/correctness-critical mechanism from the v1.6.0 feature set
(dashboard bind address, content-capture default, redaction choke-points,
tool-repeat-refusal threshold, truncated-summary rejection, `--selftest`
never starting the server, `--version` reading `pyproject.toml` fresh, the
dashboard's read-only connection, error bodies never echoing request input,
and Host-header validation); wire a new `mutation-v160` gate into
`config/quality_gates.yaml`'s `pre-push` profile mirroring `mutation-v15`'s
shape, with both `mutation-v160` and the now-82-entry `mutation-all` gates'
`timeout_seconds` re-measured (not carried over); repoint
`tests/test_v15_standards.py`'s gate-matrix test at
`docs/spec/spec-v1.6.0.md` and add the new gate's row to its label map; and
close T12's deferred `AGENTS.md` sentence (72 -> 82 entries).

## Constraints

- Own exactly `devtools/mutation_check.py` (append-only to `MUTATIONS`, plus
  `main()`'s `--select`/`--list` handling if needed -- it was not: the
  existing `startswith(prefix)` logic already covers `v160-`),
  `config/quality_gates.yaml` (the new `mutation-v160` gate block, its
  `pre-push` membership, and the two re-measured `timeout_seconds` values
  only -- no other gate's `argv`/`result_mode`/`blocking`/`severity`/profile
  membership touched), `tests/test_v15_standards.py` (the two named lines:
  the `_GATE_MATRIX_LABEL_TO_NAME` entry and the spec-file path in
  `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`), `AGENTS.md`
  (the one "72 entries as of spec-v1.5" -> "82 entries as of spec-v1.6.0"
  sentence), the chosen mutation-coverage test file, and this prompt file.
- Do not touch any production module (`agent.py`, `config.py`, `tracing.py`,
  `storage.py`, `bot.py`, `dashboard_server.py`) -- only *target* code in
  those files for mutation `find`/`replace` strings, never edit real code.
- This task is the one named exception permitting running
  `devtools/mutation_check.py` directly (both `--select v160-` and a full
  run) -- normally forbidden for an agent to invoke itself.
- No `bot.py --selftest-live`, no live LM Studio/OpenRouter network call.
- Do not commit; leave the tree unstaged for the orchestrator.
- No new dependencies.

## Acceptance

- `uv run --locked ruff check .` -- clean.
- `uv run --locked pytest -q` -- all green, no new failures.
- `uv run --locked python devtools/mutation_check.py --list` -- 82 entries,
  all ids unique, the ten `v160-*` ids present.
- `uv run --locked python devtools/mutation_check.py --select v160-` -- 10
  mutations, 10 killed, 0 survived, 0 errored, 0 drifted.
- `uv run --locked python devtools/checks.py lint-docs` -- clean, including
  this prompt file's header/block shape.
- `git status --porcelain` -- exactly the six owned files, nothing under
  `docs/spec/`, no production module dirty.

### Measurement 1 -- `mutation-v160` (`--select v160-`)

Corrected run (after both survivors were fixed -- see the two entries'
history in `devtools/mutation_check.py`), `10 mutations, 10 killed,
0 survived, 0 errored, 0 drifted`:

```
real	9m10,338s
user	4m44,990s
sys	1m7,610s
```

`timeout_seconds` arithmetic: 550.338s measured -> 2x = 1100.676s ->
smallest multiple of 10 >= 1100.676 = **1110s**. Set in
`config/quality_gates.yaml`'s `mutation-v160` gate.

An earlier, uncorrected subset run (before the `status-message-redact` and
`readonly-connection` fixes) measured `real 8m51,317s` with `8 killed,
2 survived` -- not used for the timeout, kept only as the empirical evidence
that motivated the two fixes documented in findings 2 and the ledger above.

### Measurement 2 -- `mutation-all` (full 82-entry run)

`82 mutations, 82 killed, 0 survived, 0 errored, 0 drifted`:

```
real	31m48,041s
user	12m33,928s
sys	2m51,918s
```

`timeout_seconds` arithmetic: 1908.041s measured -> 2x = 3816.082s ->
smallest multiple of 10 >= 3816.082 = **3820s**, replacing the previous
`2600` (measured 2026-09-04 at 72 entries, ~1273s). Cross-check: the ten
new `v160-*` entries alone measured ~550s in isolation (Measurement 1);
1273 + 550 = 1823s tracks the new 1908s total closely; the remaining ~85s
gap is consistent with the pre-existing 72 entries running marginally
slower as the overall suite grew, not with any change to those entries
themselves -- an inference from arithmetic, not separately measured.

### `--list` output (verbatim, 82 entries)

```
cov-01-live-docker-sandbox-max-bytes	bot.py	TST-02 #1: _live_docker must pass the configured quota, not the default
cov-02-pre-run-refusal-incomplete	tools.py	TST-02 #2: an unreadable sandbox must be refused, not measured as empty
cov-03-post-run-quota-on-timeout	tools.py	TST-02 #3: the timeout branch must still record the post-run quota fact
cov-04-post-run-quota-on-docker-exit	tools.py	TST-02 #4: the docker-exit 125/126/127 branch must record post-run quota
cov-05-pop-before-envelope	tools.py	TST-02 #5: the internal keys must be popped, not merely read, before the envelope
cov-06-empty-resolv-wiring	bot.py	TST-02 #6: main() must pass the real empty_resolv path into the runner partial
cov-07-finish-redacts	agent.py	TST-02 #7: agent.finish must redact before storing the reply
cov-08-summarize-redacts	agent.py	TST-02 #8: summarize_conversation must redact before any caller sees it
cov-09-probe-user-flag	tools.py	TST-02 #9: the timeout probe must run as the bot's own uid:gid, not root
cov-10-sandbox-usage-followlinks	tools.py	TST-02 #10: sandbox_usage must never follow a symlinked directory
cov-11-capture-headroom	tools.py	TST-02 #11: _Capture must see a straddling secret whole before the cut
sec-id-01-minted-id	agent.py	REQ-V12-ID-01: the model's tool-call id must never be trusted or stored
sec-qta-01-onerror	tools.py	REQ-V12-QTA-01: an unreadable subtree must fail the scan closed, not silently
sec-qta-02-fail-closed	tools.py	REQ-V12-QTA-02: a cut-short scan must refuse the run, not let it proceed
sec-qta-01-incomplete-precedence	tools.py	REQ-V12-QTA-01: SCAN_INCOMPLETE must never be downgraded to SCAN_CUT_SHORT
sec-ssr-01-shape-check	config.py	REQ-V12-SSR-01: shortened/hexadecimal IPv4 allowlist entries must be rejected
sec-ssr-03-request-time-guard	tools.py	REQ-V12-SSR-03: the resolved address must be checked before any request
sec-inf-01-o-nofollow	bot.py	REQ-V12-INF-01: a symlink planted at the resolv path must be refused
sec-orp-02-liveness-check	bot.py	REQ-V12-ORP-02: a container owned by a live process must be skipped
sec-orp-01-start-ticks-parse	tools.py	REQ-V12-ORP-01: a foreign process's comm field may contain spaces/parens
sec-orp-03-137-mapping	tools.py	REQ-V12-ORP-03: exit 137 under the wrapper must map to timed_out too
sec-aud-01-hook-redaction	tools.py	REQ-V12-AUD-01: the audit hook must receive an already-redacted record
sec-id-04-selftest-pairing	bot.py	REQ-V12-ID-04: the selftest must check the call and its result share an id
sec-qta-03-chmod-and-retry	bot.py	REQ-V12-QTA-03: the startup cleanup must survive a chmod-000 subdirectory
v11-storage-add-tool-turn-redacts	storage.py	REQ-V11-RED-01: add_tool_turn must redact the assistant content it stores
v11-send-redacts	bot.py	REQ-V11-RED-04: every outgoing Telegram send must redact its text
v11-status-line-redacts	bot.py	REQ-V1-VIS-01: the status line must redact before truncating
v11-fetch-cap-breaks-the-stream	tools.py	REQ-V1-FT-02: fetch_url must stop reading once past its cap
trn-03-secret-headroom-term	tools.py	REQ-V12-TST-01: fetch_url must read past its cap by the longest secret
trn-03-strip-secret-fragment	tools.py	REQ-V13-TOO-09: fetch_url must strip a surviving fragment after the byte cut
ssr-is-global-backstop	config.py	REQ-V12-SSR-02: carrier-grade NAT must be caught by the is_global backstop
v13-usage-parse-none	llm/base.py	REQ-V13-OBS-01: parse_response must hand the parsed usage to the response
v13-cached-tokens-dropped	llm/base.py	REQ-V13-OBS-01: a reported cached_tokens count must reach the row
v13-think-not-stripped	llm/base.py	REQ-V13-OBS-02: a balanced <think> block must never reach the user
v13-llm-call-not-recorded-on-error	agent.py	REQ-V13-OBS-04 / REQ-V160-TRC-08: every LLM invocation, failed or not, is an invocation and gets its own row and chat span
v13-resent-formula	metrics.py	REQ-V13-OBS-08: new_i is the growth over the previous prompt, not all of it
v13-cost-drops-output	llm/pricing.py	REQ-V13-PRC-01: the cost formula must charge the completion tokens
v13-cost-none-as-zero	llm/pricing.py	REQ-V13-PRC-01: a partially reported usage stores NULL, never a cost of 0.0
v13-bench-gate-threshold	devtools/bench.py	REQ-V13-BEN-12: the gate demands a 30% cut, not merely no regression
v13-bench-skipset-ignored	devtools/bench.py	REQ-V13-BEN-12: two files with different skip sets may not be compared
v13-bench-scenario-hash-ignored	devtools/bench.py	REQ-V13-BEN-12: a differing scenarios_sha256 makes two files incomparable
v13-bench-candidate-pricing	devtools/bench.py	REQ-V13-BEN-12: both sides are priced with the baseline's snapshot
v13-bench-quality-minus-one	devtools/bench.py	REQ-V13-BEN-12: at 36 runs one lost run is 2.8 pp and must fail the gate
v13-bench-redact-detail	devtools/bench.py	REQ-V13-BEN-10: redaction recurses into arrays of objects (checks[].detail)
v13-bench-turn-zero-based	devtools/bench_scenarios.py	REQ-V13-BEN-08: a positive turn is one-based over the non-command turns
v13-bench-timeout-continues	devtools/bench.py	REQ-V13-BEN-05: a timeout aborts the run; no later scenario is started
v13-bench-check-trusts-summary	devtools/bench.py	REQ-V13-BEN-01: check recomputes the summary instead of trusting the file
v13-usage-missing-ignores-failed	devtools/bench.py	REQ-V13-BEN-01: a failed call's NULL token columns are not usage_missing
v13-openrouter-cap-ignored	devtools/bench.py	REQ-V13-BEN-02: an OpenRouter run without --max-cost-usd is refused
v13-symlink-chmod	bot.py	REQ-V13-CO-01: the recovery chmod must skip a symlink, never its target
v13-only-typo-exit0	devtools/mutation_check.py	REQ-V13-CO-06: --only with an unknown id exits 1, never a clean zero
v13-compact-keeps-head-only	tools.py	REQ-V13-TOO-01: compaction keeps a tail window, not the head alone
v13-dedup-threshold	tools.py	REQ-V13-TOO-04: a run of exactly two identical lines is not collapsed
v13-fragment-after-cut	tools.py	REQ-V13-TOO-01: the single-line fallback strips a fragment after the cut
v13-fetch-inline-fragment-after-cut	tools.py	REQ-V13-TOO-09: the inline max_chars cut is followed by a fragment strip
v13-fetch-script-kept	tools.py	REQ-V13-TOO-05: script bodies are markup, never extracted text
v13-fetch-save-path	tools.py	REQ-V13-TOO-06: the saved name is the URL hash, never a model-chosen path
v13-fetch-dir-follows-symlink	tools.py	REQ-V13-TOO-06: a symlinked fetch/ directory must be refused, not followed
v13-fetch-save-reuses-inode	tools.py	REQ-V13-TOO-06: a fresh inode, never a truncating write into a hard link
v13-fetch-save-always	tools.py	REQ-V13-TOO-06: only a truncated fetch leaves a file behind
v13-compact-over-budget	tools.py	REQ-V13-TOO-01: the marker is reserved, so len(result) <= max_chars holds
v13-stub-current-turn	agent.py	REQ-V13-HST-01: a result of this invocation is never stale, never stubbed
v13-stub-skill-latest	agent.py	REQ-V13-HST-02: the most recent load of each skill survives verbatim
v13-now-in-system	agent.py	REQ-V13-CCH-01: the clock stays out of the cacheable prefix
v13-routing-agent-too	llm/__init__.py	REQ-V13-RTE-01: LLM_SUMMARY_MODEL routes the summary purpose and only it
v14-ben-03-unknown-column-accepted	devtools/bench.py	REQ-V14-BEN-03: a row carrying a key neither REQUIRED nor ALLOWED expects must be rejected, naming it -- this mutation accepts any unknown column silently
v14-ben-03-missing-column-accepted	devtools/bench.py	REQ-V14-BEN-03: a row missing a REQUIRED column must be rejected, naming it -- this mutation silently accepts a row lacking one
v14-rel-01-timeout-budget-boundary-disabled	config.py	REQ-V14-REL-01: an LLM_TIMEOUT_S/LLM_MAX_TOKENS pair under the latency-model floor must be refused before it ever reaches a live request, not silently accepted
v15-severity-comparison-inverted	devtools/checks.py	REQ-V15-GATE-12: a configured severity must block, an unconfigured one must not -- inverting the membership test makes a blocking gate ignore exactly the severities it is configured to catch
v15-fail-closed-becomes-fail-open	devtools/checks.py	REQ-V15-GATE-06: a gate that cannot run (missing binary, timeout) must fail closed, never silently pass
v15-shadow-flag-ignored	devtools/checks.py	REQ-V15-GATE-06: blocking: false must withhold findings from blocking the profile -- discarding the flag makes every gate with a finding block regardless of shadow status
v15-diff-scope-filter-dropped	devtools/checks.py	REQ-V15-GATE-07: a diff-scoped gate must block only on the in-scope partition -- replacing the filter with "all files" makes every finding in-scope, including ones the change never touched
v160-bind-address-widened	dashboard_server.py	REQ-V160-SRV-03: the dashboard binds loopback only, never a configurable or wider address
v160-capture-content-default-on	config.py	REQ-V160-TRC-09: content capture is off by default -- content never leaves the process unless an operator opts in
v160-status-message-redact-bypassed	tracing.py	REQ-V160-TRC-11: a span's status_message must be redacted before it is ever stored, the same content-must-never-leave-unredacted mechanism section 15.4 is after
v160-fingerprint-threshold-off-by-one	agent.py	REQ-V160-TQ-04: the third identical failing call is refused, not the fourth
v160-truncated-summary-accepted	agent.py	REQ-V160-TQ-01: a summary response with finish_reason == "length" must be rejected unparsed, never accepted as a real summary
v160-selftest-starts-the-server	bot.py	REQ-V160-SRV-05: the selftest path must construct no server at all -- it must return before any of the default run's startup work, dashboard construction included, ever executes
v160-version-literal-not-pyproject	bot.py	REQ-V160-VER-01: --version must print pyproject.toml's real version, read fresh, never a literal
v160-readonly-connection-writable	storage.py	REQ-V160-SRV-06: the dashboard's own connection must be unable to write, an INSERT through it must raise
v160-error-echoes-request-input	dashboard_server.py	REQ-V160-DSH-07 / N5: a 400 body must name only the parameter, never echo the attacker-supplied value back
v160-host-check-disabled	dashboard_server.py	REQ-V160-SRV-10: a request whose Host header does not match must be rejected with 400, never let through
```

## Stop

Three findings surfaced during construction, all resolved by reading and
empirical hand-mutation rather than by assuming the spec table's mechanism
descriptions map 1:1 onto what the current test suite actually exercises:

1. **`config.py:334`'s `load_config()`-path `_parse_bool(source,
   "OBS_CAPTURE_CONTENT", False)` is unprovable as a mutation target.** No
   test in the suite calls `load_config()` and inspects the resulting
   `Config.obs_capture_content` field for the `OBS_CAPTURE_CONTENT` env var
   specifically (`tests/test_config.py` never touches this variable; the
   observability tests build `Config` directly via `make_cfg()`, bypassing
   `load_config()` entirely). The entry
   (`v160-capture-content-default-on`) instead targets the *other*
   independent default -- the `Config` dataclass field default itself
   (`obs_capture_content: bool = False` at `config.py:123`) -- which is what
   every content-capture test actually exercises when it does not pass the
   field explicitly. This is a genuine coverage gap in the `load_config()`
   path, not a defect in the entry: worth a follow-up test in a later task,
   not fixed here (out of this task's owned-file scope).

2. **`tracing.py:343`'s content-attribute redaction
   (`set_content_attribute`'s own `text = config.redact(value)` call) is
   masked by a redundant upstream protection.** `storage.add_user_message`
   and `add_assistant_message` redact content *before* persisting it, so by
   the time `agent.run_agent`'s message history is re-read from storage and
   reaches `tracing.set_content_attribute`, the content is already redacted
   -- mutating that call's own redact step changes nothing any existing test
   observes. The spec table's prescribed id
   (`v160-content-redact-bypassed`) was therefore **not added** as a
   distinct entry; landing it under that id with a retargeted `find`/
   `replace` would have produced an entry that *looks* like it proves
   REQ-V160-TRC-10 while actually proving nothing (REQ-V160-REV-01 item 5's
   reviewer check -- "each mechanism of §15.4 has a mutation entry whose
   `find` matches once" -- would pass on a false premise, which is worse
   than a visible gap). In its place, `v160-status-message-redact-bypassed`
   targets the same redact-before-storage *mechanism*, one call site over:
   `MutableSpan.set_error`'s `message = config.redact(message)`
   (`tracing.py:224`, REQ-V160-TRC-11), which has no such upstream
   double-protection and is killed by the suite's existing `set_error`/
   status-message tests. Net count unchanged at ten `v160-*` entries; the
   full landed-vs-spec ledger is below.

3. **`T-V160-DSH-05`'s described "canary sweep" over all 14 dashboard routes
   (REQ-V160-DSH-07) appears unimplemented in the current test suite.**
   `tests/test_v160_dashboard.py:380-396` has a CANARY-based test, but it
   exercises `dashboard_render.py`'s rendering-layer scrub, not
   `dashboard_server.py`'s error-body echo path the spec table's
   "killed by" column names for `v160-error-echoes-request-input`. The
   entry instead targets `_parse_group`'s `_bad_request("group",
   is_api=is_api)` call (the only single-occurrence `_bad_request`
   name-argument call site in the file -- `since`/`limit`/`conv` each call
   it twice, so mutating any of those would drift, not kill) and is
   confirmed killed by the real, existing N5 test,
   `test_n5_bad_params_400_names_only_the_parameter`. Flagged for whichever
   later task owns dashboard test coverage, not fixed here.

Full ten-row ledger, spec §15.4's id/mechanism against what actually landed
(the "first failure" column names the test that appeared first under
`pytest -x`'s stop-on-first-failure ordering in the real `--select v160-`
run above (Measurement 1) -- the test that *fired*, not necessarily the one
§15.4's table predicts. Note for anyone re-opening the raw log
(`/tmp/v160_final.log`, not committed): `mutation_check.py`'s own
`running mutation: <id>` prints are block-buffered when stdout is not a
tty (redirected to a file), while each `pytest -x` subprocess writes
straight to the inherited file descriptor -- so the file shows all ten
`FAILED ...` lines first, then all ten `running mutation:`/verdict pairs as
one flushed block at exit, not interleaved pairs. Nine of the ten rows
below are identifiable by test name alone regardless of this (each
`FAILED` test's name encodes the mechanism it proves --
`srv_03_bind_address`, `trc_11_status_message`,
`tq_04_third_identical_failure`, `tq_01_double_truncation`,
`srv_04_selftest_binds_nothing`, `ver_01_version_matches_pyproject`,
`srv_06_connect_readonly_cannot_write`, `n5_bad_params`,
`srv_10_host_header`); only the
`capture-content-default-on` row's attribution (the bench meta test, whose
name says nothing about content capture) rests on *ordinal position*
within the two separately-buffered, internally-chronological sequences; REQ-V160-REV-01 item 5's per-mechanism check is satisfied by the
`find` match, independent of which test happens to sort first):

| spec §15.4 id | landed as | path / target | first failure under `-x` | deviation |
|---|---|---|---|---|
| `v160-bind-address-widened` | unchanged | `dashboard_server.py`: `DASHBOARD_BIND` | `test_t_v160_srv_03_bind_address_is_fixed_loopback` | none |
| `v160-capture-content-default-on` | unchanged | `config.py:123` `Config.obs_capture_content` dataclass default (not `config.py:334`'s `load_config()` path -- finding 1) | `test_v160_bench.py::test_the_six_new_meta_keys_are_present_after_a_run` (`assert True is False`) | target moved; §15.4 names the TRC-09/-10 content-capture tests, but under `-x` the first failure was this bench meta test (which also depends on the same dataclass default) -- the TRC-09/-10 tests were never reached, not confirmed as killers here |
| `v160-content-redact-bypassed` | **`v160-status-message-redact-bypassed`** | `tracing.py:224` `MutableSpan.set_error`'s `config.redact(message)` (not `tracing.py:343` -- finding 2) | `test_t_v160_trc_11_status_message_is_redacted_then_truncated` | substituted id, target one call site over |
| `v160-fingerprint-threshold-off-by-one` | unchanged | `agent.py`: `TOOL_REPEAT_REFUSAL_THRESHOLD` | `test_t_v160_tq_04_third_identical_failure_is_refused_not_executed` | none |
| `v160-truncated-summary-accepted` | unchanged | `agent.py`: `truncated = response.finish_reason == "length"` | `test_t_v160_tq_01_double_truncation_proceeds_without_a_summary` | none |
| `v160-selftest-starts-the-server` | unchanged | `bot.py`: `if "--selftest" in arguments:` guard | `test_t_v160_srv_04_selftest_binds_nothing` | none |
| `v160-version-literal-not-pyproject` | unchanged | `bot.py`: `_read_version` | `test_t_v160_ver_01_version_matches_pyproject` | none |
| `v160-readonly-connection-writable` | unchanged | `storage.py`: `connect_readonly` -- combined `mode=ro` -> `mode=rw` AND dropped `PRAGMA query_only = ON` in one mutation | `test_t_v160_srv_06_connect_readonly_cannot_write` | broader: either protection alone is masked by the other (empirically verified by hand-mutation), so the entry mutates both in one `find`/`replace` |
| `v160-error-echoes-request-input` | unchanged | `dashboard_server.py`: `_parse_group`'s `_bad_request("group", is_api=is_api)` (the only single-occurrence `_bad_request` name-argument call site -- `since`/`limit`/`conv` each call it twice, which would drift, not kill) | `test_n5_bad_params_400_names_only_the_parameter` | different killer than §15.4's T-V160-DSH-05 canary sweep, which appears unimplemented (finding 3) |
| `v160-host-check-disabled` | unchanged | `dashboard_server.py`: Host-header `if not valid:` guard | `test_t_v160_srv_10_host_header_rejected_cases` | none |

One line on `devtools/mutation_check.py`'s own top-of-file running-tally
comment (the "28 ... 65 in all ... 68 in all" progression near lines 30-44):
left untouched deliberately, not an oversight. It already stops at v1.4 and
never mentioned the four `v15-*` entries either, so leaving it at its
pre-existing endpoint is consistent with precedent, not a new gap this task
introduced.

REQ-V160-GATE-05 note, flagged for T15, no action taken here:
`mutation-v160` alone measured 550.338s (Measurement 1) against the
`pre-push` profile's 180s observational budget -- roughly 3x that budget by
itself, before `mutation-v15`'s own ~99.5s (per its existing comment) or any
of the other `pre-push` gates (`ruff-check-all`, `ruff-format`,
`branch-name`, `pytest`, `selftest`, the three scanners, `hooks-installed`,
`doctor`) are added. Root cause: every `v160-*` entry's killing test lives
in `test_v160_*.py`, which sorts after `test_v15_*.py` and every earlier
`test_v1*.py` file alphabetically, so under `pytest -x`'s stop-on-first-
failure ordering, each `v160-*` kill runs nearly the entire ~1004-test
suite before the first failure lands, instead of exiting early the way
`mutation-v15`'s earlier-sorting killers do (~25s/entry there vs
~55s/entry here). T15 owns whatever profile-budget consequence follows.

One process-management note for the orchestrator: mid-task, an earlier
(uncorrected) full 82-entry measurement attempt was interrupted with
`pkill -9` while `bot.py` was mid-mutation under the pre-existing entry
`cov-01-live-docker-sandbox-max-bytes` (`_live_docker`'s
`sandbox_max_bytes=cfg.exec_sandbox_max_bytes` -> the unconfigured default,
TST-02 #1), because `SIGKILL` bypasses
`mutation_check.py`'s `finally`-based restore and the working tree was
briefly left with a mutated `bot.py`. Caught immediately via `git status
--porcelain` (`M bot.py` where only the six owned files should appear),
restored with `git checkout -- bot.py`, and the restore was verified clean
-- not merely assumed -- by rerunning `uv run --locked pytest
tests/test_mutation_check.py -q` (exit 0), which re-reads every `find`
string, `bot.py`'s two entries included, against the real tree. The
corrected full run was relaunched via `nohup ... & disown` rather than
`pkill`, and left to complete undisturbed; see Measurement 2 above.
