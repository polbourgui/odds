from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://odds:odds@localhost:5432/odds"

    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"

    stale_odds_minutes: int = 10

    devig_method: str = "multiplicative"
    kelly_fraction: float = 0.25
    kelly_cap_pct: float = 0.02
    edge_threshold: float = 0.03

    default_bankroll: float = 1000.0
    monthly_loss_limit: float | None = None

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
