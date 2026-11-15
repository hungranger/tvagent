import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from gate_setup.mutation_adapters import score  # noqa: E402

MUTMUT = '{"killed": 246, "survived": 85, "total": 400, "no_tests": 3}'
STRYKER_SCORE = '{"schemaVersion": "1", "mutationScore": 82.5, "files": {}}'
STRYKER_FILES = (
    '{"schemaVersion": "1", "files": {"src/a.ts": {"mutants": ['
    '{"id": "1", "status": "Killed"}, {"id": "2", "status": "Timeout"},'
    '{"id": "3", "status": "Survived"}, {"id": "4", "status": "NoCoverage"},'
    '{"id": "5", "status": "Ignored"}]}}}'
)
CARGO = (
    "Found 120 mutants to test\n"
    "ok       Unmutated baseline in 2.1s build + 0.4s test\n"
    "120 mutants tested in 3m: 12 missed, 90 caught, 18 unviable\n"
)
GREMLINS = (
    "Gremlins 0.5.0\n"
    "Mutation testing completed in 5 seconds 10 milliseconds\n"
    "Killed: 30, Lived: 10, Not covered: 4\n"
    "Timed out: 2, Not viable: 1, Skipped: 0\n"
    "Test efficacy: 75.00%\n"
    "Mutator coverage: 90.91%\n"
)


def test_mutmut_adapter_parses() -> None:
    assert score("mutmut", MUTMUT) == 100 * 246 // 331


def test_stryker_adapter_parses() -> None:
    assert score("stryker", STRYKER_SCORE) == 82
    # Killed+Timeout detected; Survived+NoCoverage not; Ignored excluded -> 2/4
    assert score("stryker", STRYKER_FILES) == 50


def test_cargo_mutants_adapter_parses() -> None:
    assert score("cargo-mutants", CARGO) == 100 * 90 // 102


def test_gremlins_adapter_parses() -> None:
    assert score("gremlins", GREMLINS) == 75
