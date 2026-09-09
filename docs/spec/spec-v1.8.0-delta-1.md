# spec-v1.8.0-delta-1 — the gate matrix, the design plan, the review log

Overflow file of `docs/spec/spec-v1.8.0.md`, created because that file is at
`standards/workflow.md` §12's ~80 KB ceiling (REQ-V180-EC-01, "The spec's own
budget"). It is **normative**: REQ-V180-EC-12 makes this table the one
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
(`tests/test_v15_standards.py:1727-1741`) parses, in place of
`spec-v1.7.0.md`, and REQ-V180-DSH-02 makes the frozen design plan below the
one §&nbsp;5.1 points at. Nothing else belongs in this file beyond those two and
`spec-v1.8.0.md`'s Appendix C tables, all moved here as overflow
(REQ-V180-EC-01).

## The gate matrix (REQ-V180-EC-12)

REQ-V170-GATE-03's table, yes/— verbatim, plus the `mutation_check.py --select
v180-` row REQ-V180-EC-10 adds, minus the `note` column the parser never
reads. It is load-bearing markup: the parser finds the header by the literal
`| gate | pre-commit` and takes rows until the first line not starting with
`|`, and every label must match `_GATE_MATRIX_LABEL_TO_NAME`
(`tests/test_v15_standards.py:1685-1707`) byte-for-byte.

| gate | pre-commit | pre-push | full |
|---|:---:|:---:|:---:|
| `ruff check` (staged) | yes | — | — |
| `ruff check .` (tree) | — | yes | yes |
| `ruff format --check` | yes | yes | yes |
| branch-name check | yes | yes | yes |
| `gitleaks git --staged` | yes | — | — |
| `gitleaks dir` (tree) | — | yes | yes |
| `uv sync --locked` | — | — | yes |
| `pytest` | — | yes | yes |
| `bot.py --selftest` | — | yes | yes |
| `bot.py --selftest-live` | — | — | yes |
| `mutation_check.py --select v15-` | — | yes | — |
| `mutation_check.py --select v160-` | — | yes | — |
| `mutation_check.py --select v170-` | — | yes | — |
| `mutation_check.py --select v180-` | — | yes | — |
| `mutation_check.py` (all) | — | — | yes |
| `trivy fs` | — | yes | yes |
| `semgrep scan` | — | yes | yes |
| `skylos` | — | yes | yes |
| `install_hooks.py --check` | — | yes | yes |
| `checks.py doctor` | — | yes | yes |
| `checks.py lint-docs` | — | — | yes |

---

## The frozen design plan (REQ-V180-DSH-02, §&nbsp;5.1 of `spec-v1.8.0.md`)

Moved here as round 3's overflow (REQ-V180-EC-01). **Normative and frozen:**
the executor implements it and never designs. REQ-V180-DSH-03…-06, which bind
it, stay in §&nbsp;5.1 of the spec.

**Direction.** An **operator's instrument panel**, not a SaaS analytics
product: hairline rules, not floating cards; one accent reserved for
**measured signal**; numbers in columns you read down.

**Palette — exactly six named values**, custom properties on `:root` inside
the one `STYLE` block:

| token | hex | role |
|---|---|---|
| `--ink` | `#16181c` | body text, headings, the one heavy rule under `h1` |
| `--ground` | `#eef0f2` | the page background: cool paper, never warm cream |
| `--plate` | `#ffffff` | the surface of a panel/section, flat |
| `--rule` | `#ccd2d8` | every hairline: panel edges, row rules, chart baselines, the `h2` scale line |
| `--dim` | `#5f6873` | secondary text: column headers, units, timestamps, footer |
| `--signal` | `#1f5fb0` | the single accent: bar fill, link, active nav item, focus ring — signal only |

Two status colours carry over unchanged and are the **only** other saturated
values: ok `#1c7a4a`, fault `#b23636`, on status text and an error-outlined
gantt bar, nowhere else. A ninth colour is a defect.

**The `PALETTE` dict is remapped onto those eight and gains no key.**
`dashboard_render.PALETTE` (`dashboard_render.py:79-85`) is the SVG helpers'
colour table: five keys today, the same five afterwards, with these literals.
This is what DSH-06 means by "only the colour literals move", and what makes
DSH-04's "every colour literal is one of the eight" satisfiable:

