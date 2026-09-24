# tg-agent-bot v1.11.1 — the plain fallback narrowed to HTTP 400, two table widths, the `/sessions` empty state, one batch constant, the xdist-order flake, six untested error rows, and the v1.11.0 paperwork corrected

A PATCH collecting every known v1.11.0 leftover: the `<pre>` plain
fallback fires only on `TelegramError.status == 400`; `/documents` ids
render whole to 99,999 and the `/model` status label never truncates;
`/sessions` gets a plain empty-state reply; `DOC_LIMIT_REPLY` names both
`/delete` forms; one embedding batch constant
(`llm.embeddings.BATCH_SIZE`); ERR-01 rows 11–16 get dispatch-level
tests; an autouse `tests/conftest.py` fixture kills the secrets-registry
xdist-order flake; README/`docs/plan.md`/`AGENTS.md` drift and the
v1.11.0 report/post record are corrected. Spec: `docs/spec/spec-v1.11.1.md`.
`<base>` = `2431034` (`24310349ee95d703bb3b256443a4b5e1dd22b415`, the
commit the spec's `file:line` citations describe, also tag `v1.11.0`).
Spec `sha256`:
`4c8b32e837a81cab37d0fc1516db6971ce960eeba61f8c4331f6ae0da86550e0`
(110,779 bytes).

This file is filled progressively: T0 (this skeleton), T1 (the 400-only
fallback, three docstrings), T2 (table widths, empty state, refusal
string, batch constant), T3 (the six ERR-01 rows, the xdist flake), T4
(README/plan/AGENTS drift, the v1.11.0 report/post correction), T5
(clean-context review, gates 1–8), T6 (version bump, evidence commit,
local tag). Sections not yet reached read "not reached: T\<n\>".

## T0 — preconditions, gates 1–5, measurements, pin inventory

`<base>` = `2431034`. Spec `sha256` as above. `Status: ready for \`go\`` —
present once (`grep -n '^Status:'`), reads "ready for `go` — cross-review
rounds 1–3 of 3 applied (Appendix C; termination `round_limit`)".

### Preconditions (EC-04)

- `git rev-parse v1.11.0^{commit}` = `24310349ee95d703bb3b256443a4b5e1dd22b415`
  — matches.
- `git merge-base --is-ancestor v1.11.0 HEAD` — exit 0.
- `git describe --tags --abbrev=0` = `v1.11.0`.
- `git diff --name-only v1.11.0..HEAD`, sorted: `docs/handoff-v1.11.1.md`,
  `docs/llm-usage.md`, `docs/prompts/255-v1111-spec-authoring.md`,
  `docs/spec/spec-v1.11.1.md` — exactly EC-04's four paths, nothing else.
- `git status --porcelain` — empty.
- `git stash list` — empty, recorded.
- `test -f .env` — exit 0.
- `docs/prompts/255-v1111-spec-authoring.md` present; `docs/llm-usage.md`
  row 166 present (the spec-authoring row).
- `git diff --exit-code HEAD -- docs/spec/spec-v1.11.1.md` — exit 0
  (committed, unmodified).
- `git rev-parse HEAD` at `go` time = `43a985daae29098e56209fdbf07db9e4f4f87818`
  — matches `docs/handoff-v1.11.1.md`'s informational statement.

Every structural precondition holds; no precondition mismatch (ERR-01 row
14 not triggered).

### LM Studio address and the override precondition (EC-04)

- **LM Studio address**: `go` text named `<addr>`. Applied the one
  permitted `sed -i` to `.env`'s `LMSTUDIO_BASE_URL` line (value never
  printed; confirmed only by `grep -c` exit status matching the expected
  pattern `LMSTUDIO_BASE_URL=http://<addr>:1234/v1` — `/v1` suffix
  per `config.py:378`'s default shape). Probed
  `curl -sS -m 3 http://<addr>:1234/v1/models` — **reachable**,
  catalogue includes the project's pinned `qwen/qwen3.8-27b` among 16
  models. Not the blocking condition this run.
  **Correction (disclosed at T0-resume, prompt 264)**: this bullet and
  the equivalent line in `docs/llm-usage.md` row 167 originally printed
  the literal LAN address instead of `<addr>`, violating SEC-01/EC-04;
  fixed in place here. The `grep -c` verification itself also violated
  EC-01/SEC-01's "no command may print, copy, diff, grep, or otherwise
  inspect `.env`" — disclosed, not repeated at T0-resume. Neither
  violation is fixable in the originating commit (`5780562`) without a
  history rewrite, which is more destructive than the leak of a private
  LAN literal; both are corrected going forward only.
- **Override precondition**: the one permitted programmatic `data/` read —
  `SELECT COUNT(*) FROM bot_state WHERE key = 'provider_override' OR key
  LIKE 'model_override:%'` — printed **`2`** (non-zero).

### Outcome — blocked run (ERR-01 row 6)

A non-zero `bot_state` override count at T0 is a **blocked run**
(EC-04, ERR-01 row 6), the same class as an unreachable LM Studio — not a
stop route. Per REV-03's closing clause: "A blocked run (ERR-01 row 6) is
not a stop: only T0's prompt and skeleton are committed and the operator
re-issues `go`." No task proceeds past this check: gates 1–5 were **not**
run, no measurement was taken, no pin inventory was delegated, no test
file was written. `EC-01`/`NG-12` forbid any write to `data/` beyond the
one permitted read, so this run does not and cannot clear the override
rows itself — that is the operator's call (e.g. via the bot's own
`/model` command, or a decision that the override is intentional and the
precondition needs a disclosed amendment).

