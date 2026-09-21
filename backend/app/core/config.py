from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _csv_to_list(value: object) -> object:
    # Used with NoDecode fields so FOO=a,b,c works in .env, alongside the
    # JSON array syntax pydantic-settings also accepts for non-string input.
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://odds:odds@localhost:5432/odds"

    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    odds_api_regions: str = "eu"
    odds_api_timeout_seconds: float = 10.0
    # How many days back to look for finished events on the /scores endpoint
    # (The Odds API accepts 1-3).
    odds_api_scores_days_from: int = 3

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

    _split_anj_bookmaker_keys = field_validator("anj_bookmaker_keys", mode="before")(_csv_to_list)

    stale_odds_minutes: int = 10

    devig_method: str = "multiplicative"
    kelly_fraction: float = 0.25
    kelly_cap_pct: float = 0.02
    edge_threshold: float = 0.03

    default_bankroll: float = 1000.0
    monthly_loss_limit: float | None = None

    log_level: str = "INFO"

    # How often the standalone scheduler process (app/scheduler.py) runs its
    # jobs.
    closing_capture_interval_minutes: int = 5
    auto_settlement_interval_minutes: int = 15

    # Frontend origins allowed to call the API (Vite dev server + the Vercel
    # deployment). Comma-separated in .env, e.g. "https://odds.vercel.app".
    cors_allow_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    _split_cors_origins = field_validator("cors_allow_origins", mode="before")(_csv_to_list)


@lru_cache
def get_settings() -> Settings:
    return Settings()
