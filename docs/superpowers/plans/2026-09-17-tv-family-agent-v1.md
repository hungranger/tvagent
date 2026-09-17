# TV Family Agent v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a wake-word-gated, speaker-aware voice agent (POC on PC) that identifies which family member is speaking, answers via Claude with per-person memory, and speaks + shows the reply.

**Architecture:** Ports & adapters (hexagonal). A pure `Orchestrator` depends only on interfaces (`WakeWord`, `AudioCapture`, `SpeakerID`, `STT`, `LLM`, `TTS`, `MemoryStore`, `Display`). POC adapters run on a PC; hardware phase swaps only edge adapters. STT/TTS/VAD adapters borrow backends validated by huggingface/speech-to-speech (Path A) but we own the loop.

**Tech Stack:** Python 3.11+, `anthropic` SDK (Claude), `faster-whisper` (STT), `piper-tts` (TTS), `speechbrain` (speaker ID), `openwakeword` (wake), `webrtcvad`/`silero` (VAD), `websockets` + static HTML (display), `pytest` (tests).

**Spec:** `docs/superpowers/specs/2026-09-17-tv-family-agent-design.md`

## Global Constraints

- **Modularity is a hard requirement.** The `Orchestrator` and everything under `core/` import ONLY from `core.ports` and `core.models` — never a concrete adapter or a backend lib. Enforced by a test (Task 4) and re-checked in Task 13 (criterion M1).
- **Every port has a fake** under `tests/fakes.py`. Core tests run with zero hardware and zero paid API calls (M3).
- **TDD always:** write the failing test, watch it fail, minimal impl, watch it pass, commit. One behavior per test.
- **No non-commercial model weights.** Only MIT/Apache/CC-BY backends wired in; each recorded in `LICENSES.md` (L1). Never wire ChatTTS (CC-BY-NC) or an unread Qwen license.
- **Claude:** model id `claude-opus-5` via the `anthropic` SDK. For voice latency, use `output_config={"effort": "low"}` (tuning knob, documented) — do NOT switch model without the user's say-so. Read the `claude-api` skill before editing the LLM adapter.
- **Python:** 3.11+. Package under `src/tvagent/`.
- **Lint/type gate (added after Task 10):** `ruff check .` and `pyright` MUST pass clean. Ruff runs a comprehensive rule set including `PLR2004` (magic values) — `src/` app code has NO magic numbers/strings; every literal is a named constant. Pyright runs in `strict` mode. Tasks 11–13 must satisfy this gate; Task 13's test gate runs both.

---

## File Structure

```
tvagent/
  pyproject.toml                     # deps, pytest config, ruff
  LICENSES.md                        # per-model license record (Task 12)
  src/tvagent/
    core/
      models.py        # AudioClip, PersonId, Person, Turn, Fact, RenderState, GUEST
      ports.py         # 8 Protocol interfaces
      orchestrator.py  # the turn loop; imports only models + ports
    adapters/
      memory_json.py   # MemoryStore -> JSON files
      llm_claude.py    # LLM -> Claude
      stt_whisper.py   # STT -> faster-whisper
      speakerid_ecapa.py # SpeakerID -> SpeechBrain ECAPA + enroll
      wakeword_oww.py  # WakeWord -> openWakeWord
      audio_vad.py     # AudioCapture -> mic + VAD
      tts_piper.py     # TTS -> Piper
      display_web.py   # Display -> websocket server
    web/index.html     # kiosk page (browser window for POC)
    config.py          # which adapter per port, from env/dict
    app.py             # wiring + run loop entrypoint
    enroll.py          # CLI: record + register a family voice
  tests/
    fakes.py           # fake impl of every port
    fixtures/          # small .wav clips, sample voice embeddings
    test_*.py
```

Each file has one responsibility. Files that change together (an adapter + its test) stay paired.

---

### Task 1: Scaffold + domain models

**Files:**
- Create: `pyproject.toml`, `src/tvagent/__init__.py`, `src/tvagent/core/__init__.py`, `src/tvagent/core/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: dataclasses `AudioClip(samples: bytes, sample_rate: int)`, `Person(id: str, name: str, embedding: list[float], prefs: dict)`, `Turn(person_id: str, ts: float, said: str, replied: str)`, `Fact(person_id: str, text: str, created_at: float)`, `RenderState(person: str, text: str, card: dict | None)`; constant `GUEST = "guest"`. `PersonId = str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from tvagent.core.models import AudioClip, Person, Turn, RenderState, GUEST

