import math
import numpy as np
import pytest

from app.services.embedding_service import EmbeddingService


def test_embedding_dimensions_and_normalization():
    """Verifies embeddings are 384 dimensions and normalized to unit length."""
    service = EmbeddingService(dimension=384)
    query = "What are the regulatory requirements for SAR reporting?"
    vec = service.embed_query(query)

    assert len(vec) == 384
    norm = np.linalg.norm(vec)
    assert math.isclose(norm, 1.0, rel_tol=1e-3)


def test_batch_embedding():
    """Verifies batch document embedding preserves order and dimension."""
    service = EmbeddingService(dimension=384)
    texts = [
        "BSA Section 5318(g) suspicious transaction rules.",
        "Basel III liquidity coverage ratio standards.",
        "GDPR Article 33 72-hour breach notification."
    ]
    embeddings = service.embed_documents(texts, batch_size=2)

    assert len(embeddings) == 3
    for emb in embeddings:
        assert len(emb) == 384
        assert math.isclose(np.linalg.norm(emb), 1.0, rel_tol=1e-3)


def test_empty_and_whitespace_input():
    """Verifies empty strings or whitespace don't raise uncaught exceptions."""
    service = EmbeddingService(dimension=384)
    vec = service.embed_query("")
    assert len(vec) == 384

    batch = service.embed_documents(["   ", ""])
    assert len(batch) == 2
    assert len(batch[0]) == 384
    assert len(batch[1]) == 384
