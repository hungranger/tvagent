---
name: setup-quality-gates
description: Use when setting up or hardening quality gates (lint, types, coverage, security, mutation, anti-gaming ratchet + CI) for a Python, Rust, Go, or React/TypeScript project — greenfield or existing. Measures the repo, proposes baselines that pass day one, installs in tiers.
---

# Setup Quality Gates

A detect → measure → propose → tier → write → verify procedure. It installs
a tamper-resistant quality-gate stack (lint, types, coverage, dead-code,
security, optional mutation testing, and an anti-gaming ratchet) into
greenfield or existing repos without producing a day-one wall of red.

Languages are **profiles** under `profiles/<lang>/profile.toml`: `python`,
`rust`, `go`, `react-ts`. A language-agnostic manifest, `quality-gates.toml`,
is the single source of truth for every threshold; native configs (ruff,
clippy.toml, golangci, biome, ...) are rendered from it and `check-drift`
proves they still match.

**Python-spine dependency:** the gate scripts (`detect`, `render`,
`manifest`, `gate_ratchet`, the guard hook) are Python using stdlib
`tomllib`, so Python >= 3.11 must be available in CI and locally even for
rust/go/react-ts repos.

Phases 0, 1, and 5 are non-interactive. Phases 2, 3, and 4 each end with a
user confirmation — never write, apply, or overwrite anything the user
hasn't confirmed.

## Phase 0 — Detect

1. Run `python <skill-dir>/scripts/gate_setup/detect.py <target>` (e.g.
   `python <skill-dir>/scripts/gate_setup/detect.py .` from the target repo
   root) and read the JSON it prints. Top level: `language`, `candidates`,
   `git.{host,visibility,admin,gh_auth}`; python detail is namespaced under
   `python.` (`python.pkg_manager`, `python.audit_export`,
   `python.layout.{src_layout,core_candidates,packages}`,
   `python.existing.{ruff,pyright,coverage,precommit,ci}`).
2. Pick the profile from `language`: exactly one signal → that profile
   (`python`, `rust`, `go`, `react-ts`). `language: null` with several
   `candidates` (polyglot repo) or none → ask the user which profile; never
   guess. The chosen `profiles/<lang>/profile.toml` drives Phases 1-4.
