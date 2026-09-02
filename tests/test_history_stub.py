"""Request-time compaction of stale tool results — spec-v1.3 section 10.2
(REQ-V13-HST-01…05).

Everything here is offline: a scripted `FakeLLM`, a `RecordingRunner` that never
starts a process, and conversations written straight into SQLite. The subject is
always the *request* `run_agent` builds, compared with the rows the database
keeps — the two must diverge exactly where the spec says they may.
"""

import hashlib
import json

import agent
import config
import storage
from llm.base import LLMResponse, ToolCall
from tests.fakes import FakeLLM, RecordingRunner

NOW = "2026-09-02T10:00:00Z"
USER_ID = 424242
BIG_STDOUT = "\n".join(f"line {i:04d} of a long build log" for i in range(120))


def exec_result(stdout: str, exit_code: int = 0) -> str:
    return json.dumps({
        "exit_code": exit_code,
        "timed_out": False,
        "truncated": False,
        "stdout": stdout,
        "stderr": "",
        "compacted": False,
        "stdout_bytes_total": len(stdout.encode("utf-8")),
        "stderr_bytes_total": 0,
    }, ensure_ascii=False)


def fetch_result(url: str, text: str, saved_to: str | None) -> str:
    return json.dumps({
        "url": url,
        "status": 200,
        "content_type": "text/plain",
        "chars_total": len(text) + 500,
        "returned_chars": len(text),
        "truncated": saved_to is not None,
        "saved_to": saved_to,
        "save_error": None,
        "text": text,
    }, ensure_ascii=False)


def skill_result(name: str, body: str) -> str:
    return json.dumps({"name": name, "body": body}, ensure_ascii=False)


def wire(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def tool_turn(conn, conv, calls: list[tuple[dict, str]], content: str = "") -> None:
    """One assistant turn plus its tool results, exactly as `run_agent` stores them."""
    storage.add_tool_turn(
        conn, conv, content,
        [call for call, _ in calls],
        [(call["id"], result) for call, result in calls],
    )


def conversation(conn, *, stdout=BIG_STDOUT) -> int:
    """Turn 1 asks, turn 2 runs exec, turn 3 answers, turn 4 is the new user
    message — the shape the serving path produces before `run_agent` is called."""
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "build the project")
    tool_turn(conn, conv, [(wire("call_2_0", "exec", {"argv": ["make"]}),
                            exec_result(stdout))])
    storage.add_assistant_message(conn, conv, "the build succeeded")
    storage.add_user_message(conn, conv, "and now the tests?")
    return conv


def assemble(conn, conv, **overrides) -> list[dict]:
    kwargs = {"context_length": None, "max_tokens": None}
    kwargs.update(overrides)
    _, history = agent._assemble_context(conn, conv, {}, NOW, None, **kwargs)
    return history


def run(conn, conv, script=None, *, cfg=None):
    llm = FakeLLM(script if script is not None else [LLMResponse("done", [], "stop")])
    agent.run_agent(
        conn=conn, conv_id=conv, llm=llm, skills={}, runner=RecordingRunner(),
        now=NOW, sleep=lambda _seconds: None, cfg=cfg,
    )
    return llm


def make_cfg(tmp_path, **overrides):
    fields = {
        "telegram_bot_token": "123456789:sentinel-token-for-the-history-stub-tests",
        "allowed_tg_ids": frozenset({USER_ID}),
        "llm_provider": "lmstudio",
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_model": "m",
        "openrouter_api_key": "",
        "openrouter_model": "",
        "llm_timeout_s": 120.0,
        "exec_workdir": tmp_path / "sandbox",
        "db_path": tmp_path / "test.db",
        "audit_log_path": tmp_path / "exec_audit.jsonl",
    }
    fields.update(overrides)
    return config.Config(**fields)


def tool_messages(messages: list[dict]) -> list[dict]:
    return [message for message in messages if message.get("role") == "tool"]


