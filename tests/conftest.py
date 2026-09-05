import socket

import httpx
import pytest

import config as config_module
import storage


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any real outbound HTTP request fails the test."""
    def _forbidden(self, request):
        raise AssertionError(
            f"unexpected network request: {request.method} {request.url.host}")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _forbidden)


@pytest.fixture(autouse=True)
def no_dns(monkeypatch):
    """REQ-V12-OFF-01: DNS is barred as well as HTTP. Any test that needs
    resolution must inject its own stub; none may reach the real resolver."""
    def _forbidden(host, *args, **kwargs):
        raise AssertionError(f"unexpected DNS lookup: {host}")
    monkeypatch.setattr(socket, "getaddrinfo", _forbidden)


@pytest.fixture(autouse=True)
def isolated_project_root(monkeypatch, tmp_path):
    """The developer's real .env is never visible to a test."""
    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)


@pytest.fixture(autouse=True)
def no_real_bind(monkeypatch):
    """REQ-V160-SRV-05: nothing but the bot's own dashboard-server construction
    may bind a port, and even that must bind port 0 in a test. Any other bind
    target (a real port, a real socket path) raises, naming the address."""
    real_bind = socket.socket.bind

    def _guarded_bind(self, address, *args, **kwargs):
        if address == ("127.0.0.1", 0):
            return real_bind(self, address, *args, **kwargs)
        raise RuntimeError(f"unexpected bind: {address!r}")

    monkeypatch.setattr(socket.socket, "bind", _guarded_bind)


@pytest.fixture
def conn(tmp_path):
    c = storage.connect(tmp_path / "test.db")
    storage.init_schema(c)
    yield c
    c.close()
