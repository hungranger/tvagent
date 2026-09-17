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
