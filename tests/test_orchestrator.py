import threading

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
from tvagent.core.models import GUEST, AudioClip, Fact, Person
from tvagent.core.orchestrator import Orchestrator, iter_sentences


def test_iter_sentences_splits_on_boundaries_and_flushes_remainder():
    chunks = ["Hello wor", "ld. How ", "are you? ", "Fine"]
    assert list(iter_sentences(chunks)) == ["Hello world.", "How are you?", "Fine"]


def test_iter_sentences_no_terminal_punctuation_yields_whole():
    assert list(iter_sentences(["just ", "one line"])) == ["just one line"]


def test_iter_sentences_empty_stream_yields_nothing():
    assert list(iter_sentences([])) == []


def _orch(
    memory: FakeMemory, speaker_id: str, said: str = "what's my day", reply: str = "Standup at 9"
) -> tuple[Orchestrator, FakeLLM, FakeTTS, FakeDisplay, FakeSpeakerID, FakeSTT]:
    clip = AudioClip(samples=b"x", sample_rate=16000)
    llm = FakeLLM(reply)
    tts, disp = FakeTTS(), FakeDisplay()
    speaker, stt = FakeSpeakerID(speaker_id), FakeSTT(said)
    orch = Orchestrator(
        FakeWakeWord(),
        FakeAudioCapture(clip),
        speaker,
        stt,
        llm,
        tts,
        memory,
        disp,
    )
    return orch, llm, tts, disp, speaker, stt


def test_build_prompt_content_for_known_person():
    orch, *_rest = _orch(FakeMemory(), "dad")
    person = Person(id="dad", name="Dad", embedding=[0.1], prefs={"tone": "adult"})
    facts = [
        Fact(person_id="dad", text="loves pizza", created_at=1.0),
        Fact(person_id="dad", text="allergic to peanuts", created_at=2.0),
    ]
    build = orch._build  # pyright: ignore[reportPrivateUsage]
    system, user = build(person, facts, "what's up")
    assert system == (
        "You are a family home assistant speaking with Dad.\n"
        "Use a adult tone. Keep replies short and spoken-friendly.\n"
        "What you remember about them: loves pizza; allergic to peanuts"
    )
    assert user == "what's up"


def test_build_prompt_defaults_for_unknown_guest():
    orch, *_rest = _orch(FakeMemory(), "dad")
    system, _ = orch._build(None, [], "hi")  # pyright: ignore[reportPrivateUsage]
    assert system == (
        "You are a family home assistant speaking with an unknown guest.\n"
        "Use a friendly tone. Keep replies short and spoken-friendly."
    )


def test_turn_tuned_to_person_and_persisted():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={"tone": "adult"}))
    orch, llm, tts, disp, speaker, stt = _orch(m, "dad")
    turn = orch.run_once()
    assert llm.last_system is not None and "Dad" in llm.last_system  # F5: prompt tuned to who
    assert llm.last_user == "what's my day"  # the transcribed utterance reaches the LLM
    assert turn.replied == "Standup at 9"
    assert tts.spoken == ["Standup at 9"]  # F7
    assert disp.last is not None and disp.last.text == "Standup at 9"  # F8
    assert disp.last.person == "Dad"  # rendered display names the identified person
    assert isinstance(turn.ts, float)  # timestamp is real, not a stand-in
    assert m.recent_turns("dad", 1)[0].said == "what's my day"  # F9
    clip = orch.capture.capture()
    assert speaker.last_clip is clip  # identify sees the real clip
    assert stt.last_clip is clip  # transcribe sees the real clip


def test_memory_recall_reaches_prompt():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    m.add_fact(Fact(person_id="dad", text="allergic to peanuts", created_at=1.0))
    orch, llm, *_rest = _orch(m, "dad", said="what am I allergic to")
    orch.run_once()
    assert llm.last_system is not None and "peanuts" in llm.last_system  # F10: fact in prompt


def test_prior_turn_recalled_in_next_prompt():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    orch, llm, *_rest = _orch(m, "dad", said="what's my day", reply="Standup at 9")
    orch.run_once()
    orch, llm, *_rest = _orch(m, "dad", said="anything else", reply="Nope")
    orch.run_once()
    assert llm.last_history == [("what's my day", "Standup at 9")]  # F6: history reaches the LLM


def test_on_event_emits_each_stage_in_order():
    # The console front-end observes the turn stage-by-stage via on_event.
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    orch, *_rest = _orch(m, "dad", said="what's my day", reply="Standup at 9")
    events: list[tuple[str, dict[str, object]]] = []
    orch.run_once(on_event=lambda stage, data: events.append((stage, data)))
    assert [stage for stage, _ in events] == [
        "wake",
        "identified",
        "transcribed",
        "replied",
        "spoken",
    ]
    by_stage = dict(events)
    assert by_stage["identified"] == {"person_id": "dad", "name": "Dad"}
    assert by_stage["transcribed"] == {"said": "what's my day"}
    assert by_stage["replied"] == {"reply": "Standup at 9"}


def test_reply_streamed_to_tts_sentence_by_sentence():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    orch, _llm, tts, disp, *_rest = _orch(m, "dad", said="hi", reply="Hi there. All good.")
    turn = orch.run_once()
    assert tts.spoken == ["Hi there.", "All good."]  # each sentence spoken as it completes
    assert turn.replied == "Hi there. All good."
    assert disp.last is not None and disp.last.text == "Hi there. All good."


def test_identify_and_transcribe_run_concurrently():
    # Both consume the same clip independently; running them in parallel shaves a
    # stage off the turn. Proven with a 2-party barrier: if run_once called them
    # sequentially, the first would block on the barrier and time out (BrokenBarrier),
    # failing the test; only concurrent execution lets both arrive and proceed.
    barrier = threading.Barrier(2, timeout=3)
    clip = AudioClip(samples=b"x", sample_rate=16000)

    class _BarrierSpeaker:
        def identify(self, clip: AudioClip) -> str:
            barrier.wait()
            return "guest"

        def enroll(self, name: str, clips: list[AudioClip]) -> Person:
            return Person(id=name.lower(), name=name, embedding=[0.0], prefs={})

    class _BarrierSTT:
        def transcribe(self, clip: AudioClip) -> str:
            barrier.wait()
            return "hello"

    orch = Orchestrator(
        FakeWakeWord(),
        FakeAudioCapture(clip),
        _BarrierSpeaker(),
        _BarrierSTT(),
        FakeLLM("hi"),
        FakeTTS(),
        FakeMemory(),
        FakeDisplay(),
    )
    turn = orch.run_once()
    assert turn.said == "hello" and turn.replied == "hi"


def test_on_event_reports_guest_for_unknown_speaker():
    orch, *_rest = _orch(FakeMemory(), "guest", said="hi", reply="hello")
    events: list[tuple[str, dict[str, object]]] = []
    orch.run_once(on_event=lambda stage, data: events.append((stage, data)))
    assert dict(events)["identified"] == {"person_id": GUEST, "name": "Guest"}


def test_guest_does_not_read_or_write_enrolled_memory():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    m.add_fact(Fact(person_id="dad", text="secret", created_at=1.0))
    orch, llm, _, disp, *_rest = _orch(m, "guest")
    orch.run_once()
    assert llm.last_system is not None and "secret" not in llm.last_system  # F11: guest isolation
    assert m.recent_turns("dad", 10) == []  # F11: guest write didn't touch Dad
    assert disp.last is not None and disp.last.person == "Guest"  # unenrolled -> shows as Guest
    assert m.recent_turns(GUEST, 10)[0].person_id == GUEST  # guest turn recorded under GUEST
