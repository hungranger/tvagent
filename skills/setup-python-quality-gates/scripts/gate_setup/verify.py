"""Live self-check: prove the installed gate_ratchet.py actually blocks a weakening.

Builds a throwaway git repo in a temp dir, commits the real (un-weakened)
pyproject.toml as the ratchet's base, then overwrites the *working tree*
copy with a lowered coverage floor and runs the ratchet against it. The
real repo's pyproject.toml is never touched.

gate_ratchet.py diffs the working tree against `git show origin/master:...`
(BASE_REF, hard-coded, verbatim script -- not ours to edit). A plain `git
init` + commit does NOT create a ref named `origin/master`, so without an
explicit fixup `git show origin/master:pyproject.toml` fails, the ratchet
treats the gate as newly-added (no baseline to compare against) and skips
it, returning 0 -- a false "not weakened" even though this function just
weakened it. Fix: after committing the base, alias that commit under
`refs/remotes/origin/master` so `git show origin/master:...` resolves to it.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def prove_ratchet_bites(root: Path) -> bool:
    """Simulate lowering the coverage floor and confirm gate_ratchet.py rejects it.

    Runs entirely in a temp git repo seeded from `root`; `root`'s own
    pyproject.toml is only read, never written. Returns True iff the
    ratchet exits non-zero against the weakened working tree.
    """
    root = Path(root)
    ratchet_src = root / "scripts" / "gate_ratchet.py"
    pyproject_src = root / "pyproject.toml"
    if not ratchet_src.exists() or not pyproject_src.exists():
        return False
    original = pyproject_src.read_text()
    m = re.search(r"fail_under\s*=\s*(\d+)", original)
    if not m:
        return False
    weakened = original[: m.start(1)] + str(int(m.group(1)) - 10) + original[m.end(1) :]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "work"
        (work / "scripts").mkdir(parents=True)
        (work / "scripts" / "gate_ratchet.py").write_text(ratchet_src.read_text())
        (work / "pyproject.toml").write_text(original)

        _git("init", "-q", cwd=work)
        _git("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A", cwd=work)
        _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base", cwd=work)
        # gate_ratchet.py reads BASE_REF = "origin/master"; a bare `git init`
        # + commit never creates that ref, so alias the base commit to it.
        _git("update-ref", "refs/remotes/origin/master", "HEAD", cwd=work)

        (work / "pyproject.toml").write_text(weakened)
        result = subprocess.run(
            [sys.executable, str(work / "scripts" / "gate_ratchet.py")],
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode != 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    bites = prove_ratchet_bites(target)
    print("ratchet BITES (weakening blocked)" if bites else "ratchet did NOT block weakening")
    sys.exit(0 if bites else 1)
