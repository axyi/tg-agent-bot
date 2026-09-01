"""Structured conversation summaries, schema migration 1 -> 2, recent goals."""

import json
import sqlite3

import pytest

import agent
import bot
import config
import storage
from llm.base import LLMResponse
from tests.fakes import FakeLLM, RecordingRunner

TOKEN = "123456789:sentinel-telegram-token-for-summary-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"

# The v0 DDL, verbatim: what a version-1 database on disk looks like.
V0_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 1);

CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER NOT NULL,
    created_at TEXT    NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_one_active
    ON conversations (tg_user_id) WHERE active = 1;

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id         INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    turn_id         INTEGER NOT NULL,
    role            TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content         TEXT    NOT NULL DEFAULT '',
    tool_calls_json TEXT,
    tool_call_id    TEXT,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

VALID_SUMMARY = {
    "goal": "Ship the docker sandbox",
    "files": ["tools.py", "bot.py"],
    "decisions": ["Use one pinned public image"],
    "errors": ["docker exit 125 while the daemon was down"],
    "next_action": "Run the gates",
}


def make_cfg(tmp_path, **overrides):
    return config.Config(
        telegram_bot_token=TOKEN,
        allowed_tg_ids=frozenset({USER_ID}),
        llm_provider="lmstudio",
        lmstudio_base_url="http://localhost:1234/v1",
        lmstudio_model="m",
        openrouter_api_key="",
        openrouter_model="",
        llm_timeout_s=120.0,
        exec_workdir=tmp_path / "sandbox",
        db_path=tmp_path / "bot.db",
        audit_log_path=tmp_path / "audit.jsonl",
        **overrides,
    )


def update(text, update_id=1):
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": USER_ID, "type": "private"},
            "from": {"id": USER_ID, "is_bot": False},
            "text": text,
        },
    }


class RecordingTelegram:
    def __init__(self):
        self.sent = []

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))
        return {"message_id": len(self.sent)}


def process(conn, cfg, text, llm, update_id=1):
    tg = RecordingTelegram()
    bot.process_update(
        update(text, update_id),
        conn=conn, tg=tg, cfg=cfg, llm=llm, skills={},
        runner=RecordingRunner(), bot_username=BOT_USERNAME,
    )
    return tg.sent


def seed(conn, *messages):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    for role, content in messages:
        if role == "user":
            storage.add_user_message(conn, conv, content)
        else:
            storage.add_assistant_message(conn, conv, content)
    return conv


def scripted(payload):
    return FakeLLM([LLMResponse(payload, [], "stop")])


def test_t_v1_sum_01_migration_from_version_one(tmp_path):
    path = tmp_path / "legacy.db"
    legacy = sqlite3.connect(str(path), isolation_level=None)
    legacy.executescript(V0_SCHEMA)
    legacy.execute(
        "INSERT INTO conversations (tg_user_id, created_at, active) VALUES (7, 'x', 1)"
    )
    legacy.close()

    conn = storage.connect(path)
    storage.init_schema(conn)
    assert storage.schema_version(conn) == 2
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'summaries'"
    ).fetchone() is not None
    # The migration is additive: existing rows survive.
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 1

    storage.init_schema(conn)
    assert storage.schema_version(conn) == 2
    conn.close()

    ahead = storage.connect(path)
    ahead.execute("UPDATE schema_version SET version = 3 WHERE id = 1")
    with pytest.raises(RuntimeError) as raised:
        storage.init_schema(ahead)
    assert "3" in str(raised.value)
    ahead.close()


def test_t_v1_sum_01_fresh_database_is_version_two(conn):
    assert storage.schema_version(conn) == 2
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_summary(conn, conv, USER_ID, json.dumps(VALID_SUMMARY))
    storage.add_summary(conn, conv, USER_ID, json.dumps(dict(VALID_SUMMARY, goal="second")))
    assert json.loads(storage.get_summary(conn, conv))["goal"] == "second"


