import pathlib
from collections.abc import Iterator

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


class _SequenceEmbedder:
    """Returns a different vector per call, in order -- for multi-clip enroll tests."""

    def __init__(self, vectors: Iterator[list[float]]) -> None:
        self._vectors = vectors

    def __call__(self, clip: AudioClip) -> list[float]:
        return next(self._vectors)


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
    sid = EcapaSpeakerID(m, threshold=0.5, margin=0.0, _embed=embed)
    embed.next = vecs["dad"]
    clip = _clip()
    person = sid.enroll("Dad", [clip])
    assert embed.last_clip is clip  # enroll must embed the given clip, not a stand-in
    assert person.name == "Dad"
    assert person.prefs == {}
    embed.next = vecs["mom"]
    sid.enroll("Mom", [_clip()])
    embed.next = [0.9, 0.1]  # close to Dad
    id_clip = _clip()
    assert sid.identify(id_clip) == "dad"  # F3: right person
    assert embed.last_clip is id_clip  # identify must embed the given clip too


def test_enroll_averages_multiple_clips(tmp_path: pathlib.Path):
    m = JsonMemory(tmp_path)
    embed = _StubEmbedder()
    sid = EcapaSpeakerID(m, _embed=embed)
    clips = [_clip(), _clip()]
    vectors = iter([[1.0, 0.0], [0.0, 2.0]])
    embed_seq = _SequenceEmbedder(vectors)
    sid._embed = embed_seq  # type: ignore[method-assign]  # pyright: ignore[reportPrivateUsage]
    person = sid.enroll("Dad", clips)
    assert person.embedding == [0.5, 1.0]  # elementwise mean of the two clip embeddings


def test_stranger_falls_back_to_guest(tmp_path: pathlib.Path):
    m = JsonMemory(tmp_path)
    embed = _StubEmbedder()
    sid = EcapaSpeakerID(m, threshold=0.8, margin=0.0, _embed=embed)
    embed.next = [1.0, 0.0]
    sid.enroll("Dad", [_clip()])
    embed.next = [0.0, 1.0]  # orthogonal -> below threshold
    assert sid.identify(_clip()) == "guest"  # F3: stranger -> GUEST


def test_identify_matches_at_exact_threshold(tmp_path: pathlib.Path):
    m = JsonMemory(tmp_path)
    embed = _StubEmbedder()
    sid = EcapaSpeakerID(m, threshold=1.0, margin=0.0, _embed=embed)
    embed.next = [1.0, 0.0]
    sid.enroll("Dad", [_clip()])
    embed.next = [1.0, 0.0]  # identical vector -> cosine == 1.0 == threshold, must match
    assert sid.identify(_clip()) == "dad"


def test_margin_rejects_ambiguous_match(tmp_path: pathlib.Path):
    # Dad and Mom are near-identical; a query equidistant from both must be GUEST
    # even though it clears the threshold, because best-vs-2nd-best gap < margin.
    m = JsonMemory(tmp_path)
    embed = _StubEmbedder()
    sid = EcapaSpeakerID(m, threshold=0.5, margin=0.1, _embed=embed)
    embed.next = [1.0, 0.0]
    sid.enroll("Dad", [_clip()])
    embed.next = [0.99, 0.01]
    sid.enroll("Mom", [_clip()])
    embed.next = [0.9, 0.1]  # close to both, gap between them tiny
    assert sid.identify(_clip()) == "guest"


def test_margin_admits_clear_winner(tmp_path: pathlib.Path):
    # Same two enrolled people, but a query clearly closer to Dad (gap >= margin)
    # must still resolve to Dad, not fall back to GUEST.
    m = JsonMemory(tmp_path)
    embed = _StubEmbedder()
    sid = EcapaSpeakerID(m, threshold=0.5, margin=0.1, _embed=embed)
    embed.next = [1.0, 0.0]
    sid.enroll("Dad", [_clip()])
    embed.next = [0.0, 1.0]
    sid.enroll("Mom", [_clip()])
    embed.next = [0.9, 0.1]  # near Dad, far from Mom -> big gap
    assert sid.identify(_clip()) == "dad"


def test_warmup_noop_with_injected_embed(tmp_path: pathlib.Path) -> None:
    # warmup preloads the real ECAPA model; with an injected embedder there is
    # nothing to preload, so it must be a safe no-op (no download, no _model).
    sid = EcapaSpeakerID(JsonMemory(tmp_path), _embed=lambda _c: [1.0])
    sid.warmup()
    assert sid._model is None  # pyright: ignore[reportPrivateUsage]


def test_warmup_loads_model_when_default(tmp_path: pathlib.Path) -> None:
    # With the default embedder, warmup() must populate _model via _load_model.
    sid = EcapaSpeakerID(JsonMemory(tmp_path))
    sid._load_model = lambda: "MODEL"  # type: ignore[method-assign]  # stub the heavy download
    sid.warmup()
    assert sid._model == "MODEL"  # pyright: ignore[reportPrivateUsage]
