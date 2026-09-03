"""Configuration, project paths and secret redaction.

Kept out of the entry point so that `llm/`, `tools.py`, `agent.py` and `bot.py`
can share configuration and redaction without an import cycle.
"""

import ipaddress
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import dotenv

# CONTRACT: config.py MUST stay at the repository root; PROJECT_ROOT is derived
# from this file's location, never from os.getcwd().
PROJECT_ROOT = Path(__file__).resolve().parent

REDACTION = "***REDACTED***"
MIN_SECRET_LENGTH = 8
SECRET_FRAGMENT_MIN = 8
PROVIDERS = ("lmstudio", "openrouter")
FAILOVER_MODES = ("auto", "off")
HISTORY_TOOL_STUB_MODES = ("on", "off")
DEFAULT_DOCKER_IMAGE = "python:3.13-slim"
DEFAULT_FETCH_DOMAINS = "wttr.in"
DEFAULT_EXEC_SANDBOX_MAX_BYTES = 268435456
MIN_EXEC_SANDBOX_MAX_BYTES = 1048576
MAX_EXEC_SANDBOX_MAX_BYTES = 4294967296

# v1.3 token-aware tool output (REQ-V13-TOO-02, REQ-V13-TOO-07). The two
# defaults are the inline window a tool result gets in the model's context; the
# ranges are also the clamp the tool arguments `max_output_chars` / `max_chars`
# are held to, so a model that asks for more than the ceiling never widens it.
DEFAULT_EXEC_OUTPUT_CHARS = 1500
MIN_EXEC_OUTPUT_CHARS = 200
MAX_EXEC_OUTPUT_CHARS = 4096
DEFAULT_FETCH_INLINE_CHARS = 5000
MIN_FETCH_INLINE_CHARS = 500
MAX_FETCH_INLINE_CHARS = 20000

# v1.4 addition (REQ-V14-REL-01): v1.3's measured latency model
# (report-v1.3.md:340, `21.1 s + 0.093 s/token`) — a completion budget larger
# than what the timeout can outlast times out and is retried with identical
# parameters, re-sending the whole prompt.
LATENCY_INTERCEPT_S = 21.1
LATENCY_PER_TOKEN_S = 0.093

# v1.2 addition (REQ-V12-SSR-02): scopes `address_scope` can name, and the
# backstop the six is_* flags alone would miss (finding W-6).
FORBIDDEN_SCOPES = ("loopback", "private", "link-local", "multicast",
                    "reserved", "unspecified", "non-global", "unparsable")

_DIGITS_RE = re.compile(r"^[0-9]+$")
_TG_ID_RE = re.compile(r"^[1-9][0-9]*$")
# REQ-V12-SSR-01: a strict domain shape, checked after the four v1.1 clauses.
# Rejects every shortened/hexadecimal IPv4 form by construction: a label made
# only of digits (or "0x..") can never be a valid two-letter-or-more TLD nor an
# `xn--` A-label, so `127.1`, `0x7f.1` and friends fail the last-label check
# below even though they match this shape.
_DOMAIN_SHAPE_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$"
)
_secrets: set[str] = set()


class ConfigError(Exception):
    """A configuration value is missing or invalid."""


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    allowed_tg_ids: frozenset[int]
    llm_provider: str          # "lmstudio" | "openrouter"
    lmstudio_base_url: str
    lmstudio_model: str
    openrouter_api_key: str
    openrouter_model: str
    llm_timeout_s: float
    exec_workdir: Path
    db_path: Path
    # v1 additions. Every one carries a default so that v0 call sites — the ten
    # positional fields above — keep constructing a valid Config (REQ-V1-EC-05).
    llm_max_tokens: int = 2048
    lmstudio_context_length: int = 42496
    openrouter_context_length: int = 131072
    llm_failover: str = "auto"
    exec_docker_image: str = DEFAULT_DOCKER_IMAGE
    audit_log_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "exec_audit.jsonl"
    )
    rate_limit_capacity: int = 10
    rate_limit_refill_s: float = 6.0
    telegram_bot_name: str = ""
    fetch_allowed_domains: frozenset[str] = frozenset({DEFAULT_FETCH_DOMAINS})
    # v1.1 addition (REQ-V11-QTA-01).
    exec_sandbox_max_bytes: int = DEFAULT_EXEC_SANDBOX_MAX_BYTES
    # v1.2 addition (REQ-V12-QTA-03).
    exec_sandbox_clean_on_start: bool = True
    # v1.3 additions (REQ-V13-PRE-04): the inline windows of section 10.1.
    exec_output_default_chars: int = DEFAULT_EXEC_OUTPUT_CHARS
    fetch_inline_default_chars: int = DEFAULT_FETCH_INLINE_CHARS
    # v1.3 addition (REQ-V13-PRE-04, REQ-V13-HST-04): the O2 switch. `off`
    # leaves `_assemble_context` byte-for-byte the un-stubbed assembly.
    history_tool_stub: str = "on"
    # v1.3 additions (REQ-V13-PRE-04): the three pricing variables. Empty is the
    # default everywhere — an unpriced call stores NULL rather than a guess.
    llm_price_ref_model: str = ""
    llm_price_input_usd_per_mtok: float | None = None
    llm_price_output_usd_per_mtok: float | None = None
    # v1.3 addition (REQ-V13-PRE-04, REQ-V13-RTE-01): `<provider>:<model>` for
    # the summary purpose, normalised by `parse_summary_model`. Empty is the
    # default — the summary then runs on the main client, as it always has.
    llm_summary_model: str = ""


