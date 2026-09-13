"""v1.9.4 T1 (task-brief docs/spec/task-briefs/v194-T1.md): redaction at the
logging layer. The ~105 hand-placed `config.redact()` call sites never
covered a `log.exception(...)` traceback -- `record.exc_info` (and any
chained `__cause__`/`__context__`) is rendered by the `Formatter` from text
no call site ever sees. `config.RedactingFormatter` closes that seam by
redacting the fully rendered line instead.

`caplog` is deliberately not used for these assertions: caplog captures
records *before* the formatter runs, so it cannot observe what the formatter
does. Each test below builds its own logger with a `StringIO`-backed
handler carrying a `RedactingFormatter` and asserts on the emitted text.
"""

import io
import logging

import bot
import config
from devtools import bench, rag_eval


def _stringio_logger(name):
    """A throwaway logger with a `StringIO` handler carrying a
    `RedactingFormatter`, isolated from the root logger and from every
    other test's logger of the same kind (a unique name per test)."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    config.install_redacting_logging(handler, "%(message)s")
    logger.addHandler(handler)
    return logger, stream


def _clear_root_handlers():
    root = logging.getLogger()
    saved, saved_level = list(root.handlers), root.level
    for handler in saved:
        root.removeHandler(handler)
    return saved, saved_level


def _restore_root_handlers(saved, saved_level):
    root = logging.getLogger()
    for handler in list(root.handlers):
        handler.close()
        root.removeHandler(handler)
    for handler in saved:
        root.addHandler(handler)
    root.setLevel(saved_level)


def test_t_v194_red_01_message_args_masked_in_emitted_line():
    secret = "sentinel-secret-v194-red-01-args"
    config.register_secret(secret)
    logger, stream = _stringio_logger("test_v194_red_01")

    logger.info("token=%s", secret)

    text = stream.getvalue()
    assert secret not in text
    assert config.REDACTION in text


def test_t_v194_red_02_exception_str_masked_in_traceback():
    secret = "sentinel-secret-v194-red-02-excstr"
    config.register_secret(secret)
    logger, stream = _stringio_logger("test_v194_red_02")

    try:
        raise ValueError(f"boom {secret}")
    except ValueError:
        logger.exception("failed")

    text = stream.getvalue()
    assert secret not in text
    assert config.REDACTION in text
    assert "Traceback" in text


def test_t_v194_red_03_chained_cause_masked():
    secret = "sentinel-secret-v194-red-03-cause"
    config.register_secret(secret)
    logger, stream = _stringio_logger("test_v194_red_03")

    try:
        try:
            raise ValueError(f"root cause {secret}")
        except ValueError as cause:
            raise RuntimeError("wrapped") from cause
    except RuntimeError:
        logger.exception("failed")

    text = stream.getvalue()
    assert secret not in text
    assert config.REDACTION in text
    assert "direct cause" in text


def test_t_v194_red_04_secret_registered_after_install_still_masked():
    # The formatter is installed (and one line already emitted) before the
    # secret is registered -- a snapshot taken at install time would never
    # see it; the live `_secrets` registry, read at format time, does.
    logger, stream = _stringio_logger("test_v194_red_04")
    logger.info("before registration, nothing to mask here")

    secret = "sentinel-secret-v194-red-04-late"
    config.register_secret(secret)
    logger.info("late=%s", secret)

    text = stream.getvalue()
    assert secret not in text
    assert config.REDACTION in text


def test_t_v194_red_05_entry_points_install_redacting_formatter(tmp_path, monkeypatch):
    # bot.main's own logging setup.
    saved, saved_level = _clear_root_handlers()
    try:
        assert bot.main(["--selftest"]) == 0
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, config.RedactingFormatter)
    finally:
        _restore_root_handlers(saved, saved_level)

    # devtools/bench.py's _configure_logging.
    saved, saved_level = _clear_root_handlers()
    try:
        bench._configure_logging(tmp_path / "bench.log")
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, config.RedactingFormatter)
    finally:
        _restore_root_handlers(saved, saved_level)

    # devtools/rag_eval.py's main() -- load_config stubbed to fail
    # immediately so this test never reads `.env`; the logging setup runs
    # unconditionally before that call.
    saved, saved_level = _clear_root_handlers()
    try:

        def _raise_config_error(*args, **kwargs):
            raise config.ConfigError("no .env access in this test")

        monkeypatch.setattr(rag_eval, "load_config", _raise_config_error)
        assert rag_eval.main() == 2
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, config.RedactingFormatter)
    finally:
        _restore_root_handlers(saved, saved_level)
