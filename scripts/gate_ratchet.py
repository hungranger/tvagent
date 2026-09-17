"""Fail CI if any quality gate was weakened relative to origin/master.

Direction-aware: coverage floor must not go down, ruff `select` must not lose
a rule (mccabe max-complexity must not go up), vulture min_confidence must
not go up (higher = noisier = weaker), pyright must stay strict and must not
loosen reportMissing*/reportMissingTypeStubs toward "none", the mutation
floor (nightly-mutation.yml's `--min`) must not go down, and no
import-linter contract may be removed.

A gate whose config key is absent on master (no baseline to ratchet
against) is skipped with a printed note -- absence isn't intent, and there
is nothing to compare against. A gate that *was* present on master and is
now missing from this tree is a HARD FAIL, not a skip: deletion is the
strongest possible weakening (set-valued gates like ruff `select` and
import-linter contracts catch this by construction -- an empty/shrunk set
is already "weaker"; value-valued gates like `fail_under` check for it
explicitly, since a missing value is not comparable by `<`/`>`).

stdlib only: tomllib for TOML, subprocess for `git show origin/master:...`.
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

BASE_REF = "origin/master"


def git_show(ref: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, text=True, check=False
    )
    return proc.stdout if proc.returncode == 0 else None


def get(config: dict[str, Any], *keys: str) -> Any:
    node: Any = config
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return None
        node = cast(Any, node[key])
    return node


# --- individual gate checks: (current, base) -> list[failure message] -----


def check_coverage(current: dict[str, Any], base: dict[str, Any]) -> list[str]:
    cur, old = (
        get(current, "tool", "coverage", "report", "fail_under"),
        get(base, "tool", "coverage", "report", "fail_under"),
    )
    if old is None:
        return []  # no baseline in master -- new gate, nothing to ratchet against
    if cur is None:
        return [f"coverage fail_under was DELETED (was {old} in master)"]
    if cur >= old:
        return []
    return [f"coverage fail_under lowered: {old} -> {cur}"]


def check_ruff_select(current: dict[str, Any], base: dict[str, Any]) -> list[str]:
    cur = set(get(current, "tool", "ruff", "lint", "select") or [])
    cur |= set(get(current, "tool", "ruff", "lint", "extend-select") or [])
    old = set(get(base, "tool", "ruff", "lint", "select") or [])
    old |= set(get(base, "tool", "ruff", "lint", "extend-select") or [])
    missing = old - cur
    if not old or not missing:
        return []
    return [f"ruff select lost rule(s): {sorted(missing)}"]


def check_mccabe(current: dict[str, Any], base: dict[str, Any]) -> list[str]:
    cur, old = (
        get(current, "tool", "ruff", "lint", "mccabe", "max-complexity"),
        get(base, "tool", "ruff", "lint", "mccabe", "max-complexity"),
    )
    if old is None:
        return []  # no baseline in master -- new gate, nothing to ratchet against
    if cur is None:
        return [f"mccabe max-complexity was DELETED (was {old} in master)"]
    if cur <= old:
        return []
    return [f"mccabe max-complexity raised: {old} -> {cur}"]


def check_vulture(current: dict[str, Any], base: dict[str, Any]) -> list[str]:
    cur, old = (
        get(current, "tool", "vulture", "min_confidence"),
        get(base, "tool", "vulture", "min_confidence"),
    )
    if old is None:
        return []  # no baseline in master -- new gate, nothing to ratchet against
    if cur is None:
        return [f"vulture min_confidence was DELETED (was {old} in master)"]
    if cur <= old:
        return []
    return [f"vulture min_confidence raised (weaker, noisier floor is 60): {old} -> {cur}"]


_STRICTNESS = {"error": 2, "warning": 1, "none": 0}


def check_pyright(current: dict[str, Any], base: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    cur_mode = get(current, "tool", "pyright", "typeCheckingMode")
    if cur_mode != "strict":
        failures.append(f"pyright typeCheckingMode no longer strict: {cur_mode!r}")
    for key in ("reportMissingImports", "reportMissingModuleSource", "reportMissingTypeStubs"):
        cur, old = get(current, "tool", "pyright", key), get(base, "tool", "pyright", key)
        if old not in _STRICTNESS:
            continue  # no baseline in master -- new gate, nothing to ratchet against
        if cur not in _STRICTNESS:
            failures.append(
                f"pyright {key} was DELETED or set to an unrecognized value (was {old!r} in master)"
            )
        elif _STRICTNESS[cur] < _STRICTNESS[old]:
            failures.append(f"pyright {key} loosened: {old!r} -> {cur!r}")
    return failures


def check_importlinter(current: dict[str, Any], base: dict[str, Any]) -> list[str]:
    old_n = len(get(base, "tool", "importlinter", "contracts") or [])
    cur_n = len(get(current, "tool", "importlinter", "contracts") or [])
    if old_n == 0 or cur_n >= old_n:
        return []
    return [f"import-linter contract(s) removed: {old_n} -> {cur_n}"]


PYPROJECT_CHECKS = [
    check_coverage,
    check_ruff_select,
    check_mccabe,
    check_vulture,
    check_pyright,
    check_importlinter,
]


def run(current: dict[str, Any], base: dict[str, Any] | None) -> list[str]:
    if base is None:
        return []
    failures: list[str] = []
    for check in PYPROJECT_CHECKS:
        failures.extend(check(current, base))
    return failures


MIN_RE = re.compile(r"--min[= ](\d+(?:\.\d+)?)")


def check_mutation_floor(current_text: str, base_text: str | None) -> list[str]:
    if base_text is None:
        return []
    old_match = MIN_RE.search(base_text)
    if not old_match:
        return []  # no baseline in master -- new gate, nothing to ratchet against
    old = float(old_match.group(1))
    cur_match = MIN_RE.search(current_text)
    if not cur_match:
        return [f"mutation floor (--min) was DELETED (was {old} in master)"]
    cur = float(cur_match.group(1))
    if cur >= old:
        return []
    return [f"mutation floor lowered: {old} -> {cur}"]


def main() -> int:
    current = tomllib.loads(Path("pyproject.toml").read_text())

    base_pyproject_text = git_show(BASE_REF, "pyproject.toml")
    if base_pyproject_text is None:
        print(f"note: {BASE_REF}:pyproject.toml not found -- skipping pyproject-based gate checks")
        base = None
    else:
        base = tomllib.loads(base_pyproject_text)

    failures = run(current, base)

    nightly_path = Path(".github/workflows/nightly-mutation.yml")
    current_nightly = nightly_path.read_text() if nightly_path.exists() else ""
    base_nightly = git_show(BASE_REF, ".github/workflows/nightly-mutation.yml")
    if base_nightly is None:
        print(
            f"note: {BASE_REF}:.github/workflows/nightly-mutation.yml not found -- "
            "skipping mutation-floor check"
        )
    else:
        failures.extend(check_mutation_floor(current_nightly, base_nightly))

    if failures:
        print("GATE RATCHET FAILED -- gate(s) weakened relative to origin/master:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: no gate weakened relative to origin/master")
    return 0


if __name__ == "__main__":
    # Self-check: two fake config dicts, one weakened -> must fail.
    _base = {
        "tool": {
            "coverage": {"report": {"fail_under": 92}},
            "ruff": {"lint": {"select": ["E", "F"], "mccabe": {"max-complexity": 10}}},
            "vulture": {"min_confidence": 60},
            "pyright": {"typeCheckingMode": "strict", "reportMissingImports": "warning"},
            "importlinter": {"contracts": [{"name": "a"}, {"name": "b"}]},
        }
    }
    assert run(_base, _base) == []

    _weakened = {
        "tool": {
            "coverage": {"report": {"fail_under": 50}},  # lowered
            # rule dropped + complexity raised
            "ruff": {"lint": {"select": ["E"], "mccabe": {"max-complexity": 20}}},
            "vulture": {"min_confidence": 90},  # raised (weaker)
            "pyright": {"typeCheckingMode": "basic", "reportMissingImports": "none"},  # loosened
            "importlinter": {"contracts": [{"name": "a"}]},  # one removed
        }
    }
    _weakened_failures = run(_weakened, _base)
    assert len(_weakened_failures) >= 6, _weakened_failures
    assert check_mutation_floor(
        "run: python scripts/mutation_score.py --min 50",
        "run: python scripts/mutation_score.py --min 90",
    )

    # Deletion case: master HAS the gate, the PR removes the whole table/key --
    # must FAIL, not skip (this is the bug this fix-round closed).
    _deleted: dict[str, Any] = {"tool": {}}
    _deleted_failures = run(_deleted, _base)
    assert len(_deleted_failures) >= 3, _deleted_failures  # coverage, mccabe, vulture at least
    assert any("DELETED" in f for f in _deleted_failures), _deleted_failures
    assert check_mutation_floor(
        "run: python scripts/mutation_score.py",  # --min flag removed
        "run: python scripts/mutation_score.py --min 90",
    )

    sys.exit(main())
