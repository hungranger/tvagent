import math
from collections.abc import Callable
from typing import Any

import numpy as np

from tvagent.core.models import GUEST, AudioClip, Person
from tvagent.core.ports import MemoryStore

_PCM_MAX = 32768.0
_DEFAULT_THRESHOLD = 0.25
_DEFAULT_MARGIN = 0.15  # min gap between best and 2nd-best cosine to accept a match
# 0.15 chosen from a real-ECAPA harness run (distinct TTS voices): 0.10 let a stranger
# through (50% reject), 0.15 gave 100% correct-ID + 100% stranger-reject. Re-tune on
# real family voices via scripts/eval_speaker.py.
_ECAPA_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
_MIN_FOR_MARGIN = 2  # need a 2nd-best score to apply the margin check


def _mean_embedding(vectors: list[list[float]]) -> list[float]:
    n = len(vectors)
    return [sum(dim) / n for dim in zip(*vectors, strict=True)]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


class EcapaSpeakerID:
    def __init__(
        self,
        memory: MemoryStore,
        threshold: float = _DEFAULT_THRESHOLD,
        margin: float = _DEFAULT_MARGIN,
        _embed: Callable[[AudioClip], list[float]] | None = None,
    ) -> None:
        self.memory, self.threshold, self.margin = memory, threshold, margin
        self._using_default_embed = _embed is None
        self._embed = _embed or self._default_embed
        self._model: Any = None

    def _load_model(self) -> Any:
        import speechbrain.inference.speaker as sb_speaker  # noqa: PLC0415 -- lazy

        sb: Any = sb_speaker
        return sb.EncoderClassifier.from_hparams(source=_ECAPA_SOURCE)

    def warmup(self) -> None:
        # Preload the ECAPA model at boot so the first turn doesn't pay for it.
        if self._using_default_embed and self._model is None:
            self._model = self._load_model()

    def _default_embed(self, clip: AudioClip) -> list[float]:
        if self._model is None:
            self._model = self._load_model()
        import torch  # noqa: PLC0415 -- lazy

        th: Any = torch
        npx: Any = np
        audio = npx.frombuffer(clip.samples, dtype=np.int16).astype(np.float32) / _PCM_MAX
        emb: Any = self._model.encode_batch(th.tensor(audio).unsqueeze(0))
        return emb.squeeze().detach().cpu().tolist()

    def enroll(self, name: str, clips: list[AudioClip]) -> Person:
        embedding = _mean_embedding([self._embed(clip) for clip in clips])
        person = Person(id=name.lower(), name=name, embedding=embedding, prefs={})
        self.memory.upsert_person(person)
        return person

    def identify(self, clip: AudioClip) -> str:
        vec = self._embed(clip)
        scores = sorted((cosine(vec, p.embedding), p.id) for p in self.memory.list_people())
        if not scores or scores[-1][0] < self.threshold:
            return GUEST
        best, best_id = scores[-1]
        if len(scores) >= _MIN_FOR_MARGIN and best - scores[-2][0] < self.margin:
            return GUEST
        return best_id
