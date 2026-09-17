import pathlib

from tvagent.adapters.memory_json import JsonMemory
from tvagent.adapters.speakerid_ecapa import EcapaSpeakerID, cosine
from tvagent.core.models import AudioClip


class _StubEmbedder:
    def __init__(self) -> None:
        self.next: list[float] = []
        self.last_clip: AudioClip | None = None

    def __call__(self, clip: AudioClip) -> list[float]:
        self.last_clip = clip
        return self.next


def test_cosine_basic():
    assert abs(cosine([1, 0], [1, 0]) - 1.0) < 1e-6
    assert abs(cosine([1, 0], [0, 1]) - 0.0) < 1e-6


def test_cosine_zero_vector_is_zero_not_one():
    # guards the na==0/nb==0 short-circuit: a zero vector must yield 0.0, never 1.0,
    # and must not divide by zero, regardless of which side is zero.
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
    assert cosine([1.0, 0.0], [0.0, 0.0]) == 0.0


def test_cosine_scales_with_magnitude():
    # non-unit, asymmetric vectors: pins dot/(na*nb) exactly (catches operand-order
    # and operator swaps that unit/orthogonal vectors can't distinguish).
    assert abs(cosine([3.0, 4.0], [0.0, 5.0]) - 0.8) < 1e-6


def _clip() -> AudioClip:
    return AudioClip(samples=b"x", sample_rate=16000)


def test_enroll_then_identify_matches(tmp_path: pathlib.Path):
    m = JsonMemory(tmp_path)
    vecs = {"dad": [1.0, 0.0], "mom": [0.0, 1.0]}
    embed = _StubEmbedder()
    sid = EcapaSpeakerID(m, threshold=0.5, _embed=embed)
    embed.next = vecs["dad"]
    clip = _clip()
    person = sid.enroll("Dad", clip)
    assert embed.last_clip is clip  # enroll must embed the given clip, not a stand-in
    assert person.name == "Dad"
    assert person.prefs == {}
    embed.next = vecs["mom"]
    sid.enroll("Mom", _clip())
    embed.next = [0.9, 0.1]  # close to Dad
    id_clip = _clip()
    assert sid.identify(id_clip) == "dad"  # F3: right person
    assert embed.last_clip is id_clip  # identify must embed the given clip too


def test_stranger_falls_back_to_guest(tmp_path: pathlib.Path):
    m = JsonMemory(tmp_path)
    embed = _StubEmbedder()
    sid = EcapaSpeakerID(m, threshold=0.8, _embed=embed)
    embed.next = [1.0, 0.0]
    sid.enroll("Dad", _clip())
    embed.next = [0.0, 1.0]  # orthogonal -> below threshold
    assert sid.identify(_clip()) == "guest"  # F3: stranger -> GUEST


def test_identify_matches_at_exact_threshold(tmp_path: pathlib.Path):
    m = JsonMemory(tmp_path)
    embed = _StubEmbedder()
    sid = EcapaSpeakerID(m, threshold=1.0, _embed=embed)
    embed.next = [1.0, 0.0]
    sid.enroll("Dad", _clip())
    embed.next = [1.0, 0.0]  # identical vector -> cosine == 1.0 == threshold, must match
    assert sid.identify(_clip()) == "dad"
