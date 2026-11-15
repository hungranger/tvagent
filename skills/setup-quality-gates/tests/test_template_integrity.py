import re
from pathlib import Path

TPL = Path(__file__).resolve().parents[1] / "templates"
TOKEN_RE = re.compile(r"\{\{([A-Z_]+)\}\}")
# scripts/<name>.py referenced from template prose/commands (not the
# gate_ratchet.py / suppression_diff.py doc mentions inside anti-gaming.md --
# those aren't templates). Matches e.g. "scripts/mutation_score.py".
SCRIPT_REF_RE = re.compile(r"\bscripts/([\w.-]+\.py)\b")

SAMPLE_VALUES = {
    "COVERAGE_FLOOR": "92",
    "MAX_COMPLEXITY": "10",
    "VULTURE_MIN_CONFIDENCE": "60",
    "PYRIGHT_MODE": "strict",
    "MUTATION_FLOOR": "90",
    "PKG_AUDIT_EXPORT": "uv export --no-hashes --all-extras",
    "PKG_INSTALL_STEP": "pip install -e .[dev]",
    "SRC_DIRS": '["src/demo"]',
    "OWNER": "someone",
    "DEFAULT_BRANCH": "master",
}


def _render(text: str) -> str:
    for token, value in SAMPLE_VALUES.items():
        text = text.replace("{{" + token + "}}", value)
    return text


def test_full_render_leaves_no_token_placeholder():
    for f in TPL.rglob("*"):
        if not f.is_file() or f.name == "TOKENS.md":
            continue
        rendered = _render(f.read_text(errors="ignore"))
        leftover = TOKEN_RE.findall(rendered)
        assert not leftover, f"{f}: unrendered token(s) {leftover}"


def test_every_referenced_script_is_shipped():
    scripts_dir = TPL / "scripts"
    for f in TPL.rglob("*"):
        if not f.is_file() or f.parent == scripts_dir:
            continue
        for name in SCRIPT_REF_RE.findall(f.read_text(errors="ignore")):
            assert (scripts_dir / name).exists(), (
                f"{f} references scripts/{name}, missing from {scripts_dir}"
            )
