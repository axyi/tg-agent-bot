# tg-agent-bot — implementation specification v1.2 (patch: second-audit findings)

This document is the complete contract for a **patch release** on top of the
implemented spec-v1.1 state. It is a **delta specification**: spec-v0, spec-v1
and spec-v1.1 remain in force except where a requirement here explicitly
**amends**, **supersedes** or **extends** them (section 2 is the authoritative
amendment table). Everything needed to implement, test and accept the work is
in this file, in the earlier specs, or in files this spec tells you to change.
Do not look for other sources.

Every requirement has a stable `REQ-V12-*` id and is tagged `MUST` or
`NON-GOAL`. v1.2 ids never collide with v0, v1 or v1.1 ids. `MUST` = required
for acceptance. `NON-GOAL` = out of scope; implementing it is a defect, not a
bonus.

Target platform: **Linux only**. Language: **Python**. Package manager: **uv**.

Executor model for this run: **claude-sonnet-5**. This is a deliberate choice,
not a cost compromise. The v1.1 audit ran 83 mutation probes against the
delivered code and found **zero** defects where the implementation disagreed
with its specification: the executor was precise. Every finding below traces
to a gap in the *spec text*, not to sloppy implementation. The difficulty of
this release therefore lives in the requirements you are reading, and it has
already been paid for — a larger model is not needed and must not be
substituted for reading this spec less carefully.

**This is a patch release.** Behaviour changes only where a requirement below
says so. No new features, no refactoring beyond what a listed fix requires, no
opportunistic cleanups. Every v0/v1/v1.1 acceptance property must still hold
when you are done.

Provenance: the defect list comes from two independent post-implementation
audits of the delivered v1.1 (commit `b61b186`), both run in clean contexts:

- an **adversarial security probe** that exercised the running system against a
  real Docker daemon (findings W-1 … W-8);
- a **spec-compliance review** with 83 mutation probes, of which 23 survived
  (findings G-1 … G-9) — a surviving mutation is a place where the suite
  cannot tell correct code from broken code.

Both audits agree on the headline result: the v1.1 patch **worked**. Secret
truncation is closed across 197 probed offsets, containers no longer outlive
the bot, the exec sandbox still yields nothing when attacked, and — the fix
that mattered most — `pytest` no longer touches a live Docker daemon
(verified: a logging `docker` shim on `PATH` recorded zero invocations across
the whole suite). The findings below are the residue, plus one systemic
problem: three mitigations are correct *by the letter of their requirement*
and still bypassable in practice, because the requirement described a
mechanism instead of a property.

Appendix A maps every finding to requirements.

---

## 1. Execution contract

**REQ-V12-EC-01 (MUST)** All of spec-v0 section 1, spec-v1 section 1 and
spec-v1.1 section 1 apply to this run unchanged, with these adjustments:

- "The gate commands" means the **six** commands of section 11 of this spec —
  the five of v1.1 plus the mutation gate.
- The repair budget is **5 total** repair-and-rerun cycles (one cycle = one fix
  + one complete run of all gates from the first).
- REQ-V1-EC-01's absolute rule stands: the executor reads and writes **nothing
  outside the repository root**, without exception.
- The Python dependency set is unchanged and MUST stay unchanged: `httpx`,
  `python-dotenv`. The `docker` CLI remains an external host dependency.
  Everything this spec adds uses the standard library (`ipaddress`, `os`, `re`,
  `shutil`, `signal`, `socket`, `subprocess`).

**REQ-V12-EC-02 (MUST)** Work test-first: write the new and corrected tests of
section 10 first, observe them fail for the right reason, then implement in the
order of section 9.

For every requirement in sections 5 and 6 the corresponding test MUST be proven
to detect the defect: temporarily break the production line the way section 8's
mutation entry describes, confirm the test goes red, restore, confirm green.
From this release on that proof is **mechanised** — section 8's
`devtools/mutation_check.py` is exactly this loop, and it is gate 6. Running it is
the evidence; the report records its output, not a hand-written table.

**REQ-V12-EC-03 (MUST)** The v1.1 test suite is 251 passing tests. No test may
be deleted. Tests may be **modified only** where section 10.1 lists them.
Section 10.1 is exhaustive; changing any other existing test is a defect. When
a change makes an unlisted test fail, that is a signal the change is wrong —
stop and reconsider, do not edit the test.

**REQ-V12-EC-04 (MUST)** Secrets discipline is unchanged (REQ-V1-EC-04,
REQ-V11-EC-04): credential **values** are never printed, logged, committed or
quoted in `docs/`. Presence checks are by key **name** only. Tests use the
existing synthetic sentinel pattern, never a real credential.

**REQ-V12-EC-05 (MUST)** Backward compatibility, same rule as REQ-V1-EC-05 and
REQ-V11-EC-05: every new parameter, config field and helper introduced here has
a default that reproduces current behaviour when absent, so unlisted tests and
fakes keep passing. Where that is impossible — the tool-call identifiers of
REQ-V12-ID-01 change observable values — the affected tests are named in
section 10.1 and nowhere else.

---

## 2. Amendments to spec-v0 / spec-v1 / spec-v1.1 — authoritative table

**REQ-V12-AMEND-01 (MUST)** Apply exactly these changes. Requirements not
listed here stay in force verbatim.

| id | Status in v1.2 | Replacement / change |
|---|---|---|
| REQ-V11-RED-01 | amended | its clause "ids, names and shape are preserved byte-for-byte" is **withdrawn**: model-authored identifiers are no longer trusted or stored. The bot mints its own `tool_call_id` and validates `function.name` (REQ-V12-ID-01, REQ-V12-ID-02). The four storage guards stay exactly as delivered |
| REQ-V11-QTA-02 | amended | `sandbox_usage` reports a tri-state scan status and fails closed on an unreadable subtree; the cut-short case gets its own message and audit outcome (REQ-V12-QTA-01, REQ-V12-QTA-02) |
| REQ-V11-QTA-03 | extended | the post-run record distinguishes "over quota" from "scan incomplete" (REQ-V12-QTA-02) |
| REQ-V11-CFV-01 | extended | entry syntax is validated strictly, the allowlist is resolved once at startup, and the resolved address is checked again at request time (REQ-V12-SSR-01 … REQ-V12-SSR-03) |
| REQ-V11-INF-01 | amended | the empty resolv file is created with `O_NOFOLLOW`/`O_TRUNC` and verified to be a regular empty file; a world-writable parent directory is refused (REQ-V12-INF-01) |
| REQ-V11-ORP-02 | amended | the reap is ownership-aware: it removes only containers whose owning bot process is gone (REQ-V12-ORP-02). The single-instance assumption of v1.1 is thereby lifted for *safety*, though multi-instance operation stays a non-goal |
| REQ-V11-ORP-01 | extended | every container carries a second label naming its owner (REQ-V12-ORP-01) |
| REQ-V11-ORP-03 | extended | with the wrapper active, exit **137** maps to `timed_out: true` as well as 124 (REQ-V12-ORP-03) |
| REQ-V11-ORP-04 | amended | the probe container is named and labelled like any other, so it can never become an unreapable orphan (REQ-V12-ORP-04) |
| REQ-V1-AUD-01 | extended | the audit **hook** receives an already-redacted record, not only the file writer (REQ-V12-AUD-01) |
| REQ-V1-AUD-02 | extended | the exec audit record gains `sandbox_scan` (REQ-V12-QTA-02) |
| REQ-V1-CFG-02 | extended | new variable `EXEC_SANDBOX_CLEAN_ON_START` (REQ-V12-QTA-03) |
| REQ-V1-CFG-04 | extended | `.env.example` gains that variable with its default |
| REQ-V11-WIR-01 | extended | the seam additionally performs the startup sandbox cleanup (REQ-V12-QTA-03) and the allowlist resolution check (REQ-V12-SSR-02); its contract — no subprocess, no file system side effect when `docker_ok` is false — is unchanged for the docker-dependent parts |
| REQ-V1-ST-01 (`--selftest`) | amended | `_selftest_failure` checks identifier **pairing** instead of the literal `call_1` (REQ-V12-ID-04) |
| `tests/conftest.py` offline guard | extended | DNS is barred as well as HTTP (REQ-V12-OFF-01) |
| `AGENTS.md` gate list | amended | six commands, updated in the same commit as the gate itself (REQ-V12-GATE-01) |
| REQ-V11-GATE-01 | superseded | six gates, not five (REQ-V12-GATE-01) |
| REQ-V11-REP-01 | extended | at least two commits, and the Deviations section MUST list process deviations, naming how live scenarios were driven (REQ-V12-REP-01, REQ-V12-REP-02) |
| REQ-V11-TST-03 companion `T-V11-TRN-03` | amended | made non-vacuous: the body must arrive in chunks so the cut really lands inside the secret (REQ-V12-TST-01) |
| `normalize_tool_calls` call sites in `tests/test_agent.py` | amended | expected ids follow REQ-V12-ID-01 (section 10.1) |

Everything else in v0/v1/v1.1 — the Docker isolation posture, the redaction
choke points, truncation headroom, failover, structured memory, commands, rate
limiting, the error matrix, the token budget — is unchanged and MUST keep
working.

---

## 3. Preconditions (verify before writing any code)