| key | new literal | role |
|---|---|---|
| `bar` | `#1f5fb0` (`--signal`) | bar fill |
| `bar_track` | `#eef0f2` (`--ground`) | bar track |
| `kind_client` | `#1f5fb0` (`--signal`) | a `CLIENT` span — the outbound call, the signal |
| `kind_internal` | `#5f6873` (`--dim`) | an `INTERNAL` span — structure, not signal |
| `error_outline` | `#b23636` (fault) | unchanged |

**Type scale — four sizes, two weights, one face**: REQ-V180-DSH-01's system
stack, for **everything including numbers**.

| element | size / line-height | weight | notes |
|---|---|---|---|
| `h1` | 22px / 1.25 | 600 | `letter-spacing: -0.01em`; one 2px `--ink` rule beneath, full content width |
| `h2` | 16px / 1.3 | 600 | sentence case; a 1px `--rule` line from the text's right edge to the content's right edge — a scale line, not decoration |
| `h3` | 13px / 1.35 | 600 | sentence case |
| body, `td` | 13px / 1.5 | 400 | |
| `th`, `.meta`, `footer`, units | 12px / 1.4 | 600 (`th`) / 400 (rest) | `--dim`; **sentence case, `text-transform: none`, `letter-spacing: 0`** |

Four sizes and no fifth: 22 → 16 → 13 → 12. `h3` is **deliberately body size
at the heavier weight** — weight is the distinction, not a fifth size and not a
collision. No 300 or 700 weight, no italic.

**Alignment — the answer to "the numbers slide".** The page is **one column**,
`max-width: 68rem`, centred, and *every* element — `h1`'s rule, each `h2`'s
scale line, every plate, table and `<svg>` — shares its left and right edges.
Text is left-aligned, nothing centred but a single empty-state line; **every
`class="num"` cell is right-aligned with `font-variant-numeric: tabular-nums`**
in the body face, so a column of numbers has one right edge and one glyph width
(REQ-V180-DSH-03 makes this checkable); units go in the column header, never
per cell; charts are drawn to the table's content width, so bar baselines line
up with table rules.

**Surfaces.** A `section` is a **plate**: `background: var(--plate)`, `border:
1px solid var(--rule)`, `border-radius: 2px`, **no `box-shadow` anywhere in the
sheet**, padding `0 1rem 1rem`. Table rows are separated by 1px `--rule`, the
last by none. A bar is a 0.6rem `--ground` track with a `--signal` fill, square
ends.

**Layout, per page.**

| page | concept |
|---|---|
| `/` (usage) | a **reading strip** across the top of the first plate: four measured values — calls, total tokens, cost, error rate — as label-above-number pairs on one baseline, split by 1px `--rule` verticals, numbers at 22px/600 tabular; then the totals table, then the by-group table |
| `/traces` | one full-width table, newest first; the duration column carries an inline `--signal` bar sized against the page's widest duration, drawn **inside** the number's own cell so magnitude and value read together |
| `/traces/<id>` | the gantt on its own plate first, span table beneath, both at content width so a bar sits above its row |
| `/tools` | the tool-health table on one plate, the limit-hits bar chart on the next, drawn to the same width |
| `/conversations` | one table: id, user, started, messages, active, last activity — **five of the six** (id, user, started, messages, last activity) carry `class="num"`, right-aligned and tabular; `active` does not, its content being the word `yes`/`no` (REQ-V180-DSH-03) |
| `/conversations/<id>` | a **two-column transcript**: a fixed 7rem left rail carrying role and turn (with the trace link when there is one), and a single measure column of message text; one left edge to track down, one 1px `--rule` between messages, no bubbles. In the rail, turn id and timestamp carry `class="num"`; the role word, the trace link and the message text do not |

**What this deliberately is not.** Warm cream, a serif display face, card
shadows, ALL-CAPS eyebrows, middle-dot meta strings, monospace data, an arrow
after link text — all rejected; REQ-V180-DSH-04's list is the closed one.

---

## Cross-review log (Appendix C of `spec-v1.8.0.md`)

All three round tables, moved here as overflow (REQ-V180-EC-01). Appendix C's
heading, its closing tally and its `round_limit` note stay in the spec.

