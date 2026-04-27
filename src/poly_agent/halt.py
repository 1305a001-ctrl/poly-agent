"""Cross-agent kill switch (mirrors trading-agent/halt.py).

Reads `system:halt` from Redis. Set by pa-agent's /halt command. Cached 5s.
"""
import logging
import time

import redis.asyncio as aioredis

from poly_agent.settings import settings

log = logging.getLogger(__name__)

KEY = "system:halt"
CACHE_TTL_S = 5

_state: dict = {"halted": False, "ts": 0.0, "client": None}


async def is_halted() -> bool:
    if settings.poly_agent_halt:
        return True

    now = time.monotonic()
    if now - _state["ts"] < CACHE_TTL_S:
        return _state["halted"]

    try:
        if _state["client"] is None:
            _state["client"] = aioredis.from_url(settings.redis_url, decode_responses=True)
        v = await _state["client"].get(KEY)
        halted = bool(v) and v not in ("0", "false", "False", "")
    except Exception as exc:  # noqa: BLE001
        log.warning("halt check failed: %s — assuming NOT halted", exc)
        halted = False

    _state["halted"] = halted
    _state["ts"] = now
    return halted
