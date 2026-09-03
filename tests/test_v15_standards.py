"""spec-v1.5: engineering standards, quality gates, dependency refresh.

One test per T-V15-* id of section 15. Offline discipline unchanged
(REQ-V12-OFF-01's conftest.py guard): no test touches the network, DNS or a
real Docker daemon, and none of these use a live credential as a test
secret. Tests needing a repository use a temporary git repo in `tmp_path`,
never the real one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools import checks

# ---------------------------------------------------------------------------
# T-V15-CC-01 .. T-V15-CC-07 (REQ-V15-CC-01..05)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subject",
    [
        "feat: add the runner",
        "fix: add the runner",
        "docs: add the runner",
        "style: add the runner",
        "refactor: add the runner",
        "perf: add the runner",
        "test: add the runner",
        "build: add the runner",
        "ci: add the runner",
        "chore: add the runner",
        "revert: add the runner",
        "feat(gates): add the runner",
        "feat!: add the runner",
        "feat(gates)!: add the runner",
    ],
)
def test_v15_cc_01_header_accepts_every_type_scope_bang(subject):
    ok, msg = checks.check_header(subject)
    assert ok, msg


@pytest.mark.parametrize(
    "subject",
    [
        "feature: add the runner",
        "Feat: add the runner",
        "feat add the runner",
        "feat:add the runner",
        "feat(Gates): add the runner",
        "feat: ",
        "feat:",
    ],
)
def test_v15_cc_02_header_rejects_malformed(subject):
    ok, msg = checks.check_header(subject)
    assert not ok
    assert "header check failed" in msg


def test_v15_cc_03_length_boundary():
    subject_72 = "feat: " + "x" * 66
    subject_73 = "feat: " + "x" * 67
    assert len(subject_72) == 72
    assert len(subject_73) == 73
    ok72, _ = checks.check_length(subject_72)
    ok73, msg73 = checks.check_length(subject_73)
    assert ok72
    assert not ok73
    assert "length check failed" in msg73
    assert "73" in msg73


def test_v15_cc_04_trailing_period_rejected_mid_subject_dot_unaffected():
    ok, msg = checks.check_punctuation("feat: add the runner.")
    assert not ok
    assert "punctuation check failed" in msg

    ok2, _ = checks.check_punctuation("docs: update README.md instructions")
    assert ok2


def test_v15_cc_05_prompt_reference(tmp_path: Path):
    (tmp_path / "docs" / "prompts").mkdir(parents=True)
    (tmp_path / "docs" / "prompts" / "44-go-spec-v1.5.md").write_text("x", encoding="utf-8")

    ok, _ = checks.check_prompt_reference(
        "body\n\n(prompt: docs/prompts/44-go-spec-v1.5.md)\n", tmp_path
    )
    assert ok

    ok_missing_ref, msg_missing_ref = checks.check_prompt_reference("no reference here", tmp_path)
    assert not ok_missing_ref
    assert "body check failed" in msg_missing_ref

    ok_dangling, msg_dangling = checks.check_prompt_reference(
        "(prompt: docs/prompts/99-does-not-exist.md)", tmp_path
    )
    assert not ok_dangling
    assert "does not exist" in msg_dangling


@pytest.mark.parametrize(
    "subject",
    [
        "Merge branch 'feat/x' into main",
        "Revert \"feat: add the runner\"",
        "fixup! feat: add the runner",
        "squash! feat: add the runner",
    ],
)
def test_v15_cc_06_bypass_prefixes_skip_every_check(subject):
    assert checks.is_bypassed(subject)
    assert checks.run_commit_msg_checks(subject, "", Path("/nonexistent")) == []


@pytest.mark.parametrize("branch", ["feat/x", "fix/a-b", "docs/v1.5", "chore/x_y"])
def test_v15_cc_07_branch_regex_accepts(branch):
    status, msg = checks.check_branch_name(
        branch,
        pattern=r"^(main|(feat|fix|docs|test|chore)/[a-z0-9][a-z0-9._-]*)$",
        warn_refs=["main"],
        warn_on_detached=True,
    )
    assert status == "ok", msg


@pytest.mark.parametrize("branch", ["feature/x", "FEAT/x", "feat/", "wip"])
def test_v15_cc_07_branch_regex_rejects(branch):
    status, _ = checks.check_branch_name(
        branch,
        pattern=r"^(main|(feat|fix|docs|test|chore)/[a-z0-9][a-z0-9._-]*)$",
        warn_refs=["main"],
        warn_on_detached=True,
    )
    assert status == "fail"


def test_v15_cc_07_branch_regex_warns_main_and_detached():
    status_main, _ = checks.check_branch_name(
        "main",
        pattern=r"^(main|(feat|fix|docs|test|chore)/[a-z0-9][a-z0-9._-]*)$",
        warn_refs=["main"],
        warn_on_detached=True,
    )
    assert status_main == "warn"

    status_detached, _ = checks.check_branch_name(
        None,
        pattern=r"^(main|(feat|fix|docs|test|chore)/[a-z0-9][a-z0-9._-]*)$",
        warn_refs=["main"],
        warn_on_detached=True,
    )
    assert status_detached == "warn"


# ---------------------------------------------------------------------------
# T-V15-GATE-01 .. T-V15-GATE-03 (REQ-V15-GATE-01..03)
# ---------------------------------------------------------------------------


def test_v15_gate_01_real_config_parses_and_is_bijective():
    config = checks.load_gate_config()
    gate_names = set(config["gates"])
    named_by_profile: set[str] = set()
    for members in config["profiles"].values():
        named_by_profile |= set(members)
    assert named_by_profile == gate_names

    for name, gate in config["gates"].items():
        if gate["kind"] != "command":
            continue
        result_mode = gate["result_mode"]
        if result_mode == "findings":
            for key in ("output_format", "parser", "findings_exit_codes", "artefact", "severity"):
                assert key in gate, f"{name} missing {key}"
        else:
            for key in ("output_format", "parser", "findings_exit_codes", "artefact", "severity"):
                assert key not in gate, f"{name} must not carry {key}"


def _minimal_config_text(gates_block: str, profiles_block: str = "  x: [g]") -> str:
    return f"""\
