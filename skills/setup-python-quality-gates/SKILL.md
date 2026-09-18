---
name: setup-python-quality-gates
description: Use when setting up or hardening quality gates (lint, types, coverage, security, mutation, anti-gaming ratchet + CI) for a Python project — greenfield or existing. Measures the repo, proposes baselines that pass day one, installs in tiers.
---

# Setup Python Quality Gates

A detect → measure → propose → tier → write → verify procedure. It installs
a tamper-resistant Python quality-gate stack (lint, types, coverage,
dead-code, security, optional mutation testing, and an anti-gaming ratchet)
into greenfield or existing repos without producing a day-one wall of red.

Phases 0, 1, and 5 are non-interactive. Phases 2, 3, and 4 each end with a
user confirmation — never write, apply, or overwrite anything the user
hasn't confirmed.

## Phase 0 — Detect

1. Run `python <skill-dir>/scripts/gate_setup/detect.py <target>` (e.g.
   `python <skill-dir>/scripts/gate_setup/detect.py .` from the target repo
   root) and read the JSON it prints (keys: `pkg_manager`, `audit_export`,
   `layout.{src_layout,core_candidates,packages}`,
   `existing.{ruff,pyright,coverage,precommit,ci}`,
   `git.{host,visibility,admin,gh_auth}`).
