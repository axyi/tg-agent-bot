"""spec-v1.3 section 5: the carry-over from the v1.2 audits.

One test per REQ-V13-CO-01…06 (CO-05 = three tests), per section 11.1. All
offline: the only subprocesses are the stub `docker` on PATH and the CLI
exit-code check of REQ-V13-CO-06, which is run with `sys.executable` and
never reaches a real mutation run.
"""

import os
import signal
import socket
import stat
import subprocess
import sys

import pytest

import bot
import tools
from config import ConfigError
from devtools import mutation_check as mc

# Reused fixtures/helpers, exactly as tests/test_v12_patch.py already does.
from tests.test_docker import docker_stub, sandbox  # noqa: F401
from tests.test_v1_guardrails import make_cfg

FIFO_OPEN_BUDGET_S = 5.0


# --------------------------------------------------------------------------
# REQ-V13-CO-01 — the recovery chmod loop must not follow a symlink
# --------------------------------------------------------------------------

def test_t_v13_co_01_recovery_chmod_never_follows_a_symlink(tmp_path):
    """A `0o555` sandbox subdirectory whose child is a symlink pointing out of
    the sandbox: `rmtree`'s first pass cannot unlink the child, and the
    recovery loop must chmod the *parent directory* only — never the symlink,
    whose mode change would land on the bot-owned file it points at."""
    box = tmp_path / "sandbox"
    box.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("payload", encoding="utf-8")
    outside.chmod(0o644)
    ghost = box / "ghost"
    ghost.mkdir()
    (ghost / "link").symlink_to(outside)
    ghost.chmod(0o555)

    cfg = make_cfg(tmp_path, exec_workdir=box)
    try:
        bot._clean_sandbox_at_start(cfg)
    finally:
        if ghost.is_dir():
            ghost.chmod(0o700)

    assert list(box.iterdir()) == []
    assert outside.exists()
    assert stat.S_IMODE(outside.stat().st_mode) == 0o644
    assert outside.read_text(encoding="utf-8") == "payload"


# --------------------------------------------------------------------------
# REQ-V13-CO-02 — the `owner=owner_key()` binding of the orphan reap
# --------------------------------------------------------------------------

def test_t_v13_co_02_owner_key_binding_drives_the_reap(docker_stub, sandbox):  # noqa: F811
    """`run_command_docker` labels the container with *this* process's
    `owner_key()` (tools.py's `owner=owner_key()`), and the reap discriminates
    on exactly that label: of two containers carrying different owner keys,
    only the one whose key is not this live process's is removed."""
    docker_stub.set(exit=0, stdout="ok\n")
    tools.run_command_docker(
        ["uname"], workdir=sandbox, image="python:3.13-slim", docker_ok=True,
    )
    run_argv = [c["argv"] for c in docker_stub.calls() if c["argv"][:1] == ["run"]][0]
    owner_labels = [a for a in run_argv if a.startswith("tgexec-owner=")]
    assert owner_labels == [f"tgexec-owner={tools.owner_key()}"]

    mine = owner_labels[0].split("=", 1)[1]
    dead = "999999999-1"
    assert mine != dead
    docker_stub.set(ps_entries=[["mine1", mine], ["dead1", dead]])
    bot._reap_orphaned_containers()

    rm_calls = [c["argv"] for c in docker_stub.calls() if c["argv"][:1] == ["rm"]]
    assert rm_calls == [["rm", "-f", "dead1"]]


# --------------------------------------------------------------------------
# REQ-V13-CO-03 — `resolve` is looked up at call time, not bound at `def` time
# --------------------------------------------------------------------------

def test_t_v13_co_03_resolve_is_bound_at_call_time(tmp_path, monkeypatch):
    """`_check_allowlist_resolution(cfg, resolve=None)` must reach
    `socket.getaddrinfo` through the module attribute: a stub installed long
    after import (as the offline guard installs its own) is observed."""
    seen = []

    def recording(host, port, **kwargs):
        seen.append((host, port, kwargs))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", recording)

    box = tmp_path / "sandbox"
    box.mkdir()
    cfg = make_cfg(
        tmp_path, exec_workdir=box, fetch_allowed_domains=frozenset({"wttr.in"}),
    )
    assert bot._startup_docker_wiring(cfg, docker_ok=False) == (False, None)
    assert [entry[:2] for entry in seen] == [("wttr.in", 443)]


