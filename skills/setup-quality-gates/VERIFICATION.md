# Verification: setup-quality-gates

## Multi-language generalization (G1-G14)

Spec: `docs/superpowers/specs/2026-11-15-generalize-quality-gates-design.md` (success criteria G1-G14).
All test names below are in `skills/setup-quality-gates/tests/`.

| ID | Status | Evidence |
|----|--------|----------|
| G1 | PASS | `test_detect.py::test_detect_rust`, `test_detect_go`, `test_detect_react_ts`, `test_detect_python` (4 fixtures); also `test_detect_bare_packagejson_unsupported`, `test_detect_packagejson_not_object` |
| G2 | PASS | `test_ratchet_manifest.py::test_lowered_coverage_fails`, `test_raised_complexity_fails`, `test_strictness_downgrade_fails`, `test_deleted_key_fails` (plus `test_lint_rules_shrink_fails`, `test_protected_paths_shrink_fails`, `test_new_key_allowed`); `test_assets.py::test_ratchet_selfcheck_passes` |
| G3 | PARTIAL | `test_profile_rust.py::test_rust_e2e_green`, `test_profile_go.py::test_go_e2e_green`, `test_profile_react_ts.py::test_ts_e2e_green`, `test_e2e_install.py::test_greenfield_l1_is_green_day_one` (python). Each renders the profile onto a min fixture and runs the toolchain-native fast gates (fmt/clippy/test, gofmt/vet/test+cover, node --test + biome.json validity). Skipped without the toolchain. Gap: the profile's third-party tools (golangci-lint, biome, stryker, cargo-llvm-cov, cargo-mutants) were NOT executed, only the language-bundled ones. |
| G4 | PASS | `test_profile_react_ts.py::test_ts_uses_biome_not_prettier_eslint` |
| G5 | PASS | `test_profile_rust.py::test_rust_rust_native_flags`, `test_rust_coverage_is_llvm_cov`; `test_profile_python.py::test_python_rust_native_first` (ruff/ty-class tools first) |
| G6 | PASS | `test_guard_protected_paths.py::test_default_protected_asks` (parametrized: Cargo.toml, Cargo.lock, clippy.toml, go.mod, go.sum, tsconfig.json, biome.json, lockfiles, package.json, quality-gates.toml, pyproject.toml, workflows, spine scripts) + `test_manifest_protected_path_honored`, `test_evasion_matrix` |
| G7 | PASS | `test_suppression_tokens.py::test_token_flagged_in_added_line` (parametrized: `#[allow(`, `#![allow(`, `//nolint`, `// eslint-disable*`, `// @ts-ignore/expect-error/nocheck`, `// biome-ignore`, noqa, type: ignore, ...), `test_token_flagged_regardless_of_extension`, `test_plain_line_not_flagged` |
| G8 | PASS | `test_detect.py::test_detect_polyglot` (returns `candidates`, no silent pick) + `test_skill_doc.py::test_multilanguage_skill_md` (Phase 0 asks which profile; SKILL.md l.39). The interactive ask itself is documented behavior, not executable here. |
| G9 | PASS | tvagent full gate, both hook stages green (counts below); `uv lock --check` passes |
| G10 | PARTIAL | `test_skill_doc.py::test_anti_gaming_covers_manifest_judge`, `test_l3_degradation_documented`; existing hardening tests carried through (`test_guard_protected_paths.py`, `test_ratchet_manifest.py`). Master-copy judge/ruleset/solo-team model is verified by doc assertions + review, not by a live ruleset. |
| G11 | PASS | this document |
| G12 | PASS | `test_manifest.py::test_check_drift`, `test_check_drift_detects_mismatch`, `test_check_drift_json_native`, `test_check_drift_malformed_is_drift_not_crash`, `test_check_drift_missing_binding_fails`; per-profile `test_rust_drift_bites`, `test_go_drift_bites`, `test_ts_drift_bites`, `test_drift_python` |
| G13 | PASS | `test_manifest.py::test_unknown_key_rejected`, `test_wrong_type_rejected`, `test_illegal_strictness_rejected`, `test_illegal_language_rejected`, `test_unknown_top_level_table_rejected`, `test_nonstring_language_rejected`, `test_missing_key_message_clear` |
| G14 | PASS (structural) | `test_template_integrity.py::test_spine_has_no_language_branching` (AST scan of `render.py`, `manifest.py`, `templates/scripts/gate_ratchet.py`, `guard_protected_paths.py`: no string literal equal to a language name, except the `LANGUAGES` registry constant in manifest.py; `detect.py` excluded as it is the per-language detector registry) + `test_every_profile_validates_and_renders` (all profiles render, no residual tokens, referenced scripts shipped). Caveat: the guard's protected-file default set names language files (e.g. `go.mod`) as data, so adding a language that needs new protected files edits that data set, per the spec's "registry data" allowance. The structural check cannot prove a hypothetical 5th-profile diff; it proves no branching exists to edit. |

