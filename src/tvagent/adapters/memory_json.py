import json
import pathlib
from dataclasses import asdict

from tvagent.core.models import Fact, Person, Turn


class JsonMemory:
    def __init__(self, root: pathlib.Path) -> None:
        self.root = pathlib.Path(root)

    def _person_dir(self, person_id: str) -> pathlib.Path:
        # person_id can come from an untrusted name (console enroll / CLI); a value
        # like "../x" would escape the memory root. Require a direct child of root.
        d = (self.root / person_id).resolve()
        if d.parent != self.root.resolve():
            raise ValueError(f"unsafe person_id: {person_id!r}")
        return d

    def _dir(self, person_id: str) -> pathlib.Path:
        d = self._person_dir(person_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def upsert_person(self, person: Person) -> None:
        (self._dir(person.id) / "profile.json").write_text(json.dumps(asdict(person)))

    def get_person(self, person_id: str) -> Person | None:
        f = self._person_dir(person_id) / "profile.json"
        if not f.exists():
            return None
        return Person(**json.loads(f.read_text()))

    def list_people(self) -> list[Person]:
        if not self.root.exists():
            return []
        out: list[Person] = []
        for d in self.root.iterdir():
            p = self.get_person(d.name)
            if p:
                out.append(p)
        return out

    def save_turn(self, turn: Turn) -> None:
        with (self._dir(turn.person_id) / "turns.jsonl").open("a") as fh:
            fh.write(json.dumps(asdict(turn)) + "\n")

    def recent_turns(self, person_id: str, n: int) -> list[Turn]:
        f = self._person_dir(person_id) / "turns.jsonl"
        if not f.exists():
            return []
        lines = f.read_text().splitlines()[-n:]
        return [Turn(**json.loads(line)) for line in lines]

    def add_fact(self, fact: Fact) -> None:
        with (self._dir(fact.person_id) / "facts.jsonl").open("a") as fh:
            fh.write(json.dumps(asdict(fact)) + "\n")

    def get_facts(self, person_id: str) -> list[Fact]:
        f = self._person_dir(person_id) / "facts.jsonl"
        if not f.exists():
            return []
        return [Fact(**json.loads(line)) for line in f.read_text().splitlines()]
