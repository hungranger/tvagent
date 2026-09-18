import threading
from typing import Any

from tvagent.audio import MicSource

# ponytail: NAIVE STUB — no acoustic echo cancellation. While armed, the mic
# hears the assistant's own TTS through the speakers and will self-interrupt.
# Only usable with headphones or a muted/echo-free setup until AEC lands (the
# next P0 item). Wired behind TVAGENT_BARGE_IN so it ships opt-in, not on.
_ONSET_FRAMES = 3  # consecutive speech frames (~90ms at 30ms/frame) = the user talking
_JOIN_TIMEOUT = 1.0


class VadBargeIn:
    def __init__(
        self, sample_rate: int = 16000, onset_frames: int = _ONSET_FRAMES, _source: Any = None
    ) -> None:
        self._onset = onset_frames
        self._source: Any = _source or MicSource(sample_rate)
        self._speaking = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def arm(self) -> None:
        self._speaking.clear()
        self._stop.clear()
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
        run = 0
        for _frame, is_speech in self._source.frames():
            if self._stop.is_set():
                return
            run = run + 1 if is_speech else 0
            if run >= self._onset:
                self._speaking.set()
                return
