"""The static HTML dashboard — spec-v1.3 section 8 (REQ-V13-DSH-01…02).

Two on-disk fixtures (`tests/fixtures/bench/{baseline,candidate}.json`, both
accepted by `bench.check_document`) stand in for a benchmark run; every
assertion about the rendered page goes through `html.parser`, so a page that
stopped being well-formed HTML, or an id that silently disappeared, fails here
rather than in a browser.
"""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

import metrics
from devtools import bench, dashboard

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bench"
BASELINE = FIXTURES / "baseline.json"
CANDIDATE = FIXTURES / "candidate.json"

# Tags that never carry an end tag; the id stack below would never pop them.
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}


# --------------------------------------------------------------------------
# a parser that proves the page is HTML, not a string that happens to contain
# the right substrings
# --------------------------------------------------------------------------

class Page(HTMLParser):
    """Collects every `id` and the text under it, and keeps the open-tag stack
    so an unbalanced document is visible (`self.open` is non-empty at the end)."""

    def __init__(self, markup: str):
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.text: dict[str, str] = {}
        self.open: list[str | None] = []
        self.tags: list[str] = []
        self.attributes: list[tuple[str, dict]] = []
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append(tag)
        self.attributes.append((tag, attributes))
        if tag in VOID_TAGS:
            return
        ident = attributes.get("id")
        if ident:
            self.ids.append(ident)
            self.text.setdefault(ident, "")
        self.open.append(ident)

    def handle_startendtag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if self.open:
            self.open.pop()

    def handle_data(self, data):
        for ident in self.open:
            if ident is not None:
                self.text[ident] += data

    def value(self, ident: str) -> str:
        assert ident in self.text, f"no element with id={ident!r}"
        return self.text[ident].strip()

    def number(self, ident: str) -> float:
        raw = self.value(ident).lstrip("$").rstrip("%")
        return float(raw)


def render_fixture(path=BASELINE, compare=None):
    document = json.loads(path.read_text(encoding="utf-8"))
    other = None if compare is None else json.loads(compare.read_text(encoding="utf-8"))
    return document, dashboard.render(document, other)


# --------------------------------------------------------------------------
# synthetic documents, self-consistent through the harness' own arithmetic
# --------------------------------------------------------------------------

def llm_row(row_id, *, conv_seq=1, turn=1, purpose="agent", rnd=1, prompt=1000,
            completion=100, cached=None, latency=500, cost=None, tool_calls_n=0,
            error_kind=None, by_role=None, encode=True):
    roles = by_role if by_role is not None else {"system": 100, "tools": 50, "user": 10,
                                                 "assistant": 0, "tool": 0}
    total = None if prompt is None or completion is None else prompt + completion
    return {
        "id": row_id, "conv_seq": conv_seq, "turn_id": turn, "purpose": purpose,
        "round": rnd, "attempt": 1, "ts": "2026-01-01T00:00:00Z", "provider": "lmstudio",
        "model": "m", "prompt_tokens": prompt, "completion_tokens": completion,
        "total_tokens": total, "cached_tokens": cached, "reasoning_tokens": None,
        "reasoning_chars": 0, "prompt_chars": (prompt or 0) * 3,
        "prompt_chars_by_role": json.dumps(roles, sort_keys=True) if encode else roles,
        "messages_n": 2, "tools_exposed": 1, "latency_ms": latency,
        "finish_reason": "stop", "tool_calls_n": tool_calls_n, "error_kind": error_kind,
        "cost_usd": cost, "cost_basis": None if cost is None else "reference:some/model",
    }


def tool_row(row_id, *, conv_seq=1, turn=1, tool="exec", out_tokens=200, duration=100):
    return {
        "id": row_id, "conv_seq": conv_seq, "turn_id": turn, "tool_call_id": f"c{row_id}",
        "tool": tool, "ts": "2026-01-01T00:00:00Z", "input_chars": 10,
        "raw_output_chars": 40, "output_chars": 40, "output_tokens_est": out_tokens,
        "duration_ms": duration, "outcome": "ok",
    }


