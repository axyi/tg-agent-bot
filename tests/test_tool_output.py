"""Token-aware tool output — spec-v1.3 section 10.1 (REQ-V13-TOO-01…10).

The compaction algorithm of REQ-V13-TOO-01 is normative, so the fixtures here
are byte-exact against it: every expected string is either written out in full
or assembled from split points whose arithmetic is asserted in the test itself.
Secrets are synthetic canaries; no live value is ever registered.
"""

import hashlib
import json
import os
import random
import re
import stat
import sys

import httpx
import pytest

import agent
import bot
import config
import storage
import tools
from llm.base import LLMResponse, ToolCall
from tests.fakes import FakeFetcher, FakeLLM, RecordingRunner, mock_llm_transport
from tests.test_v1_guardrails import make_cfg

ALLOWED = frozenset({"wttr.in"})
URL = "https://wttr.in/Koln"
CANARY = "SYNTHETIC-CANARY-NEVER-A-LIVE-VALUE"


@pytest.fixture
def only_canary(monkeypatch):
    """The canary is the only registered secret, and no test leaks it into the
    process-wide set that `config` keeps."""
    monkeypatch.setattr(config, "_secrets", {CANARY})
    return CANARY


def fetch_client(handler):
    return httpx.Client(transport=mock_llm_transport(handler))


def body_handler(body=b"sunny", status=200, content_type="text/plain"):
    def handler(request):
        headers = {"content-type": content_type} if content_type else {}
        return httpx.Response(status, content=body, headers=headers)
    return handler


def marker_for(omitted: list[str]) -> str:
    """The step-6 marker, spelled out exactly as the algorithm builds it."""
    return f"[… {len(chr(10).join(omitted))} chars / {len(omitted)} lines omitted …]"


# --------------------------------------------------------------------------
# REQ-V13-TOO-01 — the compaction algorithm
# --------------------------------------------------------------------------

def test_too_01_short_text_passes_through_with_ansi_removed():
    assert tools.compact_output("plain\ntext\n", max_chars=200) == "plain\ntext\n"
    coloured = "\x1b[31mred\x1b[0m and \x1b[1;32mgreen\x1b[m\n"
    assert tools.compact_output(coloured, max_chars=200) == "red and green\n"
    assert tools.compact_output("", max_chars=200) == ""


def test_too_01_marker_reserve_and_regexes_are_the_normative_constants():
    assert tools.MARKER_RESERVE == 50
    assert tools.ANSI_RE.pattern == r"\x1b\[[0-?]*[ -/]*[@-~]"
    assert tools.ERROR_RE.findall("Traceback") == ["Traceback"]
    # `\b` on both sides: a word that merely contains one of the five does not
    # make a line the error anchor.
    assert tools.ERROR_RE.search("ZeroDivisionError: x") is None
    assert tools.ERROR_RE.search("the job FAILED") is not None


def test_too_04_duplicate_collapse_of_a_200_line_log():
    """Appendix B: 200 identical INFO lines, 3600 B, under the capture cap."""
    stdout = "INFO heartbeat ok\n" * 200
    assert len(stdout.encode("utf-8")) == 3600 < tools.EXEC_MAX_STREAM_BYTES
    # The trailing newline leaves a final empty line, which is kept.
    assert tools.compact_output(stdout, max_chars=1500) == "INFO heartbeat ok [×200]\n"
    # A run of exactly two is not a run: 3 is the threshold.
    assert tools.compact_output("a\na\nb\n", max_chars=200) == "a\na\nb\n"
    assert tools.compact_output("a\na\na\nb\n", max_chars=200) == "a [×3]\nb\n"


def test_too_04_head_tail_window_of_a_5000_line_numeric_output():
    lines = [str(i) for i in range(5000)]
    text = "\n".join(lines)
    result = tools.compact_output(text, max_chars=1500)

    # budget 1450, head_budget 1450*40//100 = 580, tail_budget 870.
    # Head: lines 0-9 cost 2 each (20), 10-99 cost 3 each (270) -> 290 through
    # line 99; the three-digit lines that follow cost 4 each, and 580-290 = 290
    # buys 72 of them -> lines 100..171, 578 total, the next would be 582.
    # Tail: every remaining line costs 5, 870 // 5 = 174 -> lines 4826..4999.
    head, tail = lines[:172], lines[4826:]
    assert sum(len(line) + 1 for line in head) == 578
    assert sum(len(line) + 1 for line in tail) == 870
    omitted = lines[172:4826]
    assert result == "\n".join(head + [marker_for(omitted)] + tail)
    assert len(result) <= 1500


def traceback_lines() -> list[str]:
    """A long stderr whose traceback sits far enough from the end that the plain
    tail window cannot reach it — otherwise `error_context` would be a no-op and
    the fixture would prove nothing."""
    noise = [f"warn {i:04d}" for i in range(100)]                 # cost 10 each
    trace = [
        "Traceback (most recent call last):",
        '  File "/work/job.py", line 42, in main',
        "    total = done / left",
        "ZeroDivisionError: division by zero",
    ]
    cleanup = [f"cleanup {i:03d}: removed a temp file" for i in range(27)]
    return noise + trace + cleanup + [""]


