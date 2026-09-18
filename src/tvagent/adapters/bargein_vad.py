import threading
from collections.abc import Callable
from typing import Any

from tvagent.audio import MicSource, PlaybackReference
from tvagent.core import ports

# ponytail: NAIVE STUB without an echo canceller — while armed, the mic hears the
# assistant's own TTS through the speakers and self-interrupts. Pass an `aec` +
# `reference` (PlaybackReference) to subtract the playback and make it usable on
# speakers. Wired behind TVAGENT_BARGE_IN so it ships opt-in, not on.
_ONSET_FRAMES = 3  # consecutive speech frames (~90ms at 30ms/frame) = the user talking
_JOIN_TIMEOUT = 1.0
_VAD_AGGRESSIVENESS = 2


class VadBargeIn:
    def __init__(
        self,
        sample_rate: int = 16000,
        onset_frames: int = _ONSET_FRAMES,
        _source: Any = None,
        aec: ports.EchoCanceller | None = None,
        reference: PlaybackReference | None = None,
        _vad: Callable[[bytes], bool] | None = None,
    ) -> None:
        self._sr = sample_rate
        self._onset = onset_frames
        self._source: Any = _source or MicSource(sample_rate)
        self._aec = aec
        self._reference = reference
        # Built lazily on first cleaned frame (real AEC path only) so construction
        # never imports webrtcvad — tests inject `_vad` or don't use AEC at all.
        self._vad = _vad
        self._speaking = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None  # last listen failure, for the console to surface

    def _default_vad(self) -> Callable[[bytes], bool]:
        import webrtcvad  # noqa: PLC0415 -- lazy

        wv: Any = webrtcvad
        vad = wv.Vad(_VAD_AGGRESSIVENESS)

        def speech(frame: bytes) -> bool:
            return bool(vad.is_speech(frame, self._sr))

        return speech

    def arm(self) -> None:
        self._speaking.clear()
        self._stop.clear()
        self.error = None
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def speaking(self) -> bool:
        return self._speaking.is_set()

    def disarm(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=_JOIN_TIMEOUT)
            self._thread = None

    def _detect(self, frame: bytes, is_speech: bool) -> bool:
        # With an echo canceller, subtract the assistant's playback and re-judge
        # the cleaned frame; otherwise trust the mic source's raw VAD.
        if self._aec is None or self._reference is None:
            return is_speech
        if self._vad is None:  # pragma: no cover - real webrtcvad path, live only
            self._vad = self._default_vad()
        far = self._reference.read(len(frame))
        return bool(self._vad(self._aec.process(frame, far)))

    def _listen(self) -> None:
        run = 0
        try:
            for frame, is_speech in self._source.frames():
                if self._stop.is_set():
                    return
                run = run + 1 if self._detect(frame, is_speech) else 0
                if run >= self._onset:
                    self._speaking.set()
                    return
        except Exception as exc:  # daemon thread: record, don't crash silently
            self.error = f"{type(exc).__name__}: {exc}"