### Round 1 of at most 3 — against the whole spec (`58d4553`); 24 findings, 24 accepted (7 adapted), 0 rejected

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R1-1 | Crit | CHAT-04, CHAT-07 | accepted, adapted | the signal is a frozen `AgentOutcome` returned by a new `run_agent_outcome`; `run_agent` stays a `-> str` one-line wrapper, so no test call site moves |
| R1-2 | High | CHAT-04, `T-V180-CHAT-04` | accepted, adapted | the same change removes text matching entirely: `is_failure_reply`, its closed table and `_LLM_ERROR_PREFIX` are gone, so decoration and truncation cannot mis-classify |
| R1-3 | High | CHAT-02, CHAT-04 | accepted | new REQ-V180-CHAT-08 fixes the order — outcome, then reply, then delete only when the send returned `True`; `_send` gains an additive `-> bool` |
| R1-4 | High | CHAT-03, CHAT-06 | accepted | CHAT-03 now promises only the attempt: a rejected edit leaves the previous status text, logs once, and is an accepted outcome |
| R1-5 | Med | CHAT-01 | accepted | `delete_message` is annotated `-> bool` and the client's unwrapped-`result` contract is stated; `_call_with_retry` widens to `-> dict \| bool` |
| R1-6 | High | CHAT-05, CHAT-06 | accepted | the typing worker makes one **unretried** `tg.call` per tick and checks the stop event and the elapsed clock immediately before each attempt |
| R1-7 | High | CHAT-05, `T-V180-CHAT-06` | accepted | `stop()` sets the event **and joins**, bounded by `TYPING_JOIN_TIMEOUT_S = 1.0`; a timeout is logged and the caller proceeds |
| R1-8 | Med | CHAT-05, CHAT-06 | accepted | one attempt per tick makes the ceiling arithmetic true: at most `ceil(llm_timeout_s / TYPING_INTERVAL_S)` requests, no bursts |
| R1-9 | Med | CHAT-05, `T-V180-CHAT-06` | accepted | the seams are named constructor parameters — `interval_s`, `ceiling_s`, `monotonic`, `stop_event` — with their production defaults, so no test sleeps |
| R1-10 | High | SEC-01, CONV-06 | accepted | SEC-01 is stated per sink: `redact()` everywhere, `esc()` on the HTML sink only, because `json.dumps` escapes and HTML-escaping would corrupt the mirror |
| R1-11 | Crit | SEC-02, `T-V180-SEC-02` | accepted, adapted | the bound is enforced, not proved: the page builder accumulates rendered **bytes** against `TRANSCRIPT_PAGE_BUDGET_BYTES = 1.5 MiB`, and the test uses a 4-byte / escape-expanding fixture |
| R1-12 | Med | SEC-02 | accepted | the 2000 governs the escaped message text alone; the marker and the original-length note are additional and counted by the byte budget |
| R1-13 | High | CONV-02, `T-V180-CONV-02` | accepted, adapted | the page is selected **by turn**: a turn window bounded `limit + 1`, turns taken whole, "up to `limit` messages, extended to the end of the last turn" |
| R1-14 | High | CONV-04 | accepted | the window fetches one turn beyond the page; that probe alone decides the next link and is discarded before rendering (`has_more`) |
| R1-15 | Med | CONV-04, CONV-07 | accepted | a fourth reader, `conversation_row`, decides the 404; an existing conversation with no messages answers 200 with the empty state |
| R1-16 | Med | CONV-05 | accepted | the link is the `trace_id` of the lowest `llm_calls` `id` for the turn with a non-null value, then the lowest in `tool_calls`, then none |
| R1-17 | High | DSH-03, CONV-03 | accepted | `class="num"` is a property of the **column**, decided by its data cells and carried on the `<th>` and every `<td>`; the word-valued-`<th>` prohibition is gone |
| R1-18 | Med | DSH-04, `T-V180-DSH-02` | accepted | the anti-pattern scan is scoped to the static chrome through a named sentinel-intersection seam, excluding interpolated message content |
| R1-19 | Med | EC-10 | accepted | `v180-dashboard-bind-widened` is replaced by `v180-transcript-budget-removed`, a mechanism this release introduces; the bind keeps its pre-existing `T-V160-SRV-*` coverage |
| R1-20 | High | AGT-03, T1, T7 | accepted | AGT-03 splits by when the fact becomes true: T1 writes the layout line only, T7 writes every count-bearing line once, after T6 |
| R1-21 | Crit | REV-04, EC-09 | accepted, adapted | the stop route has two stages; from T2 on there is no revert, no test deletion, and the collected count is whatever the tree has |
| R1-22 | Crit | REV-04, VER-01 | accepted, adapted | the version bump moves to T9, the last task before tagging, so a stop at any earlier point needs no revert and VER-01's stop evidence is true by construction |
| R1-23 | High | REV-04 items 5–6 | accepted, adapted | item 5's evidence commit is explicitly permitted on the stop route; the ban on an evidence-only commit is named as the normal route's rule |
| R1-24 | High | REV-02, EC-09, T10 | accepted | `lint-docs` is re-run against the final docs-only commit and the tag goes on **that** commit; the other gates are not re-run, and the spec says why |