2. For every key that came back `null` (most commonly `pkg_manager` or
   `git.host`), do not guess — state what's missing and ask the user
   directly (e.g. "no lockfile found — which package manager: uv / poetry /
   pdm / pip?").
3. Carry the full detection result forward; it drives every later phase
   (Phase 1's tool commands, Phase 2's import-linter proposal, Phase 4's
   template tokens, Phase 4's L3 eligibility).

See `references/detectors.md` for the full detector table, what each one
adapts, and its fallback behavior.

## Phase 1 — Measure

Run the actual tools against the repo to get real numbers — never propose a
threshold you haven't measured.

1. Coverage: `pytest --cov --cov-report=term-missing` (or
   `--cov-report=json` for an exact number) — read the total coverage %.
2. Complexity: `ruff check --select C901 --statistics .` — take the worst
   reported function complexity.
3. Type strictness: `pyright --outputjson` (or `--stats`) at `strict`; if it
   fails, step down through `standard` → `basic` until one passes cleanly —
   that mode is the baseline.
4. Dead code: `vulture <src> <tests> --min-confidence 60` — count findings.
5. If any tool isn't installed, install it into the project's dev
   dependencies first, using the package manager detected in Phase 0
   (`uv add --dev <tool>`, `poetry add --group dev <tool>`, etc.) — don't
   run an undeclared tool.

See `references/thresholds.md` for the exact measure/parse recipe per gate.

## Phase 2 — Propose thresholds

1. For each gate, show a **measured vs. proposed** line and ask the user to
   confirm or edit it: `"current coverage 76% → floor 76? or aim higher?"`.
2. Greenfield (near-empty repo): propose the strict canonical defaults —
   coverage 92, complexity 10, pyright `strict`, vulture confidence 60 —
   since there's no legacy debt to baseline against.
3. Legacy (existing code): propose baseline = current measured reality for
   every gate. This is what makes gates pass on day one; the ratchet in L3
   only tightens from here. Pyright legacy baseline is the mode the code
   already passes at zero errors, with a documented graduate-to-strict path
   noted in the installed docs.
4. Import-linter contracts: propose them **only if** `layout.core_candidates`
   from Phase 0 is non-empty (a clear core/domain/entities package exists).
   Show the proposed contracts (forbidden: core imports adapters/backends;
   independence among sibling adapters) and ask to opt in. If
   `core_candidates` is empty, state plainly that import-linter is skipped
   and why — never invent contracts on a flat repo.
5. Record every confirmed value against its `{{TOKEN}}`
   (`templates/TOKENS.md`) for Phase 4.

See `references/thresholds.md` for the full rules (greenfield-strict vs.
legacy-baseline, the pyright sharp edge, the confirm-loop shape).

## Phase 3 — Choose tier

1. Ask the user which tier(s) to install: L1 (local), L2 (CI + security),
   or L3 (anti-gaming + ruleset). Each is standalone — a repo can stop at
   L1 and still get real value.
2. Briefly describe what each tier adds (pulled from
   `references/tiers.md`) so the choice is informed, not blind.
3. If L3 is chosen, flag now (before Phase 4 writes anything) that its
   branch-ruleset piece needs `git.admin` truthy and an eligible repo
   (public, or a paid plan on private) — otherwise it will install
   CI-side-only and degrade the rest to advisory.

See `references/tiers.md` for full tier contents.

## Phase 4 — Write (merge + confirm)

For each target file (`pyproject.toml` gate blocks, `.pre-commit-config.yaml`,
`.github/workflows/ci.yml`, `.github/workflows/nightly-mutation.yml`,
`CODEOWNERS`, `scripts/gate_ratchet.py`, `scripts/suppression_diff.py`,
`ruleset.json`):

1. Render the template: substitute every confirmed `{{TOKEN}}`
   (`templates/TOKENS.md`); strip `# TEMPLATE-CONDITIONAL: uv-only` lines
   (currently just the `uv-lock-check` pre-commit hook) when the detected
   `pkg_manager` isn't `uv`; add the import-linter pre-commit hook and its
   `[tool.importlinter]` contracts to the rendered `pyproject.toml` only if
   the user opted in during Phase 2. `{{SRC_DIRS}}` renders differently per
   target: a TOML array (`["src/demo"]`) in `pyproject.gates.toml`, but
   space-separated paths (`src/demo`) in the `.pre-commit-config.yaml`
   vulture hook, since vulture's CLI takes positional directories, not a
   list literal. `{{PKG_INSTALL_STEP}}` also renders per detected
   `pkg_manager`: for `uv`, it expands to the `astral-sh/setup-uv` action
   step followed by `uv sync`; for poetry/pdm/pip, it's just that tool's
   install command — CI never installs `setup-uv` for a non-uv repo.
2. Create `.vulture_allowlist.py` (an empty file is enough — `touch
   .vulture_allowlist.py`) whenever the vulture gate is installed (L1), so
   the pre-commit vulture hook has something to read on day one instead of
   failing with "file not found."
3. Check `existing.<key>` from Phase 0 for that target:
   - `False` (nothing there) → write the rendered file directly.
   - `True` (something's already there) → **show a diff** of what would be
     added/changed, merge non-destructively (keep the user's existing
     rules, append only the missing gate blocks/hooks/steps), and
     **confirm before overwriting any conflicting key**. Never lower a
     threshold that's already present and higher than the proposal — state
     "keeping existing higher value N" and move on.
4. Copy `templates/scripts/gate_ratchet.py` and
   `templates/scripts/suppression_diff.py` verbatim to the repo's
   `scripts/` (no token substitution needed — they're already
   repo-agnostic). Also copy `templates/scripts/mutation_score.py` verbatim
   to `scripts/`, but only when L2's nightly mutation workflow is opted in
   (it's `nightly-mutation.yml`'s only consumer).
5. **L3 only:**
   - Write `CODEOWNERS` (owner token filled from the user).
   - **Pyright-strict gate:** the ratchet's `check_pyright` (see
     `references/anti-gaming.md`) hardcodes a requirement that
     `typeCheckingMode == "strict"` — it has no concept of "ratchet toward
     strict," only "is strict." So if Phase 2 baselined pyright below
     `strict` (a legacy repo that doesn't pass strict yet), install L1 + L2
     but hold off enabling L3's ratchet on `pyproject.toml`'s pyright block
     until the repo graduates to `strict` — otherwise every PR is red on
     the pyright ratchet check from day one. See `references/tiers.md`.
   - Apply `ruleset.json` via `gh api` **only if** `git.admin` is true and
     the repo's visibility/plan makes rulesets eligible. If either
     condition fails, do not call `gh api` — instead install the CI-side
     ratchet/suppression-diff steps (they already block merges via the
     required `quality-gate` status check regardless) and report to the
     user that CODEOWNERS/required-review are **advisory** until branch
     protection is enabled, naming the specific reason (no admin /
     private+free plan / non-GitHub host).

Re-run safety: this phase is itself ratchet-like — a config already present
and equal/higher than the proposed template value is left alone, never
reset to the template default.

## Phase 5 — Verify

Runs every installed gate once end-to-end and proves the install rather than
just asserting files were written. The verification step is implemented as
`scripts/gate_setup/verify.py`, run by path — `python
<skill-dir>/scripts/gate_setup/verify.py <target>` — not `-m`; it:

1. Runs each installed gate (ruff, pyright, pytest+coverage, vulture, and
   import-linter if opted in) and confirms all are green on day one — the
   Phase 2 baseline strategy guarantees this.
2. L2: confirms the CI workflow parses (`actionlint` if available).
3. L3: performs the **live ratchet proof** — `prove_ratchet_bites()` builds
   a throwaway temp git repo seeded from the target's `pyproject.toml` and
   `scripts/gate_ratchet.py`, lowers the coverage floor in that temp copy,
   and confirms `gate_ratchet.py` fails (exit 1) against the temp repo's
   aliased `origin/master`. It works entirely inside the temp copy and
   never writes to the real target repo, so there is nothing to revert.
   See `references/anti-gaming.md`.
4. Emits a "what I did NOT install / verify" list — e.g. "ruleset skipped:
   free private repo — CODEOWNERS advisory only," "mutation floor not
   measured — mutmut not installed."

See `references/anti-gaming.md` for exactly how `gate_ratchet.py` and
`suppression_diff.py` behave (including the real invocation — there is no
`--self-check` flag) and why CODEOWNERS needs branch protection to have
teeth.
