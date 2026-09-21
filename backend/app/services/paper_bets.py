"""Paper (fictitious) betting: placing a bet freezes the odds, stake, edge,
true probability and fair odds computed at that instant, exactly mirroring
what the value bets table showed. No real money or bookmaker account is
ever involved.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.calculations import DevigMethod as CalcDevigMethod
from app.core.calculations import devig, fair_odds, kelly_stake
from app.core.calculations import edge as compute_edge
from app.core.config import Settings, get_settings
from app.models.bankroll import Bankroll, PaperBet
from app.models.bookmakers import Bookmaker
from app.models.enums import BetStatus, MarketType, SelectionCode
from app.models.enums import DevigMethod as ModelDevigMethod
from app.models.odds import OddsSnapshot
from app.services.odds_query import as_utc


class PaperBettingError(ValueError):
    """A paper bet could not be placed or settled."""


def get_or_create_default_bankroll(db: Session, *, settings: Settings | None = None) -> Bankroll:
    settings = settings or get_settings()
    bankroll = db.scalars(select(Bankroll).order_by(Bankroll.id)).first()
    if bankroll is not None:
        return bankroll
    bankroll = Bankroll(
        name="Bankroll",
        currency="EUR",
        initial_balance=settings.default_bankroll,
        current_balance=settings.default_bankroll,
    )
    db.add(bankroll)
    db.flush()
    return bankroll


def update_bankroll(
    db: Session,
    bankroll: Bankroll,
    *,
    name: str | None = None,
    initial_balance: float | None = None,
) -> Bankroll:
    if name is not None:
        bankroll.name = name
    if initial_balance is not None:
        if initial_balance < 0:
            raise PaperBettingError("Le solde initial ne peut pas être négatif")
        # Preserve accumulated P&L: shift current_balance by the same delta
        # rather than wiping out settled bets' effect.
        delta = initial_balance - float(bankroll.initial_balance)
        bankroll.initial_balance = initial_balance
        bankroll.current_balance = float(bankroll.current_balance) + delta
    db.flush()
    return bankroll


def reset_bankroll(db: Session, bankroll: Bankroll) -> Bankroll:
    bankroll.current_balance = bankroll.initial_balance
    db.flush()
    return bankroll


def _latest_snapshot_for(db: Session, selection_id: int, bookmaker_id: int) -> OddsSnapshot | None:
    return db.scalars(
        select(OddsSnapshot)
        .where(OddsSnapshot.selection_id == selection_id, OddsSnapshot.bookmaker_id == bookmaker_id)
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    ).first()


@dataclass
class _PlacementPricing:
    odds_taken: float
    true_probability: float
    fair_odds_value: float
    edge_value: float
    stake: float


def _price_bet(
    db: Session,
    selection_id: int,
    bookmaker: Bookmaker,
    settings: Settings,
    *,
    bankroll_amount: float,
) -> _PlacementPricing:
    stale_cutoff = datetime.now(UTC) - timedelta(minutes=settings.stale_odds_minutes)

    book_snapshot = _latest_snapshot_for(db, selection_id, bookmaker.id)
    if book_snapshot is None or as_utc(book_snapshot.captured_at) < stale_cutoff:
        raise PaperBettingError("Aucune cote fraîche disponible pour ce book sur cette sélection")

    event_market = book_snapshot.selection.event_market
    selections = event_market.selections

    sharp_snapshots: dict[int, OddsSnapshot] = {}
    for selection in selections:
        snap = db.scalars(
            select(OddsSnapshot)
            .join(Bookmaker, OddsSnapshot.bookmaker_id == Bookmaker.id)
            .where(
                OddsSnapshot.selection_id == selection.id,
                Bookmaker.is_sharp_reference.is_(True),
            )
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        ).first()
        if snap is not None and as_utc(snap.captured_at) >= stale_cutoff:
            sharp_snapshots[selection.id] = snap

    if len(sharp_snapshots) != len(selections):
        raise PaperBettingError(
            "La référence sharp ne couvre pas tout le marché ou n'est plus fraîche"
        )

    ordered = sorted(selections, key=lambda sel: sel.id)
    sharp_odds = [float(sharp_snapshots[sel.id].odds) for sel in ordered]
    try:
        true_probs = devig(sharp_odds, method=CalcDevigMethod(settings.devig_method))
    except ValueError as exc:
        raise PaperBettingError("Échec du dévigage de la référence sharp") from exc
    prob_by_selection = dict(zip((sel.id for sel in ordered), true_probs, strict=True))

    true_probability = prob_by_selection[selection_id]
    odds_taken = float(book_snapshot.odds)
    edge_value = compute_edge(true_probability, odds_taken)
    stake = kelly_stake(
        true_probability,
        odds_taken,
        bankroll_amount,
        fraction=settings.kelly_fraction,
        cap_pct=settings.kelly_cap_pct,
        edge_threshold=settings.edge_threshold,
    )
    if stake <= 0:
        raise PaperBettingError("Edge insuffisant pour placer ce pari")

    return _PlacementPricing(
        odds_taken=odds_taken,
        true_probability=true_probability,
        fair_odds_value=fair_odds(true_probability),
        edge_value=edge_value,
        stake=stake,
    )


def place_paper_bet(
    db: Session,
    *,
    selection_id: int,
    bookmaker_slug: str,
    bankroll: Bankroll | None = None,
    settings: Settings | None = None,
) -> PaperBet:
    settings = settings or get_settings()
    bankroll = bankroll or get_or_create_default_bankroll(db, settings=settings)

    bookmaker = db.scalars(select(Bookmaker).where(Bookmaker.slug == bookmaker_slug)).one_or_none()
    if bookmaker is None:
        raise PaperBettingError(f"Bookmaker inconnu: {bookmaker_slug}")
    if not bookmaker.is_anj_licensed:
        raise PaperBettingError("Seuls les books agréés ANJ peuvent recevoir un pari fictif")

    # kelly_stake() caps the stake at bankroll_amount * cap_pct (cap_pct <= 1),
    # so the resulting stake can never exceed the bankroll it was sized from.
    pricing = _price_bet(
        db, selection_id, bookmaker, settings, bankroll_amount=float(bankroll.current_balance)
    )

    bet = PaperBet(
        bankroll_id=bankroll.id,
        selection_id=selection_id,
        bookmaker_id=bookmaker.id,
        odds_taken=pricing.odds_taken,
        stake=pricing.stake,
        true_probability_at_placement=pricing.true_probability,
        fair_odds_at_placement=pricing.fair_odds_value,
        edge_at_placement=pricing.edge_value,
        devig_method_at_placement=ModelDevigMethod(settings.devig_method),
        placed_at=datetime.now(UTC),
        status=BetStatus.PENDING,
    )
    bankroll.current_balance = float(bankroll.current_balance) - pricing.stake
    db.add(bet)
    db.commit()
    db.refresh(bet)
    return bet


_SETTLEMENT_STATUSES = {BetStatus.WON, BetStatus.LOST, BetStatus.PUSH, BetStatus.VOID}


def settle_paper_bet(db: Session, *, bet_id: int, status: BetStatus) -> PaperBet:
    if status not in _SETTLEMENT_STATUSES:
        raise PaperBettingError(f"Statut de règlement invalide: {status}")

    bet = db.get(PaperBet, bet_id)
    if bet is None:
        raise PaperBettingError(f"Pari introuvable: {bet_id}")
    if bet.status != BetStatus.PENDING:
        raise PaperBettingError("Ce pari a déjà été réglé")

    stake = float(bet.stake)
    if status == BetStatus.WON:
        payout = stake * float(bet.odds_taken)
    elif status == BetStatus.LOST:
        payout = 0.0
    else:  # PUSH or VOID: stake returned in full
        payout = stake

    bet.status = status
    bet.payout = payout
    bet.settled_at = datetime.now(UTC)
    bet.bankroll.current_balance = float(bet.bankroll.current_balance) + payout

    db.commit()
    db.refresh(bet)
    return bet


@dataclass
class PaperBetView:
    """A PaperBet flattened with its event/market/selection/bookmaker
    context, for API responses -- the ORM row alone doesn't carry these."""

    id: int
    bankroll_id: int
    sport_slug: str
    competition_name: str
    home_name: str
    away_name: str
    event_start_time: datetime
    market_type: MarketType
    line: float | None
    selection_code: SelectionCode
    participant_name: str | None
    bookmaker_slug: str
    bookmaker_name: str
    odds_taken: float
    stake: float
    true_probability_at_placement: float
    fair_odds_at_placement: float
    edge_at_placement: float
    devig_method_at_placement: ModelDevigMethod
    placed_at: datetime
    closing_odds: float | None
    clv: float | None
    status: BetStatus
    settled_at: datetime | None
    payout: float | None


