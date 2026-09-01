"""Configuration, project paths and secret redaction.

Kept out of the entry point so that `llm/`, `tools.py`, `agent.py` and `bot.py`
can share configuration and redaction without an import cycle.
"""

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
PROVIDERS = ("lmstudio", "openrouter")
FAILOVER_MODES = ("auto", "off")
DEFAULT_DOCKER_IMAGE = "python:3.13-slim"
DEFAULT_FETCH_DOMAINS = "wttr.in"

_DIGITS_RE = re.compile(r"^[0-9]+$")
_TG_ID_RE = re.compile(r"^[1-9][0-9]*$")
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

    # Paths are resolved before anything is created on disk: REQ-V1-CFG-03 must be
    # able to refuse a project-root sandbox without having chmod-ed it first.
    exec_workdir = _resolve(_value(source, "EXEC_WORKDIR") or "./sandbox")
    db_path = _resolve(_value(source, "DB_PATH") or "./bot.db")
    audit_log_path = _resolve(_value(source, "AUDIT_LOG_PATH") or "./exec_audit.jsonl")
    _check_sandbox_placement(exec_workdir, db_path, audit_log_path)

    return Config(
        telegram_bot_token=token,
        allowed_tg_ids=allowed_tg_ids,
        llm_provider=provider,
        lmstudio_base_url=lmstudio_base_url,
        lmstudio_model=lmstudio_model,
        openrouter_api_key=openrouter_api_key,
        openrouter_model=openrouter_model,
        llm_timeout_s=_parse_timeout(_value(source, "LLM_TIMEOUT_S")),
        exec_workdir=_prepare_workdir(exec_workdir),
        db_path=_prepare_db_path(db_path),
        llm_max_tokens=_parse_int(source, "LLM_MAX_TOKENS", 2048, 1, 8192),
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
        return 120.0
    try:
        timeout = float(raw)
    except ValueError:
        raise ConfigError(f"LLM_TIMEOUT_S must be a number, got: {raw}") from None
    if not 0 < timeout <= 600:
        raise ConfigError(f"LLM_TIMEOUT_S must be greater than 0 and at most 600, got: {raw}")
    return timeout


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
    return frozenset(items)
