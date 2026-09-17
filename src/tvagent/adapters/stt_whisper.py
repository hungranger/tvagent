from typing import Any

import numpy as np

from tvagent.core.models import AudioClip

_PCM_MAX = 32768.0
_MODEL_SIZE = "base"


class WhisperSTT:
    def __init__(self, model_size: str = _MODEL_SIZE, _model: Any = None) -> None:
        if _model is None:
            import faster_whisper  # noqa: PLC0415 -- lazy
            fw: Any = faster_whisper
            _model = fw.WhisperModel(model_size, device="cpu", compute_type="int8")
        self._model: Any = _model

    def transcribe(self, clip: AudioClip) -> str:
        npx: Any = np
        audio = npx.frombuffer(clip.samples, dtype=np.int16).astype(np.float32) / _PCM_MAX
        segments, _ = self._model.transcribe(audio, language="en")
        texts: list[str] = [s.text.strip() for s in segments]
        return " ".join(texts).strip()
