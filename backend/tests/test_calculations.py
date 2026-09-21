import pytest

from app.core.calculations import (
    DevigMethod,
    clv,
    devig,
    devig_multiplicative,
    devig_power,
    devig_shin,
    edge,
    fair_odds,
    implied_probability,
    kelly_fraction_full,
    kelly_stake,
)

# 1X2 odds with a ~3.57% overround, used throughout as the reference case.
ONE_X_TWO_ODDS = [2.00, 3.50, 4.00]


class TestImpliedProbability:
    def test_known_values(self):
        assert implied_probability(2.0) == pytest.approx(0.5)
        assert implied_probability(4.0) == pytest.approx(0.25)

    def test_rejects_odds_at_or_below_one(self):
        with pytest.raises(ValueError):
            implied_probability(1.0)
        with pytest.raises(ValueError):
            implied_probability(0.5)


class TestFairOdds:
    def test_known_values(self):
        assert fair_odds(0.5) == pytest.approx(2.0)
        assert fair_odds(0.25) == pytest.approx(4.0)

    def test_rejects_out_of_range_probability(self):
        with pytest.raises(ValueError):
            fair_odds(0.0)
        with pytest.raises(ValueError):
            fair_odds(1.0)


class TestDevigMultiplicative:
    def test_known_1x2_case(self):
        probs = devig_multiplicative(ONE_X_TWO_ODDS)
        assert probs == pytest.approx([0.4827586207, 0.2758620690, 0.2413793103], abs=1e-9)
        assert sum(probs) == pytest.approx(1.0)

    def test_no_overround_returns_raw_probabilities(self):
        # Odds with exactly 0% margin: 1/2.0 + 1/2.5 + 1/10.0 == 1
        odds = [2.0, 2.5, 10.0]
        raw = [implied_probability(o) for o in odds]
        probs = devig_multiplicative(odds)
        assert probs == pytest.approx(raw, abs=1e-12)

    def test_rejects_single_outcome(self):
        with pytest.raises(ValueError):
            devig_multiplicative([2.0])

    def test_rejects_invalid_odds(self):
        with pytest.raises(ValueError):
            devig_multiplicative([2.0, 0.9])


class TestDevigPower:
    def test_sums_to_one(self):
        probs = devig_power(ONE_X_TWO_ODDS)
        assert sum(probs) == pytest.approx(1.0, abs=1e-9)

    def test_symmetric_odds_split_evenly(self):
        probs = devig_power([3.0, 3.0, 3.0])
        assert probs == pytest.approx([1 / 3, 1 / 3, 1 / 3], abs=1e-9)

    def test_no_overround_returns_raw_probabilities(self):
        odds = [2.0, 2.5, 10.0]
        raw = [implied_probability(o) for o in odds]
        probs = devig_power(odds)
        assert probs == pytest.approx(raw, abs=1e-6)

    def test_preserves_favorite_ordering(self):
        probs = devig_power(ONE_X_TWO_ODDS)
        assert probs[0] > probs[1] > probs[2]


class TestDevigShin:
    def test_sums_to_one(self):
        probs = devig_shin(ONE_X_TWO_ODDS)
        assert sum(probs) == pytest.approx(1.0, abs=1e-9)

    def test_symmetric_odds_split_evenly(self):
        probs = devig_shin([3.0, 3.0, 3.0])
        assert probs == pytest.approx([1 / 3, 1 / 3, 1 / 3], abs=1e-9)

    def test_no_overround_returns_raw_probabilities(self):
        odds = [2.0, 2.5, 10.0]
        raw = [implied_probability(o) for o in odds]
        probs = devig_shin(odds)
        assert probs == pytest.approx(raw, abs=1e-6)

    def test_preserves_favorite_ordering(self):
        probs = devig_shin(ONE_X_TWO_ODDS)
        assert probs[0] > probs[1] > probs[2]


class TestDevigDispatcher:
    def test_dispatches_by_enum(self):
        assert devig(ONE_X_TWO_ODDS, DevigMethod.MULTIPLICATIVE) == pytest.approx(
            devig_multiplicative(ONE_X_TWO_ODDS)
        )
        assert devig(ONE_X_TWO_ODDS, DevigMethod.POWER) == pytest.approx(
            devig_power(ONE_X_TWO_ODDS)
        )
        assert devig(ONE_X_TWO_ODDS, DevigMethod.SHIN) == pytest.approx(
            devig_shin(ONE_X_TWO_ODDS)
        )

    def test_dispatches_by_string(self):
        assert devig(ONE_X_TWO_ODDS, "multiplicative") == pytest.approx(
            devig_multiplicative(ONE_X_TWO_ODDS)
        )

    def test_rejects_unknown_method(self):
        with pytest.raises(ValueError):
            devig(ONE_X_TWO_ODDS, "banana")


