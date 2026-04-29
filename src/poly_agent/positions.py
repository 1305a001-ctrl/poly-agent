"""Position polling loop: walks every open paper position, settles if market resolved."""
import asyncio
import logging
from datetime import UTC, datetime

from poly_agent import alerts
from poly_agent.db import db
from poly_agent.polymarket import get_market
from poly_agent.settings import settings

log = logging.getLogger(__name__)


async def _settle(pos, market) -> None:
    """Settle a position. winner==side → +(1-entry)*shares; loser → -stake."""
    side = pos["side"]
    entry = pos["entry_probability"] or 0.0
    shares = pos["shares"] or 0.0
    stake = pos["stake_usd"]

    if market.winner == side:
        exit_prob = 1.0
        pnl = shares * 1.0 - stake
    else:
        exit_prob = 0.0
        pnl = -stake

    closed_at = datetime.now(UTC)
    await db.close_position(
        pos["id"], exit_probability=exit_prob, pnl_usd=pnl,
        resolved_outcome=market.winner, close_reason="resolved", closed_at=closed_at,
    )

    # Outcome row labeled 'poly_resolved' so consistency_scores treats
    # poly settlements as their own bucket, distinct from outcome-scorer
    # horizon evaluations (which can't score poly markets anyway — no spot price).
    duration_h = (closed_at - pos["opened_at"]).total_seconds() / 3600 if pos["opened_at"] else 0
    await db.write_signal_outcome(
        signal_id=pos["signal_id"],
        horizon="poly_resolved",
        outcome="win" if pnl > 0 else ("loss" if pnl < 0 else "flat"),
        price_at_signal=entry,
        price_at_eval=exit_prob,
        notes=(
            f"poly resolved {market.winner} after {duration_h:.1f}h "
            f"(paper, pnl=${pnl:+.2f})"
        ),
    )

    await alerts.telegram(alerts.format_close(
        market_slug=pos["market_slug"], side=side, entry=entry,
        exit_probability=exit_prob, pnl_usd=pnl, reason="resolved",
        resolved_outcome=market.winner,
    ))
    log.info("Settled %s %s on %s: pnl=$%.2f", pos["market_slug"], side, market.winner, pnl)


async def _check_one(pos) -> None:
    if pos["status"] != "open":
        return
    market = await get_market(pos["market_url"] or pos["market_slug"])
    if market is None:
        return
    if market.resolved and market.winner:
        await _settle(pos, market)


async def position_loop() -> None:
    log.info("Poly position polling loop started (every %ds)", settings.poll_interval_seconds)
    while True:
        try:
            positions = await db.open_positions()
            for p in positions:
                await _check_one(p)
        except Exception:
            log.exception("position_loop iteration failed")
        await asyncio.sleep(settings.poll_interval_seconds)
