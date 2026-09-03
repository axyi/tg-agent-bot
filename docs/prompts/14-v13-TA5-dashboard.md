# Prompt 14 — v1.3 TA5: static HTML dashboard (stage A)

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Model reason:** inherits spec-v1.3's claude-opus-5 pin for this run (docs/llm-usage.md row 31); same judgment rationale as prompt 09, applied to this task.
- **Owner of:** `devtools/dashboard.py` (new), `tests/test_dashboard.py` (new)
- **REQ ids:** REQ-V13-DSH-01, REQ-V13-DSH-02

## Brief as sent

```
Repo: /home/akh/aihome/coders-su/projects/tg-agent-bot (Python 3.13, uv, stdlib
only). Read docs/spec/spec-v1.3.md section 8 (REQ-V13-DSH-01..02) and the
section 7.4 schema — that is your contract.
One self-contained HTML file: inline CSS, no JavaScript required for reading,
no external resources at all. Sections #aggregates, #cache, #tools, #timeline,
and #compare only with --compare. Reuse metrics.py where it already computes a
value; input is benchmark JSON only.
The #timeline median-run rule is exact: a scenario's runs sorted ascending by
totals.cost_usd, or by prompt+completion tokens when any run's cost_usd is
null, stable on execution order, element at index n // 2. Test both keys and a tie.
Use the fixtures in tests/fixtures/bench/ that TA4 created.
Do NOT touch: devtools/bench.py, devtools/bench_scenarios.py, or any application
source. NEVER open .env. Gates: ruff check . and pytest green.
Return a <=15-line summary: sections implemented, tests added, gates.
Never paste file contents.
```
