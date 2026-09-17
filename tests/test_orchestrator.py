import time
from tvagent.core.models import AudioClip, Person
from tvagent.core.orchestrator import Orchestrator
from tests.fakes import (FakeWakeWord, FakeAudioCapture, FakeSpeakerID, FakeSTT,
                         FakeLLM, FakeTTS, FakeMemory, FakeDisplay)

def _orch(memory, speaker_id, said="what's my day", reply="Standup at 9"):
    clip = AudioClip(samples=b"x", sample_rate=16000)
    llm = FakeLLM(reply)
    tts, disp = FakeTTS(), FakeDisplay()
    orch = Orchestrator(FakeWakeWord(), FakeAudioCapture(clip),
                        FakeSpeakerID(speaker_id), FakeSTT(said),
                        llm, tts, memory, disp)
    return orch, llm, tts, disp

def test_turn_tuned_to_person_and_persisted():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={"tone": "adult"}))
    orch, llm, tts, disp = _orch(m, "dad")
    turn = orch.run_once()
    assert "Dad" in llm.last_system          # F5: prompt tuned to who
    assert turn.replied == "Standup at 9"
    assert tts.spoken == ["Standup at 9"]    # F7
    assert disp.last.text == "Standup at 9"  # F8
    assert m.recent_turns("dad", 1)[0].said == "what's my day"  # F9

def test_memory_recall_reaches_prompt():
    from tvagent.core.models import Fact
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    m.add_fact(Fact(person_id="dad", text="allergic to peanuts", created_at=1.0))
    orch, llm, _, _ = _orch(m, "dad", said="what am I allergic to")
    orch.run_once()
    assert "peanuts" in llm.last_system      # F10: fact reaches the prompt

def test_guest_does_not_read_or_write_enrolled_memory():
    from tvagent.core.models import Fact
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    m.add_fact(Fact(person_id="dad", text="secret", created_at=1.0))
    orch, llm, _, _ = _orch(m, "guest")
    orch.run_once()
    assert "secret" not in llm.last_system   # F11: guest can't read Dad
    assert m.recent_turns("dad", 10) == []   # F11: guest write didn't touch Dad
