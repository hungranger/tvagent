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


def _all_fakes() -> dict[str, object]:
    clip = AudioClip(samples=b"x", sample_rate=16000)
    return {
        "wake": FakeWakeWord(),
        "capture": FakeAudioCapture(clip),
        "speaker": FakeSpeakerID("guest"),
        "stt": FakeSTT("hi"),
        "llm": FakeLLM("yo"),
        "tts": FakeTTS(),
        "memory": FakeMemory(),
        "display": FakeDisplay(),
    }


class _WarmSpy(FakeSTT):
    def __init__(self) -> None:
        super().__init__("hi")
        self.warmed = False

    def warmup(self) -> None:
        self.warmed = True


def test_build_with_all_fakes_swapped_by_config() -> None:
    orch = build_orchestrator(_all_fakes())
    assert isinstance(orch, Orchestrator)
    assert orch.run_once().replied == "yo"  # M2/M3: fully swappable, no hardware


def test_build_warm_calls_warmup_on_capable_adapters() -> None:
    spy = _WarmSpy()
    build_orchestrator({**_all_fakes(), "stt": spy}, warm=True)
    assert spy.warmed is True


def test_build_no_warm_skips_warmup() -> None:
    spy = _WarmSpy()
    build_orchestrator({**_all_fakes(), "stt": spy}, warm=False)
    assert spy.warmed is False


def test_build_warm_ignores_adapters_without_warmup() -> None:
    # plain fakes have no warmup(); warm=True must not raise
    orch = build_orchestrator(_all_fakes(), warm=True)
    assert orch.run_once().replied == "yo"


def test_barge_in_off_by_default_and_wired_via_override() -> None:
    from tests.fakes import FakeBargeIn  # noqa: PLC0415 -- lazy test import

    assert build_orchestrator(_all_fakes()).barge_in is None  # opt-in only
    det = FakeBargeIn()
    assert build_orchestrator({**_all_fakes(), "barge_in": det}).barge_in is det
