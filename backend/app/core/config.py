from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://odds:odds@localhost:5432/odds"

    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    odds_api_regions: str = "eu"
    odds_api_timeout_seconds: float = 10.0

    # Bookmaker keys (as returned by the provider) used to flag ANJ-licensed
    # French books and the sharp reference line. Adjust to match the exact
    # keys exposed by whichever provider/region is active.
    anj_bookmaker_keys: Annotated[list[str], NoDecode] = [
        "winamax_fr",
        "betclic",
        "unibet_fr",
        "zebet_fr",
        "pmu_fr",
    ]
    sharp_reference_bookmaker_key: str = "pinnacle"

    @field_validator("anj_bookmaker_keys", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        # NoDecode above skips pydantic-settings' default JSON-array parsing,
        # so ANJ_BOOKMAKER_KEYS=winamax_fr,betclic,... works as a plain CSV.
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

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
