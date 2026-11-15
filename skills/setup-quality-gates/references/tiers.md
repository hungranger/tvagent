# Tiers (Phase 3)

Each tier is standalone — a repo can stop at L1 and get real value. Ask the
user which tier(s) they want before Phase 4 writes anything.

## L1 — local

Requires: Python + pre-commit.

Installs:
- ruff (lint + format, C901 complexity cap, no-magic-value rule via `PLR2004`)
- pyright (mode confirmed in Phase 2)
- pytest + coverage (floor confirmed in Phase 2)
- vulture (dead-code, confidence confirmed in Phase 2)
- import-linter contracts — **only if** the user opted in during Phase 2
  (i.e. `layout.core_candidates` was non-empty and they confirmed the
  proposed contracts)
- the pre-commit stage map: fast hygiene + ruff on `pre-commit`; pyright,
  pytest+coverage, pip-audit, ruff ARG, vulture, and (uv only) lock-check on
  `pre-push`

## L2 — CI + security

Requires: a GitHub remote (non-GitHub hosts get this tier described, not
auto-applied — see `detectors.md`).

Adds:
- `ci.yml`: a `quality-gate` GitHub Actions job that runs `pre-commit run`
  for both stages server-side — the single source of truth stays the
  pre-commit config, not a duplicated tool list in CI
- gitleaks, semgrep already run via pre-commit/pre-push and are mirrored by
  the same CI job
- pip-audit already wired via pre-push and CI
- optional nightly mutmut (`nightly-mutation.yml`), floor from the first
  measured run
- SHA-pinned actions (not floating tags) so CI itself isn't a supply-chain
  weak point
- lock-drift check (`uv lock --check` or the pkg-manager equivalent)

## L3 — anti-gaming

Requires: repo admin rights + a public or paid-plan repo (branch rulesets
need one of those — see `detectors.md`'s git-host detector and
`anti-gaming.md`).

**Pyright-strict constraint:** `gate_ratchet.py`'s `check_pyright` hardcodes
`typeCheckingMode == "strict"` as the pass condition — it does not ratchet
from an arbitrary starting mode, it requires `strict` outright (see
`anti-gaming.md`). A legacy repo whose Phase 2 baseline is below `strict`
(`basic`/`standard`) must install L1 + L2 only and defer enabling L3's
ratchet on the pyright gate until the repo graduates to `strict` — enabling
it earlier makes every PR red on the pyright check regardless of code
quality.

Adds:
- `scripts/gate_ratchet.py` — fails CI on any weakened or deleted threshold
  relative to `origin/master`
- `scripts/suppression_diff.py` — annotates newly-added suppressions
  (`noqa`, `type: ignore`, `--no-verify`, etc.) on the PR, non-blocking
- `CODEOWNERS` covering the gate-defining files (`pyproject.toml`,
  `.pre-commit-config.yaml`, `.github/**`, the two scripts above)
- a GitHub branch ruleset (`ruleset.json`) requiring green CI + CODEOWNER
  review + no bypass on the default branch — applied via `gh api` **only
  when** `git.admin` is true and the repo is eligible (public, or private on
  a plan that supports rulesets)

### L3 degradation

When the ruleset can't be applied (free private repo, no admin, or a
non-GitHub host), the skill still installs the CI-side pieces — the ratchet
and suppression-diff scripts run and the ratchet blocks merges through the
required `quality-gate` status check regardless of ruleset support. What's
lost without the ruleset is *enforcement* of CODEOWNERS review and
no-bypass; the skill installs CODEOWNERS anyway and reports it as
**advisory-only** until branch protection is enabled, and tells the user
exactly why (missing admin / private+free / non-GitHub).
