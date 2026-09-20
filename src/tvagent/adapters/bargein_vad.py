import os
import threading
from typing import Any

from tvagent.audio import MicSource, PlaybackReference
from tvagent.core import ports

# ponytail: NAIVE STUB without an echo canceller — while armed, the mic hears the
# assistant's own TTS through the speakers and self-interrupts. Pass an `aec` +
# `reference` (PlaybackReference) to subtract the playback and make it usable on
# speakers. Wired behind TVAGENT_BARGE_IN so it ships opt-in, not on.
_ONSET_FRAMES = 3  # consecutive speech frames (~90ms at 30ms/frame) = the user talking
_JOIN_TIMEOUT = 1.0
# AEC-path double-talk gate. webrtcvad can't be used on the cancelled signal — it
# flags the quiet speech-shaped residual as "speech" regardless of amplitude. So
# barge-in on the AEC path fires only when the residual is BOTH loud enough to be
# real speech AND a large fraction of the input survived cancellation (double-talk).
_RESIDUAL_RMS = float(os.environ.get("TVAGENT_AEC_RESIDUAL", "300"))
_DOUBLETALK_RATIO = float(os.environ.get("TVAGENT_AEC_RATIO", "0.5"))


class VadBargeIn:
    def __init__(  # noqa: PLR0913 -- optional AEC collaborators + gate knobs + test seam
        self,
        sample_rate: int = 16000,
        onset_frames: int = _ONSET_FRAMES,
        _source: Any = None,
        aec: ports.EchoCanceller | None = None,
        reference: PlaybackReference | None = None,
        residual_rms: float = _RESIDUAL_RMS,
        ratio: float = _DOUBLETALK_RATIO,
    ) -> None:
        self._onset = onset_frames
        self._source: Any = _source or MicSource(sample_rate)
        self._aec = aec
        self._reference = reference
        self._residual = residual_rms
        self._ratio = ratio
        self._speaking = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None  # last listen failure, for the console to surface

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
        # With an echo canceller, cancel the assistant's playback and judge the
        # residual by energy (double-talk); otherwise trust the mic's raw VAD.
        if self._aec is None or self._reference is None:
            return is_speech
        far = self._reference.read(len(frame))
        return self._double_talk(frame, self._aec.process(frame, far))

    def _double_talk(self, near: bytes, clean: bytes) -> bool:
        import numpy as np  # noqa: PLC0415 -- lazy

        npx: Any = np
        n = npx.frombuffer(near, dtype=np.int16).astype(np.float64)
        c = npx.frombuffer(clean, dtype=np.int16).astype(np.float64)
        near_rms = float(npx.sqrt(npx.mean(n * n))) if len(n) else 0.0
        clean_rms = float(npx.sqrt(npx.mean(c * c))) if len(c) else 0.0
        # Loud enough to be real speech AND a big fraction survived cancellation.
        return clean_rms > self._residual and clean_rms > self._ratio * near_rms

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
