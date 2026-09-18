# Design: `setup-python-quality-gates` skill

**Date:** 2026-09-18
**Status:** Approved (brainstorm), pending spec review → writing-plans
**Author:** hungranger + Claude

## Purpose

A reusable Claude skill that installs a comprehensive, tamper-resistant Python
quality-gate stack into any Python repository — greenfield or existing —
without producing a day-one wall of red on legacy code. It generalizes the
stack built and proven in the `tvagent` repo (ruff, pyright, pytest+coverage,
vulture, gitleaks, semgrep, pip-audit, mutmut, import-linter, pre-commit stage
map, CI mirror, and the anti-gaming ratchet / suppression-diff / CODEOWNERS /
branch ruleset) into a detect → propose → confirm → write → verify procedure.

The skill is the packaging of a hard-won principle: **quality gates only work
if an autonomous coding agent cannot quietly weaken them.** The actor (the
agent writing code) must be separated from the judge (CI + a second identity),
and the thresholds must ratchet one way. This skill ports both the gates and
that enforcement model.

## Non-goals

- **Non-Python languages** — the skill is Python-scoped by its name; never in scope.
- **Non-GitHub hosts (GitLab/Gitea/Bitbucket) for L3 GitHub-side enforcement** —
  the host detector stubs them and degrades L3 to advisory; native support is a
  future add, not this version.
- **Auto-fixing existing gate failures** on legacy code — the baseline strategy
  makes gates pass day one, so mass auto-fix is unnecessary; out of scope.

## Design decisions (locked in brainstorm)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Install scope | **Tiered** — L1 local / L2 CI+security / L3 anti-gaming+ruleset; each standalone; user picks depth |
| 2 | Existing-repo thresholds | **Research-then-ask** — measure current reality, propose baseline, user confirms/edits each |
| 3 | import-linter | **Detect + propose, opt-in** — propose contracts only on a clear architecture shape; never invent; skip + say so on a flat repo |
| 4 | Package manager | **Detect + adapt** — uv / poetry / pdm / pip; wire lock-check + pip-audit to what's there; greenfield → offer `uv init` |
| 5 | Existing-config conflicts | **Merge + confirm** — read existing, show diff, merge non-destructively, confirm before overwriting a conflict |

## Architecture: the skill as a procedure

The skill is a superpowers-style skill directory:

```
setup-python-quality-gates/
  SKILL.md                 # the detect→propose→write→verify procedure
  references/
    thresholds.md          # how to measure + baseline each threshold
    tiers.md               # what each tier installs, standalone
    detectors.md           # the four detectors + fallbacks
    anti-gaming.md         # ratchet/suppression/CODEOWNERS/ruleset rationale
  templates/               # battle-tested config seeded from tvagent, adapted at install
    pyproject.gates.toml
    pre-commit-config.yaml
    ci.yml
    nightly-mutation.yml
    scripts/gate_ratchet.py
    scripts/suppression_diff.py
    CODEOWNERS
    ruleset.json
    docs/dev-tooling.md
    docs/agent-safety.md
```

It is a *procedure with assets*, not a black-box installer: Claude reads the
repo, adapts templates, shows diffs, and confirms — so the same skill handles
the messy reality of existing repos.

### Phased flow

```
PHASE 0  DETECT   pkg-mgr · pkg layout · existing config · git host + power
PHASE 1  MEASURE  run ruff / pyright --stats / pytest --cov / ruff C901 / vulture once
PHASE 2  PROPOSE  show measured vs proposed thresholds; user confirms/edits each
                  (import-linter contracts proposed only on a clear shape)
PHASE 3  TIER     user picks L1 / L2 / L3 depth
PHASE 4  WRITE    merge non-destructively; show diff; confirm before any overwrite
PHASE 5  VERIFY   run every installed gate green; L3: live ratchet-blocks proof;
                  emit "did NOT install/verify" list
```

Gates on the user: Phase 2 (confirm thresholds), Phase 3 (pick tier), Phase 4
(confirm overwrites). Phases 0/1/5 are non-interactive.

