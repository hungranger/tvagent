"""CLI: python -m tvagent.enroll "Dad"  — records ~30s and registers the voice."""

import pathlib
import sys

from tvagent.adapters.audio_vad import record_seconds  # from Task 8
from tvagent.adapters.memory_json import JsonMemory
from tvagent.adapters.speakerid_ecapa import EcapaSpeakerID

_ENROLL_SECONDS = 30


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else input("Name: ")
    clip = record_seconds(_ENROLL_SECONDS)
    sid = EcapaSpeakerID(JsonMemory(pathlib.Path("data/memory")))
    p = sid.enroll(name, [clip])
    print(f"enrolled {p.name} ({p.id})")


if __name__ == "__main__":
    main()
