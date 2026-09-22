# tg-agent-bot v1.11.0 — Telegram tables, sessions, the `/model` menu and a background ingest worker

Seven bundled changes to the bot's Telegram surface: an HTML `<pre>` table
path for five read-only commands (agent replies stay byte-identical plain
text), `/stats`/`/documents` as tables and `/delete #<id>`, session
list/switch (`/sessions`, `/session <id>`, no schema change),
`callback_query` handling behind a two-step `/model` provider→model menu,
and document ingest caps raised to the Bot API's 20 MB ceiling behind a new
background `IngestWorker` with `/cancel`. Spec:
`docs/spec/spec-v1.11.0.md`. `<base>` = `295b01f` (the commit the spec's
`file:line` citations describe); `git diff --name-only 295b01f HEAD` at T0
touches only `docs/handoff-v1.11.0.md`, `docs/llm-usage.md`,
`docs/prompts/235-v1110-spec-authoring.md` and `docs/spec/spec-v1.11.0.md`
— no source, test or config file differs from `295b01f`, so every spec
`file:line` citation holds unchanged. Spec `sha256`:
`98a4af264196138b1b3ee01d16e63fa3a052fba3e7a1891e7dfed5037de5b4a5`.

This file is filled progressively: T0 (this skeleton), T1 (tables.py +
HTML pre-text plumbing), T2 (/stats, /documents tables, /delete #id), T3
(sessions), T4 (/model menu, callback_query), T5 (IngestWorker, raised
caps, /cancel), T6 (commands registration, bench waiver, pins), T7
(mutation entries, review, gates 1-8), T8 (version bump, evidence commit,
tag). Sections not yet reached read "not reached: T\<n\>".

## T0 — preconditions, gates 1-5, measurements, pin inventory

`<base>` = `295b01f`. Spec `sha256` as above. `Status: ready for \`go\`` —
present once (`grep -c`).

### Preconditions (EC-05)

- `git rev-parse HEAD` = `c29d53384b4d0f854a782a39fd5d4c08c64de1da`
  (`git describe --tags` = `v1.10.4-6-gc29d533`) — six commits ahead of
  `295b01f`, all four docs-only (the spec's own authoring pipeline: draft,
  3 cross-review rounds, handoff) plus two more (a ledger-row correction,
  the handoff+usage-row commit) — matches `docs/handoff-v1.11.0.md`'s
  stated precondition ("tree at `8695b52` or later on `main`"), which
  supersedes EC-05's literal `295b01f`-exact wording for this detail; this
  is expected drift from the spec-authoring process itself, not a spec
  ambiguity — recorded here, not treated as a repair cycle.
- `git status --porcelain` — empty (even cleaner than EC-05's expected
  `?? .README.md.swp`; no untracked file present at all).
- `git stash list` — empty, recorded.
- `test -f .env` — exit 0.
- `docs/prompts/235-v1110-spec-authoring.md` and `docs/llm-usage.md` row
  145 present in `HEAD` — confirmed (row 146 is the spec-authoring row
  itself; row 145 is the prior ledger-row correction).
- `git diff --exit-code HEAD -- docs/spec/spec-v1.11.0.md` — exit 0
  (committed, unmodified).
- **LM Studio address**: `go` text named `192.168.0.145`. Probed
  `curl -sS -m 3 http://192.168.0.145:1234/v1/models` before `go` was
  issued — reachable, catalogue includes the project's pinned
  `qwen/qwen3.8-27b`. Applied the one permitted `sed -i` to `.env`'s
  `LMSTUDIO_BASE_URL` line (value never printed; confirmed only by
  `grep -c` exit status matching the expected pattern
  `LMSTUDIO_BASE_URL=http://192.168.0.145:1234/v1` — `/v1` suffix added to
  match `config.py:359`'s default shape, since the bare `host:port` the
  operator supplied would not have matched the OpenAI-compatible base-url
  convention the client expects).
- **Override precondition (MOD-05)**: the one permitted programmatic
  `data/` read —
  `SELECT COUNT(*) FROM bot_state WHERE key = 'provider_override' OR key
  LIKE 'model_override:%'` — printed `0`. No blocked run.

### Gates 1-5

- Gate 1 (`uv sync --locked`): resolved 25 packages, checked 23 — exit 0.
- Gate 2 (`ruff check .`): all checks passed — exit 0.
- Gate 3 (`pytest`): exit 0, 100% collected/run, no failures.
- Gate 4 (`bot.py --selftest`): `selftest: OK`.
- Gate 5 (`bot.py --selftest-live`): `OK config`, `OK db`,
  `OK docker (29.8.1)`, `OK telegram`, `OK embeddings`, `OK openrouter`;
  `SKIP lmstudio (no route uses it)` — disclosed, non-blocking (AGENTS.md's
  gate-5 rule: a provider no route names SKIPs cleanly). Exit 0.

### Measurements

- Test-collection floor:
  `uv run --locked pytest --collect-only -q -o addopts="" | grep -c '::'`
  = **2311** (matches `AGENTS.md:161` / `tests/test_v190_agents.py:146-149`).
- Baseline node-id list written to
  `docs/spec/task-briefs/v1110-T0-nodeids.txt` (2311 lines, sorted).
- `len(devtools.mutation_check.MUTATIONS)` = **144**.
- The v190 `find` string
  (`    if isinstance(file_size, int) and file_size > DOCUMENT_MAX_BYTES:`,
  `v190-size-precheck-disabled`, `devtools/mutation_check.py:1218`) occurs
  **exactly once** in `bot.py` (`grep -cF`).

### Pin inventory (PIN-01)

Delegated (one general-purpose subagent, brief `v1110-T0.md`, EC-04),
landed at `docs/spec/task-briefs/v1110-T0-pin-inventory.md` (129 lines,
built by grepping the live tree at `c29d533`, not copied from the spec).
55 pin-table rows (source-definition + test-assertion + README-table
sites) plus one explanatory note on STA-01's "43 pins" figure (12 grouped
rows covering 24 individually located `/stats` assertion sites plus the
renderer; the remainder of the 43 not itemised one-by-one, disclosed
rather than padded), 4 measurement rows (cited, not re-derived), 2 rename
mapping entries.

