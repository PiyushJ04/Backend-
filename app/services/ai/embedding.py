from __future__ import annotations

import math
from typing import Any

from huggingface_hub import InferenceClient

from app.core.config import settings


class EmbeddingConfigurationError(RuntimeError):
    """Raised when embedding generation is not configured."""


class EmbeddingGenerationError(RuntimeError):
    """Raised when Hugging Face cannot generate an embedding."""


class EmbeddingService:
    """Generate 384-dimensional BGE embeddings through Hugging Face inference.

    BAAI/bge-small-en-v1.5 is intentionally kept behind this service so the
    rest of the application does not depend on a particular inference host.
    """

    def __init__(self, client: InferenceClient | None = None) -> None:
        if not settings.hf_token:
            raise EmbeddingConfigurationError(
                "HF_TOKEN is not configured. Add a Hugging Face User Access Token "
                "before generating document embeddings."
            )

        self.model = settings.embedding_model
        self.client = client or InferenceClient(
            token=settings.hf_token,
            provider=settings.hf_provider,
            timeout=settings.embedding_timeout_seconds,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed document passages."""
        return self._embed_texts(texts)

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query using the BGE retrieval instruction."""
        return self._embed_texts([
            "Represent this sentence for searching relevant passages: " + query.strip()
        ])[0]

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            cleaned = text.strip()
            if not cleaned:
                continue
            try:
                raw = self.client.feature_extraction(
                    cleaned,
                    model=self.model,
                )
                vector = self._to_sentence_vector(raw)
            except Exception as exc:
                raise EmbeddingGenerationError(
                    f"Hugging Face embedding inference failed: {exc}"
                ) from exc

            if len(vector) != settings.embedding_dimensions:
                raise EmbeddingGenerationError(
                    f"Embedding model returned {len(vector)} dimensions; "
                    f"expected {settings.embedding_dimensions}."
                )
            vectors.append(vector)

        return vectors

    @staticmethod
    def _to_sentence_vector(raw: Any) -> list[float]:
        """Normalize 1D/2D/3D HF feature-extraction output to one vector."""
        if hasattr(raw, "tolist"):
            raw = raw.tolist()

        if not isinstance(raw, list) or not raw:
            raise ValueError("Embedding response was empty or not a list")

        # Some inference backends return [batch, tokens, dimensions].
        if isinstance(raw[0], list) and raw[0] and isinstance(raw[0][0], list):
            raw = raw[0]

        if isinstance(raw[0], list):
            vector = EmbeddingService._mean_pool(raw)
        else:
            vector = [float(x) for x in raw]

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            raise ValueError("Embedding model returned a zero vector")
        return [value / norm for value in vector]

    @staticmethod
    def _mean_pool(rows: list[list[float]]) -> list[float]:
        width = len(rows[0])
        if width == 0:
            raise ValueError("Embedding response contained empty vectors")
        if any(len(row) != width for row in rows):
            raise ValueError("Embedding response contains inconsistent dimensions")
        return [
            sum(float(row[index]) for row in rows) / len(rows)
            for index in range(width)
        ]
