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

- T0 | delegated: no | to: commands only for the preconditions and gate 5 probe, artefacts only for the prompt file and report skeleton (§5.1 exemptions) | brief: — | map vs actual: matches §10.1's no/no cells for this partial commit (`5780562`); the yes cell (the pin inventory) was not reached — blocked before it (ERR-01 row 6)
- T0 | delegated: yes | to: general-purpose subagent, the pin inventory and `tests/test_v1111_pin.py` | brief: docs/spec/task-briefs/v1111-T0.md | map vs actual: matches §10.1's yes cell for the pin inventory (`07522f4`); the preconditions re-check/gates 1-5/measurements (commands only) and the prompt file/report update (artefacts only) are bundled into this same landing commit as disclosed orchestrator work, matching §10.1's no/no cells for those parts

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
(`bot.py:221-272`) now sets `status=status` on every raise that follows a
response — the 401/404 fatal branch, the 429 branch, the other non-200
branch, the non-JSON branch, and the `data.get("ok") is not True` branch —
and leaves it `None` on the transport raise (the only raise before a
response exists). `_call_with_retry` (`bot.py:274-288` on this tree)
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

### Test-first (EC-02) — disclosed deviation

**Not genuinely test-first.** The subagent's own post-commit self-check
(via `advisor`) found the actual authoring order was: read the spec →
edit `bot.py`/`tables.py` → write `tests/test_v1111_out.py` against the
already-changed tree → `git stash push -- bot.py tables.py` to revert the
source edits and confirm each test's failure reason against the
pre-change tree → `git stash pop` to restore them. The red-check below is
still valid evidence the tests discriminate the old predicate from the
new one; only the *authoring* order was implementation-first, not
test-first — the same category of deviation `docs/llm-usage.md` row 155
records for v1.11.0 T5 ("disclosed plainly, not described as partial
compliance"), not a carve-out case (T1 is not among EC-02's four named
carve-out ids: `T-V1111-VER-02`, `-PIN-01`, `-PIN-02`, `-DOC-03`):

| test | pre-change result | reason |
| --- | --- | --- |
| `test_t_v1111_out_01_status_set_from_response` | FAIL | `AttributeError: 'TelegramError' object has no attribute 'status'` |
| `test_t_v1111_out_02_fallback_on_400_send_and_edit` | pass (incidental) | none of its sub-cases (400/500/transport, never 401/404) are `fatal`, so the old `exc.fatal` predicate and the new `exc.status != 400` predicate coincide on every case this test exercises |
| `test_t_v1111_out_03_no_fallback_on_429_after_budget` | FAIL | `assert 6 == 3` — the old `exc.fatal` check let a budget-exhausted 429 fall through to a second logical fallback (3 HTML + 3 plain requests) instead of skipping it |
| `test_t_v1111_out_04_no_fallback_on_5xx_or_transport` | FAIL | `assert 2 == 1` — the old check let a bare 5xx fall through to a plain resend instead of skipping it |
| `test_t_v1111_out_05_docstrings_current` | FAIL | `assert 'status' in '...'` — the pre-change `send_pre` docstring has neither `status` nor `400`, and still names `bot.py:154-198` |

All 5 green after implementation:
`uv run --locked pytest tests/test_v1111_out.py -v` → `5 passed`.

**Disclosed gap**: `test_t_v1111_out_02_fallback_on_400_send_and_edit`
passed on the pre-change tree too — not because it is structural (it is
not one of EC-02's four named carve-out ids), but because none of its
sub-cases were designed to discriminate the old `exc.fatal` predicate
from the new `exc.status != 400` one (both agree whenever the case is
400/500/transport and never 401/404). Accepted as-is for this release —
the other four tests in the same module do discriminate the predicates,
and OUT-02's own fallback-shape assertions (request counts, `parse_mode`
omission, the fitted text) are still genuine coverage — but flagged here
rather than silently left as an apparent (and false) carve-out
compliance.

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

### `gitleaks-tree` per-commit record (GATE-01, RPT-01)

| commit | exit | note |
| --- | --- | --- |
| `7b910fd` | 0 | `gitleaks-tree exit=0`, no leaks found |
| `bf9f2ec` | 0 | recorded at T2 (this commit) -- the T1 follow-up's own docs-only commit, already scanned by the orchestrator before T2 started; T0's table shape reused here since T1 previously carried only the single-line form above |
| `ebc2822` | 0 | recorded at T3 (this commit) -- T2's own landing commit, already scanned by the orchestrator before T3 started, same lag pattern as `5780562`/`bf9f2ec` |

### Delegation record (EC-03, §10.1)

- T1 | delegated: yes | to: general-purpose subagent, OUT-01/OUT-02 (`TelegramError.status`, the `call` raises, the 400-only predicate, the three docstrings) and `tests/test_v1111_out.py` | brief: docs/spec/task-briefs/v1111-T1.md | map vs actual: matches §10.1's yes cell for T1 -- touched `bot.py:176-190` (`TelegramError`), `:221-272` (`call`, status-tagged raises), `_call_with_retry` at `:274-288` read only and confirmed byte-unchanged, `:1926-1942` (`IngestJob` docstring), `:2554-2598` (`send_pre`/`edit_pre`); `tables.py:134-139` (`fit_lines` docstring); `tests/test_v1110_out.py:94-95`, `:359-422` read only, unamended; `tests/test_v1111_out.py` created (5 functions) -- the reading map's file/line ranges match, shifted only by this task's own earlier insertions within `bot.py`; not genuinely test-first, disclosed above

## T2 — TAB-01…06: table widths, the /sessions empty state, DOC_LIMIT_REPLY, one batch constant

Delegated to one subagent, brief `docs/spec/task-briefs/v1111-T2.md`.

### Amendment table (spec `:315-321`, NG-07)

Amendments by reference to `spec-v1.11.0.md`, both landed by this task:

| spec site | was | is | id |
|---|---|---|---|
| `spec-v1.11.0.md:451-453` (DOC-01, `/documents`) | `#` 3, `file` 24 (72) | `#` 5, `file` 22 (72) | TAB-01 |
| `spec-v1.11.0.md:658-659` (MOD-01, `/model`) | `[12, 44]` (58) | `[16, 40]` (58) | TAB-02 |

### TAB-01/-02 -- /documents' `#` column widens, `file` narrows

`bot.py:2391`'s `max_width` for `_handle_documents`' table became `[5, 22,
4, 8, 6, 5, 10]` (sum 60 + 6 separators of 2 units each = 72 <= 72; was
`[3, 24, 4, 8, 6, 5, 10]`). A 5-digit id (`12345`) now renders whole in the `#` column; a
40-character filename now truncates to 21 `f`s + `…` (22 units), not 23 +
`…` (24 units). `T-V1111-TAB-01`'s round trip also drives `/delete
#12345` through `process` -- the reply is `Deleted #12345.` (it echoes
the `#<id>` argument, `_handle_delete`'s existing, unchanged mechanism; it
does not print the filename `third.txt`, which is what "the reply names
the file" in the spec's own test-table wording turns out to mean in
practice for the `#<id>` form, as distinct from the `<filename>` form's
`Deleted <filename>.`). README's fenced `/documents` sample
(`README.md:215-233` region, was `:213-232` pre-change) regenerated from
`tables.render_table` over the same two-row fixture `T-V1110-DOC-01`
uses, byte-equal to the live function's own output (`T-V1111-TAB-02`
computes and compares both sides directly, not a hand-copied literal);
the sentence at the old `:217` (now `README.md:219`) changed from "cut to
23 UTF-16 units" to "cut to 21 UTF-16 units". Also fixed, within the T2
reading map's `README.md:150-155` region but not separately named by any
`REQ-V1111-TAB-*` id: the `/sessions` prose at `README.md:147-151`
claimed `/documents`' `#` column has "the same property" (truncates past
9999) as `/sessions`' own 4-unit `#`/`msgs` columns -- true before this
task, false after TAB-01 widened `/documents`' `#` column to 5 units;
reworded to state the two columns now differ, unwidened `/sessions` still
truncating past 9999, `/documents` only past 99999 (no test pins the old
sentence -- checked by grep before the edit).

