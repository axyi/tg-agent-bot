"""Entry point: Telegram long polling, update dispatch and the offline selftest.

The process is single-threaded and sequential: updates are handled strictly one
at a time. The only threads are the two output readers created per `exec` call.
"""

import functools
import json
import logging
import random
import signal
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import httpx

import agent
import storage
import tools
from config import PROJECT_ROOT, Config, ConfigError, load_config, redact
from llm import build_llm_client
from llm.base import LLMResponse, ToolCall

TELEGRAM_API_HOST = "https://api.telegram.org"
LONG_POLL_TIMEOUT_S = 50
GET_UPDATES_READ_TIMEOUT_S = 60.0
DEFAULT_READ_TIMEOUT_S = 20.0
MESSAGE_LIMIT = 4096
MAX_BACKOFF_S = 30.0

NON_TEXT_REPLY = "I can only process plain text messages."
NEW_CONVERSATION_REPLY = "New conversation started."
USAGE = "usage: bot.py [--selftest]"

log = logging.getLogger("bot")

# httpx logs every request URL at INFO. The Telegram URL embeds the bot token,
# which must never reach a log record, redacted or not (REQ-CFG-04).
logging.getLogger("httpx").setLevel(logging.WARNING)

_shutdown = False


class TelegramError(Exception):
    def __init__(
        self, message: str, *, retry_after: float | None = None, fatal: bool = False
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.fatal = fatal


class TelegramClient:
    def __init__(self, token: str, *, client: httpx.Client) -> None:
        self._token = token
        self._client = client

    def call(self, method: str, payload: dict, *, read_timeout: float) -> dict:
        # The URL embeds the bot token: never log it, redacted or not.
        url = f"{TELEGRAM_API_HOST}/bot{self._token}/{method}"
        timeout = httpx.Timeout(connect=10.0, read=read_timeout, write=10.0, pool=10.0)
        try:
            response = self._client.post(url, json=payload, timeout=timeout)
        except httpx.TransportError as exc:
            raise TelegramError(
                redact(f"telegram {method} transport error: {exc.__class__.__name__}")
            ) from None

        status = response.status_code
        if status in (401, 404):
            raise TelegramError(
                redact(f"telegram {method} rejected the bot token"), fatal=True
            )
        if status == 429:
            raise TelegramError(
                redact(f"telegram {method} rate limited"), retry_after=_retry_after(response)
            )
        if status != 200:
            raise TelegramError(redact(f"telegram {method} http {status}"))

        try:
            data = response.json()
        except ValueError:
            raise TelegramError(redact(f"telegram {method} returned non-json")) from None
        if not isinstance(data, dict) or data.get("ok") is not True:
            code = data.get("error_code") if isinstance(data, dict) else None
            description = data.get("description") if isinstance(data, dict) else ""
            raise TelegramError(
                redact(f"telegram {method} api error {code}: {description}"),
                retry_after=_retry_after(response) if code == 429 else None,
            )
        return data["result"]

    def get_me(self) -> dict:
        return self.call("getMe", {}, read_timeout=DEFAULT_READ_TIMEOUT_S)

    def get_updates(self, offset: int | None) -> list[dict]:
        payload = {"timeout": LONG_POLL_TIMEOUT_S, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload, read_timeout=GET_UPDATES_READ_TIMEOUT_S)

    def send_message(self, chat_id: int, text: str) -> None:
        self.call(
            "sendMessage",
            {"chat_id": chat_id, "text": text},
            read_timeout=DEFAULT_READ_TIMEOUT_S,
        )


def _retry_after(response: httpx.Response) -> float | None:
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    parameters = body.get("parameters")
    value = parameters.get("retry_after") if isinstance(parameters, dict) else None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """Split on UTF-16 code units, which is what Telegram counts."""
    parts: list[str] = []
    current: list[str] = []
    used = 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if used + width > limit:
            parts.append("".join(current))
            current = []
            used = 0
        current.append(char)
        used += width
    if current:
        parts.append("".join(current))
    return parts


def process_update(
    update: dict,
    *,
    conn: sqlite3.Connection,
    tg,
    cfg: Config,
    llm,
    skills: dict,
    runner,
    bot_username: str,
) -> None:
    if not isinstance(update, dict) or not isinstance(update.get("update_id"), int):
        log.warning("update without a usable update_id ignored")
        return
    update_id = update["update_id"]
    # The at-most-once boundary: the cursor is persisted before any side effect.
    storage.set_state(conn, "last_update_id", str(update_id))

    message = update.get("message")
    if not isinstance(message, dict):
        log.info("update %d carries no message; ignored", update_id)
        return
    chat = message.get("chat")
    if not isinstance(chat, dict) or chat.get("type") != "private":
        log.info("update %d is not from a private chat; ignored", update_id)
        return
    sender = message.get("from")
    if not isinstance(sender, dict) or sender.get("is_bot"):
        log.info("update %d has no human sender; ignored", update_id)
        return
    from_id = sender.get("id")
    if from_id not in cfg.allowed_tg_ids:
        log.warning("unauthorized update from tg_id=%s", from_id)
        return
    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        log.info("update %d is not a text message; answered with a hint", update_id)
        _send(tg, chat["id"], [NON_TEXT_REPLY])
        return

    stripped = text.strip()
    if stripped.startswith("/"):
        command, _, suffix = stripped.split()[0].partition("@")
        if suffix and suffix.casefold() != bot_username.casefold():
            log.info("update %d addresses another bot; ignored", update_id)
            return
        if command.casefold() == "/new":
            storage.start_new_conversation(conn, from_id)
            _send(tg, chat["id"], [NEW_CONVERSATION_REPLY])
            return

    conv_id = storage.get_or_create_active_conversation(conn, from_id)
    storage.add_user_message(conn, conv_id, text)
    reply = agent.run_agent(
        conn=conn,
        conv_id=conv_id,
        llm=llm,
        skills=skills,
        runner=runner,
        now=storage.utc_now_iso(),
    )
    _send(tg, chat["id"], split_message(reply))


def _send(tg, chat_id: int, parts: list[str]) -> None:
    """Send the parts in order; stop at the first failure (at-most-once)."""
    for part in parts:
        try:
            tg.send_message(chat_id, part)
        except TelegramError as exc:
            log.error("sending the reply failed: %s", redact(str(exc)))
            return


def poll_loop(
    *,
    conn: sqlite3.Connection,
    tg,
    cfg: Config,
    llm,
    skills: dict,
    runner,
    bot_username: str,
    sleep=time.sleep,
) -> int:
    raw = storage.get_state(conn, "last_update_id")
    offset = int(raw) + 1 if raw is not None else None
    backoff_attempt = 0
    try:
        while not _shutdown:
            try:
                updates = tg.get_updates(offset)
            except TelegramError as exc:
                if exc.fatal:
                    log.error("polling stopped: %s", redact(str(exc)))
                    return 2
                backoff_attempt += 1
                if exc.retry_after is not None:
                    delay = exc.retry_after + 1.0
                else:
                    delay = min(2.0 ** (backoff_attempt - 1), MAX_BACKOFF_S)
                    delay += random.uniform(0.0, 0.5)
                log.warning("polling failed: %s; retrying in %.1fs", redact(str(exc)), delay)
                sleep(delay)
                continue
            backoff_attempt = 0
            for update in updates:
                process_update(
                    update,
                    conn=conn,
                    tg=tg,
                    cfg=cfg,
                    llm=llm,
                    skills=skills,
                    runner=runner,
                    bot_username=bot_username,
                )
                if isinstance(update, dict) and isinstance(update.get("update_id"), int):
                    offset = update["update_id"] + 1
    except KeyboardInterrupt:
        pass
    log.info("shutting down")
    return 0


def _handle_signal(signum, frame) -> None:
    global _shutdown
    _shutdown = True


class _SelftestLLM:
    """Two canned responses: one exec tool call, then a final answer."""

    def __init__(self) -> None:
        self._script = [
            LLMResponse(
                "",
                [
                    ToolCall(
                        "call_1",
                        "exec",
                        json.dumps({"argv": [sys.executable, "-c", "print('ok')"]}),
                    )
                ],
                "tool_calls",
            ),
            LLMResponse("selftest ok", [], "stop"),
        ]
        self.calls = 0

    def complete(self, messages, tool_definitions) -> LLMResponse:
        response = self._script[min(self.calls, len(self._script) - 1)]
        self.calls += 1
        return response


class _SelftestTelegram:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


_SELFTEST_UPDATE = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 0,
        "chat": {"id": 424242, "type": "private"},
        "from": {"id": 424242, "is_bot": False},
        "text": "run the selftest",
    },
}


