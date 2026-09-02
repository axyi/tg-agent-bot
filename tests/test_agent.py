import json
from pathlib import Path

import agent
import storage
import tools
from llm.base import LLMError, LLMResponse, ToolCall
from tests.fakes import FakeFetcher, FakeLLM, RecordingRunner

NOW = "2026-08-28T12:00:00Z"
REPO_ROOT = Path(__file__).resolve().parents[1]
EXEC_ARGS = '{"argv": ["uname", "-a"]}'


def call(index, name="exec", arguments=EXEC_ARGS):
    return ToolCall(f"call_{index}", name, arguments)


def tool_response(n, content="", start=0):
    return LLMResponse(content, [call(i) for i in range(start, start + n)], "tool_calls")


def answer(content="done"):
    return LLMResponse(content, [], "stop")


def run(conn, script, *, skills=None, runner=None, user="hello", fetcher=None):
    conv = storage.get_or_create_active_conversation(conn, 7)
    storage.add_user_message(conn, conv, user)
    llm = FakeLLM(script)
    runner = runner if runner is not None else RecordingRunner()
    sleeps = []
    reply = agent.run_agent(
        conn=conn,
        conv_id=conv,
        llm=llm,
        skills=skills or {},
        runner=runner,
        now=NOW,
        sleep=sleeps.append,
        fetcher=fetcher,
    )
    return reply, llm, runner, sleeps, conv


def rows(conn, conv):
    return conn.execute(
        "SELECT turn_id, role, content, tool_calls_json, tool_call_id "
        "FROM messages WHERE conv_id = ? ORDER BY id",
        (conv,),
    ).fetchall()


def test_t_ag_01_plain_answer(conn):
    reply, llm, runner, _, conv = run(conn, [answer("the answer")])
    assert reply == "the answer"
    assert len(llm.calls) == 1
    assert runner.argv_calls == []
    stored = rows(conn, conv)
    assert [r["role"] for r in stored] == ["user", "assistant"]
    assert stored[-1]["content"] == "the answer"
    assert stored[-1]["tool_calls_json"] is None
    assert stored[0]["turn_id"] != stored[1]["turn_id"]


def test_t_ag_02_tool_round_then_answer(conn):
    reply, llm, runner, _, conv = run(conn, [tool_response(1), answer("final")])
    assert reply == "final"
    assert runner.argv_calls == [["uname", "-a"]]
    stored = rows(conn, conv)
    assert [r["role"] for r in stored] == ["user", "assistant", "tool", "assistant"]
    assert stored[1]["turn_id"] == stored[2]["turn_id"]
    # REQ-V12-ID-01: the id is minted by the bot, not a literal the model
    # supplied — only the pairing between the two rows is guaranteed.
    wire = json.loads(stored[1]["tool_calls_json"])
    assert stored[2]["tool_call_id"] == wire[0]["id"]
    assert stored[3]["turn_id"] not in {stored[1]["turn_id"], stored[0]["turn_id"]}
    # the tool result reached the provider on the next request
    second_request = llm.calls[1][0]
    assert second_request[-1]["role"] == "tool"
    assert second_request[-2]["role"] == "assistant"


def test_t_ag_03_round_limit(conn):
    script = [tool_response(1) for _ in range(agent.ROUND_LIMIT)]
    reply, llm, runner, _, _ = run(conn, script)
    assert len(llm.calls) == 8
    assert reply == agent.FALLBACK_NO_ANSWER
    assert llm.calls[7][1] is None
    assert llm.calls[7][0][-1] == {"role": "system", "content": agent.FINAL_INSTRUCTION}
    for messages, exposed in llm.calls[:7]:
        assert exposed is not None
        assert messages[-1].get("content") != agent.FINAL_INSTRUCTION
    assert len(runner.argv_calls) == 7


def test_t_ag_04_tool_execution_limit(conn):
    script = [tool_response(3) for _ in range(4)] + [answer("wrapped up")]
    reply, llm, runner, _, _ = run(conn, script)
    assert reply == "wrapped up"
    assert len(runner.argv_calls) == 12
    assert llm.calls[3][1] is not None
    assert llm.calls[4][1] is None
    assert llm.calls[4][0][-1]["content"] == agent.FINAL_INSTRUCTION


def test_t_ag_05_excess_calls_in_one_response(conn):
    reply, llm, runner, _, conv = run(conn, [tool_response(5), answer("ok")])
    assert reply == "ok"
    assert len(runner.argv_calls) == 3
    stored = rows(conn, conv)
    assistant = stored[1]
    assert len(json.loads(assistant["tool_calls_json"])) == 5
    tool_rows = [r for r in stored if r["role"] == "tool"]
    assert len(tool_rows) == 5
    for row in tool_rows[3:]:
        assert json.loads(row["content"])["error"].startswith("too many tool calls")


