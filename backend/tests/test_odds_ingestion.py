from app.core.config import Settings
from app.models.bookmakers import Bookmaker
from app.models.enums import MarketType, SelectionCode
from app.models.events import Event
from app.models.markets import Selection
from app.models.odds import OddsSnapshot
from app.providers.base import (
    OddsProvider,
    ProviderBookmakerQuote,
    ProviderEvent,
    ProviderEventOdds,
    ProviderMarket,
    ProviderOutcome,
)
from app.providers.exceptions import ProviderError
from app.services.odds_ingestion import OddsIngestionService, run_ingestion_for_tracked_sports

EVENT = ProviderEvent(
    provider_event_id="evt-1",
    sport_key="soccer_epl",
    competition_name="EPL",
    home_name="Arsenal",
    away_name="Chelsea",
    start_time="2026-03-01T20:00:00Z",
)

ONE_X_TWO_MARKET = ProviderMarket(
    market_type=MarketType.ONE_X_TWO,
    outcomes=[
        ProviderOutcome(selection_code=SelectionCode.HOME, price=2.10),
        ProviderOutcome(selection_code=SelectionCode.DRAW, price=3.40),
        ProviderOutcome(selection_code=SelectionCode.AWAY, price=3.60),
    ],
)


class FakeProvider(OddsProvider):
    name = "fake_provider"

    def __init__(self, event_odds_list: list[ProviderEventOdds]):
        self._event_odds_list = event_odds_list

    def fetch_events(self, sport_key: str) -> list[ProviderEvent]:
        return [eo.event for eo in self._event_odds_list]

    def fetch_odds(self, sport_key: str, market_types=None) -> list[ProviderEventOdds]:
        return self._event_odds_list


def make_event_odds() -> ProviderEventOdds:
    return ProviderEventOdds(
        event=EVENT,
        bookmakers=[
            ProviderBookmakerQuote(
                bookmaker_key="winamax_fr",
                bookmaker_name="Winamax",
                last_update="2026-03-01T19:55:00Z",
                markets=[ONE_X_TWO_MARKET],
            ),
            ProviderBookmakerQuote(
                bookmaker_key="pinnacle",
                bookmaker_name="Pinnacle",
                last_update="2026-03-01T19:55:00Z",
                markets=[ONE_X_TWO_MARKET],
            ),
        ],
    )


class TestOddsIngestion:
    def test_creates_event_bookmakers_selections_and_snapshots(self, db_session):
        provider = FakeProvider([make_event_odds()])
        service = OddsIngestionService(db_session, provider)

        result = service.ingest_sport("soccer_epl")

        assert result.events_seen == 1
        assert result.snapshots_created == 6  # 2 bookmakers x 3 outcomes

        assert db_session.query(Event).count() == 1
        assert db_session.query(Selection).count() == 3
        assert db_session.query(OddsSnapshot).count() == 6

        winamax = db_session.query(Bookmaker).filter_by(slug="winamax_fr").one()
        assert winamax.is_anj_licensed is True
        assert winamax.is_sharp_reference is False

        pinnacle = db_session.query(Bookmaker).filter_by(slug="pinnacle").one()
        assert pinnacle.is_anj_licensed is False
        assert pinnacle.is_sharp_reference is True

    def test_snapshots_are_append_only_across_ingestion_runs(self, db_session):
        provider = FakeProvider([make_event_odds()])
        service = OddsIngestionService(db_session, provider)

        service.ingest_sport("soccer_epl")
        service.ingest_sport("soccer_epl")

        # No duplicate events/bookmakers/selections, but every run adds new
        # timestamped snapshots on top of the previous ones.
        assert db_session.query(Event).count() == 1
        assert db_session.query(Bookmaker).count() == 2
        assert db_session.query(Selection).count() == 3
        assert db_session.query(OddsSnapshot).count() == 12

    def test_snapshot_odds_values_match_provider_prices(self, db_session):
        provider = FakeProvider([make_event_odds()])
        service = OddsIngestionService(db_session, provider)
        service.ingest_sport("soccer_epl")

        prices = sorted(float(s.odds) for s in db_session.query(OddsSnapshot).all())
        assert prices == sorted([2.10, 3.40, 3.60, 2.10, 3.40, 3.60])


class MultiSportFakeProvider(OddsProvider):
    """A fake OddsProvider whose fetch_odds is keyed by sport_key, so a
    single instance can back tests exercising several tracked sports."""

    name = "multi_sport_fake_provider"

    def __init__(self, by_sport_key: dict[str, list[ProviderEventOdds] | Exception]):
        self._by_sport_key = by_sport_key

    def fetch_events(self, sport_key: str) -> list[ProviderEvent]:
        raise NotImplementedError

    def fetch_odds(self, sport_key: str, market_types=None) -> list[ProviderEventOdds]:
        outcome = self._by_sport_key.get(sport_key, [])
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class TestRunIngestionForTrackedSports:
    def test_ingests_every_tracked_sport_key(self, db_session):
        provider = MultiSportFakeProvider(
            {
                "soccer_epl": [make_event_odds()],
                "tennis_atp": [make_event_odds()],
            }
        )
        settings = Settings(
            _env_file=None, tracked_sport_keys=["soccer_epl", "tennis_atp"]
        )

        results = run_ingestion_for_tracked_sports(db_session, provider, settings=settings)

        assert [r.events_seen for r in results] == [1, 1]
        assert db_session.query(OddsSnapshot).count() == 12  # 6 per sport_key

    def test_provider_error_on_one_sport_key_does_not_abort_the_others(self, db_session):
        provider = MultiSportFakeProvider(
            {
                "soccer_epl": ProviderError("boom"),
                "tennis_atp": [make_event_odds()],
            }
        )
        settings = Settings(
            _env_file=None, tracked_sport_keys=["soccer_epl", "tennis_atp"]
        )

        results = run_ingestion_for_tracked_sports(db_session, provider, settings=settings)

        assert len(results) == 1
        assert results[0].events_seen == 1
        assert db_session.query(OddsSnapshot).count() == 6