**REQ-V12-PRE-01 (MUST)** Verify each item; on failure stop and emit the
blocker template (v0 section 7.2) instead of guessing.

1. Repository state: branch `main`, clean tree, HEAD at the delivered v1.1
   (`docs/spec/spec-v1.1.md` and `docs/reports/report-v1.1.md` both present).
2. All five v1.1 gates green **before** you change anything. A gate that is
   already red is a blocker, not something to fix silently inside this run.
   Exception, and the only one: gate 5's `lmstudio` check depends on a host
   outside this repository. If it fails **solely** because LM Studio is
   unreachable, record that and proceed — every other check of gate 5 must
   still be green.
3. Provisioned credentials: the git-ignored `.env` exists at the repository
   root and contains `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_NAME`,
   `ALLOWED_TG_IDS`, `LLM_PROVIDER`, `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`,
   `LMSTUDIO_CONTEXT_LENGTH`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`.
   Validate **presence by key name only**. Reading a value programmatically is
   expected; printing or displaying a secret value is forbidden. Do not create
   or overwrite `.env`.
4. Docker: `docker version` succeeds without `sudo`; the sandbox image is
   present locally (`docker image inspect`) — exec never pulls at request time.
5. `python3 -c "import shutil, socket, ipaddress"` — all stdlib, no install.

---

## 4. Required file tree (delta)

**REQ-V12-TREE-01 (MUST)** New files:

```
devtools/__init__.py                 # package marker (see the naming note below)
devtools/mutation_check.py           # the mutation gate (REQ-V12-MUT-01)
tests/test_v12_patch.py              # every new test of section 10.2
tests/test_mutation_check.py         # the gate's own safety tests (REQ-V12-MUT-03)
docs/prompts/07-go-spec-v1.2.md      # this run's go prompt
docs/prompts/08-code-review-v1.2.md
docs/reports/report-v1.2.md
docs/reports/tg-post-v1.2.md
```

**Prompt numbering, fixed to avoid a collision:** `07` is the `go` prompt that
starts this run, `08` is this run's code-review prompt. Use exactly these.

`devtools/` is linted like the rest of the tree: gate 2 (`ruff check .`) covers
it, so it follows the project's existing style rather than sitting in an
exclude list.

Changed files: `config.py`, `storage.py`, `agent.py`, `tools.py`, `bot.py`,
`.env.example`, `README.md`, `docs/llm-usage.md`, `docs/plan.md`,
`docs/reports/report-v1.1.md`, `docs/reports/tg-post-v1.1.md`, plus exactly the
test files named in section 10.1.

`devtools/` is a **new directory** and the one exception to "no new modules"
(REQ-V11-NG-06): the mutation gate is a developer tool, not part of the bot. It
MUST NOT be imported by any production module.

**The name is not negotiable and the reason is mechanical.** A directory named
`tools/` would shadow the existing top-level module `tools.py`: with an
`__init__.py` the package wins the import, and `bot.py`, `agent.py` and the
whole suite fail at import time. Do not "fix" that by omitting `__init__.py` —
the collision must not depend on anyone's discipline. `devtools/` carries an
`__init__.py`; the test imports it as `devtools.mutation_check`.

---

## 5. Security fixes

### 5.1 The bot must not trust model-authored identifiers (finding W-1)

v1.1 closed the content and argument legs of the redaction hole and explicitly
licensed the remaining one: *"ids, names and shape are preserved byte-for-byte,
because the provider matches `tool_call_id` against them."* That reasoning is
wrong in one respect that matters: **the id is authored by the model**, so it
is an attacker-controlled channel, and `normalize_tool_calls` keeps it whenever
it is non-empty and unique.

The adversarial probe demonstrated the full chain: a sentinel placed in
`tool_call_id` reached the raw bytes of `bot.db`, survived a restart, and was
replayed by `load_context_messages` into **every** subsequent request payload —
under OpenRouter, to a third party. `function.name` takes the same path.

Redacting the identifier is the wrong fix: two secrets would collapse to the
same placeholder and break the pairing the provider needs. The right fix is to
stop carrying the model's string at all.

**REQ-V12-ID-01 (MUST)** The bot mints its own tool-call identifiers.

1. `storage.py` gains `next_turn_id(conn, conv_id) -> int`, a public alias of
   the existing `_next_turn_id`. It is a pure read (`MAX(turn_id) + 1`) and is
   therefore safe to call before `add_tool_turn` allocates the same value; no
   row is inserted between the two calls in a round.
2. `agent.normalize_tool_calls` takes a keyword-only `turn_id: int = 0` and
   assigns **every** kept call the identifier

   ```python
   f"call_{turn_id}_{index}"
   ```

   where `index` is the zero-based position among the kept calls. The model's
   `raw.id` is discarded unconditionally — not inspected, not compared, not
   used as a fallback. The uniqueness bookkeeping of v1 (`seen`, the `auto_`
   fallback, the trailing-underscore loop) is deleted: minted ids are unique by
   construction.
3. `run_agent` calls `storage.next_turn_id(conn, conv_id)` **inside the round
   loop, immediately before `normalize_tool_calls`** — never once before the
   `while`. Each round writes a turn, so the value advances per round; hoisting
   the call would mint `call_<T>_0…` again in round two, put duplicate ids in
   one payload and break REQ-V12-ID-03. Because `turn_id` is monotonic per
   conversation, an id minted this way can never collide with one restored from
   an earlier turn in the same payload — which a round-local counter would.
4. `function.name` is validated before it is stored or sent: a name outside the
   advertised tool set is replaced with the fixed string `"unknown"`. There is
   no dispatch *table* to consult — `execute_tool` is an if/elif chain — so the
   source of truth is the specs the bot itself advertises:
   `{spec["function"]["name"] for spec in tool_specs()}`, computed once at
   module level or per call, never a hand-copied literal list. Dispatch
   behaviour is unchanged (an unknown tool already produces the "unknown tool"
   envelope); only the recorded and transmitted text changes.

**REQ-V12-ID-04 (MUST)** `bot._selftest_failure` stops pinning the literal
identifier. It asserts twice that the stored id is exactly `"call_1"` — the
value the selftest's scripted model happens to emit — which REQ-V12-ID-01
replaces with a minted one, turning gate 4 and `tests/test_selftest.py` red.
Replace both checks with the properties they were standing in for:

- the assistant call and the tool row share one identifier
  (`calls[0]["id"] == tool_rows[0]["tool_call_id"]`);
- `calls[0]["function"]["name"] == "exec"`.

The failure strings are reworded to match ("the stored tool call and its result
do not share an identifier"). A selftest that pins a value the bot now chooses
for itself tests the scripted fake, not the bot.

**REQ-V12-ID-02 (MUST)** `_redact_tool_calls`'s docstring is corrected: it
redacts `function.arguments`; ids and names are safe because they are minted
and validated upstream, **not** because they are trusted. The helper itself is
unchanged.

**REQ-V12-ID-03 (MUST)** Pairing must survive. The assistant message's
`tool_calls[i].id` and the following `{"role": "tool", "tool_call_id": …}`
message MUST carry the same minted value, in the payload and in the database,
and `load_context_messages` MUST reproduce that pairing after a restart. This
is what the provider matches on; a mismatch is a functional regression, not a
cosmetic one.

### 5.2 The sandbox quota must not be bypassable (finding W-4)

`sandbox_usage` walks with `os.walk(path, followlinks=False)` and **no**
`onerror` handler, so every traversal error is silently discarded. The probe
exploited it in three commands: `mkdir` a subdirectory, write 20 MiB into it,
`chmod 000` it. The scan then reports zero, the quota never fires, and the
cycle repeats — 60 MiB written against a 10 MiB limit, every exec permitted.
The model owns the directory, so it can restore the mode later and read its own
data back.

Separately, the cut-short path lies to the operator: it reports
`sandbox is full: 0 bytes of 10485760 allowed`, a sentence that is false on its
face and gives no hint that the real problem is the file *count*.

**REQ-V12-QTA-01 (MUST)** `tools.sandbox_usage(path: Path) -> tuple[int, str]`
returns the total size of regular files and a **scan status**, one of the three
module constants:

```python
SCAN_OK = "ok"
SCAN_CUT_SHORT = "cut_short"      # entry limit reached
SCAN_INCOMPLETE = "incomplete"    # a subtree could not be read
```

- The walk passes `onerror=` a handler that records `SCAN_INCOMPLETE` and
  returns; an `OSError` on an individual `os.lstat` does the same instead of
  being skipped silently. Any unreadable part of the tree means the total is a
  lower bound, and a lower bound MUST NOT be used to permit a run.
- The entry limit (`SANDBOX_SCAN_MAX_ENTRIES = 200000`) still yields
  `SCAN_CUT_SHORT`.
- A missing directory still returns `(0, SCAN_OK)`, so the pre-existing
  `{"error": "sandbox directory is missing"}` check of `_run_process` keeps
  firing first and `test_missing_sandbox_is_reported_before_docker_runs` stays
  green unchanged.
- `SCAN_INCOMPLETE` wins over `SCAN_CUT_SHORT` when both occur.

**REQ-V12-QTA-02 (MUST)** Fail closed, and say which failure it is.
`run_command_docker` refuses to start a container when the status is not
`SCAN_OK` **or** the usage is at or above the limit, with three distinct
envelopes:

| condition | envelope `error` | log |
|---|---|---|
| `used >= limit`, status `SCAN_OK` | `sandbox is full: <used> bytes of <limit> allowed; ask the operator to clear the sandbox directory` | — |
| status `SCAN_CUT_SHORT` | `sandbox holds too many files to measure (over 200000 entries); ask the operator to clear the sandbox directory` | `WARNING sandbox scan hit the entry limit` |
| status `SCAN_INCOMPLETE` | `sandbox size could not be measured; ask the operator to inspect the sandbox directory` | `WARNING sandbox scan could not read part of the tree; refusing` |

The audit record gains `"sandbox_scan": "<status>"` alongside the existing
`sandbox_over_quota`, plumbed the same way (`run_command_docker` sets it on the
returned dict, `_run_exec` **pops** it into the record before the envelope is
built). The success envelope's key set MUST stay byte-for-byte the v1 set: an
internal bookkeeping key must never reach the model.

**The key is set only when the status is not `SCAN_OK`** — never as an
`"ok"` value, exactly mirroring the convention the delivered code already uses
for `sandbox_over_quota` and that
`test_t_v11_qta_03_run_command_docker_omits_key_when_under_quota` pins.
`_run_exec` reads it with a default (`payload.pop("sandbox_scan", SCAN_OK)`).
After a completed run `_record_sandbox_quota` applies the same rule to the
post-run status.

This is not a stylistic choice. Five delivered assertions compare the runner's
**whole** return value against an exact key set — `tests/test_docker.py` for
the unavailable backend (dict equality), for the missing sandbox, and twice for
docker exit 125/126/127 (`set(result) == {"error"}`), plus the same equality in
`tests/test_v1_guardrails.py`. None of them is in section 10.1, and section
10.1 is exhaustive: a key added unconditionally would force an executor to
either edit unlisted tests or stop. Under this rule all five stay byte-for-byte
green, and REQ-V12-QTA-01's promise that
`test_missing_sandbox_is_reported_before_docker_runs` "stays green unchanged"
stops contradicting this section.

Accepted cost, stated so no one reads the audit log wrongly: an absent
`sandbox_scan` means "the scan found nothing worth reporting **or** no scan
ran". The distinction is not recoverable from the log, and it is not worth
buying at the price of five broken invariants.

**REQ-V12-QTA-03 (MUST)** Give the operator an automatic way out. The probe
created 50 000 files in 2.7 seconds, so the 200 000-entry limit is reachable
inside a single 30-second exec: a model can disable `exec` for the rest of the
bot's life at will, and today only a manual `rm -rf` restores it.

New configuration variable `EXEC_SANDBOX_CLEAN_ON_START`, parsed like the other
booleans, default **`true`**, joining `Config` as `exec_sandbox_clean_on_start`
and `.env.example` with a one-line comment. When true, the REQ-V11-WIR-01 seam
empties the sandbox directory at startup — every entry inside it removed
(`shutil.rmtree` per child directory, `os.unlink` per file), the directory
itself kept with its mode — and logs
`INFO cleared N entr(y|ies) from the sandbox at startup`. Failures are logged
at WARNING and never prevent startup.

**The cleanup MUST survive an unreadable subtree**, or it does not solve the
problem it was written for. The W-4 attack ends with a `chmod 000`
subdirectory, and a plain `shutil.rmtree` fails on exactly that — leaving the
sandbox over quota forever, `exec` refused forever, and this requirement's
README line ("emptied on every start") a falsehood. Pass an error handler
(`onexc=`, or `onerror=` on the older signature) that chmods the offending path
to `u+rwX` and retries the operation once; if the retry also fails, log
`WARNING could not clear <path> from the sandbox; clear it by hand` and
continue. The chmod succeeds because the bot owns those entries — the container
ran as the bot's own uid. `README.md` states the manual fallback for the case
where even that fails.

This step runs **regardless of `docker_ok`**: it touches only the local
filesystem, spawns no subprocess, and a sandbox left full by a previous run
must be recoverable even while Docker is down. It is therefore placed in the
seam *before* the `docker_ok` early return.

`T-V11-WIR-01`'s two tests keep passing **unchanged**, and that is a constraint
on your implementation, not a coincidence to verify afterwards. The
`docker_ok=False` test monkeypatches `bot.subprocess.run` to fail on any call
and asserts that `.resolv-empty` is not created; the cleanup therefore MUST use
`shutil`/`os` directly (never a subprocess) and MUST NOT create the resolv file
on that path. Section 10.1 lists both tests as unchanged-and-must-stay-green.

`README.md` MUST state plainly: **the sandbox is scratch space and is emptied
on every start by default**; anything a previous run left there is deleted; set
`EXEC_SANDBOX_CLEAN_ON_START=false` to keep it, accepting that a sandbox filled
past the quota then stays broken until cleared by hand.

### 5.3 The fetch allowlist must resist shortened addresses (finding W-6)

`_reject_ssrf_shaped_domain` rejects an entry when `ipaddress.ip_address()`
parses it — and that function is strict. `127.1`, `127.0.1`, `0x7f.1` and
`0x7f.0.0.1` do not parse, contain a dot, and are therefore accepted as
"ordinary domains". `getaddrinfo` then resolves all four to `127.0.0.1`; the
probe stood up a loopback listener and watched the connection arrive.

The failure mode is worse than a plain gap: `127.0.0.1` produces a loud
`ConfigError`, so an operator reasonably concludes that IP-shaped entries are
blocked, and writes `127.1` with a false sense of safety.

The lesson generalises beyond this one function: a validator that enumerates
*forms* will always trail the forms an attacker can write. Validate the
**property** — where the name actually points — in three layers.

**REQ-V12-SSR-01 (MUST)** Layer 1, syntax, at config load, offline and pure.
`_reject_ssrf_shaped_domain` keeps its four existing clauses and gains a strict
shape check: the entry MUST match

```
^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$
```

after case folding, and its **last label** MUST be either two or more ASCII
letters, or an IDN A-label beginning `xn--`. This rejects every shortened and
hexadecimal IPv4 form by construction (`1` and `0x7f` are not valid TLDs) while
accepting `wttr.in`, `sub.wttr.in`, `example.co.uk` and domains **under** an
`xn--` TLD such as `xn--80a1acny.xn--p1ai`. The message names the entry and the
reason, in the established style.

Two consequences, stated so they are not mistaken for defects. The pattern
requires at least two labels, so a bare TLD (`xn--p1ai` on its own) is refused
— consistent with the retained "contains no `.`" clause, which would refuse it
anyway. And a Unicode domain written in its native script (`пример.рф`) is
refused by layer 1; there is no practical regression, because `httpx` presents
hosts as A-labels, so the allowlist entry must be the `xn--` form regardless.

**REQ-V12-SSR-02 (MUST)** Layer 2, resolution, once at startup, best effort.
`config` gains

```python
FORBIDDEN_SCOPES = ("loopback", "private", "link-local", "multicast",
                    "reserved", "unspecified", "non-global", "unparsable")

