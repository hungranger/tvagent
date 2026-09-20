from collections.abc import Iterator
from typing import Any

from tvagent.adapters.bargein_wake import WakeWordBargeIn


class _Frames:
    def __init__(self, n: int) -> None:
        self._n = n

    def frames(self) -> Iterator[tuple[bytes, bool]]:
        for _ in range(self._n):
            yield b"\x00\x00", False


class _Detector:
    """Fake oww model: fires (score>threshold) on the Nth predict call."""

    def __init__(self, fire_on: int | None) -> None:
        self._i = 0
        self._fire = fire_on

    def predict(self, _arr: Any) -> dict[str, float]:
        self._i += 1
        hot = self._fire is not None and self._i >= self._fire
        return {"alexa": 0.9 if hot else 0.1}


def _drain(det: WakeWordBargeIn) -> None:
    t = det._thread  # pyright: ignore[reportPrivateUsage]
    assert t is not None
    t.join(2.0)


def test_speaking_when_wake_word_heard_during_playback() -> None:
    det = WakeWordBargeIn(_source=_Frames(5), _detector=_Detector(fire_on=3))
    det.arm()
    _drain(det)
    assert det.speaking() is True


def test_no_barge_when_wake_word_absent() -> None:
    # The assistant's own TTS never says the wake word -> scores stay low -> no fire.
    det = WakeWordBargeIn(_source=_Frames(5), _detector=_Detector(fire_on=None))
    det.arm()
    _drain(det)
    assert det.speaking() is False


def test_disarm_is_safe() -> None:
    det = WakeWordBargeIn(_source=_Frames(1), _detector=_Detector(fire_on=None))
    det.arm()
    det.disarm()
    assert det.speaking() is False


class _Boom:
    def frames(self) -> Iterator[tuple[bytes, bool]]:
        raise RuntimeError("mic busy")


def test_listen_error_captured() -> None:
    det = WakeWordBargeIn(_source=_Boom(), _detector=_Detector(fire_on=None))
    det.arm()
    _drain(det)
    assert det.error is not None and "mic busy" in det.error
