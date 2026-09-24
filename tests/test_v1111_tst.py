"""spec-v1.11.1 T3 (REQ-V1111-TST-01, REQ-V1111-TST-02): six new
dispatch-level tests for v1.11.0 ERR-01 rows 11-16, and the secrets-registry
snapshot/restore autouse fixture that kills the xdist-order flake. See
`docs/spec/task-briefs/v1111-T3.md` and `docs/spec/spec-v1.11.1.md:404-475`.

REQ-V1111-TST-01's drafter's choice: a new module, not an extension of the
frozen `tests/test_v1110_err.py::test_t_v1110_err_01_error_matrix_strings`
-- that function stays byte-unchanged. Each row test drives
`bot.process_update` through `tests/test_v1110_err.py:81-109`'s own
`process`/`text_update` helpers (imported here, never retyped) with a
hand-written update dict, and asserts the reply byte-equal to the row's
string, plus that string's presence in README's `## Error behaviour`
section via the same file's `_error_section()` (`:112-116`).

REQ-V1111-TST-02's registry is the module-level set `config._secrets`
(`config.py:98`) -- `tests/conftest.py` gains `secrets_registry_snapshot()`
and the autouse `restore_secrets_registry` fixture; `T-V1111-TST-07` here
proves the *fixture*, not only the context manager, with a nested pytest
run over a nested-only module in `tmp_path`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import bot
import config
import storage
from tests.conftest import secrets_registry_snapshot
from tests.fakes import FakeTelegram
from tests.test_v1110_err import USER_ID, _error_section, make_cfg, new_conn, process, text_update

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _callback_update(data, *, user_id=USER_ID, update_id=1, callback_id="cbq-tst05", message_id=50):
    """A hand-written `callback_query` update -- `text_update` (imported
    above) only builds `message` updates, so row 15's trigger needs its own
    builder (`tests/test_v1110_cbq.py:78-102`'s shape)."""
    return {
        "update_id": update_id,
        "callback_query": {
            "id": callback_id,
            "from": {"id": user_id, "is_bot": False},
            "message": {
                "message_id": message_id,
                "date": 0,
                "chat": {"id": user_id, "type": "private"},
                "text": "",
            },
            "chat_instance": "ci-tst05",
            "data": data,
        },
    }


def _bot_state_keys(conn) -> set[str]:
    return {row["key"] for row in conn.execute("SELECT key FROM bot_state")}


# --------------------------------------------------------------------------
# REQ-V1111-TST-01 -- v1.11.0 ERR-01 rows 11-16 (spec-v1.11.0.md:1138-1143)
# --------------------------------------------------------------------------


def test_t_v1111_tst_01_err_row_11_session_usage(tmp_path):
    """Row 11: `/session` bare -> `bot.SESSION_USAGE_REPLY`."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    process(conn, cfg, text_update("/session"), tg=tg, worker=None)
    assert tg.sent == [(USER_ID, "Usage: /session <id> (see /sessions)")]
    assert tg.sent == [(USER_ID, bot.SESSION_USAGE_REPLY)]
    assert bot.SESSION_USAGE_REPLY in _error_section()
    conn.close()


def test_t_v1111_tst_02_err_row_12_session_unknown(tmp_path):
    """Row 12: `/session 999999` with an existing active session ->
    `No session #999999.`; the active-session row stays exactly the
    caller's own seeded conversation -- `activate_conversation`
    deactivates the current row before conditionally reactivating the
    target, rolling back on a missing/foreign id, so a caller with no
    active session at all (`None` before and after) would pass even if
    that rollback were broken; seeding one first makes the "unchanged"
    claim actually exercise it."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    seeded = storage.get_or_create_active_conversation(conn, USER_ID)
    assert storage.active_conversation_id(conn, USER_ID) == seeded
    process(conn, cfg, text_update("/session 999999"), tg=tg, worker=None)
    assert tg.sent == [(USER_ID, "No session #999999.")]
    assert storage.active_conversation_id(conn, USER_ID) == seeded
    assert "No session #<id>." in _error_section()
    conn.close()


def test_t_v1111_tst_03_err_row_13_delete_not_found(tmp_path):
    """Row 13: `/delete #999` with no documents at all ->
    `No document named #999.`; `document_count` stays unchanged."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    before = storage.document_count(conn, user_id=USER_ID)
    assert before == 0
    process(conn, cfg, text_update("/delete #999"), tg=tg, worker=None)
    assert tg.sent == [(USER_ID, "No document named #999.")]
    assert storage.document_count(conn, user_id=USER_ID) == before
    assert "No document named <argument>." in _error_section()
    conn.close()


def test_t_v1111_tst_04_err_row_14_delete_usage(tmp_path):
    """Row 14: `/delete` bare -> `bot.DELETE_USAGE_REPLY`; README's own
    row carries the `\\|`-escaped form (a literal backslash before the
    pipe, since the string itself sits inside a `|`-delimited table row)."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    process(conn, cfg, text_update("/delete"), tg=tg, worker=None)
    assert tg.sent == [(USER_ID, "Usage: /delete <filename> | /delete #<id>")]
    assert tg.sent == [(USER_ID, bot.DELETE_USAGE_REPLY)]
    assert r"Usage: /delete <filename> \| /delete #<id>" in _error_section()
    conn.close()


def test_t_v1111_tst_05_err_row_15_stale_callback(tmp_path):
    """Row 15: a `callback_query` with data `zzz` from an allowed user --
    `_resolve_callback_action` rejects it (fewer than 3 `:`-parts), so
    `_handle_callback` acknowledges with `CALLBACK_EXPIRED_REPLY` and
    nothing else. Read from `FakeTelegram.callback_answers`
    (`tests/fakes.py:179`); nothing sent or edited; the polling cursor
    (`storage.get_state(conn, "last_update_id")`) still advances -- the
    at-most-once boundary is unconditional, before any dispatch."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    upd = _callback_update("zzz", update_id=915)
    process(conn, cfg, upd, tg=tg, worker=None)
    assert tg.callback_answers[-1]["text"] == "Expired — send the command again."
    assert tg.callback_answers[-1]["text"] == bot.CALLBACK_EXPIRED_REPLY
    assert tg.sent == []
    assert tg.edited == []
    assert storage.get_state(conn, "last_update_id") == "915"
    assert bot.CALLBACK_EXPIRED_REPLY in _error_section()
    conn.close()


def test_t_v1111_tst_06_err_row_16_model_unknown_and_usage(tmp_path):
    """Row 16, two triggers: `/model openrouter nope` (a configured
    provider, an unknown model) -> `Unknown model for openrouter; see
    /model`; `/model a b c` (three arguments) -> `bot.MODEL_USAGE_REPLY`.
    Neither writes a `bot_state` override row (`PROVIDER_OVERRIDE_KEY` /
    `model_override:*`) -- both are refusals, not selections."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(
        tmp_path,
        # `provider_is_configured` only needs a truthy value here; "k"
        # (the placeholder `tests/test_v160_bench.py:464` already uses for
        # the same field) keeps it non-credential-shaped.
        openrouter_api_key="k",
        openrouter_model="o-default",
        openrouter_models=("o-default",),
    )
    tg = FakeTelegram()
    before_keys = _bot_state_keys(conn)

    process(conn, cfg, text_update("/model openrouter nope", update_id=1), tg=tg, worker=None)
    assert tg.sent == [(USER_ID, "Unknown model for openrouter; see /model")]

    process(conn, cfg, text_update("/model a b c", update_id=2), tg=tg, worker=None)
    assert tg.sent[-1] == (USER_ID, "Usage: /model [lmstudio|openrouter|auto] [<model>]")
    assert tg.sent[-1] == (USER_ID, bot.MODEL_USAGE_REPLY)

    after_keys = _bot_state_keys(conn)
    after_keys.discard("last_update_id")
    before_keys.discard("last_update_id")
    assert after_keys == before_keys
    assert bot.PROVIDER_OVERRIDE_KEY not in after_keys
    assert not any(key.startswith("model_override:") for key in after_keys)

    assert "Unknown model for <provider>; see /model" in _error_section()
    assert r"Usage: /model [lmstudio\|openrouter\|auto] [<model>]" in _error_section()
    conn.close()


