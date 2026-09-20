from typing import Any

_MU = 0.5  # NLMS step size
_EPS = 1e-6


class EchoGainCanceller:
    """Adaptive single-gain echo canceller (EchoCanceller port).

    Models the echo as ``gain * far`` and adapts ``gain`` by NLMS, returning
    ``near - gain*far``. Cancels the dominant direct playback path so the
    barge-in detector stops hearing the assistant's own voice on speakers.
    Pure numpy, real-time, no model download — a stand-in for a full DTLN model,
    which can replace it behind the same port later. Far-end alignment (the
    ~105ms round-trip delay) is handled upstream by the PlaybackReference read.
    """

    def __init__(self, mu: float = _MU) -> None:
        self._gain = 0.0
        self._mu = mu

    def process(self, near: bytes, far: bytes) -> bytes:
        import numpy as np  # noqa: PLC0415 -- lazy

        npx: Any = np
        n = npx.frombuffer(near, dtype=np.int16).astype(np.float64)
        f = npx.frombuffer(far, dtype=np.int16).astype(np.float64)
        length = min(len(n), len(f))
        if length == 0:
            return near
        n, f = n[:length], f[:length]
        err = n - self._gain * f
        self._gain += self._mu * float(npx.dot(err, f)) / (float(npx.dot(f, f)) + _EPS)
        clean = npx.clip(n - self._gain * f, -32768, 32767).astype(np.int16)
        return bytes(clean.tobytes())
