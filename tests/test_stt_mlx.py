from typing import Any

import numpy as np

from tvagent.adapters.stt_mlx import MlxWhisperSTT
from tvagent.core.models import AudioClip


def test_transcribe_normalizes_pcm_and_returns_text() -> None:
    seen: dict[str, Any] = {}

    def fake(audio: Any, path_or_hf_repo: str | None = None) -> dict[str, str]:
        seen["audio"] = audio
        seen["repo"] = path_or_hf_repo
        return {"text": "  hi there  "}

    pcm = np.array([0, 16384, -16384], dtype=np.int16).tobytes()
    stt = MlxWhisperSTT(model="mlx-community/whisper-base-mlx", _model=fake)
    assert stt.transcribe(AudioClip(samples=pcm, sample_rate=16000)) == "hi there"
    assert seen["repo"] == "mlx-community/whisper-base-mlx"
    assert seen["audio"].dtype == np.float32  # int16 PCM converted to normalized float32
    assert abs(float(seen["audio"][1]) - 0.5) < 1e-3  # 16384 / 32768
