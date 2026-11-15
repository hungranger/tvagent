import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.render import render  # noqa: E402

FAKE = SKILL / "tests" / "fixtures" / "profile_fake"
M = {"thresholds": {"coverage_floor": 87, "complexity_max": 7}}


def test_render_emits_flag_from_manifest():
    assert "--cov-fail-under=87" in render(FAKE, M)["ci.yml"]


def test_render_emits_native_config():
    assert "max-complexity = 7" in render(FAKE, M)["ruff.toml"]


def test_render_no_residual_tokens():
    assert all("{{" not in v for v in render(FAKE, M).values())


def test_render_deterministic():
    assert list(render(FAKE, M).items()) == list(render(FAKE, M).items())