def test_t_ag_06_budget_exhausted_mid_response(conn):
    script = [tool_response(3) for _ in range(3)]
    script.append(tool_response(1))
    script.append(tool_response(3))
    script.append(answer("finished"))
    reply, llm, runner, _, conv = run(conn, script)
    assert reply == "finished"
    assert len(runner.argv_calls) == 12
    last_group = [r for r in rows(conn, conv) if r["role"] == "tool"][-3:]
    assert json.loads(last_group[2]["content"])["error"].startswith("tool budget exhausted")
    assert json.loads(last_group[0]["content"]).get("error") is None
    assert llm.calls[5][1] is None


def test_t_ag_07_malformed_calls_all_get_results(conn):
    calls = [
        ToolCall("call_a", "exec", "{not json"),
        ToolCall("call_b", "exec", "[1, 2]"),
        ToolCall("call_c", "nosuchtool", "{}"),
        ToolCall("  ", "exec", EXEC_ARGS),
        ToolCall("call_a", "exec", EXEC_ARGS),
    ]
    script = [LLMResponse("", calls, "tool_calls"), answer("ok")]
    reply, llm, runner, _, conv = run(conn, script)
    assert reply == "ok"
    stored = rows(conn, conv)
    wire = json.loads(stored[1]["tool_calls_json"])
    ids = [c["id"] for c in wire]
    # REQ-V12-ID-01: the model's ids (duplicate, empty, whatever it sent) are
    # discarded unconditionally — every kept call gets the minted
    # call_<turn_id>_<index> value regardless.
    turn_id = stored[1]["turn_id"]
    assert ids == [f"call_{turn_id}_{i}" for i in range(5)]
    assert len(ids) == len(set(ids)) == 5
    tool_rows = [r for r in stored if r["role"] == "tool"]
    assert [r["tool_call_id"] for r in tool_rows] == ids
    assert json.loads(tool_rows[0]["content"]) == {"error": "arguments are not valid JSON"}
    assert json.loads(tool_rows[1]["content"]) == {"error": "arguments must be a JSON object"}
    assert json.loads(tool_rows[2]["content"]) == {"error": "unknown tool: nosuchtool"}


def test_t_ag_08_retryable_error_then_success(conn):
    script = [LLMError("llm http 500", retryable=True), answer("recovered")]
    reply, llm, runner, sleeps, _ = run(conn, script)
    assert reply == "recovered"
    assert len(llm.calls) == 2
    assert sleeps == [agent.RETRY_SLEEP_S]
    assert llm.calls[0][1] is not None
    assert llm.calls[1][1] is not None
    assert llm.calls[0][0] == llm.calls[1][0]


def test_t_ag_09_retry_pool_exhausted(conn):
    script = [LLMError("llm http 503", retryable=True) for _ in range(9)]
    reply, llm, runner, sleeps, conv = run(conn, script)
    assert len(llm.calls) == agent.HTTP_ATTEMPT_LIMIT
    assert len(sleeps) == 8
    assert reply == agent.FALLBACK_LLM_ERROR.format(reason="llm http 503")
    stored = rows(conn, conv)
    assert stored[-1]["role"] == "assistant"
    assert stored[-1]["content"] == reply


def test_t_ag_10_non_retryable_error(conn):
    script = [LLMError("llm http 400: bad", retryable=False)]
    reply, llm, runner, sleeps, _ = run(conn, script)
    assert len(llm.calls) == 1
    assert sleeps == []
    assert reply == agent.FALLBACK_LLM_ERROR.format(reason="llm http 400: bad")


def test_t_ag_11_tool_calls_while_tools_are_none(conn):
    script = [tool_response(3) for _ in range(4)]
    script.append(LLMResponse("late answer", [call(0)], "tool_calls"))
    reply, llm, runner, _, conv = run(conn, script)
    assert reply == "late answer"
    assert len(runner.argv_calls) == 12
    assert len([r for r in rows(conn, conv) if r["role"] == "tool"]) == 12


def test_t_ag_11_tool_calls_while_tools_are_none_without_content(conn):
    script = [tool_response(3) for _ in range(4)]
    script.append(LLMResponse("", [call(0)], "tool_calls"))
    reply, llm, runner, _, conv = run(conn, script)
    assert reply == agent.FALLBACK_NO_ANSWER
    assert len(runner.argv_calls) == 12
    assert rows(conn, conv)[-1]["content"] == agent.FALLBACK_NO_ANSWER


def test_t_ag_12_empty_content_triggers_one_repair_round(conn):
    # REQ-V1-RP-03: the first empty response buys one repair round, not the fallback.
    empty = [LLMResponse("", [], "stop"), LLMResponse("", [], "stop")]
    reply, llm, runner, _, conv = run(conn, empty)
    assert reply == agent.FALLBACK_EMPTY
    assert len(llm.calls) == 2
    assert llm.calls[0][0][-1]["content"] != agent.EMPTY_REPAIR_INSTRUCTION
    assert llm.calls[1][0][-1] == {
        "role": "system", "content": agent.EMPTY_REPAIR_INSTRUCTION
    }
    assert rows(conn, conv)[-1]["content"] == agent.FALLBACK_EMPTY
    # The repair instruction is a request-time nudge, never a stored message.
    stored = conn.execute("SELECT content FROM messages").fetchall()
    assert all(agent.EMPTY_REPAIR_INSTRUCTION not in r["content"] for r in stored)