def run(scenario, repeat, *, llm_rows=None, tool_rows=None, wall_ms=1000, success=True):
    llm_rows = [llm_row(repeat)] if llm_rows is None else list(llm_rows)
    tool_rows = [] if tool_rows is None else list(tool_rows)
    return {
        "scenario": scenario, "repeat": repeat, "success": success,
        "failure": None if success else "checks",
        "checks": [{"kind": "answer_regex", "ok": success, "detail": "detail"}],
        "answers": ["ok"], "llm_calls": llm_rows, "tool_calls": tool_rows,
        "totals": bench.totals_from_rows(llm_rows, tool_rows, wall_ms),
    }


def document(runs, **meta):
    base = {
        "bench_schema": 1,
        "meta": {
            "tag": "synthetic", "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:10:00Z", "git_commit": "0" * 40,
            "provider": "lmstudio", "model": "m", "context_length": 42496,
            "repeats": max((r["repeat"] for r in runs), default=1), "timeout_s": 600.0,
            "prefix_tokens": 100, "scenarios_sha256": "0" * 64, "pricing": None,
            "skipped_scenarios": [], "only": None,
            "env_flags": {key: None for key in bench.ENV_FLAG_KEYS},
            "config_sha256": "c" * 64, "constants": {"REQUEST_DEFAULTS": {}},
        },
        "runs": runs,
        "summary": bench.summarize(runs, [], max((r["repeat"] for r in runs), default=1)),
    }
    base["meta"].update(meta)
    return base


def priced(scenario, costs):
    """One run per cost, in execution order; `None` means the run reported no
    price at all."""
    runs = []
    for index, cost in enumerate(costs, start=1):
        rows = [llm_row(index, prompt=1000 + index * 100, completion=10, cost=cost)]
        runs.append(run(scenario, index, llm_rows=rows))
    return runs


# --------------------------------------------------------------------------
# REQ-V13-DSH-02: the fixtures render, parse and carry the documented ids
# --------------------------------------------------------------------------

def test_fixtures_are_arithmetically_valid_benchmark_documents():
    """The fixtures are not hand-typed numbers: `bench.check_document`
    recomputes every total and every summary value from the embedded rows. The
    one tolerated failure is a stale `scenarios_sha256` — amending
    `bench_scenarios.py` changes the digest, never the arithmetic the dashboard
    reads."""
    for path in (BASELINE, CANDIDATE):
        code, reason = bench.check_document(json.loads(path.read_text(encoding="utf-8")))
        assert code == 0 or "scenarios_sha256" in reason, f"{path.name}: {reason}"


def test_page_parses_and_holds_the_four_ids_without_compare():
    _, markup = render_fixture()
    page = Page(markup)
    assert page.open == [], "the document is not well-nested"
    assert {"aggregates", "cache", "tools", "timeline"} <= set(page.ids)
    assert "compare" not in page.ids
    assert len(page.ids) == len(set(page.ids)), "duplicate id in the page"


def test_compare_adds_the_fifth_id_and_nothing_else_disappears():
    _, markup = render_fixture(compare=CANDIDATE)
    page = Page(markup)
    assert page.open == []
    assert {"aggregates", "cache", "tools", "timeline", "compare"} <= set(page.ids)


def test_no_external_resource_and_no_script():
    for compare in (None, CANDIDATE):
        _, markup = render_fixture(compare=compare)
        assert not re.search(r'(?:src|href)\s*=\s*"[^"]*https?://', markup)
        assert "<script" not in markup
        assert "url(" not in markup          # no @font-face, no background image
        page = Page(markup)
        for tag, attributes in page.attributes:
            for name in ("src", "href"):
                target = attributes.get(name)
                if target is not None:
                    assert target.startswith("#"), f"{tag} {name}={target}"


