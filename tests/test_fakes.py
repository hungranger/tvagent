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
from tvagent.core.models import AudioClip, RenderState


def test_fakes_satisfy_ports():
    clip = AudioClip(samples=b"x", sample_rate=16000)
    assert FakeAudioCapture(clip).capture() is clip
    assert FakeSpeakerID(person_id="dad").identify(clip) == "dad"
    assert FakeSTT("hi there").transcribe(clip) == "hi there"
    assert FakeLLM("reply").respond("sys", "hi", []) == "reply"
    d = FakeDisplay()
    d.render(RenderState(person="Dad", text="hello"))
    assert d.last is not None and d.last.text == "hello"
    m = FakeMemory()
    assert m.get_person("nope") is None
    FakeTTS().speak("hi")
    FakeWakeWord().wait()  # no raise
