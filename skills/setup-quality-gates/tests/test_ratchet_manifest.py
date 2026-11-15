import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
RATCHET = SKILL / "templates" / "scripts" / "gate_ratchet.py"

BASE = """[thresholds]
coverage_floor = 90
complexity_max = 10
mutation_floor = 70
type_strictness = "strict"
lint_rules = ["E", "C901"]
[protected]
paths = [".github/**", "quality-gates.toml"]
"""


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _run(tmp_path: Path, pr: str) -> subprocess.CompletedProcess[str]:
    _git(tmp_path, "init", "-q")
    (tmp_path / "quality-gates.toml").write_text(BASE)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b")
    _git(tmp_path, "update-ref", "refs/remotes/origin/master", "HEAD")
    (tmp_path / "quality-gates.toml").write_text(pr)
    return subprocess.run(
        [sys.executable, str(RATCHET)], cwd=tmp_path, capture_output=True, text=True, check=False
    )


def _fails(tmp_path: Path, old: str, new: str, needle: str) -> None:
    r = _run(tmp_path, BASE.replace(old, new))
    assert r.returncode == 1, r.stdout + r.stderr
    assert needle in r.stdout


def test_lowered_coverage_fails(tmp_path: Path):
    _fails(tmp_path, "coverage_floor = 90", "coverage_floor = 50", "coverage_floor")


def test_raised_complexity_fails(tmp_path: Path):
    _fails(tmp_path, "complexity_max = 10", "complexity_max = 20", "complexity_max")


def test_strictness_downgrade_fails(tmp_path: Path):
    _fails(tmp_path, '"strict"', '"standard"', "type_strictness")


def test_lint_rules_shrink_fails(tmp_path: Path):
    _fails(tmp_path, '["E", "C901"]', '["E"]', "lint_rules")


def test_protected_paths_shrink_fails(tmp_path: Path):
    _fails(tmp_path, '".github/**", ', "", "protected.paths")


def test_deleted_key_fails(tmp_path: Path):
    _fails(tmp_path, "mutation_floor = 70\n", "", "DELETED")


def test_new_key_allowed(tmp_path: Path):
    base = BASE.replace("mutation_floor = 70\n", "")
    _git(tmp_path, "init", "-q")
    (tmp_path / "quality-gates.toml").write_text(base)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b")
    _git(tmp_path, "update-ref", "refs/remotes/origin/master", "HEAD")
    (tmp_path / "quality-gates.toml").write_text(BASE)  # PR adds mutation_floor
    r = subprocess.run(
        [sys.executable, str(RATCHET)], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert r.returncode == 0, r.stdout + r.stderr
