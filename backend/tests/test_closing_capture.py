from datetime import UTC, datetime, timedelta

import pytest

from app.core.calculations import clv as calc_clv
from app.core.calculations import devig_multiplicative
from app.core.calculations import fair_odds as calc_fair_odds
from app.core.config import Settings
from app.models.events import Event
from app.models.odds import OddsSnapshot
from app.services.closing_capture import run_closing_capture
from app.services.paper_bets import place_paper_bet
from tests.test_value_bets import build_1x2_market

SETTINGS = Settings(_env_file=None)

PAST_KICKOFF = datetime.now(UTC) - timedelta(hours=2)
# The sharp reference's line right at kickoff -- deliberately different from
# PINNACLE_ODDS (the "current" odds build_1x2_market seeds) so tests can
# tell which snapshot a computed closing value actually came from.
CLOSING_ODDS = [1.90, 3.60, 4.20]


def _setup_past_event_with_bet(db_session, *, add_closing_snapshots=True):
    """A 1X2 market with a placed bet, whose event kicked off 2h ago. The
    sharp reference's genuine pre-kickoff closing snapshots (dated just
    before kickoff) are added unless the caller wants to set those up
    itself -- the odds build_1x2_market seeds are stamped "now", which
    after moving start_time into the past becomes in-play data, not a
    valid closing line.
    """
    scenario = build_1x2_market(db_session, home_odds=2.30)
    event = scenario["event"]

    bet = place_paper_bet(
        db_session,
        selection_id=scenario["selections"]["home"].id,
        bookmaker_slug="winamax_fr",
        settings=SETTINGS,
    )

    event.start_time = PAST_KICKOFF
    db_session.flush()

    if add_closing_snapshots:
        pinnacle = scenario["bookmakers"]["pinnacle"]
        sels = scenario["selections"]
        for sel, price in zip(
            [sels["home"], sels["draw"], sels["away"]], CLOSING_ODDS, strict=True
        ):
            db_session.add(
                OddsSnapshot(
                    selection_id=sel.id,
                    bookmaker_id=pinnacle.id,
                    odds=price,
                    captured_at=PAST_KICKOFF - timedelta(minutes=1),
                )
            )
        db_session.flush()

    return scenario, bet


class TestRunClosingCapture:
    def test_backfills_closing_odds_and_clv_for_past_event(self, db_session):
        _scenario, bet = _setup_past_event_with_bet(db_session)

        updated = run_closing_capture(db_session, settings=SETTINGS)
        assert updated == 1

        db_session.refresh(bet)
        expected_fair_close = calc_fair_odds(devig_multiplicative(CLOSING_ODDS)[0])
        assert float(bet.closing_odds) == pytest.approx(expected_fair_close, abs=1e-3)
        expected_clv = calc_clv(float(bet.odds_taken), expected_fair_close)
        assert float(bet.clv) == pytest.approx(expected_clv, abs=1e-4)

    def test_marks_the_closing_sharp_snapshot(self, db_session):
        scenario, _bet = _setup_past_event_with_bet(db_session)
        pinnacle = scenario["bookmakers"]["pinnacle"]
        home_sel = scenario["selections"]["home"]

        run_closing_capture(db_session, settings=SETTINGS)

        closing_snapshot = (
            db_session.query(OddsSnapshot)
            .filter_by(bookmaker_id=pinnacle.id, selection_id=home_sel.id, odds=CLOSING_ODDS[0])
            .one()
        )
        assert closing_snapshot.is_closing is True

        # The original (pre-placement, "now") snapshot is in-play data, not
        # the closing line, and must be left untouched.
        live_snapshot = (
            db_session.query(OddsSnapshot)
            .filter_by(bookmaker_id=pinnacle.id, selection_id=home_sel.id, odds=2.00)
            .one()
        )
        assert live_snapshot.is_closing is False

    def test_future_event_is_not_captured(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)  # start_time in the future
        bet = place_paper_bet(
            db_session,
            selection_id=scenario["selections"]["home"].id,
            bookmaker_slug="winamax_fr",
            settings=SETTINGS,
        )

        updated = run_closing_capture(db_session, settings=SETTINGS)

        assert updated == 0
        db_session.refresh(bet)
        assert bet.closing_odds is None
        assert bet.clv is None

    def test_incomplete_sharp_coverage_at_close_leaves_bet_unset(self, db_session):
        scenario, bet = _setup_past_event_with_bet(db_session, add_closing_snapshots=False)
        pinnacle = scenario["bookmakers"]["pinnacle"]
        # Only the home selection gets a pre-kickoff closing price; draw/away don't.
        db_session.add(
            OddsSnapshot(
                selection_id=scenario["selections"]["home"].id,
                bookmaker_id=pinnacle.id,
                odds=1.90,
                captured_at=PAST_KICKOFF - timedelta(minutes=1),
            )
        )
        db_session.flush()

        updated = run_closing_capture(db_session, settings=SETTINGS)

        assert updated == 0
        db_session.refresh(bet)
        assert bet.closing_odds is None

    def test_is_idempotent(self, db_session):
        _scenario, _bet = _setup_past_event_with_bet(db_session)

        first_run = run_closing_capture(db_session, settings=SETTINGS)
        second_run = run_closing_capture(db_session, settings=SETTINGS)

        assert first_run == 1
        assert second_run == 0

    def test_ignores_snapshots_captured_after_kickoff(self, db_session):
        scenario, bet = _setup_past_event_with_bet(db_session)
        pinnacle = scenario["bookmakers"]["pinnacle"]
        # A snapshot AFTER kickoff shouldn't be treated as the closing price.
        for sel in (scenario["selections"][k] for k in ("home", "draw", "away")):
            db_session.add(
                OddsSnapshot(
                    selection_id=sel.id,
                    bookmaker_id=pinnacle.id,
                    odds=9.99,
                    captured_at=PAST_KICKOFF + timedelta(minutes=5),
                )
            )
        db_session.flush()

        run_closing_capture(db_session, settings=SETTINGS)

        db_session.refresh(bet)
        # Still the genuine pre-kickoff closing line, not the 9.99 in-play price.
        expected_fair_close = calc_fair_odds(devig_multiplicative(CLOSING_ODDS)[0])
        assert float(bet.closing_odds) == pytest.approx(expected_fair_close, abs=1e-3)

    def test_only_touches_events_referenced_by_pending_paper_bets(self, db_session):
        # An event with no paper bets shouldn't be scanned/processed at all.
        scenario = build_1x2_market(db_session, home_odds=2.30)
        event = scenario["event"]
        event.start_time = PAST_KICKOFF
        db_session.flush()

        updated = run_closing_capture(db_session, settings=SETTINGS)
        assert updated == 0
        assert db_session.get(Event, event.id) is not None  # sanity: event still exists, untouched
