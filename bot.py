"""Entry point: Telegram long polling, update dispatch and the two selftests.

The polling loop itself is single-threaded and sequential: updates are
dequeued and dispatched strictly one at a time. Document uploads are the one
exception (v1.11.0 T5, `REQ-V1110-ING-02`): `_handle_document` only
pre-checks, reserves and enqueues on the loop thread -- the actual indexing
runs on `IngestWorker`'s own daemon thread, `IngestWorker._run`, so a large
upload never blocks the chat. The dashboard server (`dashboard_server.py`)
and the two output readers created per `exec` call are the process's other
threads.
"""

import enum
import functools
import hashlib
import html
import json
import logging
import os
import queue
import random
import re
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import unicodedata
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import docx.opc.exceptions
import httpx
import pypdf.errors

import agent
import config
import dashboard_server
import documents
import metrics
import rag
import storage
import tables
import tools
from config import PROJECT_ROOT, PROVIDERS, Config, ConfigError, load_config, redact
from llm import build_llm_client, pricing, provider_is_configured
from llm.base import REASONING_DEFAULT, CostResolver, LLMResponse, ReasoningRequest, ToolCall
from llm.embeddings import EmbeddingError, EmbeddingsClient, EmbeddingTimeoutError
from tables import utf16_length

TELEGRAM_API_HOST = "https://api.telegram.org"
LONG_POLL_TIMEOUT_S = 50
GET_UPDATES_READ_TIMEOUT_S = 60.0
DEFAULT_READ_TIMEOUT_S = 20.0
MESSAGE_LIMIT = 4096
MAX_BACKOFF_S = 30.0

SEND_ATTEMPT_LIMIT = 3  # total attempts per send/edit call
SEND_TRANSPORT_SLEEP_S = 2.0
MAX_MESSAGE_CHARS = 4000  # the accepted length of one user message
STATUS_MAX_CHARS = 64
LIVE_READ_TIMEOUT_S = 30.0
PROVIDER_OVERRIDE_KEY = "provider_override"
PRICING_STATE_KEY = "pricing_json"  # REQ-V13-PRC-02: the persisted price snapshot
STATS_MAX_CHARS = 3500  # REQ-V13-OBS-07
REAP_TIMEOUT_S = 15.0  # REQ-V11-ORP-02

TYPING_INTERVAL_S = 4.0  # REQ-V180-CHAT-05
TYPING_JOIN_TIMEOUT_S = 3.0
TYPING_REQUEST_TIMEOUT_S = 2.0

NON_TEXT_REPLY = "I can only process plain text messages."
# v1.11.0 T3 (REQ-V1110-SES-03): a format template, not a literal string --
# `_handle_new` names the id `start_new_conversation` returns.
NEW_CONVERSATION_REPLY = "New conversation started (#{conv_id})."
RATE_LIMIT_REPLY = "Rate limit exceeded. Please wait a moment."
TOO_LONG_REPLY = "Message too long (over 4000 characters). Please shorten it."
SUMMARY_FAILED_REPLY = "Could not summarize this conversation right now."
NOTHING_TO_SUMMARIZE_REPLY = "Nothing to summarize yet."
MODEL_USAGE_REPLY = "Usage: /model [lmstudio|openrouter|auto] [<model>]"
# v1.11.0 T4 (REQ-V1110-CBQ-02): the callback-data grammar's byte ceiling and
# the one text every stale/malformed callback is acknowledged with.
CALLBACK_DATA_MAX_BYTES = 64
CALLBACK_EXPIRED_REPLY = "Expired — send the command again."
STATUS_WORKING = "⚙️ working…"
STATUS_FAILED = "⚠️ failed"
USAGE = "usage: bot.py [--selftest|--selftest-live|--version] [--no-dashboard]"

# v1.9.0: the document upload flow (REQ-V190-CMD-01..07) and its error matrix
# (REQ-V190-ERR-01), the Telegram-facing half. `DOCUMENT_MAX_BYTES` is
# CMD-02/-03's cap, checked both before download (`file_size`) and during it
# (`TelegramClient.download_file`'s streamed cap). v1.11.0 T5 (REQ-V1110-
# ING-01) raises it to 20,000,000 -- decimal 20 MB, the Bot API's own
# ceiling ("bots can download files of up to 20MB in size" -- `getFile`
# docs); decimal keeps the cap under that ceiling whichever unit Telegram
# means.
DOCUMENT_MAX_BYTES = 20_000_000
DOC_RAG_NOT_CONFIGURED_REPLY = "Document search is not configured on this bot."
DOC_TOO_LARGE_REPLY = "File too large (over 20 MB)."
DOC_UNSUPPORTED_REPLY = "Unsupported file type. Supported: .txt .md .docx .pdf"
DOC_LIMIT_REPLY = "Limit of 20 documents reached. Use /delete <filename>."
DOC_CORRUPTED_PDF_REPLY = "Could not read this PDF file."
DOC_CORRUPTED_DOCX_REPLY = "Could not read this DOCX file."
DOC_EMPTY_REPLY = "The document contains no readable text."
DOC_TEXT_TOO_LARGE_REPLY = "Document too large (over 2,000,000 characters)."
# REQ-V1110-DOC-03: DocxArchiveTooLargeError/PdfTooManyPagesError used to
# share DOC_TEXT_TOO_LARGE_REPLY, wrongly telling an over-page-limit PDF it
# had too many *characters*. T5 moves the underlying constants they
# describe (MAX_EXTRACTED_TEXT_CHARS, PDF_MAX_PAGES) to these numbers; T2
# lands only the three reply strings.
DOC_DOCX_BOUNDS_REPLY = "Document too large (DOCX archive bounds)."
DOC_PDF_PAGES_REPLY = "Document too large (over 2,000 pages)."
DOC_EMBEDDING_ERROR_REPLY = "Embedding service error. Please try again later."
DOC_EMBEDDING_TIMEOUT_REPLY = "Embedding service timed out. Please try again later."
DOC_STORAGE_ERROR_REPLY = "Storage error. The document was not saved."
DOC_DOWNLOAD_TIMEOUT_REPLY = "Download timed out. Please try again."
DOC_TELEGRAM_ERROR_REPLY = "Telegram error while receiving the file. Please try again."
DOC_BUDGET_EXCEEDED_REPLY = "Indexing timed out (over 1800 s). Nothing was saved."
DOC_HANDLER_FAILED_REPLY = "Something went wrong while processing the document."
DOCUMENTS_EMPTY_REPLY = "No documents yet. Send me a .txt, .md, .docx or .pdf file."
DELETE_USAGE_REPLY = "Usage: /delete <filename> | /delete #<id>"
# v1.11.0 T5 (REQ-V1110-ING-02..05): the ingest worker -- one in-flight job
# per user, a four-slot admission queue (a fifth, reserved physical slot
# for the shutdown sentinel -- see `INGEST_QUEUE_MAX`), cooperative cancel.
INGEST_QUEUE_MAX = 4
DOC_QUEUE_FULL_REPLY = "Indexing queue is full; try again later."
CANCEL_NOTHING_REPLY = "Nothing to cancel."
CANCEL_ALREADY_FINISHING_REPLY = "Indexing is already finishing."
DOC_CANCELLED_REPLY = "❌ Cancelled."
DOC_INTERRUPTED_REPLY = "❌ Interrupted by restart."
# v1.11.0 T3 (REQ-V1110-SES-02/-03): sessions -- list and switch.
SESSIONS_LIST_LIMIT = 10
SESSION_USAGE_REPLY = "Usage: /session <id> (see /sessions)"

# v1.11.0 T6 (REQ-V1110-EXT-01): the Bot API command menu, registered once
# at startup by `main()` through `TelegramClient.set_my_commands`. Names
# without the leading slash (<= 32 chars), ASCII descriptions (<= 256
# chars), in the same order as README's Commands table. `/start` is the
# documented alias for `/help` (EXT-02) and is deliberately absent here --
# only a dispatched command gets a `COMMANDS` row.
COMMANDS: tuple[tuple[str, str], ...] = (
    ("new", "Summarize this conversation and start a fresh one"),
    ("status", "Uptime, provider, exec backend, database, skills"),
    ("stats", "Token, cost and tool counters"),
    ("summary", "Summarize this conversation on demand"),
    ("model", "Show or switch the LLM provider and model"),
    ("reload_skills", "Re-read skills/ without restarting the bot"),
    ("documents", "List your uploaded documents"),
    ("delete", "Delete one of your documents"),
    ("sessions", "List your recent sessions"),
    ("session", "Switch your active session"),
    ("cancel", "Cancel your in-progress document indexing"),
    ("help", "Show this command list"),
)

log = logging.getLogger("bot")

# httpx logs every request URL at INFO. The Telegram URL embeds the bot token,
# which must never reach a log record, redacted or not (REQ-CFG-04).
logging.getLogger("httpx").setLevel(logging.WARNING)

_shutdown = False
# Defined at module level so that `/status` has an uptime even in tests that never
# call `main()`; `main()` resets it when the bot actually starts serving.
_started_at: float = time.monotonic()


class TelegramError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        fatal: bool = False,
        transport: bool = False,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.fatal = fatal
        self.transport = transport


class TelegramDownloadTimeout(TelegramError):
    """REQ-V190-CMD-02: `download_file`'s `httpx.TimeoutException` maps here,
    `from exc`, in a clause placed **before** the generic `TransportError`
    one -- `httpx.TimeoutException` subclasses `httpx.TransportError`, so
    that order is what keeps ERR-01 row 10a reachable at all. Matched by
    type only, never by parsing a message."""


class DocumentTooLarge(Exception):
    """REQ-V190-CMD-02: raised by `TelegramClient.download_file` (and
    mimicked by `FakeTelegram`, TST-02) the instant the streamed buffer
    would exceed `max_bytes` -- ERR-01 row 5a's mid-stream half, alongside
    the handler's own pre-download `file_size` check. Not a `TelegramError`
    subclass: this is a size-cap refusal, not a transport failure."""


