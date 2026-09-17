import pathlib
from typing import Any

from tvagent.core import ports
from tvagent.core.orchestrator import Orchestrator

_MEMORY_ROOT = pathlib.Path("data/memory")


def build_orchestrator(
    overrides: dict[str, object] | None = None, warm: bool = True
) -> Orchestrator:
    o = overrides or {}
    memory = _get(o, "memory", _memory)
    orch = Orchestrator(
        wake=_get(o, "wake", _wake),
        capture=_get(o, "capture", _capture),
        speaker=_get(o, "speaker", lambda: _speaker(memory)),
        stt=_get(o, "stt", _stt),
        llm=_get(o, "llm", _llm),
        tts=_get(o, "tts", _tts),
        memory=memory,
        display=_get(o, "display", _display),
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
    from tvagent.adapters.stt_whisper import WhisperSTT  # noqa: PLC0415 -- lazy

    return WhisperSTT()


def _llm() -> ports.LLM:
    from tvagent.adapters.llm_claude import ClaudeLLM  # noqa: PLC0415 -- lazy

    return ClaudeLLM()


def _tts() -> ports.TTS:
    from tvagent.adapters.tts_piper import PiperTTS  # noqa: PLC0415 -- lazy

    return PiperTTS()


def _display() -> ports.Display:
    from tvagent.adapters.display_web import WebDisplay  # noqa: PLC0415 -- lazy

    return WebDisplay()
