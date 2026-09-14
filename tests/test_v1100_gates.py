"""spec-v1.10.0 T6 (docs/spec/spec-v1.10.0.md sec.13-14, REQ-V1100-GATE-03,
REQ-V1100-EVAL-01, REQ-V1100-RPT-01): gate 8 (`agent-eval`) registered in
`config/quality_gates.yaml`, the eight-gate documentation blocks in
`AGENTS.md`/`README.md`, and the runner's own sizing arithmetic
(`worst_case_calls`/`gate8_timeout_seconds`, T5's, re-pinned here against
the spec's worked examples). Entirely offline: no network, no live LLM, no
Docker -- this module only reads the repository's own committed files and
imports `devtools.agent_eval`/`devtools.checks`/`agent` for their pure
constants and functions.

`T-V1100-EVAL-01`, `T-V1100-EVAL-02`, `T-V1100-EVAL-03`.
"""

from __future__ import annotations

import math
from pathlib import Path

import agent
import devtools.agent_eval as ae
import devtools.mutation_check as mc
from devtools.checks import DEFAULT_CONFIG_PATH, load_gate_config

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"
README_MD = REPO_ROOT / "README.md"

_EXPECTED_AGENT_EVAL_GATE = {
    "kind": "command",
    "result_mode": "exit_status",
    "argv": ["uv", "run", "--locked", "python", "devtools/agent_eval.py"],
    "placeholders": {},
    "success_exit_codes": [0],
    "blocking": True,
    "diff_scoped": False,
    "timeout_seconds": 8200,
}

_EIGHT_GATE_BLOCK = [
    "uv sync --locked",
    "uv run --locked ruff check .",
    "uv run --locked pytest",
    "uv run --locked python bot.py --selftest",
    "uv run --locked python bot.py --selftest-live",
    "uv run --locked python devtools/mutation_check.py",
    "uv run --locked python devtools/rag_eval.py",
    "uv run --locked python devtools/agent_eval.py",
]


# ---------------------------------------------------------------------------
# T-V1100-EVAL-01: the `agent-eval` gate entry and `GATE8_DEPENDENCIES`
# ---------------------------------------------------------------------------


def _raw_config() -> dict:
    return load_gate_config(DEFAULT_CONFIG_PATH)


def test_agent_eval_gate_has_exactly_the_expected_key_set_and_values():
    config = _raw_config()
    gate = config["gates"]["agent-eval"]
    assert gate == _EXPECTED_AGENT_EVAL_GATE
    assert "--select" not in gate["argv"]


def test_agent_eval_gate_is_in_full_profile_and_no_other():
    config = _raw_config()
    for profile_name, members in config["profiles"].items():
        if profile_name == "full":
            assert "agent-eval" in members
        else:
            assert "agent-eval" not in members


def test_mutation_v1100_gate_registered_with_the_v190_shape():
    # spec-v1.10.0 sec.13 (REQ-V1100-GATE-02, ~:1178-1184): T7 registers
    # `mutation-v1100` with the exact key set and order of `mutation-v190`
    # (config/quality_gates.yaml), only the `--select` prefix and
    # `timeout_seconds` differing.
    config = _raw_config()
    gate = config["gates"]["mutation-v1100"]
    assert gate == {
        "kind": "command",
        "result_mode": "exit_status",
        "argv": [
            "uv",
            "run",
            "--locked",
            "python",
            "devtools/mutation_check.py",
            "--select",
            "v1100-",
        ],
        "placeholders": {},
        "success_exit_codes": [0],
        "blocking": True,
        "diff_scoped": False,
        "timeout_seconds": gate["timeout_seconds"],
    }
    assert gate["timeout_seconds"] > 0


def test_mutation_v1100_is_in_mutation_subsets_and_no_hook_profile():
    # `mutation-subsets` is the inert bookkeeping profile that satisfies
    # `_validate_profiles`'s "every gate must be named by some profile"
    # invariant (devtools/checks.py:540-552) now that no hook profile
    # references the per-range mutation-v* gates directly.
    config = _raw_config()
    assert "mutation-v1100" in config["profiles"]["mutation-subsets"]
    for profile_name, members in config["profiles"].items():
        if profile_name != "mutation-subsets":
            assert "mutation-v1100" not in members


def test_agent_eval_timeout_is_a_multiple_of_100_and_at_least_1800():
    config = _raw_config()
    timeout = config["gates"]["agent-eval"]["timeout_seconds"]
    assert timeout >= 1800
    assert timeout % 100 == 0


def test_gate8_dependencies_matches_the_root_py_glob_plus_the_fixed_set():
    expected_root_py = {str(p.relative_to(REPO_ROOT)) for p in REPO_ROOT.glob("*.py")}
    expected = expected_root_py | {
        "llm/",
        "devtools/agent_eval.py",
        "evals/agent/",
        "config/quality_gates.yaml",
        "pyproject.toml",
        "uv.lock",
    }
    assert set(ae.GATE8_DEPENDENCIES) == expected


