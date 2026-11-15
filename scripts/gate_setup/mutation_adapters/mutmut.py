"""mutmut: `mutmut export-cicd-stats` JSON, e.g. {"killed": 246, "survived": 85, ...}."""

import json

from . import pct


def score(raw: str) -> int:
    s = json.loads(raw)
    return pct(s["killed"], s["survived"])
