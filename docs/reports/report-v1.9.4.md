# tg-agent-bot v1.9.4 -- patch report

Operator's decision (`docs/spec/task-briefs/v194-T1.md`, verbatim,
2026-09-13): "Поехали 1.9.4 по всем трём предложенным пунктам и прочим
хвостам." Patch release, no spec file (precedent v1.5.1, v1.9.1-v1.9.3).
Five tasks: **T1** -- redaction at the logging layer (a `RedactingFormatter`
mechanism, closing the "no secret reaches a traceback today" guarantee-by-
inspection from the v1.9.3 T1+T2 review); **T2** -- gate-7 smoke; **T3** --
per-mutation timeout; **T4** -- the PTH/RUF043 ruff tail; **T5** -- version
bump and paperwork close. Baseline: `673f32f` (tag `v1.9.3`, pushed, clean).

## T1 -- redaction at the logging layer

Contract: `docs/spec/task-briefs/v194-T1.md`, prompt 181.

**The defect.** Redaction is call-site-only: `config.redact()` is called at
~105 sites by hand. At every `log.exception(...)` site, the traceback and
any chained `__cause__`/`__context__` are rendered by the `Formatter` from
`record.exc_info` and never pass through `redact()`. The v1.9.3 T1+T2 review
checked every site and found no registered secret reaching those exception
objects today -- a guarantee by inspection, not a mechanism.

**The seam.** `config.py` gains `class RedactingFormatter(logging.Formatter)`
whose `format()` renders through the base class, then returns `redact()` of
the rendered text -- because `Formatter.format` already renders the message,
its args, `exc_info` (via `formatException`) and `stack_info` into one
string, redacting that one rendered string covers all of them in one place.
Deliberately not a `logging.Filter`: a filter runs before the traceback is
rendered and would miss exactly the text this exists for. `redact()` reads
the live `_secrets` registry at format time, not a snapshot, so a secret
registered after the formatter is installed is still masked.
`config.install_redacting_logging(handler, fmt, datefmt=None)` is the one
call every entry point makes to attach it.

Four independent logging entry points, closed as follows:

- `bot.py`'s `main()` -- `logging.basicConfig(...)` replaced with the same
  guard `basicConfig` itself uses (act only when the root logger has no
  handler yet), building a `StreamHandler(sys.stderr)` and installing the
  redacting formatter on it explicitly. Format string, stream and level are
  unchanged.
- `devtools/bench.py`'s `_configure_logging` -- its own `FileHandler` (which
  already tears down every pre-existing root handler) now carries the
  redacting formatter instead of a plain one.
- `devtools/rag_eval.py`'s `main()` -- had no logging configuration of its
  own, so its records went to `logging`'s unredacted `lastResort` stderr
  handler. Gained a `basicConfig`-equivalent through the same helper, so
  gate 7's own warnings are covered too.
- `dashboard_server.py` -- gains no separate configuration. Its
  `log = logging.getLogger("dashboard")` (line 35) inherits whichever root
  config the hosting process installed: `bot.py` builds the dashboard server
  via `dashboard_server.build_server(...)` and starts it in a daemon thread
  (`bot.py`'s `main()`, around line 2077-2088) strictly after `main()`'s own
  logging setup above has already run, so the dashboard thread's log records
  pass through the same redacting formatter as the rest of the bot process.

**Tests** (`tests/test_v194_redaction.py`, `caplog` not used for any
assertion -- it captures records before the formatter runs; each test builds
its own logger with a `StringIO`-backed handler carrying the redacting
formatter and asserts on the emitted text):

1. `test_t_v194_red_01_message_args_masked_in_emitted_line` -- a registered
   secret passed as a `%s` message argument is masked in the emitted line.
2. `test_t_v194_red_02_exception_str_masked_in_traceback` -- a registered
   secret inside `str(exc)` of an exception logged via `log.exception` is
   masked in the rendered traceback text.
3. `test_t_v194_red_03_chained_cause_masked` -- a registered secret inside a
   chained `__cause__` (`raise X from Y` where `str(Y)` carries the secret)
   is masked in the traceback's "direct cause" section.
4. `test_t_v194_red_04_secret_registered_after_install_still_masked` -- a
   secret registered strictly after the formatter is constructed and one
   line already emitted is still masked in a later line, proving the
   formatter reads the live registry rather than a snapshot.
5. `test_t_v194_red_05_entry_points_install_redacting_formatter` -- with the
   root logger's handlers cleared and restored around each check,
   `bot.main(["--selftest"])`, `devtools.bench._configure_logging` and
   `devtools.rag_eval.main()` (its own `load_config` stubbed to raise
   immediately, so this test never touches `.env`) each install exactly one
   root handler whose `formatter` is `config.RedactingFormatter`.

**Mutation coverage** (`devtools/mutation_check.py`, left for the
coordinator to run via `--only` after commit):

- `v194-redacting-formatter-skips-redact` -- mutates
  `RedactingFormatter.format` to return the rendered text unredacted; killed
  by tests 1-3 (message-args, exception-str and chained-cause secrets all
  reach the emitted text unmasked once redaction is skipped).
- `v194-bench-logging-unredacted` -- mutates `devtools/bench.py`'s
  `_configure_logging` to attach a plain `logging.Formatter` instead of the
  redacting one; killed by test 5's bench assertion.

Every existing `redact()` call site is kept untouched -- removing them would
be a large diff with mutation-`find` fallout, and defence in depth (both the
call-site guards and the logging-layer mechanism active at once) is the
intended end state, not a replacement of one by the other.

**Delegation record.** Executor model: `claude-sonnet-5` (Claude Code). This
subagent performed the implementation directly (seam, four entry points,
five tests, two mutation entries, paperwork) against
`docs/spec/task-briefs/v194-T1.md`; the coordinator verifies the report
against the brief and commits.