**Next step (resolved at T0-resume, prompt 264)**: the operator cleared
the override rows and re-issued `go docs/spec/spec-v1.11.1.md — LM Studio
at http://<addr>:1234`. The `.env` `LMSTUDIO_BASE_URL` edit already
applied at prompt 256 was idempotent and was overwritten cleanly by the
new address at prompt 264, not undone first.

### T0-resume (prompt 264) — a disclosed amendment to EC-04

Before any further command ran, the structural precondition was
re-checked against the current tree (which now includes prompt 256's own
commit, `5780562`): `git rev-parse v1.11.0^{commit}`, `git merge-base
--is-ancestor v1.11.0 HEAD`, `git describe --tags --abbrev=0` all still
match as recorded above. The sorted `git diff --name-only v1.11.0..HEAD`
now reads: `docs/handoff-v1.11.1.md`, `docs/llm-usage.md`,
`docs/prompts/255-v1111-spec-authoring.md`,
`docs/prompts/256-go-spec-v1.11.1.md`, `docs/reports/report-v1.11.1.md`,
`docs/spec/spec-v1.11.1.md` — **six paths, not EC-04's four**. The two
extras are T0's own artefacts, sanctioned by REV-03's blocked-run clause
("only T0's prompt and skeleton are committed") at the previous pass.
`git status --porcelain` and `git stash list` still empty; `test -f .env`
still exit 0.

This is literally ERR-01 row 14's trigger (a precondition mismatch, no
repair cycle, stop route before T0) — but REV-03's own text says a
blocked run "is not a stop: only T0's prompt and skeleton are committed
and the operator re-issues `go`", which structurally cannot be satisfied
without tripping row 14 on the very next `go`. The spec conflicts with
itself on this exact sequence — a spec ambiguity under EC-02's clause
("a larger drift or an absent mechanism is a spec ambiguity → the stop
route"). Surfaced to the operator via `AskUserQuestion` (three options:
resume T0 as a disclosed amendment, take the literal stop route, or
amend the spec first) before touching `.env` or running any gate.
**The operator chose "resume T0 as disclosed amendment."** Recorded here
per EC-02's disclosed-amendment clause: the six-path diff is treated as
the expected shape after a blocked-run commit, not a fresh precondition
mismatch, and T0 continues.

