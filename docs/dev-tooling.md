# Dev tooling

Git hooks run through the [pre-commit](https://pre-commit.com) framework, staged so
`git commit` stays fast and `git push` carries the heavier gate.

| Stage | Hook | What it checks |
|---|---|---|
| pre-commit | ruff | lint (`[tool.ruff]` in `pyproject.toml`) |
| pre-commit | ruff-format | formatting |
| pre-commit | gitleaks | secret scan of the staged diff |
| pre-commit | pyright | strict type check (`[tool.pyright]`) |
| pre-push | pytest-cov | tests + coverage floor (`[tool.coverage]`) |
| pre-push | pip-audit | dependency CVE scan (audits `uv.lock`) |
| pre-push | uv sync --locked | fails if `uv.lock` drifted from `pyproject.toml` |
| pre-push | semgrep | `p/python` + `p/security-audit` rule sets |

## Reuse in another project

1. Copy `.pre-commit-config.yaml`, `.gitleaks.toml`, and the `[tool.ruff]`,
   `[tool.pyright]`, and `[tool.coverage]` blocks from `pyproject.toml`.
2. Install `ruff`, `pyright`, `pytest-cov`, `pip-audit`, `semgrep`, and `uv` in
   the project's environment, then run:
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
