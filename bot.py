"""Entry point: Telegram long polling, update dispatch and the two selftests.

The process is single-threaded and sequential: updates are handled strictly one
at a time. The only threads are the two output readers created per `exec` call.
"""

import functools
import json
import logging
import os
import random
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import httpx

import agent
import config
import metrics
import storage
import tools
from config import PROJECT_ROOT, PROVIDERS, Config, ConfigError, load_config, redact
from llm import build_llm_client, pricing, provider_is_configured
from llm.base import CostResolver, LLMResponse, ToolCall

TELEGRAM_API_HOST = "https://api.telegram.org"
LONG_POLL_TIMEOUT_S = 50
GET_UPDATES_READ_TIMEOUT_S = 60.0
DEFAULT_READ_TIMEOUT_S = 20.0
MESSAGE_LIMIT = 4096
MAX_BACKOFF_S = 30.0

SEND_ATTEMPT_LIMIT = 3            # total attempts per send/edit call
SEND_TRANSPORT_SLEEP_S = 2.0
MAX_MESSAGE_CHARS = 4000          # the accepted length of one user message
STATUS_MAX_CHARS = 64
LIVE_READ_TIMEOUT_S = 30.0
PROVIDER_OVERRIDE_KEY = "provider_override"
PRICING_STATE_KEY = "pricing_json"    # REQ-V13-PRC-02: the persisted price snapshot
STATS_MAX_CHARS = 3500            # REQ-V13-OBS-07
REAP_TIMEOUT_S = 15.0             # REQ-V11-ORP-02

