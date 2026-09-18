import io
import wave
from typing import Any

from tvagent.adapters.tts_piper import PiperTTS


def _wav(seconds: float, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def test_synth_returns_audio_and_its_duration() -> None:
    wav = _wav(1.5)
    pcm, dur = PiperTTS(_synth=lambda _t: wav).synth("hello")
    assert pcm == wav
    assert abs(dur - 1.5) < 0.01  # duration read from the WAV, for caption pacing


def test_synth_empty_text_is_zero() -> None:
    assert PiperTTS(_synth=lambda _t: b"x").synth("   ") == (b"", 0.0)


def test_play_delegates_and_skips_empty() -> None:
    played: list[bytes] = []
    tts = PiperTTS(_synth=lambda _t: b"x", _play=played.append)
    tts.play(b"abc")
    tts.play(b"")
    assert played == [b"abc"]


def test_speak_synthesizes_then_plays():
    calls: dict[str, Any] = {}

    def synth(text: str) -> bytes:
        calls["text"] = text
        return b"PCMDATA"

    def play(pcm: bytes) -> None:
        calls["played"] = pcm

    PiperTTS(_synth=synth, _play=play).speak("hello Dad")
    assert calls["text"] == "hello Dad"
    assert calls["played"] == b"PCMDATA"


def test_empty_text_does_not_play():
    played: list[bytes] = []
    PiperTTS(_synth=lambda _t: b"x", _play=played.append).speak("  ")
    assert played == []


def test_default_voice_is_stored():
    assert PiperTTS().voice == "en_US-amy-medium"


def test_set_voice_changes_voice_and_clears_cached_model() -> None:
    # console voice picker: switching voice must take effect on the next utterance,
    # so the cached model is dropped and reloaded lazily under the new voice.
    tts = PiperTTS()
    tts._model = "OLD"  # pyright: ignore[reportPrivateUsage]  # pretend a voice was loaded
    tts.set_voice("en_US-ryan-high")
    assert tts.voice == "en_US-ryan-high"
    assert tts._model is None  # pyright: ignore[reportPrivateUsage]


def test_warmup_noop_with_injected_synth() -> None:
    # warmup preloads/downloads the real Piper voice; with an injected synth
    # there is nothing to preload, so it must be a safe no-op.
    tts = PiperTTS(_synth=lambda _t: b"x")
    tts.warmup()
    assert tts._model is None  # pyright: ignore[reportPrivateUsage]


def test_warmup_loads_model_when_default() -> None:
    # With the default synth, warmup() must populate _model via _load_model.
    tts = PiperTTS()
    tts._load_model = lambda: "VOICE"  # type: ignore[method-assign]  # stub the heavy download
    tts.warmup()
    assert tts._model == "VOICE"  # pyright: ignore[reportPrivateUsage]