def register_secret(value: str) -> None:
    """Remember a value so that `redact` can strip it out of logs and errors."""
    if value and len(value) >= MIN_SECRET_LENGTH:
        _secrets.add(value)


def redact(text: str) -> str:
    """Replace every registered secret in `text` with a fixed placeholder."""
    result = str(text)
    for secret in sorted(_secrets, key=len, reverse=True):
        result = result.replace(secret, REDACTION)
    return result


def max_secret_length() -> int:
    """The length in bytes (UTF-8) of the longest registered secret, or 0."""
    if not _secrets:
        return 0
    return max(len(secret.encode("utf-8")) for secret in _secrets)


def strip_secret_fragment(text: str) -> str:
    """Remove from the end of `text` the longest suffix that is a proper prefix
    of some registered secret and is at least `SECRET_FRAGMENT_MIN` characters
    long. A text ending in a *complete* secret is `redact`'s job, not this
    helper's: only proper (strictly shorter) prefixes are considered here."""
    best_len = 0
    for secret in _secrets:
        max_len = min(len(text), len(secret) - 1)
        for length in range(max_len, SECRET_FRAGMENT_MIN - 1, -1):
            if text.endswith(secret[:length]):
                if length > best_len:
                    best_len = length
                break
    return text[:-best_len] if best_len else text


def parse_summary_model(raw: str) -> tuple[str, str] | None:
    """Split `LLM_SUMMARY_MODEL` into `(provider, model)`; `None` when unset.

    Shared by `load_config` and `llm.build_llm_client` so the routed value is
    read in exactly one way (REQ-V13-RTE-01). Whether the named provider is
    *configured* is a separate question, answered once, in `load_config`.
    """
    value = raw.strip()
    if not value:
        return None
    provider, _, model = value.partition(":")
    provider, model = provider.strip().lower(), model.strip()
    if provider not in PROVIDERS:
        raise ConfigError(
            f"LLM_SUMMARY_MODEL must be '<provider>:<model>' with the provider one of "
            f"{', '.join(PROVIDERS)}, got: {value}"
        )
    if not model:
        raise ConfigError(f"LLM_SUMMARY_MODEL names no model after '{provider}:', got: {value}")
    return provider, model


