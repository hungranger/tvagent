# Dev tooling

Git hooks run through the [pre-commit](https://pre-commit.com) framework, staged so
`git commit` stays fast and `git push` carries the heavier gate.

| Stage | Hook | What it checks |
|---|---|---|
| pre-commit | ruff | lint (`[tool.ruff]` in `pyproject.toml`) |
| pre-commit | ruff-format | formatting |
| pre-commit | gitleaks | secret scan of the staged diff |
| pre-push | pyright | strict type check (`[tool.pyright]`) |
| pre-push | pytest-cov | tests + coverage floor (`[tool.coverage]`) |
| pre-push | pip-audit | dependency CVE scan (audits `uv.lock`) |
| pre-push | uv lock --check | fails if `uv.lock` drifted from `pyproject.toml` (non-mutating — does not touch the venv) |
| pre-push | semgrep | `p/python` + `p/security-audit` rule sets |
| pre-push | ruff-arg | unused function/lambda args (`ARG`), not in the main `[tool.ruff.lint] select` so it stays out of pre-commit |
| pre-push | vulture | dead code, gated by `.vulture_allowlist.py`. At `--min-confidence 80` this reliably catches unused imports and unreachable code; vulture scores unused functions/classes/attrs/variables at 60% confidence, so those need a manual `--min-confidence 60` pass (higher noise, more false positives from dataclass fields round-tripped through serialization) |

pyright and the dead-code checks (`ruff --select ARG`, `vulture`) live on pre-push, not
pre-commit: strict typing and whole-picture dead-code analysis can legitimately fail on
an intermediate TDD-RED commit (e.g. a test that references a symbol that doesn't exist
yet), and pre-commit should stay fast and RED-friendly.

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
