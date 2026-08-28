"""Tool definitions: bounded arbitrary execution, skills and tool dispatch.

`exec` runs arbitrary programs chosen by a language model. The cwd, the
environment allowlist, the timeout and the output caps bound resource usage and
accident blast radius; they are NOT a security boundary. See README.md.
"""

import json
import logging
import os
import re
import signal
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import config

EXEC_TIMEOUT_S = 30.0
EXEC_KILL_GRACE_S = 5.0
EXEC_DRAIN_GRACE_S = 2.0
EXEC_MAX_STREAM_BYTES = 4096
_READ_CHUNK = 65536

MAX_ARGV_ELEMENTS = 32
MAX_ARGV_ELEMENT_CHARS = 4096

log = logging.getLogger("tools")

_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_FRONTMATTER_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")

CommandRunner = Callable[[list[str]], dict]


class _Capture:
    """Bounded, thread-safe sink. Keeps the first `cap` bytes, discards the rest."""

    def __init__(self, cap: int) -> None:
        self._cap = cap
        self._buf = bytearray()
        self._truncated = False
        self._lock = threading.Lock()

    def feed(self, chunk: bytes) -> None:
        with self._lock:
            room = self._cap - len(self._buf)
            if room > 0:
                self._buf += chunk[:room]
            if len(chunk) > room:
                self._truncated = True

    def snapshot(self) -> tuple[bytes, bool]:
        with self._lock:
            return bytes(self._buf), self._truncated


def _drain(stream, sink: _Capture) -> None:
    """Read `stream` to EOF.

    CONTRACT: this MUST keep reading after the cap is reached. Stopping early
    fills the pipe buffer and blocks the child forever.
    """
    try:
        while True:
            chunk = stream.read(_READ_CHUNK)
            if not chunk:
                return
            sink.feed(chunk)
    except (OSError, ValueError):
        return
    finally:
        try:
            stream.close()
        except Exception:
            pass


def _killpg(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def run_command(
    argv: list[str],
    *,
    workdir: Path,
    timeout_s: float = EXEC_TIMEOUT_S,
) -> dict:
    # CONTRACT: Popen raises FileNotFoundError for BOTH a missing program and a
    # missing cwd. Check the cwd first so the two never share an error message.
    if not workdir.is_dir():
        return {"error": "sandbox directory is missing"}
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "HOME": str(workdir),
    }
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(workdir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
            bufsize=0,
        )
    except FileNotFoundError:
        return {"error": f"program not found: {argv[0]}"}
    except PermissionError:
        return {"error": f"permission denied: {argv[0]}"}
    except OSError as exc:
        return {"error": f"failed to start process: {exc.__class__.__name__}"}

    # CONTRACT: start_new_session=True makes the child a process-group leader,
    # so pgid == proc.pid. Capture it now: os.getpgid() raises after the child
    # is reaped.
    pgid = proc.pid
    out, err = _Capture(EXEC_MAX_STREAM_BYTES), _Capture(EXEC_MAX_STREAM_BYTES)
    t_out = threading.Thread(target=_drain, args=(proc.stdout, out), daemon=True)
    t_err = threading.Thread(target=_drain, args=(proc.stderr, err), daemon=True)
    t_out.start()
    t_err.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _killpg(pgid, signal.SIGTERM)
        try:
            proc.wait(timeout=EXEC_KILL_GRACE_S)
        except subprocess.TimeoutExpired:
            _killpg(pgid, signal.SIGKILL)
            proc.wait()

    # The direct child is reaped. Descendants may still hold the pipe write
    # ends open; give them a short grace period, then kill the whole group so
    # the reader threads reach EOF.
    t_out.join(timeout=EXEC_DRAIN_GRACE_S)
    t_err.join(timeout=EXEC_DRAIN_GRACE_S)
    if t_out.is_alive() or t_err.is_alive():
        _killpg(pgid, signal.SIGKILL)
        t_out.join(timeout=EXEC_DRAIN_GRACE_S)
        t_err.join(timeout=EXEC_DRAIN_GRACE_S)

    out_bytes, out_trunc = out.snapshot()
    err_bytes, err_trunc = err.snapshot()
    return {
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "truncated": out_trunc or err_trunc,
        "stdout": out_bytes.decode("utf-8", errors="replace"),
        "stderr": err_bytes.decode("utf-8", errors="replace"),
    }


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    source: str          # file name only, e.g. "weather.md"


def load_skills(skills_dir: Path) -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    if not skills_dir.is_dir():
        log.warning("skills directory %s is missing; no skills loaded", skills_dir)
        return skills
    for path in sorted(skills_dir.glob("*.md")):
        try:
            skill = _parse_skill(path.read_text(encoding="utf-8"), path.name)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            log.warning("skill file %s ignored: %s", path.name, config.redact(str(exc)))
            continue
        if skill.name in skills:
            log.warning("duplicate skill name '%s' in %s ignored", skill.name, path.name)
            continue
        skills[skill.name] = skill
    return skills


