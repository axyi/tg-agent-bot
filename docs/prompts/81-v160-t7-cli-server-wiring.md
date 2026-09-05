# Prompt 81 — spec-v1.6.0 T7: CLI grammar, server start/stop, /status

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §"Executor: claude-sonnet-5"; §14.1 marks T7
  "delegate: no" -- the CLI grammar and server lifecycle interleave with
  `main()`'s existing startup/shutdown sequence closely enough that a fresh
  subagent would need to re-derive the same control-flow understanding
  already built up implementing T3 and T6
- **Harness:** Claude Code
- **Stage:** T7
- **Owner of:** `config.py` (`dashboard_enabled`, `dashboard_port`),
  `bot.py` (CLI grammar, `--version`, `--no-dashboard`, server start/stop,
  `/status`'s eighth line, `USAGE`), `tests/conftest.py` (the
  `socket.socket.bind` guard), `.env.example`,
  `tests/test_v160_dashboard.py` (T7's tests, appended),
  `tests/test_v1_guardrails.py` (one amendment)
- **REQ ids:** REQ-V160-SRV-01, -02, -03, -04, -05, -07, -09, VER-01, -02, -03

## Goal

Add `Config.dashboard_enabled`/`dashboard_port` (parsed the existing
`_parse_bool`/`_parse_int` way). Rewrite `bot.py`'s CLI grammar: no
arguments runs polling plus the dashboard; `--no-dashboard` suppresses just
the dashboard; `--selftest`/`--selftest-live`/`--version` are mutually
exclusive and bind no port; `--version` reads `pyproject.toml` fresh via
`tomllib` (never cached) and prints `tg-agent-bot <version>`; anything else
is a usage error, exit 2. Wire the dashboard's actual start (via
`dashboard_server.build_server`) and stop (`shutdown()` +
`server_close()`, joined with a 5s timeout) around `poll_loop`, threading a
`dashboard_status` string through `poll_loop` → `process_update` →
`_render_status`'s new eighth line. Extend `tests/conftest.py`'s offline
guard with a `socket.socket.bind` patch restricting every test's real binds
to `("127.0.0.1", 0)`.

## Constraints

- **The startup guard catches broadly, not narrowly.** REQ-V160-SRV-07 says
  "a failure to bind... to create the server, or to start the thread is
  caught" — deliberately not scoped to `OSError`. This turned out to matter
  for more than production robustness: `tests/conftest.py`'s new
  `socket.socket.bind` guard raises `RuntimeError` (not `OSError`) for any
  bind outside `("127.0.0.1", 0)`, and several **pre-existing** tests
  (`test_main_disables_exec_when_the_backend_is_down` and its neighbours)
  call `bot.main([])` with the real `dashboard_port` default (8765) and no
  mock for `dashboard_server.build_server`. A narrow `except OSError` would
  have left those tests crashing on an uncaught `RuntimeError` — exactly
  the "an unlisted test fails, the change is wrong" trap REQ-V160-EC-03
  warns about. Catching `Exception` broadly at that one call site resolves
  it cleanly, matches the spec's own wording, and required touching zero
  unlisted tests.
- **`bot.py` imports `PROJECT_ROOT` by value** (`from config import
  PROJECT_ROOT`), a separate binding from `config.PROJECT_ROOT` taken at
  import time. The autouse `isolated_project_root` fixture
  (`tests/conftest.py`) only patches the latter, so any test exercising
  `bot._read_version()`/`--version` needs to patch `bot.PROJECT_ROOT`
  itself — precedent already existed at `tests/test_v1_guardrails.py:1166`
  for the same reason; followed it rather than rediscovering it the hard
  way twice.
- Only one existing test amended, per §15.1: `tests/test_v1_guardrails.py:1398`'s
  asserted `USAGE` string.
- `dashboard_status` threads through `poll_loop`/`process_update` as a
  plain string with a safe default (`"off (--no-dashboard)"`), so every
  existing caller/fake that doesn't pass it keeps working unamended
  (REQ-V160-EC-05).
- Zero new dependencies: `tomllib` is stdlib (3.11+).
- One prompt → one commit, referencing this file.

## Acceptance

- `tests/test_v160_dashboard.py`'s T7 section (8 new tests) covers
  `DASHBOARD_PORT` range validation, `DASHBOARD_ENABLED=false` and
  `--no-dashboard` each producing the right `/status` phrase (and the flag
  winning when both would apply), the bind address never becoming
  configurable, `--selftest` binding nothing even with `socket.socket.bind`
  patched to always raise, `/status`'s eighth line in all four states,
  the full N9 usage-error sweep (mutually exclusive flags together,
  `--no-dashboard` doubled, an unknown flag, a positional argument), and
  `--version` matching an independently-read `pyproject.toml` plus N10's
  clean-error path when the file is missing the version key.
- `uv run --locked ruff check .` exits 0.
- `uv run --locked pytest` exits 0, 949 passed (941 + 8 new).
- `uv run --locked python devtools/mutation_check.py` exits 0, 72/72 killed.
- No test outside `tests/test_v1_guardrails.py:1398` needed amendment —
  verified by running the full suite before writing a single new test, to
  confirm the broad-`Exception` startup guard alone was sufficient.

## Stop

If any pre-existing test had needed amendment to accommodate the new
server-start code path, that would be exactly the "stop and reconsider"
signal REQ-V160-EC-03 describes — resolved instead by widening the
exception clause to match the spec's own wording, not by touching the test.
