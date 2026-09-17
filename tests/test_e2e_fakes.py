"""Hermetic full-turn e2e through build_orchestrator with fakes.

Proves F7 (spoken), F8 (shown), F9 (persisted) and F10 (recall of an earlier
turn) through the real save->load path: two real Orchestrator.run_once()
calls sharing one JsonMemory, no pre-seeded facts.
"""

import pathlib

from tests.fakes import (
    FakeAudioCapture,
    FakeDisplay,
    FakeLLM,
    FakeSpeakerID,
    FakeSTT,
    FakeTTS,
    FakeWakeWord,
)
from tvagent.adapters.memory_json import JsonMemory
from tvagent.config import build_orchestrator
from tvagent.core.models import AudioClip, Person
from tvagent.core.orchestrator import Orchestrator

_SAMPLE_RATE = 16000


def test_e2e_turn_recall_and_render(tmp_path: pathlib.Path) -> None:
    mem = JsonMemory(tmp_path)
    mem.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={"tone": "adult"}))
    clip = AudioClip(samples=b"x", sample_rate=_SAMPLE_RATE)
    llm, tts, disp = FakeLLM("Noted."), FakeTTS(), FakeDisplay()

    def orch(said: str) -> Orchestrator:
        return build_orchestrator(
            {
                "wake": FakeWakeWord(),
                "capture": FakeAudioCapture(clip),
                "speaker": FakeSpeakerID("dad"),
                "stt": FakeSTT(said),
                "llm": llm,
                "tts": tts,
                "memory": mem,
                "display": disp,
            }
        )

    orch("my dog is named Rex").run_once()  # turn 1 persisted
    orch("what did I just tell you").run_once()  # turn 2 loads history

    assert llm.last_history == [("my dog is named Rex", "Noted.")]  # F10: earlier turn recalled
    assert tts.spoken[-1] == "Noted."  # F7
    assert disp.last is not None and disp.last.text == "Noted."  # F8
    assert mem.recent_turns("dad", 2)[0].said == "my dog is named Rex"  # F9 persist
