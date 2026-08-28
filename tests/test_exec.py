import json
import sys
import time
from pathlib import Path

import pytest

import tools


def run(tmp_path, code, timeout_s=tools.EXEC_TIMEOUT_S):
    return tools.run_command(
        [sys.executable, "-c", code], workdir=tmp_path, timeout_s=timeout_s
    )


def exec_tool(payload, runner=None):
    return json.loads(
        tools.execute_tool(
            "exec", json.dumps(payload), skills={}, runner=runner or (lambda argv: {})
        )
    )


def test_t_ex_01_success_envelope(tmp_path):
    assert run(tmp_path, "print('ok')") == {
        "exit_code": 0,
        "timed_out": False,
        "truncated": False,
        "stdout": "ok\n",
        "stderr": "",
    }


def test_t_ex_02_exit_code_and_stderr(tmp_path):
    result = run(tmp_path, "import sys; sys.stderr.write('bad\\n'); sys.exit(3)")
    assert result["exit_code"] == 3
    assert result["stderr"] == "bad\n"
    assert result["stdout"] == ""
    assert result["timed_out"] is False


def test_t_ex_03_timeout(tmp_path):
    started = time.monotonic()
    result = run(tmp_path, "import time; time.sleep(30)", timeout_s=1.0)
    elapsed = time.monotonic() - started
    assert result["timed_out"] is True
    assert result["exit_code"] < 0
    assert elapsed < 5.0


def test_t_ex_04_term_ignoring_child_is_killed(tmp_path):
    code = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
    started = time.monotonic()
    result = run(tmp_path, code, timeout_s=1.0)
    elapsed = time.monotonic() - started
    assert result["timed_out"] is True
    assert result["exit_code"] == -9
    assert elapsed < 12.0


def test_t_ex_05_grandchild_holding_pipes_does_not_hang(tmp_path):
    code = (
        "import subprocess, sys; "
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])"
    )
    started = time.monotonic()
    result = run(tmp_path, code)
    elapsed = time.monotonic() - started
    assert result["exit_code"] == 0
    assert elapsed < 10.0


def test_t_ex_06_both_streams_truncated(tmp_path):
    code = (
        "import sys; "
        "sys.stdout.write('a' * 1048576); sys.stdout.flush(); "
        "sys.stderr.write('b' * 1048576); sys.stderr.flush()"
    )
    result = run(tmp_path, code)
    assert len(result["stdout"]) == tools.EXEC_MAX_STREAM_BYTES
    assert len(result["stderr"]) == tools.EXEC_MAX_STREAM_BYTES
    assert result["truncated"] is True


def test_t_ex_07_environment_allowlist(tmp_path):
    result = run(tmp_path, "import json, os, sys; sys.stdout.write(json.dumps(dict(os.environ)))")
    env = json.loads(result["stdout"])
    assert set(env) <= {"PATH", "LANG", "HOME"}
    assert Path(env["HOME"]) == tmp_path


def test_t_ex_08_cwd_is_the_sandbox(tmp_path):
    result = run(tmp_path, "import os, sys; sys.stdout.write(os.getcwd())")
    assert Path(result["stdout"]).resolve() == tmp_path.resolve()


def test_t_ex_09_start_failures(tmp_path):
    assert tools.run_command(["nosuchprogram-xyz"], workdir=tmp_path) == {
        "error": "program not found: nosuchprogram-xyz"
    }
    assert tools.run_command([sys.executable], workdir=tmp_path / "gone") == {
        "error": "sandbox directory is missing"
    }


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "argv must contain between 1 and 32 elements"),
        (["a"] * 33, "argv must contain between 1 and 32 elements"),
        ([1], "argv must be an array of strings"),
        (["a\x00b"], "argv elements must not contain NUL bytes"),
        ("uname", "argv must be an array of strings"),
    ],
)
def test_t_ex_10_argv_validation(argv, message):
    assert exec_tool({"argv": argv}) == {"error": message}


def test_t_ex_10_argv_extra_rules():
    assert exec_tool({}) == {"error": "argv is required"}
    assert exec_tool({"argv": ["a" * 4097]}) == {
        "error": "argv elements must be at most 4096 characters"
    }
    assert exec_tool({"argv": ["  "]}) == {"error": "argv[0] must be a program name"}


def test_t_ex_11_invalid_utf8_is_replaced(tmp_path):
    result = run(tmp_path, "import sys; sys.stdout.buffer.write(b'\\xff\\xfe')")
    assert result["stdout"] == "\ufffd\ufffd"


def test_t_ex_12_byte_cap_applied_before_decoding(tmp_path):
    code = "import sys; sys.stdout.buffer.write(('\\u00e9' * 5000).encode('utf-8'))"
    result = run(tmp_path, code)
    assert result["truncated"] is True
    assert len(result["stdout"].encode("utf-8")) == 4096
    assert len(result["stdout"]) == 2048


@pytest.mark.parametrize("size", [4095, 4096, 4097])
def test_t_ex_13_cap_boundary(tmp_path, size):
    result = run(tmp_path, f"import sys; sys.stdout.buffer.write(b'x' * {size})")
    assert result["truncated"] is (size > 4096)
    assert len(result["stdout"]) == min(size, 4096)

