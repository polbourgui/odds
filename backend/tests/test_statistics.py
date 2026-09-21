import pytest

from app.core.statistics import (
    confidence_interval_mean,
    max_drawdown,
    mean,
    stdev,
    wilson_score_interval,
)


class TestMean:
    def test_known_values(self):
        assert mean([1, 2, 3, 4]) == pytest.approx(2.5)

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            mean([])


class TestStdev:
    def test_known_values(self):
        # Sample stdev (n-1) of [2, 4, 4, 4, 5, 5, 7, 9] is 2.13809...
        assert stdev([2, 4, 4, 4, 5, 5, 7, 9]) == pytest.approx(2.13809, abs=1e-5)

    def test_rejects_fewer_than_two_values(self):
        with pytest.raises(ValueError):
            stdev([1.0])


class TestConfidenceIntervalMean:
    def test_known_case(self):
        values = [0.1, 0.2, -0.05, 0.15, 0.0]
        lower, upper = confidence_interval_mean(values)
        assert lower == pytest.approx(-0.010879791287680504)
        assert upper == pytest.approx(0.1708797912876805)

    def test_interval_narrows_with_larger_sample(self):
        small = confidence_interval_mean([0.1, 0.2, 0.0])
        large = confidence_interval_mean([0.1, 0.2, 0.0] * 20)
        assert (large[1] - large[0]) < (small[1] - small[0])

    def test_rejects_fewer_than_two_values(self):
        with pytest.raises(ValueError):
            confidence_interval_mean([0.1])

    def test_rejects_unsupported_confidence_level(self):
        with pytest.raises(ValueError):
            confidence_interval_mean([0.1, 0.2], confidence=0.5)


class TestWilsonScoreInterval:
    def test_known_case_15_of_20(self):
        lower, upper = wilson_score_interval(15, 20)
        assert lower == pytest.approx(0.531299122381256)
        assert upper == pytest.approx(0.8881382985923343)

    def test_perfect_record_stays_within_bounds(self):
        lower, upper = wilson_score_interval(1, 1)
        assert 0.0 <= lower <= upper <= 1.0
        assert upper == pytest.approx(1.0)

    def test_interval_narrows_with_larger_sample_same_ratio(self):
        small = wilson_score_interval(8, 10)
        large = wilson_score_interval(800, 1000)
        assert (large[1] - large[0]) < (small[1] - small[0])

    def test_rejects_successes_out_of_range(self):
        with pytest.raises(ValueError):
            wilson_score_interval(11, 10)
        with pytest.raises(ValueError):
            wilson_score_interval(-1, 10)

    def test_rejects_non_positive_n(self):
        with pytest.raises(ValueError):
            wilson_score_interval(0, 0)


class TestMaxDrawdown:
    def test_known_case(self):
        curve = [1000, 1100, 900, 950, 1200]
        assert max_drawdown(curve) == pytest.approx(200 / 1100)

    def test_monotonically_increasing_curve_has_zero_drawdown(self):
        assert max_drawdown([100, 150, 200, 300]) == pytest.approx(0.0)

    def test_monotonically_decreasing_curve(self):
        assert max_drawdown([1000, 500, 250]) == pytest.approx(0.75)

    def test_rejects_empty_curve(self):
        with pytest.raises(ValueError):
            max_drawdown([])
