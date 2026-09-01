"""spec-v1.1 patch: redaction of model-authored content, truncation headroom,
orphaned-container cleanup, sandbox quota, config hardening and the resolv.conf
mount. One file per REQ-V11-TREE-01.
"""

import functools
import json
import logging
import os
import re
import stat
import sys
from pathlib import Path

import httpx
import pytest

import agent
import bot
import config
import storage
import tools
from config import ConfigError, load_config
from llm.base import LLMResponse, ToolCall
from tests.fakes import FakeLLM, mock_llm_transport

# REQ-V11-ORP-02: "reuse the existing docker_stub fixture rather than writing a
# second stub" — pytest finds a fixture by matching a test's parameter name
# against any object in the module carrying the `@pytest.fixture` marker,
# including one merely imported here. Static analysis cannot see that use, so
# every test below that takes `docker_stub` or `sandbox` as a parameter has a
# lint suppression on its `def` line.
from tests.test_docker import docker_stub, sandbox  # noqa: F401
from tests.test_v1_guardrails import (
    SENTINEL,
    USER_ID,
    RecordingTelegram,
    env,
    make_cfg,
    process,
    update,
)

ALLOWED = frozenset({"wttr.in"})


@pytest.fixture(autouse=True)
def isolated_secret_registry():
    """`config._secrets` is process-global. Several tests below assert on an
    *empty* registry (`max_secret_length() == 0`), so the registry is cleared
    at setup, not merely restored at teardown."""
    before = set(config._secrets)
    config._secrets.clear()
    yield
    config._secrets.clear()
    config._secrets.update(before)


# --------------------------------------------------------------------------
# 5.1 Redaction of model-authored content (REQ-V11-RED-01/02)
# --------------------------------------------------------------------------

def test_t_v11_red_01_model_authored_content_and_args_are_redacted(conn, tmp_path):
    config.register_secret(SENTINEL)
    cfg = make_cfg(tmp_path)
    llm = FakeLLM([
        LLMResponse(
            f"noted: {SENTINEL}",
            [ToolCall("call_1", "exec", json.dumps({"argv": ["echo", SENTINEL]}))],
            "tool_calls",
        ),
        LLMResponse("done", [], "stop"),
    ])
    process(conn, cfg, update(), llm=llm)

    rows = conn.execute(
        "SELECT content, tool_calls_json FROM messages "
        "WHERE role = 'assistant' AND tool_calls_json IS NOT NULL"
    ).fetchall()
    assert len(rows) == 1
    assert SENTINEL not in rows[0]["content"]
    assert "***REDACTED***" in rows[0]["content"]
    assert SENTINEL not in rows[0]["tool_calls_json"]
    assert "***REDACTED***" in rows[0]["tool_calls_json"]

    # The payload of the following round must carry neither.
    second_messages, _ = llm.calls[1]
    assert SENTINEL not in json.dumps(second_messages)


def test_t_v11_red_02_add_user_message_redacts(conn):
    config.register_secret(SENTINEL)
    conv_id = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv_id, f"secret {SENTINEL} here")
    row = conn.execute(
        "SELECT content FROM messages WHERE conv_id = ? AND role = 'user'", (conv_id,)
    ).fetchone()
    assert SENTINEL not in row["content"]
    assert "***REDACTED***" in row["content"]


def test_t_v11_red_02_add_assistant_message_redacts(conn):
    config.register_secret(SENTINEL)
    conv_id = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_assistant_message(conn, conv_id, f"secret {SENTINEL} here")
    row = conn.execute(
        "SELECT content FROM messages WHERE conv_id = ? AND role = 'assistant'", (conv_id,)
    ).fetchone()
    assert SENTINEL not in row["content"]
    assert "***REDACTED***" in row["content"]


