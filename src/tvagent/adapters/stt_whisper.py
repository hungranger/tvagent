import numpy as np
from tvagent.core.models import AudioClip


class WhisperSTT:
    def __init__(self, model_size: str = "base", _model=None):
        if _model is None:
            from faster_whisper import WhisperModel
            _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self._model = _model

    def transcribe(self, clip: AudioClip) -> str:
        audio = np.frombuffer(clip.samples, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(audio, language="en")
        return " ".join(s.text.strip() for s in segments).strip()
