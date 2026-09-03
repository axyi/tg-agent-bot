@AGENTS.md

# RTK — token-optimized command output

A `PreToolUse` hook in this repository's own `.claude/settings.json`
(`rtk hook claude`) rewrites every Bash command to its `rtk` equivalent
automatically — in the main context and in subagents — so commands are
written plainly (`git status`, `pytest`, `ls`); a dedicated filter kicks
in when one exists, transparent passthrough otherwise (also inside
`&&`-chains). Do NOT hand-prefix `rtk`.

Meta commands (used directly): `rtk gain` — measured savings; `rtk proxy
<cmd>` — bypass filtering; `rtk err|log|json|summary <x>` — explicit
filters. On failure rtk saves the full untrimmed output under
`~/.local/share/rtk/tee/` and prints the path. Telemetry consent was
never granted — NEVER enable it (`rtk telemetry status` must stay
`consent: never asked`).
