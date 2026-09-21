"""Pure statistics helpers for the stats page: mean/stdev, confidence
intervals (normal approximation for a sample mean, Wilson score for a
binomial proportion), and max drawdown from an equity curve.

No I/O, no DB access — the stats service (`app/services/stats.py`) queries
settled bets and feeds plain lists of numbers into these.
"""

from collections.abc import Sequence

# z-scores for the two-sided normal confidence levels this module supports.
_Z_SCORES = {
    0.90: 1.6448536269514722,
    0.95: 1.959963984540054,
    0.99: 2.5758293035489004,
}


def _validate_confidence(confidence: float) -> float:
    if confidence not in _Z_SCORES:
        raise ValueError(f"unsupported confidence level: {confidence} (use 0.90, 0.95 or 0.99)")
    return _Z_SCORES[confidence]


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("values must not be empty")
    return sum(values) / len(values)


def stdev(values: Sequence[float]) -> float:
    """Sample standard deviation (n-1 denominator)."""
    n = len(values)
    if n < 2:
        raise ValueError("stdev requires at least 2 values")
    m = mean(values)
    variance = sum((v - m) ** 2 for v in values) / (n - 1)
    return variance**0.5


def confidence_interval_mean(
    values: Sequence[float], confidence: float = 0.95
) -> tuple[float, float]:
    """Normal-approximation CI for a sample mean: mean +/- z * stderr."""
    z = _validate_confidence(confidence)
    n = len(values)
    if n < 2:
        raise ValueError("confidence_interval_mean requires at least 2 values")
    m = mean(values)
    standard_error = stdev(values) / (n**0.5)
    margin = z * standard_error
    return (m - margin, m + margin)


def wilson_score_interval(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion -- more reliable than
    the normal approximation for small samples or proportions near 0/1."""
    z = _validate_confidence(confidence)
    if n <= 0:
        raise ValueError("n must be positive")
    if not (0 <= successes <= n):
        raise ValueError("successes must be between 0 and n")

    p_hat = successes / n
    z2 = z * z
    denominator = 1 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denominator
    margin = (z * ((p_hat * (1 - p_hat) / n + z2 / (4 * n * n)) ** 0.5)) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def max_drawdown(equity_curve: Sequence[float]) -> float:
    """Largest peak-to-trough decline, as a fraction of the peak (0..1)."""
    if not equity_curve:
        raise ValueError("equity_curve must not be empty")

    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst
