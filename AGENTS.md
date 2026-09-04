# tg-agent-bot — agent rules

Telegram bot turned into an LLM agent: minimal harness, bounded agent loop,
exec tool, skills (course assignment 3).

Standards summary (self-contained): SDD — the spec is the contract; atomic commits (one prompt → one commit); review in a clean context; deterministic gates before done.

## Spec

SDD: implementation task → spec first (`docs/spec/spec-vN.md`); the spec is
the contract.

**Spec drift:** architecture, tests/interfaces, behaviour, limits, security
posture, storage schema or the command set change → update the relevant
`docs/spec/spec-vN.md` delta (or add a new one) in the same commit. A PR that
changes behaviour without touching `docs/spec/` is incomplete.

## Stack

- Language: Python 3.14 (pinned via .python-version; requires-python ">=3.13,<3.15"), environment managed by **uv**
- Runtime dependency of the host: the **`docker` CLI** — `exec` runs every
  command inside a disposable container and never falls back to the host
- Frameworks/libs: `httpx` (Telegram Bot API and LLM HTTP calls),
  `python-dotenv` (config from `.env`); standard library for everything else —
  no bot framework, no agent framework
- Tooling: uv (lockfile-pinned), pytest, ruff; local quality gates add
  gitleaks, semgrep, trivy, skylos (shadow) and rtk (operator
  convenience, not a gate) — see "Local quality gates" below
- Platform: Linux
- NEVER add dependencies beyond the allowed list without asking.

## Project layout

- `bot.py` — entry point: Telegram long-polling loop, `--selftest` mode
- `agent.py` — the bounded agent loop (plan → tool call → observation), with a
  hard iteration cap
- `llm/` — inference behind one swappable interface (local ↔ cloud provider),
  hard timeouts, clean error path
- `llm/pricing.py` — price snapshot and the per-call cost resolver (no I/O
  beyond the one startup fetch, no global state)
- `tools.py` — tool definitions, including the exec tool
- `storage.py` — conversation/state persistence
- `metrics.py` — pure functions over the `llm_calls`/`tool_calls` rows; the one
  implementation `/stats`, the benchmark report and the dashboard all use
- `skills/` — skill definitions loaded by the agent
- `tests/` — pytest suite
- `devtools/` — operator tooling, never imported by the bot: `bench.py`
  (live token benchmark), `dashboard.py` (static HTML report),
  `mutation_check.py` (the mutation gate)
- `docs/` — spec, prompt log, reports, token accounting

Context boundaries: agents work inside this repository only. NEVER read or edit
anything above the repository root.
The exec tool runs untrusted model output — it executes only inside the
sandbox described in the spec, NEVER against the host working tree.

## Commit format

- Conventional commits: `feat:`, `fix:`, `docs:`, `style:`, `refactor:`,
  `perf:`, `test:`, `build:`, `ci:`, `chore:`, `revert:`. Header ≤ 72
  Unicode characters, no trailing period.
- **One prompt → one commit.** Reference the prompt file in the body:
  `(prompt: docs/prompts/NN-<slug>.md)`.
- NEVER mix results of different prompts in one commit or MR.
- Enforced automatically by the `commit-msg` hook
  (`.githooks/commit-msg` → `devtools/checks.py commit-msg`) from
  spec-v1.5 T8 on; `Merge`/`Revert`/`fixup!`/`squash!` subjects bypass
  every check above.
<!-- SYNC: canonical text lives in standards/workflow.md §6 (lab repo); this copy is intentionally self-contained -->

## Branch strategy

- One task → one branch: `feat/<slug>`, `fix/<slug>`, `docs/<slug>`,
  `test/<slug>` or `chore/<slug>`.
- Exception: a single-agent run implementing a whole spec end-to-end may
  commit directly to `main`; branches are for parallel or partial work.
- Parallel agent work: **one git worktree per agent**, merge via MR; NEVER two
  agents in one working tree.
- Enforced automatically by the `pre-commit`/`pre-push` branch-name
  check from spec-v1.5 T8 on; `main` and a detached HEAD warn rather
  than fail (a solo end-to-end run is permitted).

## Gates — run before reporting success

