# setup-python-quality-gates Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable Claude skill that installs a tiered, tamper-resistant Python quality-gate stack into any repo (greenfield or existing) without a day-one wall of red.

**Architecture:** The skill is a procedure-with-assets. `SKILL.md` drives a detect→measure→propose→tier→write→verify flow that Claude executes with its own tools. Deterministic detection is the one piece extracted into a tested helper (`detect.py`); measurement and config-merge stay prose steps gated by user confirmation. Config lives in `templates/` as `{{TOKEN}}`-parameterized copies of tvagent's battle-tested files; the ratchet/suppression scripts ship verbatim.

**Tech Stack:** Python ≥3.11 (stdlib `tomllib` for reading; no third-party TOML writer), pre-commit, ruff, pyright, pytest+coverage, vulture, gitleaks, semgrep, pip-audit, mutmut, import-linter, GitHub Actions, `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-09-18-quality-gates-skill-design.md`

## Global Constraints

- Helper code is **stdlib-only** — no `tomlkit`/`toml` deps; read with `tomllib`, never programmatically rewrite TOML (append-or-confirm instead).
- Python floor: **3.11** (for `tomllib`).
- The `gate_ratchet.py` and `suppression_diff.py` templates ship **verbatim** from tvagent — repo-agnostic already; do not fork their logic.
- Detection **never guesses silently** — every detector returns an explicit `null`/`"unknown"` the SKILL.md flow must handle by asking.
- The skill **never lowers an already-higher threshold** on re-run (idempotency = detect-present → skip/diff, never stomp).
- Skill directory name: `setup-python-quality-gates`. It is authored in this repo under `skills/setup-python-quality-gates/` (portable — copyable to `~/.claude/skills/` or a plugin).
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Work on a feature branch; land via PR to master (branch protection active: green `quality-gate` CI + CODEOWNER review, no bypass). Never push to master directly, never `--no-verify`.

---

### Task 1: Scaffold skill dir + copy verbatim assets

**Files:**
- Create: `skills/setup-python-quality-gates/SKILL.md` (skeleton only — frontmatter + section headers)
- Create: `skills/setup-python-quality-gates/templates/scripts/gate_ratchet.py` (copied verbatim from repo root `scripts/gate_ratchet.py`)
- Create: `skills/setup-python-quality-gates/templates/scripts/suppression_diff.py` (copied verbatim from `scripts/suppression_diff.py`)
- Test: `skills/setup-python-quality-gates/tests/test_assets.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `templates/scripts/gate_ratchet.py` exposing its existing `--self-check` mode; `templates/scripts/suppression_diff.py` importable.

- [ ] **Step 1: Write the failing test**

```python
# skills/setup-python-quality-gates/tests/test_assets.py
import subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]