def test_models_construct():
    clip = AudioClip(samples=b"\x00\x01", sample_rate=16000)
    assert clip.sample_rate == 16000
    p = Person(id="dad", name="Dad", embedding=[0.1, 0.2], prefs={"tone": "adult"})
    assert p.name == "Dad"
    t = Turn(person_id="dad", ts=1.0, said="hi", replied="hello")
    assert t.said == "hi"
    assert RenderState(person="Dad", text="hello", card=None).card is None
    assert GUEST == "guest"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: tvagent.core.models`.

- [ ] **Step 3: Write pyproject + minimal implementation**

```toml
# pyproject.toml
[project]
name = "tvagent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest", "ruff"]
run = ["anthropic", "faster-whisper", "piper-tts", "speechbrain", "openwakeword", "webrtcvad", "websockets", "sounddevice", "numpy"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"
```

```python
# src/tvagent/core/models.py
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
```

Create empty `src/tvagent/__init__.py` and `src/tvagent/core/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/tvagent tests/test_models.py
git commit -m "feat: scaffold + domain models"
```

---

### Task 2: Ports (interfaces) + fakes

**Files:**
- Create: `src/tvagent/core/ports.py`, `tests/fakes.py`
- Test: `tests/test_fakes.py`

**Interfaces:**
- Consumes: models from Task 1.
- Produces: `Protocol` classes — `WakeWord.wait() -> None`; `AudioCapture.capture() -> AudioClip`; `SpeakerID.identify(clip) -> PersonId` and `enroll(name, clip) -> Person`; `STT.transcribe(clip) -> str`; `LLM.respond(system: str, user: str, history: list[tuple[str,str]]) -> str`; `TTS.speak(text) -> None`; `MemoryStore.get_person(id) -> Person | None`, `list_people() -> list[Person]`, `save_turn(turn)`, `recent_turns(person_id, n) -> list[Turn]`, `get_facts(person_id) -> list[Fact]`, `add_fact(fact)`, `upsert_person(person)`; `Display.render(state: RenderState) -> None`. Fakes for all eight in `tests/fakes.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fakes.py
from tvagent.core.models import AudioClip, RenderState
from tests.fakes import (FakeWakeWord, FakeAudioCapture, FakeSpeakerID, FakeSTT,
                         FakeLLM, FakeTTS, FakeMemory, FakeDisplay)

def test_fakes_satisfy_ports():
    clip = AudioClip(samples=b"x", sample_rate=16000)
    assert FakeAudioCapture(clip).capture() is clip
    assert FakeSpeakerID(person_id="dad").identify(clip) == "dad"
    assert FakeSTT("hi there").transcribe(clip) == "hi there"
    assert FakeLLM("reply").respond("sys", "hi", []) == "reply"
    d = FakeDisplay(); d.render(RenderState(person="Dad", text="hello"))
    assert d.last.text == "hello"
    m = FakeMemory(); assert m.get_person("nope") is None
    FakeTTS().speak("hi"); FakeWakeWord().wait()  # no raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fakes.py -v`
Expected: FAIL — `ModuleNotFoundError: tvagent.core.ports` / `tests.fakes`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tvagent/core/ports.py
from typing import Protocol
from tvagent.core.models import AudioClip, Person, Turn, Fact, RenderState, PersonId

class WakeWord(Protocol):
    def wait(self) -> None: ...

class AudioCapture(Protocol):
    def capture(self) -> AudioClip: ...

class SpeakerID(Protocol):
    def identify(self, clip: AudioClip) -> PersonId: ...
    def enroll(self, name: str, clip: AudioClip) -> Person: ...

class STT(Protocol):
    def transcribe(self, clip: AudioClip) -> str: ...

class LLM(Protocol):
    def respond(self, system: str, user: str, history: list[tuple[str, str]]) -> str: ...

class TTS(Protocol):
    def speak(self, text: str) -> None: ...

class MemoryStore(Protocol):
    def get_person(self, person_id: str) -> Person | None: ...
    def list_people(self) -> list[Person]: ...
    def upsert_person(self, person: Person) -> None: ...
    def save_turn(self, turn: Turn) -> None: ...
    def recent_turns(self, person_id: str, n: int) -> list[Turn]: ...
    def get_facts(self, person_id: str) -> list[Fact]: ...
    def add_fact(self, fact: Fact) -> None: ...

class Display(Protocol):
    def render(self, state: RenderState) -> None: ...
```

```python
# tests/fakes.py
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
```

Add empty `tests/__init__.py` so `tests.fakes` imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fakes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tvagent/core/ports.py tests/fakes.py tests/__init__.py
git commit -m "feat: ports + fakes for all components"
```

---

### Task 3: MemoryStore JSON adapter

**Files:**
- Create: `src/tvagent/adapters/__init__.py`, `src/tvagent/adapters/memory_json.py`
- Test: `tests/test_memory_json.py`

**Interfaces:**
- Consumes: `MemoryStore` protocol, models.
- Produces: `JsonMemory(root: pathlib.Path)` implementing `MemoryStore`. On-disk layout: `root/<person_id>/profile.json`, `.../turns.jsonl`, `.../facts.jsonl`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory_json.py
from tvagent.core.models import Person, Turn, Fact, GUEST
from tvagent.adapters.memory_json import JsonMemory

def test_person_and_turn_roundtrip(tmp_path):
    m = JsonMemory(tmp_path)
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={"tone": "adult"}))
    assert m.get_person("dad").name == "Dad"
    m.save_turn(Turn(person_id="dad", ts=1.0, said="hi", replied="yo"))
    m.save_turn(Turn(person_id="dad", ts=2.0, said="bye", replied="cya"))
    recent = m.recent_turns("dad", 1)
    assert len(recent) == 1 and recent[0].said == "bye"

def test_facts_and_guest_isolation(tmp_path):
    m = JsonMemory(tmp_path)
    m.add_fact(Fact(person_id="dad", text="standup 9am", created_at=1.0))
    assert m.get_facts("dad")[0].text == "standup 9am"
    # guest writes never leak into an enrolled person
    m.save_turn(Turn(person_id=GUEST, ts=3.0, said="who am i", replied="a guest"))
    assert m.recent_turns("dad", 10) == []
    assert m.get_facts(GUEST) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_json.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tvagent/adapters/memory_json.py
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
```

Create empty `src/tvagent/adapters/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory_json.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/tvagent/adapters/__init__.py src/tvagent/adapters/memory_json.py tests/test_memory_json.py
git commit -m "feat: JSON-file MemoryStore adapter with guest isolation"
```

---

### Task 4: Orchestrator (core loop)

**Files:**
- Create: `src/tvagent/core/orchestrator.py`
- Test: `tests/test_orchestrator.py`, `tests/test_core_isolation.py`

**Interfaces:**
- Consumes: all eight ports, models.
- Produces: `Orchestrator(wake, capture, speaker, stt, llm, tts, memory, display)` with `run_once() -> Turn`. Prompt-building is a method `_build(person: Person | None, facts, history, said) -> tuple[str, str]` returning `(system, user)`.

Behavior of `run_once()`: wait for wake → capture → identify → transcribe → resolve person (or GUEST) → load facts + recent turns (skip for GUEST) → build a prompt tuned to the person → LLM respond → TTS speak + Display render → save turn (for GUEST too, under the guest id) → return the Turn.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrator.py
import time
from tvagent.core.models import AudioClip, Person
from tvagent.core.orchestrator import Orchestrator
from tests.fakes import (FakeWakeWord, FakeAudioCapture, FakeSpeakerID, FakeSTT,
                         FakeLLM, FakeTTS, FakeMemory, FakeDisplay)

def _orch(memory, speaker_id, said="what's my day", reply="Standup at 9"):
    clip = AudioClip(samples=b"x", sample_rate=16000)
    llm = FakeLLM(reply)
    tts, disp = FakeTTS(), FakeDisplay()
    orch = Orchestrator(FakeWakeWord(), FakeAudioCapture(clip),
                        FakeSpeakerID(speaker_id), FakeSTT(said),
                        llm, tts, memory, disp)
    return orch, llm, tts, disp

def test_turn_tuned_to_person_and_persisted():
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={"tone": "adult"}))
    orch, llm, tts, disp = _orch(m, "dad")
    turn = orch.run_once()
    assert "Dad" in llm.last_system          # F5: prompt tuned to who
    assert turn.replied == "Standup at 9"
    assert tts.spoken == ["Standup at 9"]    # F7
    assert disp.last.text == "Standup at 9"  # F8
    assert m.recent_turns("dad", 1)[0].said == "what's my day"  # F9

def test_memory_recall_reaches_prompt():
    from tvagent.core.models import Fact
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    m.add_fact(Fact(person_id="dad", text="allergic to peanuts", created_at=1.0))
    orch, llm, _, _ = _orch(m, "dad", said="what am I allergic to")
    orch.run_once()
    assert "peanuts" in llm.last_system      # F10: fact reaches the prompt

def test_guest_does_not_read_or_write_enrolled_memory():
    from tvagent.core.models import Fact
    m = FakeMemory()
    m.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={}))
    m.add_fact(Fact(person_id="dad", text="secret", created_at=1.0))
    orch, llm, _, _ = _orch(m, "guest")
    orch.run_once()
    assert "secret" not in llm.last_system   # F11: guest can't read Dad
    assert m.recent_turns("dad", 10) == []   # F11: guest write didn't touch Dad
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py -v`
Expected: FAIL — `tvagent.core.orchestrator` missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tvagent/core/orchestrator.py
import time
from tvagent.core.models import Turn, Person, GUEST
from tvagent.core import ports