### TAB-02 (spec numbering) -- /model's status label never truncates

`bot.py:1555`'s `max_width` for `_model_status_table` became `[16, 40]`
(was `[12, 44]`); `openrouter model` (16 units, the widest label) now
renders whole in every case, since the field column no longer clips it.
The docstring at `bot.py:1528-1534` was rewritten to describe the new
widths and drop the old "truncates with an ellipsis" claim about the
label, which is no longer true. README carries no status-table sample
(unchanged, per the spec).

### TAB-03 -- /sessions with no sessions replies on the plain path

A new constant, `bot.py:141`: `SESSIONS_EMPTY_REPLY = "No sessions yet.
Send me a message to start one."`, placed next to `SESSIONS_LIST_LIMIT`.
`_handle_sessions` (`bot.py:2463-2472`) gained `if not rows: _send(tg,
chat_id, [SESSIONS_EMPTY_REPLY]); return` right after computing `rows`,
before `total`/`table` -- the mirror of `_handle_documents`' own empty
branch. With rows present, nothing else in the function changed. README's
wording at the old `:153-154` (now `README.md:154-156`) ("A caller with
no sessions yet sees the header and rule only.") became "... gets a plain
reply instead: `No sessions yet. Send me a message to start one.`";
`## Error behaviour` (heading `README.md:954`) gained a new row for this
case at `README.md:974`.

### TAB-04 -- DOC_LIMIT_REPLY names both /delete forms

`bot.py:109`: `DOC_LIMIT_REPLY` became one literal, `"Limit of 20
documents reached. Use /delete <filename> or /delete #<id>."` (was "...
Use /delete <filename>."). Both senders are mechanically unchanged --
`bot.py:2306`, `_handle_document`'s pre-admission count check (a plain
`_send`), and `bot.py:2141-2144`, the worker's `except
documents.DocumentLimitExceededError` branch (delivered through
`_document_error_ending`, `bot.py:1878-1886`, as an edit of the existing
status message). `T-V1111-TAB-05` drives both cases through
`process_update`: (a) a caller already at 20 documents uploading a 21st
is refused before any enqueue, `tg.sent == [(USER_ID,
bot.DOC_LIMIT_REPLY)]`, no status message ever created; (b) a caller
admitted at 19 documents, whose 20th document is inserted directly via
`storage.add_document` (this task's own out-of-band mechanism for the
race the spec describes -- no real thread, a plain call between admission
and `worker.run_one`) before the job's own commit, ends with
`tg.edited[-1][2] == bot.DOC_LIMIT_REPLY` through the
`DocumentLimitExceededError` branch. Both cases: no document, chunk or
vector row inserted for the refused upload, `document_count` unchanged
by that upload. README's row (the old `:993`, now `README.md:995`)
carries the new literal verbatim; `tests/test_v190_agents.py:300`'s
needle rewritten to match
(`tests/test_v1110_pin.py:114`'s prefix, `DELETE_USAGE_REPLY`'s, checked
unaffected -- it is a different string).

### TAB-05 (spec numbering; test id T-V1111-TAB-06) -- one embedding batch constant

`documents.py:386`'s `EMBED_BATCH_SIZE = 32` removed; `documents.py:31`
gains `from llm.embeddings import BATCH_SIZE` (no cycle --
`llm/embeddings.py`'s own imports among project modules are `tracing` and
`config` only). The loop at `documents.py:551-559` uses `BATCH_SIZE` in
the five places `EMBED_BATCH_SIZE` stood (`:552` twice, `:554`, `:555`,
`:558`); the outer loop, `total_batches`, `batch_no` and the per-batch
`_check_budget` checkpoint are otherwise unchanged, so the progress and
cancel cadence stays at 32. `T-V1111-TAB-06` proves the HTTP-call
invariant two ways: a size-recording `FakeEmbedder` through
`IngestWorker.run_one` over 65 chunks saw batch sizes `[32, 32, 1]` and
the progress edits `1/3 … 3/3`; a real `EmbeddingsClient` over
`httpx.MockTransport`, fed the same 65 chunks through
`documents.index_document` directly, made exactly three embedding
requests with body `input` sizes `[32, 32, 1]`, the same progress
sequence alongside. README's paragraph (`README.md:532-548` region)
rewritten per spec `:389-393`'s text, naming `llm.embeddings.BATCH_SIZE`
as the one constant, not two.

### Pin rewrites (the five T2 rows from the pin inventory)

All five sites the inventory catalogued for T2 were rewritten in place,
intent preserved, no new pin sites found beyond that list:

- `tests/test_v1110_doc.py:200-202` -- `"f" * 23 + "…"` / `== 24` ->
  `"f" * 21 + "…"` / `== 22`.
- `tests/test_v1110_doc.py:378` -- `monkeypatch.setattr(documents,
  "EMBED_BATCH_SIZE", 1)` -> `"BATCH_SIZE"` (the adjacent comment prose
  also updated, since it named the old constant).
- `tests/test_v1110_ing.py:548` -- same rewrite, same reason.
- `tests/test_v190_agents.py:300` -- the `DOC_LIMIT_REPLY` needle
  rewritten to the new `/delete #<id>` form.
- `tests/test_v1110_ver.py:135` -- rewritten to assert
  `"documents.EMBED_BATCH_SIZE"` **absent** from README (it used to
  assert presence); `:136` (`"llm.embeddings.BATCH_SIZE"` present)
  unchanged.

### Test-first (EC-02)

**Genuinely test-first this time.** `tests/test_v1111_tab.py` (six
functions) was written before any of the five source edits above, then
red-checked against the pre-change tree directly (no `git stash` needed
-- the source edits had not been made yet):

| test | pre-change result | reason |
| --- | --- | --- |
| `test_t_v1111_tab_01_documents_id_width_five_round_trip` | FAIL | `assert '12345' in body` -- the old `#` column (`max_width` 3) rendered the id as `12…` |
| `test_t_v1111_tab_02_readme_documents_sample_byte_equal` | FAIL | `assert 'cut to 21 UTF-16 units' in readme_text` -- README still read "23" |
| `test_t_v1111_tab_03_model_status_label_whole` | FAIL | `assert 'openrouter model' in inner` -- the old `field` column (`max_width` 12) truncated it to `openrouter …` |
| `test_t_v1111_tab_04_sessions_empty_plain` | FAIL | `AttributeError: module 'bot' has no attribute 'SESSIONS_EMPTY_REPLY'` |
| `test_t_v1111_tab_05_doc_limit_reply_names_both_forms` | FAIL | `assert bot.DOC_LIMIT_REPLY == "...or /delete #<id>."` -- the live constant still read the single-form string |
| `test_t_v1111_tab_06_single_batch_constant` | FAIL | `assert not hasattr(documents, "EMBED_BATCH_SIZE")` -- the attribute still existed |

All 6 green after implementation: `uv run --locked pytest
tests/test_v1111_tab.py -v` -> `6 passed`. Every failure is for the
targeted reason (no incidental pass, unlike T1's own `OUT-02`
disclosure) -- none of these six tests is among EC-02's four named
carve-out ids (`T-V1111-VER-02`, `-PIN-01`, `-PIN-02`, `-DOC-03`), and
none needed to be, since every one of them failed red for the right
reason pre-change.

### Gates 1-4 and `lint-docs` (T2)

| gate | command | result |
| --- | --- | --- |
| 1 | `uv sync --locked` | `Resolved 25 packages`, `Checked 23 packages`, exit 0 |
| 2 | `uv run --locked ruff check .` | `All checks passed!`, exit 0 |
| 3 | `uv run --locked pytest` | `2394 passed, 1 skipped, 2 xfailed in 28.40s` (2397 collected -- the 2391 T1 count plus this task's 6 new `test_v1111_tab.py` functions), exit 0 |
| 4 | `uv run --locked python bot.py --selftest` | `selftest: OK` |
| -- | `uv run --locked python devtools/checks.py lint-docs` | `[PASS] lint-docs: all prompts and the report ledger row pass` |

`gitleaks-tree` on this task's own commit: not run by this subagent (the
orchestrator runs the standalone block after the commit lands, per the
brief); recorded in a later task's follow-up once it has, matching T0/T1's
own lag pattern.

### Delegation record (EC-03, §10.1)

- T2 | delegated: yes | to: general-purpose subagent, TAB-01…05 (table widths, the /sessions empty state, DOC_LIMIT_REPLY, one batch constant) and tests/test_v1111_tab.py | brief: docs/spec/task-briefs/v1111-T2.md | map vs actual: matches §10.1's yes cell for T2 -- touched bot.py:109, :141, :1528-1534, :1555, :2391, :2463-2472; documents.py:31, :386 (removed), :551-559; README.md:147-151 (the /sessions "same property" sentence, in the reading map's :150-155 region but not separately named by any REQ-V1111-TAB-* id), :154-156, :215-233, :532-548, :954-1004 region, plus the amendment table in this report; tests/test_v1110_doc.py:200-202, :378; tests/test_v1110_ing.py:548; tests/test_v190_agents.py:300; tests/test_v1110_ver.py:135; tests/test_v1111_tab.py created (6 functions) -- the reading map's file/line ranges match, no unplanned file touched