Result: 12 PASS, 2 PARTIAL (G3, G10) counting G11 and G14 as PASS.

### Full-gate results (this run)

| Command | Result |
|---------|--------|
| `python -m pytest skills/setup-quality-gates/` | 143 passed |
| `python -m pytest -q` (tvagent full suite) | 131 passed |
| `SKIP=pip-audit pre-commit run --all-files --hook-stage pre-commit` | all passed |
| `SKIP=pip-audit pre-commit run --all-files --hook-stage pre-push` | all passed (pip-audit skipped: sandbox pyexpat issue) |

Toolchains present in this run (so e2e tests ran, not skipped): `go`, `cargo`/`rustc`, `node`. Not present: `biome`.

### What I did NOT verify

- Real GitHub Actions runners: only the master-copy CI blocks were exercised locally; no rendered `ci.yml` was pushed and run.
- L3 ruleset end-to-end (branch-protection behavior, solo/team model on a real repo).
- Live install/run of third-party tools: `cargo-llvm-cov`, `cargo-mutants`, `golangci-lint`, `gremlins`, `biome`, `stryker`, `vitest` coverage. The e2e tests run only language-bundled commands (cargo fmt/clippy/test, gofmt/go vet/go test, `node --test`).
- Per-language mutation tools end-to-end: the adapters are parse-tested on canned output (`test_mutation_adapters.py`) only.
- The Go `.golangci` v2 gocyclo config was not validated by a live golangci-lint.
- The interactive skill flow (Phase 0 polyglot question, Phase 4 confirm) is asserted in SKILL.md text only.
- G14 is checked structurally; no actual 5th-profile diff was built.

---

## Legacy (Python-only) criteria S1-S10

Original spec `docs/superpowers/specs/2026-09-18-quality-gates-skill-design.md`; unchanged.

