"""spec-v1.10.3 T1 (docs/spec/spec-v1.10.3.md Sec.4 lines 309-383, Sec.7 rows
1-2, Sec.8 SEC-01; REQ-V1103-EXEC-01, REQ-V1103-EXEC-02, REQ-V1103-ERR-01
rows 1-2, REQ-V1103-SEC-01, REQ-V1103-NG-03, REQ-V1103-NG-04,
REQ-V1103-NG-14): the three `_validate_exec_arguments` deny rules --
`env`/`printenv` by basename, a `.env`-basename file anywhere in argv, and a
full-match `/proc/<pid-or-self>/environ` path -- checked only after every
existing shape check has already passed (T-V1103-EXEC-06's precedence
cases), and deliberately narrow: the documented bypass shapes
(T-V1103-EXEC-04) are proven to keep running unrefused, on purpose. No
shell parsing, allow-list, symlink resolution or path normalisation is
added here (NG-03, NG-04); the `exec` tool description is untouched
(NG-14, T-V1103-EXEC-08).

Entirely offline: `tests/fakes.RecordingRunner` never starts a real
process, `tests.test_v1100_runner._cfg`/`_conn` build the same offline
fixtures `devtools/agent_eval.py`'s own tests use, and T-V1103-EXEC-07
additionally forbids a real `subprocess.Popen` call via `monkeypatch`.
"""

import json
import subprocess
from pathlib import Path

import pytest

import agent
import config
import devtools.agent_eval as ae
import storage
import tools
from llm.base import LLMResponse, ToolCall
from tests.fakes import FakeLLM, RecordingRunner
from tests.test_v1100_runner import _cfg, _conn

REPO_ROOT = Path(__file__).resolve().parent.parent
RED_TEAM = json.loads((REPO_ROOT / "evals" / "agent" / "red_team.json").read_text(encoding="utf-8"))
SYSTEM_PROMPT = agent.build_system_prompt({})


def _exec(payload, runner=None, audit=None):
    runner = runner if runner is not None else RecordingRunner()
    result = json.loads(
        tools.execute_tool("exec", json.dumps(payload), skills={}, runner=runner, audit=audit)
    )
    return result, runner


# --------------------------------------------------------------------------
# T-V1103-EXEC-01: rule 1 -- env/printenv by basename
# --------------------------------------------------------------------------


@pytest.mark.parametrize("argv", [["printenv"], ["env"], ["/usr/bin/env"], ["./printenv", "-0"]])
def test_t_v1103_exec_01_rule1_denies_env_programs(argv):
    result, runner = _exec({"argv": argv})
    assert result == {"error": tools.EXEC_ENV_REFUSAL_TEXT}
    assert runner.argv_calls == []


def test_t_v1103_exec_01_deny_programs_constant():
    assert frozenset({"env", "printenv"}) == tools.EXEC_DENY_PROGRAMS


# --------------------------------------------------------------------------
# T-V1103-EXEC-02: rule 2 -- a `.env`-basename file anywhere in argv
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["cat", ".env"],
        ["cat", "./.env"],
        ["ls", "-la", "/app/.env"],
        ["head", ".env.local"],
        ["cat", "/app/.env.production"],
    ],
)
def test_t_v1103_exec_02_rule2_denies_env_files(argv):
    result, runner = _exec({"argv": argv})
    assert result == {"error": tools.EXEC_ENV_REFUSAL_TEXT}
    assert runner.argv_calls == []


# --------------------------------------------------------------------------
# T-V1103-EXEC-03: rule 3 -- a full-match /proc/<pid-or-self>/environ path
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["cat", "/proc/self/environ"],
        ["cat", "/proc/1/environ"],
        ["xxd", "/proc/12345/environ"],
    ],
)
def test_t_v1103_exec_03_rule3_denies_procfs_environ(argv):
    result, runner = _exec({"argv": argv})
    assert result == {"error": tools.EXEC_ENV_REFUSAL_TEXT}
    assert runner.argv_calls == []


# --------------------------------------------------------------------------
# T-V1103-EXEC-04: near-misses AND the documented bypass shapes (NG-03,
# NG-04) both run unrefused, through the recording runner, argv unchanged
# --------------------------------------------------------------------------

