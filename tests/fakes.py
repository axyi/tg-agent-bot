"""Test doubles. None of them performs I/O."""

import re
import subprocess
import zlib

import httpx

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
    ):
        # The agent reuses one `messages` list, so snapshot it before it grows.
        self.calls.append((list(messages), tool_definitions))
        self.max_tokens_calls.append(max_tokens)
        self.reasoning_calls.append(reasoning)
        self.timeout_s_calls.append(timeout_s)
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


class FakeTelegram:
    """Records `(chat_id, text)`; can be scripted to raise on the n-th send."""

    def __init__(self, fail_on=None, error=None):
        self.sent = []
        self.send_calls = 0
        self._fail_on = fail_on
        self._error = error or RuntimeError("send failed")

    def send_message(self, chat_id, text):
        self.send_calls += 1
        if self._fail_on is not None and self.send_calls == self._fail_on:
            raise self._error
        self.sent.append((chat_id, text))


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

    def __init__(self, dim=768, *, script=None):
        self.dim = dim
        self.calls = []
        self._script = list(script) if script is not None else None

    def describe(self):
        return ("fake", "fake-embedding-model")

    def embed(self, texts, *, conv_id=None):
        texts = list(texts)
        self.calls.append((texts, conv_id))
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
