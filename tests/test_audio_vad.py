from collections.abc import Iterable, Iterator
from typing import Any

import numpy as np

from tvagent.adapters.audio_vad import VadCapture
from tvagent.adapters.wakeword_oww import OwwWakeWord


class _ScriptedSource:
    """Yields (frame_bytes, is_speech) then signals stream end."""

    def __init__(self, script: Iterable[tuple[bytes, bool]]) -> None:
        self.script = list(script)

    def frames(self) -> Iterator[tuple[bytes, bool]]:
        yield from self.script


def test_capture_stops_after_trailing_silence():
    # 3 speech frames, then 2 silent frames (silence_limit=2) -> capture ends
    script = [(b"a", True), (b"b", True), (b"c", True), (b"", False), (b"", False)]
    cap = VadCapture(sample_rate=16000, silence_limit=2, _source=_ScriptedSource(script))
    clip = cap.capture()
    assert clip.samples == b"abc"  # F2: bounded capture to silence
    assert clip.sample_rate == 16000


def test_default_sample_rate_and_silence_limit():
    cap = VadCapture(_source=_ScriptedSource([]))
    assert cap.sample_rate == 16000
    assert cap.silence_limit == 15


def test_leading_silence_before_any_speech_does_not_count():
    # silence before speech ever starts must not arm the silence-limit break
    script = [(b"", False), (b"", False), (b"z", True)]
    cap = VadCapture(sample_rate=16000, silence_limit=2, _source=_ScriptedSource(script))
    assert cap.capture().samples == b"z"


def test_silence_counter_resets_on_speech_and_breaks_at_limit():
    # a single silent frame between speech must not trip a limit of 3, but 3
    # *consecutive* silent frames must, stopping capture before later speech
    script = [
        (b"a", True),
        (b"", False),
        (b"", False),
        (b"b", True),  # counter must reset here, not carry over
        (b"", False),
        (b"", False),
        (b"", False),  # 3rd consecutive silent frame -> break
        (b"z", True),  # must never be reached
    ]
    cap = VadCapture(sample_rate=16000, silence_limit=3, _source=_ScriptedSource(script))
    assert cap.capture().samples == b"ab"


def test_wakeword_returns_only_after_detection():
    # F1: wait() must not return until a frame scores above threshold
    frame = np.zeros(1, dtype=np.int16).tobytes()
    frames = _ScriptedSource([(frame, False)] * 3)
    scores = iter([{"w": 0.1}, {"w": 0.2}, {"w": 0.9}])  # fires on 3rd frame

    class _Det:
        def __init__(self) -> None:
            self.calls: list[Any] = []

        def predict(self, arr: Any) -> dict[str, float]:
            self.calls.append(arr)
            return next(scores)

    det = _Det()
    ww = OwwWakeWord(_detector=det, _source=frames)
    ww.wait()  # returns (does not hang / raise) exactly when score>0.5 arrives
    assert len(det.calls) == 3
    assert det.calls[0].tobytes() == frame  # predict() got the real frame, not a stand-in


def test_wakeword_does_not_fire_exactly_at_threshold():
    # a score == threshold must not fire (strictly greater-than only)
    frame = np.zeros(1, dtype=np.int16).tobytes()
    frames = _ScriptedSource([(frame, False), (frame, False)])
    scores = iter([{"w": 0.5}, {"w": 0.9}])

    class _Det:
        def __init__(self) -> None:
            self.calls = 0

        def predict(self, arr: Any) -> dict[str, float]:
            self.calls += 1
            return next(scores)

    det = _Det()
    ww = OwwWakeWord(_detector=det, _source=frames)
    ww.wait()
    assert det.calls == 2  # first (0.5) must not fire; only the second (0.9) does
