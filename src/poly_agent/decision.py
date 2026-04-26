"""Pure function: signal + agent_config → PolyIntent or skip."""
import logging

from poly_agent.models import PolyIntent, Signal
from poly_agent.settings import settings

log = logging.getLogger(__name__)


def decide(
    signal: Signal,
    agent_config: dict | None,
    *,
    open_total_stake_usd: float,
    has_open_on_market: bool,
    halt: bool,
) -> tuple[PolyIntent | None, str]:
    """Return (intent, skip_reason). Maps signal.direction to YES/NO buy.

      long  → buy YES (the resolution_condition will resolve TRUE)
      short → buy NO  (the resolution_condition will resolve FALSE)
      neutral / watch → skip
    """
    if halt:
        return None, "halt switch on"
    if signal.direction not in ("long", "short"):
        return None, f"non-actionable direction {signal.direction!r}"
    if agent_config is None:
        return None, f"no poly config for market {signal.asset}"

    cfg = agent_config["config"]
    if not cfg.get("enabled", False):
        return None, f"market {signal.asset} config disabled"

    min_conf = float(cfg.get("min_confidence", settings.min_confidence))
    if signal.confidence < min_conf:
        return None, f"confidence {signal.confidence:.2f} < {min_conf:.2f}"

    if has_open_on_market:
        return None, f"already have open position on {signal.asset}"

    stake = float(settings.stake_per_signal_usd)  # MVP fixed stake
    if open_total_stake_usd + stake > settings.total_stake_cap_usd:
        return None, (
            f"would exceed stake cap: ${open_total_stake_usd:.0f} + ${stake:.0f} "
            f"> ${settings.total_stake_cap_usd:.0f}"
        )

    side = "YES" if signal.direction == "long" else "NO"

    return PolyIntent(
        signal_id=signal.id,
        agent_config_id=agent_config["id"],
        agent_config_version=agent_config["version"],
        market_slug=signal.asset,
        market_url=cfg.get("market_url"),
        side=side,
        stake_usd=stake,
    ), ""
