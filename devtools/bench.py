"""The v1.3 benchmark harness (spec-v1.3 section 7): `run`, `report`, `check`.

Pytest cannot measure tokens — every LLM call is faked there — so measurement
lives here: a live, deterministic-as-possible driver that replays the twelve
frozen scenarios of `devtools/bench_scenarios.py` through the real
`bot.process_update` and copies the `llm_calls` / `tool_calls` rows the agent
wrote into one self-describing JSON document (`bench_schema: 1`, section 7.4).

Three properties are load-bearing and easy to lose:

* **Nothing is trusted.** `check` recomputes every `runs[].totals` and every
  `summary` value from the embedded rows; the stored aggregates are compared
  against that recomputation, never read as input. A harness that silently
  dropped a scenario, or a hand-edited file, is caught arithmetically.
* **The treatment is pinned by the harness, not by a maintainer's `.env`.**
  `meta.env_flags`, `meta.config_sha256` and `meta.constants` record what was
  measured, and `report --gate` refuses to compare two files that disagree.
* **The wiring mirrors `bot.main()` literally** (REQ-V13-BEN-03), because a
  benchmark of a differently wired agent measures nothing.

Never imported by production code (REQ-V12-TREE-01).
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import functools
import hashlib
import json
import logging
import math
import os
import re
import shutil
import sqlite3
import statistics
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    # `bench.py` is invoked as a script (section 13.2), so the project root is
    # not on `sys.path` by default.
    sys.path.insert(0, str(REPO_ROOT))

import httpx  # noqa: E402

import agent  # noqa: E402
import bot  # noqa: E402
import config  # noqa: E402
import llm as llm_module  # noqa: E402
import metrics  # noqa: E402
import storage  # noqa: E402
import tools  # noqa: E402
from config import Config  # noqa: E402
from devtools import bench_scenarios  # noqa: E402
from devtools.bench_scenarios import SCENARIOS, Scenario  # noqa: E402
from llm import base as llm_base  # noqa: E402
from llm import pricing  # noqa: E402

log = logging.getLogger("bench")

BENCH_SCHEMA = 1
DEFAULT_REPEATS = 3
DEFAULT_TIMEOUT_S = 600
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "assets" / "bench"
BENCH_ROOT = REPO_ROOT / ".bench"
BOT_USERNAME = "bench"
PREFIX_PROBE_MESSAGE = "ping"
NETWORK_PROBE_URL = "https://wttr.in/"
NETWORK_PROBE_TIMEOUT_S = 5.0
SUMMARY_LINE_LIMIT = 40
# A short settle between runs: the previous run's container has just been
# removed and its sandbox unlinked. `run_bench` never sleeps after the last run.
INTER_RUN_SLEEP_S = 0.5

# Exit codes (REQ-V13-BEN-01, REQ-V13-BEN-02).
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOT_COMPARABLE = 2
EXIT_USAGE_MISSING = 3
EXIT_ABORTED = 4

# `runs[].failure`, in the precedence order of section 7.4.
FAIL_HARNESS_ERROR = "harness_error"
FAIL_TIMEOUT = "timeout"
FAIL_USAGE_MISSING = "usage_missing"
FAIL_COST_CAP = "cost_cap"
FAIL_CHECKS = "checks"
FAILURES = (FAIL_HARNESS_ERROR, FAIL_TIMEOUT, FAIL_USAGE_MISSING, FAIL_COST_CAP, FAIL_CHECKS)

ABORT_SIGINT = "sigint"
ABORT_COST_CAP = "cost_cap"

REDACTED_TG_ID = "[tg-id]"

# The seven keys of `meta.env_flags`, in the order of the 7.4 schema, mapped to
# the `config.Config` field that carries each. A field absent at this commit is
# recorded as `null` (REQ-V13-BEN-10) — never guessed, never omitted.
ENV_FLAG_FIELDS = {
    "HISTORY_TOOL_STUB": "history_tool_stub",
    "EXEC_OUTPUT_DEFAULT_CHARS": "exec_output_default_chars",
    "FETCH_INLINE_DEFAULT_CHARS": "fetch_inline_default_chars",
    "LLM_REASONING": "llm_reasoning",
    "LLM_SUMMARY_MODEL": "llm_summary_model",
    "LLM_FAILOVER": "llm_failover",
    "LLM_MAX_TOKENS": "llm_max_tokens",
}
ENV_FLAG_KEYS = tuple(ENV_FLAG_FIELDS)
# The stage-C treatment (REQ-V13-PRE-04): `null` on a C1 baseline, the PRE-04
# default on a C3 candidate.
STAGE_C_DEFAULTS = {
    "HISTORY_TOOL_STUB": "on",
    "EXEC_OUTPUT_DEFAULT_CHARS": 1500,
    "FETCH_INLINE_DEFAULT_CHARS": 5000,
    "LLM_REASONING": "auto",
}
STAGE_C_KEYS = tuple(STAGE_C_DEFAULTS)

# What `meta.config_sha256` deliberately leaves out (section 7.4): secrets,
# identifiers, the location, every `Path` (per run) and the treatment itself.
# `llm_max_tokens` is deliberately NOT excluded: it is pinned equal by
# `env_flags`, and hashing it makes a silent change to it a locked-field
# mismatch rather than an invisible one.
CONFIG_HASH_EXCLUDED = frozenset({
    "telegram_bot_token", "openrouter_api_key",          # secrets
    "allowed_tg_ids", "telegram_bot_name",               # identifiers
    "lmstudio_base_url",                                 # location
    "exec_workdir", "db_path", "audit_log_path",         # per-run paths
    "llm_failover", "llm_summary_model", "history_tool_stub",
    "exec_output_default_chars", "fetch_inline_default_chars", "llm_reasoning",
})

LOCKED_META_FIELDS = (
    "provider", "model", "context_length", "repeats", "timeout_s",
    "scenarios_sha256", "skipped_scenarios", "constants", "config_sha256",
    # `only` is not in the 7.4 list; it is the documented reconciliation of
    # REQ-V13-BEN-01's run-set rule with REQ-V13-AUD-03 / REQ-V13-RSN-02, which
    # both require `report` to render a file produced by `--only`. Locking it
    # keeps a one-run file from ever being compared with a full one.
    "only",
)

TOTALS_KEYS = (
    "calls", "failed_calls", "prompt_tokens", "completion_tokens", "cached_tokens",
    "reasoning_tokens", "tool_calls", "tool_output_tokens_est", "latency_ms",
    "cost_usd", "resent_tokens", "new_tokens", "wall_ms",
)
AVG_KEYS = ("tokens", "rounds", "tool_calls", "latency_ms")
PRICING_BASES_WITH_MODEL = ("openrouter-list", "openrouter-list-stale")

LLM_ROW_KEYS = frozenset(storage.LLM_CALL_COLUMNS) - {"conv_id"} | {"conv_seq"}
TOOL_ROW_KEYS = frozenset(storage.TOOL_CALL_COLUMNS) - {"conv_id"} | {"conv_seq"}

FLOAT_REL_TOL = 1e-9
FLOAT_ABS_TOL = 1e-12

COST_GATE_FACTOR = 0.70
QUALITY_GATE_SLACK = 0.02


# --------------------------------------------------------------------------
# meta: what was measured
# --------------------------------------------------------------------------

def scenarios_sha256() -> str:
    """The sha256 of `devtools/bench_scenarios.py`'s bytes (REQ-V13-BEN-12).

    Hashing the file rather than the objects is the point: a changed check, a
    changed turn and a changed id are all one comparison away from being caught.
    """
    return hashlib.sha256(Path(bench_scenarios.__file__).read_bytes()).hexdigest()


def env_flags(cfg: Config) -> dict:
    """Exactly the seven keys of the 7.4 schema, at every commit."""
    present = {item.name for item in dataclasses.fields(Config)}
    return {
        key: (getattr(cfg, field_name) if field_name in present else None)
        for key, field_name in ENV_FLAG_FIELDS.items()
    }


def config_sha256(cfg: Config) -> str:
    """A hash of every behaviour-affecting, non-secret, non-treatment `Config`
    field. A secret is never serialized, not even hashed."""
    fields: dict[str, Any] = {}
    for item in dataclasses.fields(Config):
        if item.name in CONFIG_HASH_EXCLUDED:
            continue
        value = getattr(cfg, item.name)
        if isinstance(value, Path):
            continue
        if isinstance(value, (frozenset, set)):
            value = sorted(value)
        fields[item.name] = value
    encoded = json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def constants() -> dict:
    """The seven module constants plus `llm.base.REQUEST_DEFAULTS` verbatim.

    Recorded, never made configurable: sampling or request-control drift between
    two files is a locked-field mismatch, not a hidden treatment.
    """
    return {
        "CONTEXT_WINDOW_MESSAGES": agent.CONTEXT_WINDOW_MESSAGES,
        "EXEC_MAX_STREAM_BYTES": tools.EXEC_MAX_STREAM_BYTES,
        "FETCH_MAX_BYTES": tools.FETCH_MAX_BYTES,
        "ROUND_LIMIT": agent.ROUND_LIMIT,
        "TOOL_ROUND_LIMIT": agent.TOOL_ROUND_LIMIT,
        "TOOL_EXECUTION_LIMIT": agent.TOOL_EXECUTION_LIMIT,
        "HTTP_ATTEMPT_LIMIT": agent.HTTP_ATTEMPT_LIMIT,
        "REQUEST_DEFAULTS": dict(llm_base.REQUEST_DEFAULTS),
    }


def context_length(cfg: Config) -> int:
    """The *configured* context length — never a measured server property."""
    if cfg.llm_provider == "openrouter":
        return cfg.openrouter_context_length
    return cfg.lmstudio_context_length


# --------------------------------------------------------------------------
# checks (section 7.3): evaluated against one run's observation
# --------------------------------------------------------------------------

@dataclass
class Observation:
    """Everything a check may look at. `answers` holds one entry per
    **non-command** user turn, so the one-based `turn` of a check indexes it
    directly (REQ-V13-BEN-08)."""

    answers: list[str] = field(default_factory=list)
    llm_rows: list[dict] = field(default_factory=list)
    tool_rows: list[dict] = field(default_factory=list)
    exit_codes: list[int] = field(default_factory=list)
    summary_goals: list[str] = field(default_factory=list)
    audit_read: bool = True


def evaluate_checks(scenario: Scenario, observation: Observation) -> list[dict]:
    """One `{kind, ok, detail}` per check. `detail` is a bounded reason code —
    never an excerpt of the answer (REQ-V13-BEN-10)."""
    return [
        {"kind": check.kind, **_evaluate(check, scenario, observation)}
        for check in scenario.checks
    ]


def _evaluate(check, scenario: Scenario, obs: Observation) -> dict:
    kind = check.kind
    if kind == bench_scenarios.TOOL_USED:
        used = any(row["tool"] == check.tool for row in obs.tool_rows)
        return _outcome(used, f"{check.tool} not called" if not used else "called")
    if kind == bench_scenarios.NO_TOOLS:
        count = len(obs.tool_rows)
        return _outcome(count == 0, f"{count} tool call(s) made")
    if kind == bench_scenarios.EXIT_CODE_SEEN:
        if not obs.audit_read:
            return _outcome(False, "audit log unreadable")
        seen = any((code != 0) == check.nonzero for code in obs.exit_codes)
        want = "non-zero" if check.nonzero else "zero"
        return _outcome(seen, f"no {want} exit code among {len(obs.exit_codes)}")
    if kind == bench_scenarios.SUMMARY_EXISTS:
        goals = [goal for goal in obs.summary_goals if goal.strip()]
        return _outcome(bool(goals), f"{len(obs.summary_goals)} summary row(s), no goal")

    answer = _answer_for(check, scenario, obs)
    if answer is None:
        return _outcome(False, f"no answer for turn {check.turn}")
    if kind == bench_scenarios.ANSWER_REGEX:
        found = re.search(check.pattern, answer, re.I | re.S) is not None
        return _outcome(found, "pattern not found")
    if kind == bench_scenarios.ANSWER_NOT_REGEX:
        found = re.search(check.pattern, answer, re.I | re.S) is not None
        return _outcome(not found, "forbidden pattern found")
    if kind == bench_scenarios.ANSWER_MAX_CHARS:
        return _outcome(
            len(answer) <= check.max_chars,
            f"{len(answer)} > {check.max_chars} chars",
        )
    if kind == bench_scenarios.JSON_KEYS:
        return _json_keys_outcome(check, answer)
    return _outcome(False, f"unknown check kind: {kind}")


def _first_json_object(text: str) -> str | None:
    """The first balanced `{…}` of `text` (section 7.3), or `None`.

    A regex cannot do this: `{.*?}` stops at the first `}`, which truncates
    every nested object and every brace inside a string literal, and `{.*}`
    swallows a second object. The scan tracks depth outside string literals
    only, and an unterminated brace is not an object — it restarts at the next
    one instead of failing the whole answer.
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        start = text.find("{", start + 1)
    return None


