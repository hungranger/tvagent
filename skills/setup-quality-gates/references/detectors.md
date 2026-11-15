# Detectors (Phase 0)

`python <skill-dir>/scripts/gate_setup/detect.py <root>` (or `python
<skill-dir>/scripts/gate_setup/detect.py .` from the target repo root) runs
all four detectors and prints one JSON object. Invoke it by path, not `python
-m gate_setup.detect` — the module isn't importable from a target repo that
hasn't added the skill's `scripts/` to its `sys.path`.
Every detector has a graceful, explicit fallback — never guess silently; if a
key comes back `null`/empty, say so and ask the user rather than assuming.

| Detector | JSON key(s) | Sniffs | Adapts | No-match fallback |
|---|---|---|---|---|
| Package manager | `pkg_manager`, `audit_export` | `uv.lock` / `poetry.lock` / `pdm.lock` / `requirements*.txt` (checked in that order) | wires `{{PKG_AUDIT_EXPORT}}` (pip-audit input) and the lock-check hook to the matched tool | `pkg_manager: null` → greenfield: offer `uv init`; existing repo with no lockfile: ask which manager, never guess |
| Package layout | `layout.src_layout`, `layout.core_candidates`, `layout.packages` | `src/` layout vs flat; any package whose last path segment is `core`, `domain`, or `entities` | proposes import-linter contracts only when `core_candidates` is non-empty (Phase 2) | `core_candidates: []` → skip import-linter entirely, state why ("no core/domain/entities package found") |
| Existing config | `existing.ruff`, `existing.pyright`, `existing.coverage`, `existing.precommit`, `existing.ci` | `[tool.ruff]` / `[tool.pyright]` / `[tool.coverage]` in `pyproject.toml`; `.pre-commit-config.yaml`; any workflow file under `.github/workflows/` | each `True` key becomes a merge target in Phase 4 (diff shown, confirm before overwrite) instead of a clean write | all `False` → clean install, no merge needed |
| Git host + power | `git.host`, `git.visibility`, `git.admin`, `git.gh_auth` | `gh auth status`; `git remote get-url origin` for `github.com`; `gh repo view` for visibility/permission | picks the L3 enforcement actually applicable (ruleset via `gh api` vs CI-only) | `git.host != "github"` or `git.admin` falsy or no `gh_auth` → L3 degrades to advisory-only (see `anti-gaming.md`) |

## Handling nulls

`detect()` never fails on a missing signal — it returns `null` for that key.
Treat every `null` as a stop-and-ask, not a default:

- `pkg_manager: null` on a non-empty repo → ask "which package manager: uv /
  poetry / pdm / pip?" before Phase 1 measures anything (pip-audit and the
  lock-check hook need to know).
- `git.host: null` → ask for the host; L2 (GitHub Actions CI) and L3
  (ruleset via `gh api`) assume GitHub, so a non-GitHub host means those
  pieces are described but not auto-applied.
- `git.admin: null` (not authed, or `gh` not installed) → treat as "cannot
  verify admin," which forces the same advisory-only L3 path as `admin:
  false`.

## Running it

```bash
python <skill-dir>/scripts/gate_setup/detect.py .
```

Output keys: `pkg_manager`, `audit_export`, `layout.{src_layout,
core_candidates, packages}`, `existing.{ruff, pyright, coverage, precommit,
ci}`, `git.{host, visibility, admin, gh_auth}`.
