# Implementation report — spec-v1.8.0

**Status: T0 complete — all six gates green on the unchanged tree, plus
`doctor` and `install_hooks.py --check`. Gate 5 needed one re-pin (see
deviation note below). Test floor re-measured at 1133, no drift. Proceeding
to T1.**

- **Spec:** `docs/spec/spec-v1.8.0.md`
- **Spec `sha256` at T0:** `fad1e70998d77e5e2e7501edea5b4c16a7caa01fe14560ae528152ac6897f138`
- **Delta:** `docs/spec/spec-v1.8.0-delta-1.md` (§5.1 frozen design plan, gate matrix, Appendix C)
- **Handoff:** `docs/handoff-v1.8.0.md`
- **Executor:** claude-sonnet-5 (Claude Code)
- **`<base>`** (HEAD before this run's first commit): `28e6169797be98bbf8bb874faa88e4758032c2ad`
- **`<implementation-tip>`**: not reached yet — filled at T9.

## Operator inputs

The `go` request text, verbatim:

```text
go docs/spec/spec-v1.8.0.md
```

No operator input was needed in the request text per `docs/handoff-v1.8.0.md`
(the release makes no live model call). One clarifying exchange happened
mid-T0, recorded below.

## Preconditions (T0 — REQ-V180-EC-01, EC-11 row T0)

Six gates of §9, offline except gate 5, run on the unchanged tree before any
change in this run.

| # | gate | command | exit | note |
|---|---|---|---|---|
| 1 | uv sync | `uv sync --locked` | 0 | |
| 2 | ruff check | `uv run --locked ruff check .` | 0 | |
| 3 | pytest | `uv run --locked pytest` | 0 | 1132 passed, 1 skipped = 1133 |
| 4 | selftest | `uv run --locked python bot.py --selftest` | 0 | |
| 5 | selftest-live | `uv run --locked python bot.py --selftest-live` | 0 (after re-pin) | see deviation below |
| 6 | mutation_check.py | `uv run --locked python devtools/mutation_check.py` | 0 | 92 mutations, 92 killed, 0 survived, 0 errored, 0 drifted |

Also at T0: `uv run --locked python devtools/checks.py doctor` → `[PASS] doctor: all tools at pin, hooks installed`.
`uv run --locked python devtools/install_hooks.py --check` → `install_hooks.py --check: hooks installed correctly`.

**Test floor:** `pytest --collect-only -q` re-measured at `<base>` = **1133**,
matching `AGENTS.md:103`'s stated figure exactly — no drift, floor stays 1133.

## Deviation: gate 5's first run blocked on LM Studio reachability

Gate 5 failed on first run: `live: FAIL lmstudio — ConnectTimeout: timed
out`. Per REQ-V180-EC-04, no `.env` value may be printed, and no task may
edit `.env` blindly. The executor probed the three IPs on record for the
GPU box's floating address (`172.16.50.233`, `192.168.0.145`,
`192.168.178.170`, each with `curl -sS -m 3 http://<ip>:1234/v1/models`);
none answered. The executor stopped and asked the operator rather than
guessing (`AskUserQuestion`) — this is a T0 blocker per the spec's own
acceptance row, not something a sed-in-the-dark should resolve. The
operator brought the box online; a second probe found `192.168.0.145:1234`
serving `qwen/qwen3.8-27b` among other models. `.env`'s `LMSTUDIO_BASE_URL`
was re-pinned to that address by a single-line `sed -i` (no `cat`, no
`.env.bak`, no value ever printed — only host-pattern-redacted greps were
used to confirm the change). Gate 5 then passed all six checks. `.env` stays
git-ignored and untouched by any commit.

## Per-task delegation record (REQ-V180-EC-07 item 6)

| task | delegated? | to what | map vs actual |
|---|---|---|---|
| T0 | no — *artefacts only* | — | map: `AGENTS.md:92-121`, `config/quality_gates.yaml:330-340`; actual: same, plus `.env`'s `LMSTUDIO_BASE_URL` line (working-tree only, never committed) to unblock gate 5 |

## Project-prompt review record (REQ-V180-AGT-04)

Not reached yet — T1.

## Pre-existing dead code surfaced, not fixed (NG-09)

Not reached yet — recorded at T6/T7 (`_STATIC_ROUTES`, `dashboard_server.py:53-55`, and the 8 skylos shadow findings in the same module).

## Benchmark rule (REQ-V180-EC-06)

Not reached yet — this release makes no token-affecting change; the
statement that the rule does not fire, with reason and touched modules, is
recorded once every code task has landed.

## `--no-verify` attestation

Not reached yet — recorded at closure.

---

*(This report is a T0 skeleton per REQ-V180-EC-11. Sections are filled in
task order; "not reached yet" is replaced with content or, on the stop
route, with the explicit words "not reached: `<task>` stop" per
REQ-V180-REV-04 item 1.)*