def test_aggregate_totals_match_the_fixture_summary():
    document_json, markup = render_fixture()
    page = Page(markup)
    totals = document_json["summary"]["totals"]
    for key, _label, kind in dashboard.TOTAL_ROWS:
        if kind == "int":
            assert page.value(f"m-{key}") == str(totals[key]), key
    assert page.number("m-cost_usd") == pytest.approx(totals["cost_usd"], abs=5e-7)
    summary = document_json["summary"]
    assert page.value("m-runs") == str(summary["runs"])
    assert page.value("m-successes") == str(summary["successes"])
    assert page.value("m-skipped") == str(summary["skipped"])
    assert page.number("m-success_rate") / 100 == pytest.approx(summary["success_rate"],
                                                                abs=1e-4)
    assert page.number("m-cost_per_success") == pytest.approx(summary["cost_per_success"],
                                                              abs=5e-7)
    assert page.number("m-tokens_per_success") == pytest.approx(
        summary["tokens_per_success"], abs=0.05)


def test_per_task_averages_match_the_fixture_summary():
    document_json, markup = render_fixture()
    page = Page(markup)
    averages = document_json["summary"]["avg_per_task"]
    for key, _label, _kind in dashboard.AVG_ROWS:
        assert page.number(f"m-avg-{key}") == pytest.approx(averages[key], abs=0.05), key
    # The assignment's four per-task figures are all present, none renamed away.
    assert {"tokens", "rounds", "tool_calls", "latency_ms"} == {
        key for key, _label, _kind in dashboard.AVG_ROWS}


def test_context_growth_row_comes_from_the_shared_metrics_implementation():
    document_json, markup = render_fixture()
    page = Page(markup)
    for role, value in document_json["summary"]["context_growth"].items():
        assert page.number(f"m-growth-{role}") == pytest.approx(value, abs=0.05)


# --------------------------------------------------------------------------
# #cache
# --------------------------------------------------------------------------

def test_cache_section_reports_hit_rate_resent_and_prefix_share():
    document_json, markup = render_fixture()
    page = Page(markup)
    summary = document_json["summary"]
    assert page.number("m-cache_hit_rate") / 100 == pytest.approx(summary["cache_hit_rate"],
                                                                  abs=1e-4)
    assert page.number("m-resent_share") / 100 == pytest.approx(summary["resent_share"],
                                                                abs=1e-4)
    expected = (document_json["meta"]["prefix_tokens"] * summary["totals"]["calls"]
                / summary["totals"]["prompt_tokens"])
    assert page.number("m-prefix_share") / 100 == pytest.approx(expected, abs=1e-4)
    assert page.value("m-cache-resent_tokens") == str(summary["totals"]["resent_tokens"])
    assert page.value("m-cache-new_tokens") == str(summary["totals"]["new_tokens"])


def test_cache_hit_rate_renders_na_when_the_provider_reported_none():
    doc = document([run("S01", 1, llm_rows=[llm_row(1, cached=None)])])
    assert doc["summary"]["cache_hit_rate"] is None
    page = Page(dashboard.render(doc))
    assert page.value("m-cache_hit_rate") == "n/a"


def test_prefix_share_is_na_without_a_prefix_probe():
    doc = document([run("S01", 1)], prefix_tokens=None)
    # REQ-V13-OBS-08: one implementation, shared with `bench.py report`.
    assert metrics.prefix_share(doc) is None
    assert not hasattr(dashboard, "prefix_share")
    assert Page(dashboard.render(doc)).value("m-prefix_share") == "n/a"


# --------------------------------------------------------------------------
# #tools
# --------------------------------------------------------------------------

def test_tool_breakdown_sums_output_tokens_and_time_over_every_run():
    document_json = json.loads(BASELINE.read_text(encoding="utf-8"))
    breakdown = dashboard.tool_breakdown(document_json["runs"])
    rows = [row for run_ in document_json["runs"] for row in run_["tool_calls"]]
    for entry in breakdown:
        mine = [row for row in rows if row["tool"] == entry["name"]]
        assert entry["calls"] == len(mine)
        assert entry["output_tokens_est"] == sum(row["output_tokens_est"] for row in mine)
        assert entry["duration_ms"] == sum(row["duration_ms"] for row in mine)
    assert [entry["name"] for entry in breakdown] == sorted(
        (entry["name"] for entry in breakdown),
        key=lambda name: (-next(e["output_tokens_est"] for e in breakdown
                                if e["name"] == name), name))