def tool_specs() -> list[dict]:
    """The complete LLM-visible tool catalog, in a fixed order."""
    return [
        {
            "type": "function",
            "function": {
                "name": "exec",
                "description": (
                    "Run one program on the bot's Linux host and return its output. This is "
                    "NOT a shell: pipes, redirection, globbing, quoting, environment-variable "
                    "expansion and ';' / '&&' chains do not work. Pass the program name as the "
                    "first array element and every argument as its own element, for example "
                    '["uname", "-a"]. The working directory is the bot sandbox. The process is '
                    "killed after 30 seconds; stdout and stderr are each truncated to 4096 bytes."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "argv": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 32,
                            "description": (
                                "Program name followed by its arguments, one array element "
                                "per argument."
                            ),
                        }
                    },
                    "required": ["argv"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "load_skill",
                "description": (
                    "Load the full instructions of one locally installed skill. Call this "
                    "before acting on any topic a skill covers; the skill body states the "
                    "exact exec commands to run. The valid skill names are listed in the "
                    "system prompt."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Skill name exactly as listed in the system prompt.",
                        }
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
        },
    ]


def execute_tool(
    name: str,
    arguments: str,
    *,
    skills: dict[str, Skill],
    runner: CommandRunner,
) -> str:
    """Return the content string of a tool message. Never raises."""
    try:
        parsed = json.loads(arguments)
    except (TypeError, ValueError):
        return _envelope({"error": "arguments are not valid JSON"})
    if not isinstance(parsed, dict):
        return _envelope({"error": "arguments must be a JSON object"})
    if name == "exec":
        return _envelope(_run_exec(parsed, runner))
    if name == "load_skill":
        return _envelope(_run_load_skill(parsed, skills))
    return _envelope({"error": f"unknown tool: {name}"})


def _envelope(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _run_exec(arguments: dict, runner: CommandRunner) -> dict:
    if "argv" not in arguments:
        return {"error": "argv is required"}
    argv = arguments["argv"]
    if not isinstance(argv, list):
        return {"error": "argv must be an array of strings"}
    if not 1 <= len(argv) <= MAX_ARGV_ELEMENTS:
        return {"error": f"argv must contain between 1 and {MAX_ARGV_ELEMENTS} elements"}
    if not all(isinstance(item, str) for item in argv):
        return {"error": "argv must be an array of strings"}
    if any("\x00" in item for item in argv):
        return {"error": "argv elements must not contain NUL bytes"}
    if any(len(item) > MAX_ARGV_ELEMENT_CHARS for item in argv):
        return {
            "error": f"argv elements must be at most {MAX_ARGV_ELEMENT_CHARS} characters"
        }
    if not argv[0].strip():
        return {"error": "argv[0] must be a program name"}
    try:
        return runner(argv)
    except Exception as exc:  # a broken runner must not break the agent loop
        return {"error": f"failed to run the command: {exc.__class__.__name__}"}


def _run_load_skill(arguments: dict, skills: dict[str, Skill]) -> dict:
    name = arguments.get("name")
    if not isinstance(name, str):
        return {"error": "name is required and must be a string"}
    key = name.strip()
    skill = skills.get(key)
    if skill is None:
        return {"error": f"unknown skill: {key}. Available: {', '.join(sorted(skills))}"}
    return {"name": skill.name, "body": skill.body}


def _parse_skill(text: str, source: str) -> Skill:
    lines = [line.rstrip("\r") for line in text.split("\n")]
    if not lines or lines[0] != "---":
        raise ValueError("the first line must be exactly '---'")
    closing = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
    if closing is None:
        raise ValueError("the frontmatter is not closed by a '---' line")

    meta: dict[str, str] = {}
    for line in lines[1:closing]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"frontmatter line is not 'key: value': {stripped}")
        key = key.strip()
        if not _FRONTMATTER_KEY_RE.match(key):
            raise ValueError(f"invalid frontmatter key: {key}")
        value = value.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        meta[key] = value

    name = meta.get("name", "").strip()
    description = meta.get("description", "").strip()
    if not name:
        raise ValueError("'name' is missing or empty")
    if not description:
        raise ValueError("'description' is missing or empty")
    if not _SKILL_NAME_RE.match(name):
        raise ValueError(f"'name' does not match the required pattern: {name}")

    body_lines = lines[closing + 1:]
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    return Skill(
        name=name,
        description=description,
        body="\n".join(body_lines).rstrip(),
        source=source,
    )
