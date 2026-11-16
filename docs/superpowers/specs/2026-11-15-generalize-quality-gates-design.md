# Design: generalize `setup-python-quality-gates` → multi-language `setup-quality-gates`

**Date:** 2026-11-15
**Status:** Draft (brainstorm) — pending builder-check + user approval → writing-plans
**Supersedes/extends:** `docs/superpowers/specs/2026-09-18-quality-gates-skill-design.md` (the Python-only skill, now shipped on master)

## Intent & why

The shipped `setup-python-quality-gates` skill installs a tiered, tamper-resistant quality-gate stack — but only for Python, because its ratchet parses `pyproject.toml` and its gates are Python tools. The anti-gaming spine (ratchet, suppression-diff, PreToolUse guard hook, master-copy CI judge, ruleset model) is **already language-neutral**; only the gate *tools* and the *threshold source* are Python-specific. Generalize the skill to Rust, Go, and React (TypeScript) by extracting that spine and adding per-language gate profiles, so the same anti-gaming guarantees apply to any of the four ecosystems.

## Goals

- One multi-language skill, renamed `setup-quality-gates`, that detects a repo's primary language and installs the matching gate profile on the shared spine.
- A **language-neutral threshold manifest** (`quality-gates.toml`) as the single source of truth the ratchet guards, replacing `pyproject.toml` parsing.
- Gate profiles for **python, rust, go, react-ts**, each prefering a **Rust-native single-static-binary tool** wherever a mature one covers the gate.
- The full anti-gaming spine works unchanged across all four: ratchet (guard manifest vs origin/master), suppression-diff, PreToolUse guard hook (protected files generalized), master-copy CI judge, ruleset.
- The existing Python behavior is preserved (a Python repo gets the same gates it gets today, now driven through the manifest).

## Non-goals

- **Polyglot repos (multiple active profiles in one repo).** v1 detects ONE primary language; if several are present it asks the user which to gate. True multi-manifest support is a documented follow-up.
- **Languages beyond the four named.** The profile mechanism is extensible, but only python/rust/go/react-ts ship.
- **Replacing a type checker that has no mature Rust equivalent.** tsc (TS) and pyright (Python) stay until Astral's `ty`/red-knot matures; the profile is structured so that swap is one line later.
- **New anti-gaming mechanisms.** The spine is reused, not redesigned.

## Anti-goals (failure even if it "works")

- A design where adding a 5th language requires editing the spine. Profiles must be additive data, not spine code changes.
- Threshold drift: a gate's effective threshold differing from what the ratchet guards. The manifest must be the single source the tools READ, not a mirror.
- A Python-shaped abstraction that only superficially supports the others (e.g. assuming every language has a single config file, or that coverage is always a percentage flag).

## Locked decisions (from brainstorm)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Threshold source | **Normalized manifest** `quality-gates.toml` is the ratcheted source of truth; because many thresholds are config-file-only (no CLI flag), native config MIRRORS the manifest and a **drift-check CI gate** fails if they differ (checked mirror, not silent) |
| 2 | Packaging | **One multi-language skill** `setup-quality-gates`; `detect.py` senses language → loads profile |
| 3 | Scope | **Spine refactor + all 3 new profiles** (rust, go, react-ts) alongside the migrated python profile |
| 4 | Tool preference | **Prefer tools written in Rust; else a single static binary** per gate; ecosystem-native only where neither exists. A `impl_lang`/`rust_native` flag in profile.toml makes this testable (G5) |
| 5 | Polyglot | **One primary language per repo** in v1; ask when ambiguous; multi-manifest is future |
| 6 | Spine runtime | **Accept the Python spine** — reuse the shipped ratchet/guard/manifest/suppression scripts as-is; a Rust/Go/TS repo gains Python 3.11 + pre-commit as a dev/CI dependency (only to run the gate scripts). Stated honestly in anti-gaming.md |
| 7 | Mechanical rendering | A deterministic **`render.py`** emits the per-profile config/hooks/CI from `profile.toml` + the confirmed manifest; the agent does only the measure/propose/confirm loop (so install is CI-testable) |

## Architecture

