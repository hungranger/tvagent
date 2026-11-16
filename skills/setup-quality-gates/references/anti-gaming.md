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

The ratchet guards the **normalized manifest** `quality-gates.toml`, not any
native config file. It reads the working tree's `quality-gates.toml`, runs
`git show origin/master:quality-gates.toml` (constant
`BASE_REF = "origin/master"`) for the base, and judges **every key
generically by its direction** in `gate_setup.manifest.KEY_DIRECTIONS`:

- `scalar-up` must not go down (`coverage_floor`, `mutation_floor`,
  `arch_contracts_min`)
- `scalar-down` must not go up (`complexity_max`, `vulture_confidence`)
- `enum` strictness index must not drop (`type_strictness`, via
  `STRICTNESS_ORDER`)
- `set` must not shrink (`lint_rules`, `protected.paths`, and
  `drift.bindings`)

There is no language-specific logic in the ratchet — it only knows keys and
directions. A key present on master but absent in the tree is a **hard
fail** (deletion is the strongest weakening); a key absent on master is new
and allowed. If `git show` can't find the base (`origin/master` not fetched),
it prints a note and skips the ratchet (bootstrap), returning 0.

**`drift.bindings` is a ratchet-tracked set.** `_flat()` emits
`drift.bindings` as the sorted `spec=key` **pairs** of the `[drift]` table
(always emitted, even as `[]`). Because it's a must-not-shrink `set`,
deleting a `[drift]` line, deleting the whole table, **or retargeting a
binding to a different native path** (which changes the `spec=key` pair) all
fail the ratchet — the same way `protected.paths` can only grow. The cost is
symmetric to `protected.paths`: a binding can never be retargeted or removed
without a CODEOWNER-reviewed master change.

**The `--self-check` flag.** The `if __name__ == "__main__":` block *always*
runs its hardcoded asserts (against two fake manifest dicts, to verify the
checker functions themselves). Then its last line is
`sys.exit(0 if "--self-check" in sys.argv else main())`: with `--self-check`
it exits 0 after the asserts **instead of** calling `main()`; without it,
`main()` runs (the real ratchet). CI invokes it with no flag.

**Native config is bound to the manifest by `check-drift`, not the ratchet.**
The ratchet floors the manifest *numbers*; `gate_setup.manifest check-drift`
is the separate blocking gate that asserts each native config file actually
*equals* its bound manifest value (see below). Three generic binding forms, all
language-agnostic (no tool names in the code — only in profile/manifest data):

- `<file>#<dotted.key>` — the value at a dotted key of a TOML/JSON file must
  `==` the manifest value.
- `<file>#<dotted.key>|len` — `len()` of the list at that key must `==` the
  manifest value. This reproduces the old import-linter *contract-count* floor
  generically: deleting a contract drops the count below the floor and fails;
  adding one without bumping the floor also fails (`==` semantics), forcing an
  intentional floor bump.
- `<file>~<regex>` — the one capture group of a regex, coerced to the manifest
  value's type, must `==` it, and the regex must match **exactly once** (0 or
  >1 matches = drift, so a same-shape decoy line can't mask a lowered real
  value). This reproduces the old nightly-mutation `--min` floor generically,
  since the nightly YAML isn't TOML/JSON and the dotted-key parser can't read
  it. The binding stays line-anchored (`(?m)^...$`) against the literal
  `--min <N>` kept in `nightly-mutation.yml`.
  The exactly-once defense only covers *same-shape* duplicate lines: a
  shape-changing edit the regex can't read (`--min=50`, or a multi-line
  `run: |` block) could dodge the binding while a same-value decoy keeps the
  match count at one. That residual leans on the server side — the workflow
  file lives under `.github/**`, which is in `[protected].paths`, so the guard
  hook asks and CODEOWNERS gates any shape-changing edit. The regex binding is
  the drift-level backstop for value edits, not the sole gate.

**Deliberately narrower than the old pyright sub-key check (F1(b)).** The old
`pyproject.toml`-based ratchet also blocked loosening pyright's
`reportMissingImports` / `reportMissingModuleSource` / `reportMissingTypeStubs`
toward `"none"`. The manifest ratchet does **not** track these. In tvagent they
are already `none` / `none` / `warning` on purpose (optional runtime backends
have no stubs), and pyright's exit code reflects **errors only** — loosening
these three toward `"none"` changes no gate outcome here, so there is nothing
to ratchet. An adopter who instead sets any of them to `"error"` as a real gate
should add it as its own `[drift]` binding (e.g.
`"pyproject.toml#tool.pyright.reportMissingImports" = "..."`), which the
generic drift mechanism enforces without code changes.

