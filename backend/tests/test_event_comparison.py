from datetime import timedelta

from app.core.calculations import devig_multiplicative
from app.core.calculations import fair_odds as calc_fair_odds
from app.core.config import Settings
from app.models.bookmakers import Bookmaker
from app.models.enums import MarketType, SelectionCode
from app.models.odds import OddsSnapshot
from app.services.event_comparison import get_event_comparison
from tests.test_value_bets import NOW, PINNACLE_ODDS, build_1x2_market


def _home_selection(comparison, market_type=MarketType.ONE_X_TWO):
    market = next(m for m in comparison.markets if m.market_type == market_type)
    return next(s for s in market.selections if s.selection_code == SelectionCode.HOME)


class TestEventComparison:
    def test_unknown_event_returns_none(self, db_session):
        result = get_event_comparison(db_session, 999, settings=Settings(_env_file=None))
        assert result is None

    def test_side_by_side_quotes_and_best_odds(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30, extra_books=["betclic"])
        home_sel = scenario["selections"]["home"]
        betclic = db_session.query(Bookmaker).filter_by(slug="betclic").one()
        db_session.add(
            OddsSnapshot(
                selection_id=home_sel.id, bookmaker_id=betclic.id, odds=2.25, captured_at=NOW
            )
        )
        db_session.flush()

        result = get_event_comparison(
            db_session, scenario["event"].id, settings=Settings(_env_file=None)
        )
        assert result is not None
        assert result.event_id == scenario["event"].id
        assert result.home_name == "Arsenal"
        assert result.away_name == "Chelsea"

        home_selection = _home_selection(result)
        bookmaker_slugs = {q.bookmaker_slug for q in home_selection.quotes}
        assert bookmaker_slugs == {"pinnacle", "winamax_fr", "betclic"}

        by_slug = {q.bookmaker_slug: q for q in home_selection.quotes}
        assert by_slug["winamax_fr"].is_best is True
        assert by_slug["betclic"].is_best is False
        assert by_slug["pinnacle"].is_best is False  # sharp book never eligible

        expected_fair = calc_fair_odds(devig_multiplicative(PINNACLE_ODDS)[0])
        assert home_selection.fair_odds == expected_fair
        expected_deviation = by_slug["winamax_fr"].odds / expected_fair - 1
        assert by_slug["winamax_fr"].deviation_vs_reference == expected_deviation

    def test_quotes_are_sorted_best_first(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30, extra_books=["betclic"])
        home_sel = scenario["selections"]["home"]
        betclic = db_session.query(Bookmaker).filter_by(slug="betclic").one()
        db_session.add(
            OddsSnapshot(
                selection_id=home_sel.id, bookmaker_id=betclic.id, odds=2.10, captured_at=NOW
            )
        )
        db_session.flush()

        result = get_event_comparison(
            db_session, scenario["event"].id, settings=Settings(_env_file=None)
        )
        home_selection = _home_selection(result)
        prices = [q.odds for q in home_selection.quotes]
        assert prices == sorted(prices, reverse=True)

    def test_stale_quote_is_shown_but_never_best(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30, extra_books=["betclic"])
        home_sel = scenario["selections"]["home"]
        betclic = db_session.query(Bookmaker).filter_by(slug="betclic").one()
        # A much higher but stale quote shouldn't win "best".
        db_session.add(
            OddsSnapshot(
                selection_id=home_sel.id,
                bookmaker_id=betclic.id,
                odds=5.00,
                captured_at=NOW - timedelta(minutes=60),
            )
        )
        db_session.flush()

        result = get_event_comparison(
            db_session, scenario["event"].id, settings=Settings(_env_file=None)
        )
        home_selection = _home_selection(result)
        by_slug = {q.bookmaker_slug: q for q in home_selection.quotes}

        assert by_slug["betclic"].is_stale is True
        assert by_slug["betclic"].is_best is False
        assert by_slug["winamax_fr"].is_best is True

    def test_partial_sharp_coverage_falls_back_to_raw_reference_price(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        pinnacle = scenario["bookmakers"]["pinnacle"]
        away_id = scenario["selections"]["away"].id
        stale_snapshot = (
            db_session.query(OddsSnapshot)
            .filter_by(bookmaker_id=pinnacle.id, selection_id=away_id)
            .one()
        )
        db_session.delete(stale_snapshot)
        db_session.flush()

        result = get_event_comparison(
            db_session, scenario["event"].id, settings=Settings(_env_file=None)
        )
        home_selection = _home_selection(result)

        assert home_selection.fair_odds is None
        assert home_selection.reference_odds == 2.00  # pinnacle's raw home price
        winamax_quote = next(
            q for q in home_selection.quotes if q.bookmaker_slug == "winamax_fr"
        )
        assert winamax_quote.deviation_vs_reference == winamax_quote.odds / 2.00 - 1

    def test_only_includes_this_events_markets(self, db_session):
        scenario_1 = build_1x2_market(
            db_session,
            home_odds=2.30,
            home_name="Arsenal",
            away_name="Chelsea",
            external_ref="evt-1",
        )
        build_1x2_market(
            db_session,
            home_odds=2.10,
            home_book="unibet_fr",
            home_name="Real Madrid",
            away_name="Barcelona",
            competition_slug="liga",
            external_ref="evt-2",
        )

        result = get_event_comparison(
            db_session, scenario_1["event"].id, settings=Settings(_env_file=None)
        )
        assert len(result.markets) == 1
        home_selection = _home_selection(result)
        bookmaker_slugs = {q.bookmaker_slug for q in home_selection.quotes}
        assert "unibet_fr" not in bookmaker_slugs

    def test_sharp_reference_row_always_present_when_quoted(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        result = get_event_comparison(
            db_session, scenario["event"].id, settings=Settings(_env_file=None)
        )
        home_selection = _home_selection(result)
        sharp_quotes = [q for q in home_selection.quotes if q.is_sharp_reference]
        assert len(sharp_quotes) == 1
        assert sharp_quotes[0].bookmaker_slug == "pinnacle"
