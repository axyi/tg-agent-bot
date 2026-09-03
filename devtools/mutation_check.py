"""The mutation gate (REQ-V12-MUT-01..04).

For each entry in `MUTATIONS`, temporarily replaces one exact, once-occurring
substring in one production file, runs the test suite, and checks that the
suite goes red for the right reason (exit code exactly 1 — pytest's "tests
failed" code). Restoration is unconditional: the original bytes of every
touched file are held in memory and written back in a `finally`, both around
each mutation and around the whole run, and verified byte-for-byte afterwards.

Never imported by production code (REQ-V12-TREE-01). Standard library only —
no third-party mutation framework (REQ-V12-NG-05).
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

KILLED = "killed"
SURVIVED = "survived"
ERRORED = "errored"
DRIFTED = "drifted"

# --------------------------------------------------------------------------
# The mutation catalogue (REQ-V12-MUT-04): at least 28 entries — one per row
# of REQ-V12-TST-02's table (11), one per named security requirement of
# section 5 (11), the four v1.1 guards whose tests already pass (4), and the
# two lines REQ-V12-TST-01 restores plus the SSR-02 backstop (2).
#
# spec-v1.3 section 12 adds its 33 rows: 20 tagged A and the 13 tagged C that
# land with the stage-C code they mutate — 65 in all (corrected: this
# comment previously said 64).
#
# spec-v1.4 adds 2 more, TST-05's STOP-branch minimum (RSN-06/GATE-02
# narrowed the mechanism-found branch's six down to the two defending
# shipped code): BEN-03's row-key rule and REL-01's timeout/budget
# boundary — 67 in all.
# --------------------------------------------------------------------------

MUTATIONS = [
    # -- REQ-V12-TST-02 table (11 rows) -------------------------------------
    {
        "id": "cov-01-live-docker-sandbox-max-bytes",
        "path": "bot.py",
        "find": (
            "docker_ok=True,\n"
            "        sandbox_max_bytes=cfg.exec_sandbox_max_bytes,\n"
            "    )"
        ),
        "replace": (
            "docker_ok=True,\n"
            "        sandbox_max_bytes=config.DEFAULT_EXEC_SANDBOX_MAX_BYTES,\n"
            "    )"
        ),
        "why": "TST-02 #1: _live_docker must pass the configured quota, not the default",
    },
    {
        "id": "cov-02-pre-run-refusal-incomplete",
        "path": "tools.py",
        "find": "    if status == SCAN_INCOMPLETE:\n",
        "replace": "    if False and status == SCAN_INCOMPLETE:\n",
        "why": "TST-02 #2: an unreadable sandbox must be refused, not measured as empty",
    },
    {
        "id": "cov-03-post-run-quota-on-timeout",
        "path": "tools.py",
        "find": (
            "        envelope[\"notice\"] = UNTRUSTED_NOTICE\n"
            "        _record_sandbox_quota(envelope, workdir, sandbox_max_bytes)\n"
            "        return envelope\n\n    exit_code = envelope[\"exit_code\"]"
        ),
        "replace": (
            "        envelope[\"notice\"] = UNTRUSTED_NOTICE\n"
            "        return envelope\n\n    exit_code = envelope[\"exit_code\"]"
        ),
        "why": "TST-02 #3: the timeout branch must still record the post-run quota fact",
    },
    {
        "id": "cov-04-post-run-quota-on-docker-exit",
        "path": "tools.py",
        "find": (
            "        failure = {\"error\": f\"exec failed (docker exit {exit_code}): "
            "{excerpt}\"}\n"
            "        _record_sandbox_quota(failure, workdir, sandbox_max_bytes)\n"
            "        return failure"
        ),
        "replace": (
            "        failure = {\"error\": f\"exec failed (docker exit {exit_code}): "
            "{excerpt}\"}\n"
            "        return failure"
        ),
        "why": "TST-02 #4: the docker-exit 125/126/127 branch must record post-run quota",
    },
    {
        "id": "cov-05-pop-before-envelope",
        "path": "tools.py",
        "find": (
            "    record[\"sandbox_over_quota\"] = payload.pop(\"sandbox_over_quota\", False)\n"
            "    record[\"sandbox_scan\"] = payload.pop(\"sandbox_scan\", SCAN_OK)\n"
        ),
        "replace": (
            "    record[\"sandbox_over_quota\"] = payload.get(\"sandbox_over_quota\", False)\n"
            "    record[\"sandbox_scan\"] = payload.get(\"sandbox_scan\", SCAN_OK)\n"
        ),
        "why": "TST-02 #5: the internal keys must be popped, not merely read, before the envelope",
    },
    {
        "id": "cov-06-empty-resolv-wiring",
        "path": "bot.py",
        "find": "                empty_resolv=empty_resolv,\n",
        "replace": "                empty_resolv=None,\n",
        "why": "TST-02 #6: main() must pass the real empty_resolv path into the runner partial",
    },
    {
        "id": "cov-07-finish-redacts",
        "path": "agent.py",
        "find": "        text = config.redact(text)\n",
        "replace": "",
        "why": "TST-02 #7: agent.finish must redact before storing the reply",
    },
    {
        "id": "cov-08-summarize-redacts",
        "path": "agent.py",
        "find": (
            "    return config.redact(json.dumps(_normalise_summary(parsed), "
            "ensure_ascii=False))"
        ),
        "replace": "    return json.dumps(_normalise_summary(parsed), ensure_ascii=False)",
        "why": "TST-02 #8: summarize_conversation must redact before any caller sees it",
    },
    {
        "id": "cov-09-probe-user-flag",
        "path": "tools.py",
        "find": (
            '                "--user", f"{os.getuid()}:{os.getgid()}",\n'
            '                "--read-only",\n'
            '                "--cap-drop", "ALL",\n'
            '                "--security-opt", "no-new-privileges",\n'
            '                image, "timeout", "--version",'
        ),
        "replace": (
            '                "--read-only",\n'
            '                "--cap-drop", "ALL",\n'
            '                "--security-opt", "no-new-privileges",\n'
            '                image, "timeout", "--version",'
        ),
        "why": "TST-02 #9: the timeout probe must run as the bot's own uid:gid, not root",
    },
    {
        "id": "cov-10-sandbox-usage-followlinks",
        "path": "tools.py",
        "find": "for root, dirs, files in os.walk(p, followlinks=False, onerror=_on_walk_error):",
        "replace": "for root, dirs, files in os.walk(p, followlinks=True, onerror=_on_walk_error):",
        "why": "TST-02 #10: sandbox_usage must never follow a symlinked directory",
    },
    {
        "id": "cov-11-capture-headroom",
        "path": "tools.py",
        "find": "        self._room_cap = cap + headroom\n",
        "replace": "        self._room_cap = cap\n",
        "why": "TST-02 #11: _Capture must see a straddling secret whole before the cut",
    },
    # -- Section 5 security requirements (11) -------------------------------
    {
        "id": "sec-id-01-minted-id",
        "path": "agent.py",
        "find": (
            'ToolCall(id=f"call_{turn_id}_{index}", name=raw.name.strip(), '
            "arguments=raw.arguments)"
        ),
        "replace": (
            'ToolCall(id=raw.id.strip() or f"call_{turn_id}_{index}", '
            "name=raw.name.strip(), arguments=raw.arguments)"
        ),
        "why": "REQ-V12-ID-01: the model's tool-call id must never be trusted or stored",
    },
    {
        "id": "sec-qta-01-onerror",
        "path": "tools.py",
        "find": "for root, dirs, files in os.walk(p, followlinks=False, onerror=_on_walk_error):",
        "replace": "for root, dirs, files in os.walk(p, followlinks=False):",
        "why": "REQ-V12-QTA-01: an unreadable subtree must fail the scan closed, not silently",
    },
    {
        "id": "sec-qta-02-fail-closed",
        "path": "tools.py",
        "find": "    if status == SCAN_CUT_SHORT:\n",
        "replace": "    if False and status == SCAN_CUT_SHORT:\n",
        "why": "REQ-V12-QTA-02: a cut-short scan must refuse the run, not let it proceed",
    },
    {
        "id": "sec-qta-01-incomplete-precedence",
        "path": "tools.py",
        "find": (
            "                if status != SCAN_INCOMPLETE:\n"
            "                    status = SCAN_CUT_SHORT\n"
        ),
        "replace": "                status = SCAN_CUT_SHORT\n",
        "why": "REQ-V12-QTA-01: SCAN_INCOMPLETE must never be downgraded to SCAN_CUT_SHORT",
    },
    {
        "id": "sec-ssr-01-shape-check",
        "path": "config.py",
        "find": "    if not _DOMAIN_SHAPE_RE.match(entry):\n",
        "replace": "    if False and not _DOMAIN_SHAPE_RE.match(entry):\n",
        "why": "REQ-V12-SSR-01: shortened/hexadecimal IPv4 allowlist entries must be rejected",
    },
    {
        "id": "sec-ssr-03-request-time-guard",
        "path": "tools.py",
        "find": (
            "    if resolve is not None:\n"
            "        error = _check_resolved_scope(url, resolve)\n"
            "        if error is not None:\n"
            "            return error\n"
        ),
        "replace": "",
        "why": "REQ-V12-SSR-03: the resolved address must be checked before any request",
    },
    {
        "id": "sec-inf-01-o-nofollow",
        "path": "bot.py",
        "find": "os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_NONBLOCK,",
        "replace": "os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NONBLOCK,",
        "why": "REQ-V12-INF-01: a symlink planted at the resolv path must be refused",
    },
    {
        "id": "sec-orp-02-liveness-check",
        "path": "bot.py",
        "find": "        if owner and tools.owner_is_alive(owner):\n",
        "replace": "        if False and owner and tools.owner_is_alive(owner):\n",
        "why": "REQ-V12-ORP-02: a container owned by a live process must be skipped",
    },
    {
        "id": "sec-orp-01-start-ticks-parse",
        "path": "tools.py",
        "find": (
            '    remainder = line.rsplit(")", 1)[1]\n'
            "    return int(remainder.split()[19])"
        ),
        "replace": "    return int(line.split()[21])",
        "why": "REQ-V12-ORP-01: a foreign process's comm field may contain spaces/parens",
    },
    {
        "id": "sec-orp-03-137-mapping",
        "path": "tools.py",
        "find": "if wrap_timeout and exit_code in (124, 137):",
        "replace": "if wrap_timeout and exit_code in (124,):",
        "why": "REQ-V12-ORP-03: exit 137 under the wrapper must map to timed_out too",
    },
    {
        "id": "sec-aud-01-hook-redaction",
        "path": "tools.py",
        "find": (
            "        record = json.loads(config.redact(json.dumps(record, "
            "ensure_ascii=False)))\n"
        ),
        "replace": "",
        "why": "REQ-V12-AUD-01: the audit hook must receive an already-redacted record",
    },
    {
        "id": "sec-id-04-selftest-pairing",
        "path": "bot.py",
        "find": '    if calls[0]["id"] != tool_rows[0]["tool_call_id"]:\n',
        "replace": '    if False and calls[0]["id"] != tool_rows[0]["tool_call_id"]:\n',
        "why": "REQ-V12-ID-04: the selftest must check the call and its result share an id",
    },
    {
        "id": "sec-qta-03-chmod-and-retry",
        "path": "bot.py",
        "find": "    os.chmod(path, stat.S_IRWXU)\n",
        "replace": "",
        "why": "REQ-V12-QTA-03: the startup cleanup must survive a chmod-000 subdirectory",
    },
    # -- The four v1.1 guards whose tests already pass (4) ------------------
    {
        "id": "v11-storage-add-tool-turn-redacts",
        "path": "storage.py",
        "find": "    redacted_content = config.redact(content)\n",
        "replace": "    redacted_content = content\n",
        "why": "REQ-V11-RED-01: add_tool_turn must redact the assistant content it stores",
    },
    {
        "id": "v11-send-redacts",
        "path": "bot.py",
        "find": "            tg.send_message(chat_id, redact(part))\n",
        "replace": "            tg.send_message(chat_id, part)\n",
        "why": "REQ-V11-RED-04: every outgoing Telegram send must redact its text",
    },
    {
        "id": "v11-status-line-redacts",
        "path": "bot.py",
        "find": "    return redact(f\"⚙️ {tool}: {first_argument}…\")[:STATUS_MAX_CHARS]",
        "replace": "    return f\"⚙️ {tool}: {first_argument}…\"[:STATUS_MAX_CHARS]",
        "why": "REQ-V1-VIS-01: the status line must redact before truncating",
    },
    {
        "id": "v11-fetch-cap-breaks-the-stream",
        "path": "tools.py",
        "find": (
            "                    if len(body) > max_bytes + secret_headroom:\n"
            "                        break\n"
        ),
        "replace": "",
        "why": "REQ-V1-FT-02: fetch_url must stop reading once past its cap",
    },
    # -- REQ-V12-TST-01 restoration + the SSR-02 backstop (2) ---------------
    {
        "id": "trn-03-secret-headroom-term",
        "path": "tools.py",
        "find": "                secret_headroom = config.max_secret_length()\n",
        "replace": "                secret_headroom = 0\n",
        "why": "REQ-V12-TST-01: fetch_url must read past its cap by the longest secret",
    },
    {
        "id": "trn-03-strip-secret-fragment",
        "path": "tools.py",
        "find": (
            "        text = text.encode(\"utf-8\")[:max_bytes]"
            ".decode(\"utf-8\", errors=\"replace\")\n"
            "        text = config.strip_secret_fragment(text)\n"
        ),
        "replace": (
            "        text = text.encode(\"utf-8\")[:max_bytes]"
            ".decode(\"utf-8\", errors=\"replace\")\n"
        ),
        "why": "REQ-V13-TOO-09: fetch_url must strip a surviving fragment after the byte cut",
    },
    {
        "id": "ssr-is-global-backstop",
        "path": "config.py",
        "find": "    if not ip.is_global:\n        return \"non-global\"\n",
        "replace": "",
        "why": "REQ-V12-SSR-02: carrier-grade NAT must be caught by the is_global backstop",
    },
    # -- spec-v1.3 section 12, stage A (20) ---------------------------------
    {
        "id": "v13-usage-parse-none",
        "path": "llm/base.py",
        "find": '        usage=parse_usage(data.get("usage")),\n',
        "replace": "        usage=None,\n",
        "why": "REQ-V13-OBS-01: parse_response must hand the parsed usage to the response",
    },
    {
        "id": "v13-cached-tokens-dropped",
        "path": "llm/base.py",
        "find": (
            "        cached_tokens=_as_int(\n"
            '            prompt_details.get("cached_tokens") if isinstance(prompt_details, dict)'
            " else None\n"
            "        ),\n"
        ),
        "replace": "        cached_tokens=None,\n",
        "why": "REQ-V13-OBS-01: a reported cached_tokens count must reach the row",
    },
    {
        "id": "v13-think-not-stripped",
        "path": "llm/base.py",
        "find": (
            "    reasoning_chars += sum(len(block) for block in _THINK_BLOCK.findall(content))\n"
            '    content = _THINK_BLOCK.sub("", content)\n'
        ),
        "replace": (
            "    reasoning_chars += sum(len(block) for block in _THINK_BLOCK.findall(content))\n"
        ),
        "why": "REQ-V13-OBS-02: a balanced <think> block must never reach the user",
    },
    {
        "id": "v13-llm-call-not-recorded-on-error",
        "path": "agent.py",
        "find": (
            "            _record_llm_call(\n"
            "                conn, conv_id, llm, resolve_cost,\n"
            '                purpose="agent", round_no=round_no, attempt=attempts, ts=ts,\n'
            "                latency_ms=_elapsed_ms(started), turn_id=None,\n"
            "                messages=request_messages, tools=request_tools,\n"
            '                response=None, error_kind=getattr(exc, "kind", "http"),\n'
            "            )\n"
        ),
        "replace": "",
        "why": "REQ-V13-OBS-04: a failed invocation is an invocation and gets its own row",
    },
    {
        "id": "v13-resent-formula",
        "path": "metrics.py",
        "find": "        fresh = prompt if previous is None else max(0, prompt - previous)\n",
        "replace": "        fresh = prompt\n",
        "why": "REQ-V13-OBS-08: new_i is the growth over the previous prompt, not all of it",
    },
    {
        "id": "v13-cost-drops-output",
        "path": "llm/pricing.py",
        "find": (
            "        + cached * cached_rate\n"
            "        + completion * price.output_usd_per_mtok\n"
        ),
        "replace": "        + cached * cached_rate\n",
        "why": "REQ-V13-PRC-01: the cost formula must charge the completion tokens",
    },
    {
        "id": "v13-cost-none-as-zero",
        "path": "llm/pricing.py",
        "find": (
            "    if prompt is None or completion is None:\n"
            "        return None\n"
        ),
        "replace": (
            "    if prompt is None or completion is None:\n"
            "        return 0.0\n"
        ),
        "why": "REQ-V13-PRC-01: a partially reported usage stores NULL, never a cost of 0.0",
    },
    {
        "id": "v13-bench-gate-threshold",
        "path": "devtools/bench.py",
        "find": "COST_GATE_FACTOR = 0.70\n",
        "replace": "COST_GATE_FACTOR = 1.00\n",
        "why": "REQ-V13-BEN-12: the gate demands a 30% cut, not merely no regression",
    },
    {
        "id": "v13-bench-skipset-ignored",
        "path": "devtools/bench.py",
        "find": '    "scenarios_sha256", "skipped_scenarios", "constants", "config_sha256",\n',
        "replace": '    "scenarios_sha256", "constants", "config_sha256",\n',
        "why": "REQ-V13-BEN-12: two files with different skip sets may not be compared",
    },
    {
        "id": "v13-bench-scenario-hash-ignored",
        "path": "devtools/bench.py",
        "find": '    "scenarios_sha256", "skipped_scenarios", "constants", "config_sha256",\n',
        "replace": '    "skipped_scenarios", "constants", "config_sha256",\n',
        "why": "REQ-V13-BEN-12: a differing scenarios_sha256 makes two files incomparable",
    },
    {
        "id": "v13-bench-candidate-pricing",
        "path": "devtools/bench.py",
        "find": (
            "    total_b = _recomputed_total(baseline, price)\n"
            "    total_c = _recomputed_total(candidate, price)\n"
        ),
        "replace": (
            "    total_b = _recomputed_total(baseline, price)\n"
            "    total_c = _recomputed_total(\n"
            '        candidate, _price_from_meta(candidate["meta"].get("pricing"))\n'
            "    )\n"
        ),
        "why": "REQ-V13-BEN-12: both sides are priced with the baseline's snapshot",
    },
    {
        "id": "v13-bench-quality-minus-one",
        "path": "devtools/bench.py",
        "find": "QUALITY_GATE_SLACK = 0.02\n",
        "replace": "QUALITY_GATE_SLACK = 0.03\n",
        "why": "REQ-V13-BEN-12: at 36 runs one lost run is 2.8 pp and must fail the gate",
    },
    {
        "id": "v13-bench-redact-detail",
        "path": "devtools/bench.py",
        "find": (
            "        if isinstance(value, list):\n"
            "            return [walk(item) for item in value]\n"
        ),
        "replace": (
            "        if isinstance(value, list):\n"
            "            return [scrub(item) if isinstance(item, str) else item"
            " for item in value]\n"
        ),
        "why": "REQ-V13-BEN-10: redaction recurses into arrays of objects (checks[].detail)",
    },
    {
        "id": "v13-bench-turn-zero-based",
        "path": "devtools/bench_scenarios.py",
        "find": (
            "        return len(non_command_turns(self.turns)) - 1 "
            "if turn == LAST_TURN else turn - 1\n"
        ),
        "replace": (
            "        return len(non_command_turns(self.turns)) - 1 "
            "if turn == LAST_TURN else turn\n"
        ),
        "why": "REQ-V13-BEN-08: a positive turn is one-based over the non-command turns",
    },
    {
        "id": "v13-bench-timeout-continues",
        "path": "devtools/bench.py",
        "find": (
            "        if aborted is not None:\n"
            "            break\n"
            "\n"
            "    if aborted is not None:\n"
            '        meta["aborted"] = aborted\n'
        ),
        "replace": (
            "    if aborted is not None:\n"
            '        meta["aborted"] = aborted\n'
        ),
        "why": "REQ-V13-BEN-05: a timeout aborts the run; no later scenario is started",
    },
    {
        "id": "v13-bench-check-trusts-summary",
        "path": "devtools/bench.py",
        "find": (
            '    expected_summary = summarize(runs, meta["skipped_scenarios"], meta["repeats"])\n'
            '    _compare_summary(summary, expected_summary, "summary")\n'
        ),
        "replace": '    _compare_summary(summary, summary, "summary")\n',
        "why": "REQ-V13-BEN-01: check recomputes the summary instead of trusting the file",
    },
    {
        "id": "v13-usage-missing-ignores-failed",
        "path": "devtools/bench.py",
        "find": (
            '        row["error_kind"] is None\n'
            '        and (row["prompt_tokens"] is None or row["completion_tokens"] is None)\n'
        ),
        "replace": (
            '        (row["prompt_tokens"] is None or row["completion_tokens"] is None)\n'
        ),
        "why": "REQ-V13-BEN-01: a failed call's NULL token columns are not usage_missing",
    },
    {
        "id": "v13-openrouter-cap-ignored",
        "path": "devtools/bench.py",
        "find": (
            '    if cfg.llm_provider == "openrouter" '
            "and arguments.max_cost_usd is None:\n"
        ),
        "replace": (
            '    if False and cfg.llm_provider == "openrouter" '
            "and arguments.max_cost_usd is None:\n"
        ),
        "why": "REQ-V13-BEN-02: an OpenRouter run without --max-cost-usd is refused",
    },
    {
        "id": "v13-symlink-chmod",
        "path": "bot.py",
        "find": (
            "            if os.path.islink(path):\n"
            "                continue\n"
        ),
        "replace": "",
        "why": "REQ-V13-CO-01: the recovery chmod must skip a symlink, never its target",
    },
    {
        "id": "v13-only-typo-exit0",
        "path": "devtools/mutation_check.py",
        "find": '    if args.only is not None and all(m["id"] != args.only for m in MUTATIONS):\n',
        "replace": (
            "    if False and args.only is not None "
            'and all(m["id"] != args.only for m in MUTATIONS):\n'
        ),
        "why": "REQ-V13-CO-06: --only with an unknown id exits 1, never a clean zero",
    },
    # -- spec-v1.3 section 12, stage C (13) ---------------------------------
    {
        "id": "v13-compact-keeps-head-only",
        "path": "tools.py",
        "find": "    tail = _suffix_within(lines[len(head):], tail_budget)\n",
        "replace": "    tail = []\n",
        "why": "REQ-V13-TOO-01: compaction keeps a tail window, not the head alone",
    },
    {
        "id": "v13-dedup-threshold",
        "path": "tools.py",
        "find": "DUPLICATE_RUN_MIN = 3",
        "replace": "DUPLICATE_RUN_MIN = 2",
        "why": "REQ-V13-TOO-04: a run of exactly two identical lines is not collapsed",
    },
    {
        "id": "v13-fragment-after-cut",
        "path": "tools.py",
        "find": (
            "    return config.strip_secret_fragment("
            "head_part + marker + text[-tail_budget:])"
        ),
        "replace": "    return head_part + marker + text[-tail_budget:]",
        "why": "REQ-V13-TOO-01: the single-line fallback strips a fragment after the cut",
    },
    {
        "id": "v13-fetch-inline-fragment-after-cut",
        "path": "tools.py",
        "find": "        excerpt = config.strip_secret_fragment(text[:max_chars])\n",
        "replace": "        excerpt = text[:max_chars]\n",
        "why": "REQ-V13-TOO-09: the inline max_chars cut is followed by a fragment strip",
    },
    {
        "id": "v13-fetch-script-kept",
        "path": "tools.py",
        "find": 'HTML_DROP_TAGS = frozenset({"script", "style", "noscript", "template", "svg"})',
        "replace": 'HTML_DROP_TAGS = frozenset({"style", "noscript", "template", "svg"})',
        "why": "REQ-V13-TOO-05: script bodies are markup, never extracted text",
    },
    {
        "id": "v13-fetch-save-path",
        "path": "tools.py",
        "find": (
            '    name = hashlib.sha256(url.encode("utf-8")).hexdigest()'
            '[:FETCH_HASH_CHARS] + ".txt"'
        ),
        "replace": '    name = url.rstrip("/").rsplit("/", 1)[-1] + ".txt"',
        "why": "REQ-V13-TOO-06: the saved name is the URL hash, never a model-chosen path",
    },
    {
        "id": "v13-fetch-dir-follows-symlink",
        "path": "tools.py",
        "find": (
            "            FETCH_DIR_NAME, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,"
            " dir_fd=root_fd\n"
        ),
        "replace": "            FETCH_DIR_NAME, os.O_RDONLY | os.O_DIRECTORY, dir_fd=root_fd\n",
        "why": "REQ-V13-TOO-06: a symlinked fetch/ directory must be refused, not followed",
    },
    {
        "id": "v13-fetch-save-reuses-inode",
        "path": "tools.py",
        "find": (
            "        try:\n"
            "            os.unlink(name, dir_fd=fetch_fd)\n"
            "        except FileNotFoundError:\n"
            "            pass\n"
            "        fd = os.open(\n"
            "            name,\n"
            "            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,\n"
        ),
        "replace": (
            "        fd = os.open(\n"
            "            name,\n"
            "            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,\n"
        ),
        "why": "REQ-V13-TOO-06: a fresh inode, never a truncating write into a hard link",
    },
    {
        "id": "v13-fetch-save-always",
        "path": "tools.py",
        "find": "        saved_to = save_error = None\n        if truncated:\n",
        "replace": "        saved_to = save_error = None\n        if True:\n",
        "why": "REQ-V13-TOO-06: only a truncated fetch leaves a file behind",
    },
    {
        "id": "v13-compact-over-budget",
        "path": "tools.py",
        "find": "    budget = max_chars - MARKER_RESERVE\n",
        "replace": "    budget = max_chars\n",
        "why": "REQ-V13-TOO-01: the marker is reserved, so len(result) <= max_chars holds",
    },
    {
        "id": "v13-stub-current-turn",
        "path": "agent.py",
        "find": (
            "        if expose_tools:\n"
            "            request_messages = messages\n"
        ),
        "replace": (
            "        if expose_tools:\n"
            "            request_messages = _stub_stale_tool_results(messages)\n"
        ),
        "why": "REQ-V13-HST-01: a result of this invocation is never stale, never stubbed",
    },
    {
        "id": "v13-stub-skill-latest",
        "path": "agent.py",
        "find": "    keep = set(latest_skill.values())\n",
        "replace": "    keep = set()\n",
        "why": "REQ-V13-HST-02: the most recent load of each skill survives verbatim",
    },
    {
        "id": "v13-now-in-system",
        "path": "agent.py",
        "find": "    prompt = SYSTEM_PROMPT.format(skill_lines=skill_lines)\n",
        "replace": (
            "    prompt = SYSTEM_PROMPT.format(skill_lines=skill_lines)"
            ' + f" current date: {now}"\n'
        ),
        "why": "REQ-V13-CCH-01: the clock stays out of the cacheable prefix",
    },
    {
        "id": "v13-routing-agent-too",
        "path": "llm/__init__.py",
        "find": '    if purpose == "summary":\n',
        "replace": '    if purpose in ("summary", "agent"):\n',
        "why": "REQ-V13-RTE-01: LLM_SUMMARY_MODEL routes the summary purpose and only it",
    },
    # -- spec-v1.4, STOP branch (TST-05's narrowed minimum, 2) --------------
    {
        "id": "v14-ben-03-unknown-column-accepted",
        "path": "devtools/bench.py",
        "find": "            unknown = row_keys - allowed\n",
        "replace": "            unknown = set()\n",
        "why": "REQ-V14-BEN-03: a row carrying a key neither REQUIRED nor ALLOWED "
               "expects must be rejected, naming it — this mutation accepts any "
               "unknown column silently",
    },
    {
        "id": "v14-rel-01-timeout-budget-boundary-disabled",
        "path": "config.py",
        "find": "    if llm_timeout_s < floor:\n",
        "replace": "    if False and llm_timeout_s < floor:\n",
        "why": "REQ-V14-REL-01: an LLM_TIMEOUT_S/LLM_MAX_TOKENS pair under the "
               "latency-model floor must be refused before it ever reaches a live "
               "request, not silently accepted",
    },
]

_IDS = [m["id"] for m in MUTATIONS]
assert len(_IDS) == len(set(_IDS)), "duplicate mutation id in MUTATIONS"


class _Restorer:
    """Holds original file bytes in memory and restores them, verified
    byte-for-byte (REQ-V12-MUT-02)."""

    def __init__(self) -> None:
        self._snapshots: dict[Path, bytes] = {}

    def snapshot(self, path: Path) -> None:
        if path not in self._snapshots:
            self._snapshots[path] = path.read_bytes()

    def restore_one(self, path: Path) -> None:
        original = self._snapshots[path]
        path.write_bytes(original)
        if path.read_bytes() != original:
            print(f"FATAL: could not restore {path}", file=sys.stderr)
            sys.exit(2)

    def restore_all(self) -> None:
        for path in self._snapshots:
            self.restore_one(path)


_SELF_CHECK_NODE_ID = (
    "tests/test_mutation_check.py"
    "::test_t_v12_mut_04_every_find_string_occurs_exactly_once_in_the_real_repo"
)


def default_runner() -> int:
    """Run the real suite once, `-x -q`, with a fresh bytecode cache.

    Deselects the mutation table's own real-repo find-string check: that test
    asserts each `find` string is present in the untouched repo, so while a
    mutation is applied it fails on its own bookkeeping regardless of whether
    any functional test catches the mutation, which would make every mutation
    look "killed" for the wrong reason.
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        ["uv", "run", "--locked", "pytest", "-x", "-q", "--deselect", _SELF_CHECK_NODE_ID],
        cwd=REPO_ROOT,
        env=env,
    )
    return completed.returncode