def test_t_v1_sum_02_new_summarizes_before_resetting(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    conv = seed(conn, ("user", "how do I ship it"), ("assistant", "like this"))
    llm = scripted(json.dumps(VALID_SUMMARY))

    assert process(conn, cfg, "/new", llm) == [(USER_ID, "New conversation started.")]

    assert llm.max_tokens_calls == [512]
    assert llm.calls[0][1] is None                    # no tools are exposed
    assert llm.calls[0][0][-1]["content"] == agent.SUMMARY_PROMPT

    stored = json.loads(storage.get_summary(conn, conv))
    assert set(stored) == {"goal", "files", "decisions", "errors", "next_action"}
    assert stored["goal"] == VALID_SUMMARY["goal"]
    assert stored["files"] == ["tools.py", "bot.py"]

    assert storage.get_or_create_active_conversation(conn, USER_ID) != conv


def test_t_v1_sum_02_new_without_history_does_not_call_the_model(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    seed(conn, ("user", "only one message"))
    llm = FakeLLM([])
    assert process(conn, cfg, "/new", llm) == [(USER_ID, "New conversation started.")]
    assert llm.calls == []


def test_t_v1_sum_02_extra_keys_are_dropped_and_types_coerced(conn, tmp_path):
    llm = FakeLLM([LLMResponse(json.dumps({
        "goal": "keep going",
        "files": "not-an-array",
        "decisions": ["a", 2],
        "errors": [],
        "next_action": None,
        "surprise": "dropped",
    }), [], "stop")])
    conv = seed(conn, ("user", "a"), ("assistant", "b"))
    result = json.loads(agent.summarize_conversation(conn, conv, llm, make_cfg(tmp_path)))
    assert set(result) == {"goal", "files", "decisions", "errors", "next_action"}
    assert result["files"] == []
    assert result["decisions"] == ["a", "2"]
    assert result["next_action"] == ""


def test_t_v1_sum_03_unparsable_summary_never_blocks_new(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    conv = seed(conn, ("user", "a"), ("assistant", "b"))
    llm = FakeLLM([LLMResponse("not json", [], "stop"), LLMResponse("still not", [], "stop")])

    assert process(conn, cfg, "/new", llm) == [(USER_ID, "New conversation started.")]
    assert len(llm.calls) == 2
    assert "not valid JSON" in llm.calls[1][0][-1]["content"]
    assert storage.get_summary(conn, conv) is None
    assert storage.get_or_create_active_conversation(conn, USER_ID) != conv


def test_t_v1_sum_03_fenced_json_is_repaired(conn, tmp_path):
    conv = seed(conn, ("user", "a"), ("assistant", "b"))
    fenced = "```json\n" + json.dumps(VALID_SUMMARY) + "\n```"
    llm = scripted(fenced)
    result = agent.summarize_conversation(conn, conv, llm, make_cfg(tmp_path))
    assert json.loads(result)["goal"] == VALID_SUMMARY["goal"]
    assert len(llm.calls) == 1                        # the fence strip needs no retry


def test_t_v1_sum_04_summary_command(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    conv = seed(conn, ("user", "a"), ("assistant", "b"))
    sent = process(conn, cfg, "/summary", scripted(json.dumps(VALID_SUMMARY)))
    assert sent == [(USER_ID, (
        "Goal: Ship the docker sandbox\n"
        "Files: tools.py; bot.py\n"
        "Decisions: Use one pinned public image\n"
        "Errors: docker exit 125 while the daemon was down\n"
        "Next: Run the gates"
    ))]
    assert storage.get_summary(conn, conv) is not None
    # The active conversation is untouched by /summary.
    assert storage.get_or_create_active_conversation(conn, USER_ID) == conv

    empty = dict(VALID_SUMMARY, files=[], decisions=[], errors=[], next_action="")
    sent = process(conn, cfg, "/summary", scripted(json.dumps(empty)), update_id=2)
    assert sent[0][1].splitlines()[1:] == [
        "Files: -", "Decisions: -", "Errors: -", "Next: "
    ]

    failing = FakeLLM([LLMResponse("nope", [], "stop"), LLMResponse("nope", [], "stop")])
    assert process(conn, cfg, "/summary", failing, update_id=3) == [
        (USER_ID, "Could not summarize this conversation right now.")
    ]


def test_t_v1_sum_04_summary_needs_two_messages(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    seed(conn, ("user", "hello"))
    llm = FakeLLM([])
    assert process(conn, cfg, "/summary", llm) == [(USER_ID, "Nothing to summarize yet.")]
    assert llm.calls == []


def test_t_v1_sum_05_recent_goals_reach_the_system_prompt(conn):
    conv_ids = []
    for index in range(4):
        conv = storage.start_new_conversation(conn, USER_ID)
        conv_ids.append(conv)
        storage.add_summary(
            conn, conv, USER_ID,
            json.dumps(dict(VALID_SUMMARY, goal=f"goal {index} " + "x" * 300)),
        )
    # A summary whose JSON has no string goal is skipped, not rendered as "None".
    skipped = storage.start_new_conversation(conn, USER_ID)
    storage.add_summary(conn, skipped, USER_ID, json.dumps({"files": []}))

    # The newest three summaries are read; the goal-less one among them is skipped,
    # so two goals survive, newest first.
    goals = storage.recent_goals(conn, USER_ID)
    assert len(goals) == 2
    assert goals[0].startswith("goal 3 ")
    assert goals[1].startswith("goal 2 ")
    assert all(len(goal) == 200 for goal in goals)
    assert storage.recent_goals(conn, 999) == []
    assert len(storage.recent_goals(conn, USER_ID, limit=5)) == 4

    prompt = agent.build_system_prompt({}, "2026-09-01T00:00:00Z", recent_goals=goals)
    assert "Recent conversation goals" in prompt
    for goal in goals:
        assert f"- {goal}" in prompt


def test_t_v1_sum_05_goal_block_is_dropped_when_the_budget_is_tiny(conn, tmp_path):
    class BudgetedLLM(FakeLLM):
        context_length = 2048

    goals = ["remember the sandbox layout"]
    conv = seed(conn, ("user", "hi"))
    cfg = make_cfg(tmp_path, llm_max_tokens=1500)

    tight = BudgetedLLM([LLMResponse("ok", [], "stop")])
    agent.run_agent(
        conn=conn, conv_id=conv, llm=tight, skills={}, runner=RecordingRunner(),
        now="2026-09-01T00:00:00Z", cfg=cfg, recent_goals=goals,
    )
    system = tight.calls[0][0][0]["content"]
    assert "Recent conversation goals" not in system
    assert goals[0] not in system

    roomy = BudgetedLLM([LLMResponse("ok", [], "stop")])
    roomy.context_length = 42496
    agent.run_agent(
        conn=conn, conv_id=conv, llm=roomy, skills={}, runner=RecordingRunner(),
        now="2026-09-01T00:00:00Z", cfg=cfg, recent_goals=goals,
    )
    assert "Recent conversation goals" in roomy.calls[0][0][0]["content"]
