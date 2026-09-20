import io
import wave
from typing import Any

from tvagent.audio import PlaybackReference, resample_pcm

_DEV_RATE = 48000  # device-native output rate (avoids the duplex -50); also far-end rate
_BLOCK = 1024  # output samples per device write (~21ms @48k)


class TappedTTS:
    """Wraps a TTS adapter and OWNS playback so it can stream the far-end in real
    time: as each block is fed to the output device, the matching block (at 16k)
    is written to the PlaybackReference. That keeps the AEC far-end time-aligned
    with what the mic actually hears — unlike writing the whole clip up front.
    Everything except play/stop delegates to the inner adapter.
    """

    def __init__(
        self,
        inner: Any,
        reference: PlaybackReference,
        dev_rate: int = _DEV_RATE,
        block: int = _BLOCK,
        _stream_factory: Any = None,
    ) -> None:
        self._inner = inner
        self._ref = reference
        self._dev = dev_rate
        self._block = block
        self._stream_factory = _stream_factory or self._default_stream
        self._stopped = False
        self._stream: Any = None

    def _default_stream(self, dev_rate: int) -> Any:  # pragma: no cover - real device I/O
        import sounddevice  # noqa: PLC0415 -- lazy

        sd: Any = sounddevice
        stream = sd.OutputStream(samplerate=dev_rate, channels=1, dtype="int16")
        stream.start()
        return stream

    def speak(self, text: str) -> None:
        self._inner.speak(text)

    def synth(self, text: str) -> tuple[bytes, float]:
        result: tuple[bytes, float] = self._inner.synth(text)
        return result

    def play(self, pcm: bytes) -> None:
        if not pcm:
            return
        import numpy as np  # noqa: PLC0415 -- lazy

        npx: Any = np
        with wave.open(io.BytesIO(pcm)) as wf:
            raw = wf.readframes(wf.getnframes())
            src = wf.getframerate()
        out = npx.frombuffer(resample_pcm(raw, src, self._dev), dtype=np.int16)
        self._stopped = False
        stream = self._stream_factory(self._dev)
        self._stream = stream
        try:
            oi, n = 0, len(out)
            while oi < n and not self._stopped:
                nxt = min(oi + self._block, n)
                # far-end = exactly what plays, at device rate. Kept full-band (no
                # downsample to 16k): the AEC runs at 48k so it can use the coherent
                # high band the resampler would alias away.
                self._ref.write(out[oi:nxt].tobytes())
                try:
                    stream.write(out[oi:nxt])
                except Exception:  # barge-in stop() aborts the stream mid-write
                    if self._stopped:
                        break  # expected: barge-in aborted the stream (PortAudio -9986)
                    raise
                oi = nxt
        finally:
            stream.close()
            self._stream = None

    def stop(self) -> None:
        self._stopped = True
        stream = self._stream
        if stream is not None:
            abort = getattr(stream, "abort", None)  # pragma: no cover - real device I/O
            if callable(abort):
                abort()

    def set_voice(self, voice: str) -> None:
        self._inner.set_voice(voice)

    def warmup(self) -> None:
        warm = getattr(self._inner, "warmup", None)
        if callable(warm):
            warm()
