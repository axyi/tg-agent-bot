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

- **LM Studio address**: `go` text named `192.168.0.145`. Applied the one
  permitted `sed -i` to `.env`'s `LMSTUDIO_BASE_URL` line (value never
  printed; confirmed only by `grep -c` exit status matching the expected
  pattern `LMSTUDIO_BASE_URL=http://192.168.0.145:1234/v1` — `/v1` suffix
  per `config.py:378`'s default shape). Probed
  `curl -sS -m 3 http://192.168.0.145:1234/v1/models` — **reachable**,
  catalogue includes the project's pinned `qwen/qwen3.8-27b` among 16
  models. Not the blocking condition this run.
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

**Next step**: the operator clears (or confirms) the `provider_override`
/ `model_override:*` row(s) in `bot_state`, then re-issues
`go docs/spec/spec-v1.11.1.md — LM Studio at http://192.168.0.145:1234`.
The `.env` `LMSTUDIO_BASE_URL` edit already applied is idempotent and
does not need to be undone.

## T1 — not reached

## T2 — not reached

## T3 — not reached

## T4 — not reached

## T5 — not reached

## T6 — not reached

## Operator inputs

- **Run configuration (EC-04), source `.env`** (operator-prepared ahead of
  `go`, opened only by the one permitted `sed -i` for `LMSTUDIO_BASE_URL`
  and never otherwise read/printed): `LMSTUDIO_BASE_URL` set to
  `http://192.168.0.145:1234/v1` at T0; all other `.env` values unchanged
  from v1.11.0.
- **`go` text**: `go docs/spec/spec-v1.11.1.md — LM Studio at
  http://192.168.0.145:1234`.

## Gate-8 attempt log

| task | attempt | exit | outcome |
| --- | --- | --- | --- |
| not reached | | | |

## `docs/reports/tg-post-v1.11.1.md`

Not written yet — written at T6 (or at the stop route, if triggered).

## Ledger row (paste into `economics.md`)

Not reached — filled at T6. This run: **blocked at T0** (`bot_state`
override count = 2), no ledger row this attempt.