```
setup-quality-gates/
  SKILL.md                     detect → choose profile → write manifest+config → verify
  scripts/                     SPINE (language-agnostic, reused verbatim where possible)
    gate_ratchet.py              reads quality-gates.toml ONLY (was: pyproject.toml)
    suppression_diff.py          unchanged
    guard_protected_paths.py     protected set generalized per profile
    mutation_score.py            unchanged
    gate_setup/
      detect.py                  language + layout + pkg-mgr + git detection
      manifest.py                validate quality-gates.toml; `get <key>`, `check-drift`; owns KEY_DIRECTIONS + strictness order
      render.py                  deterministic: profile.toml + manifest → native config / hooks / CI steps
      verify.py                  live ratchet-bites proof (seeds from quality-gates.toml, lowers coverage_floor)
      mutation_adapters/         per-tool parsers (mutmut, cargo-mutants, stryker, gremlins) → a common score
  profiles/
    python/   rust/   go/   react-ts/
      profile.toml               the tool→config→hook→CI mapping + preference order
      pre-commit-hooks.yaml      profile's hooks (fast stage / heavy stage)
      ci-steps.yaml              profile's CI install + gate steps
      protected.toml             profile's protected-file list (merged into guard defaults)
  templates/                   spine templates (ci.yml skeleton, ruleset.json, CODEOWNERS, claude-settings.json, quality-gates.toml)
  references/  tests/
```

### The normalized manifest (`quality-gates.toml`)

Single source of truth, committed at repo root. Richer than the first sketch — it must carry everything the Python ratchet guards today (B1), typed by direction. Example (python, post-migration):

```toml
[meta]
language = "python"            # ratcheted: changing it must not silently drop gates (see below)

[thresholds]                    # each key's DIRECTION comes from manifest.py's registry, not here
coverage_floor   = 92           # scalar, higher-is-stronger  → lowering fails
complexity_max   = 10           # scalar, lower-is-stronger   → raising fails
mutation_floor   = 90           # scalar, higher-is-stronger
type_strictness  = "strict"     # enum (global order basic<standard<deny-warnings<strict) → downgrade fails
vulture_confidence = 60         # scalar, lower-is-stronger (python-only)
lint_rules = ["E","F","I","UP","B","SIM","PL","RUF","N","C4","C901","PTH"]  # SET, must-not-shrink (python ruff select)
arch_contracts_min = 3          # scalar, higher-is-stronger (python import-linter contract count)

[protected]                     # SET, must-not-shrink; extends the guard hook's default set
paths = ["pyproject.toml","quality-gates.toml",".github/**","scripts/**","CODEOWNERS"]
```

- **Direction registry (B1, A3).** `manifest.py` owns a `KEY_DIRECTIONS` map: each known key → one of `scalar-up` (higher stronger), `scalar-down` (lower stronger), `enum:<ordered-list>`, `set` (must-not-shrink). The ratchet consults this registry; profiles declare which keys they use but never define direction. So **adding a language never edits the ratchet** (anti-goal satisfied). An unknown key fails validation closed (prevents a `coverage_flor` typo passing vacuously).
- **Who reads it (B2 — drift-check, not pure drive-from):**
  - Where a tool has a CLI flag, the hook/CI step passes `--flag $(python scripts/gate_setup/manifest.py get coverage_floor)` (coverage, gocyclo `-over`).
  - Where a threshold is config-file-only (ruff `max-complexity`, clippy `cognitive-complexity-threshold`, Biome `maxAllowedComplexity`), native config holds the value and a **`drift-check` gate** (`manifest.py check-drift`) fails if the native config value ≠ the manifest value. Checked mirror.
  - `gate_ratchet.py` compares the PR manifest vs `origin/master:quality-gates.toml` per the registry; the guard hook protects `quality-gates.toml`.
