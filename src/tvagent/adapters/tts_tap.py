import io
import wave
from typing import Any

from tvagent.audio import PlaybackReference, resample_pcm

_AEC_RATE = 16000  # far-end reference lives at the AEC/VAD rate


class TappedTTS:
    """Wraps a TTS adapter and, on each play, writes the played audio (downsampled
    to 16k) into a PlaybackReference — the AEC far-end. Lets the barge-in detector
    subtract the assistant's own voice. Transparent for every other call.
    """

    def __init__(self, inner: Any, reference: PlaybackReference) -> None:
        self._inner = inner
        self._ref = reference

    def speak(self, text: str) -> None:
        self._inner.speak(text)

    def synth(self, text: str) -> tuple[bytes, float]:
        result: tuple[bytes, float] = self._inner.synth(text)
        return result

    def play(self, pcm: bytes) -> None:
        if pcm:
            with wave.open(io.BytesIO(pcm)) as wf:
                raw = wf.readframes(wf.getnframes())
                rate = wf.getframerate()
            self._ref.write(resample_pcm(raw, rate, _AEC_RATE))  # far-end for the AEC
        self._inner.play(pcm)

    def stop(self) -> None:
        self._inner.stop()

    def set_voice(self, voice: str) -> None:
        self._inner.set_voice(voice)

    def warmup(self) -> None:
        warm = getattr(self._inner, "warmup", None)
        if callable(warm):
            warm()
