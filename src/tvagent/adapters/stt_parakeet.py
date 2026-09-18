import tempfile
import wave
from pathlib import Path
from typing import Any

from tvagent.core.models import AudioClip

_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"  # SOTA English ASR, ~1.2GB, runs on MLX


class ParakeetSTT:
    """STT via NVIDIA Parakeet on Apple MLX (parakeet-mlx). Top-of-leaderboard
    English accuracy, fast on Apple Silicon. Opt-in, mac-only; default stays
    faster-whisper. `_model` injects the loaded model for tests (the real load
    lives in the coverage-excluded guard).
    """

    def __init__(self, model: str = _MODEL, _model: Any = None) -> None:
        if _model is None:
            import parakeet_mlx  # noqa: PLC0415 -- lazy, mac-only

            pm: Any = parakeet_mlx
            _model = pm.from_pretrained(model)
        self._model: Any = _model

    def transcribe(self, clip: AudioClip) -> str:
        # parakeet-mlx transcribes a file, so write the clip to a temp 16k mono wav.
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(clip.sample_rate)
                wf.writeframes(clip.samples)
            result = self._model.transcribe(Path(tmp.name))
        return str(result.text).strip()
