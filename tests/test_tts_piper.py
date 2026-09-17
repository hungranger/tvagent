from typing import Any

from tvagent.adapters.tts_piper import PiperTTS


def test_speak_synthesizes_then_plays():
    calls: dict[str, Any] = {}
    def synth(text: str) -> bytes:
        calls["text"] = text
        return b"PCMDATA"
    def play(pcm: bytes) -> None: calls["played"] = pcm
    PiperTTS(_synth=synth, _play=play).speak("hello Dad")
    assert calls["text"] == "hello Dad"
    assert calls["played"] == b"PCMDATA"

def test_empty_text_does_not_play():
    played: list[bytes] = []
    PiperTTS(_synth=lambda t: b"x", _play=played.append).speak("  ")
    assert played == []