version: "1"
scope:
  base_branch: main
  zero_sha: "0000000000000000000000000000000000000000"
profiles:
{profiles_block}
tools: {{}}
gates:
{gates_block}
"""


def test_v15_gate_02_unknown_top_level_key(tmp_path: Path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        _minimal_config_text(
            "  g:\n    kind: builtin\n    handler: branch_name\n"
            "    blocking: true\n    diff_scoped: false\n    timeout_seconds: 1\n"
        )
        + "bogus: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(checks.GateConfigError, match="bogus"):
        checks.load_gate_config(path)


def test_v15_gate_02_duplicate_key(tmp_path: Path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        "version: \"1\"\nversion: \"2\"\nscope:\n  base_branch: main\n"
        "  zero_sha: \"0\"\nprofiles: {}\ntools: {}\ngates: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(checks.YamlError, match="duplicate key"):
        checks.load_gate_config(path)


def test_v15_gate_02_tab_character(tmp_path: Path):
    path = tmp_path / "cfg.yaml"
    path.write_text("version: \"1\"\n\tscope: {}\n", encoding="utf-8")
    with pytest.raises(checks.YamlError, match="tab"):
        checks.load_gate_config(path)


def test_v15_gate_02_bool_where_int_belongs(tmp_path: Path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        _minimal_config_text(
            "  g:\n    kind: builtin\n    handler: branch_name\n"
            "    blocking: true\n    diff_scoped: false\n    timeout_seconds: true\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(checks.GateConfigError, match="timeout_seconds"):
        checks.load_gate_config(path)


def test_v15_gate_02_gate_with_no_kind(tmp_path: Path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        _minimal_config_text(
            "  g:\n    blocking: true\n    diff_scoped: false\n    timeout_seconds: 1\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(checks.GateConfigError, match="kind"):
        checks.load_gate_config(path)


def test_v15_gate_02_command_gate_no_argv(tmp_path: Path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        _minimal_config_text(
            "  g:\n    kind: command\n    result_mode: exit_status\n"
            "    placeholders: {}\n    success_exit_codes: [0]\n"
            "    blocking: true\n    diff_scoped: false\n    timeout_seconds: 1\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(checks.GateConfigError, match="argv"):
        checks.load_gate_config(path)


def test_v15_gate_02_command_gate_no_result_mode(tmp_path: Path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        _minimal_config_text(
            "  g:\n    kind: command\n    argv: [true]\n"
            "    placeholders: {}\n    success_exit_codes: [0]\n"
            "    blocking: true\n    diff_scoped: false\n    timeout_seconds: 1\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(checks.GateConfigError, match="result_mode"):
        checks.load_gate_config(path)


@pytest.mark.parametrize("extra_key,extra_val", [("parser", "bare"), ("severity", "[LOW]"),
                                                  ("artefact", "a.json")])
def test_v15_gate_02_exit_status_gate_forbidden_keys(tmp_path: Path, extra_key, extra_val):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        _minimal_config_text(
            "  g:\n    kind: command\n    result_mode: exit_status\n"
            "    argv: [echo]\n    placeholders: {}\n    success_exit_codes: [0]\n"
            f"    {extra_key}: {extra_val}\n"
            "    blocking: true\n    diff_scoped: false\n    timeout_seconds: 1\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(checks.GateConfigError, match=extra_key):
        checks.load_gate_config(path)


@pytest.mark.parametrize(
    "extra_key,extra_val", [("argv", "[true]"), ("result_mode", "exit_status")]
)
def test_v15_gate_02_builtin_gate_forbidden_keys(tmp_path: Path, extra_key, extra_val):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        _minimal_config_text(
            "  g:\n    kind: builtin\n    handler: branch_name\n"
            f"    {extra_key}: {extra_val}\n"
            "    blocking: true\n    diff_scoped: false\n    timeout_seconds: 1\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(checks.GateConfigError, match=extra_key):
        checks.load_gate_config(path)


def test_v15_gate_02_unknown_handler(tmp_path: Path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        _minimal_config_text(
            "  g:\n    kind: builtin\n    handler: not_a_real_handler\n"
            "    blocking: true\n    diff_scoped: false\n    timeout_seconds: 1\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(checks.GateConfigError, match="handler"):
        checks.load_gate_config(path)


def test_v15_gate_02_unknown_placeholder(tmp_path: Path):
    path = tmp_path / "cfg.yaml"
    path.write_text(
        _minimal_config_text(
            "  g:\n    kind: command\n    result_mode: exit_status\n"
            '    argv: [echo, "{nope}"]\n    placeholders: {}\n'
            "    success_exit_codes: [0]\n"
            "    blocking: true\n    diff_scoped: false\n    timeout_seconds: 1\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(checks.GateConfigError, match="placeholder"):
        checks.load_gate_config(path)


def test_v15_gate_03_ruff_pin_drift():
    config = checks.load_gate_config()
    assert checks.pyproject_ruff_pin() == checks.config_ruff_pin(config)


# ---------------------------------------------------------------------------
# T-V15-TREE-01 (REQ-V15-TREE-02)
# ---------------------------------------------------------------------------


def test_v15_tree_01_config_module_not_shadowed_by_config_dir():
    import config as config_module

    assert config_module.__file__.endswith("config.py")


def test_v15_tree_01_config_dir_has_no_init(tmp_path: Path):
    del tmp_path
    repo_config_dir = checks.REPO_ROOT / "config"
    assert repo_config_dir.is_dir()
    assert not (repo_config_dir / "__init__.py").exists()
