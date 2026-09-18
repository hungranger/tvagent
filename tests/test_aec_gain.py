from typing import Any

import numpy

from tvagent.adapters.aec_gain import EchoGainCanceller

np: Any = numpy


def _pcm(arr: Any) -> bytes:
    return arr.astype(np.int16).tobytes()


def _rms(pcm: bytes) -> float:
    a = np.frombuffer(pcm, np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(a * a))) if len(a) else 0.0


def test_adapts_to_cancel_scaled_echo() -> None:
    # Pure echo: the mic hears only the assistant's playback, scaled by the room.
    # The adaptive gain should converge and drive the cleaned output toward silence.
    rng = np.random.default_rng(0)
    far = rng.integers(-8000, 8000, size=480)
    near = (0.6 * far).astype(np.int16)  # echo = 0.6 * far, no talker
    aec = EchoGainCanceller()
    clean = b""
    for _ in range(40):  # feed the same echo repeatedly; gain converges
        clean = aec.process(_pcm(near), _pcm(far))
    assert _rms(clean) < 0.2 * _rms(_pcm(near))  # echo largely removed


def test_preserves_speech_over_echo() -> None:
    rng = np.random.default_rng(1)
    far = rng.integers(-8000, 8000, size=480)
    speech = rng.integers(-6000, 6000, size=480)
    near = (0.6 * far + speech).astype(np.int16)
    aec = EchoGainCanceller()
    clean = b""
    for _ in range(40):
        clean = aec.process(_pcm(near), _pcm(far))
    # the talker survives: cleaned output keeps most of the speech energy
    assert _rms(clean) > 0.5 * _rms(_pcm(speech.astype(np.int16)))
