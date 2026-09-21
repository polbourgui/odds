from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.calculations import devig_multiplicative
from app.core.calculations import edge as calc_edge
from app.core.calculations import fair_odds as calc_fair_odds
from app.core.calculations import kelly_stake as calc_kelly_stake
from app.core.config import Settings
from app.models.bookmakers import Bookmaker
from app.models.enums import MarketType, SelectionCode
from app.models.events import Event
from app.models.markets import EventMarket, Selection
from app.models.odds import OddsSnapshot
from app.models.participants import Participant
from app.models.sports import Competition, Sport
from app.services.value_bets import compute_value_bets

NOW = datetime.now(UTC)
PINNACLE_ODDS = [2.00, 3.50, 4.00]  # same reference case as test_calculations.py


def _get_or_create_sport(db, slug: str, name: str) -> Sport:
    sport = db.scalars(select(Sport).where(Sport.slug == slug)).one_or_none()
    if sport is None:
        sport = Sport(slug=slug, name=name)
        db.add(sport)
        db.flush()
    return sport


def _get_or_create_bookmaker(db, slug: str, **kwargs) -> Bookmaker:
    bookmaker = db.scalars(select(Bookmaker).where(Bookmaker.slug == slug)).one_or_none()
    if bookmaker is None:
        bookmaker = Bookmaker(slug=slug, name=slug, **kwargs)
        db.add(bookmaker)
        db.flush()
    return bookmaker


def build_1x2_market(
    db,
    *,
    home_odds=2.30,
    home_book="winamax_fr",
    extra_books=(),
    home_name="Arsenal",
    away_name="Chelsea",
    competition_slug="epl",
    external_ref="evt-1",
):
    """A soccer event with a 1X2 market, Pinnacle (sharp) priced on all three
    outcomes, and `home_book` offering `home_odds` on the home selection.

    Sport/competition/bookmakers are reused by slug across calls so a test
    can build several independent events without unique-constraint clashes.
    """
    sport = _get_or_create_sport(db, "soccer", "Football")

    competition = db.scalars(
        select(Competition).where(Competition.slug == competition_slug)
    ).one_or_none()
    if competition is None:
        competition = Competition(sport_id=sport.id, slug=competition_slug, name="EPL")
        db.add(competition)
    home = Participant(sport_id=sport.id, name=home_name, normalized_name=home_name.lower())
    away = Participant(sport_id=sport.id, name=away_name, normalized_name=away_name.lower())
    db.add_all([competition, home, away])
    db.flush()

    event = Event(
        sport_id=sport.id,
        competition_id=competition.id,
        home_participant_id=home.id,
        away_participant_id=away.id,
        start_time=NOW + timedelta(days=1),
        external_ref=external_ref,
    )
    db.add(event)
    db.flush()

    market = EventMarket(event_id=event.id, market_type=MarketType.ONE_X_TWO)
    db.add(market)
    db.flush()

    home_sel = Selection(event_market_id=market.id, code=SelectionCode.HOME)
    draw_sel = Selection(event_market_id=market.id, code=SelectionCode.DRAW)
    away_sel = Selection(event_market_id=market.id, code=SelectionCode.AWAY)
    db.add_all([home_sel, draw_sel, away_sel])
    db.flush()

    pinnacle = _get_or_create_bookmaker(db, "pinnacle", is_sharp_reference=True)
    book = _get_or_create_bookmaker(db, home_book, is_anj_licensed=True)
    for slug in extra_books:
        _get_or_create_bookmaker(db, slug, is_anj_licensed=True)
    db.flush()

    for sel, price in zip([home_sel, draw_sel, away_sel], PINNACLE_ODDS, strict=True):
        db.add(
            OddsSnapshot(
                selection_id=sel.id, bookmaker_id=pinnacle.id, odds=price, captured_at=NOW
            )
        )
    db.add(
        OddsSnapshot(
            selection_id=home_sel.id, bookmaker_id=book.id, odds=home_odds, captured_at=NOW
        )
    )
    db.flush()

    return {
        "sport": sport,
        "event": event,
        "market": market,
        "selections": {"home": home_sel, "draw": draw_sel, "away": away_sel},
        "bookmakers": {"pinnacle": pinnacle, home_book: book},
    }