3. For every key that came back `null` (most commonly `python.pkg_manager`
   or `git.host`), do not guess — state what's missing and ask the user
   directly (e.g. "no lockfile found — which package manager: uv / poetry /
   pdm / pip?").
4. Carry the full detection result forward; it drives every later phase
   (Phase 1's tool commands, Phase 2's import-linter proposal, Phase 4's
   template tokens, Phase 4's L3 eligibility).

See `references/detectors.md` for the full detector table, what each one
adapts, and its fallback behavior.

## Phase 1 — Measure

Run the actual tools against the repo to get real numbers — never propose a
threshold you haven't measured.

Take the commands from the chosen profile's `[measure]` table (coverage,
complexity, lint, types, deadcode, mutation, audit, arch):

| Profile | coverage | complexity | types | deadcode |
|---|---|---|---|---|
| python | `pytest --cov` | `ruff check --select C901` | `pyright` (strict → standard → basic) | `vulture` |
| rust | `cargo llvm-cov --summary-only` | `cargo clippy` cognitive_complexity | `cargo clippy -- -D warnings` | `cargo +nightly udeps` |
| go | `go test -coverprofile` + `go tool cover -func` | `golangci-lint` gocyclo | `go vet` + `staticcheck` | `staticcheck -checks U1000` |
| react-ts | `vitest run --coverage` | biome cognitive complexity | `tsc --noEmit` | `knip` |

Read the coverage %, the worst function complexity, and the types/dead-code
finding counts. If any tool isn't installed, install it first — don't run an
undeclared tool. Python: add it to the dev dependencies with the manager
detected in Phase 0 (`uv add --dev <tool>`, `poetry add --group dev <tool>`).
Rust: `cargo install <tool>` / `rustup component add`. Go: `go install
<tool>@latest`. react-ts: `npm i -D <tool>` (or the repo's JS package
manager).

See `references/thresholds.md` for the exact measure/parse recipe per gate.

## Phase 2 — Propose thresholds

1. For each gate, show a **measured vs. proposed** line and ask the user to
   confirm or edit it: `"current coverage 76% → floor 76? or aim higher?"`.
2. Greenfield (near-empty repo): propose the profile's `[greenfield]`
   defaults (python: coverage 90, complexity 10, pyright `strict`, vulture
   confidence 60; rust/go/react-ts: coverage 80, complexity 15) — there's
   no legacy debt to baseline against.
3. Legacy (existing code): propose baseline = current measured reality for
   every gate. This is what makes gates pass on day one; the ratchet in L3
   only tightens from here. Pyright legacy baseline is the mode the code
   already passes at zero errors, with a documented graduate-to-strict path
   noted in the installed docs.
4. Python only — import-linter contracts: propose them **only if** `python.layout.core_candidates`
   from Phase 0 is non-empty (a clear core/domain/entities package exists).
   Show the proposed contracts (forbidden: core imports adapters/backends;
   independence among sibling adapters) and ask to opt in. If
   `core_candidates` is empty, state plainly that import-linter is skipped
   and why — never invent contracts on a flat repo. When skipped, drop
   `arch_contracts_min` from `[thresholds]` **and** its
   `...importlinter.contracts|len` line from `[drift]` — the arch gate and its
   drift binding are opt-in together, or check-drift fails on a missing
   `[tool.importlinter]` table.
5. Record every confirmed value in `quality-gates.toml` (the manifest) for
   Phase 4.

See `references/thresholds.md` for the full rules (greenfield-strict vs.
legacy-baseline, the pyright sharp edge, the confirm-loop shape).

## Phase 3 — Choose tier

1. Ask the user which tier(s) to install: L1 (local), L2 (CI + security),
   or L3 (anti-gaming + ruleset). Each is standalone — a repo can stop at
   L1 and still get real value.
2. Briefly describe what each tier adds (pulled from
   `references/tiers.md`) so the choice is informed, not blind.
3. L3 also needs a ruleset model: **team** (require review by a code owner)
   or **solo dev** (0 required approvals + guard hook + green CI — GitHub
   forbids self-approval). Ask which; see `references/anti-gaming.md`.
4. If L3 is chosen, flag now (before Phase 4 writes anything) that its
   branch-ruleset piece needs `git.admin` truthy and an eligible repo
   (public, or a paid plan on private) — otherwise it will install
   CI-side-only and degrade the rest to advisory.

See `references/tiers.md` for full tier contents.

## Phase 4 — Write (merge + confirm)

For each target file (`pyproject.toml` gate blocks, `.pre-commit-config.yaml`,
`.github/workflows/ci.yml`, `.github/workflows/nightly-mutation.yml`,
`CODEOWNERS`, `scripts/gate_ratchet.py`, `scripts/suppression_diff.py`,
`ruleset.json`):

0. **Manifest first.** Write the confirmed values to `quality-gates.toml`,
   then render native configs from it with
   `python <skill-dir>/scripts/gate_setup/render.py profiles/<lang> --manifest quality-gates.toml --out <target>`.
   **Never blindly re-render over an existing hand-authored
   `quality-gates.toml`**: the TOML dump does not preserve user comments.
   Edit an existing manifest in place; re-render only a fresh one. After
   writing, run, from the **target repo root**,
   `PYTHONPATH=<path-to-skill>/scripts python -P -m gate_setup.manifest check-drift --file quality-gates.toml --profile .`
   (`--file` = the target repo's manifest, `--profile` = the repo root; `-P`
   stops cwd module shadowing) to prove native configs equal the manifest. The same check runs as a blocking CI gate.
1. Render the template: substitute every confirmed template token
   (`templates/TOKENS.md`); strip `# TEMPLATE-CONDITIONAL: uv-only` lines
   (currently just the `uv-lock-check` pre-commit hook) when the detected
   `python.pkg_manager` isn't `uv`; add the import-linter pre-commit hook and its
   `[tool.importlinter]` contracts to the rendered `pyproject.toml` only if
   the user opted in during Phase 2. `SRC_DIRS` renders differently per
   target: a TOML array (`["src/demo"]`) in `pyproject.gates.toml`, but
   space-separated paths (`src/demo`) in the `.pre-commit-config.yaml`
   vulture hook, since vulture's CLI takes positional directories, not a
   list literal. `PKG_INSTALL_STEP` also renders per detected
   `python.pkg_manager`: for `uv`, it expands to the `astral-sh/setup-uv` action
   step followed by `uv sync`; for poetry/pdm/pip, it's just that tool's
   install command — CI never installs `setup-uv` for a non-uv repo.
2. Create `.vulture_allowlist.py` (an empty file is enough — `touch
   .vulture_allowlist.py`) whenever the vulture gate is installed (L1), so
   the pre-commit vulture hook has something to read on day one instead of
   failing with "file not found."
3. Check `python.existing.<key>` from Phase 0 for that target:
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
   - The CI judge runs `origin/master`'s copy of the whole `gate_setup/`
     package plus `gate_ratchet.py`; the guard casefolds paths for
     case-insensitive filesystems (see `references/anti-gaming.md`).
   - **Edit-time guard hook:** copy `templates/scripts/guard_protected_paths.py`
     verbatim to the repo's `scripts/` (stdlib-only, repo-agnostic — no token
     substitution; a repo extends the protected set via
     `.claude/protected-paths.json`), and merge `templates/claude-settings.json`'s
     `PreToolUse` block into the repo's `.claude/settings.json`
     non-destructively (create the file if absent; preserve any existing
     keys). This is the deterministic human checkpoint at edit time — it
     `ask`s before the agent writes a protected gate file or runs a
     gate-bypassing command (`gh pr merge`, push to master/main,
     `--no-verify`, ruleset/protection `gh api`). It activates on the next
     Claude Code session load. See `references/anti-gaming.md`.
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
   - **Required-approvals variant — ask which applies** (see
     `references/anti-gaming.md`, "Amending the judge & who reviews"):
     - **Team (≥ 2 humans):** require **≥ 1 approval including a code owner**
       so a *second identity* signs off on any gate change. This is
       `ruleset.json`'s default.
     - **Solo dev (one human + agent):** GitHub blocks self-approval, so
       set **required approvals = 0** (otherwise every PR deadlocks). The
       human gate is instead the edit-time guard hook above plus CI running
       `origin/master`'s ratchet — keep the required `quality-gate` check,
       no-direct-push, and no-bypass rules load-bearing.

Re-run safety: this phase is itself ratchet-like — a config already present
and equal/higher than the proposed template value is left alone, never
reset to the template default.

## Phase 5 — Verify

Runs every installed gate once end-to-end and proves the install rather than
just asserting files were written. The verification step is implemented as
`scripts/gate_setup/verify.py`, run by path — `python
<skill-dir>/scripts/gate_setup/verify.py <target>` — not `-m`; it:

1. Runs each installed gate (the profile's `[measure]` commands; for
   python: ruff, pyright, pytest+coverage, vulture, import-linter if opted in) and confirms all are green on day one — the
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
