import pathlib
import wave
from typing import Any

import numpy as np
import pytest

from tvagent.adapters.stt_whisper import WhisperSTT
from tvagent.core.models import AudioClip


class _Seg:
    def __init__(self, t: str) -> None:
        self.text = t


class _StubModel:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def transcribe(self, audio: "np.ndarray[Any, Any]", **kw: Any) -> tuple[list[_Seg], None]:
        self.calls.append((audio, kw))
        return ([_Seg("hello"), _Seg("there")], None)


def test_transcribe_joins_segments():
    model = _StubModel()
    stt = WhisperSTT(_model=model)
    samples = np.array([0, 16384], dtype=np.int16).tobytes()
    out = stt.transcribe(AudioClip(samples=samples, sample_rate=16000))
    assert out == "hello there"  # pins the " " join separator across segments
    audio, kw = model.calls[0]
    assert kw == {"language": "en"}
    assert audio.tolist() == [0.0, 0.5]  # pins int16->float32 scaling by /_PCM_MAX
    assert audio.dtype == np.float32


@pytest.mark.component
def test_real_whisper_on_fixture():
    pytest.importorskip("faster_whisper")
    f = pathlib.Path("tests/fixtures/hello.wav")
    if not f.exists():
        pytest.skip("record tests/fixtures/hello.wav saying 'hello there'")
    with wave.open(str(f)) as w:
        clip = AudioClip(samples=w.readframes(w.getnframes()), sample_rate=w.getframerate())
    text = WhisperSTT(model_size="base").transcribe(clip).lower()
    assert "hello" in text  # F4: within tolerance
