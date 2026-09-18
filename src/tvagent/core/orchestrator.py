import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from tvagent.core import ports
from tvagent.core.models import GUEST, Fact, Person, RenderState, Turn

_HISTORY_LIMIT = 5
_DEFAULT_TONE = "friendly"
_TONE_PREF_KEY = "tone"

# Per-stage observer for front-ends (e.g. the console): (stage, payload).
OnEvent = Callable[[str, dict[str, object]], None]


class Orchestrator:
    def __init__(  # noqa: PLR0913 -- ports: one collaborator per port, DI by design
        self,
        wake: ports.WakeWord,
        capture: ports.AudioCapture,
        speaker: ports.SpeakerID,
        stt: ports.STT,
        llm: ports.LLM,
        tts: ports.TTS,
        memory: ports.MemoryStore,
        display: ports.Display,
    ) -> None:
        self.wake, self.capture, self.speaker = wake, capture, speaker
        self.stt, self.llm, self.tts = stt, llm, tts
        self.memory, self.display = memory, display

    def _build(self, person: Person | None, facts: list[Fact], said: str) -> tuple[str, str]:
        who = person.name if person else "an unknown guest"
        tone = (person.prefs.get(_TONE_PREF_KEY) if person else None) or _DEFAULT_TONE
        lines = [
            f"You are a family home assistant speaking with {who}.",
            f"Use a {tone} tone. Keep replies short and spoken-friendly.",
        ]
        if facts:
            lines.append("What you remember about them: " + "; ".join(f.text for f in facts))
        return "\n".join(lines), said

    def run_once(self, on_event: OnEvent | None = None) -> Turn:
        emit: OnEvent = on_event or (lambda _stage, _data: None)
        self.wake.wait()
        emit("wake", {})
        clip = self.capture.capture()
        # Speaker-ID and transcription both consume the same clip independently;
        # run them concurrently (both release the GIL in native code) to shave a
        # stage off the turn.
        with ThreadPoolExecutor(max_workers=2) as pool:
            id_future = pool.submit(self.speaker.identify, clip)
            said = self.stt.transcribe(clip)
            person_id = id_future.result()
        person = None if person_id == GUEST else self.memory.get_person(person_id)
        if person is None:
            person_id = GUEST
            facts: list[Fact] = []
            history: list[Turn] = []
        else:
            facts = self.memory.get_facts(person.id)
            history = self.memory.recent_turns(person.id, _HISTORY_LIMIT)
        name = person.name if person else "Guest"
        emit("identified", {"person_id": person_id, "name": name})
        emit("transcribed", {"said": said})
        system, user = self._build(person, facts, said)
        reply = self.llm.respond(system, user, [(h.said, h.replied) for h in history])
        emit("replied", {"reply": reply})
        self.tts.speak(reply)
        self.display.render(RenderState(person=name, text=reply))
        emit("spoken", {})
        turn = Turn(person_id=person_id, ts=time.time(), said=said, replied=reply)
        self.memory.save_turn(turn)
        return turn
