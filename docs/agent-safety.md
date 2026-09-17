# Agent safety: keeping the quality gates un-gameable

Principle: **separate the actor (agent) from the judge (CI + human
reviewer), and keep the rules where the actor can't reach them.** An
autonomous coding agent working in this repo should never be in a position
to both weaken a gate and approve/merge its own change past it.

## Layers, and who enforces each one

| Layer | What it stops | Enforced here (repo) or by the user (harness)? |
|---|---|---|
| `.pre-commit-config.yaml` + `pyproject.toml` gate configs | Lint/type/coverage/complexity/dead-code/secret regressions | Here — config in-repo |
| `.github/workflows/ci.yml` (`quality-gate`) | Same gates, but server-side — a local `git push --no-verify` or a stripped `.venv` can't skip them | Here — CI |
| `scripts/gate_ratchet.py` (wired into `ci.yml`, `pull_request`) | An agent *loosening* a gate (lower `fail_under`, drop a ruff rule, raise `max-complexity`/`vulture` confidence, loosen pyright, drop an import-linter contract, lower the mutation floor) in the same PR that needs it loosened | Here — hard CI blocker |
| `scripts/suppression_diff.py` (wired into `ci.yml`, `pull_request`) | An agent burying new `# noqa` / `# type: ignore` / `--no-verify` / `\|\| true` / allowlist growth where a reviewer skimming the diff might miss it | Here — visibility only (prints GitHub annotations, exits 0; the teeth are the required review below) |
| `.github/CODEOWNERS` | Merging a change to a gate-defining file without a human looking at it | Here — file exists, but only *works* once branch protection (below) is on |
| Branch protection: "require review from Code Owners" + required `quality-gate` check, on `master` | Merging past either of the above without human sign-off | **User must enable** — a repo setting, not a file; also only takes effect once `CODEOWNERS` is merged to the default branch |
| Agent pushes to a feature branch only, never `master` | Agent bypassing PR review entirely | **User's harness** — the agent's git remote / token scope must not permit direct pushes to `master` |
| Agent has no rights to change repo settings, branch protection, or merge/force-push its own PR | Agent turning off the very protections above | **User's harness** — this is an identity/permissions question outside this repo's files |
| Review approval comes from a separate identity than the agent | Agent approving its own PR (self-review) | **User's harness** — GitHub can't tell "agent" from "human" by itself; the org must require an approval from an identity that isn't the agent's own token/account |
| Egress + credential scoping: no prod secrets, network allowlist | Agent exfiltrating data or reaching prod from a sandboxed CI/dev run | **User's harness** — outside this repo; scope the agent's runtime credentials and network access, not just its git permissions |

## Why the ratchet is the hard blocker and suppression-diff isn't

`gate_ratchet.py` compares numeric/set-valued config *derived facts*
(a coverage percentage, a rule set, a complexity ceiling) against
`origin/master` and fails the build on any regression — no human judgment
needed, so it's safe to make blocking.

`suppression_diff.py` flags *textual* patterns (`# noqa`, `\|\| true`,
allowlist growth) that are sometimes legitimate and sometimes not — judgment
calls. Blocking on it would either be too strict (blocks a legitimate
`# type: ignore` for a genuinely untyped third-party call) or trivially
defeated (an agent just adds a matching allowlist entry to the checker
itself). So it stays non-blocking and pushes the decision to the required
human reviewer instead, via `CODEOWNERS` + branch protection.

## What this buys, concretely

An autonomous agent with commit access to a feature branch and PR-creation
rights, but **without** repo-admin rights and **without** its own review
approval counting, cannot:

- Lower `fail_under`, widen `min_confidence`, raise `max-complexity`, drop a
  ruff rule, loosen pyright, drop an import-linter contract, or lower the
  mutation floor and have that PR merge on its own — `gate_ratchet.py`
  fails the required `quality-gate` check.
- Quietly add a `# noqa`/`--no-verify`/allowlist-growth suppression and have
  it slip past review unnoticed — `suppression_diff.py` annotates it
  inline on the PR diff.
- Edit `.pre-commit-config.yaml`, `pyproject.toml`, `.github/**`,
  `.gitleaks.toml`, `.vulture_allowlist.py`, `uv.lock`, or the ratchet
  scripts themselves and merge without a `@hungranger` review —
  `CODEOWNERS` + required Code Owner review on `master`.
- Turn any of the above off — it doesn't have repo-settings or force-push
  rights (harness-level, not this repo's to enforce).

What it does **not** buy on its own: none of this stops an agent from
writing bad *logic* that still satisfies every gate, or from a reviewer
rubber-stamping a PR without reading it. The gates raise the cost of
gaming the numbers; they don't replace reading the diff.
