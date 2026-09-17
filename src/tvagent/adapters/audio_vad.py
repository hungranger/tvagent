from tvagent.core.models import AudioClip


class VadCapture:
    def __init__(self, sample_rate=16000, silence_limit=15, _source=None):
        self.sample_rate, self.silence_limit = sample_rate, silence_limit
        self._source = _source or _MicSource(sample_rate)

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


class _MicSource:
    def __init__(self, sample_rate):
        import webrtcvad
        import sounddevice  # imported lazily so CI without a mic still tests logic
        self.sample_rate = sample_rate
        self.vad = webrtcvad.Vad(2)
        self.sd = sounddevice

    def frames(self):
        frame_ms, sr = 30, self.sample_rate
        n = int(sr * frame_ms / 1000)
        with self.sd.RawInputStream(samplerate=sr, blocksize=n, dtype="int16",
                                    channels=1) as stream:
            while True:
                data, _ = stream.read(n)
                frame = bytes(data)
                yield frame, self.vad.is_speech(frame, sr)


def record_seconds(seconds: int, sample_rate: int = 16000) -> AudioClip:
    import sounddevice
    import numpy as np
    rec = sounddevice.rec(int(seconds * sample_rate), samplerate=sample_rate,
                          channels=1, dtype="int16")
    sounddevice.wait()
    return AudioClip(samples=rec.tobytes(), sample_rate=sample_rate)
