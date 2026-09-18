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
_IDLE_ACK_SECONDS = 45.0  # re-acknowledge the wake word after this much idle time
_PLAY_JOIN_TIMEOUT = 30.0  # cap the wait on a playback thread so barge-in can't deadlock a turn
_BARGE_POLL_SECONDS = 0.05  # how often to check for barge-in while a sentence's audio plays

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


def paced_reveal(  # noqa: PLR0913 -- cohesive render helper: text, timing, and two injectable hooks
    prefix: str,
    sentence: str,
    duration: float,
    render: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
    should_stop: Callable[[], bool] | None = None,
) -> str:
    """Reveal a sentence's words one at a time, spread evenly across `duration`
    (its spoken length), appending to `prefix` (already-shown text). Keeps the
    caption in step with the audio instead of racing ahead. Returns the full text
    shown so far. `sleep` is injectable so tests don't wait in real time. If
    `should_stop` is given and returns True, the reveal halts mid-sentence
    (barge-in) and returns the partial text shown so far.
    """
    words = sentence.split()
    if not words:
        return prefix
    per = duration / len(words)
    shown = prefix
    for word in words:
        if should_stop is not None and should_stop():
            return shown
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
        wake_ack: str | None = None,
        idle_ack_seconds: float = _IDLE_ACK_SECONDS,
        barge_in: ports.BargeInDetector | None = None,
    ) -> None:
        self.wake, self.capture, self.speaker = wake, capture, speaker
        self.stt, self.llm, self.tts = stt, llm, tts
        self.memory, self.display = memory, display
        # Spoken acknowledgement on the first wake or after an idle gap, so the
        # user knows it's listening; suppressed during an active back-and-forth.
        self.wake_ack = wake_ack
        self.idle_ack_seconds = idle_ack_seconds
        self._last_turn_ts: float | None = None
        # Optional barge-in: lets the user talk over the reply to interrupt it.
        self.barge_in = barge_in
        # After an interrupt, the user's follow-up is captured without re-waking.
        self._skip_wake = False

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
        if self._skip_wake:  # follow-up right after a barge-in: skip the wake word once
            self._skip_wake = False
        else:
            self.wake.wait()
        emit("wake", {})
        now = time.time()
        if self.wake_ack and (
            self._last_turn_ts is None or now - self._last_turn_ts > self.idle_ack_seconds
        ):
            self.tts.speak(self.wake_ack)
            emit("ack", {"text": self.wake_ack})
        self._last_turn_ts = now
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
        pairs = [(h.said, h.replied) for h in history]
        reply, interrupted = self._stream_reply(system, user, pairs, name, emit)
        turn = Turn(person_id=person_id, ts=time.time(), said=said, replied=reply)
        self.memory.save_turn(turn)
        if interrupted:
            self._skip_wake = True  # hear the user's follow-up without re-waking
            emit("interrupted", {"reply": reply})
        else:
            emit("replied", {"reply": reply})
            emit("spoken", {})
        return turn

    def _stream_reply(
        self, system: str, user: str, pairs: list[tuple[str, str]], name: str, emit: OnEvent
    ) -> tuple[str, bool]:
        """Stream the reply sentence-by-sentence: synthesize each, play it, and
        reveal its words paced across the audio's duration so the caption keeps
        step with the voice. If a barge-in detector is set, poll it during
        playback and abort (stop the audio, drop the rest) the moment the user
        talks over the reply. Returns (text shown, whether interrupted).
        ponytail: barge-in polls per word; tighten by chunking paced_reveal's sleep.
        """

        def show(text: str) -> None:
            self.display.render(RenderState(person=name, text=text))

        barge = threading.Event()

        def watch() -> bool:
            if barge.is_set():
                return True
            if self.barge_in is not None and self.barge_in.speaking():
                barge.set()
                self.tts.stop()
                return True
            return False

        should_stop = watch if self.barge_in is not None else None
        reply, rendered = "", False
        if self.barge_in is not None:
            self.barge_in.arm()
            emit("barge_armed", {})  # proves barge-in is live this turn
        try:
            for sentence in iter_sentences(self.llm.stream(system, user, pairs)):
                pcm, duration = self.tts.synth(sentence)
                player = threading.Thread(target=self.tts.play, args=(pcm,), daemon=True)
                player.start()
                reply = paced_reveal(reply, sentence, duration, show, should_stop=should_stop)
                rendered = True
                self._await_playback(player, should_stop)
                if barge.is_set():
                    break
        finally:
            self._disarm_barge(emit)
        if not rendered:  # nothing streamed -> refresh the screen once
            show(reply)
        return reply, barge.is_set()

    def _disarm_barge(self, emit: OnEvent) -> None:
        if self.barge_in is None:
            return
        self.barge_in.disarm()
        err = getattr(self.barge_in, "error", None)
        if err:  # mic failure in the listen thread -> tell the UI why barge-in is dead
            emit("error", {"message": f"barge-in: {err}"})

    def _await_playback(
        self, player: threading.Thread, should_stop: Callable[[], bool] | None
    ) -> None:
        """Wait for a sentence's audio to finish. With barge-in armed, keep
        polling while it plays so the user can interrupt during the audio's
        tail, not only between words. Capped so a stuck player can't hang a turn.
        """
        if should_stop is None:
            player.join(timeout=_PLAY_JOIN_TIMEOUT)
            return
        deadline = time.monotonic() + _PLAY_JOIN_TIMEOUT
        while player.is_alive():
            player.join(_BARGE_POLL_SECONDS)
            if should_stop() or time.monotonic() > deadline:
                return
