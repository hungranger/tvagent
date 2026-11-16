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


# --- G14: the spine never branches on a language name ----------------------
import ast  # noqa: E402
import sys  # noqa: E402

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from gate_setup.render import render  # noqa: E402

LANG_NAMES = {"rust", "go", "react-ts", "react", "typescript", "golang"}
# detect.py is deliberately excluded: detection is inherently language-aware
# (it IS the registry of per-language marker files), not spine logic.
SPINE = [
    SKILL / "scripts/gate_setup/render.py",
    SKILL / "scripts/gate_setup/manifest.py",
    SKILL / "templates/scripts/gate_ratchet.py",
    SKILL / "templates/scripts/guard_protected_paths.py",
]


def _lang_literals(path: Path) -> list[tuple[int, str]]:
    """String literals exactly equal to a language name, as (line, text).

    Comments and docstrings are ignored; so are protected-file names like
    "go.mod" (not an exact language name). Catches `== "rust"`-style branching.
    """
    hits = []
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in LANG_NAMES:
            hits.append((n.lineno, n.value))
    return hits


def test_spine_has_no_language_branching():
    for p in SPINE:
        hits = _lang_literals(p)
        if p.name == "manifest.py":  # only the LANGUAGES registry constant may name languages
            lines = p.read_text().splitlines()
            hits = [h for h in hits if not lines[h[0] - 1].startswith("LANGUAGES")]
        assert not hits, f"{p}: language literal(s) in spine logic: {hits}"


def test_every_profile_validates_and_renders():
    m = {
        "thresholds": {
            "coverage_floor": 80, "complexity_max": 15, "mutation_floor": 60,
            "vulture_confidence": 60, "arch_contracts_min": 1, "type_strictness": "strict",
            "lint_rules": ["E"],
        },
        "protected": {"paths": ["quality-gates.toml"]},
    }
    profs = [p for p in (SKILL / "profiles").iterdir() if (p / "profile.toml").is_file()]
    assert len(profs) >= 4
    for prof in profs:
        out = render(prof, m)
        assert all("{{" not in v for v in out.values()), prof
        # every scripts/<x>.py a profile template references is shipped
        for text in out.values():
            for name in SCRIPT_REF_RE.findall(text):
                assert (TPL / "scripts" / name).exists(), f"{prof.name}: scripts/{name}"
