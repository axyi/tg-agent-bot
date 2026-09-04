"""spec-v1.5: engineering standards, quality gates, dependency refresh.

One test per T-V15-* id of section 15. Offline discipline unchanged
(REQ-V12-OFF-01's conftest.py guard): no test touches the network, DNS or a
real Docker daemon, and none of these use a live credential as a test
secret. Tests needing a repository use a temporary git repo in `tmp_path`,
never the real one.
"""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from devtools import checks, install_hooks

_ALL_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"}

# Split so the 20-char pattern never appears contiguous in this file's own
# tracked source -- once the pre-commit hook is live (T8), a literal match
# would make gitleaks-staged block every future commit touching this file.
# The concatenation still produces the real matchable value inside the
# throwaway fixture repos these tests write it into.
_FAKE_AWS_KEY = "AKIAQWERTY" + "UIOPASDFGH"


def _init_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.local"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    return path


def _commit_all(path: Path, message: str = "init") -> None:
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", message], cwd=path, check=True)


def _stub_gate(exit_code: int, *, blocking: bool, diff_scoped: bool = False, path: str = "x.py"):
    script = (
        f"import json, sys\n"
        f"json.dump([dict(File={path!r}, RuleID='stub')], open(sys.argv[1], 'w'))\n"
        f"sys.exit({exit_code})\n"
    )
    return {
        "kind": "command",
        "result_mode": "findings",
        "argv": [sys.executable, "-c", script, "{artefact}"],
        "placeholders": {},
        "output_format": "json",
        "parser": "gitleaks_json",
        "success_exit_codes": [0],
        "findings_exit_codes": [1],
        "artefact": ".bench/checks/{profile}/stub.json",
        "blocking": blocking,
        "diff_scoped": diff_scoped,
        "severity": sorted(_ALL_SEVERITIES),
        "timeout_seconds": 10,
    }


def _exec(gate, repo, *, scope_files=None, tracked_tree=None, known_severities=None):
    return checks.execute_command_gate(
        "stub",
        gate,
        repo_root=repo,
        profile="full",
        scope_files=scope_files,
        tracked_tree=tracked_tree,
        known_severities=known_severities if known_severities is not None else set(_ALL_SEVERITIES),
    )


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
        'Revert "feat: add the runner"',
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
        'version: "1"\nversion: "2"\nscope:\n  base_branch: main\n'
        '  zero_sha: "0"\nprofiles: {}\ntools: {}\ngates: {}\n',
        encoding="utf-8",
    )
    with pytest.raises(checks.YamlError, match="duplicate key"):
        checks.load_gate_config(path)


def test_v15_gate_02_tab_character(tmp_path: Path):
    path = tmp_path / "cfg.yaml"
    path.write_text('version: "1"\n\tscope: {}\n', encoding="utf-8")
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


@pytest.mark.parametrize(
    "extra_key,extra_val", [("parser", "bare"), ("severity", "[LOW]"), ("artefact", "a.json")]
)
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


# ---------------------------------------------------------------------------
# T-V15-SCAN-01 .. T-V15-SCAN-12 (REQ-V15-SCAN-*, REQ-V15-GATE-06/07/08/12)
# ---------------------------------------------------------------------------


def test_v15_scan_01_stub_scanner_nonzero_blocking_true_fails(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo)
    result = _exec(_stub_gate(1, blocking=True), repo)
    assert result.ran
    assert result.blocked
    assert checks.ProfileResult("full", [result]).blocked


def test_v15_scan_02_stub_scanner_blocking_false_reports_but_passes(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo)
    result = _exec(_stub_gate(1, blocking=False), repo)
    assert result.ran
    assert not result.blocked
    assert len(result.findings_in_scope) == 1
    assert not checks.ProfileResult("full", [result]).blocked


def test_v15_scan_03_fail_closed_absent_binary(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo)
    gate = dict(_stub_gate(0, blocking=True))
    gate["argv"] = ["definitely-not-a-real-binary-xyz", "{artefact}"]
    result = _exec(gate, repo)
    assert not result.ran
    assert result.blocked
    assert "stub" in result.message


def test_v15_scan_03_fail_closed_timeout(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo)
    gate = dict(_stub_gate(0, blocking=True))
    gate["argv"] = [sys.executable, "-c", "import time; time.sleep(5)"]
    gate["timeout_seconds"] = 1
    result = _exec(gate, repo)
    assert not result.ran
    assert result.blocked
    assert "timed out" in result.message


def test_v15_scan_03_fail_closed_unparseable(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo)
    gate = dict(_stub_gate(1, blocking=True))
    script = "import sys\nopen(sys.argv[1], 'w').write('not json')\nsys.exit(1)\n"
    gate["argv"] = [sys.executable, "-c", script, "{artefact}"]
    result = _exec(gate, repo)
    assert not result.ran
    assert result.blocked
    assert "unparseable" in result.message


def test_v15_scan_04_fail_closed_in_shadow(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo)
    gate = dict(_stub_gate(0, blocking=False))
    gate["argv"] = ["definitely-not-a-real-binary-xyz"]
    result = _exec(gate, repo)
    assert not result.ran
    assert result.blocked
    assert checks.ProfileResult("full", [result]).blocked


def _two_finding_stub_gate(*, blocking: bool = True, diff_scoped: bool = True):
    script = (
        "import json, sys\n"
        "old = dict(path='old.py', extra=dict(severity='ERROR'))\n"
        "new = dict(path='new.py', extra=dict(severity='ERROR'))\n"
        "json.dump(dict(results=[old, new]), open(sys.argv[1], 'w'))\n"
        "sys.exit(1)\n"
    )
    return {
        "kind": "command",
        "result_mode": "findings",
        "argv": [sys.executable, "-c", script, "{artefact}"],
        "placeholders": {},
        "output_format": "json",
        "parser": "semgrep_json",
        "success_exit_codes": [0],
        "findings_exit_codes": [1],
        "artefact": ".bench/checks/{profile}/two.json",
        "blocking": blocking,
        "diff_scoped": diff_scoped,
        "severity": ["ERROR"],
        "timeout_seconds": 10,
    }