def to_paper_bet_view(bet: PaperBet) -> PaperBetView:
    event_market = bet.selection.event_market
    event = event_market.event
    return PaperBetView(
        id=bet.id,
        bankroll_id=bet.bankroll_id,
        sport_slug=event.sport.slug,
        competition_name=event.competition.name,
        home_name=event.home_participant.name,
        away_name=event.away_participant.name,
        event_start_time=as_utc(event.start_time),
        market_type=event_market.market_type,
        line=float(event_market.line) if event_market.line is not None else None,
        selection_code=bet.selection.code,
        participant_name=(
            bet.selection.participant.name if bet.selection.participant is not None else None
        ),
        bookmaker_slug=bet.bookmaker.slug,
        bookmaker_name=bet.bookmaker.name,
        odds_taken=float(bet.odds_taken),
        stake=float(bet.stake),
        true_probability_at_placement=float(bet.true_probability_at_placement),
        fair_odds_at_placement=float(bet.fair_odds_at_placement),
        edge_at_placement=float(bet.edge_at_placement),
        devig_method_at_placement=bet.devig_method_at_placement,
        placed_at=as_utc(bet.placed_at),
        closing_odds=float(bet.closing_odds) if bet.closing_odds is not None else None,
        clv=float(bet.clv) if bet.clv is not None else None,
        status=bet.status,
        settled_at=as_utc(bet.settled_at) if bet.settled_at is not None else None,
        payout=float(bet.payout) if bet.payout is not None else None,
    )


def list_paper_bets(db: Session, *, status: BetStatus | None = None) -> list[PaperBetView]:
    stmt = select(PaperBet).order_by(PaperBet.placed_at.desc())
    if status is not None:
        stmt = stmt.where(PaperBet.status == status)
    bets = db.scalars(stmt).all()
    return [to_paper_bet_view(bet) for bet in bets]
