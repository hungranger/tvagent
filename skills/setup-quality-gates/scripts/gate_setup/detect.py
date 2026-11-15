from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

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
    return {
        "src_layout": src_layout,
        "core_candidates": sorted(core_candidates),
        "packages": sorted(packages),
    }


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
            r = subprocess.run(
                ["gh", *args], cwd=root, capture_output=True, text=True, timeout=15, check=False
            )
            return r.stdout.strip() if r.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    authed = gh("auth", "status") is not None
    host: str | None = None
    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
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


def _is_react_ts(root: Path) -> bool:
    pkg = root / "package.json"
    if not pkg.exists():
        return False
    if (root / "tsconfig.json").exists():
        return True
    try:
        data: Any = json.loads(pkg.read_text())
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    obj = cast("dict[str, Any]", data)
    deps: set[str] = set()
    for key in ("dependencies", "devDependencies"):
        section = obj.get(key)
        if isinstance(section, dict):
            deps |= set(cast("dict[str, Any]", section))
    return bool(deps & {"react", "next", "vite"})


def _python(root: Path) -> dict[str, Any]:
    pm = _pkg_manager(root)
    return {
        "pkg_manager": pm,
        "audit_export": _AUDIT.get(pm) if pm else None,
        "layout": _layout(root),
        "existing": _existing(root),
    }


def detect(root: Path) -> dict[str, Any]:
    root = Path(root)
    signals = {
        "go": (root / "go.mod").exists(),
        "python": (root / "pyproject.toml").exists() or (root / "setup.py").exists(),
        "react-ts": _is_react_ts(root),
        "rust": (root / "Cargo.toml").exists(),
    }
    candidates = sorted(k for k, v in signals.items() if v)
    language = candidates[0] if len(candidates) == 1 else None
    out: dict[str, Any] = {"language": language, "candidates": candidates, "git": _git(root)}
    if language == "python":
        out["python"] = _python(root)
    elif language:
        # ponytail: non-python profiles fill these in their own tasks
        out[language] = {"pkg_manager": None, "existing": {}}
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps(detect(target), indent=2))
