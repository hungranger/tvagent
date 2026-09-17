from tvagent.core.models import GUEST, AudioClip, Person, RenderState, Turn


def test_models_construct():
    clip = AudioClip(samples=b"\x00\x01", sample_rate=16000)
    assert clip.sample_rate == 16000
    p = Person(id="dad", name="Dad", embedding=[0.1, 0.2], prefs={"tone": "adult"})
    assert p.name == "Dad"
    t = Turn(person_id="dad", ts=1.0, said="hi", replied="hello")
    assert t.said == "hi"
    assert RenderState(person="Dad", text="hello", card=None).card is None
    assert GUEST == "guest"
