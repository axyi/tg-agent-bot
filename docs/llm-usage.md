# LLM usage

| # | Stage | Model | Tokens | Cost |
|---|-------|-------|--------|------|
| 1 | spec authoring (writer agent, 3 iterations incl. gate-chain and exec-recipe proof runs) | claude (lab session) | ~213k (harness-reported aggregate; in/out split not exposed) | — (flat-rate session) |
| 2 | spec review (reviewer agent, clean context, 3 passes) | claude (lab session) | ~270k (aggregate) | — |
| 3 | implementation step 1 — bootstrap: `.python-version`, `pyproject.toml`, `.gitignore`, `.env.example`, `uv lock`, `uv sync --locked` | claude-opus-5 | unknown | unknown |
| 4 | implementation step 2 — all test files, `conftest.py`, `fakes.py`; first `pytest` run observed failing | claude-opus-5 | unknown | unknown |
| 5 | implementation step 3 — `config.py` | claude-opus-5 | unknown | unknown |
| 6 | implementation step 4 — `storage.py` | claude-opus-5 | unknown | unknown |
| 7 | implementation step 5 — `tools.py` part 1 (`run_command`, `_Capture`, `_drain`) | claude-opus-5 | unknown | unknown |
| 8 | implementation step 6 — `tools.py` part 2 (skills, tool specs, dispatch) + `skills/*.md` | claude-opus-5 | unknown | unknown |
| 9 | implementation step 7 — `llm/base.py`, `llm/lmstudio.py`, `llm/openrouter.py`, `llm/__init__.py` | claude-opus-5 | unknown | unknown |
| 10 | implementation step 8 — `agent.py` | claude-opus-5 | unknown | unknown |
| 11 | implementation step 9 — `bot.py` (Telegram layer, poll loop, `--selftest`) | claude-opus-5 | unknown | unknown |
| 12 | implementation step 10 — `README.md`, prompt log, this table | claude-opus-5 | unknown | unknown |
| 13 | implementation step 11 — the four acceptance gates + code review | claude-opus-5 | unknown | unknown |
| **Σ** (rows 3–13, one continuous session) | | claude-opus-5 | in 14.78M (160 uncached + 260k cache-write + 14.52M cache-read), out 148.5k — measured from the local session transcript | ≈$12.60 (estimate at public API prices; actual billing: flat-rate subscription) |
| 14 | spec-v1 authoring (writer + reviewer agents, separate session) | claude-fable-5 (lab session) | ~unknown (separate session; not measured here) | — |
| 15 | v1 step 1 — preconditions: `.env` key-name checks, `docker pull python:3.13-slim`, LM Studio and OpenRouter model queries, `OPENROUTER_MODEL` appended; `.env.example`, `.gitignore` | claude-opus-5 | unknown | unknown |
| 16 | v1 step 2 — the four new test files plus the section-9.1 amendments; first `pytest` observed failing (6 collection errors) | claude-opus-5 | unknown | unknown |
| 17 | v1 step 3 — `config.py` (new variables, secret registration, sandbox placement) | claude-opus-5 | unknown | unknown |
| 18 | v1 step 4 — `storage.py` (schema v2 + migration, summaries, budget-aware loader, DB chmod) | claude-opus-5 | unknown | unknown |
| 19 | v1 step 5 — `tools.py` (docker argv/probe/runner, `_run_process`, `fetch_url`, audit, catalog) and both skills | claude-opus-5 | unknown | unknown |
| 20 | v1 step 6 — `llm/base.py`, `llm/lmstudio.py`, `llm/openrouter.py`, `llm/failover.py`, `llm/__init__.py` | claude-opus-5 | unknown | unknown |
| 21 | v1 step 7 — `agent.py` (repair rounds, truncation notice, token budget, interrupt, goals, summarizer) | claude-opus-5 | unknown | unknown |
| 22 | v1 step 8 — `bot.py` (pipeline order, rate limiter, commands, status message, send retry, `--selftest-live`) | claude-opus-5 | unknown | unknown |
| 23 | v1 step 9 — `README.md`, `AGENTS.md` | claude-opus-5 | unknown | unknown |
| 24 | v1 step 10 — five gates, Appendix-B acceptance probes, clean-context review, fix cycle 1/5, report | claude-opus-5 | unknown | unknown |
| **Σ** (rows 15–24, one continuous session + the review subagent) | | claude-opus-5 | in 35.51M (280 uncached + 692k cache-write + 34.82M cache-read), out 243.3k — measured from the local session transcripts | ≈$27.82 (estimate at public API prices; actual billing: flat-rate subscription) |
| 25 | v1.1 main session — preconditions, section-9.2 tests + section-9.1 amendments (observed the expected failures), the four mutation-check proofs, `config.py`/`storage.py`/`agent.py`/`tools.py`/`bot.py` in the order of section 8, five gates, Appendix-B live driver (C1–C7 + B1/B3/B4/B10 regression), documentation (`.env.example`, `.gitignore`, README, both spec doc-fixes, prompts 03/04/05, `report-v1.md` reconciliation), the review's `_record_sandbox_quota` completeness fix, the report, this table, and the final commit | claude-sonnet-5 | in 504 (uncached) + 534,939 (cache write) + 81,416,730 (cache read), out 229,845 — measured from the local Claude Code session transcript, per-request `usage` fields deduplicated by `requestId`, re-measured immediately before the commit | ≈$19.92 (estimate at public API prices: $2/$10 per MTok in/out, cache write ×1.25, cache read ×0.1; actual billing: flat-rate subscription) |
| 26 | v1.1 code-review subagent (`code-reviewer`, clean context, prompt `docs/prompts/06-code-review-v1.1.md`) | claude-sonnet-5 (subagent default) | 158,889 total (harness-reported aggregate; in/out/cache split not exposed to the parent session — unlike rows 1–24, the transcript backing this number is an async task-output file the harness instructs the parent session not to read) | not computed — the split needed for the cache-aware formula above is unavailable |
| **Σ** (rows 25–26, one `go` run) | | claude-sonnet-5 | 82,182,018 (row 25) + 158,889 aggregate (row 26) | ≈$19.92 + unknown (row 26) |
| 27 | v1.2 main session — precondition checks (incl. the LM Studio gate-5 exception), section-10.2 tests + section-10.1 amendments (observed red before green), `devtools/mutation_check.py` and its own test suite built before use, `config.py`/`storage.py`/`agent.py`/`tools.py`/`bot.py` in section-9 order, six gates (incl. one fix-and-rerun of the mutation gate itself — see report Fix cycles), Appendix-B live driver (D1–D8 + C1/C3/C4/C6 regression), documentation housekeeping (this table, `docs/plan.md`, both v1.1 report corrections, `AGENTS.md`'s gate list), the review, the report, and the final commits | claude-sonnet-5 | not computed — this run's harness did not expose a local session transcript to re-measure from at commit time (see note below); the per-column split was never reconstructed | ≈$33.11 (estimate at public API prices, measured after the fact from the local session transcript — see note below; actual billing: flat-rate subscription) |
| 28 | v1.2 code-review subagent (`code-reviewer`, clean context, prompt `docs/prompts/08-code-review-v1.2.md`) | claude-sonnet-5 (subagent default) | not computed — same async task-output constraint as row 26 | not computed |
| **Σ** (rows 27–28, one `go` run) | | claude-sonnet-5 | not computed | ≈$33.11 + unknown (row 28) |
| 29 | spec-v1.3 authoring — writer pass in the lab session plus two clean-context reviewer subagents (design review, then a consistency re-review after 25 fixes); executor of the spec is `claude-opus-5`, not yet run | claude-fable-5 (lab session; reviewers on the subagent default) | ≈258k subagent aggregate (≈134k design review + writer helpers, 123,557 consistency re-review; harness-reported, in/out split not exposed) + a main-session share that is not isolatable from the lab session transcript (that session also carried unrelated lab work) | — (flat-rate session) |
| 30 | v1.3 implementation run — the whole `go docs/spec/spec-v1.3.md` run across its four commits: stage A (v1.2 carry-over, observability, pricing, benchmark harness, dashboard, mutation entries), the baseline benchmark and the OpenRouter smoke, the token audit, stage C (optimizations O1–O6 incl. the O5 probe), the optimized run and the gate report, the six gates at C1/C3/C4, two clean-context reviews with one fix round each, and the C4 documentation | claude-opus-5 | unknown | unknown |
| 31 | v1.3 task subagents — 18 of the run's 19 prompt files (`docs/prompts/10-v13-TA1-carryover.md` … `27-v13-TC9-docs.md`; the 19th is row 30's own `09-go-spec-v1.3.md`), including the two `code-reviewer` clean-context reviews (`16-…`, `25-…`) and the audit subagent (`18-…`) | claude-opus-5 | unknown | unknown |
| **Σ** (rows 30–31, one `go` run) | | claude-opus-5 | unknown | unknown |
| 32 | v1.3 verify-run docs fixes (prompt 30): trimmed `docs/reports/tg-post-v1.3.md` under the 1500-char limit, added the `Model reason` bullet required by `standards/reporting.md` to all 21 v1.3 prompt files (`09-go-spec-v1.3.md`–`29-v13-TD2-tg-post.md`), and this row | claude-sonnet-5 | unknown | unknown |
| 33 | spec-v1.4 authoring — design in the lab session after `/verify-run` of v1.3, one fact-finding subagent over the v1.3 reports and bench files, one writer subagent for the draft, two markers resolved in the lab session (OpenRouter `reasoning` field, LM Studio model-level fallback), then four rounds of Codex cross-review (`gpt-5.6-sol`, 31 findings, all accepted; Appendix C of the spec) each applied by one clean-context subagent; executor of the spec is `claude-sonnet-5`, not yet run | claude-fable-5 (lab session; fact-finding on `claude-sonnet-5`, writer and the four fix passes on `claude-opus-5`; challenger OpenAI `gpt-5.6-sol`) | ≈1.11M subagent aggregate (≈120k fact-finding, ≈300k writer, ≈690k across the four fix passes; harness-reported, in/out split not exposed) + a main-session share that is not isolatable from the lab session transcript; Codex: 4 requests × ≈25k prompt tokens, output ≤ 16k each | — (flat-rate session; Codex API metered, amount not captured) |