class TelegramClient:
    def __init__(
        self,
        token: str,
        *,
        client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._token = token
        self._client = client
        self._sleep = sleep

    def call(
        self,
        method: str,
        payload: dict,
        *,
        read_timeout: float,
        connect_timeout: float = 10.0,
        write_timeout: float = 10.0,
        pool_timeout: float = 10.0,
    ) -> dict:
        # The URL embeds the bot token: never log it, redacted or not.
        url = f"{TELEGRAM_API_HOST}/bot{self._token}/{method}"
        timeout = httpx.Timeout(
            connect=connect_timeout, read=read_timeout, write=write_timeout, pool=pool_timeout
        )
        try:
            response = self._client.post(url, json=payload, timeout=timeout)
        except httpx.TransportError as exc:
            raise TelegramError(
                redact(f"telegram {method} transport error: {exc.__class__.__name__}"),
                transport=True,
            ) from None

        status = response.status_code
        if status in (401, 404):
            raise TelegramError(redact(f"telegram {method} rejected the bot token"), fatal=True)
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

    def _call_with_retry(self, method: str, payload: dict) -> dict | bool:
        """Bounded delivery retry (REQ-V1-SND-01). Only a rate limit or a transport
        hiccup is worth a second attempt; everything else raises straight away."""
        for attempt in range(1, SEND_ATTEMPT_LIMIT + 1):
            try:
                return self.call(method, payload, read_timeout=DEFAULT_READ_TIMEOUT_S)
            except TelegramError as exc:
                if exc.fatal or attempt == SEND_ATTEMPT_LIMIT:
                    raise
                if exc.retry_after is not None:
                    self._sleep(exc.retry_after + 1.0)
                elif exc.transport:
                    self._sleep(SEND_TRANSPORT_SLEEP_S)
                else:
                    raise
        raise AssertionError("unreachable: the loop either returns or raises")

    def get_me(self) -> dict:
        return self.call("getMe", {}, read_timeout=DEFAULT_READ_TIMEOUT_S)

    def get_updates(self, offset: int | None) -> list[dict]:
        payload = {
            "timeout": LONG_POLL_TIMEOUT_S,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload, read_timeout=GET_UPDATES_READ_TIMEOUT_S)

    def send_message(self, chat_id: int, text: str) -> dict:
        return self._call_with_retry("sendMessage", {"chat_id": chat_id, "text": text})

    def send_message_html(
        self, chat_id: int, text: str, *, reply_markup: dict | None = None
    ) -> dict:
        """REQ-V1110-OUT-01/CBQ-03: the table path's `sendMessage`. Payload is
        exactly `{chat_id, text, parse_mode: "HTML"}` plus `reply_markup` when
        given -- no other tag, no MarkdownV2, no `entities`. `send_pre` is the
        only production caller; command/callback handlers never call this
        directly."""
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._call_with_retry("sendMessage", payload)

    def edit_message_text(self, chat_id: int, message_id: int, text: str) -> dict:
        return self._call_with_retry(
            "editMessageText",
            {"chat_id": chat_id, "message_id": message_id, "text": text},
        )

    def edit_message_html(
        self, chat_id: int, message_id: int, text: str, *, reply_markup: dict | None = None
    ) -> dict:
        """REQ-V1110-OUT-01/CBQ-03: the table path's `editMessageText`, same
        payload rule as `send_message_html` plus `message_id`. `edit_pre` is
        the only production caller."""
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._call_with_retry("editMessageText", payload)

    def answer_callback_query(
        self, callback_query_id: str, *, text: str | None = None
    ) -> dict | bool:
        """REQ-V1110-CBQ-03: `answerCallbackQuery`, `text` only when given.
        `edit_pre`'s handled-callback caller acknowledges once, first --
        this method itself carries no ordering guarantee, that is the
        caller's job (`_answer_callback`/`_handle_callback`)."""
        payload = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text
        return self._call_with_retry("answerCallbackQuery", payload)

    def delete_message(self, chat_id: int, message_id: int) -> bool:
        return self._call_with_retry(
            "deleteMessage", {"chat_id": chat_id, "message_id": message_id}
        )

    def get_file(self, file_id: str) -> dict:
        return self.call("getFile", {"file_id": file_id}, read_timeout=DEFAULT_READ_TIMEOUT_S)

    def set_my_commands(self, commands: list[dict]) -> bool:
        """REQ-V1110-EXT-01: `setMyCommands`, `main()`'s one caller --
        `commands` arrives already shaped as `[{"command": ...,
        "description": ...}, ...]` in `COMMANDS` order; this method does no
        validation or reshaping of its own."""
        return self._call_with_retry("setMyCommands", {"commands": commands})

    def download_file(
        self,
        file_path: str,
        *,
        max_bytes: int,
        should_stop: Callable[[], bool] | None = None,
    ) -> bytes | None:
        """REQ-V190-CMD-02: a streamed GET, capped at `max_bytes` -- the
        buffer is never allowed to exceed it, not even transiently. Clause
        order is normative (see `TelegramDownloadTimeout`): the timeout
        clause must come before the generic `TransportError` one.
        `should_stop` (REQ-V1110-ING-04, v1.11.0 T5) is checked between
        streamed chunks; the agent's own fetch/exec paths pass nothing
        (`None`, unchanged behavior). Once `should_stop()` is true the
        stream is closed and this returns `None` instead of `bytes` --
        the caller's own post-download checkpoint is what raises."""
        url = f"{TELEGRAM_API_HOST}/file/bot{self._token}/{file_path}"
        timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
        try:
            with self._client.stream("GET", url, timeout=timeout) as response:
                if response.status_code != 200:
                    raise TelegramError(
                        redact(f"telegram file download http {response.status_code}")
                    )
                buffer = bytearray()
                for chunk in response.iter_bytes():
                    if len(buffer) + len(chunk) > max_bytes:
                        response.close()
                        raise DocumentTooLarge("downloaded file exceeds the size cap")
                    buffer.extend(chunk)
                    if should_stop is not None and should_stop():
                        response.close()
                        return None
        except httpx.TimeoutException as exc:
            raise TelegramDownloadTimeout("download timed out") from exc
        except httpx.TransportError as exc:
            raise TelegramError(
                redact(f"telegram file download transport error: {exc.__class__.__name__}"),
                transport=True,
            ) from exc
        return bytes(buffer)


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


def reply_parts(text: str) -> list[str]:
    """Redact first, then split: a secret can never straddle a part boundary."""
    return split_message(redact(text))


class RateLimiter:
    """A token bucket per Telegram user id.

    The state is in-memory on purpose: a restart forgives everyone, which is the
    right trade for a personal bot and is documented in README.
    """

    def __init__(
        self,
        capacity: int,
        refill_s: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._capacity = float(capacity)
        self._refill_s = refill_s
        self._clock = clock
        self._buckets: dict[int, tuple[float, float]] = {}

    def allow(self, key: int) -> bool:
        now = self._clock()
        tokens, updated_at = self._buckets.get(key, (self._capacity, now))
        tokens = min(self._capacity, tokens + (now - updated_at) / self._refill_s)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - 1.0, now)
        return True


class _StatusMessage:
    """One editable Telegram message per run, entirely best-effort.

    Any Telegram error disables further edits for this run; the run itself never
    notices (REQ-V1-VIS-02).
    """

    def __init__(self, tg, chat_id: int) -> None:
        self._tg = tg
        self._chat_id = chat_id
        self._message_id: int | None = None
        self._disabled = False
        # v1.11.0 T5 (REQ-V1110-DOC-05): the last text `update()` attempted
        # to send, so `/documents`' in-flight line can show an ingest job's
        # progress without re-deriving it from anywhere else.
        self.last_text: str | None = None

    def on_tool(self, name: str, first_argument: str) -> None:
        if self._disabled:
            return
        if self._message_id is None:
            self._start()
            if self._message_id is None:
                return
        if name in ("exec", "fetch", "search_documents"):
            self._edit(_status_line(name, first_argument))

    def update(self, text: str) -> bool:
        """REQ-V190-CMD-04: with no message yet, sends `text` as the first
        message (the `_start` discipline `on_tool` already uses, just with
        `text` instead of `STATUS_WORKING`); otherwise edits it. Returns
        `True` iff the message exists and the call did not fail -- the
        caller's cue to fall back to `_send` when it returns `False`."""
        if self._disabled:
            return False
        self.last_text = text
        if self._message_id is None:
            self._start(text)
        else:
            self._edit(text)
        return self._message_id is not None and not self._disabled

    def finish(self, *, ok: bool) -> None:
        if self._message_id is None or self._disabled:
            return
        if ok:
            self._delete()
        else:
            self._edit(STATUS_FAILED)

    def _delete(self) -> None:
        try:
            result = self._tg.delete_message(self._chat_id, self._message_id)
        except Exception as exc:
            self._fail(exc)
            return
        if result is True:
            self._message_id = None
        else:
            # A failed delete leaves the message and `_message_id` in place
            # (CHAT-06): not an exception, so `_fail`'s wholesale disable does
            # not apply here — only this one delete is given up on.
            log.warning("status message delete failed: %s", redact(str(result)))

    def _start(self, text: str = STATUS_WORKING) -> None:
        try:
            result = self._tg.send_message(self._chat_id, text)
        except Exception as exc:
            self._fail(exc)
            return
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if message_id is None:
            self._disabled = True
            return
        self._message_id = message_id

    def _edit(self, text: str) -> None:
        try:
            self._tg.edit_message_text(self._chat_id, self._message_id, redact(text))
        except Exception as exc:
            self._fail(exc)

    def _fail(self, exc: Exception) -> None:
        self._disabled = True
        log.warning("status message disabled: %s", redact(str(exc)))


def _status_line(tool: str, first_argument: str) -> str:
    # Redact before truncating: cutting a secret in half would leave a fragment
    # that `redact` can no longer recognise.
    return redact(f"⚙️ {tool}: {first_argument}…")[:STATUS_MAX_CHARS]


class _TypingIndicator:
    """Best-effort "typing…" indicator, run alongside `_StatusMessage` for the
    duration of one agent run (REQ-V180-CHAT-05). Any error from Telegram
    disables it for the rest of this run; the run itself never notices --
    the same one-`log.warning`-then-disable discipline as `_StatusMessage`.
    """

    def __init__(
        self,
        tg,
        chat_id: int,
        *,
        ceiling_s: float,
        interval_s: float = TYPING_INTERVAL_S,
        monotonic: Callable[[], float] = time.monotonic,
        stop_event: threading.Event | None = None,
    ) -> None:
        self._tg = tg
        self._chat_id = chat_id
        self._ceiling_s = ceiling_s
        self._interval_s = interval_s
        self._monotonic = monotonic
        self._stop_event = stop_event if stop_event is not None else threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        thread = threading.Thread(target=self._run, daemon=True)
        try:
            thread.start()
        except Exception as exc:
            log.warning("typing indicator disabled: %s", redact(str(exc)))
            self._thread = None
            return
        self._thread = thread

    def _run(self) -> None:
        deadline = self._monotonic() + self._ceiling_s
        while True:
            if self._stop_event.is_set():
                return
            if self._monotonic() >= deadline:
                return
            try:
                self._tg.call(
                    "sendChatAction",
                    {"chat_id": self._chat_id, "action": "typing"},
                    read_timeout=TYPING_REQUEST_TIMEOUT_S,
                    connect_timeout=TYPING_REQUEST_TIMEOUT_S,
                    write_timeout=TYPING_REQUEST_TIMEOUT_S,
                    pool_timeout=TYPING_REQUEST_TIMEOUT_S,
                )
            except Exception as exc:
                log.warning("typing indicator disabled: %s", redact(str(exc)))
                return
            # Re-checked after the request returns, before scheduling anything
            # further: at most one stale action can still land (~5s after the
            # reply) if this request was in flight when `stop()` fired --
            # accepted, not fixed.
            if self._stop_event.is_set():
                return
            self._stop_event.wait(self._interval_s)

    def stop(self) -> None:
        self._stop_event.set()
        thread, self._thread = self._thread, None
        if thread is None:
            return
        thread.join(TYPING_JOIN_TIMEOUT_S)
        if thread.is_alive():
            log.warning("typing indicator join timed out")


def exec_backend_status(
    probe: Callable[[], str | None] = tools.docker_probe,
) -> tuple[str | None, bool]:
    """The startup exec wiring: the probed docker version and whether exec is armed.

    Running as root would make "non-root inside the container" a lie, so it
    disables exec regardless of what the probe found (REQ-V1-DK-07).
    """
    version = probe()
    docker_ok = True
    if os.getuid() == 0:
        log.warning(
            "exec backend disabled: refusing to run exec as root; "
            "use a dedicated low-privilege account"
        )
        docker_ok = False
    if version is None:
        log.warning("exec backend disabled: docker unavailable")
        docker_ok = False
    return version, docker_ok


def _startup_docker_wiring(
    cfg: Config, docker_ok: bool, *, resolve: Callable[..., list] | None = None
) -> tuple[bool, Path | None]:
    """REQ-V11-WIR-01: the one named seam everything this patch adds to startup
    lives behind.

    REQ-V12-QTA-03 and REQ-V12-SSR-02 run first and **regardless** of
    `docker_ok`: sandbox cleanup and the allowlist resolution check touch only
    the local filesystem and the network, never `docker`, and a sandbox left
    over quota — or an allowlist entry that has started resolving somewhere
    forbidden — must be caught even while Docker is down. Past that point the
    seam does nothing at all — no subprocess, no file creation — when
    `docker_ok` is false.

    This is a safety requirement, not a style choice: the existing tests that
    monkeypatch `exec_backend_status` without touching PATH would otherwise
    shell out to a real `docker` during `pytest`. Section 9.1 stubs this one
    seam in both; no other startup path may call `docker`.
    """
    _clean_sandbox_at_start(cfg)
    _check_allowlist_resolution(cfg, resolve)
    if not docker_ok:
        return False, None
    _reap_orphaned_containers()
    wrap_timeout = tools.image_has_timeout(cfg.exec_docker_image)
    if not wrap_timeout:
        log.warning(
            "exec container self-timeout unavailable: %s has no timeout(1); "
            "relying on startup reap",
            cfg.exec_docker_image,
        )
    empty_resolv = _ensure_empty_resolv(cfg.db_path)
    return wrap_timeout, empty_resolv


def _clean_sandbox_at_start(cfg: Config) -> None:
    """REQ-V12-QTA-03: give the operator an automatic way out of a sandbox a
    previous run left over quota. Uses `shutil`/`os` directly, never a
    subprocess, and runs before the `docker_ok` branch above — a prior test's
    contract (no subprocess, no file-system side effect when `docker_ok` is
    false) covers only the docker-dependent parts of this seam."""
    if not cfg.exec_sandbox_clean_on_start:
        return
    try:
        entries = list(cfg.exec_workdir.iterdir())
    except OSError as exc:
        log.warning("could not list the sandbox for startup cleanup: %s", redact(str(exc)))
        return
    removed = 0
    for entry in entries:
        try:
            _remove_sandbox_entry(entry)
            removed += 1
        except OSError:
            log.warning("could not clear %s from the sandbox; clear it by hand", entry)
    if removed:
        noun = "entry" if removed == 1 else "entries"
        log.info("cleared %d %s from the sandbox at startup", removed, noun)


def _remove_sandbox_entry(entry: Path) -> None:
    """The W-4 attack ends with a `chmod 000` subdirectory, which a plain
    `rmtree` cannot remove. `shutil.rmtree`'s `onexc` hands back a `func` that
    is "platform and implementation dependent" (its own docs' words) — on
    Python 3.12+'s fd-based implementation it can be `os.open`, whose
    signature `func(path)` cannot satisfy — so retrying that exact call is not
    reliable. Instead: a first pass that never raises, only records every path
    it could not remove; chmod each of those paths to `u+rwX` (the bot owns
    them — the container ran as the bot's own uid); then retry the whole
    removal once, letting a second failure propagate to the caller."""
    if entry.is_symlink() or not entry.is_dir():
        entry.unlink()
        return
    failed_paths: list[str] = []
    shutil.rmtree(entry, onexc=lambda _func, path, _exc: failed_paths.append(path))
    if failed_paths:
        for path in failed_paths:
            p = Path(path)
            # REQ-V13-CO-01: `os.chmod` follows symlinks, so a symlink the
            # first pass could not unlink would have its *target* — a
            # bot-owned file anywhere on the host — chmod-ed to `u+rwX`.
            # A symlink never needs a mode change: unlinking it needs only
            # its parent directory's mode, which this same loop fixes.
            if p.is_symlink():
                continue
            p.chmod(stat.S_IRWXU)
        shutil.rmtree(entry)


def _check_allowlist_resolution(cfg: Config, resolve: Callable[..., list] | None) -> None:
    """REQ-V12-SSR-02, layer 2: resolved once at startup, best effort.

    `resolve` defaults to `None` here — never `= socket.getaddrinfo` in the
    signature, which would bind the original function object at `def` time and
    let a call that omits `resolve=` slip past the offline test guard
    (REQ-V12-OFF-01) into real DNS. The lookup happens through the module
    attribute at call time instead, so the guard is mechanical.
    """
    resolve = resolve or socket.getaddrinfo
    for entry in cfg.fetch_allowed_domains:
        try:
            results = resolve(entry, 443, proto=socket.IPPROTO_TCP)
        except OSError as exc:
            log.warning(
                "could not resolve allowlisted domain %s: %s; the request-time "
                "guard remains in force",
                entry,
                exc.__class__.__name__,
            )
            continue
        for result in results:
            address = result[4][0]
            scope = config.address_scope(address)
            if scope is not None:
                raise ConfigError(
                    f"allowlisted domain {entry} resolves to a {scope} address "
                    f"({address}); refusing to start"
                )


_REAP_PS_FORMAT = '{{.ID}}\t{{.Label "tgexec-owner"}}'


def _reap_orphaned_containers() -> None:
    """REQ-V12-ORP-02: remove only what is genuinely orphaned — a container
    from v1.1 (no owner label) is always an orphan by now; one labelled by a
    still-live bot process is left alone, so starting a second instance can no
    longer kill the first one's running exec. A failure here is logged and
    never prevents startup."""
    try:
        listed = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"label={tools.CONTAINER_LABEL}",
                "--format",
                _REAP_PS_FORMAT,
            ],
            timeout=REAP_TIMEOUT_S,
            capture_output=True,
            env=tools._probe_env(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("orphan container reap failed: %s", redact(str(exc)))
        return
    if listed.returncode != 0:
        log.warning("orphan container reap failed: docker ps exited %d", listed.returncode)
        return
    lines = [line for line in listed.stdout.decode("utf-8", errors="replace").split("\n") if line]
    to_remove = []
    skipped = 0
    for line in lines:
        container_id, _sep, owner = line.partition("\t")
        if owner and tools.owner_is_alive(owner):
            skipped += 1
            continue
        to_remove.append(container_id)
    if skipped:
        log.info("skipped %d container(s) owned by a live process", skipped)
    if not to_remove:
        return
    try:
        removed = subprocess.run(
            ["docker", "rm", "-f", *to_remove],
            timeout=REAP_TIMEOUT_S,
            capture_output=True,
            env=tools._probe_env(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("orphan container reap failed: %s", redact(str(exc)))
        return
    if removed.returncode != 0:
        log.warning("orphan container reap failed: docker rm exited %d", removed.returncode)
        return
    log.info("reaped %d orphaned exec container(s)", len(to_remove))


def _ensure_empty_resolv(db_path: Path) -> Path:
    """REQ-V12-INF-01: an empty file mounted read-only at /etc/resolv.conf so a
    network-less container learns nothing about the host's DNS configuration.

    Creates or truncates the file unconditionally and refuses anything that is
    not a plain empty file it owns: `path.exists()` follows symlinks, so a
    symlink planted at this predictable, world-writable-adjacent path (finding
    W-8-bis) would otherwise be mounted into every container unexamined.
    """
    path = db_path.parent / ".resolv-empty"
    _refuse_shared_parent(path.parent)
    try:
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o644,
        )
    except OSError as exc:
        raise ConfigError(
            f'could not create the empty resolv file at "{path}": {exc.__class__.__name__}'
        ) from None
    try:
        st = os.fstat(fd)
        if not (
            stat.S_ISREG(st.st_mode)
            and st.st_size == 0
            and st.st_uid == os.getuid()
            and st.st_nlink == 1
        ):
            raise ConfigError(
                f'refusing to use "{path}" as the empty resolv file: '
                "it is not a plain file owned by this process"
            )
        os.fchmod(fd, 0o644)  # exact perms regardless of umask
    finally:
        os.close(fd)
    return path


def _refuse_shared_parent(parent: Path) -> None:
    """A sticky world-writable directory such as `/tmp` still allows the race
    on a pre-existing file, which `O_NOFOLLOW` + `O_TRUNC` + the `fstat`
    checks above defeat; a non-sticky one does not even need a pre-existing
    file, so it is refused outright."""
    st = parent.stat()
    if (st.st_mode & 0o002) and not (st.st_mode & stat.S_ISVTX):
        raise ConfigError(
            f'"{parent}" is world-writable and not sticky; move DB_PATH out of a shared directory'
        )


def load_provider_override(conn: sqlite3.Connection) -> str | None:
    value = storage.get_state(conn, PROVIDER_OVERRIDE_KEY)
    return value if value in PROVIDERS else None


def load_model_override(conn: sqlite3.Connection, provider: str) -> str | None:
    """REQ-V1110-MOD-05: the raw `model_override:<provider>` read, next to
    `load_provider_override` and the same shape -- a plain lookup, no
    catalogue validation. Catalogue membership (`cfg` is not available
    here) is `_effective_model_override`'s job, the wrapper `main()`'s
    wiring and the `/model` status block both call instead."""
    return storage.get_state(conn, f"model_override:{provider}")


def build_cost_resolver(
    conn: sqlite3.Connection,
    cfg: Config,
    client: httpx.Client,
    *,
    now: str | None = None,
) -> CostResolver:
    """The one path from a price to a stored row (REQ-V13-PRC-02).

    Prices are fetched **once**, here at startup, and never again per message.
    Nothing about this is allowed to block the bot: an unreachable `/models`
    logs a warning and leaves the resolver to fall through to the manual env
    prices and then to the snapshot an earlier run persisted.
    """
    stale = _load_pricing_state(conn)
    fetched_at = now or storage.utc_now_iso()
    snapshot = {}
    try:
        snapshot = pricing.fetch_openrouter_prices(
            client,
            (cfg.openrouter_model, cfg.llm_price_ref_model),
            now=fetched_at,
        )
    except pricing.PricingError as exc:
        log.warning("fetching OpenRouter prices failed: %s", redact(str(exc)))
    if snapshot:
        storage.set_state(
            conn,
            PRICING_STATE_KEY,
            json.dumps(
                pricing.snapshot_to_state(snapshot, fetched_at=fetched_at),
                ensure_ascii=False,
            ),
        )
    return pricing.make_resolver(cfg, snapshot, snapshot_basis=None, stale=stale)


def _load_pricing_state(conn: sqlite3.Connection) -> dict | None:
    raw = storage.get_state(conn, PRICING_STATE_KEY)
    if not raw:
        return None
    try:
        state = json.loads(raw)
    except ValueError:
        log.warning("the persisted price snapshot is not valid json; ignored")
        return None
    return state if isinstance(state, dict) else None


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
    limiter: RateLimiter | None = None,
    fetcher=None,
    docker_version: str | None = None,
    docker_ok: bool = False,
    set_provider: Callable[[str | None], object] | None = None,
    resolve_cost: CostResolver | None = None,
    summary_llm=None,
    dashboard_status: str = "off (--no-dashboard)",
    embedder=None,
    rerank_llm=None,
    worker: "IngestWorker | None" = None,
) -> None:
    if not isinstance(update, dict) or not isinstance(update.get("update_id"), int):
        log.warning("update without a usable update_id ignored")
        return
    update_id = update["update_id"]
    # The at-most-once boundary: the cursor is persisted before any side effect.
    storage.set_state(conn, "last_update_id", str(update_id))

    callback_query = update.get("callback_query")
    if isinstance(callback_query, dict):
        # REQ-V1110-CBQ-01: a callback_query update is handled entirely by
        # `_handle_callback` -- its own guard chain replicates the
        # message-path order below, plus the two callback-only checks
        # (from.id == chat.id, the rate limiter) -- and never falls through
        # to the message-only guard past this point.
        _handle_callback(
            callback_query,
            conn=conn,
            tg=tg,
            cfg=cfg,
            llm=llm,
            set_provider=set_provider,
            limiter=limiter,
        )
        return

    message = update.get("message")
    if not isinstance(message, dict):
        log.info("update %d carries no message; ignored", update_id)
        return
    chat = message.get("chat")
    if (
        not isinstance(chat, dict)
        or chat.get("type") != "private"
        or not isinstance(chat.get("id"), int)
    ):
        log.info("update %d is not from a usable private chat; ignored", update_id)
        return
    sender = message.get("from")
    if not isinstance(sender, dict) or sender.get("is_bot"):
        log.info("update %d has no human sender; ignored", update_id)
        return
    from_id = sender.get("id")
    if from_id not in cfg.allowed_tg_ids:
        # Nothing below this line can spend a resource on an intruder.
        log.warning("unauthorized update from tg_id=%s", from_id)
        return
    chat_id = chat["id"]
    document = message.get("document")
    if isinstance(document, dict):
        # REQ-V190-CMD-01: the rate limiter applies to a document exactly as
        # to a text message -- one token, before any download -- but none of
        # the text-only checks below (length, command dispatch) apply here.
        if limiter is not None and not limiter.allow(from_id):
            log.warning("rate limit hit for tg_id=%s", from_id)
            _send(tg, chat_id, [RATE_LIMIT_REPLY])
            return
        _handle_document(
            document,
            conn=conn,
            tg=tg,
            cfg=cfg,
            chat_id=chat_id,
            from_id=from_id,
            embedder=embedder,
            worker=worker,
        )
        return
    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        log.info("update %d is not a text message; answered with a hint", update_id)
        _send(tg, chat_id, [NON_TEXT_REPLY])
        return
    if utf16_length(text) > MAX_MESSAGE_CHARS:
        log.info("update %d exceeds the message length cap; rejected", update_id)
        _send(tg, chat_id, [TOO_LONG_REPLY])
        return
    if limiter is not None and not limiter.allow(from_id):
        log.warning("rate limit hit for tg_id=%s", from_id)
        _send(tg, chat_id, [RATE_LIMIT_REPLY])
        return

    stripped = text.strip()
    if stripped.startswith("/"):
        token = stripped.split()[0]
        command, _, suffix = token.partition("@")
        if suffix and suffix.casefold() != bot_username.casefold():
            log.info("update %d addresses another bot; ignored", update_id)
            return
        name = command.casefold()
        if name == "/new":
            _handle_new(conn, tg, cfg, llm, chat_id, from_id, resolve_cost, summary_llm)
            return
        if name == "/status":
            _send(
                tg,
                chat_id,
                reply_parts(
                    _render_status(
                        conn,
                        cfg,
                        llm,
                        skills,
                        docker_version,
                        docker_ok,
                        load_provider_override(conn),
                        from_id,
                        dashboard_status,
                    )
                ),
            )
            return
        if name == "/stats":
            send_pre(tg, chat_id, _render_stats(conn, from_id))
            return
        if name == "/summary":
            _handle_summary(conn, tg, cfg, llm, chat_id, from_id, resolve_cost, summary_llm)
            return
        if name == "/model":
            parts = stripped.split()
            # REQ-V1110-MOD-03: every remaining token is handed to
            # `_handle_model`, which enforces the "at most two arguments"
            # rule itself -- a `parts[1:3]` slice at this site would
            # silently drop a third argument instead of refusing it.
            _handle_model(conn, tg, cfg, llm, chat_id, parts[1:], set_provider)
            return
        if name == "/reload_skills":
            _handle_reload_skills(tg, skills, chat_id)
            return
        if name == "/documents":
            _handle_documents(conn, tg, chat_id, from_id, worker=worker)
            return
        if name == "/delete":
            argument = stripped[len(token) :].strip()
            _handle_delete(conn, tg, chat_id, from_id, argument)
            return
        if name == "/cancel":
            _handle_cancel(tg, chat_id, from_id, worker)
            return
        if name == "/sessions":
            _handle_sessions(conn, tg, chat_id, from_id)
            return
        if name == "/session":
            argument = stripped[len(token) :].strip()
            _handle_session(conn, tg, chat_id, from_id, argument)
            return
        if name == "/help":
            _handle_help(tg, chat_id)
            return
        if name == "/start":
            _handle_help(tg, chat_id)
            return

    conv_id = storage.get_or_create_active_conversation(conn, from_id)
    storage.add_user_message(conn, conv_id, redact(text))
    status = _StatusMessage(tg, chat_id)
    typing = _TypingIndicator(tg, chat_id, ceiling_s=cfg.llm_timeout_s)
    typing.start()
    # REQ-V190-CMD-01: a fresh `Searcher` per turn, bound to `from_id`; with
    # no embedder configured the tool stays "not available" (TOOL-02).
    searcher = (
        rag.Searcher(
            conn,
            user_id=from_id,
            embedder=embedder,
            llm=rerank_llm or llm,
            cfg=cfg,
            conv_id=conv_id,
            resolve_cost=resolve_cost,
        )
        if embedder is not None
        else None
    )
    try:
        outcome = agent.run_agent_outcome(
            conn=conn,
            conv_id=conv_id,
            llm=llm,
            skills=skills,
            runner=runner,
            now=storage.utc_now_iso(),
            cfg=cfg,
            fetcher=fetcher,
            searcher=searcher,
            audit=functools.partial(_write_audit, cfg.audit_log_path, from_id, conv_id),
            recent_goals=storage.recent_goals(conn, from_id),
            should_stop=lambda: _shutdown,
            on_tool=status.on_tool,
            resolve_cost=resolve_cost,
        )
    except Exception:
        # The indicator must be stopped before `status.finish` runs, on this
        # path too (REQ-V180-CHAT-08 step 2's ordering) -- not just before
        # the reply send below.
        typing.stop()
        status.finish(ok=False)
        raise
    typing.stop()
    reply = outcome.reply
    if not outcome.failed and searcher is not None and searcher.calls:
        reply, _ = rag.attach_sources(reply, searcher.calls)
    sent_ok = _send(tg, chat_id, reply_parts(reply))
    status.finish(ok=sent_ok and not outcome.failed)


def _write_audit(path: Path, tg_user_id: int, conv_id: int, record: dict) -> None:
    tools.append_audit(
        path,
        {
            "ts": storage.utc_now_iso(),
            "tg_user_id": tg_user_id,
            "conv_id": conv_id,
            **record,
        },
    )


def _handle_new(
    conn,
    tg,
    cfg: Config,
    llm,
    chat_id: int,
    from_id: int,
    resolve_cost: CostResolver | None = None,
    summary_llm=None,
) -> None:
    conv_id = storage.get_or_create_active_conversation(conn, from_id)
    if len(storage.load_context_messages(conn, conv_id, agent.CONTEXT_WINDOW_MESSAGES)) >= 2:
        try:
            summary = agent.summarize_conversation(
                # REQ-V13-RTE-01: the summary purpose, and only it, may run on
                # the routed client; `summary_llm` is None unless it is configured.
                conn,
                conv_id,
                summary_llm or llm,
                cfg,
                resolve_cost=resolve_cost,
                retry_max_tokens=cfg.llm_summary_max_tokens,
                budget_s=cfg.llm_timeout_s,
            )
            if summary is not None:
                storage.add_summary(conn, conv_id, from_id, summary)
        except Exception as exc:  # summarization never blocks /new
            log.warning("summarizing the outgoing conversation failed: %s", redact(str(exc)))
    conv_id = storage.start_new_conversation(conn, from_id)
    _send(tg, chat_id, [NEW_CONVERSATION_REPLY.format(conv_id=conv_id)])


def _handle_summary(
    conn,
    tg,
    cfg: Config,
    llm,
    chat_id: int,
    from_id: int,
    resolve_cost: CostResolver | None = None,
    summary_llm=None,
) -> None:
    conv_id = storage.get_or_create_active_conversation(conn, from_id)
    if len(storage.load_context_messages(conn, conv_id, agent.CONTEXT_WINDOW_MESSAGES)) < 2:
        _send(tg, chat_id, [NOTHING_TO_SUMMARIZE_REPLY])
        return
    try:
        summary = agent.summarize_conversation(
            conn,
            conv_id,
            summary_llm or llm,
            cfg,
            resolve_cost=resolve_cost,
            retry_max_tokens=cfg.llm_summary_max_tokens,
            budget_s=cfg.llm_timeout_s,
        )
    except Exception as exc:
        log.warning("summarizing on request failed: %s", redact(str(exc)))
        summary = None
    if summary is None:
        _send(tg, chat_id, [SUMMARY_FAILED_REPLY])
        return
    storage.add_summary(conn, conv_id, from_id, summary)
    _send(tg, chat_id, reply_parts(_render_summary(summary)))


def _render_summary(summary_json: str) -> str:
    data = json.loads(summary_json)
    return (
        f"Goal: {data['goal']}\n"
        f"Files: {_render_list(data['files'])}\n"
        f"Decisions: {_render_list(data['decisions'])}\n"
        f"Errors: {_render_list(data['errors'])}\n"
        f"Next: {data['next_action']}"
    )


def _render_list(values: list[str]) -> str:
    return "; ".join(values) if values else "-"


def _render_status(
    conn,
    cfg: Config,
    llm,
    skills: dict,
    docker_version: str | None,
    docker_ok: bool,
    override: str | None,
    from_id: int,
    dashboard_status: str = "off (--no-dashboard)",
) -> str:
    here = metrics.conversation_stats(conn, storage.active_conversation_id(conn, from_id))
    uptime = max(0, int(time.monotonic() - _started_at))
    days, rest = divmod(uptime, 86400)
    hours, rest = divmod(rest, 3600)
    backend = f"docker {docker_version}" if docker_version and docker_ok else "unavailable"
    try:
        db_size = cfg.db_path.stat().st_size
    except OSError:
        db_size = 0
    return (
        f"Uptime: {days}d {hours}h {rest // 60}m\n"
        f"Provider: {_active_provider(cfg, llm, override)} (override: {override or 'none'})\n"
        f"Provider failures: {_render_failures(llm)}\n"
        f"Exec backend: {backend}\n"
        f"DB: {db_size} bytes, schema v{storage.schema_version(conn)}\n"
        f"Skills: {len(skills)} loaded\n"
        f"Tokens this conversation: in {here.tokens_in or 0} / out {here.tokens_out or 0}\n"
        f"Dashboard: {dashboard_status}"
    )


def _render_stats(conn, from_id: int) -> str:
    """REQ-V1110-STA-01. A three-column `metric | this conv | all time` table
    (`tables.render_table`) over the rows `agent.py` recorded, followed by a
    blank line and the four single-value lines (wrapped, never truncated, by
    `_wrap_line`). Reading them never opens a conversation. Cell-content
    semantics are REQ-V13-OBS-07's, preserved verbatim: `n/a` for a missing
    value (`_cell`), `n/a (no pricing)` for a side with no pricing basis
    (`_render_cost`), `mixed` when several bases disagree, the percent
    rendering of `_render_share`. `tables.fit_lines` replaces `_fit` at the
    `STATS_MAX_CHARS` cap, whole lines (continuation lines included) dropped
    from the end, `… N more` appended."""
    conv_id = storage.active_conversation_id(conn, from_id)
    here = metrics.conversation_stats(conn, conv_id)
    everywhere = metrics.global_stats(conn)
    table = tables.render_table(
        ["metric", "this conv", "all time"],
        [
            ("LLM calls", _cell(here.calls, str), _cell(everywhere.calls, str)),
            ("errors", _cell(here.errors, str), _cell(everywhere.errors, str)),
            ("tokens in", _cell(here.tokens_in, str), _cell(everywhere.tokens_in, str)),
            ("cached", _cell(here.cached_tokens, str), _cell(everywhere.cached_tokens, str)),
            (
                "reasoning",
                _cell(here.reasoning_tokens, str),
                _cell(everywhere.reasoning_tokens, str),
            ),
            ("tokens out", _cell(here.tokens_out, str), _cell(everywhere.tokens_out, str)),
            ("est. cost", _render_cost(here.cost_usd), _render_cost(everywhere.cost_usd)),
            ("cost basis", _cell(here.cost_basis, str), _cell(everywhere.cost_basis, str)),
            (
                "avg prompt/call",
                _cell(here.avg_prompt, str),
                _cell(everywhere.avg_prompt, str),
            ),
            (
                "re-sent share",
                _cell(here.resent_share, _render_share),
                _cell(everywhere.resent_share, _render_share),
            ),
        ],
        max_width=[22, 16, 16],
    )
    single_value_lines = [
        f"Top tools: {_render_top_tools(conn)}",
        f"Last turn: {_render_last_turn(conn, conv_id)}",
        _render_errors_line(conn),
        _render_summaries_line(conn),
    ]
    lines = [*table.split("\n"), ""]
    for line in single_value_lines:
        lines.extend(_wrap_line(line))
    return tables.fit_lines(lines, limit=STATS_MAX_CHARS)


def _render_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items()) or "none"


