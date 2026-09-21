"""Automatic closing-line capture, per the brief: at kickoff, freeze the
sharp reference's closing price for every selection in a market and use it
(devigged) to backfill `closing_odds`/`clv` on any paper bet still missing
them. Idempotent -- safe to call repeatedly (e.g. from a scheduled job).
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.calculations import DevigMethod, clv, devig, fair_odds
from app.core.config import Settings, get_settings
from app.models.bankroll import PaperBet
from app.models.bookmakers import Bookmaker
from app.models.events import Event
from app.models.markets import EventMarket, Selection
from app.models.odds import OddsSnapshot

logger = logging.getLogger(__name__)


def _capture_market_closing_line(
    db: Session, market: EventMarket, event: Event, *, settings: Settings
) -> int:
    sharp_closing_by_selection: dict[int, OddsSnapshot] = {}
    for selection in market.selections:
        snap = db.scalars(
            select(OddsSnapshot)
            .join(Bookmaker, OddsSnapshot.bookmaker_id == Bookmaker.id)
            .where(
                OddsSnapshot.selection_id == selection.id,
                Bookmaker.is_sharp_reference.is_(True),
                OddsSnapshot.captured_at <= event.start_time,
            )
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        ).first()
        if snap is not None:
            sharp_closing_by_selection[selection.id] = snap

    if len(sharp_closing_by_selection) != len(market.selections):
        # No fully-priced sharp closing line for this market yet (or ever) --
        # nothing to backfill from.
        return 0

    for snap in sharp_closing_by_selection.values():
        snap.is_closing = True

    ordered = sorted(market.selections, key=lambda sel: sel.id)
    closing_odds_list = [float(sharp_closing_by_selection[sel.id].odds) for sel in ordered]
    try:
        true_probs = devig(closing_odds_list, method=DevigMethod(settings.devig_method))
    except ValueError:
        logger.warning("Could not devig closing line for event_market_id=%s", market.id)
        return 0
    fair_by_selection = {
        sel.id: fair_odds(p) for sel, p in zip(ordered, true_probs, strict=True)
    }

    updated = 0
    for selection in market.selections:
        fair = fair_by_selection[selection.id]
        pending_bets = db.scalars(
            select(PaperBet).where(
                PaperBet.selection_id == selection.id, PaperBet.closing_odds.is_(None)
            )
        ).all()
        for bet in pending_bets:
            bet.closing_odds = fair
            bet.clv = clv(float(bet.odds_taken), fair)
            updated += 1

    return updated


def run_closing_capture(db: Session, *, settings: Settings | None = None) -> int:
    """Backfill closing_odds/clv on paper bets for events that have kicked
    off. Returns the number of bets updated."""
    settings = settings or get_settings()
    now = datetime.now(UTC)

    event_ids = db.scalars(
        select(Event.id)
        .join(EventMarket, EventMarket.event_id == Event.id)
        .join(Selection, Selection.event_market_id == EventMarket.id)
        .join(PaperBet, PaperBet.selection_id == Selection.id)
        .where(Event.start_time <= now, PaperBet.closing_odds.is_(None))
        .distinct()
    ).all()

    total_updated = 0
    for event_id in event_ids:
        event = db.get(Event, event_id)
        for market in event.markets:
            total_updated += _capture_market_closing_line(db, market, event, settings=settings)

    db.commit()
    if total_updated:
        logger.info("Closing-line capture backfilled %d paper bet(s)", total_updated)
    return total_updated
