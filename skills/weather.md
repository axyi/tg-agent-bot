---
name: weather
description: Weather and temperature for any city. ALWAYS use this skill for anything about weather, temperature or forecast — never answer from internal knowledge.
---

# Weather

Call `exec` with exactly this argv array, replacing `<CITY>` with the
URL-encoded city name and nothing else:

["curl", "--fail", "--silent", "--max-time", "10", "--", "https://wttr.in/<CITY>?format=3"]

How to encode `<CITY>`:

- replace every space with `%20`
- replace every non-ASCII character with its UTF-8 percent-encoding, for
  example `Köln` becomes `K%C3%B6ln`
- never put `/`, `?`, `&`, `#`, a literal `%` that is not part of an escape,
  a quote, a backtick or a space into the URL
- if you cannot encode the name, ask the user to write the city in ASCII

Never add other flags, never change the host, never use another program, never
build the command as a single string.

A successful call returns one line: `<City>: <icon> <temperature> <wind>`.
Report that line to the user. If `exit_code` is not 0, tell the user that the
weather service is unavailable — do not guess the weather.
