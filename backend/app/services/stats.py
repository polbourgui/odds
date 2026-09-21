"""Paper betting statistics: ROI/yield, win rate, average CLV (each with a
95% confidence interval and the sample size they're based on, so a handful
of bets never reads as a proven edge), max drawdown, a bankroll equity
curve, and breakdowns by bookmaker/sport/market. Also flags whether the
optional monthly virtual loss limit has been hit.

Push/void bets are counted in turnover/profit (both contribute exactly 0,
since payout == stake) but excluded from the win-rate denominator, since
they were never actually won or lost.
"""

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.statistics import confidence_interval_mean, max_drawdown, mean, wilson_score_interval
from app.models.bankroll import Bankroll, PaperBet
from app.models.enums import BetStatus
from app.services.odds_query import as_utc
from app.services.paper_bets import get_or_create_default_bankroll

_GRADED_STATUSES = (BetStatus.WON, BetStatus.LOST)
_SETTLED_STATUSES = (BetStatus.WON, BetStatus.LOST, BetStatus.PUSH, BetStatus.VOID)


@dataclass
class BankrollPoint:
    at: datetime
    balance: float
    label: str


@dataclass
class GroupStat:
    key: str
    label: str
    bets: int
    profit: float
    turnover: float
    roi: float | None


@dataclass
class StatsSummary:
    total_bets: int
    pending_bets: int
    graded_bets: int
    wins: int
    losses: int
    pushes: int
    voids: int

    win_rate: float | None
    win_rate_ci: tuple[float, float] | None

    turnover: float
    profit: float
    roi: float | None
    roi_ci: tuple[float, float] | None

    average_clv: float | None
    average_clv_ci: tuple[float, float] | None
    clv_sample_size: int

    max_drawdown_pct: float | None
    bankroll_curve: list[BankrollPoint] = field(default_factory=list)
    by_bookmaker: list[GroupStat] = field(default_factory=list)
    by_sport: list[GroupStat] = field(default_factory=list)
    by_market: list[GroupStat] = field(default_factory=list)

    monthly_profit: float = 0.0
    monthly_loss_limit: float | None = None
    monthly_loss_limit_reached: bool = False


def _bet_profit(bet: PaperBet) -> float:
    return float(bet.payout) - float(bet.stake)


def _group_stats(
    bets: Sequence[PaperBet],
    *,
    key_fn: Callable[[PaperBet], str],
    label_fn: Callable[[PaperBet], str],
) -> list[GroupStat]:
    grouped: dict[str, list[PaperBet]] = defaultdict(list)
    labels: dict[str, str] = {}
    for bet in bets:
        key = key_fn(bet)
        grouped[key].append(bet)
        labels.setdefault(key, label_fn(bet))

    stats = []
    for key, group in grouped.items():
        turnover = sum(float(b.stake) for b in group)
        profit = sum(_bet_profit(b) for b in group)
        stats.append(
            GroupStat(
                key=key,
                label=labels[key],
                bets=len(group),
                profit=profit,
                turnover=turnover,
                roi=profit / turnover if turnover > 0 else None,
            )
        )
    stats.sort(key=lambda g: g.profit, reverse=True)
    return stats


def compute_stats(
    db: Session, *, bankroll: Bankroll | None = None, settings: Settings | None = None
) -> StatsSummary:
    settings = settings or get_settings()
    bankroll = bankroll or get_or_create_default_bankroll(db, settings=settings)

    bets = list(
        db.scalars(
            select(PaperBet)
            .where(PaperBet.bankroll_id == bankroll.id)
            .order_by(PaperBet.placed_at)
        )
    )

    pending = [b for b in bets if b.status == BetStatus.PENDING]
    settled = [b for b in bets if b.status in _SETTLED_STATUSES]
    graded = [b for b in settled if b.status in _GRADED_STATUSES]

    wins = sum(1 for b in graded if b.status == BetStatus.WON)
    losses = len(graded) - wins
    pushes = sum(1 for b in settled if b.status == BetStatus.PUSH)
    voids = sum(1 for b in settled if b.status == BetStatus.VOID)

    turnover = sum(float(b.stake) for b in settled)
    profit = sum(_bet_profit(b) for b in settled)
    roi = profit / turnover if turnover > 0 else None

    per_bet_returns = [_bet_profit(b) / float(b.stake) for b in settled if float(b.stake) > 0]
    roi_ci = confidence_interval_mean(per_bet_returns) if len(per_bet_returns) >= 2 else None

    win_rate = wins / len(graded) if graded else None
    win_rate_ci = wilson_score_interval(wins, len(graded)) if graded else None

    clv_values = [float(b.clv) for b in bets if b.clv is not None]
    average_clv = mean(clv_values) if clv_values else None
    average_clv_ci = confidence_interval_mean(clv_values) if len(clv_values) >= 2 else None

    settled_by_time = sorted(settled, key=lambda b: as_utc(b.settled_at or b.placed_at))
    start_at = (
        as_utc(settled_by_time[0].placed_at) if settled_by_time else datetime.now(UTC)
    )
    curve = [BankrollPoint(at=start_at, balance=float(bankroll.initial_balance), label="Départ")]
    running_balance = float(bankroll.initial_balance)
    for bet in settled_by_time:
        running_balance += _bet_profit(bet)
        curve.append(
            BankrollPoint(
                at=as_utc(bet.settled_at or bet.placed_at),
                balance=running_balance,
                label=f"Pari #{bet.id}",
            )
        )
    max_dd = max_drawdown([p.balance for p in curve])

    by_bookmaker = _group_stats(
        settled, key_fn=lambda b: b.bookmaker.slug, label_fn=lambda b: b.bookmaker.name
    )
    by_sport = _group_stats(
        settled,
        key_fn=lambda b: b.selection.event_market.event.sport.slug,
        label_fn=lambda b: b.selection.event_market.event.sport.name,
    )
    by_market = _group_stats(
        settled,
        key_fn=lambda b: b.selection.event_market.market_type.value,
        label_fn=lambda b: b.selection.event_market.market_type.value,
    )

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_profit = sum(
        _bet_profit(b) for b in settled if as_utc(b.settled_at or b.placed_at) >= month_start
    )
    monthly_loss_limit = settings.monthly_loss_limit
    monthly_loss_limit_reached = (
        monthly_loss_limit is not None and monthly_profit <= -monthly_loss_limit
    )

    return StatsSummary(
        total_bets=len(bets),
        pending_bets=len(pending),
        graded_bets=len(graded),
        wins=wins,
        losses=losses,
        pushes=pushes,
        voids=voids,
        win_rate=win_rate,
        win_rate_ci=win_rate_ci,
        turnover=turnover,
        profit=profit,
        roi=roi,
        roi_ci=roi_ci,
        average_clv=average_clv,
        average_clv_ci=average_clv_ci,
        clv_sample_size=len(clv_values),
        max_drawdown_pct=max_dd if len(curve) > 1 else None,
        bankroll_curve=curve,
        by_bookmaker=by_bookmaker,
        by_sport=by_sport,
        by_market=by_market,
        monthly_profit=monthly_profit,
        monthly_loss_limit=monthly_loss_limit,
        monthly_loss_limit_reached=monthly_loss_limit_reached,
    )