def test_v15_scan_05_diff_scoping_blocks_new_reports_old(tmp_path: Path):
    repo = _init_repo(tmp_path)
    (repo / "old.py").write_text("x = 1\n")
    (repo / "new.py").write_text("y = 2\n")
    _commit_all(repo)
    gate = _two_finding_stub_gate()
    result = _exec(gate, repo, scope_files={"new.py"}, known_severities={"ERROR"})
    assert result.ran
    assert result.blocked
    assert {f["path"] for f in result.findings_in_scope} == {"new.py"}
    assert {f["path"] for f in result.findings_out_of_scope} == {"old.py"}


def test_v15_scan_06_empty_scope_trap_on_main(tmp_path: Path):
    repo = _init_repo(tmp_path)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=repo, check=True)
    (repo / "a.py").write_text("x = 1\n")
    _commit_all(repo, "base")
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "empty"], cwd=repo, check=True)

    config = {"scope": {"base_branch": "main", "zero_sha": "0" * 40}}
    with pytest.raises(checks.EmptyScopeError):
        checks.compute_scope("full", config, repo, since=base_sha)


def test_v15_scan_06_full_on_main_without_since_refused(tmp_path: Path):
    repo = _init_repo(tmp_path)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=repo, check=True)
    (repo / "a.py").write_text("x = 1\n")
    _commit_all(repo, "base")
    config = {"scope": {"base_branch": "main", "zero_sha": "0" * 40}}
    with pytest.raises(checks.GateRunError, match="--since"):
        checks.compute_scope("full", config, repo)


def test_v15_scan_07_gitleaks_tree_not_diff_scoped_blocks_anywhere(tmp_path: Path):
    repo = _init_repo(tmp_path)
    (repo / "untouched.py").write_text("x = 1\n")
    _commit_all(repo)
    gate = _stub_gate(1, blocking=True, diff_scoped=False, path="untouched.py")
    result = _exec(gate, repo, scope_files=set())
    assert result.ran
    assert result.blocked
    assert {f["path"] for f in result.findings_in_scope} == {"untouched.py"}


def test_v15_scan_08_ruff_format_partition_blocks_only_new(tmp_path: Path):
    repo = _init_repo(tmp_path)
    (repo / "new_file.py").write_text("x=1\n")
    (repo / "legacy_file.py").write_text("y=2\n")
    _commit_all(repo)
    gate = {
        "kind": "command",
        "result_mode": "exit_status",
        "argv": ["ruff", "format", "--check", "--force-exclude", "{target}"],
        "placeholders": {},
        "success_exit_codes": [0],
        "blocking": True,
        "diff_scoped": True,
        "blocking_paths": ["new_file.py"],
        "timeout_seconds": 30,
    }
    result = checks.execute_command_gate(
        "ruff-format",
        gate,
        repo_root=repo,
        profile="full",
        scope_files={"new_file.py", "legacy_file.py"},
        tracked_tree=None,
        known_severities=set(),
    )
    assert result.ran
    assert result.blocked
    assert "new: 1 file(s), would reformat" in result.message
    assert "legacy: 1 file(s), would reformat" in result.message


def test_v15_scan_08_ruff_format_partition_legacy_only_passes(tmp_path: Path):
    repo = _init_repo(tmp_path)
    (repo / "new_file.py").write_text("z = 3\n")
    (repo / "legacy_file.py").write_text("y=2\n")
    _commit_all(repo)
    gate = {
        "kind": "command",
        "result_mode": "exit_status",
        "argv": ["ruff", "format", "--check", "--force-exclude", "{target}"],
        "placeholders": {},
        "success_exit_codes": [0],
        "blocking": True,
        "diff_scoped": True,
        "blocking_paths": ["new_file.py"],
        "timeout_seconds": 30,
    }
    result = checks.execute_command_gate(
        "ruff-format",
        gate,
        repo_root=repo,
        profile="full",
        scope_files={"new_file.py", "legacy_file.py"},
        tracked_tree=None,
        known_severities=set(),
    )
    assert result.ran
    assert not result.blocked
    assert "legacy: 1 file(s), would reformat" in result.message


def test_v15_scan_09_findings_gates_carry_artefact_placeholder():
    config = checks.load_gate_config()
    for name in ("gitleaks-staged", "gitleaks-tree", "trivy", "semgrep", "skylos"):
        gate = config["gates"][name]
        assert gate["result_mode"] == "findings"
        assert "{artefact}" in gate["argv"]
        assert "artefact" in gate

    exit_status_gate = config["gates"]["pytest"]
    assert exit_status_gate["result_mode"] == "exit_status"
    assert "artefact" not in exit_status_gate


def test_v15_scan_09_artefact_written_and_parsed(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo)
    result = _exec(_stub_gate(1, blocking=True), repo)
    assert result.ran
    assert result.artefact_path is not None
    assert result.artefact_path.exists()
    assert json.loads(result.artefact_path.read_text())


def test_v15_scan_09_missing_artefact_fails_the_gate(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo)
    gate = dict(_stub_gate(1, blocking=True))
    gate["argv"] = [sys.executable, "-c", "import sys\nsys.exit(1)\n"]
    result = _exec(gate, repo)
    assert not result.ran
    assert result.blocked
    assert "no artefact" in result.message


