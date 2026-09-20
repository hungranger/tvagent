import io
import wave
from typing import Any

import numpy

from tests.fakes import FakeTTS
from tvagent.adapters.tts_tap import TappedTTS

np: Any = numpy


def _wav(samples: list[int], rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.array(samples, dtype=np.int16).tobytes())
    return buf.getvalue()


class _FakeSink:
    """Stand-in for DuplexAudio: records enqueued far-end, reports drained."""

    def __init__(self) -> None:
        self.data = b""
        self.cleared = False

    def enqueue(self, pcm: bytes) -> None:
        self.data += pcm

    def clear(self) -> None:
        self.cleared = True

    def pending(self) -> int:
        return 0  # drained immediately so play() returns


def test_play_enqueues_resampled_far_end_into_sink() -> None:
    sink = _FakeSink()
    tapped = TappedTTS(FakeTTS(), sink, dev_rate=16000)  # type: ignore[arg-type]
    samples = list(range(300))
    tapped.play(_wav(samples, 16000))  # 16k in -> 16k dev: identity
    assert sink.data == np.array(samples, dtype=np.int16).tobytes()


def test_play_ignores_empty_pcm() -> None:
    sink = _FakeSink()
    tapped = TappedTTS(FakeTTS(), sink, dev_rate=16000)  # type: ignore[arg-type]
    tapped.play(b"")
    assert sink.data == b""


def test_stop_clears_the_sink() -> None:
    sink = _FakeSink()
    tapped = TappedTTS(FakeTTS(), sink, dev_rate=16000)  # type: ignore[arg-type]
    tapped.stop()
    assert sink.cleared is True


def test_synth_speak_and_voice_delegate() -> None:
    inner = FakeTTS()
    tapped = TappedTTS(inner, _FakeSink())  # type: ignore[arg-type]
    assert tapped.synth("hi")[0] == b"hi"
    tapped.speak("yo")
    assert inner.spoken == ["hi", "yo"]
