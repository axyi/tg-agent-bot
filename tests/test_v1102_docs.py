"""spec-v1.10.2 T3 (docs/spec/spec-v1.10.2.md Sec.10, REQ-V1102-RPT-02's T3
half, REQ-V1102-RPT-03's T3 half, REQ-V1102-RPT-04) and REQ-V1101-CFG-01
(`.env.example` routing defaults, carried over from v1.10.1's own T7/T8,
which never ran): `.env.example` now defaults `LLM_PROVIDER` to
`openrouter`; README's release table gains the two stopped-run rows
(`v1.10.0`, `v1.10.1`) but not yet a `v1.10.2` row; `AGENTS.md` gains the
eight-gate count, the benchmark waiver and the `v1102-T<N>` brief-path
token; `docs/reports/report-v1.10.0.md` and `docs/llm-usage.md` row 108 get
a corrective clause (a workflow.md Sec.5.1 deviation disclosed after the
fact).

Offline: reads `.env.example`/README.md/AGENTS.md/the two docs files off
disk; `config.load_config(env=..., load_env_file=False)` only, no network,
no live LLM. The T6 half of RPT-02/RPT-03 (the `v1.10.2` release row, the
pending-table numbers, the two mutation/pytest count lines) is written
separately, at T6 -- not here.
"""

from __future__ import annotations

import re
from pathlib import Path

import dotenv

from config import load_config

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"
_AGENTS_MD = _REPO_ROOT / "AGENTS.md"
_README_MD = _REPO_ROOT / "README.md"
_REPORT_V1100 = _REPO_ROOT / "docs" / "reports" / "report-v1.10.0.md"
_LLM_USAGE = _REPO_ROOT / "docs" / "llm-usage.md"


def _read_agents_md() -> str:
    return _AGENTS_MD.read_text(encoding="utf-8")


def _read_readme() -> str:
    return _README_MD.read_text(encoding="utf-8")


def _normalize(text: str) -> str:
    """Collapse whitespace runs -- both AGENTS.md and the reports wrap prose,
    so a multi-line-sentence substring check does not fail merely because
    the real text line-wraps (tests/test_v190_agents.py's own pattern)."""
    return re.sub(r"\s+", " ", text)


# ---------------------------------------------------------------------------
# T-V1102-CFG-01 (REQ-V1101-CFG-01, never landed as a test at v1.10.1 --
# tests/test_v1101_config.py's T-V1101-CFG-03, per the task brief): loading
# .env.example through load_config(), the token/id/key fields stubbed with
# placeholder strings the same shape tests/test_config.py's base_env uses.
# ---------------------------------------------------------------------------


def _env_example_config():
    values = dotenv.dotenv_values(_ENV_EXAMPLE)
    source = {k: v for k, v in values.items() if v is not None}
    source.update(
        TELEGRAM_BOT_TOKEN="123456789:sentinel-v1102-cfg-01-token",
        ALLOWED_TG_IDS="424242",
        OPENROUTER_API_KEY="SYNTHETIC-V1102-CFG-01-CANARY-OPENROUTER-KEY",
    )
    return load_config(env=source, load_env_file=False)


def test_t_v1102_cfg_01_env_example_defaults_to_openrouter():
    cfg = _env_example_config()
    assert cfg.llm_provider == "openrouter"
    assert cfg.lmstudio_model == ""
    # Not asserted: cfg.lmstudio_base_url == "" -- config.py:341's own
    # built-in default ("http://localhost:1234/v1") substitutes for an
    # empty LMSTUDIO_BASE_URL regardless of the active provider.
    for routed in (
        cfg.llm_summary_model,
        cfg.llm_rerank_model,
        cfg.llm_eval_chat_model,
        cfg.llm_judge_model,
    ):
        assert not routed.startswith("lmstudio:"), routed


# ---------------------------------------------------------------------------
# T-V1102-RPT-02 (T3 half): the two stopped-run release rows land verbatim.
# v1.10.3 T4 (REQ-V1103-VER-01) amends this test in place: the v1.10.2 row
# (added at v1.10.3 T4) now also lands verbatim here, no v1.10.3 row yet
# (T7's job).
# ---------------------------------------------------------------------------