Notes: rows 1–2 are the authoring cost of the specification, recorded per
the lab reporting standard; runtime data and secrets are never logged here.
Rows 3–13 are the implementation run (`go docs/spec/spec-v0.md`, prompt
`docs/prompts/01-go-spec-v0.md`), one row per stage of the spec's section 4
implementation order. The run executed as one continuous agent session; the
harness does not expose per-request input/output token counts or money cost to
the agent, so the per-step cells stay `unknown`. The Σ row was measured
afterwards from the local Claude Code session transcript (per-request `usage`
fields, deduplicated by request id); cost estimated at Anthropic's public API
price list (claude-opus-5: $5/$25 per MTok in/out, cache write ×1.25, cache
read ×0.1) — the session actually ran on a flat-rate subscription. The table keeps
its original five columns — the spec's REQ-EC-11 names a six-column variant
(`Tokens in` / `Tokens out`), but the instruction to keep the existing columns
takes precedence over the parenthetical.

Rows 15–24 are the spec-v1 implementation run (`go docs/spec/spec-v1.md`, prompt
`docs/prompts/03-go-spec-v1.md`), one row per stage of that spec's section-8
implementation order. As in the v0 run the harness exposes no per-request
counts to the agent, so the per-step cells stay `unknown`; the Σ row was measured
afterwards from the local Claude Code transcripts — the main session (108
requests) plus the `code-reviewer` subagent's own transcript (29 requests) —
keeping the final streaming `usage` row per request id. Cost is estimated at
Anthropic's public price list for claude-opus-5 ($5/$25 per MTok in/out, cache
write ×1.25, cache read ×0.1). Inference the *bot* itself spent during the
Appendix-B probes is separate and negligible: a handful of LM Studio calls
(local, free) and two OpenRouter calls on `google/gemini-2.5-flash-lite` at
$0.10/$0.40 per 1M tokens — well under a cent.