def stored_tool_contents(conn, conv) -> list[str]:
    return [row["content"] for row in conn.execute(
        "SELECT content FROM messages WHERE conv_id = ? AND role = 'tool' ORDER BY id",
        (conv,),
    ).fetchall()]


def window_cost(messages: list[dict]) -> int:
    return sum(agent.estimate_message(message) for message in messages)


# --------------------------------------------------------------------------
# REQ-V13-HST-01 — stale tool results become stubs, in the request only
# --------------------------------------------------------------------------

def test_hst_01_a_stale_exec_result_is_stubbed_in_the_request(conn, monkeypatch):
    monkeypatch.setattr(config, "_secrets", set())   # so `head` is an exact prefix
    conv = conversation(conn)
    original = stored_tool_contents(conn, conv)[0]

    llm = run(conn, conv)
    stubs = tool_messages(llm.calls[0][0])
    assert len(stubs) == 1
    stub = json.loads(stubs[0]["content"])
    assert stub["stub"] is True
    assert stub["tool"] == "exec"
    assert stub["exit_code"] == 0
    assert stub["chars"] == len(original)
    assert stub["sha256_16"] == hashlib.sha256(original.encode("utf-8")).hexdigest()[:16]
    assert stub["head"] == original[:agent.STUB_HEAD_CHARS]
    # The stub is what makes O2 worth doing at all.
    assert len(stubs[0]["content"]) < len(original)


def test_hst_01_the_database_row_is_untouched(conn):
    conv = conversation(conn)
    before = stored_tool_contents(conn, conv)
    run(conn, conv)
    assert stored_tool_contents(conn, conv) == before
    assert json.loads(before[0])["stdout"] == BIG_STDOUT


def test_hst_01_a_stale_fetch_result_keeps_its_url_and_saved_path(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "what is the weather?")
    tool_turn(conn, conv, [(
        wire("call_2_0", "fetch", {"url": "https://wttr.in/Koln"}),
        fetch_result("https://wttr.in/Koln", "sunny " * 400, "fetch/abcdef0123456789.txt"),
    )])
    storage.add_assistant_message(conn, conv, "sunny")
    storage.add_user_message(conn, conv, "and tomorrow?")

    stub = json.loads(tool_messages(assemble(conn, conv))[0]["content"])
    assert stub == {
        "stub": True,
        "tool": "fetch",
        "url": "https://wttr.in/Koln",
        "saved_to": "fetch/abcdef0123456789.txt",
        "chars": len(stored_tool_contents(conn, conv)[0]),
    }


