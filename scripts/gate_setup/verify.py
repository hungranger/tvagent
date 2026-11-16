"""Live self-check: prove the installed gate_ratchet.py actually blocks a weakening.

Builds a throwaway git repo in a temp dir containing scripts/gate_ratchet.py,
the whole scripts/gate_setup/ package (the ratchet imports it) and the real
quality-gates.toml, commits that as the base, aliases it to
refs/remotes/origin/master (gate_ratchet.py reads BASE_REF = "origin/master",
which a bare `git init` never creates), then overwrites the *working tree*
manifest with `coverage_floor` lowered by 10 and runs the ratchet.
The real repo's quality-gates.toml is only read, never written.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def prove_ratchet_bites(root: Path) -> bool:
    """True iff gate_ratchet.py exits non-zero against a lowered coverage_floor."""
    root = Path(root)
    ratchet_src = root / "scripts" / "gate_ratchet.py"
    pkg_src = root / "scripts" / "gate_setup"
    manifest_src = root / "quality-gates.toml"
    if not (ratchet_src.exists() and pkg_src.is_dir() and manifest_src.exists()):
        return False
    original = manifest_src.read_text()
    m = re.search(r"coverage_floor\s*=\s*(\d+)", original)
    if not m:
        return False
    weakened = original[: m.start(1)] + str(int(m.group(1)) - 10) + original[m.end(1) :]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "work"
        (work / "scripts").mkdir(parents=True)
        shutil.copy(ratchet_src, work / "scripts" / "gate_ratchet.py")
        shutil.copytree(
            pkg_src, work / "scripts" / "gate_setup", ignore=shutil.ignore_patterns("__pycache__")
        )
        (work / "quality-gates.toml").write_text(original)

        _git("init", "-q", cwd=work)
        _git("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A", cwd=work)
        _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base", cwd=work)
        _git("update-ref", "refs/remotes/origin/master", "HEAD", cwd=work)

        (work / "quality-gates.toml").write_text(weakened)
        env = {**os.environ, "PYTHONPATH": str(work / "scripts")}
        result = subprocess.run(
            [sys.executable, str(work / "scripts" / "gate_ratchet.py")],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        # Require the ratchet's own failure message so a crash (ImportError) is not a "bite".
        return result.returncode != 0 and "coverage_floor lowered" in result.stdout


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    bites = prove_ratchet_bites(target)
    print("ratchet BITES (weakening blocked)" if bites else "ratchet did NOT block weakening")
    sys.exit(0 if bites else 1)
