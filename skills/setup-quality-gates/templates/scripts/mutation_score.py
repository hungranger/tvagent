"""Gate CI on the mutmut mutation score.

Reads mutmut's CI/CD stats JSON (`mutmut export-cicd-stats`, written to
`mutants/mutmut-cicd-stats.json`) and fails if killed/(killed+survived) is
below --min. Mutants with no result yet (timeouts, no_tests, etc.) are
excluded from the ratio -- they aren't evidence either way.
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_STATS_FILE = Path("mutants/mutmut-cicd-stats.json")


def score_percent(stats: dict[str, int]) -> float:
    killed, survived = stats["killed"], stats["survived"]
    decided = killed + survived
    return 100.0 * killed / decided if decided else 100.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min", type=float, required=True, help="minimum score, in percent")
    parser.add_argument("--stats-file", type=Path, default=DEFAULT_STATS_FILE)
    args = parser.parse_args()

    stats = json.loads(args.stats_file.read_text())
    score = score_percent(stats)
    print(f"mutation score: {score:.2f}% (killed={stats['killed']} survived={stats['survived']})")
    if score < args.min:
        print(f"FAIL: below floor of {args.min}%")
        return 1
    print(f"OK: at or above floor of {args.min}%")
    return 0


if __name__ == "__main__":
    # Self-check: a fake results input must compute the ratio correctly.
    assert score_percent({"killed": 246, "survived": 85}) == 100.0 * 246 / 331
    assert score_percent({"killed": 10, "survived": 0}) == 100.0
    sys.exit(main())
