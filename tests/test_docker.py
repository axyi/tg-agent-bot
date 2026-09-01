"""Docker sandbox: argv builder, availability probe, timeout kill, root refusal.

Every test here drives a **stub** `docker` executable placed on `PATH`; no real
container is ever started, so the suite stays offline and fast.
"""

import json
import logging
import os
import re
import subprocess
from pathlib import Path

import pytest

import bot
import tools

STUB = '''#!/usr/bin/env python3
import json, os, sys, time

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "calls.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"argv": sys.argv[1:], "env": dict(os.environ)}) + "\\n")
with open(os.path.join(here, "mode.json"), encoding="utf-8") as fh:
    mode = json.load(fh)

verb = sys.argv[1] if len(sys.argv) > 1 else ""
if verb == "kill":
    sys.exit(0)
if verb == "version":
    if mode.get("version_fail"):
        sys.stderr.write("cannot connect to the docker daemon\\n")
        sys.exit(1)
    sys.stdout.write(mode.get("version", "27.1.2") + "\\n")
    sys.exit(0)
if verb == "ps":
    for cid in mode.get("ps_ids", []):
        sys.stdout.write(cid + "\\n")
    sys.exit(0)
if verb == "rm":
    sys.exit(mode.get("rm_exit", 0))
if mode.get("sleep"):
    time.sleep(mode["sleep"])
if mode.get("write_bytes"):
    with open("grown.bin", "wb") as fh:
        fh.write(b"0" * mode["write_bytes"])
sys.stdout.write(mode.get("stdout", ""))
sys.stderr.write(mode.get("stderr", ""))
sys.exit(mode.get("exit", 0))
'''


