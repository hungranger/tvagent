"""Sweep speaker-ID threshold/margin against recorded enroll+test clips.

Layout:
  data/voices/enroll/<name>/*.wav   -- a few clips per person to enroll
  data/voices/test/<label>/*.wav    -- held-out clips; label is a name or "stranger"

Uses the REAL EcapaSpeakerID (real ECAPA embeddings), scored with the pure
functions in tvagent.speaker_eval. Gated on data/voices/ existing, like
verify_live.py -- no fixtures are shipped, so CI SKIPs this cleanly.
"""

import itertools
import sys
import wave
from pathlib import Path

from tvagent.adapters.memory_json import JsonMemory
from tvagent.adapters.speakerid_ecapa import EcapaSpeakerID
from tvagent.core.models import AudioClip
from tvagent.speaker_eval import EvalCase, best_by_grid, score_cases

_DATA_ROOT = Path("data/voices")
_THRESHOLDS = [0.20, 0.25, 0.30, 0.35]
_MARGINS = [0.05, 0.10, 0.15]


def _load_clip(wav_path: Path) -> AudioClip:
    with wave.open(str(wav_path)) as w:
        return AudioClip(samples=w.readframes(w.getnframes()), sample_rate=w.getframerate())


def _load_by_label(root: Path) -> dict[str, list[AudioClip]]:
    return {
        d.name: [_load_clip(f) for f in sorted(d.glob("*.wav"))]
        for d in sorted(root.iterdir())
        if d.is_dir()
    }


def _run_grid(
    enroll_clips: dict[str, list[AudioClip]],
    test_clips: dict[str, list[AudioClip]],
    embed_cache: dict[int, list[float]],
) -> list[tuple[float, float, float, float]]:
    def cached_embed(clip: AudioClip) -> list[float]:
        key = id(clip)
        if key not in embed_cache:
            embed_cache[key] = real_sid._default_embed(clip)  # pyright: ignore[reportPrivateUsage]
        return embed_cache[key]

    real_sid = EcapaSpeakerID(JsonMemory(Path("data/eval_tmp")))
    grid: list[tuple[float, float, float, float]] = []
    for threshold, margin in itertools.product(_THRESHOLDS, _MARGINS):
        sid = EcapaSpeakerID(
            JsonMemory(Path("data/eval_tmp")),
            threshold=threshold,
            margin=margin,
            _embed=cached_embed,
        )
        for name, clips in enroll_clips.items():
            sid.enroll(name, clips)
        cases = [
            EvalCase(true=label, predicted=sid.identify(clip))
            for label, clips in test_clips.items()
            for clip in clips
        ]
        report = score_cases(cases)
        correct, reject = report.correct_rate or 0.0, report.stranger_reject_rate or 0.0
        grid.append((threshold, margin, correct, reject))
    return grid


def main() -> int:
    if not _DATA_ROOT.exists():
        print(f"SKIP speaker eval: {_DATA_ROOT} not found (record clips to run this)")
        return 0

    enroll_clips = _load_by_label(_DATA_ROOT / "enroll")
    test_clips = _load_by_label(_DATA_ROOT / "test")
    grid = _run_grid(enroll_clips, test_clips, {})

    for threshold, margin, correct, reject in grid:
        print(
            f"threshold={threshold:.2f} margin={margin:.2f} "
            f"correct_rate={correct:.2%} stranger_reject_rate={reject:.2%}"
        )
    best_threshold, best_margin = best_by_grid(grid)
    print(f"\nRECOMMENDED: threshold={best_threshold:.2f} margin={best_margin:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
