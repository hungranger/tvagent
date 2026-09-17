class PiperTTS:
    def __init__(self, voice: str = "en_US-amy-medium", _synth=None, _play=None):
        self.voice = voice
        self._synth = _synth or self._default_synth
        self._play = _play or self._default_play
        self._model = None

    def _default_synth(self, text: str) -> bytes:
        from piper import PiperVoice
        if self._model is None:
            self._model = PiperVoice.load(self.voice)
        import io, wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            self._model.synthesize(text, wf)
        return buf.getvalue()

    def _default_play(self, pcm: bytes) -> None:
        import io, wave, sounddevice, numpy as np
        with wave.open(io.BytesIO(pcm)) as wf:
            data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
            sounddevice.play(data, wf.getframerate()); sounddevice.wait()

    def speak(self, text: str) -> None:
        if not text.strip(): return
        self._play(self._synth(text))
