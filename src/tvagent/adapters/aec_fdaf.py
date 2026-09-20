import os
from typing import Any

# Frequency-domain block adaptive filter (constrained overlap-save FDAF) — a real
# multi-tap acoustic echo canceller. A single-gain canceller gets ~0-10% on a
# reverberant room echo because the echo is spread over the round-trip delay +
# reverb (~200ms); this learns a filter that spans it (default 4096 taps @16k =
# 256ms). EchoCanceller port: process(near, far) -> cleaned near.
_TAPS = int(os.environ.get("TVAGENT_AEC_TAPS", "4096"))
_MU = float(os.environ.get("TVAGENT_AEC_MU", "0.3"))  # 0.5 diverges on colored speech
_LAMBDA = 0.9  # running-power smoothing for the per-bin NLMS step


class FdafEchoCanceller:
    def __init__(self, taps: int = _TAPS, mu: float = _MU) -> None:
        import numpy as np  # noqa: PLC0415 -- lazy

        npx: Any = np
        self._np = npx
        self._taps = taps
        self._mu = mu
        n = 1
        while n < taps * 2:
            n <<= 1
        self._n = n  # FFT size, pow2 >= 2*taps
        self._w = npx.zeros(n // 2 + 1, dtype=npx.complex128)  # filter, freq domain (rfft)
        self._farhist = npx.zeros(n, dtype=npx.float64)  # last n far samples
        self._power = npx.zeros(n // 2 + 1, dtype=npx.float64)  # running per-bin far power

    def process(self, near: bytes, far: bytes) -> bytes:
        npx = self._np
        n_arr = npx.frombuffer(near, dtype=npx.int16).astype(npx.float64)
        f_arr = npx.frombuffer(far, dtype=npx.int16).astype(npx.float64)
        b = min(len(n_arr), len(f_arr))
        if b == 0:
            return near
        n_arr, f_arr = n_arr[:b], f_arr[:b]
        # slide far history, FFT the window, estimate echo (overlap-save valid tail)
        self._farhist = npx.concatenate([self._farhist[b:], f_arr])
        x = npx.fft.rfft(self._farhist)
        echo = npx.fft.irfft(self._w * x, n=self._n)[-b:]
        err = n_arr - echo
        # NLMS update in the frequency domain, normalized by a per-bin RUNNING
        # power (instantaneous |X|^2 is unstable; a global norm never converges).
        e_full = npx.concatenate([npx.zeros(self._n - b), err])
        e_freq = npx.fft.rfft(e_full)
        self._power = _LAMBDA * self._power + (1.0 - _LAMBDA) * npx.abs(x) ** 2
        reg = 1e-3 * float(npx.mean(self._power)) + 1e-9
        # guard: the running power lags speech onsets, so |X|^2 can exceed it and
        # make the step >mu -> divergence. Normalize by whichever is larger.
        denom = npx.maximum(self._power, npx.abs(x) ** 2) + reg
        self._w += self._mu * npx.conj(x) * e_freq / denom
        # gradient constraint: keep the filter causal, length `taps`
        w_time = npx.fft.irfft(self._w, n=self._n)
        w_time[self._taps :] = 0.0
        self._w = npx.fft.rfft(w_time)
        clean: bytes = npx.clip(err, -32768, 32767).astype(npx.int16).tobytes()
        return clean
