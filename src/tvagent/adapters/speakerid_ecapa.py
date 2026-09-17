import math
import numpy as np
from tvagent.core.models import AudioClip, Person, GUEST

def cosine(a, b) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)

class EcapaSpeakerID:
    def __init__(self, memory, threshold: float = 0.25, _embed=None):
        self.memory, self.threshold = memory, threshold
        self._embed = _embed or self._default_embed
        self._model = None

    def _default_embed(self, clip: AudioClip) -> list[float]:
        if self._model is None:
            from speechbrain.inference.speaker import EncoderClassifier
            self._model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb")
        import torch
        audio = np.frombuffer(clip.samples, dtype=np.int16).astype(np.float32) / 32768.0
        emb = self._model.encode_batch(torch.tensor(audio).unsqueeze(0))
        return emb.squeeze().detach().cpu().tolist()

    def enroll(self, name: str, clip: AudioClip) -> Person:
        person = Person(id=name.lower(), name=name, embedding=self._embed(clip), prefs={})
        self.memory.upsert_person(person)
        return person

    def identify(self, clip: AudioClip) -> str:
        vec = self._embed(clip)
        best_id, best = GUEST, self.threshold
        for p in self.memory.list_people():
            if p.id == GUEST: continue
            score = cosine(vec, p.embedding)
            if score >= best:
                best, best_id = score, p.id
        return best_id