def test_hst_01_an_unmatched_tool_call_id_gets_the_generic_stub(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    # The assistant announced one id; the stored result carries another — the
    # pairing the resolver needs is simply not there.
    storage.add_tool_turn(
        conn, conv, "", [wire("call_2_0", "exec", {"argv": ["make"]})],
        [("call_2_9", exec_result("orphan output"))],
    )
    storage.add_user_message(conn, conv, "again")

    original = stored_tool_contents(conn, conv)[0]
    stub = json.loads(tool_messages(assemble(conn, conv))[0]["content"])
    assert stub == {
        "stub": True,
        "tool": "unknown",
        "chars": len(original),
        "sha256_16": hashlib.sha256(original.encode("utf-8")).hexdigest()[:16],
        "head": original[:agent.STUB_HEAD_CHARS],
    }


def test_hst_01_a_coerced_tool_name_gets_the_generic_stub(conn):
    """REQ-V12-ID-01 item 4 records a name outside the advertised set as the
    literal `unknown`; that stored turn resolves to no tool, so the stub is the
    generic one rather than a shape invented for a tool that does not exist."""
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    tool_turn(conn, conv, [(wire("call_2_0", "unknown", {"argv": ["make"]}),
                            json.dumps({"error": "unknown tool: rm"}))])
    storage.add_user_message(conn, conv, "again")

    stub = json.loads(tool_messages(assemble(conn, conv))[0]["content"])
    assert stub["tool"] == "unknown"
    assert set(stub) == {"stub", "tool", "chars", "sha256_16", "head"}


def test_hst_01_the_nearest_preceding_assistant_resolves_the_name(conn):
    """A later turn reusing an earlier id must not decide the earlier stub."""
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    tool_turn(conn, conv, [(wire("dup", "exec", {"argv": ["make"]}),
                            exec_result("first"))])
    tool_turn(conn, conv, [(wire("dup", "fetch", {"url": "https://wttr.in/x"}),
                            fetch_result("https://wttr.in/x", "sunny", None))])
    storage.add_user_message(conn, conv, "again")

    stubs = [json.loads(message["content"])
             for message in tool_messages(assemble(conn, conv))]
    assert [stub["tool"] for stub in stubs] == ["exec", "fetch"]


def test_hst_01_the_stub_head_never_ends_inside_a_secret(conn, monkeypatch):
    canary = "SYNTHETIC-CANARY-NEVER-A-LIVE-VALUE"
    monkeypatch.setattr(config, "_secrets", {canary})
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "hello")
    # A *prefix* of the canary straddles the 120-char head cut, so redaction —
    # which only ever sees complete secrets — cannot have removed it.
    empty = exec_result("")
    offset = empty.index('"stdout": "') + len('"stdout": "')
    stdout = "x" * (agent.STUB_HEAD_CHARS - offset - 10) + canary[:20]
    tool_turn(conn, conv, [(wire("call_2_0", "exec", {"argv": ["cat", "key"]}),
                            exec_result(stdout))])
    storage.add_user_message(conn, conv, "again")

    stub = json.loads(tool_messages(assemble(conn, conv))[0]["content"])
    assert canary[:8] not in stub["head"]
    assert stub["head"].endswith("x")


def test_hst_01_results_of_the_current_invocation_stay_verbatim(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "run it")
    llm = run(conn, conv, [
        LLMResponse("", [ToolCall("x", "exec", '{"argv": ["uname"]}')], "tool_calls"),
        LLMResponse("done", [], "stop"),
    ])
    second_request = llm.calls[1][0]
    assert second_request[-1]["role"] == "tool"
    assert json.loads(second_request[-1]["content"])["stdout"] == "recorded\n"


# --------------------------------------------------------------------------
# REQ-V13-HST-02 — the newest load of each skill survives verbatim
# --------------------------------------------------------------------------

def test_hst_02_the_latest_load_of_each_skill_is_verbatim(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "weather please")
    tool_turn(conn, conv, [(wire("call_2_0", "load_skill", {"name": "weather"}),
                            skill_result("weather", "old weather instructions"))])
    tool_turn(conn, conv, [(wire("call_3_0", "load_skill", {"name": "weather"}),
                            skill_result("weather", "new weather instructions"))])
    tool_turn(conn, conv, [(wire("call_4_0", "load_skill", {"name": "hosts"}),
                            skill_result("hosts", "host instructions"))])
    storage.add_user_message(conn, conv, "and now?")

    contents = [message["content"] for message in tool_messages(assemble(conn, conv))]
    assert json.loads(contents[0]) == {"stub": True, "tool": "load_skill",
                                       "name": "weather"}
    assert contents[1] == skill_result("weather", "new weather instructions")
    assert contents[2] == skill_result("hosts", "host instructions")


# --------------------------------------------------------------------------
# REQ-V13-HST-03 — nothing but tool messages is ever rewritten
# --------------------------------------------------------------------------