class Orchestrator:
    def __init__(self, wake: ports.WakeWord, capture: ports.AudioCapture,
                 speaker: ports.SpeakerID, stt: ports.STT, llm: ports.LLM,
                 tts: ports.TTS, memory: ports.MemoryStore, display: ports.Display):
        self.wake, self.capture, self.speaker = wake, capture, speaker
        self.stt, self.llm, self.tts = stt, llm, tts
        self.memory, self.display = memory, display

    def _build(self, person, facts, history, said):
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
            facts, history = [], []
        else:
            facts = self.memory.get_facts(person.id)
            history = self.memory.recent_turns(person.id, 5)
        system, user = self._build(person, facts, history, said)
        reply = self.llm.respond(system, user, [(h.said, h.replied) for h in history])
        self.tts.speak(reply)
        from tvagent.core.models import RenderState
        self.display.render(RenderState(person=(person.name if person else "Guest"), text=reply))
        turn = Turn(person_id=person_id, ts=time.time(), said=said, replied=reply)
        self.memory.save_turn(turn)
        return turn
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Write the core-isolation test (M1)**

```python
# tests/test_core_isolation.py
import ast, pathlib

def test_core_imports_only_core():
    # anchor off this file, not CWD, so it can't vacuously pass from another dir
    repo = pathlib.Path(__file__).resolve().parent.parent
    core_dir = repo / "src" / "tvagent" / "core"
    files = list(core_dir.glob("*.py"))
    assert len(files) >= 3, f"isolation test found no core files (looked in {core_dir})"
    for pyfile in files:
        tree = ast.parse(pyfile.read_text())
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.ImportFrom): mod = node.module or ""
            elif isinstance(node, ast.Import): mod = node.names[0].name
            if mod and mod.startswith("tvagent") and not mod.startswith("tvagent.core"):
                raise AssertionError(f"{pyfile.name} imports non-core module {mod}")
```

- [ ] **Step 6: Run isolation test**

Run: `pytest tests/test_core_isolation.py -v`
Expected: PASS — core imports only `tvagent.core.*`.

- [ ] **Step 7: Commit**

```bash
git add src/tvagent/core/orchestrator.py tests/test_orchestrator.py tests/test_core_isolation.py
git commit -m "feat: orchestrator turn loop + core isolation guard"
```

---

### Task 5: LLM Claude adapter

**Files:**
- Create: `src/tvagent/adapters/llm_claude.py`
- Test: `tests/test_llm_claude.py`

**Interfaces:**
- Consumes: `LLM` protocol.
- Produces: `ClaudeLLM(model="claude-opus-5", client=None)` implementing `respond`. Injectable `client` so tests pass a stub (no network).

**Before coding:** read the `claude-api` skill (model id, SDK shape). Model `claude-opus-5`; low effort for voice latency; text extracted from `message.content` text blocks.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_claude.py
from tvagent.adapters.llm_claude import ClaudeLLM

class _StubMessages:
    def __init__(self, outer): self.outer = outer
    def create(self, **kwargs):
        self.outer.seen = kwargs
        class Block: type = "text"; text = "hi Dad"
        class Msg: content = [Block()]
        return Msg()

class _StubClient:
    def __init__(self): self.messages = _StubMessages(self)

def test_respond_extracts_text_and_sends_system():
    stub = _StubClient()
    llm = ClaudeLLM(client=stub)
    out = llm.respond("You are talking to Dad.", "hello", [])
    assert out == "hi Dad"
    assert stub.seen["model"] == "claude-opus-5"
    assert stub.seen["system"] == "You are talking to Dad."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_claude.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tvagent/adapters/llm_claude.py
