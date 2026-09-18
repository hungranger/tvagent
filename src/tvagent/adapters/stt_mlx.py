from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from tvagent.core.models import AudioClip

_PCM_MAX = 32768.0
_MODEL = "mlx-community/whisper-base-mlx"  # Metal-accelerated whisper on Apple Silicon


class MlxWhisperSTT:
    """STT via mlx-whisper (Apple MLX / Metal GPU). Opt-in, mac-only; default
    stays faster-whisper.

    MLX streams are thread-bound, and the console drives turns on a background
    thread, so all MLX work (import, load, inference) is pinned to one dedicated
    worker thread. `_model` injects the transcribe callable for tests.
    """

    def __init__(self, model: str = _MODEL, _model: Any = None) -> None:
        self.model = model
        self._transcribe_fn: Any = _model
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx-whisper")

    def transcribe(self, clip: AudioClip) -> str:
        return self._pool.submit(self._transcribe, clip).result()

    def _transcribe(self, clip: AudioClip) -> str:
        if self._transcribe_fn is None:
            import mlx_whisper  # noqa: PLC0415 -- lazy, mac-only

            mw: Any = mlx_whisper
            self._transcribe_fn = mw.transcribe
        npx: Any = np
        audio = npx.frombuffer(clip.samples, dtype=np.int16).astype(np.float32) / _PCM_MAX
        result = self._transcribe_fn(audio, path_or_hf_repo=self.model)
        return str(result["text"]).strip()
