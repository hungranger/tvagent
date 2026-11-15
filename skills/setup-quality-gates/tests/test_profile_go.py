"""Go profile: golangci-lint/gofmt/staticcheck, gremlins non-blocking, coverage via cover -func total."""

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

GO = SKILL / "profiles" / "go"
M = {
    "meta": {"language": "go"},
    "thresholds": {"coverage_floor": 80, "complexity_max": 15},
    "protected": {"paths": [".github/**", ".golangci.toml", "quality-gates.toml"]},
}


def test_go_profile_valid():
    out = render(GO, M)
    cfg = tomllib.loads(out[".golangci.toml"])
    assert cfg["linters"]["settings"]["gocyclo"]["min-complexity"] == 15
    assert not any("{{" in t for t in out.values())
    g = load_profile(GO)["gates"]
    assert g["lint"]["tools"][0] == "golangci-lint" and g["format"]["tools"] == ["gofmt"]
    assert "govulncheck" in g["audit"]["tools"]


def test_go_mutation_non_blocking():
    m = load_profile(GO)["gates"]["mutation"]
    assert m["tools"] == ["gremlins"] and m["blocking"] is False


def test_go_coverage_recipe():
    p = load_profile(GO)
    assert "go tool cover -func" in p["measure"]["coverage"]
    assert "total" in p["measure"]["coverage"]
    assert "go tool cover -func" in render(GO, M)["ci-steps.yml"]


def test_go_drift_bites(tmp_path: Path):
    manifest = tomllib.loads(render(GO, M)["quality-gates.toml"])
    (tmp_path / ".golangci.toml").write_text('[linters.settings.gocyclo]\nmin-complexity = 99\n')
    assert any("complexity_max" in b for b in check_drift(manifest, tmp_path))


@pytest.mark.skipif(not shutil.which("go"), reason="go not installed")
def test_go_e2e_green(tmp_path: Path):
    proj = tmp_path / "p"
    shutil.copytree(SKILL / "tests/fixtures/go_min", proj)
    for rel, text in render(GO, M).items():
        (proj / rel).write_text(text)
    for cmd in (["gofmt", "-l", "."], ["go", "vet", "./..."], ["go", "test", "-coverprofile=c.out", "./..."],
                ["go", "tool", "cover", "-func=c.out"]):
        r = subprocess.run(cmd, cwd=proj, capture_output=True, text=True)
        assert r.returncode == 0 and (cmd[0] != "gofmt" or not r.stdout), (cmd, r.stdout, r.stderr)
