"""The single entry point for every quality gate this repository runs.

Hooks call it, gates call it, the report quotes it (REQ-V15-GATE-01). Uses
only the standard library: a small explicit reader for the YAML subset
`config/quality_gates.yaml` uses, never an imported YAML library.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "quality_gates.yaml"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


# ---------------------------------------------------------------------------
# a small explicit YAML reader for the subset config/quality_gates.yaml uses:
# nested block mappings, flow lists/maps (possibly spanning several physical
# lines), quoted and bare scalars, integers, booleans. Anything else -- a
# tab, a duplicate key, a block-list dash, an unbalanced bracket -- is a
# parse error (REQ-V15-GATE-01: "fails closed on anything it does not
# understand").
# ---------------------------------------------------------------------------


class YamlError(ValueError):
    pass


_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_.\-]*):(.*)$")
_INT_RE = re.compile(r"^-?[0-9]+$")


def read_yaml(path: Path) -> dict[str, Any]:
    return _parse_yaml_text(path.read_text(encoding="utf-8"))


def _parse_yaml_text(text: str) -> dict[str, Any]:
    lines = _logical_lines(text)
    value, idx = _parse_block(lines, 0, 0)
    if idx != len(lines):
        raise YamlError(f"unexpected content at line {lines[idx][0]}")
    if not isinstance(value, dict):
        raise YamlError("the top level of the document must be a mapping")
    return value


def _mask_quotes_ok(s: str) -> bool:
    """True if every quote in s is closed -- used to detect unterminated strings."""
    in_quote = False
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if in_quote:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_quote = False
            i += 1
            continue
        if c == '"':
            in_quote = True
        i += 1
    return not in_quote


def _net_bracket_depth(s: str) -> int:
    depth = 0
    in_quote = False
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if in_quote:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_quote = False
            i += 1
            continue
        if c == '"':
            in_quote = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        i += 1
    return depth


def _strip_comment(line: str) -> str:
    in_quote = False
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if in_quote:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_quote = False
            i += 1
            continue
        if c == '"':
            in_quote = True
            i += 1
            continue
        if c == "#":
            return line[:i]
        i += 1
    return line


def _logical_lines(text: str) -> list[tuple[int, int, str]]:
    result: list[tuple[int, int, str]] = []
    pending: list[Any] | None = None  # [line_no, indent, parts, depth]
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw:
            raise YamlError(f"tab character at line {line_no}")
        content = _strip_comment(raw).rstrip()
        if not _mask_quotes_ok(content):
            raise YamlError(f"unterminated quoted string at line {line_no}")
        if pending is None:
            if not content.strip():
                continue
            indent = len(content) - len(content.lstrip(" "))
            stripped = content.strip()
            depth = _net_bracket_depth(stripped)
            if depth < 0:
                raise YamlError(f"unbalanced brackets at line {line_no}")
            if depth == 0:
                result.append((line_no, indent, stripped))
            else:
                pending = [line_no, indent, [stripped], depth]
        else:
            piece = content.strip()
            if not piece:
                continue
            pending[3] += _net_bracket_depth(piece)
            pending[2].append(piece)
            if pending[3] < 0:
                raise YamlError(f"unbalanced brackets near line {line_no}")
            if pending[3] == 0:
                result.append((pending[0], pending[1], " ".join(pending[2])))
                pending = None
    if pending is not None:
        raise YamlError(f"unterminated flow collection starting at line {pending[0]}")
    return result


def _parse_block(
    lines: list[tuple[int, int, str]], idx: int, indent: int
) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while idx < len(lines) and lines[idx][1] == indent:
        line_no, _cur_indent, content = lines[idx]
        m = _KEY_RE.match(content)
        if not m:
            raise YamlError(f"expected 'key: value' at line {line_no}: {content!r}")
        key, rest = m.group(1), m.group(2).strip()
        if key in result:
            raise YamlError(f"duplicate key {key!r} at line {line_no}")
        idx += 1
        if rest == "":
            if idx < len(lines) and lines[idx][1] > indent:
                child, idx = _parse_block(lines, idx, lines[idx][1])
            else:
                child = {}
            result[key] = child
        else:
            result[key] = _parse_scalar_or_flow(rest, line_no)
    return result, idx


def _tokenize_flow(s: str, line_no: int) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t":
            i += 1
            continue
        if c in "[]{},:":
            tokens.append((c, c))
            i += 1
            continue
        if c == '"':
            j = i + 1
            buf: list[str] = []
            while j < n and s[j] != '"':
                if s[j] == "\\" and j + 1 < n:
                    buf.append(s[j + 1])
                    j += 2
                else:
                    buf.append(s[j])
                    j += 1
            if j >= n:
                raise YamlError(f"unterminated quoted string at line {line_no}")
            tokens.append(("QSTR", "".join(buf)))
            i = j + 1
            continue
        j = i
        while j < n and s[j] not in " \t[]{},:":
            j += 1
        if j == i:
            raise YamlError(f"unexpected character {c!r} at line {line_no}")
        tokens.append(("BARE", s[i:j]))
        i = j
    return tokens


def _coerce_bare(v: str) -> Any:
    if v == "true":
        return True
    if v == "false":
        return False
    if _INT_RE.match(v):
        return int(v)
    return v


def _parse_flow_tokens(
    tokens: list[tuple[str, str]], pos: int, line_no: int
) -> tuple[Any, int]:
    if pos >= len(tokens):
        raise YamlError(f"unexpected end of flow value at line {line_no}")
    kind, val = tokens[pos]
    if kind == "[":
        pos += 1
        items: list[Any] = []
        if pos < len(tokens) and tokens[pos][0] == "]":
            return items, pos + 1
        while True:
            item, pos = _parse_flow_tokens(tokens, pos, line_no)
            items.append(item)
            if pos >= len(tokens):
                raise YamlError(f"unterminated list at line {line_no}")
            k2 = tokens[pos][0]
            if k2 == ",":
                pos += 1
                continue
            if k2 == "]":
                return items, pos + 1
            raise YamlError(f"expected ',' or ']' at line {line_no}")
    if kind == "{":
        pos += 1
        mapping: dict[str, Any] = {}
        if pos < len(tokens) and tokens[pos][0] == "}":
            return mapping, pos + 1
        while True:
            if pos >= len(tokens) or tokens[pos][0] not in ("BARE", "QSTR"):
                raise YamlError(f"expected a key at line {line_no}")
            kkey = tokens[pos][1]
            pos += 1
            if pos >= len(tokens) or tokens[pos][0] != ":":
                raise YamlError(f"expected ':' at line {line_no}")
            pos += 1
            val2, pos = _parse_flow_tokens(tokens, pos, line_no)
            if kkey in mapping:
                raise YamlError(f"duplicate key {kkey!r} at line {line_no}")
            mapping[kkey] = val2
            if pos >= len(tokens):
                raise YamlError(f"unterminated mapping at line {line_no}")
            k2 = tokens[pos][0]
            if k2 == ",":
                pos += 1
                continue
            if k2 == "}":
                return mapping, pos + 1
            raise YamlError(f"expected ',' or '}}' at line {line_no}")
    if kind == "QSTR":
        return val, pos + 1
    if kind == "BARE":
        return _coerce_bare(val), pos + 1
    raise YamlError(f"unexpected token {val!r} at line {line_no}")


def _parse_scalar_or_flow(s: str, line_no: int) -> Any:
    s = s.strip()
    if not s:
        raise YamlError(f"empty value at line {line_no}")
    if s[0] in "[{":
        tokens = _tokenize_flow(s, line_no)
        value, pos = _parse_flow_tokens(tokens, 0, line_no)
        if pos != len(tokens):
            raise YamlError(f"trailing content after flow value at line {line_no}")
        return value
    return _parse_plain_scalar(s, line_no)


def _parse_plain_scalar(s: str, line_no: int) -> Any:
    if s.startswith('"'):
        if len(s) < 2 or not s.endswith('"'):
            raise YamlError(f"unterminated quoted string at line {line_no}")
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return _coerce_bare(s)


# ---------------------------------------------------------------------------
# config/quality_gates.yaml: schema validation (REQ-V15-GATE-02).
# ---------------------------------------------------------------------------


class GateConfigError(ValueError):
    pass


TOP_LEVEL_KEYS = {"version", "scope", "profiles", "tools", "gates"}
SCOPE_KEYS = {"base_branch", "zero_sha"}
TOOL_KEYS = {"version", "via", "version_argv", "version_parser"}

# Adapter, parser and handler identifiers are mechanism names, permitted as
# Python literals (REQ-V15-GATE-02); everything else authoritative -- argv,
# severities, thresholds, profile membership -- comes only from the file.
KNOWN_HANDLERS = {"branch_name", "doctor", "lint_docs"}
KNOWN_FINDINGS_PARSERS = {"gitleaks_json", "trivy_json", "semgrep_json", "skylos_json"}
KNOWN_VERSION_PARSERS = {"bare", "last_token"}
FIXED_PLACEHOLDERS = {"target", "config", "artefact", "profile", "tracked_tree"}

# A gate's own *name* is not a forbidden literal under REQ-V15-GATE-02 (the
# ban covers argv/severity/threshold/exit-code/profile-membership values,
# not schema-key legality); these four sets are each legal on exactly the
# gate named, per §7.
EXTRA_KEYS_BY_GATE: dict[str, set[str]] = {
    "ruff-format": {"blocking_paths"},
    "branch-name": {"pattern", "warn_refs", "warn_on_detached"},
    "doctor": {"warn_only_tools"},
    "lint-docs": {"prompt_glob", "exempt_files", "report_path", "ledger_header"},
}

_COMMAND_BASE_KEYS = {
    "kind",
    "result_mode",
    "argv",
    "placeholders",
    "success_exit_codes",
    "blocking",
    "diff_scoped",
    "timeout_seconds",
}
_FINDINGS_EXTRA_KEYS = {"output_format", "parser", "findings_exit_codes", "artefact", "severity"}
_EXIT_STATUS_FORBIDDEN = {"parser", "output_format", "findings_exit_codes", "severity", "artefact"}
_BUILTIN_BASE_KEYS = {"kind", "handler", "blocking", "diff_scoped", "timeout_seconds"}
_BUILTIN_FORBIDDEN = {
    "argv",
    "placeholders",
    "parser",
    "output_format",
    "result_mode",
    "success_exit_codes",
    "findings_exit_codes",
}

_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")


def load_gate_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    raw = read_yaml(path)
    unknown = set(raw) - TOP_LEVEL_KEYS
    if unknown:
        raise GateConfigError(f"unknown top-level key(s): {sorted(unknown)}")
    missing = TOP_LEVEL_KEYS - set(raw)
    if missing:
        raise GateConfigError(f"missing top-level key(s): {sorted(missing)}")
    if not isinstance(raw["version"], str):
        raise GateConfigError("version must be a string")
    _validate_scope(raw["scope"])
    _validate_tools(raw["tools"])
    _validate_gates(raw["gates"])
    _validate_profiles(raw["profiles"], raw["gates"])
    return raw


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _validate_scope(scope: Any) -> None:
    if not isinstance(scope, dict):
        raise GateConfigError("scope must be a mapping")
    unknown = set(scope) - SCOPE_KEYS
    if unknown:
        raise GateConfigError(f"unknown scope key(s): {sorted(unknown)}")
    missing = SCOPE_KEYS - set(scope)
    if missing:
        raise GateConfigError(f"missing scope key(s): {sorted(missing)}")
    if not isinstance(scope["base_branch"], str):
        raise GateConfigError("scope.base_branch must be a string")
    if not isinstance(scope["zero_sha"], str):
        raise GateConfigError("scope.zero_sha must be a string")


def _validate_tools(tools: Any) -> None:
    if not isinstance(tools, dict):
        raise GateConfigError("tools must be a mapping")
    for name, spec in tools.items():
        if not isinstance(spec, dict):
            raise GateConfigError(f"tools.{name} must be a mapping")
        unknown = set(spec) - TOOL_KEYS
        if unknown:
            raise GateConfigError(f"tools.{name}: unknown key(s) {sorted(unknown)}")
        missing = TOOL_KEYS - set(spec)
        if missing:
            raise GateConfigError(f"tools.{name}: missing key(s) {sorted(missing)}")
        if not isinstance(spec["version"], str):
            raise GateConfigError(f"tools.{name}.version must be a string")
        if not isinstance(spec["via"], str):
            raise GateConfigError(f"tools.{name}.via must be a string")
        if spec["version_parser"] not in KNOWN_VERSION_PARSERS:
            raise GateConfigError(
                f"tools.{name}.version_parser names no known parser: "
                f"{spec['version_parser']!r}"
            )
        argv = spec["version_argv"]
        if not isinstance(argv, list) or not argv or not all(isinstance(t, str) for t in argv):
            raise GateConfigError(f"tools.{name}.version_argv must be a non-empty list of strings")


def _validate_placeholders_used(gate_name: str, strings: list[str]) -> None:
    for s in strings:
        for token in _PLACEHOLDER_RE.findall(s):
            if token not in FIXED_PLACEHOLDERS:
                raise GateConfigError(f"gates.{gate_name}: unknown placeholder {{{token}}}")


def _validate_gates(gates: Any) -> None:
    if not isinstance(gates, dict):
        raise GateConfigError("gates must be a mapping")
    for name, gate in gates.items():
        _validate_one_gate(name, gate)


def _validate_one_gate(name: str, gate: Any) -> None:
    if not isinstance(gate, dict):
        raise GateConfigError(f"gates.{name} must be a mapping")
    if "kind" not in gate:
        raise GateConfigError(f"gates.{name}: missing 'kind'")
    kind = gate["kind"]
    if kind not in ("command", "builtin"):
        raise GateConfigError(f"gates.{name}: unknown kind {kind!r}")
    for key in ("blocking", "diff_scoped", "timeout_seconds"):
        if key not in gate:
            raise GateConfigError(f"gates.{name}: missing {key!r}")
    if not isinstance(gate["blocking"], bool):
        raise GateConfigError(f"gates.{name}.blocking must be a boolean")
    if not isinstance(gate["diff_scoped"], bool):
        raise GateConfigError(f"gates.{name}.diff_scoped must be a boolean")
    if not _is_int(gate["timeout_seconds"]):
        raise GateConfigError(f"gates.{name}.timeout_seconds must be an integer")

    extra_allowed = EXTRA_KEYS_BY_GATE.get(name, set())
    if kind == "command":
        _validate_command_gate(name, gate, extra_allowed)
    else:
        _validate_builtin_gate(name, gate, extra_allowed)


def _validate_command_gate(name: str, gate: dict[str, Any], extra_allowed: set[str]) -> None:
    if "handler" in gate:
        raise GateConfigError(f"gates.{name}: a command gate must not carry 'handler'")
    if "result_mode" not in gate:
        raise GateConfigError(f"gates.{name}: a command gate requires 'result_mode'")
    result_mode = gate["result_mode"]
    if result_mode not in ("exit_status", "findings"):
        raise GateConfigError(f"gates.{name}: unknown result_mode {result_mode!r}")

    for key in ("argv", "placeholders", "success_exit_codes"):
        if key not in gate:
            raise GateConfigError(f"gates.{name}: missing {key!r}")
    argv = gate["argv"]
    if not isinstance(argv, list) or not argv or not all(isinstance(t, str) for t in argv):
        raise GateConfigError(f"gates.{name}.argv must be a non-empty list of strings")
    if not isinstance(gate["placeholders"], dict):
        raise GateConfigError(f"gates.{name}.placeholders must be a mapping")
    codes = gate["success_exit_codes"]
    if not isinstance(codes, list) or not all(_is_int(c) for c in codes):
        raise GateConfigError(f"gates.{name}.success_exit_codes must be a list of integers")
    _validate_placeholders_used(name, argv)

    if result_mode == "findings":
        missing = _FINDINGS_EXTRA_KEYS - set(gate)
        if missing:
            raise GateConfigError(f"gates.{name}: findings gate missing {sorted(missing)}")
        if not isinstance(gate["output_format"], str):
            raise GateConfigError(f"gates.{name}.output_format must be a string")
        if gate["parser"] not in KNOWN_FINDINGS_PARSERS:
            raise GateConfigError(f"gates.{name}.parser names no known adapter: {gate['parser']!r}")
        fcodes = gate["findings_exit_codes"]
        if not isinstance(fcodes, list) or not all(_is_int(c) for c in fcodes):
            raise GateConfigError(f"gates.{name}.findings_exit_codes must be a list of integers")
        if not isinstance(gate["artefact"], str):
            raise GateConfigError(f"gates.{name}.artefact must be a string")
        severity = gate["severity"]
        if not isinstance(severity, list) or not severity or not all(
            isinstance(s, str) for s in severity
        ):
            raise GateConfigError(f"gates.{name}.severity must be a non-empty list of strings")
        _validate_placeholders_used(name, [gate["artefact"]])
        allowed = _COMMAND_BASE_KEYS | _FINDINGS_EXTRA_KEYS | extra_allowed
    else:
        forbidden = _EXIT_STATUS_FORBIDDEN & set(gate)
        if forbidden:
            raise GateConfigError(
                f"gates.{name}: exit_status gate must not carry {sorted(forbidden)}"
            )
        allowed = _COMMAND_BASE_KEYS | extra_allowed

    unknown = set(gate) - allowed
    if unknown:
        raise GateConfigError(f"gates.{name}: unknown key(s) {sorted(unknown)}")


def _validate_builtin_gate(name: str, gate: dict[str, Any], extra_allowed: set[str]) -> None:
    if "handler" not in gate:
        raise GateConfigError(f"gates.{name}: a builtin gate requires 'handler'")
    if gate["handler"] not in KNOWN_HANDLERS:
        raise GateConfigError(f"gates.{name}: unknown handler {gate['handler']!r}")
    forbidden = _BUILTIN_FORBIDDEN & set(gate)
    if forbidden:
        raise GateConfigError(f"gates.{name}: builtin gate must not carry {sorted(forbidden)}")
    allowed = _BUILTIN_BASE_KEYS | extra_allowed
    unknown = set(gate) - allowed
    if unknown:
        raise GateConfigError(f"gates.{name}: unknown key(s) {sorted(unknown)}")


def _validate_profiles(profiles: Any, gates: dict[str, Any]) -> None:
    if not isinstance(profiles, dict):
        raise GateConfigError("profiles must be a mapping")
    for pname, members in profiles.items():
        if not isinstance(members, list) or not all(isinstance(m, str) for m in members):
            raise GateConfigError(f"profiles.{pname} must be a list of gate names")
        for m in members:
            if m not in gates:
                raise GateConfigError(f"profiles.{pname} references unknown gate {m!r}")
    named = {m for members in profiles.values() for m in members}
    orphans = set(gates) - named
    if orphans:
        raise GateConfigError(f"gate(s) named by no profile: {sorted(orphans)}")


def pyproject_ruff_pin(path: Path = PYPROJECT_PATH) -> str:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for spec in data.get("dependency-groups", {}).get("dev", []):
        if spec.startswith("ruff=="):
            return spec.split("==", 1)[1]
    raise ValueError(f"no ruff== pin found in {path}'s dev dependency group")


def config_ruff_pin(config: dict[str, Any]) -> str:
    return config["tools"]["ruff"]["version"]


# ---------------------------------------------------------------------------
# Conventional Commits (REQ-V15-CC-01..05). One implementation, two callers:
# the commit-msg hook and `checks.py replay`.
# ---------------------------------------------------------------------------

HEADER_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(\([a-z0-9.\-]+\))?!?: .+$"
)
BYPASS_RE = re.compile(r"^(Merge|Revert|fixup!|squash!)")
PROMPT_REF_RE = re.compile(r"\(prompt: (docs/prompts/[0-9]{2,}-[a-z0-9.\-]+\.md)\)")
HEADER_MAX_LEN = 72
ALLOWED_TYPES = "feat fix docs style refactor perf test build ci chore revert"


def is_bypassed(subject: str) -> bool:
    return bool(BYPASS_RE.match(subject))


def check_header(subject: str) -> tuple[bool, str]:
    if HEADER_RE.match(subject):
        return True, ""
    return False, (
        f"header check failed: {subject!r} does not match "
        f"'<type>(<scope>)?!?: <subject>'. Allowed types: {ALLOWED_TYPES}"
    )


def check_length(subject: str) -> tuple[bool, str]:
    n = len(subject)
    if n <= HEADER_MAX_LEN:
        return True, ""
    return False, (
        f"length check failed: header is {n} characters "
        f"(limit {HEADER_MAX_LEN}): {subject!r}"
    )


def check_punctuation(subject: str) -> tuple[bool, str]:
    if not subject.endswith("."):
        return True, ""
    return False, f"punctuation check failed: header must not end with '.': {subject!r}"


def check_prompt_reference(body: str, repo_root: Path) -> tuple[bool, str]:
    m = PROMPT_REF_RE.search(body)
    if not m:
        return False, (
            "body check failed: no '(prompt: docs/prompts/NN-<slug>.md)' reference found"
        )
    ref = m.group(1)
    if not (repo_root / ref).exists():
        return False, (
            f"body check failed: {ref!r} is referenced but does not exist in the working tree"
        )
    return True, ""


def run_commit_msg_checks(subject: str, body: str, repo_root: Path = REPO_ROOT) -> list[str]:
    if is_bypassed(subject):
        return []
    failures: list[str] = []
    for check in (check_header, check_length, check_punctuation):
        ok, msg = check(subject)
        if not ok:
            failures.append(msg)
    ok, msg = check_prompt_reference(body, repo_root)
    if not ok:
        failures.append(msg)
    return failures


def read_commit_message(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    subject = lines[0] if lines else ""
    body = "\n".join(lines[1:])
    return subject, body


def check_branch_name(
    branch: str | None,
    pattern: str,
    warn_refs: list[str],
    warn_on_detached: bool,
) -> tuple[str, str]:
    """Returns (status, message); status is one of "ok", "warn", "fail"."""
    if branch is None:
        if warn_on_detached:
            return "warn", "branch-name check: detached HEAD (warning only)"
        return "fail", "branch-name check: detached HEAD and warn_on_detached is false"
    if branch in warn_refs:
        return "warn", (
            f"branch-name check: {branch!r} is a warn-only ref (solo end-to-end run permitted)"
        )
    if re.match(pattern, branch):
        return "ok", ""
    return "fail", f"branch-name check: {branch!r} does not match {pattern!r}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_commit_msg(args: argparse.Namespace) -> int:
    subject, body = read_commit_message(Path(args.message_file))
    failures = run_commit_msg_checks(subject, body)
    if not failures:
        return 0
    for failure in failures:
        print(f"commit-msg: {failure}", file=sys.stderr)
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    print(
        "checks.py run: gate execution lands in T7 (findings gates), "
        "T8 (pre-commit exit_status via the hook chain) and T12 (full wiring)",
        file=sys.stderr,
    )
    return 2


def cmd_doctor(args: argparse.Namespace) -> int:
    print("checks.py doctor: lands in T9", file=sys.stderr)
    return 2


def cmd_replay(args: argparse.Namespace) -> int:
    print("checks.py replay: lands in T8", file=sys.stderr)
    return 2


def cmd_lint_docs(args: argparse.Namespace) -> int:
    print("checks.py lint-docs: lands in T11", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="checks.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("--profile", required=True, choices=["pre-commit", "pre-push", "full"])
    p_run.add_argument("--stdin-refs", action="store_true")
    p_run.add_argument("--since")
    p_run.set_defaults(func=cmd_run)

    p_doctor = sub.add_parser("doctor")
    p_doctor.set_defaults(func=cmd_doctor)

    p_commit_msg = sub.add_parser("commit-msg")
    p_commit_msg.add_argument("message_file")
    p_commit_msg.set_defaults(func=cmd_commit_msg)

    p_replay = sub.add_parser("replay")
    p_replay.add_argument("--range", required=True)
    p_replay.set_defaults(func=cmd_replay)

    p_lint_docs = sub.add_parser("lint-docs")
    p_lint_docs.set_defaults(func=cmd_lint_docs)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run" and args.stdin_refs and args.since:
        parser.error("--stdin-refs and --since are mutually exclusive")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
