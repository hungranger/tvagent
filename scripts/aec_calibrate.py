#!/usr/bin/env python3
"""Measure the audio numbers AEC needs, on THIS machine's mic + speakers.

Run it with the console STOPPED (it needs exclusive mic + speaker):

    cd ~/Workspace/projects/tvagent-console
    .venv/bin/python scripts/aec_calibrate.py

It prints three things:
  1. the default input/output device sample rates,
  2. which (input, output) rate combos open together without a CoreAudio -50,
  3. the mic<->speaker round-trip delay (ms + samples @16k) via a chirp + cross-correlation.

Feed the delay into TVAGENT_AEC_DELAY_MS and pick a shared rate for capture+playback.
It plays a short, quiet chirp — expect a brief blip. Nothing is written to disk.
"""

from __future__ import annotations

import sys
import time
from typing import Any

import numpy as np
import sounddevice as sd

npx: Any = np
sdx: Any = sd

_CAPTURE_RATES = (16000, 24000, 48000)


def device_defaults() -> tuple[int, int]:
    din, dout = sdx.default.device
    info_in = sdx.query_devices(din, "input")
    info_out = sdx.query_devices(dout, "output")
    return int(info_in["default_samplerate"]), int(info_out["default_samplerate"])


def probe_coexistence(out_rate: int) -> list[tuple[int, bool, str]]:
    """Try to open an input stream at each candidate rate while an output stream
    at out_rate is live. Returns (in_rate, ok, note)."""
    results: list[tuple[int, bool, str]] = []
    for in_rate in _CAPTURE_RATES:
        try:
            with (
                sdx.OutputStream(samplerate=out_rate, channels=1, dtype="int16"),
                sdx.InputStream(samplerate=in_rate, channels=1, dtype="int16"),
            ):
                time.sleep(0.2)
            results.append((in_rate, True, "ok"))
        except Exception as exc:
            results.append((in_rate, False, f"{type(exc).__name__}: {exc}"))
    return results


def measure_delay(rate: int = 48000, dur: float = 0.4) -> tuple[float, int]:
    """Play a chirp while recording; cross-correlate to find the round-trip delay.
    Returns (delay_ms, delay_samples_at_16k)."""
    n = int(rate * dur)
    t = npx.linspace(0, dur, n, endpoint=False)
    chirp = (0.2 * npx.sin(2 * npx.pi * (800 + 4000 * t / dur) * t)).astype(npx.float32)
    rec = sdx.playrec(chirp.reshape(-1, 1), samplerate=rate, channels=1, dtype="float32")
    sdx.wait()
    rec1d = rec.reshape(-1)
    corr = npx.correlate(rec1d, chirp, mode="full")
    lag = int(npx.argmax(corr)) - (len(chirp) - 1)
    delay_ms = 1000.0 * lag / rate
    return delay_ms, round(lag * 16000 / rate)


def main() -> int:
    print("== device defaults ==")
    try:
        in_hz, out_hz = device_defaults()
        print(f"input default:  {in_hz} Hz")
        print(f"output default: {out_hz} Hz")
    except Exception as exc:
        print(f"could not query devices: {exc}")
        return 1

    print("\n== duplex coexistence (find a combo with no err=-50) ==")
    for in_rate, ok, note in probe_coexistence(out_hz):
        mark = "OK " if ok else "FAIL"
        print(f"  out {out_hz} + in {in_rate}: {mark}  {note}")

    print("\n== round-trip delay (chirp) ==")
    try:
        delay_ms, delay_16k = measure_delay(rate=out_hz)
        print(f"  delay: {delay_ms:.1f} ms  ({delay_16k} samples @16k)")
        print(f"\n  -> export TVAGENT_AEC_DELAY_MS={delay_ms:.0f}")
    except Exception as exc:
        print(f"  delay measurement failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
