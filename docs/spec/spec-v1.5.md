# tg-agent-bot — implementation specification v1.5 (engineering standards, local quality gates and dependency refresh)

Complete contract for a **patch release** on the implemented spec-v1.4 state. It
is a **delta specification**: spec-v0 … spec-v1.4 remain in force except where a
requirement here explicitly **amends**, **supersedes** or **extends** them (§2 is
the authoritative amendment table). Everything needed to implement, test and
accept the work is in this file, in the earlier specs, or in files this spec
tells you to change.

Every requirement has a stable `REQ-V15-*` id and is tagged `MUST`, `SHOULD` or
`NON-GOAL`; v1.5 ids never collide with v0…v1.4 ids. `MUST` = required for
acceptance; `SHOULD` = required unless the report names why not; `NON-GOAL` = out
of scope, and implementing it is a defect, not a bonus.

Target platform: **Linux only**. Language **Python**, package manager **uv**.

Executor: **claude-sonnet-5**. Reviewer: **sonnet in a clean context**. This
release has no algorithm and no new bot behaviour — engineering plumbing (hook
scripts, a config-driven runner, four scanner invocations, a version bump) where
every decision is already made below.

**It changes no prompt text, tool schema, tool output shape, history assembly or
routing — so it runs no benchmark** (REQ-V15-EC-06 makes that a rule with a
mandatory escape hatch). It is a patch release of
the *repository*, not the *agent*: bot behaviour changes in one observable
place, the sandbox image (§12), and even there observable tool output must *not*
change. No new features, no opportunistic cleanups; every v0…v1.4 acceptance
property must still hold.

**Provenance**, cited where used: this repository's `AGENTS.md` and the lab
`AGENTS.md` (read *about* through this spec, never opened — REQ-V15-EC-01);
**`/verify-run` on the v1.4 run**, which found `economics.md` has no row a
project-local agent may write (§13); and two sibling projects running gates in
production — `ai-workflows-concept` (shadow-then-promote, fail-closed,
diff-scoped) and `idp-concept` (trivy). Appendix A maps every requirement to
source and verifying artefact.

---

## 1. Execution contract

**REQ-V15-EC-01 (MUST)** Section 1 of every earlier spec applies unchanged, with
these adjustments:

- "the gate commands" means section 14's set — the six of v1.2/v1.4 plus the
  scanner gates, in the profiles section 14 assigns;
- the repair budget is **5 total** repair-and-rerun cycles (one cycle = one fix
  + a complete run of all gates from the first); exhausted → stop and report;
- **no project or lab file outside the repository root may be read or written.**
  The only permitted external effects are the installations, version/`--help`
  queries, Docker operations and tool-owned caches of §§3, 8, 9 and 11;
  sibling-project files stay forbidden — where this spec cites one, the text is
  quoted *here* and the file never opened. The write half bites in a new place —
  see REQ-V15-RPT-01;
- the **runtime** dependency set is unchanged and MUST stay so (`httpx`,
  `python-dotenv`; the `docker` CLI as a host dependency). The **developer** tool
  set is **five pinned external tools** (§11) — three release binaries (gitleaks,
  trivy, rtk) and two uv tools (semgrep, skylos), trivy and skylos new to this
  host — none imported by or required by any production module.

**REQ-V15-EC-02 (MUST)** Test-first: write §15's tests, watch them fail for the
right reason, then implement in §17's order. Every requirement in §§5–13 has a
named unit test, negative test, acceptance scenario or recorded artefact. The
four high-risk gate mechanisms listed in §15.4 additionally require mutation
proof through `devtools/mutation_check.py`.

**REQ-V15-EC-03 (MUST)** The v1.4 suite is **728 collected tests**
(`uv run --locked pytest --collect-only -q`, measured 2026-09-03 at HEAD
`5a69fd3`). No test may be deleted; tests may be modified **only** where §15.1
lists them, and that list is exhaustive. A change making an unlisted test fail
means the change is wrong — stop and reconsider, do not edit the test.

**REQ-V15-EC-04 (MUST)** Secrets discipline unchanged (REQ-V1/V11/V12-EC-04):
credential **values** are never printed, logged, committed or quoted in `docs/`;
presence checks are by key **name** only; tests use the synthetic sentinel
pattern. REQ-V15-SCAN-01's machine check never excuses relaxing it.

**REQ-V15-EC-05 (MUST)** Backward compatibility as in REQ-V1-EC-05: every new
parameter, config field and helper defaults to current behaviour when absent, so
unlisted tests and fakes keep passing.

**REQ-V15-EC-06 (MUST) — the no-benchmark rule and its escape hatch.**
`AGENTS.md` requires that "a behaviour change that touches tokens — prompts, tool
schemas, tool output, history assembly, routing — MUST be accompanied by a
benchmark run before and after, compared with `report --candidate`". No
requirement here changes any of those five, so **this release runs no benchmark**
and `docs/assets/bench/baseline-v1.4.json` stays the baseline.

The escape hatch is neither optional nor a judgement call. If a change touching
any of those five is proposed or discovered at any point: (1) stop the task that
proposed it; (2) record it and its trigger in the report under
"Benchmark-affecting changes"; (3) either drop it and hand it to v1.6, or — only
if dropping is impossible — run the full before/after benchmark with the same
provider, model and context length, `report --gate` machine-checking that they
match. Silently proceeding is a defect; the image bump is the one requirement
that can plausibly trip it.

**REQ-V15-EC-07 (MUST) — the RLM execution rule.** The lab `AGENTS.md` rule 5
("Delegate bulk reading") is a requirement of this run, not an ambient
preference. A task exceeding **one** of these thresholds is delegated to a
subagent: more than one file or folder **to explore beyond the files and line
ranges the task's own reading map names** — exploring is reading to find out
what is there, and a targeted edit to a mapped file is not exploration; a single
read over **100 lines** or **8 KB**; more than **10 edits** to one file in a
task; applying a review or critique to a spec. The subagent gets a **≤ 5-line brief** with no
history and MUST return a **summary only**, never a raw file dump. In the main
context, reads use `Read` with `offset`/`limit` or `grep`/`find` with line
context — never a whole-file read, never a directory walk.

Each task in section 17 carries a **reading map** naming its files and sizes; it
is authoritative for the file-count threshold, so the threshold is decidable
before the task starts, and the report records **per
task** whether the executor delegated and to what. An undelegated task that
crossed a threshold is a process deviation, declared under REQ-V12-REP-02.

**REQ-V15-EC-08 (MUST)** Every prompt file written from this release on carries
the existing bullet header then exactly four blocks — `## Goal`,
`## Constraints`, `## Acceptance`, `## Stop` — specified in §10.

**REQ-V15-EC-09 (MUST) — `--no-verify` is forbidden.** No commit or push in this
run may use `git commit --no-verify`, `git push --no-verify`, `-n`, or any other
bypass (environment switches, a temporary `core.hooksPath` change,
`git config --unset`, deleting and restoring a hook). The report MUST contain
the sentence *"No commit or push in this run used `--no-verify` or any other
hook bypass."* — and MUST omit it, with an explanation, if that is untrue.

A hook cannot observe its own bypass, so the attestation is backed by evidence:
`devtools/checks.py replay --range <base>..<implementation-tip>`
(REQ-V15-GATE-05) re-runs the `pre-commit` profile over every implementation
commit through `<implementation-tip>` (REQ-V15-ACC-04) and exits non-zero if any
would have been rejected. **Replay proves that final-policy substitutes accept
the resulting commits; it does not prove hook invocation or the absence of a
bypass** — it skips the branch check, substitutes a different gitleaks
invocation, and uses today's policy rather than the hook in force at each commit
(hooks land at T8). The no-bypass statement
therefore stays a **process attestation** with replay as consistency evidence,
and the report quotes its output.

---

## 2. Amendments to spec-v0 … spec-v1.4 — authoritative table

**REQ-V15-AMEND-01 (MUST)** Apply exactly these; unlisted requirements stay in
force verbatim.

| id | Status | Change |
|---|---|---|
| REQ-V14-GATE-01 (six gates) | extended | the six commands stay **verbatim and in order**; four scanner gates and a profile assignment are added around them (GATE-06 … GATE-12); no existing gate command is edited, reordered or removed |
| `AGENTS.md` gate list | amended | gains the scanner gates and the profile matrix, in the same commit as the gate (the spec-sync rule) |
| `AGENTS.md` "Commit format" | extended | the prose becomes an enforced `commit-msg` hook (§5); the `(prompt: …)` wording is preserved exactly and machine-checked |
| `AGENTS.md` "Branch strategy" | extended | a branch-name check (REQ-V15-CC-04); the exception letting a whole-spec solo run commit to `main` is preserved, which is why the check is **warn-only** there |
| `AGENTS.md` "Stack" | amended | Python 3.13 → **3.14**; `requires-python ">=3.12,<3.14"` → `">=3.13,<3.15"` |
| `AGENTS.md` "Reporting" | extended | the run report MUST carry a ready-to-paste `economics.md` row (REQ-V15-RPT-01) |
| `.python-version` | amended | `3.13` → `3.14` |
| `pyproject.toml` `requires-python` | amended | `">=3.12,<3.14"` → `">=3.13,<3.15"` |
| `pyproject.toml` `[tool.ruff] target-version` | amended | `"py312"` → `"py313"`, tracking the new lower bound |
| `pyproject.toml` dev `ruff==0.16.5` | amended | `ruff==0.16.6` |
| `uv.lock` | amended | regenerated by `uv lock` in the same commit as the `requires-python` change; `uv sync --locked` stays green |
| `config.py:27` `DEFAULT_DOCKER_IMAGE` | amended | → `"python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6"` (REQ-V15-IMG-01). `_parse_docker_image` (`config.py:555`) needs **no change**: it imposes no `name:tag` shape, so the digest form passes — verified by reading it |
| `.env.example:33` | amended | `EXEC_DOCKER_IMAGE=` gains the same digest value |
| `README.md:19,:24` | amended | says 3.14; the pull uses the digest-pinned ref |
| `tests/test_v1_guardrails.py:371` | amended | the one assertion comparing `cfg.exec_docker_image` to the default literal follows the new default (§15.1). The other **48** `python:3.13-slim` occurrences under `tests/` are arbitrary fake arguments and MUST NOT be touched |
| REQ-V12-MUT-01 / `mutation_check.py` | extended | gains `--select <prefix>` (REQ-V15-GATE-04) and four `v15-*` entries (§15.4); `--only` and its fail-loud-on-unknown-id behaviour (REQ-V13-CO-06) are unchanged |
| REQ-V12-REP-02 (process honesty) | extended | Deviations also records, per task, whether the RLM rule was applied |
| `CLAUDE.md` (one line, `@AGENTS.md`) | extended | keeps that import, gains the RTK block (REQ-V15-RTK-02) |
| REQ-V1-EC-01 (repository boundary) | clarified | the read/write ban covers project and lab **files**; the installs, `--version`/`--help` queries, Docker operations and tool caches of §§3, 8, 9, 11 are permitted (REQ-V15-EC-01) |
| REQ-V13-BEN-* baselines | unchanged | no benchmark runs; `baseline-v1.4.json` stays (REQ-V15-EC-06) |

Everything else in v0…v1.4 — Docker isolation, redaction choke points,
truncation headroom, failover, structured memory, commands, rate limiting, the
error matrix, the token budget, observability, the benchmark harness, the
reasoning-control STOP decision — is unchanged and MUST keep working.

---

## 3. Preconditions

**REQ-V15-PRE-01 (MUST)** Verify each; on failure stop and emit the blocker
template (v0 section 7.2) instead of guessing.

1. **Repository**: branch `main`, clean tree, HEAD at the delivered v1.4
   (`docs/spec/spec-v1.4.md` and `docs/reports/report-v1.4.md` present).
2. **All six v1.4 gates green before anything changes.** An already-red gate is a
   blocker, not something to fix silently here. Gate 5's `lmstudio` check is
   **not** excused (REQ-V14-GATE-01 withdrew the v1.2 exception), so an
   unreachable LM Studio blocks the run.
3. **Credentials**: the git-ignored `.env` exists with the keys spec-v1.2 §3.3
   lists. Presence **by key name only**; never create, overwrite, print or scan
   it (REQ-V15-SCAN-01).
4. **Docker**: `docker version` succeeds without `sudo`. Both images are locally
   present before section 12 begins, and **presence is not enough for the
   outgoing one**: `docker image inspect --format '{{json .RepoDigests}}'
   python:3.13-slim` MUST show
   `sha256:881d80734ee05dca6f7f42dcb080975652a53c7eda9ba1f03bb8da31aa6a6ec2`
   (REQ-V15-IMG-01) — a floating tag can point at any digest, and an arbitrary
   cached image yields valid-looking, non-reproducible bytes. On mismatch,
   pulling **that exact digest** is a sanctioned network
   operation; the run does not proceed on the mismatched local tag. The incoming
   digest-pinned 3.14 image is pulled explicitly. `exec` never pulls at request
   time.
