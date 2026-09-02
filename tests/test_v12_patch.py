"""spec-v1.2 patch: minted tool-call identifiers, the tri-state sandbox scan,
the three-layer fetch allowlist, the hardened resolv file, the ownership-aware
reap, and the mutation-gate coverage rows. One file per REQ-V12-TREE-01.
"""

import functools
import io
import json
import logging
import socket
import stat
import sys

import httpx
import pytest

import agent
import bot
import config
import storage
import tools
from config import ConfigError
from llm.base import LLMResponse, ToolCall
from tests.fakes import FakeLLM, RecordingRunner, mock_llm_transport

# Reused fixtures/helpers, exactly as tests/test_v11_patch.py already does.
from tests.test_docker import docker_stub, sandbox  # noqa: F401
from tests.test_v1_guardrails import SENTINEL, USER_ID, make_cfg

ALLOWED = frozenset({"wttr.in"})
NOW = "2026-09-01T12:00:00Z"
EXEC_ARGS = '{"argv": ["uname", "-a"]}'


@pytest.fixture(autouse=True)
def isolated_secret_registry():
    """`config._secrets` is process-global (see tests/test_v11_patch.py)."""
    before = set(config._secrets)
    config._secrets.clear()
    yield
    config._secrets.clear()
    config._secrets.update(before)


# --------------------------------------------------------------------------
# 5.1 Minted tool-call identifiers (REQ-V12-ID-01..04)
# --------------------------------------------------------------------------