class ClaudeLLM:
    def __init__(self, model: str = "claude-opus-5", client=None, max_tokens: int = 512):
        self.model, self.max_tokens = model, max_tokens
        if client is None:
            from anthropic import Anthropic
            client = Anthropic()
        self.client = client

    def respond(self, system: str, user: str, history: list[tuple[str, str]]) -> str:
        messages = []
        for said, replied in history:
            messages.append({"role": "user", "content": said})
            messages.append({"role": "assistant", "content": replied})
        messages.append({"role": "user", "content": user})
        msg = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system,
            output_config={"effort": "low"},  # voice latency knob
            messages=messages,
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_claude.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tvagent/adapters/llm_claude.py tests/test_llm_claude.py
git commit -m "feat: Claude LLM adapter (opus-5, low effort, injectable client)"
```

---

### Task 6: STT faster-whisper adapter

**Files:**
- Create: `src/tvagent/adapters/stt_whisper.py`
- Test: `tests/test_stt_whisper.py`, fixture `tests/fixtures/hello.wav` (a short real clip saying a known phrase)

**Interfaces:**
- Consumes: `STT` protocol, `AudioClip`.
- Produces: `WhisperSTT(model_size="base")` implementing `transcribe`. Injectable `_model` for a stub test; a real component test gated on the lib being installed.

- [ ] **Step 0: Record the audio fixture (required for the live proof in Task 13)**

Record a ~2s mono 16kHz WAV of yourself saying "hello there" to `tests/fixtures/hello.wav`:

```bash
mkdir -p tests/fixtures
python -c "import sounddevice as sd, wave; sr=16000; \
d=sd.rec(int(2*sr),samplerate=sr,channels=1,dtype='int16'); sd.wait(); \
w=wave.open('tests/fixtures/hello.wav','wb'); w.setnchannels(1); w.setsampwidth(2); \
w.setframerate(sr); w.writeframes(d.tobytes()); w.close(); print('saved')"
```

This fixture gates the component test below and the live e2e in Task 13; without it Task 13's live proof fails when a key is present (it must not silently skip).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stt_whisper.py
import pytest
from tvagent.core.models import AudioClip
from tvagent.adapters.stt_whisper import WhisperSTT

class _Seg:
    def __init__(self, t): self.text = t

class _StubModel:
    def transcribe(self, audio, **kw): return ([_Seg("hello there")], None)

def test_transcribe_joins_segments():
    stt = WhisperSTT(_model=_StubModel())
    out = stt.transcribe(AudioClip(samples=b"\x00\x00", sample_rate=16000))
    assert out == "hello there"

@pytest.mark.component
def test_real_whisper_on_fixture():
    pytest.importorskip("faster_whisper")
    import wave, pathlib
    f = pathlib.Path("tests/fixtures/hello.wav")
    if not f.exists(): pytest.skip("record tests/fixtures/hello.wav saying 'hello there'")
    with wave.open(str(f)) as w:
        clip = AudioClip(samples=w.readframes(w.getnframes()), sample_rate=w.getframerate())
    text = WhisperSTT(model_size="base").transcribe(clip).lower()
    assert "hello" in text  # F4: within tolerance
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stt_whisper.py::test_transcribe_joins_segments -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tvagent/adapters/stt_whisper.py
import numpy as np
from tvagent.core.models import AudioClip

class WhisperSTT:
    def __init__(self, model_size: str = "base", _model=None):
        if _model is None:
            from faster_whisper import WhisperModel
            _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self._model = _model

    def transcribe(self, clip: AudioClip) -> str:
        audio = np.frombuffer(clip.samples, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self._model.transcribe(audio, language="en")
        return " ".join(s.text.strip() for s in segments).strip()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_stt_whisper.py -v`
Expected: unit PASS; component PASS if fixture recorded, else SKIP.

- [ ] **Step 5: Commit**

```bash
git add src/tvagent/adapters/stt_whisper.py tests/test_stt_whisper.py
git commit -m "feat: faster-whisper STT adapter"
```

---

### Task 7: SpeakerID (ECAPA) adapter + enrollment

**Files:**
- Create: `src/tvagent/adapters/speakerid_ecapa.py`, `src/tvagent/enroll.py`
- Test: `tests/test_speakerid.py`

**Interfaces:**
- Consumes: `SpeakerID` protocol, `MemoryStore`, models.
- Produces: `EcapaSpeakerID(memory, threshold=0.25, _embed=None)` — `enroll(name, clip)` computes an embedding + `upsert_person`; `identify(clip)` returns the best-matching enrolled `PersonId` above threshold else `GUEST`. `_embed(clip) -> list[float]` is injectable for tests. `enroll.py` is a CLI that records ~30s from the mic and calls `enroll`.

The matching math (cosine similarity + threshold) is pure and fully unit-tested with a stub embedder — no model download in CI.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_speakerid.py
from tvagent.core.models import AudioClip
from tvagent.adapters.speakerid_ecapa import EcapaSpeakerID, cosine
from tvagent.adapters.memory_json import JsonMemory

def test_cosine_basic():
    assert abs(cosine([1,0], [1,0]) - 1.0) < 1e-6
    assert abs(cosine([1,0], [0,1]) - 0.0) < 1e-6

def _clip(): return AudioClip(samples=b"x", sample_rate=16000)

def test_enroll_then_identify_matches(tmp_path):
    m = JsonMemory(tmp_path)
    vecs = {"dad": [1.0, 0.0], "mom": [0.0, 1.0]}
    def embed(clip): return embed.next
    sid = EcapaSpeakerID(m, threshold=0.5, _embed=embed)
    embed.next = vecs["dad"]; sid.enroll("Dad", _clip())
    embed.next = vecs["mom"]; sid.enroll("Mom", _clip())
    embed.next = [0.9, 0.1]  # close to Dad
    assert sid.identify(_clip()) == "dad"          # F3: right person

def test_stranger_falls_back_to_guest(tmp_path):
    m = JsonMemory(tmp_path)
    def embed(clip): return embed.next
    sid = EcapaSpeakerID(m, threshold=0.8, _embed=embed)
    embed.next = [1.0, 0.0]; sid.enroll("Dad", _clip())
    embed.next = [0.0, 1.0]  # orthogonal -> below threshold
    assert sid.identify(_clip()) == "guest"        # F3: stranger -> GUEST
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_speakerid.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tvagent/adapters/speakerid_ecapa.py
import math
import numpy as np
from tvagent.core.models import AudioClip, Person, GUEST

def cosine(a, b) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)

class EcapaSpeakerID:
    def __init__(self, memory, threshold: float = 0.25, _embed=None):
        self.memory, self.threshold = memory, threshold
        self._embed = _embed or self._default_embed
        self._model = None

    def _default_embed(self, clip: AudioClip) -> list[float]:
        if self._model is None:
            from speechbrain.inference.speaker import EncoderClassifier
            self._model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb")
        import torch
        audio = np.frombuffer(clip.samples, dtype=np.int16).astype(np.float32) / 32768.0
        emb = self._model.encode_batch(torch.tensor(audio).unsqueeze(0))
        return emb.squeeze().detach().cpu().tolist()

    def enroll(self, name: str, clip: AudioClip) -> Person:
        person = Person(id=name.lower(), name=name, embedding=self._embed(clip), prefs={})
        self.memory.upsert_person(person)
        return person

    def identify(self, clip: AudioClip) -> str:
        vec = self._embed(clip)
        best_id, best = GUEST, self.threshold
        for p in self.memory.list_people():
            if p.id == GUEST: continue
            score = cosine(vec, p.embedding)
            if score >= best:
                best, best_id = score, p.id
        return best_id