5. **Network, three sanctioned steps and no more**: the five tool installs
   (section 11, one per task T2–T6), the image pulls (the incoming digest, plus
   the outgoing digest only where item 4's inspect showed a mismatch), and the
   one-off resolution of the semgrep ruleset vendored in T7 (REQ-V15-SCAN-04).
   Everything else — every gate, test and scanner run — MUST work offline, and
   REQ-V15-SCAN-04 requires that be *proven* with the network denied and an empty
   semgrep cache. Record which step needed the network.
6. **`git --version` ≥ 2.9** — when `core.hooksPath` was introduced; section 6
   rests on it.

**REQ-V15-PRE-02 (MUST) — tool availability, measured not assumed.** Before the
install tasks T2–T6, record each tool's *installed* version from its own version
command and compare against its pin. Measured 2026-09-03:

| tool | measured | command |
|---|---|---|
| Python | 3.14.7 | `python3 --version` |
| uv | 0.12.7 | `uv --version` |
| ruff | 0.16.5 | `uv run --locked ruff --version` |
| gitleaks | 8.24.3 | `gitleaks version` |
| semgrep | 1.167.0 | `semgrep --version` |
| trivy | **not installed** | `trivy --version` → command not found |
| skylos | **not installed** | `skylos --version` → command not found |
| rtk | 0.46.0 | `rtk --version` |

A version differing from its pin after its install task fails `checks.py doctor`,
and `doctor` failing fails the gate (REQ-V15-GATE-03).

---

## 4. Required file tree (delta)

**REQ-V15-TREE-01 (MUST)** New files:

```
.githooks/commit-msg .githooks/pre-commit .githooks/pre-push   # §6
.gitleaks.toml  .semgrep/*.yml  .semgrep/SOURCES.md            # §8
.claude/settings.json                                          # §9
config/quality_gates.yaml     # the only source of gate authority (§7)
devtools/checks.py            # the one runner (§7)
devtools/install_hooks.py     # idempotent installer, --check mode (§6)
tests/test_v15_standards.py   # §15.2, §15.3
docs/prompts/TEMPLATE.md      # §10
docs/prompts/44-go-spec-v1.5.md, 45-v15-*.md …   # one per task of §17
docs/reports/report-v1.5.md   docs/reports/tg-post-v1.5.md
```

**Prompt numbering.** `docs/prompts/43-v14-verify-run-fixes.md` closes the v1.4
cycle, exists before this run starts, and is the **first example of the
four-block format** (REQ-V15-PRM-02). This run's `go` prompt is therefore `44`,
per-task prompts continue from `45`, and `43` missing at T0 is a precondition
failure, not a licence to renumber.

**REQ-V15-TREE-02 (MUST)** Changed files: `.python-version`, `pyproject.toml`,
`uv.lock`, `config.py`, `.env.example`, `README.md`, `AGENTS.md`, `CLAUDE.md`,
`devtools/mutation_check.py`, `docs/plan.md`, plus exactly the test files named
in section 15.1.

`config/` and `.githooks/` are **new directories**, required by no production
module: the bot must start, answer and run `--selftest` on a checkout where the
hooks were never installed. `config/` holds
data and carries **no `__init__.py`** — it must not shadow the top-level
`config.py` (spec-v1.2 §4's `tools/` vs `tools.py` hazard), with a test asserting
`config.__file__` ends with `config.py`. `checks.py` and `install_hooks.py` are
linted by gate 2 and never imported (REQ-V11-NG-06's `devtools/` exception).

---

## 5. Conventional Commits (CC)

`AGENTS.md` already requires conventional commits in prose: "Conventional
commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`. **One prompt
→ one commit.** Reference the prompt file in the body: `(prompt:
docs/prompts/NN-<slug>.md)`. NEVER mix results of different prompts in one
commit or MR." This section turns that into a hook; the prompt-reference wording
is preserved and only its enforcement is new.

**REQ-V15-CC-01 (MUST) — the header.** The first line MUST match Conventional
Commits v1.0.0 (https://www.conventionalcommits.org/en/v1.0.0/) as narrowed
here. Allowed types, exactly:
`feat fix docs style refactor perf test build ci chore revert`. Scope optional
and lower-case; `!` optional and after the scope; separator is a colon and one
space. Anchored POSIX ERE:

```
^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9.-]+\))?!?: .+$
```

Adapted from the RTL server-side hook regex, minus the **ticket key** (no issue
tracker here) and with the full Conventional Commits type list (Appendix A).

**REQ-V15-CC-02 (MUST) — length and punctuation, checked separately.** Two
properties would make the header regex unreadable, so each is its own check with
its own message: the header is **≤ 72 characters** (Unicode, not bytes) and does
**not** end with `.`. A rejection MUST name which of the three checks failed,
quote the offending line and print the correct form; a bare "invalid commit
message" pushes the user toward the `--no-verify` REQ-V15-EC-09 forbids.

**REQ-V15-CC-03 (MUST) — the prompt reference and the bypass allowlist.** The
**body** MUST contain `\(prompt: docs/prompts/[0-9]{2,}-[a-z0-9.-]+\.md\)` and
the referenced file MUST exist in the working tree — a dangling path satisfies
the letter while defeating the point, so it is a rejection.

Four subject shapes are **exempt from every check in this section**, because git
generates them and rejecting them leaves `--no-verify` as the only exit:
`^Merge`, `^Revert`, `^fixup!`, `^squash!` — a first-line prefix test applied
before the header regex. A hand-written "Merge…" is a residual gap the reviewer
catches.

**REQ-V15-CC-04 (MUST) — the branch name.** The current branch MUST match
`^(main|(feat|fix|docs|test|chore)/[a-z0-9][a-z0-9._-]*)$`. A branch matching
nothing is a **failure**. `main` matches but produces a **warning, never a
failure** — `AGENTS.md` explicitly permits "a single-agent run implementing a
whole spec end-to-end" to commit directly to `main`, which is exactly this run;
the warning catches a *parallel* run on the wrong branch. A detached HEAD warns
and passes.

**REQ-V15-CC-05 (MUST) — one implementation, two callers.** The regexes, the
length bound, the trailing-period rule and the allowlist live in **one** Python
function in `devtools/checks.py`, called by the `commit-msg` hook and by
`checks.py replay`. Duplicating the regex into the hook is a defect; the hook is
a shim, and §15.2 tests the function directly.

---

## 6. The hook chain (HOOK)

**REQ-V15-HOOK-01 (MUST) — versioned in the repository.** Hooks live in
`.githooks/`, are committed and executable (`0755`), and are activated by
`git config core.hooksPath .githooks`. `.git/hooks/` is never written, so hooks
are reviewed and diffed like any other code.

**REQ-V15-HOOK-02 (MUST) — `commit-msg`.** Receives the message path as `$1`,
calls `python3 devtools/checks.py commit-msg "$1"`; exit 0 accepts, non-zero
rejects with REQ-V15-CC-02's message. Budget **< 1 s**.

**REQ-V15-HOOK-03 (MUST) — `pre-commit`, fast only.** Calls
`checks.py run --profile pre-commit`, which runs exactly:

1. `ruff check --force-exclude <staged .py files>`
2. `ruff format --check --force-exclude` — run **twice, over two disjoint
   subsets of the staged set**, because one invocation yields one exit code and
   the runner cannot tell a new-file finding from a legacy one after the fact.
   The runner partitions *before* invoking (REQ-V15-SCAN-05)
3. `gitleaks git --staged --no-banner --redact --config .gitleaks.toml .`
4. the branch-name check of REQ-V15-CC-04

`--force-exclude` is required because ruff receives explicit paths: without it a
staged file inside an `exclude` entry would be linted anyway. Budget **< 15 s**;
nothing slow belongs here — no pytest, no scanner but gitleaks, no mutations.

**REQ-V15-HOOK-04 (MUST) — `pre-push`.** Calls `checks.py run --profile
pre-push --stdin-refs`, **forwarding its own stdin unchanged** so the runner
derives the pushed range from git's ref records (REQ-V15-GATE-07) instead of
guessing. Membership is defined by
`config/quality_gates.yaml`, not by the script (REQ-V15-GATE-02); section 14
gives the default. It excludes gate 5 (`--selftest-live`), which needs `.env`, a
Docker daemon and LM Studio and would make every push depend on a live
environment.

**Budget: target ≤ 180 s, observational only.** T12 measures the wall-clock
three times; the report records the **median as a filled-in number**. Exceeding
180 s is **reported and alters no profile membership in this release** —
`T-V15-GATE-04` asserts the matrix against the config, and the slowest member
could be a security or doctor gate. An over-budget median is an input to v1.6,
not a licence to move a gate mid-run.

Measured at spec-writing time: 728 tests, `pytest -q` **23.05 s**; the unselected
mutation gate costs **16–17 minutes**, so REQ-V15-GATE-04 gives `pre-push` the
four `v15-*` entries (≈ 92 s) instead.

**REQ-V15-HOOK-05 (MUST) — the installer.** `devtools/install_hooks.py`:

- no argument: sets `core.hooksPath` to `.githooks`, makes each hook executable,
  prints what it changed. A second run changes nothing and says so —
  **idempotence is a tested property** (§15.2), not a claim;
- `--check`: changes nothing, exits **non-zero** when `core.hooksPath` is unset,
  points elsewhere, or a hook is missing or non-executable — what the gate calls;
- refuses to run outside a git work tree, clearly; stdlib plus `git` only.

**REQ-V15-HOOK-06 (MUST) — the hooks are shims.** Each hook file is at most ten
lines: shebang, `set -eu`, one call into `checks.py`. No hook contains a regex, a
severity threshold, a tool invocation or a path list — every such decision lives
in `config/quality_gates.yaml`.

---

## 7. The runner and the gate config (GATE)

**REQ-V15-GATE-01 (MUST) — one runner.** `devtools/checks.py` is the single entry
point for every check this release adds: hooks call it, gates call it, the report
quotes it.

| subcommand | does |
|---|---|
| `run --profile pre-commit\|pre-push\|full [--stdin-refs] [--since <rev>]` | runs that profile's members in order. `--stdin-refs` reads git's `pre-push` ref records from stdin (REQ-V15-HOOK-04); `--since <rev>` names the exclusive lower bound of the run's own commit range. The two are **mutually exclusive**, and `full` on `main` without `--since` is refused (REQ-V15-GATE-07) |
| `doctor` | every pinned tool installed at its pin (via `tools.version_argv`) and the hook chain installed (`install_hooks.py --check`); non-zero otherwise |
| `commit-msg <file>` | the checks of §5 |
| `replay --range <rev>..<rev>` | re-runs the `pre-commit` profile over each commit in the range (REQ-V15-EC-09's evidence) |
| `lint-docs` | prompt-header and report-ledger lints (REQ-V15-PRM-04, REQ-V15-RPT-03) |

`checks.py` uses only the standard library. YAML is parsed by a **small explicit
reader for the subset `config/quality_gates.yaml` uses** (nested maps, lists of
scalars, strings, integers, booleans) — not an imported library (REQ-V15-EC-01),
not a regex over the file. It **fails closed on
anything it does not understand**: an unknown top-level key, a wrong-typed value,
a duplicate key or a tab is a parse error that fails the gate; a parser that
skips what it cannot read is a fail-open hole.

**REQ-V15-GATE-02 (MUST) — the config is the only authority.**
`config/quality_gates.yaml` holds, per gate: the pinned tool version, the
severity list, **blocking** or **shadow**, whether it is **diff-scoped**, its
timeout and its profile membership. `checks.py` is a **pure function over that
file** — no threshold, severity list, shadow default or profile membership is a
literal in the code — so a gate's authority changes in a one-line diff.

**Python holds parsing mechanisms only — never a policy value, never a command
argument.** `checks.py` may contain one adapter per output format (turning a
scanner's JSON into normalised findings), one handler per built-in gate, and the
runner that executes what the config says. **Adapter, parser and handler
identifiers are mechanism names and are permitted as Python literals**; nothing
else is. The code may not contain a tool name, a flag, an argv fragment, a
target path, a severity, a threshold, an exit code or a profile list.

**Two gate kinds, and every gate declares which.**

- `kind: command` — the runner executes `argv` and declares
  **`result_mode: exit_status|findings`**, legal on this kind only. Both modes
  require `argv` (full token list), `placeholders`, `success_exit_codes` (ran,
  no finding) and `timeout_seconds`; neither carries `handler`.
  - `result_mode: findings` — the gate produces findings the runner reads.
    Also required: `output_format`, `parser`, `findings_exit_codes` (ran,
    findings; any other code is a run failure), `artefact` (REQ-V15-SCAN-06's
    path) and `severity` (REQ-V15-GATE-12; a tool reporting none yields the
    adapter's `UNKNOWN`, which the list then includes). Membership, the five
    scanner
    invocations: `gitleaks-staged`, `gitleaks-tree`, `trivy`, `semgrep`,
    `skylos`.
  - `result_mode: exit_status` — the exit code is the verdict and nothing is
    parsed; any code outside `success_exit_codes` fails it. MUST NOT carry
    `parser`, `output_format`, `findings_exit_codes`, `severity` or `artefact`
    — SCAN-06's artefact obligation is on `findings` gates only. Membership:
    `uv-sync`, `ruff-check`, `ruff-check-all`, `ruff-format`, `pytest`,
    `selftest`, `selftest-live`, `mutation-v15`, `mutation-all`,
    `hooks-installed`.
- `kind: builtin` — the runner calls a named `handler`; no external command, no
  output to parse. Permitted handlers, exactly three: `branch_name`
  (REQ-V15-CC-04), `doctor` (REQ-V15-GATE-03), `lint_docs` (REQ-V15-PRM-04,
  REQ-V15-RPT-03). MUST NOT carry `argv`, `placeholders`, `parser`,
  `output_format`, `result_mode` or either exit-code list.

Both kinds carry `blocking`, `diff_scoped` and `timeout_seconds`.
`diff_scoped: true` on an `exit_status` gate means the runner
partitions the **argv path list before invoking** — REQ-V15-SCAN-05's
`ruff-format`, run twice over disjoint subsets; only a `findings` gate
partitions results after the fact (REQ-V15-GATE-07).
Beyond those, the **only** further keys are these four sets, each legal on
exactly the gate named — `ruff-format.blocking_paths` (REQ-V15-SCAN-05's new-file
list, which the runner partitions the scope against); `branch-name.pattern`,
`.warn_refs`, `.warn_on_detached` (REQ-V15-CC-04's regex, the refs that warn
instead of fail — `[main]` — and the detached-HEAD verdict);
`doctor.warn_only_tools` (`[rtk]`, REQ-V15-RTK-03); and `lint-docs.prompt_glob`,
`.exempt_files`, `.report_path`, `.ledger_header` (REQ-V15-PRM-04's glob and
**literal** exemption list, the report path, the ledger header row).

A gate with no `kind`, a `command` gate with no `argv` or no `result_mode`, an
`exit_status` gate carrying `parser`, `severity` or `artefact`, a `builtin` gate
naming a handler outside those three or carrying `result_mode`, a `parser`
naming no known adapter, any key
outside the sets above, or a placeholder outside the fixed five `{target}`,
`{config}`, `{artefact}`, `{profile}`, `{tracked_tree}` is a **parse error and
fails closed** (REQ-V15-GATE-06).

Top-level keys are exactly `version`, `scope`, `profiles`, `tools`, `gates`; any
other is a parse error. Each `tools` entry carries `version`, `via`,
**`version_argv`** and **`version_parser`**, and `doctor` runs that argv verbatim
(REQ-V15-GATE-03) — which is why no version command appears in Python. The
example is complete in its key set, illustrative in its gates: the executor
writes *every* gate named in `profiles:` in this shape (`T-V15-GATE-01`):

```yaml
version: "2026-09-03.1"

scope:                              # REQ-V15-GATE-07
  base_branch: main
  zero_sha: "0000000000000000000000000000000000000000"

