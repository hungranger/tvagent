# Dev tooling

Git hooks run through the [pre-commit](https://pre-commit.com) framework, staged so
`git commit` stays fast and `git push` carries the heavier gate.

| Stage | Hook | What it checks |
|---|---|---|
| pre-commit | ruff | lint (`[tool.ruff]` in `pyproject.toml`) |
| pre-commit | ruff-format | formatting |
| pre-commit | gitleaks | secret scan of the staged diff |
| pre-commit | import-linter | hexagonal architecture contracts (`[tool.importlinter]`), fast static import-graph check on `src`, safe pre-commit |
| pre-push | pyright | strict type check (`[tool.pyright]`) |
| pre-push | pytest-cov | tests + coverage floor (`[tool.coverage]`) |
| pre-push | pip-audit | dependency CVE scan (audits `uv.lock`) |
| pre-push | uv lock --check | fails if `uv.lock` drifted from `pyproject.toml` (non-mutating — does not touch the venv) |
| pre-push | semgrep | `p/python` + `p/security-audit` rule sets |
| pre-push | ruff-arg | unused function/lambda args (`ARG`), not in the main `[tool.ruff.lint] select` so it stays out of pre-commit |
| pre-push | vulture | dead functions/classes/methods/attrs/variables, gated by `.vulture_allowlist.py`. Runs at `--min-confidence 60` — vulture scores unused functions/classes/attrs/variables at exactly 60%, so `80` (the default-ish "safe" threshold) would only catch unused imports (90%) and unreachable code (100%) and never fire on dead functions, which defeats the point of adding vulture. `60` is noisier (more false positives, e.g. dataclass fields round-tripped through serialization); triage misses into `.vulture_allowlist.py`, don't raise the threshold to silence them |

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
2. Install `ruff`, `pyright`, `pytest-cov`, `pip-audit`, `semgrep`, `vulture`,
   and `uv` in the project's environment, then run:
   ```
   pre-commit install
   ```
   (`default_install_hook_types` in the config wires both the pre-commit and
   pre-push stages from that one command.)

## Notes

- All local/system hooks call tools by bare name (`pyright`, `pytest`,
  `pip-audit`, `uv`, `semgrep`) resolved from `PATH` — no machine-specific
  paths in the config.
- Coverage floor: see `task-hook-report.md` for how it was measured and set.
