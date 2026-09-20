import io
import time
import wave
from typing import Any

from tvagent.audio import DuplexAudio, resample_pcm

_DEV_RATE = 48000  # full-duplex stream rate (mic + speaker share one clock)
_DRAIN_POLL = 0.02  # s between checks while the enqueued sentence plays out


class TappedTTS:
    """Wraps a TTS adapter and feeds playback into a DuplexAudio sink instead of
    owning its own output stream. The sink plays the far-end AND captures the mic
    in one callback, so the AEC gets time-aligned near/far (a separate mic +
    speaker stream drifts and defeats cancellation). play() blocks until the
    sentence has played so the orchestrator can poll barge-in during the audio.
    Everything except play/stop delegates to the inner adapter.
    """

    def __init__(self, inner: Any, sink: DuplexAudio, dev_rate: int = _DEV_RATE) -> None:
        self._inner = inner
        self._sink = sink
        self._dev = dev_rate
        self._stopped = False

    def speak(self, text: str) -> None:
        self._inner.speak(text)

    def synth(self, text: str) -> tuple[bytes, float]:
        result: tuple[bytes, float] = self._inner.synth(text)
        return result

    def play(self, pcm: bytes) -> None:
        if not pcm:
            return
        with wave.open(io.BytesIO(pcm)) as wf:
            raw = wf.readframes(wf.getnframes())
            src = wf.getframerate()
        out = resample_pcm(raw, src, self._dev)
        self._stopped = False
        self._sink.enqueue(out)
        # block until the sink has played it (or barge-in cleared it), so the
        # orchestrator keeps polling for interruption for the audio's duration.
        while not self._stopped and self._sink.pending() > 0:
            time.sleep(_DRAIN_POLL)

    def stop(self) -> None:
        self._stopped = True
        self._sink.clear()

    def set_voice(self, voice: str) -> None:
        self._inner.set_voice(voice)

    def warmup(self) -> None:
        warm = getattr(self._inner, "warmup", None)
        if callable(warm):
            warm()
