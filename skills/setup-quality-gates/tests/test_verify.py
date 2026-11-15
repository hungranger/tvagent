import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.verify import prove_ratchet_bites  # noqa: E402  # pyright: ignore[reportUnknownVariableType]

MANIFEST = """[meta]
language = "python"
[thresholds]
coverage_floor = 90
"""


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    shutil.copy(SKILL / "templates/scripts/gate_ratchet.py", tmp_path / "scripts/gate_ratchet.py")
    shutil.copytree(
        SKILL / "scripts/gate_setup",
        tmp_path / "scripts/gate_setup",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (tmp_path / "quality-gates.toml").write_text(MANIFEST)
    return tmp_path


def test_verify_seeds_manifest(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert prove_ratchet_bites(repo) is True
    assert (repo / "quality-gates.toml").read_text() == MANIFEST
    assert (repo / "pyproject.toml").read_text() == "[project]\nname='x'\n"


def test_verify_false_without_manifest(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "quality-gates.toml").unlink()
    assert prove_ratchet_bites(repo) is False


def test_verify_crash_is_not_a_bite(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "scripts/gate_setup/manifest.py").write_text("raise ImportError('boom')\n")
    assert prove_ratchet_bites(repo) is False
