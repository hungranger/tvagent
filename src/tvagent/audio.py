"""Shared hardware audio source.

Lives below `adapters/` so both `audio_vad.py` and `wakeword_oww.py` can
import `MicSource` without one adapter importing the other.
"""

from collections.abc import Iterator
from typing import Any

_VAD_AGGRESSIVENESS = 2
_FRAME_MS = 30
_MS_PER_SEC = 1000


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
