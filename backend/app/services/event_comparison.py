"""Per-event odds comparator: every bookmaker's latest price side by side,
the best ANJ price highlighted, and each price's deviation from the sharp
reference (its devigged fair odds when the reference covers the whole
market, otherwise its raw quote).

Unlike the value bets table, a stale quote is not hidden here — this view
is for inspecting what data is available for an event, so a stale price is
shown (with `is_stale=True`) rather than disappearing. It is however never
eligible to be flagged as the best price, per the "never valid" freshness
rule.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.calculations import DevigMethod, devig, fair_odds
from app.core.config import Settings, get_settings
from app.models.enums import MarketType, SelectionCode
from app.models.events import Event
from app.models.markets import EventMarket
from app.models.odds import OddsSnapshot
from app.services.odds_query import as_utc, latest_snapshots


@dataclass
class ComparisonQuote:
    bookmaker_slug: str
    bookmaker_name: str
    is_sharp_reference: bool
    is_anj_licensed: bool
    odds: float
    captured_at: datetime
    is_stale: bool
    is_best: bool
    deviation_vs_reference: float | None


@dataclass
class ComparisonSelection:
    selection_code: SelectionCode
    participant_name: str | None
    reference_odds: float | None
    fair_odds: float | None
    true_probability: float | None
    quotes: list[ComparisonQuote] = field(default_factory=list)


@dataclass
class ComparisonMarket:
    market_type: MarketType
    line: float | None
    selections: list[ComparisonSelection]


@dataclass
class EventComparison:
    event_id: int
    sport_slug: str
    competition_name: str
    home_name: str
    away_name: str
    start_time: datetime
    markets: list[ComparisonMarket]


def _market_sort_key(market: EventMarket) -> tuple[str, float]:
    return (market.market_type.value, float(market.line) if market.line is not None else 0.0)


def get_event_comparison(
    db: Session, event_id: int, *, settings: Settings | None = None
) -> EventComparison | None:
    settings = settings or get_settings()
    event = db.get(Event, event_id)
    if event is None:
        return None

    stale_cutoff = datetime.now(UTC) - timedelta(minutes=settings.stale_odds_minutes)

    snapshots_by_market: dict[int, list[OddsSnapshot]] = defaultdict(list)
    for snapshot in latest_snapshots(db):
        if snapshot.selection.event_market.event_id == event_id:
            snapshots_by_market[snapshot.selection.event_market_id].append(snapshot)

    markets: list[ComparisonMarket] = []
    for event_market in sorted(event.markets, key=_market_sort_key):
        market_snapshots = snapshots_by_market.get(event_market.id, [])
        snapshots_by_selection: dict[int, list[OddsSnapshot]] = defaultdict(list)
        for snapshot in market_snapshots:
            snapshots_by_selection[snapshot.selection_id].append(snapshot)

        fresh_sharp_by_selection = {
            s.selection_id: s
            for s in market_snapshots
            if s.bookmaker.is_sharp_reference and as_utc(s.captured_at) >= stale_cutoff
        }
        prob_by_selection: dict[int, float] = {}
        if len(fresh_sharp_by_selection) == len(event_market.selections):
            ordered = sorted(event_market.selections, key=lambda sel: sel.id)
            sharp_odds = [float(fresh_sharp_by_selection[sel.id].odds) for sel in ordered]
            try:
                probs = devig(sharp_odds, method=DevigMethod(settings.devig_method))
                prob_by_selection = dict(zip((sel.id for sel in ordered), probs, strict=True))
            except ValueError:
                prob_by_selection = {}

        selections_out: list[ComparisonSelection] = []
        for selection in event_market.selections:
            selection_snapshots = snapshots_by_selection.get(selection.id, [])

            true_probability = prob_by_selection.get(selection.id)
            fair = fair_odds(true_probability) if true_probability is not None else None
            # Any sharp quote for this selection (even a stale one) still
            # anchors "écart vs référence" when a fresh, full devig isn't
            # available -- better than no reference at all.
            any_sharp_snapshot = next(
                (s for s in selection_snapshots if s.bookmaker.is_sharp_reference), None
            )
            reference_price = fair if fair is not None else (
                float(any_sharp_snapshot.odds) if any_sharp_snapshot is not None else None
            )

            best_price = max(
                (
                    float(s.odds)
                    for s in selection_snapshots
                    if s.bookmaker.is_anj_licensed and as_utc(s.captured_at) >= stale_cutoff
                ),
                default=None,
            )

            quotes = [
                ComparisonQuote(
                    bookmaker_slug=s.bookmaker.slug,
                    bookmaker_name=s.bookmaker.name,
                    is_sharp_reference=s.bookmaker.is_sharp_reference,
                    is_anj_licensed=s.bookmaker.is_anj_licensed,
                    odds=float(s.odds),
                    captured_at=as_utc(s.captured_at),
                    is_stale=as_utc(s.captured_at) < stale_cutoff,
                    is_best=(
                        best_price is not None
                        and float(s.odds) == best_price
                        and s.bookmaker.is_anj_licensed
                        and as_utc(s.captured_at) >= stale_cutoff
                    ),
                    deviation_vs_reference=(
                        float(s.odds) / reference_price - 1 if reference_price else None
                    ),
                )
                for s in sorted(selection_snapshots, key=lambda s: float(s.odds), reverse=True)
            ]

            selections_out.append(
                ComparisonSelection(
                    selection_code=selection.code,
                    participant_name=(
                        selection.participant.name if selection.participant is not None else None
                    ),
                    reference_odds=(
                        float(any_sharp_snapshot.odds) if any_sharp_snapshot is not None else None
                    ),
                    fair_odds=fair,
                    true_probability=true_probability,
                    quotes=quotes,
                )
            )

        markets.append(
            ComparisonMarket(
                market_type=event_market.market_type,
                line=float(event_market.line) if event_market.line is not None else None,
                selections=selections_out,
            )
        )

    return EventComparison(
        event_id=event.id,
        sport_slug=event.sport.slug,
        competition_name=event.competition.name,
        home_name=event.home_participant.name,
        away_name=event.away_participant.name,
        start_time=as_utc(event.start_time),
        markets=markets,
    )
