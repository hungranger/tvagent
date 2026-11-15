"""Python profile: renders tvagent's gate blocks, rust-native lint first, drift bites."""

import sys
import tomllib
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.manifest import check_drift, load_profile  # noqa: E402
from gate_setup.render import render  # noqa: E402

PY = SKILL / "profiles" / "python"

# tvagent's own current gate values (the dogfood baseline).
TVAGENT_M = {
    "meta": {"language": "python"},
    "thresholds": {
        "coverage_floor": 92,
        "complexity_max": 10,
        "mutation_floor": 90,
        "vulture_confidence": 60,
        "arch_contracts_min": 3,
        "type_strictness": "strict",
        "lint_rules": ["E", "F", "I", "UP", "B", "SIM", "PL", "RUF", "N", "C4", "C901", "PTH"],
    },
    "protected": {"paths": [".github/**", "pyproject.toml", "quality-gates.toml"]},
}


def test_python_profile_renders():
    out = render(PY, TVAGENT_M)
    gates = out["pyproject.gates.toml"]
    assert "fail_under = 92" in gates
    assert "max-complexity = 10" in gates
    assert "min_confidence = 60" in gates
    assert 'typeCheckingMode = "strict"' in gates


def test_python_rust_native_first():
    lint = load_profile(PY)["gates"]["lint"]
    assert lint["tools"][0] == "ruff"
    assert lint["impl_lang"] == "rust"


def test_drift_python(tmp_path: Path):
    # Manifest with the profile's drift bindings, via render's quality-gates.toml.
    manifest = tomllib.loads(render(PY, TVAGENT_M)["quality-gates.toml"])
    # A pyproject whose max-complexity is weakened (20) while the manifest says 10.
    (tmp_path / "pyproject.toml").write_text(
        "[tool.coverage.report]\nfail_under = 92\n"
        "[tool.ruff.lint]\nselect = "
        '["E", "F", "I", "UP", "B", "SIM", "PL", "RUF", "N", "C4", "C901", "PTH"]\n'
        "[tool.ruff.lint.mccabe]\nmax-complexity = 20\n"
        '[tool.pyright]\ntypeCheckingMode = "strict"\n'
        "[tool.vulture]\nmin_confidence = 60\n"
    )
    bad = check_drift(manifest, tmp_path)
    assert any("complexity_max" in b for b in bad), bad
