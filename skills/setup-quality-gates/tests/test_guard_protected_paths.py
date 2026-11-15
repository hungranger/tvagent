"""Installed guard template: protected set = DEFAULTS | override json | manifest (union only)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "templates" / "scripts" / "guard_protected_paths.py"


def _asks(cwd: Path, file_path: str) -> bool:
    payload = {"tool_name": "Edit", "tool_input": {"file_path": file_path}}
    p = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    assert p.returncode == 0
    if not p.stdout:
        return False
    return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


@pytest.mark.parametrize(
    "path",
    [
        "Cargo.toml",
        "Cargo.lock",
        "clippy.toml",
        "go.mod",
        "go.sum",
        "tsconfig.json",
        "biome.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "package.json",
        "quality-gates.toml",
        "scripts/gate_setup/manifest.py",
        "scripts/gate_setup/sub/x.py",
        "scripts/guard_protected_paths.py",
        "pyproject.toml",
        ".github/workflows/ci.yml",
    ],
)
def test_default_protected_asks(tmp_path: Path, path: str):
    assert _asks(tmp_path, path)


def test_root_package_json_abs_asks(tmp_path: Path):
    assert _asks(tmp_path, str(tmp_path / "package.json"))


def test_nested_package_json_silent(tmp_path: Path):
    assert not _asks(tmp_path, "src/x/package.json")
    assert not _asks(tmp_path, str(tmp_path / "src" / "x" / "package.json"))


def test_normal_nested_file_silent(tmp_path: Path):
    assert not _asks(tmp_path, "src/app/main.py")


def test_manifest_protected_path_honored(tmp_path: Path):
    (tmp_path / "quality-gates.toml").write_text(
        '[protected]\npaths = ["docs/secret.md", "infra/**"]\n'
    )
    assert _asks(tmp_path, "docs/secret.md")
    assert _asks(tmp_path, "infra/a/b.tf")
    assert not _asks(tmp_path, "docs/other.md")


def test_manifest_omitting_default_cannot_shrink(tmp_path: Path):
    (tmp_path / "quality-gates.toml").write_text('[protected]\npaths = ["docs/secret.md"]\n')
    assert _asks(tmp_path, "Cargo.toml")
    assert _asks(tmp_path, "scripts/gate_setup/manifest.py")


def test_broken_manifest_keeps_defaults(tmp_path: Path):
    (tmp_path / "quality-gates.toml").write_text("not = [valid")
    assert _asks(tmp_path, "go.mod")


def test_broken_override_json_keeps_defaults(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "protected-paths.json").write_text("{not json")
    assert _asks(tmp_path, "Cargo.toml")


def test_dotdot_root_package_json_asks(tmp_path: Path):
    assert _asks(tmp_path, "sub/../package.json")


def test_dotdot_gate_setup_asks(tmp_path: Path):
    assert _asks(tmp_path, "scripts/../scripts/gate_setup/manifest.py")


def test_bash_write_to_glob_protected_dir_asks(tmp_path: Path):
    (tmp_path / "quality-gates.toml").write_text('[protected]\npaths = ["infra/**"]\n')
    payload = {"tool_name": "Bash", "tool_input": {"command": "echo x > infra/main.tf"}}
    p = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert '"ask"' in p.stdout


def test_symlinked_settings_json_asks(tmp_path: Path):
    repo, outside = tmp_path / "repo", tmp_path / "outside"
    (repo / ".claude").mkdir(parents=True)
    outside.mkdir()
    (outside / "s.json").write_text("{}")
    (repo / ".claude" / "settings.json").symlink_to(outside / "s.json")
    assert _asks(repo, ".claude/settings.json")


def test_symlinked_root_package_json_asks(tmp_path: Path):
    repo, outside = tmp_path / "repo", tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    (outside / "p.json").write_text("{}")
    (repo / "package.json").symlink_to(outside / "p.json")
    assert _asks(repo, "package.json")
