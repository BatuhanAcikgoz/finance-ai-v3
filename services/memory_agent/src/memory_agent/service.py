"""Memory Agent main service logic."""
import time
from typing import Any

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from memory_agent.config import settings
from memory_agent.models import (
    CollectionType,
    EmbeddingRecord,
    EmbedRequest,
    MemoryStats,
    SearchRequest,
    SimilaritySearchResponse,
    SimilaritySearchResult,
)

logger = structlog.get_logger()


# Collection configurations
COLLECTION_CONFIGS: dict[str, dict[str, Any]] = {
    CollectionType.NEWS.value: {
        "vector_size": settings.embedding_dimensions,
        "distance": Distance.COSINE,
    },
    CollectionType.KAP.value: {
        "vector_size": settings.embedding_dimensions,
        "distance": Distance.COSINE,
    },
    CollectionType.DECISION.value: {
        "vector_size": settings.embedding_dimensions,
        "distance": Distance.COSINE,
    },
    CollectionType.ANALYSIS.value: {
        "vector_size": settings.embedding_dimensions,
        "distance": Distance.COSINE,
    },
}


class MemoryAgentService:
    """Service for embedding and similarity search via Qdrant."""

    def __init__(self) -> None:
        """Initialize the memory agent service."""
        self._qdrant: QdrantClient | None = None
        self._embedding_client: Any = None  # LiteLLM client placeholder

    async def initialize(self) -> None:
        """Initialize Qdrant client and ensure collections exist."""
        self._qdrant = QdrantClient(url=settings.qdrant_url)
        self._ensure_collections()
        logger.info("memory_agent_initialized", qdrant_url=settings.qdrant_url)

    def _ensure_collections(self) -> None:
        """Ensure all required collections exist with correct configuration."""
        for collection_name, config in COLLECTION_CONFIGS.items():
            collections = self._qdrant.get_collections().collections
            collection_names = [c.name for c in collections]

            if collection_name not in collection_names:
                self._qdrant.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(**config),
                )
                logger.info("collection_created", collection=collection_name)

    async def close(self) -> None:
        """Close connections."""
        self._qdrant = None
        logger.info("memory_agent_shutdown")

    # -------------------------------------------------------------------------
    # Embedding
    # -------------------------------------------------------------------------

    async def _get_embedding(self, text: str) -> list[float]:
        """
        Get embedding vector for text using LiteLLM.

        In production, this calls litellm.embedding() with text-embedding-3-large.
        """
        # Placeholder for LiteLLM embedding call
        # In production: response = await litellm.aembedding(model=settings.embedding_model, input=text)
        # return response.data[0].embedding

        # Return placeholder vector of correct dimensions
        import random
        return [random.random() for _ in range(settings.embedding_dimensions)]

    async def embed_record(self, request: EmbedRequest) -> EmbeddingRecord:
        """
        Embed a record and store in Qdrant.

        Args:
            request: EmbedRequest with record details

        Returns:
            EmbeddingRecord with metadata
        """
        if self._qdrant is None:
            raise RuntimeError("Qdrant client not initialized")

        # Get embedding
        vector = await self._get_embedding(request.text_representation)

        # Create record
        record = EmbeddingRecord(
            record_id=request.record_id,
            collection=request.collection,
            text_representation=request.text_representation,
            metadata=request.metadata,
        )

        # Store in Qdrant
        self._qdrant.upsert(
            collection_name=request.collection.value,
            points=[
                {
                    "id": request.record_id,
                    "vector": vector,
                    "payload": {
                        "text": request.text_representation,
                        "metadata": request.metadata,
                        "collection": request.collection.value,
                        "created_at": record.created_at,
                    },
                }
            ],
        )

        logger.info(
            "record_embedded",
            record_id=request.record_id,
            collection=request.collection.value,
        )

        return record

    async def embed_decision(self, decision_record: dict[str, Any]) -> str:
        """
        Embed a decision record.

        Converts decision to text representation and stores in Qdrant.

        Args:
            decision_record: Decision record dict

        Returns:
            Record ID
        """
        # Build text representation
        ticker = decision_record.get("ticker", "UNKNOWN")
        action = decision_record.get("action", "UNKNOWN")
        confidence = decision_record.get("confidence", 0.0)
        evidence = decision_record.get("evidence", [])

        evidence_summary = "; ".join(
            f"{e.get('stream', 'UNKNOWN')}:{e.get('signal', 'UNKNOWN')}({e.get('strength', 0):.2f})"
            for e in evidence[:3]  # Top 3 evidence
        )

        text_representation = (
            f"Decision: {action} {ticker} "
            f"(confidence: {confidence:.2f}). "
            f"Evidence: {evidence_summary}"
        )

        metadata = {
            "ticker": ticker,
            "action": action,
            "confidence": confidence,
            "effective_at": decision_record.get("effective_at"),
            "portfolio_id": decision_record.get("portfolio_id"),
        }

        request = EmbedRequest(
            record_id=decision_record.get("decision_id", ""),
            collection=CollectionType.DECISION,
            text_representation=text_representation,
            metadata=metadata,
        )

        record = await self.embed_record(request)
        return record.record_id

    async def embed_analysis(self, analysis_result: dict[str, Any]) -> str:
        """
        Embed an analysis result.

        Args:
            analysis_result: Analysis result dict

        Returns:
            Record ID
        """
        ticker = analysis_result.get("ticker", "UNKNOWN")
        analysis_type = analysis_result.get("analysis_type", "unknown")
        conclusion = analysis_result.get("conclusion", "")
        sentiment = analysis_result.get("sentiment", "NEUTRAL")

        text_representation = (
            f"Analysis: {analysis_type} for {ticker}. "
            f"Sentiment: {sentiment}. "
            f"Conclusion: {conclusion[:200]}..."
        )

        metadata = {
            "ticker": ticker,
            "analysis_type": analysis_type,
            "sentiment": sentiment,
        }

        request = EmbedRequest(
            record_id=analysis_result.get("result_id", ""),
            collection=CollectionType.ANALYSIS,
            text_representation=text_representation,
            metadata=metadata,
        )

        record = await self.embed_record(request)
        return record.record_id

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    async def search(
        self, request: SearchRequest
    ) -> SimilaritySearchResponse:
        """
        Search for similar records.

        Args:
            request: SearchRequest with query and filters

        Returns:
            SimilaritySearchResponse with results
        """
        if self._qdrant is None:
            raise RuntimeError("Qdrant client not initialized")

        start_time = time.time()

        # Get query embedding
        query_vector = await self._get_embedding(request.query)

        # Determine which collections to search
        if request.collection:
            collections = [request.collection.value]
        else:
            collections = list(COLLECTION_CONFIGS.keys())

        all_results: list[SimilaritySearchResult] = []

        for collection in collections:
            try:
                results = self._qdrant.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    limit=request.top_k,
                    score_threshold=settings.min_similarity_score,
                    query_filter=request.filter_criteria,
                )

                for result in results:
                    all_results.append(
                        SimilaritySearchResult(
                            id=str(result.id),
                            score=result.score,
                            payload=result.payload or {},
                            collection=CollectionType(collection),
                        )
                    )
            except Exception as e:
                logger.warning(
                    "search_failed_on_collection",
                    collection=collection,
                    error=str(e),
                )

        # Sort by score descending
        all_results.sort(key=lambda x: x.score, reverse=True)
        all_results = all_results[: request.top_k]

        search_time_ms = (time.time() - start_time) * 1000

        return SimilaritySearchResponse(
            query=request.query,
            results=all_results,
            total_results=len(all_results),
            search_time_ms=search_time_ms,
        )

    async def get_similar_decisions(
        self, ticker: str, top_k: int = 5
    ) -> list[SimilaritySearchResult]:
        """
        Get similar past decisions for a ticker.

        Args:
            ticker: BIST ticker symbol
            top_k: Number of results to return

        Returns:
            List of similar decision results
        """
        search_request = SearchRequest(
            query=f"Past trading decisions for {ticker}",
            collection=CollectionType.DECISION,
            top_k=top_k,
            filter_criteria={
                "must": [
                    {"key": "metadata.ticker", "match": {"value": ticker}}
                ]
            },
        )

        response = await self.search(search_request)
        return response.results

    # -------------------------------------------------------------------------
    # Stats & Maintenance
    # -------------------------------------------------------------------------

    async def get_stats(self) -> MemoryStats:
        """
        Get statistics about stored embeddings.

        Returns:
            MemoryStats with counts per collection
        """
        if self._qdrant is None:
            raise RuntimeError("Qdrant client not initialized")

        stats = MemoryStats()

        for collection_name in COLLECTION_CONFIGS:
            try:
                info = self._qdrant.get_collection(collection_name)
                count = info.points_count

                if CollectionType.NEWS.value in collection_name:
                    stats.news_count = count
                elif CollectionType.KAP.value in collection_name:
                    stats.kap_count = count
                elif CollectionType.DECISION.value in collection_name:
                    stats.decision_count = count
                elif CollectionType.ANALYSIS.value in collection_name:
                    stats.analysis_count = count

                stats.total_count += count
            except Exception as e:
                logger.warning(
                    "stats_collection_failed",
                    collection=collection_name,
                    error=str(e),
                )

        return stats

    async def delete_old_records(self, days: int = 730) -> int:
        """
        Delete records older than specified days.

        Args:
            days: Retention period in days

        Returns:
            Number of deleted records
        """
        if self._qdrant is None:
            raise RuntimeError("Qdrant client not initialized")

        # Note: Qdrant doesn't have built-in TTL
        # This would need to be implemented with a timestamp field
        # and periodic cleanup using delete by filter

        logger.info("delete_old_records_not_implemented", days=days)
        return 0

    # -------------------------------------------------------------------------
    # Service Runner
    # -------------------------------------------------------------------------

    async def run(self) -> None:
        """Run the memory agent service (listen for Redis events)."""
        await self.initialize()
        try:
            logger.info("memory_agent_running")
            # In production, this would listen to Redis for new records to embed
            # For now, this is a passive service triggered via API
            while True:
                import asyncio
                await asyncio.sleep(3600)  # Sleep 1 hour
        except Exception as e:
            logger.error("memory_agent_error", error=str(e))
        finally:
            await self.close()
