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
