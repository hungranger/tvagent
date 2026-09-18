import io
import os
import wave
from collections.abc import Callable
from typing import Any

from tvagent.audio import resample_pcm

# Play at the device-native rate so a 16k barge-in mic can share the built-in
# device without a CoreAudio err=-50 (Kokoro synthesizes at 24k). See
# scripts/aec_calibrate.py. Tunable per machine.
_PLAY_RATE = int(os.environ.get("TVAGENT_PLAY_RATE", "48000"))
_VOICE = "af_heart"  # Kokoro's flagship voice
_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
_MODEL_URL = f"{_RELEASE}/kokoro-v1.0.onnx"
_VOICES_URL = f"{_RELEASE}/voices-v1.0.bin"


class KokoroTTS:
    """TTS via Kokoro-82M (kokoro-onnx). Much more natural than Piper, still
    real-time on-device. Opt-in (TVAGENT_TTS=kokoro); default stays Piper.
    Same port as PiperTTS: speak / synth(audio, duration) / play, so the karaoke
    caption pacing keeps working.
    """

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
        import urllib.request  # noqa: PLC0415 -- lazy
        from pathlib import Path  # noqa: PLC0415 -- lazy

        import kokoro_onnx  # noqa: PLC0415 -- lazy

        kk: Any = kokoro_onnx
        cache = Path.home() / ".cache" / "tvagent" / "kokoro"
        cache.mkdir(parents=True, exist_ok=True)
        onnx = cache / "kokoro-v1.0.onnx"
        voices = cache / "voices-v1.0.bin"
        # URLs are fixed https release constants (not user input), so semgrep's
        # dynamic-urllib file:// SSRF concern does not apply here.
        if not onnx.exists():
            urllib.request.urlretrieve(_MODEL_URL, onnx)  # nosemgrep
        if not voices.exists():
            urllib.request.urlretrieve(_VOICES_URL, voices)  # nosemgrep
        return kk.Kokoro(str(onnx), str(voices))

    def warmup(self) -> None:
        if self._using_default_synth and self._model is None:
            self._model = self._load_model()

    def _default_synth(self, text: str) -> bytes:
        import numpy as np  # noqa: PLC0415 -- lazy

        if self._model is None:
            self._model = self._load_model()
        npx: Any = np
        samples, rate = self._model.create(text, voice=self.voice, lang="en-us")
        pcm16 = (npx.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(pcm16.tobytes())
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

    def set_voice(self, voice: str) -> None:
        # All voices live in one voices.bin, so no model reload is needed.
        self.voice = voice

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        self._play(self._synth(text))

    def synth(self, text: str) -> tuple[bytes, float]:
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
