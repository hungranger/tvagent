from typing import Any

import numpy

from tvagent.adapters.aec_fdaf import FdafEchoCanceller

np: Any = numpy


def _rms(a: Any) -> float:
    a = a.astype(float)
    return float(np.sqrt(np.mean(a * a))) if len(a) else 0.0


def _i16(a: Any) -> bytes:
    return np.clip(a, -32768, 32767).astype(np.int16).tobytes()


def test_fdaf_cancels_multitap_reverberant_echo() -> None:
    # Real acoustic echo = room impulse (delay + multipath) convolved with far.
    # A scalar (1-tap) canceller gets ~0-10%; a multi-tap FDAF must do far better.
    rng = np.random.default_rng(0)
    far = (rng.standard_normal(16000 * 3) * 3000).astype(np.float64)
    h = np.zeros(3600)  # room impulse: ~200ms delay + decaying multipath
    h[3200], h[3300], h[3400], h[3500] = 0.6, 0.3, 0.18, 0.09
    echo = np.convolve(far, h)[: len(far)]  # near = pure echo, no talker

    aec = FdafEchoCanceller(taps=4096, mu=0.3)
    b = 480
    out: list[bytes] = []
    for i in range(0, len(far) - b, b):
        out.append(aec.process(_i16(echo[i : i + b]), _i16(far[i : i + b])))
    clean = np.frombuffer(b"".join(out), np.int16).astype(np.float64)
    tail = slice(len(clean) // 2, None)  # after convergence
    near_tail = echo[: len(clean)][tail]
    reduction = 1 - _rms(clean[tail]) / _rms(near_tail)
    assert reduction > 0.6, f"only {reduction:.0%} cancelled"


def test_fdaf_preserves_talker_over_echo() -> None:
    rng = np.random.default_rng(1)
    far = (rng.standard_normal(16000 * 3) * 3000).astype(np.float64)
    h = np.zeros(3300)
    h[3200] = 0.6
    echo = np.convolve(far, h)[: len(far)]
    talker = (rng.standard_normal(16000 * 3) * 2000).astype(np.float64)
    near = echo + talker

    aec = FdafEchoCanceller(taps=4096, mu=0.3)
    b = 480
    out: list[bytes] = []
    for i in range(0, len(far) - b, b):
        out.append(aec.process(_i16(near[i : i + b]), _i16(far[i : i + b])))
    clean = np.frombuffer(b"".join(out), np.int16).astype(np.float64)
    tail = slice(len(clean) // 2, None)
    # talker energy largely retained after cancelling the echo
    assert _rms(clean[tail]) > 0.6 * _rms(talker[: len(clean)][tail])
