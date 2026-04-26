"""Polymarket Gamma API adapter (read-only, no auth).

Docs: https://docs.polymarket.com/#gamma-markets-api
"""
import json
import logging
import re

import httpx

from poly_agent.models import PolyMarket
from poly_agent.settings import settings

log = logging.getLogger(__name__)


def url_to_slug(market_url_or_slug: str) -> str:
    """Extract Polymarket slug from a full URL, or pass through if already a slug."""
    if not market_url_or_slug:
        return market_url_or_slug
    # https://polymarket.com/event/some-slug or /market/some-slug
    m = re.search(r"polymarket\.com/(?:event|market)/([^/?#]+)", market_url_or_slug)
    if m:
        return m.group(1)
    return market_url_or_slug


async def get_market(slug_or_url: str) -> PolyMarket | None:
    slug = url_to_slug(slug_or_url)
    url = f"{settings.polymarket_gamma_url}/markets"
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(url, params={"slug": slug})
            r.raise_for_status()
            data = r.json()
    except Exception as exc:  # noqa: BLE001
        log.error("Polymarket fetch failed for %s: %s", slug, exc)
        return None

    items = data if isinstance(data, list) else data.get("data") or []
    if not items:
        log.warning("No Polymarket market found for slug=%s", slug)
        return None

    m = items[0]
    return _parse_market(m, slug)


def _parse_market(m: dict, fallback_slug: str) -> PolyMarket | None:
    """Parse a Gamma /markets row. Outcome prices are string-encoded JSON arrays."""
    try:
        outcomes_raw = m.get("outcomes") or "[]"
        outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
        prices_raw = m.get("outcomePrices") or "[]"
        prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw

        yes_idx = next((i for i, o in enumerate(outcomes) if o.upper() == "YES"), 0)
        no_idx = 1 - yes_idx if len(outcomes) >= 2 else 1

        yes_price = float(prices[yes_idx]) if len(prices) > yes_idx else 0.5
        no_price = float(prices[no_idx]) if len(prices) > no_idx else 1.0 - yes_price

        closed = bool(m.get("closed", False))
        # Polymarket marks resolved markets with closedTime + outcomes that go to 0/1
        resolved = closed and (yes_price == 1.0 or no_price == 1.0)
        winner = None
        if resolved:
            winner = "YES" if yes_price >= no_price else "NO"

        return PolyMarket(
            slug=m.get("slug") or fallback_slug,
            condition_id=m.get("conditionId") or m.get("condition_id"),
            yes_price=yes_price,
            no_price=no_price,
            closed=closed,
            resolved=resolved,
            winner=winner,
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to parse market row %s: %s", fallback_slug, exc)
        return None
