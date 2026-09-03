# Vendored semgrep rulesets

REQ-V15-SCAN-04: the ruleset is vendored, not fetched at gate time. This is
the one-off online resolution (T7), the run's last sanctioned network step;
every scanner run after this reads only these repository-local files
(`semgrep scan --config .semgrep/`, proven offline with an empty cache by
`N5`).

| file | registry id | resolved | rules | SHA-256 |
|---|---|---|---|---|
| `p-python.yaml` | `p/python` | 2026-09-04 | 151 | `31c1dfa46e8ddd97f9ac98c607ddd77b20a2c3356d7ec987359961d47ec27035` |
| `p-security-audit.yaml` | `p/security-audit` | 2026-09-04 | 225 | `b109a039df712f30c6d3e25e1e8358053fd0f1c91b92d0e8d2871cd141fe602f` |

Resolved via the registry's direct config endpoint
(`https://semgrep.dev/c/<registry-id>`), the same content `semgrep
--config <registry-id>` would fetch and cache — copied here verbatim, byte
for byte (the SHA-256 above is over the file as committed).

**Upstream revision.** The registry does not expose a ruleset git commit;
the closest upstream-revision marker each response exposes is its HTTP
`ETag`, captured at resolution time:

- `p/python`: `W/"5a0df03d3b4ab579a2a33e843cace71782acc255"`
- `p/security-audit`: `W/"eba951b81c18bf273fd189807814713b13bff45e"`

**Overlap.** 30 rule ids appear in both files (rules the registry groups
under more than one pack). `semgrep scan --config .semgrep/` (a directory
of YAML files, confirmed via `semgrep scan --config --help` at 1.176.0)
tolerates this without error — measured directly: a two-file `.semgrep/`
with the overlap loaded 94 `ERROR`-severity Python rules and produced a
real finding with exit code 1 under the exact gate invocation
(`--severity ERROR --error`), the run's evidence this vendoring works
end-to-end before it goes live in `config/quality_gates.yaml`.

**Re-resolving.** A future refresh re-runs this same fetch, replaces both
files, and updates this table's date, rule counts, ETags and SHA-256 in
the same commit — never a partial edit of one file without the other.
