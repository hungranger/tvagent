"""quality-gates.toml: validator, direction registry, `get` / `check-drift` CLI."""

from __future__ import annotations

import argparse
import json
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


def load_profile(profile_dir: Path) -> dict[str, Any]:
    try:
        with (profile_dir / "profile.toml").open("rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ManifestError(f"{profile_dir}/profile.toml: {e}") from e


def gates_of(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    g = profile.get("gates", {})
    return g if isinstance(g, dict) else {}  # pyright: ignore[reportUnknownVariableType]


def config_only_keys(profile: dict[str, Any]) -> list[str]:
    """Threshold keys whose only enforcement is a native config file."""
    return sorted(
        g["threshold_key"]
        for g in gates_of(profile).values()
        if g.get("threshold_mechanism") == "config" and g.get("threshold_key")
    )


def _native(spec: str, base: Path) -> Any:
    """`<native_path>#<dotted.key>` -> value from a TOML or JSON file (by extension)."""
    rel, _, dotted = spec.partition("#")
    path = base / rel
    with path.open("rb") as f:
        v: Any = json.load(f) if path.suffix == ".json" else tomllib.load(f)
    for part in dotted.split("."):
        if not isinstance(v, dict) or part not in v:
            raise KeyError(part)
        v = v[part]  # pyright: ignore[reportUnknownVariableType]
    return v


def check_drift(manifest: dict[str, Any], base: Path, gates: Path | None = None) -> list[str]:
    """Native-vs-manifest mismatches; `gates` (profile dir) adds unbound config-only keys."""
    out: list[str] = []
    try:
        drift = _table(manifest, "drift")
    except ManifestError as e:
        return [str(e)]
    for spec, mkey in drift.items():
        try:
            nat = _native(spec, base)
            want = _lookup(manifest, mkey)
        except (OSError, KeyError, ValueError, ManifestError) as e:  # ValueError: bad TOML/JSON
            out.append(f"{spec}: unreadable ({e!r})")
            continue
        if nat != want:
            out.append(f"{spec}: native={nat!r} manifest[{mkey}]={want!r}")
    if gates is not None:
        bound = set(drift.values())
        out += [
            f"{k}: config-only threshold has no [drift] binding"
            for k in config_only_keys(load_profile(gates))
            if k in _table(manifest, "thresholds") and k not in bound
        ]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gate_setup.manifest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get")
    g.add_argument("key")
    d = sub.add_parser("check-drift")
    d.add_argument("--profile", type=Path, default=Path())
    d.add_argument("--gates", type=Path, default=None)
    for p in (g, d):
        p.add_argument("--file", type=Path, default=Path("quality-gates.toml"))
    a = ap.parse_args(argv)
    try:
        m = load(a.file)
        if a.cmd == "get":
            print(get(m, a.key))
            return 0
        bad = check_drift(m, a.profile, a.gates)
    except (ManifestError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for line in bad:
        print(line, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