NON_TEXT_REPLY = "I can only process plain text messages."
NEW_CONVERSATION_REPLY = "New conversation started."
RATE_LIMIT_REPLY = "Rate limit exceeded. Please wait a moment."
TOO_LONG_REPLY = "Message too long (over 4000 characters). Please shorten it."
SUMMARY_FAILED_REPLY = "Could not summarize this conversation right now."
NOTHING_TO_SUMMARIZE_REPLY = "Nothing to summarize yet."
MODEL_USAGE_REPLY = "Usage: /model [lmstudio|openrouter|auto]"
STATUS_WORKING = "⚙️ working…"
STATUS_DONE = "✅ done"
USAGE = "usage: bot.py [--selftest|--selftest-live]"

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

    def call(self, method: str, payload: dict, *, read_timeout: float) -> dict:
        # The URL embeds the bot token: never log it, redacted or not.
        url = f"{TELEGRAM_API_HOST}/bot{self._token}/{method}"
        timeout = httpx.Timeout(connect=10.0, read=read_timeout, write=10.0, pool=10.0)
        try:
            response = self._client.post(url, json=payload, timeout=timeout)
        except httpx.TransportError as exc:
            raise TelegramError(
                redact(f"telegram {method} transport error: {exc.__class__.__name__}"),
                transport=True,
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

    def _call_with_retry(self, method: str, payload: dict) -> dict:
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
        payload = {"timeout": LONG_POLL_TIMEOUT_S, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload, read_timeout=GET_UPDATES_READ_TIMEOUT_S)

    def send_message(self, chat_id: int, text: str) -> dict:
        return self._call_with_retry("sendMessage", {"chat_id": chat_id, "text": text})

    def edit_message_text(self, chat_id: int, message_id: int, text: str) -> dict:
        return self._call_with_retry(
            "editMessageText",
            {"chat_id": chat_id, "message_id": message_id, "text": text},
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

    def on_tool(self, name: str, first_argument: str) -> None:
        if self._disabled:
            return
        if self._message_id is None:
            self._start()
            if self._message_id is None:
                return
        if name in ("exec", "fetch"):
            self._edit(_status_line(name, first_argument))

    def finish(self) -> None:
        if self._message_id is not None and not self._disabled:
            self._edit(STATUS_DONE)

    def _start(self) -> None:
        try:
            result = self._tg.send_message(self._chat_id, STATUS_WORKING)
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
        os.unlink(entry)
        return
    failed_paths: list[str] = []
    shutil.rmtree(entry, onexc=lambda _func, path, _exc: failed_paths.append(path))
    if failed_paths:
        for path in failed_paths:
            # REQ-V13-CO-01: `os.chmod` follows symlinks, so a symlink the
            # first pass could not unlink would have its *target* — a
            # bot-owned file anywhere on the host — chmod-ed to `u+rwX`.
            # A symlink never needs a mode change: unlinking it needs only
            # its parent directory's mode, which this same loop fixes.
            if os.path.islink(path):
                continue
            os.chmod(path, stat.S_IRWXU)
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
                entry, exc.__class__.__name__,
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
            ["docker", "ps", "-a", "--filter", f"label={tools.CONTAINER_LABEL}",
             "--format", _REAP_PS_FORMAT],
            timeout=REAP_TIMEOUT_S, capture_output=True, env=tools._probe_env(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("orphan container reap failed: %s", redact(str(exc)))
        return
    if listed.returncode != 0:
        log.warning("orphan container reap failed: docker ps exited %d", listed.returncode)
        return
    lines = [
        line for line in listed.stdout.decode("utf-8", errors="replace").split("\n") if line
    ]
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
            timeout=REAP_TIMEOUT_S, capture_output=True, env=tools._probe_env(),
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
        os.fchmod(fd, 0o644)          # exact perms regardless of umask
    finally:
        os.close(fd)
    return path


def _refuse_shared_parent(parent: Path) -> None:
    """A sticky world-writable directory such as `/tmp` still allows the race
    on a pre-existing file, which `O_NOFOLLOW` + `O_TRUNC` + the `fstat`
    checks above defeat; a non-sticky one does not even need a pre-existing
    file, so it is refused outright."""
    st = os.stat(parent)
    if (st.st_mode & 0o002) and not (st.st_mode & stat.S_ISVTX):
        raise ConfigError(
            f'"{parent}" is world-writable and not sticky; move DB_PATH out of '
            "a shared directory"
        )


def load_provider_override(conn: sqlite3.Connection) -> str | None:
    value = storage.get_state(conn, PROVIDER_OVERRIDE_KEY)
    return value if value in PROVIDERS else None


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
    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        log.info("update %d is not a text message; answered with a hint", update_id)
        _send(tg, chat_id, [NON_TEXT_REPLY])
        return
    if len(text) > MAX_MESSAGE_CHARS:
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
            _send(tg, chat_id, split_message(_render_status(
                conn, cfg, llm, skills, docker_version, docker_ok,
                load_provider_override(conn), from_id,
            )))
            return
        if name == "/stats":
            _send(tg, chat_id, split_message(_render_stats(conn, from_id)))
            return
        if name == "/summary":
            _handle_summary(conn, tg, cfg, llm, chat_id, from_id, resolve_cost, summary_llm)
            return
        if name == "/model":
            parts = stripped.split()
            _handle_model(
                conn, tg, cfg, llm, chat_id,
                parts[1] if len(parts) > 1 else "", set_provider,
            )
            return
        if name == "/reload_skills":
            _handle_reload_skills(tg, skills, chat_id)
            return

    conv_id = storage.get_or_create_active_conversation(conn, from_id)
    storage.add_user_message(conn, conv_id, redact(text))
    status = _StatusMessage(tg, chat_id)
    reply = agent.run_agent(
        conn=conn,
        conv_id=conv_id,
        llm=llm,
        skills=skills,
        runner=runner,
        now=storage.utc_now_iso(),
        cfg=cfg,
        fetcher=fetcher,
        audit=functools.partial(_write_audit, cfg.audit_log_path, from_id, conv_id),
        recent_goals=storage.recent_goals(conn, from_id),
        should_stop=lambda: _shutdown,
        on_tool=status.on_tool,
        resolve_cost=resolve_cost,
    )
    status.finish()
    _send(tg, chat_id, split_message(reply))


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
    conn, tg, cfg: Config, llm, chat_id: int, from_id: int,
    resolve_cost: CostResolver | None = None, summary_llm=None,
) -> None:
    conv_id = storage.get_or_create_active_conversation(conn, from_id)
    if len(storage.load_context_messages(conn, conv_id, agent.CONTEXT_WINDOW_MESSAGES)) >= 2:
        try:
            summary = agent.summarize_conversation(
                # REQ-V13-RTE-01: the summary purpose, and only it, may run on
                # the routed client; `summary_llm` is None unless it is configured.
                conn, conv_id, summary_llm or llm, cfg, resolve_cost=resolve_cost
            )
            if summary is not None:
                storage.add_summary(conn, conv_id, from_id, summary)
        except Exception as exc:      # summarization never blocks /new
            log.warning("summarizing the outgoing conversation failed: %s", redact(str(exc)))
    storage.start_new_conversation(conn, from_id)
    _send(tg, chat_id, [NEW_CONVERSATION_REPLY])


def _handle_summary(
    conn, tg, cfg: Config, llm, chat_id: int, from_id: int,
    resolve_cost: CostResolver | None = None, summary_llm=None,
) -> None:
    conv_id = storage.get_or_create_active_conversation(conn, from_id)
    if len(storage.load_context_messages(conn, conv_id, agent.CONTEXT_WINDOW_MESSAGES)) < 2:
        _send(tg, chat_id, [NOTHING_TO_SUMMARIZE_REPLY])
        return
    try:
        summary = agent.summarize_conversation(
            conn, conv_id, summary_llm or llm, cfg, resolve_cost=resolve_cost
        )
    except Exception as exc:
        log.warning("summarizing on request failed: %s", redact(str(exc)))
        summary = None
    if summary is None:
        _send(tg, chat_id, [SUMMARY_FAILED_REPLY])
        return
    storage.add_summary(conn, conv_id, from_id, summary)
    _send(tg, chat_id, split_message(_render_summary(summary)))


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
        f"Tokens this conversation: in {here.tokens_in or 0} / out {here.tokens_out or 0}"
    )


def _render_stats(conn, from_id: int) -> str:
    """REQ-V13-OBS-07. Two columns — this conversation and all time — over the
    rows `agent.py` recorded. Reading them never opens a conversation."""
    conv_id = storage.active_conversation_id(conn, from_id)
    here = metrics.conversation_stats(conn, conv_id)
    everywhere = metrics.global_stats(conn)
    return _fit([
        "Stats (this conversation | all time)",
        f"LLM calls: {here.calls} | {everywhere.calls} "
        f"(errors {here.errors} | {everywhere.errors})",
        f"Tokens in: {_pair(here.tokens_in, everywhere.tokens_in)} "
        f"(cached: {_pair(here.cached_tokens, everywhere.cached_tokens)}, "
        f"reasoning: {_pair(here.reasoning_tokens, everywhere.reasoning_tokens)})",
        f"Tokens out: {_pair(here.tokens_out, everywhere.tokens_out)}",
        f"Est. cost: {_render_cost(here.cost_usd)} | {_render_cost(everywhere.cost_usd)} "
        f"(basis: {_pair(here.cost_basis, everywhere.cost_basis)})",
        f"Avg prompt/call: {_pair(here.avg_prompt, everywhere.avg_prompt)}; "
        f"re-sent share: {_pair(here.resent_share, everywhere.resent_share, _render_share)}",
        f"Top tools by output tokens (all time): {_render_top_tools(conn)}",
        f"Last turn: {_render_last_turn(conn, conv_id)}",
    ])


def _fit(lines: list[str]) -> str:
    """Hold the character cap without breaking the fixed layout: whole lines go
    from the end, never half of one. Every line is bounded by a limit of its own
    (`ROUND_LIMIT` rounds, `TOP_TOOLS_LIMIT` tools), so this only ever fires on
    an absurdly long `cost_basis`; the final slice is the hard guarantee."""
    while len(lines) > 1 and len("\n".join(lines)) > STATS_MAX_CHARS:
        lines.pop()
    return "\n".join(lines)[:STATS_MAX_CHARS]


def _pair(left, right, render=None) -> str:
    render = render or (lambda value: str(value))
    return f"{_cell(left, render)} | {_cell(right, render)}"


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
    return ", ".join(
        f"{tool} {tokens} ({round(share * 100)}%)" for tool, tokens, share in ranked
    )


def _render_last_turn(conn, conv_id: int | None) -> str:
    timeline = metrics.turn_timeline(conn, conv_id) if conv_id is not None else []
    if not timeline:
        return "none"
    parts = []
    for entry in timeline:
        part = (f"r{entry['round']} in {_cell(entry['prompt_tokens'], str)} "
                f"out {_cell(entry['completion_tokens'], str)}")
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


def _handle_model(
    conn, tg, cfg: Config, llm, chat_id: int, argument: str, set_provider
) -> None:
    override = load_provider_override(conn)
    if not argument:
        _send(tg, chat_id, [
            f"Provider: {_active_provider(cfg, llm, override)} "
            f"(override: {override or 'none'}, failures: {_render_failures(llm)})"
        ])
        return
    choice = argument.casefold()
    if choice == "auto":
        storage.delete_state(conn, PROVIDER_OVERRIDE_KEY)
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
    storage.set_state(conn, PROVIDER_OVERRIDE_KEY, choice)
    if set_provider is not None:
        set_provider(choice)
    _send(tg, chat_id, [f"Provider switched to {choice}."])


def _handle_reload_skills(tg, skills: dict, chat_id: int) -> None:
    loaded = tools.load_skills(PROJECT_ROOT / "skills")
    # The registry object is the one later messages read, so it is replaced in
    # place rather than rebound.
    skills.clear()
    skills.update(loaded)
    names = ", ".join(sorted(skills)) if skills else "none"
    _send(tg, chat_id, [f"Skills reloaded: {len(skills)} ({names})."])


def _send(tg, chat_id: int, parts: list[str]) -> None:
    """Send the parts in order; stop at the first failure (at-most-once)."""
    for part in parts:
        try:
            tg.send_message(chat_id, redact(part))
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
    limiter: RateLimiter | None = None,
    fetcher=None,
    docker_version: str | None = None,
    docker_ok: bool = False,
    set_provider: Callable[[str | None], object] | None = None,
    get_llm: Callable[[], object] | None = None,
    resolve_cost: CostResolver | None = None,
    summary_llm=None,
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

    def describe(self) -> tuple[str, str]:
        return ("selftest", "selftest")

    def complete(self, messages, tool_definitions, *, max_tokens=None) -> LLMResponse:
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

    def send_message(self, chat_id: int, text: str) -> dict:
        if text == STATUS_WORKING:
            self.status.append((chat_id, text))
            return {"message_id": 1}
        self.sent.append((chat_id, text))
        return {"message_id": 100 + len(self.sent)}

    def edit_message_text(self, chat_id: int, message_id: int, text: str) -> dict:
        self.edits.append((chat_id, message_id, text))
        return {"message_id": message_id}


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
            storage.init_schema(conn)
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

    answers = [
        row for row in rows if row["role"] == "assistant" and row["tool_calls_json"] is None
    ]
    if len(answers) != 1 or answers[0]["content"] != "selftest ok":
        return "the final assistant message was not stored exactly once"

    if tg.sent != [(424242, "selftest ok")]:
        return "the reply was not recorded exactly once"
    if tg.status != [(424242, STATUS_WORKING)]:
        return "the status message was not sent exactly once"
    edits = [text for _chat, _mid, text in tg.edits]
    if len(edits) != 2 or not edits[0].startswith("⚙️ exec: ") or edits[1] != STATUS_DONE:
        return "the status message was not edited through the expected states"
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
            storage.init_schema(conn)
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
    if not (cfg.lmstudio_base_url and cfg.lmstudio_model):
        print("live: SKIP lmstudio (not configured)")
        return 0
    try:
        response = client.get(f"{cfg.lmstudio_base_url}/models", timeout=LIVE_READ_TIMEOUT_S)
        if response.status_code != 200:
            return _live_fail(
                "lmstudio", f"http {response.status_code}: {response.text[:200]}"
            )
        body = response.json()
    except Exception as exc:
        return _live_fail("lmstudio", exc)
    models = [entry.get("id") for entry in (body.get("data") or [])]
    if cfg.lmstudio_model not in models:
        return _live_fail("lmstudio", f"model {cfg.lmstudio_model} is not loaded")
    print("live: OK lmstudio")
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


def main(argv: list[str] | None = None) -> int:
    global _started_at
    arguments = list(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    if arguments == ["--selftest"]:
        return run_selftest()
    if arguments == ["--selftest-live"]:
        return run_selftest_live()
    if arguments:
        print(USAGE)
        return 2

    try:
        cfg = load_config()
    except ConfigError as exc:
        log.error("configuration error: %s", redact(str(exc)))
        return 2

    _started_at = time.monotonic()
    conn = storage.connect(cfg.db_path)
    storage.init_schema(conn)
    skills = tools.load_skills(PROJECT_ROOT / "skills")
    client = httpx.Client()
    tg = TelegramClient(cfg.telegram_bot_token, client=client)
    try:
        bot_username = tg.get_me()["username"]
    except (TelegramError, KeyError, TypeError) as exc:
        log.error("cannot identify the bot: %s", redact(str(exc)))
        client.close()
        conn.close()
        return 2

    docker_version, docker_ok = exec_backend_status()
    try:
        wrap_timeout, empty_resolv = _startup_docker_wiring(cfg, docker_ok)
    except ConfigError as exc:
        # REQ-V12-ERR-01: a configuration refusal must look like one, not an
        # unhandled traceback — whether it comes from `load_config` above or
        # from this seam (REQ-V12-INF-01, REQ-V12-SSR-02).
        log.error("configuration error: %s", redact(str(exc)))
        client.close()
        conn.close()
        return 2
    override = load_provider_override(conn)
    live = {"llm": build_llm_client(cfg, client=client, override=override)}

    def set_provider(name: str | None):
        live["llm"] = build_llm_client(cfg, client=client, override=name)
        return live["llm"]

    # REQ-V13-RTE-01: a second client, on the same `httpx.Client`, only when the
    # routing is configured. Unset it stays None so the summary keeps running on
    # whichever client `/model` has selected, exactly as before.
    summary_llm = (
        build_llm_client(cfg, client=client, purpose="summary")
        if cfg.llm_summary_model
        else None
    )

    # REQ-V13-PRC-02: once, at startup, and never per message.
    resolve_cost = build_cost_resolver(conn, cfg, client)

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
        )
    finally:
        client.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