```

```python
# src/tvagent/enroll.py
"""CLI: python -m tvagent.enroll "Dad"  — records ~30s and registers the voice."""
import sys, pathlib
from tvagent.adapters.memory_json import JsonMemory
from tvagent.adapters.speakerid_ecapa import EcapaSpeakerID
from tvagent.adapters.audio_vad import record_seconds  # from Task 8

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else input("Name: ")
    clip = record_seconds(30)
    sid = EcapaSpeakerID(JsonMemory(pathlib.Path("data/memory")))
    p = sid.enroll(name, clip)
    print(f"enrolled {p.name} ({p.id})")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_speakerid.py -v`
Expected: PASS (all four).

- [ ] **Step 5: Commit**

```bash
git add src/tvagent/adapters/speakerid_ecapa.py src/tvagent/enroll.py tests/test_speakerid.py
git commit -m "feat: ECAPA speaker-ID adapter (cosine match + guest fallback) + enroll CLI"
```

---

### Task 8: WakeWord + AudioCapture (VAD) adapters

**Files:**
- Create: `src/tvagent/adapters/wakeword_oww.py`, `src/tvagent/adapters/audio_vad.py`
- Test: `tests/test_audio_vad.py`

**Interfaces:**
- Consumes: `WakeWord`, `AudioCapture` protocols, `AudioClip`.
- Produces: `OwwWakeWord(phrase_model=..., _detector=None).wait()`; `VadCapture(sample_rate=16000, _source=None).capture() -> AudioClip` that reads frames until trailing silence; module fn `record_seconds(n) -> AudioClip` used by enrollment. Frame source injectable for tests (no mic in CI).

The end-of-speech logic (stop after N silent frames) is pure and unit-tested with a scripted frame source.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_audio_vad.py
from tvagent.adapters.audio_vad import VadCapture

class _ScriptedSource:
    """Yields (frame_bytes, is_speech) then signals stream end."""
    def __init__(self, script): self.script = list(script)
    def frames(self):
        for frame, speech in self.script:
            yield frame, speech

def test_capture_stops_after_trailing_silence():
    # 3 speech frames, then 2 silent frames (silence_limit=2) -> capture ends
    script = [(b"a", True), (b"b", True), (b"c", True), (b"", False), (b"", False)]
    cap = VadCapture(sample_rate=16000, silence_limit=2, _source=_ScriptedSource(script))
    clip = cap.capture()
    assert clip.samples == b"abc"          # F2: bounded capture to silence
    assert clip.sample_rate == 16000

def test_wakeword_returns_only_after_detection():
    # F1: wait() must not return until a frame scores above threshold
    from tvagent.adapters.wakeword_oww import OwwWakeWord
    import numpy as np
    frames = _ScriptedSource([(np.zeros(1, dtype=np.int16).tobytes(), False)] * 3)
    scores = iter([{"w": 0.1}, {"w": 0.2}, {"w": 0.9}])  # fires on 3rd frame
    class _Det:
        def predict(self, arr): return next(scores)
    ww = OwwWakeWord(_detector=_Det(), _source=frames)
    ww.wait()  # returns (does not hang / raise) exactly when score>0.5 arrives
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_audio_vad.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tvagent/adapters/audio_vad.py
from tvagent.core.models import AudioClip

class VadCapture:
    def __init__(self, sample_rate=16000, silence_limit=15, _source=None):
        self.sample_rate, self.silence_limit = sample_rate, silence_limit
        self._source = _source or _MicSource(sample_rate)

    def capture(self) -> AudioClip:
        buf, silent, started = bytearray(), 0, False
        for frame, is_speech in self._source.frames():
            if is_speech:
                buf.extend(frame); started, silent = True, 0
            elif started:
                silent += 1
                if silent >= self.silence_limit:
                    break
        return AudioClip(samples=bytes(buf), sample_rate=self.sample_rate)

class _MicSource:
    def __init__(self, sample_rate):
        import webrtcvad, sounddevice  # imported lazily so CI without a mic still tests logic
        self.sample_rate = sample_rate
        self.vad = webrtcvad.Vad(2)
        self.sd = sounddevice
    def frames(self):
        frame_ms, sr = 30, self.sample_rate
        n = int(sr * frame_ms / 1000)
        with self.sd.RawInputStream(samplerate=sr, blocksize=n, dtype="int16",
                                    channels=1) as stream:
            while True:
                data, _ = stream.read(n)
                frame = bytes(data)
                yield frame, self.vad.is_speech(frame, sr)

def record_seconds(seconds: int, sample_rate: int = 16000) -> AudioClip:
    import sounddevice, numpy as np
    rec = sounddevice.rec(int(seconds * sample_rate), samplerate=sample_rate,
                          channels=1, dtype="int16")
    sounddevice.wait()
    return AudioClip(samples=rec.tobytes(), sample_rate=sample_rate)
```

```python
# src/tvagent/adapters/wakeword_oww.py
class OwwWakeWord:
    def __init__(self, model_name: str = "hey_jarvis", _detector=None, _source=None):
        self.model_name, self._detector, self._source = model_name, _detector, _source

    def _ensure(self):
        if self._detector is None:
            from openwakeword.model import Model
            self._detector = Model(wakeword_models=[self.model_name])
        if self._source is None:
            from tvagent.adapters.audio_vad import _MicSource
            self._source = _MicSource(16000)

    def wait(self) -> None:
        self._ensure()
        for frame, _ in self._source.frames():
            import numpy as np
            scores = self._detector.predict(np.frombuffer(frame, dtype=np.int16))
            if any(v > 0.5 for v in scores.values()):
                return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_audio_vad.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tvagent/adapters/audio_vad.py src/tvagent/adapters/wakeword_oww.py tests/test_audio_vad.py
git commit -m "feat: VAD capture (stops on silence) + openWakeWord adapter"
```

---

### Task 9: TTS Piper adapter

**Files:**
- Create: `src/tvagent/adapters/tts_piper.py`
- Test: `tests/test_tts_piper.py`

**Interfaces:**
- Consumes: `TTS` protocol.
- Produces: `PiperTTS(voice=..., _synth=None, _play=None).speak(text)` — synthesizes audio and plays it. Both synth and play injectable so the unit test asserts wiring without audio hardware.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tts_piper.py
from tvagent.adapters.tts_piper import PiperTTS

def test_speak_synthesizes_then_plays():
    calls = {}
    def synth(text): calls["text"] = text; return b"PCMDATA"
    def play(pcm): calls["played"] = pcm
    PiperTTS(_synth=synth, _play=play).speak("hello Dad")
    assert calls["text"] == "hello Dad"
    assert calls["played"] == b"PCMDATA"

def test_empty_text_does_not_play():
    played = []
    PiperTTS(_synth=lambda t: b"x", _play=lambda p: played.append(p)).speak("  ")
    assert played == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tts_piper.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tvagent/adapters/tts_piper.py