def test_v15_scan_10_severity_membership(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo)
    script = (
        "import json, sys\n"
        "hi = dict(path='a.py', extra=dict(severity='HIGH'))\n"
        "lo = dict(path='b.py', extra=dict(severity='LOW'))\n"
        "json.dump(dict(results=[hi, lo]), open(sys.argv[1], 'w'))\n"
        "sys.exit(1)\n"
    )
    gate = {
        "kind": "command",
        "result_mode": "findings",
        "argv": [sys.executable, "-c", script, "{artefact}"],
        "placeholders": {},
        "output_format": "json",
        "parser": "semgrep_json",
        "success_exit_codes": [0],
        "findings_exit_codes": [1],
        "artefact": ".bench/checks/{profile}/sev.json",
        "blocking": True,
        "diff_scoped": False,
        "severity": ["CRITICAL", "HIGH"],
        "timeout_seconds": 10,
    }
    result = checks.execute_command_gate(
        "sev",
        gate,
        repo_root=repo,
        profile="full",
        scope_files=None,
        tracked_tree=None,
        known_severities={"CRITICAL", "HIGH", "LOW"},
    )
    assert result.ran
    assert result.blocked
    blocking_paths = {
        f["path"] for f in result.findings_in_scope if f["severity"] in gate["severity"]
    }
    assert blocking_paths == {"a.py"}
    reported_only = [f for f in result.findings_in_scope if f["severity"] not in gate["severity"]]
    assert {f["path"] for f in reported_only} == {"b.py"}


def test_v15_scan_10_unknown_severity_fails_closed(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo)
    script = (
        "import json, sys\n"
        "finding = dict(path='a.py', extra=dict(severity='NOTASEVERITY'))\n"
        "json.dump(dict(results=[finding]), open(sys.argv[1], 'w'))\n"
        "sys.exit(1)\n"
    )
    gate = {
        "kind": "command",
        "result_mode": "findings",
        "argv": [sys.executable, "-c", script, "{artefact}"],
        "placeholders": {},
        "output_format": "json",
        "parser": "semgrep_json",
        "success_exit_codes": [0],
        "findings_exit_codes": [1],
        "artefact": ".bench/checks/{profile}/sev2.json",
        "blocking": True,
        "diff_scoped": False,
        "severity": ["CRITICAL", "HIGH"],
        "timeout_seconds": 10,
    }
    result = checks.execute_command_gate(
        "sev",
        gate,
        repo_root=repo,
        profile="full",
        scope_files=None,
        tracked_tree=None,
        known_severities={"CRITICAL", "HIGH"},
    )
    assert not result.ran
    assert result.blocked
    assert "unrecognised severity" in result.message


