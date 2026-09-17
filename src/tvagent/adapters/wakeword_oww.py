from typing import Any

from tvagent.adapters.audio_vad import MicSource

_SAMPLE_RATE = 16000
_WAKE_THRESHOLD = 0.5
_WAKE_MODEL = "hey_jarvis"


class OwwWakeWord:
    def __init__(
        self, model_name: str = _WAKE_MODEL, _detector: Any = None, _source: Any = None
    ) -> None:
        self.model_name = model_name
        self._detector: Any = _detector
        self._source: Any = _source

    def _ensure(self) -> None:
        if self._detector is None:
            import openwakeword.model as oww_model  # noqa: PLC0415 -- lazy

            om: Any = oww_model
            self._detector = om.Model(wakeword_models=[self.model_name])
        if self._source is None:
            self._source = MicSource(_SAMPLE_RATE)

    def wait(self) -> None:
        self._ensure()
        import numpy as np  # noqa: PLC0415 -- lazy

        npx: Any = np
        for frame, _ in self._source.frames():
            scores = self._detector.predict(npx.frombuffer(frame, dtype=np.int16))
            if any(v > _WAKE_THRESHOLD for v in scores.values()):
                return
