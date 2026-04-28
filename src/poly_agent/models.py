from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from signals_contract import Signal

# Re-export Signal so existing imports of `from poly_agent.models import Signal` keep working.
# For poly signals, Signal.asset is the Polymarket market slug (matches agent_configs.slug).
__all__ = ["Signal", "PolyMarket", "PolyIntent", "Fill"]


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