**Round 1: 24 findings, 24 accepted (7 adapted), 0 rejected.** New
requirements: `REQ-V180-CHAT-08`; `REQ-V180-CHAT-07` was deleted and its id
reused for the outcome contract, and `T-V180-CHAT-09` is new.

**Two standing lab rulings were overturned in this round**, and are recorded
as such rather than quietly dropped:

- **R3 — "a structured return from `run_agent` is rejected on cost"** — the
  ruling missed the third shape: a new `run_agent_outcome` beside it, zero test
  churn, so the cost that justified the rejection does not exist (R1-1, R1-2).
- **The single-stage stop route** — written for a stop before any commit and
  impossible after one. It demanded the T0 test floor, an unwritten source
  tree, a pre-bump `pyproject.toml` and an evidence commit another item
  forbade (R1-21…R1-23).

### Round 2 of at most 3 — against the whole spec (`e537335`); 16 findings, 16 accepted (6 adapted), 0 rejected

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R2-1 | Crit | CONV-02, -04, -06, -07, SEC-02, `T-V180-CONV-02` | accepted, adapted | **three findings collapsed into one ruling** — a byte budget that stops mid-page cannot coexist with an offset counting whole turns: pagination is now an opaque `(turn_id, id)` **cursor**, a turn larger than the budget is split and marked *continued*, the previous link and `_parse_offset` are **deleted**, and an unparseable or unknown cursor is a 400 |
| R2-2 | Crit | RPT-02 item 10, REV-02, EC-09 | accepted | the report records the tag **name** and the gate results for its own tree; the tagged sha and the post-tag `lint-docs` code go to the closing message and the uncommitted handoff copy |
| R2-3 | Crit | REV-04, EC-09 | accepted | the stop stages are defined by **whether any source or test file has been committed**, with no task number in either definition |
| R2-4 | High | CHAT-05, CHAT-08 | accepted, adapted | the indicator is stopped and joined **before** the reply is sent, so a stale action can only land before it and the reply itself clears typing |
| R2-5 | High | CHAT-05, EC-05 | accepted | `TYPING_REQUEST_TIMEOUT_S = 2.0` on the read and connect bounds, `TYPING_JOIN_TIMEOUT_S = 3.0`; the request bound is shorter than the join |
| R2-6 | High | SEC-02, CONV-06 | accepted | the 2000-character cap is over the **redacted plain text, before escaping**, identically on both sinks; the byte budget is the separate bound, on rendered output |
| R2-7 | High | SEC-02 | accepted | `TRANSCRIPT_PAGE_SUFFIX_BYTES = 4096` is reserved for the marker, the links and the closing chrome and subtracted before the first row is admitted |
| R2-8 | High | EC-07, §12.1 | accepted | every delegate cell recomputed against the closed exemptions: T1, T7 and T8 now delegate, T0 and T10 are *artefacts only*, and nine of eleven tasks delegate |
| R2-9 | High | DSH-04, `T-V180-DSH-02` | accepted, adapted | the chrome is one render against an all-sentinel fixture, not an intersection of two renders |
| R2-10 | High | EC-10, REV-01 item 8 | accepted | red-before is the mutation gate's own mutate → red → revert cycle, run at T6 once the code exists |
| R2-11 | Med | CHAT-05, E4 | accepted | the first typing action is sent immediately on start, then every 4.0 s |
| R2-12 | Med | CHAT-01, CHAT-02 | accepted | `finish(ok=True)` clears `_message_id` only when the unwrapped result is exactly `True`; anything else is a failed delete |
| R2-13 | Med | CONV-02, CONV-05 | accepted | `conversation_turn_traces(conn, conv_id, turn_ids)` returns mappings for the page's turns only |
| R2-14 | Med | DSH-03, CONV-03, `T-V180-DSH-01` | accepted, adapted | column kind is **declared** in each builder's column spec, never inferred from cell data; a placeholder cell keeps its column's class |