def test_t_ag_12_repaired_empty_response_answers(conn):
    script = [LLMResponse("", [], "stop"), answer("recovered")]
    reply, llm, runner, _, conv = run(conn, script)
    assert reply == "recovered"
    assert len(llm.calls) == 2


def test_t_ag_13_system_prompt(conn):
    skills = tools.load_skills(REPO_ROOT / "skills")
    reply, llm, runner, _, conv = run(conn, [answer("ok")], skills=skills)
    system = llm.calls[0][0][0]
    assert system["role"] == "system"
    # REQ-V13-CCH-01: the clock left the prefix; it rides on the user message.
    assert NOW not in system["content"]
    assert llm.calls[0][0][-1]["content"].endswith(agent.format_now_line(NOW))
    for skill in skills.values():
        assert f"- {skill.name}: {skill.description}" in system["content"]
    assert "- host-info:" in system["content"].split(agent.SKILLS_HEADER)[1]
    # REQ-AG-10: the system prompt is rebuilt per request and never persisted.
    stored = conn.execute("SELECT content FROM messages").fetchall()
    assert all(system["content"] not in row["content"] for row in stored)
    assert all(agent.SKILLS_HEADER not in row["content"] for row in stored)


def test_t_ag_13_system_prompt_without_skills(conn):
    prompt = agent.build_system_prompt({}, NOW)
    assert prompt.rstrip().endswith("- (none)")


def test_t_ag_14_weather_skill_url_reaches_the_fetcher(conn, monkeypatch):
    # REQ-V1-SK-01: the weather skill now scripts a `fetch` call, never an exec.
    skills = tools.load_skills(REPO_ROOT / "skills")
    url = "https://wttr.in/K%C3%B6ln?format=3"
    script = [
        LLMResponse("", [ToolCall("call_1", "load_skill", '{"name": "weather"}')], "tool_calls"),
        LLMResponse("", [ToolCall("call_2", "fetch", json.dumps({"url": url}))], "tool_calls"),
        answer("Koln: sunny"),
    ]
    # REQ-V13-TOO-07 shape, not the dead v1.2 one: a stub that still spoke the
    # old envelope made `tools._fetch_size` return None, so the size columns
    # silently fell back to the envelope length and this end-to-end leg stopped
    # covering TOO-07 at all.
    fetcher = FakeFetcher({"url": url, "status": 200, "content_type": "text/plain",
                           "chars_total": 128, "returned_chars": 16,
                           "truncated": True, "saved_to": "fetch/" + "0" * 16 + ".txt",
                           "save_error": None, "text": "Koln: sunny +21C"})
    runner = RecordingRunner()
    runner.forbid_real_processes(monkeypatch)
    reply, llm, runner, _, conv = run(
        conn, script, skills=skills, runner=runner, fetcher=fetcher
    )
    assert reply == "Koln: sunny"
    # No process was started (forbid_real_processes) and no request left the process
    # (the `no_network` conftest fixture); only the injected fetcher saw the URL.
    assert fetcher.urls == [url]
    assert runner.argv_calls == []
    tool_rows = [r for r in rows(conn, conv) if r["role"] == "tool"]
    assert json.loads(tool_rows[0]["content"])["name"] == "weather"
    assert json.loads(tool_rows[1]["content"])["text"].startswith("Koln: sunny")
    # REQ-V13-TOO-03: the fetch row is measured on `chars_total` against the
    # inline excerpt — the assertion that goes red if the envelope shape rots.
    row = conn.execute(
        "SELECT * FROM tool_calls WHERE tool = 'fetch' ORDER BY id"
    ).fetchone()
    assert (row["raw_output_chars"], row["output_chars"]) == (128, 16)


def test_t_ag_15_calls_beyond_the_accept_cap_are_dropped(conn):
    script = [tool_response(12), answer("ok")]
    reply, llm, runner, _, conv = run(conn, script)
    assert reply == "ok"
    assert len(runner.argv_calls) == 3
    stored = rows(conn, conv)
    wire = json.loads(stored[1]["tool_calls_json"])
    assert len(wire) == agent.MAX_TOOL_CALLS_ACCEPTED
    tool_rows = [r for r in stored if r["role"] == "tool"]
    assert len(tool_rows) == 8
    group = [r for r in stored if r["turn_id"] == stored[1]["turn_id"]]
    assert len(group) == 9
    excess = [json.loads(r["content"])["error"] for r in tool_rows[3:]]
    assert all(e.startswith("too many tool calls") for e in excess)
    dropped = [f"call_{i}" for i in range(8, 12)]
    blob = json.dumps([dict(r) for r in stored]) + json.dumps(llm.calls[1][0])
    assert not any(d in blob for d in dropped)
