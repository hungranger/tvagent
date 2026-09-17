# TV Family Agent — v1 Design (POC)

**Date:** 2026-09-17
**Status:** Approved design, pre-implementation
**Scope:** v1 = "the spine" — an always-listening voice agent that identifies *who* in the family is speaking and responds with per-person memory, rendered on a screen. Runs as a software-only POC on a PC first; hardware port is a later phase.

---

## 1. Goal

Build a modular, always-listening LLM agent whose interface is a TV. v1 proves the hard, novel part: **it knows who is talking and behaves/remembers accordingly.** Home-assistant, work-partner, companion, and media-hub capabilities are later phases that plug into this spine.

### Non-goals (v1)
- Fullscreen TV kiosk hardware (POC uses a browser window on the PC).
- Controlling other TV apps (YouTube, browser, smart home).
- Rich dashboards / media hub.
- Cloud STT/TTS (start local; cloud is a swappable adapter later).

---

## 2. Architecture — Ports & Adapters (Hexagonal)

The core orchestration logic is pure and hardware-free. Every capability is an interface (port). The POC picks PC adapters; the hardware phase swaps only the edge adapters (mic, display). Core, brain, and memory stay identical.

```
        ┌──────────── CORE (pure logic, no hardware) ────────────┐
        │   Orchestrator: wake -> who -> text -> think ->         │
        │                 speak -> show -> save                   │
        └───┬────┬────┬────┬────┬────┬────────────────────────────┘
   ports    │    │    │    │    │    │       (interfaces / ABCs)
        ┌───┴─┐┌─┴──┐┌┴───┐┌┴──┐┌┴───┐┌┴──────┐┌────────┐
        │Wake ││Spk ││STT ││LLM││TTS ││Memory ││Display │
        │Word ││ID  ││    ││   ││    ││Store  ││        │
        └─────┘└────┘└────┘└───┘└────┘└───────┘└────────┘
  POC adapters: laptop mic, Whisper, Claude, Piper, JSON files, browser window
  HW  adapters: USB mic array, (same core), Chromium kiosk on TV
```

### Design principles (per user requirement)
- **Swappable:** each component is an interface; impl chosen by config.
- **Pluggable:** new tools/skills = new adapters, core unchanged.
- **Testable:** tests use fake adapters (fake mic feeds a `.wav`, fake LLM returns canned text) — no hardware, no API cost.
- **Maintainable:** swapping an impl (e.g. Whisper -> other STT) touches one file.
- **POC -> HW:** only edge adapters change.

---

## 3. Ports (interfaces)

Each is a small Python `Protocol`/ABC. Signatures are indicative, to be finalized in the plan.

| Port | Responsibility | Key method(s) |
|------|----------------|---------------|
| `WakeWord` | detect wake phrase in audio stream | `stream() -> yields wake events` |
| `AudioCapture` | capture utterance until silence (VAD) | `capture() -> AudioClip` |
| `SpeakerID` | map an audio clip to a known person or "guest" | `identify(clip) -> PersonId \| GUEST`; `enroll(name, clip)` |
| `STT` | speech clip -> text | `transcribe(clip) -> str` |
| `LLM` | text + context -> reply | `respond(prompt, history) -> str` |
| `TTS` | text -> spoken audio | `speak(text) -> AudioClip / plays` |
| `MemoryStore` | per-person durable memory | `load(person)`, `save_turn(...)`, `get_facts(person)`, `add_fact(...)` |
| `Display` | push UI state to the screen | `render(state)` |

The **Orchestrator** depends only on these interfaces, never on concrete libs.

---

## 4. v1 Adapter choices (POC on PC)

