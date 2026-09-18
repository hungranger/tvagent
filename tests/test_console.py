import threading
import time

from tests.fakes import (
    FakeAudioCapture,
    FakeDisplay,
    FakeLLM,
    FakeMemory,
    FakeSTT,
    FakeTTS,
    FakeWakeWord,
)
from tvagent.console import ListenLoop, handle_command, origin_allowed
from tvagent.core.models import AudioClip, Person
from tvagent.core.orchestrator import Orchestrator


class _TunableSpeaker:
    """SpeakerID fake exposing the runtime-tunable threshold/margin the console sets."""

    def __init__(self) -> None:
        self.threshold = 0.25
        self.margin = 0.15

    def identify(self, clip: AudioClip) -> str:
        return "guest"

    def enroll(self, name: str, clips: list[AudioClip]) -> Person:
        return Person(id=name.lower(), name=name, embedding=[0.0], prefs={})


class _VoiceTTS(FakeTTS):
    def __init__(self) -> None:
        super().__init__()
        self.voice = "en_US-amy-medium"

    def set_voice(self, name: str) -> None:
        self.voice = name


def _orch(memory: FakeMemory | None = None) -> Orchestrator:
    return Orchestrator(
        FakeWakeWord(),
        FakeAudioCapture(AudioClip(samples=b"x", sample_rate=16000)),
        _TunableSpeaker(),
        FakeSTT("hi"),
        FakeLLM("yo"),
        _VoiceTTS(),
        memory or FakeMemory(),
        FakeDisplay(),
    )


def test_tune_sets_threshold_and_margin_and_returns_status() -> None:
    orch = _orch()
    status = handle_command(orch, {"cmd": "tune", "threshold": 0.4, "margin": 0.2})
    speaker: object = orch.speaker
    assert getattr(speaker, "threshold") == 0.4  # noqa: B009
    assert getattr(speaker, "margin") == 0.2  # noqa: B009
    assert status["threshold"] == 0.4
    assert status["margin"] == 0.2


def test_tune_accepts_partial_update() -> None:
    orch = _orch()
    handle_command(orch, {"cmd": "tune", "threshold": 0.5})  # margin omitted
    speaker: object = orch.speaker
    assert getattr(speaker, "threshold") == 0.5  # noqa: B009
    assert getattr(speaker, "margin") == 0.15  # unchanged  # noqa: B009


def test_voice_command_switches_tts_voice() -> None:
    orch = _orch()
    status = handle_command(orch, {"cmd": "voice", "name": "en_US-ryan-high"})
    assert getattr(orch.tts, "voice") == "en_US-ryan-high"  # noqa: B009
    assert status["voice"] == "en_US-ryan-high"


def test_status_lists_enrolled_people() -> None:
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    m.upsert_person(Person(id="mom", name="Mom", embedding=[0.2], prefs={}))
    status = handle_command(_orch(m), {"cmd": "status"})
    assert sorted(status["people"]) == ["Dad", "Mom"]  # type: ignore[type-var]


def test_unknown_command_returns_status_unchanged() -> None:
    # An unrecognized command must not raise and must still report current state.
    status = handle_command(_orch(), {"cmd": "bogus"})
    assert status["threshold"] == 0.25


def test_origin_allowed_accepts_local_rejects_cross_site() -> None:
    assert origin_allowed(None) is True  # non-browser client
    assert origin_allowed("null") is True  # file:// kiosk/console
    assert origin_allowed("http://localhost:8080") is True
    assert origin_allowed("http://127.0.0.1:5500") is True
    assert origin_allowed("https://evil.example.com") is False  # CSWSH attempt
    assert origin_allowed("http://localhost.attacker.com") is False  # suffix trick


def test_listenloop_toggles_idempotently_and_stays_single_threaded() -> None:
    seen: list[threading.Thread] = []

    def run_turn() -> None:
        seen.append(threading.current_thread())
        time.sleep(0.005)

    ll = ListenLoop(run_turn)
    assert ll.listening is False
    ll.set(True)
    time.sleep(0.03)  # let a few turns run
    t1 = ll._thread  # pyright: ignore[reportPrivateUsage]
    ll.set(True)  # idempotent -> must NOT spawn a second thread
    assert ll._thread is t1  # pyright: ignore[reportPrivateUsage]
    assert ll.listening is True
    ll.set(False)
    assert t1 is not None
    t1.join(1.0)
    assert not t1.is_alive()  # stop actually ends the loop (turns are instant here)
    assert seen and all(t is t1 for t in seen)  # only ever one worker thread

    # restart after the thread has died -> a fresh worker
    ll.set(True)
    time.sleep(0.03)
    t2 = ll._thread  # pyright: ignore[reportPrivateUsage]
    assert t2 is not None and t2 is not t1
    ll.set(False)
    t2.join(1.0)
