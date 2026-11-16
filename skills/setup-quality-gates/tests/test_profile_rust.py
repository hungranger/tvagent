"""Rust profile: rust-native tools first, llvm-cov (not tarpaulin), complexity drift-bound."""

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.manifest import check_drift, load_profile  # noqa: E402
from gate_setup.render import render  # noqa: E402

RS = SKILL / "profiles" / "rust"
M = {
    "meta": {"language": "rust"},
    "thresholds": {
        "coverage_floor": 80,
        "complexity_max": 15,
        "mutation_floor": 70,
        "type_strictness": "deny-warnings",
    },
    "protected": {"paths": [".github/**", "clippy.toml", "quality-gates.toml"]},
}


def test_rust_profile_valid():
    out = render(RS, M)
    assert tomllib.loads(out["clippy.toml"])["cognitive-complexity-threshold"] == 15
    assert "--fail-under-lines 80" in out["ci-steps.yml"]
    assert not any("{{" in t for t in out.values())


def test_rust_coverage_is_llvm_cov():
    cov = load_profile(RS)["gates"]["coverage"]
    assert cov["tools"] == ["cargo-llvm-cov"]
    assert "tarpaulin" not in str(load_profile(RS))


def test_rust_complexity_is_drift():
    p = load_profile(RS)
    assert p["gates"]["complexity"]["threshold_mechanism"] == "config"
    assert "complexity_max" in p["drift"].values()


def test_rust_rust_native_flags():
    g = load_profile(RS)["gates"]
    for name in ("lint", "format", "coverage", "mutation"):
        assert g[name]["impl_lang"] == "rust", name
    assert g["lint"]["tools"][0] == "clippy"
    assert g["format"]["tools"][0] == "rustfmt"
    assert g["mutation"]["tools"] == ["cargo-mutants"] and g["mutation"]["blocking"]


def test_rust_drift_bites(tmp_path: Path):
    manifest = tomllib.loads(render(RS, M)["quality-gates.toml"])
    (tmp_path / "clippy.toml").write_text("cognitive-complexity-threshold = 99\n")
    assert any("complexity_max" in b for b in check_drift(manifest, tmp_path))


@pytest.mark.skipif(not shutil.which("cargo"), reason="cargo not installed")
def test_rust_e2e_green(tmp_path: Path):
    proj = tmp_path / "p"
    shutil.copytree(SKILL / "tests/fixtures/rust_min", proj)
    for rel, text in render(RS, M).items():
        (proj / rel).write_text(text)
    for cmd in (
        ["cargo", "fmt", "--check"],
        ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"],
        ["cargo", "test"],
    ):
        r = subprocess.run(cmd, cwd=proj, capture_output=True, text=True)
        assert r.returncode == 0, (cmd, r.stdout, r.stderr)
