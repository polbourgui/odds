"""Value bet computation: joins the latest odds per (selection, bookmaker),
devigs the sharp reference book's full market to get true probabilities,
then scores every ANJ-licensed bookmaker's price against it.

A quote — the sharp reference's or an ANJ book's — older than
`stale_odds_minutes` is never treated as valid: it is dropped before any
edge/Kelly computation happens, per the brief's freshness requirement.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.calculations import DevigMethod, devig, fair_odds, kelly_stake
from app.core.calculations import edge as compute_edge
from app.core.config import Settings, get_settings
from app.models.enums import MarketType, SelectionCode
from app.models.markets import EventMarket
from app.models.odds import OddsSnapshot
from app.services.odds_query import as_utc, latest_snapshots


@dataclass
class ValueBet:
    event_id: int
    sport_slug: str
    competition_name: str
    home_name: str
    away_name: str
    start_time: datetime
    market_type: MarketType
    line: float | None
    selection_code: SelectionCode
    participant_name: str | None
    bookmaker_slug: str
    bookmaker_name: str
    book_odds: float
    fair_odds: float
    true_probability: float
    edge: float
    kelly_stake: float
    captured_at: datetime
    reference_captured_at: datetime


def compute_value_bets(
    db: Session,
    *,
    settings: Settings | None = None,
    sport_slug: str | None = None,
    market_type: MarketType | None = None,
    bookmaker_slug: str | None = None,
    edge_min: float | None = None,
) -> list[ValueBet]:
    settings = settings or get_settings()
    stale_cutoff = datetime.now(UTC) - timedelta(minutes=settings.stale_odds_minutes)

    fresh_snapshots = [s for s in latest_snapshots(db) if as_utc(s.captured_at) >= stale_cutoff]

    by_market: dict[int, list[OddsSnapshot]] = defaultdict(list)
    for snapshot in fresh_snapshots:
        by_market[snapshot.selection.event_market_id].append(snapshot)

    results: list[ValueBet] = []

    for market_snapshots in by_market.values():
        event_market: EventMarket = market_snapshots[0].selection.event_market
        event = event_market.event

        if sport_slug is not None and event.sport.slug != sport_slug:
            continue
        if market_type is not None and event_market.market_type != market_type:
            continue

        sharp_by_selection = {
            s.selection_id: s for s in market_snapshots if s.bookmaker.is_sharp_reference
        }
        selections = event_market.selections
        # A devig needs a fresh sharp price for every outcome in the market;
        # a partial set would silently misprice the whole market.
        if len(sharp_by_selection) != len(selections):
            continue

        ordered_selections = sorted(selections, key=lambda sel: sel.id)
        sharp_odds = [float(sharp_by_selection[sel.id].odds) for sel in ordered_selections]
        try:
            true_probs = devig(sharp_odds, method=DevigMethod(settings.devig_method))
        except ValueError:
            continue
        selection_ids = (sel.id for sel in ordered_selections)
        prob_by_selection = dict(zip(selection_ids, true_probs, strict=True))
        reference_captured_at = min(
            as_utc(s.captured_at) for s in sharp_by_selection.values()
        )

        for snapshot in market_snapshots:
            bookmaker = snapshot.bookmaker
            if not bookmaker.is_anj_licensed or bookmaker.is_sharp_reference:
                continue
            if bookmaker_slug is not None and bookmaker.slug != bookmaker_slug:
                continue

            true_probability = prob_by_selection[snapshot.selection_id]
            book_odds = float(snapshot.odds)
            bet_edge = compute_edge(true_probability, book_odds)
            if edge_min is not None and bet_edge < edge_min:
                continue

            selection = snapshot.selection
            results.append(
                ValueBet(
                    event_id=event.id,
                    sport_slug=event.sport.slug,
                    competition_name=event.competition.name,
                    home_name=event.home_participant.name,
                    away_name=event.away_participant.name,
                    start_time=as_utc(event.start_time),
                    market_type=event_market.market_type,
                    line=float(event_market.line) if event_market.line is not None else None,
                    selection_code=selection.code,
                    participant_name=(
                        selection.participant.name if selection.participant is not None else None
                    ),
                    bookmaker_slug=bookmaker.slug,
                    bookmaker_name=bookmaker.name,
                    book_odds=book_odds,
                    fair_odds=fair_odds(true_probability),
                    true_probability=true_probability,
                    edge=bet_edge,
                    kelly_stake=kelly_stake(
                        true_probability,
                        book_odds,
                        settings.default_bankroll,
                        fraction=settings.kelly_fraction,
                        cap_pct=settings.kelly_cap_pct,
                        edge_threshold=settings.edge_threshold,
                    ),
                    captured_at=as_utc(snapshot.captured_at),
                    reference_captured_at=reference_captured_at,
                )
            )

    results.sort(key=lambda r: r.edge, reverse=True)
    return results
