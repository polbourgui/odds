from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.enums import MarketType, SelectionCode
from app.models.events import Event
from app.models.markets import EventMarket, Selection
from app.models.participants import Participant, ParticipantAlias
from app.models.sports import Competition, Sport
from app.providers.base import ProviderEvent
from app.services.reconciliation import EventReconciler

KICKOFF = datetime(2026, 3, 1, 20, 0, tzinfo=UTC)


def make_provider_event(
    provider_event_id="evt-1",
    sport_key="soccer_epl",
    competition_name="EPL",
    home_name="Arsenal",
    away_name="Chelsea",
    start_time=KICKOFF,
) -> ProviderEvent:
    return ProviderEvent(
        provider_event_id=provider_event_id,
        sport_key=sport_key,
        competition_name=competition_name,
        home_name=home_name,
        away_name=away_name,
        start_time=start_time,
    )


class TestResolveSport:
    def test_derives_slug_from_provider_sport_key_prefix(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        sport = reconciler.resolve_sport("soccer_epl")
        assert sport.slug == "soccer"

    def test_reuses_existing_sport(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        a = reconciler.resolve_sport("soccer_epl")
        b = reconciler.resolve_sport("soccer_france_ligue_one")
        assert a.id == b.id
        assert db_session.query(Sport).count() == 1


class TestResolveParticipant:
    def test_second_call_with_same_raw_name_hits_alias(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        sport = reconciler.resolve_sport("soccer_epl")

        first = reconciler.resolve_participant(sport, "Arsenal")
        second = reconciler.resolve_participant(sport, "Arsenal")

        assert first.id == second.id
        assert db_session.query(Participant).count() == 1
        assert db_session.query(ParticipantAlias).count() == 1

    def test_exact_normalized_match_avoids_duplicate_across_providers(self, db_session):
        reconciler_a = EventReconciler(db_session, provider_name="provider_a")
        reconciler_b = EventReconciler(db_session, provider_name="provider_b")
        sport = reconciler_a.resolve_sport("soccer_epl")

        canonical = reconciler_a.resolve_participant(sport, "Arsenal FC")
        matched = reconciler_b.resolve_participant(sport, "Arsenal")

        assert canonical.id == matched.id
        assert db_session.query(Participant).count() == 1
        # Both providers now have their own alias row pointing at the same participant.
        assert db_session.query(ParticipantAlias).count() == 2

    def test_fuzzy_match_above_threshold_reuses_participant(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api", fuzzy_threshold=0.88)
        sport = reconciler.resolve_sport("soccer_epl")

        canonical = reconciler.resolve_participant(sport, "Manchester United")
        matched = reconciler.resolve_participant(sport, "Manchester Utd")

        assert canonical.id == matched.id
        assert db_session.query(Participant).count() == 1

    def test_dissimilar_names_create_distinct_participants(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api", fuzzy_threshold=0.88)
        sport = reconciler.resolve_sport("soccer_la_liga")

        real_madrid = reconciler.resolve_participant(sport, "Real Madrid")
        real_sociedad = reconciler.resolve_participant(sport, "Real Sociedad")

        assert real_madrid.id != real_sociedad.id
        assert db_session.query(Participant).count() == 2

    def test_matching_is_scoped_to_sport(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        soccer = reconciler.resolve_sport("soccer_epl")
        basketball = reconciler.resolve_sport("basketball_nba")

        soccer_team = reconciler.resolve_participant(soccer, "Miami")
        basketball_team = reconciler.resolve_participant(basketball, "Miami")

        assert soccer_team.id != basketball_team.id


class TestResolveCompetition:
    def test_alias_and_normalized_match_avoid_duplicates(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        sport = reconciler.resolve_sport("soccer_epl")

        first = reconciler.resolve_competition(sport, "Premier League")
        second = reconciler.resolve_competition(sport, "Premier League")
        third = reconciler.resolve_competition(sport, "premier league")  # normalized match

        assert first.id == second.id == third.id
        assert db_session.query(Competition).count() == 1


class TestResolveEvent:
    def test_same_provider_event_id_returns_same_event(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        pe = make_provider_event()

        first = reconciler.resolve_event(pe)
        second = reconciler.resolve_event(pe)

        assert first.id == second.id
        assert db_session.query(Event).count() == 1

    def test_composite_match_reconciles_across_providers(self, db_session):
        reconciler_a = EventReconciler(db_session, provider_name="provider_a")
        reconciler_b = EventReconciler(db_session, provider_name="provider_b")

        event_a = reconciler_a.resolve_event(
            make_provider_event(provider_event_id="a-1", home_name="Arsenal", away_name="Chelsea")
        )
        # Different provider, different id, near-identical fixture (small kickoff drift).
        event_b = reconciler_b.resolve_event(
            make_provider_event(
                provider_event_id="b-1",
                home_name="Arsenal",
                away_name="Chelsea",
                start_time=KICKOFF + timedelta(minutes=15),
            )
        )

        assert event_a.id == event_b.id
        assert db_session.query(Event).count() == 1

    def test_far_apart_kickoff_times_create_distinct_events(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")

        event_1 = reconciler.resolve_event(
            make_provider_event(provider_event_id="e1", start_time=KICKOFF)
        )
        event_2 = reconciler.resolve_event(
            make_provider_event(
                provider_event_id="e2", start_time=KICKOFF + timedelta(days=7)
            )
        )

        assert event_1.id != event_2.id
        assert db_session.query(Event).count() == 2


class TestResolveSelection:
    def test_repeated_resolution_reuses_market_and_selection(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        sport = reconciler.resolve_sport("soccer_epl")
        event = reconciler.resolve_event(make_provider_event())

        first = reconciler.resolve_selection(
            event, sport, MarketType.ONE_X_TWO, SelectionCode.HOME
        )
        second = reconciler.resolve_selection(
            event, sport, MarketType.ONE_X_TWO, SelectionCode.HOME
        )

        assert first.id == second.id
        assert db_session.query(EventMarket).count() == 1
        assert db_session.query(Selection).count() == 1

    def test_over_under_selections_are_scoped_by_line(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        sport = reconciler.resolve_sport("soccer_epl")
        event = reconciler.resolve_event(make_provider_event())

        over_25 = reconciler.resolve_selection(
            event, sport, MarketType.OVER_UNDER, SelectionCode.OVER, line=2.5
        )
        over_35 = reconciler.resolve_selection(
            event, sport, MarketType.OVER_UNDER, SelectionCode.OVER, line=3.5
        )

        assert over_25.id != over_35.id
        assert db_session.query(EventMarket).count() == 2

    def test_participant_win_selection_resolves_participant(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        sport = reconciler.resolve_sport("tennis_atp")
        event = reconciler.resolve_event(
            make_provider_event(
                sport_key="tennis_atp",
                competition_name="ATP Masters",
                home_name="Novak Djokovic",
                away_name="Carlos Alcaraz",
            )
        )

        selection = reconciler.resolve_selection(
            event,
            sport,
            MarketType.MONEYLINE,
            SelectionCode.PARTICIPANT_WIN,
            participant_name="Novak Djokovic",
        )

        assert selection.participant is not None
        assert selection.participant.name == "Novak Djokovic"

    def test_participant_win_without_name_raises(self, db_session):
        reconciler = EventReconciler(db_session, provider_name="the_odds_api")
        sport = reconciler.resolve_sport("tennis_atp")
        event = reconciler.resolve_event(
            make_provider_event(sport_key="tennis_atp", home_name="A", away_name="B")
        )

        try:
            reconciler.resolve_selection(
                event, sport, MarketType.MONEYLINE, SelectionCode.PARTICIPANT_WIN
            )
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")


def test_alias_table_is_editable_and_takes_priority(db_session):
    """An operator can hand-correct a bad match by editing the alias row;
    the next resolution for that raw name must honor the new mapping."""
    reconciler = EventReconciler(db_session, provider_name="the_odds_api")
    sport = reconciler.resolve_sport("soccer_epl")

    wrong = reconciler.resolve_participant(sport, "PSG")
    correct = Participant(
        sport_id=sport.id, name="Paris Saint-Germain", normalized_name="paris germain"
    )
    db_session.add(correct)
    db_session.flush()

    alias = db_session.scalar(
        select(ParticipantAlias).where(
            ParticipantAlias.provider == "the_odds_api", ParticipantAlias.raw_name == "PSG"
        )
    )
    alias.participant_id = correct.id
    db_session.flush()

    resolved_again = reconciler.resolve_participant(sport, "PSG")
    assert resolved_again.id == correct.id
    assert resolved_again.id != wrong.id
