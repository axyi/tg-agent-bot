"""The single entry point for every quality gate this repository runs.

Hooks call it, gates call it, the report quotes it (REQ-V15-GATE-01). Uses
only the standard library: a small explicit reader for the YAML subset
`config/quality_gates.yaml` uses, never an imported YAML library.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
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


def _parse_flow_tokens(tokens: list[tuple[str, str]], pos: int, line_no: int) -> tuple[Any, int]:
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
                f"tools.{name}.version_parser names no known parser: {spec['version_parser']!r}"
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
        if (
            not isinstance(severity, list)
            or not severity
            or not all(isinstance(s, str) for s in severity)
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
        f"length check failed: header is {n} characters (limit {HEADER_MAX_LEN}): {subject!r}"
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
# git helpers (REQ-V15-GATE-07): scope computation reads git state, never
# assumes it.
# ---------------------------------------------------------------------------


class GitError(RuntimeError):
    pass


class GitlinkRejected(RuntimeError):
    pass


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def staged_files(repo_root: Path) -> list[str]:
    out = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"], repo_root)
    return [line for line in out.splitlines() if line]


def current_branch(repo_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def merge_base(base_branch: str, rev: str, repo_root: Path) -> str:
    return _run_git(["merge-base", base_branch, rev], repo_root).strip()


def changed_files_in_range(base: str, head: str, repo_root: Path) -> set[str]:
    out = _run_git(["diff", "--name-only", "--diff-filter=ACMR", f"{base}..{head}"], repo_root)
    return {line for line in out.splitlines() if line}


def working_tree_dirty(repo_root: Path) -> bool:
    return bool(_run_git(["status", "--porcelain"], repo_root).strip())


def commit_count_in_range(base: str, head: str, repo_root: Path) -> int:
    out = _run_git(["rev-list", "--count", f"{base}..{head}"], repo_root)
    return int(out.strip() or "0")


def list_tree_entries(rev: str, repo_root: Path) -> list[tuple[str, str, str]]:
    """(mode, blob_sha, repo-relative path) for every entry `git ls-tree -r` names."""
    result = subprocess.run(
        ["git", "ls-tree", "-r", "-z", rev],
        cwd=repo_root,
        capture_output=True,
        text=False,
        check=False,
    )
    if result.returncode != 0:
        raise GitError(f"git ls-tree -r {rev} failed: {result.stderr!r}")
    entries = []
    for record in result.stdout.split(b"\x00"):
        if not record:
            continue
        meta, _, path = record.partition(b"\t")
        mode, _obj_type, sha = meta.split(b" ")
        entries.append((mode.decode(), sha.decode(), path.decode("utf-8", "surrogateescape")))
    return entries


def materialize_tracked_tree(
    entries: list[tuple[str, str, str]], dest_dir: Path, repo_root: Path
) -> None:
    """Writes each entry's blob bytes to dest_dir/path -- from git objects, never
    from filesystem paths (REQ-V15-SCAN-01). A 120000 (symlink) blob's content
    *is* its link text, so writing those bytes as a regular file is already the
    required "never re-created as a symlink" behaviour; 160000 (gitlink) is
    rejected outright."""
    for mode, sha, path in entries:
        if mode == "160000":
            raise GitlinkRejected(f"gitlink entry rejected: {path}")
        target = dest_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        blob = subprocess.run(
            ["git", "cat-file", "-p", sha], cwd=repo_root, capture_output=True, check=False
        )
        if blob.returncode != 0:
            raise GitError(f"git cat-file -p {sha} failed for {path}")
        target.write_bytes(blob.stdout)


def parse_pre_push_stdin(text: str) -> list[tuple[str, str, str, str]]:
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 4:
            raise GateRunError(f"unparseable pre-push stdin line: {line!r}")
        records.append((parts[0], parts[1], parts[2], parts[3]))
    if not records:
        raise GateRunError("empty pre-push stdin")
    return records


def _pre_push_scope(
    stdin_text: str, scope_cfg: dict[str, Any], repo_root: Path
) -> tuple[set[str], Path]:
    records = parse_pre_push_stdin(stdin_text)
    files: set[str] = set()
    heads: list[str] = []
    for _local_ref, local_sha, _remote_ref, remote_sha in records:
        base = (
            merge_base(scope_cfg["base_branch"], local_sha, repo_root)
            if remote_sha == scope_cfg["zero_sha"]
            else remote_sha
        )
        files |= changed_files_in_range(base, local_sha, repo_root)
        heads.append(local_sha)
    tmp = Path(tempfile.mkdtemp(prefix="checks-tracked-tree-"))
    latest: dict[str, tuple[str, str]] = {}
    for head in heads:
        for mode, sha, path in list_tree_entries(head, repo_root):
            latest[path] = (mode, sha)
    materialize_tracked_tree(
        [(mode, sha, path) for path, (mode, sha) in latest.items()], tmp, repo_root
    )
    return files, tmp


class GateRunError(RuntimeError):
    pass


class EmptyScopeError(RuntimeError):
    pass


def compute_scope(
    profile: str,
    config: dict[str, Any],
    repo_root: Path,
    *,
    since: str | None = None,
    stdin_refs: str | None = None,
) -> tuple[set[str] | None, Path | None, list[Path]]:
    """Returns (scope_files, tracked_tree_dir, dirs_to_clean_up_afterwards)."""
    scope_cfg = config["scope"]
    if profile == "pre-commit":
        return set(staged_files(repo_root)), None, []
    if profile == "pre-push":
        if not stdin_refs:
            raise GateRunError("profile 'pre-push' requires --stdin-refs input")
        files, tree_dir = _pre_push_scope(stdin_refs, scope_cfg, repo_root)
        return files, tree_dir, [tree_dir]
    if profile == "full":
        branch = current_branch(repo_root)
        if branch == scope_cfg["base_branch"]:
            if not since:
                raise GateRunError("run --profile full on the base branch requires --since <rev>")
            base = since
        else:
            base = since or merge_base(scope_cfg["base_branch"], "HEAD", repo_root)
        files = changed_files_in_range(base, "HEAD", repo_root)
        if not files and (
            working_tree_dirty(repo_root) or commit_count_in_range(base, "HEAD", repo_root) > 0
        ):
            raise EmptyScopeError(
                f"profile 'full' at {base}..HEAD computed an empty scope while the "
                f"tree or commit range is non-empty -- scope computation is wrong"
            )
        tmp = Path(tempfile.mkdtemp(prefix="checks-tracked-tree-"))
        materialize_tracked_tree(list_tree_entries("HEAD", repo_root), tmp, repo_root)
        return files, tmp, [tmp]
    raise GateRunError(f"unknown profile {profile!r}")


# ---------------------------------------------------------------------------
# replay history helpers (REQ-V15-GATE-05). Reads blobs via `git show`/
# `git cat-file` only -- never checks out, resets or otherwise touches the
# working tree.
# ---------------------------------------------------------------------------


def commits_in_range(base: str, head: str, repo_root: Path) -> list[str]:
    out = _run_git(["rev-list", "--reverse", f"{base}..{head}"], repo_root)
    return [line for line in out.splitlines() if line]


def commit_changed_files(sha: str, repo_root: Path) -> list[str]:
    out = _run_git(
        ["diff-tree", "--no-commit-id", "--name-only", "-r", "--root", "--diff-filter=ACMR", sha],
        repo_root,
    )
    return [line for line in out.splitlines() if line]


def commit_message(sha: str, repo_root: Path) -> tuple[str, str]:
    raw = _run_git(["log", "-1", "--format=%B", sha], repo_root)
    subject, _, body = raw.partition("\n")
    return subject, body.strip("\n")


def show_blob(sha: str, path: str, repo_root: Path) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{sha}:{path}"], cwd=repo_root, capture_output=True, check=False
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _replay_one_commit(sha: str, config: dict[str, Any], repo_root: Path) -> list[str]:
    problems: list[str] = []

    subject, body = commit_message(sha, repo_root)
    problems.extend(f"commit-msg: {f}" for f in run_commit_msg_checks(subject, body, repo_root))

    check_gate = config["gates"]["ruff-check"]
    format_gate = config["gates"]["ruff-format"]
    blocking_paths = set(format_gate["blocking_paths"])
    check_prefix = check_gate["argv"][:-2]  # drop --force-exclude, {target}
    format_prefix = format_gate["argv"][:-2]  # drop --force-exclude, {target}

    py_files = [p for p in commit_changed_files(sha, repo_root) if p.endswith(".py")]
    for path in py_files:
        blob = show_blob(sha, path, repo_root)
        if blob is None:
            continue  # the path existed in the diff but not at this blob (rare race) -- skip

        check = run_argv(
            [*check_prefix, "--force-exclude", "--stdin-filename", path, "-"],
            repo_root,
            check_gate["timeout_seconds"],
            input_bytes=blob,
        )
        if not check.ok:
            problems.append(f"ruff check {path}: {check.error}")
        elif check.returncode not in check_gate["success_exit_codes"]:
            problems.append(f"ruff check {path}: {check.stdout.decode(errors='replace').strip()}")

        fmt = run_argv(
            [*format_prefix, "--stdin-filename", path, "-"],
            repo_root,
            format_gate["timeout_seconds"],
            input_bytes=blob,
        )
        if not fmt.ok:
            problems.append(f"ruff format {path}: {fmt.error}")
        elif fmt.returncode not in format_gate["success_exit_codes"] and path in blocking_paths:
            problems.append(f"ruff format {path}: would reformat")

    gitleaks_gate = config["gates"]["gitleaks-staged"]
    artefact = repo_root / ".bench" / "checks" / "replay" / f"gitleaks-{sha}.json"
    artefact.parent.mkdir(parents=True, exist_ok=True)
    tool, subcommand = gitleaks_gate["argv"][0], gitleaks_gate["argv"][1]
    argv = [
        tool,
        subcommand,
        "--no-banner",
        "--redact",
        "--config",
        gitleaks_gate["placeholders"]["config"],
        "--report-format",
        "json",
        "--report-path",
        str(artefact),
        "--log-opts",
        f"--no-walk {sha}",
        ".",
    ]
    result = run_argv(argv, repo_root, gitleaks_gate["timeout_seconds"])
    if not result.ok:
        problems.append(f"gitleaks: {result.error}")
    elif result.returncode in gitleaks_gate["findings_exit_codes"]:
        if not artefact.exists():
            problems.append("gitleaks: no artefact produced")
        else:
            blocking_severities = set(gitleaks_gate["severity"])
            findings = PARSERS[gitleaks_gate["parser"]](artefact.read_bytes())
            for finding in findings:
                if finding["severity"] in blocking_severities:
                    problems.append(f"gitleaks: {finding['path']}: {finding['severity']}")
    elif result.returncode not in gitleaks_gate["success_exit_codes"]:
        problems.append(f"gitleaks: unexpected exit code {result.returncode}")

    return problems


def replay_range(range_arg: str, config: dict[str, Any], repo_root: Path) -> bool:
    base, sep, head = range_arg.partition("..")
    if not sep or not base or not head:
        raise GateRunError(f"replay --range must be <rev>..<rev>, got {range_arg!r}")

    ok = True
    for sha in commits_in_range(base, head, repo_root):
        problems = _replay_one_commit(sha, config, repo_root)
        status = "FAIL" if problems else "PASS"
        detail = "; ".join(problems) if problems else "clean"
        print(f"[{status}] {sha[:12]}: {detail}")
        if problems:
            ok = False
    return ok


# ---------------------------------------------------------------------------
# adapters: turn a scanner's own JSON into normalised findings. Adapter
# identifiers are mechanism names, permitted as literals (REQ-V15-GATE-02);
# no policy value (a threshold, an argv fragment) lives here.
# ---------------------------------------------------------------------------


def gitleaks_json(raw: bytes) -> list[dict[str, Any]]:
    data = json.loads(raw) or []
    return [
        {
            "path": item.get("File", ""),
            "severity": "UNKNOWN",
            "rule_id": item.get("RuleID", ""),
            "message": item.get("Description", ""),
        }
        for item in data
    ]


def trivy_json(raw: bytes) -> list[dict[str, Any]]:
    data = json.loads(raw)
    findings: list[dict[str, Any]] = []
    for result in data.get("Results") or []:
        target = result.get("Target", "")
        for vuln in result.get("Vulnerabilities") or []:
            findings.append(
                {
                    "path": target,
                    "severity": str(vuln.get("Severity", "")).upper(),
                    "rule_id": vuln.get("VulnerabilityID", ""),
                    "message": vuln.get("Title", ""),
                }
            )
        for mis in result.get("Misconfigurations") or []:
            findings.append(
                {
                    "path": target,
                    "severity": str(mis.get("Severity", "")).upper(),
                    "rule_id": mis.get("ID", ""),
                    "message": mis.get("Title", ""),
                }
            )
    return findings


def semgrep_json(raw: bytes) -> list[dict[str, Any]]:
    data = json.loads(raw)
    findings = []
    for item in data.get("results") or []:
        findings.append(
            {
                "path": item.get("path", ""),
                "severity": str(item.get("extra", {}).get("severity", "")).upper(),
                "rule_id": item.get("check_id", ""),
                "message": item.get("extra", {}).get("message", ""),
            }
        )
    return findings


_SKYLOS_CATEGORIES = (
    "unused_functions",
    "unused_imports",
    "unused_classes",
    "unused_variables",
    "unused_parameters",
    "unused_files",
)


def skylos_json(raw: bytes) -> list[dict[str, Any]]:
    data = json.loads(raw)
    findings = []
    for category in _SKYLOS_CATEGORIES:
        for item in data.get(category) or []:
            findings.append(
                {
                    "path": item.get("file", ""),
                    "severity": "LOW",
                    "rule_id": category,
                    "message": item.get("full_name") or item.get("name", ""),
                }
            )
    return findings


PARSERS = {
    "gitleaks_json": gitleaks_json,
    "trivy_json": trivy_json,
    "semgrep_json": semgrep_json,
    "skylos_json": skylos_json,
}


def normalise_finding_path(path: str, repo_root: Path) -> str | None:
    if not path:
        return None
    p = Path(path)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return None
    return p.as_posix()


# ---------------------------------------------------------------------------
# the gate execution engine (REQ-V15-GATE-06/07/08/12, REQ-V15-SCAN-*).
# ---------------------------------------------------------------------------


@dataclass
class CommandResult:
    ok: bool
    returncode: int | None
    stdout: bytes
    stderr: bytes
    error: str | None = None


def run_argv(
    argv: list[str], cwd: Path, timeout_seconds: int, *, input_bytes: bytes | None = None
) -> CommandResult:
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            input=input_bytes,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return CommandResult(False, None, b"", b"", f"binary not found: {exc}")
    except subprocess.TimeoutExpired:
        return CommandResult(False, None, b"", b"", f"timed out after {timeout_seconds}s")
    return CommandResult(True, proc.returncode, proc.stdout, proc.stderr, None)


def render_token(token: str, values: dict[str, str]) -> str:
    def _sub(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise GateRunError(f"unresolved placeholder {{{name}}}")
        return values[name]

    return _PLACEHOLDER_RE.sub(_sub, token)


def render_argv(argv: list[str], values: dict[str, Any]) -> list[str]:
    rendered: list[str] = []
    for token in argv:
        m = re.fullmatch(r"\{(\w+)\}", token)
        if m and isinstance(values.get(m.group(1)), list):
            rendered.extend(values[m.group(1)])
            continue
        rendered.append(
            render_token(token, {k: v for k, v in values.items() if isinstance(v, str)})
        )
    return rendered


@dataclass
class GateResult:
    name: str
    ran: bool
    blocked: bool
    findings_in_scope: list[dict[str, Any]] = field(default_factory=list)
    findings_out_of_scope: list[dict[str, Any]] = field(default_factory=list)
    message: str = ""
    artefact_path: Path | None = None


def _artefact_path(gate: dict[str, Any], repo_root: Path, profile: str) -> Path:
    return repo_root / render_token(gate["artefact"], {"profile": profile})


def _partition_findings(
    raw_findings: list[dict[str, Any]],
    repo_root: Path,
    scope_files: set[str] | None,
    diff_scoped: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    in_scope, out_of_scope = [], []
    for finding in raw_findings:
        norm = normalise_finding_path(finding["path"], repo_root)
        if norm is None:
            return [], [], finding["path"]
        finding = {**finding, "path": norm}
        if not diff_scoped or scope_files is None or norm in scope_files:
            in_scope.append(finding)
        else:
            out_of_scope.append(finding)
    return in_scope, out_of_scope, None


def _execute_ruff_format_partitioned(
    name: str, gate: dict[str, Any], *, repo_root: Path, scope_files: set[str] | None, timeout: int
) -> GateResult:
    blocking_paths = set(gate["blocking_paths"])
    scope = scope_files if scope_files is not None else set(blocking_paths)
    scope = {p for p in scope if p.endswith(".py")}
    new_files = sorted(p for p in scope if p in blocking_paths)
    legacy_files = sorted(p for p in scope if p not in blocking_paths)

    blocked = False
    reports = []
    for label, paths, counts_toward_blocking in (
        ("new", new_files, True),
        ("legacy", legacy_files, False),
    ):
        if not paths:
            continue
        argv = render_argv(gate["argv"], {"target": paths})
        cmd = run_argv(argv, repo_root, timeout)
        if not cmd.ok:
            return GateResult(name, ran=False, blocked=True, message=f"gate {name}: {cmd.error}")
        clean = cmd.returncode in gate["success_exit_codes"]
        if not clean and counts_toward_blocking:
            blocked = True
        reports.append(f"{label}: {len(paths)} file(s), {'clean' if clean else 'would reformat'}")
    return GateResult(
        name,
        ran=True,
        blocked=blocked and gate["blocking"],
        message="; ".join(reports) or "no files in scope",
    )


def execute_command_gate(
    name: str,
    gate: dict[str, Any],
    *,
    repo_root: Path,
    profile: str,
    scope_files: set[str] | None,
    tracked_tree: Path | None,
    known_severities: set[str],
) -> GateResult:
    timeout = gate["timeout_seconds"]
    if gate.get("blocking_paths") is not None:
        return _execute_ruff_format_partitioned(
            name, gate, repo_root=repo_root, scope_files=scope_files, timeout=timeout
        )

    result_mode = gate["result_mode"]
    values: dict[str, Any] = dict(gate.get("placeholders", {}))
    values.setdefault("profile", profile)
    if tracked_tree is not None:
        values.setdefault("tracked_tree", str(tracked_tree))

    if result_mode == "exit_status" and gate["diff_scoped"] and "target" not in values:
        if scope_files is None:
            values["target"] = "."
        else:
            paths = sorted(p for p in scope_files if p.endswith(".py"))
            if not paths:
                return GateResult(name, ran=True, blocked=False, message="no files in scope")
            values["target"] = paths
    else:
        values.setdefault("target", ".")

    artefact_path = None
    if result_mode == "findings":
        artefact_path = _artefact_path(gate, repo_root, profile)
        artefact_path.parent.mkdir(parents=True, exist_ok=True)
        values["artefact"] = str(artefact_path)

    argv = render_argv(gate["argv"], values)
    cmd = run_argv(argv, repo_root, timeout)
    if not cmd.ok:
        return GateResult(
            name, ran=False, blocked=True, message=f"gate {name} could not run: {cmd.error}"
        )

    if result_mode == "exit_status":
        if cmd.returncode in gate["success_exit_codes"]:
            return GateResult(name, ran=True, blocked=False, message="clean")
        return GateResult(
            name, ran=True, blocked=gate["blocking"], message=f"gate {name} exited {cmd.returncode}"
        )

    if cmd.returncode in gate["success_exit_codes"]:
        raw_findings: list[dict[str, Any]] = []
    elif cmd.returncode in gate["findings_exit_codes"]:
        if artefact_path is None or not artefact_path.exists():
            return GateResult(
                name, ran=False, blocked=True, message=f"gate {name}: no artefact produced"
            )
        try:
            raw_findings = PARSERS[gate["parser"]](artefact_path.read_bytes())
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return GateResult(
                name, ran=False, blocked=True, message=f"gate {name}: unparseable output: {exc}"
            )
    else:
        return GateResult(
            name,
            ran=False,
            blocked=True,
            message=f"gate {name}: unexpected exit code {cmd.returncode}",
        )

    in_scope, out_of_scope, bad_path = _partition_findings(
        raw_findings, repo_root, scope_files, gate["diff_scoped"]
    )
    if bad_path is not None:
        return GateResult(
            name,
            ran=False,
            blocked=True,
            message=f"gate {name}: finding path could not be normalised: {bad_path!r}",
        )
    for finding in in_scope + out_of_scope:
        severity = finding["severity"]
        if not severity or severity not in known_severities:
            return GateResult(
                name,
                ran=False,
                blocked=True,
                message=f"gate {name}: finding has an unrecognised severity {severity!r}",
            )

    blocking_findings = [f for f in in_scope if f["severity"] in gate["severity"]]
    blocked = gate["blocking"] and bool(blocking_findings)
    return GateResult(
        name,
        ran=True,
        blocked=blocked,
        findings_in_scope=in_scope,
        findings_out_of_scope=out_of_scope,
        message=f"{len(in_scope)} in-scope finding(s), {len(out_of_scope)} out-of-scope",
        artefact_path=artefact_path,
    )


def execute_builtin_gate(
    name: str, gate: dict[str, Any], *, config: dict[str, Any], repo_root: Path, profile: str
) -> GateResult:
    handler = gate["handler"]
    if handler == "branch_name":
        status, msg = check_branch_name(
            current_branch(repo_root), gate["pattern"], gate["warn_refs"], gate["warn_on_detached"]
        )
        return GateResult(
            name, ran=True, blocked=gate["blocking"] and status == "fail", message=msg
        )
    if handler == "doctor":
        return GateResult(name, ran=False, blocked=True, message="doctor: lands in T9")
    if handler == "lint_docs":
        return GateResult(name, ran=False, blocked=True, message="lint-docs: lands in T11")
    raise GateConfigError(f"gates.{name}: unknown handler {handler!r}")


@dataclass
class ProfileResult:
    profile: str
    gate_results: list[GateResult]

    @property
    def blocked(self) -> bool:
        return any(g.blocked for g in self.gate_results)


def _known_severities(config: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for gate in config["gates"].values():
        if gate.get("result_mode") == "findings":
            values |= set(gate["severity"])
    return values


def run_profile(
    profile: str,
    config: dict[str, Any],
    repo_root: Path,
    *,
    since: str | None = None,
    stdin_refs: str | None = None,
) -> ProfileResult:
    scope_files, tracked_tree, cleanup_dirs = compute_scope(
        profile, config, repo_root, since=since, stdin_refs=stdin_refs
    )
    known_severities = _known_severities(config)
    results: list[GateResult] = []
    try:
        for gate_name in config["profiles"][profile]:
            gate = config["gates"][gate_name]
            if gate["kind"] == "builtin":
                result = execute_builtin_gate(
                    gate_name, gate, config=config, repo_root=repo_root, profile=profile
                )
            else:
                result = execute_command_gate(
                    gate_name,
                    gate,
                    repo_root=repo_root,
                    profile=profile,
                    scope_files=scope_files if gate["diff_scoped"] else None,
                    tracked_tree=tracked_tree,
                    known_severities=known_severities,
                )
            results.append(result)
    finally:
        for d in cleanup_dirs:
            shutil.rmtree(d, ignore_errors=True)
    return ProfileResult(profile, results)


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
    config = load_gate_config()
    stdin_text = sys.stdin.read() if args.stdin_refs else None
    try:
        result = run_profile(
            args.profile, config, REPO_ROOT, since=args.since, stdin_refs=stdin_text
        )
    except (GateRunError, EmptyScopeError) as exc:
        print(f"checks.py run --profile {args.profile}: {exc}", file=sys.stderr)
        return 2
    for gate_result in result.gate_results:
        status = "FAIL" if gate_result.blocked else "PASS"
        print(f"[{status}] {gate_result.name}: {gate_result.message}")
    return 1 if result.blocked else 0


def cmd_doctor(args: argparse.Namespace) -> int:
    print("checks.py doctor: lands in T9", file=sys.stderr)
    return 2


def cmd_replay(args: argparse.Namespace) -> int:
    config = load_gate_config()
    try:
        ok = replay_range(args.range, config, REPO_ROOT)
    except GateRunError as exc:
        print(f"checks.py replay: {exc}", file=sys.stderr)
        return 2
    return 0 if ok else 1


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