All six MUST exit 0, run in this order:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
uv run --locked python devtools/mutation_check.py
```

Gates 1–4 are unconditional and offline. Gate 5 needs the live environment
(a provisioned `.env`, a reachable Docker daemon with the sandbox image pulled,
LM Studio and an OpenRouter key); it spends no inference tokens and sends no
Telegram message. **Gate 5 must be fully green at every commit, including its
`lmstudio` check** — the v1.2 "record the failure and proceed" exception is
withdrawn: an unreachable LM Studio is a blocked run, not a noted one, because
the benchmark measures against it. Gate 6 is the mutation-testing gate
(`devtools/mutation_check.py`): offline, but slow (minutes, since it reruns
the test suite once per mutation) — 72 entries as of spec-v1.5;
`--select <prefix>` runs a named subset (mutually exclusive with
`--only`).

## Local quality gates (spec-v1.5)

`devtools/checks.py` is the single entry point for every check this
release adds — hooks call it, gates call it. `core.hooksPath` points at
the versioned `.githooks/` (committed, never `.git/hooks/`):
`commit-msg` and `pre-commit` run on every local commit, `pre-push` on
every push. `config/quality_gates.yaml` is the sole authority for gate
membership, severity thresholds and tool pins — never a literal inside
`checks.py`. Beyond the six gates above: `checks.py doctor` (every
pinned tool at its exact version, fails closed on a newer one too),
`checks.py lint-docs` (prompt header/block format, the report's ledger
row), `checks.py replay --range <rev>..<rev>` (re-verifies historical
commits by reading git objects only, never touching the working tree),
plus four scanners: gitleaks (secrets, committed content only, blocks
at any severity anywhere — not diff-scoped), semgrep and trivy (SAST
and filesystem vuln/misconfig scanning, diff-scoped, blocking), and
skylos (dead code, diff-scoped, shadow — findings reported, never
blocking).
`checks.py run --profile pre-commit|pre-push|full` wires them
into three profiles; `install_hooks.py [--check]` installs/verifies the
chain itself. `--no-verify` and any other hook bypass are forbidden.

## Benchmark

Tokens are measured live, never by the test suite (all LLM traffic in pytest is
faked):

```bash
uv run --locked python devtools/bench.py run --tag <tag> --repeats 3
uv run --locked python devtools/bench.py report --baseline A.json [--candidate B.json] --out docs/reports/bench-<name>.md
```

**A behaviour change that touches tokens — prompts, tool schemas, tool output,
history assembly, routing — MUST be accompanied by a benchmark run before and
after, compared with `report --candidate`.** Both runs use the same provider,
model and context length; `report --gate` machine-checks that (exit 2 when the
pinned meta fields differ) so "same configuration" is never merely asserted.
Scenarios are frozen once a baseline exists — changing `bench_scenarios.py`
invalidates every file measured against it.

## go protocol

<!-- SYNC: canonical text lives in standards/workflow.md §9 (lab repo); this copy is intentionally self-contained -->

`go docs/spec/spec-v0.md` is a standing instruction meaning: **execute that spec
end-to-end, following its own Execution contract section.** Concretely:

- run the gate commands above **verbatim** — same commands, same order, no
  substitutions, no "equivalent" invocations;
- on a failing gate, use the bounded fix loop defined in the spec (fixed maximum
  number of iterations); when the budget is exhausted, stop and report instead
  of retrying;
- log every prompt sent to an LLM as its own file in `docs/prompts/`, and record
  tokens/cost in `docs/llm-usage.md`;
- report the task as done only when every gate is green.

The spec is the contract. Where the spec and this file disagree, stop and ask.

## Review

Code review is performed by the `code-reviewer` subagent
(`.claude/agents/code-reviewer.md`) in its own clean context — NEVER
self-review in the writing context.

## Reporting

Every prompt sent to an LLM is logged in `docs/prompts/` (one file per
prompt — `docs/prompts/TEMPLATE.md`'s header-plus-four-block shape from
spec-v1.5 on, enforced by `checks.py lint-docs`), tokens/cost in
`docs/llm-usage.md`, run results in `docs/reports/` (the report's own
"Ledger row" section is lint-checked too, from spec-v1.5 on).

After each run report, generate `docs/reports/tg-post-vN.md` — a
ready-to-paste Telegram post, written in **Russian**: constraints → result →
metrics (executor model — always named; spec tokens, prompts, first-run,
bugs, tokens in/out, cost — when the harness does not expose tokens/cost,
keep that note and add an estimate at public API prices) → a
link to this project's GitHub repository
(https://github.com/axyi/tg-agent-bot). Under ~1500 characters.


## Secrets

Secrets live in `.env` (git-ignored) — the Telegram bot token and the LLM API
key never leave it. NEVER write secrets into code, docs, prompts, or reports.
