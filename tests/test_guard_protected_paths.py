"""Tests for the deterministic PreToolUse guard hook.

Feeds a JSON hook payload through scripts/guard_protected_paths.py on stdin
and asserts on stdout: protected edits emit an "ask" decision, everything
else emits nothing (falls through to normal permission handling).
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "guard_protected_paths.py"


def run(payload: object) -> str:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload) if not isinstance(payload, str) else payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"non-zero exit: {proc.returncode}, stderr={proc.stderr}"
    return proc.stdout.strip()


def asks(stdout: str) -> bool:
    if not stdout:
        return False
    out = json.loads(stdout)
    return out["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_edit_pyproject_asks():
    out = run({"tool_name": "Edit", "tool_input": {"file_path": "pyproject.toml"}})
    assert asks(out)


def test_edit_normal_source_no_output():
    out = run({"tool_name": "Edit", "tool_input": {"file_path": "src/tvagent/app.py"}})
    assert out == ""


def test_write_github_workflow_asks():
    out = run({"tool_name": "Write", "tool_input": {"file_path": ".github/workflows/ci.yml"}})
    assert asks(out)


def test_multiedit_gate_ratchet_asks():
    out = run({"tool_name": "MultiEdit", "tool_input": {"file_path": "scripts/gate_ratchet.py"}})
    assert asks(out)


def test_edit_claude_settings_asks_self_guard():
    out = run({"tool_name": "Edit", "tool_input": {"file_path": ".claude/settings.json"}})
    assert asks(out)


def test_edit_self_guard_asks():
    out = run(
        {"tool_name": "Edit", "tool_input": {"file_path": "scripts/guard_protected_paths.py"}}
    )
    assert asks(out)


def test_bash_sed_inplace_pyproject_asks():
    out = run({"tool_name": "Bash", "tool_input": {"command": "sed -i s/92/80/ pyproject.toml"}})
    assert asks(out)


def test_bash_cat_gate_ratchet_no_output():
    out = run({"tool_name": "Bash", "tool_input": {"command": "cat scripts/gate_ratchet.py"}})
    assert out == ""


def test_bash_append_codeowners_asks():
    out = run({"tool_name": "Bash", "tool_input": {"command": "echo x >> CODEOWNERS"}})
    assert asks(out)


def test_bash_ls_no_output():
    out = run({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    assert out == ""


def test_malformed_stdin_no_output_fail_open():
    out = run("{not valid json")
    assert out == ""


def test_edit_by_nested_path_basename_asks():
    # basename match works regardless of directory depth
    out = run({"tool_name": "Edit", "tool_input": {"file_path": "any/where/uv.lock"}})
    assert asks(out)


# --- Category B: gate-bypass / merge / protection-mutating commands ---


def test_bash_gh_pr_merge_asks():
    # No write indicator and no protected file — must still ask.
    out = run({"tool_name": "Bash", "tool_input": {"command": "gh pr merge 15"}})
    assert asks(out)


def test_bash_git_push_master_asks():
    out = run({"tool_name": "Bash", "tool_input": {"command": "git push origin master"}})
    assert asks(out)


def test_bash_git_commit_no_verify_asks():
    out = run({"tool_name": "Bash", "tool_input": {"command": "git commit --no-verify -m x"}})
    assert asks(out)


def test_bash_gh_api_rulesets_asks():
    out = run({"tool_name": "Bash", "tool_input": {"command": "gh api repos/o/r/rulesets -X POST"}})
    assert asks(out)


def test_bash_git_push_feature_branch_no_output():
    # "master" as a substring of a branch name must NOT trigger (word boundary).
    out = run({"tool_name": "Bash", "tool_input": {"command": "git push origin feat/no-master-x"}})
    assert out == ""


def test_bash_git_commit_normal_no_output():
    out = run({"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}})
    assert out == ""
