"""Seed the local dev database with a handful of realistic value bets, by
running fake provider payloads through the real ingestion pipeline. Not
meant for production use — just a way to eyeball the API/table locally.

Usage: DATABASE_URL=... python scripts/seed_dev_data.py
"""

from datetime import UTC, datetime, timedelta

from app.db.session import SessionLocal
from app.models.enums import MarketType, SelectionCode
from app.providers.base import (
    OddsProvider,
    ProviderBookmakerQuote,
    ProviderEvent,
    ProviderEventOdds,
    ProviderMarket,
    ProviderOutcome,
)
from app.services.odds_ingestion import OddsIngestionService

NOW = datetime.now(UTC)


class SeedProvider(OddsProvider):
    name = "seed_provider"

    def __init__(self, event_odds_list: list[ProviderEventOdds]):
        self._event_odds_list = event_odds_list

    def fetch_events(self, sport_key: str) -> list[ProviderEvent]:
        return [eo.event for eo in self._event_odds_list]

    def list_sports(self):
        return []

    def fetch_odds(self, sport_key: str, market_types=None) -> list[ProviderEventOdds]:
        return [eo for eo in self._event_odds_list if eo.event.sport_key == sport_key]


def one_x_two(home: float, draw: float, away: float) -> ProviderMarket:
    return ProviderMarket(
        market_type=MarketType.ONE_X_TWO,
        outcomes=[
            ProviderOutcome(selection_code=SelectionCode.HOME, price=home),
            ProviderOutcome(selection_code=SelectionCode.DRAW, price=draw),
            ProviderOutcome(selection_code=SelectionCode.AWAY, price=away),
        ],
    )


def totals(over: float, under: float, line: float) -> ProviderMarket:
    return ProviderMarket(
        market_type=MarketType.OVER_UNDER,
        outcomes=[
            ProviderOutcome(selection_code=SelectionCode.OVER, price=over, line=line),
            ProviderOutcome(selection_code=SelectionCode.UNDER, price=under, line=line),
        ],
    )


def moneyline(a_name: str, a_price: float, b_name: str, b_price: float) -> ProviderMarket:
    return ProviderMarket(
        market_type=MarketType.MONEYLINE,
        outcomes=[
            ProviderOutcome(
                selection_code=SelectionCode.PARTICIPANT_WIN, price=a_price, participant_name=a_name
            ),
            ProviderOutcome(
                selection_code=SelectionCode.PARTICIPANT_WIN, price=b_price, participant_name=b_name
            ),
        ],
    )


def bookmaker(key: str, name: str, markets: list[ProviderMarket]) -> ProviderBookmakerQuote:
    return ProviderBookmakerQuote(
        bookmaker_key=key, bookmaker_name=name, last_update=NOW, markets=markets
    )


SOCCER_EVENTS = [
    ProviderEventOdds(
        event=ProviderEvent(
            provider_event_id="seed-soccer-1",
            sport_key="soccer_epl",
            competition_name="Premier League",
            home_name="Arsenal",
            away_name="Chelsea",
            start_time=NOW + timedelta(days=1),
        ),
        bookmakers=[
            bookmaker(
                "pinnacle", "Pinnacle", [one_x_two(2.00, 3.50, 4.00), totals(1.90, 1.95, 2.5)]
            ),
            bookmaker(
                "winamax_fr", "Winamax", [one_x_two(2.30, 3.40, 3.90), totals(2.05, 1.85, 2.5)]
            ),
            bookmaker(
                "betclic", "Betclic", [one_x_two(2.05, 3.55, 3.85), totals(1.88, 1.98, 2.5)]
            ),
        ],
    ),
    ProviderEventOdds(
        event=ProviderEvent(
            provider_event_id="seed-soccer-2",
            sport_key="soccer_france_ligue_one",
            competition_name="Ligue 1",
            home_name="Paris Saint-Germain",
            away_name="Marseille",
            start_time=NOW + timedelta(days=2),
        ),
        bookmakers=[
            bookmaker("pinnacle", "Pinnacle", [one_x_two(1.45, 4.80, 7.00)]),
            bookmaker("unibet_fr", "Unibet", [one_x_two(1.50, 4.60, 7.50)]),
        ],
    ),
]

TENNIS_EVENTS = [
    ProviderEventOdds(
        event=ProviderEvent(
            provider_event_id="seed-tennis-1",
            sport_key="tennis_atp",
            competition_name="ATP Masters",
            home_name="Novak Djokovic",
            away_name="Carlos Alcaraz",
            start_time=NOW + timedelta(hours=6),
        ),
        bookmakers=[
            bookmaker(
                "pinnacle", "Pinnacle", [moneyline("Novak Djokovic", 1.75, "Carlos Alcaraz", 2.15)]
            ),
            bookmaker(
                "winamax_fr", "Winamax", [moneyline("Novak Djokovic", 1.95, "Carlos Alcaraz", 2.05)]
            ),
        ],
    ),
]


def main() -> None:
    db = SessionLocal()
    try:
        for sport_key, events in (
            ("soccer_epl", SOCCER_EVENTS[:1]),
            ("soccer_france_ligue_one", SOCCER_EVENTS[1:]),
            ("tennis_atp", TENNIS_EVENTS),
        ):
            provider = SeedProvider(events)
            service = OddsIngestionService(db, provider)
            result = service.ingest_sport(sport_key)
            print(f"{sport_key}: {result.events_seen} events, {result.snapshots_created} snapshots")
    finally:
        db.close()


if __name__ == "__main__":
    main()