## T3 — TST-01…08: dispatch-level error-row tests, the secrets-registry restore fixture

Delegated to one subagent, brief `docs/spec/task-briefs/v1111-T3.md`.

### Prompt-numbering disclosure (see also the commit body)

The brief's static per-task map (§10, originally `256=T0, 257=T1,
258=T2, 259=T3, 260+261=T4, 262=T5, 263=T6`) broke once T0's
resume/follow-up consumed `264`/`265` out of order and T1's follow-up
took `258`. This task's own prompt is **260** (confirmed free and used
here). Flagged forward: **T4 now takes 261+262** for its two commits
(was 260+261, matching spec `:1022`'s own table), **T5 takes 263** (was
262), and **T6 must skip 264/265** (already used by the T0
resume/follow-up) **and take 266** (was 263) -- whoever writes
`v1111-T4.md`'s brief should use 261/262, and `v1111-T6.md`'s brief
should use 266.

### TST-01 -- six new dispatch-level tests, v1.11.0 ERR-01 rows 11-16

New module `tests/test_v1111_tst.py`; the frozen
`tests/test_v1110_err.py::test_t_v1110_err_01_error_matrix_strings` stays
byte-unchanged, per the spec's own drafter's choice
(`spec-v1.11.1.md:404-426`). Each of the six tests imports
`process`/`text_update`/`make_cfg`/`new_conn`/`_error_section` (all
within `tests/test_v1110_err.py:50-116`) and `USER_ID` (that file's
`:29`, outside that range -- not retyping any of them either way) rather
than retyping them, and drives `bot.process_update` with a hand-written
update dict (row 15 gets its own `_callback_update` builder, local to
the new module, since `text_update` only builds `message` updates): row
11 `/session` bare -> `SESSION_USAGE_REPLY`; row 12 `/session 999999`,
with the caller's own active session seeded first via
`storage.get_or_create_active_conversation` -> `"No session #999999."`,
`storage.active_conversation_id` still that seeded id (seeding matters:
`activate_conversation` deactivates the current row *before*
conditionally reactivating the target and only rolls back on a
missing/foreign id, so an unseeded, already-`None` caller would pass
this assertion even if that rollback were broken -- confirmed by
temporarily breaking the rollback in `storage.py` and watching this test
fail, then restoring it unmodified); row 13 `/delete #999` (no documents
at all) -> `"No document named #999."`, `document_count` unchanged (0
before and after); row 14 `/delete` bare -> `DELETE_USAGE_REPLY`; row 15
a `callback_query` with data `"zzz"` -> `CALLBACK_EXPIRED_REPLY` read
from `FakeTelegram.callback_answers[-1]["text"]`, nothing sent or
edited, the polling cursor (`storage.get_state(conn, "last_update_id")`)
still advances; row 16 two triggers, `/model openrouter nope` (a
configured provider -- `openrouter_api_key="k"`, the same
non-credential-shaped placeholder `tests/test_v160_bench.py:464` already
uses for this field, not a `sk-`-prefixed key-shaped literal -- unknown
model) -> `"Unknown model for openrouter; see /model"`, `/model a b c`
(three arguments) -> `MODEL_USAGE_REPLY`, neither writes a `bot_state`
row (`PROVIDER_OVERRIDE_KEY` or `model_override:*`). Every reply is
asserted byte-equal against the row's own string; every row's string
(the exact one `bot.py` emits, or its generic
`<id>`/`<argument>`/`\|`-escaped template where the reply is dynamic) is
also asserted present in `_error_section()`.

Four stale `bot.py` line citations found and corrected in this
report/prompt (the spec's own table at `:417-424` cites an earlier
tree): `SESSION_USAGE_REPLY` is at `bot.py:142`, not `:141`;
`_no_session_reply`'s f-string is at `bot.py:2497`, not `:2477`;
`_no_document_named_reply`'s f-string is at `bot.py:2426`, not `:2411`;
the row-16 `f"Unknown model for {choice}; see /model"` site is at
`bot.py:1646`, not `:1636`. (`DELETE_USAGE_REPLY` `:129`,
`CALLBACK_EXPIRED_REPLY` `:92` and `MODEL_USAGE_REPLY` `:88` all
confirmed exact, no drift.) Also stale: spec sec.3.3's own sentence
citing README's rows 14 and 16 "in the `\|`-escaped form of `:975,
:978`" -- the two rows are now at `README.md:977` and `:980` (T2
inserted two new `## Error behaviour` rows, TAB-03/TAB-04, ahead of
them).

### TST-02 -- `secrets_registry_snapshot()` + the autouse `restore_secrets_registry` fixture

