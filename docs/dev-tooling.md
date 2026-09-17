# Dev tooling

Git hooks run through the [pre-commit](https://pre-commit.com) framework, staged so
`git commit` stays fast and `git push` carries the heavier gate.

| Stage | Hook | Env | What it checks |
|---|---|---|---|
| pre-commit | ruff | isolated (repo hook) | lint (`[tool.ruff]` in `pyproject.toml`), cyclomatic complexity C901 (max-complexity 10) |
| pre-commit | ruff-format | isolated (repo hook) | formatting |
| pre-commit | gitleaks | isolated (repo hook) | secret scan of the staged diff |
| pre-commit | import-linter | isolated (`language: python`) | hexagonal architecture contracts (`[tool.importlinter]`), fast static import-graph check on `src`, safe pre-commit |
| pre-push | pyright | **project venv** | strict type check (`[tool.pyright]`) |
| pre-push | pytest-cov | **project venv** | tests + coverage floor (`[tool.coverage]`) |
| pre-push | pip-audit | **project venv (`uv`)** | dependency CVE scan (audits `uv.lock`) |
| pre-push | uv lock --check | **project venv (`uv`)** | fails if `uv.lock` drifted from `pyproject.toml` (non-mutating — does not touch the venv) |
| pre-push | semgrep | isolated (official `semgrep/semgrep` repo hook, rev-pinned) | `p/python` + `p/security-audit` rule sets |
| pre-push | ruff-arg | isolated (repo hook, `ruff-pre-commit` again) | unused function/lambda args (`ARG`), not in the main `[tool.ruff.lint] select` so it stays out of pre-commit |
| pre-push | vulture | isolated (`language: python`) | dead functions/classes/methods/attrs/variables, gated by `.vulture_allowlist.py`. Runs at `--min-confidence 60` — vulture scores unused functions/classes/attrs/variables at exactly 60%, so `80` (the default-ish "safe" threshold) would only catch unused imports (90%) and unreachable code (100%) and never fire on dead functions, which defeats the point of adding vulture. `60` is noisier (more false positives, e.g. dataclass fields round-tripped through serialization); triage misses into `.vulture_allowlist.py`, don't raise the threshold to silence them |

**Self-contained vs. project-venv hooks:** pre-commit resolves `language: python`
hooks (and hooks from an external hook repo, like `ruff-pre-commit`) into their
own isolated envs, pinned via `additional_dependencies`/`rev` — these run
regardless of what's on `PATH`, so a bare `git push` with no `.venv` activated
still works for them. `pyright`, `pytest-cov`, `pip-audit` and `uv-lock-check`
stay `language: system` (**project venv** above) because they genuinely need
the project's own environment: pyright type-checks against installed deps,
pytest-cov runs the app and its deps, and pip-audit/uv-lock-check both need
`uv` itself. Activate `.venv` (or otherwise put those four on `PATH`) before
pushing.

`import-linter` moved to an isolated `language: python` env even though it
analyzes `tvagent`: `grimp` (its import-graph engine) does static AST-level
analysis of import statements only — it never actually imports `tvagent`'s
runtime dependencies — so `PYTHONPATH=src` is enough for `lint-imports` to
find the `tvagent` package; the project need not be installed. Verified by
running `lint-imports` from a fresh `uv venv` with only `import-linter`
installed and `PATH` stripped to `/usr/bin:/bin` — it still resolved and
passed all 3 contracts.

`semgrep` uses the official `https://github.com/semgrep/semgrep` pre-commit
repo hook, pinned by `rev: v1.176.0` — same pattern as `ruff-pre-commit` and
`gitleaks` above. `rev` is the single source of truth for the version; there
is no separate `additional_dependencies` pin to drift out of sync. It still
downloads the `p/python`/`p/security-audit` rulesets over the network at run
time, same as before.

`[tool.importlinter]` (root_package `tvagent`) enforces three contracts: a
`forbidden` contract keeping `tvagent.core` free of adapter/config/app/shared
and external-backend imports; a `layers` contract pinning the dependency
direction `core -> tvagent.audio -> adapters -> config -> app/enroll`; and an
`independence` contract requiring the 8 port adapters never import each
other. These replace the hand-rolled `tests/test_core_isolation.py` (which
only checked the core-purity half) with a single static source of truth that
also runs on every commit.

pyright and the dead-code checks (`ruff --select ARG`, `vulture`) live on pre-push, not
pre-commit: strict typing and whole-picture dead-code analysis can legitimately fail on
an intermediate TDD-RED commit (e.g. a test that references a symbol that doesn't exist
yet), and pre-commit should stay fast and RED-friendly.

`[tool.pyright]` sets `reportMissingTypeStubs = "warning"`: the untyped C-extension
runtime backends (sounddevice, webrtcvad, speechbrain, faster_whisper, openwakeword, …)
ship no stubs, so this stays a visible warning rather than a silent `"none"` — the gate
still fails only on real type errors, not on these.

## Reuse in another project

1. Copy `.pre-commit-config.yaml`, `.gitleaks.toml`, and the `[tool.ruff]`,
   `[tool.pyright]`, and `[tool.coverage]` blocks from `pyproject.toml`.
2. `ruff`, `ruff-format`, `ruff-arg`, `gitleaks`, `import-linter`, `semgrep`
   and `vulture` are self-contained — `pre-commit install` provisions their
   isolated envs on its own, nothing to install for those.
3. Install `pyright`, `pytest-cov`, `pip-audit` and `uv` in the project's own
   environment (they run `language: system`), then run:
   ```
   pre-commit install
   ```
   (`default_install_hook_types` in the config wires both the pre-commit and
   pre-push stages from that one command.)

## Notes

- The four `language: system` hooks (`pyright`, `pytest-cov`, `pip-audit`,
  `uv-lock-check`) call tools by bare name resolved from `PATH` — no
  machine-specific paths in the config — but that means the project venv (or
  wherever those tools live) must be on `PATH` when pushing. Every other hook
  runs in a pre-commit-managed isolated env, so `git push` with no venv
  active still runs those.
- Coverage floor: see `task-hook-report.md` for how it was measured and set.
