from collections.abc import Iterator

from tvagent.adapters.bargein_vad import VadBargeIn


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


def test_listen_error_is_captured_not_swallowed() -> None:
    # A mic failure in the background thread must be recorded (so the console can
    # show why barge-in isn't working), not silently kill the thread.
    det = VadBargeIn(onset_frames=3, _source=_BoomSource())
    det.arm()
    _drain(det)
    assert det.speaking() is False
    assert det.error is not None and "mic busy" in det.error
