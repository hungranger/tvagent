"""Stryker JSON report (mutation-testing-elements schema).

Counts files.*.mutants[].status:
Killed/Timeout are kills, Survived/NoCoverage are not, everything else is excluded.
"""

import json

from . import pct

_KILLED = {"Killed", "Timeout"}
_ALIVE = {"Survived", "NoCoverage"}


def score(raw: str) -> int:
    r = json.loads(raw)
    st = [m["status"] for f in r.get("files", {}).values() for m in f.get("mutants", [])]
    if not st:
        raise ValueError("no mutants in Stryker report")
    return pct(sum(s in _KILLED for s in st), sum(s in _ALIVE for s in st))
