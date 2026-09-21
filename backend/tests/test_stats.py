
import pytest

from app.core.config import Settings
from app.core.statistics import max_drawdown
from app.models.enums import BetStatus
from app.services.paper_bets import (
    get_or_create_default_bankroll,
    place_paper_bet,
    settle_paper_bet,
)
from app.services.stats import compute_stats
from tests.test_value_bets import build_1x2_market

SETTINGS = Settings(_env_file=None)


class TestComputeStatsEmpty:
    def test_no_bets_yields_empty_summary(self, db_session):
        get_or_create_default_bankroll(db_session, settings=SETTINGS)
        summary = compute_stats(db_session, settings=SETTINGS)

        assert summary.total_bets == 0
        assert summary.pending_bets == 0
        assert summary.graded_bets == 0
        assert summary.roi is None
        assert summary.win_rate is None
        assert summary.average_clv is None
        assert summary.max_drawdown_pct is None
        assert len(summary.bankroll_curve) == 1
        assert summary.bankroll_curve[0].label == "Départ"


def _place_and_settle(db_session, *, home_odds, outcome, home_book="winamax_fr"):
    scenario = build_1x2_market(db_session, home_odds=home_odds, home_book=home_book)
    bet = place_paper_bet(
        db_session,
        selection_id=scenario["selections"]["home"].id,
        bookmaker_slug=home_book,
        settings=SETTINGS,
    )
    settled = settle_paper_bet(db_session, bet_id=bet.id, status=outcome)
    return settled


class TestComputeStatsBasics:
    def test_win_and_loss_are_counted_and_win_rate_computed(self, db_session):
        get_or_create_default_bankroll(db_session, settings=SETTINGS)
        won = _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.WON, home_book="winamax_fr"
        )
        lost = _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.LOST, home_book="unibet_fr"
        )

        summary = compute_stats(db_session, settings=SETTINGS)

        assert summary.total_bets == 2
        assert summary.graded_bets == 2
        assert summary.wins == 1
        assert summary.losses == 1
        assert summary.win_rate == pytest.approx(0.5)
        assert summary.win_rate_ci is not None
        assert summary.win_rate_ci[0] <= 0.5 <= summary.win_rate_ci[1]

        expected_turnover = float(won.stake) + float(lost.stake)
        expected_profit = (float(won.payout) - float(won.stake)) + (
            float(lost.payout) - float(lost.stake)
        )
        assert summary.turnover == pytest.approx(expected_turnover)
        assert summary.profit == pytest.approx(expected_profit)
        assert summary.roi == pytest.approx(expected_profit / expected_turnover)

    def test_push_and_void_are_settled_but_excluded_from_win_rate(self, db_session):
        get_or_create_default_bankroll(db_session, settings=SETTINGS)
        _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.PUSH, home_book="winamax_fr"
        )
        _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.VOID, home_book="unibet_fr"
        )

        summary = compute_stats(db_session, settings=SETTINGS)

        assert summary.total_bets == 2
        assert summary.graded_bets == 0
        assert summary.win_rate is None
        assert summary.pushes == 1
        assert summary.voids == 1
        # Push/void bets refund the stake exactly -> zero net profit, but
        # their stake still counts as turnover.
        assert summary.profit == pytest.approx(0.0)
        assert summary.turnover > 0

    def test_pending_bets_are_not_settled(self, db_session):
        get_or_create_default_bankroll(db_session, settings=SETTINGS)
        scenario = build_1x2_market(db_session, home_odds=2.30)
        place_paper_bet(
            db_session,
            selection_id=scenario["selections"]["home"].id,
            bookmaker_slug="winamax_fr",
            settings=SETTINGS,
        )

        summary = compute_stats(db_session, settings=SETTINGS)

        assert summary.total_bets == 1
        assert summary.pending_bets == 1
        assert summary.graded_bets == 0
        assert summary.turnover == pytest.approx(0.0)


