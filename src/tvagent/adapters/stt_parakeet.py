import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from tvagent.core.models import AudioClip

_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"  # SOTA English ASR, ~1.2GB, runs on MLX


class ParakeetSTT:
    """STT via NVIDIA Parakeet on Apple MLX (parakeet-mlx). Top-of-leaderboard
    English accuracy, fast on Apple Silicon. Opt-in, mac-only; default stays
    faster-whisper.

    MLX streams are thread-bound: a model loaded on one thread cannot be run from
    another (RuntimeError "no Stream in current thread"). The console drives turns
    on a background listen thread, so we pin the model load AND every inference to
    one dedicated worker thread. `_model` injects a loaded model for tests.
    """

    def __init__(self, model: str = _MODEL, _model: Any = None) -> None:
        self.model = model
        self._model: Any = _model
        # single worker: all MLX work (import, load, inference) stays on one thread
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="parakeet-mlx")

    def transcribe(self, clip: AudioClip) -> str:
        return self._pool.submit(self._transcribe, clip).result()

    def _transcribe(self, clip: AudioClip) -> str:
        if self._model is None:
            import parakeet_mlx  # noqa: PLC0415 -- lazy, mac-only

            pm: Any = parakeet_mlx
            self._model = pm.from_pretrained(self.model)
        # parakeet-mlx transcribes a file, so write the clip to a temp 16k mono wav.
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(clip.sample_rate)
                wf.writeframes(clip.samples)
            result = self._model.transcribe(Path(tmp.name))
        return str(result.text).strip()
