from collections.abc import Iterator
from typing import Any

import numpy

from tvagent.adapters.aec_gain import EchoGainCanceller
from tvagent.adapters.bargein_vad import VadBargeIn
from tvagent.audio import PlaybackReference

np: Any = numpy  # numpy's partial stubs trip pyright strict; treat as Any in tests


class _Frames:
    """Fake mic source: yields a fixed list of (frame, is_speech) pairs."""

    def __init__(self, frames: list[tuple[bytes, bool]]) -> None:
        self._frames = frames

    def frames(self) -> Iterator[tuple[bytes, bool]]:
        yield from self._frames


def _drain(det: VadBargeIn) -> None:
    """Wait for the (finite-source) listen thread to run to completion."""
    t = det._thread  # pyright: ignore[reportPrivateUsage]
    assert t is not None
    t.join(2.0)


def test_speaking_flags_after_consecutive_speech_frames() -> None:
    src = _Frames([(b"", False), (b"", True), (b"", True), (b"", True)])
    det = VadBargeIn(onset_frames=3, _source=src)
    det.arm()
    _drain(det)
    assert det.speaking() is True


def test_no_speaking_when_speech_not_sustained() -> None:
    # isolated speech frames (< onset in a row) must not count as barge-in
    src = _Frames([(b"", True), (b"", False), (b"", True), (b"", False)])
    det = VadBargeIn(onset_frames=3, _source=src)
    det.arm()
    _drain(det)
    assert det.speaking() is False


def test_disarm_resets_and_is_safe() -> None:
    src = _Frames([(b"", False)])
    det = VadBargeIn(onset_frames=3, _source=src)
    det.arm()
    det.disarm()
    assert det.speaking() is False


class _BoomSource:
    def frames(self) -> Iterator[tuple[bytes, bool]]:
        raise RuntimeError("mic busy")  # raises when the listen loop calls frames()


def _aec_frames(far: Any, near: Any, n: int) -> tuple[Any, PlaybackReference]:
    ref = PlaybackReference()
    frames: list[tuple[bytes, bool]] = []
    for _ in range(n):
        ref.write(far.tobytes())  # far-end for this frame
        frames.append((near.tobytes(), True))  # raw is_speech True (it hears the assistant)
    return _Frames(frames), ref


def test_double_talk_gate_ignores_quiet_residual_fires_on_loud() -> None:
    # The AEC-path speech test is on RESIDUAL ENERGY, not webrtcvad (which flags
    # even the quiet cancelled residual as speech). Quiet residual = echo, not barge.
    det = VadBargeIn(_source=_Frames([]), aec=EchoGainCanceller(), reference=PlaybackReference())
    loud = (np.ones(480) * 2000).astype(np.int16).tobytes()
    quiet = (np.ones(480) * 50).astype(np.int16).tobytes()
    assert det._double_talk(loud, quiet) is False  # pyright: ignore[reportPrivateUsage]
    assert det._double_talk(loud, loud) is True  # pyright: ignore[reportPrivateUsage]


def test_aec_no_false_barge_on_pure_echo() -> None:
    # near == the assistant's own playback (self-hearing). The canceller drives the
    # residual down; the energy gate must NOT fire.
    rng = np.random.default_rng(0)
    far = rng.integers(-8000, 8000, 480).astype(np.int16)
    near = (0.6 * far).astype(np.int16)  # room echo of the playback
    src, ref = _aec_frames(far, near, 10)
    det = VadBargeIn(onset_frames=3, _source=src, aec=EchoGainCanceller(), reference=ref)
    det.arm()
    _drain(det)
    assert det.speaking() is False


def test_aec_barge_on_speech_over_echo() -> None:
    rng = np.random.default_rng(1)
    far = rng.integers(-8000, 8000, 480).astype(np.int16)
    speech = rng.integers(-6000, 6000, 480).astype(np.int16)
    near = (0.6 * far + speech).astype(np.int16)  # user talks over the echo
    src, ref = _aec_frames(far, near, 10)
    det = VadBargeIn(onset_frames=3, _source=src, aec=EchoGainCanceller(), reference=ref)
    det.arm()
    _drain(det)
    assert det.speaking() is True


def test_listen_error_is_captured_not_swallowed() -> None:
    # A mic failure in the background thread must be recorded (so the console can
    # show why barge-in isn't working), not silently kill the thread.
    det = VadBargeIn(onset_frames=3, _source=_BoomSource())
    det.arm()
    _drain(det)
    assert det.speaking() is False
    assert det.error is not None and "mic busy" in det.error
