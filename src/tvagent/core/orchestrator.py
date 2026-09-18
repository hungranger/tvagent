import re
import time
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor

from tvagent.core import ports
from tvagent.core.models import GUEST, Fact, Person, RenderState, Turn

_HISTORY_LIMIT = 5
_DEFAULT_TONE = "friendly"
_TONE_PREF_KEY = "tone"

# Per-stage observer for front-ends (e.g. the console): (stage, payload).
OnEvent = Callable[[str, dict[str, object]], None]

# A sentence ends at . ! ? (optionally closing quote/bracket) followed by whitespace.
_SENTENCE_END = re.compile(r"[.!?][\"')\]]?\s")


def has_speech(text: str) -> bool:
    """True only if the transcript carries actual words — guards against replying
    to silence or whisper's noise artifacts (empty, whitespace, "...", "- .").
    """
    return any(c.isalnum() for c in text)


def stream_reply(chunks: Iterable[str]) -> Iterator[tuple[str, str]]:
    """Drive both surfaces from one pass over the LLM token stream:

    - ("caption", full_text_so_far) on every chunk — the on-screen text types out
      word-by-word as tokens arrive.
    - ("speak", sentence) when a sentence completes (plus the trailing remainder)
      — TTS gets whole sentences, since Piper synthesizes a sentence at a time.
    """
    full = ""
    pending = ""
    for chunk in chunks:
        if not chunk:
            continue
        full += chunk
        pending += chunk
        yield ("caption", full.strip())
        while (m := _SENTENCE_END.search(pending)) is not None:
            yield ("speak", pending[: m.end()].strip())
            pending = pending[m.end() :]
    if pending.strip():
        yield ("speak", pending.strip())


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
        if not has_speech(said):
            # Wake word then silence/noise -> don't invent a reply or persist it.
            emit("ignored", {"said": said})
            return Turn(person_id=person_id, ts=time.time(), said=said, replied="")
        system, user = self._build(person, facts, said)
        # Stream the reply: speak each sentence as the LLM finishes it, so the
        # first words play while the rest is still generating (time-to-first-audio).
        pairs = [(h.said, h.replied) for h in history]
        reply = ""
        rendered = False
        for kind, payload in stream_reply(self.llm.stream(system, user, pairs)):
            if kind == "caption":  # word-by-word text, in step with the audio
                reply = payload
                self.display.render(RenderState(person=name, text=payload))
                rendered = True
            else:  # a completed sentence -> speak it
                self.tts.speak(payload)
        if not rendered:  # nothing streamed -> refresh the screen once
            self.display.render(RenderState(person=name, text=reply))
        emit("replied", {"reply": reply})
        emit("spoken", {})
        turn = Turn(person_id=person_id, ts=time.time(), said=said, replied=reply)
        self.memory.save_turn(turn)
        return turn
