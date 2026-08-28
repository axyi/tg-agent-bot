"""The bounded agent loop: system prompt, tool-call normalisation, budgets.

Every budget below is per incoming user message. Nothing here is unbounded: the
loop always terminates and always stores the text it returns.
"""

import json
import logging
import sqlite3
import time
from collections.abc import Callable

import storage
from llm.base import LLMClient, LLMError, ToolCall
from tools import CommandRunner, Skill, execute_tool, tool_specs

ROUND_LIMIT = 8               # logical rounds per user message
TOOL_ROUND_LIMIT = 7          # rounds 1..7 may expose tools
HTTP_ATTEMPT_LIMIT = 9        # total calls to llm.complete per user message
TOOL_EXECUTION_LIMIT = 12     # total tool executions per user message
MAX_TOOL_CALLS_PER_RESPONSE = 3    # how many are executed
MAX_TOOL_CALLS_ACCEPTED = 8        # how many are kept at all (bounds the turn group)
RETRY_SLEEP_S = 2.0

CONTEXT_WINDOW_MESSAGES = 30

FALLBACK_EMPTY = "The model returned an empty answer. Please rephrase your message."
FALLBACK_NO_ANSWER = ("I could not produce an answer within the allowed number of steps. "
                      "Please try a simpler request.")
FALLBACK_LLM_ERROR = (
    "The language model is unavailable right now: {reason}. Please try again later."
)
FINAL_INSTRUCTION = ("Tool use is finished. Answer the user now, in plain text, "
                     "using the information you already have.")

BUDGET_EXHAUSTED_RESULT = json.dumps({"error": "tool budget exhausted for this message; "
                                               "answer with the information you already have"})
EXCESS_CALL_RESULT = json.dumps({"error": "too many tool calls in one response; only "
                                          "the first 3 are executed. This call was not executed."})

SYSTEM_PROMPT = """You are a Telegram assistant agent running on a Linux host.
Current date and time (UTC): {current_datetime}

Answer in the language of the user's message. Your replies are delivered as
plain Telegram text: no Markdown, no HTML, no code fences, no tables.

Tools available to you:
- exec(argv): runs one program directly on the host. It is NOT a shell. Pipes,
  redirection, globbing, variable expansion and command chaining do not work.
  Pass the program name and every argument as separate array elements.
- load_skill(name): returns the full instructions of one installed skill.

Rules:
- If a skill covers the topic, call load_skill with that skill's name first and
  then follow its instructions exactly.
- Never invent command output. If a tool returns an error, say so.
- At most 3 tool calls per reply; additional calls are rejected unexecuted.
- When you have enough information, reply in plain text with no tool calls.

Installed skills:
{skill_lines}
"""

log = logging.getLogger("agent")


def build_system_prompt(skills: dict[str, Skill], now: str) -> str:
    if skills:
        skill_lines = "\n".join(
            f"- {skill.name}: {skill.description}"
            for skill in sorted(skills.values(), key=lambda skill: skill.name)
        )
    else:
        skill_lines = "- (none)"
    return SYSTEM_PROMPT.format(current_datetime=now, skill_lines=skill_lines)


def normalize_tool_calls(calls: list[ToolCall]) -> list[ToolCall]:
    """Truncate to the accept cap, then give every kept call a unique id."""
    if len(calls) > MAX_TOOL_CALLS_ACCEPTED:
        log.warning(
            "response carried %d tool calls; kept the first %d",
            len(calls),
            MAX_TOOL_CALLS_ACCEPTED,
        )
    normalized: list[ToolCall] = []
    seen: set[str] = set()
    for index, raw in enumerate(calls[:MAX_TOOL_CALLS_ACCEPTED]):
        call_id = raw.id.strip()
        if not call_id or call_id in seen:
            call_id = f"auto_{index}"
        while call_id in seen:
            call_id = call_id + "_"
        seen.add(call_id)
        normalized.append(ToolCall(id=call_id, name=raw.name.strip(), arguments=raw.arguments))
    return normalized


def run_agent(
    *,
    conn: sqlite3.Connection,
    conv_id: int,
    llm: LLMClient,
    skills: dict[str, Skill],
    runner: CommandRunner,
    now: str,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    def finish(text: str) -> str:
        storage.add_assistant_message(conn, conv_id, text)
        return text

    messages: list[dict] = [{"role": "system", "content": build_system_prompt(skills, now)}]
    messages += storage.load_context_messages(conn, conv_id, CONTEXT_WINDOW_MESSAGES)

    round_no = 1
    attempts = 0
    tools_used = 0

    while round_no <= ROUND_LIMIT:
        expose_tools = round_no <= TOOL_ROUND_LIMIT and tools_used < TOOL_EXECUTION_LIMIT
        if expose_tools:
            request_messages = messages
            request_tools = tool_specs()
        else:
            request_messages = messages + [{"role": "system", "content": FINAL_INSTRUCTION}]
            request_tools = None

        try:
            attempts += 1
            response = llm.complete(request_messages, request_tools)
        except LLMError as exc:
            if exc.retryable and attempts < HTTP_ATTEMPT_LIMIT:
                sleep(RETRY_SLEEP_S)
                continue                      # same round, same tool policy
            return finish(FALLBACK_LLM_ERROR.format(reason=str(exc)))

        has_content = bool(response.content.strip())
        if not response.tool_calls:
            if has_content:
                return finish(response.content)
            return finish(FALLBACK_EMPTY if expose_tools else FALLBACK_NO_ANSWER)
        if not expose_tools:
            # Tool calls are discarded unexecuted and never stored.
            log.info("discarded %d tool calls offered without tools", len(response.tool_calls))
            return finish(response.content if has_content else FALLBACK_NO_ANSWER)

        normalized = normalize_tool_calls(response.tool_calls)
        results, tools_used = _execute_tool_calls(
            normalized, skills=skills, runner=runner, tools_used=tools_used
        )
        wire_tool_calls = [_to_wire(call) for call in normalized]
        storage.add_tool_turn(conn, conv_id, response.content, wire_tool_calls, results)
        messages.append(
            {"role": "assistant", "content": response.content, "tool_calls": wire_tool_calls}
        )
        for call_id, result in results:
            messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
        round_no += 1

    return finish(FALLBACK_NO_ANSWER)         # defensive; normally unreachable


def _execute_tool_calls(
    normalized: list[ToolCall],
    *,
    skills: dict[str, Skill],
    runner: CommandRunner,
    tools_used: int,
) -> tuple[list[tuple[str, str]], int]:
    executable = normalized[:MAX_TOOL_CALLS_PER_RESPONSE]
    excess = normalized[MAX_TOOL_CALLS_PER_RESPONSE:]
    results: list[tuple[str, str]] = []
    for call in executable:
        if tools_used < TOOL_EXECUTION_LIMIT:
            result = execute_tool(call.name, call.arguments, skills=skills, runner=runner)
            tools_used += 1
        else:
            result = BUDGET_EXHAUSTED_RESULT
        results.append((call.id, result))
    for call in excess:
        results.append((call.id, EXCESS_CALL_RESULT))
    return results, tools_used


def _to_wire(call: ToolCall) -> dict:
    return {
        "id": call.id,
        "type": "function",
        "function": {"name": call.name, "arguments": call.arguments},
    }
