import json
import logging
from pathlib import Path

import tools

REPO_ROOT = Path(__file__).resolve().parents[1]
CURL_ARGV = (
    '["curl", "--fail", "--silent", "--max-time", "10", "--", '
    '"https://wttr.in/<CITY>?format=3"]'
)

VALID = """---
name: demo
description: A demo skill.
# a comment
unknown_key: ignored

---

# Demo

Body line.
"""


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_t_sk_01_valid_file(tmp_path):
    write(tmp_path, "demo.md", VALID)
    skills = tools.load_skills(tmp_path)
    assert set(skills) == {"demo"}
    skill = skills["demo"]
    assert skill.name == "demo"
    assert skill.description == "A demo skill."
    assert skill.body == "# Demo\n\nBody line."
    assert skill.source == "demo.md"


def test_t_sk_02_invalid_files_are_skipped(tmp_path, caplog):
    write(tmp_path, "a-no-open.md", "name: x\n---\nbody\n")
    write(tmp_path, "b-no-close.md", "---\nname: x\ndescription: y\nbody\n")
    write(tmp_path, "c-no-name.md", "---\ndescription: y\n---\nbody\n")
    write(tmp_path, "d-no-description.md", "---\nname: x\n---\nbody\n")
    write(tmp_path, "e-bad-name.md", "---\nname: Bad Name\ndescription: y\n---\nbody\n")
    (tmp_path / "f-bad-bytes.md").write_bytes(b"---\nname: x\ndescription: \xff\xfe\n---\n")
    with caplog.at_level(logging.WARNING):
        skills = tools.load_skills(tmp_path)
    assert skills == {}
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 6
    for name in ("a-no-open.md", "b-no-close.md", "c-no-name.md",
                 "d-no-description.md", "e-bad-name.md", "f-bad-bytes.md"):
        assert any(name in w for w in warnings)


def test_t_sk_03_duplicate_names(tmp_path, caplog):
    write(tmp_path, "aaa.md", "---\nname: dup\ndescription: first\n---\nfirst body\n")
    write(tmp_path, "bbb.md", "---\nname: dup\ndescription: second\n---\nsecond body\n")
    with caplog.at_level(logging.WARNING):
        skills = tools.load_skills(tmp_path)
    assert set(skills) == {"dup"}
    assert skills["dup"].source == "aaa.md"
    assert skills["dup"].description == "first"
    assert any("duplicate skill name 'dup' in bbb.md ignored" in r.getMessage()
               for r in caplog.records)


def test_t_sk_04_shipped_skills_load():
    skills = tools.load_skills(REPO_ROOT / "skills")
    assert set(skills) == {"weather", "host-info"}
    assert skills["weather"].source == "weather.md"
    assert skills["host-info"].source == "host-info.md"


def test_t_sk_05_weather_body_carries_the_exact_argv():
    skills = tools.load_skills(REPO_ROOT / "skills")
    assert CURL_ARGV in skills["weather"].body


def test_t_sk_06_load_skill_dispatch():
    skills = tools.load_skills(REPO_ROOT / "skills")

    def runner(argv):
        raise AssertionError("the runner must not be called for load_skill")

    ok = json.loads(
        tools.execute_tool("load_skill", '{"name": "weather"}', skills=skills, runner=runner)
    )
    assert ok["name"] == "weather"
    assert ok["body"] == skills["weather"].body

    for bad in ("../../etc/passwd", "Weather", "no-such-skill"):
        result = json.loads(
            tools.execute_tool(
                "load_skill", json.dumps({"name": bad}), skills=skills, runner=runner
            )
        )
        assert result == {"error": f"unknown skill: {bad}. Available: host-info, weather"}

    assert json.loads(
        tools.execute_tool("load_skill", '{"name": 7}', skills=skills, runner=runner)
    ) == {"error": "name is required and must be a string"}
    assert json.loads(
        tools.execute_tool("load_skill", "{}", skills=skills, runner=runner)
    ) == {"error": "name is required and must be a string"}


def test_t_sk_07_missing_directory(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        assert tools.load_skills(tmp_path / "absent") == {}
    assert caplog.records


def test_t_sk_08_tool_specs():
    specs = tools.tool_specs()
    assert [s["function"]["name"] for s in specs] == ["exec", "load_skill"]
    assert all(s["type"] == "function" for s in specs)
    assert specs[0]["function"]["parameters"]["required"] == ["argv"]
    assert specs[1]["function"]["parameters"]["required"] == ["name"]


def test_t_sk_unknown_tool_and_bad_arguments():
    assert json.loads(
        tools.execute_tool("nope", "{}", skills={}, runner=lambda argv: {})
    ) == {"error": "unknown tool: nope"}
    assert json.loads(
        tools.execute_tool("exec", "{oops", skills={}, runner=lambda argv: {})
    ) == {"error": "arguments are not valid JSON"}
    assert json.loads(
        tools.execute_tool("exec", "[1]", skills={}, runner=lambda argv: {})
    ) == {"error": "arguments must be a JSON object"}
    # Arguments are parsed before the tool name is looked at (REQ-TOOL-03 order).
    assert json.loads(
        tools.execute_tool("nope", "{oops", skills={}, runner=lambda argv: {})
    ) == {"error": "arguments are not valid JSON"}