def test_t_v11_red_02_add_tool_turn_redacts_content_calls_and_results(conn):
    config.register_secret(SENTINEL)
    conv_id = storage.get_or_create_active_conversation(conn, USER_ID)
    tool_calls = [{
        "id": "call_1", "type": "function",
        "function": {"name": "exec", "arguments": json.dumps({"argv": [SENTINEL]})},
    }]
    storage.add_tool_turn(
        conn, conv_id, f"assistant said {SENTINEL}", tool_calls,
        [("call_1", f"result {SENTINEL}")],
    )
    rows = conn.execute(
        "SELECT role, content, tool_calls_json FROM messages WHERE conv_id = ?", (conv_id,)
    ).fetchall()
    assistant_row = next(r for r in rows if r["role"] == "assistant")
    tool_row = next(r for r in rows if r["role"] == "tool")
    assert SENTINEL not in assistant_row["content"]
    assert "***REDACTED***" in assistant_row["content"]
    assert SENTINEL not in assistant_row["tool_calls_json"]
    assert "***REDACTED***" in assistant_row["tool_calls_json"]
    assert SENTINEL not in tool_row["content"]
    assert "***REDACTED***" in tool_row["content"]


def test_t_v11_red_02_add_summary_redacts(conn):
    config.register_secret(SENTINEL)
    conv_id = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_summary(conn, conv_id, USER_ID, json.dumps({"goal": SENTINEL}))
    row = conn.execute(
        "SELECT summary_json FROM summaries WHERE conv_id = ?", (conv_id,)
    ).fetchone()
    assert SENTINEL not in row["summary_json"]
    assert "***REDACTED***" in row["summary_json"]


def test_t_v11_red_03_redact_tool_calls_preserves_shape():
    config.register_secret(SENTINEL)
    calls = [
        {
            "id": "call_1", "type": "function",
            "function": {"name": "exec", "arguments": json.dumps({"argv": [SENTINEL]})},
        },
        {
            "id": "call_2", "type": "function",
            "function": {"name": "fetch", "arguments": json.dumps({"url": "https://wttr.in/x"})},
        },
    ]
    redacted = agent._redact_tool_calls(calls)
    assert [c["id"] for c in redacted] == ["call_1", "call_2"]
    assert [c["type"] for c in redacted] == ["function", "function"]
    assert [c["function"]["name"] for c in redacted] == ["exec", "fetch"]
    assert SENTINEL not in redacted[0]["function"]["arguments"]
    assert "***REDACTED***" in redacted[0]["function"]["arguments"]
    assert redacted[1]["function"]["arguments"] == calls[1]["function"]["arguments"]


def test_t_v11_red_04_summary_reply_redacted_only_by_send(conn, tmp_path, monkeypatch):
    config.register_secret(SENTINEL)
    cfg = make_cfg(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv_id, "hi")
    storage.add_assistant_message(conn, conv_id, "hello")

    monkeypatch.setattr(
        agent, "summarize_conversation",
        lambda conn, conv_id, llm, cfg: json.dumps({
            "goal": SENTINEL, "files": [], "decisions": [], "errors": [], "next_action": "",
        }),
    )
    tg = RecordingTelegram()
    bot._handle_summary(conn, tg, cfg, object(), USER_ID, USER_ID)
    assert tg.sent
    assert all(SENTINEL not in text for _chat, text in tg.sent)


# --------------------------------------------------------------------------
# 5.2 Truncation headroom (REQ-V11-TRN-01/02)
# --------------------------------------------------------------------------

def test_t_v11_trn_01_max_secret_length_and_strip_fragment():
    assert config.max_secret_length() == 0
    assert config.strip_secret_fragment("hello world") == "hello world"

    secret = SENTINEL
    config.register_secret(secret)
    assert config.max_secret_length() == len(secret.encode("utf-8"))

    prefix8 = secret[:8]
    text8 = f"filler {prefix8}"
    assert config.strip_secret_fragment(text8) == "filler "

    prefix7 = secret[:7]
    text7 = f"filler {prefix7}"
    assert config.strip_secret_fragment(text7) == text7

    # A text ending in the *complete* secret is `redact`'s job, not this helper's.
    full = f"filler {secret}"
    assert config.strip_secret_fragment(full) == full


