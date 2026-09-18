import io
import os
import wave
from collections.abc import Callable
from typing import Any

from tvagent.audio import resample_pcm

# Play at the device-native rate so a 16k barge-in mic can share the built-in
# device without a CoreAudio err=-50. See scripts/aec_calibrate.py. Tunable.
_PLAY_RATE = int(os.environ.get("TVAGENT_PLAY_RATE", "48000"))
_VOICE = "en_US-amy-medium"


class PiperTTS:
    def __init__(
        self,
        voice: str = _VOICE,
        _synth: Callable[[str], bytes] | None = None,
        _play: Callable[[bytes], None] | None = None,
        _stop: Callable[[], None] | None = None,
    ) -> None:
        self.voice = voice
        self._using_default_synth = _synth is None
        self._synth = _synth or self._default_synth
        self._play = _play or self._default_play
        self._stop = _stop or self._default_stop
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

    def set_voice(self, voice: str) -> None:
        # Console voice picker: drop the cached model so the next utterance
        # reloads (and, on the default synth, downloads) under the new voice.
        self.voice = voice
        self._model = None

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
            raw = wf.readframes(wf.getnframes())
            rate = wf.getframerate()
        data = npx.frombuffer(resample_pcm(raw, rate, _PLAY_RATE), dtype=np.int16)
        sd.play(data, _PLAY_RATE)  # device-native rate -> no duplex -50 with the barge mic
        sd.wait()

    def _default_stop(self) -> None:
        import sounddevice  # noqa: PLC0415 -- lazy

        sd: Any = sounddevice
        sd.stop()

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        self._play(self._synth(text))

    def synth(self, text: str) -> tuple[bytes, float]:
        # Return the WAV audio plus its playback duration (seconds), so callers can
        # pace an on-screen caption to the spoken length.
        if not text.strip():
            return b"", 0.0
        pcm = self._synth(text)
        with wave.open(io.BytesIO(pcm)) as wf:
            duration = wf.getnframes() / float(wf.getframerate())
        return pcm, duration

    def play(self, pcm: bytes) -> None:
        if pcm:
            self._play(pcm)

    def stop(self) -> None:
        self._stop()