def test_v15_scan_11_gitleaks_tree_committed_vs_gitignored(tmp_path: Path):
    repo = _init_repo(tmp_path)
    (repo / ".gitignore").write_text("ignored.py\n")
    (repo / "committed.py").write_text("AWS_KEY = '" + _FAKE_AWS_KEY + "'\n")
    (repo / "ignored.py").write_text("AWS_KEY = '" + _FAKE_AWS_KEY + "'\n")
    _commit_all(repo)

    tree_dir = tmp_path / "materialized"
    tree_dir.mkdir()
    entries = checks.list_tree_entries("HEAD", repo)
    checks.materialize_tracked_tree(entries, tree_dir, repo)
    assert (tree_dir / "committed.py").exists()
    assert not (tree_dir / "ignored.py").exists()

    report_path = tmp_path / "report.json"
    result = subprocess.run(
        [
            "gitleaks",
            "dir",
            "--no-banner",
            "--redact",
            "--report-format",
            "json",
            "--report-path",
            str(report_path),
            str(tree_dir),
        ],
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 1
    findings = json.loads(report_path.read_text())
    files_found = {f["File"] for f in findings}
    assert any("committed.py" in f for f in files_found)
    assert not any("ignored.py" in f for f in files_found)


def test_v15_scan_12_committed_content_survives_deletion(tmp_path: Path):
    repo = _init_repo(tmp_path)
    (repo / "secret.py").write_text("AWS_KEY = '" + _FAKE_AWS_KEY + "'\n")
    _commit_all(repo)
    (repo / "secret.py").unlink()

    tree_dir = tmp_path / "materialized"
    tree_dir.mkdir()
    checks.materialize_tracked_tree(checks.list_tree_entries("HEAD", repo), tree_dir, repo)
    assert (tree_dir / "secret.py").read_text() == "AWS_KEY = '" + _FAKE_AWS_KEY + "'\n"


def test_v15_scan_12_committed_content_survives_overwrite(tmp_path: Path):
    repo = _init_repo(tmp_path)
    (repo / "secret.py").write_text("AWS_KEY = '" + _FAKE_AWS_KEY + "'\n")
    _commit_all(repo)
    (repo / "secret.py").write_text("clean = True\n")

    tree_dir = tmp_path / "materialized"
    tree_dir.mkdir()
    checks.materialize_tracked_tree(checks.list_tree_entries("HEAD", repo), tree_dir, repo)
    assert "AKIA" in (tree_dir / "secret.py").read_text()


def test_v15_scan_12_gitlink_rejected(tmp_path: Path):
    entries = [("160000", "0" * 40, "vendor/submodule")]
    with pytest.raises(checks.GitlinkRejected, match="vendor/submodule"):
        checks.materialize_tracked_tree(entries, tmp_path, tmp_path)


# ---------------------------------------------------------------------------
# N4, N5 (REQ-V15-SCAN-02, REQ-V15-SCAN-04)
# ---------------------------------------------------------------------------


def test_n4_gitleaks_allowlist_control_suppression_escape(tmp_path: Path):
    import re as _re

    real_config = (checks.REPO_ROOT / ".gitleaks.toml").read_text()
    control_config = _re.sub(r"\n\[\[allowlists\]\].*", "", real_config, flags=_re.S)
    assert control_config != real_config

    repo = _init_repo(tmp_path)
    (repo / "tests").mkdir()
    (repo / "src").mkdir()
    control_path = tmp_path / "control.toml"
    control_path.write_text(control_config)
    real_path = tmp_path / "real.toml"
    real_path.write_text(real_config)

    (repo / "tests" / "canary.py").write_text("SYNTHETIC-CANARY-1\n")
    subprocess.run(["git", "add", "tests/canary.py"], cwd=repo, check=True)

    control_report = tmp_path / "control-report.json"
    control_result = subprocess.run(
        [
            "gitleaks",
            "git",
            "--staged",
            "--no-banner",
            "--redact",
            "--config",
            str(control_path),
            "--report-format",
            "json",
            "--report-path",
            str(control_report),
            ".",
        ],
        cwd=repo,
        capture_output=True,
        timeout=30,
    )
    assert control_result.returncode == 1, "control: canary must be detected without the allowlist"

    suppress_report = tmp_path / "suppress-report.json"
    suppress_result = subprocess.run(
        [
            "gitleaks",
            "git",
            "--staged",
            "--no-banner",
            "--redact",
            "--config",
            str(real_path),
            "--report-format",
            "json",
            "--report-path",
            str(suppress_report),
            ".",
        ],
        cwd=repo,
        capture_output=True,
        timeout=30,
    )
    assert suppress_result.returncode == 0, "suppression: same value, same path, must be suppressed"
    assert json.loads(suppress_report.read_text()) == []

    (repo / "src" / "leak.py").write_text("SYNTHETIC-CANARY-NOT-ALLOWLISTED-1\n")
    subprocess.run(["git", "add", "src/leak.py"], cwd=repo, check=True)
    escape_report = tmp_path / "escape-report.json"
    escape_result = subprocess.run(
        [
            "gitleaks",
            "git",
            "--staged",
            "--no-banner",
            "--redact",
            "--config",
            str(real_path),
            "--report-format",
            "json",
            "--report-path",
            str(escape_report),
            ".",
        ],
        cwd=repo,
        capture_output=True,
        timeout=30,
    )
    assert escape_result.returncode == 1, "escape: sentinel outside tests/ and docs/ must be caught"
    escape_findings = json.loads(escape_report.read_text())
    assert any(f["File"] == "src/leak.py" for f in escape_findings)
    assert not any(f["File"] == "tests/canary.py" for f in escape_findings)
    assert all(f["Secret"] == "REDACTED" for f in escape_findings)


def test_n5_semgrep_offline_with_vendored_ruleset_and_empty_cache(tmp_path: Path):
    import os
    import shutil as _shutil

    repo = _init_repo(tmp_path)
    _shutil.copytree(checks.REPO_ROOT / ".semgrep", repo / ".semgrep")
    (repo / "x.py").write_text('import subprocess\nsubprocess.call("ls " + input(), shell=True)\n')
    _commit_all(repo)

    env = dict(os.environ)
    env["HOME"] = str(tmp_path / "empty-home")
    (tmp_path / "empty-home").mkdir()
    env["HTTP_PROXY"] = env["HTTPS_PROXY"] = "http://127.0.0.1:1"
    env["http_proxy"] = env["https_proxy"] = "http://127.0.0.1:1"

    out_path = repo / "out.json"
    result = subprocess.run(
        [
            "semgrep",
            "scan",
            "--config",
            ".semgrep/",
            "--severity",
            "ERROR",
            "--error",
            "--metrics=off",
            "--disable-version-check",
            "--json",
            "--output",
            str(out_path),
            ".",
        ],
        cwd=repo,
        capture_output=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 1, result.stderr.decode(errors="replace")
    findings = json.loads(out_path.read_text())
    assert findings["results"]


# ---------------------------------------------------------------------------
# T-V15-HOOK-01 .. T-V15-HOOK-05, N1, N2, N3, N6, T-V15-GATE-06
# (REQ-V15-HOOK-01..06, REQ-V15-GATE-05, REQ-V15-GATE-07's pre-push scope)
# ---------------------------------------------------------------------------


def _fixture_hooks_dir(repo: Path) -> Path:
    """A `.githooks/` whose three files exist but start non-executable --
    exactly what `install_hooks.install()` is supposed to fix."""
    hooks = repo / ".githooks"
    hooks.mkdir()
    for name in install_hooks.HOOK_NAMES:
        (hooks / name).write_text("#!/bin/sh\nset -eu\nexit 0\n")
        (hooks / name).chmod(0o644)
    return hooks


def test_v15_hook_01_install_sets_hooks_path_and_executable(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _fixture_hooks_dir(repo)
    changed = install_hooks.install(repo)
    assert changed
    assert install_hooks._configured_hooks_path(repo) == ".githooks"
    for name in install_hooks.HOOK_NAMES:
        assert (repo / ".githooks" / name).stat().st_mode & stat.S_IXUSR


def test_v15_hook_02_second_run_is_idempotent_and_byte_identical(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _fixture_hooks_dir(repo)
    install_hooks.install(repo)
    before_bytes = {n: (repo / ".githooks" / n).read_bytes() for n in install_hooks.HOOK_NAMES}
    before_mode = {n: (repo / ".githooks" / n).stat().st_mode for n in install_hooks.HOOK_NAMES}

    changed = install_hooks.install(repo)

    assert changed == []
    assert install_hooks.check(repo) == []
    after_bytes = {n: (repo / ".githooks" / n).read_bytes() for n in install_hooks.HOOK_NAMES}
    after_mode = {n: (repo / ".githooks" / n).stat().st_mode for n in install_hooks.HOOK_NAMES}
    assert before_bytes == after_bytes
    assert before_mode == after_mode


@pytest.mark.parametrize("problem", ["unset", "wrong_path", "missing_hook", "not_executable"])
def test_v15_hook_03_check_reports_each_problem_distinctly(tmp_path: Path, problem: str):
    repo = _init_repo(tmp_path)
    _fixture_hooks_dir(repo)
    install_hooks.install(repo)

    if problem == "unset":
        subprocess.run(["git", "config", "--unset", "core.hooksPath"], cwd=repo, check=True)
        needle = "core.hooksPath is not set"
    elif problem == "wrong_path":
        subprocess.run(["git", "config", "core.hooksPath", "elsewhere"], cwd=repo, check=True)
        needle = "core.hooksPath is 'elsewhere'"
    elif problem == "missing_hook":
        (repo / ".githooks" / "pre-push").unlink()
        needle = "hook missing"
    else:
        (repo / ".githooks" / "pre-commit").chmod(0o644)
        needle = "hook not executable"

    problems = install_hooks.check(repo)
    assert problems
    assert any(needle in p for p in problems)


def test_v15_hook_04_check_passes_on_correctly_installed_repo(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _fixture_hooks_dir(repo)
    install_hooks.install(repo)
    assert install_hooks.check(repo) == []


def test_v15_hook_05_first_push_scope_covers_every_commit_not_just_head(tmp_path: Path):
    repo = _init_repo(tmp_path)
    (repo / "root.txt").write_text("1\n")
    _commit_all(repo, "root")
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feature"], cwd=repo, check=True)

    (repo / "a.txt").write_text("1\n")
    _commit_all(repo, "c1")
    (repo / "b.txt").write_text("1\n")
    _commit_all(repo, "c2")  # second-to-last commit
    (repo / "c.txt").write_text("1\n")
    _commit_all(repo, "c3")
    local_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    zero_sha = "0" * 40
    stdin_text = f"refs/heads/feature {local_sha} refs/heads/feature {zero_sha}\n"
    scope_cfg = {"base_branch": "main", "zero_sha": zero_sha}

    files, tree_dir = checks._pre_push_scope(stdin_text, scope_cfg, repo)
    try:
        assert "b.txt" in files
        head1_only = checks.changed_files_in_range("HEAD~1", "HEAD", repo)
        assert "b.txt" not in head1_only
    finally:
        shutil.rmtree(tree_dir, ignore_errors=True)


def test_v15_hook_05_empty_or_unparseable_stdin_fails_closed(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo, "c1")
    scope_cfg = {"base_branch": "main", "zero_sha": "0" * 40}
    with pytest.raises(checks.GateRunError):
        checks._pre_push_scope("", scope_cfg, repo)
    with pytest.raises(checks.GateRunError):
        checks._pre_push_scope("not a valid ref record\n", scope_cfg, repo)


def _install_commit_msg_hook(repo: Path) -> None:
    hooks_dir = repo / ".githooks"
    hooks_dir.mkdir()
    shutil.copy(checks.REPO_ROOT / ".githooks" / "commit-msg", hooks_dir / "commit-msg")
    (hooks_dir / "commit-msg").chmod(0o755)
    dest_devtools = repo / "devtools"
    dest_devtools.mkdir()
    (dest_devtools / "__init__.py").write_text("")
    shutil.copy(checks.REPO_ROOT / "devtools" / "checks.py", dest_devtools / "checks.py")
    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=repo, check=True)


def _commit_via_real_hook(repo: Path, subject: str) -> subprocess.CompletedProcess[str]:
    (repo / "a.txt").write_text("x\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    return subprocess.run(
        ["git", "commit", "-m", subject], cwd=repo, capture_output=True, text=True
    )


def test_n1_bad_header_rejected_by_the_real_hook(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _install_commit_msg_hook(repo)
    result = _commit_via_real_hook(repo, "added stuff")
    assert result.returncode != 0
    assert "header" in (result.stdout + result.stderr)


def test_n2_missing_prompt_reference_rejected_by_the_real_hook(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _install_commit_msg_hook(repo)
    result = _commit_via_real_hook(repo, "feat: add the runner")
    assert result.returncode != 0
    assert "body" in (result.stdout + result.stderr)


def test_n3_overlong_header_rejected_by_the_real_hook(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _install_commit_msg_hook(repo)
    subject = "feat: " + "x" * 74  # 80 chars total
    assert len(subject) == 80
    result = _commit_via_real_hook(repo, subject)
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "length" in combined
    assert "80" in combined


@pytest.fixture
def git_worktree(tmp_path: Path):
    """A disposable worktree of this repo's own HEAD on a throwaway branch --
    gives `uv run`/pyproject.toml-dependent gates (ruff, pytest) a real
    project to run against without ever touching the main working tree."""
    wt = tmp_path / "wt"
    branch = f"test/v15-{tmp_path.name}"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(wt), "HEAD"],
        cwd=checks.REPO_ROOT,
        check=True,
        capture_output=True,
    )
    try:
        subprocess.run(
            ["git", "checkout", "-q", "-b", branch], cwd=wt, check=True, capture_output=True
        )
        subprocess.run(["git", "config", "user.email", "t@t.local"], cwd=wt, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=wt, check=True)
        yield wt
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(wt)],
            cwd=checks.REPO_ROOT,
            check=False,
            capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-D", branch], cwd=checks.REPO_ROOT, check=False, capture_output=True
        )


def test_v15_gate_06_replay_ruff_invocation_uses_repo_root_cwd_and_relative_path(
    tmp_path: Path, monkeypatch
):
    """REQ-V15-GATE-05: ruff runs with the repository root as cwd (so
    pyproject.toml resolves) and `--stdin-filename` set to the exact
    repository-relative path -- never a $TMPDIR path a materialized-blob
    implementation would produce, which `exclude`/`per-file-ignores` would
    then resolve differently than `pre-commit` does."""
    repo = _init_repo(tmp_path)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "x.py").write_text("x = 1\n")
    (repo / "docs" / "prompts").mkdir(parents=True)
    (repo / "docs" / "prompts" / "44-go-spec-v1.5.md").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "commit",
            "-q",
            "-m",
            "feat: add pkg/x.py",
            "-m",
            "(prompt: docs/prompts/44-go-spec-v1.5.md)",
        ],
        cwd=repo,
        check=True,
    )
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    calls: list[tuple[list[str], Path]] = []

    def fake_run_argv(argv, cwd, timeout_seconds, **kwargs):
        calls.append((list(argv), Path(cwd)))
        return checks.CommandResult(True, 0, b"", b"", None)

    monkeypatch.setattr(checks, "run_argv", fake_run_argv)

    config = checks.load_gate_config()
    problems = checks._replay_one_commit(sha, config, repo)

    assert not problems, problems
    ruff_calls = [c for c in calls if "ruff" in c[0]]
    assert ruff_calls
    for argv, cwd in ruff_calls:
        assert cwd == repo
        idx = argv.index("--stdin-filename")
        stdin_path = argv[idx + 1]
        assert stdin_path == "pkg/x.py"
        assert not Path(stdin_path).is_absolute()