def test_too_04_error_context_keeps_the_traceback_whole():
    lines = traceback_lines()
    stderr = "\n".join(lines)
    assert len(stderr.encode("utf-8")) < tools.EXEC_MAX_STREAM_BYTES

    costs = [len(line) + 1 for line in lines]
    budget = 1500 - tools.MARKER_RESERVE
    anchor = 100                              # the last ERROR_RE match: "Traceback"
    assert tools.ERROR_RE.search(lines[anchor]) and not any(
        tools.ERROR_RE.search(line) for line in lines[anchor + 1:]
    )
    # Without the error context the anchor is dropped: that is what step 5 is
    # for, and it is what makes this fixture exercise it.
    assert "Traceback" not in tools.compact_output(stderr, max_chars=1500)

    start = anchor - tools.ERROR_CONTEXT_LINES
    tail_cost = sum(costs[start:])
    assert tail_cost <= budget                # the window fits whole, nothing
    assert set(costs[:100]) == {10}           # is dropped from its front
    head_count = (budget - tail_cost) // 10

    result = tools.compact_output(stderr, max_chars=1500, error_context=True)
    expected = "\n".join(
        lines[:head_count] + [marker_for(lines[head_count:start])] + lines[start:]
    )
    assert result == expected
    assert len(result) <= 1500
    assert "ZeroDivisionError: division by zero" in result
    assert "[… " not in result[result.index("Traceback"):]


def test_too_04_without_error_context_the_same_stderr_is_windowed():
    stderr = "\n".join(traceback_lines())
    plain = tools.compact_output(stderr, max_chars=1500)
    with_context = tools.compact_output(stderr, max_chars=1500, error_context=True)
    assert plain != with_context
    assert "Traceback (most recent call last):" not in plain
    assert "Traceback (most recent call last):" in with_context


def test_too_01_step_7_single_line_fallback():
    text = "x" * 5000
    result = tools.compact_output(text, max_chars=1000)
    # budget 950, head_budget 380, tail_budget 570; omitted is the whole input.
    marker = marker_for([text])
    assert marker == "[… 5000 chars / 1 lines omitted …]"
    assert result == "x" * 380 + marker + "x" * 570
    assert "\n" not in result
    assert len(result) <= 1000


def test_too_01_length_invariant_over_random_inputs():
    """The property test of REQ-V13-TOO-01: `len(result) <= max_chars`, always."""
    rng = random.Random(20260902)
    alphabet = "ab \t…é\x1b[0m/"
    for case in range(400):
        max_chars = rng.randint(200, 4096)
        shape = case % 4
        if shape == 0:                                   # one very long line
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 9000)))
        elif shape == 1:                                 # many short lines
            text = "\n".join(
                "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))
                for _ in range(rng.randint(0, 400))
            )
        elif shape == 2:                                 # duplicate-heavy
            text = "\n".join(
                rng.choice(["same line", "same line", "same line", "other"])
                for _ in range(rng.randint(0, 500))
            ) + rng.choice(["", "\n"])
        else:                                            # mixed, with an error
            text = "\n".join(
                ["Traceback (most recent call last):" if rng.random() < 0.1
                 else "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 90)))
                 for _ in range(rng.randint(0, 200))]
            )
        for error_context in (False, True):
            result = tools.compact_output(
                text, max_chars=max_chars, error_context=error_context
            )
            assert len(result) <= max_chars, (case, max_chars, error_context)


def test_too_01_boundary_contract_a_head_cut_never_ends_in_a_secret_prefix(only_canary):
    """Test (a): the head window's last line ends in a proper prefix of the
    canary; the cut must not publish it."""
    first_line = "token=" + CANARY[:10]
    filler = [f"filler line {i:02d} " + "F" * 30 for i in range(10)]
    for line in filler:
        assert len(line) == 45                            # cost 46
    lines = [first_line] + filler
    text = "\n".join(lines)
    assert CANARY not in text

    result = tools.compact_output(text, max_chars=200)
    # budget 150, head_budget 60, tail_budget 90. Head: the first line costs
    # 17, the next 46 would overrun 60 -> head is the first line alone.
    # Tail: 90 // 46 = 1 filler line.
    assert len(first_line) + 1 == 17
    head_part, tail_part = ["token="], filler[-1:]
    omitted = lines[1:len(lines) - 1]
    assert result == "\n".join(head_part + [marker_for(omitted)] + tail_part)
    assert result.split("\n")[0] == "token="
    for length in range(config.SECRET_FRAGMENT_MIN, len(CANARY)):
        assert CANARY[:length] not in result, length


def test_too_01_boundary_contract_b_fallback_result_never_ends_in_a_fragment(only_canary):
    """Test (b): step 7's tail is an arbitrary character offset; the assembled
    result is stripped at its end."""
    text = "X" * 3000 + "key=" + CANARY[:12]
    assert CANARY not in text
    result = tools.compact_output(text, max_chars=500)
    # budget 450, head_budget 180, tail_budget 270.
    marker = marker_for([text])
    assert result == "X" * 180 + marker + text[-270:-12]
    assert result.endswith("key=")
    for length in range(config.SECRET_FRAGMENT_MIN, len(CANARY)):
        assert CANARY[:length] not in result, length


