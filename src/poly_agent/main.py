"""Poly agent daemon. Two loops: signal_loop + position_loop (resolution polling)."""
import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as aioredis
import sentry_sdk

from poly_agent import alerts
from poly_agent.db import db
from poly_agent.decision import decide
from poly_agent.models import Signal
from poly_agent.polymarket import get_market
from poly_agent.positions import position_loop
from poly_agent.settings import settings

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.0)


async def _open_position(intent, signal: Signal) -> None:
    pid = await db.insert_position({
        "signal_id": intent.signal_id,
        "agent_config_id": intent.agent_config_id,
        "agent_config_version": intent.agent_config_version,
        "market_slug": intent.market_slug,
        "market_url": intent.market_url,
        "side": intent.side,
        "stake_usd": intent.stake_usd,
        "metadata": {
            "confidence": signal.confidence,
            "composite_risk_score": signal.composite_risk_score,
            "strategy_git_sha": signal.strategy_git_sha,
        },
    })

    market = await get_market(intent.market_url or intent.market_slug)
    if market is None:
        await db.reject_position(pid, "could not fetch Polymarket data")
        return
    if market.resolved:
        await db.reject_position(pid, f"market already resolved {market.winner}")
        return

    entry_prob = market.yes_price if intent.side == "YES" else market.no_price
    if entry_prob <= 0 or entry_prob >= 1:
        await db.reject_position(pid, f"non-tradable probability {entry_prob:.3f}")
        return

    shares = intent.stake_usd / entry_prob
    opened_at = datetime.now(UTC)

    await db.fill_position(
        pid,
        entry_probability=entry_prob,
        shares=shares,
        condition_id=market.condition_id,
        opened_at=opened_at,
    )

    await alerts.telegram(alerts.format_open(
        market_slug=intent.market_slug, side=intent.side, stake_usd=intent.stake_usd,
        entry_probability=entry_prob, shares=shares, confidence=signal.confidence,
        market_url=intent.market_url,
    ))
    log.info("Opened poly %s %s stake=$%.0f @ %.3f shares=%.1f",
             intent.market_slug, intent.side, intent.stake_usd, entry_prob, shares)


async def _handle_signal(signal: Signal) -> None:
    cfg = await db.get_active_poly_config(signal.asset)
    open_total = await db.open_stake_total_usd()
    has_dup = await db.has_open_on_market(signal.asset)

    intent, skip = decide(
        signal=signal, agent_config=cfg,
        open_total_stake_usd=open_total,
        has_open_on_market=has_dup,
        halt=settings.poly_agent_halt,
    )
    if intent is None:
        log.info("Skipped poly signal %s (%s %s conf=%.2f): %s",
                 signal.id, signal.asset, signal.direction, signal.confidence, skip)
        return

    await _open_position(intent, signal)


async def signal_loop() -> None:
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("signals:poly", "signals:critical")
    log.info("Subscribed to signals:poly + signals:critical")

    seen: set[UUID] = set()
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            raw = json.loads(message["data"])
            signal = Signal.model_validate(raw)
        except Exception as exc:
            log.error("Bad payload on %s: %s", message.get("channel"), exc)
            continue

        # Critical channel can carry non-poly signals — ignore unless we have a config for the asset
        if signal.id in seen:
            continue
        seen.add(signal.id)
        if len(seen) > 1000:
            seen.clear()

        try:
            await _handle_signal(signal)
        except Exception:
            log.exception("Failed to handle signal %s", signal.id)


async def main() -> None:
    _setup_logging()
    log.info("poly-agent starting (halt=%s)", settings.poly_agent_halt)
    await db.connect()
    try:
        await asyncio.gather(signal_loop(), position_loop())
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
