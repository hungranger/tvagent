"""cargo-mutants: text summary line of the console run, e.g.

    120 mutants tested in 3m: 12 missed, 90 caught, 18 unviable

Unviable and timeout mutants are excluded; score = caught / (caught + missed).
"""

import re

from . import pct


def _n(label: str, raw: str) -> int:
    m = re.search(rf"(\d+) {label}", raw)
    if not m:
        raise ValueError(f"no {label!r} count in tool output")
    return int(m.group(1))


def score(raw: str) -> int:
    return pct(_n("caught", raw), _n("missed", raw))