def _render_errors_line(conn) -> str:
    # REQ-V160-MET-05: built from metrics.error_breakdown, never its own SQL.
    breakdown = metrics.error_breakdown(conn)
    error_count = breakdown.total - breakdown.by_error_kind.get("ok", 0)
    return (
        f"Errors: {error_count} "
        f"(finish reasons: {_render_counts(breakdown.by_finish_reason)}; "
        f"kinds: {_render_counts(breakdown.by_error_kind)})"
    )


def _render_summaries_line(conn) -> str:
    # REQ-V160-MET-05: built from metrics.summary_health, never its own SQL.
    # "truncated-retried" is `.retried`; `.failed` is REQ-V160-MET-06's
    # terminal-failure count over rows.
    health = metrics.summary_health(conn)
    return f"Summaries: {health.ok} ok, {health.retried} truncated-retried, {health.failed} failed"


def _wrap_line(
    line: str, *, width: int = tables.MAX_TABLE_LINE_UNITS, indent: str = "  "
) -> list[str]:
    """REQ-V1110-STA-01: wrap, never truncate, one of `/stats`'s four
    single-value lines. Continuation lines are indented by two spaces;
    every line -- first and continuation -- stays within `width` UTF-16
    units (`tables.py`'s own OUT-03 ceiling, reused rather than
    reimplemented); breaks prefer the last space within budget and never
    split a Unicode scalar."""
    if tables.utf16_length(line) <= width:
        return [line]
    wrapped: list[str] = []
    remaining = line
    prefix = ""
    while remaining:
        budget = width - tables.utf16_length(prefix)
        if tables.utf16_length(remaining) <= budget:
            wrapped.append(prefix + remaining)
            break
        cut = max(_break_point(remaining, budget), 1)
        piece, remaining = remaining[:cut], remaining[cut:].lstrip(" ")
        wrapped.append(prefix + piece)
        prefix = indent
    return wrapped