def test_ratchet_selfcheck_passes():
    r = subprocess.run([sys.executable, str(SKILL / "templates/scripts/gate_ratchet.py"), "--self-check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout

def test_suppression_diff_importable():
    # syntactic sanity: byte-compile it
    r = subprocess.run([sys.executable, "-m", "py_compile",
                        str(SKILL / "templates/scripts/suppression_diff.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/setup-python-quality-gates/tests/test_assets.py -v`
Expected: FAIL — files don't exist (`No such file or directory`).

- [ ] **Step 3: Create the scaffold + copy assets**

```bash
cd /Users/hungvu/Workspace/projects/tvagent
mkdir -p skills/setup-python-quality-gates/{templates/scripts,templates/docs,references,tests}
cp scripts/gate_ratchet.py    skills/setup-python-quality-gates/templates/scripts/gate_ratchet.py
cp scripts/suppression_diff.py skills/setup-python-quality-gates/templates/scripts/suppression_diff.py
```

Then create `SKILL.md` with frontmatter and empty section headers (filled in Task 5):

```markdown
---
name: setup-python-quality-gates
description: Use when setting up or hardening quality gates (lint, types, coverage, security, mutation, anti-gaming ratchet + CI) for a Python project — greenfield or existing. Measures the repo, proposes baselines that pass day one, installs in tiers.
---

# Setup Python Quality Gates

<!-- Phase sections filled in Task 5 -->
## Phase 0 — Detect
## Phase 1 — Measure
## Phase 2 — Propose thresholds
## Phase 3 — Choose tier
## Phase 4 — Write (merge + confirm)
## Phase 5 — Verify
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest skills/setup-python-quality-gates/tests/test_assets.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add skills/setup-python-quality-gates
git commit -m "feat(skill): scaffold setup-python-quality-gates + verbatim ratchet/suppression assets

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Parameterize config templates

**Files:**
- Create: `skills/setup-python-quality-gates/templates/pyproject.gates.toml`
- Create: `skills/setup-python-quality-gates/templates/pre-commit-config.yaml`
- Create: `skills/setup-python-quality-gates/templates/ci.yml`
- Create: `skills/setup-python-quality-gates/templates/nightly-mutation.yml`
- Create: `skills/setup-python-quality-gates/templates/ruleset.json`
- Create: `skills/setup-python-quality-gates/templates/CODEOWNERS`
- Create: `skills/setup-python-quality-gates/templates/TOKENS.md` (documents every `{{TOKEN}}`)
- Test: `skills/setup-python-quality-gates/tests/test_templates.py`

**Interfaces:**
- Consumes: nothing.
- Produces: template files whose only `{{...}}` tokens are the ones listed in `TOKENS.md`. Token set (exact): `{{COVERAGE_FLOOR}}`, `{{MAX_COMPLEXITY}}`, `{{VULTURE_MIN_CONFIDENCE}}`, `{{PYRIGHT_MODE}}`, `{{MUTATION_FLOOR}}`, `{{PKG_AUDIT_EXPORT}}`, `{{PKG_INSTALL_STEP}}`, `{{SRC_DIRS}}`, `{{OWNER}}`, `{{DEFAULT_BRANCH}}`.

- [ ] **Step 1: Write the failing test**

```python
# skills/setup-python-quality-gates/tests/test_templates.py
import re
from pathlib import Path

TPL = Path(__file__).resolve().parents[1] / "templates"
TOKEN_RE = re.compile(r"\{\{([A-Z_]+)\}\}")

def documented_tokens():
    text = (TPL / "TOKENS.md").read_text()
    return set(TOKEN_RE.findall(text))

def test_every_used_token_is_documented():
    used = set()
    for f in TPL.rglob("*"):
        if f.is_file() and f.name != "TOKENS.md" and f.suffix in {".toml", ".yaml", ".yml", ".json", ""}:
            used |= set(TOKEN_RE.findall(f.read_text(errors="ignore")))
    undocumented = used - documented_tokens()
    assert not undocumented, f"tokens used but not in TOKENS.md: {undocumented}"

def test_core_templates_exist():
    for name in ["pyproject.gates.toml", "pre-commit-config.yaml", "ci.yml",
                 "nightly-mutation.yml", "ruleset.json", "CODEOWNERS"]:
        assert (TPL / name).exists(), name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/setup-python-quality-gates/tests/test_templates.py -v`
Expected: FAIL — `test_core_templates_exist` (files missing).

- [ ] **Step 3: Create the parameterized templates**

Base each on the tvagent original, replacing repo-specific values with tokens. Copy the real file, then substitute:

`pyproject.gates.toml` — from tvagent `pyproject.toml` `[tool.*]` blocks (ruff, ruff.lint, ruff.lint.mccabe, ruff.lint.per-file-ignores, pyright, vulture, mutmut, coverage.run, coverage.report; import-linter block is added by SKILL.md only when opted-in, so it is NOT in this template). Substitutions:
- `fail_under = 92` → `fail_under = {{COVERAGE_FLOOR}}`
- `max-complexity = 10` → `max-complexity = {{MAX_COMPLEXITY}}`
- `min_confidence = 60` → `min_confidence = {{VULTURE_MIN_CONFIDENCE}}`
- `typeCheckingMode = "strict"` → `typeCheckingMode = "{{PYRIGHT_MODE}}"`
- `source = ["src/tvagent"]` and `source_paths = ["src/tvagent/"]` → `{{SRC_DIRS}}`
- drop the tvagent-specific `exclude_also` coverage patterns down to the generic ones only (`if __name__`, `if TYPE_CHECKING:`); repo-specific excludes are added by the user later.

`pre-commit-config.yaml` — from tvagent `.pre-commit-config.yaml`, but:
- the `pip-audit` hook `entry` → `entry: sh -c '{{PKG_AUDIT_EXPORT}} | pip-audit -r /dev/stdin'`
- the `uv-lock-check` hook stays but is emitted only for uv repos (SKILL.md conditionally strips it); keep it in the template with a comment marker `# TEMPLATE-CONDITIONAL: uv-only`
- remove the `import-linter` local hook (added only when opted-in)

`ci.yml` — from tvagent `.github/workflows/ci.yml`, with the dependency-install step replaced by `{{PKG_INSTALL_STEP}}` and keep all actions SHA-pinned exactly as in the source.

`nightly-mutation.yml` — from tvagent, `--min` value → `{{MUTATION_FLOOR}}`, install step → `{{PKG_INSTALL_STEP}}`.

`ruleset.json` — from the ruleset we applied (branch protection), with `require_extra_approval_for_unattributed_changes` kept; no tokens needed except it is applied against `{{DEFAULT_BRANCH}}` at runtime via the SKILL.md flow (the JSON targets `~DEFAULT_BRANCH` so no substitution).

`CODEOWNERS` — the gate-owning paths from tvagent, owner → `{{OWNER}}`:
```
/pyproject.toml            @{{OWNER}}
/.pre-commit-config.yaml   @{{OWNER}}
/.github/**                @{{OWNER}}
/scripts/gate_ratchet.py       @{{OWNER}}
/scripts/suppression_diff.py   @{{OWNER}}
```

`TOKENS.md` — a table documenting all 10 tokens listed in the Interfaces block, each with meaning + example value + which phase fills it.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest skills/setup-python-quality-gates/tests/test_templates.py -v`
Expected: PASS (2 tests). If `test_every_used_token_is_documented` fails, add the missing token to `TOKENS.md` (or fix a typo'd token in a template).

- [ ] **Step 5: Commit**

```bash
git add skills/setup-python-quality-gates/templates
git commit -m "feat(skill): add {{token}}-parameterized gate config templates

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Fixture repos for detection + e2e

**Files:**
- Create: `skills/setup-python-quality-gates/tests/fixtures/greenfield/` (empty-ish package, `src/pkg/__init__.py`, minimal `pyproject.toml`, no lockfile)
- Create: `.../fixtures/uv_hexagonal/` (`uv.lock`, `src/app/core/__init__.py` + `src/app/adapters/__init__.py`, `pyproject.toml`)
- Create: `.../fixtures/poetry_flat/` (`poetry.lock`, flat `mod.py` at root, `pyproject.toml` with `[tool.poetry]`)
- Create: `.../fixtures/partial_config/` (has `[tool.ruff]` + a `.pre-commit-config.yaml` already)
- Test: (fixtures are consumed by Task 4; this task's deliverable is the fixtures themselves + a sanity test)
- Test file: `skills/setup-python-quality-gates/tests/test_fixtures_shape.py`

**Interfaces:**
- Consumes: nothing.
- Produces: four fixture repo dirs with the exact marker files Task 4's detector asserts on: `uv_hexagonal/uv.lock`, `uv_hexagonal/src/app/core/__init__.py`; `poetry_flat/poetry.lock`, `poetry_flat/mod.py`; `partial_config/pyproject.toml` containing `[tool.ruff]`; `greenfield/src/pkg/__init__.py` and no lockfile.

- [ ] **Step 1: Write the failing test**

```python
# skills/setup-python-quality-gates/tests/test_fixtures_shape.py
from pathlib import Path
F = Path(__file__).resolve().parents[1] / "tests/fixtures"

def test_fixture_markers_present():
    assert (F / "greenfield/src/pkg/__init__.py").exists()
    assert not (F / "greenfield/uv.lock").exists()
    assert (F / "uv_hexagonal/uv.lock").exists()
    assert (F / "uv_hexagonal/src/app/core/__init__.py").exists()
    assert (F / "poetry_flat/poetry.lock").exists()
    assert (F / "poetry_flat/mod.py").exists()
    assert "[tool.ruff]" in (F / "partial_config/pyproject.toml").read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/setup-python-quality-gates/tests/test_fixtures_shape.py -v`
Expected: FAIL — fixture files missing.

- [ ] **Step 3: Create the fixture files**

Create each with minimal real content. Lockfiles can be near-empty stubs (detection only checks their existence + name), e.g.:
```bash
cd skills/setup-python-quality-gates/tests/fixtures
mkdir -p greenfield/src/pkg uv_hexagonal/src/app/core uv_hexagonal/src/app/adapters poetry_flat partial_config
touch greenfield/src/pkg/__init__.py
printf '[project]\nname="pkg"\nversion="0"\n' > greenfield/pyproject.toml
touch uv_hexagonal/uv.lock uv_hexagonal/src/app/core/__init__.py uv_hexagonal/src/app/adapters/__init__.py
printf '[project]\nname="app"\nversion="0"\n' > uv_hexagonal/pyproject.toml
touch poetry_flat/poetry.lock
printf 'x = 1\n' > poetry_flat/mod.py
printf '[tool.poetry]\nname="flat"\nversion="0"\n' > poetry_flat/pyproject.toml
printf '[tool.ruff]\nline-length = 100\n' > partial_config/pyproject.toml
printf 'repos: []\n' > partial_config/.pre-commit-config.yaml
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest skills/setup-python-quality-gates/tests/test_fixtures_shape.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/setup-python-quality-gates/tests/fixtures skills/setup-python-quality-gates/tests/test_fixtures_shape.py
git commit -m "test(skill): add detection fixture repos (greenfield/uv-hex/poetry-flat/partial)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `detect.py` — deterministic detection

**Files:**
- Create: `skills/setup-python-quality-gates/scripts/gate_setup/detect.py`
- Create: `skills/setup-python-quality-gates/scripts/gate_setup/__init__.py` (empty)
- Test: `skills/setup-python-quality-gates/tests/test_detect.py`

**Interfaces:**
- Consumes: fixtures from Task 3.
- Produces: `detect(root: Path) -> dict` and a `python -m gate_setup.detect <root>` CLI printing that dict as JSON. Returned dict keys (exact):
  ```
  {
    "pkg_manager": "uv"|"poetry"|"pdm"|"pip"|None,
    "audit_export": str|None,          # command to pipe into pip-audit, e.g. "uv export --no-hashes --extra dev"
    "layout": {"src_layout": bool, "core_candidates": list[str], "packages": list[str]},
    "existing": {"ruff": bool, "pyright": bool, "coverage": bool, "precommit": bool, "ci": bool},
    "git": {"host": str|None, "visibility": str|None, "admin": bool|None, "gh_auth": bool}
  }
  ```

- [ ] **Step 1: Write the failing test**

```python
# skills/setup-python-quality-gates/tests/test_detect.py
import sys
from pathlib import Path
SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.detect import detect  # noqa: E402

F = SKILL / "tests/fixtures"

def test_uv_hexagonal():
    d = detect(F / "uv_hexagonal")
    assert d["pkg_manager"] == "uv"
    assert d["audit_export"] and "uv export" in d["audit_export"]
    assert d["layout"]["src_layout"] is True
    assert "app.core" in d["layout"]["core_candidates"]

def test_poetry_flat():
    d = detect(F / "poetry_flat")
    assert d["pkg_manager"] == "poetry"
    assert d["layout"]["src_layout"] is False
    assert d["layout"]["core_candidates"] == []   # no core pkg -> import-linter skipped later

def test_greenfield_no_lock():
    d = detect(F / "greenfield")
    assert d["pkg_manager"] is None                # SKILL.md will offer `uv init`
    assert d["existing"]["ruff"] is False

def test_partial_config_detected():
    d = detect(F / "partial_config")
    assert d["existing"]["ruff"] is True
    assert d["existing"]["precommit"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/setup-python-quality-gates/tests/test_detect.py -v`
Expected: FAIL — `ModuleNotFoundError: gate_setup.detect`.

- [ ] **Step 3: Write minimal implementation**

```python
# skills/setup-python-quality-gates/scripts/gate_setup/detect.py
from __future__ import annotations
import json, subprocess, sys, tomllib
from pathlib import Path

_AUDIT = {
    "uv": "uv export --no-hashes --all-extras",
    "poetry": "poetry export --without-hashes --with dev -f requirements.txt",
    "pdm": "pdm export --no-hashes -d",
    "pip": "cat requirements.txt",
}

def _pkg_manager(root: Path) -> str | None:
    if (root / "uv.lock").exists():
        return "uv"
    if (root / "poetry.lock").exists():
        return "poetry"
    if (root / "pdm.lock").exists():
        return "pdm"
    if list(root.glob("requirements*.txt")):
        return "pip"
    return None

def _layout(root: Path) -> dict:
    src = root / "src"
    src_layout = src.is_dir()
    base = src if src_layout else root
    packages: list[str] = []
    core_candidates: list[str] = []
    if base.is_dir():
        for init in base.rglob("__init__.py"):
            rel = init.parent.relative_to(base)
            dotted = ".".join(rel.parts)
            if not dotted:
                continue
            packages.append(dotted)
            if rel.parts and rel.parts[-1] in {"core", "domain", "entities"}:
                core_candidates.append(dotted)
    return {"src_layout": src_layout, "core_candidates": sorted(core_candidates),
            "packages": sorted(packages)}

def _existing(root: Path) -> dict:
    pyproject = {}
    p = root / "pyproject.toml"
    if p.exists():
        try:
            pyproject = tomllib.loads(p.read_text())
        except tomllib.TOMLDecodeError:
            pyproject = {}
    tool = pyproject.get("tool", {})
    return {
        "ruff": "ruff" in tool,
        "pyright": "pyright" in tool,
        "coverage": "coverage" in tool,
        "precommit": (root / ".pre-commit-config.yaml").exists(),
        "ci": (root / ".github" / "workflows").is_dir()
              and any((root / ".github" / "workflows").glob("*.y*ml")),
    }

def _git(root: Path) -> dict:
    def gh(*args: str) -> str | None:
        try:
            r = subprocess.run(["gh", *args], cwd=root, capture_output=True, text=True, timeout=15)
            return r.stdout.strip() if r.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
    authed = gh("auth", "status") is not None
    host = None
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root,
                            capture_output=True, text=True)
    if remote.returncode == 0 and "github.com" in remote.stdout:
        host = "github"
    visibility = admin = None
    if authed and host == "github":
        vis = gh("repo", "view", "--json", "visibility", "-q", ".visibility")
        visibility = vis.lower() if vis else None
        adm = gh("repo", "view", "--json", "viewerPermission", "-q", ".viewerPermission")
        admin = (adm == "ADMIN") if adm is not None else None
    return {"host": host, "visibility": visibility, "admin": admin, "gh_auth": authed}

def detect(root: Path) -> dict:
    root = Path(root)
    pm = _pkg_manager(root)
    return {
        "pkg_manager": pm,
        "audit_export": _AUDIT.get(pm) if pm else None,
        "layout": _layout(root),
        "existing": _existing(root),
        "git": _git(root),
    }

if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps(detect(target), indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest skills/setup-python-quality-gates/tests/test_detect.py -v`
Expected: PASS (4 tests). The `_git` calls on fixtures return `gh_auth` from the real environment but `host=None` (fixtures have no origin remote), so git assertions aren't made in these tests — correct.

- [ ] **Step 5: Commit**

```bash
git add skills/setup-python-quality-gates/scripts skills/setup-python-quality-gates/tests/test_detect.py
git commit -m "feat(skill): add detect.py (pkg-mgr/layout/existing-config/git detection)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Write the SKILL.md procedure + reference docs

**Files:**
- Modify: `skills/setup-python-quality-gates/SKILL.md` (fill the phase sections)
- Create: `skills/setup-python-quality-gates/references/detectors.md`
- Create: `skills/setup-python-quality-gates/references/thresholds.md`
- Create: `skills/setup-python-quality-gates/references/tiers.md`
- Create: `skills/setup-python-quality-gates/references/anti-gaming.md`
- Test: `skills/setup-python-quality-gates/tests/test_skill_doc.py`

**Interfaces:**
- Consumes: `detect.py` (Phase 0 runs `python -m gate_setup.detect .`), all templates (Phase 4 renders their tokens), `references/*` (linked from SKILL.md).
- Produces: an executable procedure. No code symbols consumed downstream — Task 6 and 7 consume the installed artifacts, not SKILL.md functions.

- [ ] **Step 1: Write the failing test**

The prose procedure isn't unit-testable, but its *structure* is — assert every phase, every reference link, and the measure→propose→confirm gate are present and internally consistent.

```python
# skills/setup-python-quality-gates/tests/test_skill_doc.py
from pathlib import Path
SKILL = Path(__file__).resolve().parents[1]

def test_skill_has_all_phases_and_refs():
    text = (SKILL / "SKILL.md").read_text()
    for phase in ["Phase 0", "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]:
        assert phase in text, f"missing {phase}"
    # references exist and are linked
    for ref in ["detectors.md", "thresholds.md", "tiers.md", "anti-gaming.md"]:
        assert (SKILL / "references" / ref).exists(), f"missing ref file {ref}"
        assert ref in text, f"SKILL.md does not link {ref}"

def test_confirm_gates_documented():
    text = (SKILL / "SKILL.md").read_text().lower()
    # the three user gates from the spec must be explicit
    assert "confirm" in text and "overwrite" in text          # Phase 4 merge-confirm
    assert "measured" in text or "current" in text            # Phase 2 measure-then-propose
    assert "tier" in text                                     # Phase 3

def test_l3_degradation_documented():
    text = (SKILL / "SKILL.md").read_text().lower()
    assert "advisory" in text  # L3 degrade path when ruleset can't apply
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/setup-python-quality-gates/tests/test_skill_doc.py -v`
Expected: FAIL — reference files missing / phase bodies empty of the asserted keywords.

- [ ] **Step 3: Write the SKILL.md body + references**

Fill `SKILL.md` phases (each a numbered, executable procedure for Claude):

- **Phase 0 Detect:** run `python -m gate_setup.detect .`; read the JSON; for each `null` (pkg_manager, git.host) state it and ask rather than guess. Link `references/detectors.md`.
- **Phase 1 Measure:** run the tools the repo already permits, capturing current numbers: `pytest --cov` (coverage %), `ruff check --select C901 --statistics` (worst complexity), `pyright --outputjson` or `--stats` (error count under strict), `vulture` (findings). If a tool isn't installed, install it into the project's dev deps first (per detected pkg-mgr). Link `references/thresholds.md` for exact parse recipes.
- **Phase 2 Propose:** present a measured-vs-proposed table; greenfield (near-zero code) → strict canonical defaults (coverage 92 / complexity 10 / pyright strict / vulture 60); legacy → baseline = current reality, and pyright starts at the mode the code passes with a documented graduate path. Ask the user to confirm/edit each. If `layout.core_candidates` non-empty, propose import-linter contracts (forbidden: core imports adapters/backends; independence among sibling adapters) and ask; else state import-linter is skipped.
- **Phase 3 Tier:** ask L1/L2/L3. Describe what each adds (link `references/tiers.md`).
- **Phase 4 Write (merge + confirm):** for each target file: if `existing[...]` is False → render the template (substitute confirmed tokens; strip `# TEMPLATE-CONDITIONAL: uv-only` lines when pkg-mgr≠uv; add the import-linter hook + contracts only if opted-in) and write. If True → show a diff of what would be added, merge non-destructively (keep the user's rules, append missing gate blocks), and **confirm before overwriting any conflicting key**. Never lower a threshold already present and higher than the proposal (state "keeping existing higher value N"). Copy `templates/scripts/*` to the repo's `scripts/`. L3 only: write CODEOWNERS; apply `ruleset.json` via `gh api` **only if** `git.admin` and visibility allows — else install the CI-side ratchet/suppression steps and report CODEOWNERS/required-review are **advisory** until protection is enabled.
- **Phase 5 Verify:** see Task 6.

Write the four reference docs with the depth content from the spec (detectors table + fallbacks; per-gate measure/parse recipes; tier contents; anti-gaming rationale = actor-vs-judge + ratchet + suppression-diff + why CODEOWNERS needs protection).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest skills/setup-python-quality-gates/tests/test_skill_doc.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add skills/setup-python-quality-gates/SKILL.md skills/setup-python-quality-gates/references skills/setup-python-quality-gates/tests/test_skill_doc.py
git commit -m "feat(skill): write SKILL.md procedure + reference docs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `--verify` self-verification (live ratchet proof)

**Files:**
- Create: `skills/setup-python-quality-gates/scripts/gate_setup/verify.py`
- Test: `skills/setup-python-quality-gates/tests/test_verify.py`

**Interfaces:**
- Consumes: an installed repo's `scripts/gate_ratchet.py` + `pyproject.toml`.
- Produces: `prove_ratchet_bites(root: Path) -> bool` — temporarily lowers `fail_under` in a COPY of pyproject, runs the ratchet against the real one as base, asserts it fails, never mutates the real file. CLI: `python -m gate_setup.verify <root>`.

- [ ] **Step 1: Write the failing test**

```python
# skills/setup-python-quality-gates/tests/test_verify.py
import sys, shutil, textwrap
from pathlib import Path
SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.verify import prove_ratchet_bites  # noqa: E402

def _repo(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(SKILL / "templates/scripts/gate_ratchet.py", tmp_path / "scripts/gate_ratchet.py")
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [tool.coverage.report]
        fail_under = 90
    """))
    return tmp_path

def test_verify_detects_weakening(tmp_path):
    # the proof must return True == "ratchet correctly blocked a simulated weakening"
    assert prove_ratchet_bites(_repo(tmp_path)) is True

def test_verify_leaves_pyproject_untouched(tmp_path):
    repo = _repo(tmp_path)
    before = (repo / "pyproject.toml").read_text()
    prove_ratchet_bites(repo)
    assert (repo / "pyproject.toml").read_text() == before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest skills/setup-python-quality-gates/tests/test_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: gate_setup.verify`.

- [ ] **Step 3: Write minimal implementation**

```python
# skills/setup-python-quality-gates/scripts/gate_setup/verify.py
from __future__ import annotations
import re, subprocess, sys, tempfile, shutil
from pathlib import Path

def prove_ratchet_bites(root: Path) -> bool:
    """Simulate lowering the coverage floor and confirm gate_ratchet.py rejects it.

    Runs entirely in a temp copy; the real pyproject.toml is never modified.
    Returns True iff the ratchet exits non-zero on the weakened copy.
    """
    root = Path(root)
    ratchet = root / "scripts" / "gate_ratchet.py"
    pyproject = root / "pyproject.toml"
    if not ratchet.exists() or not pyproject.exists():
        return False
    original = pyproject.read_text()
    m = re.search(r"fail_under\s*=\s*(\d+)", original)
    if not m:
        return False
    weakened = original[:m.start(1)] + str(int(m.group(1)) - 10) + original[m.end(1):]
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "work"
        shutil.copytree(root, work, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", ".venv", "node_modules"))
        # base = original (a mini git repo so the ratchet can diff against it)
        subprocess.run(["git", "init", "-q"], cwd=work, check=True)
        subprocess.run(["git", "add", "-A"], cwd=work, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "base"], cwd=work, check=True)
        (work / "pyproject.toml").write_text(weakened)
        r = subprocess.run([sys.executable, str(work / "scripts/gate_ratchet.py")],
                           cwd=work, capture_output=True, text=True)
        return r.returncode != 0

if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    ok = prove_ratchet_bites(root)
    print("ratchet BITES (weakening blocked)" if ok else "ratchet did NOT block weakening")
    sys.exit(0 if ok else 1)
```

Note for implementer: `gate_ratchet.py` compares against `origin/master` by default — check how it selects its base (it may need a `BASE` env var or arg). If it hard-codes `origin/master`, add a base override to the verbatim script is NOT allowed (it ships verbatim); instead set up the temp repo so the ratchet's expected base ref exists (e.g. create a branch/ref named as the ratchet expects, or set the env var the ratchet already honors). Inspect `gate_ratchet.py` for its base-ref mechanism during Step 3 and adapt the temp-repo setup accordingly. If the script honors no override, the verify uses `git` to create the ref name it reads.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest skills/setup-python-quality-gates/tests/test_verify.py -v`
Expected: PASS (2 tests). If the ratchet's base-ref lookup fails in the temp repo, fix the temp-repo setup (create the ref the ratchet reads) — do not edit the verbatim ratchet.

- [ ] **Step 5: Commit**

```bash
git add skills/setup-python-quality-gates/scripts/gate_setup/verify.py skills/setup-python-quality-gates/tests/test_verify.py
git commit -m "feat(skill): add --verify live ratchet-bites self-check

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Comprehensive verification (spec satisfaction + real end-to-end)

**Files:**
- Create: `skills/setup-python-quality-gates/tests/test_e2e_install.py`
- Create: `skills/setup-python-quality-gates/VERIFICATION.md` (the criterion→check map + "what I did NOT verify")

**Interfaces:**
- Consumes: everything built in Tasks 1–6.
- Produces: a passing e2e that installs L1 onto the greenfield fixture and proves green-on-day-one; a documented map of S1–S10.

- [ ] **Step 1: Map every success criterion to a concrete check**

Write `VERIFICATION.md` with a row per S1–S10 (from the spec), each naming the test or manual step that satisfies it. Mark which are automated here vs. deferred to real-repo manual runs.

- [ ] **Step 2: Write the real end-to-end test (L1 on greenfield)**

```python
# skills/setup-python-quality-gates/tests/test_e2e_install.py
import sys, shutil, subprocess, textwrap
from pathlib import Path
SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.detect import detect  # noqa: E402

def test_greenfield_l1_is_green_day_one(tmp_path):
    # arrange: a real tiny package with one clean, typed, tested function
    pkg = tmp_path / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "core.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_core.py").write_text(
        "from demo.core import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [project]
        name = "demo"
        version = "0"
        requires-python = ">=3.11"
        [tool.pytest.ini_options]
        pythonpath = ["src"]
    """))
    # act: detection should see greenfield + no existing gates
    d = detect(tmp_path)
    assert d["existing"]["ruff"] is False
    # apply the strict greenfield gate block (simulates Phase 4 render for a clean repo)
    gates = (SKILL / "templates/pyproject.gates.toml").read_text()
    rendered = (gates.replace("{{COVERAGE_FLOOR}}", "92").replace("{{MAX_COMPLEXITY}}", "10")
                .replace("{{VULTURE_MIN_CONFIDENCE}}", "60").replace("{{PYRIGHT_MODE}}", "strict")
                .replace("{{MUTATION_FLOOR}}", "0").replace('{{SRC_DIRS}}', '["src/demo"]'))
    with (tmp_path / "pyproject.toml").open("a") as f:
        f.write("\n" + rendered)
    # assert: the core gates pass on day one for clean code
    ruff = subprocess.run(["ruff", "check", "."], cwd=tmp_path, capture_output=True, text=True)
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    cov = subprocess.run(["pytest", "--cov=demo", "--cov-report=", "--cov-fail-under=92"],
                         cwd=tmp_path, capture_output=True, text=True)
    assert cov.returncode == 0, cov.stdout + cov.stderr
```

- [ ] **Step 3: Run test to verify it fails, then passes**

Run: `pytest skills/setup-python-quality-gates/tests/test_e2e_install.py -v`
Expected first: FAIL if the rendered template has a stray token or a bad table (fix the template). Then PASS once the greenfield block renders cleanly and clean code clears ruff + 100% coverage ≥ 92 floor.

- [ ] **Step 4: Run the FULL skill test suite + this repo's gate**

```bash
pytest skills/setup-python-quality-gates/ -v
PATH="$PWD/.venv/bin:$PATH" pre-commit run --all-files --hook-stage pre-commit
PATH="$PWD/.venv/bin:$PATH" SKIP=pip-audit pre-commit run --all-files --hook-stage pre-push
```
Expected: all skill tests pass; this repo's own gates stay green (the new skill dir must not break tvagent's ruff/pyright — add `skills/**` to tvagent's tool excludes if strict pyright flags template/fixture stubs, and note it in VERIFICATION.md).

- [ ] **Step 5: Finalize VERIFICATION.md "What I did NOT verify"**

List honestly: L2 CI job not run in a real GitHub Actions runner here; L3 ruleset application not exercised end-to-end (needs an admin+eligible repo); poetry/pdm lock-drift hooks detected but not run; mutation baseline not measured. State each as a deferred manual check with the command to run it on a real repo.

- [ ] **Step 6: Commit + open PR**

```bash
git add skills/setup-python-quality-gates/tests/test_e2e_install.py skills/setup-python-quality-gates/VERIFICATION.md
git commit -m "test(skill): e2e greenfield L1 green-day-one + S1-S10 verification map

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
gh pr create --base master --title "feat: setup-python-quality-gates skill" --body "$(cat <<'EOF'
Reusable skill that installs the tiered, tamper-resistant quality-gate stack into any Python repo. Implements docs/superpowers/specs/2026-09-18-quality-gates-skill-design.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**1. Spec coverage:**

| Spec item | Task |
|-----------|------|
| Decision 1 (tiers) | Task 5 Phase 3 + `references/tiers.md`; Task 2 conditional template bits |
| Decision 2 (research-then-ask) | Task 5 Phases 1–2 + `references/thresholds.md` |
| Decision 3 (import-linter detect+propose) | Task 4 `core_candidates`; Task 5 Phase 2/4 opt-in |
| Decision 4 (pkg-mgr detect+adapt) | Task 4 `_pkg_manager`/`_AUDIT`; Task 2 `{{PKG_*}}` tokens |
| Decision 5 (merge+confirm) | Task 5 Phase 4 |
| 4 detectors | Task 4 |
| Threshold engine | Task 5 Phase 1–2 |
| 3 tiers + L3 degradation | Task 2 (templates), Task 5 (Phase 4 advisory path) |
| Templates carried | Task 1 (verbatim scripts) + Task 2 (parameterized) |
| Idempotency (never lower higher) | Task 5 Phase 4 rule; partial-config fixture Task 3; detection Task 4 |
| Self-verification | Task 6 (`--verify`) + Task 7 (e2e) |
| S1 greenfield strict green | Task 7 test_e2e |
| S2 legacy baseline green | Task 7 VERIFICATION (deferred manual — needs a debt repo) |
| S3 never lower higher | Task 5 Phase 4 + noted in VERIFICATION |
| S4 pkg-mgr uv+poetry | Task 4 tests |
| S5 import-linter shape gate | Task 4 tests (core_candidates for hex vs flat) |
| S6 merge not stomp | Task 4 `existing` detection + Task 5 Phase 4 |
| S7 ratchet blocks weakening | Task 6 |
| S8 L3 graceful degrade | Task 5 Phase 4 + VERIFICATION deferred |
| S9 "did NOT verify" list | Task 7 Step 5 |
| S10 no destructive write w/o confirm | Task 5 Phase 4 |

Gaps: S2 and S8 have no automated test (need a debt repo / an admin GitHub repo) — both are explicitly logged as deferred manual checks in VERIFICATION.md with the exact command. Acceptable: they require environments a hermetic test can't provide.

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". Every code step has real code. The one judgment call (ratchet base-ref in Task 6 Step 3) is spelled out with the constraint (script ships verbatim; adapt the temp repo, not the script).

**3. Type consistency:** `detect(root) -> dict` keys used in Task 4 tests and Task 7 match the Interfaces block. `prove_ratchet_bites(root) -> bool` consistent between Task 6 def, test, and CLI. Template token set identical between Task 2 Interfaces and `TOKENS.md` test.
