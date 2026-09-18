import wave
from pathlib import Path
from typing import Any

import numpy as np

from tvagent.adapters.stt_parakeet import ParakeetSTT
from tvagent.core.models import AudioClip


class _FakeModel:
    def __init__(self) -> None:
        self.path: str | None = None
        self.saw_wav = False

    def transcribe(self, path: str, **_kw: Any) -> Any:
        self.path = str(path)
        # the adapter must hand parakeet a real, readable 16k mono wav
        with wave.open(str(path)) as w:
            self.saw_wav = w.getframerate() == 16000 and w.getnchannels() == 1
        return type("R", (), {"text": "  hello world  "})()


def test_transcribe_writes_wav_and_returns_text() -> None:
    fake = _FakeModel()
    stt = ParakeetSTT(_model=fake)
    pcm = np.array([0, 16384, -16384], dtype=np.int16).tobytes()
    out = stt.transcribe(AudioClip(samples=pcm, sample_rate=16000))
    assert out == "hello world"
    assert fake.path is not None and Path(fake.path).suffix == ".wav"
    assert fake.saw_wav  # 16 kHz mono handed to parakeet