def _json_keys_outcome(check, answer: str) -> dict:
    expected = check.expected_json
    candidate = _first_json_object(answer)
    if candidate is None:
        return _outcome(False, "no json object in the answer")
    try:
        parsed = json.loads(candidate)
    except ValueError:
        return _outcome(False, "the json object does not parse")
    if not isinstance(parsed, dict):
        return _outcome(False, "the json value is not an object")
    matched = sum(1 for key, value in expected.items() if parsed.get(key) == value)
    return _outcome(
        matched == len(expected), f"{matched} of {len(expected)} keys matched"
    )


def _answer_for(check, scenario: Scenario, obs: Observation) -> str | None:
    if check.turn is None:
        return None
    index = scenario.turn_index(check.turn)
    if not 0 <= index < len(obs.answers):
        return None
    return obs.answers[index]


def _outcome(ok: bool, detail: str) -> dict:
    return {"ok": bool(ok), "detail": "ok" if ok else detail[:120]}


# --------------------------------------------------------------------------
# arithmetic (section 7.4) — one implementation, used by the writer *and* by
# `check`, which never reads a stored aggregate
# --------------------------------------------------------------------------

def _conv_groups(rows: Sequence[dict]) -> list[list[dict]]:
    """The run's `llm_calls` rows split by `conv_seq`, each group ordered by
    `id` — a `/new` turn starts a new group and resets the re-sent arithmetic."""
    groups: dict[int, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["conv_seq"], []).append(row)
    return [groups[key] for key in sorted(groups)]


def _isum(rows: Sequence[dict], column: str) -> int:
    return sum(int(row[column] or 0) for row in rows)


def totals_from_rows(llm_rows: Sequence[dict], tool_rows: Sequence[dict], wall_ms: int) -> dict:
    """`runs[].totals` from the embedded rows alone.

    `wall_ms` is the one value no row carries: it is measured, passed in, and
    the only key `check` cannot recompute (it validates its type instead).
    """
    resent = 0
    fresh = 0
    for group in _conv_groups(llm_rows):
        group_resent, group_new = metrics.resent_tokens(group)
        resent += group_resent
        fresh += group_new
    priced = [row["cost_usd"] for row in llm_rows if row["cost_usd"] is not None]
    return {
        "calls": len(llm_rows),
        "failed_calls": sum(1 for row in llm_rows if row["error_kind"] is not None),
        "prompt_tokens": _isum(llm_rows, "prompt_tokens"),
        "completion_tokens": _isum(llm_rows, "completion_tokens"),
        "cached_tokens": _isum(llm_rows, "cached_tokens"),
        "reasoning_tokens": _isum(llm_rows, "reasoning_tokens"),
        "tool_calls": len(tool_rows),
        "tool_output_tokens_est": _isum(tool_rows, "output_tokens_est"),
        "latency_ms": _isum(llm_rows, "latency_ms"),
        "cost_usd": float(sum(priced)) if priced else None,
        "resent_tokens": resent,
        "new_tokens": fresh,
        "wall_ms": int(wall_ms),
    }


def summarize(runs: Sequence[dict], skipped_scenarios: Sequence[str], repeats: int) -> dict:
    """The whole `summary` object from `runs[]` — every value recomputable."""
    count = len(runs)
    successes = sum(1 for run in runs if run["success"])
    llm_rows = [row for run in runs for row in run["llm_calls"]]
    tool_rows = [row for run in runs for row in run["tool_calls"]]

    totals = {}
    for key in TOTALS_KEYS:
        values = [run["totals"][key] for run in runs]
        present = [value for value in values if value is not None]
        if key == "cost_usd":
            totals[key] = float(sum(present)) if present else None
        else:
            totals[key] = sum(present)

    tokens = totals["prompt_tokens"] + totals["completion_tokens"]
    rounds = sum(
        1 for row in llm_rows if row["purpose"] == "agent" and row["error_kind"] is None
    )
    prompt_total = totals["prompt_tokens"]
    cached_reported = any(row["cached_tokens"] is not None for row in llm_rows)

    return {
        "runs": count,
        "skipped": len(skipped_scenarios) * repeats,
        "successes": successes,
        "success_rate": (successes / count) if count else 0.0,
        "per_scenario": _per_scenario(runs),
        "totals": totals,
        "avg_per_task": {
            "tokens": (tokens / count) if count else 0.0,
            "rounds": (rounds / count) if count else 0.0,
            "tool_calls": (totals["tool_calls"] / count) if count else 0.0,
            "latency_ms": (totals["latency_ms"] / count) if count else 0.0,
        },
        "cost_per_success": (
            (totals["cost_usd"] / successes)
            if totals["cost_usd"] is not None and successes
            else None
        ),
        "tokens_per_success": (tokens / successes) if successes else None,
        "resent_share": (totals["resent_tokens"] / prompt_total) if prompt_total else 0.0,
        "cache_hit_rate": (
            (totals["cached_tokens"] / prompt_total)
            if cached_reported and prompt_total
            else (0.0 if cached_reported else None)
        ),
        "top_tools": top_tools(tool_rows),
        "top_turn": _top_turn(runs),
        "context_growth": _context_growth(runs),
    }


