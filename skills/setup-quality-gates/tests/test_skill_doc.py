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
