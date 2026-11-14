from collections import defaultdict
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.user import User
from app.repositories.chunk_repository import ChunkRepository
from app.services.embedding_service import EmbeddingService
from app.services.permission_service import PermissionService
from app.services.reranking_service import RerankingService

logger = logging.getLogger(__name__)


class HybridSearchService:
    """Enterprise Hybrid Retrieval Service combining dense vectors, sparse FTS, RRF, and Cross-Encoder reranking."""

    def __init__(self, db: Session):
        self.db = db
        self.chunk_repo = ChunkRepository(db)
        self.embedding_service = EmbeddingService()
        self.reranking_service = RerankingService()
        self.perm_service = PermissionService(db)

    def dense_search(
        self,
        query: str,
        user: User,
        limit: int = settings.DENSE_SEARCH_LIMIT
    ) -> List[Dict[str, Any]]:
        """Executes dense vector similarity search with strict database-level tenant and ACL filtering."""
        allowed_doc_ids = self.perm_service.get_accessible_document_ids(user)
        if not allowed_doc_ids:
            return []

        query_vector = self.embedding_service.embed_query(query)
        results = self.chunk_repo.dense_search(
            tenant_id=user.tenant_id,
            allowed_doc_ids=allowed_doc_ids,
            query_vector=query_vector,
            limit=limit
        )

        for rank_idx, r in enumerate(results, start=1):
            r["dense_rank"] = rank_idx
            r["retrieval_sources"] = ["dense"]
        return results

    def sparse_search(
        self,
        query: str,
        user: User,
        limit: int = settings.SPARSE_SEARCH_LIMIT
    ) -> List[Dict[str, Any]]:
        """Executes sparse keyword search with strict database-level tenant and ACL filtering."""
        allowed_doc_ids = self.perm_service.get_accessible_document_ids(user)
        if not allowed_doc_ids:
            return []

        results = self.chunk_repo.sparse_search(
            tenant_id=user.tenant_id,
            allowed_doc_ids=allowed_doc_ids,
            query_text=query,
            limit=limit
        )

        for rank_idx, r in enumerate(results, start=1):
            r["sparse_rank"] = rank_idx
            r["retrieval_sources"] = ["sparse"]
        return results

    def reciprocal_rank_fusion(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        k_constant: int = settings.RRF_K_CONSTANT
    ) -> List[Dict[str, Any]]:
        """Fuses dense and sparse ranked candidate lists using Reciprocal Rank Fusion (RRF).
        
        RRF_score(d) = sum(1 / (k + rank_m(d)))
        """
        fused_candidates: Dict[uuid.UUID, Dict[str, Any]] = {}

        # 1. Process Dense Results
        for item in dense_results:
            c_id = item["chunk_id"]
            dense_rank = item.get("dense_rank", 1)
            score_contribution = 1.0 / (k_constant + dense_rank)

            entry = dict(item)
            entry["rrf_score"] = score_contribution
            entry["retrieval_sources"] = ["dense"]
            entry["sparse_rank"] = None
            fused_candidates[c_id] = entry

        # 2. Process Sparse Results
        for item in sparse_results:
            c_id = item["chunk_id"]
            sparse_rank = item.get("sparse_rank", 1)
            score_contribution = 1.0 / (k_constant + sparse_rank)

            if c_id in fused_candidates:
                fused_candidates[c_id]["rrf_score"] += score_contribution
                fused_candidates[c_id]["sparse_rank"] = sparse_rank
                fused_candidates[c_id]["sparse_score"] = item.get("sparse_score")
                if "sparse" not in fused_candidates[c_id]["retrieval_sources"]:
                    fused_candidates[c_id]["retrieval_sources"].append("sparse")
            else:
                entry = dict(item)
                entry["rrf_score"] = score_contribution
                entry["retrieval_sources"] = ["sparse"]
                entry["dense_rank"] = None
                entry["dense_score"] = None
                fused_candidates[c_id] = entry

        # Sort descending by fused RRF score
        ranked_list = sorted(
            fused_candidates.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )

        # Attach RRF overall rank
        for idx, item in enumerate(ranked_list, start=1):
            item["rrf_rank"] = idx

        return ranked_list

    def hybrid_search(
        self,
        query: str,
        user: User,
        dense_limit: int = settings.DENSE_SEARCH_LIMIT,
        sparse_limit: int = settings.SPARSE_SEARCH_LIMIT,
        top_k: int = settings.RERANK_TOP_K,
        apply_rerank: bool = True
    ) -> List[Dict[str, Any]]:
        """Full end-to-end hybrid retrieval:
        Dense Search + Sparse Search -> Reciprocal Rank Fusion -> Cross-Encoder Reranking
        """
        dense_cands = self.dense_search(query, user, limit=dense_limit)
        sparse_cands = self.sparse_search(query, user, limit=sparse_limit)

        fused_cands = self.reciprocal_rank_fusion(dense_cands, sparse_cands)

        if apply_rerank and fused_cands:
            reranked = self.reranking_service.rerank(
                query=query,
                candidates=fused_cands,
                top_k=top_k
            )
            return reranked
        return fused_cands[:top_k]
