"""Turn text into vectors so we can search by meaning."""

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from .config import get_settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    """Small local model (bge-small, 384 dims). Downloads once, then works offline. No API key."""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vec.tolist() for vec in self.model.embed(texts)]


class HashEmbedder:
    """Offline fallback for tests: a bag-of-words vector built with hashing.

    Not as smart as a real model, but deterministic and good enough for keyword-style search.
    """

    def __init__(self, dim: int):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * self.dim
            for word in re.findall(r"[a-z0-9+#.]+", t.lower()):
                h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider == "hash":
        return HashEmbedder(s.embedding_dim)
    return FastEmbedEmbedder(s.embedding_model)
