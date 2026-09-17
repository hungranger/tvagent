import pathlib

from tvagent.adapters.memory_json import JsonMemory
from tvagent.adapters.speakerid_ecapa import EcapaSpeakerID, cosine
from tvagent.core.models import AudioClip


class _StubEmbedder:
    def __init__(self) -> None:
        self.next: list[float] = []

    def __call__(self, clip: AudioClip) -> list[float]:
        return self.next


def test_cosine_basic():
    assert abs(cosine([1,0], [1,0]) - 1.0) < 1e-6
    assert abs(cosine([1,0], [0,1]) - 0.0) < 1e-6

def _clip() -> AudioClip: return AudioClip(samples=b"x", sample_rate=16000)

def test_enroll_then_identify_matches(tmp_path: pathlib.Path):
    m = JsonMemory(tmp_path)
    vecs = {"dad": [1.0, 0.0], "mom": [0.0, 1.0]}
    embed = _StubEmbedder()
    sid = EcapaSpeakerID(m, threshold=0.5, _embed=embed)
    embed.next = vecs["dad"]
    sid.enroll("Dad", _clip())
    embed.next = vecs["mom"]
    sid.enroll("Mom", _clip())
    embed.next = [0.9, 0.1]  # close to Dad
    assert sid.identify(_clip()) == "dad"          # F3: right person

def test_stranger_falls_back_to_guest(tmp_path: pathlib.Path):
    m = JsonMemory(tmp_path)
    embed = _StubEmbedder()
    sid = EcapaSpeakerID(m, threshold=0.8, _embed=embed)
    embed.next = [1.0, 0.0]
    sid.enroll("Dad", _clip())
    embed.next = [0.0, 1.0]  # orthogonal -> below threshold
    assert sid.identify(_clip()) == "guest"        # F3: stranger -> GUEST
