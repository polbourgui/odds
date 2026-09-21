"""Cross-provider event/participant/competition reconciliation.

Matching order, cheapest and most precise first:
1. Editable alias table (`ParticipantAlias` / `CompetitionAlias`) — an exact
   hit on (provider, raw_name) recorded from a previous resolution or added
   by hand.
2. Exact match on the normalized name within the same sport.
3. Fuzzy match (difflib ratio) within the same sport, above a threshold.
4. Otherwise, create a new canonical row and record the alias for next time.

Events are matched by the provider's own event id first, then by
(competition, participants, start time within a tolerance window) to allow
future providers to reconcile onto the same event even without a shared id.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import MarketType, SelectionCode
from app.models.events import Event
from app.models.markets import EventMarket, Selection
from app.models.participants import CompetitionAlias, Participant, ParticipantAlias
from app.models.sports import Competition, Sport
from app.providers.base import ProviderEvent
from app.services.normalization import normalize_name, similarity

_EVENT_TIME_TOLERANCE = timedelta(hours=6)


class EventReconciler:
    def __init__(self, db: Session, provider_name: str, fuzzy_threshold: float = 0.88):
        self.db = db
        self.provider_name = provider_name
        self.fuzzy_threshold = fuzzy_threshold

    # -- Sport -----------------------------------------------------------

    def resolve_sport(self, sport_key: str) -> Sport:
        slug = sport_key.split("_")[0]
        sport = self.db.scalar(select(Sport).where(Sport.slug == slug))
        if sport is not None:
            return sport
        sport = Sport(slug=slug, name=slug.capitalize())
        self.db.add(sport)
        self.db.flush()
        return sport

    # -- Competition -------------------------------------------------------

    def resolve_competition(self, sport: Sport, raw_name: str) -> Competition:
        alias = self.db.scalar(
            select(CompetitionAlias).where(
                CompetitionAlias.provider == self.provider_name,
                CompetitionAlias.raw_name == raw_name,
            )
        )
        if alias is not None:
            return alias.competition

        normalized = normalize_name(raw_name)
        candidates = list(
            self.db.scalars(select(Competition).where(Competition.sport_id == sport.id))
        )

        for candidate in candidates:
            if normalize_name(candidate.name) == normalized:
                self._add_competition_alias(candidate, raw_name)
                return candidate

        best, best_score = self._best_fuzzy_match(
            normalized, candidates, key=lambda c: normalize_name(c.name)
        )
        if best is not None and best_score >= self.fuzzy_threshold:
            self._add_competition_alias(best, raw_name)
            return best

        competition = Competition(
            sport_id=sport.id,
            slug=self._unique_competition_slug(normalized or raw_name),
            name=raw_name,
        )
        self.db.add(competition)
        self.db.flush()
        self._add_competition_alias(competition, raw_name)
        return competition

    def _unique_competition_slug(self, normalized_name: str) -> str:
        base = normalized_name.replace(" ", "-") or "competition"
        slug = base
        suffix = 2
        while self.db.scalar(select(Competition).where(Competition.slug == slug)) is not None:
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug

    def _add_competition_alias(self, competition: Competition, raw_name: str) -> None:
        exists = self.db.scalar(
            select(CompetitionAlias).where(
                CompetitionAlias.provider == self.provider_name,
                CompetitionAlias.raw_name == raw_name,
            )
        )
        if exists is None:
            self.db.add(
                CompetitionAlias(
                    competition_id=competition.id, provider=self.provider_name, raw_name=raw_name
                )
            )

    # -- Participant ---------------------------------------------------------

    def resolve_participant(self, sport: Sport, raw_name: str) -> Participant:
        alias = self.db.scalar(
            select(ParticipantAlias).where(
                ParticipantAlias.provider == self.provider_name,
                ParticipantAlias.raw_name == raw_name,
                ParticipantAlias.sport_id == sport.id,
            )
        )
        if alias is not None:
            return alias.participant

        normalized = normalize_name(raw_name)
        candidates = list(
            self.db.scalars(select(Participant).where(Participant.sport_id == sport.id))
        )

        for candidate in candidates:
            if candidate.normalized_name == normalized:
                self._add_participant_alias(candidate, raw_name, sport)
                return candidate

        best, best_score = self._best_fuzzy_match(
            normalized, candidates, key=lambda p: p.normalized_name
        )
        if best is not None and best_score >= self.fuzzy_threshold:
            self._add_participant_alias(best, raw_name, sport)
            return best

        participant = Participant(sport_id=sport.id, name=raw_name, normalized_name=normalized)
        self.db.add(participant)
        self.db.flush()
        self._add_participant_alias(participant, raw_name, sport)
        return participant

    def _add_participant_alias(self, participant: Participant, raw_name: str, sport: Sport) -> None:
        exists = self.db.scalar(
            select(ParticipantAlias).where(
                ParticipantAlias.provider == self.provider_name,
                ParticipantAlias.raw_name == raw_name,
                ParticipantAlias.sport_id == sport.id,
            )
        )
        if exists is None:
            self.db.add(
                ParticipantAlias(
                    participant_id=participant.id,
                    sport_id=sport.id,
                    provider=self.provider_name,
                    raw_name=raw_name,
                )
            )

    # -- Event -----------------------------------------------------------

    def resolve_event(self, provider_event: ProviderEvent) -> Event:
        sport = self.resolve_sport(provider_event.sport_key)
        competition = self.resolve_competition(sport, provider_event.competition_name)
        home = self.resolve_participant(sport, provider_event.home_name)
        away = self.resolve_participant(sport, provider_event.away_name)

        event = self.db.scalar(
            select(Event).where(Event.external_ref == provider_event.provider_event_id)
        )
        if event is not None:
            return event

        candidates = self.db.scalars(
            select(Event).where(
                Event.competition_id == competition.id,
                Event.home_participant_id == home.id,
                Event.away_participant_id == away.id,
            )
        )
        for candidate in candidates:
            if abs(candidate.start_time - provider_event.start_time) <= _EVENT_TIME_TOLERANCE:
                if candidate.external_ref is None:
                    candidate.external_ref = provider_event.provider_event_id
                return candidate

        event = Event(
            sport_id=sport.id,
            competition_id=competition.id,
            home_participant_id=home.id,
            away_participant_id=away.id,
            start_time=provider_event.start_time,
            external_ref=provider_event.provider_event_id,
        )
        self.db.add(event)
        self.db.flush()
        return event

    # -- Selection ---------------------------------------------------------

    def resolve_selection(
        self,
        event: Event,
        sport: Sport,
        market_type: MarketType,
        selection_code: SelectionCode,
        *,
        line: float | None = None,
        participant_name: str | None = None,
    ) -> Selection:
        market = self.db.scalar(
            select(EventMarket).where(
                EventMarket.event_id == event.id,
                EventMarket.market_type == market_type,
                EventMarket.line == line,
            )
        )
        if market is None:
            market = EventMarket(event_id=event.id, market_type=market_type, line=line)
            self.db.add(market)
            self.db.flush()

        participant_id = None
        if selection_code == SelectionCode.PARTICIPANT_WIN:
            if participant_name is None:
                raise ValueError("participant_name is required for a PARTICIPANT_WIN selection")
            participant_id = self.resolve_participant(sport, participant_name).id

        selection = self.db.scalar(
            select(Selection).where(
                Selection.event_market_id == market.id,
                Selection.code == selection_code,
                Selection.participant_id == participant_id,
            )
        )
        if selection is None:
            selection = Selection(
                event_market_id=market.id, code=selection_code, participant_id=participant_id
            )
            self.db.add(selection)
            self.db.flush()
        return selection

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _best_fuzzy_match(normalized: str, candidates: list, key):
        best, best_score = None, 0.0
        for candidate in candidates:
            score = similarity(normalized, key(candidate))
            if score > best_score:
                best, best_score = candidate, score
        return best, best_score
