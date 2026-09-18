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
| `{{PKG_INSTALL_STEP}}` | One or more full YAML workflow step(s) (each starting with `- name:`/`- uses:`/`- run:` at the surrounding steps-list indentation) that install the project + dev/test deps. For `uv`, this renders as an `astral-sh/setup-uv` step followed by an `- run: uv sync` step; for poetry/pdm/pip, a single `- run:` step with that tool's install command. Not just a bare shell command — it replaces the whole step entry in `ci.yml` and `nightly-mutation.yml` | `- uses: astral-sh/setup-uv@38f3f...  # v4\n      - run: uv sync` (uv) / `- run: pip install -e ".[dev]"` (pip) | SKILL.md setup, detected from the repo's package manager |
| `{{SRC_DIRS}}` | Source paths coverage/mutmut/vulture should target. Rendered as a TOML array (`["src/tvagent"]`) everywhere except the pre-commit vulture hook, where it renders as space-separated paths (`src/tvagent`) since vulture's CLI takes positional dirs, not a list literal — see SKILL.md Phase 4 | `["src/tvagent"]` (TOML) / `src/tvagent` (vulture hook) | SKILL.md setup, detected from the repo layout |
| `{{OWNER}}` | GitHub username/team owning the gate-defining files in CODEOWNERS | `hungranger` | SKILL.md setup, asked of the user |
| `{{DEFAULT_BRANCH}}` | The repo's default branch, applied to `ruleset.json`'s `~DEFAULT_BRANCH` placeholder at apply time (not a literal template substitution) | `master` | SKILL.md setup, detected via `gh` |
