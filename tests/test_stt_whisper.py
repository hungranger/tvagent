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
    def transcribe(self, audio: "np.ndarray[Any, Any]", **kw: Any) -> tuple[list[_Seg], None]:
        return ([_Seg("hello there")], None)


def test_transcribe_joins_segments():
    stt = WhisperSTT(_model=_StubModel())
    out = stt.transcribe(AudioClip(samples=b"\x00\x00", sample_rate=16000))
    assert out == "hello there"


@pytest.mark.component
def test_real_whisper_on_fixture():
    pytest.importorskip("faster_whisper")
    f = pathlib.Path("tests/fixtures/hello.wav")
    if not f.exists():
        pytest.skip("record tests/fixtures/hello.wav saying 'hello there'")
    with wave.open(str(f)) as w:
        clip = AudioClip(
            samples=w.readframes(w.getnframes()), sample_rate=w.getframerate()
        )
    text = WhisperSTT(model_size="base").transcribe(clip).lower()
    assert "hello" in text  # F4: within tolerance
