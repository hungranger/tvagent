# Multi-language setup-quality-gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize the shipped Python-only quality-gate skill into one multi-language `setup-quality-gates` skill (python, rust, go, react-ts) on a shared language-agnostic spine driven by a normalized `quality-gates.toml` manifest.

**Architecture:** A language-agnostic spine (ratchet, guard, suppression-diff, manifest reader/validator, deterministic renderer) reads one normalized manifest; per-language profiles are DATA (`profile.toml` + config/hook/CI fragments) that a renderer emits. The manifest is the ratcheted source of truth; a drift-check CI gate binds native tool config to it. tvagent (a Python repo) is the dogfood and must stay green.

**Tech Stack:** Python 3.11 (stdlib + tomllib; spine runtime), pre-commit, GitHub Actions. Gate tools per profile prefer Rust-native binaries (ruff, clippy, Biome, cargo-llvm-cov, osv-scanner).

**Spec:** `docs/superpowers/specs/2026-11-15-generalize-quality-gates-design.md` (read it; this plan argues from it)

## Global Constraints

- Spine scripts: **stdlib + tomllib only**, Python ≥3.11, strict-typed + ruff-clean (run tools on the files explicitly; `skills/` is excluded from tvagent's own gate).
- Manifest is the single ratcheted source of truth; native config MIRRORS it, bound by a drift-check gate (never a silent mirror).
- Adding a language must edit only `profiles/` + the `KEY_DIRECTIONS` registry DATA — never ratchet/guard/render logic (anti-goal; G14).
- `KEY_DIRECTIONS` values: `scalar-up` (higher stronger), `scalar-down` (lower stronger), `enum:<ordered list>`, `set` (must-not-shrink). `type_strictness` global order: `["basic","standard","deny-warnings","strict"]`.
- Installed-into-repo spine scripts (`gate_ratchet.py`, `suppression_diff.py`, `guard_protected_paths.py`, `mutation_score.py`, `gate_setup/manifest.py`) run as **master's copy** in CI (fetch `origin/master:` copy), and are in the guard's protected set.
- Rust-native preference: tool written in Rust first, else single static binary; `impl_lang` recorded per tool in `profile.toml` (G5). Rust coverage = **cargo-llvm-cov** (not tarpaulin — Linux-only).
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Never `--no-verify`. Land via PR to master (branch protection: green `quality-gate` CI; solo-dev 0-approval). Push with `PATH="$PWD/.venv/bin:$PATH" SKIP=pip-audit`.
- tvagent must keep passing its own full pre-commit (pre-commit + pre-push) at every task boundary (G9).

## Review Focus

- **Unknown/typo manifest key** (`coverage_flor = 80`): must fail validation closed, NOT pass vacuously through the ratchet's "absent in base → skip". → Task 2 validator test.
- **PR edits an installed spine script to weaken it** (lowers a number in `manifest.py`/`gate_ratchet.py` in the PR): CI must run master's copy and still catch it. → Task 3 master-copy test.
- **Polyglot repo** (`go.mod` + `package.json` both present): detect must return `candidates` + null `language`, never silently pick. → Task 7 test.
- **Drift** (native `ruff max-complexity=20` while manifest says 10): drift-check must fail. → Task 4 drift test.
- **`[protected]` / `lint_rules` set shrinks** in a PR: ratchet must hard-fail (set-must-not-shrink), not treat as a scalar. → Task 3 set-direction test.

---

### Task 1: Rename skill dir + restructure for profiles

**Files:**
- Rename: `skills/setup-python-quality-gates/` → `skills/setup-quality-gates/` (git mv the whole tree)
- Create: `skills/setup-quality-gates/profiles/{python,rust,go,react-ts}/` (empty dirs with a `.gitkeep`)
- Move: `templates/pyproject.gates.toml`, `templates/pre-commit-config.yaml`, `templates/ci.yml`, `templates/nightly-mutation.yml` → staged for Task 9 (leave in place for now; Task 9 relocates into `profiles/python/`)
- Modify: `.pre-commit-config.yaml` (repo root) lines excluding `^skills/setup-python-quality-gates/templates/` → `^skills/setup-quality-gates/templates/` (and any other old-path references; grep first)
- Modify: `skills/setup-quality-gates/tests/*` path constants (`parents[1]` already relative — verify none hardcode the old name)
- Create: `skills/setup-quality-gates/REDIRECT.md` at the note "renamed from setup-python-quality-gates"

**Interfaces:**
- Produces: the new skill root `skills/setup-quality-gates/`; all subsequent tasks use this path.

- [ ] **Step 1: `git grep -n "setup-python-quality-gates"`** — record every reference (pre-commit excludes, docs links, test path constants).
- [ ] **Step 2: `git mv skills/setup-python-quality-gates skills/setup-quality-gates`**, create `profiles/*` dirs.
- [ ] **Step 3: Update every reference from Step 1** to the new path (root `.pre-commit-config.yaml` excludes; the 2026-09-18 spec/plan links; any test constant).
- [ ] **Step 4: Run the skill suite + tvagent gate**
  Run: `PATH="$PWD/.venv/bin:$PATH" pytest skills/setup-quality-gates/ -q && PATH="$PWD/.venv/bin:$PATH" SKIP=pip-audit pre-commit run --all-files --hook-stage pre-commit`
  Expected: skill tests pass; tvagent pre-commit green (rename is path-only, no semantics changed).
- [ ] **Step 5: Commit** `refactor(skill): rename setup-python-quality-gates → setup-quality-gates; scaffold profiles/`

---

### Task 2: `manifest.py` — validator, direction registry, `get`, `check-drift`

**Files:**
- Create: `skills/setup-quality-gates/scripts/gate_setup/manifest.py`
- Test: `skills/setup-quality-gates/tests/test_manifest.py`

**Interfaces:**
- Produces:
  - `KEY_DIRECTIONS: dict[str, str]` — e.g. `{"coverage_floor":"scalar-up","complexity_max":"scalar-down","mutation_floor":"scalar-up","vulture_confidence":"scalar-down","arch_contracts_min":"scalar-up","type_strictness":"enum","lint_rules":"set","protected.paths":"set"}`
  - `STRICTNESS_ORDER = ["basic","standard","deny-warnings","strict"]`
  - `load(path: Path) -> dict` — parse + validate; raises `ManifestError` on unknown key, wrong type, illegal enum/language.
  - `get(manifest: dict, key: str) -> str` — rendered scalar (`int`→bare, `str`→unquoted, `list`→newline-join).
  - CLI `python -m gate_setup.manifest get <key> [--file quality-gates.toml]` → stdout value, exit 0; missing/unknown → exit 2 + stderr.
  - CLI `... check-drift --profile <dir>` → exit 1 listing native-vs-manifest mismatches (reads the profile's drift map; Task 4 defines the map, so this subcommand is stubbed to "no drift sources" until Task 4 wires profiles — leave a TODO-free minimal impl that reads a `[drift]` table if present and compares).

- [ ] **Step 1: Write failing tests** in `test_manifest.py`:
  - `test_unknown_key_rejected`: `load` on `{"thresholds":{"coverage_flor":80}}` raises `ManifestError`.
  - `test_wrong_type_rejected`: `coverage_floor = "high"` raises.
  - `test_illegal_strictness_rejected`: `type_strictness = "ultra"` raises.
  - `test_illegal_language_rejected`: `meta.language = "cobol"` raises.
  - `test_get_scalar`: `get({"thresholds":{"coverage_floor":92}}, "coverage_floor") == "92"`.
  - `test_get_set_newline_joined`: `lint_rules=["E","F"]` → `"E\nF"`.
  - `test_get_missing_exits_nonzero`: CLI `get nope` exits 2.
- [ ] **Step 2: Run** `pytest skills/setup-quality-gates/tests/test_manifest.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement `manifest.py`** with the interface above; validation = a hardcoded schema dict (key→type) + `KEY_DIRECTIONS` keyset + `LANGUAGES = {"python","rust","go","react-ts"}`.
- [ ] **Step 4: Run tests** → PASS. Also `pyright`/`ruff` on the file → clean.
- [ ] **Step 5: Commit** `feat(spine): manifest.py — validate/get/check-drift + KEY_DIRECTIONS registry`

---

### Task 3: migrate `gate_ratchet.py` to the manifest

**Files:**
- Modify: `skills/setup-quality-gates/templates/scripts/gate_ratchet.py`
- Test: extend `skills/setup-quality-gates/tests/` (the ratchet self-check + a new `test_ratchet_manifest.py`)

**Interfaces:**
- Consumes: `gate_setup.manifest.KEY_DIRECTIONS`, `STRICTNESS_ORDER`.
- Produces: a ratchet that reads `quality-gates.toml` (working tree) vs `git show origin/master:quality-gates.toml`, iterating `KEY_DIRECTIONS` generically: `scalar-up` fails if cur<base, `scalar-down` fails if cur>base, `enum` fails if index drops, `set` fails if cur ⊊ base, any base-present key absent in PR = DELETED hard-fail. `BASE_REF="origin/master"` unchanged.

- [ ] **Step 1: Write failing tests** (`test_ratchet_manifest.py`, using a temp git repo + `refs/remotes/origin/master` like `verify.py` does):
  - `test_lowered_coverage_fails` (scalar-up down).
  - `test_raised_complexity_fails` (scalar-down up).
  - `test_strictness_downgrade_fails` (strict→standard).
  - `test_lint_rules_shrink_fails` (set loses "C901").
  - `test_protected_paths_shrink_fails` (set loses ".github/**").
  - `test_deleted_key_fails` (base has mutation_floor, PR omits it).
  - `test_new_key_allowed` (PR adds a key absent on base).
  - Update the in-script self-check (`__main__` asserts) to the manifest shape.
- [ ] **Step 2: Run** → FAIL (ratchet still parses pyproject).
- [ ] **Step 3: Rewrite the ratchet's check functions** to the generic registry-driven loop over `quality-gates.toml`; delete the per-`[tool.*]` parsing. Keep the master-copy/BASE_REF behavior.
- [ ] **Step 4: Run** tests + `python templates/scripts/gate_ratchet.py` self-check → PASS.
- [ ] **Step 5: Commit** `feat(spine): ratchet reads quality-gates.toml via KEY_DIRECTIONS`

---

### Task 4: `render.py` + `profile.toml` schema + drift map

**Files:**
- Create: `skills/setup-quality-gates/scripts/gate_setup/render.py`
- Create: `skills/setup-quality-gates/profiles/SCHEMA.md` (documents `profile.toml`)
- Test: `skills/setup-quality-gates/tests/test_render.py`

**Interfaces:**
- Consumes: `manifest.get`.
- Produces:
  - `profile.toml` schema: `[gates.<name>] tools = [..]`, `impl_lang = "rust"|...`, `threshold_key = "coverage_floor"|null`, `threshold_mechanism = "flag"|"config"|"none"`, `blocking = true|false`; `[drift] <native_path>#<key> = "<manifest_key>"` map; `[coverage] metric`, `[measure] <gate> = "<shell recipe>"`, `[greenfield] <key> = <value>`.
  - `render(profile_dir: Path, manifest: dict) -> dict[str, str]` — returns `{relative_path: rendered_content}` for native config + merged pre-commit hooks + ci/nightly fragments, substituting manifest values where `threshold_mechanism="flag"` and emitting native config where `"config"`.
  - CLI `python -m gate_setup.render <profile_dir> --manifest quality-gates.toml --out <dir>`.

- [ ] **Step 1: Write failing tests** with a tiny fake profile fixture under `tests/fixtures/profile_fake/`:
  - `test_render_emits_flag_from_manifest`: a `flag` gate's rendered CI step contains the manifest's coverage value.
  - `test_render_emits_native_config`: a `config` gate writes the native file with the manifest value.
  - `test_render_no_residual_tokens`: no `{{` remains.
  - `test_render_deterministic`: two renders byte-identical.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `render.py`**; wire `manifest.py check-drift` to read the `[drift]` map (completes Task 2's stub).
- [ ] **Step 4: Run** → PASS; add `test_check_drift_detects_mismatch` to `test_manifest.py` now that `[drift]` is defined.
- [ ] **Step 5: Commit** `feat(spine): render.py + profile.toml schema + drift map`

---

### Task 5: generalize `suppression_diff.py` tokens

**Files:**
- Modify: `skills/setup-quality-gates/templates/scripts/suppression_diff.py`
- Test: `skills/setup-quality-gates/tests/test_suppression_tokens.py`

**Interfaces:**
- Produces: a per-language `SUPPRESSION_TOKENS` map; the scan flags any added line containing a token regardless of file extension.

- [ ] **Step 1: Write failing tests** asserting each new token is flagged: `#[allow(`, `#![allow(`, `//nolint`, `// eslint-disable`, `eslint-disable-next-line`, `// @ts-ignore`, `// @ts-expect-error`, `// @ts-nocheck`, `// biome-ignore` (plus the existing python ones still flagged).
- [ ] **Step 2: Run** → FAIL. **Step 3:** add the token map. **Step 4:** PASS. **Step 5: Commit** `feat(spine): per-language suppression tokens`

---

### Task 6: generalize `guard_protected_paths.py`

**Files:**
- Modify: `skills/setup-quality-gates/templates/scripts/guard_protected_paths.py`
- Test: extend `skills/setup-quality-gates/tests/test_guard_protected_paths.py`

**Interfaces:**
- Produces: default protected set covering all four ecosystems (`Cargo.toml/Cargo.lock`, `go.mod/go.sum`, `package.json`[root-only]/`package-lock.json`/`pnpm-lock.yaml`/`yarn.lock`/`tsconfig.json`/`biome.json`, `clippy.toml`, `quality-gates.toml`) ∪ `.claude/protected-paths.json` ∪ manifest `[protected].paths` (union only — never shrink).

- [ ] **Step 1: Write failing tests**: Edit `Cargo.toml`→ask; `go.mod`→ask; `tsconfig.json`→ask; `quality-gates.toml`→ask; root `package.json`→ask; nested `src/x/package.json`→silent (root-only rule); a manifest `[protected]` entry is honored.
- [ ] **Step 2–4:** RED → implement → GREEN. **Step 5: Commit** `feat(spine): guard protects all four ecosystems' gate files`

---

### Task 7: `detect.py` language detection

**Files:**
- Modify: `skills/setup-quality-gates/scripts/gate_setup/detect.py`
- Test: extend `tests/test_detect.py` + 4 language fixtures under `tests/fixtures/`

**Interfaces:**
- Produces: `detect(root)` returning `{"language": str|None, "candidates": [str...], "git": {...}, "<lang>": {pkg_manager, existing:{...}}}`. Precedence: exactly one primary signal → that language; multiple → `language=None, candidates=[...]`; none/unsupported (plain-JS `package.json`) → `language=None, candidates=[]`.

- [ ] **Step 1: Write failing tests**: `Cargo.toml`→rust; `go.mod`→go; `package.json`+`tsconfig.json`→react-ts; `pyproject.toml`→python; `go.mod`+`package.json`→`language=None, candidates=["go","react-ts"]`; bare `package.json` (no tsconfig/react dep)→`language=None, candidates=[]`.
- [ ] **Step 2–4:** RED → implement the signal detector (keep existing python fields namespaced under `python`) → GREEN.
- [ ] **Step 5: Commit** `feat(spine): multi-language detection with candidates`

---

### Task 8: `verify.py` manifest seed + mutation adapters

**Files:**
- Modify: `skills/setup-quality-gates/scripts/gate_setup/verify.py`
- Create: `skills/setup-quality-gates/scripts/gate_setup/mutation_adapters/__init__.py` (+ `mutmut.py`, `cargo_mutants.py`, `stryker.py`, `gremlins.py`)
- Modify: `skills/setup-quality-gates/templates/scripts/mutation_score.py` (dispatch to adapter by `--tool`)
- Test: `tests/test_verify.py` (update), `tests/test_mutation_adapters.py`

**Interfaces:**
- `verify.prove_ratchet_bites` seeds the temp repo from `quality-gates.toml`, lowers `coverage_floor`.
- `mutation_adapters.score(tool: str, raw: str) -> int` — one normalized score per tool from a captured sample output.

- [ ] **Step 1: Write failing tests**: `test_verify_seeds_manifest` (bites on lowered coverage_floor, pyproject untouched); `test_<tool>_adapter_parses` for each of the 4 using a captured sample string.
- [ ] **Step 2–4:** RED → implement → GREEN. **Step 5: Commit** `feat(spine): verify seeds manifest; per-tool mutation adapters`

---

### Task 9: python profile + tvagent dogfood migration (G9)

**Files:**
- Create: `skills/setup-quality-gates/profiles/python/profile.toml` (+ moved `pyproject.gates.toml`, `pre-commit-hooks.yaml`, `ci-steps.yaml`, `nightly.yml`, `protected.toml` from `templates/`)
- Create: `quality-gates.toml` (repo root — tvagent's own: coverage 92, complexity 10, mutation 90, strict, vulture 60, `lint_rules` = tvagent's ruff select set, arch_contracts 3, `[protected]`)
- Modify: tvagent `.github/workflows/ci.yml` — ratchet/suppression steps already run master's copy; add the manifest install + master-copy for `manifest.py`; keep the `quality-gate` check name
- Test: `tests/test_profile_python.py`

**Interfaces:**
- Consumes: render.py, manifest.py. Produces the python profile as the template for G3/G4/G5 assertions.

- [ ] **Step 1: Write failing tests**: `test_python_profile_renders` (render(python, tvagent-manifest) reproduces the current pyproject gate blocks); `test_python_rust_native_first` (ruff `impl_lang="rust"` listed first for lint); `test_drift_python` (mutating pyproject max-complexity while manifest=10 → check-drift fails).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Author `profiles/python/`** from the existing Python config; create tvagent's root `quality-gates.toml` with its CURRENT values (so the first post-migration ratchet baseline equals today's gates).
- [ ] **Step 4: Verify tvagent stays green** (G9):
  Run: `PATH="$PWD/.venv/bin:$PATH" pytest -q && PATH="$PWD/.venv/bin:$PATH" SKIP=pip-audit pre-commit run --all-files --hook-stage pre-commit && PATH="$PWD/.venv/bin:$PATH" SKIP=pip-audit pre-commit run --all-files --hook-stage pre-push`
  Expected: all green; the ratchet now reads `quality-gates.toml`.
- [ ] **Step 5: Commit** `feat(profile): python profile + tvagent quality-gates.toml migration`

---

### Task 10: rust profile

**Files:**
- Create: `skills/setup-quality-gates/profiles/rust/{profile.toml,pre-commit-hooks.yaml,ci-steps.yaml,nightly.yml,protected.toml,clippy.toml.tmpl}`
- Create: `skills/setup-quality-gates/tests/fixtures/rust_min/` (tiny crate: `Cargo.toml`, `src/lib.rs` with one tested fn)
- Test: `tests/test_profile_rust.py`

**Interfaces:**
- Produces the rust profile: lint/format = clippy+rustfmt, types = `clippy -D warnings`, coverage = **cargo-llvm-cov** (`--fail-under $(manifest get coverage_floor)`, flag), complexity = clippy `cognitive-complexity-threshold` in clippy.toml (config/drift), dead-code = cargo-udeps, mutation = cargo-mutants (blocking), audit = cargo-audit, arch = optional.

- [ ] **Step 1: Write failing tests**: `test_rust_profile_valid` (render + validate); `test_rust_coverage_is_llvm_cov` (not tarpaulin); `test_rust_complexity_is_drift` (`threshold_mechanism="config"`); `test_rust_rust_native_flags` (clippy/rustfmt/llvm-cov `impl_lang="rust"`).
- [ ] **Step 2–3:** RED → author `profiles/rust/` per the spec's tool map.
- [ ] **Step 4: e2e (toolchain-gated)**: `test_rust_e2e_green` — skip unless `cargo` present; else render onto `rust_min`, run the fast gates, assert green on clean code.
- [ ] **Step 5: Commit** `feat(profile): rust (clippy/rustfmt/cargo-llvm-cov/cargo-mutants)`

---

### Task 11: go profile

**Files:** `profiles/go/*`, `tests/fixtures/go_min/` (`go.mod`, one tested pkg), `tests/test_profile_go.py`

**Interfaces:** lint = golangci-lint (incl. gocyclo complexity via config), format = gofmt, types = `go vet`+staticcheck, coverage = `go test -coverprofile` → `go tool cover -func|total` (recipe), mutation = gremlins (**non-blocking**), audit = govulncheck, dead-code = staticcheck.

- [ ] **Step 1: Write failing tests**: `test_go_profile_valid`; `test_go_mutation_non_blocking` (`blocking=false`); `test_go_coverage_recipe` (aggregates to total %).
- [ ] **Step 2–3:** RED → author. **Step 4:** toolchain-gated e2e (`go` present). **Step 5: Commit** `feat(profile): go (golangci-lint/staticcheck/govulncheck/gremlins-opt)`

---

### Task 12: react-ts profile (Biome)

**Files:** `profiles/react-ts/{profile.toml,biome.json.tmpl,...}`, `tests/fixtures/ts_min/` (`package.json`+`tsconfig.json`+one tested module), `tests/test_profile_react_ts.py`

**Interfaces:** lint+format = **Biome** (one binary, replaces prettier+eslint), complexity = Biome `maxAllowedComplexity` (config/drift), types = `tsc --noEmit` (strict from tsconfig), test+cov = vitest (`coverage_floor`→vitest `lines`), dead-code = knip, mutation = stryker, audit = osv-scanner/npm audit, arch = dependency-cruiser (optional).

- [ ] **Step 1: Write failing tests**: `test_ts_uses_biome_not_prettier_eslint` (profile tools for lint+format == Biome, `impl_lang="rust"`); `test_ts_types_tsc_strict`; `test_ts_coverage_maps_vitest_lines`.
- [ ] **Step 2–3:** RED → author. **Step 4:** toolchain-gated e2e (`node` present). **Step 5: Commit** `feat(profile): react-ts (Biome/tsc/vitest/knip/stryker)`

---

### Task 13: SKILL.md + references generalization

**Files:**
- Modify: `skills/setup-quality-gates/SKILL.md` (Phase 0 detect→profile; Phase 1/2 per-profile measure/propose; Phase 4 render+drift+guard+manifest; team vs solo-dev ruleset)
- Modify: `references/{detectors,thresholds,tiers,anti-gaming}.md`
- Test: `tests/test_skill_doc.py` (extend)

- [ ] **Step 1: Write failing tests**: SKILL.md references each profile + the manifest + drift-check + the Python-spine-dependency note; anti-gaming.md documents master-copy judge covers `manifest.py` too; no `{{`-unfilled or `setup-python-quality-gates` leftovers.
- [ ] **Step 2–4:** RED → write the docs (mine per-profile Phase 1/2 recipes from each `profile.toml [measure]`) → GREEN.
- [ ] **Step 5: Commit** `docs(skill): multi-language SKILL.md + references`

---

### Task 14: Comprehensive verification (G1–G14)

**Files:**
- Create: `skills/setup-quality-gates/VERIFICATION.md`
- Test: `tests/test_template_integrity.py` (extend: every profile's referenced scripts exist; every profile validates; G14 structural check)

- [ ] **Step 1:** Map each of G1–G14 to a concrete test/step in `VERIFICATION.md`.
- [ ] **Step 2: Write the G14 structural test**: assert the spine files (`gate_ratchet.py`, `guard_protected_paths.py`, `render.py`, `manifest.py`) contain no literal language name from `{rust,go,react-ts}` in their logic (profiles carry all language specifics).
- [ ] **Step 3: Run the full suite + tvagent gate**
  Run: `PATH="$PWD/.venv/bin:$PATH" pytest skills/setup-quality-gates/ -v && PATH="$PWD/.venv/bin:$PATH" pytest -q && PATH="$PWD/.venv/bin:$PATH" SKIP=pip-audit pre-commit run --all-files --hook-stage pre-push`
  Expected: all green.
- [ ] **Step 4: Write "What I did NOT verify"**: real CI runners, L3 ruleset e2e, live install of rustc/go/node toolchains (e2e tests skip without them), per-language mutation tools run end-to-end.
- [ ] **Step 5: Commit + open PR** `gh pr create --base master` (body: multi-language generalization, link spec; ends with the Claude Code attribution).

---

## Self-Review

**1. Spec coverage:**

| Spec item | Task |
|-----------|------|
| Decision 1 manifest+drift | T2 (manifest), T4 (drift/render) |
| Decision 6 Python spine / pre-commit dep | T13 anti-gaming.md; every profile `language: system` |
| Decision 7 render.py | T4 |
| B1 richer manifest + registry | T2 |
| B2 drift-check | T4 + T9 drift test |
| B3 manifest.py install/protected/master-copy | T2, T6 (protected), T9 (CI master-copy) |
| B4 strictness enum order | T2, exercised T3 |
| B5 migration ordering | T1 (rename/excludes) + T9 (manifest/switch) |
| A1 profile schema | T4 |
| A2 detection shape/precedence | T7 |
| A3 ratchet set/enum/deleted/meta | T3 |
| A4 rust-native + llvm-cov | T10, assertions T9/T10/T12 |
| A5 blocking flag | T4 schema, T11 go-mutation test |
| A6 coverage per-profile + Phase 1/2 | T9–T12 profiles, T13 SKILL.md |
| suppression tokens | T5 |
| guard generalization/union/lockfiles | T6 |
| mutation adapters / verify seed | T8 |
| nightly per-profile | T9–T12 (`nightly.yml` each) |
| G1–G14 | T7, T3, T10–T12, T12(G4), T10(G5), T6, T5, T9, T13, T2(G13), T4(G12), T14(G14) |

Gaps: none unmapped. G10 (ruleset/master-copy unchanged) is asserted in T13 docs + the existing hardening tests carried through T3.

**2. Step scan:** Each code step names a signature + its file; test steps name assertions with exact values (92/10/90, token strings, enum order). No full function bodies (the spine logic is registry-driven, left to the implementer). No "TBD"/"handle edge cases".

**3. Type consistency:** `KEY_DIRECTIONS`/`STRICTNESS_ORDER`/`load`/`get`/`check-drift` (T2) are the names T3/T4/T9 consume. `detect()` return shape (T7) matches the spec. `render(profile_dir, manifest)->dict` (T4) consumed by T9–T12. `mutation_adapters.score(tool, raw)->int` (T8) consumed by mutation_score.

**4. Review Focus:** all five lines have an owning test (T2 typo, T3 master-copy+set, T7 polyglot, T4 drift) — pinned above.

**5. Proportion:** plan carries interfaces + test names + exact values, not bodies; the registry-driven spine means the real code is short and idiomatic. Plan is not a transcript.