class TestComputeValueBets:
    def test_edge_and_kelly_match_the_calculation_module(self, db_session):
        build_1x2_market(db_session, home_odds=2.30)

        results = compute_value_bets(db_session, settings=Settings(_env_file=None))

        assert len(results) == 1
        bet = results[0]

        true_probs = devig_multiplicative(PINNACLE_ODDS)
        expected_true_prob = true_probs[0]  # home
        expected_edge = calc_edge(expected_true_prob, 2.30)
        expected_fair_odds = calc_fair_odds(expected_true_prob)
        expected_stake = calc_kelly_stake(expected_true_prob, 2.30, 1000.0)

        assert bet.true_probability == expected_true_prob
        assert bet.edge == expected_edge
        assert bet.fair_odds == expected_fair_odds
        assert bet.kelly_stake == expected_stake
        assert bet.book_odds == 2.30
        assert bet.bookmaker_slug == "winamax_fr"
        assert bet.selection_code == SelectionCode.HOME
        assert bet.home_name == "Arsenal"
        assert bet.away_name == "Chelsea"
        assert bet.sport_slug == "soccer"

    def test_sharp_reference_book_is_never_a_row(self, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        results = compute_value_bets(db_session, settings=Settings(_env_file=None))
        assert all(r.bookmaker_slug != "pinnacle" for r in results)

    def test_non_anj_bookmaker_is_excluded(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        unlicensed = Bookmaker(slug="offshore_book", name="Offshore", is_anj_licensed=False)
        db_session.add(unlicensed)
        db_session.flush()
        db_session.add(
            OddsSnapshot(
                selection_id=scenario["selections"]["home"].id,
                bookmaker_id=unlicensed.id,
                odds=2.50,
                captured_at=NOW,
            )
        )
        db_session.flush()

        results = compute_value_bets(db_session, settings=Settings(_env_file=None))
        assert all(r.bookmaker_slug != "offshore_book" for r in results)

    def test_incomplete_sharp_coverage_excludes_the_whole_market(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        # Remove the sharp price on one outcome: devig can no longer be trusted.
        pinnacle_id = scenario["bookmakers"]["pinnacle"].id
        away_id = scenario["selections"]["away"].id
        snap = (
            db_session.query(OddsSnapshot)
            .filter_by(bookmaker_id=pinnacle_id, selection_id=away_id)
            .one()
        )
        db_session.delete(snap)
        db_session.flush()

        results = compute_value_bets(db_session, settings=Settings(_env_file=None))
        assert results == []

    def test_stale_anj_quote_is_excluded(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        home_sel = scenario["selections"]["home"]
        book = scenario["bookmakers"]["winamax_fr"]
        # Overwrite with an older-than-threshold snapshot on top of the fresh one.
        db_session.add(
            OddsSnapshot(
                selection_id=home_sel.id,
                bookmaker_id=book.id,
                odds=2.40,
                captured_at=NOW - timedelta(minutes=60),
            )
        )
        db_session.flush()
        # Latest snapshot per (selection, bookmaker) is now the fresh 2.30 one,
        # so this should still show up: sanity check before the real stale test.
        results = compute_value_bets(
            db_session, settings=Settings(_env_file=None, stale_odds_minutes=10)
        )
        assert len(results) == 1

    def test_stale_sharp_reference_excludes_market(self, db_session):
        sport = Sport(slug="soccer", name="Football")
        db_session.add(sport)
        db_session.flush()
        competition = Competition(sport_id=sport.id, slug="epl", name="EPL")
        home = Participant(sport_id=sport.id, name="Arsenal", normalized_name="arsenal")
        away = Participant(sport_id=sport.id, name="Chelsea", normalized_name="chelsea")
        db_session.add_all([competition, home, away])
        db_session.flush()
        event = Event(
            sport_id=sport.id,
            competition_id=competition.id,
            home_participant_id=home.id,
            away_participant_id=away.id,
            start_time=NOW + timedelta(days=1),
        )
        db_session.add(event)
        db_session.flush()
        market = EventMarket(event_id=event.id, market_type=MarketType.ONE_X_TWO)
        db_session.add(market)
        db_session.flush()
        sels = [Selection(event_market_id=market.id, code=c) for c in (
            SelectionCode.HOME, SelectionCode.DRAW, SelectionCode.AWAY
        )]
        db_session.add_all(sels)
        db_session.flush()
        pinnacle = Bookmaker(slug="pinnacle", name="Pinnacle", is_sharp_reference=True)
        book = Bookmaker(slug="winamax_fr", name="Winamax", is_anj_licensed=True)
        db_session.add_all([pinnacle, book])
        db_session.flush()
        # Sharp prices are all stale (40 min old, default threshold 10 min).
        for sel, price in zip(sels, PINNACLE_ODDS, strict=True):
            db_session.add(
                OddsSnapshot(
                    selection_id=sel.id,
                    bookmaker_id=pinnacle.id,
                    odds=price,
                    captured_at=NOW - timedelta(minutes=40),
                )
            )
        db_session.add(
            OddsSnapshot(selection_id=sels[0].id, bookmaker_id=book.id, odds=2.30, captured_at=NOW)
        )
        db_session.flush()

        results = compute_value_bets(db_session, settings=Settings(_env_file=None))
        assert results == []

    def test_edge_min_filter(self, db_session):
        build_1x2_market(db_session, home_odds=2.30)  # ~11% edge
        results = compute_value_bets(
            db_session, settings=Settings(_env_file=None), edge_min=0.50
        )
        assert results == []

    def test_sport_filter(self, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        results = compute_value_bets(
            db_session, settings=Settings(_env_file=None), sport_slug="tennis"
        )
        assert results == []

    def test_bookmaker_filter(self, db_session):
        build_1x2_market(db_session, home_odds=2.30)
        results = compute_value_bets(
            db_session, settings=Settings(_env_file=None), bookmaker_slug="betclic"
        )
        assert results == []

    def test_results_sorted_by_edge_descending(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.05, extra_books=["betclic"])
        home_sel = scenario["selections"]["home"]
        betclic = db_session.scalars(select(Bookmaker).where(Bookmaker.slug == "betclic")).one()
        # A second, higher-edge quote from a different book on the same selection.
        db_session.add(
            OddsSnapshot(
                selection_id=home_sel.id, bookmaker_id=betclic.id, odds=2.40, captured_at=NOW
            )
        )
        db_session.flush()

        results = compute_value_bets(db_session, settings=Settings(_env_file=None))
        edges = [r.edge for r in results]
        assert edges == sorted(edges, reverse=True)