def load_config(
    env: Mapping[str, str] | None = None,
    *,
    load_env_file: bool = True,
) -> Config:
    if load_env_file:
        dotenv.load_dotenv(PROJECT_ROOT / ".env", override=False)
    source: Mapping[str, str] = os.environ if env is None else env

    token = _required(source, "TELEGRAM_BOT_TOKEN")
    prefix, separator, _ = token.partition(":")
    if not separator or not _DIGITS_RE.match(prefix):
        raise ConfigError("TELEGRAM_BOT_TOKEN is malformed: expected '<digits>:<secret>'")
    register_secret(token)

    allowed_tg_ids = _parse_allowed_ids(_required(source, "ALLOWED_TG_IDS"))

    provider = _value(source, "LLM_PROVIDER").lower() or "lmstudio"
    if provider not in PROVIDERS:
        raise ConfigError(f"LLM_PROVIDER must be one of {', '.join(PROVIDERS)}, got: {provider}")

    lmstudio_base_url = _value(source, "LMSTUDIO_BASE_URL") or "http://localhost:1234/v1"
    lmstudio_model = _value(source, "LMSTUDIO_MODEL")
    openrouter_api_key = _value(source, "OPENROUTER_API_KEY")
    openrouter_model = _value(source, "OPENROUTER_MODEL")

    failover = (_value(source, "LLM_FAILOVER").lower() or "auto")
    if failover not in FAILOVER_MODES:
        raise ConfigError(
            f"LLM_FAILOVER must be one of {', '.join(FAILOVER_MODES)}, got: {failover}"
        )

    history_tool_stub = (_value(source, "HISTORY_TOOL_STUB").lower() or "on")
    if history_tool_stub not in HISTORY_TOOL_STUB_MODES:
        raise ConfigError(
            f"HISTORY_TOOL_STUB must be one of {', '.join(HISTORY_TOOL_STUB_MODES)}, "
            f"got: {history_tool_stub}"
        )

    # REQ-V1-SEC-05: the OpenRouter key is a secret whenever it exists — failover can
    # activate that provider at any time, whatever LLM_PROVIDER says.
    register_secret(openrouter_api_key)

    # REQ-V1-CFG-02: with failover on and both provider sets present, both are
    # validated; otherwise the v0 rule (only the selected provider) stands.
    both_present = bool(lmstudio_model) and bool(openrouter_api_key and openrouter_model)
    validate_both = failover == "auto" and both_present
    if provider == "lmstudio" or validate_both:
        if not lmstudio_base_url.startswith(("http://", "https://")):
            raise ConfigError("LMSTUDIO_BASE_URL must start with http:// or https://")
        if not lmstudio_model:
            raise ConfigError("LMSTUDIO_MODEL is required when LLM_PROVIDER is lmstudio")
    if provider == "openrouter" or validate_both:
        if not openrouter_api_key:
            raise ConfigError("OPENROUTER_API_KEY is required when LLM_PROVIDER is openrouter")
        if not openrouter_model:
            raise ConfigError("OPENROUTER_MODEL is required when LLM_PROVIDER is openrouter")
    lmstudio_base_url = lmstudio_base_url.rstrip("/")

    # REQ-V13-RTE-01: routing the summary to a provider this process has no
    # credentials for is a configuration error, not a runtime surprise. The
    # configured-ness test mirrors `llm.provider_is_configured`, which config.py
    # cannot import (the import goes the other way).
    summary_model = ""
    routed = parse_summary_model(_value(source, "LLM_SUMMARY_MODEL"))
    if routed is not None:
        routed_provider, routed_name = routed
        configured = (
            bool(lmstudio_base_url and lmstudio_model)
            if routed_provider == "lmstudio"
            else bool(openrouter_api_key and openrouter_model)
        )
        if not configured:
            raise ConfigError(
                f"LLM_SUMMARY_MODEL routes the summary to {routed_provider}, "
                f"which is not configured"
            )
        summary_model = f"{routed_provider}:{routed_name}"

    manual_input_price, manual_output_price = _parse_manual_prices(source)

    # Paths are resolved before anything is created on disk: REQ-V1-CFG-03 must be
    # able to refuse a project-root sandbox without having chmod-ed it first.
    exec_workdir = _resolve(_value(source, "EXEC_WORKDIR") or "./sandbox")
    db_path = _resolve(_value(source, "DB_PATH") or "./bot.db")
    audit_log_path = _resolve(_value(source, "AUDIT_LOG_PATH") or "./exec_audit.jsonl")
    _check_sandbox_placement(exec_workdir, db_path, audit_log_path)

    llm_timeout_s = _parse_timeout(_value(source, "LLM_TIMEOUT_S"))
    llm_max_tokens = _parse_int(source, "LLM_MAX_TOKENS", 2048, 1, 8192)
    _check_timeout_budget(llm_timeout_s, llm_max_tokens)

    return Config(
        telegram_bot_token=token,
        allowed_tg_ids=allowed_tg_ids,
        llm_provider=provider,
        lmstudio_base_url=lmstudio_base_url,
        lmstudio_model=lmstudio_model,
        openrouter_api_key=openrouter_api_key,
        openrouter_model=openrouter_model,
        llm_timeout_s=llm_timeout_s,
        exec_workdir=_prepare_workdir(exec_workdir),
        db_path=_prepare_db_path(db_path),
        llm_max_tokens=llm_max_tokens,
        lmstudio_context_length=_parse_int(
            source, "LMSTUDIO_CONTEXT_LENGTH", 42496, 2048, 2_000_000
        ),
        openrouter_context_length=_parse_int(
            source, "OPENROUTER_CONTEXT_LENGTH", 131072, 2048, 2_000_000
        ),
        llm_failover=failover,
        exec_docker_image=_parse_docker_image(source.get("EXEC_DOCKER_IMAGE")),
        audit_log_path=_prepare_audit_path(audit_log_path),
        rate_limit_capacity=_parse_int(source, "RATE_LIMIT_CAPACITY", 10, 1, 100),
        rate_limit_refill_s=_parse_float(source, "RATE_LIMIT_REFILL_S", 6.0, 3600.0),
        telegram_bot_name=_value(source, "TELEGRAM_BOT_NAME"),
        fetch_allowed_domains=_parse_domains(_value(source, "FETCH_ALLOWED_DOMAINS")),
        exec_sandbox_max_bytes=_parse_int(
            source, "EXEC_SANDBOX_MAX_BYTES", DEFAULT_EXEC_SANDBOX_MAX_BYTES,
            MIN_EXEC_SANDBOX_MAX_BYTES, MAX_EXEC_SANDBOX_MAX_BYTES,
        ),
        exec_sandbox_clean_on_start=_parse_bool(
            source, "EXEC_SANDBOX_CLEAN_ON_START", True
        ),
        exec_output_default_chars=_parse_int(
            source, "EXEC_OUTPUT_DEFAULT_CHARS", DEFAULT_EXEC_OUTPUT_CHARS,
            MIN_EXEC_OUTPUT_CHARS, MAX_EXEC_OUTPUT_CHARS,
        ),
        fetch_inline_default_chars=_parse_int(
            source, "FETCH_INLINE_DEFAULT_CHARS", DEFAULT_FETCH_INLINE_CHARS,
            MIN_FETCH_INLINE_CHARS, MAX_FETCH_INLINE_CHARS,
        ),
        history_tool_stub=history_tool_stub,
        llm_price_ref_model=_value(source, "LLM_PRICE_REF_MODEL"),
        llm_price_input_usd_per_mtok=manual_input_price,
        llm_price_output_usd_per_mtok=manual_output_price,
        llm_summary_model=summary_model,
    )


