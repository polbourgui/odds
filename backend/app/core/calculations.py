"""Pure, side-effect-free betting math: devigging, edge, Kelly stake, CLV.

No I/O, no DB access, no framework dependency — everything here operates on
plain floats so it can be unit tested exhaustively and reused anywhere
(API layer, scheduled jobs, scripts).
"""

from collections.abc import Sequence
from enum import Enum


class DevigMethod(str, Enum):
    MULTIPLICATIVE = "multiplicative"
    POWER = "power"
    SHIN = "shin"


def _validate_odds(odds: float, *, name: str = "odds") -> None:
    if odds <= 1.0:
        raise ValueError(f"{name} must be > 1.0, got {odds}")


def _validate_probability(probability: float, *, name: str = "probability") -> None:
    if not (0.0 < probability < 1.0):
        raise ValueError(f"{name} must be strictly between 0 and 1, got {probability}")


def implied_probability(odds: float) -> float:
    """Raw (vig-included) implied probability of a decimal odds quote."""
    _validate_odds(odds)
    return 1.0 / odds


def fair_odds(probability: float) -> float:
    """Odds implied by a (devigged) true probability."""
    _validate_probability(probability)
    return 1.0 / probability


def _validate_odds_list(odds_list: Sequence[float]) -> None:
    if len(odds_list) < 2:
        raise ValueError("odds_list must contain at least 2 outcomes")
    for o in odds_list:
        _validate_odds(o)


def devig_multiplicative(odds_list: Sequence[float]) -> list[float]:
    """Remove the overround by normalizing raw implied probabilities to sum to 1.

    p_i = (1/o_i) / sum_j(1/o_j)
    """
    _validate_odds_list(odds_list)
    raw = [1.0 / o for o in odds_list]
    total = sum(raw)
    return [r / total for r in raw]


def _bisect(
    func, target: float, lo: float, hi: float, *, tol: float = 1e-12, max_iter: int = 200
) -> float:
    """Find x in [lo, hi] with func(x) == target, assuming func is monotonic
    decreasing on that interval and func(lo) >= target >= func(hi)."""
    f_lo = func(lo) - target
    f_hi = func(hi) - target
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if f_lo < 0 or f_hi > 0:
        raise ValueError("target is not bracketed by [lo, hi]")

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = func(mid) - target
        if abs(f_mid) < tol:
            return mid
        if f_mid > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def devig_power(odds_list: Sequence[float]) -> list[float]:
    """Power method: find exponent k such that sum((1/o_i)**k) == 1,
    then p_i = (1/o_i)**k.
    """
    _validate_odds_list(odds_list)
    raw = [1.0 / o for o in odds_list]

    def total_at(k: float) -> float:
        return sum(r**k for r in raw)

    hi = 2.0
    while total_at(hi) > 1.0:
        hi *= 2
        if hi > 1e6:
            raise ValueError("failed to bracket power-method exponent; check input odds")

    k = _bisect(total_at, 1.0, lo=0.0, hi=hi)
    return [r**k for r in raw]


def devig_shin(odds_list: Sequence[float]) -> list[float]:
    """Shin's method: solve for the insider-trading proportion z in [0, 1)
    such that sum(p_i(z)) == 1, where

    p_i(z) = (sqrt(z**2 + 4*(1-z)*pi_i**2/S) - z) / (2*(1-z))

    with pi_i = 1/o_i (raw implied probabilities) and S = sum(pi_i).
    """
    _validate_odds_list(odds_list)
    pi = [1.0 / o for o in odds_list]
    s = sum(pi)

    def probs_at(z: float) -> list[float]:
        denom = 2 * (1 - z)
        return [(((z**2 + 4 * (1 - z) * p * p / s) ** 0.5) - z) / denom for p in pi]

    def total_at(z: float) -> float:
        return sum(probs_at(z))

    z = _bisect(total_at, 1.0, lo=0.0, hi=1.0 - 1e-9)
    return probs_at(z)


_DEVIG_FUNCS = {
    DevigMethod.MULTIPLICATIVE: devig_multiplicative,
    DevigMethod.POWER: devig_power,
    DevigMethod.SHIN: devig_shin,
}


def devig(
    odds_list: Sequence[float], method: DevigMethod | str = DevigMethod.MULTIPLICATIVE
) -> list[float]:
    """Dispatch to the requested devig method."""
    method = DevigMethod(method)
    return _DEVIG_FUNCS[method](odds_list)


def edge(true_probability: float, book_odds: float) -> float:
    """Expected value per unit staked: p * odds - 1."""
    _validate_probability(true_probability)
    _validate_odds(book_odds)
    return true_probability * book_odds - 1.0


def kelly_fraction_full(true_probability: float, book_odds: float) -> float:
    """Full Kelly fraction: f* = (p*o - 1) / (o - 1)."""
    _validate_probability(true_probability)
    _validate_odds(book_odds)
    return (true_probability * book_odds - 1.0) / (book_odds - 1.0)


def kelly_stake(
    true_probability: float,
    book_odds: float,
    bankroll: float,
    *,
    fraction: float = 0.25,
    cap_pct: float = 0.02,
    edge_threshold: float = 0.03,
) -> float:
    """Suggested stake using fractional Kelly, capped as a percentage of bankroll.

    Returns 0 when the edge is below `edge_threshold` or non-positive.
    Result is rounded to 2 decimal places (currency).
    """
    if bankroll < 0:
        raise ValueError(f"bankroll must be >= 0, got {bankroll}")
    if not (0.0 < fraction <= 1.0):
        raise ValueError(f"fraction must be in (0, 1], got {fraction}")
    if not (0.0 < cap_pct <= 1.0):
        raise ValueError(f"cap_pct must be in (0, 1], got {cap_pct}")

    e = edge(true_probability, book_odds)
    if e < edge_threshold:
        return 0.0

    f_star = kelly_fraction_full(true_probability, book_odds)
    if f_star <= 0:
        return 0.0

    raw_stake = bankroll * f_star * fraction
    capped_stake = min(raw_stake, bankroll * cap_pct)
    return round(capped_stake, 2)


def clv(odds_taken: float, closing_odds_devigged: float) -> float:
    """Closing line value: the edge captured versus the devigged closing price."""
    _validate_odds(odds_taken)
    _validate_odds(closing_odds_devigged)
    return odds_taken / closing_odds_devigged - 1.0
