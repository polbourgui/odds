"""Abstract odds-provider interface.

Every odds source (aggregation API or, if unavoidable, a compliant scraper)
implements this interface. Nothing outside `app/providers/` should depend on
a specific provider's raw JSON shape — the rest of the app only ever sees
these schemas, so swapping or adding a source never touches reconciliation,
ingestion or the calculation module.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import MarketType, SelectionCode


class ProviderEvent(BaseModel):
    """A single fixture, without odds. Cheap to fetch for reconciliation."""

    provider_event_id: str
    sport_key: str
    competition_name: str
    home_name: str
    away_name: str
    start_time: datetime


class ProviderOutcome(BaseModel):
    selection_code: SelectionCode
    price: float
    # Set for OVER_UNDER outcomes (the total line, e.g. 2.5).
    line: float | None = None
    # Set for MONEYLINE PARTICIPANT_WIN outcomes (tennis, NBA winner).
    participant_name: str | None = None


class ProviderMarket(BaseModel):
    market_type: MarketType
    outcomes: list[ProviderOutcome]


class ProviderBookmakerQuote(BaseModel):
    bookmaker_key: str
    bookmaker_name: str
    last_update: datetime
    markets: list[ProviderMarket]


class ProviderEventOdds(BaseModel):
    event: ProviderEvent
    bookmakers: list[ProviderBookmakerQuote]


class OddsProvider(ABC):
    """Adapter contract. Implementations must raise the typed errors in
    `app.providers.exceptions` rather than leaking transport-level ones."""

    name: str

    @abstractmethod
    def fetch_events(self, sport_key: str) -> list[ProviderEvent]:
        """List upcoming events for a sport, without odds."""

    @abstractmethod
    def fetch_odds(
        self, sport_key: str, market_types: list[MarketType] | None = None
    ) -> list[ProviderEventOdds]:
        """Fetch current odds for a sport, across bookmakers and markets."""
