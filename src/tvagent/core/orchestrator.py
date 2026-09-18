import re
import threading
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


def iter_sentences(chunks: Iterable[str]) -> Iterator[str]:
    """Reassemble streamed LLM chunks and yield complete sentences as soon as each
    finishes (then the trailing remainder), so TTS can synthesize sentence-by-
    sentence while the model is still generating the rest.
    """
    buf = ""
    for chunk in chunks:
        buf += chunk
        while (m := _SENTENCE_END.search(buf)) is not None:
            yield buf[: m.end()].strip()
            buf = buf[m.end() :]
    if buf.strip():
        yield buf.strip()


def paced_reveal(
    prefix: str,
    sentence: str,
    duration: float,
    render: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Reveal a sentence's words one at a time, spread evenly across `duration`
    (its spoken length), appending to `prefix` (already-shown text). Keeps the
    caption in step with the audio instead of racing ahead. Returns the full text
    shown so far. `sleep` is injectable so tests don't wait in real time.
    """
    words = sentence.split()
    if not words:
        return prefix
    per = duration / len(words)
    shown = prefix
    for word in words:
        shown = f"{shown} {word}".strip()
        render(shown)
        if per > 0:
            sleep(per)
    return shown


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
        # Stream the reply sentence-by-sentence; for each, synthesize its audio,
        # start playing it, and reveal its words paced across the audio's duration
        # so the caption keeps step with the voice instead of racing ahead.
        pairs = [(h.said, h.replied) for h in history]
        reply = ""
        rendered = False

        def show(text: str) -> None:
            self.display.render(RenderState(person=name, text=text))

        for sentence in iter_sentences(self.llm.stream(system, user, pairs)):
            pcm, duration = self.tts.synth(sentence)
            player = threading.Thread(target=self.tts.play, args=(pcm,), daemon=True)
            player.start()
            reply = paced_reveal(reply, sentence, duration, show)
            rendered = True
            player.join()
        if not rendered:  # nothing streamed -> refresh the screen once
            show(reply)
        emit("replied", {"reply": reply})
        emit("spoken", {})
        turn = Turn(person_id=person_id, ts=time.time(), said=said, replied=reply)
        self.memory.save_turn(turn)
        return turn
