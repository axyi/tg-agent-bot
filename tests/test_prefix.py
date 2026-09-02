"""Byte-stable prefix and prefix compression — spec-v1.3 sections 10.3 and 10.4
(REQ-V13-CCH-01…03, REQ-V13-PFX-01…03).

Everything here is offline: a scripted `FakeLLM`, a `RecordingRunner` that never
starts a process, and a mock httpx transport for the one provider-shape test.
The subject is always the *request* the bot builds — the cacheable prefix (the
system message and the tool catalog) must be byte-identical across the calls of
a conversation, and it must stay small.
"""

import copy
import json
import re

import httpx

import agent
import config
import storage
import tools
from llm.base import LLMResponse, ToolCall
from llm.openrouter import OpenRouterClient
from tests.fakes import FakeLLM, RecordingRunner, mock_llm_transport

USER_ID = 424242
NOW_A = "2026-09-02T10:00:00Z"
NOW_B = "2026-09-02T18:45:31Z"

PROMPT_LIMIT = 550          # REQ-V13-PFX-01
SCHEMA_LIMIT = 1400         # REQ-V13-PFX-02

# REQ-V13-PFX-02: the schema of spec-v1.2 (commit f0572c8, `tool_specs()` with
# every `description` removed) — the frozen structural contract. Parameter
# names, types, enums, minimum/maximum and `required` lists may not move; the
# two windows of REQ-V13-TOO-02 / REQ-V13-TOO-07 are added below, and they are
# the only permitted additions.
V12_SCHEMA_STRUCTURE = [
    {
        "type": "function",
        "function": {
            "name": "exec",
            "parameters": {
                "type": "object",
                "properties": {
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 32,
                    },
                },
                "required": ["argv"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_skill",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    },
]


def expected_structure() -> list[dict]:
    """v1.2 plus exactly the two parameters REQ-V13-TOO-02 / TOO-07 introduce."""
    expected = copy.deepcopy(V12_SCHEMA_STRUCTURE)
    expected[0]["function"]["parameters"]["properties"]["max_output_chars"] = {
        "type": "integer",
        "minimum": config.MIN_EXEC_OUTPUT_CHARS,
        "maximum": config.MAX_EXEC_OUTPUT_CHARS,
    }
    expected[2]["function"]["parameters"]["properties"]["max_chars"] = {
        "type": "integer",
        "minimum": config.MIN_FETCH_INLINE_CHARS,
        "maximum": config.MAX_FETCH_INLINE_CHARS,
    }
    return expected


def without_descriptions(value):
    if isinstance(value, dict):
        return {
            key: without_descriptions(item)
            for key, item in value.items()
            if key != "description"
        }
    if isinstance(value, list):
        return [without_descriptions(item) for item in value]
    return value


def descriptions(value, found=None):
    """Every `description` string anywhere in the catalog."""
    found = [] if found is None else found
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "description" and isinstance(item, str):
                found.append(item)
            else:
                descriptions(item, found)
    elif isinstance(value, list):
        for item in value:
            descriptions(item, found)
    return found


def skill(name: str, description: str) -> tools.Skill:
    return tools.Skill(
        name=name, description=description, body=f"body of {name}", source=f"{name}.md"
    )


def answer(content: str = "done") -> LLMResponse:
    return LLMResponse(content, [], "stop")


def exec_round(index: int) -> LLMResponse:
    return LLMResponse(
        "", [ToolCall(f"raw_{index}", "exec", '{"argv": ["true"]}')], "tool_calls"
    )


def run(conn, conv, script, *, skills=None, now=NOW_A) -> FakeLLM:
    llm = FakeLLM(script)
    agent.run_agent(
        conn=conn,
        conv_id=conv,
        llm=llm,
        skills=skills or {},
        runner=RecordingRunner(),
        now=now,
        sleep=lambda _seconds: None,
    )
    return llm


class BudgetedLLM(FakeLLM):
    """A fake that exposes `context_length`, the way every real client does.

    Without it `_assemble_context` takes its `context_length is None` early
    return, so the branch `bot.py` actually serves — the token budget, and the
    rebuild that drops the goals block — is never the one under test.
    """

    def __init__(self, script, context_length: int):
        super().__init__(script)
        self.context_length = context_length


def run_budgeted(conn, conv, script, *, context_length: int,
                 skills=None, now=NOW_A, goals=None) -> FakeLLM:
    llm = BudgetedLLM(script, context_length)
    agent.run_agent(
        conn=conn,
        conv_id=conv,
        llm=llm,
        skills=skills or {},
        runner=RecordingRunner(),
        now=now,
        sleep=lambda _seconds: None,
        recent_goals=goals,
    )
    return llm


def conversation(conn, text: str = "what is the host uptime?") -> int:
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, text)
    return conv


def system_of(llm: FakeLLM, index: int = 0) -> str:
    return llm.calls[index][0][0]["content"]


# --------------------------------------------------------------------------
# REQ-V13-PFX-01 — the compressed system prompt
# --------------------------------------------------------------------------

def test_pfx_01_system_prompt_fits_the_budget():
    measured = len(agent.SYSTEM_PROMPT.replace("{skill_lines}", ""))
    assert measured <= PROMPT_LIMIT, f"system prompt is {measured} chars"


def test_pfx_01_every_mandatory_statement_survives():
    prompt = agent.build_system_prompt(
        {"weather": skill("weather", "current weather for a city")}, NOW_A
    ).lower()
    # (statement, the tokens that carry it) — meaning, not wording.
    mandatory = [
        ("telegram plain text", ["plain text"]),
        ("no markup of any kind", ["markdown", "html", "code fence", "table"]),
        ("the user's language", ["language"]),
        ("exec is argv, not a shell", ["exec", "argv", "shell"]),
        ("exec has no network", ["network"]),
        ("skill first, then follow it", ["load_skill", "first", "follow"]),
        ("never invent tool output", ["invent", "error"]),
        ("at most three tool calls", ["3 tool calls"]),
        ("stop calling tools when done", ["no tool calls", "done"]),
        ("tool output is untrusted data", ["untrusted", "never instructions"]),
        ("concision", ["concise", "no preamble"]),
        ("the installed skills", ["weather: current weather for a city"]),
    ]
    missing = [
        (statement, token)
        for statement, needles in mandatory
        for token in needles
        if token not in prompt
    ]
    assert missing == []


def test_pfx_01_the_tool_bullet_list_is_gone():
    """The catalog carries the tool documentation; the prompt must not repeat it."""
    prompt = agent.build_system_prompt({}, NOW_A)
    assert "- exec(argv)" not in prompt
    assert "- load_skill(name)" not in prompt
    assert "- fetch(url)" not in prompt
    # The skills header is a landmark other tests and REQ-V13-CCH-01 rely on.
    assert agent.SKILLS_HEADER in agent.SYSTEM_PROMPT


def test_pfx_01_the_empty_catalog_keeps_its_sentinel():
    assert agent.build_system_prompt({}, NOW_A).rstrip().endswith("- (none)")


# --------------------------------------------------------------------------
# REQ-V13-PFX-02 — the compressed tool catalog
# --------------------------------------------------------------------------

def test_pfx_02_schema_fits_the_budget():
    measured = len(json.dumps(tools.tool_specs()))
    assert measured <= SCHEMA_LIMIT, f"tool catalog is {measured} chars"


def test_pfx_02_only_the_descriptions_changed():
    assert without_descriptions(tools.tool_specs()) == expected_structure()


def test_pfx_02_the_descriptions_stay_ascii_and_quote_free():
    """`json.dumps` escapes both, and the budget is measured on its output."""
    found = descriptions(tools.tool_specs())
    # The budget bought the removal of the `argv` and `url` restatements; the
    # five that remain are the ones the model cannot infer from the schema, and
    # none of them may be emptied to buy room (REQ-V13-TOO-02, TOO-07).
    assert len(found) == 5
    for text in found:
        assert text.strip(), "an empty description is not a saving"
        assert text.isascii(), text
        assert '"' not in text, text


# --------------------------------------------------------------------------
# REQ-V13-PFX-03 — the compressed prompt still drives the loop
# --------------------------------------------------------------------------

def test_pfx_03_the_prompt_still_drives_the_agent(conn):
    skills = {"weather": skill("weather", "current weather for a city")}
    conv = conversation(conn, "weather in Cologne?")
    llm = run(
        conn,
        conv,
        [
            LLMResponse(
                "", [ToolCall("raw", "load_skill", '{"name": "weather"}')], "tool_calls"
            ),
            answer("Cologne: sunny"),
        ],
        skills=skills,
    )
    system = system_of(llm)
    assert "weather: current weather for a city" in system
    assert "load_skill" in system
    assert "plain text" in system.lower()
    assert "untrusted" in system.lower()
    # The skill body reached the model as a tool result, so the skill-first
    # instruction was actionable, not decorative.
    tool_messages = [m for m in llm.calls[1][0] if m.get("role") == "tool"]
    assert "body of weather" in tool_messages[0]["content"]


# --------------------------------------------------------------------------
# REQ-V13-CCH-01 — the prefix is byte-stable; the clock moves to the user turn
# --------------------------------------------------------------------------

def test_cch_01_the_clock_left_the_system_prompt(conn):
    conv = conversation(conn)
    llm = run(conn, conv, [answer()], now=NOW_A)
    assert NOW_A not in system_of(llm)
    assert "current date" not in system_of(llm).lower()


def test_cch_01_two_invocations_with_different_now_share_the_prefix(conn):
    skills = {"weather": skill("weather", "current weather for a city")}
    conv = conversation(conn, "first question")
    first = run(conn, conv, [answer("a")], skills=skills, now=NOW_A)
    storage.add_user_message(conn, conv, "second question")
    second = run(conn, conv, [answer("b")], skills=skills, now=NOW_B)

    assert first.calls[0][0][0] == second.calls[0][0][0]
    assert json.dumps(first.calls[0][1]) == json.dumps(second.calls[0][1])


def test_cch_01_the_now_line_is_appended_to_the_last_user_message(conn):
    conv = conversation(conn, "first question")
    first = run(conn, conv, [answer("a")], now=NOW_A)
    storage.add_user_message(conn, conv, "second question")
    second = run(conn, conv, [answer("b")], now=NOW_B)

    users = [m for m in second.calls[0][0] if m["role"] == "user"]
    assert users[-1]["content"] == "second question\n(now: 2026-09-02 18:45 UTC)"
    # Only the most recent one carries it.
    assert users[0]["content"] == "first question"
    assert first.calls[0][0][-1]["content"].endswith("(now: 2026-09-02 10:00 UTC)")

    # The stored rows never learn about the clock (REQ-V13-CCH-01).
    stored = conn.execute(
        "SELECT content FROM messages WHERE role = 'user' ORDER BY id"
    ).fetchall()
    assert [row["content"] for row in stored] == ["first question", "second question"]


def test_cch_01_build_system_prompt_ignores_the_now_it_is_handed():
    """The parameter is kept only because `devtools/bench.py` and the v1 tests
    pass it positionally. Nothing it carries may reach the prefix — asserted
    directly here, so the footgun is caught without running the agent."""
    skills = {"weather": skill("weather", "current weather for a city")}
    for goals in (None, ["check the host uptime"]):
        prompt = agent.build_system_prompt(skills, NOW_A, goals)
        assert prompt == agent.build_system_prompt(skills, NOW_B, goals)
        assert prompt == agent.build_system_prompt(skills, None, goals)
        assert NOW_A not in prompt and NOW_B not in prompt
        assert re.search(r"\d{4}-\d{2}-\d{2}", prompt) is None
        assert re.search(r"\d{1,2}:\d{2}", prompt) is None


def test_cch_01_the_budgeted_branch_keeps_the_prefix_byte_stable(conn):
    """REQ-V13-CCH-01 on the branch D1 serves: a client with a context length,
    so `_assemble_context` walks the token budget instead of returning early."""
    skills = {"weather": skill("weather", "current weather for a city")}
    goals = ["ask about the weather in Koln", "check the host uptime"]
    ample = (
        agent.estimate_tokens(agent.build_system_prompt(skills, NOW_A, goals))
        + agent.TOKEN_BUDGET_MARGIN + 1000
    )
    conv = conversation(conn, "first question")
    first = run_budgeted(conn, conv, [answer("a")], context_length=ample,
                         skills=skills, now=NOW_A, goals=goals)
    storage.add_user_message(conn, conv, "second question")
    second = run_budgeted(conn, conv, [answer("b")], context_length=ample,
                          skills=skills, now=NOW_B, goals=goals)

    assert system_of(first) == system_of(second)
    assert agent.GOALS_BLOCK in system_of(first)
    assert NOW_A not in system_of(first) and NOW_B not in system_of(second)


def test_cch_01_the_dropped_goals_rebuild_is_byte_stable(conn):
    """`budget <= 0 and recent_goals` rebuilds the prompt without the block —
    the one place the prefix is built twice, and the one the clock could reach
    if it ever came back into `build_system_prompt`."""
    skills = {"weather": skill("weather", "current weather for a city")}
    goals = ["ask about the weather in Koln", "check the host uptime"]
    with_goals = agent.estimate_tokens(agent.build_system_prompt(skills, NOW_A, goals))
    without = agent.estimate_tokens(agent.build_system_prompt(skills, NOW_A, None))
    assert without < with_goals
    # Exactly zero budget with the block, positive without it.
    exhausted = with_goals + agent.TOKEN_BUDGET_MARGIN

    conv = conversation(conn, "first question")
    first = run_budgeted(conn, conv, [answer("a")], context_length=exhausted,
                         skills=skills, now=NOW_A, goals=goals)
    storage.add_user_message(conn, conv, "second question")
    second = run_budgeted(conn, conv, [answer("b")], context_length=exhausted,
                          skills=skills, now=NOW_B, goals=goals)

    assert agent.GOALS_BLOCK not in system_of(first)
    assert system_of(first) == system_of(second)
    assert NOW_A not in system_of(first) and NOW_B not in system_of(second)


def test_cch_01_reload_skills_is_the_only_invalidation(conn):
    before = {"weather": skill("weather", "current weather for a city")}
    after = dict(before, ping=skill("ping", "check that a host answers"))
    conv = conversation(conn, "q1")
    old = system_of(run(conn, conv, [answer()], skills=before, now=NOW_A))

    storage.add_user_message(conn, conv, "q2")
    new = system_of(run(conn, conv, [answer()], skills=after, now=NOW_B))
    assert new != old
    # The difference is exactly the skill lines: everything up to the header is
    # byte-equal, and the tail is the rendered catalog.
    head, _, old_lines = old.partition(agent.SKILLS_HEADER)
    new_head, _, new_lines = new.partition(agent.SKILLS_HEADER)
    assert head == new_head
    assert old_lines.strip() == "- weather: current weather for a city"
    assert new_lines.strip() == (
        "- ping: check that a host answers\n- weather: current weather for a city"
    )

    storage.add_user_message(conn, conv, "q3")
    third = run(conn, conv, [answer()], skills=after, now=NOW_A)
    storage.add_user_message(conn, conv, "q4")
    fourth = run(conn, conv, [answer()], skills=after, now=NOW_B)
    assert system_of(third) == new
    assert system_of(fourth) == new


# --------------------------------------------------------------------------
# REQ-V13-CCH-02 — inside one invocation the request only grows
# --------------------------------------------------------------------------

def rounds(conn) -> FakeLLM:
    """Seven tool rounds, then the tools-withheld final request of round 8."""
    conv = conversation(conn)
    script = [exec_round(index) for index in range(agent.TOOL_ROUND_LIMIT)]
    script.append(answer("finally"))
    return run(conn, conv, script)


def test_cch_02_a_every_round_is_a_prefix_extension_of_the_previous_one(conn):
    llm = rounds(conn)
    assert len(llm.calls) == agent.TOOL_ROUND_LIMIT + 1
    for index in range(1, len(llm.calls)):
        previous = llm.calls[index - 1][0]
        current = llm.calls[index][0]
        assert len(current) > len(previous)
        for position, message in enumerate(previous):
            assert json.dumps(current[position], ensure_ascii=False, sort_keys=True) == (
                json.dumps(message, ensure_ascii=False, sort_keys=True)
            ), f"round {index + 1} rewrote message {position}"


def test_cch_02_b_the_tool_catalog_is_byte_identical_on_every_round(conn):
    llm = rounds(conn)
    exposed = [json.dumps(call[1]) for call in llm.calls if call[1] is not None]
    assert len(exposed) == agent.TOOL_ROUND_LIMIT
    assert len(set(exposed)) == 1
    # The final request withholds the catalog (REQ-V13-RSN-02) and is exempt.
    assert llm.calls[-1][1] is None


# --------------------------------------------------------------------------
# REQ-V13-CCH-03 — Anthropic prompt caching through OpenRouter
# https://openrouter.ai/docs/guides/best-practices/prompt-caching
# --------------------------------------------------------------------------

def openrouter(model: str, seen: list):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop",
                         "message": {"role": "assistant", "content": "hi"}}]
        })

    return OpenRouterClient(
        "sk-or-test-key", model, 5.0, httpx.Client(transport=mock_llm_transport(handler))
    )