def test_n6_pre_push_refused_when_pytest_fails(git_worktree: Path):
    wt = git_worktree
    (wt / "tests" / "test_v15_tmp_failing.py").write_text(
        "def test_deliberately_failing():\n    assert False\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
    subprocess.run(
        [
            "git",
            "commit",
            "-q",
            "-m",
            "test: add a deliberately failing test",
            "-m",
            "(prompt: docs/prompts/44-go-spec-v1.5.md)",
        ],
        cwd=wt,
        check=True,
    )
    local_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True, check=True
    ).stdout.strip()

    config = {
        "scope": {"base_branch": "main", "zero_sha": "0" * 40},
        "profiles": {"pre-push": ["pytest"]},
        "gates": {
            "pytest": {
                "kind": "command",
                "result_mode": "exit_status",
                "argv": ["uv", "run", "--locked", "pytest", "tests/test_v15_tmp_failing.py"],
                "placeholders": {},
                "success_exit_codes": [0],
                "blocking": True,
                "diff_scoped": False,
                "timeout_seconds": 60,
            }
        },
    }
    stdin_text = f"refs/heads/{wt.name} {local_sha} refs/heads/main {'0' * 40}\n"

    result = checks.run_profile("pre-push", config, wt, stdin_refs=stdin_text)

    assert result.blocked
    pytest_result = next(g for g in result.gate_results if g.name == "pytest")
    assert pytest_result.blocked
    assert "pytest" in pytest_result.message


