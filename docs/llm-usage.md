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
| 34 | spec-v1.4 implementation run — the whole `go docs/spec/spec-v1.4.md` run, prompts 31–41, across T0–T10: preconditions, S01 root-cause repair (H1), bench harness readiness (BEN-03/04/05), the `baseline-v1.4` two-tree measurement, the RSN spike (all five candidates tried, RSN-06 STOP — no honored+shippable reasoning mechanism), REL-01's timeout/budget consistency check, default-selection documentation (STOP branch), mutation coverage for BEN-03/REL-01, the code review's two fixes, Appendix-B acceptance (E5/E8/E10 + D1/D3 regression), and this report/errata/post/table | claude-sonnet-5 (background session) | unknown — this harness does not expose a local session transcript to this session for re-measurement, unlike row 25's run; reconciled later via `tools/session-usage.py` outside this repository, the same way row 27 and rows 30–32 were left for the maintainer | unknown (estimate to follow the same after-the-fact reconciliation, at public API prices, once measured; actual billing: flat-rate subscription) |
| 35 | spec-v1.4 T9 code-review subagent (`code-reviewer`, clean context, prompt `docs/prompts/40-v14-t9-review.md`) | claude-sonnet-5 (subagent default) | 153,558 total (harness-reported aggregate over 62 tool uses; in/out/cache split not exposed to the parent session — same async task-output constraint rows 26/28 hit) | not computed — the split needed for the cache-aware formula is unavailable, as for rows 26/28 |
| **Σ** (rows 34–35, one `go` run) | | claude-sonnet-5 | unknown (row 34) + 153,558 aggregate (row 35) | unknown + unknown (row 35) |
| 36 | `/verify-run` docs-only fixes (prompt 43): added the `Model reason` bullet to `docs/prompts/40-v14-t9-review.md`, corrected `report-v1.4.md`'s gate-table commit count to 9→11 and its `llm-usage.md` contribution to rows 34–35, added the deferred lab-ledger row (applied by the lab as `3c12cc9`) to the same section, and this row | claude-sonnet-5 | unknown | unknown |
| 37 | spec-v1.5 authoring — lab session after `/verify-run` of v1.4: four fact-finding subagents (v1.4 outcome and tool-use evidence, ethinking/idp-concept standards inventory, ai-workflows-concept lessons, upstream version audit), one writer subagent, then three rounds of Codex cross-review (`gpt-5.6-sol`, 28 findings, all accepted; Appendix C of the spec) each applied by a clean-context subagent; executor of the spec is `claude-sonnet-5`, not yet run | claude-fable-5.1 (lab session; fact-finding on `claude-sonnet-5`, writer and the three fix passes on `claude-opus-5`; challenger OpenAI `gpt-5.6-sol`) | ≈1.14M subagent aggregate (≈325k fact-finding, ≈202k writer, ≈690k across the three fix passes; harness-reported, in/out split not exposed) + a main-session share that is not isolatable from the lab session transcript; Codex: 3 requests × ≈27k prompt tokens, output ≤ 16k each | — (flat-rate session; Codex API metered, amount not captured) |
| 38 | spec-v1.5 implementation run — the whole `go docs/spec/spec-v1.5.md` run, prompts 44–62, across T0–T18: `checks.py`'s YAML reader/schema/CC functions, five tool installs (gitleaks/semgrep/trivy/skylos/rtk, each its own atomic commit), scanner wiring (fail-closed, diff-scope partition, shadow mode), the `.githooks/` chain + `install_hooks.py` + `replay` (hooks activated live from T8 on, every later commit passing through them), `checks.py doctor`, the project-local RTK hook, prompt-format `lint-docs`, the three-profile wiring + wall-clock measurement + four `v15-*` mutations, the ruff 0.16.6 and Python 3.14 bumps, the sandbox image digest pin + byte-compared smoke, `AGENTS.md`/`docs/plan.md` sync, the T17 review's own fixes, and this report/post/table | claude-sonnet-5 (background session) | unknown — this harness does not expose a local session transcript to this session for re-measurement, same constraint as rows 27/30–34 | unknown (same after-the-fact reconciliation as row 34, once measured; actual billing: flat-rate subscription) |
| 39 | spec-v1.5 T11 prompt-backfill subagent (general-purpose, clean context: backfilled the 7-bullet header on the 29 historical prompt files `01`–`29` failing `lint-docs` check 1) | claude-sonnet-5 (subagent default) | unknown — the harness-reported aggregate was not captured into this table at the time (its own independent re-verification — a fresh check-1 sweep and the full test suite, run directly by the main session — is recorded in the T11 report section instead) | not computed |
| 40 | spec-v1.5 T16 `AGENTS.md`/`docs/plan.md` diff-review subagent (general-purpose, clean context) | claude-sonnet-5 (subagent default) | unknown — same as row 39, not captured into this table at the time | not computed |
| 41 | spec-v1.5 T17 code-review subagent (`code-reviewer`, clean context, prompt `docs/prompts/61-v15-t17-review.md`) | claude-sonnet-5 (subagent default) | 231,051 total (harness-reported aggregate over 50 tool uses, ~12.8 min; in/out/cache split not exposed to the parent session — same async task-output constraint as rows 26/28/35/44) | not computed — same reason as rows 26/28/35/44 |
| 42 | spec-v1.5 T19 final acceptance — the six gates, `checks.py run --profile full --since <base>`, `checks.py replay --range <base>..<implementation-tip>` (diagnosed both historical exceptions directly rather than assuming a cause), all 12 Appendix-B scenarios (2 driven live against the real repository: E6's trivy-binary-hidden run, E7's shadow/blocking-flip run), the REQ-V15-ACC-02 regression note, and the freeze commit (`docs/reports/report-v1.5.md`'s Final acceptance/attestation/RLM/Fix-cycles/Ledger/Verdict sections, `docs/plan.md`'s v1.5 → complete, this row, prompt 63) | claude-sonnet-5 (background session) | unknown — same constraint as row 38 | unknown (same after-the-fact reconciliation as row 38) |
| 43 | spec-v1.5 post-freeze corrections — two `advisor()` calls after T19 was believed done surfaced (a) `tg-post-v1.5.md`'s stale prompt count and missing T19 summary (fixed in `346a67b`) and (b) `346a67b`'s own commit message citing the wrong prompt (fixed by this row's own commit, prompt 64, which also updates the report's Deviations/Bugs/Ledger sections) | claude-sonnet-5 (background session) | unknown — same constraint as row 38 | unknown (same after-the-fact reconciliation as row 38) |
| 44 | spec-v1.5 post-freeze correction — a third `advisor()` call found the T17 review's own finding count was wrong (report said "5 findings," the enumeration and the reviewer's raw output both show 6: 4 🟡 + 2 🟢); fixed the Review section header, the RLM table's T17 row, `docs/plan.md`'s mention, and recorded `cd88b35`/`6fde12f`'s already-made commit messages as errata (prompt 65) | claude-sonnet-5 (background session) | unknown — same constraint as row 38 | unknown (same after-the-fact reconciliation as row 38) |
| **Σ** (rows 38–44, one `go` run + post-freeze, prompts 44–65) | | claude-sonnet-5 | unknown (row 38) + unknown (row 39) + unknown (row 40) + 231,051 aggregate (row 41) + unknown (row 42) + unknown (row 43) + unknown (row 44) | unknown + unknown + unknown + unknown + unknown + unknown + unknown |

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