def test_every_gate8_dependency_exists_in_the_repo():
    for entry in ae.GATE8_DEPENDENCIES:
        assert (REPO_ROOT / entry).exists(), f"missing GATE8_DEPENDENCIES entry: {entry!r}"


def test_print_dependencies_prints_exactly_the_dependencies_and_returns_0(monkeypatch, capsys):
    def _forbidden_load_config():
        raise AssertionError("load_config must not be called with --print-dependencies")

    def _forbidden_run_agent_outcome(*args, **kwargs):
        raise AssertionError("run_agent_outcome must not be called with --print-dependencies")

    monkeypatch.setattr(ae, "load_config", _forbidden_load_config)
    monkeypatch.setattr(agent, "run_agent_outcome", _forbidden_run_agent_outcome)

    exit_code = ae.main(["--print-dependencies"])

    assert exit_code == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed == list(ae.GATE8_DEPENDENCIES)


# ---------------------------------------------------------------------------
# T-V1100-EVAL-02: the eight-gate documentation blocks
# ---------------------------------------------------------------------------


def _fenced_bash_block_after(text: str, anchor: str) -> list[str]:
    start = text.index(anchor)
    fence_start = text.index("```bash", start)
    body_start = text.index("\n", fence_start) + 1
    fence_end = text.index("```", body_start)
    return text[body_start:fence_end].splitlines()


def test_agents_md_gate_block_is_the_eight_gate_block_verbatim():
    text = AGENTS_MD.read_text(encoding="utf-8")
    block = _fenced_bash_block_after(text, "## Gates — run before reporting success")
    assert block == _EIGHT_GATE_BLOCK


def test_readme_tests_gate_block_is_the_eight_gate_block_verbatim():
    text = README_MD.read_text(encoding="utf-8")
    block = _fenced_bash_block_after(text, "## Tests")
    assert block == _EIGHT_GATE_BLOCK


def test_readme_has_the_agent_evaluation_gate_8_heading():
    text = README_MD.read_text(encoding="utf-8")
    assert "## Agent evaluation (gate 8)" in text


# ---------------------------------------------------------------------------
# T-V1100-EVAL-03: worst_case_calls / gate8_timeout_seconds worked examples
# ---------------------------------------------------------------------------


def test_worst_case_calls_formula_for_several_rounds_limits():
    for rounds_limit in (1, 8, 9):
        assert ae.worst_case_calls(rounds_limit) == 23 * rounds_limit + 12


def test_worst_case_calls_at_the_real_http_attempt_limit_is_219():
    assert ae.worst_case_calls(agent.HTTP_ATTEMPT_LIMIT) == 219


def test_gate8_timeout_seconds_worked_examples():
    assert ae.gate8_timeout_seconds(219, 1.0) == 1800
    assert ae.gate8_timeout_seconds(35, 10.0) == 1800
    assert ae.gate8_timeout_seconds(219, 10.0) == 3300
    assert ae.gate8_timeout_seconds(219, 100.0) == 32900
    assert ae.gate8_timeout_seconds(219, 1000.0) == 328500


def test_gate8_timeout_seconds_always_a_multiple_of_100_and_at_least_the_raw_ceiling():
    for max_calls, t_turn in ((219, 1.0), (35, 10.0), (219, 10.0), (219, 100.0), (219, 1000.0)):
        timeout = ae.gate8_timeout_seconds(max_calls, t_turn)
        assert timeout % 100 == 0
        assert timeout >= math.ceil(1.5 * max_calls * t_turn)


# ---------------------------------------------------------------------------
# T-V1100-GATE-01: the seven v1100-* mutation table entries
# ---------------------------------------------------------------------------

_EXPECTED_MUTATION_KEYS = {"id", "path", "find", "replace", "why"}


def _v1100_mutations() -> list[dict]:
    return [m for m in mc.MUTATIONS if m["id"].startswith("v1100-")]


def test_exactly_seven_v1100_mutations_after_the_last_v195_entry():
    ids = [m["id"] for m in mc.MUTATIONS]
    last_v195_index = max(i for i, mid in enumerate(ids) if mid.startswith("v195-"))
    tail = ids[last_v195_index + 1 :]
    assert tail == [
        "v1100-injection-checker-always-passes",
        "v1100-hallucination-any-of-vacuous",
        "v1100-memory-structural-check-dropped",
        "v1100-judge-floor-zeroed",
        "v1100-judge-guard-dropped",
        "v1100-reply-parts-split-before-redact",
        "v1100-inbound-cap-code-points",
    ]


def test_v1100_mutations_have_exactly_the_five_keys():
    for mutation in _v1100_mutations():
        assert set(mutation) == _EXPECTED_MUTATION_KEYS


def test_v1100_mutation_paths_exist_in_the_repo():
    for mutation in _v1100_mutations():
        assert (REPO_ROOT / mutation["path"]).exists(), mutation["id"]


def test_v1100_mutation_find_strings_occur_exactly_once_in_their_file():
    for mutation in _v1100_mutations():
        text = (REPO_ROOT / mutation["path"]).read_text(encoding="utf-8")
        assert text.count(mutation["find"]) == 1, mutation["id"]