The spine is **detect-measure-propose**, so one code path serves both cases:
greenfield measures a near-empty repo → strict canonical defaults; legacy
measures reality → a baseline that passes day one and only tightens.

## The four detectors (Phase 0)

Each has a graceful, explicit fallback — the skill never guesses silently.

| Detector | Sniffs | Adapts | No-match fallback |
|----------|--------|--------|-------------------|
| Package manager | `uv.lock` / `poetry.lock` / `pdm.lock` / `requirements*.txt` | lock-check + pip-audit wired to that tool's export command | greenfield → offer `uv init`; otherwise ask, never guess |
| Package layout | `src/` layout, a `core/`-like pure package, top-level modules | proposes import-linter contracts only on a clear layered/hexagonal shape | flat/unclear → skip import-linter, state why |
| Existing config | `[tool.ruff]`, `.pre-commit-config.yaml`, `.github/workflows/*` | targets for merge; diff before write | none → clean install |
| Git host + power | `gh` auth, remote host, repo visibility, plan, admin rights | picks the L3 enforcement it can actually apply | no admin / free-private / non-GitHub → L3 degrades to advisory, tells user why |

## The threshold engine (Phases 1–2)

Research-then-ask. The skill measures the repo now, proposes a baseline, and
takes the user's edit on each.

| Gate | Measured by | Proposed baseline | Confirm prompt shape |
|------|-------------|-------------------|----------------------|
| coverage floor | `pytest --cov` | `floor(current %)` | "current 76% → floor 76 ok? or aim higher?" |
| complexity cap (mccabe C901) | ruff C901 scan | current worst function | "worst is 14 → cap 14 now, ratchet down?" |
| dead code | vulture | `min-confidence 60` default | confirm/adjust |
| type strictness | `pyright --stats` | greenfield → strict; legacy → the mode the code already passes + documented graduate-to-strict path | "strict fails 40 files → start at `basic`, ratchet up?" |
| mutation floor (L2+, optional) | first `mutmut` run | not blocking day 1; floor from that run | "first run scored 61 → nightly floor 60?" |

Rules baked in:
- **Greenfield → strict canonical defaults** (coverage 92, complexity 10, pyright strict) — no legacy debt to wall off.
- **Legacy → baseline = current reality**, ratchet locks it, only tightens. No red wall.
- Every proposed number is **confirmable** — measured-vs-proposed shown, user edits.
- pyright on legacy is the sharp edge: start at the strictness the code already
  passes; the ratchet forbids regression; a documented step graduates to strict later.

## The three tiers (Phase 3)

Each tier is standalone — a repo can stop at L1.

| Tier | Installs | Requires |
|------|----------|----------|
| **L1 local** | ruff (lint+format, C901, no-magic-values), pyright, pytest+coverage, vulture, import-linter (if opted), pre-commit stage map (fast pre-commit / heavy pre-push) | Python + pre-commit |
| **L2 CI + security** | GitHub Actions `quality-gate` job mirroring both pre-commit stages; gitleaks, semgrep, pip-audit; optional nightly mutmut; SHA-pinned actions; lock-drift check | a GitHub remote |
| **L3 anti-gaming** | `gate_ratchet.py` (fails PR CI on any weakened/deleted threshold), `suppression_diff.py` (annotates new noqa/type-ignore/etc.), CODEOWNERS, branch ruleset (green CI + CODEOWNER review + no bypass) | repo admin + public-or-paid repo for the ruleset |

**L3 degradation:** when the ruleset can't be applied (free private repo, no
admin, non-GitHub host), the skill installs the CI-side pieces (ratchet +
suppression-diff still run and block via the required check) and reports that
CODEOWNERS/required-review are advisory-only until protection is enabled —
exactly the tradeoff surfaced in the tvagent build.

## Templates carried

Sanitized, battle-tested copies from the tvagent repo (the ratchet and
suppression-diff scripts are already repo-agnostic and ship verbatim):

