"""Real end-to-end proof through the ACTUAL Orchestrator.run_once().

Only the two edge adapters are overridden: wake (fires once) and capture
(returns fixture audio instead of a live mic). Everything else is real:
real SpeakerID, real Whisper, real Claude, real Piper, real JSON memory,
real Display. Proves the full spine incl. render + persisted turn (T2).
Gated on ANTHROPIC_API_KEY (checked by name; value never printed).
"""

import os
import pathlib
import sys
import time
import wave

from tvagent.adapters.memory_json import JsonMemory
from tvagent.config import build_orchestrator
from tvagent.core.models import AudioClip, Person, RenderState


class _OnceWake:
    def __init__(self) -> None:
        self._done = False

    def wait(self) -> None:
        if self._done:
            raise SystemExit
        self._done = True


class _FixtureCapture:
    def __init__(self, clip: AudioClip) -> None:
        self._clip = clip

    def capture(self) -> AudioClip:
        return self._clip


class _RecordingDisplay:
    def __init__(self) -> None:
        self.last: RenderState | None = None

    def render(self, state: RenderState) -> None:
        self.last = state


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("SKIP live e2e: ANTHROPIC_API_KEY not set")
        return 0
    fx = pathlib.Path("tests/fixtures/hello.wav")
    if not fx.exists():
        # key present but no fixture -> the live proof cannot run; do NOT pass silently
        print(
            "FAIL live e2e: ANTHROPIC_API_KEY set but tests/fixtures/hello.wav missing "
            "(record it, see Task 6 Step 0)"
        )
        return 1
    with wave.open(str(fx)) as w:
        clip = AudioClip(samples=w.readframes(w.getnframes()), sample_rate=w.getframerate())
    mem = JsonMemory(pathlib.Path("data/verify"))
    mem.upsert_person(Person(id="tester", name="Tester", embedding=[0.0], prefs={}))
    disp = _RecordingDisplay()
    orch = build_orchestrator(
        {
            "wake": _OnceWake(),
            "capture": _FixtureCapture(clip),
            "memory": mem,
            "display": disp,
        }
    )  # speaker, stt, llm, tts are all REAL
    t0 = time.time()
    turn = orch.run_once()
    latency = time.time() - t0
    print(
        f"HEARD: {turn.said!r}\nREPLIED: {turn.replied!r}\n"
        f"RENDERED: {disp.last.text if disp.last else None!r}\n"
        f"END-TO-END LATENCY: {latency:.2f}s"
    )
    assert turn.replied.strip(), "empty reply"  # F6
    assert disp.last is not None and disp.last.text == turn.replied  # F8 render
    assert mem.recent_turns(turn.person_id, 1)[0].replied == turn.replied  # F9 persist
    print("LIVE E2E PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
