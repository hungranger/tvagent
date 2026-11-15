import shutil
import sys
import textwrap
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.verify import prove_ratchet_bites  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    shutil.copy(SKILL / "templates/scripts/gate_ratchet.py", tmp_path / "scripts/gate_ratchet.py")
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [tool.coverage.report]
        fail_under = 90
    """))
    return tmp_path

def test_verify_detects_weakening(tmp_path: Path) -> None:
    # the proof must return True == "ratchet correctly blocked a simulated weakening"
    assert prove_ratchet_bites(_repo(tmp_path)) is True

def test_verify_leaves_pyproject_untouched(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = (repo / "pyproject.toml").read_text()
    prove_ratchet_bites(repo)
    assert (repo / "pyproject.toml").read_text() == before
