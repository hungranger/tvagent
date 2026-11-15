"""Per-tool adapters: captured raw mutation-tool output -> kill-score percent (int 0-100)."""

from importlib import import_module

_MODULES = {
    "mutmut": "mutmut",
    "cargo-mutants": "cargo_mutants",
    "stryker": "stryker",
    "gremlins": "gremlins",
}


def score(tool: str, raw: str) -> int:
    if tool not in _MODULES:
        raise ValueError(f"unknown mutation tool {tool!r}; expected one of {sorted(_MODULES)}")
    return import_module(f"{__name__}.{_MODULES[tool]}").score(raw)


def pct(killed: int, survived: int) -> int:
    """Floored percent; no decided mutants -> 100 (matches mutation_score.score_percent)."""
    decided = killed + survived
    return 100 * killed // decided if decided else 100
