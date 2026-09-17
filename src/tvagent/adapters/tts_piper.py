import io
import wave
from collections.abc import Callable
from typing import Any

_VOICE = "en_US-amy-medium"


class PiperTTS:
    def __init__(
        self,
        voice: str = _VOICE,
        _synth: Callable[[str], bytes] | None = None,
        _play: Callable[[bytes], None] | None = None,
    ) -> None:
        self.voice = voice
        self._using_default_synth = _synth is None
        self._synth = _synth or self._default_synth
        self._play = _play or self._default_play
        self._model: Any = None

    def _load_model(self) -> Any:
        import importlib  # noqa: PLC0415 -- lazy
        from pathlib import Path  # noqa: PLC0415 -- lazy

        import piper  # noqa: PLC0415 -- lazy

        pp: Any = piper
        dv: Any = importlib.import_module("piper.download_voices")
        cache = Path.home() / ".cache" / "tvagent" / "piper"
        onnx = cache / f"{self.voice}.onnx"
        if not onnx.exists():
            cache.mkdir(parents=True, exist_ok=True)
            dv.download_voice(self.voice, cache)
        return pp.PiperVoice.load(onnx)

    def warmup(self) -> None:
        # Download+load the Piper voice at boot so the first turn doesn't pay for it.
        if self._using_default_synth and self._model is None:
            self._model = self._load_model()

    def _default_synth(self, text: str) -> bytes:
        if self._model is None:
            self._model = self._load_model()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            self._model.synthesize_wav(text, wf)
        return buf.getvalue()

    def _default_play(self, pcm: bytes) -> None:
        import numpy as np  # noqa: PLC0415 -- lazy
        import sounddevice  # noqa: PLC0415 -- lazy

        sd: Any = sounddevice
        npx: Any = np
        with wave.open(io.BytesIO(pcm)) as wf:
            data = npx.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
            sd.play(data, wf.getframerate())
            sd.wait()

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        self._play(self._synth(text))
