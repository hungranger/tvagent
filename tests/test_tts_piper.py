from typing import Any

from tvagent.adapters.tts_piper import PiperTTS


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
