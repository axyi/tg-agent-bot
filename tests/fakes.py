"""Test doubles. None of them performs I/O."""

import re
import subprocess
import zlib

import httpx

import bot
from llm.base import REASONING_DEFAULT, LLMError, ReasoningRequest

_DEFAULT_ENVELOPE = {
    "exit_code": 0,
    "timed_out": False,
    "truncated": False,
    "stdout": "recorded\n",
    "stderr": "",
    "stdout_bytes_total": 9,
    "stderr_bytes_total": 0,
}

# The REQ-V13-TOO-07 shape: exactly these keys, in this order.
_DEFAULT_FETCH_ENVELOPE = {
    "url": "https://wttr.in/x",
    "status": 200,
    "content_type": "text/plain",
    "chars_total": 8,
    "returned_chars": 8,
    "truncated": False,
    "saved_to": None,
    "save_error": None,
    "text": "recorded",
}


class FakeLLM:
    """Replays a scripted list of `LLMResponse` / `LLMError` items."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        # REQ-V1-FIN-02: the extended protocol carries `max_tokens`. It is recorded in
        # its own parallel list rather than as a third tuple element, because T-AG-03
        # unpacks `self.calls` entries as pairs and section 9.1 does not license
        # touching that test.
        self.max_tokens_calls = []
        # REQ-V170-POL-04, §14.1: recorded in their own parallel lists, same
        # reason as `max_tokens_calls` above.
        self.reasoning_calls = []
        self.timeout_s_calls = []
        # v1.9.1 T1: recorded in its own parallel list, same reason as the
        # three above.
        self.response_format_calls = []

    def describe(self):
        """REQ-V13-OBS-04: `provider`/`model` are NOT NULL columns."""
        return ("fake", "fake-model")

    def complete(
        self,
        messages,
        tool_definitions,
        *,
        max_tokens=None,
        reasoning: ReasoningRequest = REASONING_DEFAULT,
        timeout_s=None,
        response_format=None,
    ):
        # The agent reuses one `messages` list, so snapshot it before it grows.
        self.calls.append((list(messages), tool_definitions))
        self.max_tokens_calls.append(max_tokens)
        self.reasoning_calls.append(reasoning)
        self.timeout_s_calls.append(timeout_s)
        self.response_format_calls.append(response_format)
        if not self.script:
            raise AssertionError("FakeLLM script exhausted")
        item = self.script.pop(0)
        if isinstance(item, LLMError):
            raise item
        return item


class RecordingRunner:
    """Stands in for `tools.run_command`; records argv, never starts a process."""

    def __init__(self, result=None):
        self.result = dict(result) if result is not None else dict(_DEFAULT_ENVELOPE)
        self.argv_calls = []

    def __call__(self, argv):
        self.argv_calls.append(list(argv))
        return dict(self.result)

    def forbid_real_processes(self, monkeypatch):
        """Fail the test if anything reaches `subprocess.Popen` while this runner stands in."""

        def _forbidden(*args, **kwargs):
            raise AssertionError(f"unexpected subprocess start: {args!r}")

        monkeypatch.setattr(subprocess, "Popen", _forbidden)


class FakeFetcher:
    """Stands in for the bound `tools.fetch_url`; records URLs, never leaves the process."""

    def __init__(self, result=None):
        self.result = dict(result) if result is not None else dict(_DEFAULT_FETCH_ENVELOPE)
        self.urls = []
        self.kwargs = []

    def __call__(self, url, **kwargs):
        # `max_chars` reaches the bound `fetch_url` as a keyword (REQ-V13-TOO-07);
        # the fake records what the dispatcher passed on.
        self.urls.append(url)
        self.kwargs.append(dict(kwargs))
        return dict(self.result)


class FakeSearcher:
    """Stands in for `rag.Searcher` (structural: this file does not import
    `rag`, matching `tools.py`'s own `Searcher` Protocol boundary). Replays a
    scripted list of results (one `search_documents` payload per call, e.g. a
    `rag.SearchResult`), or one fixed `result` reused for every query.
    `user_id` is a plain attribute -- the bound identity a real `Searcher`
    fixes at construction -- so a test can assert it never moves. `.calls`
    mirrors `rag.Searcher.calls`, the field `bot.py`'s attribution wiring
    reads."""

    def __init__(self, script=None, *, result=None, user_id=None):
        self._script = list(script) if script is not None else None
        self._result = result
        self.user_id = user_id
        self.queries = []
        self.calls = []

    def search(self, query):
        self.queries.append(query)
        result = self._script.pop(0) if self._script else self._result
        self.calls.append(result)
        return result


class FakeTelegram:
    """Records `(chat_id, text)`; can be scripted to raise on the n-th send.

    Extended per REQ-V190-TST-02: `edited`/`deleted`/`get_file_calls`/
    `downloads` recorders, and `edit_message_text`/`delete_message`/
    `get_file`/`download_file` methods so a document-flow test can drive
    `process_update` through this one fake, never a socket. `files` is
    seeded by the test (`file_path -> bytes`); `download_errors` scripts a
    raise for a given `file_path` (checked before `files`, so a timeout or
    transport failure can be simulated without seeding any bytes at all).

    Extended per REQ-V1110-OUT-05: `sent_payloads`/`edited_payloads` record
    every `send_message`/`send_message_html` and `edit_message_text`/
    `edit_message_html` call as the payload dict the real `TelegramClient`
    would post (`parse_mode`/`reply_markup` included only when given);
    `callback_answers`/`commands_set` record `answer_callback_query`/
    `set_my_commands` calls (T4/T6 implement the production callers -- these
    are fake recorders only); `fail_html_with` scripts a one-time raise on
    the next `send_message_html` or `edit_message_html` call, for OUT-04's
    fallback tests through the fake. `send_message_html` also appends to
    `sent` so existing assertions over `sent` keep counting messages.
    """

    def __init__(self, fail_on=None, error=None):
        self.sent = []
        self.send_calls = 0
        self._fail_on = fail_on
        self._error = error or RuntimeError("send failed")
        self.edited = []
        self.deleted = []
        self.get_file_calls = []
        self.downloads = []
        self.files: dict[str, bytes] = {}
        self.download_errors: dict[str, Exception] = {}
        self.sent_payloads: list[dict] = []
        self.edited_payloads: list[dict] = []
        self.callback_answers: list[dict] = []
        self.commands_set: list[list[dict]] = []
        self.fail_html_with: Exception | None = None

    def send_message(self, chat_id, text):
        self.send_calls += 1
        if self._fail_on is not None and self.send_calls == self._fail_on:
            raise self._error
        self.sent.append((chat_id, text))
        self.sent_payloads.append({"chat_id": chat_id, "text": text})
        return {"message_id": 100 + self.send_calls}

    def send_message_html(self, chat_id, text, *, reply_markup=None):
        if self.fail_html_with is not None:
            exc, self.fail_html_with = self.fail_html_with, None
            raise exc
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        self.sent_payloads.append(payload)
        self.sent.append((chat_id, text))
        return {"message_id": 100 + len(self.sent)}

    def edit_message_text(self, chat_id, message_id, text):
        self.edited.append((chat_id, message_id, text))
        self.edited_payloads.append({"chat_id": chat_id, "message_id": message_id, "text": text})
        return {"message_id": message_id}

    def edit_message_html(self, chat_id, message_id, text, *, reply_markup=None):
        if self.fail_html_with is not None:
            exc, self.fail_html_with = self.fail_html_with, None
            raise exc
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        self.edited_payloads.append(payload)
        self.edited.append((chat_id, message_id, text))
        return {"message_id": message_id}

    def answer_callback_query(self, callback_query_id, *, text=None):
        payload = {"callback_query_id": callback_query_id}
        if text is not None:
            payload["text"] = text
        self.callback_answers.append(payload)
        return True

    def set_my_commands(self, commands):
        self.commands_set.append(list(commands))
        return True

    def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))
        return True

    def get_file(self, file_id):
        self.get_file_calls.append(file_id)
        return {"file_path": f"documents/{file_id}"}

    def download_file(self, file_path, *, max_bytes, should_stop=None):
        # v1.11.0 T5 (REQ-V1110-ING-04): accepted for signature
        # compatibility with the real `TelegramClient.download_file`, but
        # this fake never streams in chunks, so `should_stop` has nothing
        # to be checked between -- `T-V1110-ING-07`'s own real streamed-
        # cancel coverage goes through the real `TelegramClient` +
        # `httpx.MockTransport` instead, not this fake.
        self.downloads.append((file_path, max_bytes))
        if file_path in self.download_errors:
            raise self.download_errors[file_path]
        if file_path not in self.files:
            # A test bug (forgetting to seed bytes) must never silently
            # impersonate an ERR-01 row via a bare KeyError.
            raise AssertionError(f"no seeded bytes for {file_path!r}")
        data = self.files[file_path]
        if len(data) > max_bytes:
            raise bot.DocumentTooLarge("downloaded file exceeds the size cap")
        return data


def mock_llm_transport(handler):
    """An httpx transport that answers from `handler` instead of the network."""
    return httpx.MockTransport(handler)


class FakeEmbedder:
    """Stands in for `llm.embeddings.EmbeddingsClient` (REQ-V190-TST-02):
    deterministic, no network, same `embed`/`describe` interface. Used by
    this task's own tests and by T5+ (`rag.py`'s vector search).

    The vector is a token-bucket hash, not random noise: each lowercased
    word of the text is hashed into one of `dim` buckets and incremented,
    then L2-normalised. Two texts sharing words land closer in cosine
    distance than two that share none — the minimum structure a "meaningful
    ranking offline" test (`T-V190-RET-03`) needs; a per-call random vector
    would have none.
    """

    def __init__(self, dim=768, *, script=None, hook=None):
        self.dim = dim
        self.calls = []
        self._script = list(script) if script is not None else None
        # v1.11.0 T5 (REQ-V1110-ING-04/-05): called with the 1-based batch
        # number after `calls` records it, before the (possibly scripted)
        # vectors are returned -- a synchronous hook a test can use to set
        # a cancel event, or a blocking one (waiting on a `threading.Event`
        # the test's own thread later `.set()`s) to park a real `_run`
        # thread mid-embedding (`T-V1110-ING-05`, `-09`, `-10`, `-11`,
        # `T-V1110-DOC-05`) -- never a `time.sleep`.
        self._hook = hook

    def describe(self):
        return ("fake", "fake-embedding-model")

    def embed(self, texts, *, conv_id=None):
        texts = list(texts)
        self.calls.append((texts, conv_id))
        if self._hook is not None:
            self._hook(len(self.calls))
        if self._script is not None:
            if not self._script:
                raise AssertionError("FakeEmbedder script exhausted")
            item = self._script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return [self._vector(text) for text in texts]

    def _vector(self, text):
        # `zlib.crc32`, not the builtin `hash()`: str hashing is salted per
        # process (PYTHONHASHSEED), which would make bucket placement -- and
        # so the whole vector -- non-reproducible across runs.
        buckets = [0.0] * self.dim
        for word in re.findall(r"\w+", text.lower()):
            buckets[zlib.crc32(word.encode("utf-8")) % self.dim] += 1.0
        norm = sum(x * x for x in buckets) ** 0.5
        if norm == 0.0:
            return buckets
        return [x / norm for x in buckets]