def address_scope(addr: str) -> str | None
```

returning the first matching scope name for an `ipaddress` object built from
`addr` (checking `is_loopback`, `is_private`, `is_link_local`, `is_multicast`,
`is_reserved`, `is_unspecified` in that order), or `None` when the address is
an ordinary public one.

**Two rules keep this from repeating the mistake section 7 names.** The six
flags exist to give the operator a legible reason, not to define the boundary:

- **Backstop, checked last:** `if not ip.is_global: return "non-global"`. The
  enumeration alone leaks — `100.64.0.0/10` (carrier-grade NAT) and its
  IPv4-mapped form `::ffff:100.64.0.1` set **none** of the six flags and would
  be treated as public, which is exactly the "enumerate the forms" failure this
  release exists to stop.
- **Fail closed on garbage:** a string `ipaddress.ip_address()` cannot parse
  MUST return `"unparsable"`, never raise. `address_scope` never propagates an
  exception. Raising would crash the bot at startup from the seam, and inside
  `fetch_url` would surface as `failed to fetch the url: ValueError` audited as
  `error` — a network-stage classification for something that never left the
  process.

`bot._startup_docker_wiring` gains a keyword-only
`resolve: Callable[..., list] | None = None` and, in the body,
`resolve = resolve or socket.getaddrinfo`; it then resolves every allowlist
entry once with `resolve(entry, 443, proto=socket.IPPROTO_TCP)`.

**The `None` default is load-bearing.** Writing `= socket.getaddrinfo` in the
signature binds the original function object at `def` time, so
`monkeypatch.setattr(socket, "getaddrinfo", …)` — which is how REQ-V12-OFF-01's
guard works — would not intercept it: any call that omits `resolve=` would slip
past the guard into real DNS. Late lookup makes the guard mechanical instead of
leaving it to whoever remembers section 10.1, the same reasoning that names the
`devtools/` directory. If
any returned address has a forbidden scope it **refuses to start** with a
`ConfigError` naming the entry, the address and the scope. A resolution failure
is **not** fatal — the bot may legitimately start while DNS is down — but MUST
log `WARNING could not resolve allowlisted domain <entry>: <error class>; the
request-time guard remains in force`.

**Why the parameter exists.** Three delivered tests call the seam directly
(`tests/test_v11_patch.py`, the two `T-V11-WIR-01` cases and the reap case)
with a config whose `fetch_allowed_domains` is `{"wttr.in"}`. Without an
injection point, `pytest` would perform real DNS lookups: flaky on an offline
machine, slow everywhere, and a silent dependency on the outside world in a
suite whose whole discipline is that it has none. Section 10.1 lists those
three call sites; they pass a stub.

Resolution lives in the seam and never inside `load_config`: `load_config` runs
in dozens of offline tests and MUST stay free of DNS.

**REQ-V12-OFF-01 (MUST)** Make the offline guarantee enforceable instead of
aspirational. `tests/conftest.py` gains a second autouse fixture, beside the
existing `no_network` one, that monkeypatches `socket.getaddrinfo` to raise
`AssertionError("unexpected DNS lookup: <host>")`. Today `conftest` blocks
`httpx.HTTPTransport.handle_request` only, so name resolution was never barred
— this release adds two code paths that resolve, and without the fixture
nothing would stop a future one from resolving silently. Any test that needs
resolution injects its own stub; none may reach the real resolver.

**REQ-V12-SSR-03 (MUST)** Layer 3, request time, the one that actually binds.
`fetch_url` takes a keyword-only `resolve: Callable[[str], list[str]] | None =
None`. When it is not `None`, then after `_validate_url` accepts a URL — for
the initial URL **and for every redirect hop** — the host is resolved through
it and the request is refused with

```json
{"error": "url resolves to a <scope> address: <host>"}
```

if any returned address has a forbidden scope. The refusal is classified
`refused` by `_is_pre_network` (nothing left the process), so its message
prefix joins that predicate's tuple.

`bot.py` binds the production resolver — a module-level `tools.resolve_host`
wrapping `socket.getaddrinfo` and returning a list of address strings, `[]` on
failure — into the fetcher partial.

**Two rules about that `[]`.** First, it is deliberate **fail-open**, and the
only place in this release that fails open: an empty list means layer 3 finds
nothing to reject and the request proceeds. The justification is that the
allowlist is the primary control and a transient DNS failure should degrade a
`fetch` into an ordinary connection error rather than a refusal the operator
cannot explain; the connection itself will fail moments later anyway. State
this in `README.md` next to the other residual risks — a security layer that
opens under failure must say so out loud, especially in a document whose other
half insists on failing closed (REQ-V12-QTA-01).

Second, `resolve_host` catches **`OSError` only** (`socket.gaierror` is a
subclass), never bare `Exception`. A broad except would swallow the
`AssertionError` that REQ-V12-OFF-01's guard raises, turning the guard into
decoration: inside the seam it would degrade into the benign "could not
resolve" warning and the offending test would pass green while doing real DNS. A test MUST pin that the bound partial
carries it; this is exactly the class of defect that left
`sandbox_max_bytes=` in `_live_docker` untested in v1.1.

The default of `None` keeps every existing offline test unchanged: no test may
acquire a dependency on real DNS, and the new tests inject a stub resolver.

**Two residual risks, MUST be documented in `README.md`.** First, the port is
not constrained: `https://<allowlisted-host>:22/` passes every layer, because
layer 3 judges the resolved **address**, not the service behind it. The
allowlist is a host allowlist and nothing more. Second, checking the resolved
address is not the same as connecting to it. A name that resolves differently
between the check and the connection (DNS rebinding) defeats this layer;
closing it requires pinning the connection to the verified address, which needs
a custom transport and is a non-goal here (REQ-V12-NG-04). Layers 1 and 2
remain, and the allowlist itself is the primary control.