| Port | POC adapter | Why (laziest that works) |
|------|-------------|--------------------------|
| WakeWord | **openWakeWord** | free, local, custom phrase |
| AudioCapture | laptop mic + webrtcvad | built-in mic, standard VAD |
| SpeakerID | **SpeechBrain ECAPA** embeddings + cosine match | enroll once per person, compare embeddings |
| STT | **faster-whisper** (base/small) | local, CPU-friendly |
| LLM | **Claude API** | smartest; cheap per call; see claude-api skill for model id/pricing at build time |
| TTS | **Piper** (local) | private; swap to cloud voice later |
| MemoryStore | **JSON files** behind the interface | human-readable, `cat`-able, zero infra; swap to SQLite when turn-queries/vector search needed |
| Display | **browser window** via local websocket | same page later goes fullscreen kiosk on TV |
| Language | **Python** | every lib above is Python-first |

### Memory decision (explicitly deferred by interface)
JSON-file impl for POC. Swap to SQLite (`sqlite-vec` for semantic recall) the day "last N turns for person X" or vector search is needed. One-line config change, no rewrite.

---

## 5. Data flow (one turn)

```
1. mic stream -> WakeWord fires on "Hey House"
2. AudioCapture records until silence -> AudioClip
3. SpeakerID.identify(clip) -> person ("Dad") or GUEST
4. STT.transcribe(clip) -> text
5. MemoryStore.load(person) -> facts + recent turns
6. Orchestrator builds prompt tuned to WHO is speaking
7. LLM.respond(...) -> reply
8. TTS.speak(reply)  AND  Display.render({person, text, cards})
9. MemoryStore.save_turn(person, said, replied)
```

---

## 6. Memory model (logical; JSON impl for v1)

| Concept | Fields |
|---------|--------|
| Person | id, name, voice embedding, prefs (e.g. tone: adult/kid) |
| Turn | person, timestamp, said, replied |
| Fact | person, text, created_at (durable per-person notes) |

Enrollment: each family member records ~30s once to register a voice embedding. Unknown voice -> "guest" profile, no personal memory.

---

## 7. Testing strategy (TDD)

- **Fake adapters** for every port enable full core tests with no hardware/API.
  - Fake `AudioCapture` returns a fixture `.wav`.
  - Fake `LLM` returns canned text; assert prompt was tuned to the right person.
  - Fake `Display` records last rendered state.
- **Component tests** (real impls, small fixtures):
  - WakeWord fires on wake clip, silent on noise clip.
  - **SpeakerID accuracy** — the key risk. Test with real family voice samples: correct person above threshold, stranger -> GUEST.
  - STT transcribes a known clip within error tolerance.
  - MemoryStore round-trips facts/turns.
- **Orchestrator test** wires fakes end-to-end: wake -> who -> text -> think -> speak -> show -> save.

---

## 8. Success criteria (v1 done when)

1. Say the wake phrase at the PC mic -> agent captures the utterance.
2. It correctly identifies which enrolled family member spoke (and labels unknown voices "guest").
3. It transcribes what was said.
4. It answers via Claude with a prompt tuned to that person and their memory.
5. It speaks the reply (Piper) AND shows it in the browser window.
6. It persists the turn; a later turn by the same person reflects remembered facts.
7. Swapping any single adapter (e.g. TTS impl) requires touching only that adapter + config.
8. Full test suite (fakes + component tests incl. real speaker-ID samples) passes.

---

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Speaker-ID unreliable (similar voices, kids) | test early with real samples; tune threshold; GUEST fallback |
| Wake-word false fires | pick/tune openWakeWord model; VAD gating |
| Latency (local Whisper + cloud LLM + Piper) | measure per stage; downgrade Whisper model or stream if slow |
| Claude model id/pricing at build time | consult claude-api skill during implementation |

---

## 10. Phase roadmap (context)

| Phase | Ships |
|-------|-------|
| **v1 (this spec)** | spine: wake + speaker ID + per-person memory + Claude + voice + screen, POC on PC |
| v2 | home-assistant tools (timers, weather, reminders, smart home) |
| v3 | richer screen (dashboard cards, media/info hub); fullscreen TV kiosk + hardware port |
| v4 | work-partner + companion depth (notes, brainstorm, long-term relationship memory) |