def test_t_v11_trn_02_run_process_headroom_strips_straddling_secret(tmp_path):
    secret = SENTINEL
    config.register_secret(secret)
    filler_len = tools.EXEC_MAX_STREAM_BYTES - len(secret) // 2
    payload = "A" * filler_len + secret + "B" * 100
    code = f"import sys; sys.stdout.write({payload!r})"
    result = tools._run_process([sys.executable, "-c", code], workdir=tmp_path)

    assert secret not in result["stdout"]
    for length in range(8, len(secret)):
        assert secret[:length] not in result["stdout"], length
    assert result["truncated"] is True
    assert len(result["stdout"].encode("utf-8")) <= tools.EXEC_MAX_STREAM_BYTES


def test_t_v11_trn_03_fetch_url_headroom_strips_straddling_secret():
    # REQ-V12-TST-01: `httpx.Response(200, content=body)` delivers the whole
    # body as a single chunk, so `config.redact` alone would catch the secret
    # no matter what `fetch_url` does around it — the fetch leg of the
    # truncation fix would go unverified. Streaming the body from an iterator
    # of fixed-size chunks makes the cut genuinely land inside the secret.
    secret = SENTINEL
    config.register_secret(secret)
    filler_len = tools.FETCH_MAX_BYTES - len(secret) // 2
    body = ("A" * filler_len + secret + "B" * 100).encode("utf-8")

    def chunked(data: bytes, size: int = 8):
        # Small enough that, without the headroom this test guards, the read
        # loop's cut lands genuinely inside the sentinel rather than safely
        # past it.
        for start in range(0, len(data), size):
            yield data[start:start + size]

    def handler(request):
        return httpx.Response(200, content=chunked(body))

    client = httpx.Client(transport=mock_llm_transport(handler))
    result = tools.fetch_url("https://wttr.in/x", allowed_domains=ALLOWED, client=client)

    assert secret not in result["body"]
    for length in range(8, len(secret)):
        assert secret[:length] not in result["body"], length
    assert result["truncated"] is True
    assert len(result["body"].encode("utf-8")) <= tools.FETCH_MAX_BYTES
    # Without headroom, strip_secret_fragment's own amputation of the partial
    # secret would satisfy every assertion above with the placeholder absent —
    # proving the secret was seen *whole* is what pins the `+ secret_headroom`
    # term specifically (REQ-V12-TST-02 #11's rationale, applied to TRN-03).
    assert config.REDACTION in result["body"]


def test_t_v11_trn_03_fetch_url_strips_a_fragment_left_by_a_short_response():
    # A response that ends on its own, well under FETCH_MAX_BYTES, in a bare
    # prefix of a registered secret: headroom never engages (nothing is being
    # cut), so only `strip_secret_fragment` can be what removes the fragment.
    secret = SENTINEL
    config.register_secret(secret)
    body = ("hello world " + secret[:20]).encode("utf-8")

    def chunked(data: bytes, size: int = 8):
        for start in range(0, len(data), size):
            yield data[start:start + size]

    def handler(request):
        return httpx.Response(200, content=chunked(body))

    client = httpx.Client(transport=mock_llm_transport(handler))
    result = tools.fetch_url("https://wttr.in/x", allowed_domains=ALLOWED, client=client)

    assert secret[:20] not in result["body"]
    assert result["body"] == "hello world "


def test_t_v11_trn_04_no_secrets_registered_matches_v1_behaviour(tmp_path):
    assert config.max_secret_length() == 0
    code = "import sys; sys.stdout.buffer.write(b'x' * 5000)"
    result = tools._run_process([sys.executable, "-c", code], workdir=tmp_path)
    assert result["truncated"] is True
    assert len(result["stdout"]) == tools.EXEC_MAX_STREAM_BYTES
    assert result["stdout"] == "x" * tools.EXEC_MAX_STREAM_BYTES


# --------------------------------------------------------------------------
# 5.3 Orphaned containers (REQ-V11-ORP-01..04, REQ-V11-WIR-01)
# --------------------------------------------------------------------------