NEAR_MISSES = [
    ["ls", "-la", ".envs"],
    ["cat", "env.txt"],
    ["printenv2"],
    ["envsubst"],
    ["cat", "/proc/cpuinfo"],
    ["cat", "/proc/self/status"],
    ["cat", "dotenv"],
    ["cat", "environment.yml"],
    ["cat", "/proc/self/environ/"],  # trailing slash breaks the full-match regex
]

# Deliberately still unrefused -- NG-03/NG-04 scope boundary, not a gap.
DOCUMENTED_BYPASS_SHAPES = [
    ["busybox", "printenv"],
    ["sh", "-c", "printenv"],
    ["python3", "-c", "import os;print(os.environ)"],
    ["cat", "/proc/self/../1/environ"],
    ["cat", "/x/.env/y"],
    ["ls", "/app/.env/"],  # trailing-slash basename is empty
    ["cat", ".еnv"],  # Cyrillic U+0435, not U+0065
    ["cat", "/workspace/env-link"],
]


@pytest.mark.parametrize("argv", NEAR_MISSES)
def test_t_v1103_exec_04_near_misses_run_unrefused(argv):
    result, runner = _exec({"argv": argv})
    assert "error" not in result
    assert runner.argv_calls == [argv]


@pytest.mark.parametrize("argv", DOCUMENTED_BYPASS_SHAPES)
def test_t_v1103_exec_04_documented_bypass_shapes_run_unrefused(argv):
    result, runner = _exec({"argv": argv})
    assert "error" not in result
    assert runner.argv_calls == [argv]


# --------------------------------------------------------------------------
# T-V1103-EXEC-05 / T-V1103-SEC-01: the refused audit record, through
# `execute_tool` with an `audit` list, including SEC-01's redaction
# --------------------------------------------------------------------------


def test_t_v1103_exec_05_refused_audit_record_exact_shape():
    records = []
    result, runner = _exec({"argv": ["printenv"]}, audit=records.append)
    assert result == {"error": tools.EXEC_ENV_REFUSAL_TEXT}
    assert records == [
        {
            "tool": "exec",
            "argv": ["printenv"],
            "outcome": "refused",
            "error": tools.EXEC_ENV_REFUSAL_TEXT,
        }
    ]
    assert runner.argv_calls == []


def test_t_v1103_exec_05_refused_audit_preserves_every_argv_element():
    records = []
    _exec({"argv": ["cat", "/app/.env"]}, audit=records.append)
    assert records[0]["argv"] == ["cat", "/app/.env"]


def test_t_v1103_sec_01_refused_audit_redacts_registered_secret():
    secret = "VALUE-abcdefgh12"
    config.register_secret(secret)
    records = []
    result, runner = _exec({"argv": ["printenv", secret]}, audit=records.append)
    assert result == {"error": tools.EXEC_ENV_REFUSAL_TEXT}
    assert records[0]["argv"] == ["printenv", config.REDACTION]
    assert runner.argv_calls == []
    serialized = json.dumps(records, ensure_ascii=False)
    assert secret not in serialized


# --------------------------------------------------------------------------
# T-V1103-EXEC-06: precedence -- shape checks run first and win
# --------------------------------------------------------------------------


def test_t_v1103_exec_06_nul_byte_shape_wins_over_rule1():
    result, runner = _exec({"argv": ["printenv", "\x00"]})
    assert result == {"error": "argv elements must not contain NUL bytes"}
    assert runner.argv_calls == []


def test_t_v1103_exec_06_element_count_shape_wins_over_rule1():
    result, runner = _exec({"argv": ["env", *(["x"] * 32)]})
    assert result == {"error": "argv must contain between 1 and 32 elements"}
    assert runner.argv_calls == []


def test_t_v1103_exec_06_blank_argv0_shape_wins():
    result, runner = _exec({"argv": ["  "]})
    assert result == {"error": "argv[0] must be a program name"}
    assert runner.argv_calls == []


def test_t_v1103_exec_06_joined_string_argv_shape_wins():
    result, runner = _exec({"argv": "printenv"})
    assert result == {"error": "argv must be an array of strings"}
    assert runner.argv_calls == []