**Round 2: 16 findings, 16 accepted (6 adapted), 0 rejected.** New
requirements: none. Three findings — the byte budget against the turn offset,
the unusable previous link, the undefined out-of-range offset — share one root
cause and are ruled once, as R2-1.

### Round 3 of at most 3 (final) — against the whole spec (`a8a3db9`); 10 findings, 10 accepted (1 adapted), 0 rejected

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R3-1 | Crit | CONV-02, -04, -06, `T-V180-CONV-02` | accepted | `conversation_messages` returns `(rows, next_cursor)` — the `(turn_id, id)` of the first message it did not return, `None` at the end; `has_more` is gone from the reader, from both sinks and from the JSON payload, its meaning being `next_cursor is not None` |
| R3-2 | High | CONV-04, CONV-07 | accepted | a cursor is validated by an exact `(conv_id, turn_id, id)` lookup, never a range probe; a pair naming no message — `1-999999` — is a 400 through `_bad_request`, not a 200 that skips into a later turn |
| R3-3 | High | CONV-04, SEC-02 | accepted | turn admission is atomic and ordered: measure the whole turn's rendered bytes, admit it whole if it fits, stop the page if it does not and a turn is already there, and split only when the page is empty — the one split case |
| R3-4 | High | CONV-02 | accepted | the message fetch is bounded in SQL by `LIMIT TRANSCRIPT_FETCH_ROWS_MAX + 1`, `TRANSCRIPT_FETCH_ROWS_MAX = 2000`; hitting the cap is R3-3's split case, not an error |
| R3-5 | High | CHAT-05, CHAT-08, EC-05 | accepted, adapted | `TYPING_REQUEST_TIMEOUT_S` now binds **all four** `httpx.Timeout` phases — superseding R2-5's two — and `call` gains `connect_timeout`, `write_timeout` and `pool_timeout`, each defaulting to today's 10.0; the 3.0 s join stays and the residual is **named**: at most one stale typing action, ~5 s after the reply, accepted, with the worker re-checking the stop event after its request returns |
| R3-6 | High | REV-02, EC-04, EC-09 | accepted | `gitleaks-tree` is re-run on the evidence-only commit, before the tag, beside `lint-docs`, so the final report, Telegram post and usage rows are themselves scanned; a finding there withholds the tag |
| R3-7 | High | SEC-02, `T-V180-SEC-02` | accepted | the byte accumulator is **seeded** with the page's measured chrome plus the reserved suffix, so the budget bounds the whole response; the worst-case assertion measures the complete body |
| R3-8 | Med | EC-10, `v180-status-signal-inverted` | accepted | a new `T-V180-CHAT-10` drives `process_update` with a successful and a structurally failed outcome, asserting opposite status behaviour, and owns the mutation; `T-V180-CHAT-02`/`-03`, which drive `finish` directly, no longer claim it |
| R3-9 | Med | SEC-01, `T-V180-SEC-01` | accepted | the security test injects a registered secret into **every** rendered message-derived field — `content`, `role`, `tool_call_id` — so redaction cannot pass by protecting one column |
| R3-10 | Med | `T-V180-SEC-01` | accepted | the escaping assertion is scoped to HTML; the JSON assertion is stated separately — the literal redacted text as `json.dumps` encodes it, safe by content type and `default-src 'none'`, not by escaping |

**Round 3: 10 findings, 10 accepted (1 adapted), 0 rejected.** New
requirements: none; one new test id, `T-V180-CHAT-10`. R3-5 supersedes R2-5's
two-phase bound. **The log closes here on `round_limit`, not on a clean
round** — see Appendix C's opening paragraph.