def _break_point(text: str, budget: int) -> int:
    """The largest prefix of `text` that fits `budget` UTF-16 units: cut at
    the last space within that budget when one exists, else at the widest
    whole-scalar boundary that still fits (never splitting a supplementary
    character in half)."""
    used = 0
    last_space = None
    for idx, char in enumerate(text):
        width = 2 if ord(char) > 0xFFFF else 1
        if used + width > budget:
            return last_space if last_space is not None else idx
        if char == " ":
            last_space = idx
        used += width
    return len(text)


def _cell(value, render) -> str:
    return "n/a" if value is None else render(value)


def _render_cost(value: float | None) -> str:
    """A side whose rows carry no `cost_basis` has no price at all, which is
    not the same as a price of zero (REQ-V13-OBS-07)."""
    return "n/a (no pricing)" if value is None else f"${value:.4f}"


def _render_share(value: float) -> str:
    return f"{round(value * 100)}%"


def _render_top_tools(conn) -> str:
    ranked = metrics.top_tools(conn)
    if not ranked:
        return "none"
    return ", ".join(f"{tool} {tokens} ({round(share * 100)}%)" for tool, tokens, share in ranked)


def _render_last_turn(conn, conv_id: int | None) -> str:
    timeline = metrics.turn_timeline(conn, conv_id) if conv_id is not None else []
    if not timeline:
        return "none"
    parts = []
    for entry in timeline:
        part = (
            f"r{entry['round']} in {_cell(entry['prompt_tokens'], str)} "
            f"out {_cell(entry['completion_tokens'], str)}"
        )
        if entry["tools"]:
            part += " → " + ", ".join(f"{tool} {ms} ms" for tool, ms in entry["tools"])
        elif entry["final"]:
            part += " (final)"
        parts.append(part)
    return "; ".join(parts)


def _active_provider(cfg: Config, llm, override: str | None) -> str:
    return getattr(llm, "active_provider_name", None) or override or cfg.llm_provider


def _render_failures(llm) -> str:
    counts = getattr(llm, "failure_counts", None) or {}
    return f"lmstudio={counts.get('lmstudio', 0)}, openrouter={counts.get('openrouter', 0)}"


def model_display(model_id: str, *, limit: int) -> str:
    """REQ-V1110-MOD-04: the only form of a model id that ever reaches a
    human -- a `<pre>` catalogue row, a button, the selection body, the text
    form's confirmation. `redact` first (a hostile catalogue could carry a
    secret as a "model id"), then every Unicode `Cc`/`Cf` control/format
    character (`unicodedata.category`) replaced by a space, whitespace
    collapsed, then truncated UTF-16-safe to `limit` units -- OUT-03's exact
    algorithm, reused via `tables._truncate_cell` rather than duplicated
    (already reached across this same module boundary by
    `tests/test_observability.py`/`tests/test_pricing.py`). Exact ids are
    used only for catalogue validation, hashing, storage and client
    construction -- never surfaced raw anywhere a human reads them."""
    redacted = redact(model_id)
    cleaned = "".join(" " if unicodedata.category(ch) in ("Cc", "Cf") else ch for ch in redacted)
    collapsed = " ".join(cleaned.split())
    return tables._truncate_cell(collapsed, limit)


def _catalogue_for(cfg: Config, provider: str) -> tuple[str, ...]:
    return cfg.lmstudio_models if provider == "lmstudio" else cfg.openrouter_models


