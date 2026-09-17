import math
from collections.abc import Callable
from typing import Any

import numpy as np

from tvagent.core.models import GUEST, AudioClip, Person
from tvagent.core.ports import MemoryStore

_PCM_MAX = 32768.0
_DEFAULT_THRESHOLD = 0.25
_ECAPA_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"


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
        _embed: Callable[[AudioClip], list[float]] | None = None,
    ) -> None:
        self.memory, self.threshold = memory, threshold
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

    def enroll(self, name: str, clip: AudioClip) -> Person:
        person = Person(id=name.lower(), name=name, embedding=self._embed(clip), prefs={})
        self.memory.upsert_person(person)
        return person

    def identify(self, clip: AudioClip) -> str:
        vec = self._embed(clip)
        best_id, best = GUEST, self.threshold
        for p in self.memory.list_people():
            score = cosine(vec, p.embedding)
            if score >= best:
                best, best_id = score, p.id
        return best_id
