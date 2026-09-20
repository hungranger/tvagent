import pathlib
from typing import Any

from tvagent.core import ports
from tvagent.core.orchestrator import Orchestrator

_MEMORY_ROOT = pathlib.Path("data/memory")


def build_orchestrator(
    overrides: dict[str, object] | None = None, warm: bool = True
) -> Orchestrator:
    import os  # noqa: PLC0415 -- lazy

    o = overrides or {}
    memory = _get(o, "memory", _memory)
    tts = _get(o, "tts", _tts)
    barge_in = _get(o, "barge_in", _barge_in)
    # Echo cancellation (TVAGENT_AEC): wrap TTS to tap the far-end and give the
    # detector an AEC, both sharing one delay-primed reference so barge-in works
    # on speakers. Only when we built the real adapters (not test overrides).
    if os.environ.get("TVAGENT_AEC") and "tts" not in o and "barge_in" not in o and barge_in:
        tts, barge_in = _with_aec(tts)  # pragma: no cover - real-adapter AEC wiring, live only
    orch = Orchestrator(
        wake=_get(o, "wake", _wake),
        capture=_get(o, "capture", _capture),
        speaker=_get(o, "speaker", lambda: _speaker(memory)),
        stt=_get(o, "stt", _stt),
        llm=_get(o, "llm", _llm),
        tts=tts,
        memory=memory,
        display=_get(o, "display", _display),
        wake_ack=os.environ.get("TVAGENT_WAKE_ACK", "Yes?"),  # set "" to disable
        barge_in=barge_in,
    )
    if warm:
        # Preload heavy local models off the turn path (cold-start ~40s → boot).
        for adapter in (orch.stt, orch.speaker, orch.tts):
            warmup: Any = getattr(adapter, "warmup", None)
            if callable(warmup):
                warmup()
    return orch


def _get(overrides: dict[str, object], key: str, factory: Any) -> Any:
    return overrides[key] if key in overrides else factory()


def _memory() -> ports.MemoryStore:
    from tvagent.adapters.memory_json import JsonMemory  # noqa: PLC0415 -- lazy

    return JsonMemory(_MEMORY_ROOT)


def _wake() -> ports.WakeWord:
    from tvagent.adapters.wakeword_oww import OwwWakeWord  # noqa: PLC0415 -- lazy

    return OwwWakeWord()


def _capture() -> ports.AudioCapture:
    from tvagent.adapters.audio_vad import VadCapture  # noqa: PLC0415 -- lazy

    return VadCapture()


def _speaker(memory: ports.MemoryStore) -> ports.SpeakerID:
    from tvagent.adapters.speakerid_ecapa import EcapaSpeakerID  # noqa: PLC0415 -- lazy

    return EcapaSpeakerID(memory)


def _stt() -> ports.STT:
    import os  # noqa: PLC0415 -- lazy

    stt = os.environ.get("TVAGENT_STT")
    if stt == "parakeet":  # SOTA English ASR on MLX, mac-only opt-in
        from tvagent.adapters.stt_parakeet import ParakeetSTT  # noqa: PLC0415 -- lazy

        return ParakeetSTT()
    if stt == "mlx":  # Metal-accelerated whisper, mac-only opt-in
        from tvagent.adapters.stt_mlx import MlxWhisperSTT  # noqa: PLC0415 -- lazy

        return MlxWhisperSTT()
    from tvagent.adapters.stt_whisper import WhisperSTT  # noqa: PLC0415 -- lazy

    return WhisperSTT()


def _llm() -> ports.LLM:
    import os  # noqa: PLC0415 -- lazy

    backend = os.environ.get("TVAGENT_LLM", "claude")
    if backend == "local":  # Ollama or any OpenAI-compatible server on localhost
        from tvagent.adapters.llm_openai import OpenAILLM  # noqa: PLC0415 -- lazy

        return OpenAILLM(model=os.environ.get("TVAGENT_LLM_MODEL", "llama3.2"))
    if backend == "cerebras":
        from tvagent.adapters.llm_openai import OpenAILLM  # noqa: PLC0415 -- lazy

        return OpenAILLM(
            base_url="https://api.cerebras.ai/v1",
            api_key=os.environ.get("CEREBRAS_API_KEY"),
            model=os.environ.get("TVAGENT_LLM_MODEL", "llama-3.3-70b"),
        )
    from tvagent.adapters.llm_claude import ClaudeLLM  # noqa: PLC0415 -- lazy

    return ClaudeLLM()


def _tts() -> ports.TTS:
    import os  # noqa: PLC0415 -- lazy

    if os.environ.get("TVAGENT_TTS") == "kokoro":  # more natural, opt-in
        from tvagent.adapters.tts_kokoro import KokoroTTS  # noqa: PLC0415 -- lazy

        return KokoroTTS()
    from tvagent.adapters.tts_piper import PiperTTS  # noqa: PLC0415 -- lazy

    return PiperTTS()


def _with_aec(tts: ports.TTS) -> tuple[ports.TTS, ports.BargeInDetector]:
    import os  # noqa: PLC0415 -- lazy

    from tvagent.adapters.aec_fdaf import FdafEchoCanceller  # noqa: PLC0415 -- lazy
    from tvagent.adapters.bargein_vad import VadBargeIn  # noqa: PLC0415 -- lazy
    from tvagent.adapters.tts_tap import TappedTTS  # noqa: PLC0415 -- lazy
    from tvagent.audio import DuplexAudio  # noqa: PLC0415 -- lazy

    # One full-duplex 48k stream plays the far-end AND captures the mic on a single
    # clock, so the AEC gets time-aligned near/far. A separate mic+speaker pair
    # drifts (far written ahead of playback) and cancellation collapses (measured
    # live: clean==near). Runs at 48k so the coherent >1.5kHz band survives (16k
    # resampling aliases it; MacBook speaker nonlinearity ruins the low band ->
    # 8dB linear ceiling). FDAF (12288 taps=256ms) learns the ~208ms echo delay.
    # onset=6 (~180ms @30ms frames) clears residual-echo blips; a talker sustains.
    rate = int(os.environ.get("TVAGENT_AEC_RATE", "48000"))
    taps = int(os.environ.get("TVAGENT_AEC_TAPS", "12288"))
    onset = int(os.environ.get("TVAGENT_AEC_ONSET", "12"))
    hp = float(os.environ.get("TVAGENT_AEC_HP", "1500"))
    block = int(rate * 30 / 1000)  # 30ms blocks -> matches the offline AEC validation
    duplex = DuplexAudio(rate=rate, block=block)
    detector = VadBargeIn(
        sample_rate=rate,
        onset_frames=onset,
        aec=FdafEchoCanceller(taps=taps),
        reference=duplex.far,
        hp_cutoff=hp,
        _source=duplex,
    )
    return TappedTTS(tts, duplex, dev_rate=rate), detector


def _barge_in() -> ports.BargeInDetector | None:
    import os  # noqa: PLC0415 -- lazy

    if os.environ.get("TVAGENT_BARGE_IN"):  # opt-in; naive stub, needs AEC (see adapter)
        from tvagent.adapters.bargein_vad import VadBargeIn  # noqa: PLC0415 -- lazy

        return VadBargeIn()
    return None


def _display() -> ports.Display:
    from tvagent.adapters.display_web import WebDisplay  # noqa: PLC0415 -- lazy

    return WebDisplay()
