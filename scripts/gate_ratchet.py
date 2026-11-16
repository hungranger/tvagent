"""Fail CI if any quality gate was weakened relative to origin/master.

Reads `quality-gates.toml` (working tree) against `git show
origin/master:quality-gates.toml` and judges every key generically by its
direction in `gate_setup.manifest.KEY_DIRECTIONS`:

  scalar-up    must not go down      scalar-down  must not go up
  enum         strictness index must not drop (STRICTNESS_ORDER)
  set          must not shrink (lint_rules, protected.paths)

A key present on master but absent in this tree is a HARD FAIL (deletion is
the strongest weakening). A key absent on master is new and allowed. No
manifest on master (bootstrap) -> skipped with a note.

stdlib only: tomllib for TOML, subprocess for `git show`.
"""

import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

# Resolve `gate_setup`: when run as `python scripts/gate_ratchet.py` the script's
# own dir (which holds gate_setup/ in an installed repo) is already sys.path[0],
# so we only APPEND a fallback — never insert ahead of it. The fallback points at
# the skill tree's scripts/ (two levels above templates/scripts/), used when this
# file runs from the skill tree itself. Appending (not inserting) also means a
# stray sibling `scripts/` can never shadow the installed gate_setup.
# CI invokes this as `python scripts/gate_ratchet.py` (NOT `python -I`): -I/-P
# drops the script's own dir from sys.path, so `import gate_setup` would then
# raise ModuleNotFoundError. Running under -I is unsupported.
sys.path.append(str(Path(__file__).resolve().parents[2] / "scripts"))
from gate_setup.manifest import (  # pyright: ignore[reportMissingImports]
    KEY_DIRECTIONS,
    STRICTNESS_ORDER,
    ManifestError,
    load,
    validate,
)

BASE_REF = "origin/master"
MANIFEST = "quality-gates.toml"


def git_show(ref: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, text=True, check=False
    )
    return proc.stdout if proc.returncode == 0 else None


def _flat(m: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(m.get("thresholds", {}))
    if "paths" in m.get("protected", {}):
        out["protected.paths"] = m["protected"]["paths"]
    # Always emit (even as []) so deleting the whole [drift] table reads as a
    # shrunk set, not a new/absent key. spec=key PAIRS catch retargeting a
    # binding to a different native path, not just deleting one.
    out["drift.bindings"] = sorted(f"{spec}={key}" for spec, key in m.get("drift", {}).items())
    return out


def run(current: dict[str, Any], base: dict[str, Any] | None) -> list[str]:
    cur, old = _flat(current), _flat(base or {})
    failures: list[str] = []
    for key, direction in KEY_DIRECTIONS.items():
        if key not in old:
            continue  # no baseline on master -- new gate, nothing to ratchet against
        if key not in cur:
            failures.append(f"{key} was DELETED (was {old[key]!r} on {BASE_REF})")
            continue
        c, o = cur[key], old[key]
        if direction == "scalar-up" and c < o:
            failures.append(f"{key} lowered: {o} -> {c}")
        elif direction == "scalar-down" and c > o:
            failures.append(f"{key} raised: {o} -> {c}")
        elif direction == "enum" and STRICTNESS_ORDER.index(c) < STRICTNESS_ORDER.index(o):
            failures.append(f"{key} downgraded: {o} -> {c}")
        elif direction == "set" and not set(o) <= set(c):
            failures.append(f"{key} lost entries: {sorted(set(o) - set(c))}")
    return failures


def main() -> int:
    try:
        current = load(Path(MANIFEST))
        base_text = git_show(BASE_REF, MANIFEST)
        base = validate(tomllib.loads(base_text)) if base_text and base_text.strip() else None
    except (ManifestError, tomllib.TOMLDecodeError) as e:
        print(f"GATE RATCHET FAILED -- unreadable manifest: {e}")
        return 1
    if base is None:
        print(f"note: {BASE_REF}:{MANIFEST} not found or empty -- skipping ratchet (bootstrap)")
    failures = run(current, base)
    if failures:
        print("GATE RATCHET FAILED -- gate(s) weakened relative to origin/master:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: no gate weakened relative to origin/master")
    return 0


if __name__ == "__main__":
    _base: dict[str, Any] = {
        "thresholds": {
            "coverage_floor": 90,
            "complexity_max": 10,
            "type_strictness": "strict",
            "lint_rules": ["E", "C901"],
            "mutation_floor": 70,
        },
        "protected": {"paths": [".github/**", "a"]},
    }
    assert run(_base, _base) == []
    assert run(_base, None) == []  # bootstrap
    _weak: dict[str, Any] = {
        "thresholds": {
            "coverage_floor": 50,
            "complexity_max": 20,
            "type_strictness": "standard",
            "lint_rules": ["E"],
        },
        "protected": {"paths": ["a"]},
    }
    _f = run(_weak, _base)
    assert len(_f) == 6, _f  # 4 weakened + mutation_floor DELETED + paths shrunk
    assert any("DELETED" in x for x in _f), _f
    assert (
        run(
            {
                "thresholds": {**_base["thresholds"], "vulture_confidence": 60},
                "protected": _base["protected"],
            },
            _base,
        )
        == []
    )  # new key allowed
    sys.exit(0 if "--self-check" in sys.argv else main())
