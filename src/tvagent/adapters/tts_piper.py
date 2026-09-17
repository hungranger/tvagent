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
        self._synth = _synth or self._default_synth
        self._play = _play or self._default_play
        self._model: Any = None

    def _default_synth(self, text: str) -> bytes:
        import piper  # noqa: PLC0415 -- lazy
        pp: Any = piper
        if self._model is None:
            self._model = pp.PiperVoice.load(self.voice)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            self._model.synthesize(text, wf)
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
