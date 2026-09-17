"""spec-v1.10.1 T2 (docs/spec/spec-v1.10.1.md sec.6/13/14, REQ-V1101-GC-01,
REQ-V1101-GATE-03, REQ-V1101-RPT-01 first sentence): an optional, validated
`env:` map on command gates, passed through to the gate's subprocess and
pinned on `skylos` (`SKYLOS_GREP_BUDGET=180`, after the v1.10.0-authoring
push failed `SKY-ANALYSIS-INCOMPLETE` on 2026-09-13 without it). Entirely
offline: no network, no live LLM, no Docker, no real subprocess left
running -- `subprocess.Popen` is monkeypatched wherever a gate's own
subprocess call is under test.

`T-V1101-GC-01`..`T-V1101-GC-06`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools import checks

REPO_ROOT = Path(__file__).resolve().parent.parent


def _base_command_gate(**overrides: object) -> dict:
    gate: dict = {
        "result_mode": "exit_status",
        "argv": ["echo", "hi"],
        "placeholders": {},
        "success_exit_codes": [0],
    }
    gate.update(overrides)
    return gate


def _base_builtin_gate(**overrides: object) -> dict:
    gate: dict = {"handler": "branch_name"}
    gate.update(overrides)
    return gate


class _FakeProc:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode

    def communicate(self, input=None, timeout=None):
        return b"", b""


# ---------------------------------------------------------------------------
# T-V1101-GC-01/02: env passthrough via run_argv -> subprocess.Popen
# ---------------------------------------------------------------------------


def test_run_argv_env_absent_reaches_popen_as_none(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_popen(argv, **kwargs):
        captured.update(kwargs)
        return _FakeProc()

    monkeypatch.setattr(checks.subprocess, "Popen", fake_popen)

    result = checks.run_argv(["true"], tmp_path, 5)

    assert result.ok
    assert captured["env"] is None


def test_run_argv_env_present_merges_over_os_environ(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_popen(argv, **kwargs):
        captured.update(kwargs)
        return _FakeProc()

    monkeypatch.setattr(checks.subprocess, "Popen", fake_popen)
    monkeypatch.setenv("V1101_GC_01_MARKER", "from-os-environ")

    result = checks.run_argv(["true"], tmp_path, 5, env={"SKYLOS_GREP_BUDGET": "180"})

    assert result.ok
    assert captured["env"]["SKYLOS_GREP_BUDGET"] == "180"
    assert captured["env"]["V1101_GC_01_MARKER"] == "from-os-environ"


def test_execute_command_gate_passes_gate_env_to_run_argv(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_run_argv(argv, cwd, timeout_seconds, **kwargs):
        captured["env"] = kwargs.get("env")
        return checks.CommandResult(True, 0, b"", b"", None)

    monkeypatch.setattr(checks, "run_argv", fake_run_argv)
    gate = _base_command_gate(
        kind="command",
        blocking=True,
        diff_scoped=False,
        timeout_seconds=5,
        env={"FOO": "bar"},
    )

    result = checks.execute_command_gate(
        "g",
        gate,
        repo_root=tmp_path,
        profile="full",
        scope_files=None,
        tracked_tree=None,
        known_severities=set(),
    )

    assert result.ran
    assert captured["env"] == {"FOO": "bar"}


def test_execute_command_gate_env_absent_passes_none_to_run_argv(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_run_argv(argv, cwd, timeout_seconds, **kwargs):
        captured["env"] = kwargs.get("env")
        return checks.CommandResult(True, 0, b"", b"", None)

    monkeypatch.setattr(checks, "run_argv", fake_run_argv)
    gate = _base_command_gate(kind="command", blocking=True, diff_scoped=False, timeout_seconds=5)

    result = checks.execute_command_gate(
        "g",
        gate,
        repo_root=tmp_path,
        profile="full",
        scope_files=None,
        tracked_tree=None,
        known_severities=set(),
    )

    assert result.ran
    assert captured["env"] is None


# ---------------------------------------------------------------------------
# T-V1101-GC-03 / T-V1101-ERR-01 row 6: rejected `env:` shapes on a command
# gate, each its own test asserting the exact GateConfigError message.
# ---------------------------------------------------------------------------


def test_env_not_a_mapping_is_rejected():
    gate = _base_command_gate(env="not-a-dict")
    with pytest.raises(
        checks.GateConfigError,
        match=r"^gates\.g\.env must map non-empty string keys to string values$",
    ):
        checks._validate_command_gate("g", gate, set())


def test_env_non_string_value_is_rejected():
    gate = _base_command_gate(env={"FOO": 123})
    with pytest.raises(
        checks.GateConfigError,
        match=r"^gates\.g\.env must map non-empty string keys to string values$",
    ):
        checks._validate_command_gate("g", gate, set())


def test_env_empty_string_key_is_rejected():
    gate = _base_command_gate(env={"": "x"})
    with pytest.raises(
        checks.GateConfigError,
        match=r"^gates\.g\.env must map non-empty string keys to string values$",
    ):
        checks._validate_command_gate("g", gate, set())


@pytest.mark.parametrize("bad_key", ["A=B", "1FOO"])
def test_env_key_failing_identifier_pattern_is_rejected(bad_key):
    gate = _base_command_gate(env={bad_key: "x"})
    with pytest.raises(
        checks.GateConfigError,
        match=rf"^gates\.g\.env key is not an identifier: {bad_key}$",
    ):
        checks._validate_command_gate("g", gate, set())


def test_env_value_containing_nul_is_rejected():
    gate = _base_command_gate(env={"FOO": "a\0b"})
    with pytest.raises(checks.GateConfigError, match=r"^gates\.g\.env value contains NUL: FOO$"):
        checks._validate_command_gate("g", gate, set())


@pytest.mark.parametrize(
    "secret_key", ["OPENROUTER_API_KEY", "openrouter_api_key", "Telegram_Bot_Token"]
)
def test_env_key_naming_a_secret_is_rejected_in_any_case(secret_key):
    gate = _base_command_gate(env={secret_key: "x"})
    with pytest.raises(
        checks.GateConfigError,
        match=rf"^gates\.g\.env must not name a secret: {secret_key}$",
    ):
        checks._validate_command_gate("g", gate, set())


def test_env_valid_shape_is_accepted():
    gate = _base_command_gate(env={"SKYLOS_GREP_BUDGET": "180"})
    checks._validate_command_gate("g", gate, set())  # must not raise


# ---------------------------------------------------------------------------
# T-V1101-GC-04 / T-V1101-ERR-01 row 6: a builtin gate carrying `env:` still
# hits the pre-existing unknown-key error, not a new one.
# ---------------------------------------------------------------------------


def test_builtin_gate_carrying_env_hits_the_existing_unknown_key_error():
    gate = _base_builtin_gate(
        blocking=True, diff_scoped=False, timeout_seconds=1, env={"FOO": "bar"}
    )
    with pytest.raises(checks.GateConfigError, match=r"^gates\.g: unknown key\(s\) \['env'\]$"):
        checks._validate_builtin_gate("g", gate, set())


# ---------------------------------------------------------------------------
# T-V1101-GC-05: the real config -- skylos carries env, nothing else does.
# ---------------------------------------------------------------------------


def test_skylos_gate_env_pinned_to_grep_budget_180():
    config = checks.load_gate_config()
    assert config["gates"]["skylos"]["env"] == {"SKYLOS_GREP_BUDGET": "180"}


def test_no_other_gate_in_the_real_config_carries_env():
    config = checks.load_gate_config()
    for name, gate in config["gates"].items():
        if name == "skylos":
            continue
        assert "env" not in gate, name


# ---------------------------------------------------------------------------
# T-V1101-GC-06 / T-V1101-RPT-01 (first sentence): lint-docs repointed at
# this release's report. The gate-matrix test itself lives in
# tests/test_v15_standards.py (test_v15_gate_04_profile_matrix_agrees_with_the_spec_table),
# already repointed at spec-v1.10.1.md there -- this is a light duplicate
# assertion, not a replacement for it.
# ---------------------------------------------------------------------------


def test_lint_docs_report_path_repointed_to_v1101():
    config = checks.load_gate_config()
    assert config["gates"]["lint-docs"]["report_path"] == "docs/reports/report-v1.10.1.md"
