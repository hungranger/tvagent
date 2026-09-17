from collections.abc import Iterator
from typing import Any

from tvagent.core.models import AudioClip

_VAD_AGGRESSIVENESS = 2
_FRAME_MS = 30
_MS_PER_SEC = 1000


class VadCapture:
    def __init__(
        self, sample_rate: int = 16000, silence_limit: int = 15, _source: Any = None
    ) -> None:
        self.sample_rate, self.silence_limit = sample_rate, silence_limit
        self._source: Any = _source or MicSource(sample_rate)

    def capture(self) -> AudioClip:
        buf, silent, started = bytearray(), 0, False
        for frame, is_speech in self._source.frames():
            if is_speech:
                buf.extend(frame)
                started, silent = True, 0
            elif started:
                silent += 1
                if silent >= self.silence_limit:
                    break
        return AudioClip(samples=bytes(buf), sample_rate=self.sample_rate)


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


def record_seconds(seconds: int, sample_rate: int = 16000) -> AudioClip:
    import sounddevice  # noqa: PLC0415 -- lazy

    sd: Any = sounddevice
    rec = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    samples: bytes = rec.tobytes()
    return AudioClip(samples=samples, sample_rate=sample_rate)