# --------------------------------------------------------------------------
# REQ-V1111-TST-02 -- T-V1111-TST-07: the autouse fixture itself, proven by
# a nested pytest run, not only the direct context-manager checks.
# --------------------------------------------------------------------------

_NESTED_MODULE_SOURCE = """
import config

_REGISTRY_BEFORE = config._secrets


def test_a_registers_and_leaks():
    config.register_secret("VALUE-abcdefgh12")
    assert "VALUE-abcdefgh12" in config._secrets


def test_b_sees_restored_registry():
    assert "VALUE-abcdefgh12" not in config._secrets
    assert config._secrets is _REGISTRY_BEFORE
"""

_NESTED_CONFTEST_SOURCE = "from tests.conftest import restore_secrets_registry\n"


def test_t_v1111_tst_07_secrets_registry_restored(tmp_path):
    """T-V1111-TST-07: proves `restore_secrets_registry` itself, not only
    `secrets_registry_snapshot()` called directly. A two-test module in
    `tmp_path` -- test A registers a sentinel and never cleans up, test B
    asserts it is gone from `config._secrets` and that the registry is
    the same object (`is`) as before -- plus a `tmp_path/conftest.py` that
    imports the project's fixture by name, never calling
    `secrets_registry_snapshot()` itself. `[[VERIFY :456-464]]`: `tests`
    is importable as a package here (`tests/__init__.py` exists, and the
    subprocess's cwd is the repo root, on `sys.path[0]` under `python -m`)
    -- confirmed empirically below by the plain import succeeding and both
    nested tests passing; the `pytest_plugins` fallback and the permanent
    `xdist_group`-marked pair were not needed."""
    (tmp_path / "conftest.py").write_text(_NESTED_CONFTEST_SOURCE, encoding="utf-8")
    (tmp_path / "test_nested_secrets_leak.py").write_text(_NESTED_MODULE_SOURCE, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:xdist",
            "-q",
            str(tmp_path),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout

    # The direct context-manager checks, additional to the nested proof.
    registry_before = config._secrets
    with secrets_registry_snapshot():
        config.register_secret("VALUE-abcdefgh12")
        assert config.redact("x VALUE-abcdefgh12 y") == f"x {config.REDACTION} y"
    assert "VALUE-abcdefgh12" not in config._secrets
    assert config.redact("x VALUE-abcdefgh12 y") == "x VALUE-abcdefgh12 y"
    assert config._secrets is registry_before
