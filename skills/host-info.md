---
name: host-info
description: Facts about the isolated Linux container the bot's exec tool runs in — kernel version, disk usage of the sandbox, Python version. Use this skill for any question about the bot's runtime environment.
---

# Host info

Commands run in a disposable container, not on the bot's real host. Call
`exec` with exactly these argv arrays, one call per question:

- kernel version:          ["uname", "-a"]
- sandbox disk usage:      ["df", "-h", "/work"]
- Python version:          ["python3", "--version"]

Use at most one array per tool call. Report the command output to the user
in plain text; never invent values that were not in the output.