def test_too_01_head_strip_happens_before_the_marker(only_canary):
    """The head part is stripped on its own, not only at the end of the result:
    a fragment in the middle of the output would otherwise survive."""
    lines = ["password=" + CANARY[:20]] + [f"tail {i} " + "T" * 40 for i in range(6)]
    result = tools.compact_output("\n".join(lines), max_chars=200)
    assert result.startswith("password=\n[… ")


# --------------------------------------------------------------------------
# REQ-V13-TOO-02/03/04 — the exec envelope
# --------------------------------------------------------------------------

def exec_envelope(arguments: dict, result: dict) -> dict:
    runner = RecordingRunner(result)
    return json.loads(tools.execute_tool(
        "exec", json.dumps(arguments), skills={}, runner=runner
    ))


def stream_result(stdout="", stderr="", exit_code=0, **extra) -> dict:
    envelope = {
        "exit_code": exit_code,
        "timed_out": False,
        "truncated": False,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_bytes_total": len(stdout.encode("utf-8")),
        "stderr_bytes_total": len(stderr.encode("utf-8")),
        "notice": tools.UNTRUSTED_NOTICE,
    }
    envelope.update(extra)
    return envelope


def test_too_02_envelope_compacts_both_streams_end_to_end():
    stdout = "INFO heartbeat ok\n" * 200
    stderr = "\n".join(traceback_lines())
    envelope = exec_envelope(
        {"argv": ["job.py"], "max_output_chars": 1500},
        stream_result(stdout=stdout, stderr=stderr, exit_code=1),
    )
    assert envelope["stdout"] == "INFO heartbeat ok [×200]\n"
    assert "ZeroDivisionError: division by zero" in envelope["stderr"]
    assert "[… " not in envelope["stderr"][envelope["stderr"].index("Traceback"):]
    assert envelope["compacted"] is True
    assert envelope["truncated"] is False
    assert envelope["stdout_bytes_total"] == 3600
    assert envelope["exit_code"] == 1
    assert envelope["notice"] == tools.UNTRUSTED_NOTICE
    assert set(envelope) == {
        "exit_code", "timed_out", "truncated", "stdout", "stderr", "notice",
        "compacted", "stdout_bytes_total", "stderr_bytes_total",
    }


def test_too_02_untouched_output_is_not_reported_as_compacted():
    envelope = exec_envelope({"argv": ["echo"]}, stream_result(stdout="ok\n"))
    assert envelope["stdout"] == "ok\n"
    assert envelope["compacted"] is False


def test_too_02_error_context_follows_the_exit_code():
    stderr = "\n".join(traceback_lines())
    failed = exec_envelope({"argv": ["job.py"]}, stream_result(stderr=stderr, exit_code=1))
    passed = exec_envelope({"argv": ["job.py"]}, stream_result(stderr=stderr, exit_code=0))
    assert "Traceback (most recent call last):" in failed["stderr"]
    assert "Traceback (most recent call last):" not in passed["stderr"]


def test_too_02_stripping_ansi_alone_is_not_a_compaction():
    """`compacted` is defined as "the head/tail window or the duplicate collapse
    changed the text". Colour codes are removed from every stream, so reporting
    that as a compaction tells the model output was dropped when none was."""
    coloured = "\x1b[31mred\x1b[0m and \x1b[1;32mgreen\x1b[m\n"
    envelope = exec_envelope({"argv": ["ls", "--color"]}, stream_result(stdout=coloured))
    assert envelope["stdout"] == "red and green\n"
    assert envelope["compacted"] is False


def test_too_02_error_context_is_the_exit_code_alone():
    """REQ-V13-TOO-02 spells the flag out as `error_context = exit_code != 0`;
    `timed_out` is not a second term. On the serving path a timeout always
    carries a non-zero exit code, so the two only ever differ for a synthetic
    envelope like this one."""
    stderr = "\n".join(traceback_lines())
    envelope = exec_envelope(
        {"argv": ["job.py"]},
        stream_result(stderr=stderr, exit_code=0, timed_out=True),
    )
    assert "Traceback (most recent call last):" not in envelope["stderr"]
    assert envelope["stderr"] == exec_envelope(
        {"argv": ["job.py"]}, stream_result(stderr=stderr, exit_code=0)
    )["stderr"]


def test_too_02_and_07_the_six_window_constants_are_the_spec_literals():
    """REQ-V13-TOO-02 / REQ-V13-TOO-07 fix these numbers, and the schema the
    model is shown advertises them. Every other assertion in the suite compares
    the schema against `config`, which cannot notice a drift in `config` itself;
    the literals live here, once."""
    assert config.DEFAULT_EXEC_OUTPUT_CHARS == 1500
    assert config.MIN_EXEC_OUTPUT_CHARS == 200
    assert config.MAX_EXEC_OUTPUT_CHARS == 4096
    assert config.DEFAULT_FETCH_INLINE_CHARS == 5000
    assert config.MIN_FETCH_INLINE_CHARS == 500
    assert config.MAX_FETCH_INLINE_CHARS == 20000


