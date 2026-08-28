---
name: host-info
description: Facts about the machine the bot runs on — kernel and OS version, disk usage, uptime and load average. Use this skill for any question about the bot's host, server or machine.
---

# Host info

Call `exec` with exactly these argv arrays, one call per question:

- kernel and OS version: ["uname", "-a"]
- disk usage:            ["df", "-h"]
- uptime and load:       ["uptime"]

Use at most one array per tool call. Report the command output to the user in
plain text; never invent values that were not in the output.
