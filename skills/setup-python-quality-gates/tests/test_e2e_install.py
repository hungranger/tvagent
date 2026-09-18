import sys, shutil, subprocess, textwrap
from pathlib import Path
SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.detect import detect  # noqa: E402

def test_greenfield_l1_is_green_day_one(tmp_path):
    # arrange: a real tiny package with one clean, typed, tested function
    pkg = tmp_path / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "core.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_core.py").write_text(
        "from demo.core import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [project]
        name = "demo"
        version = "0"
        requires-python = ">=3.11"
        [tool.pytest.ini_options]
        pythonpath = ["src"]
    """))
    # act: detection should see greenfield + no existing gates
    d = detect(tmp_path)
    assert d["existing"]["ruff"] is False
    # apply the strict greenfield gate block (simulates Phase 4 render for a clean repo)
    gates = (SKILL / "templates/pyproject.gates.toml").read_text()
    rendered = (gates.replace("{{COVERAGE_FLOOR}}", "92").replace("{{MAX_COMPLEXITY}}", "10")
                .replace("{{VULTURE_MIN_CONFIDENCE}}", "60").replace("{{PYRIGHT_MODE}}", "strict")
                .replace("{{MUTATION_FLOOR}}", "0").replace('{{SRC_DIRS}}', '["src/demo"]'))
    with (tmp_path / "pyproject.toml").open("a") as f:
        f.write("\n" + rendered)
    # assert: the core gates pass on day one for clean code
    ruff = subprocess.run(["ruff", "check", "."], cwd=tmp_path, capture_output=True, text=True)
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    cov = subprocess.run(["pytest", "--cov=demo", "--cov-report=", "--cov-fail-under=92"],
                         cwd=tmp_path, capture_output=True, text=True)
    assert cov.returncode == 0, cov.stdout + cov.stderr
