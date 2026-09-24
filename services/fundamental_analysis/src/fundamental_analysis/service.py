"""Fundamental Analysis main service logic."""
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog
from redis.asyncio import Redis

from fundamental_analysis.client import LiteLLMClient
from fundamental_analysis.config import settings
from fundamental_analysis.models import (
    DataCompleteness,
    Direction,
    ExtractedFinancials,
    FundamentalAnalysisResult,
    FundamentalRatios,
    PeerPercentiles,
    SourceCitation,
)

logger = structlog.get_logger(__name__)


class FundamentalAnalysisService:
    """Service for running fundamental analysis on KAP disclosures."""

    # Financial categories that contain earnings data
    EARNINGS_CATEGORIES = {
        "FINANCIAL_REPORT",
        "QUARTERLY_RESULT",
        "ANNUAL_RESULT",
        "MATERIAL_EVENT",  # Some material events contain earnings
    }

    def __init__(self) -> None:
        """Initialize fundamental analysis service."""
        self._llm_client = LiteLLMClient()
        self._redis: Redis | None = None
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Initialize Redis and database connections."""
        self._redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
        )

    async def close(self) -> None:
        """Close all connections."""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.close()

    def _check_idempotency(self, publishing_id: str) -> str:
        """Generate idempotency key."""
        return f"fundamental:{hashlib.sha256(publishing_id.encode()).hexdigest()[:16]}"

    async def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if this disclosure was already processed."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return await self._redis.exists(idempotency_key) > 0

    async def _mark_processed(self, idempotency_key: str) -> None:
        """Mark disclosure as processed in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(
            idempotency_key,
            settings.idempotency_key_ttl_seconds,
            "1",
        )

    async def _fetch_kap_disclosure(
        self, publishing_id: str
    ) -> dict[str, Any] | None:
        """Fetch KAP disclosure from database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT publishing_id, title, summary, body, category, tickers
                FROM kap.disclosures
                WHERE publishing_id = $1
                """,
                publishing_id,
            )
            if row:
                return dict(row)
            return None

    async def _fetch_ticker_price(self, ticker: str) -> float | None:
        """Fetch latest price for ticker from database."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT close FROM market_data.ticks
                WHERE ticker = $1
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                ticker,
            )
            if row:
                return row["close"]
            return None

    async def _fetch_peer_set(self, ticker: str) -> list[str]:
        """Fetch peer tickers from same sector."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            # In a real implementation, we would have a tickers table with sector info
            # For now, return empty list - this would be enhanced with actual sector data
            rows = await conn.fetch(
                """
                SELECT ticker FROM kap.disclosures
                WHERE $1 = ANY(tickers)
                LIMIT 10
                """,
                ticker,
            )
            peers = [r["ticker"] for r in rows if r["ticker"] != ticker]
            return peers[:9]  # Max 9 peers

    async def _fetch_peer_ratios(
        self, peers: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch latest ratios for peer companies."""
        if not self._pool or not peers:
            return []

        async with self._pool.acquire() as _conn:
            # This would query a fundamental_analyses table if it existed
            # For now, return empty list
            return []

    def _compute_ratios(
        self,
        financials: ExtractedFinancials,
        market_cap: float | None,
        current_price: float | None,
        shares_outstanding: float | None = None,
    ) -> FundamentalRatios:
        """
        Compute fundamental ratios from extracted financials.

        Ratios are computed deterministically in Python per FR-027 requirements.
        """
        ratios = FundamentalRatios()

        # Infer shares outstanding from market cap / price if not provided
        if shares_outstanding is None and market_cap and current_price and current_price > 0:
            shares_outstanding = market_cap / current_price

        # P/E Ratio
        if financials.net_income and shares_outstanding and shares_outstanding > 0:
            eps_calc = financials.net_income / shares_outstanding
            if eps_calc > 0 and current_price:
                ratios.pe_ratio = current_price / eps_calc
                ratios.pe_flagged = ratios.pe_ratio > 100 or ratios.pe_ratio < 0

        # P/B Ratio
        if financials.equity and shares_outstanding and shares_outstanding > 0:
            book_value_per_share = financials.equity / shares_outstanding
            if book_value_per_share > 0 and current_price:
                ratios.pb_ratio = current_price / book_value_per_share

        # EV/EBITDA
        if financials.ebitda and financials.ebitda > 0:
            if market_cap and financials.total_debt:
                ev = market_cap + financials.total_debt - (financials.cash or 0)
                ratios.ev_ebitda = ev / financials.ebitda

        # ROE
        if financials.net_income and financials.equity and financials.equity > 0:
            ratios.roe = financials.net_income / financials.equity

        # ROA
        # Would need total assets - not extracted currently

        # Debt/Equity
        if financials.total_debt and financials.equity and financials.equity > 0:
            ratios.debt_equity = financials.total_debt / financials.equity

        # Net Margin (simplified - would need revenue)
        if financials.net_income and financials.revenue and financials.revenue > 0:
            ratios.net_margin = financials.net_income / financials.revenue

        return ratios

    def _compute_peer_percentiles(
        self,
        ticker: str,
        ratios: FundamentalRatios,
        peer_ratios: list[dict[str, Any]],
    ) -> PeerPercentiles | None:
        """
        Compute peer percentiles for key ratios.

        Returns None if insufficient peer data (< 5 peers).
        """
        if len(peer_ratios) < settings.peer_min_count:
            return None

        percentiles = PeerPercentiles()

        # Collect P/E ratios
        pe_ratios = [(p.get("pe_ratio"), p.get("ticker")) for p in peer_ratios]
        pe_ratios = [(r, t) for r, t in pe_ratios if r is not None]

        if ratios.pe_ratio is not None and pe_ratios:
            sorted_pe = sorted([r for r, _ in pe_ratios])
            rank = sum(1 for r in sorted_pe if r < ratios.pe_ratio)
            percentiles.pe_percentile = rank / len(sorted_pe)

        # Collect P/B ratios
        pb_ratios = [(p.get("pb_ratio"), p.get("ticker")) for p in peer_ratios]
        pb_ratios = [(r, t) for r, t in pb_ratios if r is not None]

        if ratios.pb_ratio is not None and pb_ratios:
            sorted_pb = sorted([r for r, _ in pb_ratios])
            rank = sum(1 for r in sorted_pb if r < ratios.pb_ratio)
            percentiles.pb_percentile = rank / len(sorted_pb)

        # Collect ROE
        roe_ratios = [(p.get("roe"), p.get("ticker")) for p in peer_ratios]
        roe_ratios = [(r, t) for r, t in roe_ratios if r is not None]

        if ratios.roe is not None and roe_ratios:
            sorted_roe = sorted([r for r, _ in roe_ratios])
            rank = sum(1 for r in sorted_roe if r < ratios.roe)
            percentiles.roe_percentile = rank / len(sorted_roe)

        return percentiles

    async def _insert_analysis(
        self, result: FundamentalAnalysisResult
    ) -> None:
        """Insert analysis result into PostgreSQL."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analysis.fundamental_analyses (
                    analysis_id, ticker, kap_publishing_id, direction, strength,
                    confidence, data_completeness, peer_count,
                    extracted_financials, ratios, peer_percentiles,
                    reasoning, source_citations, analysis_timestamp
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (kap_publishing_id) DO UPDATE SET
                    direction = EXCLUDED.direction,
                    strength = EXCLUDED.strength,
                    confidence = EXCLUDED.confidence
                """,
                result.analysis_timestamp.isoformat() + "_" + result.ticker,
                result.ticker,
                result.kap_publishing_id,
                result.direction.value,
                result.strength,
                result.confidence,
                result.data_completeness.value,
                result.peer_count,
                json.dumps(result.extracted_financials.model_dump()),
                json.dumps(result.ratios.model_dump()),
                json.dumps(result.peer_percentiles.model_dump()) if result.peer_percentiles else None,
                result.reasoning,
                json.dumps([s.model_dump() for s in result.source_citations]),
                result.analysis_timestamp,
            )

    async def _emit_complete_event(
        self, result: FundamentalAnalysisResult
    ) -> None:
        """Emit analysis complete event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")

        event = {
            "event_type": "analysis.fundamental.complete",
            "ticker": result.ticker,
            "kap_publishing_id": result.kap_publishing_id,
            "direction": result.direction.value,
            "confidence": result.confidence,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._redis.publish("analysis.fundamental.complete", str(event))

    async def analyze_kap(
        self,
        publishing_id: str,
        title: str,
        category: str,
        tickers: list[str],
    ) -> FundamentalAnalysisResult | None:
        """
        Analyze a KAP disclosure.

        Args:
            publishing_id: KAP publishing ID
            title: Disclosure title
            category: KAP category
            tickers: List of tickers mentioned in disclosure

        Returns:
            FundamentalAnalysisResult or None if skipped/failed
        """
        # Check idempotency
        idempotency_key = self._check_idempotency(publishing_id)
        if await self._is_duplicate(idempotency_key):
            logger.info("skipping_duplicate", publishing_id=publishing_id)
            return None

        # Only process earnings-related disclosures
        if category not in self.EARNINGS_CATEGORIES:
            logger.info(
                "skipping_non_earnings_category",
                publishing_id=publishing_id,
                category=category,
            )
            await self._mark_processed(idempotency_key)
            return None

        if not tickers:
            logger.info("no_tickers_found", publishing_id=publishing_id)
            await self._mark_processed(idempotency_key)
            return None

        # Fetch disclosure body
        disclosure = await self._fetch_kap_disclosure(publishing_id)
        if not disclosure:
            logger.warning("disclosure_not_found", publishing_id=publishing_id)
            return None

        body = disclosure.get("body", "") or disclosure.get("summary", "")
        if not body:
            logger.warning("empty_disclosure_body", publishing_id=publishing_id)
            await self._mark_processed(idempotency_key)
            return None

        # Use first ticker for analysis
        ticker = tickers[0]

        # Fetch market data for ratio computation
        current_price = await self._fetch_ticker_price(ticker)

        # Call LLM for extraction
        try:
            llm_result = await self._llm_client.analyze(
                ticker=ticker,
                publishing_id=publishing_id,
                title=title,
                body=body,
                current_price=current_price,
            )
        except Exception as e:
            logger.error("llm_analysis_failed", publishing_id=publishing_id, error=str(e))
            # Return insufficient evidence result
            return FundamentalAnalysisResult(
                ticker=ticker,
                kap_publishing_id=publishing_id,
                direction=Direction.NEUTRAL,
                strength=0.0,
                confidence=0.0,
                extracted_financials=ExtractedFinancials(),
                reasoning="LLM analysis failed",
                data_completeness=DataCompleteness.MISSING,
            )

        # Parse LLM response
        extracted = llm_result.get("extracted_financials", {})
        meta = llm_result.get("_meta", {})

        financials = ExtractedFinancials(
            revenue=extracted.get("revenue"),
            ebitda=extracted.get("ebitda"),
            net_income=extracted.get("net_income"),
            total_debt=extracted.get("total_debt"),
            cash=extracted.get("cash"),
            equity=extracted.get("equity"),
            eps=extracted.get("eps"),
        )

        # Parse source citations
        citations = []
        for cit in llm_result.get("source_citations", []):
            citations.append(
                SourceCitation(
                    field=cit.get("field", ""),
                    kap_id=cit.get("kap_id", publishing_id),
                    line_no=cit.get("line_no", 0),
                )
            )

        # Compute ratios
        ratios = self._compute_ratios(financials, None, current_price)

        # Fetch peer data and compute percentiles
        peers = await self._fetch_peer_set(ticker)
        peer_ratios = await self._fetch_peer_ratios(peers)
        peer_percentiles = self._compute_peer_percentiles(ticker, ratios, peer_ratios)

        # Build result
        result = FundamentalAnalysisResult(
            ticker=ticker,
            kap_publishing_id=publishing_id,
            direction=Direction(llm_result.get("direction", "NEUTRAL")),
            strength=float(llm_result.get("strength", 0.0)),
            confidence=float(llm_result.get("confidence", 0.0)),
            extracted_financials=financials,
            ratios=ratios,
            peer_percentiles=peer_percentiles,
            peer_count=len(peers),
            reasoning=llm_result.get("reasoning", ""),
            data_completeness=DataCompleteness(llm_result.get("data_completeness", "partial")),
            source_citations=citations,
            llm_tokens_in=meta.get("tokens_in"),
            llm_tokens_out=meta.get("tokens_out"),
            cost_usd=meta.get("cost_usd"),
        )

        # Insert into database
        try:
            await self._insert_analysis(result)
        except Exception as e:
            logger.error("db_insert_failed", publishing_id=publishing_id, error=str(e))

        # Emit complete event
        try:
            await self._emit_complete_event(result)
        except Exception as e:
            logger.error("redis_publish_failed", publishing_id=publishing_id, error=str(e))

        # Mark as processed
        await self._mark_processed(idempotency_key)

        logger.info(
            "fundamental_analysis_complete",
            ticker=ticker,
            direction=result.direction.value,
            confidence=result.confidence,
        )

        return result

    async def run(self) -> None:
        """Run the service (listen for Redis events)."""
        await self.initialize()
        logger.info("fundamental_analysis_service_started")

        if not self._redis:
            raise RuntimeError("Redis not initialized")

        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe("raw.kap.material")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    data = json.loads(message["data"])
                    event_type = data.get("event_type", "")

                    if event_type == "raw.kap.material":
                        await self.analyze_kap(
                            publishing_id=data["publishing_id"],
                            title=data["title"],
                            category=data["category"],
                            tickers=data["tickers"],
                        )
                except json.JSONDecodeError:
                    logger.error("invalid_json_message", data=message["data"])
                except Exception as e:
                    logger.error("event_processing_error", error=str(e))
        finally:
            await self.close()