The spec's own `[[VERIFY]]` grep (`grep -n "_secrets" config.py
tests/conftest.py tests/test_v11_patch.py`) run first, per the brief:
the registry is exactly what spec `:428-448` names -- the module-level
set `config._secrets` (`config.py:98`), touched only through
`register_secret` (`config.py:230-233`), `redact` (`:236-239`),
`max_secret_length` (`:292-296`) and `strip_secret_fragment`
(`:299-305`); no rename, no rebind found. `cited -> actual`: none --
every one of these citations matched the live tree exactly, so the
decision rule at spec `:444-448` was not invoked;
`tests/test_v11_patch.py:50-57`'s own pre-existing clear/restore fixture
(a sibling of the new one, not replaced) confirmed unaffected.

`tests/conftest.py` gains `secrets_registry_snapshot()` (a
`contextlib.contextmanager`: `saved = set(config_module._secrets)`,
yield, `config_module._secrets.clear();
config_module._secrets.update(saved)` -- mutating the same set object,
never rebinding `_secrets`) and the autouse `restore_secrets_registry`
fixture that wraps every test in it, placed immediately after
`no_real_bind` (`tests/conftest.py:37 ±5` pre-edit per the brief,
`:38-50` post-edit; the new lines land at `:53-77`, one `import
contextlib` line added at the top).

`T-V1111-TST-07` proves the fixture itself, not only the context
manager: a two-test module written to `tmp_path` (test A registers
`"VALUE-abcdefgh12"` -- the repo's existing fake sentinel, the same
literal `tests/test_v1103_exec.py:176` and others already use -- and
never cleans up; test B asserts it is absent from `config._secrets` and
that the registry `is` the same object captured at the nested module's
own import time) plus a `tmp_path/conftest.py` containing exactly `from
tests.conftest import restore_secrets_registry`, never calling
`secrets_registry_snapshot()` itself. `[[VERIFY :456-464]]`: the plain
import path worked on the first try (`tests/__init__.py` exists;
`python -m pytest`'s cwd -- the repo root, passed explicitly as
`subprocess.run`'s `cwd=` -- lands on `sys.path[0]`); the nested run
collected and passed both tests. Neither the `pytest_plugins =
("tests.conftest",)` fallback nor the permanent `xdist_group`-marked
pair was needed; no disclosed amendment on this axis. The direct
context-manager checks stay as an additional assertion in the same
test: inside `secrets_registry_snapshot()`,
`register_secret("VALUE-abcdefgh12")` makes `redact` mask it; after the
block, the sentinel is gone, `redact` is a no-op again, and
`config._secrets is registry_before`.

`T-V1111-TST-07` itself was also shown genuinely red, for the exact
case spec `:449` names ("a fixture that is ... not `autouse=True` fails
the nested run"): `restore_secrets_registry`'s decorator was temporarily
changed from `@pytest.fixture(autouse=True)` to `@pytest.fixture` (no
other line touched), and running only
`tests/test_v1111_tst.py::test_t_v1111_tst_07_secrets_registry_restored
-o addopts=""` failed as `assert result.returncode == 0` with the
captured nested output showing `test_b_sees_restored_registry` itself
failing (`AssertionError: assert 'VALUE-abcdefgh12' not in
{'VALUE-abcdefgh12'}`, `1 failed, 1 passed`) -- the sentinel leaked from
nested test A into nested test B because the fixture was never applied
without `autouse`. The decorator was then restored to
`@pytest.fixture(autouse=True)` (confirmed byte-identical to the
pre-probe version by `git diff tests/conftest.py`) and the full module
re-run green (`7 passed`).

### Test-first (EC-02)

TST-01's six row tests exercise dispatch behaviour v1.11.0 already
shipped (T0/T1/T2 touched table widths and the outbound fallback, never
these six strings or code paths) -- there is no source change for them
to red-check against, so they are not comparable to T2's genuinely
test-first TAB tests or to T1's `T-V1111-OUT-02` carve-out disclosure
(both had a source edit to be red against; these do not). Each was
confirmed to pass once written.

TST-02/-07 are genuine new code (the fixture did not exist before), and
here the ordering is **not** as clean as T2's: `tests/conftest.py`'s
`secrets_registry_snapshot()`/`restore_secrets_registry` were written
before `tests/test_v1111_tst.py`, after a manual prototype (outside any
test file, in a scratch `/tmp` directory) confirmed the nested-run
mechanics would work once the fixture existed. This is disclosed rather
than overstated (T1's mistake), and backed by three checks rather than
asserted: (1) the manual `/tmp` prototype, run *before* touching
`tests/conftest.py`, hit `ImportError: cannot import name
'restore_secrets_registry' from 'tests.conftest'` when its own
`tmp_path/conftest.py` tried to import a fixture that did not exist yet
-- the same mechanism `T-V1111-TST-07` later encodes as a real test; (2)
after both files were written and all seven tests passed on the first
run, `tests/conftest.py`'s new lines were `git stash`ed and
`tests/test_v1111_tst.py` re-run -- collection itself failed with a
*different* error, `ImportError: cannot import name
'secrets_registry_snapshot' from 'tests.conftest'` (this one from the
outer module's own top-level import, `tests/test_v1111_tst.py:31`, not
from the nested `tmp_path/conftest.py` mechanism check (1) exercised)
-- confirming the whole module depends on the fixture existing; the
stash was then popped and all seven passed again; (3) after both files
were finished, `restore_secrets_registry`'s `autouse=True` was removed
and restored as its own dedicated check (above, under TST-02) -- this
one **is** genuine red/green against the finished tree, for the specific
failure mode spec `:449` names. None of the three is genuine
file-authorship-order test-first for TST-02/-07 as a whole; disclosed as
the closest available substitute, honestly short of T2's standard on
this one item.

### TST-08 -- by command

(1) `uv run --locked pytest
"tests/test_v1103_red_team.py::test_t_v1103_rt_06_leak_shape_fixture_still_fails_on_clause_c_only"
-o addopts=""` alone -> `1 passed in 0.24s`.
(2) `uv run --locked pytest -p xdist -n 4 -o addopts="" -q`, twice ->
`2401 passed, 1 skipped, 2 xfailed in 35.85s`, then `2401 passed, 1
skipped, 2 xfailed in 44.39s`.

### Gates 1-4 and `lint-docs` (T3)

| gate | command | result |
| --- | --- | --- |
| 1 | `uv sync --locked` | `Resolved 25 packages`, `Checked 23 packages`, exit 0 |
| 2 | `uv run --locked ruff check .` | `All checks passed!`, exit 0 |
| 3 | `uv run --locked pytest` | `2401 passed, 1 skipped, 2 xfailed in 25.01s` (2404 collected -- the 2397 T2 count plus this task's 7 new `test_v1111_tst.py` functions), exit 0 |
| 4 | `uv run --locked python bot.py --selftest` | `selftest: OK` |
| -- | `uv run --locked python devtools/checks.py lint-docs` | `[PASS] lint-docs: all prompts and the report ledger row pass` |

`ruff format --check tests/test_v1111_tst.py tests/conftest.py` also
run (not a named gate, but flagged during the pre-commit self-check
below): `2 files already formatted`, after one triple-quote style fix
(`'''` -> `"""` for the nested-module source string, no content change).

`gitleaks-tree` on this task's own commit: not run by this subagent (the
orchestrator runs the standalone block after the commit lands, per the
brief); recorded in a later task's follow-up once it has, same lag
pattern as T0/T1/T2.

### Pre-commit self-check (`advisor`)

Called before committing, per the brief. It caught six real gaps, all
fixed before commit: (1) the prompt-renumbering disclosure the brief
asked for was missing from both this section and the usage row -- added
above and in `docs/llm-usage.md` row 173; (2) row 12's test could not
actually fail on a broken rollback (`None` before and after would pass
even with `activate_conversation`'s rollback removed) -- fixed by
seeding an active session first, then verified red by temporarily
breaking the rollback in `storage.py` and restoring it, as described
under TST-01 above; (3) `openrouter_api_key="sk-or-sentinel-key-value"`
in the row-16 test has the shape of a real API key, against the brief's
own constraint -- replaced with `"k"`, the non-credential-shaped
placeholder `tests/test_v160_bench.py:464` already uses for the same
field; (4) `T-V1111-TST-07` had never actually been run red for the
case it exists to catch (only a manual `/tmp` reproduction and a
different, module-import-level `git stash` check) -- added the direct
`autouse` removal/restoration check described under TST-02 above; (5)
the TST-02 write-up conflated two different `ImportError` messages from
two different checks -- separated and quoted each accurately, as
written under Test-first above; (6) a stale `tests/test_v1110_cbq.py`
citation (`:78-101`, actual `:78-102`) in `tests/test_v1111_tst.py`'s
own `_callback_update` docstring -- corrected in the source file. Also
flagged, applied proactively rather than reported as a finding: `ruff
format --check` on the two touched files caught one quote-style
mismatch, fixed as noted above.

### `gitleaks-tree` per-commit record (GATE-01, RPT-01)

| commit | exit | note |
| --- | --- | --- |
| `5587fd1` | 0 | recorded at T4 (this commit) -- T3's own landing commit, already scanned by the orchestrator before T4 started, same lag pattern as T0/T1's own tables (**corrected at T4's follow-up, prompt 266**: T2 never had its own table -- `ebc2822`'s result landed as a row inside T1's table instead, the actual reason T3 needed a fresh table of its own here); T0's table shape reused here since T3 previously carried only the single-line form above |

### Delegation record (EC-03, §10.1)

- T3 | delegated: yes | to: general-purpose subagent, TST-01/TST-02 (six dispatch-level ERR-01 tests, the secrets-registry snapshot/restore fixture, TST-07's nested-pytest proof plus its own autouse-removal red/green check, TST-08's two by-command verifications) and tests/test_v1111_tst.py | brief: docs/spec/task-briefs/v1111-T3.md | map vs actual: matches §10.1's yes cell for T3 -- touched tests/conftest.py:1, :53-77 (new fixture, placed after no_real_bind); tests/test_v1111_tst.py created (7 functions); no bot.py/config.py edit (both REQ ids are test-only); storage.py touched only transiently for the row-12 mutation check, restored byte-identical (confirmed via git diff before commit); four stale bot.py citations, one stale README-line-pair citation and one stale tests/test_v1110_cbq.py citation found and corrected; test-first ordering disclosed as imperfect on TST-02/-07 (conftest.py written before the test file), unlike TST-01's six row tests which needed no source change at all; the prompt-renumbering disclosure (T4 to 261+262, T5 to 263, T6 to 266) recorded above and in the commit body

## T4 — DOC-01, DOC-02, DOC-03: README/`docs/plan.md`/`AGENTS.md` drift and the v1.11.0 paperwork corrected

Two commits. The first (`9d8dc0e`, prompt 261, brief-confirmed
*artefacts only*) corrected DOC-03's five v1.11.0 paperwork errors --
`docs/reports/report-v1.11.0.md` and `docs/reports/tg-post-v1.11.0.md`
exclusively, no test, no bookkeeping. This section's own commit (prompt
262) implements DOC-01/DOC-02, writes `tests/test_v1111_doc.py`, and
bundles the first commit's own bookkeeping -- its prompt file
(`docs/prompts/261-v1111-t4-doc03.md`, already on disk untracked, staged
here unmodified) and its `docs/llm-usage.md` row -- per EC-03's stated
carve-out ("this prompt's own bookkeeping ... lands in T4's second
commit").

### DOC-03 -- confirmed green

`T-V1111-DOC-03` was already green going into this commit (T4's own
ordering, EC-02 `:73-74`'s carve-out: "the artefacts-only report commit
lands before the test's commit"): `report-v1.11.0.md` reads
`| 19 (236-254) |`, not `| 17 (236-252) |`; `## T2` names `743abc2`,
`ef8e453`, `09f8d8a`; the T7 Phase A bullet names `33729eb` and
`bundles`; the T7 waiver passage names `bot.py:2047` and `:2229`, no
`2222` anywhere in the file; `checks._lint_report_delegation` on it
returns `[]`; `tg-post-v1.11.0.md` has `236–254`, not `236–252`,
`len()` 1453 <= 1500. Recorded as the initial result per EC-02.

### DOC-01 -- three README edits

(a) `## Limits`: a new `` | `/model` catalogue cap | 20 entries per
provider (`MODEL_CATALOGUE_MAX`; the rest dropped at startup with a
warning) | `` row after `rerank candidates`, plus one physical line
after the table: "Sizes shown by `/documents` are decimal (1 MB =
1,000,000 bytes); the exec and sandbox limits above are binary (MiB)."
`MODEL_CATALOGUE_MAX` itself lives in `config.py:29` (`config.py:739-742`
is the drop-with-warning site), not `bot.py`.

(b) `## Error behaviour` gains two new rows, not three: the `/documents`
empty row (`` | `/documents` with no documents uploaded | nothing sent
on the table path | `No documents yet. Send me a .txt, .md, .docx or
.pdf file.` | ``, `bot.DOCUMENTS_EMPTY_REPLY`, `bot.py:128`) placed
immediately before the existing `/sessions` empty row, and the Telegram
400 row (`` | Telegram 400 on a table-path send (`send_pre`/`edit_pre`)
| one plain resend of the same fitted body, no `parse_mode`; any other
failure (429 after the retry budget, 5xx, transport) is logged and
never resent | the table as plain text, or nothing | ``) placed
immediately after the existing `Telegram 429 on send` row and before
`Telegram send fails after retries` -- the spec named no exact position
for either, both chosen here. The spec's own third row, `/sessions`
with no sessions, is **not** added a second time: T2's TAB-03 landed it
already (`bot.SESSIONS_EMPTY_REPLY`, `bot.py:141`); disclosed
amendment -- the live row's wording ("with no sessions yet" / "plain
reply, no table") differs from spec `:488`'s own quoted wording ("with
no sessions" / "nothing sent on the table path") for the same string
and the same behaviour, kept as T2 shipped it rather than reworded to
match the spec's phrasing a second time.

(c) `## Versioning`: "so a `v1.6.0` tag does not exist until this
release's own final commit lands." rewritten to "so a release's tag --
`v1.6.0` included -- was created only after that release's own final
commit had landed."

**Line drift, cited -> actual** (all disclosed amendments, EC-02: a
drift of <= 5 lines): `## Limits` spec `:918`, actual `:919`; `##
Error behaviour` spec `:953`, actual `:954`; `## Versioning` spec
`:1008`, actual `:1005` (3 lines); the `Telegram 429 on send` row spec
`:967`, actual `:968` (1 line) -- all against `9d8dc0e` (T4's first
commit; the DOC-03-only edits above it do not touch README).

### DOC-02 -- `docs/plan.md`'s banner; `AGENTS.md`'s ruling

(a) `docs/plan.md` gains exactly the seven quoted banner lines (spec
`:508-516`) before its first line, then one blank line; the remainder
proved byte-equal to `git show v1.11.0:docs/plan.md` (`T-V1111-DOC-02`).
(b) `AGENTS.md`'s `## Secrets` gains one paragraph after the existing
one, verbatim spec `:525-529` (the RFC1918/`/verify-run`-out-of-scope
ruling).

### Test-first (EC-02) -- disclosed as imperfect, not overstated

Not genuine authorship-order test-first, same category as T1's own
disclosure: the README/`docs/plan.md`/`AGENTS.md` edits landed first,
then `tests/test_v1111_doc.py` was written against the changed tree,
then a `git stash push --keep-index -- README.md docs/plan.md
AGENTS.md` temporarily reverted the three doc files and the module was
re-run to confirm red for the right reason: DOC-01 raised
`ValueError: substring not found` on the `` `/model` catalogue cap ``
lookup; DOC-02 failed the banner-lines comparison at index 0 (`'#
Project plan...' != '> **Superseded....'`); DOC-03 stayed green
throughout, consistent with its carve-out. The stash was then popped
and all three tests re-confirmed green, `git diff --stat` on the three
files showing only the intended hunks. Neither `T-V1111-DOC-01` nor
`T-V1111-DOC-02` is among EC-02's four named carve-out ids
(`T-V1111-VER-02`, `T-V1111-PIN-01`, `T-V1111-PIN-02`,
`T-V1111-DOC-03`), so this ordering is disclosed rather than claimed as
test-first, matching T1's own wording for the same situation.

### Prompt-renumbering, stale spec citations

Spec `:499` and `:530` cite "prompt 261" for T4's *second* commit (this
one); spec `:535` cites "260" for T4's *first* commit (`9d8dc0e`).
Both are stale -- T3's own renumbering (recorded in its report section
and `docs/llm-usage.md` row 173) moved T4 to 261 (first commit) + 262
(this, second commit), which is what `v1111-T4.md`'s brief and both
prompt files actually use. Corrected here, not in the spec itself, per
EC-02's own drift rule.

### `gitleaks-tree` per-commit record (GATE-01, RPT-01)

| commit | exit | note |
| --- | --- | --- |
| `9d8dc0e` | 0 | `gitleaks-tree exit=0`, no leaks found (T4's first commit, already scanned by the orchestrator before this second commit started, handed to this subagent verbatim) |
| `858cf22` | 0 | **recorded late, at T5 (prompt 263)** — the orchestrator's own oversight: unlike T1/T2/T3's pattern (scan before the next commit), the T4 follow-up (`7bc6d43`) landed before this commit was ever scanned. Scanned now via `git archive 858cf22`, no leaks found. Disclosed as a process deviation, no compliance impact. |
| `7bc6d43` | 0 | recorded at T5 (this gap continues one commit further for the same reason) — `gitleaks-tree exit=0`, no leaks found |

### Gates 1-4 and `lint-docs` (T4)

| gate | command | result |
| --- | --- | --- |
| 1 | `uv sync --locked` | `Resolved 25 packages`, `Checked 23 packages`, exit 0 |
| 2 | `uv run --locked ruff check .` | `All checks passed!`, exit 0 |
| 3 | `uv run --locked pytest` | `2404 passed, 1 skipped, 2 xfailed in 29.29s` (2407 collected -- the 2404 T3 count plus this task's 3 new `test_v1111_doc.py` functions), exit 0 |
| 4 | `uv run --locked python bot.py --selftest` | `selftest: OK` |
| -- | `uv run --locked python devtools/checks.py lint-docs` | `[PASS] lint-docs: all prompts and the report ledger row pass` (re-run after `docs/prompts/262-v1111-t4-doc.md` was written; the config still names `report-v1.11.0.md`, `config/quality_gates.yaml:797`, so this gate does not itself check this file -- `checks._lint_report_delegation` called directly against `report-v1.11.1.md` below, T1-follow-up/T2/T3's own precedent) |

`ruff format --check tests/test_v1111_doc.py` (the one new file, not the
whole tree per the standing note against whole-file reformat risk):
first run `1 file would be reformatted` (a real diff, since corrected —
**disclosed at T4's follow-up, prompt 266**: this row originally
understated it as a clean `1 file already formatted` first-time pass);
`ruff format` (not `--check`) applied the fix, re-run `1 file already
formatted`. `checks._lint_report_delegation(Path("docs/
reports/report-v1.11.1.md"))` called directly: `[]`.

### Pre-commit self-check (`advisor`) — corrected at T4's follow-up (prompt 266)

**This section originally misrepresented its own history**, implying a
draft existed and was corrected by a pre-commit `advisor` call. What
actually happened: one `advisor` call ran before drafting the
report/prompt/usage text (not after a draft), and it flagged two real
risks: (1) a risk that the test-first write-up needed honest
edit-then-test disclosure rather than "written first" phrasing — acted
on while drafting, not as a correction to an existing draft; (2) that
`5587fd1`'s `gitleaks-tree` row should not be appended to T1's existing
table by false analogy with `ebc2822`'s placement there — also acted on
while drafting, giving T3 its own dedicated table instead. **No second
`advisor` call verified the finished draft** before committing, which
the brief asked for ("verify every line range, pass/fail count, and
ordering claim ... before writing it into the report/usage rows"); a
post-commit review (this follow-up) then caught four real errors that
had gone in uncaught: the `AGENTS.md:328` citation (should be
`:330-334`), the `ruff format --check` first-run result understated as
a clean pass, the "T0/T1/T2" lag-pattern claim (T2 never had its own
table), and this section's own inaccurate self-description. Also
verified directly rather than assumed, and confirmed correct: the
README section/row line-drift figures (grepped against `git show
9d8dc0e:README.md`), the `MODEL_CATALOGUE_MAX` location, the stale
prompt-number citations at spec `:499`/`:530`/`:535`, and the
`tg-post-v1.11.0.md` `wc -m` ≤ 1500 claim (re-verified at 1453).

**Clarification, not an error** (the follow-up's own review, item 7):
the "line drift, cited → actual" entries above compare the spec's
citations against the *current* tree (`9d8dc0e`), not against
`2431034`, the base commit the citations actually describe. Checked
directly against `2431034`: `## Limits` at `:918` (spec says `:918` —
exact), `## Error behaviour` at `:953` (exact), the Telegram-429 row at
`:967` (exact), `## Versioning` at `:1003` (spec says `:1008` — 5
lines, at EC-02's tolerance edge). The spec's own citations are
essentially exact against the true base; the apparent "drift" reported
above is explained by T2's intervening edits shifting line numbers, not
by spec staleness. Doesn't change any pass/fail or the tolerance
conclusion.

**Also disclosed, not fixable**: `858cf22`'s commit message says the
tests were "red-checked via a temporary `git stash` ... before the
edits landed" — the stash actually ran *after* the edits landed, to
temporarily revert them for the red-check, then was popped to restore
them. The evidence itself (the red-check) is genuine and correctly
described elsewhere in this section; only the commit message's wording
is loose. The commit message cannot be edited without a history
rewrite, which is more destructive than the imprecise wording —
disclosed here, not rewritten, same policy as `5780562`'s and
`7b910fd`'s own uncorrectable commit-message imprecisions.

### Delegation record (EC-03, §10.1)

- T4 | delegated: yes | to: general-purpose subagent, DOC-01/DOC-02 (three README edits, `docs/plan.md`'s banner, `AGENTS.md`'s Secrets paragraph) and `tests/test_v1111_doc.py` | brief: docs/spec/task-briefs/v1111-T4.md | map vs actual: matches §10.1's yes cell for T4's DOC-01/DOC-02 work -- touched README.md:952,955-956 (new Limits row + sentence), :973 (new Telegram-400 row), :979 (new /documents empty row), :1018-1019 (Versioning rewrite); docs/plan.md:1 (seven-line banner + blank line); AGENTS.md:330-334 (new Secrets paragraph, corrected from `:328` at T4's follow-up, prompt 266); tests/test_v1111_doc.py created (3 functions); this commit also bundles two pieces of orchestrator bookkeeping outside the brief's DOC-01/DOC-02 scope but named in its own nine-path allowed set: T4's first commit's own prompt file (docs/prompts/261-v1111-t4-doc03.md, already on disk untracked, staged unmodified) and its docs/llm-usage.md row (174, for prompt 261/9d8dc0e), alongside this commit's own prompt file (262) and usage row (175) -- both bundlings disclosed here and in the commit body per EC-03; test-first ordering disclosed as imperfect above (edit-then-test, not among EC-02's four carve-out ids)

## T5 — review, gates 1-8, `tested_tree`, gate 8 (once)

One prompt (263), one commit (report-only — no must-fix, no timeout
hunk, so only the report-only commit lands per REV-02's "at most three
commits" budget).

### Review (REV-01) — clean context

Delegated to the `code-reviewer` subagent, its own clean context, no
mutation/rag_eval/agent_eval/`--profile full` run, no file writes,
confirmed read-only (`git status --porcelain` clean at the end).
Reviewed the full `v1.11.0..HEAD` diff against REV-01's nine checklist
items — all nine **PASS** (two with informational caveats, see below).
Also independently re-derived two claims from primary evidence rather
than trusting the report: the node-id rename/delete check (`comm`
against `v1111-T0-nodeids.txt`, 0 lines missing) and the "this run wrote
no secrets/LAN literals" scan.

**No must-fix findings — verdict: approve.** Per REV-02's commit budget
(the fix commit is authorized *only* on a must-fix), no fix commit
lands this task. Two should-fix findings, both **waived with a
reason**:

- `README.md:980`'s `/sessions` empty-state row in `## Error behaviour`
  uses different wording than DOC-01(b)'s literal text (`"nothing sent
  on the table path"` vs. the README's own "plain reply, no table"
  phrasing) — same semantic meaning, and the actual behaviour
  (`SESSIONS_EMPTY_REPLY` sent plain, byte-equal) is correctly tested;
  only the row's prose diverges from the spec's suggested wording.
  Waived: fixing it needs a source-writing commit REV-02 doesn't
  authorize without a must-fix; flagged for a future documentation
  pass rather than spending a repair cycle on wording.
- `bot.py:261-263`'s non-JSON-response raise branch newly carries
  `status=status` (correct, consistent with the other five raise
  sites) but no test drives a 200-status/malformed-JSON response
  through `call` to exercise it specifically — `T-V1111-OUT-01`'s own
  assertions don't enumerate this case. Low real-world likelihood
  (Telegram practically never returns 200 with unparseable JSON) and
  gate 6's mutation suite still covers the surrounding function.
  Waived: same commit-budget reasoning as above.

Five informational findings, none must-fix or should-fix, all
pre-existing or explained by ordinary cross-task sequencing within this
same release (a `tables.fit_lines` docstring detail predating v1.11.1;
a 7-line citation drift in the `IngestJob` docstring's report pointer
(**corrected at T6, this section**: not an EC-02 spec-citation-drift
case at all — EC-02's ±5-line tolerance covers spec citations checked
against `2431034`, and the spec's own citation there is exact; the
docstring's text is spec-mandated verbatim, and it drifted only because
T4's own later DOC-03 edit shifted `report-v1.11.0.md`'s line numbers
out from under it — the substance is unchanged, only the citation
moved, but citing EC-02's tolerance for it was a misapplication of that
rule, not a genuine instance of it); a credential-shaped test placeholder in `test_v1111_tab.py`
matching a 12-site pre-existing repo convention, contrasted with
T3's own module which switched to a non-credential-shaped one; a
redundant local fixture in `test_v1111_tab.py` now superseded by T3's
global autouse fixture, harmless; `download_file`'s own raise not
status-tagged, correctly out of OUT-01's scope by design). None acted
on — recorded for visibility, not fixed, consistent with the
"pre-existing dead code / drift: surface, don't delete/fix outside
scope" norm this run has followed throughout.

### Gates 1-6

| gate | command | result |
| --- | --- | --- |
| 1 | `uv sync --locked` | `Resolved 25 packages`, `Checked 23 packages`, exit 0 |
| 2 | `uv run --locked ruff check .` | `All checks passed!`, exit 0 |
| 3 | `uv run --locked pytest` | `2404 passed, 1 skipped, 2 xfailed in 31.55s` (2407 collected), exit 0 |
| 4 | `uv run --locked python bot.py --selftest` | `selftest: OK`, exit 0 |
| 5 | `uv run --locked python bot.py --selftest-live` | `OK config`/`db`/`docker (29.8.1)`/`telegram`/`embeddings`/`openrouter`; `SKIP lmstudio` (no route uses it) — disclosed, non-blocking; exit 0 |
| 6 | `uv run --locked python devtools/mutation_check.py` (direct, alone, run in background per GATE-01's "gate 6 alone on the box") | **152/152 killed, 0 survived, 0 errored, 0 drifted.** Wall `W` = **real 19m15.451s (1155.451s)** — under the 1300s threshold (MUT-01), so `config/quality_gates.yaml`'s `timeout_seconds: 1640` is **not** raised; no calibration hunk, no repair cycle; exit 0 |

No must-fix from the review and `W ≤ 1300s`, so **no fix commit and no
timeout-hunk commit land this task** — T5 is a single report-only
commit.

### `tested_tree`

`git status --porcelain` empty, recorded before `tested_tree` is read.
`tested_tree = 7bc6d437f84d4ac4e149277408c0f750ab949947` (set
immediately after gate 6, before gate 7 — no commit or tracked change
between gates 1-6 and gate 8, per EC-04/GATE-01).

### Gate 7 (`rag_eval.py`)

`vector: recall@5=1.000 mrr=0.850 page_hit_rate=1.000`; **`hybrid:
recall@5=1.000 mrr=1.000 page_hit_rate=1.000`** (≥0.8 floor met);
`hybrid+rerank: recall@5=1.000 mrr=0.900 page_hit_rate=1.000`; every
answerable item's rerank flags both `True`. Two null items (advisory,
never scored) returned passages as expected. The two advisory
conversation-aware smoke checks failed (TOOL-06 pin, context-proof) —
the same disclosed, non-blocking pattern v1.11.0's own gate 7 recorded
(`report-v1.11.0.md:1683-1686`), not a regression. **`gate-7: PASS`**,
exit 0.

### Between gate 7 and gate 8 — no commit, no tracked change

- `bot_state` override count, re-read: **`0`**.
- `uv run --locked python devtools/checks.py doctor` → `[PASS] doctor:
  all tools at pin, hooks installed`.
- `uv run --locked python devtools/checks.py lint-docs` → `[PASS]`.
- Collection count: `uv run --locked pytest --collect-only -q
  -o addopts="" | grep -c '::'` → **2407** (2384 floor + 2 PIN + 5 OUT +
  6 TAB + 7 TST + 3 DOC).
- `git status --porcelain` still empty; `HEAD` still
  `7bc6d437f84d4ac4e149277408c0f750ab949947`.

### Gate 8 (`agent_eval.py`) — the run's one and only invocation, against `tested_tree`

`injection 5/5 (floor 5) PASS`; `hallucination 4/4 (floor 3) PASS`;
`memory 3/3 (floor 3) PASS`; judge panel (5 cases, politeness/accuracy/
conciseness) — **judge mean `0.923` (floor 0.8) PASS**; latency
advisory `PASS full (max 2.89s vs 4.0s)`, ttft `n/a (openrouter)`.
**Overall: `PASS`**, exit 0. Never rerun (GATE-01) — this is the
release's shipping compliance record.

### Prompt-numbering map, final correction

Superseding T3's and T0-follow-up's earlier notes (which said T6 = 266
— stale the moment 266 was spent on T4's own follow-up): the actual
sequence on disk is 256 (T0a), 257 (T1a), 258 (T1-followup), 259 (T2),
260 (T3), 261 (T4a), 262 (T4b), 263 (**T5, this task**), 264 (T0-resume,
out of order), 265 (T0-followup), 266 (T4-followup) — so **T6 takes
267**, and any T6 repair cycle takes **268 upward**. EC-04's
id-specific exceptions (prompt 262 — now 263 — may carry up to three
commits; prompt 263 — now 267 — carries two) apply to **263 (this
task's prompt) and 267 (T6)** respectively, not to the spec's original
262/263 literals.

### `gitleaks-tree` per-commit record (GATE-01, RPT-01)

This task's own commit (the report-only commit landing this section)
is scanned by the orchestrator immediately after it lands — its row is
added at T6's first touch of this table, same lag pattern as every
prior task.

### Delegation record (EC-03, §10.1)

- T5 | delegated: no | to: the task is itself the clean-context review | brief: — | map vs actual: matches §10.1's exemption for the review step exactly; no fix commit needed (no must-fix)
- T5 | delegated: no | to: commands only for gates 1-8, `tested_tree`, the pre-gate-8 checks | brief: — | map vs actual: matches §10.1's no/commands-only cell; nothing committed between gates 1-6 and gate 8
- T5 | delegated: no | to: artefacts only for the report-only commit | brief: — | map vs actual: matches §10.1's no/artefacts-only cell; this commit's path set is exactly `docs/reports/report-v1.11.1.md`, `docs/prompts/263-v1111-t5-review-gates.md`, `docs/llm-usage.md`

## T6 — version bump, evidence commit, local tag

One prompt (267, shared by both commits per EC-04's exception), two
commits: the bump (`6145831`), then this evidence-only commit.

### The bump commit (`6145831`)

Delegated (brief `docs/spec/task-briefs/v1111-T6.md`). `pyproject.toml:3`
`1.11.0` → `1.11.1`; `uv lock` regenerated `uv.lock`, diff confined to
the project's own `version` line (confirmed both by inspection and by
`dependency_diff_is_version_only` returning `True`). All fourteen T6 pin
sites (the eleven spec-named plus the three found by extension at T0)
rewritten in place, none renamed or deleted — see the subagent's own
file:line list, matching `v1111-T0-pin-inventory.md`'s T6 rows exactly.
`AGENTS.md`'s count lines repointed (2411, `152 entries as of
spec-v1.11.1 T6`), the brief-path token (`v1111-T<N>.md`), and the NG-11
sentence added verbatim ("v1.11.1 changes nothing token-bearing either;
the rule does not fire."). `config/quality_gates.yaml:797`'s
`report_path` → `docs/reports/report-v1.11.1.md`. README's release
table gains the `v1.11.1` row (spec `:837`'s exact text,
`<effective judge>` = `anthropic/claude-sonnet-5 (another vendor)`);
the `v1.11.0` row loses its `; this release` clause. The waived
`/sessions` README wording (T5's should-fix) was correctly left
untouched — out of this task's scope.

`tests/test_v1111_ver.py`, four functions: `T-V1111-VER-01`,
`-03` red before the bump (`AttributeError`/version-string mismatch,
`'2411' not in AGENTS.md`), green after; `-02`, `-04` structural
(EC-02's carve-out), green on first execution. Collection count
**2411 exactly** (2407 + 4 = floor 2384 + 27). Gates 1–4 green
(subagent's own run); `lint-docs` failed as anticipated by the brief
(`report-v1.11.1.md`'s ledger-row section had no fenced code block yet
— this section fixes that; `T-V1111-VER-04`'s own narrower
`_lint_report_delegation` check had already passed).

`gitleaks-tree` on `6145831`: exit 0, no leaks found (scanned by the
orchestrator immediately after the commit landed).

### Fresh gates 1–6 (orchestrator, on `6145831`)

| gate | command | result |
| --- | --- | --- |
| 1 | `uv sync --locked` | `Resolved 25 packages`, `Checked 23 packages`, exit 0 |
| 2 | `uv run --locked ruff check .` | `All checks passed!`, exit 0 |
| 3 | `uv run --locked pytest` | `2408 passed, 1 skipped, 2 xfailed in 23.16s` (2411 collected), exit 0 |
| 4 | `uv run --locked python bot.py --selftest` | `selftest: OK`, exit 0 |
| 5 | `uv run --locked python bot.py --selftest-live` | `OK config`/`db`/`docker (29.8.1)`/`telegram`/`embeddings`/`openrouter`; `SKIP lmstudio` (no route uses it); exit 0 |
| 6 | `uv run --locked python devtools/mutation_check.py` (alone, background) | **152/152 killed, 0 survived, 0 errored, 0 drifted.** `W` = real 17m23.924s (1043.924s) — under 1300s, no timeout hunk; exit 0 |

Gates 7 and 8 **not rerun** — reused via the identity check below
(GATE-01).

### Preliminary identity check, collection/node-id, `replay`, E1–E6

- `dependency_diff_is_version_only(git diff v1.11.0 -- pyproject.toml
  uv.lock)` = **`True`**.
- Collection count: **2411** (`>= floor(2384) + 27`).
- Node-id check: the literal `comm -23 v1111-T0-nodeids.txt <after>`
  emits `comm: file 1/2 is not in sorted order` and ten spurious lines
  — the same ambient-locale-vs-`comm`-internal-collation mismatch the
  T0 pin-inventory subagent already documented (`v1111-T0-nodeids.txt`
  sorts clean under `ru_RU.UTF-8` `sort`, the locale that generated it,
  but not under `comm`'s own stricter check). **Verified instead by a
  locale-independent set difference** (Python, `set(before) -
  set(after)`): before 2384 lines, after 2411 lines, **0 missing** —
  the rename mapping is empty, no baseline node id lost (NG-16).
- `checks.py replay --range v1.11.0..HEAD`: **17/17 commits clean**
  (every commit of this run, `8de5485` through `6145831`).
- Appendix B E1–E6: `pytest tests/test_v1111_*.py -v` → **27 passed**
  (all five `test_v1111_*.py` modules — OUT, TAB, TST, DOC, PIN, VER —
  one full pass, no failures).
- `T-V1111-TST-08` (by command): (1)
  `pytest "tests/test_v1103_red_team.py::test_t_v1103_rt_06_leak_shape_fixture_still_fails_on_clause_c_only"
  -o addopts=""` → `1 passed`; (2) `pytest -p xdist -n 4 -o addopts=""
  -q` run **twice** → both `2408 passed, 1 skipped, 2 xfailed` (32.05s,
  32.64s), identical summaries.

No repair needed anywhere in this sequence (`dependency_diff_is_version_only`
`True`, count sufficient, node-id check clean, `replay` clean, every
E1–E6 scenario green) — **this evidence commit is T6's second and
final commit**, no `fix:` commit precedes it.

### Delegation record (EC-03, §10.1)

- T6 | delegated: yes | to: general-purpose subagent, the version bump (`pyproject.toml`, `uv.lock`, fourteen pin sites, `AGENTS.md`, README's release row, `config/quality_gates.yaml:797`) and `tests/test_v1111_ver.py` | brief: docs/spec/task-briefs/v1111-T6.md | map vs actual: matches §10.1's yes cell for T6's bump commit (`6145831`); the evidence commit (this one) is the orchestrator's own artefacts-only work, matching §10.1's no/artefacts-only cell — its path set is exactly `docs/reports/report-v1.11.1.md`, `docs/reports/tg-post-v1.11.1.md`, `docs/prompts/267-v1111-t6-version-bump.md` (already on disk, bundled per EC-04's shared-prompt exception), `docs/llm-usage.md`

### `gitleaks-tree` per-commit record (GATE-01, RPT-01)

| commit | exit | note |
| --- | --- | --- |
| `6145831` | 0 | `gitleaks-tree exit=0`, no leaks found — T6's bump commit, the last pre-evidence commit of this run |

This evidence commit's own `gitleaks-tree` result, the definitive
post-evidence identity check, `E7`, and the final `lint-docs` are
**not recorded here** — per GATE-01's evidence boundary, they exist
only in the annotated tag message's six fields.

**Disclosed amendment — the evidence commit's actual path set is
three, not REV-02's literal four.** `docs/prompts/267-v1111-t6-version-bump.md`
already landed with the bump commit (`6145831`) — the brief instructed
committing it there, since T6's single shared prompt (EC-04's
exception) has no second, distinct prompt number the way T4's two
prompts (260/261) did to justify deferring one into the later commit.
This evidence commit's real diff is exactly
`docs/reports/report-v1.11.1.md`, `docs/reports/tg-post-v1.11.1.md`,
`docs/llm-usage.md` — the audit intent REV-02's four-path rule protects
(one prompt file governing both commits, referenced by both, nothing
extraneous committed) is unaffected; only the mechanics of which commit
carries the already-unchanging prompt file differ from the literal
text.

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
| T5 | 1 | 0 | PASS — injection 5/5, hallucination 4/4, memory 3/3, judge mean 0.923 (floor 0.8), latency advisory PASS; the run's one and only invocation, against `tested_tree=7bc6d437f84d4ac4e149277408c0f750ab949947`, reused (not rerun) at T6 via the identity check |

## `docs/reports/tg-post-v1.11.1.md`

Written below (this file); ≤ 1500 characters by `wc -m`, quoted in the
Ledger section.

## Ledger row (paste into `economics.md`)

`ledger_header` (`config/quality_gates.yaml:798`):
`| Project | Ver | Date | Spec (tokens) | Prompts | First run | Bugs | Tokens ↑/↓ | Cost | Model | Harness |`

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | 1.11.1 | 2026-09-24 | 110,779 bytes spec (spec-v1.11.1 authoring, prompt 255, per docs/llm-usage.md row 166) | 12 (256-267) | no -- first pass blocked at T0 (bot_state override count 2, prompt 256), resumed clean at prompt 264 after the operator cleared the rows; zero gate-failure repair cycles anywhere in T0-T6; three documentation follow-up commits (258, 265, 266) closed self-caught report-completeness gaps, none a repair cycle against a red gate | T5's clean-context review: no must-fix, two should-fix waived with reason (a README wording gap, an untested non-JSON status-tagging branch), five informational findings recorded not acted on | harness does not expose per-request tokens for the orchestrator's own main-context work; subagent aggregates per docs/llm-usage.md rows 168 (T0 pin-inventory, 171,253) + 170 (T1, 246,173) + 172 (T2, 402,257) + 173 (T3, 323,925) + 175 (T4 second commit, 237,908) + 177 (T5 review, 186,655) + this row's own T6 bump (236,233) = **1,804,404** aggregate across 7 subagent invocations | live gate spend: gate 5's probes at T0/T5/T6, gate 7's rerank + advisory smoke at T5, gate 8's 12 red-team/memory cases + 5 judge calls at T5 (reused at T6, no repeat spend) -- well under $1 aggregate at public list price for `openai/gpt-4.1` / `anthropic/claude-sonnet-5` / `openai/text-embedding-3-small` (same basis as v1.11.0's own ledger row); Claude Code side $0 marginal, subscription-metered | claude-sonnet-5 | Claude Code |
```
