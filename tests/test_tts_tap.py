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


class _FakeStream:
    """Records the blocks written to the output device."""

    def __init__(self) -> None:
        self.blocks: list[bytes] = []

    def write(self, block: Any) -> None:
        self.blocks.append(bytes(block.tobytes()))

    def close(self) -> None:
        pass


def test_play_streams_far_end_block_by_block_aligned_with_output() -> None:
    ref = PlaybackReference()
    stream = _FakeStream()

    def factory(_rate: int) -> _FakeStream:
        return stream

    tapped = TappedTTS(FakeTTS(), ref, dev_rate=16000, block=128, _stream_factory=factory)
    samples = list(range(300))  # 300 samples @16k
    tapped.play(_wav(samples, 16000))
    # far-end captured incrementally, in more than one block (not all at once)
    assert len(stream.blocks) > 1
    # and it equals the full played audio (16k in -> 16k far-end, identity)
    assert ref.read(600) == np.array(samples, dtype=np.int16).tobytes()
    # output device received the same audio
    assert b"".join(stream.blocks) == np.array(samples, dtype=np.int16).tobytes()


def test_stop_halts_streaming_midway() -> None:
    ref = PlaybackReference()

    class _StopAfterOne:
        def __init__(self) -> None:
            self.blocks = 0

        def write(self, block: Any) -> None:
            self.blocks += 1
            tapped.stop()  # user barges in after the first block

        def close(self) -> None:
            pass

    s = _StopAfterOne()

    def factory(_rate: int) -> _StopAfterOne:
        return s

    tapped = TappedTTS(FakeTTS(), ref, dev_rate=16000, block=128, _stream_factory=factory)
    tapped.play(_wav(list(range(1000)), 16000))  # 8 blocks if not stopped
    assert s.blocks == 1  # halted right after the first block


def test_synth_speak_stop_and_voice_delegate() -> None:
    inner = FakeTTS()
    tapped = TappedTTS(inner, PlaybackReference())
    assert tapped.synth("hi")[0] == b"hi"
    tapped.speak("yo")
    assert inner.spoken == ["hi", "yo"]
    tapped.warmup()  # no warmup on FakeTTS -> safe no-op
