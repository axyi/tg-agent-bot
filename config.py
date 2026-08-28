"""Configuration, project paths and secret redaction.

Kept out of the entry point so that `llm/`, `tools.py`, `agent.py` and `bot.py`
can share configuration and redaction without an import cycle.
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import dotenv

# CONTRACT: config.py MUST stay at the repository root; PROJECT_ROOT is derived
# from this file's location, never from os.getcwd().
PROJECT_ROOT = Path(__file__).resolve().parent

REDACTION = "***REDACTED***"
MIN_SECRET_LENGTH = 8
PROVIDERS = ("lmstudio", "openrouter")

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

    if provider == "lmstudio":
        if not lmstudio_base_url.startswith(("http://", "https://")):
            raise ConfigError("LMSTUDIO_BASE_URL must start with http:// or https://")
        if not lmstudio_model:
            raise ConfigError("LMSTUDIO_MODEL is required when LLM_PROVIDER is lmstudio")
    else:
        if not openrouter_api_key:
            raise ConfigError("OPENROUTER_API_KEY is required when LLM_PROVIDER is openrouter")
        if not openrouter_model:
            raise ConfigError("OPENROUTER_MODEL is required when LLM_PROVIDER is openrouter")
        register_secret(openrouter_api_key)
    lmstudio_base_url = lmstudio_base_url.rstrip("/")

    return Config(
        telegram_bot_token=token,
        allowed_tg_ids=allowed_tg_ids,
        llm_provider=provider,
        lmstudio_base_url=lmstudio_base_url,
        lmstudio_model=lmstudio_model,
        openrouter_api_key=openrouter_api_key,
        openrouter_model=openrouter_model,
        llm_timeout_s=_parse_timeout(_value(source, "LLM_TIMEOUT_S")),
        exec_workdir=_prepare_workdir(_value(source, "EXEC_WORKDIR") or "./sandbox"),
        db_path=_prepare_db_path(_value(source, "DB_PATH") or "./bot.db"),
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
