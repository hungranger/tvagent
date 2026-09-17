import pytest
from tvagent.core.models import AudioClip
from tvagent.adapters.stt_whisper import WhisperSTT


class _Seg:
    def __init__(self, t):
        self.text = t


class _StubModel:
    def transcribe(self, audio, **kw):
        return ([_Seg("hello there")], None)


def test_transcribe_joins_segments():
    stt = WhisperSTT(_model=_StubModel())
    out = stt.transcribe(AudioClip(samples=b"\x00\x00", sample_rate=16000))
    assert out == "hello there"


@pytest.mark.component
def test_real_whisper_on_fixture():
    pytest.importorskip("faster_whisper")
    import wave
    import pathlib

    f = pathlib.Path("tests/fixtures/hello.wav")
    if not f.exists():
        pytest.skip("record tests/fixtures/hello.wav saying 'hello there'")
    with wave.open(str(f)) as w:
        clip = AudioClip(
            samples=w.readframes(w.getnframes()), sample_rate=w.getframerate()
        )
    text = WhisperSTT(model_size="base").transcribe(clip).lower()
    assert "hello" in text  # F4: within tolerance