def run_selftest() -> int:
    """Exercise the whole update path offline, in a throwaway directory."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        workdir = root / "sandbox"
        workdir.mkdir(parents=True, exist_ok=True)
        cfg = Config(
            telegram_bot_token="000000000:selftest-placeholder",
            allowed_tg_ids=frozenset({424242}),
            llm_provider="lmstudio",
            lmstudio_base_url="http://localhost:1234/v1",
            lmstudio_model="selftest",
            openrouter_api_key="",
            openrouter_model="",
            llm_timeout_s=120.0,
            exec_workdir=workdir,
            db_path=root / "selftest.db",
        )
        tg = _SelftestTelegram()
        conn = storage.connect(cfg.db_path)
        try:
            storage.init_schema(conn)
            process_update(
                _SELFTEST_UPDATE,
                conn=conn,
                tg=tg,
                cfg=cfg,
                llm=_SelftestLLM(),
                skills=tools.load_skills(PROJECT_ROOT / "skills"),
                runner=functools.partial(tools.run_command, workdir=cfg.exec_workdir),
                bot_username="selftestbot",
            )
            failure = _selftest_failure(conn, tg, cfg, root)
        finally:
            conn.close()

    if failure is not None:
        print(f"selftest: FAILED — {failure}", file=sys.stderr)
        return 1
    print("selftest: OK")
    return 0


def _selftest_failure(conn, tg, cfg: Config, root: Path) -> str | None:
    rows = conn.execute(
        "SELECT turn_id, role, content, tool_calls_json, tool_call_id "
        "FROM messages ORDER BY id"
    ).fetchall()

    users = [row for row in rows if row["role"] == "user"]
    if len(users) != 1 or users[0]["content"] != "run the selftest":
        return "the user message was not stored exactly once"

    tool_turns = [
        row for row in rows if row["role"] == "assistant" and row["tool_calls_json"] is not None
    ]
    if len(tool_turns) != 1:
        return "expected exactly one assistant message carrying tool calls"
    calls = json.loads(tool_turns[0]["tool_calls_json"])
    if len(calls) != 1 or calls[0]["id"] != "call_1" or calls[0]["function"]["name"] != "exec":
        return "the stored tool call is not the expected exec call"

    tool_rows = [row for row in rows if row["role"] == "tool"]
    if len(tool_rows) != 1 or tool_rows[0]["tool_call_id"] != "call_1":
        return "expected exactly one tool result carrying tool_call_id call_1"
    envelope = json.loads(tool_rows[0]["content"])
    if envelope.get("exit_code") != 0 or not str(envelope.get("stdout", "")).startswith("ok"):
        return "the exec tool did not produce a successful envelope"

    if tool_turns[0]["turn_id"] != tool_rows[0]["turn_id"]:
        return "the assistant row and the tool row are not in one turn group"

    answers = [
        row for row in rows if row["role"] == "assistant" and row["tool_calls_json"] is None
    ]
    if len(answers) != 1 or answers[0]["content"] != "selftest ok":
        return "the final assistant message was not stored exactly once"

    if tg.sent != [(424242, "selftest ok")]:
        return "the reply was not recorded exactly once"
    if storage.get_state(conn, "last_update_id") != "1":
        return "the polling cursor was not persisted"
    if root not in cfg.db_path.parents or root not in cfg.exec_workdir.parents:
        return "the selftest used paths outside its temporary directory"
    return None


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    if arguments == ["--selftest"]:
        return run_selftest()
    if arguments:
        print(USAGE)
        return 2

    try:
        cfg = load_config()
    except ConfigError as exc:
        log.error("configuration error: %s", redact(str(exc)))
        return 2

    conn = storage.connect(cfg.db_path)
    storage.init_schema(conn)
    skills = tools.load_skills(PROJECT_ROOT / "skills")
    client = httpx.Client()
    tg = TelegramClient(cfg.telegram_bot_token, client=client)
    try:
        bot_username = tg.get_me()["username"]
    except TelegramError as exc:
        log.error("cannot identify the bot: %s", redact(str(exc)))
        client.close()
        conn.close()
        return 2
    llm = build_llm_client(cfg, client=client)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    log.info("polling as @%s with %d skill(s)", bot_username, len(skills))
    try:
        return poll_loop(
            conn=conn,
            tg=tg,
            cfg=cfg,
            llm=llm,
            skills=skills,
            runner=functools.partial(tools.run_command, workdir=cfg.exec_workdir),
            bot_username=bot_username,
        )
    finally:
        client.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
