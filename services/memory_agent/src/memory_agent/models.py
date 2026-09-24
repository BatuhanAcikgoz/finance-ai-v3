"""Memory Agent Pydantic models."""
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CollectionType(str, Enum):
    """Qdrant collection types."""

    NEWS = "news_embeddings"
    KAP = "kap_embeddings"
    DECISION = "decision_memory"
    ANALYSIS = "analysis_embeddings"


class SimilaritySearchResult(BaseModel):
    """Single similarity search result."""

    id: str
    score: float
    payload: dict[str, Any]
    collection: CollectionType


class SimilaritySearchResponse(BaseModel):
    """Response from similarity search."""

    query: str
    results: list[SimilaritySearchResult]
    total_results: int
    search_time_ms: float


class EmbeddingRecord(BaseModel):
    """Record to be embedded and stored."""

    record_id: str
    collection: CollectionType
    text_representation: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class EmbedRequest(BaseModel):
    """Request to embed and store a record."""

    record_id: str
    collection: CollectionType
    text_representation: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    """Request to search for similar records."""

    query: str
    collection: CollectionType | None = None  # None = search all
    top_k: int = 10
    filter_criteria: dict[str, Any] | None = None


class MemoryStats(BaseModel):
    """Statistics about stored embeddings."""

    news_count: int = 0
    kap_count: int = 0
    decision_count: int = 0
    analysis_count: int = 0
    total_count: int = 0
    oldest_record: str | None = None
    newest_record: str | None = None
