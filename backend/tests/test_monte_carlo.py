"""Monte Carlo simulator tests — deterministic via seed, plus a perf budget check."""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from app.services.monte_carlo import (
    DistributionBucket,
    MonteCarloInputs,
    run_simulation,
)

D = Decimal


class TestInputsValidation:
    def test_zero_simulations_rejected(self) -> None:
        with pytest.raises(ValueError):
            MonteCarloInputs(
                historical_pnls=[D("1")], starting_bankroll=D("100"),
                n_simulations=0, horizon_trades=10,
            )

    def test_zero_horizon_rejected(self) -> None:
        with pytest.raises(ValueError):
            MonteCarloInputs(
                historical_pnls=[D("1")], starting_bankroll=D("100"),
                n_simulations=10, horizon_trades=0,
            )

    def test_zero_starting_bankroll_rejected(self) -> None:
        with pytest.raises(ValueError):
            MonteCarloInputs(
                historical_pnls=[D("1")], starting_bankroll=D("0"),
                n_simulations=10, horizon_trades=10,
            )

    def test_ruin_threshold_out_of_range_rejected(self) -> None:
        with pytest.raises(ValueError):
            MonteCarloInputs(
                historical_pnls=[D("1")], starting_bankroll=D("100"),
                n_simulations=10, horizon_trades=10,
                ruin_threshold_pct=D("150"),
            )

    def test_too_few_buckets_rejected(self) -> None:
        with pytest.raises(ValueError):
            MonteCarloInputs(
                historical_pnls=[D("1")], starting_bankroll=D("100"),
                n_simulations=10, horizon_trades=10, n_buckets=1,
            )


class TestDegenerateInputs:
    def test_empty_history_returns_flat_distribution(self) -> None:
        inputs = MonteCarloInputs(
            historical_pnls=[],
            starting_bankroll=D("1000"),
            n_simulations=100, horizon_trades=10,
        )
        out = run_simulation(inputs)
        assert out.risk_of_ruin_pct == D("0")
        assert out.p10_ending_bankroll == D("1000.00")
        assert out.p50_ending_bankroll == D("1000.00")
        assert out.p90_ending_bankroll == D("1000.00")
        assert out.distribution == [
            DistributionBucket(D("1000.00"), D("1000.00"), 100)
        ]


class TestDeterministic:
    def test_uniform_winning_history_never_ruins(self) -> None:
        # Every drawn pnl is +10 → ending = starting + 10*horizon, no ruin possible.
        inputs = MonteCarloInputs(
            historical_pnls=[D("10")],
            starting_bankroll=D("1000"),
            n_simulations=200, horizon_trades=50,
            seed=42,
        )
        out = run_simulation(inputs)
        assert out.risk_of_ruin_pct == D("0.0000")
        # Ending bankroll deterministic at 1500
        assert out.p10_ending_bankroll == D("1500.00")
        assert out.p50_ending_bankroll == D("1500.00")
        assert out.p90_ending_bankroll == D("1500.00")

    def test_uniform_losing_history_always_ruins(self) -> None:
        # Every draw is -50; horizon=20 → cum = -1000 reaches the 50%-loss
        # ruin floor (500) after 10 trades for sure.
        inputs = MonteCarloInputs(
            historical_pnls=[D("-50")],
            starting_bankroll=D("1000"),
            n_simulations=100, horizon_trades=20,
            ruin_threshold_pct=D("50"),
            seed=7,
        )
        out = run_simulation(inputs)
        assert out.risk_of_ruin_pct == D("100.0000")
        assert out.p50_ending_bankroll == D("0.00")  # 1000 - 20*50 = 0

    def test_seeded_run_is_reproducible(self) -> None:
        kwargs = dict(
            historical_pnls=[D("10"), D("-12"), D("5")],
            starting_bankroll=D("1000"),
            n_simulations=500, horizon_trades=30,
            seed=12345,
        )
        a = run_simulation(MonteCarloInputs(**kwargs))  # type: ignore[arg-type]
        b = run_simulation(MonteCarloInputs(**kwargs))  # type: ignore[arg-type]
        assert a == b

    def test_percentile_ordering(self) -> None:
        inputs = MonteCarloInputs(
            historical_pnls=[D("20"), D("-10"), D("5"), D("-15")],
            starting_bankroll=D("1000"),
            n_simulations=300, horizon_trades=40,
            seed=99,
        )
        out = run_simulation(inputs)
        assert out.p10_ending_bankroll <= out.p50_ending_bankroll <= out.p90_ending_bankroll
        assert out.min_ending_bankroll <= out.p10_ending_bankroll
        assert out.p90_ending_bankroll <= out.max_ending_bankroll

    def test_n_simulations_one_uses_single_value_for_all_percentiles(self) -> None:
        # Hits the n==1 branch in the percentile interpolator.
        inputs = MonteCarloInputs(
            historical_pnls=[D("5")],
            starting_bankroll=D("1000"),
            n_simulations=1, horizon_trades=10,
            seed=1,
        )
        out = run_simulation(inputs)
        assert out.p10_ending_bankroll == out.p50_ending_bankroll == out.p90_ending_bankroll
        assert out.min_ending_bankroll == out.max_ending_bankroll

    def test_uniform_constant_returns_collapses_to_single_bucket(self) -> None:
        # All endings identical → histogram returns one zero-width bucket.
        inputs = MonteCarloInputs(
            historical_pnls=[D("5")],
            starting_bankroll=D("1000"),
            n_simulations=50, horizon_trades=10,
            seed=1,
        )
        out = run_simulation(inputs)
        assert len(out.distribution) == 1
        assert out.distribution[0].count == 50

    def test_distribution_bucket_count_matches_n_buckets(self) -> None:
        inputs = MonteCarloInputs(
            historical_pnls=[D("3"), D("-2"), D("1")],
            starting_bankroll=D("100"),
            n_simulations=200, horizon_trades=20,
            n_buckets=8, seed=1,
        )
        out = run_simulation(inputs)
        assert len(out.distribution) == 8
        # Each bucket count is non-negative; sum equals n_simulations.
        total = sum(b.count for b in out.distribution)
        assert total == 200


class TestPerformance:
    """Spec target: 10k simulations × 100 trades in <2s on the dev machine."""

    def test_10k_sims_under_2_seconds(self) -> None:
        inputs = MonteCarloInputs(
            historical_pnls=[D("3"), D("-2"), D("1"), D("-1.5"), D("4")],
            starting_bankroll=D("1000"),
            n_simulations=10_000, horizon_trades=100,
            seed=1,
        )
        t0 = time.perf_counter()
        out = run_simulation(inputs)
        elapsed = time.perf_counter() - t0
        # Generous CI margin — local dev usually clocks ~0.7-1.2s.
        assert elapsed < 2.0, f"Monte Carlo too slow: {elapsed:.2f}s"
        assert out.n_simulations == 10_000
        assert out.horizon_trades == 100