def test_t_v11_orp_01_wrap_timeout_prefix_and_label():
    base = dict(
        image="python:3.13-slim", sandbox="/srv/sandbox", uid=1000, gid=1000,
        container_name="tgexec-deadbeef",
    )
    with_wrap = tools.build_docker_argv(["uname"], wrap_timeout=True, **base)
    without_wrap = tools.build_docker_argv(["uname"], wrap_timeout=False, **base)

    assert with_wrap[-4:] == [
        "timeout", "--kill-after=5", str(int(tools.EXEC_TIMEOUT_S)), "uname",
    ]
    assert without_wrap[-1] == "uname"
    assert "timeout" not in without_wrap

    pairs = list(zip(with_wrap, with_wrap[1:]))
    assert ("--label", tools.CONTAINER_LABEL) in pairs
    pairs2 = list(zip(without_wrap, without_wrap[1:]))
    assert ("--label", tools.CONTAINER_LABEL) in pairs2


def test_t_v11_orp_02_startup_reap_removes_labelled_orphans(docker_stub, caplog):  # noqa: F811
    # REQ-V12-ORP-02: an unlabelled (v1.1-era) container is always an orphan;
    # one owned by a still-live process is left alone.
    live_owner = tools.owner_key()
    docker_stub.set(ps_entries=[["deadbeef1", ""], ["alive1", live_owner]])
    with caplog.at_level(logging.INFO):
        bot._reap_orphaned_containers()
    ps_calls = [c["argv"] for c in docker_stub.calls() if c["argv"][:1] == ["ps"]]
    assert ps_calls == [
        ["ps", "-a", "--filter", "label=tgexec=1", "--format",
         '{{.ID}}\t{{.Label "tgexec-owner"}}'],
    ]
    rm_calls = [c["argv"] for c in docker_stub.calls() if c["argv"][:1] == ["rm"]]
    assert rm_calls == [["rm", "-f", "deadbeef1"]]
    assert any(
        "reaped 1 orphaned exec container" in record.getMessage() for record in caplog.records
    )
    assert any(
        "skipped 1 container(s) owned by a live process" in record.getMessage()
        for record in caplog.records
    )


def test_t_v11_orp_02_empty_listing_issues_no_rm(docker_stub):  # noqa: F811
    docker_stub.set(ps_entries=[])
    bot._reap_orphaned_containers()
    rm_calls = [c["argv"] for c in docker_stub.calls() if c["argv"][:1] == ["rm"]]
    assert rm_calls == []


def test_t_v11_orp_02_failing_reap_logs_and_continues(monkeypatch, caplog):
    def forbidden(*args, **kwargs):
        raise OSError("docker missing")

    monkeypatch.setattr(bot.subprocess, "run", forbidden)
    with caplog.at_level(logging.WARNING):
        bot._reap_orphaned_containers()          # must not raise
    assert any("reap" in record.getMessage() for record in caplog.records)


def test_t_v11_orp_03_image_has_timeout_true_and_false(docker_stub):  # noqa: F811
    docker_stub.set(exit=0)
    assert tools.image_has_timeout("python:3.13-slim") is True

    docker_stub.set(exit=1)
    assert tools.image_has_timeout("python:3.13-slim") is False


