import json, pathlib
from dataclasses import asdict
from tvagent.core.models import Person, Turn, Fact

class JsonMemory:
    def __init__(self, root: pathlib.Path):
        self.root = pathlib.Path(root)

    def _dir(self, person_id: str) -> pathlib.Path:
        d = self.root / person_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def upsert_person(self, person: Person) -> None:
        (self._dir(person.id) / "profile.json").write_text(json.dumps(asdict(person)))

    def get_person(self, person_id: str) -> Person | None:
        f = self.root / person_id / "profile.json"
        if not f.exists(): return None
        return Person(**json.loads(f.read_text()))

    def list_people(self) -> list[Person]:
        if not self.root.exists(): return []
        out = []
        for d in self.root.iterdir():
            p = self.get_person(d.name)
            if p: out.append(p)
        return out

    def save_turn(self, turn: Turn) -> None:
        with (self._dir(turn.person_id) / "turns.jsonl").open("a") as fh:
            fh.write(json.dumps(asdict(turn)) + "\n")

    def recent_turns(self, person_id: str, n: int) -> list[Turn]:
        f = self.root / person_id / "turns.jsonl"
        if not f.exists(): return []
        lines = f.read_text().splitlines()[-n:]
        return [Turn(**json.loads(l)) for l in lines]

    def add_fact(self, fact: Fact) -> None:
        with (self._dir(fact.person_id) / "facts.jsonl").open("a") as fh:
            fh.write(json.dumps(asdict(fact)) + "\n")

    def get_facts(self, person_id: str) -> list[Fact]:
        f = self.root / person_id / "facts.jsonl"
        if not f.exists(): return []
        return [Fact(**json.loads(l)) for l in f.read_text().splitlines()]