def test_too_02_max_output_chars_is_clamped_to_its_range():
    stdout = "\n".join(f"line {i:04d}" for i in range(600))    # 10 chars a line
    cases = [
        (1, config.MIN_EXEC_OUTPUT_CHARS),            # below the floor
        (99999, config.MAX_EXEC_OUTPUT_CHARS),        # above the ceiling
        ("big", config.DEFAULT_EXEC_OUTPUT_CHARS),    # not an integer
        (True, config.DEFAULT_EXEC_OUTPUT_CHARS),     # bool is not an integer
        (None, config.DEFAULT_EXEC_OUTPUT_CHARS),     # explicit null
        (800, 800),
    ]
    for requested, effective in cases:
        envelope = exec_envelope(
            {"argv": ["job.py"], "max_output_chars": requested},
            stream_result(stdout=stdout),
        )
        assert len(envelope["stdout"]) <= effective, requested
        # The window is filled to within one line plus the marker reserve.
        assert len(envelope["stdout"]) > effective - 70, requested
    absent = exec_envelope({"argv": ["job.py"]}, stream_result(stdout=stdout))
    assert len(absent["stdout"]) <= config.DEFAULT_EXEC_OUTPUT_CHARS
    assert len(absent["stdout"]) > config.DEFAULT_EXEC_OUTPUT_CHARS - 70


def test_too_02_the_runner_carries_the_configured_default():
    """`output_default_chars` is the runner's bookkeeping key: popped before the
    model sees the envelope, exactly like `sandbox_over_quota`."""
    stdout = "\n".join(f"line {i:04d}" for i in range(600))    # 10 chars a line
    envelope = exec_envelope(
        {"argv": ["job.py"]},
        stream_result(stdout=stdout, output_default_chars=700),
    )
    assert "output_default_chars" not in envelope
    assert len(envelope["stdout"]) <= 700
    assert len(envelope["stdout"]) > 600
    # A per-call argument still wins over it.
    envelope = exec_envelope(
        {"argv": ["job.py"], "max_output_chars": 4096},
        stream_result(stdout=stdout, output_default_chars=700),
    )
    assert len(envelope["stdout"]) > 700


def test_too_02_the_capture_cap_is_the_ceiling_a_request_cannot_lift():
    """`EXEC_MAX_STREAM_BYTES` is the security cap: 4096 is also the largest
    window a model can ask for."""
    assert tools.EXEC_MAX_STREAM_BYTES == 4096
    assert config.MAX_EXEC_OUTPUT_CHARS == tools.EXEC_MAX_STREAM_BYTES


def test_too_02_capture_snapshot_reports_the_true_fed_total():
    capture = tools._Capture(10)
    capture.feed(b"0123456789abcdef")
    data, truncated, fed = capture.snapshot()
    assert data == b"0123456789"
    assert truncated is True
    assert fed == 16


def test_too_02_run_process_reports_the_byte_totals(tmp_path):
    code = "import sys; sys.stdout.write('x' * 5000); sys.stderr.write('e' * 20)"
    result = tools._run_process([sys.executable, "-c", code], workdir=tmp_path)
    assert result["stdout_bytes_total"] == 5000
    assert result["stderr_bytes_total"] == 20
    assert result["truncated"] is True
    assert len(result["stdout"].encode("utf-8")) == tools.EXEC_MAX_STREAM_BYTES


def test_too_02_exec_schema_advertises_the_window():
    exec_spec = next(
        spec for spec in tools.tool_specs() if spec["function"]["name"] == "exec"
    )
    parameter = exec_spec["function"]["parameters"]["properties"]["max_output_chars"]
    assert parameter["type"] == "integer"
    assert parameter["minimum"] == config.MIN_EXEC_OUTPUT_CHARS
    assert parameter["maximum"] == config.MAX_EXEC_OUTPUT_CHARS
    assert str(config.DEFAULT_EXEC_OUTPUT_CHARS) in parameter["description"]
    assert str(config.MAX_EXEC_OUTPUT_CHARS) in parameter["description"]
    assert exec_spec["function"]["parameters"]["required"] == ["argv"]


def test_too_04_the_exec_caps_and_the_exit_code_mapping_are_untouched():
    envelope = exec_envelope(
        {"argv": ["job.py"], "max_output_chars": 200},
        stream_result(stdout="x" * 5000, exit_code=42, truncated=True),
    )
    assert envelope["exit_code"] == 42
    assert envelope["truncated"] is True
    assert len(envelope["stdout"]) <= 200


def test_too_10_load_skill_output_is_never_compacted(tmp_path):
    body = "\n".join(f"step {i}: do the thing" for i in range(500))
    skill = tools.Skill(name="big", description="a big skill", body=body, source="big.md")
    envelope = json.loads(tools.execute_tool(
        "load_skill", '{"name": "big"}', skills={"big": skill}, runner=RecordingRunner()
    ))
    assert envelope == {"name": "big", "body": body}
    assert len(body) > config.DEFAULT_EXEC_OUTPUT_CHARS


