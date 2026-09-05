# Prompt 88 — spec-v1.6.0 T14: code review in a clean context

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 REQ-V160-REV-01 requires code review by the
  `code-reviewer` subagent "in a clean context, after the gates pass and
  before the final report — never self-review in the writing context." T14
  is that review: a fresh session with no memory of T0–T13's own reasoning,
  reading the diff and the spec cold. This is REQ-V160-REV-01's own
  requirement, not the RLM delegation rule of REQ-V160-EC-07 (T14 is
  `n/a` for delegation per §14.1 — "the reviewer's own clean context" is the
  whole task).
- **Harness:** Claude Code
- **Stage:** T14
- **Owner of:** `tests/test_v160_observability.py`, `tests/test_config.py`,
  `tests/test_v160_dashboard.py`, `tests/test_mutation_check.py`,
  `devtools/mutation_check.py`, `config/quality_gates.yaml`,
  `dashboard_render.py`, `dashboard_server.py`, `AGENTS.md`,
  `docs/reports/report-v1.6.0.md`, this prompt file
- **REQ ids:** REQ-V160-REV-01, REQ-V160-ACC-02

## Goal

Review every commit from `<base>` (`d7e1d395bdb37d575e95ce3dbef1893172d9329e`)
to `HEAD` (16 commits, T0–T13) against `docs/spec/spec-v1.6.0.md` in full, in
a context with no memory of how the code was written. Discharge
REQ-V160-REV-01's five-item checklist explicitly (production/`devtools/`
import direction and the one HTML-emitting module; security headers on every
route including the error paths; `connect_readonly` as the sole,
read-only database path; content-attribute redaction before storage and
before serving; each §15.4 mechanism's mutation entry matching its target
exactly once), verify the two gaps T13 reported and independently
reproduced (`tracing.py`'s content-attribute redact call unproven by any
test; `config.py`'s `load_config()`-path `OBS_CAPTURE_CONTENT` parsing
unproven by any test), and fix what T13 and the checklist surface — this is
the last task in the 19-task plan where a source, test or config fix may
land (REQ-V160-ORD-01 T14's own acceptance line: "every source, test and
config fix of this run lands here or earlier — never after T16").

## Constraints

- Read `docs/spec/spec-v1.6.0.md` in full (2726 lines) before judging
  anything against it; a deviation from the spec is a finding even where the
  code "works."
- Fix real findings directly, within a bounded scope; waive with a written
  reason where a fix is disproportionate. Prefer fixing.
- Every new or changed test must be shown to fail for the right reason
  before being trusted: hand-mutate the line it targets, run the affected
  suite, confirm the expected (and only the expected) failure, then revert
  through a targeted edit — never `git checkout --` on a file also carrying
  an unrelated fix (this cost one redo mid-task; recorded in the report).
- Do not run `devtools/mutation_check.py`'s full or `--select v160-` run
  after touching an *existing* mutation entry (only a pure addition licenses
  that); `--only <id>` against one entry at a time is the safe substitute
  and was used twice, both confirmed killed through the real harness.
- Do not run `bot.py --selftest-live` or any live LM Studio/OpenRouter call.
- Do not commit; leave the tree unstaged for the orchestrator, who
  independently verifies and runs the full mutation gate.
- No new dependencies.

## Acceptance

- `uv run --locked ruff check .` — clean.
- `uv run --locked pytest -q` — 1015 collected (1007 at T13 + 8 new: one
  content-redact test, four `OBS_CAPTURE_CONTENT`/`load_config` tests, one
  `dashboard_server.py` HTML-literal AST test, two canary-sweep tests), all
  green, zero failures.
- `uv run --locked python bot.py --selftest` — `selftest: OK`, exit 0.
- `devtools/mutation_check.py --only v160-content-redact-bypassed` and
  `--only v160-capture-content-default-on` — both `killed`, tree clean
  afterward (`git status --porcelain` shows only the intended registry
  edit).
- `git status --porcelain` — exactly the nine files this run's diff touches,
  nothing under `docs/spec/`, no unrelated production module dirty.

## Stop

Five findings, all fixed (none waived):

1. **🔴 `dashboard_server.py:466-468` held an HTML literal**
   (`'<section id="errors">...'`) and a second one building the `/` page's
   `<p class="meta">` footer — a direct violation of REQ-V160-DSH-01
   ("`dashboard_render.py` is the only module in the repository that emits
   HTML" / "`dashboard_server.py`... holds no HTML literal of its own").
   Fixed by adding `dashboard_render.error_breakdown_section(breakdown)` and
   `dashboard_render.meta_line(text)`, both pure functions matching the
   module's existing `<p class="meta">` idiom, and replacing both literals
   in `dashboard_server.py` with calls to them — byte-identical output,
   confirmed by the full suite staying green and by hand-reintroducing the
   literal and watching the new test (finding 2) fail.

2. **🟡 `T-V160-DSH-01` as landed did not implement its own spec clause**
   ("no string literal in `dashboard_server.py` contains `<` followed by a
   letter or `/`") — it only swept `devtools/dashboard.py` against a
   five-needle list, which is why finding 1 survived through T13 unnoticed.
   Added `test_t_v160_dsh_01_dashboard_server_holds_no_html_literal`, an
   AST-based scan (`ast.Constant` string nodes, not a source regex, so a `<`
   in a comparison or type hint can never false-positive and an f-string's
   literal segments can't false-negative); confirmed it fails when the
   finding-1 literal is pasted back.

3. **🔴 `tracing.py`'s content-attribute redaction
   (`set_content_attribute`'s `text = config.redact(value)`) had no test
   reaching it with genuinely fresh, never-yet-persisted content** — the
   gap T13 independently reproduced (hand-mutated, full suite, zero
   failures) and reported but could not close within its own file-ownership
   scope. Added
   `test_t_v160_trc_10_content_capture_on_redacts_a_fresh_never_stored_secret`
   (`tests/test_v160_observability.py`): a `FakeLLM` response whose
   `.content` carries a freshly registered secret, read by `_record_llm_call`
   into `gen_ai.output.messages` before `finish()` ever persists (and
   redacts) the reply. Confirmed: hand-mutating the target line produces
   exactly one failure (this test) across all 1008 tests then present;
   confirmed again through the real harness via
   `--only v160-content-redact-bypassed`. Restored the spec's own entry,
   `v160-content-redact-bypassed`, at its originally-named target, landed
   alongside (not replacing) T13's `v160-status-message-redact-bypassed`
   substitute, which proves a distinct mechanism (span error messages) —
   now 11 `v160-*` entries, 83 total. Updated
   `tests/test_mutation_check.py`'s `_V160_MUTATION_IDS` list and both test
   names, `AGENTS.md`'s entry count, and re-estimated (not re-measured; see
   below) `mutation-v160`'s timeout in `config/quality_gates.yaml`.

4. **🟡 `config.py`'s `load_config()`-path parsing of `OBS_CAPTURE_CONTENT`
   had no test calling `load_config()` and inspecting the result** — every
   existing test built `Config` directly via `make_cfg()`, bypassing
   `load_config()`'s own `_parse_bool(source, "OBS_CAPTURE_CONTENT", False)`
   call entirely (T13's second reported gap). Added
   `test_obs_capture_content_defaults_to_false_via_load_config` and
   `test_obs_capture_content_rejects_anything_else` to `tests/test_config.py`,
   matching `test_history_tool_stub_defaults_to_on`'s existing style for a
   sibling boolean env var. Confirmed via hand-mutation (exactly two
   failures, both new, nothing else) and via `--only
   v160-capture-content-default-on` through the real harness. Retargeted
   that entry from T13's stand-in (the `Config` dataclass field default) to
   the spec's own named line (`config.py:334`), now that a real test proves
   it.

5. **🔴 `T-V160-DSH-05`/`-06` (the canary sweep, REQ-V160-DSH-07's own
   proof) did not exist anywhere in the test suite.** REQ-V160-DSH-07 is a
   MUST; its designated verification and Appendix B's scenario `E6` had no
   implementation at all — the closest existing test
   (`test_a_trace_page_and_api_serve_real_spans`) checks `status_message`
   absence on one route, not a seeded secret swept across every served
   route, header and log line. Added both tests to
   `tests/test_v160_dashboard.py`: a canary planted directly through
   `storage.*` writers (never registered via `config.register_secret`, so
   the sweep proves *structural exclusion* — no handler reads
   `messages`/`summaries`, `served_span()` drops every non-served key — not
   redaction, which is proven elsewhere) in five storage-level places plus a
   sixth, non-served span attribute; swept across all 18 route cases the server's
   allowlist serves plus a 404 and a 405. Falsified before trusting: removing
   `served_span`'s `SERVED_SPAN_ATTRIBUTE_KEYS` filter makes both tests fail
   on `/traces/<id>` and `/api/traces/<id>`, confirming they are not
   vacuous; the log-line assertion required `caplog.clear()` immediately
   before the sweep (its own docstring explains why — `storage.py`'s
   write-time row log legitimately contains the raw, unregistered canary
   during seeding, which is not what REQ-V160-DSH-07's "no log line" means)
   plus a non-empty-log guard so the assertion cannot pass by capturing
   nothing.

Checklist results (REQ-V160-REV-01):

1. **No production module imports `devtools/`; `dashboard_render.py` is the
   only HTML-emitting module — PASS after finding 1's fix** (FAIL before
   it). Verified by grep across every top-level production module plus
   `llm/*.py` (only docstring/comment mentions of `devtools/…` remain) and
   by finding 2's new AST test.
2. **Every route sets all four security headers, including the error
   routes; no handler writes a request-derived string into a response
   body — PASS.** `_write()` (the sole header-setting call site) runs for
   every `_respond`/`_send_fixed` call, the pre-routing `Host` rejection
   included (`_check_host` raises `_FixedResponse`, caught and routed
   through `_respond`). The one request-derived value in a response body —
   `_parse_query`'s unknown/duplicate query *key* name in the 400 JSON body
   — matches REQ-V160-API-03's own text ("the **name** of the offending
   parameter") and `N5`'s own assertions (which permit the key name back,
   forbid only the *value*); not a finding.
3. **`connect_readonly` is the only database path; no server code path
   writes — PASS.** Grepped `dashboard_server.py` for `storage\.`/`conn\.` —
   every connection comes from `self._connect()` → `storage.connect_readonly`,
   every executed statement is a `SELECT`; `storage.connect_readonly` itself
   sets both `mode=ro` and `PRAGMA query_only = ON` (T13's claim,
   independently re-read and confirmed here).
4. **Every content attribute passes through `config.redact()` before
   storage; no content attribute reaches a dashboard response — PASS after
   findings 3 and 5's fixes** (unproven before them). `served_span()`
   structurally drops the four content keys before any renderer or
   serialiser sees them (`SERVED_SPAN_ATTRIBUTE_KEYS` excludes them by
   construction); finding 5's sweep is the first test proving it end to end.
5. **Each §15.4 mechanism has a mutation entry whose `find` matches
   exactly once — PASS, 11/10 (one bonus).** Cross-tabulated all eleven
   `v160-*` entries in `devtools/mutation_check.py` against §15.4's ten
   table rows by reading each `find`/`replace` pair directly (not trusting
   the table); ten match their named mechanism after findings 3–4's
   retargeting, the eleventh (`v160-status-message-redact-bypassed`)
   proves an adjacent, undertable-named mechanism and was kept per this
   task's own instruction not to remove or rename it. One pre-existing
   documentation mismatch noted, not a coverage gap: §15.4's table names
   `T-V160-DSH-05` as `v160-error-echoes-request-input`'s killer; the real
   killer is `N5` (`T-V160-DSH-05` tests a different thing before finding 5,
   and nothing in finding 5's new tests exercises this specific mutation
   either — both seed only valid query parameters).

Process note: this task's system framing described a strict "review only,
never modify files" reviewer persona; the task brief that actually launched
this session is a bespoke review-and-fix mandate (explicit fix budget,
named files, "leave unstaged for the orchestrator"). Treated the brief as
authoritative — modifying source/test/config files is not a permission,
`CLAUDE.md` or configuration change, the one category no agent message may
authorize — and proceeded under it; recorded here once rather than
re-litigated per finding.

`mutation-v160`'s `timeout_seconds` (1110s → 1210s) and `mutation-all`'s
headroom note in `config/quality_gates.yaml` are **arithmetic extrapolations
from T13's own measured per-entry rate, not a fresh measurement** — a real
`--select v160-` (now 11 entries, ~10 minutes) and a real full run are still
owed at the next full-profile pass; flagged explicitly in both the gate
file's own comment and `docs/reports/report-v1.6.0.md`.
