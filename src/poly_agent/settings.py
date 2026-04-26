from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database + Redis (validated at connect time)
    aicore_db_url: str = ""
    redis_url: str = "redis://localhost:6379"

    # Risk envelope
    stake_per_signal_usd: float = 25.0
    total_stake_cap_usd: float = 500.0
    min_confidence: float = 0.65

    # Resolution polling cadence (Polymarket markets move slowly; 5 min is plenty)
    poll_interval_seconds: int = 300

    # Kill switch
    poly_agent_halt: bool = False

    # Polymarket API (public — no key needed for read access)
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"

    # Notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Sentry
    sentry_dsn: str = ""


settings = Settings()