Row 34 is the spec-v1.4 implementation run (`go docs/spec/spec-v1.4.md`,
prompt `docs/prompts/31-go-spec-v1.4.md`), covering the whole patch end to
end across 11 commits (`30c7a16`, `f6e634d`, `51ac747`, `818bbde`, `485fcc5`,
`e5fc230`, `718e4eb`, `3fe860a`, `9a32cda`, `64aa5da`, plus this
`advisor()`-follow-up correction commit — report/errata/post/ledger
accuracy fixes, `docs/prompts/42-…`): as in rows 27/30–32, this harness exposed no per-request
usage or cost line to the executor, so every cell stays `unknown` rather
than an invented estimate — reconciled later by the maintainer from the
lab's own session tooling, outside this repository, per RPT-05's
disposition (this run's own T0 deviation 4: `economics.md` sits outside
the repository root, so this run's contribution to it is recorded here
and left for hand reconciliation, never written by the executor). Row 35
is the one subagent this run spawned, the T9 `code-reviewer` review: the
harness reported its 153,558-token aggregate in the task-completion
notification (same shape as rows 26/28), with no in/out/cache split
exposed. Inference the *bot* itself spent during Appendix-B (E5, E10, and
the D1/D3 unchanged-code regression check) is zero: E5 drove
`config.load_config` directly with no LLM call in the path; E10 was a
static file scan; D1/D3 relied on the existing, unchanged automated test
and mutation suites rather than a fresh live drive.
