import hashlib
import logging
import math
from typing import List, Optional
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Enterprise Embedding Service using Sentence Transformers with dimension validation and batching."""

    _model = None
    _model_name: str = settings.EMBEDDING_MODEL_NAME
    _dimension: int = settings.EMBEDDING_DIMENSION

    def __init__(
        self,
        model_name: str = settings.EMBEDDING_MODEL_NAME,
        dimension: int = settings.EMBEDDING_DIMENSION
    ):
        self.model_name = model_name
        self.dimension = dimension

    @classmethod
    def get_model(cls, model_name: str):
        """Loads and caches the SentenceTransformer model once across the application process."""
        import os
        if os.environ.get("FINTRUST_USE_MOCK_EMBEDDINGS") == "1":
            cls._model = False
            return False

        if cls._model is None or cls._model_name != model_name:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading SentenceTransformer model '{model_name}'...")
                cls._model = SentenceTransformer(model_name)
                cls._model_name = model_name
                logger.info(f"Model '{model_name}' loaded successfully.")
            except Exception as e:
                logger.warning(
                    f"Could not load SentenceTransformer '{model_name}': {e}. "
                    "Falling back to deterministic pseudo-embedding mode."
                )
                cls._model = False  # Mark as unavailable
        return cls._model

    def _deterministic_embedding(self, text: str) -> List[float]:
        """Generates a deterministic, normalized 384-dimensional vector based on token hashing.
        
        Used when the external neural model weights cannot be downloaded or in constrained environments.
        """
        dim = self.dimension
        vec = np.zeros(dim, dtype=np.float32)
        words = text.lower().split()
        if not words:
            # Non-zero normalized unit vector for empty input
            vec[0] = 1.0
            return vec.tolist()

        for idx, word in enumerate(words):
            # Map word to multiple vector indices using SHA-256
            h = hashlib.sha256(f"{word}_{idx}".encode("utf-8")).digest()
            for i in range(0, min(16, len(h) - 1), 2):
                pos = (h[i] * 256 + h[i + 1]) % dim
                weight = ((h[i] % 100) / 50.0) - 1.0  # -1.0 to 1.0
                vec[pos] += weight

        # L2 Normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        else:
            vec[0] = 1.0

        return vec.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Embeds a single query string, returning an L2-normalized vector."""
        clean_query = (query or "").strip()
        if not clean_query:
            return [0.0] * self.dimension

        model = self.get_model(self.model_name)
        if model:
            try:
                # bge models recommend prepending prompt for retrieval if applicable
                embedding = model.encode(
                    clean_query,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
                vec = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
                if len(vec) != self.dimension:
                    raise ValueError(f"Embedding dimension mismatch: expected {self.dimension}, got {len(vec)}")
                return vec
            except Exception as e:
                logger.warning(f"Model encoding failed: {e}. Using deterministic fallback.")

        return self._deterministic_embedding(clean_query)

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Batch embeds a list of document chunk texts."""
        if not texts:
            return []

        model = self.get_model(self.model_name)
        if model:
            try:
                embeddings = model.encode(
                    texts,
                    batch_size=batch_size,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
                results: List[List[float]] = []
                for emb in embeddings:
                    vec = emb.tolist() if hasattr(emb, "tolist") else list(emb)
                    if len(vec) != self.dimension:
                        raise ValueError(f"Embedding dimension mismatch: expected {self.dimension}, got {len(vec)}")
                    results.append(vec)
                return results
            except Exception as e:
                logger.warning(f"Batch encoding failed: {e}. Using deterministic fallback.")

        return [self._deterministic_embedding(t) for t in texts]
