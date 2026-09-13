"""spec-v1.10.0 T2: the tool-call wire contract, end to end.

REQ-V1100-TC-01: `llm.base.parse_response`'s wire coercion of
`tool_calls[].function.arguments` feeds `tools.execute_tool`'s decode point
(the only place `json.loads(arguments)` happens) correctly, for all four
envelope shapes. See `docs/spec/spec-v1.10.0.md` sec.4 and sec.12. Nothing
in `llm/base.py` or `tools.py` changes here -- this pins the existing
contract with the tests row `T-V1100-TC-01..03` names as missing.
"""

import json

import pytest

import tools
from llm.base import ToolCall, parse_response
from tests.fakes import RecordingRunner


def wire_message(tool_calls):
    """One `choices[0].message` wire dict carrying the given raw `tool_calls`."""
    return {"choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": tool_calls}}]}


# --------------------------------------------------------------------------
# T-V1100-TC-01: `parse_response`'s wire coercion of `function.arguments`.
# --------------------------------------------------------------------------


def test_t_v1100_tc_01_missing_arguments_key_is_empty_string():
    payload = wire_message([{"id": "1", "type": "function", "function": {"name": "exec"}}])
    response = parse_response(payload)
    assert response.tool_calls[0].arguments == ""


def test_t_v1100_tc_01_null_arguments_is_empty_string():
    payload = wire_message(
        [{"id": "1", "type": "function", "function": {"name": "exec", "arguments": None}}]
    )
    response = parse_response(payload)
    assert response.tool_calls[0].arguments == ""


def test_t_v1100_tc_01_object_arguments_becomes_its_own_json_dumps():
    raw_arguments = {"name": "x"}
    payload = wire_message(
        [
            {
                "id": "1",
                "type": "function",
                "function": {"name": "load_skill", "arguments": raw_arguments},
            }
        ]
    )
    response = parse_response(payload)
    # Computed, not hardcoded: a hand-typed literal could pass by accident on
    # key order this dict doesn't exercise.
    assert response.tool_calls[0].arguments == json.dumps(raw_arguments, ensure_ascii=False)


def test_t_v1100_tc_01_string_arguments_pass_through_verbatim():
    payload = wire_message(
        [{"id": "1", "type": "function", "function": {"name": "exec", "arguments": "raw string"}}]
    )
    response = parse_response(payload)
    assert response.tool_calls[0].arguments == "raw string"


def test_t_v1100_tc_01_non_dict_tool_calls_entry_yields_an_empty_toolcall():
    payload = wire_message(["not-a-dict-entry"])
    response = parse_response(payload)
    assert response.tool_calls == [ToolCall(id="", name="", arguments="")]


# --------------------------------------------------------------------------
# T-V1100-TC-02: the positive contract -- an object-valued `arguments` for
# `load_skill` reaches `execute_tool` as valid JSON and the skill loads.
# --------------------------------------------------------------------------


def test_t_v1100_tc_02_object_arguments_load_skill_reaches_execute_tool():
    skill = tools.Skill(name="weather", description="d", body="body text", source="weather.md")
    payload = wire_message(
        [
            {
                "id": "1",
                "type": "function",
                "function": {"name": "load_skill", "arguments": {"name": "weather"}},
            }
        ]
    )
    call = parse_response(payload).tool_calls[0]
    result = json.loads(
        tools.execute_tool(
            call.name, call.arguments, skills={"weather": skill}, runner=RecordingRunner()
        )
    )
    assert result == {"name": "weather", "body": "body text"}
    assert "error" not in result


# --------------------------------------------------------------------------
# T-V1100-TC-03: the four envelopes, negative, driven from the wire shape
# through `parse_response` then `execute_tool`.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tool_name", "function_extra", "expected_error", "check_audit"),
    [
        pytest.param("exec", {}, "arguments are not valid JSON", True, id="missing-arguments-key"),
        pytest.param(
            "exec",
            {"arguments": "[1]"},
            "arguments must be a JSON object",
            True,
            id="non-object-json",
        ),
        pytest.param(
            "exec",
            {"arguments": "{not json"},
            "arguments are not valid JSON",
            True,
            id="invalid-json",
        ),
        pytest.param(
            "nosuchtool",
            {"arguments": {"x": 1}},
            "unknown tool: nosuchtool",
            False,
            id="unknown-tool",
        ),
    ],
)
def test_t_v1100_tc_03_four_envelopes_from_the_wire_shape(
    tool_name, function_extra, expected_error, check_audit
):
    """The four envelopes, driven end to end from the wire shape.

    Complements without duplicating: `tests/test_skills.py:143` (the same
    four envelopes, from hand-written argument strings), `tests/test_agent.py:134`
    (every malformed call still gets a tool message), and
    `tests/test_v1_guardrails.py:268` (the audit trace for unparsable
    arguments). What none of those prove: that `parse_response`'s own wire
    coercion -- not a hand-typed string -- produces the argument text that
    reaches `execute_tool`'s decode point, and that the result is the same
    refusal or success either way.
    """
    function = {"name": tool_name, **function_extra}
    payload = wire_message([{"id": "1", "type": "function", "function": function}])
    call = parse_response(payload).tool_calls[0]

    records = []
    result = tools.execute_tool(
        call.name, call.arguments, skills={}, runner=RecordingRunner(), audit=records.append
    )

    assert isinstance(result, str)  # never an exception, always a returned string
    envelope = json.loads(result)
    assert envelope == {"error": expected_error}
    if check_audit:
        assert [r["outcome"] for r in records] == ["refused"]
    else:
        assert records == []