| Template | Adapted at install |
|----------|--------------------|
| `pyproject.gates.toml` (ruff/pyright/coverage/vulture/mccabe/mutmut blocks) | thresholds swapped for confirmed values; merged into existing pyproject |
| `pre-commit-config.yaml` (stage map) | lock+audit hook wired to detected pkg-mgr; pyright/pytest/lock stay `language: system` |
| `ci.yml` (quality-gate + PR-only ratchet/suppression steps) | actions SHA-pinned; pkg-mgr install step swapped |
| `nightly-mutation.yml` | floor from first run |
| `scripts/gate_ratchet.py`, `scripts/suppression_diff.py` | verbatim |
| `CODEOWNERS`, `ruleset.json` | owner + host filled; ruleset applied only if eligible |
| `docs/dev-tooling.md`, `docs/agent-safety.md` | trimmed to installed tiers |

## Idempotency / re-run

Legacy repos get run more than once; the skill must be safe to re-run and must
never weaken an already-higher bar.

```
re-run on partially-set-up repo:
  config present + matches template   → skip, report "already installed"
  config present + drifted            → show diff, merge-confirm (never blind stomp)
  config missing                      → install
  threshold already ratcheted higher  → KEEP the higher value, never lower to template default
```

The installer applies the ratchet principle to itself: it adds gates, never
loosens one already present.

## Self-verification (Phase 5)

The skill proves its own install, not merely that files were written:

1. Run every installed gate once → must be **green on day one** (baseline guarantees it).
2. L2: confirm the CI workflow parses (`actionlint` if available).
3. L3: the **live ratchet proof** — temporarily lower a threshold, confirm the
   ratchet check fails, revert cleanly. Shipped as a re-runnable `--verify`.
4. Emit a "what I did NOT install / verify" list (e.g. "ruleset skipped: free
   private repo — CODEOWNERS advisory only").

This closes the loop: detect → propose → merge → **prove it bites**.

## Success criteria

| ID | Criterion | Verified by |
|----|-----------|-------------|
| S1 | On a greenfield repo, L1 install yields strict defaults, all gates green | Phase 5 green run on a scratch empty package |
| S2 | On a legacy repo with failing strict checks, install produces gates that pass day one (baseline) | Phase 5 green run on a repo with known debt |
| S3 | Re-running the skill never lowers an already-higher threshold | idempotency test: pre-set floor 95, run skill, assert still 95 |
| S4 | Package-manager detection wires lock-check + pip-audit correctly for uv AND poetry (min.) | install on one uv and one poetry fixture repo |
| S5 | import-linter contracts proposed only on a clear shape; skipped + reported on a flat repo | install on a hexagonal fixture and a flat fixture |
| S6 | Existing `[tool.ruff]` / `.pre-commit-config.yaml` are merged, not stomped; conflicts confirmed | install over a repo with pre-existing partial config |
| S7 | L3 ratchet blocks a weakening PR (coverage floor lowered) via required CI check | the live ratchet proof (as run for tvagent PR #12) |
| S8 | L3 degrades gracefully (installs CI pieces, reports advisory-only) when ruleset can't apply | install on a free/private or no-admin repo |
| S9 | Self-verification emits an accurate "did NOT install/verify" list | inspect Phase 5 output on S8's repo |
| S10 | The skill is safe on a live repo: no uncommitted destructive change without a shown diff + confirm | Phase 4 merge-confirm behavior |

## Open risks / notes

- **pyright baseline on legacy** has no native "baseline file"; the strategy is
  to start at the passing strictness mode and ratchet the *mode*, not per-error
  suppression. The plan must specify how the ratchet detects a strictness
  downgrade (already handled in `gate_ratchet.py check_pyright`).
- **Semgrep/gitleaks network dependency** at run time — note in docs; not a blocker.
- **Ruleset JSON** carries `require_extra_approval_for_unattributed_changes`
  (GitHub auto-added) which supports the separate-identity goal; keep it.