# ---------------------------------------------------------------------------
# N7, checks.py doctor (REQ-V15-GATE-03, REQ-V15-RTK-03)
# ---------------------------------------------------------------------------


def _doctor_ready_repo(tmp_path: Path) -> Path:
    """A fixture repo with install_hooks.py copied in and hooks installed --
    so doctor's own hook-chain check passes, isolating a test's assertions
    to whatever tool-version behaviour it actually exercises."""
    repo = _init_repo(tmp_path)
    _commit_all(repo, "c1")
    dest_devtools = repo / "devtools"
    dest_devtools.mkdir()
    (dest_devtools / "__init__.py").write_text("")
    shutil.copy(
        checks.REPO_ROOT / "devtools" / "install_hooks.py", dest_devtools / "install_hooks.py"
    )
    hooks_dir = repo / ".githooks"
    hooks_dir.mkdir()
    for hook_name in ("commit-msg", "pre-commit", "pre-push"):
        (hooks_dir / hook_name).write_text("#!/bin/sh\nset -eu\nexit 0\n")
    install_hooks.install(repo)
    return repo


def _doctor_gate(*, blocking: bool = True, warn_only_tools=()):
    return {
        "kind": "builtin",
        "handler": "doctor",
        "warn_only_tools": list(warn_only_tools),
        "blocking": blocking,
        "diff_scoped": False,
        "timeout_seconds": 10,
    }


def _version_tool(pinned: str, printed: str, *, parser: str = "bare"):
    return {
        "version": pinned,
        "via": "binary",
        "version_argv": [sys.executable, "-c", f"print({printed!r})"],
        "version_parser": parser,
    }


@pytest.mark.parametrize("printed", ["0.9.0", "1.1.0"])
def test_n7_doctor_fails_on_version_mismatch_including_newer(tmp_path: Path, printed: str):
    repo = _doctor_ready_repo(tmp_path)
    config = {"tools": {"widget": _version_tool("1.0.0", printed)}}
    result = checks._run_doctor("doctor", _doctor_gate(), config, repo)
    assert result.blocked
    assert "widget" in result.message
    assert "1.0.0" in result.message
    assert printed in result.message


def test_v15_gate_doctor_passes_when_every_tool_matches_its_pin(tmp_path: Path):
    repo = _doctor_ready_repo(tmp_path)
    config = {"tools": {"widget": _version_tool("1.0.0", "1.0.0")}}
    result = checks._run_doctor("doctor", _doctor_gate(), config, repo)
    assert not result.blocked
    assert "all tools at pin" in result.message


def test_v15_gate_doctor_rtk_mismatch_is_warn_only_not_blocking(tmp_path: Path):
    repo = _doctor_ready_repo(tmp_path)
    config = {
        "tools": {
            "widget": _version_tool("1.0.0", "1.0.0"),
            "rtk": _version_tool("0.47.0", "0.46.0"),
        }
    }
    result = checks._run_doctor("doctor", _doctor_gate(warn_only_tools=["rtk"]), config, repo)
    assert not result.blocked
    assert "rtk" in result.message
    assert "warning" in result.message.lower()


def test_v15_gate_doctor_missing_binary_fails_closed(tmp_path: Path):
    repo = _doctor_ready_repo(tmp_path)
    config = {
        "tools": {
            "ghost": {
                "version": "1.0.0",
                "via": "binary",
                "version_argv": ["a-binary-that-does-not-exist-anywhere"],
                "version_parser": "bare",
            }
        }
    }
    result = checks._run_doctor("doctor", _doctor_gate(), config, repo)
    assert result.blocked
    assert "ghost" in result.message