class PiperTTS:
    def __init__(self, voice: str = "en_US-amy-medium", _synth=None, _play=None):
        self.voice = voice
        self._synth = _synth or self._default_synth
        self._play = _play or self._default_play
        self._model = None

    def _default_synth(self, text: str) -> bytes:
        from piper import PiperVoice
        if self._model is None:
            self._model = PiperVoice.load(self.voice)
        import io, wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            self._model.synthesize(text, wf)
        return buf.getvalue()

    def _default_play(self, pcm: bytes) -> None:
        import io, wave, sounddevice, numpy as np
        with wave.open(io.BytesIO(pcm)) as wf:
            data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
            sounddevice.play(data, wf.getframerate()); sounddevice.wait()

    def speak(self, text: str) -> None:
        if not text.strip(): return
        self._play(self._synth(text))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tts_piper.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add src/tvagent/adapters/tts_piper.py tests/test_tts_piper.py
git commit -m "feat: Piper TTS adapter (injectable synth/play)"
```

---

### Task 10: Display web adapter

**Files:**
- Create: `src/tvagent/adapters/display_web.py`, `src/tvagent/web/index.html`
- Test: `tests/test_display_web.py`

**Interfaces:**
- Consumes: `Display` protocol, `RenderState`.
- Produces: `WebDisplay(port=8765)` implementing `render(state)` by broadcasting JSON `{"person","text","card"}` to connected browser clients over a websocket. `render` must work before any client connects (buffer last state). A pure `state_to_json(state) -> str` helper is unit-tested; the websocket server itself is smoke-tested for start/serve.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_display_web.py
import json
from tvagent.core.models import RenderState
from tvagent.adapters.display_web import state_to_json

def test_state_to_json_shape():
    s = RenderState(person="Dad", text="hi", card={"kind": "weather"})
    out = json.loads(state_to_json(s))
    assert out == {"person": "Dad", "text": "hi", "card": {"kind": "weather"}}

def test_state_to_json_null_card():
    out = json.loads(state_to_json(RenderState(person="Guest", text="hello")))
    assert out["card"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_display_web.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tvagent/adapters/display_web.py
import json, threading, asyncio
from tvagent.core.models import RenderState

def state_to_json(state: RenderState) -> str:
    return json.dumps({"person": state.person, "text": state.text, "card": state.card})

class WebDisplay:
    def __init__(self, port: int = 8765):
        self.port = port
        self._clients = set()
        self._last = state_to_json(RenderState(person="", text="Listening…"))
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        import websockets
        asyncio.set_event_loop(self._loop)
        async def handler(ws):
            self._clients.add(ws)
            await ws.send(self._last)
            try:
                async for _ in ws: pass
            finally:
                self._clients.discard(ws)
        async def main():
            async with websockets.serve(handler, "localhost", self.port):
                await asyncio.Future()
        self._loop.run_until_complete(main())

    def render(self, state: RenderState) -> None:
        self._last = state_to_json(state)
        async def broadcast():
            for ws in list(self._clients):
                try: await ws.send(self._last)
                except Exception: self._clients.discard(ws)
        asyncio.run_coroutine_threadsafe(broadcast(), self._loop)
```

```html
<!-- src/tvagent/web/index.html -->
<!doctype html><meta charset="utf-8"><title>TV Agent</title>
<style>
  :root { --bg:#0b0f14; --fg:#e8eef5; --muted:#7c8b9a; }
  html,body{height:100%;margin:0;background:var(--bg);color:var(--fg);
    font:2.5vw/1.4 system-ui,sans-serif;display:flex;align-items:center;
    justify-content:center;text-align:center}
  #who{color:var(--muted);font-size:1.5vw;letter-spacing:.1em;text-transform:uppercase}
  #text{max-width:80vw;margin-top:1vh}
  #orb{width:8vw;height:8vw;border-radius:50%;margin:0 auto 3vh;
    background:radial-gradient(circle at 40% 35%,#4fd1ff,#1567a8);
    animation:pulse 2s ease-in-out infinite}
  @keyframes pulse{50%{transform:scale(1.08);opacity:.85}}
</style>
<div><div id="orb"></div><div id="who"></div><div id="text">Connecting…</div></div>
<script>
  const ws = new WebSocket("ws://localhost:8765");
  ws.onmessage = e => {
    const s = JSON.parse(e.data);
    document.getElementById("who").textContent = s.person || "";
    document.getElementById("text").textContent = s.text || "";
  };
  ws.onclose = () => document.getElementById("text").textContent = "Disconnected";
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_display_web.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tvagent/adapters/display_web.py src/tvagent/web/index.html tests/test_display_web.py
git commit -m "feat: websocket web display + kiosk page"
```

---

### Task 11: App wiring (config-driven) + entrypoint

**Files:**
- Create: `src/tvagent/config.py`, `src/tvagent/app.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: every adapter + `Orchestrator`.
- Produces: `build_orchestrator(overrides: dict | None = None) -> Orchestrator` that constructs each adapter from config and wires the Orchestrator. `overrides` lets a test inject fakes for any port (proves M2 swap-by-config). `app.py` `main()` loops `run_once()` forever.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from tvagent.config import build_orchestrator
from tvagent.core.orchestrator import Orchestrator
from tests.fakes import (FakeWakeWord, FakeAudioCapture, FakeSpeakerID, FakeSTT,
                         FakeLLM, FakeTTS, FakeMemory, FakeDisplay)
from tvagent.core.models import AudioClip

def test_build_with_all_fakes_swapped_by_config():
    clip = AudioClip(samples=b"x", sample_rate=16000)
    orch = build_orchestrator({
        "wake": FakeWakeWord(), "capture": FakeAudioCapture(clip),
        "speaker": FakeSpeakerID("guest"), "stt": FakeSTT("hi"),
        "llm": FakeLLM("yo"), "tts": FakeTTS(),
        "memory": FakeMemory(), "display": FakeDisplay(),
    })
    assert isinstance(orch, Orchestrator)
    assert orch.run_once().replied == "yo"   # M2/M3: fully swappable, no hardware
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# src/tvagent/config.py
import pathlib
from tvagent.core.orchestrator import Orchestrator

def build_orchestrator(overrides: dict | None = None) -> Orchestrator:
    o = overrides or {}
    def get(key, factory):
        return o[key] if key in o else factory()
    memory = get("memory", lambda: _memory())
    return Orchestrator(
        wake=get("wake", lambda: _wake()),
        capture=get("capture", lambda: _capture()),
        speaker=get("speaker", lambda: _speaker(memory)),
        stt=get("stt", lambda: _stt()),
        llm=get("llm", lambda: _llm()),
        tts=get("tts", lambda: _tts()),
        memory=memory,
        display=get("display", lambda: _display()),
    )

def _memory():
    from tvagent.adapters.memory_json import JsonMemory
    return JsonMemory(pathlib.Path("data/memory"))
def _wake():
    from tvagent.adapters.wakeword_oww import OwwWakeWord; return OwwWakeWord()
def _capture():
    from tvagent.adapters.audio_vad import VadCapture; return VadCapture()
def _speaker(memory):
    from tvagent.adapters.speakerid_ecapa import EcapaSpeakerID; return EcapaSpeakerID(memory)
def _stt():
    from tvagent.adapters.stt_whisper import WhisperSTT; return WhisperSTT()
def _llm():
    from tvagent.adapters.llm_claude import ClaudeLLM; return ClaudeLLM()
def _tts():
    from tvagent.adapters.tts_piper import PiperTTS; return PiperTTS()
def _display():
    from tvagent.adapters.display_web import WebDisplay; return WebDisplay()
```

