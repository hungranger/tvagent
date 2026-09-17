import ast, pathlib

def test_core_imports_only_core():
    # anchor off this file, not CWD, so it can't vacuously pass from another dir
    repo = pathlib.Path(__file__).resolve().parent.parent
    core_dir = repo / "src" / "tvagent" / "core"
    files = list(core_dir.glob("*.py"))
    assert len(files) >= 3, f"isolation test found no core files (looked in {core_dir})"
    for pyfile in files:
        tree = ast.parse(pyfile.read_text())
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.ImportFrom): mod = node.module or ""
            elif isinstance(node, ast.Import): mod = node.names[0].name
            if mod and mod.startswith("tvagent") and not mod.startswith("tvagent.core"):
                raise AssertionError(f"{pyfile.name} imports non-core module {mod}")