def test_v15_gate_doctor_checks_hook_installation(tmp_path: Path):
    repo = _init_repo(tmp_path)
    _commit_all(repo, "c1")
    dest_devtools = repo / "devtools"
    dest_devtools.mkdir()
    (dest_devtools / "__init__.py").write_text("")
    shutil.copy(
        checks.REPO_ROOT / "devtools" / "install_hooks.py", dest_devtools / "install_hooks.py"
    )
    config = {"tools": {}}
    result = checks._run_doctor("doctor", _doctor_gate(), config, repo)
    assert result.blocked
    assert "hooks" in result.message


def test_v15_gate_doctor_real_config_against_the_real_repository():
    config = checks.load_gate_config()
    result = checks._run_doctor("doctor", config["gates"]["doctor"], config, checks.REPO_ROOT)
    assert not result.blocked, result.message


# ---------------------------------------------------------------------------
# T-V15-PRM-01 .. T-V15-PRM-04, T-V15-RPT-01 (REQ-V15-PRM-*, REQ-V15-RPT-01/03)
# ---------------------------------------------------------------------------

_FIXTURE_PROMPT_HEADER = """# Prompt NN -- fixture

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5
- **Model reason:** fixture
- **Harness:** Claude Code
- **Stage:** T11
- **Owner of:** `tests/test_v15_standards.py`
- **REQ ids:** REQ-V15-PRM-01
"""

_FIXTURE_PROMPT_BODY = """
## Goal

Fixture goal paragraph.

## Constraints

Fixture constraints.

## Acceptance

Run `uv run --locked pytest` and expect exit 0.

## Stop

Stop if the fixture breaks.
"""


def test_v15_prm_01_lint_accepts_a_well_formed_fixture(tmp_path: Path):
    p = tmp_path / "44-fixture.md"
    p.write_text(_FIXTURE_PROMPT_HEADER + _FIXTURE_PROMPT_BODY)
    assert checks._lint_prompt_file(p, exempt=False) == []


def test_v15_prm_02_lint_rejects_missing_model_reason(tmp_path: Path):
    header = _FIXTURE_PROMPT_HEADER.replace("- **Model reason:** fixture\n", "")
    p = tmp_path / "44-fixture.md"
    p.write_text(header + _FIXTURE_PROMPT_BODY)
    assert checks._lint_prompt_file(p, exempt=False) != []


def test_v15_prm_02_lint_rejects_missing_stop_block(tmp_path: Path):
    body = _FIXTURE_PROMPT_BODY.split("## Stop")[0]
    p = tmp_path / "44-fixture.md"
    p.write_text(_FIXTURE_PROMPT_HEADER + body)
    problems = checks._lint_prompt_file(p, exempt=False)
    assert problems
    assert any("Stop" in pr or "blocks" in pr for pr in problems)


def test_v15_prm_02_lint_rejects_blocks_out_of_order(tmp_path: Path):
    body = """
## Constraints

Fixture constraints.

## Goal

Fixture goal.

## Acceptance

Run `uv run --locked pytest`.

## Stop

Stop condition.
"""
    p = tmp_path / "44-fixture.md"
    p.write_text(_FIXTURE_PROMPT_HEADER + body)
    problems = checks._lint_prompt_file(p, exempt=False)
    assert problems
    assert any("order" in pr for pr in problems)


def test_v15_prm_02_lint_rejects_acceptance_with_only_prose(tmp_path: Path):
    body = """
## Goal

Fixture goal.

## Constraints

Fixture constraints.

## Acceptance

It works correctly and everyone is happy with the result.

## Stop

Stop condition.
"""
    p = tmp_path / "44-fixture.md"
    p.write_text(_FIXTURE_PROMPT_HEADER + body)
    problems = checks._lint_prompt_file(p, exempt=False)
    assert problems
    assert any("Acceptance" in pr for pr in problems)


def test_v15_prm_03_template_md_passes_the_lint():
    template = checks.REPO_ROOT / "docs" / "prompts" / "TEMPLATE.md"
    assert checks._lint_prompt_file(template, exempt=False) == []


def test_v15_prm_04_exemption_is_a_literal_filename_not_a_numeric_comparison(tmp_path: Path):
    exempt_files = {"43-v14-verify-run-fixes.md"}
    p = tmp_path / "43-a-new-different-file.md"
    p.write_text(_FIXTURE_PROMPT_HEADER)
    is_exempt = p.name in exempt_files
    assert not is_exempt
    problems = checks._lint_prompt_file(p, exempt=is_exempt)
    assert problems


_LEDGER_HEADER = (
    "| Project | Ver | Date | Spec (tokens) | Prompts | First run | Bugs | "
    "Tokens ↑/↓ | Cost | Model | Harness |"
)


def test_v15_rpt_01_lint_rejects_missing_ledger_section(tmp_path: Path):
    report = tmp_path / "report-v1.5.md"
    report.write_text("# Report\n\nNo ledger section here.\n")
    assert checks._lint_report_ledger(report, _LEDGER_HEADER) != []


def test_v15_rpt_01_lint_rejects_cell_count_mismatch(tmp_path: Path):
    report = tmp_path / "report-v1.5.md"
    short_row = "| tg-agent-bot | v1.5 | 2026-09-04 | ~5k | 11 | yes | 0 | 1k/2k |"
    report.write_text(f"## Ledger row (paste into `economics.md`)\n\n```\n{short_row}\n```\n")
    assert checks._lint_report_ledger(report, _LEDGER_HEADER) != []


