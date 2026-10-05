"""Embedding provider interface. Milestone 1 ships a deterministic local stub
so the architecture (chunk -> embed -> store) exists without network calls.
Plug a real model (sentence-transformers / API) behind this interface later.
"""

import hashlib
import math
from abc import ABC, abstractmethod

from app.core.config import get_settings


class EmbeddingProvider(ABC):
    dim: int = 384

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """Deterministic bag-of-hash embedding. NOT semantic — placeholder only."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            vec = [0.0] * self.dim
            for token in t.lower().split():
                h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


def get_embedding_provider() -> EmbeddingProvider:
    s = get_settings()
    # Future: if s.embedding_provider == "openai" -> OpenAIEmbeddingProvider, etc.
    return LocalHashEmbeddingProvider(dim=s.embedding_dim)