Rows 25–26 are the spec-v1.1 implementation run (`go docs/spec/spec-v1.1.md`,
prompt `docs/prompts/05-go-spec-v1.1.md`), covering the whole patch end to
end: tests, implementation, five gates (one of which was additionally re-run
with `docker` removed from `PATH` to confirm no test shells out to a real
daemon), the Appendix-B live driver script, the `code-reviewer` subagent's
review, its one fix cycle (1/5), and this report. Unlike the v0 and v1 runs,
this harness exposes the full per-request `usage` block directly in the
local session transcript, so row 25 needed no separate after-the-fact
reconstruction — the numbers above are a direct aggregation of that file
(249 requests as of the re-measurement taken immediately before this commit),
not an estimate. That re-measurement is itself the final action before the
commit records it, so row 25 necessarily excludes the handful of tokens this
commit step itself will spend — a residual, unavoidable undercount rather than
a stale one. The subagent call is asynchronous and its
transcript lives in a task-output file this session is explicitly instructed
not to read (to avoid pulling tool-call noise into context), so row 26 uses
only the aggregate the harness reported back in the task-completion
notification. Inference the *bot* itself spent during the Appendix-B driver
is separate and effectively free: LM Studio is local, and no OpenRouter call
was made at all — the throwaway `OPENROUTER_API_KEY` was a synthetic canary
that was deliberately never validated (`LLM_PROVIDER=lmstudio`,
`LLM_FAILOVER=off`).