def _value(source: Mapping[str, str], key: str) -> str:
    return (source.get(key) or "").strip()


def _required(source: Mapping[str, str], key: str) -> str:
    value = _value(source, key)
    if not value:
        raise ConfigError(f"{key} is required and must not be empty")
    return value


def _parse_allowed_ids(raw: str) -> frozenset[int]:
    items = [item.strip() for item in raw.split(",")]
    items = [item for item in items if item]
    if not items:
        raise ConfigError("ALLOWED_TG_IDS must contain at least one Telegram user id")
    for item in items:
        if not _TG_ID_RE.match(item):
            raise ConfigError(f"ALLOWED_TG_IDS contains an invalid Telegram user id: {item}")
    return frozenset(int(item) for item in items)


def _parse_timeout(raw: str) -> float:
    if not raw:
        # REQ-V14-REL-01: 120 no longer clears the latency-model floor at the
        # default LLM_MAX_TOKENS (2048) — supersedes EC-05 for this field only.
        return 240.0
    try:
        timeout = float(raw)
    except ValueError:
        raise ConfigError(f"LLM_TIMEOUT_S must be a number, got: {raw}") from None
    if not 0 < timeout <= 600:
        raise ConfigError(f"LLM_TIMEOUT_S must be greater than 0 and at most 600, got: {raw}")
    return timeout


def _check_timeout_budget(llm_timeout_s: float, llm_max_tokens: int) -> None:
    """REQ-V14-REL-01: a completion budget the timeout cannot outlast times
    out and is retried with identical parameters, re-sending the whole
    prompt. Raise before that pair ever reaches a live request."""
    floor = LATENCY_INTERCEPT_S + LATENCY_PER_TOKEN_S * llm_max_tokens
    if llm_timeout_s < floor:
        raise ConfigError(
            f"LLM_TIMEOUT_S ({llm_timeout_s}) is below the latency-model floor "
            f"for LLM_MAX_TOKENS ({llm_max_tokens}): needs at least {floor:.3f}s "
            f"({LATENCY_INTERCEPT_S} + {LATENCY_PER_TOKEN_S} * llm_max_tokens). "
            "Raise LLM_TIMEOUT_S or lower LLM_MAX_TOKENS."
        )