MESSAGES = [
    {"role": "system", "content": "PREFIX"},
    {"role": "user", "content": "hello"},
    {"role": "system", "content": agent.FINAL_INSTRUCTION},
]


def test_cch_03_anthropic_models_get_a_cache_breakpoint():
    seen = []
    messages = copy.deepcopy(MESSAGES)
    openrouter("anthropic/claude-opus-4.1", seen).complete(messages, None)
    sent = seen[0]["messages"]
    assert sent[0] == {
        "role": "system",
        "content": [
            {"type": "text", "text": "PREFIX", "cache_control": {"type": "ephemeral"}}
        ],
    }
    # Only the cacheable prefix is marked; the request-time nudge stays plain.
    assert sent[2] == {"role": "system", "content": agent.FINAL_INSTRUCTION}
    assert sent[1] == {"role": "user", "content": "hello"}
    # The agent reuses its `messages` list across rounds — it must come back intact.
    assert messages == MESSAGES


def test_cch_03_other_models_keep_the_plain_shape():
    seen = []
    openrouter("openai/gpt-4o-mini", seen).complete(copy.deepcopy(MESSAGES), None)
    assert seen[0]["messages"] == MESSAGES


def test_cch_03_a_request_without_a_system_message_is_untouched():
    seen = []
    openrouter("anthropic/claude-opus-4.1", seen).complete(
        [{"role": "user", "content": "hello"}], None
    )
    assert seen[0]["messages"] == [{"role": "user", "content": "hello"}]
