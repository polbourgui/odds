import httpx
import pytest

from app.core.config import Settings
from app.models.enums import MarketType, SelectionCode
from app.providers.exceptions import (
    ProviderAuthError,
    ProviderQuotaExceededError,
    ProviderTimeoutError,
)
from app.providers.the_odds_api import TheOddsApiProvider

SETTINGS = Settings(odds_api_key="test-key", odds_api_base_url="https://example.test")

ODDS_RESPONSE = [
    {
        "id": "evt-1",
        "sport_key": "soccer_epl",
        "sport_title": "EPL",
        "commence_time": "2026-03-01T20:00:00Z",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": "2026-03-01T19:50:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Arsenal", "price": 2.1},
                            {"name": "Draw", "price": 3.4},
                            {"name": "Chelsea", "price": 3.6},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.9, "point": 2.5},
                            {"name": "Under", "price": 1.95, "point": 2.5},
                        ],
                    },
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.9, "point": -1.0},
                            {"name": "Chelsea", "price": 1.9, "point": 1.0},
                        ],
                    },
                ],
            }
        ],
    }
]

EVENTS_RESPONSE = [
    {
        "id": "evt-1",
        "sport_key": "soccer_epl",
        "sport_title": "EPL",
        "commence_time": "2026-03-01T20:00:00Z",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
    }
]

TENNIS_ODDS_RESPONSE = [
    {
        "id": "evt-2",
        "sport_key": "tennis_atp",
        "sport_title": "ATP",
        "commence_time": "2026-03-02T12:00:00Z",
        "home_team": "Novak Djokovic",
        "away_team": "Carlos Alcaraz",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": "2026-03-02T11:50:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Novak Djokovic", "price": 1.5},
                            {"name": "Carlos Alcaraz", "price": 2.6},
                        ],
                    }
                ],
            }
        ],
    }
]


def _provider(handler) -> TheOddsApiProvider:
    client = httpx.Client(
        base_url=SETTINGS.odds_api_base_url, transport=httpx.MockTransport(handler)
    )
    return TheOddsApiProvider(settings=SETTINGS, client=client)


class TestFetchEvents:
    def test_parses_events_without_odds(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/sports/soccer_epl/events"
            assert request.url.params["apiKey"] == "test-key"
            return httpx.Response(200, json=EVENTS_RESPONSE)

        events = _provider(handler).fetch_events("soccer_epl")

        assert len(events) == 1
        assert events[0].provider_event_id == "evt-1"
        assert events[0].home_name == "Arsenal"
        assert events[0].away_name == "Chelsea"
        assert events[0].competition_name == "EPL"


class TestFetchOdds:
    def test_maps_1x2_totals_and_skips_spreads(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/sports/soccer_epl/odds"
            return httpx.Response(200, json=ODDS_RESPONSE)

        results = _provider(handler).fetch_odds("soccer_epl")

        assert len(results) == 1
        event_odds = results[0]
        assert event_odds.event.provider_event_id == "evt-1"
        assert len(event_odds.bookmakers) == 1

        bm = event_odds.bookmakers[0]
        assert bm.bookmaker_key == "pinnacle"
        market_types = {m.market_type for m in bm.markets}
        assert market_types == {MarketType.ONE_X_TWO, MarketType.OVER_UNDER}

        one_x_two = next(m for m in bm.markets if m.market_type == MarketType.ONE_X_TWO)
        codes = {o.selection_code: o.price for o in one_x_two.outcomes}
        assert codes == {
            SelectionCode.HOME: 2.1,
            SelectionCode.DRAW: 3.4,
            SelectionCode.AWAY: 3.6,
        }

        totals = next(m for m in bm.markets if m.market_type == MarketType.OVER_UNDER)
        assert {o.line for o in totals.outcomes} == {2.5}
        assert {o.selection_code for o in totals.outcomes} == {
            SelectionCode.OVER,
            SelectionCode.UNDER,
        }

    def test_two_way_h2h_maps_to_moneyline(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=TENNIS_ODDS_RESPONSE)

        results = _provider(handler).fetch_odds("tennis_atp")

        market = results[0].bookmakers[0].markets[0]
        assert market.market_type == MarketType.MONEYLINE
        participant_names = {o.participant_name for o in market.outcomes}
        assert participant_names == {"Novak Djokovic", "Carlos Alcaraz"}
        assert all(o.selection_code == SelectionCode.PARTICIPANT_WIN for o in market.outcomes)

    def test_market_types_filter_is_applied_client_side(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=ODDS_RESPONSE)

        results = _provider(handler).fetch_odds("soccer_epl", market_types=[MarketType.ONE_X_TWO])

        market_types = {m.market_type for m in results[0].bookmakers[0].markets}
        assert market_types == {MarketType.ONE_X_TWO}


class TestErrorHandling:
    def test_auth_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"message": "bad key"})

        with pytest.raises(ProviderAuthError):
            _provider(handler).fetch_events("soccer_epl")

    def test_quota_exceeded_carries_remaining_count(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"x-requests-remaining": "0"}, json={})

        with pytest.raises(ProviderQuotaExceededError) as exc_info:
            _provider(handler).fetch_events("soccer_epl")
        assert exc_info.value.requests_remaining == 0

    def test_timeout(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("boom", request=request)

        with pytest.raises(ProviderTimeoutError):
            _provider(handler).fetch_events("soccer_epl")