def _resolve(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _prepare_workdir(value: str) -> Path:
    workdir = _resolve(value)
    try:
        workdir.mkdir(parents=True, exist_ok=True)
        workdir.chmod(0o700)
    except OSError as exc:
        raise ConfigError(
            f"EXEC_WORKDIR could not be created: {exc.__class__.__name__}"
        ) from None
    if not workdir.is_dir():
        raise ConfigError("EXEC_WORKDIR is not a directory")
    return workdir


def _prepare_db_path(value: str) -> Path:
    db_path = _resolve(value)
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigError(
            f"DB_PATH parent directory could not be created: {exc.__class__.__name__}"
        ) from None
    return db_path


def _prepare_audit_path(audit_log_path: Path) -> Path:
    try:
        audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigError(
            f"AUDIT_LOG_PATH parent directory could not be created: {exc.__class__.__name__}"
        ) from None
    return audit_log_path


def _check_sandbox_placement(exec_workdir: Path, db_path: Path, audit_log_path: Path) -> None:
    """REQ-V1-CFG-03: the container mounts EXEC_WORKDIR read-write, so no state and
    no secret may live inside it."""
    # REQ-V11-CFV-02: subsumes the "not the project root itself" check below for
    # ordinary cases, but that check stays as delivered.
    if not _is_strict_descendant(exec_workdir, PROJECT_ROOT):
        raise ConfigError(
            f'EXEC_WORKDIR must live inside the project directory; got "{exec_workdir}"'
        )
    if _same(exec_workdir, PROJECT_ROOT):
        raise ConfigError(
            "EXEC_WORKDIR must not be the project root: the exec container mounts it "
            "read-write"
        )
    for name, target in (
        ("DB_PATH", db_path),
        ("AUDIT_LOG_PATH", audit_log_path),
        (".env", PROJECT_ROOT / ".env"),
    ):
        if _contains(exec_workdir, target):
            raise ConfigError(
                f"EXEC_WORKDIR must not contain {name}: the exec container mounts "
                "EXEC_WORKDIR read-write"
            )


def _normalized(path: Path) -> Path:
    """Follows symlinks, exactly like the `.resolve()` the container mount uses —
    otherwise a symlinked EXEC_WORKDIR would pass the check and still mount the
    project root read-write."""
    try:
        return path.resolve()
    except OSError:
        return Path(os.path.normpath(str(path)))


def _same(left: Path, right: Path) -> bool:
    return _normalized(left) == _normalized(right)


def _contains(parent: Path, child: Path) -> bool:
    parent, child = _normalized(parent), _normalized(child)
    return parent == child or parent in child.parents


def _is_strict_descendant(child: Path, parent: Path) -> bool:
    child, parent = _normalized(child), _normalized(parent)
    return parent != child and parent in child.parents


def _parse_int(source: Mapping[str, str], key: str, default: int, low: int, high: int) -> int:
    raw = _value(source, key)
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        raise ConfigError(f"{key} must be an integer, got: {raw}") from None
    if not low <= parsed <= high:
        raise ConfigError(f"{key} must be between {low} and {high}, got: {raw}")
    return parsed


def _parse_float(source: Mapping[str, str], key: str, default: float, high: float) -> float:
    raw = _value(source, key)
    if not raw:
        return default
    try:
        parsed = float(raw)
    except ValueError:
        raise ConfigError(f"{key} must be a number, got: {raw}") from None
    if not 0 < parsed <= high:
        raise ConfigError(f"{key} must be greater than 0 and at most {high:g}, got: {raw}")
    return parsed


def _parse_manual_prices(
    source: Mapping[str, str],
) -> tuple[float | None, float | None]:
    """The manual fallback prices of REQ-V13-PRE-04: both or neither. Half a
    pair would price one half of every call and silently omit the other."""
    keys = ("LLM_PRICE_INPUT_USD_PER_MTOK", "LLM_PRICE_OUTPUT_USD_PER_MTOK")
    raw_input, raw_output = (_value(source, key) for key in keys)
    if not raw_input and not raw_output:
        return None, None
    for key, raw in zip(keys, (raw_input, raw_output)):
        if not raw:
            raise ConfigError(f"{key} is required when {_other(keys, key)} is set")
    return _parse_price(keys[0], raw_input), _parse_price(keys[1], raw_output)


def _other(keys: tuple[str, str], key: str) -> str:
    return keys[1] if key == keys[0] else keys[0]


def _parse_price(key: str, raw: str) -> float:
    """A price of zero is legitimate (a free model); a negative one is not, and
    neither is an infinity or a NaN, which would poison every sum built on it."""
    try:
        price = float(raw)
    except ValueError:
        raise ConfigError(f"{key} must be a number, got: {raw}") from None
    if not math.isfinite(price) or price < 0:
        raise ConfigError(f"{key} must be a non-negative number, got: {raw}")
    return price


def _parse_bool(source: Mapping[str, str], key: str, default: bool) -> bool:
    raw = _value(source, key).casefold()
    if not raw:
        return default
    if raw in ("true", "1", "yes", "on"):
        return True
    if raw in ("false", "0", "no", "off"):
        return False
    raise ConfigError(f"{key} must be a boolean (true/false), got: {raw}")


def address_scope(addr: str) -> str | None:
    """The first matching forbidden scope for `addr`, or `None` for an ordinary
    public address (REQ-V12-SSR-02). Never raises: an unparsable string is its
    own scope, `"unparsable"`, rather than an exception the caller must guard."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return "unparsable"
    if ip.is_loopback:
        return "loopback"
    if ip.is_private:
        return "private"
    if ip.is_link_local:
        return "link-local"
    if ip.is_multicast:
        return "multicast"
    if ip.is_reserved:
        return "reserved"
    if ip.is_unspecified:
        return "unspecified"
    # Backstop: the six flags above enumerate known-forbidden *forms*, and an
    # address such as carrier-grade NAT (100.64.0.0/10) sets none of them while
    # still being non-routable on the public internet.
    if not ip.is_global:
        return "non-global"
    return None


def _parse_docker_image(raw: str | None) -> str:
    """An unset variable takes the default; a set-but-blank one is a configuration
    error rather than a silent fallback."""
    if not raw:
        return DEFAULT_DOCKER_IMAGE
    image = raw.strip()
    if not image:
        raise ConfigError("EXEC_DOCKER_IMAGE must not be empty")
    return image


def _parse_domains(raw: str) -> frozenset[str]:
    if not raw:
        return frozenset({DEFAULT_FETCH_DOMAINS})
    items = [item.strip().casefold() for item in raw.split(",")]
    items = [item for item in items if item]
    if not items:
        raise ConfigError("FETCH_ALLOWED_DOMAINS must contain at least one domain")
    for item in items:
        _reject_ssrf_shaped_domain(item)
    return frozenset(items)


def _reject_ssrf_shaped_domain(entry: str) -> None:
    """REQ-V11-CFV-01: reject the misconfigurations that silently reproduce the
    posture v1 claims to prevent (findings V-6/V-7)."""
    is_ip = True
    try:
        ipaddress.ip_address(entry.strip("[]"))
    except ValueError:
        is_ip = False
    if is_ip:
        raise ConfigError(
            f'FETCH_ALLOWED_DOMAINS rejects "{entry}": IP literals are not allowed (SSRF)'
        )
    if entry == "localhost" or entry.endswith(".localhost"):
        raise ConfigError(f'FETCH_ALLOWED_DOMAINS rejects "{entry}": localhost is not allowed')
    if "." not in entry:
        raise ConfigError(
            f'FETCH_ALLOWED_DOMAINS rejects "{entry}": bare hostnames are not allowed'
        )
    if ":" in entry or "/" in entry:
        raise ConfigError(
            f'FETCH_ALLOWED_DOMAINS rejects "{entry}": ports or paths are not allowed'
        )
    if not _DOMAIN_SHAPE_RE.match(entry):
        raise ConfigError(
            f'FETCH_ALLOWED_DOMAINS rejects "{entry}": does not look like a domain name'
        )
    last_label = entry.rsplit(".", 1)[-1]
    if not ((last_label.isalpha() and len(last_label) >= 2) or last_label.startswith("xn--")):
        raise ConfigError(
            f'FETCH_ALLOWED_DOMAINS rejects "{entry}": '
            f'"{last_label}" is not a valid top-level domain'
        )