**Operational requirement:** CI must fetch `origin/master` as a real
remote-tracking ref for the ratchet to have a base to diff against —
`fetch-depth: 0` on `actions/checkout` (as in the shipped `ci.yml`), or an
equivalent full/deep clone. Without it, the ratchet skips (bootstrap note).
This is why `ci.yml`'s checkout step is pinned to `fetch-depth: 0` and has a
belt-and-braces `git fetch` of the base ref for PR events.

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

## The master-copy judge covers the whole `gate_setup/` package

CI runs `origin/master`'s copy of the judge, and that means the **entire
`gate_setup/` package** (including `manifest.py`, which loads the manifest
and implements `check-drift`), not just `gate_ratchet.py` and
`suppression_diff.py`. Otherwise a PR could neuter the judge by editing its
own `manifest.py`.

`check-drift` is a **separate blocking master-copy CI gate**: every native
config (clippy.toml, golangci, biome, ruff, ...) must equal the value in
`quality-gates.toml`. Run it as `python -P -m gate_setup.manifest
check-drift` — `-P` stops the cwd from shadowing master's modules with
PR-supplied ones. The edit-time guard `casefold`s paths so protected files
can't be dodged on case-insensitive filesystems (`Quality-Gates.toml`).

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

## Amending the judge & who reviews

Who is allowed to weaken a gate, and who signs off, depends on how many
humans the repo has. There are two supported models.

### Model 1 — TEAM (≥ 2 humans)

The classic actor/judge split. The gate-defining files (`pyproject.toml`,
`.pre-commit-config.yaml`, `.github/`, the `scripts/` judges, `CODEOWNERS`,
etc.) are owned via `CODEOWNERS`, and the branch ruleset requires **≥ 1
approval including a code owner**. A change that weakens a gate is a normal
PR that a *second human identity* must approve. The actor cannot self-merge
a weakening because the review must come from someone else.

### Model 2 — SOLO DEV (one human + an AI agent)

A solo developer has no second identity to approve their PRs — and GitHub
**blocks self-approval**, so "required approvals ≥ 1" would deadlock every
PR. The realistic setting is therefore **required approvals = 0**. The
threat model also differs: the danger isn't a careless teammate, it's the
**agent autonomously weakening a gate** mid-task. So the human checkpoint
moves to **edit time**, not review time, via two mechanisms:

1. **A deterministic PreToolUse guard hook** (`scripts/guard_protected_paths.py`,
   wired through `.claude/settings.json`). It emits `permissionDecision:
   "ask"` — routing to the human, no LLM in the loop — when the agent tries
   to (a) write a protected gate/config file, or (b) run a gate-bypassing
   command: `gh pr merge`, `git push` to master/main, `git commit
   --no-verify`, or `gh api` against rulesets / branch protection. At 0
   required approvals, the merge itself is the checkpoint the human must
   approve.
2. **CI running `origin/master`'s copy of the judge.** `ci.yml` runs
   `gate_ratchet.py` / `suppression_diff.py` fetched from `origin/master`
   (via `git show`), not the PR's own copy, so a PR that neuters its own
   judge is still graded by the untampered master version. See `ci.yml`.

### Honest limits (both models)

- **The Bash matching is heuristic**, not a shell parser. It is substring +
  write-verb / command regex; it can be evaded (obfuscated commands, indirect
  invocation). Treat it as a speed bump, not a wall.
- **The hook runs actor-side** — it is *prevention*, running in the agent's
  own session, which the agent's environment could in principle disable. It
  is not the enforcement boundary.
- **The server-side ruleset stays load-bearing.** The real boundary is the
  branch ruleset: a required `quality-gate` status check, no direct pushes to
  master, no force-push / branch deletion, and no bypass actors. This holds
  even if the hook is bypassed or absent.
- **The final layer is not handing the agent repo-admin credentials.** If the
  agent can edit the ruleset itself (admin token / `gh api .../rulesets`),
  every layer above collapses. Keep admin out of the agent's hands.
