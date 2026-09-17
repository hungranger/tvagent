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
from tvagent.config import _get, build_orchestrator  # pyright: ignore[reportPrivateUsage]
from tvagent.core.models import AudioClip
from tvagent.core.orchestrator import Orchestrator


def test_get_falls_back_to_factory_when_key_missing() -> None:
    assert _get({}, "wake", lambda: "made") == "made"


def test_build_with_all_fakes_swapped_by_config() -> None:
    clip = AudioClip(samples=b"x", sample_rate=16000)
    orch = build_orchestrator(
        {
            "wake": FakeWakeWord(),
            "capture": FakeAudioCapture(clip),
            "speaker": FakeSpeakerID("guest"),
            "stt": FakeSTT("hi"),
            "llm": FakeLLM("yo"),
            "tts": FakeTTS(),
            "memory": FakeMemory(),
            "display": FakeDisplay(),
        }
    )
    assert isinstance(orch, Orchestrator)
    assert orch.run_once().replied == "yo"  # M2/M3: fully swappable, no hardware
