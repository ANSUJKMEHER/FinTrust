import math
import uuid
import pytest

from app.services.hybrid_search_service import HybridSearchService
from app.services.reranking_service import RerankingService


def test_reciprocal_rank_fusion_scoring():
    """Verifies RRF mathematically combines dense and sparse ranks with k=60."""
    # Chunk A is rank 1 in Dense, rank 2 in Sparse
    # Chunk B is rank 2 in Dense, not present in Sparse
    # Chunk C is rank 1 in Sparse, not present in Dense
    cid_a = uuid.uuid4()
    cid_b = uuid.uuid4()
    cid_c = uuid.uuid4()

    dense_candidates = [
        {"chunk_id": cid_a, "content": "Chunk A content", "dense_rank": 1, "dense_score": 0.95},
        {"chunk_id": cid_b, "content": "Chunk B content", "dense_rank": 2, "dense_score": 0.85},
    ]

    sparse_candidates = [
        {"chunk_id": cid_c, "content": "Chunk C content", "sparse_rank": 1, "sparse_score": 0.12},
        {"chunk_id": cid_a, "content": "Chunk A content", "sparse_rank": 2, "sparse_score": 0.08},
    ]

    # Create dummy HybridSearchService without DB binding for unit testing fusion math
    class DummyHybridSearch(HybridSearchService):
        def __init__(self):
            pass

    service = DummyHybridSearch()
    fused = service.reciprocal_rank_fusion(dense_candidates, sparse_candidates, k_constant=60)

    assert len(fused) == 3

    # Expected RRF scores:
    # A: 1/(60+1) + 1/(60+2) = 1/61 + 1/62 = 0.016393 + 0.016129 = 0.032522
    # B: 1/(60+2) = 1/62 = 0.016129
    # C: 1/(60+1) = 1/61 = 0.016393
    # Sorted order should be: A (0.0325), C (0.01639), B (0.01612)
    assert fused[0]["chunk_id"] == cid_a
    assert math.isclose(fused[0]["rrf_score"], (1.0 / 61) + (1.0 / 62), rel_tol=1e-4)
    assert set(fused[0]["retrieval_sources"]) == {"dense", "sparse"}
    assert fused[0]["dense_rank"] == 1
    assert fused[0]["sparse_rank"] == 2

    assert fused[1]["chunk_id"] == cid_c
    assert math.isclose(fused[1]["rrf_score"], 1.0 / 61, rel_tol=1e-4)
    assert fused[1]["retrieval_sources"] == ["sparse"]
    assert fused[1]["dense_rank"] is None

    assert fused[2]["chunk_id"] == cid_b
    assert math.isclose(fused[2]["rrf_score"], 1.0 / 62, rel_tol=1e-4)
    assert fused[2]["retrieval_sources"] == ["dense"]
    assert fused[2]["sparse_rank"] is None


def test_cross_encoder_reranking():
    """Verifies reranking orders candidates by cross-encoder score and preserves explainability."""
    reranker = RerankingService()
    query = "suspicious activity report filing deadline 30 days"

    candidates = [
        {
            "chunk_id": uuid.uuid4(),
            "content": "General corporate governance rules and meeting minutes guidelines.",
            "rrf_score": 0.03,
            "dense_rank": 1,
            "sparse_rank": 3
        },
        {
            "chunk_id": uuid.uuid4(),
            "content": "Under BSA Section 5318(g), suspicious activity reports must be filed within 30 days.",
            "rrf_score": 0.025,
            "dense_rank": 2,
            "sparse_rank": 1
        }
    ]

    reranked = reranker.rerank(query, candidates, top_k=2)

    assert len(reranked) == 2
    # The second candidate with exact SAR 30 days content must score higher after reranking
    assert "BSA Section 5318(g)" in reranked[0]["content"]
    assert "cross_encoder_score" in reranked[0]
    assert reranked[0]["cross_encoder_score"] >= reranked[1]["cross_encoder_score"]
    # Verify original RRF metadata is preserved
    assert reranked[0]["rrf_score"] == 0.025
    assert reranked[0]["dense_rank"] == 2
    assert reranked[0]["sparse_rank"] == 1