- **Override precondition, re-checked**: the same permitted `bot_state`
  read now prints **`0`**. Not blocking.
- **LM Studio, re-checked**: `<addr>` (new address from the re-issued
  `go` text), `sed -i` applied to `.env`'s `LMSTUDIO_BASE_URL` (no
  read/grep/print this time — see the correction bullet above), probed
  reachable, `qwen/qwen3.8-27b` in the catalogue among 16 models. Not
  blocking.

Neither condition blocks; T0 proceeds to gates 1–5.

**Prompt numbering note**: prompt 264 (this resume) was chosen as a
disclosed amendment — 256 already carries the blocked-pass commit under
the one-prompt-one-commit rule (not among the two ids, 262/263, exempted
for multiple commits), and 257–263 are reserved for T1–T6. 264 is the
first free slot in the spec's own "+1 per repair prompt" numbering
scheme (`spec-v1.11.1.md:1011-1012`), reused here for the same kind of
exceptional continuation. Consequence for later tasks: T6's own repair
cycles (`spec-v1.11.1.md:177-178`, "264 upward, +1 per repair prompt")
now start at **265**, not 264.

**Node-id-file timing, disclosed (no rerun)**: §10's T0 row says gates
1–5 run "before any T0-generated file exists"; `v1111-T0-nodeids.txt`
(this resume's own T0-generated file) already existed, untracked, in the
worktree when gates 4 and 5 ran (it was written immediately after the
floor measurement, ahead of gates 4–5 in this session's actual command
order). Neither gate reads or is affected by it — `bot.py --selftest`
and `--selftest-live` touch no `docs/` path — so this is a disclosed
timing deviation, not a result at risk; not repeated for T1–T6's own
gate runs.

### Gates 1–5 (T0-resume)

| gate | command | result |
| --- | --- | --- |
| 1 | `uv sync --locked` | resolved/checked 23–25 packages, exit 0 |
| 2 | `uv run --locked ruff check .` | all checks passed, exit 0 |
| 3 | `uv run --locked pytest` | `2381 passed, 1 skipped, 2 xfailed in 23.80s` (2384 total, matches the floor), exit 0 |
| 4 | `uv run --locked python bot.py --selftest` | `selftest: OK` |
| 5 | `uv run --locked python bot.py --selftest-live` | `config`/`db`/`docker (29.8.1)`/`telegram`/`embeddings`/`openrouter` all `OK`; `lmstudio` cleanly `SKIP` ("no route uses it") — a no-route skip, not a blocker (`AGENTS.md`'s gate-5 rule) |

### Measurements (T0-resume)

- **Floor**: `uv run --locked pytest --collect-only -q -o addopts="" |
  grep -c '::'` → **2384** — matches the authoring-time count exactly, no
  drift; `>= 2384` so the measured count is `floor = 2384`.
- **Node-id list**: the same collection, sorted, written to
  `docs/spec/task-briefs/v1111-T0-nodeids.txt` (2384 lines), measured
  before `tests/test_v1111_pin.py` existed.
- **`len(MUTATIONS)`**: `152` (`from devtools.mutation_check import
  MUTATIONS; print(len(MUTATIONS))`) — matches PIN-01's expected value.
- **`bot_state` override count**: `0` (re-confirmed above).

`[[VERIFY: the collected-test floor]]` (`spec-v1.11.1.md:91-96`):
measured **2384**, at or above 2384 → recorded as `floor` per the
decision rule; no drift from authoring time.

`[[VERIFY: the single-gate CLI form]]` (`spec-v1.11.1.md:791-796`):
`grep -n "add_argument\|--only\|--gate\|--profile" devtools/checks.py`
on the live tree still shows only `--profile` with the three
`pre-commit`/`pre-push`/`full` choices at `checks.py:1877`, no gate
selector — absent, confirming the decision rule's default: the standalone
`bash` block is the only way `gitleaks-tree` runs alone this task.

### Pin inventory (PIN-01, T0-resume)

Delegated to one subagent, brief `docs/spec/task-briefs/v1111-T0.md`.
Landed `docs/spec/task-briefs/v1111-T0-pin-inventory.md` (26 rows) and
`tests/test_v1111_pin.py`; `uv run --locked pytest
tests/test_v1111_pin.py -v` → `T-V1111-PIN-01`
(`test_t_v1111_pin_01_inventory_artefacts_exist`) and `T-V1111-PIN-02`
(`test_t_v1111_pin_02_no_v1110_test_renamed_or_listed`) both PASSED (`2
passed`); `ruff check`/`ruff format --check` clean on the new file;
`tests/test_v1110_inventory.py`'s `_SPEC_TEST_FUNCTIONS` (61 pairs)
confirmed unchanged (`git diff` empty).

**Disclosed amendment (EC-02's "pin found after T0" clause)**: the T6
`REQ-V1111-VER-01` rewrite family has **14** live sites, not the spec's
named eleven. Three found by the subagent's own tree-wide extension,
beyond `spec-v1.11.1.md:816`'s list:
`tests/test_v1101_gates.py:259` and `tests/test_v1103_gates.py:61` (the
same "`report_path` tracks the current release" family as the four
spec-named `report_path` sites), and `tests/test_v1104_version.py:108`
(`T-V1104-VER-02`'s own trailing live-version literal, already
self-documented at `:8-13` as a disclosed-amendment site bumped every
release). No cycle, no stop, no budget spent — flagged forward here for
whoever writes `v1111-T6.md`'s brief, per the inventory md's own leading
flag. Also noted (within EC-02's ±5-line tolerance, not an amendment):
three of the eleven spec-named sites land 1 line past the spec's own
citation on the live tree.

The delegated subagent also flagged a locale note (not a T0 blocker):
the frozen `v1111-T0-nodeids.txt` sorts clean under the ambient
`ru_RU.UTF-8` locale but not under `LC_ALL=C`; `devtools/checks.py` and
`devtools/mutation_check.py`'s gate subprocesses inherit the full
ambient environment (no `LANG`/`LC_*` scrubbing), so this stays
consistent across gates 1–6 on this machine — recorded for whoever runs
T6's `comm -23` check.

T0 complete: every EC-04/EC-02 acceptance item met, no stop route
triggered, one disclosed amendment (the EC-04 six-path resume) and one
forward-flagged disclosed amendment (the three extra VER-01 pin sites).

### Delegation record (EC-03, §10.1)

- T0 | delegated: no | to: commands only for the preconditions and gate 5
  probe, artefacts only for the prompt file and report skeleton (§5.1
  exemptions) | brief: — | map vs actual: matches §10.1's no/no cells for
  this partial commit (`5780562`); the yes cell (the pin inventory) was
  not reached — blocked before it (ERR-01 row 6)
- T0 | delegated: yes | to: general-purpose subagent, the pin inventory
  and `tests/test_v1111_pin.py` | brief: docs/spec/task-briefs/v1111-T0.md
  | map vs actual: matches §10.1's yes cell for the pin inventory
  (`07522f4`); the preconditions re-check/gates 1-5/measurements
  (commands only) and the prompt file/report update (artefacts only) are
  bundled into this same landing commit as disclosed orchestrator work,
  matching §10.1's no/no cells for those parts

### `gitleaks-tree` per-commit record (GATE-01, RPT-01)

| commit | exit | note |
| --- | --- | --- |
| `5780562` | 0 | recorded late, at T0-resume (prompt 264) — the "before another commit" window had already closed when `07522f4` landed; ran the spec's standalone block with `git archive 5780562` in place of `HEAD`, disclosed as a process deviation (no leak found, no compliance impact) |
| `07522f4` | 0 | `gitleaks-tree exit=0`, no leaks found |
| `ffdca15` | 0 | recorded at T1 (this commit) — the same lag pattern as 5780562's late record |

## T1 — OUT-01, OUT-02: the plain fallback narrowed to HTTP 400, three docstrings

Delegated to one subagent, brief `docs/spec/task-briefs/v1111-T1.md`.

### OUT-01 — `TelegramError.status`, `call`'s status-tagging, the 400-only predicate

`TelegramError` (`bot.py:176-190`) gained a keyword field
`status: int | None = None`, stored as `self.status`. `TelegramClient.call`
(`bot.py:221-274`) now sets `status=status` on every raise that follows a
response — the 401/404 fatal branch, the 429 branch, the other non-200
branch, the non-JSON branch, and the `data.get("ok") is not True` branch —
and leaves it `None` on the transport raise (the only raise before a
response exists). `_call_with_retry` (`bot.py:277-292` on this tree)
confirmed byte-identical to `2431034`
(`git show 2431034:bot.py | sed -n '265,280p'` diffed against the live
range, no hunk). `send_pre` and `edit_pre` (`bot.py:2554-2598`) switched
their fallback predicate from `if exc.fatal:` to `if exc.status != 400:`
— 401/404 never equal 400, so the old fatal check is subsumed and was
replaced rather than kept alongside the new one; all fallback attempts
still omit `parse_mode`, at-most-once semantics and the `_pre_text` order
are unchanged.

### OUT-02 — three docstrings

(a) `send_pre`'s docstring replaced verbatim by the spec `:278-291` block
(narrowed to the `status == 400` classification, no line-range reference).
`edit_pre`'s docstring: "the same fatal-skips-the-fallback rule … on a
non-fatal table-path failure" collapsed to "the same 400-only rule",
keeping the `edit_message_text` mechanics parenthetical (no tags, no
`parse_mode`, no `reply_markup`) that follows it. (b) `tables.fit_lines`'s
docstring (`tables.py:134-139`) drops the `` `_fit` ``/`bot.py:1190-1197`
parenthetical; it now reads "… appended until it fits -- over lines, never
a hard slice inside a line." (c) `IngestJob`'s docstring (`bot.py:1926-`)
first sentence replaced with the `cancel.is_set()` happens-before waiver
text (the v1.11.0 T7 review's finding-2 waiver); the `monotonic` paragraph
and every read/write site (`bot.py:1959`, `:1969`, `:2123`, `:2047`,
`:2229`, all shifted by this task's own insertions but otherwise
untouched) are unchanged.

### Test-first (EC-02)

`tests/test_v1111_out.py` (5 tests) written before any source change. A
temporary `git stash push -- bot.py tables.py` reverted the source edits
to confirm each test's failure reason against the pre-change tree, then
`git stash pop` restored them:

| test | pre-change result | reason |
| --- | --- | --- |
| `test_t_v1111_out_01_status_set_from_response` | FAIL | `AttributeError: 'TelegramError' object has no attribute 'status'` |
| `test_t_v1111_out_02_fallback_on_400_send_and_edit` | pass (incidental) | none of its sub-cases (400/500/transport, never 401/404) are `fatal`, so the old `exc.fatal` predicate and the new `exc.status != 400` predicate coincide on every case this test exercises |
| `test_t_v1111_out_03_no_fallback_on_429_after_budget` | FAIL | `assert 6 == 3` — the old `exc.fatal` check let a budget-exhausted 429 fall through to a second logical fallback (3 HTML + 3 plain requests) instead of skipping it |
| `test_t_v1111_out_04_no_fallback_on_5xx_or_transport` | FAIL | `assert 2 == 1` — the old check let a bare 5xx fall through to a plain resend instead of skipping it |
| `test_t_v1111_out_05_docstrings_current` | FAIL | `assert 'status' in '...'` — the pre-change `send_pre` docstring has neither `status` nor `400`, and still names `bot.py:154-198` |

All 5 green after implementation:
`uv run --locked pytest tests/test_v1111_out.py -v` → `5 passed`.

### `T-V1110-OUT-05` regression check

`tests/test_v1110_out.py:359-422`'s `test_t_v1110_out_05_plain_fallback_once_on_400`
(the four `a`–`d` sub-cases: 400→200 succeeds, a 4097-unit body's fallback
carries the fitted text, two 400s return `None` after exactly two
requests, a fatal 401 skips the fallback after exactly one request) passes
**unamended** — the new `status`-based predicate agrees with the old
`fatal`-based one on every one of these four cases, since none of them mix
a non-fatal non-400 status with the fallback path. Full
`tests/test_v1110_out.py` suite: `uv run --locked pytest
tests/test_v1110_out.py -q` → all green (no failures).

### Gates 1–4 and `lint-docs` (T1)

| gate | command | result |
| --- | --- | --- |
| 1 | `uv sync --locked` | `Resolved 25 packages`, `Checked 23 packages`, exit 0 |
| 2 | `uv run --locked ruff check .` | `All checks passed!`, exit 0 |
| 3 | `uv run --locked pytest` | `2388 passed, 1 skipped, 2 xfailed` (2391 collected — the 2384 T0 floor plus T0's own 2 `test_v1111_pin.py` functions plus this task's 5 new `test_v1111_out.py` functions), exit 0 |
| 4 | `uv run --locked python bot.py --selftest` | `selftest: OK` |
| — | `uv run --locked python devtools/checks.py lint-docs` | `[PASS] lint-docs: all prompts and the report ledger row pass` |

### Delegation record (EC-03, §10.1)

- T1 | delegated: yes | to: general-purpose subagent, OUT-01/OUT-02 (`TelegramError.status`, the `call` raises, the 400-only predicate, the three docstrings) and `tests/test_v1111_out.py` | brief: docs/spec/task-briefs/v1111-T1.md | map vs actual: matches §10.1's yes cell for T1 -- touched `bot.py:176-190` (`TelegramError`), `:221-274` (`call`, status-tagged raises), `_call_with_retry` at `:277-292` read only and confirmed byte-unchanged, `:1926-1942` (`IngestJob` docstring), `:2554-2598` (`send_pre`/`edit_pre`); `tables.py:134-139` (`fit_lines` docstring); `tests/test_v1110_out.py:94-95`, `:359-422` read only, unamended; `tests/test_v1111_out.py` created (5 functions) -- the reading map's file/line ranges match, shifted only by this task's own earlier insertions within `bot.py`

## T2 — not reached

## T3 — not reached

## T4 — not reached

## T5 — not reached

## T6 — not reached

## Operator inputs

- **Run configuration (EC-04), source `.env`** (operator-prepared ahead of
  `go`, opened only by the one permitted `sed -i` for `LMSTUDIO_BASE_URL`
  and never otherwise read/printed): `LMSTUDIO_BASE_URL` set to
  `http://<addr>:1234/v1` at T0 (prompt 256), reset to a new `<addr>` at
  T0-resume (prompt 264); all other `.env` values unchanged from v1.11.0.
- **`go` text (prompt 256)**: `go docs/spec/spec-v1.11.1.md — LM Studio at
  http://<addr>:1234`.
- **`go` text (re-issued, prompt 264)**: `go docs/spec/spec-v1.11.1.md —
  LM Studio at http://<addr>:1234` (a different LAN address than prompt
  256's — the floating-IP GPU box moved between the two runs).

## Gate-8 attempt log

| task | attempt | exit | outcome |
| --- | --- | --- | --- |
| not reached | | | |

## `docs/reports/tg-post-v1.11.1.md`

Not written yet — written at T6 (or at the stop route, if triggered).

## Ledger row (paste into `economics.md`)

Not reached — filled at T6. T0 completed at prompt 264 (resumed after
the blocked pass at prompt 256, `bot_state` override count now 0).