# --------------------------------------------------------------------------
# REQ-V13-CO-04 — `resolve_host` catches `OSError` and nothing else
# --------------------------------------------------------------------------

def test_t_v13_co_04_resolve_host_catches_oserror_only(monkeypatch):
    def raising(exc):
        def _resolve(*args, **kwargs):
            raise exc
        return _resolve

    monkeypatch.setattr(socket, "getaddrinfo", raising(socket.gaierror("no such host")))
    assert tools.resolve_host("wttr.in") == []

    monkeypatch.setattr(socket, "getaddrinfo", raising(OSError("network down")))
    assert tools.resolve_host("wttr.in") == []

    # A broad `except Exception` would swallow the offline guard's own
    # AssertionError, so anything that is not an OSError must propagate.
    monkeypatch.setattr(socket, "getaddrinfo", raising(AssertionError("guard")))
    with pytest.raises(AssertionError, match="guard"):
        tools.resolve_host("wttr.in")


# --------------------------------------------------------------------------
# REQ-V13-CO-05 — the three INF-01 clauses of `_ensure_empty_resolv`
# --------------------------------------------------------------------------

def _state_dir(tmp_path):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    return state / "bot.db"


def test_t_v13_co_05_a_file_owned_by_another_uid_is_refused(tmp_path, monkeypatch):
    db_path = _state_dir(tmp_path)
    real_fstat = os.fstat

    class _Foreign:
        def __init__(self, st):
            self.st_mode = st.st_mode
            self.st_size = st.st_size
            self.st_nlink = st.st_nlink
            self.st_uid = os.getuid() + 1

    monkeypatch.setattr(os, "fstat", lambda fd: _Foreign(real_fstat(fd)))
    with pytest.raises(ConfigError, match="not a plain file owned by this process"):
        bot._ensure_empty_resolv(db_path)


def test_t_v13_co_05_b_extra_hard_link_is_refused(tmp_path):
    db_path = _state_dir(tmp_path)
    path = db_path.parent / ".resolv-empty"
    path.write_bytes(b"")
    os.link(path, db_path.parent / "shadow")
    assert path.stat().st_nlink == 2

    with pytest.raises(ConfigError, match="not a plain file owned by this process"):
        bot._ensure_empty_resolv(db_path)


def test_t_v13_co_05_c_a_fifo_neither_hangs_nor_is_accepted(tmp_path):
    """`O_NONBLOCK` is what keeps the open from parking forever on a reader-less
    FIFO planted at the predictable path; the alarm below fails the test loudly
    instead of hanging the suite if the flag is ever dropped."""
    db_path = _state_dir(tmp_path)
    path = db_path.parent / ".resolv-empty"
    os.mkfifo(path)

    def _blocked(_signum, _frame):
        raise TimeoutError("the open on the FIFO blocked; O_NONBLOCK is missing")

    previous = signal.signal(signal.SIGALRM, _blocked)
    signal.setitimer(signal.ITIMER_REAL, FIFO_OPEN_BUDGET_S)
    try:
        with pytest.raises(ConfigError, match="could not create the empty resolv file"):
            bot._ensure_empty_resolv(db_path)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)

    assert stat.S_ISFIFO(os.lstat(path).st_mode)


# --------------------------------------------------------------------------
# REQ-V13-CO-06 — `--only <unknown-id>` exits 1 instead of running nothing
# --------------------------------------------------------------------------

def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(mc.REPO_ROOT / "devtools" / "mutation_check.py"), *args],
        cwd=mc.REPO_ROOT, capture_output=True, text=True, timeout=60,
    )


def test_t_v13_co_06_unknown_only_id_exits_one():
    unknown = "no-such-mutation-id"
    assert all(m["id"] != unknown for m in mc.MUTATIONS)

    result = _run_cli("--only", unknown)
    assert result.returncode == 1
    assert f"unknown mutation id: {unknown}" in result.stderr
    assert "running mutation" not in result.stdout

    # `--list` semantics stay untouched: exit 0, every id printed, nothing run.
    listed = _run_cli("--list")
    assert listed.returncode == 0
    assert all(m["id"] in listed.stdout for m in mc.MUTATIONS)
    assert "running mutation" not in listed.stdout