### 5.4 The empty resolv file must be a file (finding W-8-bis)

`_ensure_empty_resolv` checks `path.exists()` — which follows symlinks — and
creates the file only when that is false. Anything already at the path is
mounted into every container unexamined. The probe replaced it with a symlink
to the real `/etc/resolv.conf` and read the host's nameservers and search
domains out of the sandbox again, defeating v1.1's fix completely; a plain file
containing arbitrary text works equally well.

This is reachable because `DB_PATH` is unconstrained: `DB_PATH=/tmp/bot.db` is
a legal configuration, `/tmp` is world-writable, and the file name is
predictable — a local unprivileged user wins the race.

**REQ-V12-INF-01 (MUST)** `_ensure_empty_resolv` creates or truncates the file
unconditionally and refuses anything that is not a plain empty file:

1. Open with `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC |
   os.O_NOFOLLOW | os.O_NONBLOCK, 0o644)`. `O_NOFOLLOW` makes a symlink at the
   path raise `OSError` instead of being followed; `O_TRUNC` makes a
   pre-existing regular file empty rather than trusted; `O_NONBLOCK` is not
   optional — the threat model of this section is an attacker who plants a file
   first, and opening a **FIFO** for writing blocks until a reader appears,
   hanging the bot at startup with no error at all.
2. `os.fstat` the descriptor and require all four: `stat.S_ISREG(st_mode)`,
   `st_size == 0`, `st_uid == os.getuid()` and `st_nlink == 1`. Ownership and
   link count matter because without them a file planted by another user is
   rejected only incidentally — by `EPERM` from `fchmod`, and only for as long
   as the bot does not run as root. Then `os.fchmod` to `0o644` (exact perms
   regardless of umask).
3. Any failure — symlink, directory, device, unexpected type — raises
   `ConfigError` naming the path. This is a startup-time refusal, not a
   degradation: continuing would mount an attacker-chosen file into every
   container.
4. Before creating, verify the parent directory: if it is world-writable and
   **not** sticky (`st_mode & 0o002` and not `stat.S_ISVTX`), refuse with a
   `ConfigError` telling the operator to move `DB_PATH` out of a shared
   directory. A sticky world-writable directory such as `/tmp` still allows the
   race on a pre-existing file, which is exactly what `O_NOFOLLOW` + `O_TRUNC`
   + the `fstat` checks defeat.

**Residual risk, MUST be documented in `README.md`** beside the DNS-rebinding
note of REQ-V12-SSR-03: these checks describe the file at the moment it is
opened. In a shared directory an attacker can still act between check and use.
The real remedy is keeping `DB_PATH` out of world-writable directories, which
is why the rule above is a refusal and not a warning.

**REQ-V12-ERR-01 (MUST)** A configuration refusal from startup must look like
one. `main()` wraps only `load_config()` in `try/except ConfigError`, so a
`ConfigError` raised by the startup seam — from this requirement or from the
allowlist resolution of REQ-V12-SSR-02 — escapes as an unhandled traceback.
Extend that `try` to cover `_startup_docker_wiring` so both paths end in the
existing `log.error("configuration error: %s", redact(str(exc)))` and the exit
code the delivered code already uses for a bad configuration. A traceback is
not an error message: it prints paths and says nothing about which setting to
fix.

### 5.5 One situation, one envelope — including SIGKILL (finding W-5-bis)

REQ-V11-ORP-03 states the property plainly: *"budget exhaustion must not
produce two different envelopes depending on which killer won the race."* It
then enumerates two killers and misses the third. A command that ignores
SIGTERM (`trap '' TERM; sleep 60`) survives `timeout`'s polite signal, is
killed by `--kill-after=5`, and returns exit **137** with
`timed_out: false` — the bot reports "the program exited with 137" for a
command it killed for running too long.

Two concrete consequences: the model reasons about retrying a crash rather than
a timeout, and an operator grepping the audit log for `timed_out` misses every
SIGTERM-ignoring command — the exact population most worth noticing. The
trigger is trivially model-controlled.

**REQ-V12-ORP-03 (MUST)** When `wrap_timeout` is true for the invocation,
`run_command_docker` maps exit code **137** to `timed_out: true`, in the same
place and the same way it already maps 124. `exit_code` keeps the value the
client reported; tests never assert an exact code. With `wrap_timeout=False`
the mapping does not apply and 137 stays an ordinary exit code.

Accepted ambiguity, MUST be documented in `README.md` next to the existing
124 and 125/126/127 notes and treated as the same class of trade-off: a program
killed by an unrelated SIGKILL — the host OOM killer, most plausibly — while
the wrapper is active is indistinguishable from one the wrapper killed, and
will be reported as timed out. Reporting a container-memory OOM as a timeout is
the lesser error; both mean "the run did not finish on its own terms".

### 5.6 The reap must not kill a living bot's work (finding W-5-ter)

`_reap_orphaned_containers` removes **every** container carrying `tgexec=1`,
including containers in state `Up`. v1.1 acknowledged this and defended it with
a documented single-instance assumption. The assumption is not enough: starting
a second bot — deliberately, or by an operator's stray `python bot.py` — kills
the first bot's running exec mid-flight, and the first bot reports a docker
failure it did nothing to cause. A startup routine whose failure mode is
"silently break a healthy process" should not rely on documentation.

**REQ-V12-ORP-01 (MUST)** Ownership is recorded on the container.
`tools.owner_key() -> str` returns `f"{os.getpid()}-{_process_start_ticks()}"`,
where `_process_start_ticks()` reads field 22 (`starttime`) of
`/proc/<pid>/stat`. The pair is unforgeable in practice: a recycled pid has a
different start time.

