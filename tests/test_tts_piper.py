from tvagent.adapters.tts_piper import PiperTTS

def test_speak_synthesizes_then_plays():
    calls = {}
    def synth(text): calls["text"] = text; return b"PCMDATA"
    def play(pcm): calls["played"] = pcm
    PiperTTS(_synth=synth, _play=play).speak("hello Dad")
    assert calls["text"] == "hello Dad"
    assert calls["played"] == b"PCMDATA"

def test_empty_text_does_not_play():
    played = []
    PiperTTS(_synth=lambda t: b"x", _play=lambda p: played.append(p)).speak("  ")
    assert played == []
