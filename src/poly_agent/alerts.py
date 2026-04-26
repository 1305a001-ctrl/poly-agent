"""Telegram alerts. No-op when creds absent."""
import logging

import httpx

from poly_agent.settings import settings

log = logging.getLogger(__name__)


async def telegram(text: str) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        log.debug("Telegram skipped (no creds): %s", text[:80])
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            await c.post(url, json={
                "chat_id": settings.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
    except Exception as exc:  # noqa: BLE001
        log.error("Telegram failed: %s", exc)


def format_open(*, market_slug: str, side: str, stake_usd: float, entry_probability: float,
                shares: float, confidence: float, market_url: str | None) -> str:
    lines = [
        f"<b>🎲 OPEN</b> {market_slug} {side}",
        f"stake ${stake_usd:.0f} @ {entry_probability:.3f} → {shares:.1f} shares",
        f"conf {confidence:.2f}",
    ]
    if market_url:
        lines.append(market_url)
    return "\n".join(lines)


def format_close(*, market_slug: str, side: str, entry: float, exit_probability: float,
                 pnl_usd: float, reason: str, resolved_outcome: str | None) -> str:
    sign = "🟢" if pnl_usd >= 0 else "🔴"
    body = f"entry {entry:.3f} → exit {exit_probability:.3f}"
    if resolved_outcome:
        body += f" (resolved {resolved_outcome})"
    return (
        f"<b>{sign} CLOSE</b> {market_slug} {side} ({reason})\n"
        f"{body}\n"
        f"pnl ${pnl_usd:+.2f}"
    )
