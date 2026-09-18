from typing import Any

import numpy

from tvagent.audio import resample_pcm

np: Any = numpy  # numpy's partial stubs trip pyright strict; treat as Any in tests


def _pcm(*s: int) -> bytes:
    return np.array(s, dtype=np.int16).tobytes()


def test_downsample_3to1_shrinks_length_and_keeps_first_sample() -> None:
    # 48k -> 16k mic capture: the mic must open at the device rate then downsample
    # for VAD/AEC (both want 16k).
    src = _pcm(0, 100, 200, 300, 400, 500)  # 6 samples
    out = np.frombuffer(resample_pcm(src, 48000, 16000), np.int16)
    assert len(out) == 2  # 6 * 16000/48000
    assert out[0] == 0  # anchored at the start


def test_same_rate_is_identity() -> None:
    src = _pcm(1, 2, 3, 4)
    assert resample_pcm(src, 16000, 16000) == src


def test_empty_stays_empty() -> None:
    assert resample_pcm(b"", 48000, 16000) == b""
