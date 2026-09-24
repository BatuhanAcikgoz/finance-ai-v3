"""Pydantic models for News Analysis."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Topic(str, Enum):
    """News topic categories."""

    EARNINGS = "EARNINGS"
    MA = "MA"
    REGULATORY = "REGULATORY"
    MACRO = "MACRO"
    SECTOR = "SECTOR"
    ANALYST_RATING = "ANALYST_RATING"
    IPO = "IPO"
    CAPITAL_ACTION = "CAPITAL_ACTION"


class Materiality(str, Enum):
    """Materiality level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DataCompleteness(str, Enum):
    """Data completeness status."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class NewsAnalysisResult(BaseModel):
    """Output of news analysis agent."""

    article_id: str
    tickers: list[str] = Field(default_factory=list)
    topic: Topic
    materiality: Materiality
    summary_tr: str = Field(max_length=360)  # ~60 words
    key_entities: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    data_completeness: DataCompleteness
    truncated: bool = False
    analysis_timestamp: datetime = Field(default_factory=lambda: datetime.now())
    llm_tokens_in: int | None = None
    llm_tokens_out: int | None = None
    cost_usd: float | None = None


class NewsNewEvent(BaseModel):
    """Input event from news collector."""

    event_type: str = "raw.news.new"
    article_id: str
    source: str
    title: str
    url: str
    timestamp: str


class NewsAnalysisDBRecord(BaseModel):
    """Record to be stored in PostgreSQL."""

    analysis_id: str
    article_id: str
    tickers: list[str]
    topic: Topic
    materiality: Materiality
    summary_tr: str
    key_entities: list[str]
    confidence: float
    data_completeness: DataCompleteness
    truncated: bool
    analysis_timestamp: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now())
