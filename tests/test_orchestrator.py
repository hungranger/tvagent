from tests.fakes import (
    FakeAudioCapture,
    FakeDisplay,
    FakeLLM,
    FakeMemory,
    FakeSpeakerID,
    FakeSTT,
    FakeTTS,
    FakeWakeWord,
)
from tvagent.core.models import AudioClip, Fact, Person
from tvagent.core.orchestrator import Orchestrator


def _orch(
    memory: FakeMemory, speaker_id: str, said: str = "what's my day", reply: str = "Standup at 9"
) -> tuple[Orchestrator, FakeLLM, FakeTTS, FakeDisplay]:
    clip = AudioClip(samples=b"x", sample_rate=16000)
    llm = FakeLLM(reply)
    tts, disp = FakeTTS(), FakeDisplay()
    orch = Orchestrator(
        FakeWakeWord(),
        FakeAudioCapture(clip),
        FakeSpeakerID(speaker_id),
        FakeSTT(said),
        llm,
        tts,
        memory,
        disp,
    )
    return orch, llm, tts, disp


def test_turn_tuned_to_person_and_persisted():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={"tone": "adult"}))
    orch, llm, tts, disp = _orch(m, "dad")
    turn = orch.run_once()
    assert llm.last_system is not None and "Dad" in llm.last_system  # F5: prompt tuned to who
    assert turn.replied == "Standup at 9"
    assert tts.spoken == ["Standup at 9"]  # F7
    assert disp.last is not None and disp.last.text == "Standup at 9"  # F8
    assert m.recent_turns("dad", 1)[0].said == "what's my day"  # F9


def test_memory_recall_reaches_prompt():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    m.add_fact(Fact(person_id="dad", text="allergic to peanuts", created_at=1.0))
    orch, llm, _, _ = _orch(m, "dad", said="what am I allergic to")
    orch.run_once()
    assert llm.last_system is not None and "peanuts" in llm.last_system  # F10: fact in prompt


def test_prior_turn_recalled_in_next_prompt():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    orch, llm, _, _ = _orch(m, "dad", said="what's my day", reply="Standup at 9")
    orch.run_once()
    orch, llm, _, _ = _orch(m, "dad", said="anything else", reply="Nope")
    orch.run_once()
    assert llm.last_system is not None
    assert "Recent exchanges:" in llm.last_system
    assert "what's my day -> Standup at 9" in llm.last_system


def test_guest_does_not_read_or_write_enrolled_memory():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    m.add_fact(Fact(person_id="dad", text="secret", created_at=1.0))
    orch, llm, _, _ = _orch(m, "guest")
    orch.run_once()
    assert llm.last_system is not None and "secret" not in llm.last_system  # F11: guest isolation
    assert m.recent_turns("dad", 10) == []  # F11: guest write didn't touch Dad