class TestEdge:
    def test_positive_edge(self):
        assert edge(0.55, 2.0) == pytest.approx(0.10)

    def test_zero_edge(self):
        assert edge(0.5, 2.0) == pytest.approx(0.0)

    def test_negative_edge(self):
        assert edge(0.4, 2.0) == pytest.approx(-0.20)


class TestKellyFractionFull:
    def test_known_value(self):
        # f* = (0.6*1.8 - 1) / (1.8 - 1) = 0.08 / 0.8 = 0.10
        assert kelly_fraction_full(0.6, 1.8) == pytest.approx(0.10)

    def test_zero_edge_gives_zero_fraction(self):
        assert kelly_fraction_full(0.5, 2.0) == pytest.approx(0.0)

    def test_negative_edge_gives_negative_fraction(self):
        assert kelly_fraction_full(0.4, 2.0) < 0


class TestKellyStake:
    def test_zero_edge_yields_zero_stake(self):
        assert kelly_stake(0.5, 2.0, bankroll=1000) == 0.0

    def test_negative_edge_yields_zero_stake(self):
        assert kelly_stake(0.4, 2.0, bankroll=1000) == 0.0

    def test_edge_below_threshold_yields_zero_stake(self):
        # edge = 0.55*1.85 - 1 = 0.0175 (1.75%), below the 3% default threshold.
        assert kelly_stake(0.55, 1.85, bankroll=1000, edge_threshold=0.03) == 0.0

    def test_normal_case_below_cap(self):
        # edge = 0.6*1.8 - 1 = 0.08 (8%); f* = 0.10
        # raw stake = 1000 * 0.10 * 0.25 = 25; cap = 1000*0.05 = 50 -> uncapped
        stake = kelly_stake(
            0.6, 1.8, bankroll=1000, fraction=0.25, cap_pct=0.05, edge_threshold=0.03
        )
        assert stake == pytest.approx(25.00)

    def test_cap_is_applied(self):
        # edge = 0.55*2.0 - 1 = 0.10 (10%); f* = 0.10
        # raw stake = 1000 * 0.10 * 0.25 = 25; cap = 1000*0.02 = 20 -> capped
        stake = kelly_stake(
            0.55, 2.0, bankroll=1000, fraction=0.25, cap_pct=0.02, edge_threshold=0.03
        )
        assert stake == pytest.approx(20.00)

    def test_stake_is_rounded_to_cents(self):
        # edge = 0.53*2.10 - 1 = 0.113 (11.3%); f* = 0.113/1.10 = 0.10272727...
        # raw stake = 1000 * 0.10272727... * 0.25 = 25.68181818... -> rounds to 25.68
        stake = kelly_stake(
            0.53, 2.10, bankroll=1000, fraction=0.25, cap_pct=0.10, edge_threshold=0.03
        )
        assert stake == pytest.approx(25.68)

    def test_rejects_negative_bankroll(self):
        with pytest.raises(ValueError):
            kelly_stake(0.6, 1.8, bankroll=-100)

    def test_rejects_invalid_fraction(self):
        with pytest.raises(ValueError):
            kelly_stake(0.6, 1.8, bankroll=1000, fraction=0)
        with pytest.raises(ValueError):
            kelly_stake(0.6, 1.8, bankroll=1000, fraction=1.5)

    def test_rejects_invalid_cap_pct(self):
        with pytest.raises(ValueError):
            kelly_stake(0.6, 1.8, bankroll=1000, cap_pct=0)


class TestCLV:
    def test_positive_clv(self):
        # Took 2.10, closed at a devigged 2.00 -> beat the closing line by 5%.
        assert clv(2.10, 2.00) == pytest.approx(0.05)

    def test_zero_clv(self):
        assert clv(2.00, 2.00) == pytest.approx(0.0)

    def test_negative_clv(self):
        assert clv(1.90, 2.00) == pytest.approx(-0.05)

    def test_rejects_invalid_odds(self):
        with pytest.raises(ValueError):
            clv(0.9, 2.0)
        with pytest.raises(ValueError):
            clv(2.0, 1.0)
