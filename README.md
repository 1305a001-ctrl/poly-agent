# poly-agent

Phase 7. Long-running daemon that consumes `signals:poly` + `signals:critical` and opens / settles Polymarket positions. Paper-mode in v0.1; live (on-chain) execution to come.

For system context, read [`infra-core/docs/ARCHITECTURE.md`](https://github.com/1305a001-ctrl/infra-core/blob/main/docs/ARCHITECTURE.md) first.

## What it does

Two concurrent loops:

| Loop | Trigger | Action |
|---|---|---|
| `signal_loop` | Redis pubsub message | look up agent_config (slug = market_slug), evaluate gates, open paper position |
| `position_loop` | every `POLL_INTERVAL_SECONDS` (5min default) | walk every open position via Polymarket Gamma API; settle when market resolves |

Direction mapping: `long → buy YES`, `short → buy NO`. `neutral` / `watch` are skipped.

PnL on settle:
- **Winner side** = `shares × $1 − stake_usd`
- **Loser side** = `−stake_usd`
- (Early exit not yet implemented — markets are slow-moving so probability stops aren't worth the complexity in v0.1.)

## Module map

```
src/poly_agent/
├── main.py            # asyncio entry — signal_loop + position_loop
├── settings.py        # pydantic-settings; all env vars + tunables
├── db.py              # asyncpg pool + JSONB codec + reads/writes for poly_positions
├── decision.py        # PURE — signal × agent_config → PolyIntent (covered by tests)
├── models.py          # Signal, PolyMarket, PolyIntent, Fill — pydantic types
├── polymarket.py      # Gamma API adapter (read-only; no key needed)
├── positions.py       # polling loop — checks for resolution, settles paper PnL
└── alerts.py          # Telegram open / settle formatters
```

## Polymarket integration

v0.1 uses **only** the public Gamma API (`https://gamma-api.polymarket.com`), read-only. No USDC, no private key. Paper positions track stake and entry probability; settlement uses the resolved outcome at $1 / $0 payout.

Future on-chain execution will add `src/poly_agent/brokers/polymarket.py`:
- USDC on Polygon
- Wallet private key (env var, never committed)
- Polymarket CLOB API for order placement
- New broker entry `'polymarket'` in `poly_positions.broker` constraint

## Risk envelope

| Setting | Default | Env var |
|---|---|---|
| Stake per signal | $25 | `STAKE_PER_SIGNAL_USD` |
| Total stake cap | $500 | `TOTAL_STAKE_CAP_USD` |
| Min confidence | 0.65 | `MIN_CONFIDENCE` |
| Resolution poll | 300s | `POLL_INTERVAL_SECONDS` |
| Halt switch | off | `POLY_AGENT_HALT=1` |

## Tests

```bash
pip install -e '.[dev]'
pytest -q
```

`tests/test_decision.py` covers every gate (halt, no-config, disabled, low-confidence, dup-market, stake-cap) plus URL-to-slug parsing.

## Wire-up

1. Apply migration:
   ```bash
   cat migrations/004_poly_positions.sql | ssh ai-primary 'sudo docker exec -i postgres psql -U benadmin -d aicore'
   ```
2. Create per-market configs via control-plane `/poly/new` (slug = market slug; market_url; resolution_condition; min_confidence; max_stake_pct; enabled)
3. Set env at `/srv/secrets/poly-agent.env` (Postgres, Redis, Telegram creds, optional Sentry — no Polymarket key for paper)
4. `docker compose -f infra-core/compose/poly-agent/docker-compose.yml up -d`

See [LOCAL-DEV.md](https://github.com/1305a001-ctrl/infra-core/blob/main/docs/LOCAL-DEV.md) for running locally + creating test markets.