def test_t_v11_orp_03_image_has_timeout_missing_binary(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert tools.image_has_timeout("python:3.13-slim") is False


def test_t_v11_orp_03_image_has_timeout_hangs(docker_stub, monkeypatch):  # noqa: F811
    monkeypatch.setattr(tools, "IMAGE_PROBE_TIMEOUT_S", 0.5)
    docker_stub.set(sleep=2)
    assert tools.image_has_timeout("python:3.13-slim") is False


def test_t_v11_orp_03_image_has_timeout_argv_and_hardening(docker_stub):  # noqa: F811
    docker_stub.set(exit=0)
    tools.image_has_timeout("python:3.13-slim")
    run_calls = [c["argv"] for c in docker_stub.calls() if c["argv"][:1] == ["run"]]
    assert len(run_calls) == 1
    argv = run_calls[0]
    pairs = list(zip(argv, argv[1:]))
    assert ("--pull", "never") in pairs
    assert ("--network", "none") in pairs
    assert "--read-only" in argv
    assert ("--cap-drop", "ALL") in pairs
    assert ("--security-opt", "no-new-privileges") in pairs
    assert argv[-2:] == ["timeout", "--version"]
    # REQ-V12-ORP-04: the probe is named and labelled like every other
    # container, so it can never become an unreapable orphan.
    assert ("--label", tools.CONTAINER_LABEL) in pairs
    assert any(
        flag == "--label" and value.startswith("tgexec-owner=") for flag, value in pairs
    )
    name = argv[argv.index("--name") + 1]
    assert re.fullmatch(r"tgexec-probe-[0-9a-f]{8}", name)
    assert ("--user", f"{os.getuid()}:{os.getgid()}") in pairs


def test_t_v11_orp_03_false_result_disables_wrap_and_warns(docker_stub, tmp_path, caplog):  # noqa: F811
    docker_stub.set(exit=1)
    cfg = make_cfg(tmp_path)
    with caplog.at_level(logging.WARNING):
        wrap_timeout, _ = bot._startup_docker_wiring(
            cfg, docker_ok=True, resolve=lambda *a, **k: []
        )
    assert wrap_timeout is False
    assert any("self-timeout unavailable" in record.getMessage() for record in caplog.records)


def test_t_v11_orp_04_exit_124_mapping_depends_on_wrap_timeout(docker_stub, sandbox):  # noqa: F811
    docker_stub.set(exit=124, stdout="killed by wrapper\n")
    result = tools.run_command_docker(
        ["sleep", "30"], workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, wrap_timeout=True,
    )
    assert result["timed_out"] is True
    assert result["exit_code"] == 124

    docker_stub.set(exit=124, stdout="own exit code\n")
    result = tools.run_command_docker(
        ["sleep", "30"], workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, wrap_timeout=False,
    )
    assert result["timed_out"] is False
    assert result["exit_code"] == 124

    # REQ-V12-ORP-03: a command that ignores SIGTERM and is finished off by
    # `--kill-after` exits 137, which maps the same way 124 does.
    docker_stub.set(exit=137, stdout="killed by sigkill\n")
    result = tools.run_command_docker(
        ["sleep", "30"], workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, wrap_timeout=True,
    )
    assert result["timed_out"] is True
    assert result["exit_code"] == 137

    docker_stub.set(exit=137, stdout="own exit code\n")
    result = tools.run_command_docker(
        ["sleep", "30"], workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, wrap_timeout=False,
    )
    assert result["timed_out"] is False
    assert result["exit_code"] == 137


def test_t_v11_orp_04_outer_kill_path_still_times_out(docker_stub, sandbox, monkeypatch):  # noqa: F811
    monkeypatch.setattr(tools, "DOCKER_STARTUP_GRACE_S", 0.0)
    docker_stub.set(sleep=30)
    result = tools.run_command_docker(
        ["sleep", "30"], workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, timeout_s=0.5, wrap_timeout=True,
    )
    assert result["timed_out"] is True


def test_t_v11_wir_01_docker_not_ok_runs_nothing_and_creates_nothing(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected subprocess call")

    monkeypatch.setattr(bot.subprocess, "run", forbidden)
    result = bot._startup_docker_wiring(cfg, docker_ok=False, resolve=lambda *a, **k: [])
    assert result == (False, None)
    assert not (cfg.db_path.parent / ".resolv-empty").exists()


def test_t_v11_wir_01_docker_ok_reaps_probes_and_creates_the_file_once(docker_stub, tmp_path):  # noqa: F811
    cfg = make_cfg(tmp_path)
    docker_stub.set(ps_entries=[], exit=0)
    wrap_timeout, empty_resolv = bot._startup_docker_wiring(
        cfg, docker_ok=True, resolve=lambda *a, **k: []
    )
    assert wrap_timeout is True
    assert empty_resolv == cfg.db_path.parent / ".resolv-empty"
    assert empty_resolv.exists()
    ps_calls = [c["argv"] for c in docker_stub.calls() if c["argv"][:1] == ["ps"]]
    assert len(ps_calls) == 1
    run_calls = [c["argv"] for c in docker_stub.calls() if c["argv"][:1] == ["run"]]
    assert len(run_calls) == 1


# --------------------------------------------------------------------------
# 5.4 Sandbox disk quota (REQ-V11-QTA-01..05)
# --------------------------------------------------------------------------

def test_t_v11_qta_01_sums_regular_files_and_ignores_symlink_targets(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 100)
    outside = tmp_path.parent / "t_v11_qta_01_outside_target.bin"
    outside.write_bytes(b"z" * 100000)
    try:
        (tmp_path / "link").symlink_to(outside)
        total, status = tools.sandbox_usage(tmp_path)
        assert status == tools.SCAN_OK
        assert total == 100
    finally:
        outside.unlink()


def test_t_v11_qta_01_reports_incomplete_on_an_unreadable_entry(tmp_path, monkeypatch):
    (tmp_path / "ok.txt").write_bytes(b"x" * 50)
    (tmp_path / "ghost.txt").write_bytes(b"y" * 999)
    real_lstat = tools.os.lstat

    def flaky(path, *a, **kw):
        if str(path).endswith("ghost.txt"):
            raise OSError("permission denied")
        return real_lstat(path, *a, **kw)

    monkeypatch.setattr(tools.os, "lstat", flaky)
    total, status = tools.sandbox_usage(tmp_path)
    assert status == tools.SCAN_INCOMPLETE
    assert total == 50


def test_t_v11_qta_01_reports_cut_short_past_entry_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "SANDBOX_SCAN_MAX_ENTRIES", 3)
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_bytes(b"x")
    _total, status = tools.sandbox_usage(tmp_path)
    assert status == tools.SCAN_CUT_SHORT


def test_t_v11_qta_01_missing_directory_returns_zero_ok(tmp_path):
    assert tools.sandbox_usage(tmp_path / "gone") == (0, tools.SCAN_OK)


def test_t_v11_qta_02_full_sandbox_refuses_without_spawning(sandbox, monkeypatch):  # noqa: F811
    (sandbox / "big.bin").write_bytes(b"x" * 1000)

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected process start")

    monkeypatch.setattr(tools, "_run_process", forbidden)
    result = tools.run_command_docker(
        ["uname"], workdir=sandbox, image="python:3.13-slim", docker_ok=True,
        sandbox_max_bytes=1000,
    )
    assert result == {
        "error": "sandbox is full: 1000 bytes of 1000 allowed; "
                 "ask the operator to clear the sandbox directory"
    }

    # REQ-V12-QTA-02: the cut-short and incomplete-scan cases get their own
    # message, distinct from "full", and neither starts a process.
    with pytest.MonkeyPatch.context() as cut_mp:
        cut_mp.setattr(tools, "SANDBOX_SCAN_MAX_ENTRIES", 0)
        result = tools.run_command_docker(
            ["uname"], workdir=sandbox, image="python:3.13-slim", docker_ok=True,
            sandbox_max_bytes=10_000_000,
        )
    assert result == {
        "error": "sandbox holds too many files to measure (over 0 entries); "
                 "ask the operator to clear the sandbox directory",
        "sandbox_scan": tools.SCAN_CUT_SHORT,
    }

    ghost = sandbox / "ghost"
    ghost.mkdir()
    (ghost / "x.bin").write_bytes(b"x" * 10)
    ghost.chmod(0)
    try:
        result = tools.run_command_docker(
            ["uname"], workdir=sandbox, image="python:3.13-slim", docker_ok=True,
            sandbox_max_bytes=10_000_000,
        )
    finally:
        ghost.chmod(0o700)
    assert result == {
        "error": "sandbox size could not be measured; ask the operator to "
                 "inspect the sandbox directory",
        "sandbox_scan": tools.SCAN_INCOMPLETE,
    }


def test_t_v11_qta_02_below_limit_proceeds(docker_stub, sandbox):  # noqa: F811
    (sandbox / "small.bin").write_bytes(b"x" * 10)
    docker_stub.set(exit=0, stdout="ok\n")
    result = tools.run_command_docker(
        ["true"], workdir=sandbox, image="python:3.13-slim", docker_ok=True,
        sandbox_max_bytes=1000,
    )
    assert result["exit_code"] == 0


def test_t_v11_qta_03_run_command_docker_flags_over_quota(docker_stub, sandbox, caplog):  # noqa: F811
    docker_stub.set(exit=0, stdout="ok\n", write_bytes=2000)
    with caplog.at_level(logging.WARNING):
        result = tools.run_command_docker(
            ["true"], workdir=sandbox, image="python:3.13-slim", docker_ok=True,
            sandbox_max_bytes=1000,
        )
    assert result["exit_code"] == 0
    assert result["sandbox_over_quota"] is True
    assert any(
        "sandbox over quota after exec" in record.getMessage() for record in caplog.records
    )


def test_t_v11_qta_03_run_command_docker_omits_key_when_under_quota(docker_stub, sandbox):  # noqa: F811
    docker_stub.set(exit=0, stdout="ok\n", write_bytes=10)
    result = tools.run_command_docker(
        ["true"], workdir=sandbox, image="python:3.13-slim", docker_ok=True,
        sandbox_max_bytes=1000,
    )
    assert "sandbox_over_quota" not in result


def test_t_v11_qta_03_run_exec_pops_the_key_before_the_model_sees_it(docker_stub, tmp_path):  # noqa: F811
    box1 = tmp_path / "box1"
    box1.mkdir()
    docker_stub.set(exit=0, stdout="ok\n", write_bytes=2000)
    runner1 = functools.partial(
        tools.run_command_docker, workdir=box1, image="python:3.13-slim",
        docker_ok=True, sandbox_max_bytes=1000,
    )
    envelope = json.loads(tools.execute_tool(
        "exec", json.dumps({"argv": ["true"]}), skills={}, runner=runner1,
    ))
    assert set(envelope) == {"exit_code", "timed_out", "truncated", "stdout", "stderr", "notice"}

    box2 = tmp_path / "box2"
    box2.mkdir()
    runner2 = functools.partial(
        tools.run_command_docker, workdir=box2, image="python:3.13-slim",
        docker_ok=True, sandbox_max_bytes=1000,
    )
    captured = {}

    def audit(record):
        captured.update(record)

    tools.execute_tool(
        "exec", json.dumps({"argv": ["true"]}), skills={}, runner=runner2, audit=audit,
    )
    assert captured["sandbox_over_quota"] is True
    # REQ-V12-QTA-02: the audit record always carries the scan status; a
    # plain over-quota run (scan itself succeeded) reports it as SCAN_OK.
    assert captured["sandbox_scan"] == tools.SCAN_OK


def test_t_v11_qta_04_exec_sandbox_max_bytes_parsing():
    cfg = load_config(env=env(), load_env_file=False)
    assert cfg.exec_sandbox_max_bytes == 268435456

    cfg = load_config(env=env(EXEC_SANDBOX_MAX_BYTES="1048576"), load_env_file=False)
    assert cfg.exec_sandbox_max_bytes == 1048576

    with pytest.raises(ConfigError):
        load_config(env=env(EXEC_SANDBOX_MAX_BYTES="1048575"), load_env_file=False)
    with pytest.raises(ConfigError):
        load_config(env=env(EXEC_SANDBOX_MAX_BYTES="4294967297"), load_env_file=False)
    with pytest.raises(ConfigError):
        load_config(env=env(EXEC_SANDBOX_MAX_BYTES="nope"), load_env_file=False)


# --------------------------------------------------------------------------
# 5.5 Configuration hardening (REQ-V11-CFV-01/02)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("entry", [
    "169.254.169.254", "127.0.0.1", "[::1]", "localhost", "sub.localhost",
    "internalhost", "example.com:8080", "example.com/path",
    # REQ-V12-SSR-01: shortened and hexadecimal IPv4 forms (finding W-6) —
    # none of these parse as an `ipaddress` literal, so only the strict shape
    # check catches them.
    "127.1", "127.0.1", "0x7f.1", "0x7f.0.0.1",
])
def test_t_v11_cfv_01_rejects_ssrf_shaped_domains(entry):
    with pytest.raises(ConfigError) as raised:
        load_config(env=env(FETCH_ALLOWED_DOMAINS=entry), load_env_file=False)
    assert entry in str(raised.value)


