"""quality-gates.toml: validator, direction registry, `get` / `check-drift` CLI."""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Any

KEY_DIRECTIONS: dict[str, str] = {
    "coverage_floor": "scalar-up",
    "complexity_max": "scalar-down",
    "mutation_floor": "scalar-up",
    "vulture_confidence": "scalar-down",
    "arch_contracts_min": "scalar-up",
    "type_strictness": "enum",
    "lint_rules": "set",
    "protected.paths": "set",
}
STRICTNESS_ORDER = ["basic", "standard", "deny-warnings", "strict"]
LANGUAGES = {"python", "rust", "go", "react-ts"}

_TYPES: dict[str, type] = {
    "coverage_floor": int,
    "complexity_max": int,
    "mutation_floor": int,
    "vulture_confidence": int,
    "arch_contracts_min": int,
    "type_strictness": str,
    "lint_rules": list,
    "protected.paths": list,
}


_TOP_LEVEL = {"meta", "thresholds", "protected", "drift"}


class ManifestError(Exception):
    pass


def _table(m: dict[str, Any], name: str) -> dict[str, Any]:
    t = m.get(name, {})
    if not isinstance(t, dict):
        raise ManifestError(f"[{name}] must be a table")
    return t  # pyright: ignore[reportUnknownVariableType]


def _check(key: str, val: Any) -> None:
    want = _TYPES[key]
    # bool is an int subclass; reject it explicitly
    if not isinstance(val, want) or isinstance(val, bool):
        raise ManifestError(f"{key}: expected {want.__name__}, got {type(val).__name__}")
    if want is list and not all(isinstance(x, str) for x in val):
        raise ManifestError(f"{key}: list items must be strings")
    if key == "type_strictness" and val not in STRICTNESS_ORDER:
        raise ManifestError(f"type_strictness: {val!r} not in {STRICTNESS_ORDER}")


def validate(m: dict[str, Any]) -> dict[str, Any]:
    extra = set(m) - _TOP_LEVEL
    if extra:
        raise ManifestError(f"unknown top-level table: {sorted(extra)}")
    lang = _table(m, "meta").get("language")
    if lang is not None and not (isinstance(lang, str) and lang in LANGUAGES):
        raise ManifestError(f"meta.language: {lang!r} not in {sorted(LANGUAGES)}")
    for k, v in _table(m, "thresholds").items():
        if k not in _TYPES or k == "protected.paths":
            raise ManifestError(f"unknown threshold key: {k}")
        _check(k, v)
    for k, v in _table(m, "protected").items():
        if k != "paths":
            raise ManifestError(f"unknown protected key: {k}")
        _check("protected.paths", v)
    return m


def load(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            return validate(tomllib.load(f))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ManifestError(f"{path}: {e}") from e


def _lookup(m: dict[str, Any], key: str) -> Any:
    table, _, name = key.rpartition(".")
    if key not in KEY_DIRECTIONS or name not in _table(m, table or "thresholds"):
        raise ManifestError(f"missing key: {key}")
    return _table(m, table or "thresholds")[name]


def get(manifest: dict[str, Any], key: str) -> str:
    v = _lookup(manifest, key)
    return "\n".join(v) if isinstance(v, list) else str(v)  # pyright: ignore[reportUnknownArgumentType]


def _native(spec: str, base: Path) -> Any:
    """`<native_path>#<dotted.key>` -> value from a TOML file."""
    rel, _, dotted = spec.partition("#")
    with (base / rel).open("rb") as f:
        v: Any = tomllib.load(f)
    for part in dotted.split("."):
        v = v[part]
    return v


def check_drift(manifest: dict[str, Any], base: Path) -> list[str]:
    out: list[str] = []
    for spec, mkey in _table(manifest, "drift").items():
        try:
            nat = _native(spec, base)
        except (OSError, KeyError, tomllib.TOMLDecodeError) as e:
            out.append(f"{spec}: unreadable ({e!r})")
            continue
        want = _lookup(manifest, mkey)
        if nat != want:
            out.append(f"{spec}: native={nat!r} manifest[{mkey}]={want!r}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gate_setup.manifest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get")
    g.add_argument("key")
    d = sub.add_parser("check-drift")
    d.add_argument("--profile", type=Path, default=Path())
    for p in (g, d):
        p.add_argument("--file", type=Path, default=Path("quality-gates.toml"))
    a = ap.parse_args(argv)
    try:
        m = load(a.file)
        if a.cmd == "get":
            print(get(m, a.key))
            return 0
        bad = check_drift(m, a.profile)
    except (ManifestError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for line in bad:
        print(line, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