class TestBankrollCurveAndDrawdown:
    def test_curve_matches_running_balance_and_drawdown(self, db_session):
        bankroll = get_or_create_default_bankroll(db_session, settings=SETTINGS)
        initial = float(bankroll.initial_balance)

        won = _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.WON, home_book="winamax_fr"
        )
        lost = _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.LOST, home_book="unibet_fr"
        )

        summary = compute_stats(db_session, settings=SETTINGS)

        assert len(summary.bankroll_curve) == 3  # start + 2 settled bets
        assert summary.bankroll_curve[0].balance == pytest.approx(initial)

        after_win = initial + (float(won.payout) - float(won.stake))
        after_loss = after_win + (float(lost.payout) - float(lost.stake))
        balances = [p.balance for p in summary.bankroll_curve]
        assert balances[1] == pytest.approx(after_win)
        assert balances[2] == pytest.approx(after_loss)

        assert summary.max_drawdown_pct == pytest.approx(max_drawdown(balances))


class TestGroupBreakdowns:
    def test_groups_by_bookmaker_sport_and_market(self, db_session):
        get_or_create_default_bankroll(db_session, settings=SETTINGS)
        _place_and_settle(db_session, home_odds=2.30, outcome=BetStatus.WON, home_book="winamax_fr")
        _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.LOST, home_book="unibet_fr"
        )

        summary = compute_stats(db_session, settings=SETTINGS)

        book_keys = {g.key for g in summary.by_bookmaker}
        assert book_keys == {"winamax_fr", "unibet_fr"}
        assert all(g.bets == 1 for g in summary.by_bookmaker)

        sport_keys = {g.key for g in summary.by_sport}
        assert sport_keys == {"soccer"}
        assert next(g for g in summary.by_sport if g.key == "soccer").bets == 2

        market_keys = {g.key for g in summary.by_market}
        assert market_keys == {"1x2"}


class TestClvStatistics:
    def test_average_clv_and_confidence_interval(self, db_session):
        get_or_create_default_bankroll(db_session, settings=SETTINGS)
        bet1 = _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.WON, home_book="winamax_fr"
        )
        bet2 = _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.LOST, home_book="unibet_fr"
        )
        bet1.clv = 0.05
        bet2.clv = 0.03
        db_session.flush()

        summary = compute_stats(db_session, settings=SETTINGS)

        assert summary.clv_sample_size == 2
        assert summary.average_clv == pytest.approx(0.04)
        assert summary.average_clv_ci is not None
        assert summary.average_clv_ci[0] <= 0.04 <= summary.average_clv_ci[1]

    def test_no_clv_yet_gives_none(self, db_session):
        get_or_create_default_bankroll(db_session, settings=SETTINGS)
        scenario = build_1x2_market(db_session, home_odds=2.30)
        place_paper_bet(
            db_session,
            selection_id=scenario["selections"]["home"].id,
            bookmaker_slug="winamax_fr",
            settings=SETTINGS,
        )

        summary = compute_stats(db_session, settings=SETTINGS)
        assert summary.average_clv is None
        assert summary.clv_sample_size == 0


class TestMonthlyLossLimit:
    def test_limit_not_set_never_triggers(self, db_session):
        get_or_create_default_bankroll(db_session, settings=SETTINGS)
        _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.LOST, home_book="winamax_fr"
        )

        summary = compute_stats(db_session, settings=SETTINGS)
        assert summary.monthly_loss_limit is None
        assert summary.monthly_loss_limit_reached is False

    def test_limit_reached_when_monthly_loss_exceeds_it(self, db_session):
        get_or_create_default_bankroll(db_session, settings=SETTINGS)
        bet = _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.LOST, home_book="winamax_fr"
        )
        stake = float(bet.stake)

        tight_limit_settings = SETTINGS.model_copy(update={"monthly_loss_limit": stake / 2})
        summary = compute_stats(db_session, settings=tight_limit_settings)

        assert summary.monthly_loss_limit == pytest.approx(stake / 2)
        assert summary.monthly_loss_limit_reached is True

    def test_limit_not_reached_when_loss_is_smaller(self, db_session):
        get_or_create_default_bankroll(db_session, settings=SETTINGS)
        bet = _place_and_settle(
            db_session, home_odds=2.30, outcome=BetStatus.LOST, home_book="winamax_fr"
        )
        stake = float(bet.stake)

        loose_limit_settings = SETTINGS.model_copy(update={"monthly_loss_limit": stake * 10})
        summary = compute_stats(db_session, settings=loose_limit_settings)

        assert summary.monthly_loss_limit_reached is False
