import time

from tvagent.core import ports
from tvagent.core.models import GUEST, Fact, Person, RenderState, Turn

_HISTORY_LIMIT = 5


class Orchestrator:
    def __init__(  # noqa: PLR0913 -- ports: one collaborator per port, DI by design
        self, wake: ports.WakeWord, capture: ports.AudioCapture,
        speaker: ports.SpeakerID, stt: ports.STT, llm: ports.LLM,
        tts: ports.TTS, memory: ports.MemoryStore, display: ports.Display,
    ) -> None:
        self.wake, self.capture, self.speaker = wake, capture, speaker
        self.stt, self.llm, self.tts = stt, llm, tts
        self.memory, self.display = memory, display

    def _build(
        self, person: Person | None, facts: list[Fact], history: list[Turn], said: str
    ) -> tuple[str, str]:
        who = person.name if person else "an unknown guest"
        tone = (person.prefs.get("tone") if person else None) or "friendly"
        lines = [f"You are a family home assistant speaking with {who}.",
                 f"Use a {tone} tone. Keep replies short and spoken-friendly."]
        if facts:
            lines.append("What you remember about them: " + "; ".join(f.text for f in facts))
        if history:
            lines.append("Recent exchanges: " +
                         " | ".join(f"{h.said} -> {h.replied}" for h in history))
        return "\n".join(lines), said

    def run_once(self) -> Turn:
        self.wake.wait()
        clip = self.capture.capture()
        person_id = self.speaker.identify(clip)
        said = self.stt.transcribe(clip)
        person = None if person_id == GUEST else self.memory.get_person(person_id)
        if person is None:
            person_id = GUEST
            facts: list[Fact] = []
            history: list[Turn] = []
        else:
            facts = self.memory.get_facts(person.id)
            history = self.memory.recent_turns(person.id, _HISTORY_LIMIT)
        system, user = self._build(person, facts, history, said)
        reply = self.llm.respond(system, user, [(h.said, h.replied) for h in history])
        self.tts.speak(reply)
        self.display.render(RenderState(person=(person.name if person else "Guest"), text=reply))
        turn = Turn(person_id=person_id, ts=time.time(), said=said, replied=reply)
        self.memory.save_turn(turn)
        return turn