def test_v15_rpt_01_lint_accepts_matching_cell_count(tmp_path: Path):
    report = tmp_path / "report-v1.5.md"
    row = (
        "| tg-agent-bot | v1.5 | 2026-09-04 | ~5k/6k | 11 | yes | 0 | 1k/2k | $0.01 | sonnet | CC |"
    )
    report.write_text(f"## Ledger row (paste into `economics.md`)\n\n```\n{row}\n```\n")
    assert checks._lint_report_ledger(report, _LEDGER_HEADER) == []


# ---------------------------------------------------------------------------
# T-V15-GATE-04, T-V15-GATE-05 (REQ-V15-GATE-11, REQ-V15-GATE-04)
# ---------------------------------------------------------------------------

_GATE_MATRIX_LABEL_TO_NAME = {
    "`ruff check` (staged)": "ruff-check",
    "`ruff check .` (tree)": "ruff-check-all",
    "`ruff format --check`": "ruff-format",
    "branch-name check": "branch-name",
    # "commit-msg checks" is not a `profiles:` gate -- own hook / via `replay`.
    "`gitleaks git --staged`": "gitleaks-staged",
    "`gitleaks dir` (tree)": "gitleaks-tree",
    "`uv sync --locked`": "uv-sync",
    "`pytest`": "pytest",
    "`bot.py --selftest`": "selftest",
    "`bot.py --selftest-live`": "selftest-live",
    "`mutation_check.py --select v15-`": "mutation-v15",
    "`mutation_check.py` (all)": "mutation-all",
    "`trivy fs`": "trivy",
    "`semgrep scan`": "semgrep",
    "`skylos`": "skylos",
    "`install_hooks.py --check`": "hooks-installed",
    "`checks.py doctor`": "doctor",
    "`checks.py lint-docs`": "lint-docs",
}


def _parse_gate_matrix(spec_text: str) -> dict[str, dict[str, bool]]:
    lines = spec_text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("| gate | pre-commit"))
    matrix: dict[str, dict[str, bool]] = {}
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        label, pc, pp, full = cells[0], cells[1], cells[2], cells[3]
        matrix[label] = {
            "pre-commit": pc == "yes",
            "pre-push": pp == "yes",
            "full": full == "yes",
        }
    return matrix


def test_v15_gate_04_profile_matrix_agrees_with_the_spec_table():
    spec_text = (checks.REPO_ROOT / "docs" / "spec" / "spec-v1.5.md").read_text(encoding="utf-8")
    matrix = _parse_gate_matrix(spec_text)
    config = checks.load_gate_config()

    for label in _GATE_MATRIX_LABEL_TO_NAME:
        assert label in matrix, f"spec table row not found: {label!r}"

    for profile in ("pre-commit", "pre-push", "full"):
        expected = {
            _GATE_MATRIX_LABEL_TO_NAME[label]
            for label, cells in matrix.items()
            if label in _GATE_MATRIX_LABEL_TO_NAME and cells[profile]
        }
        assert expected == set(config["profiles"][profile]), profile


def _load_mutation_check_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mutation_check_under_test", checks.REPO_ROOT / "devtools" / "mutation_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v15_gate_05_select_matches_exactly_the_four_v15_entries():
    mc = _load_mutation_check_module()
    selected = [m["id"] for m in mc.MUTATIONS if m["id"].startswith("v15-")]
    assert selected == [
        "v15-severity-comparison-inverted",
        "v15-fail-closed-becomes-fail-open",
        "v15-shadow-flag-ignored",
        "v15-diff-scope-filter-dropped",
    ]


def test_v15_gate_05_select_unmatched_prefix_fails_loud():
    result = subprocess.run(
        [sys.executable, "devtools/mutation_check.py", "--select", "nope-"],
        cwd=checks.REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "nope-" in result.stderr


def test_v15_gate_05_select_and_only_are_mutually_exclusive():
    result = subprocess.run(
        [
            sys.executable,
            "devtools/mutation_check.py",
            "--only",
            "v15-severity-comparison-inverted",
            "--select",
            "v15-",
        ],
        cwd=checks.REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "mutually exclusive" in result.stderr


def test_v15_gate_execute_command_gate_normalises_against_tracked_tree(tmp_path: Path):
    """A gate whose argv references {tracked_tree} (gitleaks-tree in the real
    config) reports finding paths relative to that materialised copy, not
    repo_root -- normalisation must use whichever root the gate actually
    scanned. Caught live: a real `checks.py run --profile pre-push` against
    this repository crashed gitleaks-tree with "path could not be
    normalised" before this fix."""
    repo = _init_repo(tmp_path)
    (repo / "secret.py").write_text("x = 1\n")
    _commit_all(repo, "c1")

    tree_dir = tmp_path / "materialized"
    tree_dir.mkdir()
    checks.materialize_tracked_tree(checks.list_tree_entries("HEAD", repo), tree_dir, repo)

    script = (
        "import json, sys\n"
        "finding = dict(File=sys.argv[2] + '/secret.py', RuleID='stub')\n"
        "json.dump([finding], open(sys.argv[1], 'w'))\n"
        "sys.exit(1)\n"
    )
    gate = {
        "kind": "command",
        "result_mode": "findings",
        "argv": [sys.executable, "-c", script, "{artefact}", "{tracked_tree}"],
        "placeholders": {},
        "output_format": "json",
        "parser": "gitleaks_json",
        "success_exit_codes": [0],
        "findings_exit_codes": [1],
        "artefact": ".bench/checks/{profile}/stub.json",
        "blocking": True,
        "diff_scoped": False,
        "severity": sorted(_ALL_SEVERITIES),
        "timeout_seconds": 10,
    }

    result = checks.execute_command_gate(
        "stub",
        gate,
        repo_root=repo,
        profile="full",
        scope_files=None,
        tracked_tree=tree_dir,
        known_severities=set(_ALL_SEVERITIES),
    )

    assert result.ran
    assert result.blocked
    assert [f["path"] for f in result.findings_in_scope] == ["secret.py"]
