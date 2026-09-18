"""Shared hardware audio source.

Lives below `adapters/` so both `audio_vad.py` and `wakeword_oww.py` can
import `MicSource` without one adapter importing the other.
"""

import threading
from collections.abc import Iterator
from typing import Any

_VAD_AGGRESSIVENESS = 2
_FRAME_MS = 30
_MS_PER_SEC = 1000


class PlaybackReference:
    """The AEC far-end reference: a FIFO of the PCM the assistant is playing.
    The playback path writes what it plays; the barge-in detector reads the same
    bytes to subtract the assistant's own voice from the mic. Reads always return
    the requested size, zero-padding when nothing is buffered (silence), so a mic
    frame always has a matching far-end frame. Thread-safe: writer and reader run
    on different threads.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self._lock = threading.Lock()

    def write(self, pcm: bytes) -> None:
        with self._lock:
            self._buf.extend(pcm)

    def read(self, n: int) -> bytes:
        with self._lock:
            take = self._buf[:n]
            del self._buf[:n]
        return bytes(take).ljust(n, b"\x00")  # zero-pad to n = far-end silence

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()


class MicSource:
    def __init__(self, sample_rate: int) -> None:
        import sounddevice  # noqa: PLC0415 -- lazy: no mic/backend needed to test logic
        import webrtcvad  # noqa: PLC0415 -- lazy

        self.sample_rate = sample_rate
        wv: Any = webrtcvad
        self.vad: Any = wv.Vad(_VAD_AGGRESSIVENESS)
        self.sd: Any = sounddevice

    def frames(self) -> Iterator[tuple[bytes, bool]]:
        frame_ms, sr = _FRAME_MS, self.sample_rate
        n = int(sr * frame_ms / _MS_PER_SEC)
        with self.sd.RawInputStream(
            samplerate=sr, blocksize=n, dtype="int16", channels=1
        ) as stream:
            while True:
                data, _ = stream.read(n)
                frame: bytes = bytes(data)
                is_speech: bool = self.vad.is_speech(frame, sr)
                yield frame, is_speech