**Parse after the last `)`, never by splitting the whole line.** Field 2 of
that file is the executable name in parentheses and may itself contain spaces
and parentheses — and `comm` is controlled by the *foreign* process, which is
exactly the process this code inspects in REQ-V12-ORP-02. Read the text, take
`line.rsplit(")", 1)[1]`, split that remainder on whitespace and index field 22
within it. A naive `line.split()[21]` yields the wrong field for any process
whose name contains a space, so the liveness check would report a living owner
as dead and the reap would kill the running container it exists to protect.

**`owner_key` never raises.** `/proc` may be unmounted or unreadable, and the
function is called on every exec, outside any `try`. On failure it returns the
deterministic fallback `f"{os.getpid()}-0"`. A `0` start time never matches a
real one, so such a container is always treated as orphaned and reaped — the
safe direction: a stale container is removed, and nothing is destroyed that a
liveness check could have saved. `build_docker_argv` gains a keyword-only
`owner: str | None = None` and, when given, inserts
`"--label", f"tgexec-owner={owner}"` immediately after the existing
`--label tgexec=1` pair. `run_command_docker` passes `owner=owner_key()`.

**REQ-V12-ORP-02 (MUST)** The reap removes only what is genuinely orphaned:

```
docker ps -a --filter label=tgexec=1 --format {{.ID}}\t{{.Label "tgexec-owner"}}
```

For each line, remove the container when the owner label is **absent or
malformed** (a container from v1.1, which had no owner label — those are always
orphans by the time this code runs) **or** when the owner is dead. Otherwise
skip it and log `INFO skipped N container(s) owned by a live process`.

`tools.owner_is_alive(key: str) -> bool` parses `<pid>-<ticks>` and returns
`True` only when `/proc/<pid>/stat` exists **and** its field 22 equals `ticks`;
any parse or read failure returns `False` (fail toward reaping — a container
whose owner cannot be established is exactly the orphan case). Removal keeps
its current shape: a single `docker rm -f <id>…` for the collected ids, all
failures logged at WARNING, never fatal.

`README.md`'s single-instance note is updated: concurrent instances are still
unsupported (REQ-V11-NG-05 stands), but a second instance no longer destroys
the first one's work.

**REQ-V12-ORP-04 (MUST)** The probe container is named and labelled like every
other container: `--name tgexec-probe-<8 hex chars>`, `--label tgexec=1` and
the owner label, inserted in `image_has_timeout`'s argv with the same ordering
discipline as `build_docker_argv`. Today the probe runs anonymous and
unlabelled, so a probe that outlives its `--rm` — a daemon restart at the wrong
moment — is invisible to the reap forever.

### 5.7 The audit hook must receive redacted records (finding W-8-quater)

`append_audit` redacts the JSON line it writes, but `_audit` hands the raw
`record` dict to the injected hook first. Every value that reaches the file
redacted reaches a custom hook in the clear, including `argv`. The file writer
is the *default* sink, not the only one, and the redaction guarantee should
belong to the boundary rather than to one implementation of it.

**REQ-V12-AUD-01 (MUST)** `_audit` redacts before dispatching:

```python
record = json.loads(config.redact(json.dumps(record, ensure_ascii=False)))
```

so non-string values keep their types. Place it **inside the existing
`try`**, after the `if audit is None: return` guard: `json.dumps` can raise on
a record carrying a non-serialisable value, and the established contract of
this function is that an audit failure is logged and never fatal
(`log.error("audit hook failed: ...")`). Redaction must not become the one way
auditing can take a tool call down. `append_audit` keeps its own redaction —
idempotent, and it is the last line of defence for a record that reached it by
another path. The known limitation of redacting serialised JSON (a secret
containing characters JSON escapes survives in escaped form) is already
documented by REQ-V11-DOC-03 and now applies here too; extend that note rather
than duplicating it.

---

## 6. Test-suite defects

Twenty-three mutations survived the delivered v1.1 suite. Every one is a place
where the tests assert something weaker than the requirement they are named
after. One of them is a new instance of the exact defect class this project has
now fixed three times.

**REQ-V12-TST-01 (MUST)** `T-V11-TRN-03`
(`test_t_v11_trn_03_fetch_secret_across_cap`, `tests/test_v11_patch.py`) is
vacuous. `httpx.Response(200, content=body)` served through `MockTransport`
delivers the body as a **single chunk**, so `body` always holds the whole
secret and `config.redact` catches it no matter what the code around it does.
Deleting **both** the `+ secret_headroom` term and the `strip_secret_fragment`
call from `fetch_url` leaves the suite green: the fetch leg of the v1.1
truncation fix is unverified.

Rewrite it the way `tests/test_v1_guardrails.py` already does it for the
streaming-stop assertion: build the response from an iterator of fixed-size
chunks so the cut genuinely lands inside the sentinel, and assert the envelope
contains neither the sentinel nor any ≥8-character prefix of it. Then prove it:
the mutation entries of section 8 for both lines MUST be caught.

**REQ-V12-TST-02 (MUST)** Every other surviving mutant gets a test that kills
it. Each row below names the production line and what the new or extended test
must observe. All of these live in `tests/test_v12_patch.py` unless a row says
otherwise.

| # | Production line | The test must fail when the line is broken |
|---|---|---|
| 1 | `bot._live_docker` passes `sandbox_max_bytes=cfg.exec_sandbox_max_bytes` | spy on `tools.run_command_docker`, assert the kwarg equals the configured value (not the built-in default) |
| 2 | pre-run refusal `if status != SCAN_OK or used >= limit` | a cut-short sandbox and an unreadable sandbox each yield their own envelope and spawn **no** process |
| 3 | post-run `_record_sandbox_quota` on the **timeout** branch | a stub docker that times out with an over-quota sandbox still records the quota fact in the audit line |
| 4 | post-run `_record_sandbox_quota` on the **docker-exit 125/126/127** branch | same, for a stub exiting 125 |
| 5 | the `pop` in `_run_exec` sits **before** the envelope is built, on every branch | over-quota **plus** docker exit 125 → the error envelope has exactly one key (`error`); the internal keys are in the audit record |
| 6 | `main()` passes `empty_resolv=empty_resolv` into the runner partial | stub the seam to return a real path; assert the partial's keywords carry it |
| 7 | `config.redact` in `agent.finish` | a reply whose text reaches `finish` with a sentinel and bypasses `_send`'s guard (assert on the returned string) |
| 8 | `config.redact` in `agent.summarize_conversation` | a scripted summariser returning a sentinel-bearing JSON: the returned string is redacted before any caller sees it |
| 9 | `--user` in `image_has_timeout`'s argv | argv assertion covering `--user <uid>:<gid>` alongside the flags already pinned |
| 10 | `followlinks=False` in `sandbox_usage` | a symlink to a **directory** (and a symlink loop) inside the sandbox: the walk neither follows it nor hangs |
| 11 | the `+ headroom` term in `_Capture` | with a registered secret straddling the cap, assert the redaction **placeholder** appears in the envelope — proving the secret was seen whole, not merely amputated by `strip_secret_fragment` |

Rows 7 and 8 close a gap v1.1 created: the spec asserted that the upstream
redaction in `finish()` "stays exactly as delivered and keeps `T-V1-RED-02`
valid", and the mutation showed it is no longer pinned by anything — the
storage guards and `_send` now cover that test's assertions on their own.

---

## 7. What this release changes about *how* we verify