profiles:                           # REQ-V15-GATE-11's matrix, verbatim
  pre-commit: [ruff-check, ruff-format, gitleaks-staged, branch-name]
  pre-push:   [ruff-check-all, ruff-format, branch-name, pytest, selftest,
               gitleaks-tree, trivy, semgrep, skylos, mutation-v15,
               hooks-installed, doctor]
  full:       [uv-sync, ruff-check-all, ruff-format, branch-name, pytest,
               selftest, selftest-live, mutation-all, gitleaks-tree, trivy,
               semgrep, skylos, hooks-installed, doctor, lint-docs]

tools:                              # parsers for trivy/skylos confirmed in T4/T5
  ruff:     { version: "0.16.6",  via: uv,      version_parser: last_token,
              version_argv: [uv, run, --locked, ruff, --version] }
  gitleaks: { version: "8.30.1",  via: binary,  version_parser: bare,
              version_argv: [gitleaks, version] }
  semgrep:  { version: "1.176.0", via: uv-tool, version_parser: bare,
              version_argv: [semgrep, --version] }
  trivy:    { version: "0.74.0",  via: binary,  version_parser: last_token,
              version_argv: [trivy, --version] }
  skylos:   { version: "4.35.0",  via: uv-tool, version_parser: last_token,
              version_argv: [skylos, --version] }

gates:
  gitleaks-tree:                    # secrets block anywhere, at any severity
    kind: command
    result_mode: findings
    argv: [gitleaks, dir, --no-banner, --redact, --config, "{config}",
           --report-format, json, --report-path, "{artefact}", "{tracked_tree}"]
    placeholders: { config: .gitleaks.toml }   # REQ-V15-SCAN-01: tracked only
    output_format: json             # parser gitleaks_json, exit codes [0] / [1]
    artefact: .bench/checks/{profile}/gitleaks-tree.json
    blocking: true
    diff_scoped: false
    severity: [CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN]   # i.e. always a member
    timeout_seconds: 120

  gitleaks-staged:                  # kind: command; §8's staged invocation, keys
    ...                             # as gitleaks-tree — but target ".", NOT
                                    # tracked_tree: the index is already
                                    # commit-eligible. Timeout 60.

  trivy:                            # vuln + misconfig only — no secret scanner
    kind: command
    result_mode: findings
    argv: [trivy, fs, --scanners, "vuln,misconfig", --severity,
           "HIGH,CRITICAL", --exit-code, "1", --ignore-unfixed, --format, json,
           --output, "{artefact}", "{target}"]
    placeholders: { target: "." }   # whole tree; the runner partitions findings
    output_format: json             # parser trivy_json, exit codes [0] / [1]
    artefact: .bench/checks/{profile}/trivy.json
    blocking: true
    diff_scoped: true
    severity: [CRITICAL, HIGH]      # REQ-V15-GATE-12's membership list
    timeout_seconds: 240

  semgrep:                          # kind: command; §8's invocation verbatim,
    ...                             # placeholders {config: ".semgrep/",
                                    # target: "."}; every other key as trivy;
                                    # parser semgrep_json, [ERROR], timeout 180

  skylos:                           # shadow; argv, output flag and exit codes
    kind: command                   # stay under REQ-V15-SCAN-05's [[VERIFY]]
    result_mode: findings
    argv: [skylos, "{target}"]      # until T5 resolves them against --help
    placeholders: { target: "." }
    ...                             # parser skylos_json, blocking false,
                                    # diff_scoped true, timeout 120

  pytest:                           # exit_status: the code is the verdict — no
    kind: command                   # parser, artefact or severity. Same shape
    result_mode: exit_status        # for uv-sync, ruff-*, selftest*,
    argv: [uv, run, --locked, pytest]   # mutation-*, hooks-installed
    placeholders: {}
    success_exit_codes: [0]
    ...                             # blocking true, diff_scoped false, 600 s

  branch-name:                      # the built-in kind — no external command
    kind: builtin
    handler: branch_name
    pattern: "^(main|(feat|fix|docs|test|chore)/[a-z0-9][a-z0-9._-]*)$"
    warn_refs: [main]
    warn_on_detached: true
    blocking: true