# --------------------------------------------------------------------------
# REQ-V13-TOO-05…09 — fetch
# --------------------------------------------------------------------------

FETCH_KEYS = [
    "url", "status", "content_type", "chars_total", "returned_chars",
    "truncated", "saved_to", "save_error", "text",
]
HTML_PAGE = (
    "<!doctype html><html><head><title>Weather report</title>"
    "<style>body { color: red }</style>"
    "<script>var hidden = 'do-not-show-this';</script>"
    "</head><body><h1>K&ouml;ln</h1><p>"
    + "sunny " * 500
    + "</p><noscript>enable js</noscript></body></html>"
)


def fetched(tmp_path, body, *, content_type="text/html", max_chars=500,
            sandbox_max_bytes=config.DEFAULT_EXEC_SANDBOX_MAX_BYTES, url=URL,
            max_bytes=tools.FETCH_MAX_BYTES):
    client = fetch_client(body_handler(
        body.encode("utf-8") if isinstance(body, str) else body,
        content_type=content_type,
    ))
    return tools.fetch_url(
        url, allowed_domains=ALLOWED, client=client, workdir=tmp_path,
        sandbox_max_bytes=sandbox_max_bytes, max_chars=max_chars,
        max_bytes=max_bytes,
    )


def hashed_name(url: str = URL) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ".txt"


def test_too_05_html_becomes_text_and_too_07_pins_the_envelope(tmp_path):
    envelope = fetched(tmp_path, HTML_PAGE)

    assert list(envelope) == FETCH_KEYS
    assert envelope["url"] == URL
    assert envelope["status"] == 200
    assert envelope["content_type"] == "text/html"
    assert envelope["text"].startswith("Weather report")
    assert "Köln" in envelope["text"]                 # entities are decoded
    assert "do-not-show-this" not in envelope["text"]
    assert "color: red" not in envelope["text"]
    assert "enable js" not in envelope["text"]
    assert envelope["returned_chars"] == 500 == len(envelope["text"])
    assert envelope["chars_total"] > 3000
    assert envelope["truncated"] is True
    assert envelope["saved_to"] == f"fetch/{hashed_name()}"
    assert envelope["save_error"] is None

    saved = (tmp_path / "fetch" / hashed_name()).read_text(encoding="utf-8")
    assert len(saved) == envelope["chars_total"]
    assert saved.startswith(envelope["text"])
    # The name on disk is the hash and nothing else: no path component of it
    # comes from the model.
    written = [entry.name for entry in (tmp_path / "fetch").iterdir()]
    assert written == [hashed_name()]
    assert re.fullmatch(r"[0-9a-f]{16}\.txt", written[0])


def test_too_05_block_tags_and_whitespace_collapse(tmp_path):
    page = (
        "<html><body><h1>Title  line</h1><div>one</div><div>two</div>"
        "<ul><li>a</li><li>b</li></ul><p>a<br>b</p>\n\n\n\n<pre>  kept  </pre>"
        "</body></html>"
    )
    text = fetched(tmp_path, page, max_chars=20000)["text"]
    # Adjacent block tags are one break, never a blank line; the blank line in
    # the middle is the document's own, collapsed to a single one.
    assert text.split("\n") == [
        "Title line", "one", "two", "a", "b", "a", "b", "", "kept",
    ]


def test_too_05_html_is_recognised_without_a_content_type(tmp_path):
    envelope = fetched(tmp_path, "<HTML><body><p>hi there</p></body></html>",
                       content_type="application/octet-stream")
    # A binary content type wins: the sniff only helps when the type is text.
    assert set(envelope) == {"error"}
    envelope = fetched(tmp_path, "<HTML><body><p>hi there</p></body></html>",
                       content_type="text/plain")
    assert envelope["text"] == "hi there"


def test_too_05_plain_text_passes_through(tmp_path):
    envelope = fetched(tmp_path, "Koln: sunny +21C", content_type="text/plain")
    assert envelope["text"] == "Koln: sunny +21C"
    assert envelope["chars_total"] == 16
    assert envelope["truncated"] is False


def test_too_05_json_is_text_and_binary_is_refused(tmp_path):
    ok = fetched(tmp_path, '{"t": 21}', content_type="application/json")
    assert ok["text"] == '{"t": 21}'
    for content_type in ("application/pdf", "image/png", "application/octet-stream"):
        envelope = fetched(tmp_path, b"\x00\x01\x02", content_type=content_type)
        assert envelope == {"error": f"unsupported content type: {content_type}"}
    assert not (tmp_path / "fetch").exists()


def test_too_06_an_untruncated_fetch_writes_nothing(tmp_path):
    envelope = fetched(tmp_path, "x" * 300, content_type="text/plain", max_chars=500)
    assert envelope["truncated"] is False
    assert envelope["saved_to"] is None
    assert envelope["save_error"] is None
    assert not (tmp_path / "fetch").exists()


