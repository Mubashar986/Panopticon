"""Embedding provider protocol and implementations (OpenRouter & Deterministic Fallback)."""

from __future__ import annotations

import math
import re
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("panopticon.indexer.embeddings")


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate the cosine similarity between two numeric vectors.

    Returns:
        float: Similarity score between -1.0 and 1.0 (or 0.0 if zero vector).
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot_product = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for a, b in zip(vec1, vec2):
        dot_product += a * b
        norm_a += a * a
        norm_b += b * b

    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0

    return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))


class EmbeddingProvider(Protocol):
    """Protocol for generating dense vector embeddings."""

    @property
    def dimension(self) -> int:
        """Dimensionality of the generated vectors."""
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Compute embedding vectors for a batch of texts."""
        ...

    def embed_query(self, query: str) -> list[float]:
        """Compute an embedding vector for a single query string."""
        ...


class DeterministicHashEmbeddingProvider:
    """Offline, zero-setup term-frequency embedding provider with L2 normalization."""

    def __init__(self, dimension: int = 128) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Compute normalized term-frequency vectors for each text."""
        return [self.embed_query(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        """Compute an L2-normalized pseudo-semantic hash vector for a text string."""
        if not query or not query.strip():
            return [0.0] * self._dimension

        vec = [0.0] * self._dimension
        words = re.findall(r"\b\w+\b", query.lower())
        if not words:
            return vec

        for word in words:
            # Deterministic bucket assignment
            idx = abs(hash(word)) % self._dimension
            vec[idx] += 1.0

        # L2 Unit Normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0.0:
            vec = [x / norm for x in vec]

        return vec


class OpenRouterEmbeddingProvider:
    """Cloud embedding client using OpenRouter / OpenAI-compatible REST endpoint."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str = "https://openrouter.ai/api/v1",
        dimension: int = 1536,
        timeout_seconds: float = 10.0,
        fallback: EmbeddingProvider | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._dimension = dimension
        self.timeout_seconds = timeout_seconds
        self.fallback = fallback if fallback is not None else DeterministicHashEmbeddingProvider()

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch compute embeddings via OpenRouter with graceful local fallback."""
        if not self.api_key or not texts:
            return self.fallback.embed_texts(texts)

        # Clean strings
        clean_inputs = [t if t.strip() else "empty document chunk" for t in texts]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Mubashar986/Panopticon",
            "X-Title": "Panopticon Document Intelligence",
        }

        payload = {
            "model": self.model,
            "input": clean_inputs,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                raw_items = data.get("data", [])
                # Sort items by index to preserve input order
                raw_items.sort(key=lambda x: x.get("index", 0))
                embeddings = [item["embedding"] for item in raw_items]

                if len(embeddings) == len(texts):
                    return embeddings

        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            logger.warning("OpenRouter embedding call failed (%s). Falling back to local hash embeddings.", exc)

        return self.fallback.embed_texts(texts)

    def embed_query(self, query: str) -> list[float]:
        """Compute embedding for a single search query."""
        results = self.embed_texts([query])
        return results[0] if results else [0.0] * self.dimension


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Factory helper returning OpenRouterEmbeddingProvider or Deterministic fallback singleton."""
    cfg = settings if settings is not None else get_settings()

    if cfg.OPENROUTER_API_KEY and cfg.OPENROUTER_API_KEY.strip():
        logger.info("Initializing OpenRouterEmbeddingProvider (model=text-embedding-3-small)")
        return OpenRouterEmbeddingProvider(
            api_key=cfg.OPENROUTER_API_KEY,
            model="text-embedding-3-small",
            base_url=cfg.OPENROUTER_BASE_URL,
        )

    logger.debug("OPENROUTER_API_KEY is unset; using local DeterministicHashEmbeddingProvider.")
    return DeterministicHashEmbeddingProvider()
