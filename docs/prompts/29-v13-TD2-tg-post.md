# Prompt 29 — v1.3 TD2: the Telegram post (stage D)

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Owner of:** `docs/reports/tg-post-v1.3.md` (new)
- **REQ ids:** REQ-V13-RPT-02, AGENTS.md § Reporting

## Brief as sent (abridged)

```
Russian, ready to paste, under ~1500 characters, no tables or code fences.
v1.1 and v1.2 were never posted, so this covers v1 -> v1.3 as ONE story: one
short line per version, then the v1.3 headline numbers.
Be honest about the FAIL. The -30% target was not met, and the reason is worth
telling: the audit found reasoning to be 71.8% of all completion tokens — the
single biggest lever — but LM Studio does not honour the model's documented
`/no_think` switch, so that optimization was built, measured by a live probe,
and then deliberately REMOVED from the tree rather than shipped as a fake win.
Second honest point: prefix compression cut prompt tokens 18% but cost the bot
the ability to enumerate its own tools, which is why one scenario regressed.
Executor model named: claude-opus-5. Where docs/llm-usage.md records `unknown`
for the executor's own tokens/cost, KEEP that note and label any estimate.
Do not oversell. The interesting story is the method — a token audit that found
a real security regression and refused a fake optimization — not a win that did
not happen.
```

## Corrections the subagent made to this brief (accepted)

- The tool-schema "before" figure is **2041** (the v1.2 tree and
  REQ-V13-PFX-02's own "today 2041"), not the 2893 the brief quoted: 2893 was a
  transient mid-stage-C state, after O1 added two parameters and before O4
  compressed the descriptions, and was never committed in any tree.
- The security regression was introduced by O1 in this release and found by the
  stage-C `code-reviewer`, not by the token audit; the post attributes it to the
  review.