```python
# src/tvagent/app.py
"""Run the agent: python -m tvagent.app  (open src/tvagent/web/index.html in a browser)."""
from tvagent.config import build_orchestrator

def main():
    orch = build_orchestrator()
    print("Agent up. Open src/tvagent/web/index.html. Say the wake word.")
    while True:
        turn = orch.run_once()
        print(f"[{turn.person_id}] {turn.said} -> {turn.replied}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tvagent/config.py src/tvagent/app.py tests/test_config.py
git commit -m "feat: config-driven wiring + run loop entrypoint"
```

---

### Task 12: License record

**Files:**
- Create: `LICENSES.md`
- Test: `tests/test_licenses.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `LICENSES.md` recording each active model's license; test asserts no non-commercial marker (L1).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_licenses.py
import pathlib

def test_no_noncommercial_weights():
    text = pathlib.Path("LICENSES.md").read_text()
    lowered = text.lower()
    assert "-nc" not in lowered and "noncommercial" not in lowered and "non-commercial" not in lowered
    for name in ["silero", "whisper", "piper", "ecapa", "openwakeword"]:
        assert name in lowered  # each active model is recorded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_licenses.py -v`
Expected: FAIL — `LICENSES.md` missing.

- [ ] **Step 3: Write the file**

```markdown
# Model & Backend Licenses (v1)

Verify each before any commercial launch. Code of huggingface/speech-to-speech is Apache-2.0.

| Component | Model / lib | License | Commercial |
|-----------|-------------|---------|:-:|
| VAD | Silero VAD | MIT | yes |
| STT | faster-whisper (Whisper) | MIT | yes |
| TTS | Piper (en_US-amy-medium) | MIT | yes |
| Speaker ID | SpeechBrain ECAPA (spkrec-ecapa-voxceleb) | Apache-2.0 | yes |
| Wake word | openWakeWord | Apache-2.0 | yes |
| Brain | Claude API (claude-opus-5) | commercial via Anthropic API terms | yes |

Do NOT add ChatTTS (CC-BY-NC) or any `-NC` / research-only weight.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_licenses.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add LICENSES.md tests/test_licenses.py
git commit -m "docs: record model licenses; guard against NC weights"
```

---

### Task 13: Comprehensive verification (spec satisfaction + real E2E)

This is the whole-feature gate. It maps every success criterion (spec §8) to a concrete check, runs the full test gate, runs a REAL end-to-end proof (not just fakes), and produces a "What I did not verify" list. Earlier tasks proved their own units; this task proves the assembled system meets the spec.

**Files:**
- Create: `tests/test_e2e_fakes.py`, `scripts/verify_live.py`, `docs/superpowers/VERIFICATION.md`

**Interfaces:**
- Consumes: `build_orchestrator`, all adapters, fakes.
- Produces: a hermetic e2e-with-fakes test; a live proof script gated on `ANTHROPIC_API_KEY` (checked by NAME only, value never printed); a written verification report.

- [ ] **Step 1: Hermetic end-to-end test (fakes, full turn incl. recall + guest)**

```python
# tests/test_e2e_fakes.py
from tvagent.config import build_orchestrator
from tvagent.core.models import AudioClip, Person
from tests.fakes import (FakeWakeWord, FakeAudioCapture, FakeSpeakerID, FakeSTT,
                         FakeLLM, FakeTTS, FakeDisplay)
from tvagent.adapters.memory_json import JsonMemory

def test_e2e_turn_recall_and_render(tmp_path):
    # F10: a detail from an earlier turn is reflected in a later same-person turn.
    # The orchestrator writes each turn and loads recent_turns into the next prompt,
    # so turn 2's system prompt must carry turn 1's content (real save->load path,
    # not a pre-seeded fact).
    mem = JsonMemory(tmp_path)
    mem.upsert_person(Person(id="dad", name="Dad", embedding=[0.1], prefs={"tone":"adult"}))
    clip = AudioClip(samples=b"x", sample_rate=16000)
    llm, tts, disp = FakeLLM("Noted."), FakeTTS(), FakeDisplay()
    def orch(said):
        return build_orchestrator({
            "wake": FakeWakeWord(), "capture": FakeAudioCapture(clip),
            "speaker": FakeSpeakerID("dad"), "stt": FakeSTT(said),
            "llm": llm, "tts": tts, "memory": mem, "display": disp,
        })
    orch("my dog is named Rex").run_once()            # turn 1 persisted
    turn2 = orch("what did I just tell you").run_once()  # turn 2 loads history
    assert "Rex" in llm.last_system                  # F10: earlier turn recalled
    assert tts.spoken[-1] == "Noted." and disp.last.text == "Noted."  # F7/F8
    assert mem.recent_turns("dad", 2)[0].said == "my dog is named Rex"  # F9 persist
```

Run: `pytest tests/test_e2e_fakes.py -v` → Expected: PASS (proves F7/F8/F9/F10 through the real save→load path).

- [ ] **Step 2: Live E2E proof script (real STT→Claude→TTS→memory), key-gated**

