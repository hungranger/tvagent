# Template tokens

Every `{{TOKEN}}` used anywhere under `templates/`, documented here.

| Token | Meaning | Example value | Filled by |
|---|---|---|---|
| `{{COVERAGE_FLOOR}}` | Minimum branch coverage percentage (`[tool.coverage.report] fail_under`) | `92` | SKILL.md setup, asked of the user |
| `{{MAX_COMPLEXITY}}` | Max cyclomatic complexity (`[tool.ruff.lint.mccabe] max-complexity`) | `10` | SKILL.md setup, asked of the user |
| `{{VULTURE_MIN_CONFIDENCE}}` | Vulture dead-code confidence threshold (`[tool.vulture] min_confidence`) | `60` | SKILL.md setup, asked of the user |
| `{{PYRIGHT_MODE}}` | Pyright `typeCheckingMode` | `strict` | SKILL.md setup, asked of the user |
| `{{MUTATION_FLOOR}}` | Minimum mutation-testing score enforced nightly (`mutation_score.py --min`) | `90` | SKILL.md setup, asked of the user |
| `{{PKG_AUDIT_EXPORT}}` | Command that exports a requirements list for `pip-audit` to scan, piped via stdin | `uv export --no-hashes --extra dev --extra run` | SKILL.md setup, detected from the repo's package manager |
| `{{PKG_INSTALL_STEP}}` | CI step that installs the project + dev/test deps | `pip install -e ".[dev]"` | SKILL.md setup, detected from the repo's package manager |
| `{{SRC_DIRS}}` | TOML array of source paths coverage/mutmut should target | `["src/tvagent"]` | SKILL.md setup, detected from the repo layout |
| `{{OWNER}}` | GitHub username/team owning the gate-defining files in CODEOWNERS | `hungranger` | SKILL.md setup, asked of the user |
| `{{DEFAULT_BRANCH}}` | The repo's default branch, applied to `ruleset.json`'s `~DEFAULT_BRANCH` placeholder at apply time (not a literal template substitution) | `master` | SKILL.md setup, detected via `gh` |
