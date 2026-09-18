import re
from pathlib import Path

TPL = Path(__file__).resolve().parents[1] / "templates"
TOKEN_RE = re.compile(r"\{\{([A-Z_]+)\}\}")

def documented_tokens():
    text = (TPL / "TOKENS.md").read_text()
    return set(TOKEN_RE.findall(text))

def test_every_used_token_is_documented():
    used: set[str] = set()
    for f in TPL.rglob("*"):
        if f.is_file() and f.name != "TOKENS.md" and f.suffix in {".toml", ".yaml", ".yml", ".json", ""}:
            used |= set(TOKEN_RE.findall(f.read_text(errors="ignore")))
    undocumented = used - documented_tokens()
    assert not undocumented, f"tokens used but not in TOKENS.md: {undocumented}"

def test_core_templates_exist():
    for name in ["pyproject.gates.toml", "pre-commit-config.yaml", "ci.yml",
                 "nightly-mutation.yml", "ruleset.json", "CODEOWNERS"]:
        assert (TPL / name).exists(), name
