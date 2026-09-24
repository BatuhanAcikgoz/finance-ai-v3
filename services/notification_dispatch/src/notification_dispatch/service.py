"""Notification Dispatch main service logic."""
import hashlib
from datetime import UTC, datetime
from typing import Any

import asyncpg
import httpx
import structlog
from redis.asyncio import Redis

from notification_dispatch.config import settings

logger = structlog.get_logger(__name__)


class NotificationDispatchService:
    """Service for dispatching notifications to various channels."""

    def __init__(self) -> None:
        """Initialize notification dispatch service."""
        self._redis: Redis | None = None
        self._pool: asyncpg.Pool | None = None
        self._http_client = httpx.AsyncClient()

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
        await self._http_client.aclose()

    def _compute_dedup_hash(
        self, event_type: str, ticker: str | None, window_start: str
    ) -> str:
        """Compute deduplication hash for notification."""
        key_parts = [event_type]
        if ticker:
            key_parts.append(ticker)
        key_parts.append(window_start)
        return hashlib.sha256(":".join(key_parts).encode()).hexdigest()[:16]

    async def _check_dedup(self, dedup_hash: str) -> bool:
        """Check if notification was already sent within window."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        return bool(await self._redis.exists(f"notif:dedup:{dedup_hash}"))

    async def _mark_sent(self, dedup_hash: str) -> None:
        """Mark notification as sent."""
        if not self._redis:
            raise RuntimeError("Redis not initialized")
        await self._redis.setex(
            f"notif:dedup:{dedup_hash}",
            settings.dedup_window_minutes * 60,
            "1",
        )

    async def _check_rate_limit(
        self, ticker: str, severity: str
    ) -> tuple[bool, str]:
        """
        Check if rate limit would be exceeded.

        Returns:
            Tuple of (allowed, reason)
        """
        if severity not in ("CRITICAL", "EMERGENCY"):
            return True, ""

        if not self._redis:
            return True, ""

        # Check rate limit key
        key = f"notif:rate:{ticker}:{datetime.now(UTC).date().isoformat()}"
        count = await self._redis.get(key)
        current_count = int(count) if count else 0

        if current_count >= settings.max_critical_per_ticker_per_day:
            return False, f"Rate limit exceeded: {current_count}/{settings.max_critical_per_ticker_per_day}"

        # Increment counter
        await self._redis.incr(key)
        if current_count == 0:
            # Set expiry to end of day
            await self._redis.expire(key, 86400)

        return True, ""

    async def dispatch(
        self,
        event_type: str,
        payload: dict[str, Any],
        channels: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Dispatch notification to configured channels.

        Args:
            event_type: Type of event (e.g., decision.created, report.generated)
            payload: Event payload
            channels: List of channels to use (email, slack, ws). If None, use defaults.

        Returns:
            Dispatch result with channel statuses
        """
        if channels is None:
            channels = ["email"]  # Default to email

        ticker = payload.get("ticker", "")
        severity = payload.get("severity", "INFO")

        # Compute dedup hash
        window_start = datetime.now(UTC).strftime("%Y-%m-%dT%H:00:00")
        dedup_hash = self._compute_dedup_hash(event_type, ticker, window_start)

        # Check deduplication
        if await self._check_dedup(dedup_hash):
            logger.info("notification_suppressed_dedup", event_type=event_type, ticker=ticker)
            return {"status": "suppressed", "reason": "dedup", "channels": {}}

        # Check rate limit
        allowed, reason = await self._check_rate_limit(ticker, severity)
        if not allowed:
            logger.info("notification_suppressed_rate_limit", ticker=ticker, reason=reason)
            return {"status": "suppressed", "reason": "rate_limit", "channels": {}}

        # Dispatch to channels
        results: dict[str, Any] = {}
        for channel in channels:
            if channel == "email":
                results["email"] = await self._send_email(event_type, payload)
            elif channel == "slack":
                results["slack"] = await self._send_slack(event_type, payload)
            elif channel == "ws":
                results["ws"] = await self._send_websocket(event_type, payload)

        # Mark as sent
        await self._mark_sent(dedup_hash)

        # Log delivery
        await self._log_delivery(event_type, payload, results)

        logger.info(
            "notification_dispatched",
            event_type=event_type,
            ticker=ticker,
            channels=list(results.keys()),
        )

        return {"status": "sent", "channels": results}

    async def _send_email(
        self, event_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Send email notification via SendGrid."""
        if not settings.sendgrid_api_key:
            return {"status": "skipped", "reason": "no_api_key"}

        try:
            # Get recipient from payload or database
            to_email = payload.get("email", "user@example.com")

            # Build email content
            subject = f"Finance AI V3 - {event_type.replace('.', ' ').title()}"
            if "ticker" in payload:
                subject = f"[{payload['ticker']}] {subject}"

            # Prepare SendGrid payload
            sendgrid_payload = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {
                    "email": settings.sendgrid_from_email,
                    "name": settings.sendgrid_from_name,
                },
                "subject": subject,
                "content": [
                    {
                        "type": "text/html",
                        "value": self._build_email_body(event_type, payload),
                    }
                ],
            }

            response = await self._http_client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=sendgrid_payload,
                headers={
                    "Authorization": f"Bearer {settings.sendgrid_api_key}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code in (200, 201, 202):
                return {"status": "sent"}
            else:
                return {"status": "failed", "error": response.text}

        except Exception as e:
            logger.error("email_send_failed", error=str(e))
            return {"status": "failed", "error": str(e)}

    def _build_email_body(self, event_type: str, payload: dict[str, Any]) -> str:
        """Build HTML email body."""
        ticker = payload.get("ticker", "N/A")
        message = payload.get("message", payload.get("title", ""))

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{event_type}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Finance AI V3 Bildirimi</h2>
            <p><strong>Olay:</strong> {event_type}</p>
            <p><strong>Hisse:</strong> {ticker}</p>
            <p><strong>Mesaj:</strong> {message}</p>
            <hr>
            <p style="font-size: 12px; color: #666;">
                Bu otomatik bir bildirimdir. Yanıtlamayın.
            </p>
        </body>
        </html>
        """

    async def _send_slack(
        self, event_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Send Slack notification."""
        if not settings.slack_webhook_url:
            return {"status": "skipped", "reason": "no_webhook"}

        # Only send CRITICAL and EMERGENCY to Slack
        severity = payload.get("severity", "INFO")
        if severity not in ("CRITICAL", "EMERGENCY"):
            return {"status": "skipped", "reason": "severity"}

        try:
            ticker = payload.get("ticker", "N/A")
            message = payload.get("message", payload.get("title", ""))

            slack_payload = {
                "text": f"*{event_type}*",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{ticker}* - {message}",
                        },
                    }
                ],
            }

            response = await self._http_client.post(
                settings.slack_webhook_url,
                json=slack_payload,
            )

            if response.status_code == 200:
                return {"status": "sent"}
            else:
                return {"status": "failed", "error": response.text}

        except Exception as e:
            logger.error("slack_send_failed", error=str(e))
            return {"status": "failed", "error": str(e)}

    async def _send_websocket(
        self, event_type: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Send WebSocket push to dashboard."""
        # In production, this would push to connected WebSocket clients
        # For now, this is a placeholder
        logger.info("websocket_push", event_type=event_type, payload=payload)
        return {"status": "sent"}

    async def _log_delivery(
        self, event_type: str, payload: dict[str, Any], results: dict[str, Any]
    ) -> None:
        """Log notification delivery to database."""
        if not self._pool:
            return

        import uuid

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO notifications.deliveries (
                    delivery_id, event_type, ticker, severity,
                    channel_results, payload, delivered_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                str(uuid.uuid4()),
                event_type,
                payload.get("ticker"),
                payload.get("severity", "INFO"),
                str(results),
                str(payload),
                datetime.now(UTC).isoformat(),
            )
