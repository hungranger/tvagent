#!/usr/bin/env python3
"""Deterministic PreToolUse guard hook: force a human "ask" on protected files.

Reads a Claude Code PreToolUse hook payload (JSON) from stdin. When the coding
agent tries to edit a gate/config file that governs the quality gates, this
emits a ``permissionDecision: "ask"`` so the harness routes it to a human —
no LLM in the loop.

Fail-open is deliberate: on ANY parse/logic error we exit 0 with no output so a
bug here never bricks the session. This is acceptable because the server-side
ratchet + branch ruleset is the real enforcement boundary; this hook is
actor-side prevention (a nudge, not the gate).

The Bash-command matching is best-effort/heuristic (substring + write-verb
regex). It is not a shell parser and can be evaded; again, the server-side gate
is the real boundary.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import cast

# Exact basenames that are protected regardless of directory (so the guard
# works whatever the cwd or how deep the path is).
PROTECTED_BASENAMES: set[str] = {
    "pyproject.toml",
    ".pre-commit-config.yaml",
    "CODEOWNERS",
    ".gitleaks.toml",
    ".vulture_allowlist.py",
    "uv.lock",
    # rust
    "Cargo.toml",
    "Cargo.lock",
    "clippy.toml",
    # go
    "go.mod",
    "go.sum",
    # react-ts (package.json is root-only, see ROOT_ONLY)
    "tsconfig.json",
    "biome.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    # the manifest itself: editing it is how thresholds get weakened
    "quality-gates.toml",
    "gate_ratchet.py",
    "suppression_diff.py",
    "mutation_score.py",
    "guard_protected_paths.py",  # SELF-GUARD
}

# Path-scoped protections: matched by path suffix, NOT bare basename, so a
# random settings.json elsewhere in the tree is not swept in.
PROTECTED_SUFFIXES: tuple[tuple[str, ...], ...] = (
    (".claude", "settings.json"),  # SELF-GUARD of the hook config
    (".claude", "settings.local.json"),
)

# Protected only at the repo root (package.json churn is high; nested ones are not gates).
ROOT_ONLY: frozenset[str] = frozenset({"package.json"})

# Any path containing this contiguous component run (.github: workflows, CODEOWNERS, ...;
# scripts/gate_setup: the spine package -- editing manifest.py neuters the ratchet registry).
PROTECTED_DIRS: tuple[tuple[str, ...], ...] = ((".github",), ("scripts", "gate_setup"))

# Repo manifest: its [protected].paths are unioned in (never replace the defaults).
MANIFEST_FILE = Path("quality-gates.toml")

# Optional repo-local extension: a JSON list of extra protected paths/names.
OVERRIDE_FILE = Path(".claude/protected-paths.json")

# Shell write indicators. Presence of one of these AND a protected token in a
# Bash command triggers an ask; a read-only command (cat/grep/...) does not.
_WRITE_INDICATORS = re.compile(
    r"(>>?|\btee\b|sed\s+-i\b|sed\s+--in-place\b|\btruncate\b|\bdd\b|\bmv\b"
    r"|\bcp\b|\brm\b|python[0-9.]*\s+-c\b|\bapplypatch\b|\bpatch\b)"
)

# Category B: gate-bypass / merge / protection-mutating commands. Evaluated for
# ANY Bash command independently of write indicators and protected files —
# these ask because at 0 required approvals the agent must still route a merge
# or a protection change through the human. Heuristic, not a shell parser.
_GH_PR_MERGE = re.compile(r"\bgh\s+pr\s+merge\b")
_GH_API = re.compile(r"\bgh\s+api\b")
_GH_API_PROTECT = re.compile(r"\b(merge|rulesets|branches/[^\s]*/protection)\b")
_GIT_PUSH = re.compile(r"\bgit\s+push\b")
# master/main as a ref token (space/colon-delimited), so "feat/no-master-x" is
# NOT swept in — a hyphen is a \b boundary, so \bmaster\b alone would false-fire.
_PUSH_PROTECTED_REF = re.compile(r"(?:^|[\s:])(?:master|main)(?:\s|$)")


def _extra_basenames() -> set[str]:
    """Merge in .claude/protected-paths.json (a JSON list) if present.

    Any problem -> empty set: a bad override must degrade to "defaults still apply".
    """
    try:
        if not OVERRIDE_FILE.exists():
            return set()
        raw: object = json.loads(OVERRIDE_FILE.read_text())
        if not isinstance(raw, list):
            return set()
        return {PurePosixPath(str(entry)).name for entry in cast("list[object]", raw)}
    except Exception:
        return set()


def _manifest_patterns() -> list[str]:
    """[protected].paths from quality-gates.toml; any problem -> [] (defaults still apply)."""
    try:
        data: object = tomllib.loads(MANIFEST_FILE.read_text())
        prot: object = cast("dict[str, object]", data).get("protected")
        paths: object = cast("dict[str, object]", prot).get("paths")
        return [p for p in cast("list[object]", paths) if isinstance(p, str)]
    except Exception:
        return []


def _has_run(parts: tuple[str, ...], run: tuple[str, ...]) -> bool:
    n = len(run)
    return any(parts[i : i + n] == run for i in range(len(parts) - n + 1))


def _matches(rel: PurePosixPath, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return _has_run(rel.parts[:-1], PurePosixPath(pattern[:-3]).parts)
    return fnmatch.fnmatchcase(rel.as_posix(), pattern) or (
        "/" not in pattern and rel.name == pattern
    )


def _rel_to_repo(p: Path) -> PurePosixPath:
    try:
        return PurePosixPath(p.relative_to(Path.cwd().resolve()).as_posix())
    except ValueError:
        return PurePosixPath(p.as_posix())  # outside repo: absolute (name/dir checks still apply)


def _candidates(file_path: str) -> list[PurePosixPath]:
    """Lexical (`..` collapsed, symlinks NOT followed) and resolved paths; protected if either hits."""
    cwd = Path.cwd().resolve()
    try:
        lexical = Path(os.path.normpath(cwd / file_path))
        return [_rel_to_repo(lexical), _rel_to_repo(lexical.resolve())]
    except Exception:  # e.g. embedded NUL: never silently allow
        return [PurePosixPath(file_path)]


def _rel_protected(rel: PurePosixPath, basenames: set[str], patterns: list[str]) -> bool:
    parts = rel.parts
    if rel.name in basenames or (rel.name in ROOT_ONLY and len(parts) == 1):
        return True
    if any(_has_run(parts, d) for d in PROTECTED_DIRS):
        return True
    if any(parts[-len(sfx) :] == sfx for sfx in PROTECTED_SUFFIXES if len(parts) >= len(sfx)):
        return True
    return any(_matches(rel, pat) for pat in patterns)


def _is_protected_path(file_path: str, basenames: set[str], patterns: list[str]) -> bool:
    return any(_rel_protected(r, basenames, patterns) for r in _candidates(file_path))


def _protected_tokens(basenames: set[str]) -> list[str]:
    dirs = ["/".join(d) + "/" for d in PROTECTED_DIRS]
    return [*basenames, *ROOT_ONLY, *dirs, ".claude/settings.json", ".claude/settings.local.json"]


# Manifest globs match in Bash only via their longest literal chunk (best-effort heuristic;
# the server-side ratchet is the real gate).
def _glob_literals(patterns: list[str]) -> set[str]:
    """Longest literal chunk of each glob (infra/** -> infra/, *.tf -> .tf); heuristic."""
    chunks = (max(re.split(r"[*?\[\]]+", p), key=len) for p in patterns)
    return {c for c in chunks if c}


def _bash_touches_protected(command: str, basenames: set[str], patterns: list[str]) -> bool:
    if not _WRITE_INDICATORS.search(command):
        return False
    tokens = [*_protected_tokens(basenames), *_glob_literals(patterns)]
    return any(token in command for token in tokens)


def _bash_bypasses_gate(command: str) -> str | None:
    """Reason string if a Bash command bypasses/merges/mutates gates, else None."""
    if _GH_PR_MERGE.search(command):
        return "merges a PR"
    if "--no-verify" in command:
        return "bypasses git hooks (--no-verify)"
    if _GIT_PUSH.search(command) and _PUSH_PROTECTED_REF.search(command):
        return "pushes directly to master/main"
    if _GH_API.search(command) and _GH_API_PROTECT.search(command):
        return "mutates branch protection / rulesets"
    return None


def _decision(payload: dict[str, object]) -> str | None:
    """Return the full ask reason if an ask is warranted, else None."""
    tool_name = payload.get("tool_name")
    raw_input = payload.get("tool_input")
    if not isinstance(tool_name, str) or not isinstance(raw_input, dict):
        return None
    tool_input = cast("dict[str, object]", raw_input)
    basenames = PROTECTED_BASENAMES | _extra_basenames()
    patterns = _manifest_patterns()

    if tool_name in {"Edit", "Write", "MultiEdit"}:
        file_path = tool_input.get("file_path")
        if isinstance(file_path, str) and _is_protected_path(file_path, basenames, patterns):
            return (
                f"Protected gate/config file: {file_path}. "
                "A human must approve edits to quality-gate infrastructure."
            )
    elif tool_name == "Bash":
        command = tool_input.get("command")
        if isinstance(command, str):
            if _bash_touches_protected(command, basenames, patterns):
                return (
                    f"Protected gate/config file touched by: {command}. "
                    "A human must approve edits to quality-gate infrastructure."
                )
            bypass = _bash_bypasses_gate(command)
            if bypass is not None:
                return (
                    f"Command {bypass}: {command}. "
                    "A human must approve merges / pushes / protection changes."
                )
    return None


def main() -> None:
    try:
        raw: object = json.load(sys.stdin)
        if not isinstance(raw, dict):
            return
        reason = _decision(cast("dict[str, object]", raw))
        if reason is None:
            return  # fall through to normal permission handling (no "allow"!)
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
            }
        }
        print(json.dumps(out))
    except Exception:  # fail open; server-side gate is the real boundary
        return


if __name__ == "__main__":
    main()
