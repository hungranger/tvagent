import subprocess
import sys
from pathlib import Path

import pytest

NOT_FOUND = 2
SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.manifest import ManifestError, get, load  # noqa: E402


def _load(tmp_path: Path, text: str) -> dict:
    p = tmp_path / "quality-gates.toml"
    p.write_text(text)
    return load(p)


def _cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "gate_setup.manifest", *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONPATH": str(SKILL / "scripts")},
    )


def test_unknown_key_rejected(tmp_path: Path):
    with pytest.raises(ManifestError):
        _load(tmp_path, "[thresholds]\ncoverage_flor = 80\n")


def test_wrong_type_rejected(tmp_path: Path):
    with pytest.raises(ManifestError):
        _load(tmp_path, '[thresholds]\ncoverage_floor = "high"\n')


def test_illegal_strictness_rejected(tmp_path: Path):
    with pytest.raises(ManifestError):
        _load(tmp_path, '[thresholds]\ntype_strictness = "ultra"\n')


def test_illegal_language_rejected(tmp_path: Path):
    with pytest.raises(ManifestError):
        _load(tmp_path, '[meta]\nlanguage = "cobol"\n')


def test_get_scalar():
    assert get({"thresholds": {"coverage_floor": 92}}, "coverage_floor") == "92"


def test_get_set_newline_joined():
    assert get({"thresholds": {"lint_rules": ["E", "F"]}}, "lint_rules") == "E\nF"


def test_get_missing_exits_nonzero(tmp_path: Path):
    (tmp_path / "quality-gates.toml").write_text("[thresholds]\ncoverage_floor = 80\n")
    r = _cli(tmp_path, "get", "nope")
    assert r.returncode == NOT_FOUND and r.stderr
    ok = _cli(tmp_path, "get", "coverage_floor")
    assert ok.returncode == 0 and ok.stdout.strip() == "80"


def test_check_drift(tmp_path: Path):
    (tmp_path / "native.toml").write_text("[tool]\nfloor = 70\n")
    base = (
        '[thresholds]\ncoverage_floor = %d\n[drift]\n"native.toml#tool.floor" = "coverage_floor"\n'
    )
    (tmp_path / "quality-gates.toml").write_text(base % 70)
    assert _cli(tmp_path, "check-drift", "--profile", ".").returncode == 0
    (tmp_path / "quality-gates.toml").write_text(base % 80)
    assert _cli(tmp_path, "check-drift", "--profile", ".").returncode == 1


def test_unknown_top_level_table_rejected(tmp_path: Path):
    with pytest.raises(ManifestError):
        _load(tmp_path, "[threshold]\ncoverage_floor = 80\n")


def test_nonstring_language_rejected(tmp_path: Path):
    with pytest.raises(ManifestError):
        _load(tmp_path, '[meta]\nlanguage = ["x"]\n')


def test_missing_key_message_clear(tmp_path: Path):
    (tmp_path / "quality-gates.toml").write_text("[thresholds]\ncoverage_floor = 80\n")
    r = _cli(tmp_path, "get", "complexity_max")
    assert r.returncode == NOT_FOUND and "missing key: complexity_max" in r.stderr


def _drift(tmp_path: Path, manifest: str, **files: str) -> subprocess.CompletedProcess[str]:
    for name, body in files.items():
        (tmp_path / name.replace("_", ".", 1)).write_text(body)
    (tmp_path / "quality-gates.toml").write_text(manifest)
    return _cli(tmp_path, "check-drift", "--profile", ".")


def test_check_drift_detects_mismatch(tmp_path: Path):
    m = '[thresholds]\ncomplexity_max = 9\n[drift]\n"r.toml#a.b" = "complexity_max"\n'
    r = _drift(tmp_path, m, r_toml="[a]\nb = 10\n")
    assert r.returncode == 1 and "native=10" in r.stderr


def test_check_drift_json_native(tmp_path: Path):
    m = '[thresholds]\ncomplexity_max = 9\n[drift]\n"b.json#a.b" = "complexity_max"\n'
    assert _drift(tmp_path, m, b_json='{"a": {"b": 9}}').returncode == 0
    assert _drift(tmp_path, m, b_json='{"a": {"b": 8}}').returncode == 1


def test_check_drift_malformed_is_drift_not_crash(tmp_path: Path):
    m = '[thresholds]\ncomplexity_max = 9\n[drift]\n"r.toml#a.b.c" = "complexity_max"\n'
    r = _drift(tmp_path, m, r_toml="[a]\nb = 1\n")
    assert r.returncode == 1 and "Traceback" not in r.stderr
    assert _drift(tmp_path, "drift = 1\n").returncode == 1


def test_check_drift_missing_binding_fails(tmp_path: Path):
    prof = SKILL / "tests" / "fixtures" / "profile_fake"
    (tmp_path / "quality-gates.toml").write_text("[thresholds]\ncomplexity_max = 9\n")
    r = _cli(tmp_path, "check-drift", "--profile", ".", "--gates", str(prof))
    assert r.returncode == 1 and "complexity_max" in r.stderr


def test_check_drift_nonstring_binding_is_drift(tmp_path: Path):
    prof = SKILL / "tests" / "fixtures" / "profile_fake"
    (tmp_path / "quality-gates.toml").write_text(
        '[thresholds]\ncomplexity_max = 9\n[drift]\n"x#y" = ["a"]\n'
    )
    r = _cli(tmp_path, "check-drift", "--profile", ".", "--gates", str(prof))
    assert r.returncode == 1 and "Traceback" not in r.stderr
