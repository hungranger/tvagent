import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "templates" / "scripts" / "suppression_diff.py"
_spec = importlib.util.spec_from_file_location("suppression_diff", SCRIPT)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


@pytest.mark.parametrize(
    ("path", "content", "label"),
    [
        ("src/lib.rs", "#[allow(dead_code)]", "#[allow("),
        ("src/lib.rs", "#![allow(clippy::all)]", "#![allow("),
        ("cmd/main.go", "x := 1 //nolint:errcheck", "//nolint"),
        ("src/app.ts", "// eslint-disable", "// eslint-disable"),
        ("src/app.ts", "// eslint-disable-next-line", "eslint-disable-next-line"),
        ("src/app.ts", "/* eslint-disable */", "/* eslint-disable */"),
        ("src/app.ts", "// @ts-ignore", "// @ts-ignore"),
        ("src/app.ts", "// @ts-expect-error", "// @ts-expect-error"),
        ("src/app.ts", "// @ts-nocheck", "// @ts-nocheck"),
        ("src/app.ts", "// biome-ignore lint/style: x", "// biome-ignore"),
        ("src/x.py", "x = 1  # noqa: E501", "noqa"),
        ("src/x.py", "x: int = y  # type: ignore", "type: ignore"),
        ("src/x.py", "x = y  # pyright: ignore", "pyright: ignore"),
        ("src/x.py", "if x:  # pragma: no cover", "pragma: no cover"),
    ],
)
def test_token_flagged_in_added_line(path: str, content: str, label: str) -> None:
    found = mod.find_suppressions([(path, 1, content)])
    assert [label_found for *_, label_found, _ in found] == [label]


def test_token_flagged_regardless_of_extension() -> None:
    found = mod.find_suppressions([("docs/notes.md", 2, "// @ts-ignore")])
    assert len(found) == 1


def test_plain_line_not_flagged() -> None:
    assert mod.find_suppressions([("src/lib.rs", 1, "let x = 1;")]) == []
