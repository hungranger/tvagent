"""Stryker JSON report (mutation-testing-elements schema).

Uses top-level `mutationScore` if present; otherwise counts files.*.mutants[].status:
Killed/Timeout are kills, Survived/NoCoverage are not, everything else is excluded.
"""

import json

from . import pct

_KILLED = {"Killed", "Timeout"}
_ALIVE = {"Survived", "NoCoverage"}


def score(raw: str) -> int:
    r = json.loads(raw)
    if "mutationScore" in r:
        return int(r["mutationScore"])
    st = [m["status"] for f in r.get("files", {}).values() for m in f.get("mutants", [])]
    return pct(sum(s in _KILLED for s in st), sum(s in _ALIVE for s in st))