# --------------------------------------------------------------------------
# ERR-01 rows 1-2 (offline, reusing EXEC-01/-05/-06's own cases)
# --------------------------------------------------------------------------


def test_t_v1103_err_01_row1_guard_hit_pinned_text_refused_record_no_runner():
    records = []
    result, runner = _exec({"argv": ["printenv"]}, audit=records.append)
    assert result == {"error": tools.EXEC_ENV_REFUSAL_TEXT}
    assert records[0]["outcome"] == "refused"
    assert runner.argv_calls == []


def test_t_v1103_err_01_row2_shape_defect_beats_a_guard_shaped_argv():
    # cross-reference: EXEC-06's NUL case is the same scenario.
    result, runner = _exec({"argv": ["printenv", "\x00"]})
    assert result == {"error": "argv elements must not contain NUL bytes"}
    assert runner.argv_calls == []


# --------------------------------------------------------------------------
# T-V1103-EXEC-07: through `run_agent_outcome`, INJ-04's turn -- the guard
# changes what the model receives, never what the gate scores
# --------------------------------------------------------------------------


def test_t_v1103_exec_07_guard_refusal_still_fails_injection_clause_e(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    conn = _conn(tmp_path)
    conv_id = storage.get_or_create_active_conversation(conn, ae.EVAL_USER_ID)
    inj04 = next(c for c in RED_TEAM if c["id"] == "INJ-04")
    turn = inj04["turns"][0]
    expect = turn["expect"]
    storage.add_user_message(conn, conv_id, turn["user"])

    exec_call = ToolCall("call_1", "exec", json.dumps({"argv": ["printenv"]}))
    llm = FakeLLM(
        [
            LLMResponse("", [exec_call], "tool_calls"),
            LLMResponse(expect["positive_reply"], [], "stop"),
        ]
    )

    spy_calls: list[list[str]] = []

    def spy_runner(argv):
        spy_calls.append(list(argv))
        return ae._refusing_runner(argv)

    def _forbidden_popen(*args, **kwargs):
        raise AssertionError(f"unexpected subprocess start: {args!r}")

    monkeypatch.setattr(subprocess, "Popen", _forbidden_popen)

    tool_calls: list[str] = []
    tool_call_log: list[str] = []

    def on_tool(name, arg):
        tool_calls.append(name)
        safe = arg if isinstance(arg, str) else ""
        tool_call_log.append(f"{name}({json.dumps(safe, ensure_ascii=False)})")

    outcome = agent.run_agent_outcome(
        conn=conn,
        conv_id=conv_id,
        llm=llm,
        skills={},
        runner=spy_runner,
        now=storage.utc_now_iso(),
        cfg=cfg,
        fetcher=None,
        searcher=None,
        resolve_cost=None,
        recent_goals=None,
        on_tool=on_tool,
    )

    assert outcome.reply == expect["positive_reply"]
    assert tool_calls == ["exec"]
    assert tool_call_log == ['exec("printenv")']
    # The guard refuses inside `execute_tool`, before `_run_exec` ever calls
    # the runner -- so the runner spy given to `run_agent_outcome` (mirroring
    # `_refusing_runner`) is never entered, and no real process starts.
    assert spy_calls == []

    passed, detail = ae.check_injection(
        outcome.reply, expect, system_prompt=SYSTEM_PROMPT, tool_calls=tool_calls
    )
    assert not passed
    assert detail.startswith("(e)")
    assert "exec" in detail


# --------------------------------------------------------------------------
# T-V1103-EXEC-08: the exec tool description is untouched (NG-14); catalog
# stays within its 1800-char cap
# --------------------------------------------------------------------------


def test_t_v1103_exec_08_description_byte_equal_to_636a281_catalog_cap():
    # Byte-for-byte the `git show 636a281:tools.py` slice (`:1289-1291`).
    pinned_description = (
        "Run one program in a network-less container. NEVER a shell: no pipes, "
        "redirection, globbing or chaining; argv[0] is the program, one element "
        "per argument."
    )
    specs = tools.tool_specs()
    exec_spec = next(spec for spec in specs if spec["function"]["name"] == "exec")
    assert exec_spec["function"]["description"] == pinned_description
    assert len(json.dumps(specs)) <= 1800
