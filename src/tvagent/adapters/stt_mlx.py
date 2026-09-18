from typing import Any

import numpy as np

from tvagent.core.models import AudioClip

_PCM_MAX = 32768.0
_MODEL = "mlx-community/whisper-base-mlx"  # Metal-accelerated whisper on Apple Silicon


class MlxWhisperSTT:
    """STT via mlx-whisper (Apple MLX / Metal GPU) — much faster than CPU
    faster-whisper on M-series. Opt-in (mac only); default STT stays faster-whisper.

    `_model` injects the transcribe callable for tests (named to match the
    coverage-excluded real-load guard used across the adapters).
    """

    def __init__(self, model: str = _MODEL, _model: Any = None) -> None:
        self.model = model
        if _model is None:
            import mlx_whisper  # noqa: PLC0415 -- lazy, mac-only

            mw: Any = mlx_whisper
            _model = mw.transcribe
        self._transcribe: Any = _model

    def transcribe(self, clip: AudioClip) -> str:
        npx: Any = np
        audio = npx.frombuffer(clip.samples, dtype=np.int16).astype(np.float32) / _PCM_MAX
        result = self._transcribe(audio, path_or_hf_repo=self.model)
        return str(result["text"]).strip()