def _install_signal_handlers(restorer: _Restorer) -> tuple:
    """Installs restore-and-exit handlers, returning the previous ones so the
    caller can put them back — this module may run more than once in the same
    process (its own test suite does exactly that)."""
    def _handler(_signum, _frame):
        restorer.restore_all()
        sys.exit(1)

    previous = (
        signal.signal(signal.SIGINT, _handler),
        signal.signal(signal.SIGTERM, _handler),
    )
    return previous


def _restore_signal_handlers(previous: tuple) -> None:
    signal.signal(signal.SIGINT, previous[0])
    signal.signal(signal.SIGTERM, previous[1])


def run_one(
    mutation: dict, *, runner, root: Path, restorer: _Restorer
) -> tuple[str, int | None]:
    """Returns (outcome, exit_code). `exit_code` is meaningful only for
    `ERRORED` (it is what the operator needs to fix the entry)."""
    path = root / mutation["path"]
    original = path.read_text(encoding="utf-8")
    count = original.count(mutation["find"])
    if count != 1:
        return DRIFTED, None

    restorer.snapshot(path)
    mutated = original.replace(mutation["find"], mutation["replace"], 1)
    try:
        path.write_text(mutated, encoding="utf-8")
        code = runner()
    finally:
        restorer.restore_one(path)

    # REQ-V12-MUT-01: the verdict is by exact exit code, not by "non-zero".
    # pytest returns 1 for "tests failed" and 2..5 for interrupted / internal
    # error / usage error / no tests collected — a mutation that breaks
    # collection must not be handed a clean bill of health.
    if code == 1:
        return KILLED, code
    if code == 0:
        return SURVIVED, code
    return ERRORED, code


