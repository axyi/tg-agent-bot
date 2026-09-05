# Prompt 80 — spec-v1.6.0 T6: dashboard_server.py

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §"Executor: claude-sonnet-5"; §14.1 marks T6
  "delegate: no" -- building one new, self-contained module in a single
  `Write`, the same shape as T1's `tracing.py`, not the kind of scattered
  multi-location edit that argues for delegation
- **Harness:** Claude Code
- **Stage:** T6
- **Owner of:** `dashboard_server.py` (new), `dashboard_render.py` (adds
  `MAX_SPANS_PER_TRACE`), `tests/test_v160_dashboard.py` (T6's tests,
  appended)
- **REQ ids:** REQ-V160-API-01..06, REQ-V160-SRV-01..11

## Goal

Build the live dashboard's HTTP server: `ThreadingHTTPServer` bound to a
fixed `127.0.0.1`, GET/HEAD only (any other method, known or exotic, is 405
with `Allow: GET, HEAD`), a strict path allowlist (`/`, `/traces`, `/tools`,
`/api/health`, `/api/usage`, `/api/traces`, `/api/tools`, plus the two
32-hex-char trace-id patterns) compared after stripping the query string
with no normalisation/unquoting/`..` resolution, the four security headers
on every response including every error path, a `Host` header check before
routing (exactly one header, exactly `127.0.0.1:<actual_port>`), a
per-request read-only connection (`storage.connect_readonly`) closed in
`finally`, every response serialised into memory first with a 2 MiB cap
enforced as a fixed content-free 500, and the five JSON endpoints plus three
HTML pages built entirely through `dashboard_render.py` (this module holds
no HTML literal of its own). `build_server(*, db_path, port, host=...)`
raises plainly on a bind failure -- the REQ-V160-SRV-07 degraded-start guard
(catch, log once, continue without the dashboard, no retry) is `bot.py`'s
job (T7), not this module's.

## Constraints

- `MAX_SPANS_PER_TRACE = 64` added to `dashboard_render.py` (T5 didn't need
  it; it's an API-05 concern). The legitimate maximum derived from
  `agent.py`'s own limits is 35 -- comfortably under 64.
- `parse_request()` is overridden to enforce the 8 KiB request-line cap and
  64-header cap with a 400 *before* the base class's own far larger (64 KiB,
  414) defaults would fire.
- Any method name, including ones with no `do_<VERB>` handler at all, must
  produce 405 -- solved via `__getattr__` returning a bound
  `_method_not_allowed` for any `do_*` attribute lookup, rather than
  enumerating every HTTP verb `http.server` might dispatch to.
- `version_string()` overridden directly (not just `server_version`/
  `sys_version`) so the `Server:` header reads exactly `tg-agent-bot`.
- `_project_version()` reads `config.PROJECT_ROOT / "pyproject.toml"` fresh
  on every `/api/health` call (REQ-V160-VER-01's single source of truth,
  never cached) -- this surfaced a test-environment gap: `tests/conftest.py`'s
  autouse `isolated_project_root` fixture points `PROJECT_ROOT` at an empty
  `tmp_path` for every test, so any test exercising `/api/health` needs its
  own `pyproject.toml` stub written into that directory first (a
  `FileNotFoundError` there is an `OSError` subclass and was silently
  swallowed by the same broad handler N7 needs for a missing database,
  producing a misleading 503 until traced down by adding the exception
  detail to the log line -- kept in the final code, it's better diagnostics
  either way).
- `tests/conftest.py`'s `no_dns` guard (REQ-V12-OFF-01) blocks
  `socket.getaddrinfo` for every test by default; a server test that binds
  real port 0 and connects over real loopback TCP (REQ-V160-TST-01) must
  inject its own stub for the literal `"127.0.0.1"` host, per that guard's
  own docstring instruction -- never the real resolver, and every other host
  still raises.
- Zero new dependencies: stdlib `http.server`/`socketserver`/`tomllib` only,
  plus this project's own `config`/`dashboard_render`/`metrics`/`storage`/
  `tracing`.
- One prompt → one commit, referencing this file.

## Acceptance

- `tests/test_v160_dashboard.py`'s T6 section (18 new tests, real
  `ThreadingHTTPServer` bound to port 0) covers: fixed loopback bind,
  security headers on 200/404/405/400, `Allow: GET, HEAD` on 405 for every
  method tried, N4's path-traversal/unlisted-path sweep (all 404, no
  filesystem access), N5's bad-parameter sweep (400 naming only the
  parameter, the offending value never in the body), `Host` header
  rejection (wrong host, userinfo, `localhost`) and acceptance of the
  correct one, `/api/health`'s exact key set, `/api/traces/<id>` 404 on an
  unknown-but-well-formed id (both API and page), JSON is sorted with
  `ensure_ascii=False`, a missing database is 503, `connect_readonly`
  genuinely cannot write, HEAD mirrors GET's headers with an empty body,
  every page/API route serves 200 on a seeded database, and a real span
  round-trips through `/api/traces/<id>` and `/traces/<id>` with
  `status_message` absent from the JSON.
- `uv run --locked ruff check .` exits 0.
- `uv run --locked ruff format --check dashboard_server.py` exits 0 (new
  file; `dashboard_render.py`'s one-constant addition and the test file's
  appended section were verified via `git diff --stat` to carry no
  unintended deletions in code they didn't touch).
- `uv run --locked pytest` exits 0, 941 passed (904 + 23 (T5) + 14 (T6)... a
  discrepancy from the naive 904+23+18=945 is explained by four of T6's
  tests parametrising over the same `live_server` fixture rather than
  adding four separate top-level test IDs where the loop body itself
  contains the per-case assertions -- the collected count is what matters
  and it is 941 exactly).
- `uv run --locked python devtools/mutation_check.py` exits 0, 72/72 killed.

## Stop

If a response were ever missing one of the four security headers, or if the
`Host` check could be bypassed by a header shape not in the tested set,
that would be worth stopping over -- the header sweep runs across every
status class this task's own tests can reach (200/400/404/405/503) and
found no gap.