def test_t_v11_cfv_01_accepts_ordinary_domains():
    cfg = load_config(
        env=env(FETCH_ALLOWED_DOMAINS="wttr.in,sub.wttr.in,example.co.uk"),
        load_env_file=False,
    )
    assert cfg.fetch_allowed_domains == frozenset({"wttr.in", "sub.wttr.in", "example.co.uk"})


def test_t_v11_cfv_02_exec_workdir_outside_project_root_rejected(tmp_path):
    for outside in ("/etc", "/tmp/v11-cfv02-outside-dir", str(tmp_path.parent / "sibling")):
        with pytest.raises(ConfigError) as raised:
            load_config(env=env(EXEC_WORKDIR=outside), load_env_file=False)
        assert "EXEC_WORKDIR" in str(raised.value)


def test_t_v11_cfv_02_default_sandbox_and_v1_cases_still_work(tmp_path):
    cfg = load_config(env=env(), load_env_file=False)
    assert cfg.exec_workdir == tmp_path / "sandbox"

    with pytest.raises(ConfigError):
        load_config(env=env(EXEC_WORKDIR="."), load_env_file=False)
    with pytest.raises(ConfigError):
        load_config(env=env(EXEC_WORKDIR="./box", DB_PATH="./box/bot.db"), load_env_file=False)


