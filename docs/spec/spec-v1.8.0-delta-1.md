# spec-v1.8.0-delta-1 — the gate matrix

Overflow file of `docs/spec/spec-v1.8.0.md`, created because that file is at
`standards/workflow.md` §12's ~80 KB ceiling (REQ-V180-EC-01, "The spec's own
budget"). It is **normative**: REQ-V180-EC-12 makes this table the one
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
(`tests/test_v15_standards.py:1727-1741`) parses, in place of
`spec-v1.7.0.md`. Nothing else belongs in this file, beyond round 1 of
`spec-v1.8.0.md`'s Appendix C below, moved here as round 2's overflow
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

## Cross-review log — round 1 (Appendix C of `spec-v1.8.0.md`)

Round 1's table only, moved here as round 2's overflow (REQ-V180-EC-01).
Appendix C's heading and its round-2 section stay in the spec.

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