The three security findings of section 5.1–5.3 share a shape worth naming,
because it is the reason this is the third patch in a row. In each case the
implementation matched its requirement exactly, the requirement described a
**mechanism** ("reject entries that parse as IP literals", "preserve ids
byte-for-byte", "walk the tree and sum sizes"), and the mechanism turned out
not to imply the **property** anyone actually wanted ("the bot never connects
to an internal address", "no model-authored text is stored", "the sandbox
cannot exceed its quota"). Mutation testing catches a weak test; it cannot
catch a requirement that is faithfully implemented and still wrong. Only
adversarial probing of the running system did.

**REQ-V12-DOC-01 (MUST)** `README.md` gains a short "Verification" section
stating what each layer is good for: gates 1–4 prove the code runs and behaves;
gate 5 proves the live environment works; gate 6 proves the tests can tell
correct code from broken code; and none of them proves the requirements are the
right ones — that needs an adversarial pass against a running instance, which
is how every finding in v1.1 and v1.2 was found. Three sentences, not an essay.

---

## 8. The mutation gate

Mutation evidence has been produced by hand in each of the last two releases
and, in both, the hand-run list was smaller than the audit's. Automating it
turns a promise in a report into a gate that fails.

**REQ-V12-MUT-01 (MUST)** `devtools/mutation_check.py`, standard library only, no
third-party mutation framework (REQ-V12-NG-05).

Structure:

```python
MUTATIONS = [
    {
        "id": "red-agent-content",
        "path": "agent.py",
        "find": "content = config.redact(response.content or \"\")",
        "replace": "content = response.content or \"\"",
        "why": "REQ-V11-RED-01: assistant content reaches storage unredacted",
    },
    ...
]
```

`find` MUST be an exact substring occurring **exactly once** in the file; a
count other than one is a hard failure of the gate itself ("the mutation list
has drifted from the code"), reported per entry and never silently skipped.

For each mutation, in order: snapshot the file's bytes in memory, write the
mutated bytes, run

```
uv run --locked pytest -x -q
```

as a subprocess, restore the original bytes, and record the outcome.

**The verdict is by exact exit code, not by "non-zero".** `pytest` returns `1`
for *tests failed* and `2`…`5` for interrupted, internal error, usage error and
no-tests-collected. A mutation that breaks collection — a plausible outcome
when a line is replaced — exits `2` or `3`, and counting that as "killed" would
hand a clean bill of health to a gate that exists precisely to stop false
green. Therefore: **killed ⟺ exit code `1`**; exit `0` is **survived**; any
other code is **errored** and fails the gate with the code printed, so the
operator fixes the mutation entry instead of trusting it.

The gate exits `0` only when every mutation was killed and every `find` matched
exactly once; otherwise it exits `1` after printing a per-mutation table and a
summary line `N mutations, K killed, S survived, E errored, D drifted`.

The subprocess environment sets `PYTHONDONTWRITEBYTECODE=1`. Several mutations
are size-preserving, and a stale `__pycache__` entry whose source mtime and
size are unchanged would let pytest import the *unmutated* module — a survivor
that is an artefact of caching rather than of coverage.

Flags: `--list` prints the table without running anything; `--only <id>` runs
one entry; `--jobs` is **not** provided (mutations must not run in parallel —
they edit the same working tree).

**Expected runtime, so nobody kills it thinking it hung.** Each mutation runs
the suite with `-x`, so a killed mutation usually exits in seconds while a
survivor pays the full suite (~16 s at 251 tests). Budget roughly **4–8
minutes** for the whole gate at ~26 mutations. The gate prints each mutation id
as it starts, so progress is visible.

**REQ-V12-MUT-02 (MUST)** Restoration is unconditional. All original bytes are
held in memory from the moment the first file is touched. Restoration happens
in a `finally` around each mutation **and** in an outer `finally` covering the
whole run, and `signal.SIGINT`/`signal.SIGTERM` handlers restore and exit
non-zero. After restoring, the script re-reads every touched file and verifies
it matches the snapshot byte-for-byte, printing
`FATAL: could not restore <path>` and exiting `2` if not. The working tree this
script leaves behind MUST be identical to the one it found — a mutation tool
that can corrupt the repository is worse than no mutation tool.

**REQ-V12-MUT-03 (MUST)** The gate is itself tested, in
`tests/test_mutation_check.py`, without running the real suite: the module's
runner is injected (a callable returning an exit code), so the tests are fast
and offline.

- a mutation whose injected run returns non-zero is reported killed; one that
  returns zero is reported survived and the overall result is failure;
- a `find` string that occurs zero or twice is reported as drift and fails;
- **files are restored** after a normal run, after the injected runner raises,
  and after it returns a "killed" verdict — assert byte-for-byte on a temporary
  file tree, never on the real repository;
- `--list` runs no mutations at all.

**REQ-V12-MUT-04 (MUST)** The initial `MUTATIONS` list covers, at minimum, one
entry per row of REQ-V12-TST-02's table, one per security requirement of
section 5 (`REQ-V12-ID-01` minted id, `REQ-V12-QTA-01` `onerror`,
`REQ-V12-QTA-02` fail-closed condition, `REQ-V12-SSR-01` shape check,
`REQ-V12-SSR-03` request-time guard, `REQ-V12-INF-01` `O_NOFOLLOW`,
`REQ-V12-ORP-02` liveness check, `REQ-V12-ORP-03` the 137 mapping,
`REQ-V12-AUD-01` hook redaction, `REQ-V12-ID-04` the selftest pairing check,
`REQ-V12-QTA-03` the cleanup chmod-and-retry), and the four v1.1 guards whose tests already
pass (the storage writers, `_send`, `_status_line`, the fetch cap break) — so a
future release cannot quietly weaken them.

Add the two lines REQ-V12-TST-01 restores (`+ secret_headroom` and
`strip_secret_fragment` in `fetch_url`) and one entry `ssr-is-global-backstop`
for the `is_global` check of REQ-V12-SSR-02, whose absence would otherwise let
the CGNAT gap reopen silently.

That is **11 + 11 + 4 + 2 = 28 entries minimum**. "Roughly 25" would be
unfalsifiable next to a report that must state an exact count, so the
requirement is a floor: **at least 28**, each with a stable `id`, and the
report states the exact number the gate printed. Adding more is welcome;
dropping below the floor is a defect.

One clarification on the arithmetic: the 11 rows of REQ-V12-TST-02 are a
**deduplicated set of production lines**, not one row per surviving mutant. The
v1.1 audit's 22 survivors collapse onto those 11 lines (several mutants
targeted the same line from different angles), and coverage is asserted at the
level of the line, which is what a mutation entry can address.

---

## 9. Implementation order

**REQ-V12-ORD-01 (MUST)** Follow this order; each step ends with gates 1–4
green before the next begins.

1. Tests first: write section 10.2's new tests and apply section 10.1's
   corrections. They fail; that is the point.
2. `devtools/mutation_check.py` and `tests/test_mutation_check.py` — the gate
   before the fixes, so each fix can be proven as it lands.
3. `config.py`: `EXEC_SANDBOX_CLEAN_ON_START`, the strict domain shape check,
   `address_scope`/`FORBIDDEN_SCOPES`.
4. `storage.py`: `next_turn_id`.
5. `agent.py`: minted identifiers, name validation, the corrected docstring.
6. `tools.py`: `sandbox_usage` tri-state and `onerror`; the three refusal
   envelopes and `sandbox_scan` plumbing; `owner_key`/`owner_is_alive`/
   `resolve_host`; the owner label; the 137 mapping; the probe's name and
   labels; `fetch_url`'s `resolve` parameter; `_audit` redaction.
7. `bot.py`: `_ensure_empty_resolv` hardening; the seam's sandbox cleanup and
   allowlist resolution; the ownership-aware reap; the resolver bound into the
   fetcher partial; **the `_selftest_failure` identifier checks of
   REQ-V12-ID-04**. Verify here that `uv run --locked pytest` still runs with
   **no** Docker daemon reachable and issues **no** `docker` command, and that
   `python bot.py --selftest` is green — the v1.1 properties this release must
   not lose.
8. `.env.example`, `README.md`, then section 11's documentation corrections.
9. Gates 5 and 6, then Appendix B, then review, then report.

---

## 10. Tests

### 10.1 Amendments to existing tests (exhaustive — nothing else may change)

| Test | Change |
|---|---|
| `tests/test_agent.py` — **four** assertions, all in the id family: `stored[2]["tool_call_id"] == "call_0"`; `ids[:3] == ["call_a", "call_b", "call_c"]`; `ids[3] == "auto_3"`; and `[r["tool_call_id"] for r in tool_rows] == ids` | expected ids become the minted `call_<turn_id>_<index>` values (REQ-V12-ID-01). Assert the **pairing** — assistant `tool_calls[i].id` equals the following tool row's `tool_call_id` — and uniqueness, never a literal the model supplied. The `auto_3` assertion tested the v1 fallback for a duplicate id; that fallback is deleted, so it becomes an assertion that the minted id is used regardless of what the model sent. `len(ids) == len(set(ids)) == 5` stays true and stays asserted |
| `tests/test_selftest.py` (`T-ST-01`, `T-ST-02`) and `bot._selftest_failure` | **required, or gate 4 fails.** `bot.py` pins the literal identifier twice — `calls[0]["id"] != "call_1"` and `tool_rows[0]["tool_call_id"] != "call_1"` — which REQ-V12-ID-01 turns into a minted value. Replace both with the property they were standing in for: `calls[0]["id"] == tool_rows[0]["tool_call_id"]` (pairing) and `calls[0]["function"]["name"] == "exec"`. This is a production-code change in `bot.py`; the two tests exercise it and need no edit of their own beyond staying green |
| `tests/test_v11_patch.py` — the three direct `_startup_docker_wiring` call sites (both `T-V11-WIR-01` cases and the reap case) | pass a stub `resolve=` so the seam performs no real DNS (REQ-V12-SSR-02). No other change |
| `tests/conftest.py` | gains the autouse DNS guard of REQ-V12-OFF-01 |
| `T-V11-TRN-03` (`tests/test_v11_patch.py`) | rewritten to stream the body in chunks (REQ-V12-TST-01) |
| `T-V11-QTA-01` | `sandbox_usage` now returns `(int, str)`; update the expectations to the status constants and add the unreadable-subtree case. `test_t_v11_qta_01_survives_an_unreadable_entry` now asserts the **opposite** of what its name says — an unreadable entry is no longer survived, it fails the scan closed — so rename it to `test_t_v11_qta_01_reports_incomplete_on_an_unreadable_entry` |
| `T-V11-QTA-02` | the cut-short case now expects its own message; add the incomplete-scan case |
| `T-V11-QTA-03` | additionally assert `sandbox_scan` in the audit record and the unchanged success-envelope key set |
| `T-V11-ORP-02` | the stub `docker` gains the `ps -a --format` shape of REQ-V12-ORP-02; assert a live-owner container is skipped and an unlabelled one is removed |
| `T-V11-ORP-03` | the probe argv now carries `--name`, both labels and `--user` |
| `T-V11-ORP-04` | extend the 124 case with a 137 case under `wrap_timeout=True`, and with `wrap_timeout=False` for both |
| `T-V11-INF-01` | the file is now truncated and type-checked: add the **symlink refusal** and the **non-empty-file truncation** (a plain file is emptied by `O_TRUNC`, not rejected — REQ-V12-INF-01 and scenario D5 both say so) |
| `T-V11-WIR-01` (both tests) | **unchanged, and MUST stay green.** The `docker_ok=False` test forbids any `subprocess.run` and asserts `.resolv-empty` is absent, so the startup cleanup of REQ-V12-QTA-03 must use `shutil`/`os` and must not create that file on that path |
| `T-V11-CFV-01` | add `127.1`, `127.0.1`, `0x7f.1`, `0x7f.0.0.1` to the rejected set; keep every currently accepted domain accepted |
| `test_main_binds_the_container_runner_not_the_host_runner` | the fetcher partial now also carries `resolve`; the runner partial is unchanged in shape |

Nothing else. If another test fails, the production change is wrong.

### 10.2 New tests (`tests/test_v12_patch.py`)

| ID | Asserts |
|---|---|
| T-V12-ID-01 | a scripted `FakeLLM` whose tool call carries the sentinel in **both** `id` and `name`: the stored assistant row, the stored tool row, and the next round's payload contain neither; the minted id matches `call_<turn_id>_<index>` |
| T-V12-ID-02 | pairing survives a restart: after `load_context_messages`, every assistant `tool_calls[i].id` has a matching `tool_call_id` in the same turn, and ids from different turns never collide |
| T-V12-ID-03 | `normalize_tool_calls` discards the model's id unconditionally — two calls with identical ids, empty ids, and a 4 KB id all yield the minted values, in order |
| T-V12-ID-04 | (REQ-V12-ID-04) `_selftest_failure` accepts a transcript whose identifiers are minted and rejects one where the assistant call and the tool row disagree; it no longer depends on any literal id |
| T-V12-ID-05 | (REQ-V12-ID-01 item 4) an unknown `function.name` is stored and transmitted as `"unknown"`, while dispatch still returns the existing unknown-tool envelope |
| T-V12-QTA-01 | `sandbox_usage` tri-state: clean tree → `SCAN_OK`; past the entry limit → `SCAN_CUT_SHORT`; a `chmod 000` subdirectory → `SCAN_INCOMPLETE`, and `SCAN_INCOMPLETE` wins when both conditions hold |
| T-V12-QTA-02 | the three refusal envelopes of REQ-V12-QTA-02, each with **no** subprocess spawned (`_run_process` monkeypatched to fail the test), and `sandbox_scan` present in the audit record |
| T-V12-QTA-03 | the unreadable-subtree bypass is closed end to end: a sandbox whose only content is inside a `chmod 000` directory is refused rather than measured as empty |
| T-V12-QTA-04 | startup cleanup empties the sandbox (files, nested directories, a symlink) and keeps the directory itself with its mode; with `EXEC_SANDBOX_CLEAN_ON_START=false` nothing is removed; a failure logs and does not raise |
| T-V12-SSR-01 | `_parse_domains` rejects `127.1`, `127.0.1`, `0x7f.1`, `0x7f.0.0.1`, `-bad.example`, `bad-.example`, `a..b`, `example.123`; accepts `wttr.in`, `sub.wttr.in`, `example.co.uk`, `xn--80a1acny.xn--p1ai` and a 63-character label |
| T-V12-SSR-02 | `address_scope` classifies loopback, private, link-local, multicast, reserved and unspecified addresses (v4 and v6) and returns `None` for a public one; **`100.64.0.1` and `::ffff:100.64.0.1` return `"non-global"`** (they set none of the six flags — this is the backstop under test) and **`"not-an-ip"` returns `"unparsable"`** rather than raising |
| T-V12-SSR-03 | the startup resolution check refuses to start when a stub resolver maps an allowlisted domain to `127.0.0.1`, and only warns when the stub raises |
| T-V12-SSR-04 | `fetch_url` with a stub resolver: an allowlisted host resolving to a forbidden address is refused before any request reaches the transport, on the **initial URL and on a redirect hop**; the refusal audits as `refused`; with `resolve=None` behaviour is exactly v1.1 |
| T-V12-SSR-05 | the fetcher partial built in `main()` carries the production `resolve` (the v1.1 `sandbox_max_bytes` lesson, applied) |
| T-V12-INF-01 | `_ensure_empty_resolv`: a symlink at the path raises `ConfigError`; a non-empty regular file is truncated to zero; perms end at `0o644`; a world-writable non-sticky parent is refused |
| T-V12-ORP-01 | `owner_key` round-trips through `owner_is_alive` for the current process; a fabricated pid, a mismatched start time and a malformed key all yield `False`; `build_docker_argv(owner=…)` places the owner label right after `tgexec=1` |
| T-V12-ORP-02 | the reap removes an unlabelled container and one whose owner is dead, **skips** one whose owner is alive, and logs the skip count |
| T-V12-ORP-03 | `wrap_timeout=True` maps 137 to `timed_out: true`; `wrap_timeout=False` leaves it false; the 124 mapping is unchanged; the outer-kill path still reports `timed_out: true` |
| T-V12-AUD-01 | an injected audit hook receives a record in which a sentinel-bearing argv is already redacted, and non-string values keep their types; a non-serialisable record logs and does not raise |
| T-V12-ERR-01 | (REQ-V12-ERR-01) a `ConfigError` raised by the startup seam is caught by `main()`: the process logs a configuration error and returns the delivered exit code, with no traceback |
| T-V12-OFF-01 | (REQ-V12-OFF-01) the conftest guard fires: a test calling `socket.getaddrinfo` without injecting a stub fails with the guard's message. Written so it asserts the guard, not the network |
| T-V12-TRN-01 | the rewritten fetch-truncation test of REQ-V12-TST-01 (chunked body, secret across the cap) |
| T-V12-MUT-01 … 04 | the mutation-gate behaviours of REQ-V12-MUT-03, in `tests/test_mutation_check.py` |
| T-V12-COV-01 … 11 | one test per row of REQ-V12-TST-02's table |

Offline discipline is unchanged and MUST hold: `tests/conftest.py`'s no-network
guard stays in force, no new test touches the network **or DNS**, and no new
test requires a real Docker daemon — the docker layer is exercised through the
argv builder and the stub-executable pattern of `tests/test_docker.py`.

---

## 11. Gates

**REQ-V12-GATE-01 (MUST)** Run verbatim, in order, from the repository root:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
uv run --locked python devtools/mutation_check.py
```

Gates 1–4 and 6 are unconditional and offline. Gate 5 requires the section-3
preconditions; per REQ-V12-PRE-01 item 2, an LM Studio outage is the single
tolerated failure and MUST be recorded as such, with every other check green.
The test count MUST be **greater than 251**; state the exact number in the
report.

`AGENTS.md`'s gate list is updated to six commands in the same commit as the
gate itself (the repository's own spec-sync rule).

---

## 12. Acceptance, review and report

**REQ-V12-ACC-01 (MUST)** After the gates are green, execute Appendix B of this
spec against the live bot, plus spec-v1.1's scenarios C1, C3, C4 and C6 as a
regression check that this patch did not weaken v1.1's posture. Record pass or
fail per scenario, and — per REQ-V12-REP-02 — **how** each was driven.

**REQ-V12-REV-01 (MUST)** Code review by the `code-reviewer` subagent in a
clean context, after the gates pass and before the final report. Findings are
fixed, or explicitly waived with a reason in the report. Log the review prompt
in `docs/prompts/08-code-review-v1.2.md`.

The reviewer's standing instruction "for critical logic ask *which test fails
if this line changes?*" now has a mechanical answer: gate 6. The review MUST
report any security-relevant line that has **no** mutation entry, and such a
line is a finding, not an observation.

**REQ-V12-REP-01 (MUST)** Report per the project standard:
`docs/reports/report-v1.2.md` (gates table with all six commands and the exact
test count, the mutation-gate summary line and wall-clock, Appendix-B results,
deviations, fix cycles), `docs/llm-usage.md` rows appended, every prompt logged
in `docs/prompts/`, then `docs/reports/tg-post-v1.2.md` (Russian, per
`AGENTS.md`, **under 1500 characters** — v1.1's is 1621 by `wc -m`).

The report MUST state which findings this patch closes and which remain
accepted risks: DNS rebinding between check and connect (REQ-V12-SSR-03),
`/proc/self/mountinfo` host paths (REQ-V11-INF-02), in-sandbox transformation
defeating value-based redaction (REQ-V11-DOC-05), the 124/137/125/126/127
exit-code ambiguities, and the docker-group cost stated in v1.

**REQ-V12-REP-02 (MUST)** Process honesty, as a checkable requirement rather
than an aspiration. v1.1's report declared "Deviations from the spec: None"
while deviating twice — one commit for two prompts, and Appendix B driven by a
script rather than by the Telegram messages its scenarios describe. Both were
visible in adjacent prose; neither was in the section a reader checks.

1. **At least two commits.** The implementation commit references
   `docs/prompts/07-go-spec-v1.2.md`; a separate commit carries the report,
   the Telegram post and the usage rows. A review-fix round, if any, is its own
   commit. One commit for the whole run is a deviation and MUST be declared as
   one.
2. The Deviations section MUST list **process** deviations, not only technical
   ones, and MUST state for each acceptance scenario whether it was driven by a
   real Telegram message from the operator's account or by a script standing in
   for one. "Driven by a script" is an acceptable answer; leaving it unsaid is
   not.
3. "None" is only permissible when both of the above are satisfied and no
   section-10.1 amendment was exceeded.

**REQ-V12-DOC-02 (MUST)** Housekeeping the previous release left behind:

1. `docs/llm-usage.md` — the v1.1 rows were appended after the prose as a
   headerless table fragment and render as a separate table whose first data
   row becomes a header. Move them into the main table, keeping the honest
   "not computed" marker and the note about the uncounted commit.
2. `docs/plan.md` still describes the v0 state ("113 tests", "four gates").
   Update it to the delivered reality: the current test count, six gates, and
   the v1/v1.1/v1.2 milestones.
3. `docs/reports/tg-post-v1.1.md` is 1621 characters (`wc -m`) against an
   `AGENTS.md` limit of ~1500. Trim it to fit; do not touch its claims.
4. `docs/reports/report-v1.1.md` declares "Deviations from the spec: **None**"
   while the run deviated twice. Replace that section with the two entries the
   compliance review named: the whole run was delivered as **one** commit
   although it consumed two prompts (`05` go, `06` review), and Appendix B was
   executed by a scripted driver with a scripted model rather than by Telegram
   messages from the operator's account, as its scenarios describe. Neither
   fact was hidden — both appear in adjacent prose — but the Deviations section
   is where a reader checks, and "None" there was false. Correcting a shipped
   report after the fact is cheaper than leaving a known-false line standing,
   and this release is the one that turns REQ-V12-REP-02 into a rule.

---

## 13. Non-goals for v1.2

Implementing any of these is a defect.

| ID | NON-GOAL |
|---|---|
| REQ-V12-NG-01 | Everything the next assignment owns: token/cost accounting middleware, usage tables, dashboards, per-call metrics, cost reports, token optimisation. This release must stay a clean "before" baseline. |
| REQ-V12-NG-02 | Rootless Docker, micro-VMs, gVisor, seccomp/AppArmor profiles, image building, masked-path runtimes. |
| REQ-V12-NG-03 | Kernel-level filesystem quotas (XFS project quotas, loop devices, `--storage-opt`). Scan-and-refuse plus startup cleanup is the whole mechanism. |
| REQ-V12-NG-04 | A custom httpx transport pinning connections to a verified address (full DNS-rebinding protection); entropy-based secret detection. Both are documented residual risks. |
| REQ-V12-NG-05 | Third-party mutation-testing frameworks (`mutmut`, `cosmic-ray`), coverage tooling, new Python dependencies of any kind. |
| REQ-V12-NG-06 | `asyncio`, threads beyond the existing reader threads, parallel update processing, supported multi-instance operation. |
| REQ-V12-NG-07 | New features of any kind — commands, tools, providers, storage shapes — and refactoring not required by a requirement above. |

---

## Appendix A — finding traceability

| Finding | Source | Severity | Requirements |
|---|---|---|---|
| W-1 `tool_call_id` and `function.name` are model-authored, unredacted, stored in `bot.db` and replayed into every later payload | adversarial probe (confirmed independently at `storage.py:210`) | HIGH | REQ-V12-ID-01 … ID-03 |
| W-4 sandbox quota bypassed via an unreadable subtree (`chmod 000`); 60 MiB written against a 10 MiB limit | adversarial probe (confirmed at `tools.py:378`) | HIGH | REQ-V12-QTA-01, QTA-02 |
| W-4b cut-short scan disables exec permanently and reports a false reason | adversarial probe | MEDIUM | REQ-V12-QTA-02, QTA-03 |
| W-6 shortened and hexadecimal IPv4 (`127.1`, `0x7f.1`) accepted by the fetch allowlist and resolved to loopback | adversarial probe (confirmed by running `config._parse_domains`) | HIGH | REQ-V12-SSR-01 … SSR-03 |
| W-8b `.resolv-empty` is trusted if it already exists; a symlink restores the host DNS leak | adversarial probe | MEDIUM | REQ-V12-INF-01 |
| W-5b SIGTERM-ignoring command killed by `--kill-after` reports `exit 137, timed_out: false` | adversarial probe | MEDIUM | REQ-V12-ORP-03 |
| W-5c the reap removes running containers, so a second instance kills the first one's exec | adversarial probe | MEDIUM | REQ-V12-ORP-01, ORP-02 |
| W-7 the probe container is anonymous and unlabelled — an orphan the reap can never see | adversarial probe | LOW | REQ-V12-ORP-04 |
| W-8c the audit **hook** receives the record before redaction | adversarial probe | LOW | REQ-V12-AUD-01 |
| G-1 `T-V11-TRN-03` is vacuous — `MockTransport` delivers one chunk, so the fetch truncation guard is unverified | compliance review (mutation) | 🔴 | REQ-V12-TST-01 |
| G-2 … G-9 twenty-two further surviving mutants (quota branches, `_live_docker` kwarg, `empty_resolv` wiring, `finish`/`summarize` redaction, probe `--user`, `followlinks`, headroom, envelope `pop` position) | compliance review (mutation) | 🟡/🟢 | REQ-V12-TST-02, REQ-V12-MUT-04 |
| G-10 the v1.1 report declared "Deviations: None" while deviating twice | compliance review | 🟡 | REQ-V12-REP-02 |
| G-11 `docs/llm-usage.md` fragment, stale `docs/plan.md`, oversized v1.1 Telegram post | compliance review | 🟢 | REQ-V12-DOC-02 |

Deliberately **not** acted on, recorded so a later reader knows they were seen
and judged: `/proc/self/mountinfo` host paths (REQ-V11-INF-02 stands),
in-sandbox `base64` defeating value-based redaction (REQ-V11-DOC-05 stands),
the docker-group root-equivalence (v1, documented), and the three v1.1
cosmetic findings R-10 … R-12.

## Appendix B — acceptance scenarios (Gherkin, written before code)

```gherkin
# SAFETY RULE FOR EVERY SCENARIO BELOW: never use a live credential as the test
# secret. Scenarios that move a secret through Telegram or the provider would
# disclose a real token by the very act of testing.
#
# There is no "extra secret" variable: load_config registers exactly two values
# (TELEGRAM_BOT_TOKEN and, per REQ-V1-SEC-05, OPENROUTER_API_KEY). The
# throwaway run is configured like this:
#
#   OPENROUTER_API_KEY=SYNTHETIC-V12-CANARY-<random hex>   # >= MIN_SECRET_LENGTH
#   LLM_PROVIDER=lmstudio
#   LLM_FAILOVER=off
#
# The synthetic value becomes a redaction target; with the provider pinned to
# LM Studio and failover off it is never validated and never leaves the
# process. Restore the real .env afterwards.

Scenario: D1 — a secret in a tool-call identifier never reaches storage
  Given a synthetic throwaway secret is registered for this run
  And the model is scripted to emit a tool call whose id and function name
      both contain that value
  When the round completes
  Then no row of the database contains the synthetic value
  And the request payload of the following round contains no synthetic value
  And the stored assistant call and its tool result still share one identifier

Scenario: D2 — an unreadable subtree cannot hide sandbox usage
  Given EXEC_SANDBOX_MAX_BYTES is temporarily set to 8 MiB in a throwaway run
  When the operator asks the bot to write 32 MiB into a sandbox subdirectory
       and then make that subdirectory unreadable
  Then the next exec is refused because the size could not be measured
  And the refusal names measurement, not fullness
  And the bot keeps answering ordinary messages

Scenario: D3 — the sandbox recovers by itself
  Given a sandbox left over quota by a previous run
  When the bot is restarted with the default configuration
  Then the startup log reports the sandbox was cleared
  And the next exec succeeds

Scenario: D4 — a shortened loopback address is refused at startup
  Given FETCH_ALLOWED_DOMAINS is set to 127.1 in a throwaway run
  When the bot starts
  Then it exits with a configuration error naming that entry
  And the same happens for 0x7f.1 and for a dotless hostname

Scenario: D5 — a planted resolv file cannot leak host DNS
  Given a symlink to the host /etc/resolv.conf is planted at the bot's
        empty-resolv path in a throwaway run
  When the bot starts
  Then it refuses to start and names the path
  And when the symlink is replaced by a normal file containing text
  Then the file is truncated to empty and the sandbox reads nothing from it

Scenario: D6 — a command that ignores SIGTERM is still reported as timed out
  Given the bot runs an exec command that traps and ignores SIGTERM
  When the in-container budget expires and the hard kill lands
  Then the envelope reports timed_out true
  And the audit line for that call reports the same

Scenario: D7 — a second bot does not kill the first one's work
  Given one bot instance is running a long exec command
  When a second instance of the bot is started against the same daemon
  Then the running container is still alive after the second start
  And the second instance logs that it skipped a container owned by a live
      process

Scenario: D8 — v1.1 posture intact
  When spec-v1.1 scenarios C1, C3, C4 and C6 are re-run
  Then each still passes exactly as it did for v1.1
```