def test_hst_03_user_and_assistant_messages_are_never_stubbed(conn):
    conv = conversation(conn)
    plain = [message for message in assemble(conn, conv) if message["role"] != "tool"]
    assert [message["role"] for message in plain] == [
        "user", "assistant", "assistant", "user"
    ]
    assert plain[0]["content"] == "build the project"
    assert plain[2]["content"] == "the build succeeded"
    # REQ-V13-CCH-01 appends the clock to the newest user message, and only there.
    assert plain[3]["content"] == f"and now the tests?\n{agent.format_now_line(NOW)}"
    # The assistant's own tool_calls block is part of the prefix and stays.
    assert plain[1]["tool_calls"] == [wire("call_2_0", "exec", {"argv": ["make"]})]
    assert "stub" not in json.dumps(plain, ensure_ascii=False)


# --------------------------------------------------------------------------
# REQ-V13-HST-04 — the budget sees the stubs; `off` is the un-stubbed assembly
# --------------------------------------------------------------------------

def test_hst_04_off_equals_the_unstubbed_assembly(conn, tmp_path):
    conv = conversation(conn)
    expected = assemble(conn, conv, stub_tool_results=False)

    llm = run(conn, conv, cfg=make_cfg(tmp_path, history_tool_stub="off"))
    sent = [message for message in llm.calls[0][0] if message["role"] != "system"]
    assert sent == expected
    assert tool_messages(sent)[0]["content"] == stored_tool_contents(conn, conv)[0]


def test_hst_04_on_and_off_differ_only_in_the_tool_messages(conn):
    conv = conversation(conn)
    stubbed = assemble(conn, conv)
    verbatim = assemble(conn, conv, stub_tool_results=False)
    for left, right in zip(stubbed, verbatim, strict=True):
        if left["role"] == "tool":
            assert left["content"] != right["content"]
        else:
            assert left == right


def test_hst_04_the_token_budget_is_computed_on_the_stubbed_messages(conn):
    """A window that fits only once the old results are stubs is the whole
    point: with stubbing off the same budget drops the older turns."""
    conv = conversation(conn)
    stubbed_window = assemble(conn, conv)
    # Exactly enough for the stubbed window, nowhere near the verbatim one.
    context_length = (
        agent.estimate_tokens(agent.build_system_prompt({}, NOW, None))
        + agent.TOKEN_BUDGET_MARGIN + window_cost(stubbed_window) + 1
    )
    budget = {"context_length": context_length, "max_tokens": 0}

    assert assemble(conn, conv, **budget) == stubbed_window
    verbatim = assemble(conn, conv, stub_tool_results=False, **budget)
    assert len(verbatim) < len(stubbed_window)
    assert tool_messages(verbatim) == []


def test_hst_04_the_context_window_is_unchanged():
    assert agent.CONTEXT_WINDOW_MESSAGES == 30


# --------------------------------------------------------------------------
# REQ-V13-HST-05 — the recorded prompt size is the stubbed one
# --------------------------------------------------------------------------

def by_role(conn) -> dict:
    row = conn.execute("SELECT prompt_chars_by_role FROM llm_calls ORDER BY id").fetchone()
    return json.loads(row[0])


def test_hst_05_prompt_chars_by_role_tool_reflects_the_stub(conn, tmp_path):
    conv = conversation(conn)
    run(conn, conv, cfg=make_cfg(tmp_path))
    stubbed = by_role(conn)

    conn.execute("DELETE FROM llm_calls")
    run(conn, conv, cfg=make_cfg(tmp_path, history_tool_stub="off"))
    verbatim = by_role(conn)

    assert 0 < stubbed["tool"] < verbatim["tool"]
    assert stubbed["user"] == verbatim["user"]      # only the tool bucket moves


def test_the_example_payload_shrinks_by_an_order_of_magnitude(conn):
    """The `payload example sizes` artifact of spec-v1.3 section 15 (TC2)."""
    conv = conversation(conn)
    verbatim = len(json.dumps(assemble(conn, conv, stub_tool_results=False),
                              ensure_ascii=False))
    stubbed = len(json.dumps(assemble(conn, conv), ensure_ascii=False))
    assert verbatim > 3500
    assert stubbed * 5 < verbatim
