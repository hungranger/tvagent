import pathlib

from tvagent.adapters.memory_json import JsonMemory
from tvagent.core.models import GUEST, Fact, Person, Turn


def test_person_and_turn_roundtrip(tmp_path: pathlib.Path):
    m = JsonMemory(tmp_path)
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={"tone": "adult"}))
    person = m.get_person("dad")
    assert person is not None and person.name == "Dad"
    m.save_turn(Turn(person_id="dad", ts=1.0, said="hi", replied="yo"))
    m.save_turn(Turn(person_id="dad", ts=2.0, said="bye", replied="cya"))
    recent = m.recent_turns("dad", 1)
    assert len(recent) == 1 and recent[0].said == "bye"
    assert len(m.recent_turns("dad", 2)) == 2  # pins the [-n:] slice, not [n:]


def test_dir_creates_missing_parent_directories(tmp_path: pathlib.Path):
    # root itself doesn't exist yet -> _dir must create it (and person_id) in one go
    m = JsonMemory(tmp_path / "nested" / "root")
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    assert m.get_person("dad") is not None


def test_facts_and_guest_isolation(tmp_path: pathlib.Path):
    m = JsonMemory(tmp_path)
    m.add_fact(Fact(person_id="dad", text="standup 9am", created_at=1.0))
    assert m.get_facts("dad")[0].text == "standup 9am"
    # guest writes never leak into an enrolled person
    m.save_turn(Turn(person_id=GUEST, ts=3.0, said="who am i", replied="a guest"))
    assert m.recent_turns("dad", 10) == []
    assert m.get_facts(GUEST) == []
