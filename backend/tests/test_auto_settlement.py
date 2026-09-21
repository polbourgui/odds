from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.models.bankroll import PaperBet
from app.models.bookmakers import Bookmaker
from app.models.enums import BetStatus, MarketType, SelectionCode
from app.models.events import Event
from app.models.markets import EventMarket, Selection
from app.models.odds import OddsSnapshot
from app.models.participants import Participant
from app.providers.base import ProviderResult, ResultsProvider
from app.services.auto_settlement import determine_outcome, run_auto_settlement
from app.services.paper_bets import place_paper_bet
from tests.test_value_bets import build_1x2_market

SETTINGS = Settings(_env_file=None)
PAST_KICKOFF = datetime.now(UTC) - timedelta(hours=3)


class FakeResultsProvider(ResultsProvider):
    name = "fake_results"

    def __init__(self, results: list[ProviderResult]):
        self._results = results
        self.fetch_calls: list[tuple[str, list[str] | None]] = []

    def fetch_results(
        self, sport_key: str, event_ids: list[str] | None = None
    ) -> list[ProviderResult]:
        self.fetch_calls.append((sport_key, event_ids))
        return self._results


class TestDetermineOutcome:
    def test_1x2_home_win(self):
        assert determine_outcome(MarketType.ONE_X_TWO, SelectionCode.HOME, 2, 1) == BetStatus.WON
        assert determine_outcome(MarketType.ONE_X_TWO, SelectionCode.AWAY, 2, 1) == BetStatus.LOST
        assert determine_outcome(MarketType.ONE_X_TWO, SelectionCode.DRAW, 2, 1) == BetStatus.LOST

    def test_1x2_away_win(self):
        assert determine_outcome(MarketType.ONE_X_TWO, SelectionCode.AWAY, 0, 3) == BetStatus.WON
        assert determine_outcome(MarketType.ONE_X_TWO, SelectionCode.HOME, 0, 3) == BetStatus.LOST

    def test_1x2_draw(self):
        assert determine_outcome(MarketType.ONE_X_TWO, SelectionCode.DRAW, 1, 1) == BetStatus.WON
        assert determine_outcome(MarketType.ONE_X_TWO, SelectionCode.HOME, 1, 1) == BetStatus.LOST

    def test_moneyline_home_participant_wins(self):
        status = determine_outcome(
            MarketType.MONEYLINE,
            SelectionCode.PARTICIPANT_WIN,
            2,
            1,
            is_home_participant=True,
        )
        assert status == BetStatus.WON

    def test_moneyline_away_participant_loses(self):
        status = determine_outcome(
            MarketType.MONEYLINE,
            SelectionCode.PARTICIPANT_WIN,
            2,
            1,
            is_home_participant=False,
        )
        assert status == BetStatus.LOST

    def test_moneyline_tie_is_undetermined(self):
        status = determine_outcome(
            MarketType.MONEYLINE,
            SelectionCode.PARTICIPANT_WIN,
            1,
            1,
            is_home_participant=True,
        )
        assert status is None

    def test_moneyline_without_is_home_participant_is_undetermined(self):
        status = determine_outcome(MarketType.MONEYLINE, SelectionCode.PARTICIPANT_WIN, 2, 1)
        assert status is None

    def test_over_under_over_wins(self):
        assert determine_outcome(
            MarketType.OVER_UNDER, SelectionCode.OVER, 2, 1, line=2.5
        ) == BetStatus.WON
        assert determine_outcome(
            MarketType.OVER_UNDER, SelectionCode.UNDER, 2, 1, line=2.5
        ) == BetStatus.LOST

    def test_over_under_under_wins(self):
        assert determine_outcome(
            MarketType.OVER_UNDER, SelectionCode.UNDER, 1, 0, line=2.5
        ) == BetStatus.WON
        assert determine_outcome(
            MarketType.OVER_UNDER, SelectionCode.OVER, 1, 0, line=2.5
        ) == BetStatus.LOST

    def test_over_under_exact_push(self):
        assert determine_outcome(
            MarketType.OVER_UNDER, SelectionCode.OVER, 2, 1, line=3.0
        ) == BetStatus.PUSH
        assert determine_outcome(
            MarketType.OVER_UNDER, SelectionCode.UNDER, 2, 1, line=3.0
        ) == BetStatus.PUSH

    def test_over_under_without_line_is_undetermined(self):
        assert determine_outcome(MarketType.OVER_UNDER, SelectionCode.OVER, 2, 1) is None


def _snap(selection_id, bookmaker_id, odds, captured_at):
    return OddsSnapshot(
        selection_id=selection_id, bookmaker_id=bookmaker_id, odds=odds, captured_at=captured_at
    )


