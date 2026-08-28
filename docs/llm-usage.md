# LLM usage

| # | Stage | Model | Tokens | Cost |
|---|-------|-------|--------|------|
| 1 | spec authoring (writer agent, 3 iterations incl. gate-chain and exec-recipe proof runs) | claude (lab session) | ~213k (harness-reported aggregate; in/out split not exposed) | — (flat-rate session) |
| 2 | spec review (reviewer agent, clean context, 3 passes) | claude (lab session) | ~270k (aggregate) | — |
| 3 | implementation step 1 — bootstrap: `.python-version`, `pyproject.toml`, `.gitignore`, `.env.example`, `uv lock`, `uv sync --locked` | claude-opus-5 | unknown | unknown |
| 4 | implementation step 2 — all test files, `conftest.py`, `fakes.py`; first `pytest` run observed failing | claude-opus-5 | unknown | unknown |
| 5 | implementation step 3 — `config.py` | claude-opus-5 | unknown | unknown |
| 6 | implementation step 4 — `storage.py` | claude-opus-5 | unknown | unknown |
| 7 | implementation step 5 — `tools.py` part 1 (`run_command`, `_Capture`, `_drain`) | claude-opus-5 | unknown | unknown |
| 8 | implementation step 6 — `tools.py` part 2 (skills, tool specs, dispatch) + `skills/*.md` | claude-opus-5 | unknown | unknown |
| 9 | implementation step 7 — `llm/base.py`, `llm/lmstudio.py`, `llm/openrouter.py`, `llm/__init__.py` | claude-opus-5 | unknown | unknown |
| 10 | implementation step 8 — `agent.py` | claude-opus-5 | unknown | unknown |
| 11 | implementation step 9 — `bot.py` (Telegram layer, poll loop, `--selftest`) | claude-opus-5 | unknown | unknown |
| 12 | implementation step 10 — `README.md`, prompt log, this table | claude-opus-5 | unknown | unknown |
| 13 | implementation step 11 — the four acceptance gates + code review | claude-opus-5 | unknown | unknown |
| **Σ** | | | unknown for rows 3–13 | unknown |

Notes: rows 1–2 are the authoring cost of the specification, recorded per
the lab reporting standard; runtime data and secrets are never logged here.
Rows 3–13 are the implementation run (`go docs/spec/spec-v0.md`, prompt
`docs/prompts/01-go-spec-v0.md`), one row per stage of the spec's section 4
implementation order. The run executed as one continuous agent session; the
harness does not expose per-request input/output token counts or money cost to
the agent, so those cells are `unknown` rather than estimated. The table keeps
its original five columns — the spec's REQ-EC-11 names a six-column variant
(`Tokens in` / `Tokens out`), but the instruction to keep the existing columns
takes precedence over the parenthetical.