```

The gitleaks argv is flag-verified against the installed 8.24.3 and re-confirmed
at the 8.30.1 pin in T2, the semgrep argv against `semgrep scan --help` at
1.167.0; trivy's and skylos's flags and exit codes stay under their
`[[VERIFY]]` markers until T4 and T5.

**REQ-V15-GATE-03 (MUST) — one authority, two readings.**
`quality_gates.yaml` states the **expected** version. `checks.py doctor` reads
the **resolved** one by executing each `tools` entry's `version_argv` verbatim
and parsing it with the named `version_parser` — the code holds neither the
command nor the flag — and **fails closed on any mismatch, including a newer
installed version**, so an unannounced upgrade is as visible as a
missing one.

`ruff` necessarily appears in two files: `pyproject.toml`'s dev group is what
`uv sync` installs, `quality_gates.yaml` what `doctor` expects.
**`quality_gates.yaml` is authoritative and any ruff-pin change edits both in the
same commit** (T13); `T-V15-GATE-03` fails the moment one moves without the
other.

**REQ-V15-GATE-04 (MUST) — `mutation_check.py --select`.** Gains
`--select <prefix>`, running every mutation whose `id` starts with the prefix,
keeping the fail-loud rule REQ-V13-CO-06 established for `--only`: a prefix
matching **zero** mutations prints `no mutation id matches prefix: <prefix>` on
stderr and exits non-zero — a selector that silently selects nothing reports a
clean gate over an empty set. `--only` is unchanged; the two are mutually
exclusive. `pre-push` runs `--select v15-`; `full` runs
the gate unselected.

**The file being edited is one of its own targets.** `v13-only-typo-exit0`
anchors byte-exactly on `devtools/mutation_check.py:551-555` — the `args.only`
guard in `main()`, the line `--select` invites you to rewrite. **That line MUST
survive unchanged**; add `--select`'s unknown-prefix check as a
*separate* adjacent branch. If the anchor genuinely cannot be preserved, updating
the entry is permitted only in the same commit, with the new `find` string
verified by `mutation_check.py --list` and re-run to confirm it still kills its
test (REQ-V15-TST-02).

**REQ-V15-GATE-05 (MUST) — `replay`.** Walks each commit in the range,
reconstructs its changed-file set, runs the checks below against that set plus
the `commit-msg` checks against that message, prints one line per commit and
exits non-zero if any fails. It never checks out, resets or otherwise mutates
the working tree — it reads blobs via `git show`.

`pre-commit`'s four members do not all have a historical meaning, so `replay`
runs a named substitute set rather than "the profile":

| `pre-commit` member | what `replay` runs |
|---|---|
| `ruff check` (staged) | the same check over that commit's changed `.py` blobs |
| `ruff format --check` | the same, over the blocking/shadow partition of REQ-V15-SCAN-05 |
| `gitleaks git --staged` | **substituted**, exactly: `gitleaks git --no-banner --redact --config .gitleaks.toml --report-format json --report-path <artefact> --log-opts "--no-walk <sha>" .` — `--staged` has no meaning for a commit already written |
| branch-name check | **skipped**: a historical commit carries no branch |

That form is verified on the installed gitleaks 8.24.3 (`1 commits scanned`, JSON
report written) and re-confirmed at the 8.30.1 pin in T2.

**The ruff checks run one blob at a time through stdin, never from a temporary
tree.** `exclude`, `extend-exclude` and `per-file-ignores` match the path ruff is
given, so a blob at `$TMPDIR/<random>/pkg/x.py` matches different patterns than
`pkg/x.py` and `replay` would verdict differently from `pre-commit`. Per changed
`.py` blob, `replay` pipes `git show <sha>:<path>` into

```
ruff check  --force-exclude --stdin-filename <repository-relative path> -
ruff format --check         --stdin-filename <repository-relative path> -
```

with the repository root as the working directory, so `pyproject.toml` is the
resolved configuration. Both flags exist on the installed 0.16.5 (`ruff
check/format --help`). Nothing is written to disk. `T-V15-GATE-06` pins it.


**REQ-V15-GATE-06 (MUST) — fail-closed, without exception.** A gate that is
**missing, times out, crashes, or returns output the runner cannot parse** FAILS.
It never silently passes nor degrades to a warning; the message names the
gate, the cause, and that the run is blocked
(*"A gate that cannot run must not pass."* — `security_gates.yaml:36-40`).

This applies to **shadow** gates without exception. A shadow scanner's
successfully parsed findings do not fail the profile. If the scanner is missing,
times out, crashes, returns an unexpected exit code, omits its artefact, or
produces unparseable output, the profile **fails closed exactly as for a
blocking scanner**: `blocking: false` withholds findings, never operational
failures.

**REQ-V15-GATE-07 (MUST) — diff scoping and the empty-scope trap.** Where
`diff_scoped: true`, findings are evaluated only over files this change touches;
findings elsewhere are **reported, not blocking**.

**The algorithm, because no invocation can express it.** trivy, semgrep and
skylos take a target path, not a changed-file list, and a scanner invoked on a
subset can neither inspect nor report what lies outside it. So every diff-scoped
scanner gate **executes against the repository root `.`**, and the runner
normalises each finding's path to a repository-relative one, partitions findings
by membership in the computed changed-file set, **blocks only on the in-scope
partition** and **reports both**. A path that cannot be parsed or normalised
**fails the gate closed**. `ruff format --check` is the one exception: it takes
explicit path lists and is partitioned *before* invocation (REQ-V15-SCAN-05).

Rationale: a repository always carries findings that predate the change, and a
gate can only honestly answer *"did this change introduce it"*. Scope is
computed **per profile**, and matters more here because this repository's
sanctioned workflow commits to `main`:

| profile | scope |
|---|---|
| `pre-commit` | the staged set (`git diff --cached --name-only --diff-filter=ACMR`) |
| `pre-push` | the union of the ranges git names on the hook's **stdin** — below |
| `full` | on a `feat\|fix\|docs\|test\|chore/*` branch: `$(git merge-base main HEAD)..HEAD`; on `main`: the run's own commit range, passed explicitly as `--since <rev>` |

**Naive `merge-base(main, HEAD)` on `main` returns `HEAD`, making the changed
set empty and every diff-scoped gate vacuously green** — a fail-open path inside
a fail-closed requirement, and the normal case for this project's solo runs.
Therefore:

> **An empty computed scope while `git status --porcelain` or the named commit
> range is non-empty is a gate FAILURE, not a pass.** The message says the scope
> computation is wrong and names the profile and the revision it used.

**`--since` is not optional on `main`, and the trap alone is not enough.** On a
clean `main` there is neither a merge-base range nor a dirty tree, so an
unscoped `full` would compute an empty set *legitimately*, the trap would not
fire, and every diff-scoped gate would pass vacuously. Therefore **`run
--profile full` on `main` without `--since <rev>` is refused before any gate
runs**, exit non-zero, naming the missing option. `<base>` — the HEAD recorded
at T0 (§17) — is what every acceptance invocation here passes. On a
`feat|fix|docs|test|chore/*` branch `--since` is optional and overrides the
merge-base when given.

**`pre-push` scope comes from stdin; `HEAD~1..HEAD` is never a fallback.** Git
feeds the hook one `<local-ref> <local-sha> <remote-ref> <remote-sha>` record per
ref pushed; the shim forwards stdin unchanged and the runner unions the ranges.
Where `<remote-sha>` is `scope.zero_sha` — a new branch, a first push — the range
is `$(git merge-base <scope.base_branch> <local-sha>)..<local-sha>`, or the run's
explicit `--since <rev>` where given. A first push of five commits must scope
trivy, semgrep and skylos to all five: `HEAD~1..HEAD` would scope them to the
last one, and the empty-scope trap below does not fire on a scope that is
non-empty but incomplete (`T-V15-HOOK-05`). Empty or unparseable stdin fails the
gate closed.

Secrets are the exception in the other direction: `gitleaks-tree` is
`diff_scoped: false` and blocks at any severity anywhere (REQ-V15-SCAN-01).

**REQ-V15-GATE-12 (MUST) — normalised severity, and the membership test.**
Scanner CLIs already filter by severity, so the runner adds no second
*threshold*. The policy is **membership, not ordering**, and it is the only
severity logic in `checks.py`:

- every normalised finding carries a `severity`: the tool's own token,
  upper-cased by the gate's adapter, otherwise unchanged;
- a **blocking** gate blocks only on findings whose `severity` **is a member of**
  that gate's configured `severity` list; findings outside it are reported, not
  blocking — the treatment out-of-scope findings get;
- a severity missing, empty, or not a member of the union of every `severity`
  list in the config fails the gate **closed** as unparseable output
  (REQ-V15-GATE-06). There is no default severity, no "unknown means low";
- where the tool reports no severity the adapter emits the explicit token
  `UNKNOWN` — a normal member, not an absence: `gitleaks_json` does exactly this,
  and the gitleaks gates list all five tokens, so every gitleaks finding blocks
  (REQ-V15-SCAN-01). A `result_mode: exit_status` gate (`ruff-*` among them) has
  no findings and no `severity`; the membership test never applies to it.

`T-V15-SCAN-10` proves it with two otherwise identical findings — one HIGH, one
LOW — against a gate configured `severity: [CRITICAL, HIGH]`, and is the named
killer of `v15-severity-comparison-inverted` (§15.4), which inverts exactly this
membership condition.

**REQ-V15-GATE-08 (MUST) — shadow mode is real execution.** A gate with
`blocking: false` **runs for real**, its findings are printed and written to the
run's artefact directory, and its exit status is recorded — it simply does not
fail the profile. Promotion happens **only by editing
`config/quality_gates.yaml`**; no environment variable, flag or heuristic
promotes a gate at runtime (`ai-workflows-concept/README.md:313-318`).

---

## 8. The scanners (SCAN)

Four scanners, one runner, one config: every invocation below is executed by
`checks.py` from `config/quality_gates.yaml`, none hard-coded.

**REQ-V15-SCAN-01 (MUST) — gitleaks: secrets, blocking, whole tree, any
severity.** Two invocations, both with `--config .gitleaks.toml`, `--no-banner`
and `--redact` (so a finding never prints the value it found — REQ-V15-EC-04):

```bash
# pre-commit — the staged set
gitleaks git --staged --no-banner --redact --config .gitleaks.toml \
  --report-format json --report-path <artefact> .
# pre-push, full — the tracked tree, materialised (see below)
gitleaks dir --no-banner --redact --config .gitleaks.toml \
  --report-format json --report-path <artefact> <tracked_tree>
```

`--report-format json --report-path` makes REQ-V15-SCAN-06's artefact exist;
both are global flags of the installed 8.24.3 (`gitleaks --help`).

**`gitleaks-tree` scans committed content only — a security decision, not a
convenience.** REQ-V15-PRE-01.3 requires a credential-bearing `.env` in the
working directory; `gitleaks dir … .` would scan it, find live values and wedge
every `pre-push` and `full` run permanently, leaving only two exits — allowlist a
secret path (forbidden, REQ-V15-SCAN-08) or delete the operator's credentials.
"Secrets anywhere" means anywhere in repository content **already committed**.

So the runner materialises `{tracked_tree}` **from git objects, never from
filesystem paths**: `git ls-tree -r -z` names the entries, `git cat-file` writes
each blob's bytes to the same repository-relative path under a throwaway
`$TMPDIR` directory, deleted afterwards. The tree is `HEAD` for `full`; for
`pre-push` it is the **deduplicated union of the blobs introduced anywhere in
the pushed ranges** git named on stdin (REQ-V15-GATE-07), so a secret added and
then removed inside one push still blocks. **The working tree is not an input** —
a path a pushed commit carries but the working tree deleted, and unstaged bytes
replacing a committed secret, are what a working-tree copy gets wrong
(`T-V15-SCAN-12`).

Two entry modes need naming. **`120000` (symlink) is written as a regular file
holding the link text, never re-created as a symlink**, so no read escapes the
repository — this tree has one (`.agents → .claude`, measured 2026-09-03).
**`160000` (gitlink) is rejected explicitly**: the runner names the path and
fails closed rather than scan content it does not own; there are none today, so
the rejection is a guard, not a workaround.

**Untracked and git-ignored files, `.env` included, are not inputs to
`gitleaks-tree`; every committed file is — `T-V15-SCAN-11` proves both halves.**
New files are covered before they land by `gitleaks-staged`, which scans the
index.

Note the subcommands: **`gitleaks protect` does not exist** in 8.24.3 —
`gitleaks --help` lists `dir`, `git`, `stdin` and nothing else; staged mode is
`gitleaks git --staged`.

A gitleaks finding **blocks at any severity, in any tracked file, whether or not
this change touched it** — there is no low-severity version of leaking a key.
`diff_scoped: false` here is the one place this spec refuses diff scoping.

**gitleaks is this release's sole authoritative secret gate**: no other scanner's
secret detection is enabled (REQ-V15-SCAN-03) — two detectors under two policies
means the weaker one decides.

**REQ-V15-SCAN-02 (MUST) — `.gitleaks.toml`, and an allowlist *proven* to
work.** The config extends the default rule set (`[extend]` with
`useDefault = true`) and allowlists the synthetic canaries the suite already
uses: regex `SYNTHETIC-[A-Z0-9-]*CANARY[A-Za-z0-9-]*`, restricted to paths under
`tests/` and `docs/`. They exist in the tree today, so the allowlist is checked
against reality, not guessed — `SYNTHETIC-CANARY-NEVER-A-LIVE-VALUE`,
`SYNTHETIC-CANARY-OBS`, `SYNTHETIC-CANARY-1` (e.g.
`docs/spec/spec-v1.3.md:89`), `SYNTHETIC-V11-CANARY-` and
`SYNTHETIC-V12-CANARY-`, every occurrence under `tests/` or `docs/` (measured
2026-09-03).

**Default rules do not detect these canaries — measured, not assumed.** On the
installed 8.24.3, `gitleaks dir` over a file holding `SYNTHETIC-CANARY-1` reports
*no leaks found*, exit 0, so an allowlist experiment against the default rule set
proves nothing: exit 0 would mean "not detectable". `.gitleaks.toml` therefore
also carries a **named test-only rule** that makes the canaries detectable:

```toml
[[rules]]
id = "synthetic-canary-test"
description = "repository-local; makes REQ-V15-SCAN-02 falsifiable"
regex = '''SYNTHETIC-[A-Z0-9-]*CANARY[A-Za-z0-9-]*'''
```

The allowlist restricts *that rule* to paths under `tests/` and `docs/`; nothing
else in the tree carries the pattern (measured 2026-09-03: zero matches outside
those two directories), so the rule adds no standing noise.

**The table form is an open empirical question the executor MUST settle by
experiment, not by reading.** A sibling lab project recorded — quoted here so no
file outside this repository is opened (REQ-V15-EC-01) — that on **gitleaks
8.24.3 the plural `[[allowlists]]` form was silently ignored**, so it fell back
to the legacy singular `[allowlist]`, the *opposite* of the briefed direction —
a silently ignored allowlist is the worst failure a blocking gate can have.

So the requirement is behavioural and the test *is* the specification (§15.3,
`N4`) — **three assertions against `synthetic-canary-test`, same rule and same
config throughout, differing only in one deliberate control removal**:

1. **Control** — with that rule's allowlist entry **removed** (a variant the test
   builds in its fixture; only the real `.gitleaks.toml` is committed), stage
   `SYNTHETIC-CANARY-1` under `tests/` and assert it **is detected**. Without
   this, assertion 2 proves nothing.
2. **Suppression** — restore the candidate allowlist form, stage the same value
   at the same path, assert it is **suppressed**, exit 0.
3. **Escape** — stage the exact sentinel `SYNTHETIC-CANARY-NOT-ALLOWLISTED-1`
   **outside** `tests/` and `docs/`: same rule, unallowed path. Assert it is
   **caught**, exit non-zero, printed redacted.

If 2 fails, switch the table form (`[allowlist]` ↔ `[[allowlists]]`) and repeat
all three. The report records which form 8.30.1 honours and all three exit codes.
Widening the allowlist to make 3 pass is a defect (REQ-V15-SCAN-08); an allowlist
not shown to be load-bearing, to suppress *and* to still catch is not accepted.

**REQ-V15-SCAN-03 (MUST) — trivy: vuln and misconfig, blocking on HIGH/CRITICAL;
its secret scanner stays off.** Modelled on `idp-concept`'s `stdSecScan.groovy:9-11`, extended with
`--ignore-unfixed` (Appendix A):

```bash
trivy fs --scanners vuln,misconfig \
  --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed \
  --format json --output <artefact> .
```

**`secret` is deliberately absent from `--scanners`.** Under this diff-scoped,
HIGH/CRITICAL gate a trivy secret finding in an untouched file or at another
severity would not block — weaker than REQ-V15-SCAN-01 on the same class of
finding. One authoritative secret gate, not two that disagree.

`--ignore-unfixed` is scoping, not laxity: a vulnerability with no fixed version
would turn "upstream has not shipped a fix" into "no work may proceed". Unfixed
findings still reach the artefact and report.

[[VERIFY: trivy 0.74.0 flag set — not installed on this host, so the flags above
are transcribed from a 0.73-era pipeline. T4 MUST run `trivy fs --help` at the
pin, confirm every flag, the exit-code semantics and `version_argv` before
writing the invocation into `config/quality_gates.yaml`, and record any
correction in the report.]]

**REQ-V15-SCAN-04 (MUST) — semgrep: vendored, offline, blocking on ERROR.** The
ruleset is **vendored, and a registry cache is not an alternative**. In T7's one
online step the executor resolves the pinned `p/python` and `p/security-audit`
rules, commits their exact content as YAML under `.semgrep/`, and records in
`.semgrep/SOURCES.md` the registry id, the resolution date, the upstream revision
where the source exposes one, and each file's SHA-256. The gate reads nothing but
those repository-local files:

```bash
semgrep scan --config .semgrep/ --severity ERROR --error \
  --metrics=off --disable-version-check --json --output <artefact> .
```

Every flag was confirmed against the installed `semgrep scan --help` (1.167.0),
including that `--config` accepts *"a directory of YAML files"* — which is why
the ruleset is a committed **directory**: semgrep YAML has no include directive.
`--metrics=off` is not performance: this lab grants no tool telemetry consent
(REQ-V15-RTK-02).

**Why not a cache.** A machine-local cache passes on a warmed host and wedges a
fresh clone's fail-closed hooks until someone goes online. Offline operation is
*proven*: §15.3's `N5` runs the gate with the network denied **and semgrep's
cache emptied** and asserts it produces findings from `.semgrep/`.

**REQ-V15-SCAN-05 (MUST) — skylos in shadow, and the ruff-format debt beside
it.** `skylos` (local-first static analysis: dead code, security issues, secrets,
quality regressions) is added in **shadow mode** — `blocking: false`. It runs for
real over the repository root, its findings are partitioned by REQ-V15-GATE-07's
algorithm, printed and written to the artefact, and it cannot fail a profile;
promotion is an explicit edit of that one line (REQ-V15-GATE-08). The report
summarises findings by category and judges whether promotion looks safe for
v1.6; a shadow gate nobody reads is the same as no gate.

[[VERIFY: skylos 4.35.0 CLI surface — not installed here and no local docs, so
the subcommand, path passing, JSON-output flag and exit codes are unknown. T5
MUST confirm them against `skylos --help` at the pin and record the exact `argv`,
`output_format`, `success_exit_codes`, `findings_exit_codes` and `version_argv`
in `config/quality_gates.yaml`.]]

**`ruff format` shares that shadow status, for a specific and serious reason.**
`ruff format --check .` on the current tree reports **44 of 135 files would be
reformatted**, among them **11 of the 12 files `devtools/mutation_check.py`
targets**. Each of the 72 mutation entries locates its target by a **byte-exact
`find` string**, so a tree-wide reformat would silently invalidate almost the
whole mutation gate. Therefore:

- `ruff format --check` is **blocking** for files this release creates
  (`devtools/checks.py`, `devtools/install_hooks.py`,
  `tests/test_v15_standards.py`), born formatted at no cost;
- it is **shadow** for every pre-existing file: the check runs, the count is
  reported, nothing is blocked and **nothing is reformatted**;
- **the split is computed by the runner, not inferred from output.** The new-file
  set is the gate key `ruff-format.blocking_paths`, seeded from
  REQ-V15-TREE-01; a path is "new" only if listed there. The runner intersects
  the scope with that list, runs `ruff format --check` on the intersection as
  **blocking** and again on the remainder as **shadow**, reporting two counts. A
  single call over the whole scope would block on all 44 legacy files or on
  none, and both are wrong;
- the whole-tree reformat is **REQ-V15-NG-04**: known debt, its own release and
  commit, accepted only with `mutation_check.py` green and every `find` string
  re-derived.

`ruff format` also reaches into fenced blocks in `docs/spec/*.md`, so the shadow
report is scoped to `*.py` and `docs/` is excluded outright.

**REQ-V15-SCAN-06 (MUST) — artefacts.** Every `result_mode: findings` gate — the
five scanner invocations, and no other — writes a machine-readable
artefact under `.bench/checks/<profile>/<gate>.json` (`.bench/` is git-ignored).
The report quotes each summary line; raw artefacts are never committed or pasted
into `docs/`.

**REQ-V15-SCAN-07 (MUST) — no `curl … | sh`, ever.** §11's install rules bind
here too: piping an unverified script into a shell is a supply-chain hole in the
supply-chain gate.

**REQ-V15-SCAN-08 (SHOULD) — findings are fixed, not allowlisted.** Where a
blocking gate fires on this release's own new files, the fix is the code. An allowlist or inline suppression needs a comment naming the requirement
it serves and the report lists each one; zero is expected. A secret-path
allowlist is never such a fix (REQ-V15-SCAN-01).

---

## 9. RTK in this project (RTK)

**REQ-V15-RTK-01 (MUST) — the hook.** Add `.claude/settings.json` carrying the
lab repository's own shape, copied rather than reinvented: a `hooks.PreToolUse`
array with one entry whose `"matcher"` is `"Bash"` and whose single hook is
`{ "type": "command", "command": "rtk hook claude" }`.

**Why the file is needed:** settings resolve from the project root and this is
its own git repository with its own `.claude/`, so the lab-level hook never
reached it and every Bash command here has run unfiltered.
`.claude/agent-memory/` is git-ignored; `.claude/settings.json` is not and MUST
be committed. The `.agents → .claude` symlink gives non-Claude agents the same
file.

**REQ-V15-RTK-02 (MUST) — the instruction block.** `CLAUDE.md` today is one
line, `@AGENTS.md`. Keep that import and append the RTK block, copied from the
lab `CLAUDE.md` and adjusted only where it names the settings file. It MUST
state: that the `PreToolUse` hook rewrites every Bash command to its `rtk`
equivalent automatically, in the main context and in subagents, so commands are
written plainly (`git status`, `pytest`, `ls`) and **never** hand-prefixed; the
meta commands used directly (`rtk gain`, `rtk proxy <cmd>`,
`rtk err|log|json|summary <x>`); that on failure rtk saves the untrimmed output
under `~/.local/share/rtk/tee/` and prints the path; and verbatim, **"Telemetry
consent was never granted — NEVER enable it (`rtk telemetry status` must stay
`consent: never asked`)."**

**REQ-V15-RTK-03 (MUST) — rtk 0.47.0, and it is not a gate.** The pin moves
0.46.0 → 0.47.0. rtk is an operator convenience: no requirement depends on it
being installed, no gate calls it, and every gate command in §14 must produce
identical results with the hook disabled. `checks.py doctor` therefore
treats a missing or mismatched rtk as a **warning** (the config key
`doctor.warn_only_tools`) — the single documented exception to
REQ-V15-GATE-03's fail-closed check, because rtk cannot change a verdict.

---

## 10. Prompt format (PRM)

**REQ-V15-PRM-01 (MUST) — the four blocks.** Every prompt file from this release
on carries the existing bullet header, field order unchanged (`Date`, `Executor
model`, `Model reason`, `Harness`, `Stage`, `Owner of`, `REQ ids`), then exactly
these four level-2 blocks, in order, with no others between:

| block | contains | fails the lint when |
|---|---|---|
| `## Goal` | what this prompt is for, in prose; one paragraph | empty |
| `## Constraints` | what the executor may not do: files it must not touch, rules it must obey, budgets | empty |
| `## Acceptance` | how the caller decides it is done — named tests, commands with expected exit codes, artefacts; not "works correctly" | empty, or contains no command, test name or file path |
| `## Stop` | when the executor stops and reports instead of continuing: exhausted repair budget, a discovered benchmark-affecting change, a spec ambiguity | empty |

`## Stop` earns the format: v1.4 discovered its stop condition mid-run (RSN-06
STOP); writing them first makes stopping planned.

**REQ-V15-PRM-02 (MUST)** `docs/prompts/43-v14-verify-run-fixes.md` is written
in this format and is the reference the template derives from. This release does
not rewrite it.

**REQ-V15-PRM-03 (MUST) — the template.** `docs/prompts/TEMPLATE.md` holds the
header and the four blocks with one line of guidance in each, and is itself
valid input to the lint: its placeholder text is non-empty and holds a path.

**REQ-V15-PRM-04 (MUST) — the lint.** `checks.py lint-docs` checks every file
matching `docs/prompts/[0-9][0-9]*.md`:

1. all seven header bullets present, in order, non-empty — **`Model reason`
   included**, the gap `/verify-run` found on the v1.3 run;
2. the four blocks present, in order, non-empty;
3. `## Acceptance` contains at least one of: a backtick-quoted command, a
   `test_`-prefixed identifier, or a repository-relative path.

Files numbered **≤ 43** are exempt from checks 2 and 3 (they predate the
format); the exemption is the **literal filename list** `lint-docs.exempt_files`,
never a numeric comparison, so it cannot silently grow. Check 1 applies to
**all** prompt files, historical ones included.

---

## 11. Dependency and tooling refresh (DEP)

**REQ-V15-DEP-01 (MUST) — Python 3.14.** `.python-version` → `3.14`;
`requires-python` → `">=3.13,<3.15"`; `[tool.ruff] target-version` → `"py313"`
to track the new lower bound; `uv.lock` regenerated by `uv lock` in the same
commit; `AGENTS.md` and `README.md` say 3.14.

3.14 is stable since 2025-10-07 and **3.14.7** the current patch (CPython tag
list; matches the host). The lower bound moves 3.12 → 3.13, so the project still
builds one version back.

**Acceptance: the full gate set — all six commands plus every new gate — green
on 3.14.** Not "the tests pass": a runtime bump breaks what no unit test
covers.

**REQ-V15-DEP-02 (MUST) — the pins.** Every version below was confirmed against
its upstream release index on 2026-09-03.

| component | current | target | upstream |
|---|---|---|---|
| Python | 3.13, `>=3.12,<3.14` | **3.14** (3.14.7), `>=3.13,<3.15` | CPython tags |
| sandbox image | `python:3.13-slim` (floating) | **`python:3.14-slim` pinned by digest** (§12) | Docker Hub |
| ruff | 0.16.5 | **0.16.6** | PyPI |
| gitleaks | 8.24.3 installed | **8.30.1** | GitHub releases (`v8.30.1`) |
| semgrep | 1.167.0 | **1.176.0** | PyPI |
| trivy | not installed | **0.74.0** | GitHub releases (`v0.74.0`) |
| skylos | not installed | **4.35.0** | PyPI |
| rtk | 0.46.0 | **0.47.0** | GitHub releases (`v0.47.0`) |
| httpx / python-dotenv / pytest | 0.28.1 / 1.2.3 / 9.1.1 | **unchanged** | — |


All three of `httpx`, `python-dotenv` and `pytest` are current; **changing them
is a defect** (REQ-V15-NG-06).

**REQ-V15-DEP-03 (MUST) — install channels; the rule has no exception.**
**NEVER `curl … | sh`** — not for any tool, not "just this once because the
vendor's README says so". Exactly two channels:

- **`uv tool install <pkg>==<version>`** for anything on PyPI (semgrep, skylos);
- **a GitHub release asset with a verified checksum** for standalone binaries
  (gitleaks, trivy, rtk): download the asset *and* its published checksum file,
  verify with `sha256sum -c`, only then move the binary onto `PATH`; a download
  whose checksum does not verify is deleted and the run stops.

The report records per tool the channel used and, for binaries, the verified
SHA-256; unrecorded provenance fails acceptance.

**REQ-V15-DEP-04 (MUST)** Pins live in `config/quality_gates.yaml`
(REQ-V15-GATE-02) and `checks.py doctor` fails closed on any difference, newer
included (REQ-V15-GATE-03). rtk is the one warn-only entry (REQ-V15-RTK-03).

**The pins and the installs must not deadlock.** `doctor` is a `pre-push` member
live from T9; T1 writes `quality_gates.yaml`, T2–T6 install one tool each, T13
bumps ruff. Target pins written at T1 would fail `doctor` until T13.

Therefore: **T1 writes each pin at its currently installed version**
(REQ-V15-PRE-02's measured column: ruff 0.16.5, gitleaks 8.24.3, semgrep
1.167.0, rtk 0.46.0), with trivy and skylos absent and therefore **not yet
listed in `tools:`**. Each later task moves its own pin to the target in the
same commit that installs or bumps it — **T2 gitleaks, T3 semgrep, T4 trivy,
T5 skylos, T6 rtk**, one tool per commit; **T13 for ruff, which moves the two
ruff pins and `uv.lock` and touches no other line of `pyproject.toml`** —
`requires-python` and `[tool.ruff] target-version` are T14's (REQ-V15-DEP-05).
`doctor` is green at every commit because the pin never leads the install. By
the end of T13 every pin equals the REQ-V15-DEP-02 target, and
`T-V15-GATE-03`'s drift test proves the two ruff pins agree.

**REQ-V15-DEP-05 (MUST) — one bump, one commit.** The ruff bump, the Python
bump, **each single tool install** and the image bump are **separate commits**,
each with its own prompt file per REQ-V15-CC-03. Per install task, literally:
*install exactly one tool, update exactly that tool's pin and provenance row,
commit before the next.* §17 gives the five tools T2–T6 and ruff T13. Bundling
makes a bisect useless exactly when a runtime bump is the likely cause.

**REQ-V15-DEP-06 (NON-GOAL, stated here because it is a precondition
elsewhere)** LM Studio and the served model are **not touched**. The operator
upgrades LM Studio separately, a **precondition of v1.6** rather than this run;
the executor records what REQ-V15-RPT-02 item 9 asks and changes nothing.

The version string is an **operator input, supplied out of band**: LM Studio is
outside the repository boundary REQ-V15-EC-01 forbids inspecting. The operator
writes it into the `## Operator inputs` section of the T0 `report-v1.5.md`
skeleton. If it is there the report states it; if not, the report states
REQ-V15-RPT-02 item 9's fixed sentence and the run continues. **Its absence is
not a precondition failure and blocks no task**, and the executor never goes
looking for it.

---

## 12. The sandbox image (IMG)

**REQ-V15-IMG-01 (MUST) — pin by digest.** `DEFAULT_DOCKER_IMAGE`
(`config.py:27`) and `.env.example:33` become:

```
python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6
```

That is the OCI image-index digest of `python:3.14-slim`, confirmed two ways on
2026-09-03 (`docker buildx imagetools inspect` and the Docker Hub tag API). The
outgoing image's digest, so the
comparison has a fixed "before", is
`sha256:881d80734ee05dca6f7f42dcb080975652a53c7eda9ba1f03bb8da31aa6a6ec2` —
confirmed locally on 2026-09-03 and re-proved by REQ-V15-PRE-01.4's
`docker image inspect` before the smoke runs.


**REQ-V15-IMG-02 (MUST) — the validator needs no change, and the tests mostly do
not either.** `config._parse_docker_image` (`config.py:555-563`) strips the value
and rejects an empty one, imposing no `name:tag` shape, so `name:tag@sha256:…`
passes unchanged. Do not "improve" it — a stricter validator is a behaviour
change REQ-V15-NG-07 forbids.

`python:3.13-slim` occurs **49 times across five test files**. **Exactly one**
asserts the *default* — `tests/test_v1_guardrails.py:371` — and it is the only
one that changes (§15.1). The other 48 pass an arbitrary image name into a fake;
editing them breaches REQ-V15-EC-03.

**REQ-V15-IMG-03 (MUST) — the exec smoke, byte-compared.** A base-image change
can alter what tools print (coreutils, Python patch, locale), and tool output is
benchmark-affecting (REQ-V15-EC-06). So before the bump is accepted:

1. With the **outgoing** image configured **by digest** —
   `python:3.13-slim@sha256:881d…ec2`, never the floating tag, and only after
   REQ-V15-PRE-01.4's inspect has proved the tag resolves there — drive
   **S02-shaped** and **S03-shaped** commands through the tool layer, not the
   LLM. S02 is `devtools/bench_scenarios.py:166` (arithmetic via `python` through
   `exec`, expecting `396`); S03 is `:172` (create `notes.txt` with three lines,
   count them, expect `3`). Capture the **raw bytes** each `exec` returns,
   envelope included, into `.bench/checks/img/before-{s02,s03}.bin`.
2. Repeat with the **incoming** digest-pinned image into `after-{s02,s03}.bin`.
3. **Compare byte-for-byte.** Identical → the bump is not benchmark-affecting,
   and the report states that with the comparison as evidence.

**If the bytes differ, this becomes a benchmark-affecting change and
REQ-V15-EC-06's escape hatch applies.** The executor MUST NOT call the
difference cosmetic: record the exact diff, then either defer the bump to
**v1.6** (preferred) or run the full before/after benchmark. Deferring is a
planned outcome; silently accepting a byte difference is a defect.

Normalise nothing before comparing: the fix for a value that legitimately varies
is a deterministic smoke command, never a filter applied until it passes.

**REQ-V15-IMG-04 (MUST)** REQ-V1's rule stands: `exec` never pulls at request
time. `README.md`'s pull instruction uses the digest-pinned reference.

**REQ-V15-IMG-05 (SHOULD)** The report records both digests, the pull date and
the `docker image inspect` size, so a later reader comparing token measurements
can tell whether the sandbox moved underneath them.

---

## 13. Reporting (RPT)

**REQ-V15-RPT-01 (MUST) — the report carries the ledger row.** `/verify-run` item 6
requires a row in `economics.md` at the lab root, which REQ-V15-EC-01 forbids
the executor to write — on the v1.4 run the check found a missing row nobody was
permitted to add. The fix is to the process, not the permission:
`docs/reports/report-v1.5.md` MUST contain a section **"Ledger row (paste into
`economics.md`)"** holding one fenced, ready-to-paste table row matching the
ledger's column order exactly:

```
| Project | Ver | Date | Spec (tokens) | Prompts | First run | Bugs | Tokens ↑/↓ | Cost | Model | Harness |
```

The row uses this project's existing link form,
`[tg-agent-bot](https://github.com/axyi/tg-agent-bot)`, and every cell is filled
from this run's evidence — no `TBD`, no placeholder. "Spec (tokens)" carries both
the estimate and the measured byte count, as the v1.4 row does. The operator
pastes it; the executor never touches the file.

**REQ-V15-RPT-02 (MUST) — the report.** Beyond the project standard,
`report-v1.5.md` carries:

1. the gates table — the six existing commands plus every new gate, with
   command, profile and exit code;
2. the **measured** `pre-push` wall-clock (median of three) against the 180 s
   budget, stating that the profile matrix was **not** altered (REQ-V15-HOOK-04);
3. the mutation-gate summary line and wall-clock, `v15-*` included;
4. the `--no-verify` attestation of REQ-V15-EC-09, the `<base>` SHA recorded at
   T0, the `<implementation-tip>` SHA and `checks.py replay --range
   <base>..<implementation-tip>` output as evidence. **The last two are recorded
   by T19's evidence-only commit, not T18's provisional report** — a commit
   cannot contain its own SHA (REQ-V15-ACC-04);
5. per task, whether the RLM rule was applied and to what (REQ-V15-EC-07);
6. the scanner summary: the gitleaks allowlist form and `N4`'s three exit codes,
   trivy findings by severity, the semgrep vendoring evidence (`SOURCES.md`
   hashes plus `N5` offline with an empty cache), skylos shadow findings and a
   promotion judgement for v1.6;
7. the image before/after byte comparison (REQ-V15-IMG-03);
8. install provenance per tool: channel, verified SHA-256 (REQ-V15-DEP-03);
9. the LM Studio version **when the operator supplied it** in the T0 skeleton's
   `## Operator inputs` — recorded, not acted on; otherwise, verbatim: *"LM Studio
   version not inspected: LM Studio is outside the repository boundary and
   unchanged by v1.5."* Either form satisfies this item and neither blocks the
   run (REQ-V15-DEP-06);
10. fix cycles used against the budget of 5;
11. **Deviations**, per REQ-V12-REP-02, process deviations included; "None" only
    when true.

**REQ-V15-RPT-03 (MUST) — the lint enforces both halves.** `checks.py lint-docs`
additionally asserts that `report-v1.5.md` contains the ledger-row section and
that the fenced row has the same number of `|`-separated cells as the ledger
header. It is the same lint that enforces prompt headers (REQ-V15-PRM-04) and a
member of the `full` profile — documentation rules a run under time pressure
forgets, and both were found by `/verify-run`, not by a gate.

**REQ-V15-RPT-04 (MUST)** Usage rows are appended to `docs/llm-usage.md`'s
existing table, never as a headerless fragment (REQ-V12-DOC-02 must not recur).
`docs/reports/tg-post-v1.5.md` is **Russian** and **under 1500 characters** by
`wc -m`; the report quotes the count.

**REQ-V15-RPT-05 (MUST)** `AGENTS.md`'s Stack, gate list, Commit format, Branch
strategy and Reporting sections are updated in the same commits as the changes
they describe — the repository's spec-sync rule. `docs/plan.md` records the v1.5
milestone and the current test count.

---

## 14. Gates

**REQ-V15-GATE-09 (MUST) — the six existing gates, verbatim and in order.**
Restated from `AGENTS.md`; **not one character changes**:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
uv run --locked python devtools/mutation_check.py
```

Gates 1–4 and 6 are unconditional and offline. Gate 5 requires the §3
preconditions and, per REQ-V14-GATE-01, an unreachable LM Studio is a **blocked
run**, not a noted one. The test count MUST be **greater than 728**; state the
exact number in the report.

**REQ-V15-GATE-10 (MUST) — the new gates.**

```bash
python3 devtools/install_hooks.py --check
python3 devtools/checks.py doctor
python3 devtools/checks.py lint-docs
python3 devtools/checks.py run --profile full --since <base>
```

plus the four scanner invocations, written out once in §8 (REQ-V15-SCAN-01, -03,
-04, -05) and executed by the runner from `config/quality_gates.yaml`'s `argv`
lists. §8 is the readable rendering; **the config's `argv` is authoritative**
(REQ-V15-GATE-02). Each scanner takes the **repository root** as its target —
`gitleaks-tree` the materialised tracked tree — and diff scoping is the runner's
partition of the results, not a narrowed invocation (REQ-V15-GATE-07).

**REQ-V15-GATE-11 (MUST) — the profile matrix.** Every gate belongs to exactly
these profiles. The table is the readable rendering of `quality_gates.yaml`'s
`profiles:` block; the config is authoritative and a test asserts they agree
(§15.2, `T-V15-GATE-04`).

| gate | pre-commit | pre-push | full | note |
|---|:---:|:---:|:---:|---|
| `ruff check` (staged) | yes | — | — | `--force-exclude` |
| `ruff check .` (tree) | — | yes | yes | gate 2 |
| `ruff format --check` | yes | yes | yes | **blocking on new files only**, shadow elsewhere (SCAN-05) |
| branch-name check | yes | yes | yes | warn-only on `main` |
| commit-msg checks | own hook | — | via `replay` | REQ-V15-CC-01…03 |
| `gitleaks git --staged` | yes | — | — | staged secrets |
| `gitleaks dir` (tree) | — | yes | yes | tracked set, any severity, not diff-scoped |
| `uv sync --locked` | — | — | yes | gate 1 |
| `pytest` | — | yes | yes | gate 3, 23 s |
| `bot.py --selftest` | — | yes | yes | gate 4, offline |
| `bot.py --selftest-live` | — | — | yes | gate 5; needs `.env`, Docker, LM Studio |
| `mutation_check.py --select v15-` | — | yes | — | 4 entries ≈ 100 s (v1.5.1 measurement; ≈ 92 s at spec-writing time) |
| `mutation_check.py` (all) | — | — | yes | gate 6, 72 entries ≈ 21 min (v1.5.1 measurement; ≈ 16–17 min at spec-writing time, before the four `v15-*` entries) |
| `trivy fs` | — | yes | yes | diff-scoped, HIGH/CRITICAL |
| `semgrep scan` | — | yes | yes | diff-scoped, ERROR |
| `skylos` | — | yes | yes | **shadow** |
| `install_hooks.py --check` | — | yes | yes | hook chain installed |
| `checks.py doctor` | — | yes | yes | pinned versions |
| `checks.py lint-docs` | — | — | yes | prompts + ledger row |

Reporting success requires the **`full`** profile green **plus** the six commands
of REQ-V15-GATE-09 run verbatim in their own right — the runner is a convenience,
never a substitute; where the two disagree the verbatim command wins.

---

## 15. Tests

New tests live in `tests/test_v15_standards.py` unless stated otherwise. They are
offline and deterministic and touch no Docker daemon, no network and no `.env`
(REQ-V12-OFF-01's `conftest.py` guard stays in force). Tests needing a repository
use a **temporary git repo** in a `tmp_path` fixture, never the real one, and
never a live credential as a test secret.

### 15.1 Amendments to existing tests (exhaustive)

| file:line | change | driven by |
|---|---|---|
| `tests/test_v1_guardrails.py:371` | the expected default image becomes the digest-pinned 3.14 reference | REQ-V15-IMG-01 |

That is the **entire** list: the other 48 occurrences of `python:3.13-slim`
under `tests/` MUST NOT be touched (REQ-V15-IMG-02) and no existing test is
reformatted (REQ-V15-SCAN-05).

### 15.2 New unit tests — the mechanisms

| id | asserts |
|---|---|
| `T-V15-CC-01` | the header regex accepts each of the 11 types bare; with a scope; with `!`; with both |
| `T-V15-CC-02` | it rejects: an unknown type (`feature:`), an upper-case type, a missing colon, a missing space after it, an upper-case scope, an empty subject |
| `T-V15-CC-03` | a 73-character header is rejected and a 72-character one accepted — the boundary, both sides |
| `T-V15-CC-04` | a header ending in `.` is rejected; one containing `.md` mid-subject is unaffected |
| `T-V15-CC-05` | the body check accepts `(prompt: docs/prompts/44-go-spec-v1.5.md)` when that file exists in the fixture repo, and rejects both a missing reference and one naming a non-existent file |
| `T-V15-CC-06` | each of `Merge …`, `Revert …`, `fixup! …`, `squash! …` bypasses every check |
| `T-V15-CC-07` | the branch regex accepts `feat/x`, `fix/a-b`, `docs/v1.5`, `chore/x_y`; rejects `feature/x`, `FEAT/x`, `feat/`, `wip`; *warns*, not fails, for `main` and a detached HEAD |
| `T-V15-GATE-01` | `quality_gates.yaml` parses; every gate named in a profile exists in `gates:` and every gate in `gates:` is named by a profile — the bijection, since a gate no profile runs is never red; and every `kind: command` gate declares a `result_mode` whose required key set is exactly present and whose forbidden keys are absent (REQ-V15-GATE-02) |
| `T-V15-GATE-02` | the parser fails closed: an unknown top-level key, a duplicate key, a tab, a boolean where an integer belongs, a gate with no `kind`, a `command` gate with no `argv`, a `command` gate with no `result_mode`, an `exit_status` gate carrying `parser`, `severity` or `artefact`, a `builtin` gate carrying `argv` or `result_mode`, an unknown `handler`, and an unknown placeholder each raise, and each message names the offending key |
| `T-V15-GATE-03` | the ruff pin in `pyproject.toml` equals the one in `quality_gates.yaml` — the drift test of REQ-V15-GATE-03 |
| `T-V15-GATE-04` | REQ-V15-GATE-11's matrix equals the config's `profiles:` block, parsed from both, so the table cannot rot |
| `T-V15-GATE-05` | `--select v15-` selects exactly the four `v15-*` entries; `--select nope-` exits non-zero naming the prefix; `--select` with `--only` is refused |
| `T-V15-GATE-06` | **`replay` path semantics** (REQ-V15-GATE-05): with a `per-file-ignores` entry keyed on a repository-relative path, a commit whose blob violates only that ignored rule is **accepted** by `replay`, as `pre-commit` accepts it — the verdict a `$TMPDIR` absolute path would flip |
| `T-V15-HOOK-01` | `install_hooks.py` on a fresh temp repo sets `core.hooksPath` and marks the hooks executable |
| `T-V15-HOOK-02` | **idempotence**: a second run reports no change and leaves the repo byte-identical |
| `T-V15-HOOK-03` | `--check` exits non-zero when `core.hooksPath` is unset, points elsewhere, a hook is missing, or a hook is not executable — four cases, four distinct messages |
| `T-V15-HOOK-04` | `--check` exits zero on a correctly installed repo |
| `T-V15-HOOK-05` | **first-push scope** (REQ-V15-GATE-07): a fresh branch of three commits with a zero `<remote-sha>` on stdin scopes to all three — a finding in the *second-to-last* commit blocks, where a `HEAD~1..HEAD` fallback would miss it; empty or unparseable stdin fails the gate |
| `T-V15-SCAN-01` | with a stub scanner exiting non-zero, a `blocking: true` gate fails the profile |
| `T-V15-SCAN-02` | with the same stub, a `blocking: false` gate reports findings and the profile still passes |
| `T-V15-SCAN-03` | **fail-closed**: an absent binary fails; a timeout fails; unparseable output fails — three cases, each message naming gate and cause |
| `T-V15-SCAN-04` | **fail-closed in shadow**: an absent binary for a shadow gate makes the profile result **non-zero**, and the shadow gate's failure is recorded by name and cause — findings are withheld, operational failures are not |
| `T-V15-SCAN-05` | diff scoping: given a fixture repo with a pre-existing finding and a new one, a diff-scoped gate blocks on the new file and reports the old |
| `T-V15-SCAN-06` | **the empty-scope trap**: on `main`, with a non-empty commit range, a scope resolving to no files **fails the gate**, the message naming profile and revision |
| `T-V15-SCAN-07` | `gitleaks-tree` is not diff-scoped: a secret in an untouched file blocks |
| `T-V15-SCAN-08` | the `ruff format` partition: with one `blocking_paths` file and one legacy file in scope, both mis-formatted, the profile **fails**, the message names only the new file and the legacy finding is shadow-reported. With only the legacy file mis-formatted the profile **passes** and still reports the count |
| `T-V15-SCAN-10` | **severity membership** (REQ-V15-GATE-12): against a gate configured `severity: [CRITICAL, HIGH]`, two findings identical but for severity — the HIGH blocks, the LOW is reported and does not block; a missing or unknown severity fails the gate closed |
| `T-V15-SCAN-11` | **`gitleaks-tree` inputs, both halves** (REQ-V15-SCAN-01): in a fixture repo holding the sentinel in a *committed* and in a *git-ignored* file, the committed one is found and the git-ignored one is not |
| `T-V15-SCAN-12` | **committed content, not the working tree** (REQ-V15-SCAN-01): a fixture repo whose `HEAD` holds the sentinel in a file the working tree has since **deleted**, and a second whose working tree has **overwritten** it with clean bytes — `gitleaks-tree` blocks in both. A gitlink entry fails the gate closed, naming the path |
| `T-V15-SCAN-09` | **every `result_mode: findings` gate emits its artefact**: for each of `gitleaks-staged`, `gitleaks-tree`, `trivy`, `semgrep`, `skylos` the `argv` carries `{artefact}`, and a fixture run leaves parseable JSON at `.bench/checks/<profile>/<gate>.json`; no artefact fails the gate. An `exit_status` gate is asserted to emit none and to be exempt from the obligation |
| `T-V15-PRM-01` | `lint-docs` accepts a fixture prompt with all seven bullets and four blocks |
| `T-V15-PRM-02` | it rejects a prompt missing `Model reason`, one missing `## Stop`, one with blocks out of order, and one whose `## Acceptance` holds only prose |
| `T-V15-PRM-03` | `docs/prompts/TEMPLATE.md` itself passes the lint |
| `T-V15-PRM-04` | the ≤ 43 exemption is a literal filename list: a *new* file numbered `43` is still linted |

| `T-V15-RPT-01` | `lint-docs` rejects a fixture report with no ledger-row section, and one whose row's cell count differs from the header's |
| `T-V15-TREE-01` | `import config` resolves to `config.py`, not `config/` — the shadowing guard of REQ-V15-TREE-02 |

### 15.3 Negative tests — the gate must be able to fail

Each runs against a temporary repository with the hooks installed.

| id | scenario | expected |
|---|---|---|
| `N1` | commit with subject `added stuff` | rejected; exit non-zero; the message names the header check |
| `N2` | valid header, no `(prompt: …)` body | rejected; the message names the body check |
| `N3` | valid header 80 characters long | rejected; the message names the length check and prints the count |
| `N4` | **REQ-V15-SCAN-02's three assertions, in order**: control (that rule's allowlist entry removed → `SYNTHETIC-CANARY-1` under `tests/` **detected**); suppression (allowlist restored → same value, same path, **suppressed**, exit 0); escape (`SYNTHETIC-CANARY-NOT-ALLOWLISTED-1` outside `tests/` and `docs/` → **caught**, exit non-zero, redacted) | all three, same rule and config but for the control removal; the report records which table form (`[allowlist]` or `[[allowlists]]`) 8.30.1 honours and all three exit codes |
| `N5` | the semgrep gate, network denied **and semgrep's cache emptied** | completes, producing findings from the vendored `.semgrep/` (REQ-V15-SCAN-04) |
| `N6` | a deliberately failing test in the fixture repo, then `pre-push` | the push is refused, the message names `pytest` |
| `N7` | `checks.py doctor` against a stub whose `version_argv` reports a version other than its pin | non-zero, naming tool, expected and found — including when found is **newer** |

### 15.4 Mutation coverage — mutate the gates themselves

**REQ-V15-TST-01 (MUST)** Add **at least four** `v15-*` entries to
`devtools/mutation_check.py`. Each breaks *gate logic*, not the bot, and each is
killed by a named test above:

| id | mutation | killed by |
|---|---|---|
| `v15-severity-comparison-inverted` | REQ-V15-GATE-12's membership condition is inverted, so a configured severity passes and an unconfigured one blocks | `T-V15-SCAN-10` |
| `v15-fail-closed-becomes-fail-open` | the missing/timeout/unparseable branch returns success instead of failure | `T-V15-SCAN-03` |
| `v15-shadow-flag-ignored` | the `blocking` flag is read but discarded, so every gate blocks (or none does) | `T-V15-SCAN-02` |
| `v15-diff-scope-filter-dropped` | the diff-scope filter is replaced by "all files", or by the empty set on `main` | `T-V15-SCAN-05`, `T-V15-SCAN-06` |

Why (`ai-workflows-concept/PLAN-next-flows.md:631-634`): a mutation run there
found a gate whose comparison value the `Gate` object did not understand, so
**all three gates passed unconditionally** — only mutation found it.

**REQ-V15-TST-02 (MUST)** Every mutation entry's `find` string must match its
target file **exactly once**; `mutation_check.py --list` is run and recorded
before the gate is trusted — doubly important because REQ-V15-SCAN-05 keeps the
tree unformatted precisely so existing `find` strings stay valid.

---

## 16. Acceptance, review and report

**REQ-V15-ACC-01 (MUST)** After the `full` profile is green, execute Appendix B
against the repository and, where needed, the live bot. Record pass or fail per
scenario and, per REQ-V12-REP-02, **how** each was driven.

**REQ-V15-ACC-02 (MUST)** Regression check: spec-v1.2's D1 and D2 and spec-v1.4's
S01 acceptance still hold after the Python and image bumps; no earlier posture is
weakened.

**REQ-V15-ACC-03 (MUST) — the final acceptance run, and the freeze it starts.**
T14's `full` run predates the image bump, the docs changes, the review fixes and
the report, so it cannot be the reported run — `lint-docs` sees only a skeleton
there. After T18, **T19 re-runs against the final tree**: the six
verbatim gates of REQ-V15-GATE-09, `checks.py run --profile full --since
<base>`, `checks.py replay --range <base>..<implementation-tip>`
(REQ-V15-ACC-04) and Appendix B.
Failures are fixed and the whole set rerun, inside the five-cycle repair budget.

**After the final successful run no source, test or config change is
permitted.** The one exception is a documentation-only correction of the
evidence that run produced — REQ-V15-ACC-04's evidence-only commit is exactly
that case — and it re-runs the `commit-msg` checks, the `pre-commit` profile,
`lint-docs` and `gitleaks-tree` against the final tree. Anything else voids the
run, and T19 is executed again in full.

**REQ-V15-ACC-04 (MUST) — the implementation tip, frozen before the evidence.**
Replay cannot cover the commit carrying replay's own output, so the range is
frozen before that commit exists. **T18 lands a provisional report carrying
neither the `<implementation-tip>` SHA nor any T19 evidence** — a commit cannot
contain its own SHA, and T19's replay and final-gate output do not exist yet.
That commit's resulting SHA **is** `<implementation-tip>`, the run's last commit
changing source, tests, config or documentation prose. **T19 records that SHA
and every remaining REQ-V15-RPT-02 evidence item** in the evidence-only commit
below.

T19 replays `<base>..<implementation-tip>`; that output and every other T19
artefact the report quotes go into **one final evidence-only commit** touching
`docs/reports/*` and nothing else. That commit is **not** recursively required to
contain replay output covering itself. After it lands, the four checks of the
freeze exception run against the final tree — the whole post-tip obligation, and
they close the freeze.

**REQ-V15-REV-01 (MUST)** Code review by the `code-reviewer` subagent
(`.claude/agents/code-reviewer.md`) in a **clean context**, after the gates pass
and before the final report — never self-review in the writing context. Findings
are fixed or waived with a reason in the report; log the review prompt in
`docs/prompts/`. The reviewer also checks three things this release makes
checkable: that no gate authority (threshold, severity list, shadow flag, profile
membership, argv token, version command) is a literal in `devtools/checks.py`;
that each of the four new gates has a mutation entry; and that no hook holds
logic beyond one call into the runner.

---

## 17. Implementation order

**REQ-V15-ORD-01 (MUST)** Work in this order; each task is one prompt and one
commit. Each carries a **reading map**, and where it crosses a REQ-V15-EC-07
threshold the task is delegated to a subagent with a ≤ 5-line brief returning a
summary.

| T | task | acceptance | reading map (RLM) |
|---|---|---|---|
| **T0** | Preconditions (§3): six v1.4 gates green, `.env` keys by name, docker, git version, both images present. **Record the starting `HEAD` SHA as `<base>`** in the report — the lower bound of every `--since` and `replay --range` in this run (REQ-V15-GATE-07, REQ-V15-ACC-04). Create the `report-v1.5.md` skeleton, its `## Operator inputs` section included (REQ-V15-DEP-06). | all items recorded; `<base>` written down before the first commit; a failure emits the blocker template | `AGENTS.md` (6.9 KB), this section (7.1 KB) — both mapped, both under threshold, no delegation |
| **T1** | `checks.py` skeleton + the YAML reader + `config/quality_gates.yaml`; the CC functions of §5. Tests `T-V15-CC-*`, `T-V15-GATE-01…03`. | those tests green; `ruff check .` green | this spec §5 (59 lines); §7 is **322 lines / 18 KB** — **delegate** the §7 read, summary only; new files otherwise |
| **T2** | Install **gitleaks 8.30.1** (release asset + verified SHA-256, REQ-V15-DEP-03); move **only** the gitleaks pin; re-confirm SCAN-01's and GATE-05's argv at 8.30.1. | resolved version equals the pin; provenance row; argv confirmed | tool `--help` only — no repository reading, no delegation |
| **T3** | Install **semgrep 1.176.0** (`uv tool install semgrep==1.176.0`); move **only** the semgrep pin. | version equals pin; provenance row | tool `--help` only — none |
| **T4** | Install **trivy 0.74.0** (release asset + verified SHA-256); move **only** the trivy pin; run `trivy fs --help` and **resolve REQ-V15-SCAN-03's `[[VERIFY]]` marker** into `config/quality_gates.yaml`. | marker resolved; every flag and the exit-code semantics confirmed | tool `--help` only — none |
| **T5** | Install **skylos 4.35.0** (`uv tool install skylos==4.35.0`); move **only** the skylos pin; run `skylos --help` and **resolve REQ-V15-SCAN-05's `[[VERIFY]]` marker** — subcommand, path passing, JSON flag, exit codes — into the config. | marker resolved; the invocation written into the config | tool `--help` only — none |
| **T6** | Install **rtk 0.47.0** (release asset + verified SHA-256); move **only** the rtk pin, warn-only per REQ-V15-RTK-03. | version equals pin; provenance row | tool `--help` only — none |
| **T7** | The scanners: `.gitleaks.toml` (settle the allowlist form by experiment, `N4`), the vendored `.semgrep/` ruleset + `SOURCES.md` (REQ-V15-SCAN-04 — the run's last online step), trivy and skylos wiring; fail-closed, REQ-V15-GATE-07's diff-scope partition, shadow mode. Tests `T-V15-SCAN-*`, `N4`, `N5`. | those tests green; `N4`'s three exit codes recorded; `N5` green offline with an empty cache | this spec §8 is **212 lines / 12 KB** — **delegate**, summary only; no file outside the repository is opened (REQ-V15-EC-01) |
| **T8** | `.githooks/*` + `install_hooks.py` + `checks.py replay`. Tests `T-V15-HOOK-*`, `N1`, `N2`, `N3`, `N6`. Activate `core.hooksPath`; every commit from here on passes the chain. | those tests green; `install_hooks.py --check` exits 0 | this spec §6 — no delegation |
| **T9** | `checks.py doctor`: expected pins read from the config, resolved versions measured, fail closed on any difference including a newer one. Test `N7`. | `doctor` green against the five installed tools and the installed hook chain | §7's `tools:` paragraph and REQ-V15-GATE-03 (≈ 30 lines), §11 (90 lines) — two bounded mapped reads, no delegation |
| **T10** | RTK: `.claude/settings.json`, the `CLAUDE.md` block. | files present; the telemetry sentence verbatim; a Bash call in a fresh session shows the filter active | the shapes quoted in §9 — no delegation |
| **T11** | Prompt format: `docs/prompts/TEMPLATE.md`, `checks.py lint-docs` (prompts + ledger row). Tests `T-V15-PRM-*`, `T-V15-RPT-01`. | those tests green; every prompt file numbered ≥ 43 passes the lint | `docs/prompts/43-*.md` as reference; the lint sweeps 46 files — **delegate the sweep**, summary only |
| **T12** | Wire the profiles; measure `pre-push` wall-clock three times and record the median — **no demotion**, the budget is observational (REQ-V15-HOOK-04). Add the four `v15-*` mutations (§15.4). Tests `T-V15-GATE-04`, `T-V15-GATE-05`. | median recorded as a number; the profile matrix unchanged; `--select v15-` green; the matrix test green | this spec §14, §15.4; `devtools/mutation_check.py` is 34 KB — **delegate**, reading only the `MUTATIONS` tail and `main()` |
| **T13** | Bump **ruff 0.16.5 → 0.16.6** and nothing else: resolve it through `uv`, move **only** the two ruff pins — `pyproject.toml`'s dev group and `quality_gates.yaml`'s `tools.ruff.version` — and regenerate `uv.lock`. `requires-python`, `.python-version` and `[tool.ruff] target-version` belong to T14 and MUST NOT move here (REQ-V15-DEP-05). Test `T-V15-GATE-03`. | the drift test green; `doctor` green at 0.16.6; `ruff check .` green | `pyproject.toml` dev group + `config/quality_gates.yaml` — both mapped, targeted, no delegation |
| **T14** | Python 3.14: `.python-version`, `requires-python`, `[tool.ruff] target-version`, `uv.lock`, `AGENTS.md`, `README.md` — **no ruff-pin change, T13 owns it**. **Run the full gate set**, `checks.py run --profile full --since <base>` included — `lint-docs` runs here against the report skeleton, and T19's run is the authoritative one for REQ-V15-RPT-03. | every gate of §14 green on 3.14; test count > 728 | `pyproject.toml`, `.python-version`, `uv.lock`, `AGENTS.md`, `README.md` — all mapped, all targeted edits, no delegation |
| **T15** | Sandbox image: the digest pin, `tests/test_v1_guardrails.py:371`, `.env.example`, `README.md`, **and the byte-compared exec smoke of REQ-V15-IMG-03**. | bytes identical → proceed and record; **differ → STOP**, defer to v1.6 per REQ-V15-EC-06 | `config.py:27,555-563`, `bench_scenarios.py:150-185`, `tests/test_v1_guardrails.py:371`, `.env.example`, `README.md` — all mapped, all targeted, no delegation |
| **T16** | `AGENTS.md` and `docs/plan.md` brought true (REQ-V15-RPT-05). | Stack, gate list, Commit format, Branch strategy and Reporting match reality | `AGENTS.md` (6.9 KB) and `docs/plan.md`, both mapped — under threshold, but the diff review is **delegated** anyway |
| **T17** | Review (REQ-V15-REV-01) in a clean context; fix or waive findings. | findings closed or waived with reasons | the reviewer's own context |
| **T18** | **Provisional** `report-v1.5.md` — REQ-V15-RPT-02's elements minus item 4's `<implementation-tip>` SHA and every T19 artefact, ledger row included — plus `tg-post-v1.5.md` (RU, < 1500 chars) and `docs/llm-usage.md` rows. This commit's own SHA **becomes** `<implementation-tip>` (REQ-V15-ACC-04). | `checks.py lint-docs` green; `wc -m` on the post recorded; no self-referential SHA claimed | this run's own artefacts — no delegation |
| **T19** | **Final acceptance (REQ-V15-ACC-03)**: against the final tree, the six verbatim gates of §14, `checks.py run --profile full --since <base>`, `checks.py replay --range <base>..<implementation-tip>` and Appendix B. Fix and rerun inside the repair budget, then land the single evidence-only commit of REQ-V15-ACC-04. | every gate green on the tree that ships; `<implementation-tip>` and RPT-02's remaining evidence recorded in that commit; the freeze of REQ-V15-ACC-03 begins | this run's own artefacts — no delegation |

T14 and T15 are deliberately late: they are the two tasks that can move
observable behaviour. T2–T6 and T13 are atomic — one tool, one pin, one commit (REQ-V15-DEP-05). The `commit-msg` and `pre-commit` chain is live from **T8**;
no push is attempted before **T12**, by when every `pre-push` member exists.

---

## 18. Non-goals for v1.5

Implementing any of these is a defect.

| ID | NON-GOAL | why |
|---|---|---|
| REQ-V15-NG-01 | **The v1.6 agent-behaviour work: tool-use quality, the reasoning retry after the LM Studio upgrade, any benchmark change.** | v1.6 owns it; it needs an upgrade this release does not perform, and is benchmark-affecting by construction (REQ-V15-EC-06) |
| REQ-V15-NG-02 | CI, GitHub Actions, any hosted pipeline | none exists today (`.github/` absent); every gate here is local, which is the point |
| REQ-V15-NG-03 | SonarQube or any hosted code-quality service | skylos in shadow is this release's quality gate; a second one before the first is promoted is noise |
| REQ-V15-NG-04 | The whole-tree `ruff format` reformat | 44 of 135 files, 11 of them mutation targets whose byte-exact `find` strings it would invalidate (REQ-V15-SCAN-05) |
| REQ-V15-NG-05 | Commit signing, SBOM generation, provenance attestation, dependency-update automation | each is a project of its own; none needed to make the four gates work |
| REQ-V15-NG-06 | Bumping `httpx`, `python-dotenv` or `pytest`; adding any runtime dependency | all three are current; a bump nobody needs is a diff read for nothing |
| REQ-V15-NG-07 | Changing `_parse_docker_image`, or any bot behaviour not required above | REQ-V15-IMG-02: it already accepts the digest form |
| REQ-V15-NG-08 | Upgrading LM Studio or the served model | the operator does it separately, a v1.6 precondition (REQ-V15-DEP-06) |
| REQ-V15-NG-09 | A YAML dependency, a hook framework (`pre-commit`, `husky`, `lefthook`), a third-party mutation framework | REQ-V15-EC-01: stdlib plus `git`; three shims and a runner |

---

## Appendix A — requirement traceability

| Requirement | Source | Verified by |
|---|---|---|
| REQ-V15-EC-06 no-benchmark + escape hatch | `AGENTS.md` § Benchmark | the report's "Benchmark-affecting changes"; REQ-V15-IMG-03's byte comparison |
| REQ-V15-EC-07 RLM rule | lab `AGENTS.md` rule 5 | the per-task delegation record |
| REQ-V15-EC-09 `--no-verify` ban | this spec | `replay --range <base>..<implementation-tip>`; `T-V15-HOOK-03` |
| REQ-V15-ACC-04 frozen implementation tip | round-2 cross-review (R2-1) | the recorded SHA; the single evidence-only commit |
| REQ-V15-CC-01 header regex | conventionalcommits.org v1.0.0; `rtl-family.md:31` minus the ticket key | `T-V15-CC-01`, `T-V15-CC-02` |
| REQ-V15-CC-03 prompt reference | project `AGENTS.md` § Commit format, wording preserved | `T-V15-CC-05`, `N2` |
| REQ-V15-CC-04 warn-only on `main` | project `AGENTS.md` § Branch strategy, solo-run exception | `T-V15-CC-07` |
| REQ-V15-HOOK-05 idempotent installer | this spec | `T-V15-HOOK-02`, `E9` |
| REQ-V15-GATE-02 config is the only authority; two gate kinds | `ai-workflows-concept/config/security_gates.yaml` (policy-as-config) | `T-V15-GATE-01`, `-02`, `-04`, `T-V15-SCAN-09` |
| REQ-V15-GATE-03 pinned versions fail closed; `doctor` runs `tools.version_argv` verbatim | this spec | `N7`, `T-V15-GATE-02`, `-03` |
| REQ-V15-GATE-12 normalised severity, membership test | round-2 cross-review (R2-5) | `T-V15-SCAN-10`, `v15-severity-comparison-inverted` |
| REQ-V15-GATE-06 fail-closed | same file `:36-40` | `T-V15-SCAN-03`, `-04`, `v15-fail-closed-becomes-fail-open` |
| REQ-V15-GATE-07 diff scoping, empty-scope trap, stdin-derived `pre-push` scope | same file `:7-11`, `:34`; git's `pre-push` stdin contract | `T-V15-SCAN-05`, `-06`, `T-V15-HOOK-05`, `v15-diff-scope-filter-dropped` |
| REQ-V15-GATE-05 `replay` substitutes; ruff via `--stdin-filename` | this spec; `ruff check/format --help` at 0.16.5 | `T-V15-GATE-06` |

| REQ-V15-GATE-08 shadow then promote | `ai-workflows-concept/README.md:313-318` | `T-V15-SCAN-02`, `v15-shadow-flag-ignored` |
| REQ-V15-SCAN-01 secrets block anywhere; `gitleaks-tree` scans committed content materialised from git objects | `security_gates.yaml:22-24`; REQ-V15-PRE-01.3's `.env` | `T-V15-SCAN-07`, `-11`, `-12`, `N4` |
| REQ-V15-SCAN-02 allowlist proven by a control + two assertions | a sibling project's gitleaks config, quoted in §8, never opened; measured 2026-09-03: default rules do **not** detect `SYNTHETIC-CANARY-1` | `N4` |
| REQ-V15-SCAN-03 trivy, `vuln,misconfig` only | `idp-concept/.../stdSecScan.groovy:9-11`; `security_gates.yaml:31` | T4's `--help` confirmation; the artefact |
| REQ-V15-SCAN-05 skylos shadow; ruff-format debt | `ai-workflows-concept/README.md:313-318`; measured 44/135 files, 11/12 mutation targets | `T-V15-SCAN-08`; `mutation_check.py` green |
| REQ-V15-TST-01 mutate the gates | `ai-workflows-concept/PLAN-next-flows.md:631-634` | the four `v15-*` entries |
| REQ-V15-PRM-04 `Model reason` lint | `/verify-run` on the v1.3 run | `T-V15-PRM-02` |
| REQ-V15-RPT-01 ledger row in the report | `/verify-run` item 6 vs REQ-V1-EC-01 | `T-V15-RPT-01` |
| REQ-V15-DEP-01…05 pins, channels, one bump per commit (ruff T13, Python T14) | upstream indexes checked 2026-09-03 | `doctor`; `T-V15-GATE-03`; the provenance table |
| REQ-V15-IMG-01 digest pin, both ends | `docker buildx imagetools inspect` and the Hub tag API agreeing; the outgoing digest confirmed locally 2026-09-03 | §2's table; PRE-01.4's `docker image inspect` |
| REQ-V15-IMG-03 exec smoke | `AGENTS.md` § Benchmark (tool output is benchmark-affecting) | the byte-comparison artefacts; E10 |
| REQ-V15-RTK-01 project-local hook | lab `.claude/settings.json`; this repo has its own `.claude/` | file present and committed |

## Appendix B — acceptance scenarios (Gherkin, written before code)

```gherkin
# Every scenario runs against a throwaway git repository in a temporary
# directory, except E7 and E10, which run against this repository.
# SAFETY: never a live credential as a test secret — REQ-V15-SCAN-02's synthetic
# canary pattern is the only permitted value.

Scenario: E1 — a badly formed commit message is refused          # = N1
  Given the hook chain is installed via install_hooks.py
  When a commit is attempted with the subject "added stuff"
  Then it is refused, no object created, the header check named and
       the correct form printed

Scenario: E2 — a well-formed message with no prompt reference is refused  # = N2
  Given the hook chain is installed
  When a commit is attempted with subject "feat(gates): add the runner"
       and a body naming no prompt file
  Then it is refused, and the message names the body check

Scenario: E3 — a merge commit passes untouched          # = T-V15-CC-06
  Given the hook chain is installed
  When git generates a merge commit whose subject begins with "Merge"
  Then it is accepted without any check applied

Scenario: E4 — the allowlist is proven load-bearing, and proven not to overreach
  Given .gitleaks.toml is committed with the synthetic-canary-test rule
  When the fixture removes that rule's allowlist entry
   And a file under tests/ holding SYNTHETIC-CANARY-1 is staged and scanned
  Then the scan exits non-zero — the rule fires, so the next step means something
  When the allowlist entry is restored and the same file is staged and scanned
  Then the scan exits 0 and reports no finding
  When a file outside tests/ and docs/ holding
       SYNTHETIC-CANARY-NOT-ALLOWLISTED-1 is staged instead
  Then the scan exits non-zero, the commit is refused
  And the finding is printed redacted, never showing the value

Scenario: E5 — a failing test blocks the push          # = N6
  Given the hook chain is installed and a test in the suite fails
  When a push is attempted
  Then it is refused, the message names pytest, the wall-clock is printed

Scenario: E6 — a missing scanner fails the gate rather than passing it
  Given config/quality_gates.yaml pins trivy as blocking
  And the trivy binary is not on PATH
  When the pre-push profile runs
  Then the profile fails, and no gate is reported as passed
  And the message names trivy and says the gate could not run

Scenario: E7 — a shadow gate reports but does not block
  Given skylos is configured with blocking: false
  And skylos reports findings inside the changed-file partition
  When the pre-push profile runs
  Then the findings are printed and written to the artefact directory
  And the profile passes
  When blocking is edited to true in config/quality_gates.yaml
  Then the same run fails

Scenario: E8 — the diff scope is never silently empty on main
  Given the working branch is main
  When checks.py run --profile full is invoked with no --since
  Then it is refused before any gate runs, naming the missing option
  Given the same branch with --since <base> naming a non-empty commit range
  When a diff-scoped gate computes a scope that resolves to no files
  Then the gate fails, naming the profile and the revision it used

Scenario: E9 — the installer is idempotent          # = T-V15-HOOK-02/04
  Given install_hooks.py has been run once
  When it is run a second time
  Then it reports nothing changed, --check exits 0, and core.hooksPath,
       the hook files and their modes are byte-identical

Scenario: E10 — the image bump does not change tool output
  Given docker image inspect proves python:3.13-slim resolves to sha256:881d…ec2
  And the outgoing sandbox image is configured by that digest, not by the tag
  When S02-shaped and S03-shaped commands are driven through the tool layer
  Then their raw returned bytes are captured
  When the digest-pinned 3.14 image is configured and the same commands run
  Then the captured bytes are identical to the first capture
  And the report states the bump is not benchmark-affecting
  # If they are NOT identical: the run stops, records the diff and defers the
  # image bump to v1.6 per REQ-V15-EC-06. Proceeding anyway is a defect.

Scenario: E11 — the report carries a paste-ready ledger row
  Given the run is complete
  When checks.py lint-docs runs
  Then report-v1.5.md contains a "Ledger row" section, no cell a placeholder
  And the fenced row has the same cell count as economics.md's header

Scenario: E12 — a prompt without a Model reason is refused          # = T-V15-PRM-02
  Given a prompt file numbered above 43 with no "Model reason" bullet
  When checks.py lint-docs runs
  Then it exits non-zero, naming the file and the missing bullet
```

## Appendix C — cross-review log

**Rounds 1–3 of 3, termination: `round_limit`** — the lab's stop criterion for
this spec; challenger **OpenAI Codex `gpt-5.6-sol`** via the lab debate loop.

### Round 1 of at most 3 — against spec-v1.5 as delivered; all ten accepted

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R1-1 | Crit | EC-01, AMEND-01, SCAN-02 | accepted | boundary bans project/lab **files**; installs, `--help`, Docker, caches permitted; external `.gitleaks.toml` path dropped, its finding quoted in §8 |
| R1-2 | Crit | DEP-04, DEP-05, PRE-02, §17 | accepted | old T2 split into T2–T6 (one tool, one pin, one commit) plus a `doctor` task, table renumbered; "four binaries" → five pinned tools |
| R1-3 | Crit | SCAN-01, SCAN-03, GATE-02/10 | adapted | trivy `--scanners vuln,misconfig`, its secret scanner off; gitleaks the sole secret gate, whole-tree, any severity |
| R1-4 | Crit | RPT-02.9, DEP-06, T0 | adapted | version read from the T0 skeleton's `## Operator inputs` when present, else the fixed sentence; never a blocker |
| R1-5 | High | ACC-03 (new), §17 | accepted | final acceptance run over the shipped tree (six gates, `full`, `replay`, Appendix B) plus the freeze |
| R1-6 | High | HOOK-04, RPT-02.2, T12 | adapted | the 180 s budget is observational and moves no gate, so GATE-11 and `T-V15-GATE-04` stay exact |

| R1-7 | High | GATE-07, SCAN-03/04/05 | accepted | diff-scoped scanners run over `.`; the runner partitions by changed-file set, blocks in-scope only, fails closed on a bad path |
| R1-8 | High | GATE-02, SCAN-01, T-V15-SCAN-09 | accepted | full YAML schema (argv, placeholders, format, parser, exit codes, artefact); Python parses only; gitleaks gains JSON report flags |
| R1-9 | High | EC-09, GATE-05 | accepted | replay demoted to "final policy accepts these commits"; exact single-commit gitleaks command (verified on 8.24.3) |
| R1-10 | High | SCAN-04, PRE-01, TREE-01, N5 | adapted | vendored `.semgrep/` + `SOURCES.md` hashes, cache option gone, offline proof with an empty cache; `--config` takes the directory |

### Round 2 of at most 3 — against the round-1 spec; all ten accepted

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R2-1 | Crit | EC-09, ACC-03, **ACC-04** (new), RPT-02.4, §17 | accepted | `<implementation-tip>` frozen at T18's report commit; replay covers `<base>..<tip>` and its output lands in one evidence-only commit not replayed against itself |
| R2-2 | Crit | GATE-01…03, GATE-11 | accepted | `kind: command\|builtin` with disjoint required keys, three named handlers, every gate key enumerated, top-level set fixed; `tools.version_argv`/`version_parser` run verbatim by `doctor`; adapter/handler ids allowed as Python literals |
| R2-3 | Crit | HOOK-05, DEP-04, §17 | accepted | hooks moved ahead of `doctor` so `doctor` keeps one meaning: T7 scanners, **T8 hooks + activation**, **T9 doctor** (`.gitleaks.toml` must precede a live chain) |
| R2-4 | Crit | SCAN-02, N4, E4 | accepted | measured that default rules do **not** detect `SYNTHETIC-CANARY-1`; added the repo-local `synthetic-canary-test` rule and a control → suppression → escape protocol with the sentinel `SYNTHETIC-CANARY-NOT-ALLOWLISTED-1` |
| R2-5 | Crit | **GATE-12** (new), TST-01, T-V15-SCAN-10 | accepted | explicit policy, not removal: normalised upper-cased severity, blocking by **membership** in the gate's `severity` list, unknown/missing fails closed; the mutation inverts that condition, `T-V15-SCAN-10` kills it |
| R2-6 | High | GATE-07, HOOK-04, T-V15-HOOK-05 | accepted | `pre-push` scope from git's stdin ref records, zero `<remote-sha>` → merge-base with `scope.base_branch` or `--since`; `HEAD~1..HEAD` removed as a fallback; second-to-last-commit test |
| R2-7 | High | PRE-01.3, SCAN-01, GATE-02, T-V15-SCAN-11 | accepted | `gitleaks-tree` scans a `$TMPDIR` tree materialised from `git ls-files -z` (`{tracked_tree}`): `.env` and every git-ignored file out, every tracked file in; staged scanning covers new files; two-half test; **no secret-path allowlist** |
| R2-8 | High | DEP-04, DEP-05, §17 | accepted | new **T13** bumps ruff 0.16.6 alone (both pins + `uv.lock`); T14 owns `requires-python`, `.python-version`, `target-version` and touches no ruff pin |
| R2-9 | High | GATE-05, T-V15-GATE-06 | accepted | `replay` runs ruff per blob through `--stdin-filename <repo-relative path>` from the repository root, not a `$TMPDIR` tree; flags verified on 0.16.5; `per-file-ignores` test pins the semantics |
| R2-10 | High | PRE-01.4/.5, IMG-01, IMG-03, E10 | accepted | `docker image inspect` must prove `python:3.13-slim` resolves to `sha256:881d…ec2` (verified locally 2026-09-03); on mismatch pulling that digest is sanctioned; the "before" run is configured by digest, never the floating tag |

### Round 3 of 3 — against the round-2 spec; all eight accepted

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R3-1 | Crit | GATE-06, T-V15-SCAN-04, TST-01 | accepted | shadow withholds **findings**, never operational failures: missing, timeout, crash, unexpected exit code, absent artefact or unparseable output fails the profile closed; `T-V15-SCAN-04` expects non-zero with the shadow failure recorded, and is no longer a killer of `v15-shadow-flag-ignored` |
| R3-2 | Crit | GATE-01, GATE-07, GATE-10, ACC-03, T0, T14, T19, E8 | accepted | `run` gains `--since <rev>`, mutually exclusive with `--stdin-refs`; `full` on `main` without it is refused before any gate runs; `<base>` (undefined in the spec before this round) is the HEAD recorded at T0, and every acceptance invocation now passes it |
| R3-3 | Crit | SCAN-01, SCAN-06, T-V15-SCAN-11/-12 | adapted | `{tracked_tree}` is materialised from **git objects** (`ls-tree`/`cat-file`), never filesystem paths: `HEAD` for `full`, the deduplicated union of blobs in the pushed ranges for `pre-push`. Repository facts shaped the edges: the one tracked symlink (`.agents → .claude`) becomes a regular file holding the link text; zero gitlinks makes the `160000` rejection a guard. New `T-V15-SCAN-12`: `HEAD` holds a secret the working tree deleted or overwrote, and it still blocks |
| R3-4 | Crit | ACC-04, T18, T19 | accepted | a commit cannot contain its own SHA: T18 lands a **provisional** report without the tip SHA or T19 evidence, that commit's SHA *becomes* `<implementation-tip>`, and T19's evidence-only commit records both |
| R3-5 | High | GATE-02, GATE-11 | accepted | the illustrative `profiles:` block now equals the matrix — `ruff-format` and `branch-name` in all three profiles; the matrix's three stray blank lines, which split it into fragments `T-V15-GATE-04` could not parse, are repaired |
| R3-6 | High | EC-02 | accepted | every §§5–13 requirement needs a named unit test, negative test, acceptance scenario or recorded artefact; mutation proof only for §15.4's four gate mechanisms |
| R3-7 | High | EC-07, §17 | adapted | second branch taken: the file clause is narrowed to exploration **beyond the reading map**, so targeted multi-file edits (T13–T15) do not delegate. Re-checking every map moved more than the critique named: §7 is 322 lines / 18 KB and §8 212 / 12 KB, so T1 and T7 delegate on the **size** clause anyway, and T9 — unnamed in the critique — was re-mapped to two bounded reads |
| R3-8 | High | GATE-02, T-V15-GATE-01/-02, T-V15-SCAN-09 | adapted | `result_mode: exit_status\|findings` adopted with the given classification, extended where the split left holes: legal on `kind: command` only, and `diff_scoped: true` on an `exit_status` gate partitions the **argv path list before invoking** — REQ-V15-SCAN-05's `ruff-format`, which §6 already ran twice for that reason |

**Rounds 1–3: 28 findings, 28 accepted (7 adapted to repository facts, recorded
per row); nothing refused.**