def test_too_06_quota_refuses_the_save(tmp_path):
    (tmp_path / "already-full.bin").write_bytes(b"F" * 4096)
    envelope = fetched(tmp_path, "y" * 3000, content_type="text/plain",
                       sandbox_max_bytes=4096)
    assert envelope["truncated"] is True
    assert envelope["saved_to"] is None
    assert envelope["save_error"] == "sandbox quota"
    assert envelope["text"] == "y" * 500
    assert not (tmp_path / "fetch").exists()


def test_too_06_a_symlinked_fetch_directory_is_refused(tmp_path):
    outside = tmp_path.parent / "outside-dir"
    outside.mkdir()
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "fetch").symlink_to(outside, target_is_directory=True)

    envelope = fetched(sandbox, "z" * 3000, content_type="text/plain")
    assert envelope["saved_to"] is None
    assert envelope["save_error"] == "refused"
    assert list(outside.iterdir()) == []
    assert (sandbox / "fetch").is_symlink()


def test_too_06_a_symlinked_target_is_replaced_and_its_target_untouched(tmp_path):
    outside = tmp_path.parent / "outside-file.txt"
    outside.write_text("precious", encoding="utf-8")
    sandbox = tmp_path / "sandbox"
    (sandbox / "fetch").mkdir(parents=True)
    (sandbox / "fetch" / hashed_name()).symlink_to(outside)

    envelope = fetched(sandbox, "z" * 3000, content_type="text/plain")
    assert envelope["saved_to"] == f"fetch/{hashed_name()}"
    assert envelope["save_error"] is None
    target = sandbox / "fetch" / hashed_name()
    assert stat.S_ISREG(os.lstat(target).st_mode)
    assert target.read_text(encoding="utf-8") == "z" * 3000
    assert outside.read_text(encoding="utf-8") == "precious"


def test_too_06_a_hard_linked_target_never_reaches_the_outside_inode(tmp_path):
    outside = tmp_path.parent / "outside-hardlink.txt"
    outside.write_text("precious", encoding="utf-8")
    sandbox = tmp_path / "sandbox"
    (sandbox / "fetch").mkdir(parents=True)
    os.link(outside, sandbox / "fetch" / hashed_name())
    assert os.stat(outside).st_nlink == 2

    envelope = fetched(sandbox, "z" * 3000, content_type="text/plain")
    assert envelope["saved_to"] == f"fetch/{hashed_name()}"
    assert envelope["save_error"] is None
    assert outside.read_text(encoding="utf-8") == "precious"
    assert os.stat(outside).st_nlink == 1
    saved = sandbox / "fetch" / hashed_name()
    assert saved.read_text(encoding="utf-8") == "z" * 3000
    assert os.stat(saved).st_ino != os.stat(outside).st_ino


def test_too_06_a_second_save_of_the_same_url_replaces_the_file(tmp_path):
    first = fetched(tmp_path, "a" * 3000, content_type="text/plain")
    second = fetched(tmp_path, "b" * 2000, content_type="text/plain")
    assert first["saved_to"] == second["saved_to"]
    saved = tmp_path / "fetch" / hashed_name()
    assert saved.read_text(encoding="utf-8") == "b" * 2000
    assert len(list((tmp_path / "fetch").iterdir())) == 1


def test_too_06_without_a_sandbox_nothing_is_saved(tmp_path):
    client = fetch_client(body_handler(b"c" * 3000, content_type="text/plain"))
    envelope = tools.fetch_url(URL, allowed_domains=ALLOWED, client=client, max_chars=500)
    assert envelope["truncated"] is True
    assert envelope["saved_to"] is None
    assert envelope["save_error"] == "refused"


def test_too_07_error_outcomes_keep_the_single_key_shape(tmp_path):
    def raising(request):
        raise httpx.ConnectError("boom")

    client = httpx.Client(transport=mock_llm_transport(raising))
    envelope = tools.fetch_url(
        URL, allowed_domains=ALLOWED, client=client, workdir=tmp_path,
    )
    assert set(envelope) == {"error"}
    assert envelope["error"] == "fetch failed: ConnectError"
    assert not (tmp_path / "fetch").exists()

    refused = tools.fetch_url(
        "https://example.com/x", allowed_domains=ALLOWED,
        client=fetch_client(body_handler()), workdir=tmp_path,
    )
    assert set(refused) == {"error"}
    assert not (tmp_path / "fetch").exists()


def test_too_07_max_chars_is_clamped_to_its_range(tmp_path):
    body = "d" * 30000
    cases = [
        (1, config.MIN_FETCH_INLINE_CHARS),
        (99999, config.MAX_FETCH_INLINE_CHARS),
        (None, config.DEFAULT_FETCH_INLINE_CHARS),
        ("wide", config.DEFAULT_FETCH_INLINE_CHARS),
    ]
    for requested, effective in cases:
        envelope = fetched(tmp_path, body, content_type="text/plain",
                           max_chars=requested)
        assert envelope["returned_chars"] == effective, requested


