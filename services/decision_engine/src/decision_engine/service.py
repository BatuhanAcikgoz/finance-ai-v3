"""Decision Engine main service logic."""
import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import asyncpg
import structlog
from redis.asyncio import Redis

from decision_engine.config import settings
from decision_engine.models import (
    Action,
    AggregatedEvidence,
    ComplianceStatus,
    DataCompleteness,
    DecisionFactors,
    DecisionRecord,
    Evidence,
    EvidenceStream,
    EvidenceWeights,
    MarketContext,
    MarketRegime,
    PortfolioContext,
    Signal,
    TechnicalIndicators,
    Urgency,
)

logger = structlog.get_logger(__name__)

# Default evidence weights
DEFAULT_WEIGHTS = EvidenceWeights()


class DecisionEngineService:
    """Service for aggregating evidence into trading decisions."""

    def __init__(self) -> None:
        """Initialize decision engine service."""
        self._redis: Redis | None = None
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Initialize Redis and database connections."""
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self._pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)

    async def close(self) -> None:
        """Close all connections."""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.close()

    def _check_idempotency(self, portfolio_id: str, ticker: str) -> str:
        """Generate idempotency key for decision."""
        key = f"{portfolio_id}:{ticker}"
        return f"decision:{hashlib.sha256(key.encode()).hexdigest()[:16]}"

    async def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if this decision was already made."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return await self._redis.exists(idempotency_key) > 0

    async def _mark_processed(self, idempotency_key: str) -> None:
        """Mark decision as processed in Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(idempotency_key, settings.idempotency_key_ttl_seconds, "1")

    async def _fetch_latest_analysis(self, ticker: str) -> dict[str, Any] | None:
        """Fetch latest analysis results for a ticker from all streams."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            # Fetch latest technical analysis
            technical = await conn.fetchrow(
                """
                SELECT signal, confidence, metadata
                FROM analysis.technical_indicators
                WHERE ticker = $1
                ORDER BY analyzed_at DESC
                LIMIT 1
                """,
                ticker,
            )

            # Fetch latest fundamental analysis
            fundamental = await conn.fetchrow(
                """
                SELECT signal, confidence, recommendation
                FROM analysis.fundamental_analyses
                WHERE ticker = $1
                ORDER BY analyzed_at DESC
                LIMIT 1
                """,
                ticker,
            )

            # Fetch latest sentiment
            sentiment = await conn.fetchrow(
                """
                SELECT sentiment, conviction
                FROM analysis.sentiment_analyses
                WHERE ticker = $1
                ORDER BY analyzed_at DESC
                LIMIT 1
                """,
                ticker,
            )

            # Fetch latest sector analysis
            sector = await conn.fetchrow(
                """
                SELECT signal, total_score
                FROM analysis.sector_analyses s
                JOIN market_data.constituents c ON c.sector_index = s.ticker
                WHERE c.ticker = $1
                ORDER BY s.analyzed_at DESC
                LIMIT 1
                """,
                ticker,
            )

            # Fetch latest news analysis
            news = await conn.fetchrow(
                """
                SELECT signal, confidence, relevance_score
                FROM analysis.news_analyses
                WHERE $1 = ANY(tickers)
                ORDER BY analyzed_at DESC
                LIMIT 1
                """,
                ticker,
            )

            return {
                "technical": dict(technical) if technical else None,
                "fundamental": dict(fundamental) if fundamental else None,
                "sentiment": dict(sentiment) if sentiment else None,
                "sector": dict(sector) if sector else None,
                "news": dict(news) if news else None,
            }

    async def _fetch_portfolio_state(self, portfolio_id: str, ticker: str) -> PortfolioContext | None:
        """Fetch current portfolio state for a ticker with full context."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    h.current_weight, 
                    h.kelly_fraction,
                    h.shares as quantity,
                    h.cost_basis_try,
                    h.current_price,
                    h.unrealized_pnl_try,
                    h.unrealized_pnl_pct,
                    h.acquired_at as position_open_date,
                    p.drift_pct,
                    p.consecutive_red_days,
                    p.market_crash
                FROM portfolio.holdings h
                JOIN portfolio.portfolios p ON p.portfolio_id = h.portfolio_id
                WHERE h.portfolio_id = $1 AND h.ticker = $2
                """,
                portfolio_id,
                ticker,
            )

            if not row:
                return None

            # Calculate unrealized P&L if not stored
            unrealized_pnl_pct = row.get("unrealized_pnl_pct") or 0.0
            if row.get("cost_basis_try") and row.get("current_price") and row.get("quantity"):
                cost_per_share = row["cost_basis_try"] / row["quantity"] if row["quantity"] > 0 else 0
                if cost_per_share > 0:
                    unrealized_pnl_pct = ((row["current_price"] - cost_per_share) / cost_per_share) * 100

            return PortfolioContext(
                current_weight=row["current_weight"] or 0.0,
                post_trade_weight=row["current_weight"] or 0.0,
                kelly_fraction=row["kelly_fraction"] or 0.25,
                drift_pct=row.get("drift_pct") or 0.0,
                avg_cost=row["cost_basis_try"] / row["quantity"] if row.get("quantity", 0) > 0 else 0.0,
                current_price=row.get("current_price") or 0.0,
                unrealized_pnl_try=row.get("unrealized_pnl_try") or 0.0,
                unrealized_pnl_pct=unrealized_pnl_pct,
                quantity=row.get("quantity") or 0,
                consecutive_red_days=row.get("consecutive_red_days") or 0,
                market_crash=row.get("market_crash") or False,
                sector_exposure=0.0,  # Will be computed separately
                position_open_date=str(row["position_open_date"]) if row.get("position_open_date") else None,
                last_price_update=datetime.now(UTC).isoformat(),
            )

    def _aggregate_evidence(self, evidence: list[Evidence]) -> AggregatedEvidence:
        """Aggregate evidence from multiple streams into a single signal."""
        if len(evidence) < settings.min_evidence_count:
            return AggregatedEvidence(
                weighted_signal=0.0,
                evidence_count=len(evidence),
                contradiction_score=0.0,
                insufficient=True,
            )

        # Signal mapping
        signal_map = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}

        # Weight mapping
        weights = DEFAULT_WEIGHTS.to_dict()

        # Weighted signal calculation
        weighted_signal = 0.0
        total_weight_used = 0.0

        for e in evidence:
            stream_key = e.stream.value
            weight = weights.get(stream_key, 0.0)
            signal_value = signal_map[e.signal.value]
            contribution = weight * signal_value * e.strength * e.confidence
            weighted_signal += contribution
            total_weight_used += weight

        # Normalize by total weight used
        if total_weight_used > 0:
            weighted_signal /= total_weight_used

        # Contradiction score (variance of signals)
        signals = [signal_map[e.signal.value] * e.strength for e in evidence]
        if len(signals) > 1:
            mean_signal = sum(signals) / len(signals)
            variance = sum((s - mean_signal) ** 2 for s in signals) / len(signals)
            contradiction_score = float(min(1.0, variance))
        else:
            contradiction_score = 0.0

        return AggregatedEvidence(
            weighted_signal=float(weighted_signal),
            evidence_count=len(evidence),
            contradiction_score=contradiction_score,
            insufficient=False,
        )

    def _compute_confidence(self, aggregated: AggregatedEvidence) -> float:
        """Compute decision confidence based on aggregated evidence."""
        if aggregated.insufficient:
            return 0.0

        # Base confidence from evidence count
        evidence_factor = min(1.0, aggregated.evidence_count / 5.0)  # 5 streams = max

        # Signal strength factor
        signal_factor = abs(aggregated.weighted_signal)

        # Consistency factor (inverse of contradiction)
        consistency_factor = 1.0 - aggregated.contradiction_score

        # Combined confidence
        confidence = (evidence_factor * 0.4 + signal_factor * 0.4 + consistency_factor * 0.2)

        return float(max(0.0, min(1.0, confidence)))

    def _determine_action(
        self, 
        confidence: float, 
        weighted_signal: float, 
        portfolio_context: PortfolioContext,
        technical_indicators: TechnicalIndicators | None = None,
        market_context: MarketContext | None = None,
    ) -> tuple[Action, Urgency, str]:
        """
        Determine trading action using multi-variable analysis.
        
        This is the SMART decision logic that considers:
        - Evidence-based signal
        - User's position (avg_cost, unrealized_pnl)
        - Technical indicators (RSI, MACD, etc.)
        - Market regime
        - Risk management rules
        """
        _urgency = Urgency.MEDIUM  # default; overridden below
        if confidence < settings.confidence_threshold:
            return Action.INSUFFICIENT_EVIDENCE, Urgency.LOW, "Yetersiz kanıt"

        # 2. STOP-LOSS CHECK (HIGHEST PRIORITY)
        stop_result = self._check_stop_loss(portfolio_context)
        if stop_result[0]:
            action, _, _, reason = stop_result
            return action, Urgency.CRITICAL, reason

        # 3. TAKE-PROFIT CHECK
        take_profit_result = self._check_take_profit(portfolio_context, weighted_signal)
        if take_profit_result[0]:
            action, _, _, reason = take_profit_result
            return action, Urgency.HIGH, reason

        # 4. COMPUTE DECISION FACTORS
        factors = self._compute_decision_factors(
            weighted_signal, confidence, portfolio_context, technical_indicators, market_context
        )

        # 5. DETERMINE ACTION BASED ON MULTI-VARIABLE ANALYSIS
        has_position = portfolio_context.current_weight > 0.05
        unrealized_pnl_pct = portfolio_context.unrealized_pnl_pct
        
        # Position-aware decision making
        if has_position:
            # SELL/REDUCE logic for existing positions
            if factors.signal_score > 0.5 and factors.momentum_score > 0.3:
                # Strong bullish + momentum = hold or take profit
                if unrealized_pnl_pct > 15:
                    return Action.TAKE_PROFIT, Urgency.HIGH, f"Kar realizasyonu: %{unrealized_pnl_pct:.1f}"
                elif unrealized_pnl_pct > 5:
                    return Action.HOLD, Urgency.MEDIUM, f"Kardayız beklet: %{unrealized_pnl_pct:.1f}"
            
            elif factors.signal_score < -0.3:
                # Negative signal = reduce or sell
                if unrealized_pnl_pct > 10:
                    return Action.SELL, Urgency.MEDIUM, "Kar realizasyonu: güçlü satış sinyali"
                elif unrealized_pnl_pct > 0:
                    return Action.REDUCE, Urgency.MEDIUM, f"Zararda değilken azalt: %{unrealized_pnl_pct:.1f}"
                elif unrealized_pnl_pct > -5:
                    return Action.HOLD, Urgency.LOW, "Pozisyondayız ancak sinyal zayıf"
                else:
                    return Action.SELL, Urgency.HIGH, f"Zarardayken satış sinyali: %{unrealized_pnl_pct:.1f}"
        
        # NO POSITION - BUY logic
        else:
            if factors.signal_score > 0.4 and confidence > 0.65:
                # Check if price is reasonable (not at resistance)
                if technical_indicators and technical_indicators.rsi < 70:
                    return Action.BUY, Urgency.MEDIUM, f"Giriş sinyali: sinyal={factors.signal_score:.2f}"
            
            elif factors.signal_score > 0.6 and confidence > 0.75:
                # Strong signal = aggressive buy
                return Action.BUY, Urgency.HIGH, f"Güçlü giriş: sinyal={factors.signal_score:.2f}"
        
        # DEFAULT: HOLD
        return Action.HOLD, Urgency.LOW, f"Sinyal nötr: %{weighted_signal:.2f}"

    def _check_stop_loss(
        self, portfolio_context: PortfolioContext
    ) -> tuple[bool, Action, Urgency, str]:
        """
        Check if stop-loss should be triggered.
        Returns (triggered, action, urgency, reason)
        """
        unrealized_pnl_pct = portfolio_context.unrealized_pnl_pct
        consecutive_red_days = portfolio_context.consecutive_red_days
        market_crash = portfolio_context.market_crash
        
        # Hard stop-loss: -10% loss
        if unrealized_pnl_pct < -10:
            return (True, Action.STOP_LOSS, Urgency.CRITICAL, 
                    f"Stop-loss tetiklendi: %{unrealized_pnl_pct:.1f}")
        
        # Technical breakdown: -7% loss + consecutive red days
        if unrealized_pnl_pct < -7 and consecutive_red_days >= 3:
            return (True, Action.STOP_LOSS, Urgency.CRITICAL,
                    f"Teknik kırılma: %{unrealized_pnl_pct:.1f} + {consecutive_red_days} düşüş günü")
        
        # Market crash protection: -5% loss in crash market
        if market_crash and unrealized_pnl_pct < -5:
            return (True, Action.SELL, Urgency.HIGH,
                    f"Piyasa çöküşü koruması: %{unrealized_pnl_pct:.1f}")
        
        # Trailing stop: -5% loss
        if unrealized_pnl_pct < -5:
            return (True, Action.REDUCE, Urgency.MEDIUM,
                    f"Tailing stop: %{unrealized_pnl_pct:.1f}")
        
        return (False, Action.HOLD, Urgency.LOW, "")

    def _check_take_profit(
        self, portfolio_context: PortfolioContext, weighted_signal: float
    ) -> tuple[bool, Action, Urgency, str]:
        """
        Check if take-profit should be triggered.
        """
        unrealized_pnl_pct = portfolio_context.unrealized_pnl_pct
        
        # Large profit + negative signal = take profit
        if unrealized_pnl_pct > 20 and weighted_signal < -0.2:
            return (True, Action.TAKE_PROFIT, Urgency.HIGH,
                    f"Kar al: %{unrealized_pnl_pct:.1f} + zayıf sinyal")
        
        # Very large profit: 25%+
        if unrealized_pnl_pct > 25:
            return (True, Action.TAKE_PROFIT, Urgency.HIGH,
                    f"Yüksek kar realizasyonu: %{unrealized_pnl_pct:.1f}")
        
        # Moderate profit + overbought
        if unrealized_pnl_pct > 15 and weighted_signal < -0.3:
            return (True, Action.TAKE_PROFIT, Urgency.MEDIUM,
                    f"Kar al (aşırı alım): %{unrealized_pnl_pct:.1f}")
        
        return (False, Action.HOLD, Urgency.LOW, "")

    def _compute_decision_factors(
        self,
        weighted_signal: float,
        confidence: float,
        portfolio_context: PortfolioContext,
        technical_indicators: TechnicalIndicators | None,
        market_context: MarketContext | None,
    ) -> DecisionFactors:
        """
        Compute multi-variable decision factors for comprehensive analysis.
        """
        # Base signal score from evidence
        signal_score = weighted_signal
        
        # Risk score based on position and market conditions
        risk_score = 0.0
        if portfolio_context.current_weight > 0.20:
            risk_score += 0.3  # High concentration risk
        if abs(portfolio_context.unrealized_pnl_pct) > 10:
            risk_score += 0.2  # High P&L volatility
        if portfolio_context.market_crash:
            risk_score += 0.3
        risk_score = min(risk_score, 1.0)
        
        # Momentum score from technical indicators
        momentum_score = 0.0
        if technical_indicators:
            # RSI momentum: oversold = positive, overbought = negative
            if technical_indicators.rsi < 30:
                momentum_score += 0.4
            elif technical_indicators.rsi < 40:
                momentum_score += 0.2
            elif technical_indicators.rsi > 70:
                momentum_score -= 0.4
            elif technical_indicators.rsi > 60:
                momentum_score -= 0.2
            
            # MACD histogram
            momentum_score += technical_indicators.macd_histogram * 0.3
            
            # ADX trend strength
            if technical_indicators.adx > 25:
                if momentum_score > 0:
                    momentum_score += 0.1  # Strong uptrend confirmation
        
        # Value score based on avg_cost vs current price
        value_score = 0.5
        if portfolio_context.avg_cost > 0 and portfolio_context.current_price > 0:
            cost_vs_current = (portfolio_context.current_price - portfolio_context.avg_cost) / portfolio_context.avg_cost
            if cost_vs_current < -0.1:
                value_score = 0.8  # Underwater = potential value
            elif cost_vs_current > 0.1:
                value_score = 0.3  # In profit = less value opportunity
        
        # Sentiment score (placeholder - would come from sentiment analysis)
        sentiment_score = weighted_signal * 0.5
        
        # Regime score based on market conditions
        regime_score = 0.5
        if market_context:
            if market_context.regime == MarketRegime.TREND_UP:
                if weighted_signal > 0:
                    regime_score = 0.8
                else:
                    regime_score = 0.4
            elif market_context.regime == MarketRegime.TREND_DOWN:
                if weighted_signal < 0:
                    regime_score = 0.8
                else:
                    regime_score = 0.3
            elif market_context.regime == MarketRegime.VOLATILE:
                regime_score = 0.2  # Reduce risk in volatile markets
            elif market_context.regime == MarketRegime.SIDEWAYS:
                regime_score = 0.5  # Neutral
        
        return DecisionFactors(
            signal_score=signal_score,
            risk_score=risk_score,
            momentum_score=momentum_score,
            value_score=value_score,
            sentiment_score=sentiment_score,
            regime_score=regime_score,
        )

    def _compute_stop_loss_price(
        self, portfolio_context: PortfolioContext, action: Action
    ) -> float | None:
        """Compute stop-loss price level."""
        if portfolio_context.current_price <= 0:
            return None
        
        if action == Action.STOP_LOSS:
            return portfolio_context.current_price * (1 - settings.stop_loss_pct)
        elif action == Action.REDUCE:
            return portfolio_context.current_price * (1 - settings.stop_loss_pct * 0.5)
        
        return None

    def _compute_take_profit_price(
        self, portfolio_context: PortfolioContext
    ) -> float | None:
        """Compute take-profit price level."""
        if portfolio_context.current_price <= 0:
            return None
        
        return portfolio_context.current_price * (1 + settings.take_profit_pct)

    def _compute_position_size(
        self, action: Action, confidence: float, kelly_fraction: float, current_weight: float
    ) -> float:
        """Compute position size after trade."""
        if action in (Action.INSUFFICIENT_EVIDENCE, Action.HOLD):
            return current_weight

        # Use Kelly fraction scaled by confidence
        effective_kelly = kelly_fraction * confidence

        if action == Action.BUY:
            new_weight = min(current_weight + effective_kelly, 0.25)  # Max 25%
        elif action == Action.SELL:
            new_weight = max(current_weight - effective_kelly, 0.0)
        elif action == Action.REDUCE:
            new_weight = max(current_weight - effective_kelly * 0.5, 0.0)
        else:
            new_weight = current_weight

        return new_weight

    async def _insert_decision(self, decision: DecisionRecord) -> None:
        """Insert decision record into PostgreSQL."""
        if not self._pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO decision.decisions
                (decision_id, portfolio_id, ticker, action, confidence, position_size_pct,
                 evidence_count, contradiction_score, supervisor_reasoning, compliance_status,
                 effective_at, created_at, data_completeness, disclaimer_tr, prompt_versions)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                ON CONFLICT (portfolio_id, ticker, effective_at::date) DO UPDATE SET
                    action = EXCLUDED.action,
                    confidence = EXCLUDED.confidence,
                    position_size_pct = EXCLUDED.position_size_pct
                """,
                decision.decision_id,
                decision.portfolio_id,
                decision.ticker,
                decision.action.value,
                decision.confidence,
                decision.position_size_pct,
                decision.evidence_count,
                decision.contradiction_score,
                decision.supervisor_reasoning,
                decision.compliance_status.value,
                decision.effective_at,
                decision.created_at,
                decision.data_completeness.value,
                decision.disclaimer_tr,
                decision.prompt_versions,
            )

    async def _emit_decision_event(self, decision: DecisionRecord) -> None:
        """Emit decision event to Redis."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")

        event = {
            "event_type": "decision.made",
            "decision_id": decision.decision_id,
            "portfolio_id": decision.portfolio_id,
            "ticker": decision.ticker,
            "action": decision.action.value,
            "confidence": decision.confidence,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self._redis.publish("decision.made", json.dumps(event))

    async def make_decision(
        self, portfolio_id: str, ticker: str, evidence: list[Evidence] | None = None
    ) -> tuple[DecisionRecord, AggregatedEvidence]:
        """
        Make a trading decision for a ticker in a portfolio.

        Args:
            portfolio_id: Portfolio identifier
            ticker: Ticker symbol
            evidence: Optional explicit evidence (if None, fetches from database)

        Returns:
            Tuple of (DecisionRecord, AggregatedEvidence)
        """
        idempotency_key = self._check_idempotency(portfolio_id, ticker)

        if await self._is_duplicate(idempotency_key):
            logger.info("decision_already_made", portfolio_id=portfolio_id, ticker=ticker)
            # Return cached decision from Redis
            cached = await self._redis.get(f"decision:result:{idempotency_key}")
            if cached:
                data = json.loads(cached)
                return DecisionRecord(**data["decision"]), AggregatedEvidence(**data["aggregated"])

        await self.initialize()

        try:
            # Fetch evidence if not provided
            if evidence is None:
                analyses = await self._fetch_latest_analysis(ticker)
                evidence = []

                # Convert technical analysis to evidence
                if analyses.get("technical"):
                    tech = analyses["technical"]
                    evidence.append(Evidence(
                        stream=EvidenceStream.TECHNICAL,
                        signal=Signal(tech["signal"].upper()) if tech["signal"] else Signal.NEUTRAL,
                        strength=tech.get("strength", 0.5),
                        confidence=tech.get("confidence", 0.5),
                        source_id=f"tech_{ticker}",
                    ))

                # Convert fundamental analysis to evidence
                if analyses.get("fundamental"):
                    fund = analyses["fundamental"]
                    evidence.append(Evidence(
                        stream=EvidenceStream.FUNDAMENTAL,
                        signal=Signal(fund["recommendation"].upper()) if fund["recommendation"] else Signal.NEUTRAL,
                        strength=fund.get("strength", 0.5),
                        confidence=fund.get("confidence", 0.5),
                        source_id=f"fund_{ticker}",
                    ))

                # Convert sentiment to evidence
                if analyses.get("sentiment"):
                    sent = analyses["sentiment"]
                    sentiment_signal = Signal.BULLISH if sent["sentiment"] > 0.2 else (Signal.BEARISH if sent["sentiment"] < -0.2 else Signal.NEUTRAL)
                    evidence.append(Evidence(
                        stream=EvidenceStream.SENTIMENT,
                        signal=sentiment_signal,
                        strength=abs(sent["sentiment"]),
                        confidence=sent["conviction"],
                        source_id=f"sent_{ticker}",
                    ))

                # Convert sector analysis to evidence
                if analyses.get("sector"):
                    sec = analyses["sector"]
                    evidence.append(Evidence(
                        stream=EvidenceStream.SECTOR,
                        signal=Signal(sec["signal"].upper()) if sec["signal"] else Signal.NEUTRAL,
                        strength=sec.get("total_score", 0.5),
                        confidence=0.6,
                        source_id=f"sector_{ticker}",
                    ))

            # Aggregate evidence
            aggregated = self._aggregate_evidence(evidence)

            # Compute confidence
            confidence = self._compute_confidence(aggregated)

            # Get portfolio context with full details
            portfolio_context = await self._fetch_portfolio_state(portfolio_id, ticker)
            
            # Get technical indicators (placeholder - would come from technical analysis service)
            technical_indicators = await self._fetch_technical_indicators(ticker)
            
            # Get market context (placeholder - would come from market data)
            market_context = await self._fetch_market_context()
            
            # Determine action using new multi-variable logic
            action, urgency, reason = self._determine_action(
                confidence=confidence,
                weighted_signal=aggregated.weighted_signal,
                portfolio_context=portfolio_context,
                technical_indicators=technical_indicators,
                market_context=market_context,
            )

            # Compute position size
            kelly = portfolio_context.kelly_fraction if portfolio_context else 0.25
            current_weight = portfolio_context.current_weight if portfolio_context else 0.0
            position_size = self._compute_position_size(action, confidence, kelly, current_weight)

            # Compute decision factors for transparency
            decision_factors = self._compute_decision_factors(
                weighted_signal=aggregated.weighted_signal,
                confidence=confidence,
                portfolio_context=portfolio_context,
                technical_indicators=technical_indicators,
                market_context=market_context,
            )

            # Compute stop-loss and take-profit levels
            stop_loss_price = self._compute_stop_loss_price(portfolio_context, action)
            take_profit_price = self._compute_take_profit_price(portfolio_context)

            # Build enhanced decision record
            decision = DecisionRecord(
                decision_id=str(uuid4()),
                portfolio_id=portfolio_id,
                ticker=ticker,
                action=action,
                urgency=urgency,
                confidence=confidence,
                position_size_pct=position_size,
                evidence=evidence,
                evidence_count=len(evidence),
                contradiction_score=aggregated.contradiction_score,
                supervisor_reasoning=reason,
                portfolio_context=portfolio_context,
                technical_indicators=technical_indicators,
                market_context=market_context,
                decision_factors=decision_factors,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                compliance_status=ComplianceStatus.PENDING,
                effective_at=datetime.now(UTC).isoformat(),
                data_completeness=DataCompleteness.COMPLETE if len(evidence) >= 4 else DataCompleteness.PARTIAL,
            )

            # Insert decision
            await self._insert_decision(decision)

            # Emit event
            await self._emit_decision_event(decision)

            # Cache result
            if self._redis:
                cache_data = {
                    "decision": decision.model_dump(mode="json"),
                    "aggregated": aggregated.model_dump(),
                }
                await self._redis.setex(f"decision:result:{idempotency_key}", 3600, json.dumps(cache_data, default=str))

            await self._mark_processed(idempotency_key)

            logger.info(
                "decision_made",
                decision_id=decision.decision_id,
                ticker=ticker,
                action=action.value,
                confidence=confidence,
            )

            return decision, aggregated

        finally:
            await self.close()

    def _generate_reasoning(
        self, ticker: str, action: Action, confidence: float, aggregated: AggregatedEvidence, evidence: list[Evidence]
    ) -> str:
        """Generate human-readable reasoning for the decision."""
        signal_desc = "POZITIF" if aggregated.weighted_signal > 0.2 else ("NEGATIF" if aggregated.weighted_signal < -0.2 else "NÖTR")
        confidence_pct = int(confidence * 100)
        evidence_count = len(evidence)

        action_map = {
            Action.BUY: f"{ticker} için GÜÇLÜ ALım önerisi. Sinyal gücü: {signal_desc}.",
            Action.SELL: f"{ticker} için SATım önerisi. Sinyal gücü: {signal_desc}.",
            Action.REDUCE: f"{ticker} için AZALTım önerisi. Sinyal gücü: {signal_desc}.",
            Action.HOLD: f"{ticker} için BEKLE önerisi. Sinyal gücü: {signal_desc}.",
            Action.INSUFFICIENT_EVIDENCE: f"{ticker} için yetersiz kanıt. Daha fazla veri gerekli.",
        }

        base = action_map.get(action, f"{ticker} için {action.value} önerisi.")
        return f"{base} Güven: %{confidence_pct}, Kanıt sayısı: {evidence_count}, Çelişki skoru: {int(aggregated.contradiction_score * 100)}%."

    async def _fetch_technical_indicators(self, ticker: str) -> TechnicalIndicators | None:
        """Fetch latest technical indicators for a ticker."""
        if not self._pool:
            return None
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT rsi, macd, macd_signal, macd_hist,
                       sma_20, sma_50, sma_200,
                       bb_upper, bb_lower, atr, adx
                FROM analysis.technical_indicators
                WHERE ticker = $1
                ORDER BY computed_at DESC
                LIMIT 1
                """,
                ticker,
            )
            
            if not row:
                return None
            
            return TechnicalIndicators(
                rsi=row.get("rsi") or 50.0,
                macd=row.get("macd") or 0.0,
                macd_signal=row.get("macd_signal") or 0.0,
                macd_histogram=row.get("macd_hist") or 0.0,
                sma_20=row.get("sma_20") or 0.0,
                sma_50=row.get("sma_50") or 0.0,
                sma_200=row.get("sma_200") or 0.0,
                price_vs_sma_pct=0.0,  # Will be computed if sma_20 available
                bollinger_upper=row.get("bb_upper") or 0.0,
                bollinger_lower=row.get("bb_lower") or 0.0,
                volume_ratio=1.0,
                atr=row.get("atr") or 0.0,
                adx=row.get("adx") or 0.0,
            )

    async def _fetch_market_context(self) -> MarketContext | None:
        """Fetch market-wide context for regime detection."""
        if not self._pool:
            return None
        
        async with self._pool.acquire() as conn:
            # Get BIST-100 index
            index_row = await conn.fetchrow(
                """
                SELECT value, change_pct
                FROM market_data.index_values
                WHERE index_code = 'XU100'
                ORDER BY as_of DESC
                LIMIT 1
                """,
            )
            
            # Get USD/TRY
            usd_row = await conn.fetchrow(
                """
                SELECT close as usd_try, change_pct as usd_change
                FROM market_data.bars
                WHERE ticker = 'USDTRY'
                ORDER BY date DESC
                LIMIT 1
                """,
            )
            
            index_value = index_row["value"] if index_row else 0.0
            index_change = index_row["change_pct"] if index_row else 0.0
            usd_try = usd_row["usd_try"] if usd_row else 0.0
            usd_change = usd_row["usd_change"] if usd_row else 0.0
            
            # Detect market regime based on index
            regime = MarketRegime.UNKNOWN
            if abs(index_change) < 0.5:
                regime = MarketRegime.SIDEWAYS
            elif index_change > 1.5:
                regime = MarketRegime.TREND_UP
            elif index_change < -1.5:
                regime = MarketRegime.TREND_DOWN
            
            return MarketContext(
                index_value=index_value or 0.0,
                index_change_pct=index_change or 0.0,
                sector_index=0.0,
                sector_change_pct=0.0,
                regime=regime,
                volatility=abs(index_change) if index_change else 0.0,
                usd_try=usd_try or 0.0,
                usd_try_change=usd_change or 0.0,
            )

    def _is_report_time(self) -> bool:
        """Check if current time is a report time (morning or evening)."""
        now = datetime.now(UTC)
        trt_hour = (now.hour + 3) % 24  # TRT is UTC+3
        
        morning_time = settings.morning_report_hour
        evening_time = settings.evening_report_hour
        
        return trt_hour == morning_time or trt_hour == evening_time

    def _is_market_open(self) -> bool:
        """Check if BIST market is currently open."""
        now = datetime.now(UTC)
        trt_hour = (now.hour + 3) % 24  # TRT is UTC+3
        
        is_weekday = now.weekday() < 5  # Monday = 0, Friday = 4
        is_trading_hours = settings.bist_open_hour <= trt_hour < settings.bist_close_hour
        
        return is_weekday and is_trading_hours

    async def run(self) -> None:
        """Run the service with twice-daily reporting schedule."""
        logger.info("decision_engine_service_started", 
                    morning_hour=settings.morning_report_hour,
                    evening_hour=settings.evening_report_hour)
        
        last_report_date = None
        
        while True:
            import asyncio
            await asyncio.sleep(60)  # Check every minute
            
            now = datetime.now(UTC)
            trt_hour = (now.hour + 3) % 24
            today = now.date()
            
            # Check if it's report time and we haven't reported today
            should_report = False
            
            if settings.morning_report_hour <= trt_hour < settings.morning_report_hour + 1:
                if last_report_date != today:
                    should_report = True
                    last_report_date = today
                    logger.info("morning_report_triggered")
            
            elif settings.evening_report_hour <= trt_hour < settings.evening_report_hour + 1:
                if last_report_date != today:
                    should_report = True
                    last_report_date = today
                    logger.info("evening_report_triggered")
            
            if should_report:
                logger.info("running_decision_cycle", 
                          report_type="morning" if trt_hour < 14 else "evening")
                # In production, this would:
                # 1. Fetch all active portfolios
                # 2. For each portfolio's holdings, run make_decision()
                # 3. Emit reports to notification service
                # 4. Log decision metrics