- **`manifest.py` contract (B3).** Ships in `templates/scripts/gate_setup/` and is copied into the target repo's `scripts/` at install, added to the guard's protected set, and in CI the gate steps run **master's copy** (same master-copy judge rule as the ratchet) so a PR can't edit `manifest.py` to print a weaker number. `get <key>`: prints the raw value (int bare, string unquoted, list newline-joined) to stdout, exit 0; missing/unknown key → exit non-zero + stderr (never a silent empty flag). `check-drift`: exit non-zero listing each native-vs-manifest mismatch. stdlib + `tomllib` only.
- **`type_strictness` enum (B4).** One global ordered list in `manifest.py`: `["basic","standard","deny-warnings","strict"]` (keeps pyright's `standard`). Each profile declares the subset it accepts and the mapping to its tool (python→pyright mode; react-ts→tsconfig `strict` true/false→strict/basic; rust→`strict`=`clippy::pedantic -D warnings`, `deny-warnings`=`-D warnings`; go→`strict`=staticcheck+vet, `basic`=vet). Ratchet treats a move down the list as weakening; an unknown value fails closed. This replaces the current hardcoded `== "strict"` with a real downgrade-only ratchet; SKILL.md's "hold L3 until strict" note becomes "ratchet forbids downgrading from wherever you baseline."
- **`meta.language` + `[protected]` (A3).** Changing `meta.language` is allowed, but every threshold key present on master and absent in the PR still hard-fails as a deletion — so you can't drop gates by switching language. `[protected].paths` is a `set` key: removing an entry fails the ratchet.
- Thresholds that don't apply to a language are omitted at install; deleting a present one later hard-fails. An empty/absent manifest on master → ratchet skips (fresh-repo bootstrap), unchanged.

### Per-language profiles (Rust-native first)

| gate | python | rust | go | react-ts |
|------|--------|------|-----|----------|
| lint | ruff | clippy | golangci-lint / go vet | **Biome** |
| format | ruff format | rustfmt | gofmt | **Biome** |
| types | pyright | (rustc via clippy -D) | (go build) | tsc --noEmit |
| test+coverage | pytest+coverage | cargo + tarpaulin | go test -cover | vitest --coverage |
| complexity | ruff C901 | clippy cognitive_complexity | gocyclo | Biome / oxlint |
| dead code | vulture | cargo-udeps | staticcheck | knip |
| mutation (nightly) | mutmut | cargo-mutants | gremlins *(optional/non-blocking)* | stryker |
| deps audit | pip-audit | cargo-audit | govulncheck | osv-scanner / npm audit |
| secrets | gitleaks | gitleaks | gitleaks | gitleaks |
| SAST | semgrep | semgrep | semgrep | semgrep |
| architecture | import-linter | (crate graph — optional) | (package graph — optional) | dependency-cruiser |

Each `profile.toml` lists, per gate, an ordered tool list (`preferred` first = the Rust-native one where it exists) + how the hook/CI step reads its threshold from the manifest. Secrets (gitleaks) and SAST (semgrep) are shared spine hooks, not per-profile.

### Detection

`detect.py` returns a `language` field from the dominant signal:

| Signal file | language |
|-------------|----------|
| `Cargo.toml` | rust |
| `go.mod` | go |
| `package.json` + (`tsconfig.json` or a react/vite/next dep) | react-ts |
| `pyproject.toml` / `setup.py` | python |

If more than one primary signal is present, SKILL.md Phase 0 lists them and asks the user which to gate (single-language v1). Existing detect fields (pkg-manager, layout, existing-config, git) are retained and, where language-specific (e.g. pkg-manager), namespaced under the language.

### Spine generalization (what changes vs the Python skill)

- `gate_ratchet.py`: change its base file from `pyproject.toml` to `quality-gates.toml`; its check functions read `[thresholds]` keys instead of `[tool.*]`. Direction logic (lower floor = weaker, raise cap = weaker, strictness-enum downgrade = weaker, deletion = hard-fail) is unchanged. `BASE_REF = "origin/master"` unchanged. Self-check updated to the manifest shape.
- `suppression_diff.py`: unchanged (it scans added lines for suppression tokens across any language — extend the token set with per-language suppressions: `#[allow(...)]` Rust, `//nolint` Go, `// eslint-disable` / `// @ts-ignore` / `// biome-ignore` TS).
- `guard_protected_paths.py`: generalize the default protected basenames to cover all four ecosystems' gate/lock/config files + `quality-gates.toml`; still merges `.claude/protected-paths.json` and the profile's `protected.toml`.
- CI (`ci.yml`): the gate steps become profile-driven (the install step + each gate step come from the profile's `ci-steps.yaml`); the **master-copy judge** hardening (run `origin/master`'s copy of ratchet/suppression) is unchanged.
- ruleset / CODEOWNERS / master-copy judge / solo-vs-team model: unchanged (language-neutral).

### Migration of the existing Python skill

Rename `skills/setup-python-quality-gates/` → `skills/setup-quality-gates/`. The current Python tool config (`pyproject.gates.toml`, the pre-commit hooks, ci steps) becomes `profiles/python/`. The shipped Python skill's behavior is preserved: a Python repo still gets ruff/pyright/pytest/vulture/mutmut/import-linter, now with thresholds sourced from `quality-gates.toml` instead of inline `pyproject.toml` values (SKILL.md Phase 4 writes both: the manifest for ratcheted thresholds, and the native config that reads them). tvagent itself is a Python repo and must keep passing its own gates — a migration smoke test.

## Builder-check resolutions (my calls, unless marked)

- **Profiles are DATA + a renderer (A1).** `profile.toml` is data; `render.py` consumes it to emit native config, the merged `pre-commit-config.yaml`, and `ci.yml`/`nightly.yml` steps deterministically. The agent does only measure/propose/confirm (Phases 1–3); render + merge are mechanical and CI-testable (makes G3/G4 automatable). The existing `{{TOKEN}}` templates survive as the spine skeleton; profile fragments fill the language-specific blocks. `profile.toml` schema: per gate → `{ tools = [ordered], impl_lang, threshold_key?, threshold_mechanism = "flag"|"config"|"none", blocking = true|false }`.
- **Detection (A2).** Precedence when multiple roots match: ask the user (no silent pick). Root-only scan in v1 (monorepo subdir scan is future). Return shape `{ "language": <str|null>, "candidates": [<str>...], "git": {...}, "<lang>": { pkg_manager, existing:{...}, ... } }` — `git` stays top-level; language-specific fields are namespaced. Zero signals or a non-React `package.json` (plain JS / Node backend) → `language: null, candidates: []` and SKILL.md stops with "unsupported — supported: python/rust/go/react-ts". `setup.py`-only counts as python. Cargo workspace root vs member: treat the root as the repo language.
- **Rust-native meaning (A4).** "Preferred" = written in Rust; where none exists, a single static binary; else ecosystem-native. `profile.toml` carries `impl_lang` per tool so G5 is a concrete assertion. Coverage for rust = **cargo-llvm-cov** (cross-platform incl. macOS), NOT tarpaulin (Linux-only). Complexity gates that are config-only (clippy `cognitive-complexity-threshold` in clippy.toml, Biome `maxAllowedComplexity` in biome.json, ruff `max-complexity`) are driven by the drift-check, not a flag.
- **Blocking vs advisory (A5).** `profile.toml` per-gate `blocking` field. Advisory gates (Go mutation, Rust/TS architecture) run in CI but don't fail it, and their threshold is still in `[thresholds]` if present so the ratchet guards it when set — advisory means "doesn't fail the build", not "unratcheted".
- **Coverage semantics per profile (A6).** Each profile declares its coverage metric + measure recipe: python = branch coverage via pytest-cov; rust = line via cargo-llvm-cov; go = `go test -coverprofile` then `go tool cover -func | total`; react-ts = vitest lines (the single `coverage_floor` maps to vitest `lines`; the other three vitest thresholds default to the same value, overridable in native config). Phase 1 (measure) and Phase 2 (propose greenfield-strict vs legacy-baseline) recipes become **per-profile** (the shipped SKILL.md Phase 1/2 is Python-only and must be generalized). Greenfield defaults are per-profile (python 92/10/90/strict; others set in each profile).
- **Migration ordering (B5).** The plan sequences: (1) rename `setup-python-quality-gates`→`setup-quality-gates` and move its tests, re-pathed; (2) update tvagent's `.pre-commit-config.yaml` excludes (lines ~38/42 hardcode the old path) to the new path; (3) add tvagent's root `quality-gates.toml` at its current values (coverage 92, complexity 10, mutation 90, strict, plus vulture 60, the ruff select set, arch_contracts 3); (4) switch `gate_ratchet.py` to read the manifest. The migration PR's own `origin/master` has no manifest → the ratchet skips it (intended, stated). The next PR ratchets from those values. Keep a one-line redirect note at the old skill path and update the 2026-09-18 spec/plan links. tvagent staying green is G9.
- **Suppression tokens (MISSING).** Per-language token map in `suppression_diff.py`: python (`# noqa`,`# type: ignore`,`# pyright: ignore`,`# pragma: no cover` — have), rust (`#[allow(`,`#![allow(`,`unsafe`), go (`//nolint`), ts (`// eslint-disable`,`eslint-disable-next-line`,`/* eslint-disable */`,`// @ts-ignore`,`// @ts-expect-error`,`// @ts-nocheck`,`// biome-ignore`). Scan all added lines regardless of extension (a stray token is itself suspicious).
- **Guard generalization (MISSING).** Installed guard reads its protected set from: baked defaults (all four ecosystems' gate/lock/config files + `quality-gates.toml`) ∪ `.claude/protected-paths.json` ∪ the manifest's `[protected].paths` **as a union** (never letting a manifest edit shrink it; the ratchet separately guards `[protected]` from shrinking). Lockfiles protected: `uv.lock`, `Cargo.lock`, `go.sum`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`. `package.json` churn is high → protect only at repo root (not nested), unlike always-basename files.
- **pre-commit is Python (MISSING, decision 6).** Accepted: pre-commit stays as the hook runner for all profiles; profile local hooks use `language: system` and call the installed tool. Stated in anti-gaming.md that a Rust/Go/TS repo thereby depends on Python 3.11 + pre-commit for the gate layer.
- **Nightly + mutation adapters (MISSING).** Each profile ships a `nightly.yml` fragment; its `--min` reads `manifest.py get mutation_floor`. `mutation_score.py` is NOT unchanged — it dispatches to a per-tool adapter (`mutation_adapters/`) to normalize mutmut/cargo-mutants/stryker/gremlins output to one score.
- **CI needs Python even for non-Python repos (MISSING).** The spine scripts need Python 3.11 (tomllib) on the runner; every profile's `ci.yml` includes a `setup-python` spine step. Stated.
- **Fixtures gated on toolchain (MISSING).** Per-language e2e install tests are skipped unless the toolchain is present (as the existing tests gate on tools), so tvagent CI without rustc/go/node still passes; VERIFICATION lists "real toolchain install per language" as not-verified-here.

## Success criteria

| ID | Criterion | Verified by |
|----|-----------|-------------|
| G1 | detect.py returns the right `language` for a Cargo.toml / go.mod / package.json+tsconfig / pyproject fixture | unit tests on 4 fixtures |
| G2 | The ratchet reads `quality-gates.toml` and fails on a lowered `coverage_floor`, a raised `complexity_max`, a strictness downgrade, and a deleted threshold table | ratchet self-check + a live weakening test per direction |
| G3 | Each of the 4 profiles installs onto a minimal fixture repo of that language and the fast (pre-commit) gates pass green on clean code | per-language e2e install test |
| G4 | React-TS profile uses Biome (one binary) for lint+format, not prettier+eslint | assertion on the react-ts profile + its rendered pre-commit config |
| G5 | Rust-native preference honored: each gate's profile lists the Rust-native tool first where one exists | assertion over profile.toml preference orders |
| G6 | guard hook asks on edits to each language's gate files (Cargo.toml, go.mod, package.json, tsconfig, quality-gates.toml) + the shared set | guard unit tests extended per language |
| G7 | suppression-diff flags per-language suppressions (#[allow], //nolint, // eslint-disable, // @ts-ignore, // biome-ignore) | suppression-diff unit tests |
| G8 | Polyglot repo (e.g. go.mod + package.json) → skill asks which language, does not silently pick | detect + SKILL.md Phase 0 behavior test |
| G9 | Python migration: tvagent (a Python repo) still passes its own full gate after the rename + manifest indirection | run tvagent's pre-commit both stages green |
| G10 | master-copy CI judge + ruleset + solo/team model unchanged and still described accurately in anti-gaming.md | review + the existing hardening tests |
| G12 | drift-check gate fails when a native config value (e.g. ruff `max-complexity`) differs from the manifest; passes when equal | drift-check unit test per config-only threshold |
| G13 | `manifest.py` validator rejects an unknown key (typo like `coverage_flor`), a wrong-type value, and an illegal `type_strictness`/`meta.language` — fail-closed, not skipped | validator unit tests |
| G14 | spine never edited to add a language: adding a 5th profile touches only `profiles/` + the KEY_DIRECTIONS registry data, not ratchet/guard/render logic | structural check: diff of a hypothetical new profile |
| G11 | VERIFICATION.md maps G1–G14 and lists "what I did NOT verify" (real CI runners, L3 ruleset e2e, mutation tools per language, live install of each real toolchain) | final verification task |

## What's left to the builder

- Exact schema/validator for `quality-gates.toml` and the `manifest.py get` helper contract.
- The precise tool invocations + minimal config each profile writes (e.g. the Biome config for react-ts, the tarpaulin flags for rust) — follow each tool's current docs; prefer the single-binary install.
- Which gates are blocking vs advisory per language where a tool is immature (Go mutation = non-blocking; TS/Rust architecture gates = optional).
- Minimal fixture repos per language for the e2e tests.
- Whether `suppression_diff.py` token additions are a config list or inline (prefer a small per-language token map).
