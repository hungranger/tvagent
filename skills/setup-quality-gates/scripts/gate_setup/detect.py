from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

_AUDIT: dict[str, str] = {
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

def _layout(root: Path) -> dict[str, Any]:
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

def _existing(root: Path) -> dict[str, bool]:
    pyproject: dict[str, Any] = {}
    p = root / "pyproject.toml"
    if p.exists():
        try:
            pyproject = tomllib.loads(p.read_text())
        except tomllib.TOMLDecodeError:
            pyproject = {}
    tool: dict[str, Any] = pyproject.get("tool", {})
    return {
        "ruff": "ruff" in tool,
        "pyright": "pyright" in tool,
        "coverage": "coverage" in tool,
        "precommit": (root / ".pre-commit-config.yaml").exists(),
        "ci": (root / ".github" / "workflows").is_dir()
              and any((root / ".github" / "workflows").glob("*.y*ml")),
    }

def _git(root: Path) -> dict[str, Any]:
    def gh(*args: str) -> str | None:
        try:
            r = subprocess.run(["gh", *args], cwd=root, capture_output=True, text=True,
                                timeout=15, check=False)
            return r.stdout.strip() if r.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
    authed = gh("auth", "status") is not None
    host: str | None = None
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root,
                            capture_output=True, text=True, check=False)
    if remote.returncode == 0 and "github.com" in remote.stdout:
        host = "github"
    visibility: str | None = None
    admin: bool | None = None
    if authed and host == "github":
        vis = gh("repo", "view", "--json", "visibility", "-q", ".visibility")
        visibility = vis.lower() if vis else None
        adm = gh("repo", "view", "--json", "viewerPermission", "-q", ".viewerPermission")
        admin = (adm == "ADMIN") if adm is not None else None
    return {"host": host, "visibility": visibility, "admin": admin, "gh_auth": authed}

def detect(root: Path) -> dict[str, Any]:
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
