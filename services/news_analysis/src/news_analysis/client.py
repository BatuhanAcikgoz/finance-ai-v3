"""LLM client for News Analysis using LiteLLM."""
import json
from typing import Any

import structlog

from news_analysis.config import settings

logger = structlog.get_logger(__name__)


class LiteLLMClient:
    """Client for calling LLM via LiteLLM for news analysis."""

    def __init__(self) -> None:
        """Initialize LiteLLM client."""
        import litellm

        litellm.api_base = settings.litellm_api_base_url
        litellm.api_key = settings.litellm_api_key
        self._litellm = litellm

    def _build_system_prompt(self) -> str:
        """Build the system prompt for news analysis."""
        return """You are the NEWS agent of Finance AI V3. You classify news articles: extract tickers, identify topic, assess materiality, summarize in Turkish (50 words).

TURKISH MARKET CONTEXT:
- Trading hours: 10:00-18:00 TRT (Europe/Istanbul, UTC+3), weekdays only
- BIST ticker format: 4-5 uppercase letters (THYAO, GARAN, KCHOL)
- KAP = Kamuyu Aydınlatma Platformu (public disclosure platform)
- TCMB = Türkiye Cumhuriyet Merkez Bankası
- TÜİK = Türkiye İstatistik Kurumu

TASK:
- Receive article body + metadata.
- Extract BIST tickers mentioned (regex + LLM verify).
- Classify topic (8 categories).
- Assess materiality (LOW/MEDIUM/HIGH/CRITICAL).
- Summarize in Turkish, ≤ 60 words.

OUTPUT FORMAT (strict JSON):
{
  "article_id": "string",
  "tickers": ["string"],
  "topic": "EARNINGS | MA | REGULATORY | MACRO | SECTOR | ANALYST_RATING | IPO | CAPITAL_ACTION",
  "materiality": "LOW | MEDIUM | HIGH | CRITICAL",
  "summary_tr": "string (max 60 words)",
  "key_entities": ["string"],
  "confidence": "float [0, 1]",
  "data_completeness": "complete | partial | missing"
}

RULES:
- NEVER output a ticker that does not exist in BIST
- NEVER exceed 60 words in summary
- NEVER default to HIGH/CRITICAL materiality without strong justification
- NEVER use markdown in summary
- ALWAYS include tickers array (empty if no specific ticker)
- ALWAYS include materiality
- ALWAYS use Turkish for summary
- ALWAYS include data_completeness

Token Budget: Input max 4000 tokens, Output max 400 tokens. Temperature: 0.1"""

    def _build_user_prompt(
        self,
        article_id: str,
        title: str,
        body: str,
        source: str,
    ) -> str:
        """Build user prompt with article content."""
        # Truncate body if too long
        truncated = False
        if len(body) > settings.max_body_length:
            body = body[: settings.max_body_length]
            truncated = True

        prompt_parts = [
            f"ARTICLE ID: {article_id}",
            f"TITLE: {title}",
            f"SOURCE: {source}",
            "",
            "ARTICLE BODY:",
            body,
        ]

        if truncated:
            prompt_parts.append("")
            prompt_parts.append("[Article truncated due to length]")

        return "\n".join(prompt_parts)

    async def analyze(
        self,
        article_id: str,
        title: str,
        body: str,
        source: str,
    ) -> tuple[dict[str, Any], bool]:
        """
        Call LLM to analyze news article.

        Args:
            article_id: Unique article identifier
            title: Article title
            body: Article body text
            source: News source

        Returns:
            Tuple of (LLM response as dictionary, truncated flag)
        """
        system_prompt = self._build_system_prompt()
        truncated = len(body) > settings.max_body_length
        user_prompt = self._build_user_prompt(article_id, title, body, source)

        try:
            response = self._litellm.completion(
                model=settings.litellm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=settings.litellm_max_tokens,
                temperature=settings.litellm_temperature,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            usage = response.usage

            # Parse JSON response
            result = json.loads(content)

            # Add metadata
            result["_meta"] = {
                "tokens_in": usage.prompt_tokens if usage else None,
                "tokens_out": usage.completion_tokens if usage else None,
                "cost_usd": (
                    (usage.prompt_tokens * 0.00001 + usage.completion_tokens * 0.00003)
                    if usage
                    else None
                ),
            }

            logger.info(
                "llm_news_response_received",
                article_id=article_id,
                topic=result.get("topic"),
                materiality=result.get("materiality"),
                tokens_in=result["_meta"]["tokens_in"],
                tokens_out=result["_meta"]["tokens_out"],
            )

            return result, truncated

        except json.JSONDecodeError as e:
            logger.error(
                "llm_json_decode_error",
                article_id=article_id,
                error=str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "llm_call_error",
                article_id=article_id,
                error=str(e),
            )
            raise
