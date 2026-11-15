"""gremlins (Go): run summary text, e.g. `Killed: 30, Lived: 10, Not covered: 4`.

Score = killed / (killed + lived); timed-out / not-viable / not-covered excluded.
"""

import re

from . import pct


def _n(label: str, raw: str) -> int:
    m = re.search(rf"{label}:\s*(\d+)", raw)
    return int(m.group(1)) if m else 0


def score(raw: str) -> int:
    return pct(_n("Killed", raw), _n("Lived", raw))
