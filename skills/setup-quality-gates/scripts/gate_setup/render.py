"""Deterministic render of native config / hooks / CI from a profile + manifest."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from gate_setup.manifest import KEY_DIRECTIONS, ManifestError, gates_of, get, load, load_profile

_TOKEN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def _sub(text: str, manifest: dict[str, Any]) -> str:
    def one(m: re.Match[str]) -> str:
        if m.group(1) not in KEY_DIRECTIONS:
            raise ManifestError(f"unknown token: {m.group(0)}")
        return get(manifest, m.group(1))

    return _TOKEN.sub(one, text)


def render(profile_dir: Path, manifest: dict[str, Any]) -> dict[str, str]:
    profile = load_profile(profile_dir)
    for g in gates_of(profile).values():  # fail early if a gated key has no value
        if g.get("threshold_mechanism") in ("flag", "config"):
            get(manifest, g["threshold_key"])
    root = profile_dir / "templates"
    out = {
        p.relative_to(root).as_posix().removesuffix(".tmpl"): _sub(p.read_text(), manifest)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    for rel, text in out.items():
        if "{{" in text:
            raise ManifestError(f"{rel}: residual '{{{{' after render")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gate_setup.render")
    ap.add_argument("profile_dir", type=Path)
    ap.add_argument("--manifest", type=Path, default=Path("quality-gates.toml"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        files = render(a.profile_dir, load(a.manifest))
    except ManifestError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for rel, text in files.items():
        dest = a.out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
