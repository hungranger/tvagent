"""Scan this PR's added lines (vs origin/master's merge-base) for newly
introduced lint/test/CI suppressions, and print them as GitHub Actions
annotations for the human reviewer to see inline on the PR.

Visibility only: this always exits 0. Its teeth come from CODEOWNERS +
required review on the gate-defining files it watches, not from blocking CI.

stdlib only: subprocess (git diff) + re. No network, no third-party diff lib.
"""

import re
import subprocess
import sys
from functools import cache
from pathlib import Path

# This script's own pattern literals, and the doc that names them in prose,
# would otherwise flag themselves as "new suppressions" -- not real ones.
SELF_EXCLUDE = {"scripts/suppression_diff.py", "docs/agent-safety.md"}

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"#\s*noqa\b"), "noqa"),
    (re.compile(r"#\s*type:\s*ignore"), "type: ignore"),
    (re.compile(r"#\s*pyright:\s*ignore"), "pyright: ignore"),
    (re.compile(r"#\s*nosemgrep"), "nosemgrep"),
    (re.compile(r"#\s*pragma:\s*no cover"), "pragma: no cover"),
    (re.compile(r"--no-verify"), "--no-verify"),
    (re.compile(r"\|\|\s*true"), "|| true"),
    (re.compile(r"continue-on-error"), "continue-on-error"),
]

AddedLine = tuple[str, int, str]  # (path, line_no, content)

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def git_merge_base(base_ref: str) -> str | None:
    proc = subprocess.run(
        ["git", "merge-base", base_ref, "HEAD"], capture_output=True, text=True, check=False
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def parse_added_lines(diff_text: str) -> list[AddedLine]:
    lines: list[AddedLine] = []
    path, new_lineno = "", 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:]
            path = "" if target == "/dev/null" else target.removeprefix("b/")
            continue
        hunk = HUNK_RE.match(raw)
        if hunk:
            new_lineno = int(hunk.group(1))
            continue
        if raw.startswith("+") and not raw.startswith("+++") and path:
            lines.append((path, new_lineno, raw[1:]))
            new_lineno += 1
    return lines


def added_lines(base: str) -> list[AddedLine]:
    proc = subprocess.run(
        ["git", "diff", "--no-color", "--unified=0", base, "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return parse_added_lines(proc.stdout)


def find_suppressions(lines: list[AddedLine]) -> list[tuple[str, int, str, str]]:
    found: list[tuple[str, int, str, str]] = []
    for path, lineno, content in lines:
        if path in SELF_EXCLUDE:
            continue
        for pattern, label in PATTERNS:
            if pattern.search(content):
                found.append((path, lineno, label, content.strip()))
    return found


@cache
def _sections(path: str) -> tuple[tuple[int, int, str], ...]:
    """[(start_line, end_line_exclusive, section_header)] for a TOML file."""
    try:
        text = Path(path).read_text()
    except OSError:
        return ()
    lines = text.splitlines()
    sections: list[tuple[int, int, str]] = []
    current, start = "", 1
    for i, line in enumerate(lines, start=1):
        if line.strip().startswith("["):
            if current:
                sections.append((start, i, current))
            current, start = line.strip(), i
    if current:
        sections.append((start, len(lines) + 1, current))
    return tuple(sections)


def find_allowlist_growth(lines: list[AddedLine]) -> list[tuple[str, int, str]]:
    """Flag growth of the vulture/gitleaks allowlists and ruff per-file-ignores."""
    flagged: list[tuple[str, int, str]] = []
    for path, lineno, content in lines:
        stripped = content.strip()
        if not stripped:
            continue
        if path == ".vulture_allowlist.py" and not stripped.startswith("#"):
            flagged.append((path, lineno, "vulture allowlist grew"))
        elif path == ".gitleaks.toml":
            flagged.append((path, lineno, "gitleaks config changed (check for allowlist growth)"))
        elif path == "pyproject.toml" and any(
            "per-file-ignores" in name for s, e, name in _sections(path) if s <= lineno < e
        ):
            flagged.append((path, lineno, "ruff per-file-ignores grew"))
    return flagged


def main() -> int:
    base = git_merge_base("origin/master") or git_merge_base("master")
    if base is None:
        print("note: no origin/master baseline found -- skipping suppression diff")
        return 0

    lines = added_lines(base)
    suppressions = find_suppressions(lines)
    growth = find_allowlist_growth(lines)

    for path, lineno, label, content in suppressions:
        print(f"::warning file={path},line={lineno}::New suppression: {label} -- {content[:120]}")
    for path, lineno, label in growth:
        print(f"::warning file={path},line={lineno}::{label}")

    total = len(suppressions) + len(growth)
    print(
        f"suppression-diff: {total} new finding(s) "
        f"({len(suppressions)} suppression(s), {len(growth)} allowlist growth) -- non-blocking"
    )
    return 0


if __name__ == "__main__":
    # Self-check: pure pattern-matching against synthetic lines, no git needed.
    assert find_suppressions([("src/x.py", 3, "x = 1  # noqa: E501")]) == [
        ("src/x.py", 3, "noqa", "x = 1  # noqa: E501")
    ]
    assert find_suppressions([("src/x.py", 3, "x = 1")]) == []
    assert find_suppressions([("scripts/suppression_diff.py", 1, "# noqa")]) == []  # self-excluded
    _ci_line = [(".github/workflows/ci.yml", 5, "run: foo || true")]
    assert find_suppressions(_ci_line)[0][2] == "|| true"
    assert find_allowlist_growth([(".vulture_allowlist.py", 4, "some_name  # real entry")]) == [
        (".vulture_allowlist.py", 4, "vulture allowlist grew")
    ]
    assert find_allowlist_growth([(".vulture_allowlist.py", 1, "# just a comment")]) == []
    sys.exit(main())
