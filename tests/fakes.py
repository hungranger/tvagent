from tvagent.core.models import AudioClip, Person, Turn, Fact, RenderState, GUEST

class FakeWakeWord:
    def __init__(self, times: int = 1): self._n = times
    def wait(self) -> None:
        if self._n <= 0: raise StopIteration
        self._n -= 1

class FakeAudioCapture:
    def __init__(self, clip: AudioClip): self._clip = clip
    def capture(self) -> AudioClip: return self._clip

class FakeSpeakerID:
    def __init__(self, person_id: str = GUEST): self._id = person_id
    def identify(self, clip: AudioClip) -> str: return self._id
    def enroll(self, name: str, clip: AudioClip) -> Person:
        return Person(id=name.lower(), name=name, embedding=[0.0], prefs={})

class FakeSTT:
    def __init__(self, text: str): self._text = text
    def transcribe(self, clip: AudioClip) -> str: return self._text

class FakeLLM:
    def __init__(self, reply: str = "ok"): self._reply = reply; self.last_system = None; self.last_user = None
    def respond(self, system, user, history):
        self.last_system, self.last_user = system, user; return self._reply

class FakeTTS:
    def __init__(self): self.spoken = []
    def speak(self, text: str) -> None: self.spoken.append(text)

class FakeDisplay:
    def __init__(self): self.last = None
    def render(self, state: RenderState) -> None: self.last = state

class FakeMemory:
    def __init__(self):
        self.people = {}; self.turns = []; self.facts = []
    def get_person(self, person_id): return self.people.get(person_id)
    def list_people(self): return list(self.people.values())
    def upsert_person(self, person): self.people[person.id] = person
    def save_turn(self, turn): self.turns.append(turn)
    def recent_turns(self, person_id, n):
        return [t for t in self.turns if t.person_id == person_id][-n:]
    def get_facts(self, person_id):
        return [f for f in self.facts if f.person_id == person_id]
    def add_fact(self, fact): self.facts.append(fact)