def test_tools_section_renders_a_bar_and_the_numbers_for_every_tool():
    document_json, markup = render_fixture()
    page = Page(markup)
    for entry in dashboard.tool_breakdown(document_json["runs"]):
        name = entry["name"]
        assert page.value(f"m-tool-{name}-calls") == str(entry["calls"])
        assert page.value(f"m-tool-{name}-tokens") == str(entry["output_tokens_est"])
        assert page.value(f"m-tool-{name}-ms") == str(entry["duration_ms"])
    widths = [attributes["style"] for tag, attributes in page.attributes
              if tag == "span" and "style" in attributes]
    assert widths and all(re.fullmatch(r"width:\d+(\.\d+)?%", value) for value in widths)


def test_tools_section_survives_a_run_without_tool_calls():
    doc = document([run("S01", 1)])
    page = Page(dashboard.render(doc))
    assert "tools" in page.ids
    assert "No tool call" in page.text["tools"]


# --------------------------------------------------------------------------
# #timeline — the median rule of REQ-V13-DSH-01
# --------------------------------------------------------------------------

def test_median_run_ranks_by_cost_when_every_run_is_priced():
    runs = priced("S01", [0.030, 0.010, 0.020])
    assert dashboard.median_key(runs) == "cost_usd"
    assert dashboard.median_run(runs)["repeat"] == 3        # 0.010, 0.020, 0.030 → index 1


def test_median_run_falls_back_to_tokens_when_any_run_has_no_cost():
    runs = [
        run("S02", 1, llm_rows=[llm_row(1, prompt=1200, completion=150, cost=0.01)]),
        run("S02", 2, llm_rows=[llm_row(2, prompt=900, completion=60, cost=None)]),
        run("S02", 3, llm_rows=[llm_row(3, prompt=1500, completion=180, cost=0.02)]),
    ]
    assert dashboard.median_key(runs) == "tokens"
    # 960, 1350, 1680 → index 1 is repeat 1; ranking by cost would have picked 3.
    assert dashboard.median_run(runs)["repeat"] == 1


def test_the_token_fallback_is_decided_per_scenario():
    runs = priced("S01", [0.030, 0.010, 0.020]) + [
        run("S02", 1, llm_rows=[llm_row(9, cost=None)])]
    grouped = dashboard.scenario_runs(document(runs))
    assert dashboard.median_key(grouped["S01"]) == "cost_usd"
    assert dashboard.median_key(grouped["S02"]) == "tokens"


def test_median_run_keeps_execution_order_on_a_tie():
    # The tie spans indices 0 and 1: index 1 must be the *later* of the two.
    lower = priced("S01", [0.009, 0.005, 0.005])
    assert dashboard.median_run(lower)["repeat"] == 3
    # The tie spans indices 1 and 2: index 1 must be the *earlier* of the two.
    upper = priced("S01", [0.001, 0.007, 0.007])
    assert dashboard.median_run(upper)["repeat"] == 2
    # Same on the token key, where the tie is exact by construction.
    tied = [run("S03", index, llm_rows=[llm_row(index, prompt=500, completion=50,
                                                cost=None)])
            for index in (1, 2, 3)]
    assert dashboard.median_key(tied) == "tokens"
    assert dashboard.median_run(tied)["repeat"] == 2


def test_median_run_takes_the_upper_middle_of_an_even_count():
    assert dashboard.median_run(priced("S01", [0.004, 0.002]))["repeat"] == 1
    assert dashboard.median_run(priced("S01", [0.002, 0.004]))["repeat"] == 2
    assert dashboard.median_run(priced("S01", [0.005]))["repeat"] == 1
    assert dashboard.median_run([]) is None