def _catalogue_hash(catalogue: Sequence[str]) -> str:
    """REQ-V1110-CBQ-02: the first 8 hex digits of the SHA-256 of the
    catalogue's framed JSON array -- a framed list so `["a\\nb", "c"]` and
    `["a", "b\\nc"]` never collide on a naive join."""
    digest = hashlib.sha256(
        json.dumps(list(catalogue), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest[:8]


def _effective_model_override(conn: sqlite3.Connection, cfg: Config, provider: str) -> str | None:
    """REQ-V1110-MOD-05: `load_model_override`'s raw read, filtered against
    `provider`'s current catalogue -- a stale env change since the override
    was set falls back to the default instead of erroring. `model in
    catalogue` is `False` for `model is None` too (a tuple of `str`), so a
    never-set override and a now-invalid one both resolve to `None` here."""
    model = load_model_override(conn, provider)
    return model if model in _catalogue_for(cfg, provider) else None


_OVERRIDE_SUFFIX = " (override)"


def _model_row_value(model_id: str, *, is_override: bool) -> str:
    limit = 44 - len(_OVERRIDE_SUFFIX) if is_override else 44
    display = model_display(model_id, limit=limit)
    return display + _OVERRIDE_SUFFIX if is_override else display


def _model_status_table(conn: sqlite3.Connection, cfg: Config, llm) -> str:
    """REQ-V1110-MOD-01: bare `/model`'s (and `mod:back:-`'s) `<pre>` body --
    a `field | value` table, `max_width` 12/44 (58 units with the
    separator, <= 72). A row label past 12 units (`openrouter model`, 16
    units) truncates with an ellipsis -- a known cosmetic effect of the
    brief's own stated widths, not a rendering error (`render_table` never
    raises on cell content, only on a line width past 72, which this
    combination cannot reach)."""
    override = load_provider_override(conn)
    rows: list[tuple[str, str]] = [
        ("provider", _active_provider(cfg, llm, override)),
        ("override", override or "none"),
    ]
    for provider in PROVIDERS:
        if not provider_is_configured(cfg, provider):
            continue
        default = cfg.lmstudio_model if provider == "lmstudio" else cfg.openrouter_model
        overridden = _effective_model_override(conn, cfg, provider)
        rows.append(
            (
                f"{provider} model",
                _model_row_value(
                    overridden if overridden is not None else default,
                    is_override=overridden is not None,
                ),
            )
        )
    rows.append(("failures", _render_failures(llm)))
    return tables.render_table(["field", "value"], rows, max_width=[12, 44])


def _model_step1_keyboard(cfg: Config) -> dict:
    buttons = [
        {"text": provider, "callback_data": f"mod:prov:{provider}"}
        for provider in PROVIDERS
        if provider_is_configured(cfg, provider)
    ]
    buttons.append({"text": "auto", "callback_data": "mod:auto:-"})
    return {"inline_keyboard": [buttons]}


def _model_step2_body(cfg: Config, name: str) -> str:
    catalogue = _catalogue_for(cfg, name)
    lines = [f"Models for {name}:"]
    lines.extend(f"{idx}. {model_display(model, limit=64)}" for idx, model in enumerate(catalogue))
    return "\n".join(lines)


def _model_step2_keyboard(cfg: Config, name: str) -> dict:
    catalogue = _catalogue_for(cfg, name)
    digest = _catalogue_hash(catalogue)
    rows = [
        [
            {
                "text": model_display(model, limit=32),
                "callback_data": f"mod:model:{idx}:{digest}",
            }
        ]
        for idx, model in enumerate(catalogue)
    ]
    rows.append([{"text": "← back", "callback_data": "mod:back:-"}])
    return {"inline_keyboard": rows}


_MODEL_HEADER_RE = re.compile(r"^Models for ([a-z]+):$")


def _parse_model_header(text: str) -> str | None:
    """REQ-V1110-MOD-02: "state lives in the message text, not the server" --
    the provider a `mod:model` selection applies to is parsed back out of
    `callback_query.message.text`'s first line, never cached server-side."""
    first_line = text.splitlines()[0] if text else ""
    match = _MODEL_HEADER_RE.match(first_line)
    return match.group(1) if match else None


def _handle_model(
    conn, tg, cfg: Config, llm, chat_id: int, arguments: list[str], set_provider
) -> None:
    if len(arguments) > 2:
        _send(tg, chat_id, [MODEL_USAGE_REPLY])
        return
    if not arguments:
        send_pre(
            tg,
            chat_id,
            _model_status_table(conn, cfg, llm),
            reply_markup=_model_step1_keyboard(cfg),
        )
        return
    provider_arg, *rest = arguments
    model_arg = rest[0] if rest else ""
    choice = provider_arg.casefold()
    if choice == "auto":
        if model_arg:
            _send(tg, chat_id, [MODEL_USAGE_REPLY])
            return
        storage.delete_state(conn, PROVIDER_OVERRIDE_KEY)
        storage.delete_state_prefix(conn, "model_override:")
        if set_provider is not None:
            set_provider(None)
        _send(tg, chat_id, ["Provider override cleared."])
        return
    if choice not in PROVIDERS:
        _send(tg, chat_id, [MODEL_USAGE_REPLY])
        return
    if not provider_is_configured(cfg, choice):
        _send(tg, chat_id, [f"Provider {choice} is not configured."])
        return
    if not model_arg:
        # REQ-V1110-MOD-03: the single-argument form -- unchanged strings,
        # never touches any `model_override:*` key.
        storage.set_state(conn, PROVIDER_OVERRIDE_KEY, choice)
        if set_provider is not None:
            set_provider(choice)
        _send(tg, chat_id, [f"Provider switched to {choice}."])
        return
    catalogue = _catalogue_for(cfg, choice)
    if model_arg not in catalogue:
        _send(tg, chat_id, [f"Unknown model for {choice}; see /model"])
        return
    storage.set_state(conn, PROVIDER_OVERRIDE_KEY, choice)
    storage.set_state(conn, f"model_override:{choice}", model_arg)
    if set_provider is not None:
        set_provider(choice)
    _send(
        tg,
        chat_id,
        [f"Provider switched to {choice}, model: {model_display(model_arg, limit=64)}."],
    )


def _answer_callback(tg, callback_query_id: str, *, text: str | None = None) -> bool:
    try:
        tg.answer_callback_query(callback_query_id, text=text)
        return True
    except TelegramError as exc:
        # TRY400: same classified-failure reasoning as `_send`'s own
        # TelegramError handler.
        log.error("acknowledging the callback failed: %s", redact(str(exc)))  # noqa: TRY400
        return False


_CALLBACK_NAMESPACES = ("mod", "ses")


def _resolve_callback_action(data, message_text: str, cfg: Config) -> tuple | None:
    """REQ-V1110-CBQ-02: parse and validate `callback_data` against the
    closed grammar, re-deriving the catalogue from `cfg` fresh -- never
    trusting anything cached. Returns `None` for anything stale or
    malformed (unknown ns/verb, non-ASCII, over 64 bytes, a non-integer
    index, an out-of-range index, a hash mismatch, an unconfigured
    provider, or a `mod:model` selection whose message no longer shows a
    provider header); never interprets `callback_data` as a filename, a
    path or SQL."""
    if not isinstance(data, str) or not data.isascii():
        return None
    if len(data) > CALLBACK_DATA_MAX_BYTES:
        return None
    parts = data.split(":")
    if len(parts) < 3 or parts[0] not in _CALLBACK_NAMESPACES:
        return None
    ns, verb = parts[0], parts[1]
    if ns != "mod":
        # `ses` is reserved so the grammar is closed -- not emitted this
        # release, always stale.
        return None

    if verb == "prov" and len(parts) == 3:
        name = parts[2]
        if name in PROVIDERS and provider_is_configured(cfg, name):
            return ("prov", name)
        return None

    if verb == "auto" and len(parts) == 3 and parts[2] == "-":
        return ("auto",)

    if verb == "back" and len(parts) == 3 and parts[2] == "-":
        return ("back",)

    if verb == "model" and len(parts) == 4:
        idx_raw, digest = parts[2], parts[3]
        if not (idx_raw.isascii() and idx_raw.isdigit()):
            return None
        name = _parse_model_header(message_text)
        if name is None or name not in PROVIDERS or not provider_is_configured(cfg, name):
            return None
        catalogue = _catalogue_for(cfg, name)
        if digest != _catalogue_hash(catalogue):
            return None
        idx = int(idx_raw)
        if not (0 <= idx < len(catalogue)):
            return None
        return ("model", name, catalogue[idx])

    return None


def _apply_callback_action(
    action: tuple,
    *,
    conn: sqlite3.Connection,
    tg,
    cfg: Config,
    llm,
    chat_id: int,
    message_id: int,
    set_provider,
) -> None:
    verb = action[0]
    if verb == "prov":
        name = action[1]
        edit_pre(
            tg,
            chat_id,
            message_id,
            _model_step2_body(cfg, name),
            reply_markup=_model_step2_keyboard(cfg, name),
        )
        return
    if verb == "model":
        name, model = action[1], action[2]
        # REQ-V1110-MOD-02: both keys, in this order, then set_provider,
        # then the edit.
        storage.set_state(conn, PROVIDER_OVERRIDE_KEY, name)
        storage.set_state(conn, f"model_override:{name}", model)
        if set_provider is not None:
            set_provider(name)
        edit_pre(
            tg, chat_id, message_id, f"Provider: {name}, model: {model_display(model, limit=64)}"
        )
        return
    if verb == "auto":
        storage.delete_state(conn, PROVIDER_OVERRIDE_KEY)
        storage.delete_state_prefix(conn, "model_override:")
        if set_provider is not None:
            set_provider(None)
        edit_pre(tg, chat_id, message_id, "Provider override cleared.")
        return
    if verb == "back":
        edit_pre(
            tg,
            chat_id,
            message_id,
            _model_status_table(conn, cfg, llm),
            reply_markup=_model_step1_keyboard(cfg),
        )
        return


def _handle_callback(
    callback_query: dict,
    *,
    conn: sqlite3.Connection,
    tg,
    cfg: Config,
    llm,
    set_provider,
    limiter: RateLimiter | None,
) -> None:
    """REQ-V1110-CBQ-01/-02: the callback_query counterpart of the
    message-path guards (`process_update:897-...`), same order, plus the two
    callback-only checks (`from.id == chat.id`, the rate limiter)."""
    callback_id = callback_query.get("id")
    if not isinstance(callback_id, str):
        log.info("callback query carries no usable id; ignored")
        return
    message = callback_query.get("message")
    if not isinstance(message, dict):
        log.info("callback query carries no message; ignored")
        return
    chat = message.get("chat")
    if (
        not isinstance(chat, dict)
        or chat.get("type") != "private"
        or not isinstance(chat.get("id"), int)
    ):
        log.info("callback query is not from a usable private chat; ignored")
        return
    sender = callback_query.get("from")
    if not isinstance(sender, dict) or sender.get("is_bot"):
        log.info("callback query has no human sender; ignored")
        return
    from_id = sender.get("id")
    if from_id not in cfg.allowed_tg_ids:
        # Nothing below this line can spend a resource on an intruder --
        # the one acknowledgement is what stops Telegram's spinner.
        log.warning("unauthorized update from tg_id=%s", from_id)
        _answer_callback(tg, callback_id)
        return
    chat_id = chat["id"]
    if from_id != chat_id:
        # A private chat's id is its user's id -- a mismatch is ignored
        # without an answer at all.
        log.info("callback query chat/from mismatch; ignored")
        return
    if limiter is not None and not limiter.allow(from_id):
        log.warning("rate limit hit for tg_id=%s", from_id)
        _answer_callback(tg, callback_id, text=RATE_LIMIT_REPLY)
        return

    message_id = message.get("message_id")
    if not isinstance(message_id, int):
        _answer_callback(tg, callback_id, text=CALLBACK_EXPIRED_REPLY)
        return

    action = _resolve_callback_action(callback_query.get("data"), message.get("text") or "", cfg)
    if action is None:
        _answer_callback(tg, callback_id, text=CALLBACK_EXPIRED_REPLY)
        return

    # REQ-V1110-CBQ-02: acknowledged exactly once, before any other
    # Telegram call in this handler path.
    _answer_callback(tg, callback_id)
    _apply_callback_action(
        action,
        conn=conn,
        tg=tg,
        cfg=cfg,
        llm=llm,
        chat_id=chat_id,
        message_id=message_id,
        set_provider=set_provider,
    )


def _handle_reload_skills(tg, skills: dict, chat_id: int) -> None:
    loaded = tools.load_skills(PROJECT_ROOT / "skills")
    # The registry object is the one later messages read, so it is replaced in
    # place rather than rebound.
    skills.clear()
    skills.update(loaded)
    names = ", ".join(sorted(skills)) if skills else "none"
    _send(tg, chat_id, [f"Skills reloaded: {len(skills)} ({names})."])


# ---------------------------------------------------------------------------
# v1.9.0: the document upload flow (REQ-V190-CMD-01..04, -07) and the
# Telegram-facing half of the error matrix (REQ-V190-ERR-01).
# ---------------------------------------------------------------------------


def _log_ext(filename: str | None) -> str:
    """The extension for the row-1 log line only -- never for the (fixed,
    literal) user-facing message (ERR-02). `filename` may be the raw,
    uncleaned `file_name`, since this never reaches the user."""
    if not filename or "." not in filename:
        return "none"
    return filename.rsplit(".", 1)[-1].lower()[:10]


def _document_error_ending(tg, chat_id: int, status: "_StatusMessage", reply: str) -> None:
    """REQ-V190-CMD-04's failure ending (the typing indicator dropped from
    this path entirely, v1.11.0 T5 REQ-V1110-ING-05): the status message is
    edited to `reply` and kept, or -- when no message exists or status work
    is disabled -- `reply` goes through `_send` instead. Exactly one error
    message reaches the user either way.
    """
    if not status.update(reply):
        _send(tg, chat_id, [reply])


def _document_success_reply(filename: str, result: "documents.IndexResult") -> str:
    if result.page_count is not None:
        return (
            f"✅ {filename}: {result.chunk_count} chunks, "
            f"{result.page_count} pages. Ask me about it."
        )
    return f"✅ {filename}: {result.chunk_count} chunks. Ask me about it."


def _still_indexing_reply(filename: str) -> str:
    return f"⏳ Still indexing {filename}; wait for it to finish."


def _cancelling_reply(filename: str) -> str:
    return f"Cancelling {filename}…"


class SubmitError(enum.Enum):
    """`IngestWorker.reserve`'s two atomic-admission failures (REQ-V1110-
    ING-03): `inflight` -- the caller already holds a reservation or a job;
    `full` -- no capacity token is free."""

    inflight = "inflight"
    full = "full"


@dataclass(frozen=True)
class Reservation:
    """The window between a successful `reserve()` and the matching
    `enqueue()`/`release()` (REQ-V1110-ING-02) -- carries just enough to
    build `IngestJob` and to name the reservation's own filename in a
    row-6 refusal that lands during that window (`T-V1110-ING-10`)."""

    from_id: int
    filename: str


@dataclass
class IngestJob:
    """One admitted document upload, lock-protected `phase`/`cancel_reason`
    fields aside (REQ-V1110-ING-04) -- both are read and written only
    through `IngestWorker`'s own lock, never touched directly. `monotonic`
    is a T5 addition beyond the spec's own constructor prose: it is not
    part of any frozen signature, and carrying the loop thread's own clock
    (real or, in a test, a fake one) is what lets `started_at`'s clock and
    the worker's own budget/cancel checks agree -- without it a test using a
    fake `monotonic` for `started_at` would still be timed against the real
    wall clock everywhere else, and `test_t_v190_cmd_07_budget_after_*`-style
    scripted clocks would spuriously fire (or fail to fire) real time.
    """

    chat_id: int
    from_id: int
    document: dict
    filename: str
    status: "_StatusMessage"
    started_at: float
    cancel: threading.Event
    cancel_reason: str | None = None
    phase: str = "queued"
    monotonic: Callable[[], float] = time.monotonic

    def should_stop(self) -> bool:
        """`TelegramClient.download_file`'s `should_stop` callable (REQ-
        V1110-ING-04): true once cancelled or once the budget from
        `started_at` is spent."""
        if self.cancel.is_set():
            return True
        return (self.monotonic() - self.started_at) > documents.INDEX_BUDGET_S_DEFAULT


def _check_cancel_budget(job: IngestJob) -> None:
    """The worker's own pre-index checkpoint (REQ-V1110-ING-04): raises
    `documents.IndexCancelled` when `job.cancel` is set, `documents.
    IndexBudgetExceeded` when the budget from `job.started_at` is spent --
    called before `getFile`, after `getFile` and immediately after
    `download_file` returns; `documents.index_document`'s own checkpoints
    (extraction, chunking, each embeddings batch, between PDF pages) follow
    from there, threaded the same `cancel` event."""
    if job.cancel.is_set():
        raise documents.IndexCancelled(f"cancelled ({job.cancel_reason})")
    elapsed = job.monotonic() - job.started_at
    if elapsed > documents.INDEX_BUDGET_S_DEFAULT:
        raise documents.IndexBudgetExceeded(
            f"budget exceeded before index_document: {elapsed:.1f}s > "
            f"{documents.INDEX_BUDGET_S_DEFAULT}s"
        )


def _cancel_ending_reply(job: IngestJob) -> str:
    return DOC_INTERRUPTED_REPLY if job.cancel_reason == "shutdown" else DOC_CANCELLED_REPLY


_INGEST_SENTINEL = object()  # never handed out by admission; see `IngestWorker.shutdown`


class IngestWorker:
    """v1.11.0 T5 (REQ-V1110-ING-02..05): one daemon thread, a bounded
    queue, its own lazily-acquired connection, driven synchronously in
    tests via `run_one()`. See the class methods for the two-phase
    admission protocol, the cooperative-cancel protocol and the shutdown
    drain -- this docstring only fixes the one frozen contract other tasks
    depend on: `__init__`'s exact signature (`T-V1110-SEC-01`)."""

    def __init__(self, cfg: Config, tg, embedder, db_path: Path) -> None:
        self._cfg = cfg
        self._tg = tg
        self._embedder = embedder
        self._db_path = db_path
        # Five physical slots: admission (`reserve`) hands out at most
        # `INGEST_QUEUE_MAX` (4) capacity tokens, one slot always free for
        # the shutdown sentinel -- `shutdown()`'s `put_nowait` can never
        # raise `queue.Full` and never blocks behind a running job.
        self._queue: queue.Queue = queue.Queue(maxsize=INGEST_QUEUE_MAX + 1)
        self._lock = threading.Lock()
        self._in_flight: dict[int, Reservation | IngestJob] = {}
        self._tokens = 0
        self._conn: sqlite3.Connection | None = None
        self._shutdown_called = False
        self._drained = False

    # -- two-phase admission (REQ-V1110-ING-02/-03) ------------------------

    def reserve(self, from_id: int, filename: str) -> Reservation | SubmitError:
        with self._lock:
            if from_id in self._in_flight:
                return SubmitError.inflight
            if self._tokens >= INGEST_QUEUE_MAX:
                return SubmitError.full
            self._tokens += 1
            reservation = Reservation(from_id=from_id, filename=filename)
            self._in_flight[from_id] = reservation
            return reservation

    def enqueue(self, reservation: Reservation, job: IngestJob) -> None:
        with self._lock:
            self._in_flight[reservation.from_id] = job
        self._queue.put_nowait(job)

    def release(self, reservation: Reservation) -> None:
        with self._lock:
            self._in_flight.pop(reservation.from_id, None)
            self._tokens -= 1

    def _blocking_filename(self, from_id: int) -> str | None:
        """Not part of ING-02's public API: a small T5 addition so a row-6
        refusal can name whatever is blocking `from_id` -- a bare
        `Reservation` (the `reserve`/`enqueue` race, `T-V1110-ING-10`) or a
        queued/running `IngestJob` -- since `in_flight()` itself only ever
        returns an `IngestJob` by ING-02's own contract."""
        with self._lock:
            entry = self._in_flight.get(from_id)
            return entry.filename if entry is not None else None

    # -- introspection (REQ-V1110-ING-03/-04) -------------------------------

    def in_flight(self, from_id: int) -> IngestJob | None:
        with self._lock:
            entry = self._in_flight.get(from_id)
            return entry if isinstance(entry, IngestJob) else None

    def cancel(self, from_id: int) -> bool | None:
        with self._lock:
            entry = self._in_flight.get(from_id)
            if not isinstance(entry, IngestJob):
                return None
            if entry.phase == "committing":
                return False
            entry.cancel_reason = "user"
            entry.cancel.set()
            return True

    # -- processing (REQ-V1110-ING-02) --------------------------------------

    def run_one(self, conn: sqlite3.Connection | None = None) -> None:
        """One `get()` -> process -> mark done, run on the calling thread.
        The thread wrapper `_run` is the only place that loops over this --
        keeping the loop out of `run_one` is what lets a test drive exactly
        one job per call, synchronously."""
        item = self._queue.get()
        try:
            if item is _INGEST_SENTINEL:
                self._drained = True
                return
            job = item
            with self._lock:
                job.phase = "running"
                self._tokens -= 1  # freed at dequeue -- ING-11 relies on this
            try:
                active_conn = conn
                if active_conn is None:
                    # Lazy, long-lived, acquired on the calling thread --
                    # never before a job was dequeued (REQ-V1110-ING-02).
                    if self._conn is None:
                        self._conn = storage.connect(self._db_path)
                    active_conn = self._conn
                self._process(job, active_conn)
            except Exception:
                # A connection-acquisition failure lands here too (it is
                # outside `_process`'s own try): the job still ends with
                # DOC_HANDLER_FAILED_REPLY and the worker continues.
                log.exception("document handler failed")
                _document_error_ending(self._tg, job.chat_id, job.status, DOC_HANDLER_FAILED_REPLY)
            finally:
                with self._lock:
                    self._in_flight.pop(job.from_id, None)
        finally:
            self._queue.task_done()

    def _process(self, job: IngestJob, conn: sqlite3.Connection) -> None:
        """The ERR-01 clause chain, moved verbatim (plus DOC-03's two new
        rows and ING-04's cancel checkpoints/clause) from the pre-T5 inline
        `_handle_document` -- see that function's own history for the
        original shape."""
        status = job.status
        try:
            _check_cancel_budget(job)
            file_info = self._tg.get_file(job.document.get("file_id"))
            file_path = file_info.get("file_path") if isinstance(file_info, dict) else None
            if not isinstance(file_path, str) or not file_path:
                # `file_path` is optional on Telegram's `File` object; treat a
                # reply without it as a transport failure (row 11), never as a
                # corrupted-document class further down this chain.
                raise TelegramError(redact("telegram getFile returned no file_path"))
            _check_cancel_budget(job)
            data = self._tg.download_file(
                file_path, max_bytes=DOCUMENT_MAX_BYTES, should_stop=job.should_stop
            )
            _check_cancel_budget(job)
            result = documents.index_document(
                conn,
                user_id=job.from_id,
                filename=job.filename,
                data=data,
                embedder=self._embedder,
                progress=status.update,
                now=storage.utc_now_iso(),
                started_at=job.started_at,
                monotonic=job.monotonic,
                budget_s=documents.INDEX_BUDGET_S_DEFAULT,
                cancel=job.cancel,
                before_commit=lambda: self._mark_committing(job),
            )
        except documents.IndexCancelled:
            log.warning("document cancelled: %s", job.cancel_reason)
            _document_error_ending(self._tg, job.chat_id, status, _cancel_ending_reply(job))
            return
        except documents.DocumentLimitExceededError:
            log.warning("document refused: limit")
            _document_error_ending(self._tg, job.chat_id, status, DOC_LIMIT_REPLY)
            return
        except TelegramDownloadTimeout:
            log.warning("document failed: download timeout")
            _document_error_ending(self._tg, job.chat_id, status, DOC_DOWNLOAD_TIMEOUT_REPLY)
            return
        except TelegramError as exc:
            log.warning("document failed: telegram: %s", redact(str(exc)))
            _document_error_ending(self._tg, job.chat_id, status, DOC_TELEGRAM_ERROR_REPLY)
            return
        except EmbeddingTimeoutError:
            log.warning("document failed: embeddings timeout")
            _document_error_ending(self._tg, job.chat_id, status, DOC_EMBEDDING_TIMEOUT_REPLY)
            return
        except documents.IndexBudgetExceeded as exc:
            log.warning("document failed: %s", redact(str(exc)))
            _document_error_ending(self._tg, job.chat_id, status, DOC_BUDGET_EXCEEDED_REPLY)
            return
        except documents.EmptyDocumentError:
            log.warning("document refused: empty")
            _document_error_ending(self._tg, job.chat_id, status, DOC_EMPTY_REPLY)
            return
        except documents.ExtractedTextTooLargeError as exc:
            log.warning("document refused: text too large %s", redact(str(exc)))
            _document_error_ending(self._tg, job.chat_id, status, DOC_TEXT_TOO_LARGE_REPLY)
            return
        except documents.DocxArchiveTooLargeError as exc:
            log.warning("document refused: docx archive bounds %s", redact(str(exc)))
            _document_error_ending(self._tg, job.chat_id, status, DOC_DOCX_BOUNDS_REPLY)
            return
        except documents.PdfTooManyPagesError as exc:
            log.warning("document refused: pdf pages %s", redact(str(exc)))
            _document_error_ending(self._tg, job.chat_id, status, DOC_PDF_PAGES_REPLY)
            return
        except DocumentTooLarge:
            log.warning("document refused: file too large")
            _document_error_ending(self._tg, job.chat_id, status, DOC_TOO_LARGE_REPLY)
            return
        except (zipfile.BadZipFile, docx.opc.exceptions.PackageNotFoundError, KeyError) as exc:
            log.warning("document refused: corrupted docx: %s", exc.__class__.__name__)
            _document_error_ending(self._tg, job.chat_id, status, DOC_CORRUPTED_DOCX_REPLY)
            return
        except pypdf.errors.PyPdfError as exc:
            log.warning("document refused: corrupted pdf: %s", exc.__class__.__name__)
            _document_error_ending(self._tg, job.chat_id, status, DOC_CORRUPTED_PDF_REPLY)
            return
        except EmbeddingError as exc:
            log.warning("document failed: embeddings: %s", redact(str(exc)))
            _document_error_ending(self._tg, job.chat_id, status, DOC_EMBEDDING_ERROR_REPLY)
            return
        except sqlite3.Error as exc:
            log.exception("document failed: sqlite: %s", exc.__class__.__name__)
            _document_error_ending(self._tg, job.chat_id, status, DOC_STORAGE_ERROR_REPLY)
            return
        except Exception:
            log.exception("document handler failed")
            _document_error_ending(self._tg, job.chat_id, status, DOC_HANDLER_FAILED_REPLY)
            return

        status.finish(ok=True)
        _send(self._tg, job.chat_id, [_document_success_reply(job.filename, result)])

    def _mark_committing(self, job: IngestJob) -> None:
        """`documents.index_document`'s `before_commit` callable (REQ-1110-
        ING-04): under the lock, either raises `IndexCancelled` -- when a
        `/cancel` already landed while this job was still `running`, in the
        gap after the last checkpoint and before this callable runs -- or
        moves the job to `committing`, atomically with respect to
        `/cancel`'s own lock-protected read. Checking cancel here is what
        closes that gap: it is the last point before `BEGIN IMMEDIATE`, so a
        job cancelled anywhere before it is caught here instead of
        committing anyway."""
        with self._lock:
            if job.cancel.is_set():
                raise documents.IndexCancelled(f"cancelled before commit ({job.cancel_reason})")
            job.phase = "committing"

    # -- wake-up and shutdown (REQ-V1110-ING-02/-05) -------------------------

    def _run(self) -> None:
        """The thread wrapper `main()` starts as a daemon: loops over
        `run_one` until the sentinel is drained, then closes the
        worker-owned connection (idempotent)."""
        try:
            while not self._drained:
                self.run_one()
        finally:
            self.close()

    def shutdown(self) -> None:
        """Idempotent (a second call is a no-op -- `queue.Queue.put_nowait`
        would otherwise raise `queue.Full` on a second sentinel): sets
        `cancel_reason = "shutdown"` and the cancel event on every job in
        phase `queued` or `running` (never `committing`, which finishes),
        then enqueues the private sentinel into the fifth, reserved slot."""
        with self._lock:
            if self._shutdown_called:
                return
            self._shutdown_called = True
            for entry in self._in_flight.values():
                if isinstance(entry, IngestJob) and entry.phase in ("queued", "running"):
                    entry.cancel_reason = "shutdown"
                    entry.cancel.set()
        self._queue.put_nowait(_INGEST_SENTINEL)

    def close(self) -> None:
        """Idempotent -- safe to call twice (`_run`'s own `finally` and,
        harmlessly, a caller that also calls it)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _handle_document(
    document: dict,
    *,
    conn: sqlite3.Connection,
    tg,
    cfg: Config,
    chat_id: int,
    from_id: int,
    embedder,
    worker: IngestWorker | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    """REQ-V190-CMD-01..04, -07 / REQ-V1110-ING-02: the loop-thread half
    only. `started_at` is still the handler's first action (DOC-04's budget
    origin); the five pre-checks (CMD-03) still a plain reply with no
    status message and no `getFile` call. Past them, this function's only
    remaining job is the two-phase `reserve`/`enqueue` admission (ING-03):
    the actual indexing (`getFile`, `download_file`,
    `documents.index_document`, the ERR-01 clause chain) moved to
    `IngestWorker._process`, run on the worker's own thread through
    `run_one` -- so a large upload never blocks the chat."""
    started_at = monotonic()

    if embedder is None or not cfg.rag_enabled:
        log.warning("document refused: rag not configured")
        _send(tg, chat_id, [DOC_RAG_NOT_CONFIGURED_REPLY])
        return

    file_size = document.get("file_size")
    if isinstance(file_size, int) and file_size > DOCUMENT_MAX_BYTES:
        log.warning("document refused: file too large")
        _send(tg, chat_id, [DOC_TOO_LARGE_REPLY])
        return

    raw_filename = document.get("file_name")
    filename = documents.clean_filename(raw_filename)
    if filename is None:
        log.warning("document refused: unsupported type %s", _log_ext(raw_filename))
        _send(tg, chat_id, [DOC_UNSUPPORTED_REPLY])
        return
    if documents.classify(filename) is None:
        log.warning("document refused: unsupported type %s", _log_ext(filename))
        _send(tg, chat_id, [DOC_UNSUPPORTED_REPLY])
        return

    existing_id = storage.document_id_for(conn, user_id=from_id, filename=filename)
    at_limit = existing_id is None and (
        storage.document_count(conn, user_id=from_id) >= documents.DOCUMENT_LIMIT
    )
    if at_limit:
        log.warning("document refused: limit")
        _send(tg, chat_id, [DOC_LIMIT_REPLY])
        return

    if worker is None:
        # No worker configured (`run_selftest` constructs none, REQ-V1110-
        # ING-02) -- a document past the five pre-checks has nowhere to go;
        # refuse the same way a full queue would rather than drop it.
        log.warning("document refused: no ingest worker configured")
        _send(tg, chat_id, [DOC_QUEUE_FULL_REPLY])
        return

    reservation = worker.reserve(from_id, filename)
    if reservation is SubmitError.inflight:
        log.warning("document refused: already indexing")
        blocking_name = worker._blocking_filename(from_id) or filename
        _send(tg, chat_id, [_still_indexing_reply(blocking_name)])
        return
    if reservation is SubmitError.full:
        log.warning("document refused: queue full")
        _send(tg, chat_id, [DOC_QUEUE_FULL_REPLY])
        return

    status = _StatusMessage(tg, chat_id)
    if not status.update("📄 received"):
        worker.release(reservation)
        return
    job = IngestJob(
        chat_id=chat_id,
        from_id=from_id,
        document=document,
        filename=filename,
        status=status,
        started_at=started_at,
        cancel=threading.Event(),
        cancel_reason=None,
        phase="queued",
        monotonic=monotonic,
    )
    worker.enqueue(reservation, job)


def _render_size(size_bytes: int) -> str:
    """`size_bytes` in human units, decimal (1 MB = 1,000,000 bytes, never
    1,048,576), one decimal place: `< 1 MB` renders as KB, `0.0 KB` for
    zero (REQ-V1110-DOC-01)."""
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"
    return f"{size_bytes / 1_000:.1f} KB"


def _in_flight_stage(job: IngestJob) -> str:
    """DOC-05: the job's last progress string with its `📄 ` prefix
    stripped (`received`, `extracted: …`, `chunked: N`, `embedding: i/n`)
    -- or, before the first progress string ever landed (a job still
    `queued`, or a `_StatusMessage` that never recorded one), the fixed
    word `queued`."""
    text = job.status.last_text
    if text is None:
        return "queued"
    prefix = "📄 "
    return text[len(prefix) :] if text.startswith(prefix) else text


def _handle_documents(
    conn, tg, chat_id: int, from_id: int, worker: IngestWorker | None = None
) -> None:
    rows = storage.list_documents(conn, user_id=from_id)
    if not rows:
        _send(tg, chat_id, [DOCUMENTS_EMPTY_REPLY])
        return
    table = tables.render_table(
        ["#", "file", "type", "size", "chunks", "pages", "added"],
        [
            (
                row["id"],
                redact(row["filename"]),
                row["file_type"],
                _render_size(row["size_bytes"]),
                row["chunk_count"],
                row["page_count"],
                str(row["created_at"])[:10],
            )
            for row in rows
        ],
        max_width=[3, 24, 4, 8, 6, 5, 10],
    )
    # REQ-V1110-DOC-05 (T5): one in-flight `⏳ indexing …` line after the
    # table when the caller has a queued or running ingest job; with none,
    # the table is the last thing in the body (every case before T5, T2).
    body = f"Your documents ({len(rows)} of {documents.DOCUMENT_LIMIT}):\n\n{table}"
    job = worker.in_flight(from_id) if worker is not None else None
    if job is not None:
        body += f"\n⏳ indexing {job.filename} — {_in_flight_stage(job)}"
    send_pre(tg, chat_id, body)


def _handle_cancel(tg, chat_id: int, from_id: int, worker: IngestWorker | None) -> None:
    """REQ-V1110-ING-04: `/cancel` reads the caller's job and phase under
    the worker's own lock (`IngestWorker.cancel`, atomically) -- `None` no
    job, `True` the event was set (`queued`/`running`), `False` the job is
    already `committing`."""
    if worker is None:
        _send(tg, chat_id, [CANCEL_NOTHING_REPLY])
        return
    result = worker.cancel(from_id)
    if result is None:
        _send(tg, chat_id, [CANCEL_NOTHING_REPLY])
        return
    if result is False:
        _send(tg, chat_id, [CANCEL_ALREADY_FINISHING_REPLY])
        return
    job = worker.in_flight(from_id)
    _send(tg, chat_id, [_cancelling_reply(job.filename if job is not None else "")])


_DELETE_MAX_ID = 2**63 - 1  # sqlite3's INTEGER ceiling; a bigger id can't exist


def _no_document_named_reply(argument: str) -> str:
    return f"No document named {redact(argument)[:120]}."


def _handle_delete(conn, tg, chat_id: int, from_id: int, argument: str) -> None:
    if not argument:
        _send(tg, chat_id, [DELETE_USAGE_REPLY])
        return
    if argument.startswith("#"):
        id_part = argument[1:]
        # ASCII digits only (REQ-V1110-DOC-02): `str.isdigit()` alone also
        # accepts non-ASCII decimal digits `int()` would happily parse.
        parsed_id = int(id_part) if id_part.isascii() and id_part.isdigit() else None
        deleted = (
            parsed_id is not None
            and parsed_id <= _DELETE_MAX_ID
            and storage.delete_document(conn, user_id=from_id, document_id=parsed_id)
        )
        if deleted:
            _send(tg, chat_id, [f"Deleted {argument}."])
        else:
            _send(tg, chat_id, [_no_document_named_reply(argument)])
        return
    document_id = storage.document_id_for(conn, user_id=from_id, filename=argument)
    if document_id is None:
        _send(tg, chat_id, [_no_document_named_reply(argument)])
        return
    storage.delete_document(conn, user_id=from_id, document_id=document_id)
    _send(tg, chat_id, [f"Deleted {argument}."])


def _render_last_activity(value: str | None) -> str:
    """`YYYY-MM-DD HH:MM`, `n/a` when `NULL` -- `last_activity` is always
    `utc_now_iso()`'s `%Y-%m-%dT%H:%M:%SZ` shape, so a slice-and-replace is
    exact and avoids a datetime round trip (REQ-V1110-SES-02)."""
    return "n/a" if value is None else value[:16].replace("T", " ")


def _handle_sessions(conn, tg, chat_id: int, from_id: int) -> None:
    """REQ-V1110-SES-02: one table-path body over the `SESSIONS_LIST_LIMIT`
    most recent sessions, plus a trailing `N older sessions not shown` line
    when `count_conversations` exceeds that limit."""
    rows = storage.list_conversations(conn, from_id, limit=SESSIONS_LIST_LIMIT)
    total = storage.count_conversations(conn, from_id)
    table = tables.render_table(
        ["●", "#", "title", "msgs", "last"],
        [
            (
                "●" if row["active"] else "",
                row["id"],
                redact(row["title"]),
                row["message_count"],
                _render_last_activity(row["last_activity"]),
            )
            for row in rows
        ],
        max_width=[1, 4, 28, 4, 16],
    )
    body = table
    if total > SESSIONS_LIST_LIMIT:
        body = f"{table}\n\n{total - SESSIONS_LIST_LIMIT} older sessions not shown"
    send_pre(tg, chat_id, body)


def _no_session_reply(conv_id: int) -> str:
    # Never reveals whether `conv_id` doesn't exist at all or belongs to
    # someone else -- identical wording either way (REQ-V1110-SES-03).
    return f"No session #{conv_id}."


def _handle_session(conn, tg, chat_id: int, from_id: int, argument: str) -> None:
    """REQ-V1110-SES-03: `/session <id>` -- switch the caller's active
    conversation. Exactly one argument of ASCII digits, else the usage
    string; the same `_DELETE_MAX_ID` sqlite3-INTEGER-ceiling guard
    `_handle_delete` uses, for the same reason (a huge digit string would
    otherwise raise `OverflowError` binding it into the `UPDATE`)."""
    parts = argument.split()
    if len(parts) != 1 or not (parts[0].isascii() and parts[0].isdigit()):
        _send(tg, chat_id, [SESSION_USAGE_REPLY])
        return
    conv_id = int(parts[0])
    if conv_id > _DELETE_MAX_ID:
        _send(tg, chat_id, [_no_session_reply(conv_id)])
        return
    if not storage.activate_conversation(conn, from_id, conv_id):
        _send(tg, chat_id, [_no_session_reply(conv_id)])
        return
    title = redact(storage.conversation_title(conn, conv_id))
    _send(tg, chat_id, [f"Switched to session #{conv_id}: {title}"])


def _handle_help(tg, chat_id: int) -> None:
    """REQ-V1110-EXT-02: `/help` and `/start`'s shared handler -- one
    table-path body over `COMMANDS` (16 + 52 = 68, plus the two-space
    separator = 70 <= 72 units, OUT-03). Neither command is stored in the
    conversation -- both dispatch branches `return` before the fallback
    path that would store one."""
    send_pre(
        tg,
        chat_id,
        tables.render_table(("command", "what it does"), COMMANDS, max_width=(16, 52)),
    )


def _send(tg, chat_id: int, parts: list[str]) -> bool:
    """Send the parts in order; stop at the first failure (at-most-once)."""
    for part in parts:
        try:
            tg.send_message(chat_id, redact(part))
        except TelegramError as exc:
            # TRY400: TelegramError is an already-classified failure
            # (retryable/fatal are known from the exception itself); a
            # traceback here is noise, not diagnosis.
            log.error("sending the reply failed: %s", redact(str(exc)))  # noqa: TRY400
            return False
    return True


def _pre_text(body: str) -> tuple[str, str]:
    """REQ-V1110-OUT-01: the table path's shared construction. Redact before
    fit, fit before escape, escape before wrapping -- in that order and no
    other. Returns both the HTML `text` (one `<pre>` block) and the fitted,
    redacted plain body (`fitted`), so the HTML request and OUT-04's plain
    fallback send the exact same body."""
    redacted = redact(body)
    fitted = tables.fit_lines(redacted.splitlines(), limit=MESSAGE_LIMIT)
    text = "<pre>" + html.escape(fitted, quote=False) + "</pre>"
    return text, fitted


def send_pre(tg, chat_id: int, body: str, *, reply_markup: dict | None = None) -> dict | None:
    """REQ-V1110-OUT-01/-04: the table path. The only production caller of
    `TelegramClient.send_message_html` -- command and callback handlers call
    this, never the client method directly. Never splits: `_pre_text` already
    fit `body` to 4096 entity-parsed UTF-16 units. On a non-fatal table-path
    failure (the Bot API's "can't parse entities" 400 family, primarily),
    resend the same fitted body once more through the plain `send_message`;
    a fatal failure (401/404, `bot.py:154-198`'s classification) skips the
    fallback entirely -- a bad token or an unreachable chat is not a payload
    problem a plain resend could fix. Either way, a second failure is logged
    and `None` returned, never a third attempt."""
    text, fitted = _pre_text(body)
    try:
        return tg.send_message_html(chat_id, text, reply_markup=reply_markup)
    except TelegramError as exc:
        # TRY400: TelegramError is an already-classified failure, the same
        # pattern as `_send` above.
        if exc.fatal:
            log.error("sending the reply failed: %s", redact(str(exc)))  # noqa: TRY400
            return None
        try:
            return tg.send_message(chat_id, fitted)
        except TelegramError as exc2:
            log.error("sending the reply failed: %s", redact(str(exc2)))  # noqa: TRY400
            return None


def edit_pre(
    tg, chat_id: int, message_id: int, body: str, *, reply_markup: dict | None = None
) -> dict | None:
    """REQ-V1110-OUT-01/-04: `send_pre`'s edit counterpart -- same
    `_pre_text` construction, the same fatal-skips-the-fallback rule, and the
    same one-time plain fallback (`edit_message_text`, no tags, no
    `parse_mode`, no `reply_markup`) on a non-fatal table-path failure."""
    text, fitted = _pre_text(body)
    try:
        return tg.edit_message_html(chat_id, message_id, text, reply_markup=reply_markup)
    except TelegramError as exc:
        if exc.fatal:
            log.error("editing the reply failed: %s", redact(str(exc)))  # noqa: TRY400
            return None
        try:
            return tg.edit_message_text(chat_id, message_id, fitted)
        except TelegramError as exc2:
            log.error("editing the reply failed: %s", redact(str(exc2)))  # noqa: TRY400
            return None


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
    limiter: RateLimiter | None = None,
    fetcher=None,
    docker_version: str | None = None,
    docker_ok: bool = False,
    set_provider: Callable[[str | None], object] | None = None,
    get_llm: Callable[[], object] | None = None,
    resolve_cost: CostResolver | None = None,
    summary_llm=None,
    dashboard_status: str = "off (--no-dashboard)",
    embedder=None,
    rerank_llm=None,
    worker: IngestWorker | None = None,
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
                    # TRY400: same classified-failure reasoning as
                    # `_send`'s own TelegramError handler above.
                    log.error("polling stopped: %s", redact(str(exc)))  # noqa: TRY400
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
                    # `/model` can have swapped the client since the last update.
                    llm=get_llm() if get_llm is not None else llm,
                    skills=skills,
                    runner=runner,
                    bot_username=bot_username,
                    limiter=limiter,
                    fetcher=fetcher,
                    docker_version=docker_version,
                    docker_ok=docker_ok,
                    set_provider=set_provider,
                    resolve_cost=resolve_cost,
                    summary_llm=summary_llm,
                    dashboard_status=dashboard_status,
                    embedder=embedder,
                    rerank_llm=rerank_llm,
                    worker=worker,
                )
                if isinstance(update, dict) and isinstance(update.get("update_id"), int):
                    offset = update["update_id"] + 1
    except KeyboardInterrupt:
        pass
    log.info("shutting down")
    return 0


def _handle_signal(signum, frame) -> None:  # skylos: ignore -- signal.signal callback signature
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

    def describe(self) -> tuple[str, str]:
        return ("selftest", "selftest")

    def complete(
        self,
        messages,  # skylos: ignore -- LLMClient Protocol signature (llm/base.py)
        tool_definitions,  # skylos: ignore -- LLMClient Protocol signature
        *,
        max_tokens=None,  # skylos: ignore -- LLMClient Protocol signature
        reasoning: ReasoningRequest = REASONING_DEFAULT,  # skylos: ignore -- LLMClient signature
        timeout_s=None,  # skylos: ignore -- LLMClient Protocol signature
    ) -> LLMResponse:
        response = self._script[min(self.calls, len(self._script) - 1)]
        self.calls += 1
        return response


class _SelftestTelegram:
    """Status traffic is recorded apart from replies: REQ-ST-03 counts exactly one
    recorded send, and that one is the answer."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.status: list[tuple[int, str]] = []
        self.edits: list[tuple[int, int, str]] = []
        self.deleted: list[tuple[int, int]] = []

    def send_message(self, chat_id: int, text: str) -> dict:
        if text == STATUS_WORKING:
            self.status.append((chat_id, text))
            return {"message_id": 1}
        self.sent.append((chat_id, text))
        return {"message_id": 100 + len(self.sent)}

    def edit_message_text(self, chat_id: int, message_id: int, text: str) -> dict:
        self.edits.append((chat_id, message_id, text))
        return {"message_id": message_id}

    def delete_message(self, chat_id: int, message_id: int) -> bool:
        self.deleted.append((chat_id, message_id))
        return True


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
    """Exercise the whole update path offline, in a throwaway directory.

    This is the only place where a command still runs on the host: the operator
    invokes it explicitly, no Telegram update can reach it, and it must work on a
    machine where Docker is not installed at all (REQ-V1-ST-01).
    """
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
            audit_log_path=root / "exec_audit.jsonl",
        )
        tg = _SelftestTelegram()
        conn = storage.connect(cfg.db_path)
        try:
            _init_startup_schema(conn, cfg)
            process_update(
                _SELFTEST_UPDATE,
                conn=conn,
                tg=tg,
                cfg=cfg,
                llm=_SelftestLLM(),
                skills=tools.load_skills(PROJECT_ROOT / "skills"),
                runner=functools.partial(tools._run_process, workdir=cfg.exec_workdir),
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
        "SELECT turn_id, role, content, tool_calls_json, tool_call_id FROM messages ORDER BY id"
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
    if len(calls) != 1 or calls[0]["function"]["name"] != "exec":
        return "the stored tool call is not the expected exec call"

    tool_rows = [row for row in rows if row["role"] == "tool"]
    if len(tool_rows) != 1:
        return "expected exactly one tool result"
    # REQ-V12-ID-04: the identifier is minted by the bot, not pinned to a
    # literal the scripted model happens to emit — only the pairing matters.
    if calls[0]["id"] != tool_rows[0]["tool_call_id"]:
        return "the stored tool call and its result do not share an identifier"
    envelope = json.loads(tool_rows[0]["content"])
    if envelope.get("exit_code") != 0 or not str(envelope.get("stdout", "")).startswith("ok"):
        return "the exec tool did not produce a successful envelope"

    if tool_turns[0]["turn_id"] != tool_rows[0]["turn_id"]:
        return "the assistant row and the tool row are not in one turn group"

    answers = [row for row in rows if row["role"] == "assistant" and row["tool_calls_json"] is None]
    if len(answers) != 1 or answers[0]["content"] != "selftest ok":
        return "the final assistant message was not stored exactly once"

    if tg.sent != [(424242, "selftest ok")]:
        return "the reply was not recorded exactly once"
    if tg.status != [(424242, STATUS_WORKING)]:
        return "the status message was not sent exactly once"
    edits = [text for _chat, _mid, text in tg.edits]
    if len(edits) != 1 or not edits[0].startswith("⚙️ exec: "):
        return "the status message was not edited through the expected states"
    if tg.deleted != [(424242, 1)]:
        return "the status message was not deleted exactly once"
    if storage.get_state(conn, "last_update_id") != "1":
        return "the polling cursor was not persisted"
    if root not in cfg.db_path.parents or root not in cfg.exec_workdir.parents:
        return "the selftest used paths outside its temporary directory"
    if root not in cfg.audit_log_path.parents:
        return "the selftest wrote its audit log outside its temporary directory"
    return None


def run_selftest_live(
    *,
    cfg: Config | None = None,
    client: httpx.Client | None = None,
    probe: Callable[[], str | None] | None = None,
) -> int:
    """Check the live environment without spending a single inference token.

    No chat/completions request is ever made and no Telegram message is sent.
    """
    if cfg is None:
        try:
            cfg = load_config()
        except ConfigError as exc:
            _live_fail("config", str(exc))
            return 1
    print("live: OK config")

    owns_client = client is None
    client = client if client is not None else httpx.Client()
    probe = probe if probe is not None else tools.docker_probe
    failures = 0
    try:
        failures += _live_db(cfg)
        failures += _live_docker(cfg, probe)
        failures += _live_telegram(cfg, client)
        failures += _live_lmstudio(cfg, client)
        failures += _live_embeddings(cfg, client)
        failures += _live_openrouter(cfg, client)
    finally:
        if owns_client:
            client.close()
    return 1 if failures else 0


def _live_fail(check: str, reason) -> int:
    detail = reason if isinstance(reason, str) else f"{reason.__class__.__name__}: {reason}"
    print(f"live: FAIL {check} — {redact(detail)}")
    return 1


def _live_db(cfg: Config) -> int:
    try:
        conn = storage.connect(cfg.db_path)
        try:
            _init_startup_schema(conn, cfg)
            version = storage.schema_version(conn)
        finally:
            conn.close()
    except Exception as exc:
        return _live_fail("db", exc)
    if version != storage.SCHEMA_VERSION:
        return _live_fail("db", f"schema version is {version}, expected {storage.SCHEMA_VERSION}")
    print("live: OK db")
    return 0


def _live_docker(cfg: Config, probe: Callable[[], str | None]) -> int:
    version = probe()
    if version is None:
        return _live_fail("docker", "the daemon is unreachable")
    if not tools.docker_image_present(cfg.exec_docker_image):
        return _live_fail("docker", f"image {cfg.exec_docker_image} is not pulled")
    envelope = tools.run_command_docker(
        ["/bin/sh", "-c", "echo live-ok"],
        workdir=cfg.exec_workdir,
        image=cfg.exec_docker_image,
        docker_ok=True,
        sandbox_max_bytes=cfg.exec_sandbox_max_bytes,
    )
    if "error" in envelope:
        return _live_fail("docker", envelope["error"])
    if envelope.get("exit_code") != 0 or envelope.get("stdout", "").strip() != "live-ok":
        return _live_fail("docker", f"the container run exited {envelope.get('exit_code')}")
    print(f"live: OK docker ({version})")
    return 0


def _live_telegram(cfg: Config, client: httpx.Client) -> int:
    try:
        result = TelegramClient(cfg.telegram_bot_token, client=client).get_me()
    except Exception as exc:
        return _live_fail("telegram", exc)
    username = str(result.get("username", "")) if isinstance(result, dict) else ""
    if cfg.telegram_bot_name and username.casefold() != cfg.telegram_bot_name.casefold():
        return _live_fail("telegram", "the bot username does not match TELEGRAM_BOT_NAME")
    print("live: OK telegram")
    return 0


def _live_lmstudio(cfg: Config, client: httpx.Client) -> int:
    # v1.10.1 T1 (REQ-V1101-G5-01): a run that never routes anything to LM
    # Studio -- neither the main provider nor any of the four purpose
    # routes -- has nothing to probe here; a deployment that does route to
    # it (the provider itself, or any `lmstudio:`-prefixed purpose) still
    # fails hard on an unreachable box, exactly as before this rule.
    routed_purposes = (
        cfg.llm_summary_model,
        cfg.llm_rerank_model,
        cfg.llm_eval_chat_model,
        cfg.llm_judge_model,
    )
    if cfg.llm_provider != "lmstudio" and not any(
        purpose.startswith("lmstudio:") for purpose in routed_purposes
    ):
        print("live: SKIP lmstudio (no route uses it)")
        return 0
    if not (cfg.lmstudio_base_url and cfg.lmstudio_model):
        print("live: SKIP lmstudio (not configured)")
        return 0
    try:
        response = client.get(f"{cfg.lmstudio_base_url}/models", timeout=LIVE_READ_TIMEOUT_S)
        if response.status_code != 200:
            return _live_fail("lmstudio", f"http {response.status_code}: {response.text[:200]}")
        body = response.json()
    except Exception as exc:
        return _live_fail("lmstudio", exc)
    models = [entry.get("id") for entry in (body.get("data") or [])]
    if cfg.lmstudio_model not in models:
        return _live_fail("lmstudio", f"model {cfg.lmstudio_model} is not loaded")
    print("live: OK lmstudio")
    return 0


def _live_embeddings(cfg: Config, client: httpx.Client) -> int:
    """REQ-V190-RET-08: D3's "required, no default" is enforced here, at
    deployment, even though `EMBEDDING_MODEL`/`EMBEDDING_DIM` are optional at
    config level (`Config.rag_enabled`) so the 12 pre-EC-05 test files keep
    passing minimal environments to `load_config`.

    Wired into `run_selftest_live` right after `_live_lmstudio`. The T2
    handoff had left this unwired because the unconditional call broke two
    pre-existing, non-amendment-listed tests in
    `tests/test_v1_guardrails.py`; that erratum is now operator-ratified
    (same precedent class as `tests/test_summary.py`'s "authorised by the
    operator, prompt 107" comment) and `live_cfg`/`live_handler` were
    amended to cover it — see
    `docs/prompts/145-v190-t2-erratum-live-embeddings.md`.
    """
    if not cfg.rag_enabled:
        # REQ-V190-RET-08: the spec's own literal line, not `_live_fail`'s
        # "<check> — <reason>" template -- D3's "required at deployment"
        # gets one fixed, exact message.
        print("live: FAIL embeddings (EMBEDDING_MODEL and EMBEDDING_DIM are not set)")
        return 1
    # v1.10.1 T1 (REQ-V1101-G5-02): the unauthenticated `GET .../models`
    # listing is dropped -- OpenRouter's embedding catalogue lives at
    # `/embeddings/models`, not `/models` -- so the one authenticated
    # `/embeddings` round-trip below is the whole check.
    embedder = EmbeddingsClient(
        cfg.embedding_base_url,
        cfg.embedding_model,
        cfg.embedding_dim,
        LIVE_READ_TIMEOUT_S,
        client,
        api_key=cfg.embedding_api_key,
    )
    try:
        vectors = embedder.embed(["selftest"])
    except EmbeddingError as exc:
        return _live_fail("embeddings", exc)
    if len(vectors) != 1:
        return _live_fail("embeddings", f"expected 1 vector, got {len(vectors)}")
    print("live: OK embeddings")
    return 0


def _live_openrouter(cfg: Config, client: httpx.Client) -> int:
    if not cfg.openrouter_api_key:
        print("live: SKIP openrouter (no api key)")
        return 0
    try:
        response = client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {cfg.openrouter_api_key}"},
            timeout=LIVE_READ_TIMEOUT_S,
        )
    except Exception as exc:
        return _live_fail("openrouter", exc)
    if response.status_code != 200:
        return _live_fail("openrouter", f"http {response.status_code}")
    print("live: OK openrouter")
    return 0


def _read_version() -> str:
    """REQ-V160-VER-01: `pyproject.toml`'s `project.version` is the single
    source of truth, read fresh (never cached, never a literal here)."""
    path = PROJECT_ROOT / "pyproject.toml"
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        return data["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(f"cannot read version from {path}: {exc}") from exc


def _print_version() -> int:
    try:
        version = _read_version()
    except RuntimeError as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 2
    print(f"tg-agent-bot {version}")
    return 0


# REQ-V160-VER-03: --selftest, --selftest-live and --version are mutually
# exclusive; only --no-dashboard combines, and only with the default run.
_EXCLUSIVE_FLAGS = frozenset({"--selftest", "--selftest-live", "--version"})
_KNOWN_FLAGS = _EXCLUSIVE_FLAGS | {"--no-dashboard"}


def _init_startup_schema(conn: sqlite3.Connection, cfg: Config) -> None:
    """REQ-V190-STO-04: the one place `storage.init_schema` is ever called
    from `bot.py` -- `main()`, `run_selftest()` and `_live_db()` all call
    this, never `storage.init_schema` directly, so the configured embedding
    pair cannot drift out of one of the three call sites again (the bug
    behind GitHub issue #3: a bare `init_schema(conn)` leaves `vec_chunks`
    and the `rag.embedding` state key never created on a RAG-configured
    deployment)."""
    storage.init_schema(conn, embedding_dim=cfg.embedding_dim, embedding_model=cfg.embedding_model)


def main(argv: list[str] | None = None) -> int:
    global _started_at
    arguments = list(sys.argv[1:] if argv is None else argv)
    # v1.9.4 T1: same condition `logging.basicConfig` itself guards on (only
    # act when the root logger has no handler yet) -- an explicit handler is
    # built here, instead of handing a plain format string to `basicConfig`,
    # so the formatter is a `config.RedactingFormatter` (redacts a
    # `log.exception` traceback too, never covered by a call-site `redact()`
    # call) while every other observable -- format string, stream, level --
    # is unchanged.
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        config.install_redacting_logging(handler, "%(asctime)s %(levelname)s %(name)s %(message)s")
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
    # A repeated flag, an unknown token, a positional argument, or combining
    # two exclusive flags (or an exclusive flag with --no-dashboard) is a
    # usage error -- exit 2, print USAGE, nothing runs.
    if (
        len(set(arguments)) != len(arguments)
        or any(arg not in _KNOWN_FLAGS for arg in arguments)
        or len(_EXCLUSIVE_FLAGS & set(arguments)) > 1
        or (_EXCLUSIVE_FLAGS & set(arguments) and "--no-dashboard" in arguments)
    ):
        print(USAGE)
        return 2
    if "--version" in arguments:
        return _print_version()
    if "--selftest" in arguments:
        return run_selftest()
    if "--selftest-live" in arguments:
        return run_selftest_live()
    no_dashboard = "--no-dashboard" in arguments

    try:
        cfg = load_config()
    except ConfigError as exc:
        # TRY400: REQ-V12-ERR-01: a configuration refusal must look like
        # one, not an unhandled traceback (test_v12_patch.py asserts no
        # "Traceback" text reaches the log for this REQ's own seam below).
        log.error("configuration error: %s", redact(str(exc)))  # noqa: TRY400
        return 2

    _started_at = time.monotonic()
    conn = storage.connect(cfg.db_path)
    try:
        _init_startup_schema(conn, cfg)
    except ConfigError as exc:
        # REQ-V12-ERR-01: a configuration refusal must look like one, not an
        # unhandled traceback -- same shape as load_config's own catch above
        # and _startup_docker_wiring's below. This is what makes
        # _bind_new_embedding_pair's/_rebind_embedding_pair's ConfigError
        # (orphaned vec_chunks, or the pair changed while documents exist)
        # reachable from main() for the first time.
        log.error("configuration error: %s", redact(str(exc)))  # noqa: TRY400
        conn.close()
        return 2
    skills = tools.load_skills(PROJECT_ROOT / "skills")
    client = httpx.Client()
    tg = TelegramClient(cfg.telegram_bot_token, client=client)
    try:
        bot_username = tg.get_me()["username"]
    except (TelegramError, KeyError, TypeError) as exc:
        log.exception("cannot identify the bot: %s", redact(str(exc)))
        client.close()
        conn.close()
        return 2

    try:
        # REQ-V1110-EXT-01: registered once, right after `getMe` -- logged
        # and swallowed on failure, never fatal, since a stale or missing
        # command menu never stops the bot from serving updates.
        tg.set_my_commands([{"command": name, "description": desc} for name, desc in COMMANDS])
    except Exception as exc:
        log.warning("setMyCommands failed: %s", redact(str(exc)))

    docker_version, docker_ok = exec_backend_status()
    try:
        wrap_timeout, empty_resolv = _startup_docker_wiring(cfg, docker_ok)
    except ConfigError as exc:
        # REQ-V12-ERR-01: a configuration refusal must look like one, not an
        # unhandled traceback — whether it comes from `load_config` above or
        # from this seam (REQ-V12-INF-01, REQ-V12-SSR-02).
        log.error("configuration error: %s", redact(str(exc)))  # noqa: TRY400
        client.close()
        conn.close()
        return 2
    override = load_provider_override(conn)
    live = {
        "llm": build_llm_client(
            cfg,
            client=client,
            override=override,
            model=_effective_model_override(conn, cfg, override or cfg.llm_provider),
        )
    }

    def set_provider(name: str | None):
        # REQ-V1110-MOD-05: read `model_override:<provider>` at the same
        # moment the provider override is read -- a value not in the
        # provider's current catalogue is ignored (a stale env change is
        # not an error, just a fall-through to the default).
        live["llm"] = build_llm_client(
            cfg,
            client=client,
            override=name,
            model=_effective_model_override(conn, cfg, name or cfg.llm_provider),
        )
        return live["llm"]

    # REQ-V13-RTE-01: a second client, on the same `httpx.Client`, only when the
    # routing is configured. Unset it stays None so the summary keeps running on
    # whichever client `/model` has selected, exactly as before.
    summary_llm = (
        build_llm_client(cfg, client=client, purpose="summary") if cfg.llm_summary_model else None
    )

    # v1.9.1 T1: a third client, same shape as summary_llm above, only when
    # LLM_RERANK_MODEL is configured. Unset it stays None so Searcher keeps
    # reranking on whichever client `/model` has selected, exactly as before.
    rerank_llm = (
        build_llm_client(cfg, client=client, purpose="rerank") if cfg.llm_rerank_model else None
    )

    # REQ-V13-PRC-02: once, at startup, and never per message.
    resolve_cost = build_cost_resolver(conn, cfg, client)

    # REQ-V190-CMD-01: one process-wide embeddings client, next to the LLM
    # client, only when the pair is configured; `None` keeps search_documents
    # and the document upload flow "not available" (TOOL-02, ERR-01 row 14).
    embedder = (
        EmbeddingsClient(
            cfg.embedding_base_url,
            cfg.embedding_model,
            cfg.embedding_dim,
            cfg.embedding_timeout_s,
            client,
            api_key=cfg.embedding_api_key,
        )
        if cfg.rag_enabled
        else None
    )

    # v1.11.0 T5 (REQ-V1110-ING-02): the ingest worker's own daemon thread,
    # started next to the dashboard thread below -- `run_selftest` (above)
    # constructs no worker at all, `process_update`'s `worker=None` default
    # stays true there. The process-wide `embedder` instance above is
    # shared with the worker thread: `[[VERIFY]]` (T5's brief) confirmed
    # `EmbeddingsClient` holds no per-call mutable state (`llm/embeddings.py`
    # -- `embed`/`_embed_batch`/`_post_with_retry`/`_post` build only local
    # lists and read only constructor-time attributes), `httpx.Client` is
    # documented thread-safe, and `tracing.start_span`'s `_current_span` is a
    # `ContextVar` a new OS thread starts empty (`tracing.py`) -- a second
    # `EmbeddingsClient` is not needed.
    ingest_worker = IngestWorker(cfg, tg, embedder, cfg.db_path)
    ingest_thread = threading.Thread(target=ingest_worker._run, daemon=True)
    ingest_thread.start()

    # REQ-V160-SRV-01/-07: on by default; either switch suffices to turn it
    # off, the flag winning when they disagree. A failure to bind, to create
    # the server, or to start the thread is caught -- broadly, not just
    # OSError, since "a failure to create the server" is exactly as much
    # REQ-V160-SRV-07's business as a bind failure is -- logged once, and the
    # bot continues without the dashboard: no retry, no alternate port.
    dashboard_srv = None
    dashboard_thread = None
    if no_dashboard:
        dashboard_status = "off (--no-dashboard)"
    elif not cfg.dashboard_enabled:
        dashboard_status = "off (DASHBOARD_ENABLED=false)"
    else:
        try:
            dashboard_srv = dashboard_server.build_server(
                db_path=cfg.db_path, port=cfg.dashboard_port
            )
        except Exception as exc:  # REQ-V160-SRV-07's broad startup guard
            log.exception(
                "dashboard: failed to start on port %d: %s",
                cfg.dashboard_port,
                redact(f"{type(exc).__name__}: {exc}"),
            )
            dashboard_status = "off (bind failed)"
        else:
            dashboard_thread = threading.Thread(target=dashboard_srv.serve_forever, daemon=True)
            dashboard_thread.start()
            dashboard_status = f"http://127.0.0.1:{cfg.dashboard_port}/"
            log.info("dashboard: serving at %s", dashboard_status)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    log.info("polling as @%s with %d skill(s)", bot_username, len(skills))
    try:
        return poll_loop(
            conn=conn,
            tg=tg,
            cfg=cfg,
            llm=live["llm"],
            skills=skills,
            runner=functools.partial(
                tools.run_command_docker,
                workdir=cfg.exec_workdir,
                image=cfg.exec_docker_image,
                docker_ok=docker_ok,
                sandbox_max_bytes=cfg.exec_sandbox_max_bytes,
                wrap_timeout=wrap_timeout,
                empty_resolv=empty_resolv,
                output_default_chars=cfg.exec_output_default_chars,
            ),
            bot_username=bot_username,
            limiter=RateLimiter(cfg.rate_limit_capacity, cfg.rate_limit_refill_s),
            fetcher=functools.partial(
                tools.fetch_url,
                allowed_domains=cfg.fetch_allowed_domains,
                client=client,
                resolve=tools.resolve_host,
                # REQ-V13-TOO-06/07: where the full text of a truncated fetch is
                # saved, and how much of it comes back inline.
                workdir=cfg.exec_workdir,
                sandbox_max_bytes=cfg.exec_sandbox_max_bytes,
                max_chars=cfg.fetch_inline_default_chars,
            ),
            docker_version=docker_version,
            docker_ok=docker_ok,
            set_provider=set_provider,
            get_llm=lambda: live["llm"],
            resolve_cost=resolve_cost,
            # Deliberately a value, not a getter like `get_llm`: `/model` moves
            # the agent's client, never the routed summary one, which the
            # configuration pins for the life of the process (REQ-V13-RTE-01).
            summary_llm=summary_llm,
            dashboard_status=dashboard_status,
            embedder=embedder,
            rerank_llm=rerank_llm,
            worker=ingest_worker,
        )
    finally:
        if dashboard_srv is not None:
            dashboard_srv.shutdown()
            dashboard_srv.server_close()
            if dashboard_thread is not None:
                dashboard_thread.join(timeout=5.0)
                if dashboard_thread.is_alive():
                    log.warning("dashboard: server thread did not stop within 5s")
        # v1.11.0 T5 (REQ-V1110-ING-05): shutdown() sets the stop/cancel
        # state and enqueues the sentinel; the join bound is 10s (not the
        # dashboard's 5s) -- inside that window `_run` drains every
        # cancelled job and lets a `committing` one finish its commit.
        ingest_worker.shutdown()
        ingest_thread.join(timeout=10.0)
        if ingest_thread.is_alive():
            log.warning("ingest worker: did not stop within 10s")
        client.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