Rows 27–28 are the spec-v1.2 implementation run (`go docs/spec/spec-v1.2.md`,
prompt `docs/prompts/07-go-spec-v1.2.md`), covering the security-audit patch
end to end: the section-10.2 tests and section-10.1 amendments, the
`devtools/mutation_check.py` gate built before it verified a single fix, the
five security fixes of section 5, six gates including a fix-and-rerun of the
mutation gate itself (see `report-v1.2.md`'s Fix cycles — not counted against
the 5-cycle repair budget, since it happened before the gates were run as the
reported sequence), the Appendix-B live driver (D1–D8 plus the C1/C3/C4/C6
v1.1 regression), documentation housekeeping, the `code-reviewer` subagent's
review, and the report. Unlike row 25, this session's **token split** stays
`not computed` rather than reconstructed or estimated: this run did not
re-measure a local transcript immediately before the commit the way row 25's
run did, and reporting an unmeasured number as if it were the same kind of
figure would misrepresent it. The **cost** cell is no longer `not computed`
(REQ-V13-CO-07): ≈$33.11, measured after the fact from the local session
transcript at the same public API prices as row 25, with that source named in
the cell — actual billing remains the flat-rate subscription. Inference the
*bot* itself spent during the
Appendix-B driver is separate and effectively free: LM Studio is local for
the ordinary-message check in D2, and no OpenRouter call was made — D1's and
C1's registered secret was a synthetic canary never sent through the LLM
client, and D2's ordinary-turn check used a scripted `FakeLLM`, not a live
provider call.

Row 29 is the authoring cost of `docs/spec/spec-v1.3.md`, recorded before
the `go` run so that the implementation rows that follow start from a known
baseline. It is an aggregate estimate, not a measurement of the kind rows
15–25 give: the writing happened in the lab session's main context, which
`tools/session-usage.py` cannot split by task, and the two reviewer
subagents only report their totals. No inference was spent by the bot
itself; the only live checks were `pytest --collect-only` (326 tests at
`1ecc35e`) and a `len()` of `agent.SYSTEM_PROMPT`, both offline.

Rows 30–31 are the spec-v1.3 implementation run (`go docs/spec/spec-v1.3.md`,
prompt `docs/prompts/09-go-spec-v1.3.md`), covering the token-economy patch end
to end — the four commits `69ebc75`, `f0572c8`, `c11f590` and the C4
documentation commit — with **19 prompt files** logged for this run
(`09-go-spec-v1.3.md` through `27-v13-TC9-docs.md`). The prompt count is the
only directly observable figure: every token and cost cell is the literal
`unknown`, never an estimate and never a number without a named source
(REQ-V13-RPT-06). The executor has no API to its own session usage, and this
run's harness displayed no usage or cost line to it — unlike row 25, where the
session transcript was available for a direct re-measurement, there is nothing
here to cite. The measured values are filled in after the run by the maintainer
from the lab's session transcripts (`tools/session-usage.py`, outside this
repository) and recorded in `economics.md`; `docs/reports/report-v1.3.md`'s
"Cumulative: v1 → v1.3" section copies whatever this table says, `unknown`
cells included. Inference the *bot* itself spent is measured and reported
separately in `docs/reports/report-v1.3.md`: the two full benchmark runs at
$0.09675 and $0.084729 and the O5 probe at $0.001876 are all
reference-priced ESTIMATES over free local LM Studio inference
(REQ-V13-PRC-03), and the only real money spent was the OpenRouter smoke's
$0.000212 on `google/gemini-2.5-flash-lite` — one S02 run, capped at
`--max-cost-usd 0.50`.
