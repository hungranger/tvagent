"""Shared hardware audio source.

Lives below `adapters/` so both `audio_vad.py` and `wakeword_oww.py` can
import `MicSource` without one adapter importing the other.
"""

import queue
import threading
from collections.abc import Iterator
from typing import Any

_VAD_AGGRESSIVENESS = 2
_FRAME_MS = 30
_MS_PER_SEC = 1000
_DUPLEX_BLOCK = 1024  # samples per full-duplex callback (~21ms @48k)


def resample_pcm(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Linearly resample mono int16 PCM. Used to capture the mic at the device's
    native rate (avoids the CoreAudio same-device rate clash with playback) and
    downsample to 16 kHz for VAD/AEC. Identity when the rates match."""
    if not pcm or src_rate == dst_rate:
        return pcm
    import numpy as np  # noqa: PLC0415 -- lazy

    npx: Any = np
    a = npx.frombuffer(pcm, dtype=np.int16)
    n_out = len(a) * dst_rate // src_rate
    if n_out <= 0:
        return b""
    grid = npx.linspace(0, len(a) - 1, num=n_out)
    out = npx.interp(grid, npx.arange(len(a)), a).astype(np.int16)
    return bytes(out.tobytes())


class PlaybackReference:
    """The AEC far-end reference: a FIFO of the PCM the assistant is playing.
    The playback path writes what it plays; the barge-in detector reads the same
    bytes to subtract the assistant's own voice from the mic. Reads always return
    the requested size, zero-padding when nothing is buffered (silence), so a mic
    frame always has a matching far-end frame. Thread-safe: writer and reader run
    on different threads.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self._lock = threading.Lock()

    def write(self, pcm: bytes) -> None:
        with self._lock:
            self._buf.extend(pcm)

    def read(self, n: int) -> bytes:
        with self._lock:
            take = self._buf[:n]
            del self._buf[:n]
        return bytes(take).ljust(n, b"\x00")  # zero-pad to n = far-end silence

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()


class DuplexAudio:
    """One full-duplex stream: plays the queued far-end AND captures the mic in the
    SAME callback, so near[t] and far[t] share one clock. That alignment is what a
    two-stream mic+speaker setup can't give -- the play thread writes far ahead of
    real playback, so the AEC never lines echo up with reference. Here the callback
    writes the exact block it outputs to the far FIFO and the mic it captured to the
    near queue, one block at a time, so the detector reads matched near/far.

    Playback is fed via enqueue(); the barge detector uses this as its `_source`
    (frames()) and reads far from `.far`. The sd.Stream is created lazily so the
    callback logic is testable without hardware.
    """

    def __init__(
        self, rate: int = 16000, block: int = _DUPLEX_BLOCK, _stream_factory: Any = None
    ) -> None:
        self._rate = rate
        self._block = block
        self._pending = bytearray()  # far-end PCM waiting to play
        self._lock = threading.Lock()
        self._near: queue.Queue[bytes] = queue.Queue()
        self.far = PlaybackReference()  # far actually output, block-aligned with near
        self._stop = threading.Event()
        self._stream: Any = None
        self._stream_factory = _stream_factory or self._default_stream

    def enqueue(self, pcm: bytes) -> None:
        with self._lock:
            self._pending.extend(pcm)

    def clear(self) -> None:  # barge-in: drop the rest of the reply
        with self._lock:
            self._pending.clear()

    def pending(self) -> int:  # bytes of far-end still waiting to play
        with self._lock:
            return len(self._pending)

    def _callback(self, indata: Any, outdata: Any, frames: int, *_: Any) -> None:
        import numpy as np  # noqa: PLC0415 -- lazy

        npx: Any = np
        need = frames * 2  # int16 bytes
        with self._lock:
            far = bytes(self._pending[:need])
            del self._pending[:need]
        far = far.ljust(need, b"\x00")  # zero-pad = silence when nothing queued
        outdata[:, 0] = npx.frombuffer(far, dtype=np.int16)
        self.far.write(far)  # far output this instant
        self._near.put(bytes(indata))  # mic captured this instant -> same block

    def frames(self) -> Iterator[tuple[bytes, bool]]:
        while not self._stop.is_set():
            try:
                near = self._near.get(timeout=0.1)
            except queue.Empty:
                continue
            yield near, False  # is_speech unused on the AEC path

    def _default_stream(self, cb: Any) -> Any:  # pragma: no cover - real device I/O
        import sounddevice  # noqa: PLC0415 -- lazy

        sd: Any = sounddevice
        stream = sd.Stream(
            samplerate=self._rate,
            blocksize=self._block,
            dtype="int16",
            channels=1,
            callback=cb,
        )
        stream.start()
        return stream

    def start(self) -> None:  # pragma: no cover - real device I/O
        self._stop.clear()
        self._stream = self._stream_factory(self._callback)

    def stop(self) -> None:  # pragma: no cover - real device I/O
        self._stop.set()
        self.clear()
        stream = self._stream
        self._stream = None
        if stream is not None:
            stream.close()


class MicSource:
    def __init__(self, sample_rate: int, use_vad: bool = True) -> None:
        import sounddevice  # noqa: PLC0415 -- lazy: no mic/backend needed to test logic

        self.sample_rate = sample_rate
        self.sd: Any = sounddevice
        self.vad: Any = None
        if use_vad:  # webrtcvad only accepts 8/16/32k; the AEC path runs at 48k (off)
            import webrtcvad  # noqa: PLC0415 -- lazy

            wv: Any = webrtcvad
            self.vad = wv.Vad(_VAD_AGGRESSIVENESS)

    def frames(self) -> Iterator[tuple[bytes, bool]]:
        frame_ms, sr = _FRAME_MS, self.sample_rate
        n = int(sr * frame_ms / _MS_PER_SEC)
        with self.sd.RawInputStream(
            samplerate=sr, blocksize=n, dtype="int16", channels=1
        ) as stream:
            while True:
                data, _ = stream.read(n)
                frame: bytes = bytes(data)
                is_speech: bool = self.vad.is_speech(frame, sr) if self.vad else False
                yield frame, is_speech
