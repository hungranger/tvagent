class OwwWakeWord:
    def __init__(self, model_name: str = "hey_jarvis", _detector=None, _source=None):
        self.model_name, self._detector, self._source = model_name, _detector, _source

    def _ensure(self):
        if self._detector is None:
            from openwakeword.model import Model
            self._detector = Model(wakeword_models=[self.model_name])
        if self._source is None:
            from tvagent.adapters.audio_vad import _MicSource
            self._source = _MicSource(16000)

    def wait(self) -> None:
        self._ensure()
        for frame, _ in self._source.frames():
            import numpy as np
            scores = self._detector.predict(np.frombuffer(frame, dtype=np.int16))
            if any(v > 0.5 for v in scores.values()):
                return
