from datetime import timedelta

import pytest

from app.core.calculations import devig_multiplicative
from app.core.calculations import edge as calc_edge
from app.core.calculations import fair_odds as calc_fair_odds
from app.core.calculations import kelly_stake as calc_kelly_stake
from app.core.config import Settings
from app.models.bankroll import Bankroll
from app.models.bookmakers import Bookmaker
from app.models.enums import BetStatus
from app.models.odds import OddsSnapshot
from app.services.paper_bets import (
    PaperBettingError,
    get_or_create_default_bankroll,
    list_paper_bets,
    place_paper_bet,
    reset_bankroll,
    settle_paper_bet,
    update_bankroll,
)
from tests.test_value_bets import NOW, PINNACLE_ODDS, build_1x2_market

SETTINGS = Settings(_env_file=None)


class TestPlacePaperBet:
    def test_freezes_expected_values_and_debits_bankroll(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        home_sel = scenario["selections"]["home"]
        bankroll = get_or_create_default_bankroll(db_session, settings=SETTINGS)
        starting_balance = float(bankroll.current_balance)

        bet = place_paper_bet(
            db_session, selection_id=home_sel.id, bookmaker_slug="winamax_fr", settings=SETTINGS
        )

        expected_true_prob = devig_multiplicative(PINNACLE_ODDS)[0]
        expected_edge = calc_edge(expected_true_prob, 2.30)
        expected_fair = calc_fair_odds(expected_true_prob)
        expected_stake = calc_kelly_stake(expected_true_prob, 2.30, starting_balance)

        # DB columns round to their declared scale (odds/fair_odds to 3dp,
        # probability to 6dp, edge to 5dp) -- compare with matching tolerances
        # rather than the tight float precision the raw calculation gives.
        assert float(bet.odds_taken) == pytest.approx(2.30, abs=1e-3)
        assert float(bet.true_probability_at_placement) == pytest.approx(
            expected_true_prob, abs=1e-6
        )
        assert float(bet.fair_odds_at_placement) == pytest.approx(expected_fair, abs=1e-3)
        assert float(bet.edge_at_placement) == pytest.approx(expected_edge, abs=1e-5)
        assert float(bet.stake) == pytest.approx(expected_stake)
        assert bet.status == BetStatus.PENDING
        assert bet.bankroll_id == bankroll.id

        db_session.refresh(bankroll)
        assert float(bankroll.current_balance) == pytest.approx(starting_balance - expected_stake)

    def test_rejects_unknown_bookmaker(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        home_sel = scenario["selections"]["home"]
        with pytest.raises(PaperBettingError):
            place_paper_bet(
                db_session, selection_id=home_sel.id, bookmaker_slug="nope", settings=SETTINGS
            )

    def test_rejects_non_anj_bookmaker(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        home_sel = scenario["selections"]["home"]
        with pytest.raises(PaperBettingError):
            place_paper_bet(
                db_session, selection_id=home_sel.id, bookmaker_slug="pinnacle", settings=SETTINGS
            )

    def test_rejects_insufficient_edge(self, db_session):
        # home_odds close to fair (~2.07) keeps edge below the 3% default threshold.
        scenario = build_1x2_market(db_session, home_odds=2.10)
        home_sel = scenario["selections"]["home"]
        with pytest.raises(PaperBettingError):
            place_paper_bet(
                db_session, selection_id=home_sel.id, bookmaker_slug="winamax_fr", settings=SETTINGS
            )

    def test_rejects_stale_book_quote(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        home_sel = scenario["selections"]["home"]
        winamax = db_session.query(Bookmaker).filter_by(slug="winamax_fr").one()
        stale_snap = (
            db_session.query(OddsSnapshot)
            .filter_by(bookmaker_id=winamax.id, selection_id=home_sel.id)
            .one()
        )
        stale_snap.captured_at = NOW - timedelta(minutes=60)
        db_session.flush()
        with pytest.raises(PaperBettingError):
            place_paper_bet(
                db_session, selection_id=home_sel.id, bookmaker_slug="winamax_fr", settings=SETTINGS
            )

    def test_rejects_incomplete_sharp_coverage(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        pinnacle = scenario["bookmakers"]["pinnacle"]
        away_id = scenario["selections"]["away"].id
        snap = (
            db_session.query(OddsSnapshot)
            .filter_by(bookmaker_id=pinnacle.id, selection_id=away_id)
            .one()
        )
        db_session.delete(snap)
        db_session.flush()
        home_sel = scenario["selections"]["home"]
        with pytest.raises(PaperBettingError):
            place_paper_bet(
                db_session, selection_id=home_sel.id, bookmaker_slug="winamax_fr", settings=SETTINGS
            )


def _place_bet(db_session, home_odds=2.30):
    scenario = build_1x2_market(db_session, home_odds=home_odds)
    home_sel = scenario["selections"]["home"]
    return place_paper_bet(
        db_session, selection_id=home_sel.id, bookmaker_slug="winamax_fr", settings=SETTINGS
    )


class TestSettlePaperBet:
    def test_won_credits_stake_times_odds(self, db_session):
        bet = _place_bet(db_session)
        bankroll = db_session.get(Bankroll, bet.bankroll_id)
        balance_after_placement = float(bankroll.current_balance)
        stake, odds_taken = float(bet.stake), float(bet.odds_taken)

        settled = settle_paper_bet(db_session, bet_id=bet.id, status=BetStatus.WON)

        assert settled.status == BetStatus.WON
        expected_payout = stake * odds_taken
        assert float(settled.payout) == pytest.approx(expected_payout)
        db_session.refresh(bankroll)
        assert float(bankroll.current_balance) == pytest.approx(
            balance_after_placement + expected_payout
        )

    def test_lost_pays_nothing(self, db_session):
        bet = _place_bet(db_session)
        bankroll = db_session.get(Bankroll, bet.bankroll_id)
        balance_after_placement = float(bankroll.current_balance)

        settled = settle_paper_bet(db_session, bet_id=bet.id, status=BetStatus.LOST)

        assert float(settled.payout) == pytest.approx(0.0)
        db_session.refresh(bankroll)
        assert float(bankroll.current_balance) == pytest.approx(balance_after_placement)

    def test_push_refunds_stake(self, db_session):
        bet = _place_bet(db_session)
        bankroll = db_session.get(Bankroll, bet.bankroll_id)
        balance_after_placement = float(bankroll.current_balance)
        stake = float(bet.stake)

        settled = settle_paper_bet(db_session, bet_id=bet.id, status=BetStatus.PUSH)

        assert float(settled.payout) == pytest.approx(stake)
        db_session.refresh(bankroll)
        assert float(bankroll.current_balance) == pytest.approx(balance_after_placement + stake)

    def test_void_refunds_stake(self, db_session):
        bet = _place_bet(db_session)
        settled = settle_paper_bet(db_session, bet_id=bet.id, status=BetStatus.VOID)
        assert float(settled.payout) == pytest.approx(float(bet.stake))

    def test_cannot_settle_twice(self, db_session):
        bet = _place_bet(db_session)
        settle_paper_bet(db_session, bet_id=bet.id, status=BetStatus.WON)
        with pytest.raises(PaperBettingError):
            settle_paper_bet(db_session, bet_id=bet.id, status=BetStatus.LOST)

    def test_settle_unknown_bet_raises(self, db_session):
        with pytest.raises(PaperBettingError):
            settle_paper_bet(db_session, bet_id=999, status=BetStatus.WON)


class TestBankroll:
    def test_get_or_create_is_idempotent(self, db_session):
        first = get_or_create_default_bankroll(db_session, settings=SETTINGS)
        second = get_or_create_default_bankroll(db_session, settings=SETTINGS)
        assert first.id == second.id
        assert db_session.query(Bankroll).count() == 1

    def test_update_initial_balance_preserves_pl_delta(self, db_session):
        bankroll = get_or_create_default_bankroll(db_session, settings=SETTINGS)
        bankroll.current_balance = 900.0  # simulate an in-progress loss
        db_session.flush()

        updated = update_bankroll(db_session, bankroll, initial_balance=2000.0)

        # initial_balance 1000 -> 2000 (+1000 delta); current shifts by the same delta.
        assert float(updated.initial_balance) == pytest.approx(2000.0)
        assert float(updated.current_balance) == pytest.approx(1900.0)

    def test_reset_restores_current_to_initial(self, db_session):
        bankroll = get_or_create_default_bankroll(db_session, settings=SETTINGS)
        bankroll.current_balance = 500.0
        db_session.flush()

        reset = reset_bankroll(db_session, bankroll)
        assert float(reset.current_balance) == pytest.approx(float(reset.initial_balance))

    def test_negative_initial_balance_rejected(self, db_session):
        bankroll = get_or_create_default_bankroll(db_session, settings=SETTINGS)
        with pytest.raises(PaperBettingError):
            update_bankroll(db_session, bankroll, initial_balance=-10.0)


class TestListPaperBets:
    def test_lists_and_filters_by_status(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30, extra_books=["betclic"])
        home_sel = scenario["selections"]["home"]
        away_sel = scenario["selections"]["away"]
        bet1 = place_paper_bet(
            db_session, selection_id=home_sel.id, bookmaker_slug="winamax_fr", settings=SETTINGS
        )
        betclic = db_session.query(Bookmaker).filter_by(slug="betclic").one()
        db_session.add(
            OddsSnapshot(
                selection_id=away_sel.id, bookmaker_id=betclic.id, odds=4.60, captured_at=NOW
            )
        )
        db_session.flush()
        bet2 = place_paper_bet(
            db_session, selection_id=away_sel.id, bookmaker_slug="betclic", settings=SETTINGS
        )

        settle_paper_bet(db_session, bet_id=bet1.id, status=BetStatus.WON)

        assert len(list_paper_bets(db_session)) == 2

        pending = list_paper_bets(db_session, status=BetStatus.PENDING)
        assert [b.id for b in pending] == [bet2.id]

        won = list_paper_bets(db_session, status=BetStatus.WON)
        assert [b.id for b in won] == [bet1.id]
        assert won[0].home_name == "Arsenal"
        assert won[0].bookmaker_slug == "winamax_fr"
