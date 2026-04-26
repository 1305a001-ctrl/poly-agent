-- Phase 7 poly agent: poly_positions table.
-- Tracks every Polymarket position from signal-driven entry through settlement.
-- Run: cat migrations/004_poly_positions.sql | ssh benadmin@ai-primary "sudo docker exec -i postgres psql -U benadmin -d aicore"

CREATE TABLE IF NOT EXISTS poly_positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_id UUID NOT NULL REFERENCES market_signals(id),
  agent_config_id UUID NOT NULL REFERENCES agent_configs(id),
  agent_config_version INTEGER NOT NULL,
  market_slug TEXT NOT NULL,                  -- = agent_config.slug
  market_url TEXT,
  market_condition_id TEXT,                   -- Polymarket condition_id when known
  side TEXT NOT NULL,                         -- YES / NO
  stake_usd REAL NOT NULL,                    -- $ committed
  entry_probability REAL,                     -- price at entry, 0..1
  shares REAL,                                -- stake_usd / entry_probability
  status TEXT NOT NULL DEFAULT 'pending',
  broker TEXT NOT NULL DEFAULT 'paper',
  resolved_outcome TEXT,                      -- YES / NO when market resolves
  exit_probability REAL,
  pnl_usd REAL,
  close_reason TEXT,                          -- resolved / time_stop / manual / error
  opened_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  errors JSONB NOT NULL DEFAULT '[]'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (status IN ('pending','open','closed','cancelled','error')),
  CHECK (side IN ('YES','NO')),
  CHECK (broker IN ('paper','polymarket')),
  CHECK (resolved_outcome IS NULL OR resolved_outcome IN ('YES','NO')),
  CHECK (close_reason IS NULL OR close_reason IN ('resolved','time_stop','manual','error'))
);

CREATE INDEX IF NOT EXISTS poly_positions_status_idx ON poly_positions (status);
CREATE INDEX IF NOT EXISTS poly_positions_market_open_idx
  ON poly_positions (market_slug) WHERE status IN ('pending','open');
CREATE INDEX IF NOT EXISTS poly_positions_signal_idx ON poly_positions (signal_id);
