"""Memory Agent FastAPI handlers."""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from memory_agent.config import settings
from memory_agent.models import (
    CollectionType,
    EmbeddingRecord,
    EmbedRequest,
    MemoryStats,
    SearchRequest,
    SimilaritySearchResponse,
)
from memory_agent.service import MemoryAgentService

router = APIRouter(prefix="/memory", tags=["memory"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    service: str = "memory_agent"
    version: str = "1.0.0"


class EmbedResponse(BaseModel):
    """Response from embedding a record."""

    record: EmbeddingRecord
    embedded_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class StatsResponse(BaseModel):
    """Response with memory statistics."""

    stats: MemoryStats
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


# Service instance
_service: MemoryAgentService | None = None


async def get_service() -> MemoryAgentService:
    """Get or create the service instance."""
    global _service
    if _service is None:
        _service = MemoryAgentService()
        await _service.initialize()
    return _service


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", service="memory_agent", version="1.0.0")


@router.post("/embed", response_model=EmbedResponse)
async def embed_record(request: EmbedRequest) -> EmbedResponse:
    """
    Embed a record and store in Qdrant.

    Args:
        request: EmbedRequest with record details

    Returns:
        EmbedResponse with embedded record
    """
    service = await get_service()

    try:
        record = await service.embed_record(request)
        return EmbedResponse(record=record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e!s}")


@router.post("/embed/decision")
async def embed_decision(decision_record: dict[str, Any]) -> dict[str, Any]:
    """
    Embed a decision record.

    Args:
        decision_record: Decision record dict

    Returns:
        Record ID
    """
    service = await get_service()

    try:
        record_id = await service.embed_decision(decision_record)
        return {
            "status": "embedded",
            "record_id": record_id,
            "collection": CollectionType.DECISION.value,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e!s}")


@router.post("/embed/analysis")
async def embed_analysis(analysis_result: dict[str, Any]) -> dict[str, Any]:
    """
    Embed an analysis result.

    Args:
        analysis_result: Analysis result dict

    Returns:
        Record ID
    """
    service = await get_service()

    try:
        record_id = await service.embed_analysis(analysis_result)
        return {
            "status": "embedded",
            "record_id": record_id,
            "collection": CollectionType.ANALYSIS.value,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e!s}")


@router.post("/search", response_model=SimilaritySearchResponse)
async def search(request: SearchRequest) -> SimilaritySearchResponse:
    """
    Search for similar records.

    Args:
        request: SearchRequest with query and filters

    Returns:
        SimilaritySearchResponse with results
    """
    service = await get_service()

    try:
        response = await service.search(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e!s}")


@router.get("/search/similar/{ticker}")
async def get_similar_decisions(ticker: str, top_k: int = 5) -> dict[str, Any]:
    """
    Get similar past decisions for a ticker.

    Args:
        ticker: BIST ticker symbol
        top_k: Number of results to return

    Returns:
        List of similar decision results
    """
    service = await get_service()

    if top_k < 1 or top_k > 50:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 50")

    try:
        results = await service.get_similar_decisions(ticker, top_k)
        return {
            "ticker": ticker,
            "results": [
                {
                    "id": r.id,
                    "score": r.score,
                    "payload": r.payload,
                    "collection": r.collection.value,
                }
                for r in results
            ],
            "count": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e!s}")


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """
    Get statistics about stored embeddings.

    Returns:
        MemoryStats with counts per collection
    """
    service = await get_service()

    try:
        stats = await service.get_stats()
        return StatsResponse(stats=stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats failed: {e!s}")


@router.get("/collections")
async def list_collections() -> dict[str, Any]:
    """
    List available collections.

    Returns:
        List of collection names and configurations
    """
    return {
        "collections": [
            {
                "name": name,
                "vector_size": config["vector_size"],
                "distance": config["distance"].value,
            }
            for name, config in {
                "news_embeddings": {"vector_size": settings.embedding_dimensions, "distance": "COSINE"},
                "kap_embeddings": {"vector_size": settings.embedding_dimensions, "distance": "COSINE"},
                "decision_memory": {"vector_size": settings.embedding_dimensions, "distance": "COSINE"},
                "analysis_embeddings": {"vector_size": settings.embedding_dimensions, "distance": "COSINE"},
            }.items()
        ],
        "retention_days": settings.retention_days,
    }