def run_all(
    mutations: list[dict], *, runner=None, only: str | None = None, root: Path = REPO_ROOT
) -> int:
    runner = runner or default_runner
    restorer = _Restorer()
    previous_handlers = _install_signal_handlers(restorer)
    selected = mutations if only is None else [m for m in mutations if m["id"] == only]

    results: list[tuple[str, str, int | None]] = []
    try:
        for mutation in selected:
            print(f"running mutation: {mutation['id']}")
            outcome, code = run_one(mutation, runner=runner, root=root, restorer=restorer)
            results.append((mutation["id"], outcome, code))
            detail = f" (exit {code})" if outcome == ERRORED else ""
            print(f"  {mutation['id']}: {outcome}{detail}")
    finally:
        restorer.restore_all()
        _restore_signal_handlers(previous_handlers)

    killed = sum(1 for _, o, _ in results if o == KILLED)
    survived = sum(1 for _, o, _ in results if o == SURVIVED)
    errored = sum(1 for _, o, _ in results if o == ERRORED)
    drifted = sum(1 for _, o, _ in results if o == DRIFTED)

    print("")
    print(f"{'id':<40} {'outcome':<10} exit")
    for mutation_id, outcome, code in results:
        print(f"{mutation_id:<40} {outcome:<10} {code if code is not None else '-'}")
    print(
        f"{len(results)} mutations, {killed} killed, {survived} survived, "
        f"{errored} errored, {drifted} drifted"
    )
    return 0 if survived == 0 and errored == 0 and drifted == 0 else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="print the table, run nothing")
    parser.add_argument("--only", help="run a single mutation id")
    args = parser.parse_args(argv)

    if args.list:
        for mutation in MUTATIONS:
            print(f"{mutation['id']}\t{mutation['path']}\t{mutation['why']}")
        return 0

    # REQ-V13-CO-06: a mistyped id used to select the empty set and report a
    # clean gate over zero mutations. Fail loudly instead.
    if args.only is not None and all(m["id"] != args.only for m in MUTATIONS):
        print(f"unknown mutation id: {args.only}", file=sys.stderr)
        return 1

    return run_all(MUTATIONS, only=args.only)


if __name__ == "__main__":
    sys.exit(main())