```python
# scripts/verify_live.py
"""Real end-to-end proof through the ACTUAL Orchestrator.run_once().
Only the two edge adapters are overridden: wake (fires once) and capture
(returns fixture audio instead of a live mic). Everything else is real:
real SpeakerID, real Whisper, real Claude, real Piper, real JSON memory,
real Display. Proves the full spine incl. render + persisted turn (T2).
Gated on ANTHROPIC_API_KEY (checked by name; value never printed)."""
import os, sys, time, wave, pathlib
from tvagent.core.models import AudioClip, Person
from tvagent.config import build_orchestrator
from tvagent.adapters.memory_json import JsonMemory

class _OnceWake:
    def __init__(self): self._done = False
    def wait(self):
        if self._done: raise SystemExit
        self._done = True

class _FixtureCapture:
    def __init__(self, clip): self._clip = clip
    def capture(self): return self._clip

class _RecordingDisplay:
    def __init__(self): self.last = None
    def render(self, state): self.last = state

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("SKIP live e2e: ANTHROPIC_API_KEY not set"); return 0
    fx = pathlib.Path("tests/fixtures/hello.wav")
    if not fx.exists():
        # key present but no fixture -> the live proof cannot run; do NOT pass silently
        print("FAIL live e2e: ANTHROPIC_API_KEY set but tests/fixtures/hello.wav missing "
              "(record it, see Task 6 Step 0)"); return 1
    with wave.open(str(fx)) as w:
        clip = AudioClip(samples=w.readframes(w.getnframes()), sample_rate=w.getframerate())
    mem = JsonMemory(pathlib.Path("data/verify"))
    mem.upsert_person(Person(id="tester", name="Tester", embedding=[0.0], prefs={}))
    disp = _RecordingDisplay()
    orch = build_orchestrator({
        "wake": _OnceWake(), "capture": _FixtureCapture(clip),
        "memory": mem, "display": disp,
    })  # speaker, stt, llm, tts are all REAL
    t0 = time.time()
    turn = orch.run_once()
    latency = time.time() - t0
    print(f"HEARD: {turn.said!r}\nREPLIED: {turn.replied!r}\n"
          f"RENDERED: {disp.last.text!r}\nEND-TO-END LATENCY: {latency:.2f}s")
    assert turn.replied.strip(), "empty reply"                          # F6
    assert disp.last is not None and disp.last.text == turn.replied     # F8 render
    assert mem.recent_turns(turn.person_id, 1)[0].replied == turn.replied  # F9 persist
    print("LIVE E2E PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

Run (only if key present): `python scripts/verify_live.py`
Expected with key + fixture: routes through `run_once()`, prints HEARD/REPLIED/RENDERED/LATENCY, asserts reply + render + persisted turn, prints `LIVE E2E PASS` (F6, F8, F9, Q1). With key but no fixture: prints FAIL and exits **1** (never a silent skip). Without key: prints SKIP, exits 0.

- [ ] **Step 3: Run the full test gate + lint/type gate**

Run: `pytest -v`
Expected: all unit + component + isolation + e2e-fakes tests PASS (component/live SKIP where hardware/key/fixtures absent).

Run: `ruff check .` and `pyright`
Expected: both clean — zero errors. Ruff includes `PLR2004`, so any magic number/string in `src/` fails the gate.

- [ ] **Step 4: Map every spec §8 criterion to its check and record results**

Create `docs/superpowers/VERIFICATION.md` with a row per criterion:

| Criterion | Where verified | Result |
|-----------|----------------|--------|
| F1 wake gates mic | `test_wakeword_returns_only_after_detection` + manual mic run | … |
| F2 capture to silence | `test_capture_stops_after_trailing_silence` | … |
| F3 speaker id / guest | `test_speakerid.py` (match + stranger) | … |
| F4 transcribe | `test_stt_whisper` component + live | … |
| F5 prompt tuned | `test_turn_tuned_to_person_and_persisted` | … |
| F6 reply generated | `verify_live.py` (real Claude) | … |
| F7 spoken | orchestrator + tts tests | … |
| F8 shown | orchestrator + display tests | … |
| F9 persisted | orchestrator + memory tests | … |
| F10 recall (earlier turn) | `test_e2e_turn_recall_and_render` (real save→load) | … |
| F11 guest isolation | `test_guest_does_not_...` + memory test | … |
| F12 enrollment | `enroll.py` manual run + speakerid test | … |
| Q1 latency | `verify_live.py` output | … |
| Q2 speaker accuracy | manual run w/ real family samples | … |
| Q3 false-fire rate | manual noise-fixture run | … |
| M1 ports-only core | `test_core_isolation` | … |
| M2 swap by config/one file | `test_config` DI-override + `test_core_isolation` (core has no backend imports, so a swap touches only the adapter + config) | … |
| M3 fakes everywhere | `test_fakes` + `test_config` | … |
| M4 POC→HW seam | manual review: only audio_vad/display are device-specific | … |
| L1 no NC weights | `test_licenses` | … |
| T1 full suite green | `pytest -v` | … |
| T2 real e2e proof (through run_once) | `verify_live.py` — real speaker/stt/llm/tts/memory/display, asserts reply+render+persist | … |

Fill each Result from an actual run. End the file with a **"What I did NOT verify"** list — e.g. Q2/Q3 need real family voice samples the developer must record; latency measured on dev PC only, not target mini-PC; live proof used fixture audio, not a live mic capture.

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e_fakes.py scripts/verify_live.py docs/superpowers/VERIFICATION.md
git commit -m "test: comprehensive verification — spec-criteria map, hermetic + live e2e"
```

---

## Self-Review

**1. Spec coverage:** Every spec §8 criterion maps to a task — F1–F12 across Tasks 4/6/7/8 + e2e, Q1–Q3 in Task 13, M1–M4 in Tasks 4/11/13, L1 in Task 12, T1–T2 in Task 13. Ports (spec §3) = Task 2; adapters (§4) = Tasks 3,5–10; memory model (§6) = Task 3; data flow (§5) = Task 4; Path A reuse (§2) = STT/TTS/VAD adapters (Tasks 6,8,9). No gaps.

**2. Placeholder scan:** No TBD/TODO; every code step has real content; no "similar to Task N".

**3. Type consistency:** Port signatures defined in Task 2 are used verbatim downstream — `respond(system, user, history)`, `identify(clip)`, `recent_turns(person_id, n)`, `render(state)`, `save_turn(turn)`. `GUEST="guest"` used consistently. `AudioClip(samples, sample_rate)` consistent across adapters.

---

## Notes / flagged for the developer

- **Latency (Q1):** LLM uses `claude-opus-5` at `effort: low`. If the measured end-to-end latency misses the ~3s target, the tuning options in order: lower Whisper model, `claude-sonnet-5`/`claude-haiku-4-5`, or Opus fast mode — your call, not an automatic downgrade.
- **Fixtures:** you must record `tests/fixtures/hello.wav` and real family voice samples for the component/accuracy checks; CI logic tests pass without them.