def test_t_v12_id_01_model_authored_id_and_name_never_stored(conn):
    config.register_secret(SENTINEL)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    llm = FakeLLM([
        LLMResponse("", [ToolCall(SENTINEL, SENTINEL, EXEC_ARGS)], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ])
    reply = agent.run_agent(
        conn=conn, conv_id=conv, llm=llm, skills={}, runner=RecordingRunner(), now=NOW
    )
    assert reply == "done"

    stored = conn.execute(
        "SELECT turn_id, role, content, tool_calls_json, tool_call_id "
        "FROM messages WHERE conv_id = ? ORDER BY id",
        (conv,),
    ).fetchall()
    assistant_row = next(r for r in stored if r["tool_calls_json"] is not None)
    tool_row = next(r for r in stored if r["role"] == "tool")
    assert SENTINEL not in assistant_row["tool_calls_json"]
    assert SENTINEL not in tool_row["tool_call_id"]
    assert SENTINEL not in tool_row["content"]

    wire = json.loads(assistant_row["tool_calls_json"])
    assert wire[0]["id"] == f"call_{assistant_row['turn_id']}_0"
    assert wire[0]["function"]["name"] == "unknown"
    assert tool_row["tool_call_id"] == wire[0]["id"]

    second_request = llm.calls[1][0]
    assert SENTINEL not in json.dumps(second_request)


def test_t_v12_id_02_pairing_survives_a_restart(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    llm = FakeLLM([
        LLMResponse("", [ToolCall("a", "exec", EXEC_ARGS), ToolCall("b", "exec", EXEC_ARGS)],
                    "tool_calls"),
        LLMResponse("", [ToolCall("c", "exec", EXEC_ARGS)], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ])
    agent.run_agent(conn=conn, conv_id=conv, llm=llm, skills={}, runner=RecordingRunner(), now=NOW)

    restored = storage.load_context_messages(conn, conv, 30)
    seen_ids: set[str] = set()
    for index, message in enumerate(restored):
        if message["role"] != "assistant" or "tool_calls" not in message:
            continue
        ids = [call["id"] for call in message["tool_calls"]]
        # ids from different turns never collide.
        assert not (set(ids) & seen_ids)
        seen_ids.update(ids)
        # every assistant tool_calls[i].id has a matching tool_call_id in the
        # same turn, immediately following.
        following_ids = set()
        cursor = index + 1
        while cursor < len(restored) and restored[cursor]["role"] == "tool":
            following_ids.add(restored[cursor]["tool_call_id"])
            cursor += 1
        for call_id in ids:
            assert call_id in following_ids


def test_t_v12_id_03_normalize_tool_calls_discards_raw_ids():
    calls = [
        ToolCall("dup", "exec", "{}"),
        ToolCall("dup", "exec", "{}"),
        ToolCall("", "exec", "{}"),
        ToolCall("x" * 4096, "exec", "{}"),
    ]
    normalized = agent.normalize_tool_calls(calls, turn_id=7)
    assert [c.id for c in normalized] == ["call_7_0", "call_7_1", "call_7_2", "call_7_3"]
    assert [c.name for c in normalized] == ["exec"] * 4


def _seed_selftest_transcript(conn, *, assistant_call_id, tool_row_call_id):
    conv_id = storage.get_or_create_active_conversation(conn, 424242)
    storage.add_user_message(conn, conv_id, "run the selftest")
    tool_calls = [{
        "id": assistant_call_id, "type": "function",
        "function": {"name": "exec", "arguments": "{}"},
    }]
    envelope = json.dumps({
        "exit_code": 0, "stdout": "ok\n", "stderr": "",
        "timed_out": False, "truncated": False,
    })
    storage.add_tool_turn(conn, conv_id, "", tool_calls, [(tool_row_call_id, envelope)])
    storage.add_assistant_message(conn, conv_id, "selftest ok")
    storage.set_state(conn, "last_update_id", "1")


class _FakeSelftestTg:
    def __init__(self):
        self.sent = [(424242, "selftest ok")]
        self.status = [(424242, bot.STATUS_WORKING)]
        self.edits = [(424242, 1, "⚙️ exec: uname…"), (424242, 1, bot.STATUS_DONE)]


def test_t_v12_id_04_selftest_pairing_check(tmp_path):
    good_db = tmp_path / "good.db"
    conn = storage.connect(good_db)
    storage.init_schema(conn)
    _seed_selftest_transcript(conn, assistant_call_id="call_9_0", tool_row_call_id="call_9_0")
    cfg = make_cfg(
        tmp_path, db_path=good_db,
        exec_workdir=tmp_path / "sandbox", audit_log_path=tmp_path / "exec_audit.jsonl",
    )
    assert bot._selftest_failure(conn, _FakeSelftestTg(), cfg, tmp_path) is None
    conn.close()

    bad_db = tmp_path / "bad.db"
    conn2 = storage.connect(bad_db)
    storage.init_schema(conn2)
    _seed_selftest_transcript(conn2, assistant_call_id="call_9_0", tool_row_call_id="call_9_1")
    cfg2 = make_cfg(
        tmp_path, db_path=bad_db,
        exec_workdir=tmp_path / "sandbox", audit_log_path=tmp_path / "exec_audit.jsonl",
    )
    failure = bot._selftest_failure(conn2, _FakeSelftestTg(), cfg2, tmp_path)
    assert failure == "the stored tool call and its result do not share an identifier"
    conn2.close()


def test_t_v12_id_05_unknown_name_stored_as_unknown(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    llm = FakeLLM([
        LLMResponse("", [ToolCall("call_x", "nosuchtool", "{}")], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ])
    reply = agent.run_agent(
        conn=conn, conv_id=conv, llm=llm, skills={}, runner=RecordingRunner(), now=NOW
    )
    assert reply == "done"
    row = conn.execute(
        "SELECT tool_calls_json FROM messages WHERE conv_id = ? AND tool_calls_json IS NOT NULL",
        (conv,),
    ).fetchone()
    wire = json.loads(row["tool_calls_json"])
    assert wire[0]["function"]["name"] == "unknown"
    tool_row = conn.execute(
        "SELECT content FROM messages WHERE conv_id = ? AND role = 'tool'", (conv,)
    ).fetchone()
    assert json.loads(tool_row["content"]) == {"error": "unknown tool: nosuchtool"}


# --------------------------------------------------------------------------
# 5.2 The tri-state sandbox scan (REQ-V12-QTA-01..03)
# --------------------------------------------------------------------------

def test_t_v12_qta_01_tri_state(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 10)
    assert tools.sandbox_usage(tmp_path) == (10, tools.SCAN_OK)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tools, "SANDBOX_SCAN_MAX_ENTRIES", 0)
        _total, status = tools.sandbox_usage(tmp_path)
    assert status == tools.SCAN_CUT_SHORT

    ghost = tmp_path / "ghost"
    ghost.mkdir()
    (ghost / "x.bin").write_bytes(b"y" * 5)
    ghost.chmod(0)
    try:
        total, status = tools.sandbox_usage(tmp_path)
    finally:
        ghost.chmod(0o700)
    assert status == tools.SCAN_INCOMPLETE
    assert total == 10


def test_t_v12_qta_01_incomplete_wins_over_cut_short(tmp_path, monkeypatch):
    # Real directory traversal order is filesystem-dependent, so the "both
    # conditions hold" case is driven through a scripted os.walk instead: the
    # unreadable subtree is hit first (well under the entry limit), then a
    # second, readable branch pushes the count over it — proving INCOMPLETE,
    # once set, is never downgraded back to CUT_SHORT.
    (tmp_path / "a.txt").write_bytes(b"x")
    ghost = tmp_path / "ghost"
    ghost.mkdir()
    more = tmp_path / "more"
    more.mkdir()
    for name in ("b.txt", "c.txt", "d.txt"):
        (more / name).write_bytes(b"y")

    def ordered_walk(path, followlinks=False, onerror=None):
        yield (str(path), ["ghost", "more"], ["a.txt"])
        onerror(OSError("permission denied"))
        yield (str(more), [], ["b.txt", "c.txt", "d.txt"])

    monkeypatch.setattr(tools.os, "walk", ordered_walk)
    monkeypatch.setattr(tools, "SANDBOX_SCAN_MAX_ENTRIES", 3)
    _total, status = tools.sandbox_usage(tmp_path)
    assert status == tools.SCAN_INCOMPLETE


def test_t_v12_qta_02_refusal_envelopes_and_audit_record(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected process start")

    monkeypatch.setattr(tools, "_run_process", forbidden)
    box = tmp_path / "sandbox"
    box.mkdir()
    (box / "big.bin").write_bytes(b"x" * 2000)

    captured = []

    def audit(record):
        captured.append(record)

    def run(sandbox_max_bytes):
        return json.loads(tools.execute_tool(
            "exec", json.dumps({"argv": ["true"]}), skills={},
            runner=functools.partial(
                tools.run_command_docker, workdir=box, image="python:3.13-slim",
                docker_ok=True, sandbox_max_bytes=sandbox_max_bytes,
            ),
            audit=audit,
        ))

    result = run(1000)
    assert result["error"].startswith("sandbox is full")
    assert captured[-1]["sandbox_scan"] == tools.SCAN_OK

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tools, "SANDBOX_SCAN_MAX_ENTRIES", 0)
        result = run(10_000_000)
    assert result["error"].startswith("sandbox holds too many files")
    assert "sandbox_scan" not in result
    assert captured[-1]["sandbox_scan"] == tools.SCAN_CUT_SHORT

    ghost = box / "ghost"
    ghost.mkdir()
    (ghost / "x.bin").write_bytes(b"z" * 5)
    ghost.chmod(0)
    try:
        result = run(10_000_000)
    finally:
        ghost.chmod(0o700)
    assert result["error"].startswith("sandbox size could not be measured")
    assert "sandbox_scan" not in result
    assert captured[-1]["sandbox_scan"] == tools.SCAN_INCOMPLETE


def test_t_v12_qta_03_unreadable_subtree_cannot_bypass_the_quota(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected process start")

    monkeypatch.setattr(tools, "_run_process", forbidden)
    box = tmp_path / "sandbox"
    box.mkdir()
    ghost = box / "ghost"
    ghost.mkdir()
    (ghost / "big.bin").write_bytes(b"x" * 999999)
    ghost.chmod(0)
    try:
        result = tools.run_command_docker(
            ["uname"], workdir=box, image="python:3.13-slim", docker_ok=True,
            sandbox_max_bytes=1000,
        )
    finally:
        ghost.chmod(0o700)
    assert result["error"].startswith("sandbox size could not be measured")


def test_t_v12_qta_04_startup_cleanup(tmp_path, caplog):
    box = tmp_path / "sandbox"
    box.mkdir(mode=0o700)
    (box / "file.bin").write_bytes(b"x")
    nested = box / "nested"
    nested.mkdir()
    (nested / "inner.bin").write_bytes(b"y")
    outside = tmp_path / "outside.txt"
    outside.write_text("hi")
    (box / "link").symlink_to(outside)

    cfg = make_cfg(tmp_path, exec_workdir=box)
    with caplog.at_level(logging.INFO):
        bot._clean_sandbox_at_start(cfg)

    assert list(box.iterdir()) == []
    assert box.exists()
    assert stat.S_IMODE(box.stat().st_mode) == 0o700
    assert outside.exists()
    assert any(
        "cleared 3 entries from the sandbox at startup" in r.getMessage()
        for r in caplog.records
    )


def test_t_v12_qta_04_disabled_leaves_the_sandbox_alone(tmp_path):
    box = tmp_path / "sandbox"
    box.mkdir()
    (box / "file.bin").write_bytes(b"x")
    cfg = make_cfg(tmp_path, exec_workdir=box, exec_sandbox_clean_on_start=False)
    bot._clean_sandbox_at_start(cfg)
    assert [p.name for p in box.iterdir()] == ["file.bin"]


def test_t_v12_qta_04_a_chmod_000_subdirectory_is_removed_via_retry(tmp_path):
    box = tmp_path / "sandbox"
    box.mkdir()
    ghost = box / "ghost"
    ghost.mkdir()
    (ghost / "x.bin").write_bytes(b"z")
    ghost.chmod(0)
    cfg = make_cfg(tmp_path, exec_workdir=box)
    try:
        # REQ-V13-CO-08: on the green path the cleanup removes `ghost`, so the
        # restore is conditional; without it a failing assertion would leave an
        # unreadable directory behind for pytest's tmp-dir reaper to trip over.
        bot._clean_sandbox_at_start(cfg)
    finally:
        if ghost.is_dir():
            ghost.chmod(0o700)
    assert list(box.iterdir()) == []


def test_t_v12_qta_04_a_listing_failure_logs_and_does_not_raise(tmp_path, caplog, monkeypatch):
    box = tmp_path / "sandbox"
    box.mkdir()
    cfg = make_cfg(tmp_path, exec_workdir=box)

    def forbidden(self):
        raise OSError("boom")

    monkeypatch.setattr(type(box), "iterdir", forbidden)
    with caplog.at_level(logging.WARNING):
        bot._clean_sandbox_at_start(cfg)
    assert any("could not list the sandbox" in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------------------
# 5.3 The three-layer fetch allowlist (REQ-V12-SSR-01..03)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "127.1", "127.0.1", "0x7f.1", "0x7f.0.0.1",
    "-bad.example", "bad-.example", "a..b", "example.123",
])
def test_t_v12_ssr_01_rejects_malformed_shapes(bad):
    with pytest.raises(ConfigError):
        config._parse_domains(bad)


@pytest.mark.parametrize("good", [
    "wttr.in", "sub.wttr.in", "example.co.uk", "xn--80a1acny.xn--p1ai",
    "x" * 63 + ".com",
])
def test_t_v12_ssr_01_accepts_ordinary_shapes(good):
    assert config._parse_domains(good) == frozenset({good})


@pytest.mark.parametrize("addr,expected", [
    ("127.0.0.1", "loopback"),
    ("::1", "loopback"),
    ("10.0.0.1", "private"),
    # link-local addresses are also flagged private by Python's `ipaddress`,
    # and REQ-V12-SSR-02 checks is_private first — so "private" wins here,
    # exactly as the six-flag ordering the requirement specifies produces.
    ("169.254.1.1", "private"),
    ("224.0.0.1", "multicast"),
    ("5f00::1", "reserved"),
    ("0.0.0.0", "private"),
    ("100.64.0.1", "non-global"),
    ("::ffff:100.64.0.1", "non-global"),
    ("8.8.8.8", None),
    ("not-an-ip", "unparsable"),
])
def test_t_v12_ssr_02_address_scope(addr, expected):
    assert config.address_scope(addr) == expected


def test_t_v12_ssr_03_startup_resolution_check_refuses_and_warns(tmp_path, caplog):
    cfg = make_cfg(tmp_path)  # fetch_allowed_domains defaults to {"wttr.in"}

    def resolves_to_loopback(host, port, proto=0):
        return [(2, 1, 6, "", ("127.0.0.1", 443))]

    with pytest.raises(ConfigError) as raised:
        bot._check_allowlist_resolution(cfg, resolves_to_loopback)
    assert "wttr.in" in str(raised.value)
    assert "loopback" in str(raised.value)

    def raises(host, port, proto=0):
        raise OSError("no dns")

    with caplog.at_level(logging.WARNING):
        bot._check_allowlist_resolution(cfg, raises)  # must not raise
    assert any(
        "could not resolve allowlisted domain" in r.getMessage() for r in caplog.records
    )


def test_t_v12_ssr_04_fetch_url_refuses_a_forbidden_resolved_address():
    def transport_forbidden(request):
        raise AssertionError("no request should reach the transport")

    client = httpx.Client(transport=mock_llm_transport(transport_forbidden))
    result = tools.fetch_url(
        "https://wttr.in/x", allowed_domains=ALLOWED, client=client,
        resolve=lambda host: ["127.0.0.1"],
    )
    assert result["error"] == "url resolves to a loopback address: wttr.in"
    _, record = tools._run_fetch({"url": "https://wttr.in/x"}, lambda url: result)
    assert record["outcome"] == "refused"


def test_t_v12_ssr_04_redirect_hop_is_also_checked():
    calls = []

    def flaky_resolver(host):
        calls.append(host)
        return [] if len(calls) == 1 else ["127.0.0.1"]

    def redirecting(request):
        # The initial URL's resolve check (calls == ["wttr.in"]) has already
        # run by the time any request reaches the transport.
        if len(calls) == 1:
            return httpx.Response(302, headers={"location": "https://wttr.in/final"})
        raise AssertionError("the second hop must never reach the transport")

    client = httpx.Client(transport=mock_llm_transport(redirecting))
    result = tools.fetch_url(
        "https://wttr.in/start", allowed_domains=ALLOWED, client=client,
        resolve=flaky_resolver,
    )
    assert result["error"] == "url resolves to a loopback address: wttr.in"
    assert len(calls) == 2


def test_t_v12_ssr_04_resolve_none_is_exactly_v11_behaviour():
    def handler(request):
        return httpx.Response(200, content=b"sunny")

    client = httpx.Client(transport=mock_llm_transport(handler))
    result = tools.fetch_url("https://wttr.in/x", allowed_domains=ALLOWED, client=client)
    assert result["status"] == 200


# T-V12-SSR-05 (the fetcher partial in main() carries the production
# resolver) is covered by the amendment to
# test_main_binds_the_container_runner_not_the_host_runner in
# tests/test_v1_guardrails.py — not duplicated here.


# --------------------------------------------------------------------------
# 5.4 The hardened resolv file (REQ-V12-INF-01)
# --------------------------------------------------------------------------

def test_t_v12_inf_01_comprehensive(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    db_path = state / "bot.db"
    path = bot._ensure_empty_resolv(db_path)
    assert path.read_bytes() == b""
    assert stat.S_IMODE(path.stat().st_mode) == 0o644

    path.write_bytes(b"stale content")
    bot._ensure_empty_resolv(db_path)
    assert path.read_bytes() == b""

    path.unlink()
    path.symlink_to(tmp_path / "nonexistent-target")
    with pytest.raises(ConfigError):
        bot._ensure_empty_resolv(db_path)
    path.unlink()

    world_writable = tmp_path / "shared"
    world_writable.mkdir()
    world_writable.chmod(0o777)
    try:
        with pytest.raises(ConfigError):
            bot._ensure_empty_resolv(world_writable / "bot.db")
    finally:
        world_writable.chmod(0o700)

    sticky = tmp_path / "sticky"
    sticky.mkdir()
    sticky.chmod(0o1777)
    path2 = bot._ensure_empty_resolv(sticky / "bot.db")
    assert path2.read_bytes() == b""


# --------------------------------------------------------------------------
# 5.5 The ownership-aware reap (REQ-V12-ORP-01..03)
# --------------------------------------------------------------------------

def test_t_v12_orp_01_start_ticks_survives_a_space_in_comm(monkeypatch):
    # A foreign process's /proc/<pid>/stat field 2 (comm, in parens) is
    # controlled by that process and may itself contain spaces and
    # parentheses. `line.split()[21]` would silently misread field 22
    # (starttime) for such a process; parsing after the last ")" (as
    # `_process_start_ticks` does) must not.
    remainder = (
        "S 1 4242 4242 0 -1 4194560 100 0 0 0 1 1 0 0 20 0 1 0 "
        "999888 0 0 18446744073709551615 0 0 0 0 0 0 0 0 0 0 0 0 17 3 0 0 0 0 0"
    )
    fabricated = f"4242 (my weird (proc) name) {remainder}\n"

    def fake_open(path, *args, **kwargs):
        if path == "/proc/4242/stat":
            return io.StringIO(fabricated)
        raise AssertionError(f"unexpected open: {path}")

    monkeypatch.setattr(tools, "open", fake_open, raising=False)
    assert tools._process_start_ticks(4242) == 999888


def test_t_v12_orp_01_owner_key_round_trip():
    key = tools.owner_key()
    assert tools.owner_is_alive(key) is True
    assert tools.owner_is_alive("999999999-1") is False
    pid, _ticks = key.split("-", 1)
    assert tools.owner_is_alive(f"{pid}-1") is False
    assert tools.owner_is_alive("garbage") is False


def test_t_v12_orp_01_owner_label_placement():
    argv = tools.build_docker_argv(
        ["uname"], image="python:3.13-slim", sandbox="/srv/sandbox",
        uid=1000, gid=1000, container_name="tgexec-x", owner="123-456",
    )
    idx = argv.index(tools.CONTAINER_LABEL)
    assert argv[idx - 1] == "--label"
    assert argv[idx + 1] == "--label"
    assert argv[idx + 2] == "tgexec-owner=123-456"


def test_t_v12_orp_02_three_containers(docker_stub, caplog):  # noqa: F811
    live = tools.owner_key()
    dead = "999999999-1"
    docker_stub.set(ps_entries=[
        ["unlabelled1", ""],
        ["dead1", dead],
        ["alive1", live],
    ])
    with caplog.at_level(logging.INFO):
        bot._reap_orphaned_containers()
    rm_calls = [c["argv"] for c in docker_stub.calls() if c["argv"][:1] == ["rm"]]
    assert rm_calls == [["rm", "-f", "unlabelled1", "dead1"]]
    assert any(
        "skipped 1 container(s) owned by a live process" in r.getMessage()
        for r in caplog.records
    )


def test_t_v12_orp_03_137_mapping(docker_stub, sandbox):  # noqa: F811
    docker_stub.set(exit=137, stdout="ignored sigterm\n")
    result = tools.run_command_docker(
        ["sleep", "30"], workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, wrap_timeout=True,
    )
    assert result["timed_out"] is True
    assert result["exit_code"] == 137

    docker_stub.set(exit=137, stdout="own choice\n")
    result = tools.run_command_docker(
        ["sleep", "30"], workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, wrap_timeout=False,
    )
    assert result["timed_out"] is False

    docker_stub.set(exit=124, stdout="wrapper hit its own budget\n")
    result = tools.run_command_docker(
        ["sleep", "30"], workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, wrap_timeout=True,
    )
    assert result["timed_out"] is True


# --------------------------------------------------------------------------
# 5.6 The audit hook receives redacted records (REQ-V12-AUD-01)
# --------------------------------------------------------------------------

def test_t_v12_aud_01_hook_receives_redacted_record():
    config.register_secret(SENTINEL)
    captured = {}

    def hook(record):
        captured.update(record)

    runner = RecordingRunner({
        "exit_code": 0, "timed_out": False, "truncated": False, "stdout": "", "stderr": "",
    })
    tools.execute_tool(
        "exec", json.dumps({"argv": [SENTINEL, "-x"]}), skills={}, runner=runner, audit=hook,
    )
    assert SENTINEL not in json.dumps(captured)
    assert captured["exit_code"] == 0
    assert captured["timed_out"] is False


def test_t_v12_aud_01_non_serialisable_record_logs_and_does_not_raise(caplog):
    def hook(record):
        raise AssertionError("must never be called with a non-serialisable record")

    class NotSerialisable:
        pass

    with caplog.at_level(logging.ERROR):
        tools._audit(hook, {"weird": NotSerialisable()})
    assert any("audit hook failed" in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------------------
# 5.7 A configuration refusal looks like one (REQ-V12-ERR-01)
# --------------------------------------------------------------------------

def test_t_v12_err_01_config_error_from_seam_is_caught(tmp_path, monkeypatch, caplog):
    cfg = make_cfg(tmp_path, db_path=tmp_path / "main.db")
    monkeypatch.setattr(bot, "load_config", lambda: cfg)
    monkeypatch.setattr(bot.tools, "load_skills", lambda path: {})
    monkeypatch.setattr(bot.TelegramClient, "get_me", lambda self: {"username": "ThisBot"})
    monkeypatch.setattr(bot, "build_llm_client", lambda cfg, *, client, override=None: object())
    monkeypatch.setattr(bot, "exec_backend_status", lambda: ("27.1.2", True))

    def seam(cfg, docker_ok):
        raise ConfigError("synthetic startup refusal")

    monkeypatch.setattr(bot, "_startup_docker_wiring", seam)
    monkeypatch.setattr(bot.signal, "signal", lambda signum, handler: None)

    with caplog.at_level(logging.ERROR):
        assert bot.main([]) == 2
    assert any("configuration error" in r.getMessage() for r in caplog.records)
    assert all("Traceback" not in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------------------
# The offline DNS guard (REQ-V12-OFF-01)
# --------------------------------------------------------------------------

def test_t_v12_off_01_dns_guard_fires():
    with pytest.raises(AssertionError, match="unexpected DNS lookup"):
        socket.getaddrinfo("example.com", 443)


# --------------------------------------------------------------------------
# Mutation-gate coverage (REQ-V12-TST-02) — one test per table row not
# already covered by an amended v1.1 test.
# --------------------------------------------------------------------------

def test_t_v12_cov_01_live_docker_passes_configured_quota(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path, exec_sandbox_max_bytes=12345678)
    captured = {}

    def spy(argv, **kwargs):
        captured.update(kwargs)
        return {
            "exit_code": 0, "timed_out": False, "truncated": False,
            "stdout": "live-ok\n", "stderr": "",
        }

    monkeypatch.setattr(bot.tools, "run_command_docker", spy)
    monkeypatch.setattr(bot.tools, "docker_image_present", lambda image: True)
    assert bot._live_docker(cfg, probe=lambda: "27.1.2") == 0
    assert captured["sandbox_max_bytes"] == 12345678


# COV-02 (the pre-run refusal for cut-short/incomplete spawns no process) is
# exercised in full by test_t_v12_qta_02_refusal_envelopes_and_audit_record
# above.

def test_t_v12_cov_03_post_run_quota_recorded_on_timeout(docker_stub, sandbox, monkeypatch):  # noqa: F811
    monkeypatch.setattr(tools, "DOCKER_STARTUP_GRACE_S", 0.0)
    docker_stub.set(write_bytes=2000, sleep=30)
    result = tools.run_command_docker(
        ["sleep", "30"], workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, timeout_s=0.5, sandbox_max_bytes=1000,
    )
    assert result["timed_out"] is True
    assert result["sandbox_over_quota"] is True


def test_t_v12_cov_04_post_run_quota_recorded_on_docker_exit(docker_stub, sandbox):  # noqa: F811
    docker_stub.set(exit=125, stderr="boom", write_bytes=2000)
    runner = functools.partial(
        tools.run_command_docker, workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, sandbox_max_bytes=1000,
    )
    captured = {}

    def audit(record):
        captured.update(record)

    envelope = json.loads(tools.execute_tool(
        "exec", json.dumps({"argv": ["broken"]}), skills={}, runner=runner, audit=audit,
    ))
    assert envelope["error"].startswith("exec failed (docker exit 125)")
    assert captured["sandbox_over_quota"] is True


def test_t_v12_cov_05_pop_happens_before_the_envelope(docker_stub, sandbox):  # noqa: F811
    docker_stub.set(exit=125, stderr="boom", write_bytes=2000)
    runner = functools.partial(
        tools.run_command_docker, workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, sandbox_max_bytes=1000,
    )
    captured = {}

    def audit(record):
        captured.update(record)

    envelope = json.loads(tools.execute_tool(
        "exec", json.dumps({"argv": ["broken"]}), skills={}, runner=runner, audit=audit,
    ))
    assert set(envelope) == {"error"}
    assert captured["sandbox_over_quota"] is True
    assert captured["sandbox_scan"] == tools.SCAN_OK


def test_t_v12_cov_06_empty_resolv_reaches_the_runner_partial(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path, db_path=tmp_path / "main.db")
    captured = {}
    real_path = tmp_path / ".resolv-empty"
    real_path.write_bytes(b"")

    monkeypatch.setattr(bot, "load_config", lambda: cfg)
    monkeypatch.setattr(bot.tools, "load_skills", lambda path: {})
    monkeypatch.setattr(bot.TelegramClient, "get_me", lambda self: {"username": "ThisBot"})
    monkeypatch.setattr(bot, "build_llm_client", lambda cfg, *, client, override=None: object())
    monkeypatch.setattr(bot, "exec_backend_status", lambda: ("27.1.2", True))
    monkeypatch.setattr(bot, "_startup_docker_wiring", lambda cfg, docker_ok: (True, real_path))
    monkeypatch.setattr(bot.signal, "signal", lambda signum, handler: None)
    monkeypatch.setattr(bot, "poll_loop", lambda **kwargs: captured.update(kwargs) or 0)

    assert bot.main([]) == 0
    assert captured["runner"].keywords["empty_resolv"] == real_path


def test_t_v12_cov_07_finish_redacts_before_storage(conn):
    config.register_secret(SENTINEL)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hi")
    llm = FakeLLM([LLMResponse(f"leaked: {SENTINEL}", [], "stop")])
    reply = agent.run_agent(
        conn=conn, conv_id=conv, llm=llm, skills={}, runner=RecordingRunner(), now=NOW
    )
    assert SENTINEL not in reply
    assert "***REDACTED***" in reply


def test_t_v12_cov_08_summarize_conversation_redacts_before_returning(conn):
    config.register_secret(SENTINEL)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hi")
    storage.add_assistant_message(conn, conv, "hello")
    llm = FakeLLM([LLMResponse(
        json.dumps({
            "goal": SENTINEL, "files": [], "decisions": [], "errors": [], "next_action": "",
        }),
        [], "stop",
    )])
    result = agent.summarize_conversation(conn, conv, llm, None)
    assert SENTINEL not in result
    assert "***REDACTED***" in result


# COV-09 (--user in image_has_timeout's argv) is covered by the amended
# test_t_v11_orp_03_image_has_timeout_argv_and_hardening in
# tests/test_v11_patch.py.

def test_t_v12_cov_10_sandbox_usage_never_follows_directory_symlinks(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "big.bin").write_bytes(b"x" * 999999)
    box = tmp_path / "sandbox"
    box.mkdir()
    (box / "link_to_real").symlink_to(real_dir)
    total, status = tools.sandbox_usage(box)
    assert status == tools.SCAN_OK
    assert total == 0

    loop = box / "loop"
    loop.mkdir()
    (loop / "self").symlink_to(loop)
    total2, status2 = tools.sandbox_usage(box)  # must not hang
    assert status2 == tools.SCAN_OK
    assert total2 == 0


def test_t_v12_cov_11_capture_headroom_lets_redaction_see_the_whole_secret(tmp_path):
    secret = SENTINEL
    config.register_secret(secret)
    filler_len = tools.EXEC_MAX_STREAM_BYTES - len(secret) // 2
    payload = "A" * filler_len + secret + "B" * 100
    code = f"import sys; sys.stdout.write({payload!r})"
    result = tools._run_process([sys.executable, "-c", code], workdir=tmp_path)
    assert "***REDACTED***" in result["stdout"]
