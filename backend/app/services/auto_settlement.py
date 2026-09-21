"""Automatic paper-bet settlement from a results feed.

For events that have kicked off, fetches final scores from a
`ResultsProvider`, grouped by the provider sport_key each event's
competition was reconciled under (`Competition.provider_sport_key`), and
settles every PENDING paper bet on a completed event by comparing
home/away scores. Manual settlement (`app.services.paper_bets.settle_paper_bet`)
remains available for anything this can't resolve -- a market type outside
1X2/moneyline/over-under, or a tie in a market with no draw outcome.
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bankroll import PaperBet
from app.models.enums import BetStatus, MarketType, SelectionCode
from app.models.events import Event
from app.models.markets import EventMarket, Selection
from app.providers.base import ProviderResult, ResultsProvider
from app.services.paper_bets import settle_paper_bet

logger = logging.getLogger(__name__)


def determine_outcome(
    market_type: MarketType,
    selection_code: SelectionCode,
    home_score: float,
    away_score: float,
    *,
    line: float | None = None,
    is_home_participant: bool | None = None,
) -> BetStatus | None:
    """The settlement status for one selection given a final score, or None
    if it cannot be determined from the score alone."""
    if market_type == MarketType.ONE_X_TWO:
        if home_score > away_score:
            winner = SelectionCode.HOME
        elif away_score > home_score:
            winner = SelectionCode.AWAY
        else:
            winner = SelectionCode.DRAW
        return BetStatus.WON if selection_code == winner else BetStatus.LOST

    if market_type == MarketType.MONEYLINE:
        # No draw in a 2-way market: an exact tie can't be resolved from the
        # score alone (rare, but possible with abandoned/curtailed events).
        if is_home_participant is None or home_score == away_score:
            return None
        home_won = home_score > away_score
        participant_won = home_won if is_home_participant else not home_won
        return BetStatus.WON if participant_won else BetStatus.LOST

    if market_type == MarketType.OVER_UNDER:
        if line is None:
            return None
        total = home_score + away_score
        if total == line:
            return BetStatus.PUSH
        over_won = total > line
        if selection_code == SelectionCode.OVER:
            return BetStatus.WON if over_won else BetStatus.LOST
        if selection_code == SelectionCode.UNDER:
            return BetStatus.LOST if over_won else BetStatus.WON
        return None

    return None


def _events_with_pending_bets_by_sport_key(db: Session) -> dict[str, list[Event]]:
    """Events, grouped by the provider sport_key their competition was
    reconciled under, that have kicked off and still have pending bets."""
    now = datetime.now(UTC)
    event_ids = db.scalars(
        select(Event.id)
        .join(EventMarket, EventMarket.event_id == Event.id)
        .join(Selection, Selection.event_market_id == EventMarket.id)
        .join(PaperBet, PaperBet.selection_id == Selection.id)
        .where(Event.start_time <= now, PaperBet.status == BetStatus.PENDING)
        .distinct()
    ).all()

    by_sport_key: dict[str, list[Event]] = defaultdict(list)
    for event_id in event_ids:
        event = db.get(Event, event_id)
        sport_key = event.competition.provider_sport_key
        if sport_key is None:
            logger.warning(
                "Event id=%d's competition has no provider_sport_key; "
                "cannot fetch results for auto-settlement",
                event_id,
            )
            continue
        by_sport_key[sport_key].append(event)
    return by_sport_key


def _settle_event(db: Session, event: Event, result: ProviderResult) -> int:
    if not result.completed or result.home_score is None or result.away_score is None:
        return 0

    settled = 0
    for market in event.markets:
        for selection in market.selections:
            pending_bets = db.scalars(
                select(PaperBet).where(
                    PaperBet.selection_id == selection.id, PaperBet.status == BetStatus.PENDING
                )
            ).all()
            if not pending_bets:
                continue

            is_home_participant = None
            if market.market_type == MarketType.MONEYLINE:
                is_home_participant = selection.participant_id == event.home_participant_id

            outcome = determine_outcome(
                market.market_type,
                selection.code,
                result.home_score,
                result.away_score,
                line=float(market.line) if market.line is not None else None,
                is_home_participant=is_home_participant,
            )
            if outcome is None:
                continue

            for bet in pending_bets:
                settle_paper_bet(db, bet_id=bet.id, status=outcome)
                settled += 1

    return settled


def run_auto_settlement(db: Session, provider: ResultsProvider) -> int:
    """Settle every pending paper bet whose event is complete, per the
    provider's results feed. Returns the number of bets settled."""
    events_by_sport_key = _events_with_pending_bets_by_sport_key(db)

    total_settled = 0
    for sport_key, events in events_by_sport_key.items():
        event_ids = [e.external_ref for e in events if e.external_ref is not None]
        results = provider.fetch_results(sport_key, event_ids=event_ids or None)
        results_by_id = {r.provider_event_id: r for r in results}

        for event in events:
            result = results_by_id.get(event.external_ref)
            if result is not None:
                total_settled += _settle_event(db, event, result)

    if total_settled:
        logger.info("Auto-settlement resolved %d paper bet(s)", total_settled)
    return total_settled
