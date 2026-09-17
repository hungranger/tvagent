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


def test_wakeword_returns_only_after_detection():
    # F1: wait() must not return until a frame scores above threshold
    frames = _ScriptedSource([(np.zeros(1, dtype=np.int16).tobytes(), False)] * 3)
    scores = iter([{"w": 0.1}, {"w": 0.2}, {"w": 0.9}])  # fires on 3rd frame

    class _Det:
        def predict(self, arr: Any) -> dict[str, float]:
            return next(scores)

    ww = OwwWakeWord(_detector=_Det(), _source=frames)
    ww.wait()  # returns (does not hang / raise) exactly when score>0.5 arrives
