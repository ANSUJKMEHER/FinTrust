import logging
import math
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class RerankingService:
    """Enterprise Cross-Encoder Reranker preserving multi-stage ranking signals and explainability."""

    _model = None
    _model_name: str = settings.RERANKING_MODEL_NAME

    def __init__(self, model_name: str = settings.RERANKING_MODEL_NAME):
        self.model_name = model_name

    @classmethod
    def get_model(cls, model_name: str):
        """Loads and caches the CrossEncoder model once across application lifecycle."""
        import os
        if os.environ.get("FINTRUST_USE_MOCK_EMBEDDINGS") == "1":
            cls._model = False
            return False

        if cls._model is None or cls._model_name != model_name:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading CrossEncoder model '{model_name}'...")
                cls._model = CrossEncoder(model_name)
                cls._model_name = model_name
                logger.info(f"CrossEncoder '{model_name}' loaded successfully.")
            except Exception as e:
                logger.warning(
                    f"Could not load CrossEncoder '{model_name}': {e}. "
                    "Using lexical-semantic fallback reranking."
                )
                cls._model = False
        return cls._model

    def _fallback_scoring(self, query: str, content: str, rrf_score: float) -> float:
        """Calculates a fallback relevance score combining RRF rank and query term overlap."""
        q_words = set(query.lower().split())
        c_words = set(content.lower().split())
        if not q_words:
            return rrf_score

        overlap = len(q_words.intersection(c_words))
        lexical_boost = overlap / len(q_words)
        # Weighted combination of RRF signal and exact term matches
        return float(rrf_score * 0.6 + lexical_boost * 0.4)

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = settings.RERANK_TOP_K
    ) -> List[Dict[str, Any]]:
        """Reranks candidate chunks with cross-encoder scoring, preserving explainability."""
        if not candidates:
            return []

        clean_query = (query or "").strip()
        model = self.get_model(self.model_name)

        if model:
            try:
                pairs = [(clean_query, c.get("content", "")) for c in candidates]
                scores = model.predict(pairs)
                # Attach scores
                for idx, candidate in enumerate(candidates):
                    score = float(scores[idx])
                    # Sigmoid transform if logits are returned
                    if score < -10 or score > 10:
                        candidate["cross_encoder_score"] = 1.0 / (1.0 + math.exp(-score))
                    else:
                        candidate["cross_encoder_score"] = score
            except Exception as e:
                logger.warning(f"CrossEncoder predict failed: {e}. Falling back to lexical ranking.")
                for c in candidates:
                    c["cross_encoder_score"] = self._fallback_scoring(
                        clean_query,
                        c.get("content", ""),
                        c.get("rrf_score", 0.0)
                    )
        else:
            for c in candidates:
                c["cross_encoder_score"] = self._fallback_scoring(
                    clean_query,
                    c.get("content", ""),
                    c.get("rrf_score", 0.0)
                )

        # Sort candidates descending by cross_encoder_score
        reranked = sorted(candidates, key=lambda x: x.get("cross_encoder_score", 0.0), reverse=True)
        return reranked[:top_k]
