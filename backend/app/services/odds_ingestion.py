"""Fetches odds from a provider, reconciles events/selections, and stores
one timestamped `OddsSnapshot` per (selection, bookmaker) quote.

Snapshots are append-only: every call inserts new rows rather than updating
existing ones, since the full price history is what CLV is computed from.
Freshness filtering (never treat a quote older than N minutes as current) is
a read-time concern, applied where value bets are displayed, not here.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.bookmakers import Bookmaker
from app.models.odds import OddsSnapshot
from app.providers.base import OddsProvider
from app.providers.exceptions import ProviderError
from app.services.reconciliation import EventReconciler

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    events_seen: int
    snapshots_created: int


class OddsIngestionService:
    def __init__(self, db: Session, provider: OddsProvider, settings: Settings | None = None):
        self.db = db
        self.provider = provider
        self.settings = settings or get_settings()
        self.reconciler = EventReconciler(db, provider_name=provider.name)

    def _get_or_create_bookmaker(self, key: str, name: str) -> Bookmaker:
        bookmaker = self.db.scalar(select(Bookmaker).where(Bookmaker.slug == key))
        if bookmaker is not None:
            return bookmaker
        bookmaker = Bookmaker(
            slug=key,
            name=name,
            is_anj_licensed=key in self.settings.anj_bookmaker_keys,
            is_sharp_reference=key == self.settings.sharp_reference_bookmaker_key,
        )
        self.db.add(bookmaker)
        self.db.flush()
        return bookmaker

    def ingest_sport(self, sport_key: str) -> IngestionResult:
        try:
            event_odds_list = self.provider.fetch_odds(sport_key)
        except ProviderError:
            logger.error("Odds ingestion aborted for sport_key=%s", sport_key, exc_info=True)
            raise

        captured_at = datetime.now(UTC)
        snapshots_created = 0

        for event_odds in event_odds_list:
            sport = self.reconciler.resolve_sport(event_odds.event.sport_key)
            event = self.reconciler.resolve_event(event_odds.event)

            for bm_quote in event_odds.bookmakers:
                bookmaker = self._get_or_create_bookmaker(
                    bm_quote.bookmaker_key, bm_quote.bookmaker_name
                )
                for market in bm_quote.markets:
                    for outcome in market.outcomes:
                        selection = self.reconciler.resolve_selection(
                            event,
                            sport,
                            market.market_type,
                            outcome.selection_code,
                            line=outcome.line,
                            participant_name=outcome.participant_name,
                        )
                        self.db.add(
                            OddsSnapshot(
                                selection_id=selection.id,
                                bookmaker_id=bookmaker.id,
                                odds=outcome.price,
                                captured_at=captured_at,
                            )
                        )
                        snapshots_created += 1

        self.db.commit()
        logger.info(
            "Ingested %d snapshots across %d events for sport_key=%s",
            snapshots_created,
            len(event_odds_list),
            sport_key,
        )
        return IngestionResult(
            events_seen=len(event_odds_list), snapshots_created=snapshots_created
        )


def run_ingestion_for_tracked_sports(
    db: Session, provider: OddsProvider, settings: Settings | None = None
) -> list[IngestionResult]:
    """Ingest fresh odds for every sport_key in settings.tracked_sport_keys.

    Used by the periodic scheduler job. A provider error on one sport_key
    (already logged by ingest_sport) doesn't stop the others from running.
    """
    settings = settings or get_settings()
    service = OddsIngestionService(db, provider, settings=settings)
    results = []
    for sport_key in settings.tracked_sport_keys:
        try:
            results.append(service.ingest_sport(sport_key))
        except ProviderError:
            continue
    return results
