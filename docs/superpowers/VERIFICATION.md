# Verification report — TV Family Agent v1

Every spec §8 criterion mapped to a concrete check and an actual run result.
Run environment: this dev sandbox (no microphone, no speakers; `ANTHROPIC_API_KEY`
not set — checked by `os.environ.get("ANTHROPIC_API_KEY")`, name only, value
never printed or logged).

## 8.1 Functional

| # | Criterion | Where verified | Result |
|---|-----------|----------------|--------|
| F1 | Wake word gates mic | `tests/test_audio_vad.py::test_wakeword_returns_only_after_detection`, `test_wakeword_does_not_fire_exactly_at_threshold` | PASS (unit, fake detector). Real-mic false-fire measurement is a manual/hardware step — see "not verified". |
| F2 | Capture to silence | `tests/test_audio_vad.py::test_capture_stops_after_trailing_silence` + 3 related VAD tests | PASS |
| F3 | Speaker id / guest | `tests/test_speakerid.py` (`test_enroll_then_identify_matches`, `test_stranger_falls_back_to_guest`, `test_identify_matches_at_exact_threshold`) | PASS |
| F4 | Transcribe | `tests/test_stt_whisper.py::test_transcribe_joins_segments` (unit) | PASS. `test_real_whisper_on_fixture` (component, needs audio fixture) | SKIPPED — no fixture in this env |
| F5 | Prompt tuned to person | `tests/test_orchestrator.py::test_turn_tuned_to_person_and_persisted`, `test_build_prompt_content_for_known_person` | PASS |
| F6 | Reply generated (real Claude) | `scripts/verify_live.py` | DEFERRED — `ANTHROPIC_API_KEY` not set in this env; script correctly printed `SKIP live e2e: ANTHROPIC_API_KEY not set` and exited 0 |
| F7 | Reply spoken | `tests/test_e2e_fakes.py::test_e2e_turn_recall_and_render`, `tests/test_orchestrator.py::test_turn_tuned_to_person_and_persisted` | PASS |
| F8 | Reply shown | same as F7 (`disp.last.text`) | PASS |
| F9 | Turn persisted | `test_e2e_turn_recall_and_render` (`mem.recent_turns`), `tests/test_memory_json.py::test_person_and_turn_roundtrip` | PASS |
| F10 | Memory recall (earlier turn) | `tests/test_e2e_fakes.py::test_e2e_turn_recall_and_render` — two real `run_once()` calls sharing one `JsonMemory`; turn 2's `llm.last_system` contains "Rex" from turn 1's save, proving the real save→load path (not a pre-seeded fact) | PASS |
| F11 | Guest isolation | `tests/test_orchestrator.py::test_guest_does_not_read_or_write_enrolled_memory`, `tests/test_memory_json.py::test_facts_and_guest_isolation` | PASS |
| F12 | Enrollment flow | `tests/test_speakerid.py::test_enroll_then_identify_matches` | PASS (unit). `enroll.py` manual mic run | DEFERRED — no microphone in this env |

## 8.2 Quality (measured, not assumed)

| # | Criterion | Where verified | Result |
|---|-----------|----------------|--------|
| Q1 | End-to-end latency | `scripts/verify_live.py` prints `END-TO-END LATENCY` | DEFERRED — needs real hardware run (see below) |
| Q2 | Speaker-ID accuracy on real family samples | manual run w/ real voice samples | DEFERRED — needs recorded family voice samples, not available in this env |
| Q3 | Wake-word false-fire rate | manual noise-fixture run | DEFERRED — needs recorded noise/ambient fixture and a live mic, not available in this env |

## 8.3 Modularity / architecture

| # | Criterion | Where verified | Result |
|---|-----------|----------------|--------|
| M1 | Ports-only core | `tests/test_core_isolation.py::test_core_imports_only_core` (allows only stdlib + `tvagent.core.*` imports in `core/`; any third-party or other backend import fails it) | PASS |
| M2 | Adapter swap = one file + config | `tests/test_config.py::test_build_with_all_fakes_swapped_by_config` (DI override) + `test_core_isolation` (core has zero backend imports, so a swap touches only the adapter + `config.py`) | PASS |
| M3 | Fakes for every port | `tests/test_fakes.py::test_fakes_satisfy_ports`, `tests/test_config.py` (whole orchestrator runs on fakes only, zero hardware/paid calls) | PASS |
| M4 | POC→HW seam isolated | manual review: only `audio_vad.py` (mic/VAD) and `display_web.py` (browser/websocket) touch devices; `core/`, `memory_json.py`, `llm_claude.py`, `stt_whisper.py`, `tts_piper.py`, `speakerid_ecapa.py` have no device imports (confirmed by reading each adapter + `test_core_isolation`) | PASS |

## 8.4 Licensing

| # | Criterion | Where verified | Result |
|---|-----------|----------------|--------|
| L1 | No non-commercial weights | `tests/test_licenses.py::test_no_noncommercial_weights` | PASS |

## 8.5 Test gate

| # | Criterion | Where verified | Result |
|---|-----------|----------------|--------|
| T1 | Full suite green | `pytest -v` — **38 passed, 1 skipped** (`test_real_whisper_on_fixture`, component test, no fixture present — expected). `ruff check .` — **All checks passed!**. `pyright` — **0 errors, 0 warnings, 0 informations** | PASS |
| T2 | Real e2e proof (through `run_once`) | `scripts/verify_live.py` | DEFERRED — see below |

### Actual command output (this run)