**Drift**: none exceeding 5 lines. One 1-line drift disclosed:
`tests/test_v15_standards.py` cited `:1824`, actual
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` is at
`:1823` — recorded per EC-02, not a repair cycle.

**Amendments disclosed beyond the brief's starting list** (PIN-01: not a
repair cycle, no budget consumed):
1. A third `report_path` pin site, `tests/test_v190_agents.py:290-303`
   (`test_t_v1100_ec_01_quality_gates_yaml_repoints_report_path`) — same
   T6/VER-03 repoint, function name deliberately kept stable (not added
   to the rename mapping).
2. `README.md:828`/`:831` and the `:511-516` prose sentence — the
   *unchanged-unless-the-ceiling-moves* numbers (`10,485,760`, `300 s`)
   inside T5's block, alongside the two the spec names (`500,000`,
   `500 pages`), flagged so a careless table edit doesn't clobber them.
3. Four source-definition sites (`bot.py:1132` `_render_stats`, `:221`
   `allowed_updates` payload, `:1381` typing-ceiling call, `:1483`
   `Your documents (N):`) added so the inventory names both source and
   test for each literal.

Independently reconfirmed the measurements during this pass: `len(MUTATIONS)
== 144`; the v190 `find` string exactly once, at `bot.py:1355`; node-id
baseline 2311 lines — all match T0's own direct measurements above.

## T1 — not reached

## T2 — not reached

## T3 — not reached

## T4 — not reached

## T5 — not reached

## T6 — not reached

## T7 — not reached

## T8 — not reached

## Operator inputs

- **Run configuration (EC-05), source `.env`** (operator-prepared ahead of
  `go`, opened only by the one permitted `sed -i` for `LMSTUDIO_BASE_URL`
  and never otherwise read/printed): `LMSTUDIO_BASE_URL` set to
  `http://192.168.0.145:1234/v1` at T0; all other `.env` values unchanged
  from v1.10.4.
- **`go` text**: `go docs/spec/spec-v1.11.0.md — LM Studio at
  http://192.168.0.145:1234`.

## Gate-8 attempt log

| task | attempt | exit | outcome |
| --- | --- | --- | --- |
| not reached | | | |

## `docs/reports/tg-post-v1.11.0.md`

Not written yet — written at T8 (or at the stop route, if triggered).

## Ledger row (paste into `economics.md`)

Not reached — filled at T8.
