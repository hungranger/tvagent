from tvagent.core.models import GUEST, AudioClip, Fact, Person, RenderState, Turn


class FakeWakeWord:
    def __init__(self, times: int = 1) -> None:
        self._n = times

    def wait(self) -> None:
        if self._n <= 0:
            raise StopIteration
        self._n -= 1


class FakeAudioCapture:
    def __init__(self, clip: AudioClip) -> None:
        self._clip = clip

    def capture(self) -> AudioClip:
        return self._clip


class FakeSpeakerID:
    def __init__(self, person_id: str = GUEST) -> None:
        self._id = person_id

    def identify(self, clip: AudioClip) -> str:
        return self._id

    def enroll(self, name: str, clip: AudioClip) -> Person:
        return Person(id=name.lower(), name=name, embedding=[0.0], prefs={})


class FakeSTT:
    def __init__(self, text: str) -> None:
        self._text = text

    def transcribe(self, clip: AudioClip) -> str:
        return self._text


class FakeLLM:
    def __init__(self, reply: str = "ok") -> None:
        self._reply = reply
        self.last_system: str | None = None
        self.last_user: str | None = None

    def respond(self, system: str, user: str, history: list[tuple[str, str]]) -> str:
        self.last_system, self.last_user = system, user
        return self._reply


class FakeTTS:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)


class FakeDisplay:
    def __init__(self) -> None:
        self.last: RenderState | None = None

    def render(self, state: RenderState) -> None:
        self.last = state


class FakeMemory:
    def __init__(self) -> None:
        self.people: dict[str, Person] = {}
        self.turns: list[Turn] = []
        self.facts: list[Fact] = []

    def get_person(self, person_id: str) -> Person | None:
        return self.people.get(person_id)

    def list_people(self) -> list[Person]:
        return list(self.people.values())

    def upsert_person(self, person: Person) -> None:
        self.people[person.id] = person

    def save_turn(self, turn: Turn) -> None:
        self.turns.append(turn)

    def recent_turns(self, person_id: str, n: int) -> list[Turn]:
        return [t for t in self.turns if t.person_id == person_id][-n:]

    def get_facts(self, person_id: str) -> list[Fact]:
        return [f for f in self.facts if f.person_id == person_id]

    def add_fact(self, fact: Fact) -> None:
        self.facts.append(fact)