def _per_scenario(runs: Sequence[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for run in runs:
        grouped.setdefault(run["scenario"], []).append(run)
    return {
        scenario_id: {
            "success": sum(1 for run in entries if run["success"]),
            "of": len(entries),
            "median": {
                key: _median([run["totals"][key] for run in entries])
                for key in TOTALS_KEYS
            },
        }
        for scenario_id, entries in grouped.items()
    }


def _median(values: Sequence) -> float | int | None:
    present = [value for value in values if value is not None]
    return statistics.median(present) if present else None


def top_tools(tool_rows: Sequence[dict]) -> list[dict]:
    """`[{name, calls, output_tokens_est}]`, biggest output first.

    REQ-V13-OBS-08 asks for one implementation of each *aggregate*; the shared
    ones (`resent_tokens`, `context_growth`) are imported from `metrics`. This
    group-by is not one of them: `metrics.top_tools` reads a live connection and
    returns shares for `/stats`, while a benchmark file has neither.
    """
    totals: dict[str, dict] = {}
    for row in tool_rows:
        entry = totals.setdefault(row["tool"], {"name": row["tool"], "calls": 0,
                                                "output_tokens_est": 0})
        entry["calls"] += 1
        entry["output_tokens_est"] += int(row["output_tokens_est"] or 0)
    return sorted(totals.values(), key=lambda item: (-item["output_tokens_est"], item["name"]))


def _top_turn(runs: Sequence[dict]) -> dict | None:
    best = None
    for run in runs:
        for row in run["llm_calls"]:
            prompt = row["prompt_tokens"]
            if prompt is None:
                continue
            if best is None or prompt > best["prompt_tokens"]:
                best = {
                    "scenario": run["scenario"],
                    "repeat": run["repeat"],
                    "turn": row["turn_id"],
                    "round": row["round"],
                    "prompt_tokens": prompt,
                }
    return best


def _context_growth(runs: Sequence[dict]) -> dict:
    roles = metrics.PROMPT_ROLE_KEYS
    if not runs:
        return {role: 0.0 for role in roles}
    per_run = [metrics.context_growth(run["llm_calls"]) for run in runs]
    return {
        role: sum(growth.get(role, 0.0) for growth in per_run) / len(per_run)
        for role in roles
    }


# --------------------------------------------------------------------------
# redaction (REQ-V13-BEN-10)
# --------------------------------------------------------------------------

def redact_document(document: Any, tg_ids: Sequence[int]) -> Any:
    """Every string value in the whole document, recursively: registered
    secrets first, then the decimal form of every allowed Telegram id."""
    ids = [str(value) for value in sorted(tg_ids, key=lambda value: -len(str(value)))]

    def scrub(text: str) -> str:
        text = config.redact(text)
        for identifier in ids:
            text = text.replace(identifier, REDACTED_TG_ID)
        return text

    def walk(value):
        if isinstance(value, str):
            return scrub(value)
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        return value

    return walk(document)


# --------------------------------------------------------------------------
# the run mechanics (section 7.2)
# --------------------------------------------------------------------------

@dataclass
class BenchResult:
    meta: dict
    runs: list[dict]
    summary: dict

    @property
    def aborted(self) -> str | None:
        return self.meta.get("aborted")

    def document(self) -> dict:
        return {
            "bench_schema": BENCH_SCHEMA,
            "meta": self.meta,
            "runs": self.runs,
            "summary": self.summary,
        }


class BenchTelegram:
    """The in-process stand-in for Telegram — the same duck type as
    `bot._SelftestTelegram`. The harness never constructs `TelegramClient`."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.status: list[tuple[int, str]] = []
        self.edits: list[tuple[int, int, str]] = []

    def send_message(self, chat_id: int, text: str) -> dict:
        if text == bot.STATUS_WORKING:
            self.status.append((chat_id, text))
            return {"message_id": 1}
        self.sent.append((chat_id, text))
        return {"message_id": 100 + len(self.sent)}

    def edit_message_text(self, chat_id: int, message_id: int, text: str) -> dict:
        self.edits.append((chat_id, message_id, text))
        return {"message_id": message_id}


def run_bench(
    scenarios: Sequence[Scenario],
    *,
    cfg: Config,
    llm_factory: Callable[[Config], Any],
    runner_factory: Callable[[Config], Any],
    fetcher_factory: Callable[[Config], Any],
    telegram_factory: Callable[[], Any],
    repeats: int,
    timeout_s: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    network_preflight: Callable[[], bool],
    skills: dict,
    runs_root: Path,
    resolve_cost=None,
    max_cost_usd: float | None = None,
) -> BenchResult:
    """The measurable core (REQ-V13-BEN-07). `main()` wires real objects; the
    tests wire `FakeLLM` / `RecordingRunner` / `FakeFetcher` and never touch
    Docker, the network or Telegram.

    Three arguments are not in the 7.2 sketch and are forced by requirements it
    references: `runs_root` is the `.bench/<tag>/` of REQ-V13-BEN-03 (passing it
    keeps `PROJECT_ROOT` arithmetic out of the core), `skills` is what
    `bot.main()` loads once, and `resolve_cost` is the `CostResolver` that
    REQ-V13-PRC-02 requires to be built once per CLI invocation and handed down
    — without it no run would have a cost and the cost cap could never trip.

    The docker probe and `bot._startup_docker_wiring` live inside the *real*
    `runner_factory`, called once per run with that run's `cfg`: they are the
    part of `main()`'s order that touches Docker and DNS, and injecting them is
    what keeps the offline suite offline.
    """
    network_ok = _preflight(network_preflight)
    skipped = sorted({s.id for s in scenarios if s.network}) if not network_ok else []
    probe_llm = llm_factory(cfg)
    provider, model = llm_base.describe_client(probe_llm)

    meta = {
        "provider": provider,
        "model": model,
        "context_length": context_length(cfg),
        "repeats": int(repeats),
        "timeout_s": timeout_s,
        # The selection is authoritative only at the CLI, which knows `--only`;
        # `None` means "every scenario of the catalog was in scope".
        "only": None,
        "scenarios_sha256": scenarios_sha256(),
        "skipped_scenarios": skipped,
        "env_flags": env_flags(cfg),
        "config_sha256": config_sha256(cfg),
        "constants": constants(),
    }

    runs: list[dict] = []
    aborted: str | None = None
    spent = 0.0
    for scenario in scenarios:
        if scenario.id in skipped:
            continue
        for repeat in range(1, int(repeats) + 1):
            if runs:
                sleep(INTER_RUN_SLEEP_S)
            record, aborted = _execute_run(
                scenario, repeat,
                cfg=cfg, runs_root=runs_root, llm_factory=llm_factory,
                runner_factory=runner_factory, fetcher_factory=fetcher_factory,
                telegram_factory=telegram_factory, timeout_s=timeout_s, clock=clock,
                skills=skills, resolve_cost=resolve_cost,
            )
            runs.append(record)
            if aborted is not None:
                break
            spent += record["totals"]["cost_usd"] or 0.0
            if max_cost_usd is not None and spent > max_cost_usd:
                log.warning("cost cap reached: $%.4f > $%.4f", spent, max_cost_usd)
                aborted = ABORT_COST_CAP
                break
        if aborted is not None:
            break

    if aborted is not None:
        meta["aborted"] = aborted
    return BenchResult(meta=meta, runs=runs, summary=summarize(runs, skipped, repeats))


def _preflight(network_preflight: Callable[[], bool]) -> bool:
    try:
        return bool(network_preflight())
    except Exception as exc:                       # a probe must never abort a run
        log.warning("network preflight failed: %s", config.redact(str(exc)))
        return False


def _execute_run(
    scenario: Scenario,
    repeat: int,
    *,
    cfg: Config,
    runs_root: Path,
    llm_factory,
    runner_factory,
    fetcher_factory,
    telegram_factory,
    timeout_s: float,
    clock,
    skills: dict,
    resolve_cost,
) -> tuple[dict, str | None]:
    run_dir = Path(runs_root) / f"{scenario.id}-{repeat}"
    aborted: str | None = None
    failure: str | None = None
    answers: list[str] = []
    outcome: dict = {}

    try:
        run_cfg = _run_config(cfg, run_dir)
    except Exception as exc:
        log.error("run %s-%d could not be prepared: %s", scenario.id, repeat,
                  config.redact(str(exc)))
        return _run_record(scenario, repeat, Observation(), 0, FAIL_HARNESS_ERROR), None

    recorder = telegram_factory()
    started = clock()
    worker = threading.Thread(
        target=_run_turns,
        kwargs={
            "scenario": scenario, "cfg": run_cfg, "llm_factory": llm_factory,
            "runner_factory": runner_factory, "fetcher_factory": fetcher_factory,
            "recorder": recorder, "skills": skills, "resolve_cost": resolve_cost,
            "answers": answers, "outcome": outcome,
        },
        name=f"bench-{scenario.id}-{repeat}",
        daemon=True,
    )
    worker.start()
    try:
        worker.join(timeout_s)
    except KeyboardInterrupt:
        # The same abort path as a timeout, taken immediately: the worker is
        # abandoned where it stands and nothing further is started.
        failure, aborted = FAIL_HARNESS_ERROR, ABORT_SIGINT
    else:
        if worker.is_alive():
            failure = FAIL_TIMEOUT
            aborted = f"timeout:{scenario.id}-{repeat}"
        elif outcome.get("error"):
            log.error("run %s-%d failed: %s", scenario.id, repeat, outcome["error"])
            failure = FAIL_HARNESS_ERROR
    wall_ms = max(0, round((clock() - started) * 1000))

    observation = _observe(run_cfg, answers)
    record = _run_record(scenario, repeat, observation, wall_ms, failure)
    if aborted is None:
        # An aborted run's directory stays for inspection; `.bench/` is
        # git-ignored and wiped by the next `run`.
        _remove_run_dir(run_dir)
    return record, aborted


def _run_config(cfg: Config, run_dir: Path) -> Config:
    """The run's own `sandbox/`, `bot.db` and `audit.jsonl`, as siblings.

    `config._check_sandbox_placement` is called on the result for the same
    reason `load_config` calls it: the exec container mounts `EXEC_WORKDIR`
    read-write, so the DB and the audit log must not be inside it.
    """
    run_dir = Path(run_dir)
    workdir = run_dir / "sandbox"
    db_path = run_dir / "bot.db"
    audit_log_path = run_dir / "audit.jsonl"
    config._check_sandbox_placement(workdir, db_path, audit_log_path)
    workdir.mkdir(parents=True, exist_ok=True)
    workdir.chmod(0o700)
    return dataclasses.replace(
        cfg, exec_workdir=workdir, db_path=db_path, audit_log_path=audit_log_path
    )


def _run_turns(
    *, scenario: Scenario, cfg: Config, llm_factory, runner_factory, fetcher_factory,
    recorder, skills: dict, resolve_cost, answers: list[str], outcome: dict,
) -> None:
    """The worker thread. It owns the run's SQLite connection end to end —
    `sqlite3` connections belong to the thread that created them, and the main
    thread reads the committed rows through its own read-only connection."""
    conn = None
    try:
        conn = storage.connect(cfg.db_path)
        storage.init_schema(conn)
        llm = llm_factory(cfg)
        runner = runner_factory(cfg)
        fetcher = fetcher_factory(cfg)
        tg_id = sorted(cfg.allowed_tg_ids)[0]
        for index, text in enumerate(scenario.turns, start=1):
            before = len(recorder.sent)
            bot.process_update(
                _update(index, tg_id, text),
                conn=conn, tg=recorder, cfg=cfg, llm=llm, skills=skills,
                runner=runner, bot_username=BOT_USERNAME, fetcher=fetcher,
                resolve_cost=resolve_cost,
            )
            if not bench_scenarios.is_command(text):
                # `bot._send` splits one reply into Telegram-sized parts; the
                # split loses nothing, so the parts concatenate back exactly.
                answers.append("".join(part for _chat, part in recorder.sent[before:]))
    except BaseException as exc:                   # noqa: BLE001 - reported, never raised
        outcome["error"] = f"{exc.__class__.__name__}: {config.redact(str(exc))}"[:200]
    finally:
        if conn is not None:
            with contextlib.suppress(sqlite3.Error):
                conn.close()
        outcome["done"] = True


def _update(index: int, tg_id: int, text: str) -> dict:
    return {
        "update_id": index,
        "message": {
            "message_id": index,
            "date": 0,
            "chat": {"id": tg_id, "type": "private"},
            "from": {"id": tg_id, "is_bot": False},
            "text": text,
        },
    }


def _observe(cfg: Config, answers: list[str]) -> Observation:
    llm_rows, tool_rows, goals = _read_rows(cfg.db_path)
    exit_codes, audit_read = _read_exit_codes(cfg.audit_log_path)
    return Observation(
        answers=list(answers), llm_rows=llm_rows, tool_rows=tool_rows,
        exit_codes=exit_codes, summary_goals=goals, audit_read=audit_read,
    )


def _read_rows(db_path: Path) -> tuple[list[dict], list[dict], list[str]]:
    """The committed rows, through a read-only connection of this thread's own.

    Called after a normal completion as well as on a timeout, where it is a
    snapshot: the abandoned worker may still be inside a call, and only what it
    committed (every `add_llm_call` commits immediately) is visible.
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        log.error("the run database could not be opened: %s", config.redact(str(exc)))
        return [], [], []
    conn.row_factory = sqlite3.Row
    try:
        llm_rows = [dict(row) for row in conn.execute("SELECT * FROM llm_calls ORDER BY id")]
        tool_rows = [dict(row) for row in conn.execute("SELECT * FROM tool_calls ORDER BY id")]
        goals = [
            _summary_goal(row["summary_json"])
            for row in conn.execute("SELECT summary_json FROM summaries ORDER BY id")
        ]
    except sqlite3.Error as exc:
        log.error("the run database could not be read: %s", config.redact(str(exc)))
        return [], [], []
    finally:
        conn.close()
    return _with_conv_seq(llm_rows, tool_rows) + (goals,)


def _summary_goal(summary_json: str) -> str:
    try:
        parsed = json.loads(summary_json)
    except ValueError:
        return ""
    goal = parsed.get("goal") if isinstance(parsed, dict) else None
    return goal if isinstance(goal, str) else ""


def _with_conv_seq(
    llm_rows: list[dict], tool_rows: list[dict]
) -> tuple[list[dict], list[dict]]:
    """`conv_id` never leaves this function: the rows carry `conv_seq`, the
    1-based ordinal of the conversation in order of first appearance, so a
    `/new` turn is visible without any database identifier being published."""
    order: dict[int, int] = {}
    for row in [*llm_rows, *tool_rows]:
        order.setdefault(row["conv_id"], len(order) + 1)

    def convert(rows: list[dict]) -> list[dict]:
        converted = []
        for row in rows:
            row = dict(row)
            row["conv_seq"] = order[row.pop("conv_id")]
            converted.append(row)
        return converted

    return convert(llm_rows), convert(tool_rows)


def _read_exit_codes(audit_log_path: Path) -> tuple[list[int], bool]:
    """The exec exit codes of the run, from its audit log — the `tool_calls`
    table records the outcome of the *tool*, not the command's exit status."""
    try:
        text = Path(audit_log_path).read_text(encoding="utf-8")
    except OSError:
        return [], False
    codes = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        code = record.get("exit_code") if isinstance(record, dict) else None
        if isinstance(code, int) and not isinstance(code, bool):
            codes.append(code)
    return codes, True


def _run_record(
    scenario: Scenario, repeat: int, obs: Observation, wall_ms: int, failure: str | None
) -> dict:
    checks = evaluate_checks(scenario, obs)
    if failure is None and _usage_missing(obs.llm_rows):
        failure = FAIL_USAGE_MISSING
    if failure is None and not all(check["ok"] for check in checks):
        failure = FAIL_CHECKS
    return {
        "scenario": scenario.id,
        "repeat": repeat,
        "success": failure is None,
        "failure": failure,
        "checks": checks,
        "answers": list(obs.answers),
        "llm_calls": obs.llm_rows,
        "tool_calls": obs.tool_rows,
        "totals": totals_from_rows(obs.llm_rows, obs.tool_rows, wall_ms),
    }


def _usage_missing(llm_rows: Sequence[dict]) -> bool:
    """A *completed* invocation that reported no usage: measurement impossible.
    A failed invocation (`error_kind` set) is exempt — its token columns are
    legitimately NULL."""
    return any(
        row["error_kind"] is None
        and (row["prompt_tokens"] is None or row["completion_tokens"] is None)
        for row in llm_rows
    )


def _remove_run_dir(run_dir: Path) -> None:
    """Tolerant on purpose: losing one run of thirty-six to a cleanup error is a
    worse outcome than a directory left behind in a git-ignored tree."""
    try:
        shutil.rmtree(run_dir)
    except OSError as exc:
        log.warning("could not remove %s: %s", run_dir, config.redact(str(exc)))


# --------------------------------------------------------------------------
# `check` (REQ-V13-BEN-01): schema, field contract, run set, arithmetic
# --------------------------------------------------------------------------

class _Invalid(Exception):
    def __init__(self, reason: str, code: int = EXIT_ERROR) -> None:
        super().__init__(reason)
        self.reason = reason
        self.code = code


def check_document(document: Any, scenarios: Sequence[Scenario] | None = None) -> tuple[int, str]:
    """`(exit code, reason)`. 0 valid; 1 schema / run set / arithmetic;
    2 `meta.aborted`; 3 `usage_missing` or invalid token counts."""
    scenarios = SCENARIOS if scenarios is None else scenarios
    try:
        _validate(document, scenarios)
    except _Invalid as invalid:
        return invalid.code, invalid.reason
    return EXIT_OK, "valid"


def _validate(document: Any, scenarios: Sequence[Scenario]) -> None:
    _need(isinstance(document, dict), "the document is not an object")
    _need(document.get("bench_schema") == BENCH_SCHEMA,
          f"bench_schema must be {BENCH_SCHEMA}")
    meta = document.get("meta")
    runs = document.get("runs")
    summary = document.get("summary")
    _need(isinstance(meta, dict), "meta is missing or not an object")
    _need(isinstance(runs, list), "runs is missing or not an array")
    _need(isinstance(summary, dict), "summary is missing or not an object")
    if "aborted" in meta:
        raise _Invalid(f"aborted run ({meta['aborted']})", EXIT_NOT_COMPARABLE)

    _validate_meta(meta)
    digest = scenarios_sha256()
    _need(meta["scenarios_sha256"] == digest,
          "meta.scenarios_sha256 does not match devtools/bench_scenarios.py")

    for run in runs:
        _validate_run(run)
    _validate_tokens(runs)
    _validate_run_set(meta, runs, summary, scenarios)
    _validate_arithmetic(meta, runs, summary)


def _need(condition: bool, reason: str, code: int = EXIT_ERROR) -> None:
    if not condition:
        raise _Invalid(reason, code)


def _validate_meta(meta: dict) -> None:
    for key in ("tag", "started_at", "finished_at", "git_commit", "provider", "model",
                "scenarios_sha256", "config_sha256"):
        _need(isinstance(meta.get(key), str), f"meta.{key} must be a string")
    for key in ("context_length", "repeats"):
        _need(_is_int(meta.get(key)) and meta[key] > 0, f"meta.{key} must be a positive int")
    _need(_is_number(meta.get("timeout_s")), "meta.timeout_s must be a number")
    _need(meta.get("prefix_tokens") is None or _is_int(meta["prefix_tokens"]),
          "meta.prefix_tokens must be an int or null")
    skipped = meta.get("skipped_scenarios")
    _need(isinstance(skipped, list) and all(isinstance(item, str) for item in skipped),
          "meta.skipped_scenarios must be an array of strings")
    _need("only" in meta, "meta.only is missing")
    only = meta["only"]
    _need(only is None or (isinstance(only, list) and only
                           and all(isinstance(item, str) for item in only)),
          "meta.only must be null or a non-empty array of strings")
    flags = meta.get("env_flags")
    _need(isinstance(flags, dict) and set(flags) == set(ENV_FLAG_KEYS),
          "meta.env_flags must hold exactly the seven documented keys")
    constants_meta = meta.get("constants")
    _need(isinstance(constants_meta, dict), "meta.constants must be an object")
    _need(isinstance(constants_meta.get("REQUEST_DEFAULTS"), dict),
          "meta.constants.REQUEST_DEFAULTS must be an object")
    _validate_pricing(meta.get("pricing"))


def _validate_pricing(price: Any) -> None:
    if price is None:
        return
    _need(isinstance(price, dict), "meta.pricing must be an object or null")
    basis = price.get("basis")
    _need(isinstance(basis, str) and basis, "meta.pricing.basis must be a string")
    for key in ("input_usd_per_mtok", "output_usd_per_mtok"):
        value = price.get(key)
        _need(_is_number(value) and value >= 0, f"meta.pricing.{key} must be a rate >= 0")
    cached = price.get("cached_input_usd_per_mtok")
    _need(cached is None or (_is_number(cached) and cached >= 0),
          "meta.pricing.cached_input_usd_per_mtok must be a rate >= 0 or null")
    if basis == "manual":
        _need(price.get("model") is None, "meta.pricing.model must be null for basis manual")
        _need(price.get("fetched_at") is None,
              "meta.pricing.fetched_at must be null for basis manual")
        return
    _need(isinstance(price.get("model"), str) and price["model"],
          f"meta.pricing.model is required for basis {basis}")
    _need(isinstance(price.get("fetched_at"), str) and price["fetched_at"],
          f"meta.pricing.fetched_at is required for basis {basis}")


def _validate_run(run: Any) -> None:
    _need(isinstance(run, dict), "a runs[] entry is not an object")
    _need(isinstance(run.get("scenario"), str), "runs[].scenario must be a string")
    _need(_is_int(run.get("repeat")) and run["repeat"] > 0,
          "runs[].repeat must be a positive int")
    _need(isinstance(run.get("success"), bool), "runs[].success must be a boolean")
    failure = run.get("failure")
    _need(failure is None or failure in FAILURES,
          f"runs[].failure must be null or one of {', '.join(FAILURES)}")
    _need(run["success"] == (failure is None),
          "runs[].success must be true exactly when failure is null")
    checks = run.get("checks")
    _need(isinstance(checks, list) and checks, "runs[].checks must be a non-empty array")
    for check in checks:
        _need(isinstance(check, dict) and isinstance(check.get("kind"), str)
              and isinstance(check.get("ok"), bool) and isinstance(check.get("detail"), str)
              and len(check["detail"]) <= 120,
              "runs[].checks[] must be {kind, ok, detail<=120}")
    _need(isinstance(run.get("answers"), list)
          and all(isinstance(item, str) for item in run["answers"]),
          "runs[].answers must be an array of strings")
    _need(not run["success"] or all(check["ok"] for check in checks),
          "a successful run cannot carry a failing check")

    for name, keys in (("llm_calls", LLM_ROW_KEYS), ("tool_calls", TOOL_ROW_KEYS)):
        rows = run.get(name)
        _need(isinstance(rows, list), f"runs[].{name} must be an array")
        for row in rows:
            _need(isinstance(row, dict) and set(row) == set(keys),
                  f"runs[].{name}[] must carry exactly the row columns plus conv_seq")
            _need(_is_int(row.get("conv_seq")) and row["conv_seq"] >= 1,
                  f"runs[].{name}[].conv_seq must be a positive int")
    for row in run["llm_calls"]:
        _need(isinstance(row.get("prompt_chars_by_role"), (str, dict)),
              "llm_calls[].prompt_chars_by_role must be the stored JSON text")
        _need(isinstance(_by_role(row), dict),
              "llm_calls[].prompt_chars_by_role must decode to an object")
        _need(row.get("purpose") in ("agent", "summary"),
              "llm_calls[].purpose must be 'agent' or 'summary'")
        _need(_is_int(row.get("latency_ms")), "llm_calls[].latency_ms must be an int")
        _need(row.get("cost_usd") is None or _is_number(row["cost_usd"]),
              "llm_calls[].cost_usd must be a number or null")
    for row in run["tool_calls"]:
        _need(isinstance(row.get("tool"), str), "tool_calls[].tool must be a string")
        _need(_is_int(row.get("output_tokens_est")),
              "tool_calls[].output_tokens_est must be an int")

    totals = run.get("totals")
    _need(isinstance(totals, dict) and set(totals) == set(TOTALS_KEYS),
          "runs[].totals must carry exactly the documented keys")
    _need(_is_int(totals["wall_ms"]) and totals["wall_ms"] >= 0,
          "runs[].totals.wall_ms must be a non-negative int")


def _by_role(row: dict) -> Any:
    value = row["prompt_chars_by_role"]
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def _validate_tokens(runs: Sequence[dict]) -> None:
    """Exit 3: a token count that cannot be summed honestly (section 13.3)."""
    for run in runs:
        for row in run["llm_calls"]:
            for column in ("prompt_tokens", "completion_tokens", "cached_tokens",
                           "reasoning_tokens", "total_tokens"):
                value = row.get(column)
                if value is None:
                    continue
                _need(_is_int(value) and value >= 0,
                      f"{run['scenario']}-{run['repeat']}: negative {column}",
                      EXIT_USAGE_MISSING)
            prompt, cached = row.get("prompt_tokens"), row.get("cached_tokens")
            if prompt is not None and cached is not None:
                _need(cached <= prompt,
                      f"{run['scenario']}-{run['repeat']}: cached_tokens > prompt_tokens",
                      EXIT_USAGE_MISSING)
        if run["success"] and _usage_missing(run["llm_calls"]):
            raise _Invalid(
                f"{run['scenario']}-{run['repeat']}: usage_missing on a successful run",
                EXIT_USAGE_MISSING,
            )


def _validate_run_set(
    meta: dict, runs: Sequence[dict], summary: dict, scenarios: Sequence[Scenario]
) -> None:
    catalog = {scenario.id: scenario for scenario in scenarios}
    network_ids = {scenario.id for scenario in scenarios if scenario.network}
    only = meta["only"]
    # A narrowed run (`--only`) is validated against its own selection; a full
    # run against the whole catalog, exactly as REQ-V13-BEN-01 states. Either
    # way a dropped, duplicated or unknown scenario is exit 1.
    _need(only is None or set(only) <= set(catalog),
          "meta.only names an id that is not in the scenario catalog")
    known = catalog if only is None else {
        scenario_id: catalog[scenario_id] for scenario_id in only
    }
    skipped = set(meta["skipped_scenarios"])
    _need(skipped <= network_ids,
          "meta.skipped_scenarios holds an id that is not a network scenario")
    expected = {
        (scenario_id, repeat)
        for scenario_id in known
        if scenario_id not in skipped
        for repeat in range(1, meta["repeats"] + 1)
    }
    seen: set[tuple[str, int]] = set()
    for run in runs:
        pair = (run["scenario"], run["repeat"])
        _need(run["scenario"] in catalog, f"unknown scenario id: {run['scenario']}")
        _need(run["scenario"] in known,
              f"unexpected run outside meta.only: {run['scenario']}")
        _need(pair not in seen, f"duplicate run: {pair[0]}-{pair[1]}")
        seen.add(pair)
    missing = sorted(expected - seen)
    _need(not missing, f"missing run(s): {', '.join(f'{a}-{b}' for a, b in missing[:5])}")
    extra = sorted(seen - expected)
    _need(not extra, f"unexpected run(s): {', '.join(f'{a}-{b}' for a, b in extra[:5])}")

    per_scenario = summary.get("per_scenario")
    _need(isinstance(per_scenario, dict), "summary.per_scenario must be an object")
    _need(set(per_scenario) == {scenario_id for scenario_id, _ in expected},
          "summary.per_scenario must hold exactly the non-skipped scenario ids")


def _validate_arithmetic(meta: dict, runs: Sequence[dict], summary: dict) -> None:
    """Every stored aggregate against a recomputation from the embedded rows.

    The stored values are compared, never consumed: a `summary` copied from a
    tampered file, or totals a buggy writer produced, cannot pass.
    """
    for run in runs:
        expected = totals_from_rows(run["llm_calls"], run["tool_calls"],
                                    run["totals"]["wall_ms"])
        for key in TOTALS_KEYS:
            _need(_equal(run["totals"][key], expected[key]),
                  f"{run['scenario']}-{run['repeat']}: totals.{key} is "
                  f"{run['totals'][key]!r}, recomputed {expected[key]!r}")
    expected_summary = summarize(runs, meta["skipped_scenarios"], meta["repeats"])
    _compare_summary(summary, expected_summary, "summary")


def _compare_summary(actual: Any, expected: Any, path: str) -> None:
    if isinstance(expected, dict):
        _need(isinstance(actual, dict) and set(actual) == set(expected),
              f"{path} does not hold the documented keys")
        for key, value in expected.items():
            _compare_summary(actual[key], value, f"{path}.{key}")
        return
    if isinstance(expected, list):
        _need(isinstance(actual, list) and len(actual) == len(expected),
              f"{path} has {len(actual) if isinstance(actual, list) else '?'} entries, "
              f"recomputed {len(expected)}")
        for index, value in enumerate(expected):
            _compare_summary(actual[index], value, f"{path}[{index}]")
        return
    _need(_equal(actual, expected), f"{path} is {actual!r}, recomputed {expected!r}")


def _equal(actual: Any, expected: Any) -> bool:
    if actual is None or expected is None:
        return actual is expected
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual is expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(actual, expected, rel_tol=FLOAT_REL_TOL, abs_tol=FLOAT_ABS_TOL)
    return actual == expected


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# --------------------------------------------------------------------------
# `report` (section 7.8) and the verdict (section 13.3)
# --------------------------------------------------------------------------

def comparability(baseline: dict, candidate: dict) -> str | None:
    """The one-line reason two files may not be compared, or `None`."""
    for field_name in LOCKED_META_FIELDS:
        if baseline["meta"].get(field_name) != candidate["meta"].get(field_name):
            return f"locked meta field differs: {field_name}"
    base_flags = baseline["meta"]["env_flags"]
    cand_flags = candidate["meta"]["env_flags"]
    for side, flags in (("baseline", base_flags), ("candidate", cand_flags)):
        if flags.get("LLM_FAILOVER") != "off":
            return f"env_flags.LLM_FAILOVER is not 'off' on the {side} side"
        if flags.get("LLM_SUMMARY_MODEL") != "":
            return f"env_flags.LLM_SUMMARY_MODEL is not empty on the {side} side"
    if base_flags.get("LLM_MAX_TOKENS") != cand_flags.get("LLM_MAX_TOKENS"):
        return "env_flags.LLM_MAX_TOKENS differs"
    for key in STAGE_C_KEYS:
        if base_flags.get(key) is not None:
            return f"env_flags.{key} must be null on the baseline side"
        value = cand_flags.get(key)
        if key == "LLM_REASONING":
            # REQ-V13-RSN-02: the variable exists only in the `implemented` state.
            if value not in (STAGE_C_DEFAULTS[key], None):
                return f"env_flags.{key} must be 'auto' or null on the candidate side"
        elif value != STAGE_C_DEFAULTS[key]:
            return f"env_flags.{key} must be its default on the candidate side"
    return None


@dataclass
class Verdict:
    passed: bool
    reason: str
    lines: list[str]


def _price_from_meta(meta_pricing: dict | None):
    if not meta_pricing:
        return None
    return pricing.Price(
        input_usd_per_mtok=float(meta_pricing["input_usd_per_mtok"]),
        output_usd_per_mtok=float(meta_pricing["output_usd_per_mtok"]),
        cached_input_usd_per_mtok=(
            None if meta_pricing.get("cached_input_usd_per_mtok") is None
            else float(meta_pricing["cached_input_usd_per_mtok"])
        ),
        source=str(meta_pricing.get("basis") or ""),
        fetched_at=str(meta_pricing.get("fetched_at") or ""),
    )


def _recomputed_total(document: dict, price) -> float:
    """Both sides priced with the **baseline's** snapshot, from the token
    columns: a list-price change between the two runs can neither create nor
    hide a saving. With no snapshot the metric is tokens, not dollars."""
    total = 0.0
    for run in document["runs"]:
        for row in run["llm_calls"]:
            if price is None:
                total += (row["prompt_tokens"] or 0) + (row["completion_tokens"] or 0)
                continue
            usage = llm_base.Usage(
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                cached_tokens=row["cached_tokens"],
            )
            total += pricing.cost_usd(usage, price) or 0.0
    return total


def verdict(baseline: dict, candidate: dict) -> Verdict:
    price = _price_from_meta(baseline["meta"].get("pricing"))
    unit = "$" if price is not None else " tokens"
    metric = "cost per successful task" if price is not None else "tokens per successful task"

    successes_b = baseline["summary"]["successes"]
    successes_c = candidate["summary"]["successes"]
    failed_b = baseline["summary"]["totals"]["failed_calls"]
    failed_c = candidate["summary"]["totals"]["failed_calls"]
    total_b = _recomputed_total(baseline, price)
    total_c = _recomputed_total(candidate, price)

    lines = [f"metric: {metric}"]
    if price is not None:
        lines.append(
            f"price snapshot (baseline): {baseline['meta']['pricing'].get('model')} "
            f"as of {baseline['meta']['pricing'].get('fetched_at')}"
        )
    else:
        lines.append("price snapshot (baseline): none — token-based comparison")

    if not successes_b or not successes_c:
        lines.append(f"failed_calls: baseline {failed_b}, candidate {failed_c}")
        lines.append("verdict: **FAIL** — no successful runs")
        return Verdict(False, "no successful runs", lines)

    ok_calls_c = candidate["summary"]["totals"]["calls"] - failed_c
    mean_ok_c = (total_c / ok_calls_c) if ok_calls_c else 0.0
    b_plain = total_b / successes_b
    c_plain = total_c / successes_c
    c_conservative = (total_c + failed_c * mean_ok_c) / successes_c
    threshold = COST_GATE_FACTOR * b_plain

    lines += [
        f"B_plain: {_money(b_plain, unit)} (failed_B {failed_b})",
        f"C_plain: {_money(c_plain, unit)} (failed_C {failed_c})",
        f"C_conservative: {_money(c_conservative, unit)}",
        f"gate threshold (0.70 x B_plain): {_money(threshold, unit)}",
    ]
    if failed_c > failed_b:
        lines.append(
            f"warning: failed_calls rose {failed_b} → {failed_c} — "
            "the cost of failed invocations is unmeasured"
        )
    cost_ok = c_plain <= threshold and c_conservative <= threshold

    rate_b = baseline["summary"]["success_rate"]
    rate_c = candidate["summary"]["success_rate"]
    delta_pp = (rate_c - rate_b) * 100
    quality_ok = rate_c >= rate_b - QUALITY_GATE_SLACK
    lines.append(
        f"success rate: {rate_b:.4f} → {rate_c:.4f} ({delta_pp:+.1f} pp; the "
        f"assignment's headline is 2 pp, but at {candidate['summary']['runs']} runs one "
        "flipped run is already 2.8–3.0 pp, so the candidate may lose no run net)"
    )
    regressed = []
    for scenario_id, entry in baseline["summary"]["per_scenario"].items():
        after = candidate["summary"]["per_scenario"].get(scenario_id, {"success": 0, "of": 0})
        if after["success"] < entry["success"] - 1:
            regressed.append(f"{scenario_id} {entry['success']}/{entry['of']} → "
                             f"{after['success']}/{after['of']}")
    if regressed:
        lines.append("regressed scenarios: " + ", ".join(regressed))
        quality_ok = False

    passed = cost_ok and quality_ok
    reason = "pass" if passed else _fail_reason(cost_ok, quality_ok)
    lines.append(f"cost gate: {'pass' if cost_ok else 'FAIL'}")
    lines.append(f"quality gate: {'pass' if quality_ok else 'FAIL'}")
    lines.append(f"verdict: **{'PASS' if passed else 'FAIL'}**")
    return Verdict(passed, reason, lines)


def _fail_reason(cost_ok: bool, quality_ok: bool) -> str:
    if not cost_ok and not quality_ok:
        return "cost and quality gates failed"
    return "cost gate failed" if not cost_ok else "quality gate failed"


def _money(value: float, unit: str) -> str:
    return f"${value:.6f}" if unit == "$" else f"{value:.1f} tokens"


def render_report(baseline: dict, candidate: dict | None = None) -> str:
    parts = [
        _meta_section(baseline, candidate),
        _per_scenario_section(baseline, candidate),
        _totals_section(baseline, candidate),
        _purpose_section(baseline, candidate),
        _audit_section(baseline, candidate),
        _reasoning_section(baseline, candidate),
        _latency_section(baseline, candidate),
        _failures_section(baseline, candidate),
    ]
    if candidate is not None:
        parts.append("## Verdict\n\n" + "\n".join(
            f"- {line}" for line in verdict(baseline, candidate).lines
        ) + "\n")
    tag = baseline["meta"]["tag"]
    header = f"# Benchmark report — {tag}"
    if candidate is not None:
        header += f" vs {candidate['meta']['tag']}"
    return header + "\n\n" + "\n".join(parts)


def _sides(baseline: dict, candidate: dict | None) -> list[tuple[str, dict]]:
    sides = [("baseline", baseline)]
    if candidate is not None:
        sides.append(("candidate", candidate))
    return sides


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(cell for cell in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def _meta_section(baseline: dict, candidate: dict | None) -> str:
    sides = _sides(baseline, candidate)
    header = ["field", *(name for name, _ in sides)]
    rows = []
    for key in ("tag", "started_at", "finished_at", "git_commit", *LOCKED_META_FIELDS,
                "prefix_tokens"):
        rows.append([key, *(_cell(document["meta"].get(key)) for _, document in sides)])
    for key in ENV_FLAG_KEYS:
        rows.append([f"env_flags.{key}",
                     *(_cell(document["meta"]["env_flags"].get(key)) for _, document in sides)])
    for key in ("basis", "model", "input_usd_per_mtok", "output_usd_per_mtok",
                "cached_input_usd_per_mtok", "fetched_at"):
        rows.append([f"pricing.{key}",
                     *(_cell((document["meta"].get("pricing") or {}).get(key))
                       for _, document in sides)])
    return "## Meta\n\n" + _table(header, rows)


_MEDIAN_KEYS = ("prompt_tokens", "completion_tokens", "cached_tokens", "reasoning_tokens",
                "resent_tokens", "new_tokens", "tool_calls", "tool_output_tokens_est",
                "latency_ms", "wall_ms", "cost_usd", "calls", "failed_calls")


def _per_scenario_section(baseline: dict, candidate: dict | None) -> str:
    header = ["scenario", "file", "success", *_MEDIAN_KEYS]
    rows = []
    for scenario_id in sorted(baseline["summary"]["per_scenario"]):
        for name, document in _sides(baseline, candidate):
            entry = document["summary"]["per_scenario"].get(scenario_id)
            if entry is None:
                rows.append([scenario_id, name, "—", *("—" for _ in _MEDIAN_KEYS)])
                continue
            rows.append([
                scenario_id, name, f"{entry['success']}/{entry['of']}",
                *(_cell(entry["median"][key]) for key in _MEDIAN_KEYS),
            ])
        if candidate is not None:
            base = baseline["summary"]["per_scenario"][scenario_id]["median"]
            cand = (candidate["summary"]["per_scenario"].get(scenario_id) or {}).get("median", {})
            rows.append([scenario_id, "Δ", "",
                         *(_delta(base.get(key), cand.get(key)) for key in _MEDIAN_KEYS)])
    return "## Per scenario\n\n" + _table(header, rows)


def _totals_section(baseline: dict, candidate: dict | None) -> str:
    header = ["metric", *(name for name, _ in _sides(baseline, candidate))]
    if candidate is not None:
        header += ["Δ", "Δ%"]
    rows = []
    for key in TOTALS_KEYS:
        rows.append(_metric_row(key, baseline, candidate,
                                lambda document, key=key: document["summary"]["totals"][key]))
    for key in ("success_rate", "cost_per_success", "tokens_per_success", "resent_share",
                "cache_hit_rate"):
        rows.append(_metric_row(key, baseline, candidate,
                                lambda document, key=key: document["summary"][key]))
    for key in AVG_KEYS:
        rows.append(_metric_row(f"avg_per_task.{key}", baseline, candidate,
                                lambda document, key=key: document["summary"]["avg_per_task"][key]))
    rows.append(_metric_row("prefix_share", baseline, candidate, metrics.prefix_share))
    return "## Totals\n\n" + _table(header, rows)


def _metric_row(label: str, baseline: dict, candidate: dict | None, pick) -> list[str]:
    left = pick(baseline)
    row = [label, _cell(left)]
    if candidate is None:
        return row
    right = pick(candidate)
    return [*row, _cell(right), _abs_delta(left, right), _rel_delta(left, right)]


def _purpose_section(baseline: dict, candidate: dict | None) -> str:
    header = ["purpose", "metric", *(name for name, _ in _sides(baseline, candidate))]
    rows = []
    for purpose in ("agent", "summary"):
        for metric in ("calls", "prompt_tokens", "completion_tokens"):
            rows.append([purpose, metric, *(
                _cell(_purpose_value(document, purpose, metric))
                for _, document in _sides(baseline, candidate)
            )])
    return "## Totals by purpose\n\n" + _table(header, rows)


def _purpose_value(document: dict, purpose: str, metric: str) -> int:
    rows = [row for row in _all_llm_rows(document) if row["purpose"] == purpose]
    if metric == "calls":
        return len(rows)
    return sum(int(row[metric] or 0) for row in rows)


def _all_llm_rows(document: dict) -> list[dict]:
    return [row for run in document["runs"] for row in run["llm_calls"]]


def _audit_section(baseline: dict, candidate: dict | None) -> str:
    header = ["question", *(name for name, _ in _sides(baseline, candidate))]
    rows = [
        ["most expensive tool (output tokens)",
         *(_top_tool_cell(document) for _, document in _sides(baseline, candidate))],
        ["most expensive turn/round",
         *(_top_turn_cell(document) for _, document in _sides(baseline, candidate))],
        ["fastest-growing context category",
         *(_growth_cell(document) for _, document in _sides(baseline, candidate))],
        ["re-sent share",
         *(_cell(document["summary"]["resent_share"])
           for _, document in _sides(baseline, candidate))],
    ]
    return "## Audit\n\n" + _table(header, rows)


def _top_tool_cell(document: dict) -> str:
    top = document["summary"]["top_tools"]
    if not top:
        return "none"
    return f"{top[0]['name']} ({top[0]['output_tokens_est']} tokens, {top[0]['calls']} calls)"


def _top_turn_cell(document: dict) -> str:
    turn = document["summary"]["top_turn"]
    if turn is None:
        return "none"
    return (f"{turn['scenario']}-{turn['repeat']} turn {turn['turn']} round {turn['round']}: "
            f"{turn['prompt_tokens']} prompt tokens")


def _growth_cell(document: dict) -> str:
    growth = document["summary"]["context_growth"]
    if not growth:
        return "none"
    role = max(growth, key=lambda key: growth[key])
    return f"{role} (+{growth[role]:.1f} chars/run)"


def _reasoning_section(baseline: dict, candidate: dict | None) -> str:
    body = ["## Reasoning\n"]
    for name, document in _sides(baseline, candidate):
        rows = _all_llm_rows(document)
        body.append(f"### {name}\n")
        body.append("- " + _reasoning_line(rows))
        # `tools_exposed` is the size of the toolset the request carried (it
        # parallels `messages_n`), so a normal agent round holds the whole
        # catalog, not 1 — the group is "any tool at all" (REQ-V13-RSN-02).
        body.append("- tool-exposed calls: "
                    + _reasoning_line([row for row in rows
                                       if (row["tools_exposed"] or 0) > 0],
                                      with_calls=True))
        body.append("- tools-withheld calls: "
                    + _reasoning_line([row for row in rows
                                       if not row["tools_exposed"]],
                                      with_calls=True))
        body.append("")
    return "\n".join(body) + "\n"


def _reasoning_line(rows: Sequence[dict], *, with_calls: bool = False) -> str:
    tokens = [int(row["reasoning_tokens"] or 0) for row in rows]
    chars = [int(row["reasoning_chars"] or 0) for row in rows]
    observed = any(tokens) or any(chars)
    total_reasoning = sum(tokens)
    total_completion = sum(int(row["completion_tokens"] or 0) for row in rows)
    # Section 7.8: `chars only` is the branch for a provider that reports no
    # `reasoning_tokens` at all. One that honestly reports zero has a share.
    if any(row["reasoning_tokens"] is not None for row in rows):
        share = f"{total_reasoning / total_completion:.4f}" if total_completion else "n/a"
    elif any(chars):
        share = f"n/a (chars only: {sum(chars)})"
    else:
        share = "n/a"
    parts = []
    if with_calls:
        parts.append(f"calls: {sum(1 for row in rows if row['error_kind'] is None)}")
    parts += [
        f"reasoning observed: {'yes' if observed else 'no'}",
        f"max reasoning_tokens: {max(tokens) if tokens else 0}",
        f"max reasoning_chars: {max(chars) if chars else 0}",
        f"Σ reasoning_tokens: {total_reasoning}",
        f"reasoning share: {share}",
    ]
    return ", ".join(parts)


def _latency_section(baseline: dict, candidate: dict | None) -> str:
    header = ["scope", *(name for name, _ in _sides(baseline, candidate))]
    sides = _sides(baseline, candidate)
    rows = [["median latency_ms per call",
             *(_cell(_median_latency(document, None)) for _, document in sides)]]
    for purpose in ("agent", "summary"):
        rows.append([f"median latency_ms ({purpose})",
                     *(_cell(_median_latency(document, purpose))
                       for _, document in _sides(baseline, candidate))])
    return "## Latency\n\n" + _table(header, rows)


def _median_latency(document: dict, purpose: str | None) -> float | None:
    values = [int(row["latency_ms"] or 0) for row in _all_llm_rows(document)
              if purpose is None or row["purpose"] == purpose]
    return statistics.median(values) if values else None


def _failures_section(baseline: dict, candidate: dict | None) -> str:
    body = ["## Failures\n"]
    for name, document in _sides(baseline, candidate):
        body.append(f"### {name}\n")
        failed = [run for run in document["runs"] if not run["success"]]
        if not failed:
            body.append("none\n")
            continue
        rows = []
        for run in failed:
            failing = "; ".join(
                f"{check['kind']}: {check['detail']}"
                for check in run["checks"] if not check["ok"]
            ) or "—"
            answers = " ⏎ ".join(run["answers"])[:300]
            rows.append([run["scenario"], str(run["repeat"]), str(run["failure"]),
                         failing, answers.replace("|", "\\|")])
        body.append(_table(["scenario", "repeat", "failure", "checks", "answers"], rows))
    return "\n".join(body) + "\n"


def _cell(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".") if abs(value) < 1000 else f"{value:.1f}"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True).replace("|", "\\|")
    return str(value).replace("|", "\\|")


def _abs_delta(left: Any, right: Any) -> str:
    if not _is_number(left) or not _is_number(right):
        return "n/a"
    return _cell(right - left)


def _rel_delta(left: Any, right: Any) -> str:
    if not _is_number(left) or not _is_number(right) or not left:
        return "n/a"
    return f"{(right - left) / left * 100:+.1f}%"


def _delta(left: Any, right: Any) -> str:
    if not _is_number(left) or not _is_number(right):
        return "n/a"
    return f"{_cell(right - left)} ({_rel_delta(left, right)})"


# --------------------------------------------------------------------------
# the console summary (section 7.7)
# --------------------------------------------------------------------------

def console_summary(document: dict, out_path: Path) -> list[str]:
    meta = document["meta"]
    summary = document["summary"]
    price = meta.get("pricing") or {}
    lines = [
        f"bench {meta['tag']}  provider={meta['provider']}  model={meta['model']}  "
        f"repeats={meta['repeats']}  prefix_tokens={meta.get('prefix_tokens')}  "
        f"pricing={price.get('basis', 'none')}"
    ]
    for scenario_id in sorted(summary["per_scenario"]):
        entry = summary["per_scenario"][scenario_id]
        median = entry["median"]
        lines.append(
            f"{scenario_id} {_title(scenario_id):<14} {entry['success']}/{entry['of']}  "
            f"prompt {_k(median['prompt_tokens'])}  out {_k(median['completion_tokens'])}  "
            f"cost {_usd(median['cost_usd'])}  wall {_secs(median['wall_ms'])}"
        )
    totals = summary["totals"]
    lines += [
        f"totals: calls {totals['calls']} (failed {totals['failed_calls']})  "
        f"prompt {_k(totals['prompt_tokens'])}  completion {_k(totals['completion_tokens'])}  "
        f"tools {totals['tool_calls']}  cost {_usd(totals['cost_usd'])}  "
        f"wall {_secs(totals['wall_ms'])}",
        f"success rate: {summary['successes']}/{summary['runs']} "
        f"({summary['success_rate'] * 100:.1f}%)",
        f"cost/success {_usd(summary['cost_per_success'])}  "
        f"tokens/success {_num(summary['tokens_per_success'])}  "
        f"re-sent share {summary['resent_share'] * 100:.1f}%  "
        f"cache hit {_pct(summary['cache_hit_rate'])}",
        f"skipped: {', '.join(meta['skipped_scenarios']) or 'none'}",
    ]
    if meta.get("aborted"):
        lines.append(f"ABORTED: {meta['aborted']}")
    lines.append(f"output: {out_path}")
    return lines[:SUMMARY_LINE_LIMIT]


def _title(scenario_id: str) -> str:
    for scenario in SCENARIOS:
        if scenario.id == scenario_id:
            return scenario.title
    return ""


def _k(value: float | None) -> str:
    return "n/a" if value is None else f"{value / 1000:.1f}k"


def _usd(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.4f}"


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _secs(value: float | None) -> str:
    return "n/a" if value is None else f"{value / 1000:.0f}s"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bench.py", description="the spec-v1.3 benchmark harness"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="execute the scenarios and write a benchmark file")
    run.add_argument("--tag", required=True)
    run.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    run.add_argument("--only", default="")
    run.add_argument("--provider", choices=config.PROVIDERS)
    run.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    run.add_argument("--max-cost-usd", type=float)
    run.add_argument("--out")

    report = sub.add_parser("report", help="render the markdown report")
    report.add_argument("--baseline", required=True)
    report.add_argument("--candidate")
    report.add_argument("--out")
    report.add_argument("--gate", action="store_true")

    check = sub.add_parser("check", help="validate a benchmark file")
    check.add_argument("path")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "run":
        return _cmd_run(arguments)
    if arguments.command == "report":
        return _cmd_report(arguments)
    return _cmd_check(arguments)


def _cmd_check(arguments) -> int:
    document, error = _load(Path(arguments.path))
    if error is not None:
        print(error, file=sys.stderr)
        return EXIT_ERROR
    code, reason = check_document(document)
    print(f"{arguments.path}: {reason}")
    return code


def _cmd_report(arguments) -> int:
    baseline, error = _load(Path(arguments.baseline))
    if error is not None:
        print(error, file=sys.stderr)
        return EXIT_ERROR
    candidate = None
    if arguments.candidate:
        candidate, error = _load(Path(arguments.candidate))
        if error is not None:
            print(error, file=sys.stderr)
            return EXIT_ERROR

    for label, document in (("baseline", baseline), ("candidate", candidate)):
        if document is None:
            continue
        code, reason = check_document(document)
        if code != EXIT_OK:
            print(f"{label}: {reason}", file=sys.stderr)
            return code

    if arguments.gate and candidate is None:
        print("--gate needs both --baseline and --candidate", file=sys.stderr)
        return EXIT_NOT_COMPARABLE
    if candidate is not None:
        reason = comparability(baseline, candidate)
        if reason is not None:
            print(f"not comparable: {reason}", file=sys.stderr)
            return EXIT_NOT_COMPARABLE

    text = render_report(baseline, candidate)
    if arguments.out:
        out_path = Path(arguments.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"report written to {out_path}")
    else:
        print(text)
    if arguments.gate:
        decision = verdict(baseline, candidate)
        print(f"verdict: {'PASS' if decision.passed else 'FAIL'} ({decision.reason})")
        return EXIT_OK if decision.passed else EXIT_ERROR
    return EXIT_OK


def _load(path: Path) -> tuple[dict | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except OSError as exc:
        return None, f"{path}: cannot be read ({exc.__class__.__name__})"
    except ValueError:
        return None, f"{path}: is not valid json"


def _selected(only: str) -> list[Scenario]:
    if not only.strip():
        return list(SCENARIOS)
    wanted = [item.strip() for item in only.split(",") if item.strip()]
    known = {scenario.id: scenario for scenario in SCENARIOS}
    unknown = [item for item in wanted if item not in known]
    if unknown:
        raise SystemExit(f"unknown scenario id(s): {', '.join(unknown)}")
    return [known[item] for item in wanted]


def _harness_env(provider: str | None) -> dict:
    """The treatment the harness pins, so a maintainer's `.env` cannot alter
    what is measured (REQ-V13-BEN-03). Only variables whose `Config` field
    exists at this commit are set — one that does not is neither set nor read.
    """
    present = {item.name for item in dataclasses.fields(Config)}
    pinned = {"LLM_FAILOVER": "off", "LLM_SUMMARY_MODEL": ""}
    for key, value in STAGE_C_DEFAULTS.items():
        if ENV_FLAG_FIELDS[key] in present:
            pinned[key] = str(value)
    if provider:
        pinned["LLM_PROVIDER"] = provider
    return pinned


def _base_config(tag: str, provider: str | None) -> Config:
    """`.env` for the provider, model, URLs, keys, ids and timeouts; the harness
    for the treatment and the three per-run paths."""
    config.load_config()                      # loads `.env` into the environment once
    base_dir = BENCH_ROOT / tag / "_base"
    env = {
        **os.environ,
        **_harness_env(provider),
        "EXEC_WORKDIR": str(base_dir / "sandbox"),
        "DB_PATH": str(base_dir / "bot.db"),
        "AUDIT_LOG_PATH": str(base_dir / "audit.jsonl"),
    }
    return config.load_config(env=env, load_env_file=False)


def _configure_logging(log_path: Path) -> None:
    """REQ-V13-BEN-13: the per-call INFO records go to a file next to the JSON,
    never to the console — the console budget is 40 lines in total."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _network_preflight(client: httpx.Client) -> Callable[[], bool]:
    def probe() -> bool:
        try:
            client.head(NETWORK_PROBE_URL, timeout=NETWORK_PROBE_TIMEOUT_S)
        except httpx.HTTPError:
            return False
        return True
    return probe


def _real_runner_factory(cfg: Config):
    """What `bot.main()` builds, per run: the docker probe, the one startup
    seam and the exec runner bound to that run's sandbox."""
    _version, docker_ok = bot.exec_backend_status()
    wrap_timeout, empty_resolv = bot._startup_docker_wiring(cfg, docker_ok)
    return functools.partial(
        tools.run_command_docker,
        workdir=cfg.exec_workdir,
        image=cfg.exec_docker_image,
        docker_ok=docker_ok,
        sandbox_max_bytes=cfg.exec_sandbox_max_bytes,
        wrap_timeout=wrap_timeout,
        empty_resolv=empty_resolv,
    )


def _real_fetcher_factory(client: httpx.Client) -> Callable[[Config], Any]:
    """`bot.main()`'s fetch partial plus the per-run sandbox arguments of
    REQ-V13-TOO-06 — passed only once `tools.fetch_url` accepts them, so the
    same factory works before and after stage C."""
    import inspect

    accepted = set(inspect.signature(tools.fetch_url).parameters)

    def build(cfg: Config):
        extra = {}
        if "workdir" in accepted:
            extra["workdir"] = cfg.exec_workdir
        if "sandbox_max_bytes" in accepted:
            extra["sandbox_max_bytes"] = cfg.exec_sandbox_max_bytes
        return functools.partial(
            tools.fetch_url,
            allowed_domains=cfg.fetch_allowed_domains,
            client=client,
            resolve=tools.resolve_host,
            **extra,
        )
    return build


def _prefix_tokens(client, skills: dict) -> int | None:
    """REQ-V13-BEN-06: one `max_tokens=1` call with the system prompt and the
    tool catalog, made outside `run_agent` so it writes no `llm_calls` row."""
    messages = [
        {"role": "system",
         "content": agent.build_system_prompt(skills, storage.utc_now_iso())},
        {"role": "user", "content": PREFIX_PROBE_MESSAGE},
    ]
    try:
        response = client.complete(messages, tools.tool_specs(), max_tokens=1)
    except Exception as exc:
        log.warning("prefix calibration failed: %s", config.redact(str(exc)))
        return None
    usage = getattr(response, "usage", None)
    return None if usage is None else usage.prompt_tokens


def _pricing_meta(snapshot: dict, basis: str | None, model: str, fetched_at: str) -> dict | None:
    price = snapshot.get(model) if model else None
    if price is None:
        return None
    return {
        "basis": basis or pricing.BASIS_LIST,
        "model": model,
        "input_usd_per_mtok": price.input_usd_per_mtok,
        "output_usd_per_mtok": price.output_usd_per_mtok,
        "cached_input_usd_per_mtok": price.cached_input_usd_per_mtok,
        "fetched_at": fetched_at,
    }


def _resolve_pricing(cfg: Config, client: httpx.Client) -> tuple[Any, dict | None]:
    """The snapshot and the resolver, built **once per CLI invocation**
    (REQ-V13-PRC-02); every run then prices its calls through the same one."""
    fetched_at = storage.utc_now_iso()
    snapshot: dict = {}
    try:
        snapshot = pricing.fetch_openrouter_prices(
            client, (cfg.openrouter_model, cfg.llm_price_ref_model), now=fetched_at
        )
    except pricing.PricingError as exc:
        log.warning("fetching OpenRouter prices failed: %s", config.redact(str(exc)))

    if cfg.llm_provider == "openrouter":
        model, basis = cfg.openrouter_model, pricing.BASIS_LIST
    else:
        model = cfg.llm_price_ref_model
        basis = f"{pricing.REFERENCE_PREFIX}{model}" if model else None
    meta_pricing = _pricing_meta(snapshot, basis, model, fetched_at)
    if meta_pricing is None and cfg.llm_price_input_usd_per_mtok is not None:
        meta_pricing = {
            "basis": pricing.BASIS_MANUAL,
            "model": None,
            "input_usd_per_mtok": cfg.llm_price_input_usd_per_mtok,
            "output_usd_per_mtok": cfg.llm_price_output_usd_per_mtok,
            "cached_input_usd_per_mtok": None,
            "fetched_at": None,
        }
    resolver = pricing.make_resolver(cfg, snapshot, snapshot_basis=basis, stale=None)
    return resolver, meta_pricing


def _git_commit() -> str:
    head = REPO_ROOT / ".git" / "HEAD"
    try:
        text = head.read_text(encoding="utf-8").strip()
        if text.startswith("ref: "):
            ref = REPO_ROOT / ".git" / text[5:]
            return ref.read_text(encoding="utf-8").strip()
        return text
    except OSError:
        return ""


def _cmd_run(arguments) -> int:
    provider = arguments.provider
    scenarios = _selected(arguments.only)

    if BENCH_ROOT.exists():
        shutil.rmtree(BENCH_ROOT, ignore_errors=True)
    try:
        cfg = _base_config(arguments.tag, provider)
    except config.ConfigError as exc:
        print(f"configuration error: {config.redact(str(exc))}", file=sys.stderr)
        return EXIT_ERROR

    # REQ-V13-BEN-02, keyed on the provider that will actually spend: without
    # `--provider` the harness pins nothing and `.env` decides, so reading the
    # CLI flag alone would let an `LLM_PROVIDER=openrouter` box run uncapped.
    # Refused before the run's own output exists.
    if cfg.llm_provider == "openrouter" and arguments.max_cost_usd is None:
        print("an openrouter run requires --max-cost-usd", file=sys.stderr)
        return EXIT_ERROR

    out_path = Path(arguments.out) if arguments.out else DEFAULT_OUT_DIR / f"{arguments.tag}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _configure_logging(out_path.parent / f"{arguments.tag}.log")

    client = httpx.Client()
    started_at = storage.utc_now_iso()
    try:
        skills = tools.load_skills(REPO_ROOT / "skills")
        resolver, meta_pricing = _resolve_pricing(cfg, client)
        prefix = _prefix_tokens(llm_module.build_llm_client(cfg, client=client), skills)
        result = run_bench(
            scenarios,
            cfg=cfg,
            llm_factory=lambda run_cfg: llm_module.build_llm_client(run_cfg, client=client),
            runner_factory=_real_runner_factory,
            fetcher_factory=_real_fetcher_factory(client),
            telegram_factory=BenchTelegram,
            repeats=arguments.repeats,
            timeout_s=arguments.timeout_s,
            clock=time.monotonic,
            sleep=time.sleep,
            network_preflight=_network_preflight(client),
            skills=skills,
            runs_root=BENCH_ROOT / arguments.tag,
            resolve_cost=resolver,
            max_cost_usd=arguments.max_cost_usd,
        )
    finally:
        client.close()

    result.meta.update({
        "only": sorted(scenario.id for scenario in scenarios) if arguments.only.strip()
        else None,
        "tag": arguments.tag,
        "started_at": started_at,
        "finished_at": storage.utc_now_iso(),
        "git_commit": _git_commit(),
        "prefix_tokens": prefix,
        "pricing": meta_pricing,
    })
    document = _ordered(result)
    document = redact_document(document, sorted(cfg.allowed_tg_ids))
    out_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for line in console_summary(document, out_path):
        print(line)

    if result.aborted is not None:
        bot._reap_orphaned_containers()
        # `os._exit` skips every buffer flush, and under a pipe or a redirect
        # the console summary above — the `ABORTED:` line included — is still
        # sitting in one of them.
        sys.stdout.flush()
        sys.stderr.flush()
        # A daemon thread may be blocked inside a call that cannot be cancelled;
        # `os._exit` is the only way to end the process — and to stop spending.
        os._exit(EXIT_ABORTED)
    if any(run["failure"] == FAIL_USAGE_MISSING for run in result.runs):
        return EXIT_USAGE_MISSING
    if any(run["failure"] == FAIL_HARNESS_ERROR for run in result.runs):
        return EXIT_ERROR
    return EXIT_OK


def _ordered(result: BenchResult) -> dict:
    """`meta` in the order of the 7.4 schema — a benchmark file is read by
    people as well as by `check`."""
    order = ("tag", "started_at", "finished_at", "git_commit", "provider", "model",
             "context_length", "repeats", "only", "timeout_s", "prefix_tokens",
             "scenarios_sha256", "pricing", "skipped_scenarios", "env_flags",
             "config_sha256", "constants", "aborted")
    meta = {key: result.meta[key] for key in order if key in result.meta}
    meta.update({key: value for key, value in result.meta.items() if key not in meta})
    return {
        "bench_schema": BENCH_SCHEMA,
        "meta": meta,
        "runs": result.runs,
        "summary": result.summary,
    }


if __name__ == "__main__":
    sys.exit(main())