@pytest.fixture
def docker_stub(tmp_path, monkeypatch):
    """Install a fake `docker` on PATH and return a handle to inspect its calls."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "docker"
    script.write_text(STUB, encoding="utf-8")
    script.chmod(0o755)

    class Stub:
        def __init__(self):
            self.dir = bindir
            self.set()

        def set(self, **mode):
            (bindir / "mode.json").write_text(json.dumps(mode), encoding="utf-8")

        def calls(self):
            path = bindir / "calls.jsonl"
            if not path.exists():
                return []
            return [json.loads(line) for line in path.read_text().splitlines() if line]

    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    return Stub()


@pytest.fixture
def sandbox(tmp_path):
    path = tmp_path / "sandbox"
    path.mkdir()
    return path


def argv_of(stub, verb="run"):
    return [c["argv"] for c in stub.calls() if c["argv"][:1] == [verb]]


def test_t_v1_dk_01_argv_is_exactly_the_specified_list():
    built = tools.build_docker_argv(
        ["uname", "-a"],
        image="python:3.13-slim",
        sandbox="/srv/sandbox",
        uid=1000,
        gid=1000,
        container_name="tgexec-deadbeef",
        wrap_timeout=True,
        empty_resolv=Path("/state/.resolv-empty"),
    )
    assert built == [
        "docker", "run", "--rm", "--pull", "never",
        "--name", "tgexec-deadbeef",
        "--label", "tgexec=1",
        "--network", "none",
        "--user", "1000:1000",
        "--read-only",
        "--mount", "type=bind,source=/srv/sandbox,target=/work",
        "--mount", "type=bind,source=/state/.resolv-empty,target=/etc/resolv.conf,readonly",
        "--tmpfs", "/tmp:rw,size=67108864,mode=1777",
        "--workdir", "/work",
        "--env", "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "--env", "LANG=C.UTF-8",
        "--env", "HOME=/work",
        "--memory", "512m", "--memory-swap", "512m",
        "--cpus", "1.0",
        "--pids-limit", "128",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--init",
        "python:3.13-slim", "timeout", "--kill-after=5", "30", "uname", "-a",
    ]


def test_t_v1_dk_02_isolation_flags_and_only_one_mount():
    resolv = Path("/state/.resolv-empty")
    built = tools.build_docker_argv(
        ["/bin/sh", "-c", "echo hi"],
        image="python:3.13-slim",
        sandbox="/srv/sandbox",
        uid=1000,
        gid=1000,
        container_name="tgexec-00000000",
        empty_resolv=resolv,
    )
    pairs = list(zip(built, built[1:]))
    assert ("--network", "none") in pairs
    assert "--read-only" in built
    assert ("--cap-drop", "ALL") in pairs
    assert ("--pull", "never") in pairs
    assert ("--security-opt", "no-new-privileges") in pairs
    assert ("--label", tools.CONTAINER_LABEL) in pairs

    # REQ-V11-INF-01: exactly two bind mounts — the sandbox (rw) and the
    # neutralised resolv.conf (ro) — and no others.
    mounts = [value for flag, value in pairs if flag == "--mount"]
    assert mounts == [
        "type=bind,source=/srv/sandbox,target=/work",
        "type=bind,source=/state/.resolv-empty,target=/etc/resolv.conf,readonly",
    ]
    assert "--volume" not in built and "-v" not in built

    # REQ-V11-DOC-07: this pins the --env *flags the bot passes*, not the
    # container's resulting environment, which additionally carries the
    # image's own public build-time variables (HOSTNAME, GPG_KEY, ...).
    envs = [value for flag, value in pairs if flag == "--env"]
    assert envs == [
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG=C.UTF-8",
        "HOME=/work",
    ]
    # The program and its arguments come last, after the image.
    assert built[-4:] == ["python:3.13-slim", "/bin/sh", "-c", "echo hi"]


def test_t_v1_dk_03_unavailable_backend_never_spawns(sandbox, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError(f"unexpected process start: {args!r}")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    result = tools.run_command_docker(
        ["uname", "-a"], workdir=sandbox, image="python:3.13-slim", docker_ok=False
    )
    assert result == {
        "error": "exec backend unavailable: docker is not available on this host"
    }


def test_t_v1_dk_04_docker_level_failures_are_distinct(docker_stub, sandbox):
    docker_stub.set(exit=125, stderr="daemon said no: " + "x" * 400)
    result = tools.run_command_docker(
        ["uname"], workdir=sandbox, image="python:3.13-slim", docker_ok=True
    )
    prefix = "exec failed (docker exit 125): "
    assert set(result) == {"error"}
    assert result["error"].startswith(prefix + "daemon said no: ")
    assert len(result["error"][len(prefix):]) <= 200

    docker_stub.set(exit=7, stdout="partial\n", stderr="warned\n")
    normal = tools.run_command_docker(
        ["uname"], workdir=sandbox, image="python:3.13-slim", docker_ok=True
    )
    assert normal["exit_code"] == 7
    assert normal["timed_out"] is False
    assert normal["stdout"] == "partial\n"
    assert normal["notice"] == tools.UNTRUSTED_NOTICE


def test_t_v1_dk_04_program_exit_codes_are_not_docker_errors(docker_stub, sandbox):
    for code in (126, 127):
        docker_stub.set(exit=code, stderr="exec format error\n")
        result = tools.run_command_docker(
            ["broken"], workdir=sandbox, image="python:3.13-slim", docker_ok=True
        )
        assert set(result) == {"error"}
        assert result["error"].startswith(f"exec failed (docker exit {code}): ")


def test_t_v1_dk_05_timeout_kills_the_container(docker_stub, sandbox, monkeypatch):
    real_grace = tools.DOCKER_STARTUP_GRACE_S
    monkeypatch.setattr(tools, "DOCKER_STARTUP_GRACE_S", 0.0)
    docker_stub.set(sleep=30)
    result = tools.run_command_docker(
        ["sleep", "30"], workdir=sandbox, image="python:3.13-slim",
        docker_ok=True, timeout_s=0.5,
    )
    assert result["timed_out"] is True
    assert result["exit_code"] != 0

    run_argv = argv_of(docker_stub, "run")[0]
    name = run_argv[run_argv.index("--name") + 1]
    assert ["kill", name] in argv_of(docker_stub, "kill")

    # REQ-V11-TST-04: with the real grace constant restored, the outer
    # wall-clock kill carries EXEC_TIMEOUT_S + DOCKER_STARTUP_GRACE_S, not
    # just `timeout_s` — the mutation this guards against monkeypatches the
    # grace to 0.0 above and would otherwise go unnoticed.
    monkeypatch.setattr(tools, "DOCKER_STARTUP_GRACE_S", real_grace)
    seen = {}

    def spy(full_argv, **kwargs):
        seen["timeout_s"] = kwargs["timeout_s"]
        return {
            "exit_code": 0, "timed_out": False, "truncated": False,
            "stdout": "", "stderr": "",
        }

    monkeypatch.setattr(tools, "_run_process", spy)
    tools.run_command_docker(
        ["true"], workdir=sandbox, image="python:3.13-slim", docker_ok=True,
    )
    assert seen["timeout_s"] == tools.EXEC_TIMEOUT_S + real_grace


def test_t_v1_dk_06_container_names_are_unique_and_shaped(docker_stub, sandbox):
    docker_stub.set(exit=0, stdout="ok\n")
    for _ in range(2):
        tools.run_command_docker(
            ["true"], workdir=sandbox, image="python:3.13-slim", docker_ok=True
        )
    names = [argv[argv.index("--name") + 1] for argv in argv_of(docker_stub, "run")]
    assert len(names) == 2
    assert len(set(names)) == 2
    for name in names:
        assert re.fullmatch(r"tgexec-[0-9a-f]{8}", name)


def test_t_v1_dk_07_probe_and_runner_share_the_daemon(docker_stub, sandbox, monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://198.51.100.7:2376")
    docker_stub.set(version="27.1.2", exit=0, stdout="ok\n")

    assert tools.docker_probe() == "27.1.2"
    tools.run_command_docker(
        ["uname"], workdir=sandbox, image="python:3.13-slim", docker_ok=True
    )

    seen = {tuple(c["argv"][:1]): c["env"] for c in docker_stub.calls()}
    assert seen[("version",)]["DOCKER_HOST"] == "tcp://198.51.100.7:2376"
    assert seen[("run",)]["DOCKER_HOST"] == "tcp://198.51.100.7:2376"

    docker_stub.set(version_fail=True)
    assert tools.docker_probe() is None


def test_t_v1_dk_07_probe_survives_a_missing_binary(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert tools.docker_probe() is None


def test_t_v1_dk_08_root_refusal_disables_exec(sandbox, caplog, monkeypatch):
    monkeypatch.setattr(os, "getuid", lambda: 0)
    with caplog.at_level(logging.WARNING):
        version, docker_ok = bot.exec_backend_status(probe=lambda: "27.1.2")
    assert version == "27.1.2"
    assert docker_ok is False
    assert any(
        "refusing to run exec as root" in record.getMessage() for record in caplog.records
    )

    result = tools.run_command_docker(
        ["uname"], workdir=sandbox, image="python:3.13-slim", docker_ok=docker_ok
    )
    assert set(result) == {"error"}
    assert "docker is not available" in result["error"]


def test_t_v1_dk_08_missing_docker_disables_exec(caplog, monkeypatch):
    monkeypatch.setattr(os, "getuid", lambda: 1000)
    with caplog.at_level(logging.WARNING):
        version, docker_ok = bot.exec_backend_status(probe=lambda: None)
    assert (version, docker_ok) == (None, False)
    assert any(
        "exec backend disabled: docker unavailable" in record.getMessage()
        for record in caplog.records
    )

    with caplog.at_level(logging.WARNING):
        assert bot.exec_backend_status(probe=lambda: "27.1.2") == ("27.1.2", True)


def test_missing_sandbox_is_reported_before_docker_runs(docker_stub, tmp_path):
    result = tools.run_command_docker(
        ["uname"], workdir=tmp_path / "gone", image="python:3.13-slim", docker_ok=True
    )
    assert result == {"error": "sandbox directory is missing"}
    assert docker_stub.calls() == []