def test_timeline_renders_the_median_repeat_of_every_fixture_scenario():
    document_json, markup = render_fixture()
    page = Page(markup)
    grouped = dashboard.scenario_runs(document_json)
    assert set(grouped) == {"S01", "S02", "S03"}
    for scenario, runs in grouped.items():
        assert page.value(f"median-{scenario}") == str(dashboard.median_run(runs)["repeat"])
    # The fixture is built so that the three scenarios exercise all three cases.
    assert page.value("median-S01") == "3"     # cost key
    assert page.value("median-S02") == "1"     # token fallback, one unpriced repeat
    assert page.value("median-S03") == "3"     # tie kept in execution order


def test_timeline_rows_carry_rounds_tokens_latency_and_tool_names():
    entry = run("S04", 1, llm_rows=[
        llm_row(1, rnd=1, prompt=1000, completion=50, latency=400, tool_calls_n=2),
        llm_row(2, rnd=2, prompt=1400, completion=60, latency=500, tool_calls_n=1),
        llm_row(3, purpose="summary", turn=2, prompt=300, completion=20, latency=90),
    ], tool_rows=[
        tool_row(1, tool="exec"), tool_row(2, tool="fetch_url"),
        tool_row(3, tool="exec"), tool_row(4, turn=2, tool="history"),
    ])
    rows = dashboard.timeline_rows(entry)
    assert [row["round"] for row in rows] == [1, 2, 1]
    assert [row["tools"] for row in rows] == [["exec", "fetch_url"], ["exec"], ["history"]]
    assert [row["purpose"] for row in rows] == ["agent", "agent", "summary"]
    assert [row["latency_ms"] for row in rows] == [400, 500, 90]
    page = Page(dashboard.render(document([entry])))
    assert "fetch_url" in page.text["timeline"]
    assert "1400" in page.text["timeline"]


def test_timeline_rows_keep_a_tool_call_the_counts_do_not_explain():
    entry = run("S05", 1,
                llm_rows=[llm_row(1, tool_calls_n=0)],
                tool_rows=[tool_row(1, tool="exec"), tool_row(2, tool="fetch_url")])
    assert dashboard.timeline_rows(entry)[0]["tools"] == ["exec", "fetch_url"]


def test_timeline_marks_a_failed_call_and_the_run_verdict():
    entry = run("S06", 1, success=False, llm_rows=[
        llm_row(1, prompt=900, completion=40),
        llm_row(2, rnd=2, prompt=None, completion=None, error_kind="timeout"),
    ])
    page = Page(dashboard.render(document([entry])))
    assert "timeout" in page.text["timeline"]
    assert "checks" in page.text["timeline"]


def test_context_growth_accepts_the_decoded_object_as_well_as_the_stored_text():
    rows_text = [llm_row(1, by_role={"system": 100, "user": 10}),
                 llm_row(2, rnd=2, by_role={"system": 100, "user": 310})]
    rows_object = [llm_row(1, by_role={"system": 100, "user": 10}, encode=False),
                   llm_row(2, rnd=2, by_role={"system": 100, "user": 310}, encode=False)]
    assert dashboard.timeline_rows(run("S07", 1, llm_rows=rows_object))
    for rows in (rows_text, rows_object):
        page = Page(dashboard.render(document([run("S07", 1, llm_rows=rows)])))
        assert "user +300" in page.text["timeline"]


# --------------------------------------------------------------------------
# #compare
# --------------------------------------------------------------------------

def test_compare_section_shows_both_files_and_their_deltas():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    page = Page(dashboard.render(baseline, candidate))
    section = page.text["compare"]
    assert str(baseline["summary"]["totals"]["prompt_tokens"]) in section
    assert str(candidate["summary"]["totals"]["prompt_tokens"]) in section
    delta = (candidate["summary"]["totals"]["prompt_tokens"]
             - baseline["summary"]["totals"]["prompt_tokens"])
    assert f"{delta:+.0f}" in section
    for scenario in ("S01", "S02", "S03"):
        assert scenario in section
    # The treatment difference the two fixtures encode is named, not hidden.
    assert "HISTORY_TOOL_STUB" in section


