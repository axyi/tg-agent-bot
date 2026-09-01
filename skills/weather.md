---
name: weather
description: Weather and temperature for any city. ALWAYS use this skill for anything about weather, temperature or forecast — never answer from internal knowledge.
---

# Weather

Call the `fetch` tool with exactly this URL, replacing `<CITY>` with the
URL-encoded city name and nothing else:

https://wttr.in/<CITY>?format=3

How to encode `<CITY>`:

- replace every space with `%20`
- replace every non-ASCII character with its UTF-8 percent-encoding, for
  example `Köln` becomes `K%C3%B6ln`
- never put `/`, `?`, `&`, `#`, a literal `%` that is not part of an escape,
  a quote, a backtick or a space into the city part
- if you cannot encode the name, ask the user to write the city in ASCII

Never change the host, never add other query parameters, never use `exec`
for this — the exec sandbox has no network access.

A successful fetch returns one line in `body`:
`<City>: <icon> <temperature> <wind>`. Report that line to the user. If the
envelope contains an error or a non-200 `status_code`, tell the user that
the weather service is unavailable — do not guess the weather.