```
$ pytest -v
...
38 passed, 1 skipped in 0.07s

$ ruff check .
All checks passed!

$ ruff format --check .
35 files already formatted

$ pyright
0 errors, 0 warnings, 0 informations

$ python scripts/verify_live.py
SKIP live e2e: ANTHROPIC_API_KEY not set
(exit code 0)
```

## What I did NOT verify

- **T2 / F6 / Q1 real-live proof**: `ANTHROPIC_API_KEY` is not set in this sandbox, so `scripts/verify_live.py` correctly short-circuited to `SKIP` (exit 0) rather than exercising real STT→Claude→TTS. The script is written and exercised for its zero-key path only. When a key is set but `tests/fixtures/hello.wav` is absent (also true here — this sandbox has no microphone to record it), the script is designed to print `FAIL ... missing` and exit 1 rather than pass silently; this exact branch was not hit because the key-not-set branch short-circuits first. The developer must run this on real hardware with both the key and the recorded fixture present to get an actual `LIVE E2E PASS`.
- **Q2 speaker-ID accuracy on real family voices**: needs recorded samples from actual family members; none exist in this environment. Unit tests only cover synthetic embeddings.
- **Q3 wake-word false-fire rate**: needs a recorded ambient/noise fixture and a live mic; not available here.
- **Latency (Q1) on target mini-PC hardware**: not measured at all in this run (no live call made); even once measured via `verify_live.py`, that number would reflect the developer's own machine, not the target mini-PC, and must be re-measured there.
- **F1 real-mic false-fire measurement and F12 real enrollment flow**: covered here only by unit tests against fake detectors/embeddings; the manual mic-in-hand runs described in the spec were not performed (no microphone in this sandbox).
- **Hardware adapters on real devices**: `audio_vad.py` (real mic capture) and `display_web.py` (real browser/kiosk render) are excluded from coverage by design (`pyproject.toml` `[tool.coverage.report] exclude_also`) and were not exercised against real hardware in this session.
- **Anthropic SDK parameter contract**: `model="claude-opus-5"` and `output_config={"effort":"low"}` are UNVALIDATED by the test suite — the stub `create(**kwargs)` swallows any keyword, so these params are asserted-as-received, never checked against the real SDK. The first real live call is the only validation.

---

## Live E2E run — EXECUTED 2026-09-17 (real hardware, key present)

The live proof was actually run: fixture generated with macOS `say "hello there"` → `afconvert` to 16 kHz mono WAV (`tests/fixtures/hello.wav`, gitignored); `ANTHROPIC_API_KEY` sourced from the developer's key store; `.[run]` deps installed.

```
$ python scripts/verify_live.py
HEARD: 'Hello there.'
REPLIED: 'Hi Tester! Good to hear from you. What can I help with today?'
RENDERED: 'Hi Tester! Good to hear from you. What can I help with today?'
END-TO-END LATENCY: 41.42s
LIVE E2E PASS
```

Now proven LIVE through `Orchestrator.run_once()` (real ECAPA speaker-ID, real faster-whisper STT, real Claude, real Piper TTS, real JsonMemory):

| Criterion | Live result |
|-----------|-------------|
| F3 speaker ID | enrolled "Tester" via real ECAPA, identified correctly (reply is person-tuned: "Hi Tester!") ✅ |
| F4 transcribe | Whisper → "Hello there." ✅ |
| F5 prompt tuned to person | reply addresses Tester by name ✅ |
| F6 reply generated (real Claude) | non-empty reply ✅ |
| F7 spoken (Piper) | synth+play completed without error ✅ |
| F8 shown | RENDERED == reply ✅ |
| F9 persisted | asserted by script ✅ |
| Q1 latency | **41.4s COLD (first run: model loads + Piper voice download)** — FAR over the ~3s target. Steady-state (warm models) unmeasured; the ~3s budget is NOT met as-is and needs profiling/tuning (smaller Whisper, model preload, streaming). ⚠️ |

**Bug found + fixed by this live run:** `PiperTTS._default_synth` loaded the voice by bare name (`PiperVoice.load("en_US-amy-medium")`) — fails with `FileNotFoundError` on real hardware — and called the removed `synthesize(text, wf)` API. Fixed to download the voice to `~/.cache/tvagent/piper` on first use and call `synthesize_wav`. Only the real hardware path was affected (unit tests stub `_synth`), which is exactly why only live e2e caught it.

**Still not verified:** Q2 speaker-ID accuracy on real *family* voices (only one synthetic enrollee tested); Q3 wake false-fire; real-mic F1/F12; latency on the target mini-PC (this 41s is a dev-Mac cold number). Anthropic SDK param contract now implicitly validated by the successful live call (params accepted, real reply returned).

---

## Q1 latency — FIXED via startup warmup (2026-09-17, branch feat/latency-warmup)

Profiling showed the 41s was **entirely cold-start** (lazy model loads on the first turn: ECAPA + Piper voice download), not per-turn work. `build_orchestrator(warm=True)` now preloads the heavy local models at boot via each adapter's `warmup()`, moving that cost off the turn path.

| Metric | Before | After |
|--------|-------:|------:|
| Boot (build + warmup, one-time) | — | ~6s (first-ever run adds the Piper voice download) |
| Per-turn local (STT + speaker + Piper synth), warm | ~40s first turn | **0.33s** every turn |
| Warm turn incl. real Claude (~3.1s) | 41s | **~3.5s** — near the ~3s Q1 target; Claude is the floor |

Measured with the real STT/ECAPA/Piper adapters (fake LLM to isolate local latency). To go under 3s, the next lever is streaming Claude (first-token) or a smaller/faster LLM — the local pipeline is no longer the bottleneck.