def test_too_07_the_tool_argument_reaches_the_fetcher():
    seen = {}

    def fetcher(url, **kwargs):
        seen.update(kwargs)
        seen["url"] = url
        return {"error": "stopped here"}

    tools.execute_tool(
        "fetch", json.dumps({"url": URL, "max_chars": 900}), skills={},
        runner=RecordingRunner(), fetcher=fetcher,
    )
    assert seen == {"url": URL, "max_chars": 900}
    seen.clear()
    tools.execute_tool(
        "fetch", json.dumps({"url": URL}), skills={},
        runner=RecordingRunner(), fetcher=fetcher,
    )
    assert seen == {"url": URL}          # the bound default of the partial wins


def test_too_07_fetch_schema_advertises_the_window_and_the_saved_file():
    fetch_spec = next(
        spec for spec in tools.tool_specs() if spec["function"]["name"] == "fetch"
    )
    parameter = fetch_spec["function"]["parameters"]["properties"]["max_chars"]
    assert parameter["minimum"] == config.MIN_FETCH_INLINE_CHARS
    assert parameter["maximum"] == config.MAX_FETCH_INLINE_CHARS
    description = fetch_spec["function"]["description"]
    assert "grep" in description and "fetch/" in description
    assert fetch_spec["function"]["parameters"]["required"] == ["url"]


def test_too_09_a_canary_never_reaches_the_inline_text_or_the_saved_file(
    tmp_path, only_canary
):
    page = (
        "<html><body><p>key is " + CANARY + "</p><p>"
        + "filler " * 600 + "</p></body></html>"
    )
    envelope = fetched(tmp_path, page)
    saved = (tmp_path / "fetch" / hashed_name()).read_text(encoding="utf-8")
    assert CANARY not in envelope["text"]
    assert CANARY not in saved
    assert config.REDACTION in envelope["text"]
    assert config.REDACTION in saved


def test_too_09_a_canary_prefix_at_the_inline_cut_is_stripped(tmp_path, only_canary):
    prefix = CANARY[:20]
    body = "p" * 480 + prefix + "q" * 3000
    envelope = fetched(tmp_path, body, content_type="text/plain", max_chars=500)
    assert envelope["text"] == "p" * 480
    assert envelope["returned_chars"] == 480
    for length in range(config.SECRET_FRAGMENT_MIN, len(CANARY)):
        assert CANARY[:length] not in envelope["text"], length


def test_too_09_entities_that_spell_a_canary_are_redacted_after_extraction(
    tmp_path, only_canary
):
    encoded = "".join(f"&#{ord(char)};" for char in CANARY)
    page = f"<html><body><p>{encoded}</p><p>{'filler ' * 600}</p></body></html>"
    envelope = fetched(tmp_path, page)
    saved = (tmp_path / "fetch" / hashed_name()).read_text(encoding="utf-8")
    assert CANARY not in envelope["text"] and CANARY not in saved
    assert config.REDACTION in envelope["text"]


def no_fragment_at_the_end(text: str) -> None:
    """Nothing that ends `text` is a proper prefix of the canary long enough to
    be worth anything to a reader (`config.SECRET_FRAGMENT_MIN`)."""
    for length in range(config.SECRET_FRAGMENT_MIN, len(CANARY)):
        assert not text.endswith(CANARY[:length]), length


def test_too_09_the_byte_cut_fragment_never_reaches_the_saved_file(
    tmp_path, only_canary
):
    """REQ-V13-TOO-09 is redact -> cut -> strip. A page longer than
    `FETCH_MAX_BYTES` that itself prints an incomplete secret straddling byte
    65536 gives `config.redact` nothing to replace, so only a strip *after* the
    byte cut can keep the fragment out — and the saved file is the copy that
    matters, because the tool description sends the model to grep it."""
    fragment = CANARY[:20]
    body = "a" * (tools.FETCH_MAX_BYTES - len(fragment)) + fragment + "b" * 3000
    envelope = fetched(tmp_path, body, content_type="text/plain")

    assert envelope["truncated"] is True
    assert envelope["saved_to"] == f"fetch/{hashed_name()}"
    saved = (tmp_path / "fetch" / hashed_name()).read_text(encoding="utf-8")
    assert len(saved) == tools.FETCH_MAX_BYTES - len(fragment)
    no_fragment_at_the_end(saved)
    no_fragment_at_the_end(envelope["text"])
    assert CANARY[:config.SECRET_FRAGMENT_MIN] not in saved


def test_too_09_an_untruncated_excerpt_is_stripped_too(tmp_path, only_canary):
    """The narrow variant: a body of four-byte characters cut at
    `FETCH_MAX_BYTES` yields fewer characters than a wide `max_chars`, so
    `truncated` is false and nothing is saved — the fragment the byte cut left
    would go straight into the model's context."""
    fragment = CANARY[:20]
    wide = "\N{MUSICAL SYMBOL G CLEF}"                # four bytes each
    filler = (tools.FETCH_MAX_BYTES - len(fragment)) // 4
    body = wide * filler + fragment + "b" * 3000
    envelope = fetched(tmp_path, body, content_type="text/plain",
                       max_chars=config.MAX_FETCH_INLINE_CHARS)

    assert envelope["truncated"] is False
    assert envelope["saved_to"] is None and envelope["save_error"] is None
    assert envelope["chars_total"] < config.MAX_FETCH_INLINE_CHARS
    no_fragment_at_the_end(envelope["text"])
    assert envelope["text"].endswith(wide)


