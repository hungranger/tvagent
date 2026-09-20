import threading
from typing import Any

from tvagent.audio import MicSource

# Wake-word barge-in: during playback, listen for the wake word and interrupt when
# it fires. No echo cancellation needed -- the assistant's own TTS never says the
# wake word, so it can't self-interrupt. This is how real TV assistants (Fire TV,
# Android TV, Alexa) let you cut in, and it works on any hardware. To barge, the
# user says the wake word again (e.g. "alexa").
_SAMPLE_RATE = 16000
_WAKE_THRESHOLD = 0.5
_WAKE_MODEL = "alexa"
_JOIN_TIMEOUT = 1.0


class WakeWordBargeIn:
    def __init__(
        self,
        sample_rate: int = _SAMPLE_RATE,
        threshold: float = _WAKE_THRESHOLD,
        model_name: str = _WAKE_MODEL,
        _source: Any = None,
        _detector: Any = None,
    ) -> None:
        self._sr = sample_rate
        self._threshold = threshold
        self._model = model_name
        self._source: Any = _source
        self._detector: Any = _detector
        self._speaking = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None

    def _ensure(self) -> None:  # pragma: no cover - loads the real model + mic
        if self._detector is None:
            import openwakeword.model as oww_model  # noqa: PLC0415 -- lazy
            import openwakeword.utils as oww_utils  # noqa: PLC0415 -- lazy

            om: Any = oww_model
            ut: Any = oww_utils
            ut.download_models([self._model])
            self._detector = om.Model(wakeword_models=[self._model], inference_framework="onnx")
        if self._source is None:
            self._source = MicSource(self._sr)

    def arm(self) -> None:
        self._speaking.clear()
        self._stop.clear()
        self.error = None
        self._ensure()
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def speaking(self) -> bool:
        return self._speaking.is_set()

    def disarm(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=_JOIN_TIMEOUT)
            self._thread = None

    def _listen(self) -> None:
        import numpy as np  # noqa: PLC0415 -- lazy

        npx: Any = np
        try:
            for frame, _ in self._source.frames():
                if self._stop.is_set():
                    return
                scores = self._detector.predict(npx.frombuffer(frame, dtype=np.int16))
                if any(v > self._threshold for v in scores.values()):
                    self._speaking.set()
                    return
        except Exception as exc:  # daemon thread: record, don't crash silently
            self.error = f"{type(exc).__name__}: {exc}"