| ID | Criterion | Status | Check |
|----|-----------|--------|-------|
| S1 | Greenfield repo, L1 install yields strict defaults, all gates green | **Automated here** | `tests/test_e2e_install.py::test_greenfield_l1_is_green_day_one` — builds a real typed+tested package, renders the strict greenfield gate block from `templates/pyproject.gates.toml`, runs real `ruff check` and `pytest --cov --cov-fail-under=92` subprocesses against it. Both exit 0. |
| S2 | Legacy repo with failing strict checks produces gates that pass day one (baseline) | **Deferred (manual)** | Needs a real repo with pre-existing lint/type/coverage debt to prove the baselined thresholds pass without weakening the tool's own defaults. Run: `python skills/setup-quality-gates/scripts/gate_setup/detect.py <debt-repo>` then apply the skill's Phase 5 baseline-fit logic and confirm `ruff check .` / `pytest --cov` are green at the *baselined* (not strict) floor. No debt fixture repo exists in this tree. |
| S3 | Re-running the skill never lowers an already-higher threshold | **Automated here** | `tests/test_fixtures_shape.py` + `tests/fixtures/partial_config/*` exercise the merge-not-stomp path over pre-existing config; the "never lower" rule itself is enforced in Phase 4 of `SKILL.md` (documented procedure), asserted at the unit level via `detect()`'s `existing` flags in `tests/test_detect.py`. Full idempotency re-run (pre-set floor 95 → run skill → still 95) requires driving the interactive Phase 4 flow end-to-end and is not exercised as a hermetic test. |
| S4 | Package-manager detection wires lock-check + pip-audit for uv AND poetry | **Automated here** | `tests/test_detect.py` runs `detect()` against `tests/fixtures/uv_hexagonal` (uv.lock) and `tests/fixtures/poetry_flat` (poetry.lock) and asserts `pkg_manager` and `audit_export` resolve correctly for both. |
| S5 | import-linter contracts proposed only on a clear shape; skipped + reported on a flat repo | **Automated here** | `tests/test_detect.py` asserts `core_candidates` is non-empty for `tests/fixtures/uv_hexagonal` (has `core/`) and empty for `tests/fixtures/poetry_flat` (flat module). |
| S6 | Existing `[tool.ruff]` / `.pre-commit-config.yaml` merged, not stomped; conflicts confirmed | **Automated here** | `tests/test_detect.py` asserts `existing["ruff"]` / `existing["precommit"]` are `True` against `tests/fixtures/partial_config`. Confirm-before-merge UX itself (Phase 4) is a documented interactive step in `SKILL.md`, not scriptable headlessly. |
| S7 | L3 ratchet blocks a weakening PR (coverage floor lowered) via required CI check | **Automated here** | `tests/test_verify.py::test_verify_detects_weakening` calls `prove_ratchet_bites()`, which runs the real `templates/scripts/gate_ratchet.py` against a simulated floor-lowering diff and asserts it returns `True` (blocks). This is the local proof; see S7 deferred note below for the live-PR form. |
| S8 | L3 degrades gracefully (installs CI pieces, reports advisory-only) when ruleset can't apply | **Deferred (manual)** | Needs an admin-eligible GitHub repo where ruleset application is exercised for real (free/private tier or no-admin token). No such repo/credentials available in this environment. Run: on a repo where `gh api repos/{owner}/{repo}/rulesets` returns a permission error, run the skill's Phase 4 install and confirm CI workflow files still land while the ruleset step logs advisory-only and is listed in the Phase 5 "did NOT install" output. |
| S9 | Self-verification emits an accurate "did NOT install/verify" list | **Automated here (mechanism) / Deferred (S8 content)** | `tests/test_verify.py` exercises the `prove_ratchet_bites` mechanism used by `--verify`. Its accuracy on a real S8-degraded repo (i.e. does the printed list actually match what was skipped) is deferred to the S8 manual run above — inspect the CLI output there. |
| S10 | Skill is safe on a live repo: no uncommitted destructive change without a shown diff + confirm | **Documented (Phase 4), not automated** | The merge-confirm behavior is an interactive step in `SKILL.md` Phase 4 (show diff, wait for explicit yes before writing). No file write happens in any test without an explicit `tmp_path` target — the test suite itself never touches a live repo. Not independently automated beyond "the scripts never write outside the path they're given," which is true by inspection of `detect.py`/`verify.py` (both read-only; only `gate_ratchet.py`'s proof mutates a throwaway simulated diff, verified untouched by `test_verify_leaves_pyproject_untouched`). |

## What I did NOT verify

- **L2 CI job in a real GitHub Actions runner.** `templates/ci.yml` was never pushed and run on actual Actions infrastructure in this session — only its YAML shape is checked (`tests/test_templates.py`). To verify: push a branch with the rendered `ci.yml` to a real GitHub repo and confirm the workflow runs and gates the PR.
- **L3 ruleset application end-to-end (S8).** Requires an admin-eligible GitHub repo; not available here. To verify: `gh api repos/{owner}/{repo}/rulesets -f name=quality-gates -f target=branch ...` (per `templates/ruleset.json`) on a real repo you administer, then attempt on a repo you don't administer and confirm graceful advisory-only degradation.
- **Live ratchet proof on a real PR.** `test_verify.py` proves the ratchet script logic bites in a scratch temp repo; it was not re-run as an actual required check blocking a real GitHub PR in this session (that was previously done for tvagent PR #12, referenced in the spec, not re-executed here).
- **poetry/pdm lock-drift hooks.** Detection is tested (`test_detect.py` resolves `pkg_manager`/`audit_export` for poetry), but the rendered `poetry lock --check` / `pdm lock --check` hooks themselves were never executed against a real poetry/pdm project in this session — only the uv variant runs live, via this repo's own `uv lock --check` pre-push hook.
- **Mutation testing baseline (mutmut).** `[tool.mutmut]` config renders correctly (`test_templates.py`), but no mutation run was executed against any fixture or the e2e demo package — `MUTATION_FLOOR` is templated but not exercised at runtime anywhere in this suite.
- **S2 legacy-baseline fit.** No repo with real pre-existing lint/type/coverage debt exists in this tree to drive Phase 5's baseline-fit logic against. See S2 row above for the manual command.
- **Known pyright-typing gap in skill tests.** The skill's own test files (including this task's `test_e2e_install.py`) use `sys.path.insert` plus untyped `tmp_path` fixture parameters, which pyright strict mode would flag if it type-checked `skills/`. It does not: `skills/` is excluded from tvagent's `[tool.pyright]` `exclude` list (`pyproject.toml`), `[tool.ruff]` `extend-exclude`, and `[tool.coverage.run]` `omit` (this predates Task 7 — see `pyproject.toml` lines 20-21, 45-46, 79). This is a known, accepted gap; a `pyrightconfig.json` + `tmp_path: Path` annotations for the skill's own tests are batched for a later fix-wave, not addressed here.

## tvagent gate confirmation

Running this repo's own gates after adding `tests/test_e2e_install.py` and this file:

```
PATH="$PWD/.venv/bin:$PATH" pre-commit run --all-files --hook-stage pre-commit   # all hooks passed
PATH="$PWD/.venv/bin:$PATH" SKIP=pip-audit pre-commit run --all-files --hook-stage pre-push   # all hooks passed (pip-audit skipped: sandbox pyexpat issue)
```

`skills/` was already excluded from tvagent's ruff/pyright/coverage config by a prior task (Task 6 precedent, `pyproject.toml` lines 20-21/45-46/79) and from the two `ruff-arg`/`ruff-legacy-alias` pre-commit hooks (`.pre-commit-config.yaml` lines 38, 42) for `skills/setup-quality-gates/templates/`. No additional exclude was needed for Task 7 — `tests/test_e2e_install.py` lives under `skills/`, already covered.
