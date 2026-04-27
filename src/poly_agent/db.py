"""Postgres client for poly-agent."""
import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from poly_agent.settings import settings

log = logging.getLogger(__name__)


class DB:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DB not connected — call connect() first")
        return self._pool

    async def connect(self) -> None:
        if not settings.aicore_db_url:
            raise RuntimeError("AICORE_DB_URL not set")
        self._pool = await asyncpg.create_pool(
            settings.aicore_db_url, min_size=1, max_size=5, init=_init_connection,
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    # ─── Reads ──────────────────────────────────────────────────────────────

    async def get_active_poly_config(self, market_slug: str) -> dict | None:
        """Active poly agent_config whose slug matches the signal's asset (= market slug)."""
        row = await self.pool.fetchrow(
            """
            SELECT id, version, config FROM agent_configs
            WHERE agent_type = 'poly' AND is_active = TRUE AND slug = $1
            ORDER BY version DESC, updated_at DESC LIMIT 1
            """,
            market_slug,
        )
        if not row:
            return None
        return {"id": row["id"], "version": row["version"], "config": row["config"]}

    async def open_stake_total_usd(self) -> float:
        row = await self.pool.fetchrow(
            "SELECT COALESCE(SUM(stake_usd), 0) AS t FROM poly_positions "
            "WHERE status IN ('pending','open')"
        )
        return float(row["t"])

    async def has_open_on_market(self, market_slug: str) -> bool:
        row = await self.pool.fetchrow(
            "SELECT 1 FROM poly_positions WHERE market_slug = $1 "
            "AND status IN ('pending','open') LIMIT 1",
            market_slug,
        )
        return row is not None

    async def open_positions(self) -> list[asyncpg.Record]:
        return await self.pool.fetch(
            "SELECT * FROM poly_positions WHERE status IN ('pending','open') ORDER BY opened_at"
        )

    # ─── Writes ─────────────────────────────────────────────────────────────

    async def insert_position(self, row: dict[str, Any]) -> UUID:
        r = await self.pool.fetchrow(
            """
            INSERT INTO poly_positions
              (signal_id, agent_config_id, agent_config_version, market_slug, market_url,
               side, stake_usd, broker, status, metadata)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            RETURNING id
            """,
            row["signal_id"], row["agent_config_id"], row["agent_config_version"],
            row["market_slug"], row.get("market_url"),
            row["side"], row["stake_usd"],
            row.get("broker", "paper"),
            row.get("status", "pending"),
            row.get("metadata", {}),
        )
        return r["id"]

    async def fill_position(self, pid: UUID, *, entry_probability: float, shares: float,
                            condition_id: str | None, opened_at: datetime) -> None:
        await self.pool.execute(
            """
            UPDATE poly_positions
               SET status = 'open', entry_probability = $2, shares = $3,
                   market_condition_id = COALESCE($4, market_condition_id),
                   opened_at = $5
             WHERE id = $1
            """,
            pid, entry_probability, shares, condition_id, opened_at,
        )

    async def close_position(self, pid: UUID, *, exit_probability: float, pnl_usd: float,
                             resolved_outcome: str | None, close_reason: str,
                             closed_at: datetime) -> None:
        await self.pool.execute(
            """
            UPDATE poly_positions
               SET status = 'closed', exit_probability = $2, pnl_usd = $3,
                   resolved_outcome = $4, close_reason = $5, closed_at = $6
             WHERE id = $1
            """,
            pid, exit_probability, pnl_usd, resolved_outcome, close_reason, closed_at,
        )

    async def reject_position(self, pid: UUID, reason: str) -> None:
        await self.pool.execute(
            "UPDATE poly_positions SET status = 'error', errors = errors || $2::jsonb"
            " WHERE id = $1",
            pid, [reason],
        )

    async def write_signal_outcome(self, *, signal_id: UUID, horizon: str, outcome: str,
                                   price_at_signal: float | None, price_at_eval: float | None,
                                   notes: str | None) -> None:
        pct = None
        if price_at_signal and price_at_eval and price_at_signal != 0:
            pct = (price_at_eval - price_at_signal) / price_at_signal
        await self.pool.execute(
            """
            INSERT INTO signal_outcomes
              (signal_id, evaluation_horizon, outcome,
               price_at_signal, price_at_evaluation, price_change_pct, notes)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            """,
            signal_id, horizon, outcome, price_at_signal, price_at_eval, pct, notes,
        )


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


db = DB()
