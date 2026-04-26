import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class Signal(BaseModel):
    """Inbound signal from Redis (matches news-consolidator INTEGRATION.md)."""
    id: UUID
    strategy_id: UUID
    research_config_id: UUID
    strategy_git_sha: str
    research_config_version: int
    asset: str  # for poly signals, this is the market slug (matches agent_config.slug)
    direction: Literal["long", "short", "neutral", "watch"]
    confidence: float = Field(ge=0.0, le=1.0)
    composite_risk_score: float | None = None
    risk_score: dict | None = None
    source_article_ids: list[UUID] = Field(default_factory=list)
    payload: dict = Field(default_factory=dict)
    published_at: datetime

    @field_validator("risk_score", "payload", mode="before")
    @classmethod
    def _parse_json_string(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v


class PolyMarket(BaseModel):
    """Polymarket Gamma API market response (subset)."""
    slug: str
    condition_id: str | None = None
    yes_price: float = Field(ge=0.0, le=1.0)
    no_price: float = Field(ge=0.0, le=1.0)
    closed: bool = False
    resolved: bool = False
    winner: Literal["YES", "NO"] | None = None  # set when resolved


class PolyIntent(BaseModel):
    """Decision output: which side, how much."""
    signal_id: UUID
    agent_config_id: UUID
    agent_config_version: int
    market_slug: str
    market_url: str | None = None
    side: Literal["YES", "NO"]
    stake_usd: float = Field(gt=0)


class Fill(BaseModel):
    entry_probability: float = Field(ge=0.0, le=1.0)
    shares: float
    opened_at: datetime
