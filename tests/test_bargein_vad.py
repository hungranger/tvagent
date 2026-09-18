from collections.abc import Iterator
from typing import Any

import numpy

from tvagent.adapters.bargein_vad import VadBargeIn
from tvagent.audio import PlaybackReference

np: Any = numpy  # numpy's partial stubs trip pyright strict; treat as Any in tests


class _SubAEC:
    """Fake echo canceller: clean = near - far (int16). Proves cancellation, not
    just passthrough."""

    def process(self, near: bytes, far: bytes) -> bytes:
        a = np.frombuffer(near, dtype=np.int16).astype(np.int32)
        b = np.frombuffer(far, dtype=np.int16).astype(np.int32)
        n = min(len(a), len(b))
        return (a[:n] - b[:n]).astype(np.int16).tobytes()


def _pcm(*samples: int) -> bytes:
    return np.array(samples, dtype=np.int16).tobytes()


def _has_signal(frame: bytes) -> bool:
    return frame.strip(b"\x00") != b""


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


def test_aec_cancels_pure_echo_so_no_false_barge() -> None:
    # Self-hearing on speakers: the mic frame IS the assistant's playback, and the
    # raw VAD flags it as speech. With AEC subtracting the played reference, the
    # cleaned frame is silence -> no barge fires.
    echo = _pcm(100, 200, 300)
    ref = PlaybackReference()
    ref.write(echo)  # far-end == what the mic hears
    src = _Frames([(echo, True)])  # raw is_speech=True (it hears the assistant)
    det = VadBargeIn(onset_frames=1, _source=src, aec=_SubAEC(), reference=ref, _vad=_has_signal)
    det.arm()
    _drain(det)
    assert det.speaking() is False  # echo cancelled -> not a barge-in


def test_aec_keeps_real_speech_over_echo_so_barge_fires() -> None:
    far = _pcm(100, 200, 300)
    mixed = np.frombuffer(far, np.int16) + np.frombuffer(_pcm(500, 600, 700), np.int16)
    near = mixed.astype(np.int16).tobytes()  # mic hears speech on top of the echo
    ref = PlaybackReference()
    ref.write(far)
    src = _Frames([(near, True)])
    det = VadBargeIn(onset_frames=1, _source=src, aec=_SubAEC(), reference=ref, _vad=_has_signal)
    det.arm()
    _drain(det)
    assert det.speaking() is True  # speech survives cancellation -> barge


def test_listen_error_is_captured_not_swallowed() -> None:
    # A mic failure in the background thread must be recorded (so the console can
    # show why barge-in isn't working), not silently kill the thread.
    det = VadBargeIn(onset_frames=3, _source=_BoomSource())
    det.arm()
    _drain(det)
    assert det.speaking() is False
    assert det.error is not None and "mic busy" in det.error
