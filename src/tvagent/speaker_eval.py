"""Pure scoring logic for the speaker-ID evaluation harness (no IO, no model).

Kept separate from scripts/eval_speaker.py so this logic is unit-testable
without recording audio or loading the ECAPA model.
"""

from collections import Counter
from dataclasses import dataclass, field

from tvagent.core.models import GUEST

_STRANGER = "stranger"


@dataclass(frozen=True)
class EvalCase:
    """One test clip's outcome: the true label and what identify() returned."""

    true: str
    predicted: str


@dataclass
class EvalReport:
    # None means "no clips of that kind in the run" (undefined rate, not 0%).
    correct_rate: float | None
    stranger_reject_rate: float | None
    confusion: dict[tuple[str, str], int] = field(default_factory=lambda: {})


def score_cases(cases: list[EvalCase]) -> EvalReport:
    """Correct-ID rate over enrolled-person clips, GUEST-reject rate over stranger
    clips, and a confusion tally of (true, predicted) -> count for every mismatch.
    """
    enrolled = [c for c in cases if c.true != _STRANGER]
    strangers = [c for c in cases if c.true == _STRANGER]
    correct_rate = (
        sum(c.predicted == c.true for c in enrolled) / len(enrolled) if enrolled else None
    )
    stranger_reject_rate = (
        sum(c.predicted == GUEST for c in strangers) / len(strangers) if strangers else None
    )
    confusion = Counter((c.true, c.predicted) for c in cases if c.predicted != c.true)
    return EvalReport(correct_rate, stranger_reject_rate, dict(confusion))


def best_by_grid(grid: list[tuple[float, float, float, float]]) -> tuple[float, float]:
    """Pick (threshold, margin) from a (threshold, margin, correct_rate,
    stranger_reject_rate) grid, maximizing min(correct_rate, stranger_reject_rate)
    -- a balanced objective that won't reward acing one metric by tanking the
    other. Ties keep the first entry in grid order.
    """
    best_threshold, best_margin, best_correct, best_reject = grid[0]
    best_score = min(best_correct, best_reject)
    for threshold, margin, correct, reject in grid[1:]:
        score = min(correct, reject)
        if score > best_score:
            best_score, best_threshold, best_margin = score, threshold, margin
    return best_threshold, best_margin
