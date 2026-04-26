# poly-agent

Phase 7 consumer for `signals:poly` + `signals:critical` Redis channels.

**Status:** v0.1 — paper positions only (no on-chain Polymarket execution). Reads live YES/NO probabilities from the Polymarket Gamma API, simulates fills and settles paper PnL when markets resolve.

## What it does

1. Subscribes to `signals:poly` + `signals:critical`.
2. For each signal, looks up the matching `agent_configs` row (slug = market slug).
3. If the signal passes filters (enabled, confidence, dedupe, stake cap) → opens a paper position:
   - `direction='long'` → buy YES
   - `direction='short'` → buy NO
4. Polls open positions every 5min via Polymarket Gamma API; settles when market resolves.
5. Writes `signal_outcomes` after settlement.
6. Telegram alert on every open + settle.

## Risk envelope (v0.1 defaults)

| Setting | Default | Env var |
|---|---|---|
| Stake per signal | $25 | `STAKE_PER_SIGNAL_USD` |
| Total stake cap | $500 | `TOTAL_STAKE_CAP_USD` |
| Min confidence | 0.65 | `MIN_CONFIDENCE` |
| Resolution poll | 300s | `POLL_INTERVAL_SECONDS` |
| Halt switch | off | `POLY_AGENT_HALT=1` |

## Wire-up

1. Apply migration: `psql ... < migrations/004_poly_positions.sql`
2. Configure markets via control-plane `/poly/new` page (slug, market_url, resolution_condition, min_confidence, max_stake_pct, enabled).
3. Set env (Postgres, Redis, Telegram). No Polymarket key needed for paper mode.
4. `docker compose up -d`.