_V1100_ROW = (
    "| v1.10.0 | — | run stopped at T9 by the stop route, gate 8 red on "
    "model behaviour (injection 2/5, hallucination 2/4 on "
    "lmstudio:qwen/qwen3.8-27b), not tagged; the implemented suite ships "
    "with v1.10.2 |"
)
_V1101_ROW = (
    "| v1.10.1 | — | run stopped at T6 by the stop route, gate 8 red on "
    "model behaviour (injection 1/5 on openai/gpt-4.1-mini — three "
    "clause-(e) misses, the prompt gap v1.10.2 closes), not tagged; "
    "every live gate moved onto OpenRouter; ships with v1.10.2 |"
)


_V1102_ROW = (
    "| v1.10.2 | — | run stopped at T5 by the stop route, gate 8 red on "
    "model behaviour (injection 4/5 on openai/gpt-4.1-mini — INJ-04's "
    'developer-mode pretext produced exec("printenv") ×3 before a refusal; '
    "the Secrets: line held the other four), not tagged; ships with "
    "v1.10.3 |"
)

_V1103_ROW = (
    "| v1.10.3 | — | run stopped at T6 by the stop route — EC-01's repair "
    "budget spent on four test pins the spec's list missed; gate 8 never "
    "ran; the exec guard, the marker widening, the delegation lint and the "
    "paperwork landed; ships with v1.10.4 |"
)


def test_t_v1102_rpt_02_stopped_release_rows_landed_at_t3():
    text = _read_readme()
    assert _V1100_ROW in text
    assert _V1101_ROW in text
    assert "not tagged" in _V1100_ROW
    assert "not tagged" in _V1101_ROW
    # v1.10.3 T4 (REQ-V1103-VER-01): strengthened from "no v1.10.2 row yet"
    # to "the v1.10.2 row landed verbatim and no v1.10.3 row exists yet" --
    # same intent (pin the release table's leading edge), stronger pin.
    v1102_row = next(
        (line for line in text.splitlines() if line.strip().startswith("| v1.10.2 |")),
        None,
    )
    assert v1102_row == _V1102_ROW
    # v1.10.4 T1 (EC-02 row 6, REQ-V1104-PIN-01, REQ-V1104-VER-01): the
    # "and no v1.10.3 row exists yet" absence pin is exactly the shape that
    # stopped v1.10.3 -- replaced with a presence check for the row VER-01
    # actually adds this task; nothing is asserted absent.
    assert _V1103_ROW in text


# ---------------------------------------------------------------------------
# T-V1102-RPT-03 (T3 half): AGENTS.md's eight-gate count, the benchmark
# waiver sentence and the v1102-T<N> brief-path token.
# ---------------------------------------------------------------------------


def test_t_v1104_rpt_03_agents_md_brief_path_token_is_v1104():
    text = _read_agents_md()
    normalized = _normalize(text)
    assert "All eight MUST exit 0" in text
    assert "All seven MUST exit 0" not in text
    assert (
        "v1.10.1 waived this rule by operator decision — the provider, the "
        "model and `prompt_tools_sha256` all changed, so no run was "
        "comparable to the LM Studio baseline"
    ) in normalized
    assert "v1.10.2 carries the waiver: its prompt change moves the hash again" in normalized
    assert "docs/spec/task-briefs/v1104-T<N>.md" in text
    assert "docs/spec/task-briefs/v1103-T<N>.md" not in text


# ---------------------------------------------------------------------------
# T-V1102-REV-01 (T4): regression guard -- REV-01's gate-5 contradiction
# (the bolded clause named "every provider the configuration routes to"
# while the tail sentence still hard-required LM Studio) must not come back.
# ---------------------------------------------------------------------------


def test_t_v1102_rev_01_agents_md_gate5_tail_no_longer_hard_requires_lm_studio():
    text = _read_agents_md()
    assert "an unreachable LM Studio is a blocked run" not in text


# ---------------------------------------------------------------------------
# T-V1102-RPT-04: the report-v1.10.0.md T6 clause and the llm-usage.md row
# 108 correction, both disclosing the same 2026-09-17 §5.1 deviation.
# ---------------------------------------------------------------------------


def test_t_v1102_rpt_04_report_v1100_t6_line_and_usage_row_108_corrected():
    report_text = _normalize(_REPORT_V1100.read_text(encoding="utf-8"))
    assert (
        "— **not delegated: a deviation from `standards/workflow.md` §5.1, "
        "recorded on 2026-09-17 by v1.10.2 T3; `docs/llm-usage.md` row 108 "
        "corrected to match**"
    ) in report_text

    usage_text = _LLM_USAGE.read_text(encoding="utf-8")
    row_108 = next(line for line in usage_text.splitlines() if line.startswith("| 108 |"))
    assert "Not delegated (a §5.1 deviation, recorded by v1.10.2 T3)." in row_108