def _place_bet_on_past_event(db_session, *, provider_sport_key="soccer_epl", home_odds=2.30):
    scenario = build_1x2_market(db_session, home_odds=home_odds)
    bet = place_paper_bet(
        db_session,
        selection_id=scenario["selections"]["home"].id,
        bookmaker_slug="winamax_fr",
        settings=SETTINGS,
    )
    event = scenario["event"]
    event.start_time = PAST_KICKOFF
    event.competition.provider_sport_key = provider_sport_key
    db_session.flush()
    return scenario, bet


class TestRunAutoSettlement:
    def test_home_win_settles_bet_as_won_and_credits_bankroll(self, db_session):
        scenario, bet = _place_bet_on_past_event(db_session)
        bankroll = bet.bankroll
        balance_before = float(bankroll.current_balance)
        stake, odds_taken = float(bet.stake), float(bet.odds_taken)

        provider = FakeResultsProvider(
            [ProviderResult(provider_event_id=scenario["event"].external_ref, completed=True,
                             home_score=2, away_score=1)]
        )

        settled = run_auto_settlement(db_session, provider)

        assert settled == 1
        db_session.refresh(bet)
        assert bet.status == BetStatus.WON
        assert float(bet.payout) == pytest.approx(stake * odds_taken)
        db_session.refresh(bankroll)
        assert float(bankroll.current_balance) == pytest.approx(balance_before + stake * odds_taken)

    def test_away_win_settles_home_bet_as_lost(self, db_session):
        scenario, bet = _place_bet_on_past_event(db_session)
        provider = FakeResultsProvider(
            [ProviderResult(provider_event_id=scenario["event"].external_ref, completed=True,
                             home_score=0, away_score=2)]
        )

        settled = run_auto_settlement(db_session, provider)

        assert settled == 1
        db_session.refresh(bet)
        assert bet.status == BetStatus.LOST
        assert float(bet.payout) == pytest.approx(0.0)

    def test_incomplete_result_does_not_settle(self, db_session):
        scenario, bet = _place_bet_on_past_event(db_session)
        provider = FakeResultsProvider(
            [ProviderResult(provider_event_id=scenario["event"].external_ref, completed=False)]
        )

        settled = run_auto_settlement(db_session, provider)

        assert settled == 0
        db_session.refresh(bet)
        assert bet.status == BetStatus.PENDING

    def test_missing_result_does_not_settle(self, db_session):
        _scenario, bet = _place_bet_on_past_event(db_session)
        provider = FakeResultsProvider([])  # provider has nothing for this event yet

        settled = run_auto_settlement(db_session, provider)

        assert settled == 0
        db_session.refresh(bet)
        assert bet.status == BetStatus.PENDING

    def test_future_event_is_not_included(self, db_session):
        scenario = build_1x2_market(db_session, home_odds=2.30)
        bet = place_paper_bet(
            db_session,
            selection_id=scenario["selections"]["home"].id,
            bookmaker_slug="winamax_fr",
            settings=SETTINGS,
        )
        scenario["event"].competition.provider_sport_key = "soccer_epl"
        db_session.flush()

        provider = FakeResultsProvider([])
        settled = run_auto_settlement(db_session, provider)

        assert settled == 0
        assert provider.fetch_calls == []  # no sport_key had any qualifying event
        db_session.refresh(bet)
        assert bet.status == BetStatus.PENDING

    def test_missing_provider_sport_key_is_skipped(self, db_session):
        # provider_sport_key left as None (default from build_1x2_market)
        scenario = build_1x2_market(db_session, home_odds=2.30)
        bet = place_paper_bet(
            db_session,
            selection_id=scenario["selections"]["home"].id,
            bookmaker_slug="winamax_fr",
            settings=SETTINGS,
        )
        scenario["event"].start_time = PAST_KICKOFF
        db_session.flush()

        provider = FakeResultsProvider([])
        settled = run_auto_settlement(db_session, provider)

        assert settled == 0
        db_session.refresh(bet)
        assert bet.status == BetStatus.PENDING

    def test_fetches_results_scoped_to_the_events_own_sport_key(self, db_session):
        scenario, _bet = _place_bet_on_past_event(db_session, provider_sport_key="soccer_epl")
        provider = FakeResultsProvider(
            [ProviderResult(provider_event_id=scenario["event"].external_ref, completed=True,
                             home_score=1, away_score=0)]
        )

        run_auto_settlement(db_session, provider)

        assert len(provider.fetch_calls) == 1
        sport_key, event_ids = provider.fetch_calls[0]
        assert sport_key == "soccer_epl"
        assert event_ids == [scenario["event"].external_ref]

    def test_over_under_push_refunds_stake(self, db_session):
        scenario, _home_bet = _place_bet_on_past_event(db_session)
        event = scenario["event"]
        pinnacle = scenario["bookmakers"]["pinnacle"]
        winamax = db_session.query(Bookmaker).filter_by(slug="winamax_fr").one()

        totals_market = EventMarket(event_id=event.id, market_type=MarketType.OVER_UNDER, line=2.5)
        db_session.add(totals_market)
        db_session.flush()
        over_sel = Selection(event_market_id=totals_market.id, code=SelectionCode.OVER)
        under_sel = Selection(event_market_id=totals_market.id, code=SelectionCode.UNDER)
        db_session.add_all([over_sel, under_sel])
        db_session.flush()
        now = datetime.now(UTC)
        db_session.add_all(
            [
                _snap(over_sel.id, pinnacle.id, 1.90, now),
                _snap(under_sel.id, pinnacle.id, 1.95, now),
                _snap(over_sel.id, winamax.id, 2.05, now),
            ]
        )
        db_session.flush()

        over_bet = place_paper_bet(
            db_session, selection_id=over_sel.id, bookmaker_slug="winamax_fr", settings=SETTINGS
        )
        bankroll = over_bet.bankroll
        balance_before_settlement = float(bankroll.current_balance)
        stake = float(over_bet.stake)

        # Total == line exactly -> push, full stake refunded.
        provider = FakeResultsProvider(
            [
                ProviderResult(
                    provider_event_id=event.external_ref,
                    completed=True,
                    home_score=1,
                    away_score=1.5,
                )
            ]
        )
        settled = run_auto_settlement(db_session, provider)

        assert settled >= 1
        db_session.refresh(over_bet)
        assert over_bet.status == BetStatus.PUSH
        assert float(over_bet.payout) == pytest.approx(stake)
        db_session.refresh(bankroll)
        assert float(bankroll.current_balance) == pytest.approx(balance_before_settlement + stake)

    def test_moneyline_settles_by_participant_side(self, db_session):
        sport_key = "tennis_atp"
        from app.providers.base import ProviderEvent
        from app.services.reconciliation import EventReconciler

        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        event = reconciler.resolve_event(
            ProviderEvent(
                provider_event_id="tennis-evt-1",
                sport_key=sport_key,
                competition_name="ATP Masters",
                home_name="Novak Djokovic",
                away_name="Carlos Alcaraz",
                start_time=PAST_KICKOFF,
            )
        )
        event.competition.provider_sport_key = sport_key
        db_session.flush()

        pinnacle = Bookmaker(slug="pinnacle", name="Pinnacle", is_sharp_reference=True)
        winamax = Bookmaker(slug="winamax_fr", name="Winamax", is_anj_licensed=True)
        db_session.add_all([pinnacle, winamax])
        db_session.flush()

        home_participant = db_session.get(Participant, event.home_participant_id)
        away_participant = db_session.get(Participant, event.away_participant_id)

        market = EventMarket(event_id=event.id, market_type=MarketType.MONEYLINE)
        db_session.add(market)
        db_session.flush()
        home_sel = Selection(
            event_market_id=market.id,
            code=SelectionCode.PARTICIPANT_WIN,
            participant_id=home_participant.id,
        )
        away_sel = Selection(
            event_market_id=market.id,
            code=SelectionCode.PARTICIPANT_WIN,
            participant_id=away_participant.id,
        )
        db_session.add_all([home_sel, away_sel])
        db_session.flush()

        now = datetime.now(UTC)
        db_session.add_all(
            [
                _snap(home_sel.id, pinnacle.id, 1.75, now),
                _snap(away_sel.id, pinnacle.id, 2.15, now),
                _snap(away_sel.id, winamax.id, 2.30, now),
            ]
        )
        db_session.flush()

        away_bet = place_paper_bet(
            db_session, selection_id=away_sel.id, bookmaker_slug="winamax_fr", settings=SETTINGS
        )

        # Djokovic (home) wins 2 sets to 0 -> the away-side (Alcaraz) bet loses.
        provider = FakeResultsProvider(
            [
                ProviderResult(
                    provider_event_id="tennis-evt-1",
                    completed=True,
                    home_score=2,
                    away_score=0,
                )
            ]
        )
        settled = run_auto_settlement(db_session, provider)

        assert settled == 1
        db_session.refresh(away_bet)
        assert away_bet.status == BetStatus.LOST


def test_only_touches_events_with_pending_bets(db_session):
    scenario = build_1x2_market(db_session, home_odds=2.30)
    scenario["event"].start_time = PAST_KICKOFF
    scenario["event"].competition.provider_sport_key = "soccer_epl"
    db_session.flush()
    # No paper bet placed for this event at all.

    provider = FakeResultsProvider([])
    settled = run_auto_settlement(db_session, provider)

    assert settled == 0
    assert provider.fetch_calls == []
    assert db_session.get(Event, scenario["event"].id) is not None
    assert db_session.query(PaperBet).count() == 0
