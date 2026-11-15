"""react-ts profile: Biome replaces prettier+eslint, tsc strict, vitest lines coverage."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.manifest import check_drift, load_profile  # noqa: E402
from gate_setup.render import render  # noqa: E402

TS = SKILL / "profiles" / "react-ts"
M = {
    "meta": {"language": "react-ts"},
    "thresholds": {"coverage_floor": 80, "complexity_max": 15, "mutation_floor": 60, "type_strictness": "strict"},
    "protected": {"paths": [".github/**", "biome.json", "quality-gates.toml"]},
}


def test_ts_uses_biome_not_prettier_eslint():
    p = load_profile(TS)
    for name in ("lint", "format"):
        assert p["gates"][name]["tools"] == ["biome"], name
        assert p["gates"][name]["impl_lang"] == "rust", name
    assert "prettier" not in str(p) and "eslint" not in str(p)
    biome = json.loads(render(TS, M)["biome.json"])
    assert biome["linter"]["rules"]["complexity"]["noExcessiveCognitiveComplexity"]["options"][
        "maxAllowedComplexity"
    ] == 15


def test_ts_types_tsc_strict():
    assert load_profile(TS)["gates"]["types"]["tools"] == ["tsc"]
    assert json.loads(render(TS, M)["tsconfig.json"])["compilerOptions"]["strict"] is True


def test_ts_coverage_maps_vitest_lines():
    g = load_profile(TS)["gates"]["coverage"]
    assert g["tools"] == ["vitest"] and g["threshold_key"] == "coverage_floor"
    assert "--coverage.thresholds.lines=80" in render(TS, M)["ci-steps.yml"]


def test_ts_drift_bites(tmp_path: Path):
    import tomllib

    manifest = tomllib.loads(render(TS, M)["quality-gates.toml"])
    (tmp_path / "biome.json").write_text(
        '{"linter":{"rules":{"complexity":{"noExcessiveCognitiveComplexity":'
        '{"options":{"maxAllowedComplexity":99}}}}}}'
    )
    assert any("complexity_max" in b for b in check_drift(manifest, tmp_path))


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_ts_e2e_green(tmp_path: Path):
    proj = tmp_path / "p"
    shutil.copytree(SKILL / "tests/fixtures/ts_min", proj)
    for rel, text in render(TS, M).items():
        (proj / rel).write_text(text)
    assert json.loads((proj / "biome.json").read_text())  # rendered config is valid JSON
    r = subprocess.run(["node", "--test"], cwd=proj, capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout, r.stderr)
