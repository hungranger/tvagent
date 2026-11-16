from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]


def test_skill_has_all_phases_and_refs():
    text = (SKILL / "SKILL.md").read_text()
    for phase in ["Phase 0", "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"]:
        assert phase in text, f"missing {phase}"
    # references exist and are linked
    for ref in ["detectors.md", "thresholds.md", "tiers.md", "anti-gaming.md"]:
        assert (SKILL / "references" / ref).exists(), f"missing ref file {ref}"
        assert ref in text, f"SKILL.md does not link {ref}"


def test_confirm_gates_documented():
    text = (SKILL / "SKILL.md").read_text().lower()
    # the three user gates from the spec must be explicit
    assert "confirm" in text and "overwrite" in text          # Phase 4 merge-confirm
    assert "measured" in text or "current" in text            # Phase 2 measure-then-propose
    assert "tier" in text                                     # Phase 3


def test_l3_degradation_documented():
    text = (SKILL / "SKILL.md").read_text().lower()
    assert "advisory" in text  # L3 degrade path when ruleset can't apply


def _docs():
    return [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]


def test_multilanguage_skill_md():
    text = (SKILL / "SKILL.md").read_text()
    for needle in ["python", "rust", "go", "react-ts", "quality-gates.toml",
                   "check-drift", "tomllib", "solo", "python.pkg_manager"]:
        assert needle in text, f"SKILL.md missing {needle}"
    assert "Python-spine" in text


def test_detect_keys_namespaced():
    text = (SKILL / "SKILL.md").read_text()
    for stale in ["`pkg_manager`,", "`layout.{src_layout", "`existing.{ruff"]:
        assert stale not in text, f"stale flat key {stale}"
    det = (SKILL / "references" / "detectors.md").read_text()
    assert "`python.pkg_manager`" in det and "`python.existing.ruff`" in det
    assert "no precedence" in det and "Language precedence" not in det


def test_anti_gaming_covers_manifest_judge():
    text = (SKILL / "references" / "anti-gaming.md").read_text()
    assert "manifest.py" in text and "gate_setup/" in text
    assert "check-drift" in text and "python -P" in text and "casefold" in text


def test_no_leftovers_or_unfilled_tokens():
    for p in _docs():
        t = p.read_text()
        assert "{{" not in t, f"{p.name} has unfilled token"
        assert "setup-python-quality-gates" not in t
        assert "Python Quality Gates" not in t


def test_phase4_warns_about_rerender():
    text = (SKILL / "SKILL.md").read_text().lower()
    assert "comments" in text and "in place" in text
