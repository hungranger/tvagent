from typing import Any

from tvagent.audio import MicSource
from tvagent.core.models import AudioClip


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


def record_seconds(seconds: int, sample_rate: int = 16000) -> AudioClip:
    import sounddevice  # noqa: PLC0415 -- lazy

    sd: Any = sounddevice
    rec = sd.rec(int(seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    samples: bytes = rec.tobytes()
    return AudioClip(samples=samples, sample_rate=sample_rate)
