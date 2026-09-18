import io
import wave

from tvagent.adapters.tts_kokoro import KokoroTTS


def _wav(seconds: float, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def test_default_voice_is_stored() -> None:
    assert KokoroTTS(_synth=lambda _t: b"x").voice == "af_heart"


def test_synth_returns_audio_and_duration() -> None:
    wav = _wav(2.0)
    pcm, dur = KokoroTTS(_synth=lambda _t: wav).synth("hello")
    assert pcm == wav
    assert abs(dur - 2.0) < 0.01


def test_synth_empty_text_is_zero() -> None:
    assert KokoroTTS(_synth=lambda _t: b"x").synth("   ") == (b"", 0.0)


def test_speak_synthesizes_then_plays() -> None:
    calls: dict[str, bytes] = {}
    KokoroTTS(_synth=lambda _t: b"WAV", _play=lambda pcm: calls.__setitem__("p", pcm)).speak("hi")
    assert calls["p"] == b"WAV"


def test_empty_text_does_not_play() -> None:
    played: list[bytes] = []
    KokoroTTS(_synth=lambda _t: b"x", _play=played.append).speak("  ")
    assert played == []


def test_set_voice_switches_voice() -> None:
    tts = KokoroTTS(_synth=lambda _t: b"x")
    tts.set_voice("am_michael")
    assert tts.voice == "am_michael"
