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

### Reuse decision: huggingface/speech-to-speech (Path A — borrow backends)
Do NOT build the STT/TTS/VAD plumbing from scratch, and do NOT fork the repo wholesale. That repo is a modular VAD -> STT -> LLM -> TTS pipeline (Apache-2.0, active, local-capable) but its loop is *continuous* speech-to-speech, and it lacks wake word, speaker ID, per-person memory, and display — exactly this project's spine.

- **We own:** the wake-word-gated Orchestrator loop, all ports, and the spine ports (`WakeWord`, `SpeakerID`, `MemoryStore`, `Display`). None exist in the repo.
- **We borrow:** their backend integrations + config patterns behind OUR `STT`, `TTS`, `AudioCapture(VAD)` adapters. Their multi-backend design validates the swappable-adapter thesis.
- **We do NOT adopt:** their continuous threading/queue loop (fights the wake-first privacy gate).

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

### Licensing / commercialization
Two independent layers: **code license** and **model-weight license**. Apache-2.0 on the speech-to-speech repo permits commercial use of the *code*; each downloaded *model* carries its own license, which can be non-commercial even inside a permissive repo. Path A lets us pick commercial-safe backends and drop restricted ones.

| Component | Chosen model | License (verify at build) | Commercial |
|-----------|--------------|---------------------------|:-:|
| VAD | Silero | MIT | yes |
| STT | faster-whisper | MIT | yes |
| TTS | Piper | MIT | yes |
| Speaker ID | SpeechBrain ECAPA | Apache-2.0 | yes |
| Wake word | openWakeWord | Apache-2.0 | yes |
| Brain | Claude API | commercial via API terms | yes |

The v1 stack is commercial-safe by default. **Avoid** `-NC`/"research only" weights (e.g. ChatTTS = CC-BY-NC; Qwen3-TTS license must be read). Re-verify every model license before any commercial launch; get legal review for real revenue; check Anthropic usage policies for the product category. Not legal advice.

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

Each criterion maps to a concrete, runnable check. The implementation plan's final task must verify every row against a real end-to-end run, not just unit/fake tests.

### 8.1 Functional — the turn works end to end
| # | Criterion | Concrete check |
|---|-----------|----------------|
| F1 | Wake word gates the mic | Speaking the wake phrase fires exactly one capture; ordinary speech/noise does not (measure false-fire rate on a noise fixture). |
| F2 | Utterance captured to silence | After wake, VAD ends capture on trailing silence; produces a bounded `AudioClip`. |
| F3 | Speaker identified | Enrolled member's clip -> correct `PersonId` above threshold; stranger's clip -> `GUEST`. |
| F4 | Speech transcribed | Known clip -> text within a set word-error tolerance. |
| F5 | Prompt tuned to person | LLM prompt includes the identified person's profile + loaded memory (assert on built prompt). |
| F6 | Reply generated | Claude returns a non-empty reply for a real call (gated on `ANTHROPIC_API_KEY` present). |
| F7 | Reply spoken | TTS produces audible/output audio for the reply text. |
| F8 | Reply shown | Browser window renders `{person, text}` (and card when present). |
| F9 | Turn persisted | Turn written to the person's memory; readable next turn. |
| F10 | Memory recall | A detail from an earlier turn is reflected in a later same-person turn's prompt (recent-turn history load; durable `Fact` extraction is a later phase). |
| F11 | Guest isolation | GUEST turns do not read or write any enrolled person's memory. |
| F12 | Enrollment flow | A new voice can be enrolled (~30s) and is recognized on the next turn. |

### 8.2 Quality — latency & accuracy budgets (measured, not assumed)
| # | Criterion | Target (POC) |
|---|-----------|--------------|
| Q1 | End-to-end latency: end-of-speech -> first audio out | measured + recorded; document actual, target < ~3s on PC |
| Q2 | Speaker-ID accuracy on real family samples | correct-person rate + stranger-rejection rate recorded; threshold tuned from this |
| Q3 | Wake-word false-fire rate | measured on a noise/ambient fixture; recorded |

### 8.3 Modularity / architecture (the user's core requirement)
| # | Criterion | Concrete check |
|---|-----------|----------------|
| M1 | Every component behind a port | Orchestrator imports only interfaces; no direct backend import (grep/lint check). |
| M2 | Adapter swap is one-file + config | Swapping one adapter (e.g. Piper -> another TTS) changes only that adapter + config; test suite still passes. |
| M3 | Fakes for every port | Each port has a fake impl; core test runs with zero hardware and zero paid API calls. |
| M4 | POC->HW seam isolated | Only edge adapters (mic, display) are marked hardware-specific; core/brain/memory have no device imports. |

### 8.4 Licensing
| # | Criterion | Concrete check |
|---|-----------|----------------|
| L1 | No non-commercial weights | No `-NC`/research-only model wired in; each active model's license recorded in a `LICENSES.md`. |

### 8.5 Test gate
| # | Criterion | Concrete check |
|---|-----------|----------------|
| T1 | Full suite green | Fakes + component tests (incl. real speaker-ID samples) + orchestrator e2e-with-fakes all pass. |
| T2 | Real e2e proof | One live run (real mic clip -> real STT -> real Claude -> real TTS -> real render -> real persisted turn), gated on API key; output captured as evidence. |

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
