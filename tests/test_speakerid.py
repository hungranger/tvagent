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