def test_compare_keeps_the_half_token_of_an_even_repeat_median():
    """`summary.per_scenario[].median` is `statistics.median`, so two repeats
    average the two middle runs. Truncating 1150.5 to 1150 in the per-scenario
    table would report a number the file does not contain."""
    left = document([run("S01", 1, llm_rows=[llm_row(1, prompt=1000, completion=10)]),
                     run("S01", 2, llm_rows=[llm_row(2, prompt=1301, completion=10)])])
    right = document([run("S01", 1, llm_rows=[llm_row(3, prompt=900, completion=10)]),
                      run("S01", 2, llm_rows=[llm_row(4, prompt=1100, completion=10)])])
    assert left["summary"]["per_scenario"]["S01"]["median"]["prompt_tokens"] == 1150.5
    section = Page(dashboard.render(left, right)).text["compare"]
    assert "1150.5" in section
    assert "-150.5" in section                 # 1000.0 − 1150.5, not a rounded −150
    assert dashboard.fmt(1150.0, "int") == "1150"


def test_compare_tolerates_a_metric_only_one_file_reports():
    left = document([run("S01", 1, llm_rows=[llm_row(1, cost=None)])])
    right = document([run("S01", 1, llm_rows=[llm_row(1, cost=0.01)])])
    section = Page(dashboard.render(left, right)).text["compare"]
    assert "n/a" in section


def test_compare_lists_a_scenario_only_one_file_ran():
    left = document([run("S01", 1)])
    right = document([run("S01", 1), run("S02", 1)])
    section = Page(dashboard.render(left, right)).text["compare"]
    assert "S02" in section and "—" in section


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_cli_writes_the_file_and_reports_the_path(tmp_path, capsys):
    out = tmp_path / "nested" / "dash.html"
    code = dashboard.main([str(BASELINE), "--out", str(out)])
    assert code == 0
    assert "compare" not in Page(out.read_text(encoding="utf-8")).ids
    assert str(out) in capsys.readouterr().out


def test_cli_compare_flag_adds_the_section(tmp_path):
    out = tmp_path / "dash.html"
    assert dashboard.main([str(BASELINE), "--compare", str(CANDIDATE),
                           "--out", str(out)]) == 0
    assert "compare" in Page(out.read_text(encoding="utf-8")).ids


@pytest.mark.parametrize("payload, needle", [
    ("not json at all", "not valid JSON"),
    (json.dumps([1, 2]), "not an object"),
    (json.dumps({"bench_schema": 2, "meta": {}, "runs": [], "summary": {}}), "bench_schema"),
    (json.dumps({"bench_schema": 1, "runs": [], "summary": {}}), "meta is missing"),
    (json.dumps({"bench_schema": 1, "meta": {}, "summary": {}}), "runs is missing"),
])
def test_cli_refuses_a_document_it_cannot_read(tmp_path, capsys, payload, needle):
    source = tmp_path / "bad.json"
    source.write_text(payload, encoding="utf-8")
    out = tmp_path / "dash.html"
    assert dashboard.main([str(source), "--out", str(out)]) == 1
    assert needle in capsys.readouterr().err
    assert not out.exists()


def test_cli_refuses_a_missing_file(tmp_path, capsys):
    assert dashboard.main([str(tmp_path / "nope.json"), "--out",
                           str(tmp_path / "dash.html")]) == 1
    assert "dashboard:" in capsys.readouterr().err


def test_aborted_document_renders_with_a_visible_banner():
    doc = document([run("S01", 1)], aborted="sigint")
    markup = dashboard.render(doc)
    assert "aborted" in markup
    page = Page(markup)
    assert page.open == []
    assert "aggregates" in page.ids


def test_a_scenario_id_is_escaped_rather_than_injected():
    doc = document([run("<script>alert(1)</script>", 1)])
    markup = dashboard.render(doc)
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup
