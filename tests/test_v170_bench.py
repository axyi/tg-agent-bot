"""spec-v1.7.0: devtools/bench.py's comparability rule and meta.reasoning
(BEN-01…-06), the --tag sanitiser (CAR-01), the version invariant (VER-01),
the lint-docs repoint (RPT-02) and the post-measurement selection-commit
freeze machinery (ACC-03).

Offline and deterministic (REQ-V170-TST-01): no network, no Docker, no
`.env`, no live LLM.

REQ-V170-TREE-01 splits this release's tests three ways by requirement
group; `tests/test_v170_reasoning.py` (RSN-*, POL-*, OBS-*) and
`tests/test_v170_summary_budget.py` (SUM-*) hold the other two.
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import dotenv
import pytest

import bot as bot_module
from config import load_config
from devtools import bench
from tests.test_config import base_env

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_REAL_BASELINE_PATH = (
    _REAL_PROJECT_ROOT / "docs" / "assets" / "bench" / "baseline-v1.6.0.json"
)
_ACC03_ALLOWED_SELECTION_FILES = frozenset(
    {"config.py", "pyproject.toml", ".env.example", "README.md", "AGENTS.md"}
)


def _load_real_baseline() -> dict:
    with open(_REAL_BASELINE_PATH) as f:
        return json.load(f)


def _candidate_from_real_baseline(baseline: dict, *, scale: float = 1.0,
                                   fix_failures: bool = True, tag: str = "cand-test") -> dict:
    """A copy of the real, committed baseline: `meta.reasoning` and the two
    new `llm_calls` fields added (T-V170-BEN-01's "candidate-shaped
    document"); costs/tokens optionally scaled and failing repeats optionally
    fixed, entirely through the real `totals_from_rows`/`summarize` so the
    result stays internally consistent for `check_document`."""
    candidate = json.loads(json.dumps(baseline))  # a plain, dict-only deep copy
    candidate["meta"]["tag"] = tag
    candidate["meta"]["git_commit"] = "b" * 40
    candidate["meta"]["reasoning"] = {
        "policy": "by-purpose", "on_purposes": ["tool-round"],
        "mechanism": {"tool-round": None, "final": None, "summary": "c:assistant-prefill"},
        "provider_form": "lmstudio",
    }
    for run in candidate["runs"]:
        if fix_failures:
            run["success"] = True
            run["failure"] = None
            for check in run.get("checks", []):
                check["ok"] = True
                check["detail"] = "ok"
        for call in run["llm_calls"]:
            call["reasoning_requested"] = "default"
            call["reasoning_honored"] = None
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                if call.get(key) is not None:
                    call[key] = int(call[key] * scale)
            if call.get("cost_usd") is not None:
                call["cost_usd"] = call["cost_usd"] * scale
        run["totals"] = bench.totals_from_rows(
            run["llm_calls"], run["tool_calls"], run["totals"]["wall_ms"]
        )
    candidate["summary"] = bench.summarize(
        candidate["runs"], candidate["meta"]["skipped_scenarios"], candidate["meta"]["repeats"]
    )
    return candidate


# --------------------------------------------------------------------------
# T-V170-BEN-01…-06, N6 -- devtools/bench.py
# --------------------------------------------------------------------------


def test_t_v170_ben_01_meta_reasoning_shape_and_additive_optionality():
    real_baseline = _load_real_baseline()
    # The real, committed baseline carries neither field -- frozen, never
    # back-filled (REQ-V170-NG-03).
    assert "reasoning" not in real_baseline["meta"]
    for run in real_baseline["runs"]:
        for call in run["llm_calls"]:
            assert "reasoning_requested" not in call
            assert "reasoning_honored" not in call
    # bench.py check still exits 0 on it after LLM_CALL_COLUMNS widened.
    code, reason = bench.check_document(real_baseline, mode="strict")
    assert (code, reason) == (0, "valid")
    assert "reasoning" not in bench.LOCKED_META_FIELDS

    # A candidate-shaped document carrying both also passes check.
    candidate = _candidate_from_real_baseline(real_baseline)
    code, reason = bench.check_document(candidate, mode="strict")
    assert (code, reason) == (0, "valid")

    for policy in ("model-default", "off", "by-purpose"):
        cfg_stub = type("Cfg", (), {
            "llm_reasoning_policy": policy,
            "llm_reasoning_on_purposes": frozenset({"final", "tool-round"}),
        })()
        meta = bench.reasoning_meta(cfg_stub, "lmstudio")
        assert meta["policy"] == policy  # present on every run, model-default included
        assert meta["on_purposes"] == ["final", "tool-round"]  # sorted
        assert meta["mechanism"]["tool-round"] is None  # no off-mechanism -> null
        assert meta["mechanism"]["summary"] is not None


def test_t_v170_ben_02_comparability_against_the_real_baseline():
    real_baseline = _load_real_baseline()
    # The baseline compares clean with itself -- previously impossible
    # (measured refusal: "env_flags.HISTORY_TOOL_STUB must be null on the
    # baseline side"), which is why REQ-V170-BEN-02 exists at all.
    assert bench.comparability(real_baseline, real_baseline) is None

    # A treatment-only pair (only env_flags.LLM_REASONING_POLICY/_ON_PURPOSES
    # and git_commit differ) compares clean too.
    treated = _candidate_from_real_baseline(real_baseline)
    treated["meta"]["env_flags"]["LLM_REASONING_POLICY"] = "off"
    treated["meta"]["env_flags"]["LLM_REASONING_ON_PURPOSES"] = ""
    assert bench.comparability(real_baseline, treated) is None

    generation_changed = _candidate_from_real_baseline(real_baseline)
    generation_changed["meta"]["generation_settings"] = dict(
        generation_changed["meta"]["generation_settings"], agent={"temperature": 1}
    )
    reason = bench.comparability(real_baseline, generation_changed)
    assert reason is not None and "locked meta field differs" in reason

    stub_changed = _candidate_from_real_baseline(real_baseline)
    stub_changed["meta"]["env_flags"]["HISTORY_TOOL_STUB"] = "off"
    assert bench.comparability(real_baseline, stub_changed) == (
        "env_flags.HISTORY_TOOL_STUB differs"
    )

    failover_changed = _candidate_from_real_baseline(real_baseline)
    failover_changed["meta"]["env_flags"]["LLM_FAILOVER"] = "auto"
    reason = bench.comparability(real_baseline, failover_changed)
    assert reason is not None and "LLM_FAILOVER" in reason

    routed = _candidate_from_real_baseline(real_baseline)
    routed["meta"]["env_flags"]["LLM_SUMMARY_MODEL"] = "openrouter:cheap/model"
    reason = bench.comparability(real_baseline, routed)
    assert reason is not None and "LLM_SUMMARY_MODEL" in reason


def test_t_v170_ben_03_config_sha256_excludes_only_the_treatment():
    base = load_config(env=base_env(), load_env_file=False)
    treated = dataclasses.replace(
        base, llm_reasoning_policy="off", llm_reasoning_on_purposes=frozenset()
    )
    assert bench.config_sha256(base) == bench.config_sha256(treated)

    non_excluded_changed = dataclasses.replace(base, llm_max_tokens=base.llm_max_tokens + 1)
    assert bench.config_sha256(base) != bench.config_sha256(non_excluded_changed)


def test_t_v170_ben_04_and_ben_06_gate_verdicts_against_the_real_baseline(tmp_path):
    real_baseline = _load_real_baseline()
    base_path = tmp_path / "baseline.json"
    base_path.write_text(json.dumps(real_baseline), encoding="utf-8")

    def _report(candidate: dict) -> int:
        cand_path = tmp_path / "candidate.json"
        cand_path.write_text(json.dumps(candidate), encoding="utf-8")
        return bench.main([
            "report", "--baseline", str(base_path), "--candidate", str(cand_path),
            "--gate", "--out", str(tmp_path / "report.md"),
        ])

    both_pass = _candidate_from_real_baseline(real_baseline, scale=0.5, fix_failures=True)
    assert _report(both_pass) == 0

    cost_fails = _candidate_from_real_baseline(real_baseline, scale=1.0, fix_failures=True)
    assert _report(cost_fails) == 1

    s18_stays_2_of_3 = _candidate_from_real_baseline(real_baseline, scale=0.5, fix_failures=False)
    assert s18_stays_2_of_3["summary"]["per_scenario"]["S18"] == {
        **s18_stays_2_of_3["summary"]["per_scenario"]["S18"], "success": 2, "of": 3,
    }
    v = bench.verdict(real_baseline, s18_stays_2_of_3)
    assert v.passed is False
    assert any("S18 2/3" in line for line in v.lines)
    # item 2 (two-repeat-loss) does NOT catch a 2-of-3 alone -- prove the new
    # rule is the one doing the work, not the old one.
    assert not any("regressed scenarios" in line and "S18" in line for line in v.lines)
    assert _report(s18_stays_2_of_3) == 1

    two_repeat_loss = _candidate_from_real_baseline(real_baseline, scale=0.5, fix_failures=True)
    s01_runs = [r for r in two_repeat_loss["runs"] if r["scenario"] == "S01"]
    for run in s01_runs[:2]:
        run["success"] = False
        run["failure"] = "checks"
    two_repeat_loss["summary"] = bench.summarize(
        two_repeat_loss["runs"], two_repeat_loss["meta"]["skipped_scenarios"],
        two_repeat_loss["meta"]["repeats"],
    )
    assert _report(two_repeat_loss) == 1

    timeout_trap = _candidate_from_real_baseline(real_baseline, scale=0.5, fix_failures=True)
    timeout_trap["meta"]["timeout_s"] = 600.0
    assert _report(timeout_trap) == 2


def test_n6_aborted_candidate_refused_before_per_scenario():
    real_baseline = _load_real_baseline()
    candidate = _candidate_from_real_baseline(real_baseline, scale=0.5, fix_failures=True)
    candidate["meta"]["aborted"] = "timeout:S05-2"
    code, reason = bench.check_document(candidate, mode="strict")
    assert code == bench.EXIT_NOT_COMPARABLE
    assert "aborted" in reason
    v = bench.verdict(real_baseline, candidate)
    assert v.passed is False


def test_t_v170_ben_05_gate_required_full_scenarios_shape():
    assert bench.GATE_REQUIRED_FULL_SCENARIOS == ("S13", "S14", "S15", "S16", "S17", "S18")
    from llm.base import REQUEST_DEFAULTS
    assert "GATE_REQUIRED_FULL_SCENARIOS" not in bench.constants()
    assert "GATE_REQUIRED_FULL_SCENARIOS" not in REQUEST_DEFAULTS
    real_baseline = _load_real_baseline()
    assert bench.scenarios_sha256() == real_baseline["meta"]["scenarios_sha256"]


# --------------------------------------------------------------------------
# T-V170-CAR-01, N7 -- the --tag sanitiser
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tag", [
    "baseline-v1.6.0", "cand-v170-off", "a", "a" * 64,
])
def test_t_v170_car_01_tag_accepts(tag):
    assert bench._TAG_RE.match(tag) is not None
    assert tag not in (".", "..")


@pytest.mark.parametrize("tag", [
    "..", ".", "a/b", "../x", "a\\b", "", "a" * 65, "a b",
])
def test_t_v170_car_01_tag_rejects(tag):
    assert tag in (".", "..") or bench._TAG_RE.match(tag) is None


def test_n7_tag_escape_refused_before_any_filesystem_write(monkeypatch, capsys):
    def _forbidden(*args, **kwargs):
        raise AssertionError("shutil.rmtree must not be called")

    monkeypatch.setattr(shutil, "rmtree", _forbidden)
    code = bench.main(["run", "--tag", "../escape"])
    assert code == bench.EXIT_ERROR
    err = capsys.readouterr().err
    assert "--tag" in err and "[A-Za-z0-9._-]" in err


# --------------------------------------------------------------------------
# T-V170-VER-01, T-V170-RPT-02, T-V170-ACC-03 -- written at T8, before the
# candidate freeze (REQ-V170-ACC-03), because no test may change after it.
# `_REAL_PROJECT_ROOT` (not `config.PROJECT_ROOT`, which the autouse
# `isolated_project_root` fixture patches to a `tmp_path`) is required for
# every one of these: they inspect the real committed tree, never a fixture.
# --------------------------------------------------------------------------


def test_t_v170_ver_01_version_matches_independent_tomllib_read(capsys):
    with open(_REAL_PROJECT_ROOT / "pyproject.toml", "rb") as handle:
        expected = tomllib.load(handle)["project"]["version"]
    assert bot_module.main(["--version"]) == 0
    assert capsys.readouterr().out == f"tg-agent-bot {expected}\n"


def test_t_v180_rpt_01_lint_docs_repointed_to_this_release():
    """Superseded by spec-v1.8.0 REQ-V180-RPT-01, T7: lint-docs' report_path
    tracks the current release and is repointed again at each one -- this
    test's own name and assertion move with it (erratum, this run, operator-
    authorized: the v1.7.0-named predecessor asserted the v1.7.0 path, which
    v1.8.0's own required repoint necessarily made false)."""
    from devtools.checks import DEFAULT_CONFIG_PATH, load_gate_config

    raw = load_gate_config(DEFAULT_CONFIG_PATH)
    lint_docs = raw["gates"]["lint-docs"]
    assert lint_docs["report_path"] == "docs/reports/report-v1.8.0.md"
    assert lint_docs["ledger_header"] == (
        "| Project | Ver | Date | Spec (tokens) | Prompts | First run | Bugs | "
        "Tokens ↑/↓ | Cost | Model | Harness |"
    )


def _acc03_cand_v170_documents(root: Path = _REAL_PROJECT_ROOT) -> list[tuple[str, dict]]:
    """(tag, doc) for every committed `cand-v170-*.json`, sorted by tag so the
    result is deterministic; empty before T11/T12 land any."""
    bench_dir = root / "docs" / "assets" / "bench"
    docs = []
    for path in sorted(bench_dir.glob("cand-v170-*.json")):
        with open(path, encoding="utf-8") as handle:
            docs.append((path.stem, json.load(handle)))
    return docs


def _acc03_find_matching_candidates(
    cand_docs: list[tuple[str, dict]], resolved: tuple[str, list[str]]
) -> list[str]:
    """Tags of every candidate whose `meta.reasoning` (policy,
    sorted(on_purposes)) equals `resolved`; REQ-V170-ACC-03 needs this list to
    hold exactly one entry, never a policy literal of its own."""
    return [
        tag
        for tag, doc in cand_docs
        if (doc["meta"]["reasoning"]["policy"], sorted(doc["meta"]["reasoning"]["on_purposes"]))
        == resolved
    ]


def _acc03_env_example_reasoning_defaults(root: Path = _REAL_PROJECT_ROOT) -> tuple[str, list[str]]:
    """The pair `.env.example`'s active lines document, parsed the same way
    `load_dotenv` would parse `.env` itself -- never a hand-rolled reader."""
    values = dotenv.dotenv_values(root / ".env.example")
    policy = values.get("LLM_REASONING_POLICY") or "model-default"
    raw_purposes = values.get("LLM_REASONING_ON_PURPOSES")
    purposes = (
        ["tool-round"]
        if raw_purposes is None
        else sorted(item.strip() for item in raw_purposes.split(",") if item.strip())
    )
    return policy, purposes


def _acc03_final_tree_reasoning_pair() -> tuple[str, list[str]]:
    """`load_config()` with no `LLM_REASONING_*` in the process environment and
    without the deployment `.env` (REQ-V170-ACC-03's own precondition)."""
    cfg = load_config(env=base_env(), load_env_file=False)
    return cfg.llm_reasoning_policy, sorted(cfg.llm_reasoning_on_purposes)


def test_t_v170_acc_03_find_matching_candidates_synthetic():
    docs = [
        ("cand-v170-off", {"meta": {"reasoning": {"policy": "off", "on_purposes": []}}}),
        (
            "cand-v170-by-purpose",
            {"meta": {"reasoning": {"policy": "by-purpose", "on_purposes": ["summary"]}}},
        ),
    ]
    assert _acc03_find_matching_candidates(docs, ("off", [])) == ["cand-v170-off"]
    assert _acc03_find_matching_candidates(docs, ("model-default", ["tool-round"])) == []
    extra = {"meta": {"reasoning": {"policy": "off", "on_purposes": []}}}
    dup = docs + [("cand-v170-off-2", extra)]
    assert _acc03_find_matching_candidates(dup, ("off", [])) == ["cand-v170-off", "cand-v170-off-2"]


def test_t_v170_acc_03_cand_v170_documents_reads_the_committed_shape(tmp_path):
    bench_dir = tmp_path / "docs" / "assets" / "bench"
    bench_dir.mkdir(parents=True)
    (bench_dir / "cand-v170-off.json").write_text(
        json.dumps({"meta": {"reasoning": {"policy": "off", "on_purposes": []}}}), encoding="utf-8"
    )
    (bench_dir / "cand-v170-by-purpose.json").write_text(
        json.dumps({"meta": {"reasoning": {"policy": "by-purpose", "on_purposes": ["summary"]}}}),
        encoding="utf-8",
    )
    (bench_dir / "baseline-v1.6.0.json").write_text("{}", encoding="utf-8")
    docs = _acc03_cand_v170_documents(root=tmp_path)
    assert {tag for tag, _ in docs} == {"cand-v170-off", "cand-v170-by-purpose"}


def test_t_v170_acc_03_equivalence_half():
    cand_docs = _acc03_cand_v170_documents()
    if not cand_docs:
        pytest.skip("no cand-v170-*.json candidate document committed yet (pre-T11/T12)")
    resolved = _acc03_final_tree_reasoning_pair()
    matches = _acc03_find_matching_candidates(cand_docs, resolved)
    assert len(matches) == 1, f"expected exactly one matching candidate, found {matches}"
    assert resolved == _acc03_env_example_reasoning_defaults()


def test_t_v170_acc_03_version_half():
    with open(_REAL_PROJECT_ROOT / "pyproject.toml", "rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    cand_docs = _acc03_cand_v170_documents()
    resolved = _acc03_final_tree_reasoning_pair()
    has_match = len(_acc03_find_matching_candidates(cand_docs, resolved)) == 1
    assert version == ("1.7.0" if has_match else "1.6.0")


def _acc03_run_git_readonly(args: list[str], root: Path) -> subprocess.CompletedProcess:
    """Read-only against `root` -- `devtools/checks.py:677`'s plain
    `subprocess.run` precedent; no `GIT_*` scrubbing needed, unlike
    `tests/test_v15_standards.py`'s fixtures, which *write* into a throwaway
    repo and must guard against a leaked `GIT_DIR`."""
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )


_ACC03_T12_PROMPT_RE = re.compile(r"docs/prompts/\d+-v170-t12-[\w.-]*\.md")


def _acc03_find_selection_commit(root: Path = _REAL_PROJECT_ROOT) -> str | None:
    """REQ-V170-REV-01 item 8: the single commit whose body cites T12's
    prompt file. `None` (a recorded skip, never a hard failure) when zero or
    more than one commit matches."""
    result = _acc03_run_git_readonly(["log", "--format=%H%x00%B%x03"], root)
    if result.returncode != 0:
        return None
    matches = []
    for chunk in result.stdout.split("\x03"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        sha, _, body = chunk.partition("\x00")
        if _ACC03_T12_PROMPT_RE.search(body):
            matches.append(sha)
    return matches[0] if len(matches) == 1 else None


def _acc03_selection_commit_diff(sha: str, root: Path = _REAL_PROJECT_ROOT) -> dict[str, list[str]]:
    """path -> the hunk body's **added** lines only (the `+++` file header
    excluded, the leading `+` stripped) for `git diff <sha>^..<sha>`. Removed
    lines are deliberately not returned: REQ-V170-REV-01 item 8 structurally
    proves what T12 *added* is on-topic, and a removed line's pre-existing
    text (written long before T12, under no obligation to anticipate this
    check) cannot retroactively satisfy a naming requirement -- discovered
    empirically while landing T12 itself, when `config.py`'s pre-existing
    wrapped `_parse_choice` call had no line pairing the lowercase identifier
    with its default value, so changing that default always "removed" a
    non-conforming line no matter how the replacement was worded."""
    names = _acc03_run_git_readonly(["diff", "--name-only", f"{sha}^", sha], root)
    per_file: dict[str, list[str]] = {}
    for path in (line for line in names.stdout.splitlines() if line):
        diff = _acc03_run_git_readonly(["diff", f"{sha}^", sha, "--", path], root)
        per_file[path] = [
            line[1:]
            for line in diff.stdout.splitlines()
            if line[:1] == "+" and not line.startswith("+++")
        ]
    return per_file


def _acc03_validate_selection_commit_hunks(per_file: dict[str, list[str]]) -> list[str]:
    """Structural check of REQ-V170-REV-01 item 8: every **added** line in
    `config.py` names one of the two variables, `pyproject.toml`'s added
    lines touch only its `version` line, and the three documentation files'
    added lines touch only lines naming a variable or a version string.
    Scoped to additions only (`_acc03_selection_commit_diff` already drops
    removed lines) -- a removed line's pre-existing text cannot be held to a
    naming requirement it predates. Returns the list of problems found --
    empty means clean. Names no policy or version literal of its own."""
    version_re = re.compile(r"\d+\.\d+\.\d+")
    problems = []
    for path, lines in per_file.items():
        if path not in _ACC03_ALLOWED_SELECTION_FILES:
            problems.append(f"disallowed path in the selection commit: {path}")
            continue
        if path == "config.py":
            for line in lines:
                if "llm_reasoning_policy" not in line and "llm_reasoning_on_purposes" not in line:
                    problems.append(f"config.py hunk names neither variable: {line!r}")
        elif path == "pyproject.toml":
            for line in lines:
                if "version" not in line:
                    problems.append(f"pyproject.toml hunk outside the version line: {line!r}")
        else:  # .env.example, README.md, AGENTS.md
            for line in lines:
                names_variable = (
                    "LLM_REASONING_POLICY" in line or "LLM_REASONING_ON_PURPOSES" in line
                )
                if not names_variable and not version_re.search(line):
                    problems.append(
                        f"{path} hunk names neither variable nor a version string: {line!r}"
                    )
    return problems


def test_t_v170_acc_03_selection_commit_locator_and_hunks_synthetic(tmp_path):
    from tests.test_v15_standards import _git

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-q"], repo)
    _git(["config", "user.email", "test@example.invalid"], repo)
    _git(["config", "user.name", "Test"], repo)
    seed = {
        "config.py": "llm_reasoning_policy = 'model-default'\n",
        "pyproject.toml": '[project]\nversion = "1.6.0"\n',
        ".env.example": "LLM_REASONING_POLICY=model-default\n",
        "README.md": "LLM_REASONING_POLICY docs\n",
        "AGENTS.md": "LLM_REASONING_POLICY docs\n",
        "unrelated.py": "x = 1\n",
    }
    for name, content in seed.items():
        (repo / name).write_text(content, encoding="utf-8")
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "seed"], repo)

    clean = {
        "config.py": "llm_reasoning_policy = 'off'\n",
        "pyproject.toml": '[project]\nversion = "1.7.0"\n',
        ".env.example": "LLM_REASONING_POLICY=off\n",
        "README.md": "LLM_REASONING_POLICY=off now\n",
        "AGENTS.md": "LLM_REASONING_POLICY=off now\n",
    }
    for name, content in clean.items():
        (repo / name).write_text(content, encoding="utf-8")
    _git(["add", "-A"], repo)
    _git(
        ["commit", "-q", "-m",
         "feat: selection\n\n(prompt: docs/prompts/999-v170-t12-selection.md)"],
        repo,
    )

    sha = _acc03_find_selection_commit(root=repo)
    assert sha is not None
    per_file = _acc03_selection_commit_diff(sha, root=repo)
    assert set(per_file) == _ACC03_ALLOWED_SELECTION_FILES
    assert _acc03_validate_selection_commit_hunks(per_file) == []

    # a second commit citing the same T12 prompt makes the locator ambiguous
    (repo / "unrelated.py").write_text("x = 2\n", encoding="utf-8")
    (repo / "config.py").write_text("llm_reasoning_policy = 'by-purpose'\n", encoding="utf-8")
    _git(["add", "-A"], repo)
    _git(
        ["commit", "-q", "-m", "feat: bad\n\n(prompt: docs/prompts/999-v170-t12-selection.md)"],
        repo,
    )
    assert _acc03_find_selection_commit(root=repo) is None


def test_t_v170_acc_03_selection_commit_hunk_validator_rejects_a_sixth_path():
    per_file = {
        "config.py": ["    llm_reasoning_policy = 'off'"],
        "pyproject.toml": ['version = "1.7.0"'],
        "unrelated.py": ["x = 2"],
    }
    problems = _acc03_validate_selection_commit_hunks(per_file)
    assert any("unrelated.py" in problem for problem in problems)


def test_t_v170_acc_03_selection_commit_hunk_validator_rejects_an_off_topic_line():
    per_file = {"README.md": ["some unrelated documentation change"]}
    problems = _acc03_validate_selection_commit_hunks(per_file)
    assert len(problems) == 1 and "README.md" in problems[0]


def test_t_v170_acc_03_selection_commit_allowlist_half():
    sha = _acc03_find_selection_commit()
    if sha is None:
        pytest.skip("no T12 selection commit exists yet (pre-T12)")
    per_file = _acc03_selection_commit_diff(sha)
    disallowed = set(per_file) - _ACC03_ALLOWED_SELECTION_FILES
    assert not disallowed, f"selection commit touched disallowed paths: {sorted(disallowed)}"
    problems = _acc03_validate_selection_commit_hunks(per_file)
    assert problems == [], problems
