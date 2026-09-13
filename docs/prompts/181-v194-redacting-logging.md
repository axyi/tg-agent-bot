# Prompt 181 — v1.9.4 T1: secrets never reach a log line through the logging layer

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded, well-specified defect fix against an existing
  task brief (`docs/spec/task-briefs/v194-T1.md`) -- one new class, one new
  function, four call sites and their tests; no open-ended design decision.
- **Harness:** Claude Code
- **Stage:** v1.9.4 T1 (patch, no new spec file — precedent v1.5.1, v1.9.1–v1.9.3)
- **Owner of:** `config.py`, `bot.py`, `devtools/bench.py`, `devtools/rag_eval.py`,
  `devtools/mutation_check.py`, `tests/test_v194_redaction.py`,
  `docs/reports/report-v1.9.4.md`, `docs/llm-usage.md`, `README.md`
- **REQ ids:** none new for this patch (precedent: v1.9.1 T3, v1.9.2 T3 also
  landed patch fixes with no new REQ id)

## Goal

Redaction is call-site-only: `config.redact()` is called at ~105 sites by
hand, and there is no logging-layer mechanism. At every `log.exception(...)`
site the traceback and any chained `__cause__`/`__context__` are rendered by
the `Formatter` from `record.exc_info` and never pass through `redact()` — a
guarantee by inspection today (the v1.9.3 T1+T2 review checked every site: no
registered secret reaches those exception objects), not by mechanism. This
task makes it a mechanism: `config.RedactingFormatter` (a `logging.Formatter`
subclass whose `format()` renders through the base class, then returns
`redact()` of the rendered text — covering the message, its args, the
traceback and every chained exception in one place) and
`config.install_redacting_logging(handler, fmt, datefmt=None)`, the one call
every logging entry point makes. Applied at `bot.py`'s `main()` (replacing
`logging.basicConfig`), `devtools/bench.py`'s `_configure_logging` (its
`FileHandler` gets the redacting formatter), and `devtools/rag_eval.py`'s
`main()` (which had no logging setup of its own — records went to
`logging`'s unredacted `lastResort` stderr handler). `dashboard_server.py`
gains no separate configuration: its logger inherits whichever root config
the hosting bot process installed before starting the dashboard thread.
Every existing `redact()` call site is kept untouched — defence in depth is
the intended end state, not a large call-site-removal diff.

## Constraints

- Do not remove any existing `redact()` call site.
- Do not implement the seam as a `logging.Filter` — a filter runs before the
  traceback is rendered and would miss exactly the text this task is about.
- Keep every entry point's observable output identical (format string,
  stream, level) — only the formatter class changes.
- `caplog` must not be used for the five tests' assertions (it captures
  records before the formatter runs); assert on the emitted text via a
  `StringIO`-backed handler carrying the redacting formatter instead.
- `.env` is never read, printed or committed; `data/`, `evals/rag/corpus`
  never opened. No push, no `--no-verify`.
- Do not run `devtools/mutation_check.py` — the coordinator runs it after
  commit, never overlapping with other work on this box.

## Acceptance

```
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python devtools/checks.py lint-docs
```

All five exit 0. Two new mutation entries added to
`devtools/mutation_check.py` (`v194-redacting-formatter-skips-redact`,
`v194-bench-logging-unredacted`), left for the coordinator to run via
`--only` after commit.

## Stop

Stop and report instead of forcing a workaround when: an entry point cannot
take the helper without changing what it logs (format string, stream,
level); or the fourth test (a secret registered after the formatter is
installed still gets masked) cannot pass without a registry snapshot —
that would mean the registry access is wrong and the formatter needs
fixing, not the test.