# --------------------------------------------------------------------------
# REQ-V13-TOO-08 — the sandbox cleanup treats `fetch/` like any other entry
# --------------------------------------------------------------------------

def test_too_08_startup_cleanup_removes_the_fetch_directory(tmp_path):
    cfg = make_cfg(tmp_path)
    cfg.exec_workdir.mkdir()
    fetch_dir = cfg.exec_workdir / "fetch"
    fetch_dir.mkdir()
    (fetch_dir / hashed_name()).write_text("saved page", encoding="utf-8")
    (cfg.exec_workdir / "other.txt").write_text("x", encoding="utf-8")

    bot._clean_sandbox_at_start(cfg)

    assert not fetch_dir.exists()
    assert list(cfg.exec_workdir.iterdir()) == []


# --------------------------------------------------------------------------
# REQ-V13-TOO-03 — the size is measured on the stream text, never on the
# envelope. The measurement point is `agent._record_tool_call`, so these are
# end-to-end through `run_agent` and read the `tool_calls` row it writes.
# --------------------------------------------------------------------------

TOO_03_USER = 424242


def measured(conn, call, *, runner=None, fetcher=None, skills=None):
    """Run one tool call through the agent and return `(row, tool message)`."""
    conv = storage.get_or_create_active_conversation(conn, TOO_03_USER)
    storage.add_user_message(conn, conv, "go")
    agent.run_agent(
        conn=conn, conv_id=conv,
        llm=FakeLLM([LLMResponse("", [call], "tool_calls"),
                     LLMResponse("done", [], "stop")]),
        skills=skills or {}, runner=runner or RecordingRunner(),
        now="2026-09-02T10:00:00Z", sleep=lambda _seconds: None, fetcher=fetcher,
    )
    row = conn.execute("SELECT * FROM tool_calls ORDER BY id").fetchone()
    content = conn.execute(
        "SELECT content FROM messages WHERE role = 'tool' ORDER BY id"
    ).fetchone()[0]
    return row, content


def test_too_03_exec_is_measured_on_the_streams_around_compaction(conn):
    stdout = "INFO heartbeat ok\n" * 200
    stderr = "\n".join(traceback_lines())
    runner = RecordingRunner(stream_result(stdout=stdout, stderr=stderr, exit_code=1))
    row, content = measured(
        conn,
        ToolCall("c", "exec", json.dumps({"argv": ["job.py"], "max_output_chars": 400})),
        runner=runner,
    )
    envelope = json.loads(content)

    assert row["raw_output_chars"] == len(stdout) + len(stderr)
    assert row["output_chars"] == len(envelope["stdout"]) + len(envelope["stderr"])
    assert row["raw_output_chars"] > row["output_chars"]
    assert envelope["compacted"] is True
    # Neither number is the serialized envelope: that is the mistake TOO-03 names.
    assert row["output_chars"] != len(content)
    assert row["raw_output_chars"] != len(content)


def test_too_03_an_uncompacted_exec_measures_equal(conn):
    runner = RecordingRunner(stream_result(stdout="ok\n", stderr="warn\n"))
    row, content = measured(conn, ToolCall("c", "exec", '{"argv": ["true"]}'),
                            runner=runner)
    assert json.loads(content)["compacted"] is False
    assert row["raw_output_chars"] == row["output_chars"] == len("ok\n") + len("warn\n")


def test_too_03_fetch_is_measured_on_chars_total_and_the_inline_excerpt(conn):
    text = "sunny " * 400
    fetcher = FakeFetcher({
        "url": URL, "status": 200, "content_type": "text/plain",
        "chars_total": 12000, "returned_chars": len(text), "truncated": True,
        "saved_to": "fetch/" + "0" * 16 + ".txt", "save_error": None, "text": text,
    })
    row, content = measured(conn, ToolCall("c", "fetch", json.dumps({"url": URL})),
                            fetcher=fetcher)
    assert row["raw_output_chars"] == 12000
    assert row["output_chars"] == len(text)
    assert row["raw_output_chars"] > row["output_chars"]
    assert row["output_chars"] != len(content)


def test_too_03_load_skill_measures_the_body_and_never_shrinks(conn):
    body = "\n".join(f"step {i}: do the thing" for i in range(500))
    skill = tools.Skill(name="big", description="a big skill", body=body, source="big.md")
    row, content = measured(conn, ToolCall("c", "load_skill", '{"name": "big"}'),
                            skills={"big": skill})
    assert json.loads(content)["body"] == body
    assert row["raw_output_chars"] == row["output_chars"] == len(body)


def test_too_03_an_error_envelope_falls_back_to_the_envelope_size(conn):
    """No stream text exists, so the model-facing text *is* the envelope."""
    row, content = measured(conn, ToolCall("c", "exec", '{"argv": []}'))
    assert set(json.loads(content)) == {"error"}
    assert row["raw_output_chars"] == row["output_chars"] == len(content)
