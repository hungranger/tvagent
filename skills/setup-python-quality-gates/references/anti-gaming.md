# Anti-gaming rationale (L3)

## Actor vs. judge

Quality gates only work if the entity that writes the code cannot also
quietly weaken the gate that checks it. An autonomous coding agent (or a
rushed human) can otherwise "pass" a failing gate by editing the threshold
instead of the code. L3 separates the **actor** (whoever writes code on a
branch) from the **judge** (CI running against `origin/master`, plus a
second human identity via CODEOWNERS review) so no single actor can both
write and approve a weakening.

## The ratchet: `scripts/gate_ratchet.py`

**Real invocation — no `--self-check` flag exists.** The script has no
`argparse`. Its `if __name__ == "__main__":` block *always* runs a
hardcoded self-check (asserts against two fake config dicts, purely to
verify the checker functions themselves work) and *then* unconditionally
calls `main()`. There is no flag that isolates one behavior from the other —
`python scripts/gate_ratchet.py` runs both, every time. Do not describe or
invoke a `--self-check` flag; it does not exist.

What `main()` actually does: it reads the working tree's `pyproject.toml`,
then runs `git show origin/master:pyproject.toml` (the constant
`BASE_REF = "origin/master"`) to get the base version. If that ref is
missing (`git show` fails — e.g. `origin/master` isn't fetched), it prints a
note and **skips the pyproject-based checks entirely**, returning 0 for that
part. If the base is present, it diffs current vs. base per gate:

- coverage `fail_under` must not go down
- ruff `select`/`extend-select` must not lose a rule
- mccabe `max-complexity` must not go up
- vulture `min_confidence` must not go up (higher = noisier = weaker)
- pyright must stay `strict` and must not loosen `reportMissingImports` /
  `reportMissingModuleSource` / `reportMissingTypeStubs` toward `"none"`
- import-linter must not lose a contract
- (separately) the nightly-mutation workflow's `--min` floor must not go down

A gate absent on master (no baseline) is skipped with a printed note —
absence isn't intent. A gate that *was* present on master and is now
**missing** from the tree is a hard failure, not a skip — deletion is the
strongest possible weakening.

**Operational requirement:** CI must fetch `origin/master` as a real
remote-tracking ref for the ratchet to have a base to diff against —
`fetch-depth: 0` on `actions/checkout` (as in the shipped `ci.yml`), or an
equivalent full/deep clone. Without it, the ratchet silently no-ops on the
pyproject checks. This is why `ci.yml`'s checkout step is pinned to
`fetch-depth: 0` and has a belt-and-braces `git fetch` of the base ref for
PR events.

## The suppression diff: `scripts/suppression_diff.py`

Visibility only — it always exits 0. It scans this branch's added lines
(vs. the merge-base with `origin/master`) for newly introduced suppressions
(`# noqa`, `# type: ignore`, `# pyright: ignore`, `# nosemgrep`, `# pragma:
no cover`, `--no-verify`, `|| true`, `continue-on-error`) and growth of the
vulture allowlist / gitleaks config / ruff `per-file-ignores`, and prints
each as a GitHub Actions `::warning::` annotation inline on the PR diff. Its
teeth are not "block the merge" — they come from CODEOWNERS + required
review on the gate-defining files it watches, so a human reviewer sees every
new suppression before approving.

## Why CODEOWNERS needs branch protection

`CODEOWNERS` alone is inert — GitHub only *enforces* code-owner review when
a branch ruleset (or classic branch protection) turns on
`require_code_owner_review`. Installing CODEOWNERS without the ruleset gives
a false sense of security: the file exists, but nothing stops a
merge without that review. That is exactly the L3-degraded state (see
`tiers.md`): when the ruleset can't be applied (no admin, free private repo,
non-GitHub host), the skill still writes CODEOWNERS but reports it as
**advisory-only** and explains why — the CI-side ratchet and
suppression-diff still run and block via the required `quality-gate` status
check either way, but the human-review requirement is not enforced until
someone with admin turns on the ruleset.

`ruleset.json` also carries
`require_extra_approval_for_unattributed_changes` (a GitHub-added field),
which supports the same actor/judge separation goal — keep it rather than
stripping it as boilerplate.