# --------------------------------------------------------------------------
# 5.6 Information disclosure (REQ-V11-INF-01)
# --------------------------------------------------------------------------

def test_t_v11_inf_01_empty_resolv_file_created_and_reused(tmp_path):
    db_path = tmp_path / "state" / "bot.db"
    db_path.parent.mkdir(parents=True)
    path = bot._ensure_empty_resolv(db_path)
    assert path == db_path.parent / ".resolv-empty"
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    assert path.read_bytes() == b""

    # A plain non-empty file is truncated, not rejected (REQ-V12-INF-01,
    # scenario D5): only the file's *type* is untrusted, not its prior use.
    path.write_bytes(b"should be truncated away")
    path2 = bot._ensure_empty_resolv(db_path)
    assert path2 == path
    assert path.read_bytes() == b""

    # A symlink at the path is refused outright — a planted symlink to the
    # host's real resolv.conf must never be trusted or silently replaced
    # (finding W-8-bis).
    path.unlink()
    target = tmp_path / "host-resolv.conf"
    target.write_text("nameserver 10.0.0.1\n")
    path.symlink_to(target)
    with pytest.raises(ConfigError):
        bot._ensure_empty_resolv(db_path)


def test_t_v11_inf_01_mount_flag_ordering_and_omission():
    resolv = Path("/state/.resolv-empty")
    with_resolv = tools.build_docker_argv(
        ["uname"], image="python:3.13-slim", sandbox="/srv/sandbox",
        uid=1000, gid=1000, container_name="tgexec-x", empty_resolv=resolv,
    )
    mounts = [
        value for flag, value in zip(with_resolv, with_resolv[1:]) if flag == "--mount"
    ]
    assert mounts == [
        "type=bind,source=/srv/sandbox,target=/work",
        "type=bind,source=/state/.resolv-empty,target=/etc/resolv.conf,readonly",
    ]

    without_resolv = tools.build_docker_argv(
        ["uname"], image="python:3.13-slim", sandbox="/srv/sandbox",
        uid=1000, gid=1000, container_name="tgexec-x",
    )
    mounts2 = [
        value for flag, value in zip(without_resolv, without_resolv[1:]) if flag == "--mount"
    ]
    assert mounts2 == ["type=bind,source=/srv/sandbox,target=/work"]


# --------------------------------------------------------------------------
# 7 Documentation corrections with test coverage (REQ-V11-DOC-04)
# --------------------------------------------------------------------------

def test_t_v11_url_01_malformed_url_vs_not_https():
    client = httpx.Client(transport=mock_llm_transport(lambda request: httpx.Response(200)))

    malformed = tools.fetch_url(
        "https://example.com:notaport/x", allowed_domains=ALLOWED, client=client
    )
    assert malformed == {"error": tools.URL_MALFORMED}
    _, record = tools._run_fetch({"url": "https://example.com:notaport/x"}, lambda url: malformed)
    assert record["outcome"] == "refused"

    not_https = tools.fetch_url("http://wttr.in/x", allowed_domains=ALLOWED, client=client)
    assert not_https == {"error": tools.URL_NOT_HTTPS}
    _, record2 = tools._run_fetch({"url": "http://wttr.in/x"}, lambda url: not_https)
    assert record2["outcome"] == "refused"
