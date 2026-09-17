from dataclasses import dataclass

PersonId = str
GUEST: PersonId = "guest"

@dataclass
class AudioClip:
    samples: bytes
    sample_rate: int

@dataclass
class Person:
    id: str
    name: str
    embedding: list[float]
    prefs: dict

@dataclass
class Turn:
    person_id: str
    ts: float
    said: str
    replied: str

@dataclass
class Fact:
    person_id: str
    text: str
    created_at: float

@dataclass
class RenderState:
    person: str
    text: str
    card: dict | None = None
