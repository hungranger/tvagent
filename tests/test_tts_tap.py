import io
import wave
from typing import Any

import numpy

from tests.fakes import FakeTTS
from tvagent.adapters.tts_tap import TappedTTS
from tvagent.audio import PlaybackReference

np: Any = numpy


def _wav(samples: list[int], rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.array(samples, dtype=np.int16).tobytes())
    return buf.getvalue()


def test_play_delegates_and_taps_far_end_at_16k() -> None:
    ref = PlaybackReference()
    inner = FakeTTS()
    tapped = TappedTTS(inner, ref)
    wav = _wav([100, 200, 300], 16000)  # already 16k -> far-end == samples
    tapped.play(wav)
    assert inner.played == [wav]  # real playback still happens
    assert ref.read(6) == np.array([100, 200, 300], dtype=np.int16).tobytes()


def test_synth_speak_and_stop_delegate() -> None:
    ref = PlaybackReference()
    inner = FakeTTS()
    tapped = TappedTTS(inner, ref)
    assert tapped.synth("hi")[0] == b"hi"  # FakeTTS.synth returns (text.encode(), 0.0)
    tapped.speak("yo")
    tapped.stop()
    assert inner.spoken == ["hi", "yo"] and inner.stopped == 1  # synth+speak both record
    tapped.warmup()  # FakeTTS has no warmup -> safe no-op


class _VoiceTTS(FakeTTS):
    def __init__(self) -> None:
        super().__init__()
        self.voice: str | None = None
        self.warmed = False

    def set_voice(self, voice: str) -> None:
        self.voice = voice

    def warmup(self) -> None:
        self.warmed = True


def test_set_voice_and_warmup_delegate_when_present() -> None:
    inner = _VoiceTTS()
    tapped = TappedTTS(inner, PlaybackReference())
    tapped.set_voice("am_michael")
    tapped.warmup()
    assert inner.voice == "am_michael" and inner.warmed is True
