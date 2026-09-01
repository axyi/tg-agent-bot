"""Test doubles. None of them performs I/O."""

import subprocess

import httpx

import tools
from llm.base import LLMError

_DEFAULT_ENVELOPE = {
    "exit_code": 0,
    "timed_out": False,
    "truncated": False,
    "stdout": "recorded\n",
    "stderr": "",
}

_DEFAULT_FETCH_ENVELOPE = {
    "status_code": 200,
    "truncated": False,
    "body": "recorded",
    "notice": tools.UNTRUSTED_NOTICE,
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

    def complete(self, messages, tool_definitions, *, max_tokens=None):
        # The agent reuses one `messages` list, so snapshot it before it grows.
        self.calls.append((list(messages), tool_definitions))
        self.max_tokens_calls.append(max_tokens)
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

    def __call__(self, url):
        self.urls.append(url)
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
